"""Step 3 tests: /ws pushes the election state to every connected page."""
import asyncio
import signal
import time

import pytest
from fastapi.testclient import TestClient

from app import config, db, realtime
from app.main import app

PASSWORD = "correct horse battery"
RIGHT = {"X-Admin-Password": PASSWORD}


@pytest.fixture(autouse=True)
def no_hanging(request):
    """If a test waits for a message that never comes, fail after 10 seconds
    instead of freezing the whole test run (not available on Windows)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def give_up(signum, frame):
        raise TimeoutError("waited 10 seconds for a WebSocket message that never came")

    signal.signal(signal.SIGALRM, give_up)
    signal.alarm(10)
    yield
    signal.alarm(0)


@pytest.fixture
def laptop(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    # One client for both the admin calls and the sockets, so they share one event loop,
    # like the real server does.
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c


def admin(client, step):
    return client.post(f"/admin/{step}", headers=RIGHT)


def test_a_new_page_is_told_the_current_state_at_once(laptop):
    with laptop.websocket_connect("/ws") as page:
        assert page.receive_json() == {"state": "IDLE"}


def test_a_page_that_connects_late_gets_the_state_it_missed(laptop):
    admin(laptop, "open")
    with laptop.websocket_connect("/ws") as page:
        assert page.receive_json() == {"state": "OPEN"}


def test_a_phone_may_connect(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    with TestClient(app, client=("192.168.10.57", 50000)) as phone:
        with phone.websocket_connect("/ws") as page:
            assert page.receive_json() == {"state": "IDLE"}


def test_every_connected_page_hears_every_step_in_order(laptop):
    with laptop.websocket_connect("/ws") as a, laptop.websocket_connect("/ws") as b:
        assert a.receive_json() == b.receive_json() == {"state": "IDLE"}
        for step, state in (("open", "OPEN"), ("close", "CLOSED"), ("reveal", "RESULTS")):
            assert admin(laptop, step).status_code == 200
            assert a.receive_json() == {"state": state}
            assert b.receive_json() == {"state": state}


def test_a_refused_step_sends_nothing(laptop):
    with laptop.websocket_connect("/ws") as page:
        page.receive_json()                       # IDLE
        admin(laptop, "open")
        assert page.receive_json() == {"state": "OPEN"}
        assert admin(laptop, "open").status_code == 409   # pressed twice: refused
        admin(laptop, "close")
        # The very next message is CLOSED. If the refused press had sent anything
        # we would see a second OPEN here first.
        assert page.receive_json() == {"state": "CLOSED"}


def test_a_page_that_left_does_not_break_the_others(laptop):
    with laptop.websocket_connect("/ws") as stayer:
        stayer.receive_json()
        with laptop.websocket_connect("/ws") as leaver:
            leaver.receive_json()
        # `leaver` is gone now. The admin must still be able to open, and the other page hears it.
        assert admin(laptop, "open").status_code == 200
        assert stayer.receive_json() == {"state": "OPEN"}


def test_what_a_page_sends_is_ignored(laptop):
    with laptop.websocket_connect("/ws") as page:
        page.receive_json()
        page.send_text("hello")
        page.send_bytes(b"\x00\x01")
        admin(laptop, "open")
        assert page.receive_json() == {"state": "OPEN"}


def test_the_message_holds_only_the_state(laptop):
    # No counts, no names: it is public and goes to every phone (SPEC A7).
    with laptop.websocket_connect("/ws") as page:
        assert set(page.receive_json()) == {"state"}


def test_a_restart_forgets_old_connections(laptop):
    from app.realtime import broadcaster
    with laptop.websocket_connect("/ws") as page:
        page.receive_json()
        assert len(broadcaster.clients) == 1
    broadcaster.reset()
    assert len(broadcaster.clients) == 0


# ---- a broken or frozen phone must not hold up everybody else ----------------

class FakeSocket:
    """Stands in for a phone. behaviour: "good", "broken" or "frozen"."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.received = []

    async def send_json(self, data):
        if self.behaviour == "broken":
            raise RuntimeError("connection is gone")
        if self.behaviour == "frozen":
            await asyncio.sleep(60)          # never accepts the message
        self.received.append(data)


def test_a_broken_or_frozen_phone_is_dropped_and_the_others_still_hear(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setattr(realtime, "SEND_TIMEOUT_SECONDS", 0.2)
    db.init_db()

    good, broken, frozen = FakeSocket("good"), FakeSocket("broken"), FakeSocket("frozen")
    broadcaster = realtime.Broadcaster()
    broadcaster.clients = {good, broken, frozen}

    started = time.monotonic()
    asyncio.run(broadcaster.broadcast())
    elapsed = time.monotonic() - started

    assert good.received == [{"state": "IDLE"}]          # the healthy phone heard it
    assert broadcaster.clients == {good}                 # the other two were dropped
    assert elapsed < 2                                   # and nobody waited a minute for the frozen one
