"""Al-Afida par les sous-couches (28/10, tâche 2) : la grande jauge règle les freins (GABA, endocannabinoïdes) ; une chose
indifférente touche moins les hormones, sauf la voie rapide de la peur ; la reconnaissance réchauffe sans valence."""
import json

import affect

T0 = 1_800_000_000.0
MIDI = 12.0


class _Mem:
    def __init__(self, afida=None):
        self._kv = {"affect_v2": "1"}
        if afida is not None:
            self._kv["afida"] = json.dumps(afida)

    def kv_get(self, k, d=None):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def _kv(plenitude=0.0, indifferent=()):
    return {"grande": (plenitude + 1) / 2, "plenitude": plenitude, "petites": [], "aime_pas": [],
            "indifferent": [{"chose": c, "liens": [c]} for c in indifferent]}


def _suite(m):
    affect.event(m, "probleme", 0.6, now=T0, hour=MIDI, sujet="projets/x")
    affect.event(m, "soutien", 0.5, now=T0 + 600, hour=MIDI, sujet="soutien de ahmed")
    return affect.get_state(m, now=T0 + 3600, hour=MIDI)


def test_temoin_sans_afida_identique():
    assert _suite(_Mem()) == _suite(_Mem(_kv(0.0))) and affect.plenitude(_Mem()) == 0.0
    assert affect.plenitude(_Mem(_kv(0.4))) == 0.4
    m = _Mem(); m._kv["afida"] = "pas du json"
    assert affect.plenitude(m) == 0.0


def test_plenitude_monte_les_freins():
    temoin, plein, vide = _Mem(), _Mem(_kv(1.0)), _Mem(_kv(-1.0))
    for m in (temoin, plein, vide):
        affect.event(m, "nouveaute", 0.1, now=T0, hour=MIDI)
    s = {k: affect.get_state(m, now=T0 + 12 * 3600, hour=MIDI) for k, m in (("t", temoin), ("p", plein), ("v", vide))}
    for h in ("gaba", "endocannabinoides"):
        assert s["p"][h] > s["t"][h] + 0.01 and s["v"][h] < s["t"][h] - 0.01, h


def test_amour_plein_amortit_un_probleme():
    """30 min après un problème, le stress est plus bas quand le cœur est plein, plus haut quand il est vide."""
    stress = {}
    for k, kv in (("t", None), ("p", _kv(1.0)), ("v", _kv(-1.0))):
        m = _Mem(kv)
        affect.event(m, "nouveaute", 0.1, now=T0, hour=MIDI)
        affect.event(m, "probleme", 0.8, now=T0 + 6 * 3600, hour=MIDI, sujet="projets/x")
        stress[k] = affect.get_state(m, now=T0 + 6 * 3600 + 1800, hour=MIDI)
    for h in ("noradrenaline", "crh", "cortisol"):
        assert stress["p"][h] < stress["t"][h] < stress["v"][h], (h, {k: v[h] for k, v in stress.items()})


def test_indifference_moins_d_impact_sauf_danger():
    t, i = _Mem(), _Mem(_kv(0.0, indifferent=["la télé"]))
    a = affect.get_state(t, now=T0, hour=MIDI)["ocytocine"]
    st = affect.event(t, "soutien", 0.5, now=T0, hour=MIDI, sujet="soutien de la télé")["ocytocine"]
    si = affect.event(i, "soutien", 0.5, now=T0, hour=MIDI, sujet="soutien de la télé")["ocytocine"]
    assert abs((si - a) / (st - a) - affect.AFIDA_INDIFFERENCE) < 0.05
    # un danger se sent en entier : la voie rapide (adrénaline d'un sujet nouveau) ne baisse pas
    t2, i2 = _Mem(), _Mem(_kv(0.0, indifferent=["la télé"]))
    at = affect.event(t2, "attaque", 0.8, now=T0, hour=MIDI, sujet="attaque de la télé")["adrenaline"]
    ai = affect.event(i2, "attaque", 0.8, now=T0, hour=MIDI, sujet="attaque de la télé")["adrenaline"]
    rapide = affect._appliquer(affect.HORMONES_V2["adrenaline"][0], affect.RAPIDE_ADR * 0.8, affect.HORMONES_V2["adrenaline"][0])
    assert ai >= rapide - 1e-9 and ai < at


def test_reconnaissance_rechauffe_sans_valence():
    m = _Mem()
    avant = affect.get_state(m, now=T0, hour=MIDI)
    apres = affect.event(m, "reconnaissance", 0.4, now=T0, hour=MIDI, sujet="reconnaissance de ahmed")
    assert apres["ocytocine"] > avant["ocytocine"] and apres["gaba"] > avant["gaba"]
    assert "reconnaissance" not in affect.VALENCE_EV
    d = json.loads(m.kv_get("affect"))
    assert "_vm" not in d and "_surprise" not in d                      # ni attente ni surprise de récompense
