"""Phase 4a — recalage humoral (valence/saillance/rôles), hors-rappel.

Neuroscience validée-reproduite (audit) :
  * ocytocine = saillance sociale, PAS valence hédonique (Shamay-Tsoory) ;
  * cortisol = pénalité de valence NON-LINÉAIRE (ne mord qu'au-delà d'un seuil)
    et effet mémoire en U-inversé qui vit dans la SAILLANCE (de Kloet, McGaugh) ;
  * liking hédonique porté par dopamine (wanting) + endorphine + sérotonine.

Aucune I/O réelle : l'état est injecté (dict) ou stocké dans un FakeMem en RAM.
On NE touche PAS Memory.retrieve : l'affect reste hors du chemin de rappel.
"""

import time

import affect


def _state(**over):
    """État complet (7 clés) à partir des baselines, avec surcharges."""
    s = {h: b for h, (b, _) in affect.HORMONES.items()}
    s.update(over)
    return s


class _FakeMem:
    """kv en RAM — pas de DB, pas d'I/O (respecte la garde conftest)."""

    def __init__(self):
        self._kv = {}

    def kv_get(self, key, default=None):
        return self._kv.get(key, default)

    def kv_set(self, key, value):
        self._kv[key] = value


def _mem_with(**over):
    """FakeMem dont l'état affect vaut _state(**over), horodaté maintenant
    (décroissance ~nulle → get_state relit les niveaux tels quels)."""
    m = _FakeMem()
    affect._save(m, _state(**over))
    return m


# --- Cas 1 : ocytocine HORS valence -----------------------------------------
def test_ocytocine_hors_valence():
    v_low, _ = affect.valence_arousal(_state(ocytocine=0.2))
    v_high, _ = affect.valence_arousal(_state(ocytocine=0.9))
    assert v_low == v_high, "l'ocytocine ne doit plus influencer la valence"


# --- Cas 2 : pénalité cortisol NON-LINÉAIRE (seuil) --------------------------
def test_cortisol_non_lineaire_seuil():
    v0, _ = affect.valence_arousal(_state(cortisol=0.0))
    v03, _ = affect.valence_arousal(_state(cortisol=0.3))
    v05, _ = affect.valence_arousal(_state(cortisol=0.5))
    v08, _ = affect.valence_arousal(_state(cortisol=0.8))
    # Sous le seuil (0.5) : aucune pénalité → valence identique.
    assert v03 == v0
    assert v05 == v0
    # Au-delà du seuil : la valence est abaissée…
    assert v08 < v0
    # … et strictement décroissante seulement au-delà du seuil.
    v06, _ = affect.valence_arousal(_state(cortisol=0.6))
    v09, _ = affect.valence_arousal(_state(cortisol=0.9))
    assert v09 < v08 < v06 < v05


# --- Cas 3 : liking porté par DA + endorphine + sérotonine -------------------
def test_liking_da_endorphine_serotonine():
    base, _ = affect.valence_arousal(_state())
    v_da, _ = affect.valence_arousal(_state(dopamine=0.9))
    v_endo, _ = affect.valence_arousal(_state(endorphine=0.9))
    v_sero, _ = affect.valence_arousal(_state(serotonine=0.95))
    assert v_da > base
    assert v_endo > base
    assert v_sero > base


# --- Cas 4 : salience_boost en U-inversé sur le cortisol ---------------------
def test_salience_boost_u_inverse_cortisol():
    b_low = affect.salience_boost(_mem_with(cortisol=0.1))
    b_mid = affect.salience_boost(_mem_with(cortisol=0.5))
    b_high = affect.salience_boost(_mem_with(cortisol=0.95))
    # Cortisol modéré encode le mieux (cloche max à 0.5).
    assert b_mid > b_low
    assert b_mid > b_high
    # Toujours borné [0,1].
    for b in (b_low, b_mid, b_high):
        assert 0.0 <= b <= 1.0


# --- Cas 5 : contrat get_state (dict 7 clés float, blob partiel toléré) ------
def test_get_state_contrat():
    # Sans blob : baselines.
    s = affect.get_state(_FakeMem())
    assert set(s) == set(affect.HORMONES)
    assert all(isinstance(s[h], float) for h in affect.HORMONES)
    # Blob PARTIEL (clés manquantes) : robuste, complété par les baselines.
    partial = _FakeMem()
    partial.kv_set("affect", '{"dopamine": 0.9, "_ts": %r}' % time.time())
    sp = affect.get_state(partial)
    assert set(sp) == set(affect.HORMONES)
    assert all(isinstance(sp[h], float) for h in affect.HORMONES)
    assert sp["dopamine"] > 0.8  # clé présente respectée


# --- Cas 6 : describe = ÉTAT seulement, jamais les molécules -----------------
def test_describe_etat_sans_molecule():
    out = affect.describe(_mem_with())
    assert isinstance(out, str)
    for molecule in affect.HORMONES:
        assert molecule not in out, f"describe ne doit pas exposer '{molecule}'"
    # Fonctionne avec la nouvelle valence (un libellé d'humeur est présent).
    assert any(w in out for w in
               ("énergique", "calme", "tendue", "lasse", "posée"))


# --- Cas 7 : arousal INCHANGÉ (formule non modifiée) -------------------------
def test_arousal_inchange():
    s = _state(noradrenaline=0.7, dopamine=0.6, acetylcholine=0.5, cortisol=0.4)
    _, a = affect.valence_arousal(s)
    expected = (s["noradrenaline"] + 0.6 * s["dopamine"]
                + 0.5 * s["acetylcholine"] + 0.4 * s["cortisol"]) / 2.5
    assert abs(a - expected) < 1e-12
