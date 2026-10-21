"""Souvenirs périmés (2026-10-16) : avec actuel=True, l'état le plus récent passe devant l'ancien.
Mesuré sur la vraie base (eval/supersession_bench.py) : 3/5 → 5/5 ; sur 60 questions historiques,
le rappel à 6 est inchangé (60/60) mais le 1er rang tombe de 47 à 27 : d'où un MODE explicite
(actuel), jamais appliqué par défaut."""
import memory


def _r(score, ts, role, eid):
    return (score, ts, role, f"souvenir {eid}", {"rel": 0.3}, eid)


def test_le_plus_recent_d_abord_et_l_ancien_marque():
    scored = [_r(1.15, 1000, "semantic", 1), _r(0.99, 1100, "reasoning", 2), _r(0.97, 5000, "semantic", 3),
              _r(0.80, 2000, "episodic", 4), _r(0.70, 9000, "semantic", 5)]
    top = memory.supersession_rang(scored, 4)
    ids = [r[5] for r in top]
    assert ids[0] == 3 and ids.index(3) < ids.index(1)                 # le plus récent de la bande d'abord
    assert ids[1] == 2                                                  # un raisonnement garde sa place
    ancien = next(r for r in top if r[5] == 1)
    assert ancien[4]["anterieur_a"] == 5000
    assert 5 not in ids                                                 # hors bande (score trop bas)


def test_le_plus_recent_hors_du_top_y_entre():
    scored = [_r(1.0, 1000, "semantic", 1), _r(0.95, 1100, "dream", 2), _r(0.9, 1200, "insight", 3),
              _r(0.85, 9000, "semantic", 4)]
    ids = [r[5] for r in memory.supersession_rang(scored, 3)]
    assert ids[0] == 4 and 1 in ids and len(ids) == 3


def test_rien_ne_change_sans_second_souvenir_d_etat():
    scored = [_r(1.0, 1000, "semantic", 1), _r(0.95, 9000, "insight", 2), _r(0.9, 9500, "dream", 3)]
    assert memory.supersession_rang(scored, 3) == scored[:3]


def test_l_etat_actuel_regarde_au_moins_douze_souvenirs(monkeypatch, tmp_path):
    """Lot E, point 3 (mesure du 2026-10-19) : à 6 résultats, l'état à jour n'était trouvé que 5 fois sur 9 ;
    à 12, 8 fois sur 9."""
    import memory as _memory
    import migrations as _migrations
    m = _memory.Memory(db_path=tmp_path / "m.db")
    _migrations.migrate(m.db)
    monkeypatch.setattr(_memory, "Memory", lambda *a, **k: m)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", m)
    vus = []
    monkeypatch.setattr(mcp_server, "_embed", lambda q: None)
    monkeypatch.setattr(mcp_server._mem, "retrieve", lambda q, e, top_k=6, **kw: vus.append((top_k, kw.get("supersession"))) or [])
    mcp_server.memory_recall("où en est Jarvis ?", actuel=True)
    mcp_server.memory_recall("qu'avait-on décidé le 30 septembre ?")
    assert vus == [(12, True), (6, False)]
