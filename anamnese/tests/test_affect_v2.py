"""Affect v2 (2026-10-21, demande d'Ahmed : « des hormones aussi complètes que le robot, sauf les inutiles ») :
adrénaline, GABA, axe CRH → ACTH → cortisol, désensibilisation des récepteurs, habituation sensible à la force.
L'interrupteur (kv affect_v2) laisse l'ancien comportement intact quand il est éteint."""
import affect

T0 = 1_800_000_000.0
MIDI = 12.0


class _Mem:
    def __init__(self, v2=True):
        self._kv = {"affect_v2": "1"} if v2 else {}

    def kv_get(self, k, d=None):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def _ev(m, nom, t, i=1.0):
    return affect.event(m, nom, i, now=t, hour=MIDI)


def _st(m, t):
    return affect.get_state(m, now=t, hour=MIDI)


def test_eteint_rien_ne_change():
    m = _Mem(v2=False)
    s = _ev(m, "echec", T0)
    assert set(s) == set(affect.HORMONES) and "adrenaline" not in s


def test_allume_treize_hormones_et_meme_eveil_au_repos():
    m = _Mem()
    s = _st(m, T0)
    assert set(s) == set(affect.HORMONES) | set(affect.HORMONES_V2)
    v1 = {h: b for h, (b, _) in affect.HORMONES.items()}
    assert abs(affect.valence_arousal(affect.bases(v2=True))[1] - affect.valence_arousal(v1)[1]) < 1e-9


def test_axe_du_stress_retard_du_cortisol_et_sursaut_bref():
    m = _Mem()
    _st(m, T0)
    s0 = _ev(m, "echec", T0)
    base_cort = _st(m, T0)["cortisol"]
    a1, a20 = _st(m, T0 + 60), _st(m, T0 + 20 * 60)
    c45 = _st(m, T0 + 45 * 60)["cortisol"]
    assert a1["adrenaline"] > affect.HORMONES_V2["adrenaline"][0] + 0.2         # le sursaut, tout de suite
    assert a20["adrenaline"] < affect.HORMONES_V2["adrenaline"][0] + 0.05       # retombé en 20 min
    # le cortisol continue de monter après l'événement (la CRH passe par l'ACTH) : plus haut à 45 min qu'à 1 min
    assert c45 > a1["cortisol"] + 0.02 and s0["crh"] > affect.HORMONES_V2["crh"][0] + 0.2


def test_desensibilisation_puis_recuperation():
    m = _Mem()
    t = T0
    premiere = _ev(m, "succes", t)["dopamine"] - affect.HORMONES["dopamine"][0]
    for k in range(20):                                    # vingt succès, un toutes les 10 min
        t += 600
        _ev(m, "succes", t, 0.3)
    avant = _st(m, t + 1)["dopamine"]
    apres = _ev(m, "succes", t + 1)["dopamine"]
    assert apres - avant < 0.6 * premiere                   # moins réactive
    m2 = _Mem()                                           # même histoire, puis 48 h de repos
    t = T0
    for k in range(20):
        t += 600
        _ev(m2, "succes", t, 0.3)
    t += 48 * 3600
    avant = _st(m2, t)["dopamine"]
    assert _ev(m2, "succes", t)["dopamine"] - avant > 0.85 * premiere          # récupérée


def test_habituation_sensible_a_la_force():
    hab = {}
    f1 = affect._habituation(hab, "chaleur_user", 0.3, T0)
    for k in range(10):
        f = affect._habituation(hab, "chaleur_user", 0.3, T0 + 60 * (k + 1))
    assert f1 == 1.0 and f < 0.3                            # la dixième chaleur faible compte peu
    fort = affect._habituation(dict(hab), "chaleur_user", 1.0, T0 + 700)
    assert fort > f + 0.4                                   # une chaleur bien plus forte fait réagir de nouveau
    plus_tard = affect._habituation(dict(hab), "chaleur_user", 0.3, T0 + 600 + 8 * 3600)
    assert plus_tard > 0.9                                  # récupérée en quelques heures
    for k in range(10):                                     # l'ennui est un état : jamais habitué
        assert affect._habituation(hab, "ennui", 1.0, T0 + k) == 1.0


def test_le_gaba_freine_le_sursaut():
    calme, tendu = _Mem(), _Mem()
    for k in range(4):                                       # du réconfort : GABA au-dessus de sa base
        _ev(calme, "chaleur_user", T0 + k * 1800)
    t = T0 + 4 * 1800
    g = _st(calme, t)["gaba"]
    assert g > affect.HORMONES_V2["gaba"][0] + 0.1
    _st(tendu, t)
    hausse_calme = _ev(calme, "nouveaute", t)["adrenaline"] - _st(calme, t - 1)["adrenaline"]
    hausse_tendu = _ev(tendu, "nouveaute", t)["adrenaline"] - affect.HORMONES_V2["adrenaline"][0]
    assert hausse_calme < hausse_tendu


def test_etat_sauve_borne():
    import json
    m = _Mem()
    for k in range(50):
        _ev(m, ["succes", "chaleur_user", "probleme", "resolu"][k % 4], T0 + k * 300)
    d = json.loads(m._kv["affect"])
    assert set(d["_hab"]) <= set(affect.EVENTS) and all(0 <= v <= 1 for v in d["_S"].values())
    assert all(0.0 <= d[h] <= 1.0 for h in list(affect.HORMONES) + list(affect.HORMONES_V2))


def test_detecteur_d_humeur_coincee(tmp_path):
    import json
    import interieur
    m, e, vus = _Mem(), {}, []
    journal = tmp_path / "affect-evenements.jsonl"
    journal.write_text("".join(json.dumps({"ts": T0 + 3600 * k, "nom": "succes"}) + "\n" for k in (1, 2)))
    basse = interieur._BASE_V - 0.3
    assert interieur.surveiller_coincee(m, e, basse, T0, journal, vus.append) is None            # le début
    assert interieur.surveiller_coincee(m, e, basse, T0 + 3 * 3600, journal, vus.append) is None # trop tôt
    t = interieur.surveiller_coincee(m, e, basse, T0 + 7 * 3600, journal, lambda *a, **k: vus.append(a))
    assert t and "coincée" in t and json.loads(m.kv_get("affect_coincee"))["positifs"] == 2 and len(vus) == 1
    assert interieur.surveiller_coincee(m, e, basse, T0 + 8 * 3600, journal, lambda *a, **k: vus.append(a)) is None
    assert len(vus) == 1                                                 # signalée une fois
    interieur.surveiller_coincee(m, e, interieur._BASE_V, T0 + 9 * 3600, journal, vus.append)
    assert not m.kv_get("affect_coincee")                                # remontée : levée
    m1, e1 = _Mem(v2=False), {}
    assert interieur.surveiller_coincee(m1, e1, basse, T0 + 9 * 3600, journal, vus.append) is None   # v1 : rien


# ---- Émotions soudaines (2026-10-21, idée d'Ahmed) : voie rapide, peur apprise et son extinction, surprise ----
def _hausse(m, nom, t, i, sujet, h="adrenaline"):
    avant = _st(m, t)[h]
    return affect.event(m, nom, i, now=t, hour=MIDI, sujet=sujet)[h] - avant


def test_v1_ignore_le_sujet():
    a, b = _Mem(v2=False), _Mem(v2=False)
    assert affect.event(a, "echec", 1.0, now=T0, hour=MIDI, sujet="le déploiement") == _ev(b, "echec", T0)


def test_attente_neutre_comportement_d_avant(monkeypatch):
    monkeypatch.setattr(affect, "PLAFOND_DOUX", False)      # (le plafond doux sature : à part)
    m = _Mem()
    _st(m, T0)
    assert abs(_ev(m, "succes", T0)["dopamine"] - affect.HORMONES["dopamine"][0] - 0.30) < 1e-6


def test_peur_de_l_inconnu_impressionnant():
    neuf = _hausse(_Mem(), "nouveaute", T0, 1.0, "un bruit inconnu")
    m = _Mem()
    for k in range(5):                                      # un sujet rencontré cinq fois, un par jour
        affect.event(m, "succes", 0.3, now=T0 + k * 86400, hour=MIDI, sujet="le jardin")
    familier = _hausse(m, "nouveaute", T0 + 5 * 86400, 1.0, "le jardin")
    faible = _hausse(_Mem(), "nouveaute", T0, 0.3, "un bruit inconnu")
    assert neuf > 0.3 and familier <= 0.6 * neuf and faible < 0.10          # les seuils figés : eval/


def _histoire(m, t):
    for k in range(5):
        affect.event(m, "succes", 0.3, now=t - (5 - k) * 86400, hour=MIDI, sujet="le jardin")
    for k in range(3):
        affect.event(m, "echec", 1.0, now=t + k * 7200, hour=MIDI, sujet="le déploiement")
    return t + 2 * 7200


def test_le_connu_dangereux_puis_l_extinction():
    import copy
    m = _Mem()
    t = _histoire(m, T0) + 6 * 3600
    _st(m, t)
    jumeau = copy.deepcopy(m)
    danger = _hausse(m, "probleme", t, 0.5, "le déploiement")
    neutre = _hausse(jumeau, "probleme", t, 0.5, "le jardin")
    assert danger >= 1.3 * neutre
    m = _Mem()
    t = _histoire(m, T0) + 6 * 3600
    for k in range(3):                                      # trois rencontres sûres : la peur s'éteint
        affect.event(m, "resolu", 1.0, now=t + k * 3600, hour=MIDI, sujet="le déploiement")
    t += 5 * 3600
    _st(m, t)
    jumeau = copy.deepcopy(m)
    assert _hausse(m, "probleme", t, 0.5, "le déploiement") < 1.25 * _hausse(jumeau, "probleme", t, 0.5, "le jardin")


def test_la_joie_d_une_surprise():
    deçu, comble = _Mem(), _Mem()
    for k in range(3):
        _ev(deçu, "echec", T0 + k * 600)
        _ev(comble, "succes", T0 + k * 600)
    t = T0 + 1800
    for m in (deçu, comble):                                # physiologie égale : seules les attentes restent
        import json
        d = json.loads(m._kv["affect"])
        m._kv["affect"] = json.dumps({**affect.bases(v2=True), "_vm": d["_vm"], "_ts": t})
    assert _hausse(deçu, "succes", t, 0.6, None, "dopamine") >= 1.5 * _hausse(comble, "succes", t, 0.6, None, "dopamine")


def test_la_surprise_suit_l_ecart_absolu():
    """(revalidation du 24/10, règle figée avant le code) un petit « merci » après des problèmes n'est plus 15 min de
    « surprise » ; une forte bonne nouvelle inattendue en est une (elle n'en était pas une avec l'écart relatif)."""
    def charge(m):
        _st(m, T0)
        affect.event(m, "probleme", 0.5, now=T0, hour=MIDI, sujet="la toupie")
        affect.event(m, "probleme", 0.5, now=T0 + 1800, hour=MIDI, sujet="la toupie")
    petit, grand, moyen = _Mem(), _Mem(), _Mem()
    for m in (petit, grand, moyen):
        charge(m)
    t = T0 + 3600
    affect.event(petit, "chaleur_user", 0.218, now=t, hour=MIDI, sujet="la toupie")        # r = 0,174 : le cas du 24/10
    assert affect.emotion_soudaine(petit, now=t + 60) != "surprise"
    affect.event(grand, "succes", 0.8, now=t, hour=MIDI, sujet="la toupie")                 # r = 0,8 : 15 min
    assert all(affect.emotion_soudaine(grand, now=t + 60 * k) == "surprise" for k in (1, 10, 14))
    assert affect.emotion_soudaine(grand, now=t + 16 * 60) != "surprise"
    affect.event(moyen, "succes", 0.25, now=t, hour=MIDI, sujet="la toupie")                # r = 0,25 : 7 min 30
    assert affect.emotion_soudaine(moyen, now=t + 7 * 60) == "surprise"
    assert affect.emotion_soudaine(moyen, now=t + 8 * 60) != "surprise"
    attendu = _Mem()                                                     # un sujet où le bon est attendu : pas de surprise
    _st(attendu, T0)
    for k in range(4):
        affect.event(attendu, "succes", 0.6, now=T0 + k * 600, hour=MIDI, sujet="le cockpit")
    affect.event(attendu, "succes", 0.8, now=T0 + 3600, hour=MIDI, sujet="le cockpit")
    assert affect.emotion_soudaine(attendu, now=T0 + 3660) != "surprise"


def test_libelles_soudains_et_subconscient():
    import interieur
    m = _Mem()
    _st(m, T0)
    affect.event(m, "echec", 1.0, now=T0, hour=MIDI, sujet="une panne jamais vue")
    assert affect.emotion_soudaine(m, now=T0 + 30) == "alarme"
    m = _Mem()
    affect.event(m, "nouveaute", 1.0, now=T0, hour=MIDI, sujet="un cadeau")
    assert affect.emotion_soudaine(m, now=T0 + 30) == "surprise"
    assert affect.emotion_soudaine(_Mem(v2=False), now=T0) is None
    assert interieur.humeur_code(interieur._BASE_V, interieur._BASE_A, 0.9, False, soudaine="alarme") == "alarme"
    assert interieur.humeur_code(interieur._BASE_V, interieur._BASE_A, 0.0, False, soudaine="apaisement") == "apaisement"
    assert interieur.humeur_code(interieur._BASE_V + 0.2, interieur._BASE_A + 0.1, 0.0, False, soudaine="apaisement") == "elan"
    assert all(c in interieur.LIBELLES and c in interieur.EXPRESSIVITE for c in ("alarme", "surprise", "apaisement"))


def test_sujets_bornes_et_masques():
    import json
    m = _Mem()
    for k in range(affect.SUJETS_MAX + 50):
        affect.event(m, "succes", 0.5, now=T0 + k, hour=MIDI, sujet=f"sujet {k}")
    d = json.loads(m._kv["affect"])
    assert len(d["_cog"]["F"]) <= affect.SUJETS_MAX
    assert "sk-ant" not in affect._sujet("la clé sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd")
