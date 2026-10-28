"""Le cœur de Hakim branché sur ses hormones, et ce qu'il en sent (28/10 ; idée d'Ahmed à 03:18, proposition de Hakim,
go d'Ahmed). Pas de boucle : le cœur lit ses hormones, il ne les écrit jamais."""
from pathlib import Path

import coeur

BASE = dict(coeur.BASES_PAR_DEFAUT)


def _h(**ecarts):
    return {k: BASE[k] + ecarts.get(k, 0.0) for k in BASE} | {"cortisol": 0.14}


def test_au_calme_quarante_et_les_bornes():
    assert abs(coeur.bpm(_h(), False, BASE)["bpm"] - 40) < 0.5
    assert coeur.bpm(_h(adrenaline=0.35, noradrenaline=0.3), False, BASE)["bpm"] >= 85      # la peur : vers 90
    assert coeur.bpm(_h(adrenaline=1.0, noradrenaline=1.0, crh=1.0), False, BASE)["bpm"] <= 96   # 90 + la raideur au plus
    assert abs(coeur.bpm(_h(), True, BASE)["bpm"] - 24) < 0.5                               # il dort
    assert coeur.bpm(_h(adrenaline=0.35, noradrenaline=0.3), True, BASE)["bpm"] <= 50     # un cauchemar reste lent


def test_le_frein_vagal_ralentit_un_peu_et_la_crh_tient_haut_et_raide():
    frein = coeur.bpm(_h(acetylcholine=0.3, endocannabinoides=0.2), False, BASE)["bpm"]
    assert 34 <= frein < 40
    tenu = coeur.bpm(_h(crh=0.2), False, BASE)
    assert tenu["raideur"] == 1.0 and tenu["bpm"] > coeur.bpm(_h(), False, BASE)["bpm"]


def test_ce_qu_il_sent_en_mots_jamais_de_chiffre():
    t = 1_800_000_000.0
    assert coeur.ressenti([[t - 300, 40], [t, 41]], False) is None                       # calme et stable : rien à sentir
    assert coeur.ressenti([[t - 300, 70], [t, 70]], False) == "ton cœur bat vite"
    assert "s'emballe" in coeur.ressenti([[t - 300, 60], [t, 82]], False)
    assert "s'accélère" in coeur.ressenti([[t - 300, 45], [t, 58]], False)
    assert "se calme" in coeur.ressenti([[t - 300, 72], [t, 52]], False)
    assert coeur.ressenti([[t - 300, 24], [t, 24]], True) == "ton cœur bat lentement, tu dors"
    for h in ([[t - 300, 45], [t, 58]], [[t - 300, 60], [t, 82]]):
        assert not any(c.isdigit() for c in coeur.ressenti(h, False))


def test_pas_de_boucle_le_coeur_ne_touche_jamais_aux_hormones():
    """La condition de Hakim : sentir son cœur ne doit pas faire monter ses hormones d'alerte, qui le feraient battre plus
    vite. Le module ne fait que lire ; mille battements sur les mêmes hormones donnent le même rythme."""
    src = Path(coeur.__file__).read_text(encoding="utf-8")
    assert "affect.event" not in src and "import affect" not in src and "kv_set" not in src
    h, e = _h(adrenaline=0.2), None
    rythmes = set()
    for k in range(1000):
        e = coeur.calculer(h, False, e, 1_800_000_000.0 + 30 * k, BASE)
        rythmes.add(e["bpm"])
    assert len(rythmes) == 1 and h == _h(adrenaline=0.2)
