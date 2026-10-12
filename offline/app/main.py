from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import db, tokens

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app):
    db.init_db()   # runs once when the server starts
    yield


app = FastAPI(title="School Election Server", lifespan=lifespan)


@app.get("/")
def voter_page():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def api_state():
    return {"state": db.get_state()}


@app.get("/api/candidates")
def api_candidates():
    # Candidates are only shown while voting is OPEN. The server enforces this,
    # not the browser: hiding the buttons in JavaScript is not security.
    if db.get_state() != "OPEN":
        raise HTTPException(status_code=403, detail="Voting is not open")
    return {"candidates": db.list_candidates()}


class TokenCheck(BaseModel):
    # max_length stops someone sending a huge string just to waste our time.
    token: str = Field(max_length=64)


@app.post("/api/token/check")
def api_token_check(body: TokenCheck):
    # Stateless pre-check (SPEC section 6): we only look, we do not burn the token
    # and we remember nothing about who asked. The real check happens again
    # when the vote is sent.
    if db.get_state() not in ("IDLE", "OPEN"):
        raise HTTPException(status_code=403, detail="Token checking is closed")
    # "Wrong" and "already used" give the same answer, so a guesser learns nothing extra.
    return {"valid": db.token_is_usable(tokens.hash_token(body.token))}
