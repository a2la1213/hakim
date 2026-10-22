"""Les sensations calculées par le code depuis les 13 hormones (sensations.py, 2026-10-22), sans Gemma."""
import sensations as S


def test_les_etats_typiques_donnent_l_emotion_attendue():
    b = S.bases(14)
    cas = {"inquiétude": dict(b, cortisol=.55, noradrenaline=.5, dopamine=.3, crh=.5, acth=.4, gaba=.35),
           "tristesse": dict(b, ocytocine=.2, dopamine=.35, serotonine=.5, endorphine=.2, noradrenaline=.2),
           "somnolence": dict(b, melatonine=.7, acetylcholine=.2, gaba=.85, endocannabinoides=.6)}
    for attendu, etat in cas.items():
        assert S.calculer(etat, None, 1000.0, None, 14)["emotion"] == attendu, attendu
    alarme = dict(b, adrenaline=.6, noradrenaline=.7, cortisol=.4)
    assert S.calculer(alarme, None, 1000.0, "alarme", 14)["emotion"] == "peur"
    resolu = dict(b, cortisol=.15, noradrenaline=.25, dopamine=.7, endorphine=.6, endocannabinoides=.65)
    avant = dict(resolu, cortisol=.45, noradrenaline=.45)
    assert S.calculer(resolu, avant, 1000.0, None, 14)["emotion"] == "soulagement"        # la TENDANCE compte


def test_stable_quinze_minutes_et_jamais_vide():
    b = S.bases(14)
    e = dict(b, dopamine=.8, endorphine=.6)
    x, y, z = (S.calculer(e, None, t, None, 14)["mots"] for t in (900.0, 1700.0, 1801.0))
    assert x == y and x
    neutre = S.calculer(b, None, 0.0, None, 14)
    assert neutre["emotion"] and neutre["mots"]


def test_la_voix_suit_l_emotion_moderement():
    import interieur as I
    assert I.voix(0.6, {"emotion": "lassitude"}) == {"expressivite": 0.5, "vitesse": 0.94, "emotion": "lassitude"}
    assert I.voix(0.76, {"emotion": "élan"})["expressivite"] == 0.78                    # jamais au-delà de 0,78
    assert I.voix(0.36, {"emotion": "tristesse"})["expressivite"] == 0.35               # ni en dessous de 0,35
    assert I.voix(0.5, None) == {"expressivite": 0.5, "vitesse": 1.0, "emotion": None}
