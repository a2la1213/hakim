"""L'audit de l'existant (validé par Ahmed le 2026-10-20) : les tours passés qui ont lu un contenu de tiers sont
retrouvés dans les transcriptions (heure et noms d'outils seulement), et leurs souvenirs marqués, descendance comprise."""
import json
import time

import audit_provenance as A
import memory
import migrations
import rubrics


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"


def test_tours_et_marquage(tmp_path, monkeypatch):
    t0 = time.mktime((2026, 10, 18, 15, 0, 0, 0, 0, -1))
    lignes = [
        {"type": "user", "timestamp": _iso(t0), "message": {"content": "lis cette page"}},
        {"type": "assistant", "timestamp": _iso(t0 + 5), "message": {"content": [{"type": "tool_use", "name": "mcp__web__lire_page", "input": {}}]}},
        {"type": "user", "timestamp": _iso(t0 + 9), "message": {"content": [{"type": "tool_result", "content": "x"}]}},
        {"type": "assistant", "timestamp": _iso(t0 + 20), "message": {"content": [{"type": "text", "text": "ok"}]}},
        {"type": "user", "timestamp": _iso(t0 + 600), "message": {"content": "et sinon ?"}},
        {"type": "assistant", "timestamp": _iso(t0 + 610), "message": {"content": [{"type": "tool_use", "name": "mcp__terminal__executer", "input": {"commande": "ls"}}]}},
        {"type": "user", "timestamp": _iso(t0 + 1200), "message": {"content": "télécharge"}},
        {"type": "assistant", "timestamp": _iso(t0 + 1210), "message": {"content": [{"type": "tool_use", "name": "mcp__terminal__executer", "input": {"commande": "curl -O https://x.org/f"}}]}},
    ]
    d = tmp_path / "transcriptions"
    d.mkdir()
    (d / "s.jsonl").write_text("\n".join(json.dumps(l) for l in lignes))
    tours = A.tours_externes(d)
    assert [o for _a, _b, o in tours] == [["mcp__web__lire_page"], ["terminal (réseau)"]]
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    lu = m.add("episodic", f"[Échange avec Ahmed — {time.strftime('%a %d/%m %H:%M', time.localtime(t0 + 20))}] Ahmed : « lis » · Hakim : « la page dit… »", embedding=[])
    calme = m.add("episodic", f"[Échange avec Ahmed — {time.strftime('%a %d/%m %H:%M', time.localtime(t0 + 605))}] Ahmed : « et sinon ? »", embedding=[])
    note = m.add("semantic", "Hakim : la page dit X", embedding=[])
    fait = m.add("semantic", "Ahmed croit X", embedding=[])
    m.db.execute("INSERT INTO insight_edges (insight_id, source_id) VALUES (?,?)", (fait, lu))
    m.db.commit()
    ev = tmp_path / "ev.jsonl"
    ev.write_text(json.dumps({"type": "memoire", "source": "hakim", "ts": t0 + 15, "donnees": {"id": note}}) + "\n")
    c = A.candidats(m.db, tours, evenements=ev)
    assert set(c) == {lu, note}
    assert sorted(A.avec_descendance(m.db, list(c))) == sorted([lu, note, fait]) and calme not in c
