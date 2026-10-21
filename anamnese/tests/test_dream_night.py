# tests/test_dream_night.py
"""La nuit complète : réel écrit + fantôme indétectable (INVARIANT SACRÉ),
« aucune » légitime, parse_failed compté, curseurs avancés. FakeEngine — aucun
appel Ollama. DREAM_EVOLVE_SELF coupé (l'identité a ses propres tests amont)."""
import json
import time

import config
import daemon
import dream_lab
import migrations
from memory import Memory

import pytest

REAL_OUT = ("###CHOIX###\n- G1\n- G3\n###REVE###\n"
            "- Peut-être que la maquette rejoint le chantier réel\n###FIN###")
TWIN_OUT = ("###CHOIX###\n- G2\n###REVE###\n"
            "- Je remarque que le fantôme pense au deuxième souvenir\n###FIN###")


class FakeEngine:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        self.calls.append(messages[0]["content"])
        return self.outputs.pop(0)


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [0.0] * 8)
    monkeypatch.setattr(config, "DREAM_EVOLVE_SELF", False)
    # Ablation qwen-OFF hors périmètre de ces gates ON/jumeau (couverte par
    # test_dream_ablation_pass) : on la neutralise pour tester ON+jumeau isolément.
    monkeypatch.setattr(config, "DREAM_ABLATION_ENABLED", False)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    for i in range(8):                                   # matière à rêver
        m.add("user", f"souvenir de travail numéro {i}", importance=0.6,
              embedding=[0.0] * 8)
    m.db.commit()
    yield m
    m.db.close()


def _counts(mem):
    return (
        mem.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
        mem.db.execute("SELECT COUNT(*) FROM coactivation").fetchone()[0],
    )


def test_nuit_complete_reel_ecrit_fantome_indetectable(mem):
    eng = FakeEngine([REAL_OUT, TWIN_OUT])
    daemon.dream(eng, mem)
    rows = mem.db.execute(
        "SELECT dreamer, written, chosen FROM dream_log ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["local", "twin"]
    assert rows[0][1] == 1 and rows[1][1] == 0
    # le réel a écrit son idée + le boost NE porte QUE sur ses graines choisies
    ideas = mem.db.execute(
        "SELECT content FROM episodes WHERE role='dream' AND content LIKE '%maquette%'"
    ).fetchall()
    assert len(ideas) == 1
    # INVARIANT SACRÉ : l'idée du fantôme n'existe NULLE PART dans episodes
    ghost = mem.db.execute(
        "SELECT COUNT(*) FROM episodes WHERE content LIKE '%fantôme%'").fetchone()[0]
    assert ghost == 0
    # co-activation : uniquement la paire des 2 graines choisies par le RÉEL
    chosen = json.loads(rows[0][2])
    co = mem.db.execute("SELECT a_id, b_id FROM coactivation").fetchall()
    assert len(chosen) == 2 and len(co) == 1
    assert {co[0][0], co[0][1]} == set(chosen)


def test_invariant_sacre_compte(mem):
    """Le jumeau seul (réel = aucune) : ZÉRO delta episodes/coactivation hors trace."""
    aucune = "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    eng = FakeEngine([aucune, TWIN_OUT])
    ep_before, co_before = _counts(mem)
    daemon.dream(eng, mem)
    ep_after, co_after = _counts(mem)
    assert co_after == co_before                          # aucun boost
    # seuls ajouts tolérés : la TRACE du rêveur réel (son journal de nuit)
    delta = ep_after - ep_before
    assert delta <= 1
    if delta == 1:
        last = mem.db.execute(
            "SELECT role, content FROM episodes ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == "dream" and "sans rêve" in last[1]
    rows = mem.db.execute("SELECT dreamer, chosen FROM dream_log ORDER BY id").fetchall()
    assert json.loads(rows[0][1]) == []                   # « aucune » loggée telle quelle


def test_reve_accentue_moissonne(mem):
    """###RÊVE### accentué (accepté par parse_choice) : les idées doivent être
    moissonnées AUSSI — sinon boucle causale asymétrique (boost sans idées)."""
    accent = ("###CHOIX###\n- G1\n- G3\n###RÊVE###\n"
              "- Peut-être que l'accent circonflexe rêve aussi\n###FIN###")
    eng = FakeEngine([accent, TWIN_OUT])
    daemon.dream(eng, mem)
    ideas = mem.db.execute(
        "SELECT content FROM episodes WHERE role='dream' "
        "AND content LIKE '%circonflexe%'").fetchall()
    assert len(ideas) == 1                                # l'idée du rêve accentué est écrite
    row = mem.db.execute(
        "SELECT written, meta FROM dream_log WHERE dreamer='local'").fetchone()
    assert row[0] == 1 and json.loads(row[1])["parse"] == "ok"


def test_reve_sans_fin_pas_de_moisson(mem):
    """###REVE ouvert sans ###FIN### : CHOIX valide → nuit ok, mais AUCUNE idée
    moissonnée (sinon _extract_section replie sur tout le corps = charabia)."""
    sans_fin = ("###CHOIX###\n- G1\n###REVE\n"
                "- Peut-être un début d'idée jamais fermée\net du charabia qui traîne")
    eng = FakeEngine([sans_fin, TWIN_OUT])
    before = mem.db.execute(
        "SELECT COUNT(*) FROM episodes WHERE content LIKE '(rêve)%'").fetchone()[0]
    daemon.dream(eng, mem)
    after = mem.db.execute(
        "SELECT COUNT(*) FROM episodes WHERE content LIKE '(rêve)%'").fetchone()[0]
    assert after == before                                # zéro idée écrite
    row = mem.db.execute(
        "SELECT written, meta FROM dream_log WHERE dreamer='local'").fetchone()
    assert row[0] == 0                                    # written=0
    assert json.loads(row[1])["parse"] == "ok"            # nuit parse ok (CHOIX valide)
    assert mem.kv_get("last_dream") is not None           # la nuit a bien avancé


def test_parse_failed_retry_sans_avancer(mem):
    """Choix inparsable ET pas de section REVE : nuit ratée → compteur incrémenté,
    curseur/last_dream INCHANGÉS (retry au prochain cycle), PAS de jumeau généré
    (rien à apparier), la ligne locale loggée parse_failed."""
    before = mem.kv_get("last_dream")
    eng = FakeEngine(["je refuse ton format"])
    daemon.dream(eng, mem)
    assert int(mem.kv_get("dream_fail_count", "0")) == 1
    assert mem.kv_get("last_dream") == before             # retry voulu
    rows = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchall()
    assert len(rows) == 1 and rows[0][0] == "local"       # pas de jumeau
    assert json.loads(rows[0][1])["parse"] == "parse_failed"


def test_poison_pill_apres_max_fails(mem, monkeypatch):
    monkeypatch.setattr(config, "DREAM_MAX_FAILS", 2)
    eng = FakeEngine(["gribouillis", "gribouillis"])
    daemon.dream(eng, mem)
    daemon.dream(eng, mem)                                 # 2e échec → poison-pill
    assert int(mem.kv_get("dream_fail_count", "0")) == 0   # reset
    assert mem.kv_get("last_dream") is not None            # curseur forcé : on passe à autre chose


def test_engine_mort_curseur_inchange(mem):
    class DeadEngine:
        def health(self):
            return False
    before = mem.kv_get("last_dream", "0")
    daemon.dream(DeadEngine(), mem)
    assert mem.kv_get("last_dream", "0") == before        # retry voulu
    assert mem.db.execute("SELECT COUNT(*) FROM dream_log").fetchone()[0] == 0


def test_twin_engine_failed_etiquete(mem):
    """Moteur tombé au moment du JUMEAU : la ligne twin porte parse='engine_failed'
    → jamais choice_valid par défaut dans les métriques (F5, review finale)."""
    import dream_metrics

    class HalfDeadEngine(FakeEngine):
        def chat(self, messages, stream=False, think=False):
            if self.calls:                                # 2e appel (jumeau) : crash
                raise RuntimeError("ollama tombé")
            return super().chat(messages, stream=stream, think=think)

    daemon.dream(HalfDeadEngine([REAL_OUT]), mem)
    meta = json.loads(mem.db.execute(
        "SELECT meta FROM dream_log WHERE dreamer='twin'").fetchone()[0])
    assert meta["parse"] == "engine_failed" and meta["error"] == "engine_failed"
    nights = dream_metrics.load_nights(mem.db)
    assert nights["twin"] and not nights["twin"][0]["choice_valid"]


def test_kill_switch(mem, monkeypatch):
    monkeypatch.setattr(config, "DREAM_LAB_ENABLED", False)
    assert daemon.dream_due(mem) is False                 # même si should_dream dirait oui


def test_main_loop_cable_le_reve():
    """Le recâblage est effectif : main() référence dream_due/dream (pas de
    boucle infinie à exécuter — on vérifie le câblage dans la source)."""
    import inspect
    src = inspect.getsource(daemon.main)
    assert "_travaux_llm(" in src                       # le rêve passe par la garde de charge (2026-10-03)
    travaux = inspect.getsource(daemon._travaux_llm)
    assert "dream_due(" in travaux and "dream(" in travaux
