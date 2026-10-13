"""Pushes the election state to every connected voter page (WebSocket).

How it works: each voter page keeps one WebSocket open to /ws. When the admin
presses Open, Close or Reveal, we send the new state to all of them at once, so
every screen changes at the same moment.

IMPORTANT: this list of connections lives in the memory of ONE server process.
Run uvicorn as a single process (never --workers), or some voters would never
hear about a change.

PRIVACY: we keep only the open connections themselves. We never write down who
connected, from which address, or when (AGENTS.md rule 2). The one thing we
cannot control from here is uvicorn's own log, see the run command in README.
"""
import asyncio

from app import db

# A phone that does not accept a message within this many seconds is dropped,
# so one stuck phone cannot delay the message to everybody else.
SEND_TIMEOUT_SECONDS = 2


class Broadcaster:
    def __init__(self):
        self.reset()

    def reset(self):
        """Forget all connections. Called when the server starts."""
        self.clients = set()
        # Created here (not at import time) so it belongs to the running server.
        self.lock = asyncio.Lock()

    async def _send_state(self, ws):
        """Send the current state to one client. A client that fails is dropped."""
        try:
            await asyncio.wait_for(
                ws.send_json({"state": db.get_state()}), SEND_TIMEOUT_SECONDS
            )
        except Exception:
            # Phone went away, is too slow, or broke the connection. Forget it.
            self.clients.discard(ws)

    async def connect(self, ws):
        """Accept a new voter page and tell it the current state right away."""
        await ws.accept()
        # Under the lock, so a new page can never be told an OLD state after a
        # broadcast has already told it the NEW one.
        async with self.lock:
            self.clients.add(ws)
            await self._send_state(ws)

    def disconnect(self, ws):
        self.clients.discard(ws)

    async def broadcast(self):
        """Tell every connected page what the database says the state is now.

        We send what the database says at this moment, not a value somebody
        remembered, so a page can never be left showing an older state.
        """
        async with self.lock:
            await asyncio.gather(*(self._send_state(ws) for ws in list(self.clients)))


broadcaster = Broadcaster()
