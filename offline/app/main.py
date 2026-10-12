from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import db

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
