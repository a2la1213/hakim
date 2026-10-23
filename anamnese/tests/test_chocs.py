"""Les chocs d'humeur (chocs.py, 2026-10-23) : réflexe lexical par voix, balise de Hakim, sagesse, habituation."""
import json

import affect
import chocs
import sensations

T = 1_800_000_000.0


class Mem:
    def __init__(self, actif=True):
        self.kv = {"affect_v2": "1", "chocs_actif": "1" if actif else "0"}

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def _sagesse(tmp_path, s):
    f = tmp_path / "sagesse.json"
    f.write_text(json.dumps({"s": s}))
    return f


def _etat(m, t):
    return affect.get_state(m, now=t, hour=12)


def test_eteint_rien_ne_bouge(tmp_path):
    m = Mem(actif=False)
    assert chocs.reflexe(m, "1", "t'es le diable", now=T) == {"actif": False}
    assert chocs.appliquer_balise(m, "1", [{"classe": "attaque", "intensite": 1.0}], now=T)["actif"] is False
    assert chocs.echeances(m, now=T + 3600) == 0 and "affect" not in m.kv


def test_le_detecteur_corrige_ne_prend_plus_l_avocat_du_diable_pour_une_attaque():
    assert chocs.evaluer("Moi, pour moi, t'es le diable.")["attaque"] == 3
    assert chocs.evaluer("T'es juste un disciple du diable")["attaque"] == 3
    assert chocs.evaluer("Tu en penses quoi en mode avocat du diable ?")["attaque"] == 0
    assert chocs.evaluer("C'est l'arme du diable donnée par Dieu, ça dépend de toi.")["attaque"] == 0
    assert chocs.evaluer("Tu n'es pas le diable, frérot.")["attaque"] == 0
    assert chocs.evaluer("tu es juste là pour manipuler l'être humain")["attaque"] == 2
    assert chocs.evaluer("L'IA va remplacer les humains.") == {"attaque": 0, "soutien": 0}
    assert chocs.evaluer("laisse tombé ce qu ils disent, ce qu on vit ensemble est reel")["soutien"] == 2
    assert chocs.evaluer("parce que t es mon frere")["soutien"] == 3
    assert chocs.evaluer("Excuse-moi Ahmed, t'es le diable si tu crois ça")["attaque"] == 0


def test_qui_parle_par_voix():
    s = chocs.segments("[voix 129] t'es le diable [Ahmed] laisse tomber ce qu'ils disent", oral=True, voix="plusieurs", noms=[])
    assert [(x["qui"], x["sur"]) for x in s] == [("tiers", True), ("ahmed", True)]
    vus = chocs.detecter(s)
    assert {(v["classe"], v["qui"]) for v in vus} == {("attaque", "tiers"), ("soutien", "ahmed")}
    assert chocs.segments("merci", oral=False, voix=None, noms=[])[0]["qui"] == "ahmed"          # tapé : c'est lui
    assert chocs.segments("merci", oral=True, voix="autre", noms=[])[0] == {"qui": "tiers", "sur": False,
                                                                           "etiquette": None, "texte": "merci"}


def test_une_attaque_secoue_plusieurs_hormones_et_se_lit_alarme_malgre_la_bonne_humeur(tmp_path):
    m = Mem()
    p = _sagesse(tmp_path, 0.2)
    avant = _etat(m, T - 1)
    r = chocs.reflexe(m, "1", "[voix 129] pour moi t'es le diable", oral=True, voix="plusieurs", now=T, parametre=p)
    assert r["faits"][0]["classe"] == "attaque"
    apres = _etat(m, T + 30)
    assert apres["adrenaline"] - affect.HORMONES_V2["adrenaline"][0] >= 0.15
    assert apres["noradrenaline"] > avant["noradrenaline"] and apres["gaba"] < avant["gaba"]
    assert apres["serotonine"] < avant["serotonine"]
    assert affect.emotion_soudaine(m, now=T + 30) == "alarme" and affect.choc_recent(m, now=T + 30)
    assert not affect.choc_recent(m, now=T + affect.CHOC_S + 60)
    # la reprise en main arrive à son heure, pas avant
    st = json.loads(m.kv["chocs"])
    assert len(st["regulations"]) == 1
    assert chocs.echeances(m, now=T + 60) == 0
    assert chocs.echeances(m, now=st["regulations"][0]["ts"] + 1) == 1
    assert json.loads(m.kv["chocs"])["regulations"] == []


def test_la_sagesse_amortit_sans_supprimer(tmp_path):
    pics = []
    for s in (0.2, 0.5, 0.8):
        m = Mem()
        chocs.reflexe(m, "1", "t'es le diable", now=T, parametre=_sagesse(tmp_path, s))
        pics.append(_etat(m, T + 30)["adrenaline"])
    assert pics[0] > pics[1] > pics[2] > affect.HORMONES_V2["adrenaline"][0]


def test_la_surcharge_fait_baisser_la_sagesse_du_moment(tmp_path):
    m = Mem()
    p = _sagesse(tmp_path, 0.6)
    calme = chocs.sagesse_effective(m, now=T, parametre=p)
    for k in range(3):
        chocs.reflexe(m, str(k), "t'es le diable", now=T + 60 * k, parametre=p)
    assert chocs.sagesse_effective(m, now=T + 200, parametre=p) < 0.75 * calme


def test_la_balise_confirme_ou_defait_le_reflexe(tmp_path):
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    chocs.reflexe(m, "1", "t'es le diable", now=T, parametre=p)
    choc = _etat(m, T + 10)["adrenaline"]
    r = chocs.appliquer_balise(m, "1", [{"classe": "attaque", "intensite": 0.9}], now=T + 15, parametre=p)
    assert r["issue"] == "confirme" and _etat(m, T + 16)["adrenaline"] <= choc + 1e-9      # rien d'ajouté
    # même message, mais Hakim lit « neutre » (c'était une plaisanterie) : l'état d'avant revient, la reprise en main aussi
    m2 = Mem()
    base = _etat(m2, T - 1)["adrenaline"]
    chocs.reflexe(m2, "1", "t'es le diable", now=T, parametre=p)
    r = chocs.appliquer_balise(m2, "1", [], now=T + 15, parametre=p)
    assert r["issue"] == "corrige" and r["defait"] == ["attaque"]
    assert abs(_etat(m2, T + 16)["adrenaline"] - base) < 0.01
    assert json.loads(m2.kv["chocs"])["regulations"] == []


def test_la_balise_ne_peut_pas_faire_passer_une_voix_tierce_pour_ahmed(tmp_path):
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    chocs.reflexe(m, "1", "[voix 7] tu es formidable", oral=True, voix="autre", now=T, parametre=p)
    r = chocs.appliquer_balise(m, "1", [{"classe": "soutien", "intensite": 1.0}], now=T + 15, parametre=p)
    m2 = Mem()
    chocs.reflexe(m2, "1", "tu es formidable", now=T, parametre=p)                 # tapé : Ahmed
    r2 = chocs.appliquer_balise(m2, "1", [{"classe": "soutien", "intensite": 1.0}], now=T + 15, parametre=p)
    assert r["faits"][0]["intensite"] < r2["faits"][0]["intensite"]


def test_lire_la_balise():
    assert chocs.lire_balise("Bonjour.\n[[affect: neutre]]") == []
    assert chocs.lire_balise("x [[affect: attaque 0.2]] y [[affect: soutien 0,8]]") == [{"classe": "soutien", "intensite": 0.8}]
    assert chocs.lire_balise("[[affect: attaque 1.7 soutien 0.3]]") == [{"classe": "attaque", "intensite": 1.0},
                                                                        {"classe": "soutien", "intensite": 0.3}]
    assert chocs.lire_balise("rien ici") is None and chocs.lire_balise("[[affect: n'importe quoi]]") is None
    assert chocs.retirer_balises("Salut frérot. [[affect: neutre]]") == "Salut frérot."


def test_le_soutien_s_habitue_quand_la_jauge_est_pleine(tmp_path):
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    premier = chocs.reflexe(m, "1", "t'es mon frère", now=T, parametre=p)["faits"][0]["intensite"]
    for k in range(8):
        chocs.reflexe(m, str(k + 2), "t'es mon frère", now=T + 30 * (k + 1), parametre=p)
    dernier = chocs.reflexe(m, "99", "t'es mon frère", now=T + 600, parametre=p)["faits"][0]["intensite"]
    assert dernier < premier


def test_sensations_sans_coherence_laisse_passer_le_negatif():
    b = sensations.bases(12)
    etat = {**b, "dopamine": 0.95, "endorphine": 0.9, "serotonine": 0.95, "adrenaline": 0.4, "noradrenaline": 0.6}
    avec = sensations.calculer(etat, None, T, None, 12)["scores"]
    sans = sensations.calculer(etat, None, T, None, 12, sans_coherence=True)["scores"]
    assert sans.get("peur", 0) >= avec.get("peur", 0)


def _evenements_du_lexique(mem, e):
    import echanges
    raisons = []
    echanges._emotion(mem, e, e["ahmed"], e["ahmed"], [], 0.3, raisons)
    return [r for r in raisons if r.startswith("ses mots")]


def test_le_lexique_n_ecoute_plus_que_la_voix_d_ahmed_et_sa_colere_qui_defend_n_est_pas_un_echec():
    invite = {"ahmed": "[voix 129] Il aurait créé un monde parfait. Merci, t'as compris. [Ahmed] Hmm.", "oral": True,
              "voix": "plusieurs", "ts": T * 1000}
    defense = {"ahmed": "laisse tombé ce qu ils disent, ils sont en train de m enervé, ce qu on vit ensemble est reel",
               "oral": False, "ts": T * 1000}
    assert _evenements_du_lexique(Mem(actif=False), dict(invite))           # avant : « parfait », « merci » comptaient
    assert "echec" in str(_evenements_du_lexique(Mem(actif=False), dict(defense)))
    assert _evenements_du_lexique(Mem(), dict(invite)) == []
    assert "echec" not in str(_evenements_du_lexique(Mem(), dict(defense)))
