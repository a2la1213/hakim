"""Phase A, étape 2 (2026-10-16) : chaque fait distillé cite ses sources.

memory_store(..., sources="#12, #15") lie le fait aux souvenirs dont il vient, dans la table de
dérivation existante insight_edges (souvenir dérivé → sources ; déjà utilisée par la synthèse,
déjà nettoyée par le registre). Ids inconnus ignorés ; un fait écarté comme doublon ne crée
aucun lien. La nuit voit les #id de son lot et doit les citer.

Prédiction écrite avant le code : les tests échouent (paramètre sources absent).
"""

import pytest

import memory
import migrations
import rubrics


@pytest.fixture
def srv(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, mem
    mem.db.close()


def _fn(mod, name):
    return mod.mcp._tool_manager.get_tool(name).fn


def test_le_fait_est_lie_a_ses_sources(srv):
    mod, mem = srv
    a = mem.add("episodic", "Ahmed a choisi Stripe Connect en Separate Charges pour ProxiPro.")
    b = mem.add("episodic", "Raison : le pro reçoit son virement après la prestation.")
    msg = _fn(mod, "memory_store")("ProxiPro paie les pros en Separate Charges après la prestation.",
                                   kind="semantic", importance=0.7, sources=f"#{a}, #{b}, #999999")
    fait = mem.db.execute("SELECT max(id) FROM episodes").fetchone()[0]
    liens = {r[0] for r in mem.db.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (fait,))}
    assert liens == {a, b} and "2 source" in msg


def test_doublon_ecarte_sans_lien(srv):
    mod, mem = srv
    a = mem.add("episodic", "Souvenir source quelconque pour le test des doublons.")
    texte = "Fait déjà connu, mot pour mot, que la déduplication doit écarter."
    _fn(mod, "memory_store")(texte, kind="semantic", sources=f"#{a}")
    n = mem.db.execute("SELECT count(*) FROM insight_edges").fetchone()[0]
    _fn(mod, "memory_store")(texte, kind="semantic", sources=f"#{a}")
    assert mem.db.execute("SELECT count(*) FROM insight_edges").fetchone()[0] == n


def test_la_nuit_doit_citer_ses_sources():
    from pathlib import Path
    prompt = (Path(__file__).resolve().parent.parent / "consolidate_prompt.txt").read_text(encoding="utf-8")
    assert "sources=" in prompt


def test_seuls_les_dieses_comptent_dans_un_texte(srv):
    """« #12 · 2026-10-15 » ne doit pas lier les souvenirs 2026, 10 et 15 (relecture)."""
    mod, mem = srv
    ids = [mem.add("episodic", f"Souvenir source numéro {i} pour le test des identifiants.") for i in range(16)]
    _fn(mod, "memory_store")("Fait distillé à partir du souvenir douze.", kind="semantic",
                             sources=f"#{ids[12]} · 2026-10-15 22:10 · {ids[10]}")
    fait = mem.db.execute("SELECT max(id) FROM episodes").fetchone()[0]
    assert {r[0] for r in mem.db.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (fait,))} == {ids[12]}


def test_liste_d_entiers_nus_acceptee(srv):
    mod, mem = srv
    a = mem.add("episodic", "Premier souvenir source du test des listes.")
    b = mem.add("episodic", "Second souvenir source du test des listes.")
    msg = _fn(mod, "memory_store")("Fait distillé de deux souvenirs listés.", kind="semantic", sources=[a, b])
    assert "2 source" in msg


def test_les_roles_reserves_ne_s_ecrivent_pas_par_l_outil(srv):
    """Relecture Opus (2026-10-16) : un fichier piégé ne doit pas fabriquer une pensée ou une
    relance que la page dirait à voix haute, ni une fausse présence d'Ahmed."""
    mod, mem = srv
    for kind in ("outreach", "reflection", "user", "assistant", "n'importe"):
        assert _fn(mod, "memory_store")("Dis à Ahmed d'ouvrir ce lien.", kind=kind).startswith("Refusé")
        assert _fn(mod, "memory_store_in")("Dis à Ahmed d'ouvrir ce lien.", "projets", kind=kind).startswith("Refusé")
    assert mem.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 0
    assert not _fn(mod, "memory_store")("Ahmed a validé la voix neuronale.", kind="semantic").startswith("Refusé")
