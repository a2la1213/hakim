# tests/test_dream_state.py
"""Snapshot/neutralisation d'état — le jumeau garde la mémoire, perd l'affect."""
import affect
import dream_lab
import migrations
from memory import Memory

import json
import pytest


@pytest.fixture
def mem(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_snapshot_shape(mem):
    st = dream_lab.snapshot_state(mem, now=1_000_000.0)
    assert set(st["hormones"]) == set(affect.HORMONES)
    assert -1.0 <= st["valence"] <= 1.0 and 0.0 <= st["arousal"] <= 1.0
    assert isinstance(st["humeur"], str) and isinstance(st["wm_focus"], list)


def test_snapshot_reads_wm_focus(mem):
    mem.kv_set("working_memory", json.dumps(
        {"focus": [{"id": 4, "score": 0.9}, {"id": 7, "score": 0.5}], "halo": [], "updated_ts": 1.0}))
    st = dream_lab.snapshot_state(mem, now=1_000_000.0)
    assert st["wm_focus"] == [4, 7]


def test_neutralize_baselines_but_keeps_memory(mem):
    affect.event(mem, "succes", 1.0)                     # état chaud ≠ baseline
    st = dream_lab.snapshot_state(mem)
    st["wm_focus"] = [4, 7]
    tw = dream_lab.neutralize(st)
    for h, (base, _hl) in affect.HORMONES.items():       # affect → baselines exactes
        assert tw["hormones"][h] == pytest.approx(base)
    assert tw["humeur"] == "neutre"
    assert tw["wm_focus"] == [4, 7]                      # la mémoire de travail RESTE
    assert st["hormones"]["dopamine"] > tw["hormones"]["dopamine"]  # le réel était chaud


def test_state_block_same_template(mem):
    st = dream_lab.snapshot_state(mem)
    blk_real, blk_twin = dream_lab.state_block(st), dream_lab.state_block(dream_lab.neutralize(st))
    # même GABARIT (mêmes libellés/structure) : seules les valeurs diffèrent
    assert blk_real.split(":")[0] == blk_twin.split(":")[0]
    assert "dopamine" in blk_real and "dopamine" in blk_twin
