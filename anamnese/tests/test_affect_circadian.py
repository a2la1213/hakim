"""Phase 4b — circadien (cortisol/melatonine = f(heure)) + melatonine + eCB.

Ajouts validés-reproduits (audit), HORS-RAPPEL :
  * baselines circadiennes (cortisol pic ~8h, melatonine pic nocturne ~2-4h) ;
  * mélatonine = marqueur SCN nocturne ; endocannabinoïdes = frein + extinction.

Contraintes vérifiées ici :
  * baseline circadien calculé À LA VOLÉE (jamais persisté → l'heure n'est pas figée) ;
  * repli propre sur baselines statiques si `circadian` indisponible (100% offline) ;
  * contrat get_state = 9 clés floats ; valence/arousal NE lisent PAS melatonine/eCB.

Tous les tests injectent hour/now explicites → aucun time.localtime() réel (anti-flaky).
On NE touche PAS Memory.retrieve.
"""

import json

import affect
from modules.proposed import circadian


NOW = 1_700_000_000.0          # instant fixe injecté partout
OLD = NOW - 100 * 3600.0       # 100 h avant NOW → décroissance quasi complète


class _FakeMem:
    """kv en RAM — pas de DB, pas d'I/O (respecte la garde conftest)."""

    def __init__(self):
        self._kv = {}

    def kv_get(self, key, default=None):
        return self._kv.get(key, default)

    def kv_set(self, key, value):
        self._kv[key] = value


def _mem_blob(levels, ts=NOW):
    """FakeMem avec un blob affect explicite (niveaux + _ts)."""
    m = _FakeMem()
    data = dict(levels)
    data["_ts"] = ts
    m.kv_set("affect", json.dumps(data))
    return m


# --- Cas 1 : baselines_now — forme circadienne pure ---------------------------
def test_baselines_now_forme_circadienne():
    # Cortisol : plus haut le matin (~8h) qu'en pleine nuit (0h).
    assert circadian.baselines_now(8.0)["cortisol"] > circadian.baselines_now(0.0)["cortisol"]
    # Mélatonine : plus haute la nuit (2h) que l'après-midi (14h).
    assert circadian.baselines_now(2.0)["melatonine"] > circadian.baselines_now(14.0)["melatonine"]
    # Sorties dans [0,1].
    for h in (0.0, 3.0, 8.0, 14.0, 21.0, 23.5):
        b = circadian.baselines_now(h)
        assert 0.0 <= b["cortisol"] <= 1.0
        assert 0.0 <= b["melatonine"] <= 1.0
    # Lisse : pas de saut brutal sur un pas fin, y compris le wrap 24h→0h.
    h = 0.0
    while h < 24.0:
        a = circadian.baselines_now(h)
        c = circadian.baselines_now((h + 0.25) % 24.0)
        assert abs(c["cortisol"] - a["cortisol"]) < 0.05
        assert abs(c["melatonine"] - a["melatonine"]) < 0.05
        h += 0.25


# --- Cas 2 : get_state avec heure injectée → cible de decay circadienne --------
def test_get_state_decay_vers_baseline_circadien():
    # Cortisol part de 0.2, très vieux → converge vers la baseline circadienne.
    m = _mem_blob({"cortisol": 0.2, "melatonine": 0.2}, ts=OLD)
    s8 = affect.get_state(m, now=NOW, hour=8.0)
    s0 = affect.get_state(m, now=NOW, hour=0.0)
    # À 8h : cortisol attiré vers une baseline HAUTE ; à minuit vers une BASSE.
    assert s8["cortisol"] > s0["cortisol"]
    # Convergence effective vers la baseline circadienne (decay ~complet).
    assert abs(s8["cortisol"] - circadian.baselines_now(8.0)["cortisol"]) < 0.02
    assert abs(s0["cortisol"] - circadian.baselines_now(0.0)["cortisol"]) < 0.02
    # Mélatonine INVERSE : plus haute à minuit qu'à 8h.
    assert s0["melatonine"] > s8["melatonine"]


# --- Cas 3 : baseline circadien JAMAIS persisté -------------------------------
def test_baseline_circadien_non_persiste():
    m = _mem_blob({"cortisol": 0.2, "melatonine": 0.2}, ts=OLD)
    before = m.kv_get("affect")
    s_matin = affect.get_state(m, now=NOW, hour=8.0)
    s_nuit = affect.get_state(m, now=NOW, hour=2.0)
    # Deux heures → deux cibles de decay différentes pour cortisol ET mélatonine.
    assert s_matin["cortisol"] != s_nuit["cortisol"]
    assert s_matin["melatonine"] != s_nuit["melatonine"]
    # Le blob kv n'a PAS été muté par les lectures (heure non figée dedans).
    assert m.kv_get("affect") == before
    # Aucune baseline circadienne n'a été écrite : le blob ne contient que
    # les niveaux d'origine + _ts (pas de champ d'heure/baseline figé).
    assert set(json.loads(before)) == {"cortisol", "melatonine", "_ts"}


# --- Cas 4 : repli propre si circadian indisponible ---------------------------
def test_repli_propre_baselines_statiques(monkeypatch):
    def boom(name, *a, **k):
        raise ImportError("circadian indisponible (test)")

    monkeypatch.setattr(affect.importlib, "import_module", boom)
    m = _mem_blob({"cortisol": 0.2, "melatonine": 0.2}, ts=OLD)
    # Ne lève pas, contrat 9 clés tenu.
    s = affect.get_state(m, now=NOW, hour=8.0)
    assert len(s) == 9
    # Repli : cortisol converge vers la baseline STATIQUE (0.2), pas circadienne (~0.35).
    assert abs(s["cortisol"] - affect.HORMONES["cortisol"][0]) < 0.02
    assert abs(s["cortisol"] - circadian.baselines_now(8.0)["cortisol"]) > 0.05


# --- Cas 5 : contrat get_state (9 clés float, blob partiel toléré) ------------
def test_get_state_contrat_9_cles():
    # Sans blob : 9 baselines (cortisol/melatonine circadiens, autres statiques).
    s = affect.get_state(_FakeMem(), now=NOW, hour=8.0)
    assert set(s) == set(affect.HORMONES)
    assert len(s) == 9
    assert all(isinstance(s[h], float) for h in affect.HORMONES)
    assert "melatonine" in s and "endocannabinoides" in s
    # Blob PARTIEL (melatonine/eCB absents) : complété par les baselines.
    m = _mem_blob({"dopamine": 0.9}, ts=OLD)
    sp = affect.get_state(m, now=NOW, hour=8.0)
    assert set(sp) == set(affect.HORMONES)
    assert all(isinstance(sp[h], float) for h in affect.HORMONES)
    # eCB absent → converge vers sa baseline statique constante.
    assert abs(sp["endocannabinoides"] - affect.HORMONES["endocannabinoides"][0]) < 0.02
    # melatonine absente → converge vers sa baseline circadienne courante.
    assert abs(sp["melatonine"] - circadian.baselines_now(8.0)["melatonine"]) < 0.02


# --- Cas 6 : EVENT extinction (resolu augmente les endocannabinoïdes) ---------
def test_event_resolu_augmente_ecb():
    m = _mem_blob({"endocannabinoides": 0.4}, ts=NOW)
    before = affect.get_state(m, now=NOW, hour=8.0)["endocannabinoides"]
    affect.event(m, "resolu", now=NOW, hour=8.0)
    after = affect.get_state(m, now=NOW, hour=8.0)["endocannabinoides"]
    assert after > before


# --- Cas 7 : valence/arousal & salience INCHANGÉS par melatonine/eCB ----------
def test_valence_salience_ignorent_melatonine_ecb():
    core = {h: b for h, (b, _) in affect.HORMONES.items()
            if h not in ("melatonine", "endocannabinoides")}
    state7 = dict(core, melatonine=0.05, endocannabinoides=0.05)
    state9 = dict(core, melatonine=0.95, endocannabinoides=0.95)
    # valence_arousal ne lit ni melatonine ni eCB → strictement identique.
    assert affect.valence_arousal(state7) == affect.valence_arousal(state9)
    # salience_boost non plus (même cœur, melatonine/eCB extrêmes différents).
    m_lo = _mem_blob(dict(core, melatonine=0.05, endocannabinoides=0.05), ts=NOW)
    m_hi = _mem_blob(dict(core, melatonine=0.95, endocannabinoides=0.95), ts=NOW)
    assert (affect.salience_boost(m_lo, now=NOW, hour=8.0)
            == affect.salience_boost(m_hi, now=NOW, hour=8.0))
