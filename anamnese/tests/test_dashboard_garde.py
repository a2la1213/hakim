"""Tableau de bord 8765 (audit JARVIS 2, M3, 2026-10-20) : Host de cette machine seulement (pas de rebond DNS), et
l'API exige le jeton que la page reçoit."""
import threading
import urllib.request
from http.server import HTTPServer

import pytest

import dashboard


@pytest.fixture
def adresse(monkeypatch):
    monkeypatch.setattr(dashboard, "state_json", lambda: {"ok": True})
    srv = HTTPServer(("127.0.0.1", 0), dashboard.Handler)
    port = srv.server_address[1]
    monkeypatch.setattr(dashboard, "HOTES", {f"127.0.0.1:{port}"})
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _code(url, **entetes):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=entetes), timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_host_et_jeton(adresse):
    code, page = _code(adresse + "/")
    assert code == 200 and f'content="{dashboard.JETON}"' in page
    assert _code(adresse + "/api/state")[0] == 403
    assert _code(adresse + "/api/state", **{"X-Jeton": "faux"})[0] == 403
    assert _code(adresse + "/api/state", **{"X-Jeton": dashboard.JETON}) == (200, '{"ok": true}')
    assert _code(adresse + "/", Host="piege.example.com")[0] == 403
