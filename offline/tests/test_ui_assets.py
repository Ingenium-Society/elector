"""Tests for the school logo and the two HTML pages that show it.

The logo is served by one dedicated route (/logo.png). The static folder is NOT
mounted as a whole, because that would also publish admin.html to every phone.
"""
import struct

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def voter(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    with TestClient(app) as c:  # a normal phone on the Wi-Fi
        yield c


@pytest.fixture
def admin_laptop(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    with TestClient(app, client=("127.0.0.1", 50000)) as c:  # the server laptop
        yield c


def test_logo_is_served_as_a_square_png(voter):
    response = voter.get("/logo.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    data = response.content
    assert data.startswith(PNG_SIGNATURE)
    # Width and height are the first two numbers inside the PNG header chunk.
    width, height = struct.unpack(">II", data[16:24])
    assert width == height
    assert len(data) < 100_000  # small enough for 120 phones loading at once


def test_voter_page_shows_the_logo(voter):
    html = voter.get("/").text
    assert 'src="/logo.png"' in html
    assert "School Election" in html


def test_admin_page_shows_the_logo_and_uses_no_internet_links(admin_laptop):
    html = admin_laptop.get("/admin").text
    assert 'src="/logo.png"' in html
    assert "http://" not in html
    assert "https://" not in html


def test_admin_page_is_still_local_only(voter):
    assert voter.get("/admin").status_code == 403


def test_static_folder_is_not_published(voter):
    # If someone mounts /static, admin.html would leak to the whole network.
    assert voter.get("/static/admin.html").status_code == 404
    assert voter.get("/static/index.html").status_code == 404
