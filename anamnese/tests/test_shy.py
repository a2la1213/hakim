"""Tests du downscaling synaptique SHY (Phase R2) — Memory.synaptic_downscale.

Contrepoids global de la reconsolidation R1 (Tononi & Cirelli, Synaptic
Homeostasis Hypothesis) : pendant le rêve, l'importance des épisodes est
renormalisée à la baisse — factor_i = SHY_FACTOR + (1-SHY_FACTOR) *
min(1, recall_count/SHY_PROTECT), new = max(floor, floor + (imp-floor)*factor_i).
« Use it or lose it » : recall_count >= SHY_PROTECT immunise ; recall_count = 0
décroît pleinement ; jamais en dessous de SHY_FLOOR.

DB temporaire migrée — JAMAIS data/memory.db (garde autouse dans conftest.py).
Tout est offline et déterministe.
"""

import pytest

import config
import daemon
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (colonne recall_count présente)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _ep(mem, importance, recall_count=0, content="souvenir de test"):
    """Insère un épisode avec importance/recall_count contrôlés ; retourne son id."""
    eid = mem.add("semantic", content, importance=importance,
                  embedding=[1.0, 0.0], extract_facets=False)
    mem.db.execute("UPDATE episodes SET recall_count=? WHERE id=?",
                   (recall_count, eid))
    mem.db.commit()
    return eid


def _imp(mem, eid):
    return mem.db.execute(
        "SELECT importance FROM episodes WHERE id=?", (eid,)
    ).fetchone()[0]


# --- Cas 1 : décroissance pleine à rc=0, immunité à rc>=PROTECT, plancher inerte ---
def test_downscale_basic(mem):
    full = _ep(mem, 0.8, recall_count=0, content="jamais rappelé")
    prot = _ep(mem, 0.8, recall_count=config.SHY_PROTECT, content="souvent rappelé")
    at_floor = _ep(mem, config.SHY_FLOOR, recall_count=0, content="déjà au plancher")

    n = mem.synaptic_downscale()

    # rc=0 : factor_i = SHY_FACTOR, new = floor + (0.8 - floor) * SHY_FACTOR
    assert _imp(mem, full) == pytest.approx(
        config.SHY_FLOOR + (0.8 - config.SHY_FLOOR) * config.SHY_FACTOR
    )
    assert _imp(mem, full) == pytest.approx(0.1 + 0.7 * 0.97)
    # rc >= PROTECT : factor_i = 1.0, STRICTEMENT inchangé (protégé)
    assert _imp(mem, prot) == 0.8
    # importance == floor : inchangé (plancher)
    assert _imp(mem, at_floor) == config.SHY_FLOOR
    # nombre d'épisodes MODIFIÉS : seul `full` a bougé
    assert n == 1


# --- Cas 2 : rank-préservation à recall_count égal ---
def test_rank_preservation_equal_recall_count(mem):
    imps = [0.9, 0.7, 0.5, 0.3, 0.15]
    eids = [_ep(mem, i, recall_count=0, content=f"souvenir {k}")
            for k, i in enumerate(imps)]
    order_before = [eid for _, eid in
                    sorted(((_imp(mem, e), e) for e in eids), reverse=True)]

    mem.synaptic_downscale()

    after = [(_imp(mem, e), e) for e in eids]
    order_after = [eid for _, eid in sorted(after, reverse=True)]
    assert order_after == order_before          # ordre relatif conservé
    # et strictement : pas d'égalisation (la carte affine est injective)
    vals = sorted((v for v, _ in after), reverse=True)
    assert all(a > b for a, b in zip(vals, vals[1:]))


# --- Cas 3 : convergence — répété, tend vers le plancher SANS passer dessous ---
def test_convergence_to_floor(mem):
    eid = _ep(mem, 0.9, recall_count=0)
    for _ in range(500):
        mem.synaptic_downscale()
        assert _imp(mem, eid) >= config.SHY_FLOOR   # jamais en dessous, à CHAQUE cycle
    assert _imp(mem, eid) == pytest.approx(config.SHY_FLOOR, abs=1e-4)


# --- Cas 4 : protection — un fort recall_count ne s'effondre pas ---
def test_protection_high_recall(mem):
    protected = _ep(mem, 0.85, recall_count=10, content="pilier souvent rappelé")
    partial = _ep(mem, 0.85, recall_count=4, content="rappelé parfois")
    neglected = _ep(mem, 0.85, recall_count=0, content="délaissé")

    for _ in range(20):
        mem.synaptic_downscale()

    assert _imp(mem, protected) == 0.85              # immunisé : ne bouge JAMAIS
    # gradient « use it or lose it » : plus rappelé => décroît moins
    assert _imp(mem, partial) > _imp(mem, neglected)
    assert _imp(mem, partial) > 0.7                  # reste haut
    assert _imp(mem, neglected) >= config.SHY_FLOOR


# --- Cas 5 : legacy — DB sans recall_count => pas d'exception (skip propre) ---
def test_legacy_db_no_recall_count(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    try:
        cols = {r[1] for r in m.db.execute("PRAGMA table_info(episodes)").fetchall()}
        assert "recall_count" not in cols  # bien un schéma d'avant 2.0

        n = m.synaptic_downscale()  # ne lève PAS

        assert isinstance(n, int)
        # skip propre : importances seed intactes, aucune colonne apparue
        assert [r[0] for r in m.db.execute(
            "SELECT importance FROM episodes ORDER BY id"
        ).fetchall()] == [0.5, 0.7]
        cols_after = {r[1] for r in m.db.execute("PRAGMA table_info(episodes)").fetchall()}
        assert cols_after == cols
    finally:
        m.db.close()


# --- Cas 6 : câblage — dream() invoque synaptic_downscale, garde-fous intacts ---
class _FakeEng:
    """Moteur factice OFFLINE : health OK, sorties canoniques en séquence
    (format REM à choix libre : rêve réel puis jumeau fantôme)."""
    def __init__(self, healthy=True):
        self.healthy = healthy
        self.outs = [
            "###CHOIX###\n- G1\n###REVE###\n"
            "- Peut-être que la mémoire SQLite mérite un index dédié\n###FIN###",
            "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###",
        ]
        self.calls = 0

    def health(self):
        return self.healthy

    def chat(self, messages, stream=False, think=False):
        out = self.outs[min(self.calls, len(self.outs) - 1)]
        self.calls += 1
        return out


def _spy_downscale(mem, monkeypatch):
    calls = []
    orig = mem.synaptic_downscale

    def spy(*a, **k):
        calls.append((a, k))
        return orig(*a, **k)

    monkeypatch.setattr(mem, "synaptic_downscale", spy)
    return calls


def test_dream_wires_downscale_and_keeps_guardrails(mem, monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(daemon, "notify",
                        lambda *a, **k: pytest.fail("dream() ne notifie JAMAIS"))
    monkeypatch.setattr(config, "DREAM_EVOLVE_SELF", False)  # identité testée ailleurs
    # matière à rêver (roles user/assistant) + un épisode à renormaliser
    for k in range(3):
        mem.add("user", f"message humain numéro {k} sur la mémoire",
                importance=0.5, embedding=[1.0, 0.0], extract_facets=False)
    target = _ep(mem, 0.8, recall_count=0, content="épisode à renormaliser")
    calls = _spy_downscale(mem, monkeypatch)

    daemon.dream(_FakeEng(), mem)

    # 1) synaptic_downscale invoqué EXACTEMENT une fois par cycle de rêve
    assert len(calls) == 1
    assert _imp(mem, target) == pytest.approx(
        config.SHY_FLOOR + (0.8 - config.SHY_FLOOR) * config.SHY_FACTOR
    )
    # 2) placement : AVANT la génération — l'idée fraîchement rêvée cette
    #    nuit n'est PAS downscalée (importance DREAM_IDEA_IMPORTANCE intacte)
    idea = mem.db.execute(
        "SELECT importance FROM episodes WHERE role='dream' AND content LIKE '%index dédié%'"
    ).fetchone()
    assert idea is not None
    assert idea[0] == config.DREAM_IDEA_IMPORTANCE
    # 3) garde-fous intacts : lock relâché, curseurs avancés, spacing actif
    assert mem.kv_get("dream_lock") == ""
    assert float(mem.kv_get("last_dream", "0")) > 0
    assert int(mem.kv_get("last_dream_maxid", "0")) > 0
    assert mem.kv_get("dream_count") == "1"
    assert daemon.should_dream(mem) is False        # DREAM_MIN_SPACING respecté


def test_dream_health_killswitch_skips_downscale(mem, monkeypatch):
    """Ollama absent => rêve sauté AVANT le downscale (garde-fou conservé)."""
    monkeypatch.setattr(daemon.embeddings, "embed", lambda text: [1.0, 0.0])
    calls = _spy_downscale(mem, monkeypatch)

    daemon.dream(_FakeEng(healthy=False), mem)

    assert calls == []                              # pas de downscale hors cycle
    assert mem.kv_get("dream_lock") in (None, "")   # aucun lock laissé


# --- Cas 7 : garde last_shy — le rêve crashe APRÈS le downscale => PAS de
#     re-downscale au retry ~30s (sinon 0.97^N compound => tout au plancher) ---
class _CrashEng:
    """Moteur factice : health() OK mais chat() lève systématiquement (ex. modèle
    renommé/non tiré => 404 instantané ; Engine.health() ne teste que /api/tags).
    Reproduit le chemin d'échec voulu : out1 is None => last_dream NON écrit =>
    should_dream re-tire au tick suivant (~30s)."""
    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        raise RuntimeError("404: model not found")


def test_dream_crash_after_downscale_no_double_decay(mem, monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(daemon, "notify",
                        lambda *a, **k: pytest.fail("dream() ne notifie JAMAIS"))
    for k in range(3):
        mem.add("user", f"message humain numéro {k} sur la mémoire",
                importance=0.5, embedding=[1.0, 0.0], extract_facets=False)
    target = _ep(mem, 0.8, recall_count=0, content="épisode à ne pas double-décayer")
    calls = _spy_downscale(mem, monkeypatch)

    # Cycle 1 : downscale, PUIS chat lève => rejeu voulu (last_dream non écrit)
    daemon.dream(_CrashEng(), mem)
    assert mem.kv_get("last_dream") is None         # chemin de retry préservé
    # Cycle 2 : retry ~30s plus tard, DANS la fenêtre DREAM_MIN_SPACING
    daemon.dream(_CrashEng(), mem)

    # downscale AU PLUS une fois par fenêtre DREAM_MIN_SPACING
    assert len(calls) == 1
    once = config.SHY_FLOOR + (0.8 - config.SHY_FLOOR) * config.SHY_FACTOR
    assert _imp(mem, target) == pytest.approx(once)     # décayé UNE fois, pas 0.97^2
    # garde-fous existants inchangés : lock relâché, retry toujours possible
    assert mem.kv_get("dream_lock") == ""
    assert mem.kv_get("last_dream") is None
