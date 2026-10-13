import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import db, tokens

STATIC = Path(__file__).parent / "static"


class LiveClients:
    """Keep only active sockets in memory; never persist connection identities."""

    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.connections.add(websocket)
        await send_live_state(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self):
        async with self.lock:
            connections = list(self.connections)
        for websocket in connections:
            try:
                await send_live_state(websocket)
            except Exception:
                await self.disconnect(websocket)


live_clients = LiveClients()


async def send_live_state(websocket: WebSocket):
    # Only aggregate turnout and state are sent. Never broadcast candidate totals.
    payload = {"state": db.get_state(), **db.election_counts()}
    await websocket.send_json(payload)


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    yield


app = FastAPI(title="School Election Server", lifespan=lifespan)


def require_admin(request: Request, supplied_password: str | None):
    """Admin actions are loopback-only and require a configured secret."""
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Admin access is local-only")

    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD is not configured")
    if supplied_password is None or not hmac.compare_digest(supplied_password, expected):
        raise HTTPException(status_code=401, detail="Invalid admin password")


@app.get("/")
def voter_page():
    return FileResponse(STATIC / "index.html")


@app.get("/logo.png")
def logo():
    # Serve only this one file. Do NOT mount the whole static folder: that would also
    # expose admin.html to every device on the Wi-Fi and bypass the local-only check.
    return FileResponse(
        STATIC / "logo.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/admin")
def admin_page(request: Request):
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Admin page is local-only")
    return FileResponse(STATIC / "admin.html")


@app.get("/api/state")
def api_state():
    return {"state": db.get_state()}


@app.get("/api/candidates")
def api_candidates():
    if db.get_state() != "OPEN":
        raise HTTPException(status_code=403, detail="Voting is not open")
    return {"candidates": db.list_candidates()}


class TokenCheck(BaseModel):
    token: str = Field(max_length=64)


@app.post("/api/token/check")
def api_token_check(body: TokenCheck):
    if db.get_state() not in ("IDLE", "OPEN"):
        raise HTTPException(status_code=403, detail="Token checking is closed")
    return {"valid": db.token_is_usable(tokens.hash_token(body.token))}


class Vote(BaseModel):
    token: str = Field(max_length=64)
    candidate_id: int


@app.post("/api/vote")
async def api_vote(body: Vote):
    if db.get_state() != "OPEN":
        raise HTTPException(status_code=403, detail="Voting is not open")
    if not db.candidate_exists(body.candidate_id):
        raise HTTPException(status_code=400, detail="Unknown candidate")

    result = db.cast_vote(tokens.hash_token(body.token), body.candidate_id)
    if result == db.VOTE_NOT_OPEN:
        raise HTTPException(status_code=403, detail="Voting is not open")
    if result == db.VOTE_BAD_TOKEN:
        raise HTTPException(status_code=400, detail="Invalid or already used token")

    await live_clients.broadcast()
    return {"ok": True}


@app.websocket("/ws")
async def websocket_live(websocket: WebSocket):
    await live_clients.connect(websocket)
    try:
        while True:
            # The client sends a tiny keepalive; no client data is stored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await live_clients.disconnect(websocket)
    except Exception:
        await live_clients.disconnect(websocket)


@app.post("/admin/open")
async def admin_open(
    request: Request,
    x_admin_password: str | None = Header(default=None),
):
    require_admin(request, x_admin_password)
    if not db.transition_state("IDLE", "OPEN"):
        raise HTTPException(status_code=409, detail="Voting can only open from IDLE")
    await live_clients.broadcast()
    return {"state": "OPEN"}


@app.post("/admin/close")
async def admin_close(
    request: Request,
    x_admin_password: str | None = Header(default=None),
):
    require_admin(request, x_admin_password)
    if not db.transition_state("OPEN", "CLOSED"):
        raise HTTPException(status_code=409, detail="Voting can only close from OPEN")
    await live_clients.broadcast()
    return {"state": "CLOSED"}


@app.post("/admin/reveal")
async def admin_reveal(
    request: Request,
    x_admin_password: str | None = Header(default=None),
):
    require_admin(request, x_admin_password)
    if not db.transition_state("CLOSED", "RESULTS"):
        raise HTTPException(status_code=409, detail="Results can only be revealed from CLOSED")
    await live_clients.broadcast()
    return {"state": "RESULTS", "results": db.result_totals()}


@app.get("/admin/status")
def admin_status(
    request: Request,
    x_admin_password: str | None = Header(default=None),
):
    require_admin(request, x_admin_password)
    return {"state": db.get_state(), **db.election_counts()}
