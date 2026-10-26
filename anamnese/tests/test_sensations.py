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
    assert I.voix(0.6, {"emotion": "lassitude"}) == {"expressivite": 0.5, "vitesse": 0.9, "emotion": "lassitude"}
    assert I.voix(0.96, {"emotion": "élan"})["expressivite"] == 1.0                     # (26/10) jamais au-delà de 1,0
    assert I.voix(0.36, {"emotion": "tristesse"})["expressivite"] == 0.3                # ni en dessous de 0,3
    # (26/10, 13:30) la peur s'entend, sans caricature : l'écart à la voix neutre est divisé par deux
    assert 1.02 < I.voix_emotion("peur")["vitesse"] < 1.06 and 0.6 <= I.voix_emotion("peur")["expressivite"] <= 0.75
    assert 0.9 < I.voix_emotion("fatigue")["vitesse"] < 0.98
    assert I.voix(0.5, None) == {"expressivite": 0.5, "vitesse": 1.0, "emotion": None}
