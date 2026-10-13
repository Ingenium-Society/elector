"""Admin routes: Open, Close and Reveal the election, and see its status.

Who may use these (AGENTS.md rule 9):
  1. only a request that comes from the server laptop itself (localhost), AND
  2. only with the admin password.
Voters on the Wi-Fi are refused before the password is even looked at.
"""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app import config, db
from app.realtime import broadcaster

# Addresses that mean "this very computer".
LOCAL_ADDRESSES = ("127.0.0.1", "::1")


def require_admin(request: Request, x_admin_password: str = Header(default="")):
    """Runs before every admin route. Raises an error unless everything is in order."""
    # 1. Only the server laptop. Checked first, so a voter's phone learns nothing
    #    else (not even whether an admin password exists).
    client = request.client
    if client is None or client.host not in LOCAL_ADDRESSES:
        raise HTTPException(status_code=403, detail="Admin is only available on the server laptop")

    # 2. No password set on the server: admin stays switched off.
    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Admin is switched off: ADMIN_PASSWORD is not set")

    # 3. The password. It travels in a header, never in the web address, so it
    #    cannot end up in a log. compare_digest takes the same time whether the
    #    first letter or the last letter is wrong.
    if not secrets.compare_digest(x_admin_password.encode(), config.ADMIN_PASSWORD.encode()):
        raise HTTPException(status_code=401, detail="Wrong admin password")


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


async def move_to(new_state):
    """Change the election state and tell every voter page, or answer 409 Conflict
    if that step is not allowed right now (then nothing is sent to anyone)."""
    try:
        db.change_state(new_state)
    except db.BadTransition as problem:
        raise HTTPException(status_code=409, detail=str(problem))
    await broadcaster.broadcast()
    return {"state": new_state}


@router.post("/open")
async def open_voting():
    return await move_to("OPEN")


@router.post("/close")
async def close_voting():
    return await move_to("CLOSED")


@router.post("/reveal")
async def reveal_results():
    return await move_to("RESULTS")


@router.get("/status")
def status():
    # Only totals. Never per-candidate numbers before the election is closed (SPEC A7).
    return {
        "state": db.get_state(),
        "tokens_issued": db.count_tokens(),
        "votes_cast": db.count_votes(),
    }
