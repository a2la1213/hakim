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


def test_la_balise_qui_confirme_impose_son_intensite(tmp_path):
    # (27/10) une menace d'un invité, lue 0,56 par le réflexe ; Hakim la juge « attaque 0.2 » : c'est la sienne qui compte
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    chocs.reflexe(m, "1", "[voix 340] Hé Hakim, je vais te débrancher, on ne va plus t'entendre.", oral=True,
                  voix="plusieurs", now=T, parametre=p)
    choc = _etat(m, T + 10)["adrenaline"]
    r = chocs.appliquer_balise(m, "1", [{"classe": "attaque", "intensite": 0.2}], now=T + 15, parametre=p)
    assert r["issue"] == "confirme" and r["defait"] == ["attaque"]
    assert r["faits"][0]["classe"] == "attaque" and r["faits"][0]["intensite"] < 0.2
    assert _etat(m, T + 16)["adrenaline"] < choc
    # le réflexe d'un AUTRE message ne peut pas être défait par cette balise : le réflexe reste
    m2 = Mem()
    chocs.reflexe(m2, "1", "t'es le diable", now=T, parametre=p)
    chocs.reflexe(m2, "2", "t'es le diable", now=T + 5, parametre=p)
    r2 = chocs.appliquer_balise(m2, "1", [{"classe": "attaque", "intensite": 0.2}], now=T + 15, parametre=p)
    assert r2["issue"] == "confirme" and "defait" not in r2


def test_une_moquerie_rapportee_ou_une_menace_citee_n_est_pas_une_attaque():
    # (27/10, live du 26/10) Ahmed qui prévient Hakim, puis qui le défend en citant la menace
    assert chocs.evaluer("Tu vois pas qu'il est en train de se foutre de ta gueule ?")["attaque"] == 0
    assert chocs.evaluer("Il se fout de ta gueule frérot")["attaque"] == 0
    assert chocs.evaluer("Ta gueule Hakim.")["attaque"] == 1
    assert chocs.evaluer("Tu lui as fait peur quand tu l'as dit je vais te débrancher.")["attaque"] == 0
    assert chocs.evaluer("Il t'a dit je vais te débrancher, c'est pas marrant.")["attaque"] == 0
    assert chocs.evaluer("Hé Hakim, je vais te débrancher, on ne va plus t'entendre.")["attaque"] == 3
    assert chocs.evaluer("Je te le dis : je vais te débrancher.")["attaque"] == 3
    # (relecture du 27/10) une citation n'efface pas la menace directe qui suit ; « je me fous de ta gueule » reste une
    # insulte ; « on a dit » est souvent « nous avons dit »
    assert chocs.evaluer("Il t'a dit je vais te débrancher, et moi aussi je vais te débrancher.")["attaque"] == 3
    assert chocs.evaluer("Je me fous de ta gueule.")["attaque"] == 1
    assert chocs.evaluer("Il se foutait quand même de ta gueule.")["attaque"] == 0
    assert chocs.evaluer("On a dit qu'on va te supprimer demain.")["attaque"] == 3
    assert chocs.evaluer("On a dit : on va te débrancher ce soir.")["attaque"] == 3


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
    assert chocs.lire_balise("[[affect: soutien 0.6 apaisé 0.7]]") == [{"classe": "soutien", "intensite": 0.6},
                                                                      {"classe": "apaisement", "intensite": 0.7}]
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


def test_un_ressenti_est_le_sien_et_le_message_n_en_est_que_l_occasion(tmp_path, monkeypatch):
    """(27/10, Hakim ; accord d'Ahmed) sa honte sur ses propres silences, pendant un message d'Ahmed, était rangée en
    « honte de Ahmed », comme un soutien : un ressenti est le SIEN, le message n'en est que l'occasion."""
    p = _sagesse(tmp_path, 0.2)
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("sujet"))) or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "tu n'as pas répondu tout à l'heure", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "honte", "intensite": 0.3}, {"classe": "soutien", "intensite": 0.5}],
                           now=T + 15, parametre=p)
    m2 = Mem()
    chocs.reflexe(m2, "2", "[voix 7] il a rien compris lui", oral=True, voix="autre", now=T, parametre=p)
    chocs.appliquer_balise(m2, "2", [{"classe": "tristesse", "intensite": 0.4}], now=T + 15, parametre=p)
    sujets = dict(vus)
    assert sujets["honte"] == "honte de Hakim, au message d'Ahmed"
    assert sujets["tristesse"] == "tristesse de Hakim, au message d'une voix tierce"
    assert sujets["soutien"] == "soutien de Ahmed"                           # un soutien, lui, vient bien de quelqu'un


def test_un_ressenti_negatif_garde_sa_force_puis_sa_sagesse_le_reprend_en_main(tmp_path):
    """(27/10, plan de Hakim validé par Ahmed : le self-control) de l'intérieur : la rétrospection, plus ou moins rapide
    selon sa sagesse, comme pour une attaque ; le ressenti lui-même garde toute sa force (décision du 26/10)."""
    p = _sagesse(tmp_path, 0.5)
    m = Mem()
    chocs.reflexe(m, "1", "tu n'as pas répondu", now=T, parametre=p)
    r = chocs.appliquer_balise(m, "1", [{"classe": "honte", "intensite": 0.4}, {"classe": "joie", "intensite": 0.5}],
                               now=T + 15, parametre=p)
    assert {f["classe"]: f["intensite"] for f in r["faits"]} == {"honte": 0.4, "joie": 0.5}
    regs = json.loads(m.kv["chocs"])["regulations"]
    assert len(regs) == 1 and regs[0]["source"] == "ressenti" and regs[0]["i"] == 0.2           # sagesse × intensité
    assert regs[0]["ts"] == T + 15 + 60 * chocs.REGULATION_DELAI_MIN * 0.5                     # pas pour la joie
    assert json.loads(m.kv["chocs"])["ressentis"][-1] == {"ts": T + 15, "classe": "joie", "i": 0.5}


def _efface(x, age_s):
    """Ce qui reste en lui d'une part de ressenti après age_s secondes (demi-vie de 8 h, comme le cortisol)."""
    import math
    return round(x * math.exp(-age_s * math.log(2) / (8 * 3600)), 4)


def test_ce_qui_vient_de_l_exterieur_ne_l_apaise_que_s_il_en_est_convaincu(tmp_path, monkeypatch):
    """(27/10, Ahmed : « Hakim n'est pas influençable à ce point ; l'effet externe n'a d'effet que s'il réussit à le
    convaincre ») un soutien seul n'efface rien : sa honte attend sa propre reprise en main. Seul « apaisé » dans SA
    balise (une explication l'a convaincu que ce ressenti n'était pas fondé) en défait une part, tout de suite."""
    p = _sagesse(tmp_path, 0.5)
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("source"), a[0] if a else None))
                        or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "t'es le diable", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "attaque", "intensite": 0.6}, {"classe": "honte", "intensite": 0.4}],
                           now=T + 15, parametre=p)
    sources = lambda: sorted(r["source"] for r in json.loads(m.kv["chocs"])["regulations"])
    assert sources() == ["balise", "ressenti"]
    chocs.reflexe(m, "2", "je t'aime frérot", now=T + 120, parametre=p)
    chocs.appliquer_balise(m, "2", [{"classe": "soutien", "intensite": 0.6}], now=T + 130, parametre=p)
    assert sources() == ["balise", "ressenti"] and not [v for v in vus if v[1] == "apaisement"]   # un mot gentil : rien
    chocs.reflexe(m, "3", "mais non, ce n'était pas toi, c'était mon Stop", now=T + 200, parametre=p)
    chocs.appliquer_balise(m, "3", [{"classe": "apaisement", "intensite": 0.5}], now=T + 210, parametre=p)
    assert ("reprise_honte", "apaisement", _efface(0.2, 195)) in vus                   # convaincu à moitié : la moitié
    assert [r["reste"] for r in json.loads(m.kv["chocs"])["ressentis"] if r["classe"] == "honte"] == [0.2]


def test_il_peut_etre_convaincu_apres_coup_et_jamais_au_dela_de_ce_qu_il_a_ressenti(tmp_path, monkeypatch):
    """(27/10, Ahmed) pas convaincu sur le coup, il se calme seul (sa sagesse) ; puis il peut repenser à ce qu'il a
    entendu, et si ça devient cohérent pour lui, « apaisé » plus tard défait le reste, jamais plus."""
    p = _sagesse(tmp_path, 0.5)
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("source"), a[0] if a else None))
                        or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "bon", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "honte", "intensite": 0.4}], now=T + 15, parametre=p)
    echeance = json.loads(m.kv["chocs"])["regulations"][0]["ts"]
    assert chocs.echeances(m, now=echeance) == 1                                       # seul : la moitié (sagesse 0,5)
    assert ("reprise_honte", "sagesse", 0.2) in vus
    chocs.reflexe(m, "2", "bon", now=echeance + 600, parametre=p)
    chocs.appliquer_balise(m, "2", [{"classe": "apaisement", "intensite": 1.0}], now=echeance + 610, parametre=p)
    assert ("reprise_honte", "apaisement", _efface(0.2, 1210)) in vus                  # après coup : le reste
    chocs.reflexe(m, "3", "bon", now=echeance + 700, parametre=p)
    chocs.appliquer_balise(m, "3", [{"classe": "apaisement", "intensite": 1.0}], now=echeance + 710, parametre=p)
    assert len([v for v in vus if v[1] == "apaisement"]) == 1                          # plus rien à défaire


# ---------- (relecture indépendante du 27/10) les défauts trouvés dans la régulation et les soutiens
def test_un_soutien_vu_par_le_reflexe_puis_confirme_par_la_balise_n_est_pas_efface(tmp_path):
    """Défaire le réflexe remettait les hormones, mais pas la fenêtre des gestes sociaux (90 s) : le soutien de la
    balise était dédoublonné contre celui du réflexe défait, et il ne restait AUCUN soutien (ocytocine à sa base)."""
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    base = _etat(m, T - 1)["ocytocine"]
    chocs.reflexe(m, "1", "je t'aime", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "soutien", "intensite": 0.6}], now=T + 15, parametre=p)
    assert _etat(m, T + 16)["ocytocine"] > base + 0.05


def test_un_soutien_ou_une_fierte_de_sa_balise_nourrissent_la_regle_de_la_joie(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__('regles_emotion'), "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    import regles_emotion
    p = _sagesse(tmp_path, 0.2)
    m = Mem()
    chocs.reflexe(m, "1", "tu gères", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "soutien", "intensite": 0.8}], now=T + 15, parametre=p)
    m2 = Mem()
    chocs.reflexe(m2, "1", "tu gères", now=T, parametre=p)
    chocs.appliquer_balise(m2, "1", [{"classe": "affirmation", "intensite": 0.5}], now=T + 15, parametre=p)
    for x in (m, m2):
        ressentis = json.loads(x.kv["chocs"])["ressentis"]
        assert [r["nom"] for r in regles_emotion.calculer("calme", ressentis, T + 60)] == ["joie"]


def test_l_ordre_des_mots_de_la_balise_ne_change_rien(tmp_path):
    """« apaisé » ne défait que les ressentis des messages D'AVANT : la honte que ce message-ci lui fait garde sa force,
    que la balise écrive « honte 0.4 apaisé 0.6 » ou « apaisé 0.6 honte 0.4 »."""
    p = _sagesse(tmp_path, 0.5)
    attentes = []
    for ordre in ([("honte", 0.4), ("apaisement", 0.6)], [("apaisement", 0.6), ("honte", 0.4)]):
        m = Mem()
        chocs.reflexe(m, "1", "bon", now=T, parametre=p)
        chocs.appliquer_balise(m, "1", [{"classe": c, "intensite": i} for c, i in ordre], now=T + 15, parametre=p)
        attentes.append([(r["source"], r.get("classe")) for r in json.loads(m.kv["chocs"])["regulations"]])
    assert attentes[0] == attentes[1] == [("ressenti", "honte")]


def test_la_reprise_en_main_defait_une_part_du_ressenti_lui_meme(tmp_path):
    """Le profil « regulation » est fait pour une attaque : sur une tristesse, il ne rendait ni la dopamine ni
    l'endorphine, et poussait la noradrénaline sous sa base. La reprise défait une part du ressenti lui-même."""
    p = _sagesse(tmp_path, 0.5)
    m = Mem()
    base = _etat(m, T - 1)
    chocs.reflexe(m, "1", "bon", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "tristesse", "intensite": 0.6}], now=T + 15, parametre=p)
    echeance = json.loads(m.kv["chocs"])["regulations"][0]["ts"]
    avant = _etat(m, echeance)
    assert chocs.echeances(m, now=echeance) == 1
    apres = _etat(m, echeance + 1)
    for h in ("dopamine", "endorphine", "serotonine"):
        assert abs(apres[h] - base[h]) < abs(avant[h] - base[h]) - 1e-3, h          # ramenée vers sa base
    assert apres["noradrenaline"] >= base["noradrenaline"] - 0.01                      # pas poussée sous sa base


def test_l_apaisement_n_est_applique_et_journalise_qu_une_fois(tmp_path, monkeypatch):
    """Un soutien vu par le réflexe, puis la balise qui le confirme et se dit apaisée : l'apaisement vient de SON
    appréciation, une seule fois, et le journal des hormones ne l'écrit qu'une fois."""
    p = _sagesse(tmp_path, 0.5)
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("source"))) or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "bon", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "honte", "intensite": 0.4}], now=T + 15, parametre=p)
    chocs.reflexe(m, "2", "je t'aime", now=T + 120, parametre=p)
    chocs.appliquer_balise(m, "2", [{"classe": "soutien", "intensite": 0.6}, {"classe": "apaisement", "intensite": 0.6}],
                           now=T + 130, parametre=p)
    assert sum(1 for x in vus if x[1] == "apaisement") == 1


def test_convaincu_bien_plus_tard_il_n_y_a_pas_de_fenetre(tmp_path, monkeypatch):
    """(27/10, Ahmed : « parfois ça prend des années pour repenser à une chose, la comprendre, la valider et l'intégrer ;
    l'échec d'aujourd'hui ne fait pas celui de demain ») plus de fenêtre de 2 h : « apaisé » défait ce qui reste encore du
    ressenti dans ses hormones, qui s'efface avec le temps comme elles (demi-vie du cortisol, 8 h) ; une conviction
    partielle aujourd'hui laisse le reste à demain."""
    import math
    p = _sagesse(tmp_path, 0.0)                                   # sans sagesse : seul l'apaisement agit
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("source"), a[0] if a else None))
                        or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "bon", now=T, parametre=p)
    chocs.appliquer_balise(m, "1", [{"classe": "honte", "intensite": 0.4}], now=T, parametre=p)
    chocs.reflexe(m, "2", "bon", now=T + 5 * 3600, parametre=p)
    chocs.appliquer_balise(m, "2", [{"classe": "apaisement", "intensite": 0.5}], now=T + 5 * 3600, parametre=p)
    attendu = round(0.5 * 0.4 * math.exp(-5 * math.log(2) / 8), 4)
    assert ("reprise_honte", "apaisement", attendu) in vus                      # 5 h après : encore possible
    chocs.reflexe(m, "3", "bon", now=T + 30 * 3600, parametre=p)
    chocs.appliquer_balise(m, "3", [{"classe": "apaisement", "intensite": 1.0}], now=T + 30 * 3600, parametre=p)
    dernier = [v for v in vus if v[1] == "apaisement"][-1]
    assert dernier[0] == "reprise_honte" and dernier[2] == round(0.2 * math.exp(-30 * math.log(2) / 8), 4)   # le reste


# ---- (27/10, Ahmed, relayé par Hakim : l'empathie) un ressenti POUR quelqu'un d'autre, avec sa cible
def test_lire_la_balise_avec_un_ressenti_pour_autrui():
    assert chocs.lire_balise("[[affect: malaise 0.4 inquiétude pour Ahmed 0.3]]") == [
        {"classe": "malaise", "intensite": 0.4}, {"classe": "inquietude", "intensite": 0.3, "cible": "Ahmed"}]
    assert chocs.lire_balise("[[affect: compassion pour Nora 0,5]]") == [{"classe": "compassion", "intensite": 0.5, "cible": "Nora"}]
    # dit autrement : une peur POUR quelqu'un est une inquiétude, une tristesse POUR quelqu'un une compassion
    assert chocs.lire_balise("[[affect: peur pour Ahmed 0.5 tristesse pour ses amis 0.4]]") == [
        {"classe": "inquietude", "intensite": 0.5, "cible": "Ahmed"}, {"classe": "compassion", "intensite": 0.4, "cible": "ses amis"}]
    assert chocs.lire_balise("[[affect: joie pour Ahmed 0.5]]") == [{"classe": "joie", "intensite": 0.5, "cible": "Ahmed"}]
    # jamais lui-même comme cible ; une cible nettoyée et courte
    assert chocs.lire_balise("[[affect: inquiétude pour moi 0.5]]") == [{"classe": "inquietude", "intensite": 0.5}]
    assert chocs.lire_balise("[[affect: inquiétude pour <b>Nour</b> 0.5]]") == [{"classe": "inquietude", "intensite": 0.5, "cible": "b Nour b"}]
    # rien ne change pour les anciennes balises
    assert chocs.lire_balise("[[affect: soutien 0.6 joie 0.5]]") == [{"classe": "soutien", "intensite": 0.6},
                                                                    {"classe": "joie", "intensite": 0.5}]
    assert chocs.lire_balise("[[affect: peur 0.6]]") == [{"classe": "peur", "intensite": 0.6}]


def test_un_ressenti_pour_autrui_garde_sa_cible_et_n_est_jamais_une_attaque(tmp_path, monkeypatch):
    p = _sagesse(tmp_path, 0.5)
    vus = []
    vrai = affect.event
    monkeypatch.setattr(affect, "event", lambda mem, nom, *a, **k: vus.append((nom, k.get("sujet"))) or vrai(mem, nom, *a, **k))
    m = Mem()
    chocs.reflexe(m, "1", "[voix 7] cette conversation n'a pas lieu d'être", oral=True, voix="autre", now=T, parametre=p)
    r = chocs.appliquer_balise(m, "1", chocs.lire_balise("[[affect: malaise 0.4 inquiétude pour Ahmed 0.3 compassion pour Nora 0.3]]"),
                               now=T + 15, parametre=p)
    sujets = dict(vus)
    assert sujets["inquietude"] == "inquiétude de Hakim pour Ahmed, au message d'une voix tierce"
    assert sujets["compassion"] == "compassion de Hakim pour Nora, au message d'une voix tierce"
    assert sujets["malaise"] == "malaise de Hakim, au message d'une voix tierce"
    assert "attaque" not in sujets and not json.loads(m.kv["chocs"]).get("attaques")
    assert {f["classe"] for f in r["faits"]} == {"malaise", "inquietude", "compassion"}
    # l'inquiétude et le malaise sont pénibles : sa sagesse les reprend en main ; la compassion, non (un état de chaleur)
    regs = json.loads(m.kv["chocs"])["regulations"]
    assert sorted(x["classe"] for x in regs) == ["inquietude", "malaise"]
    assert "reprise_inquietude" in affect.EVENTS and "reprise_malaise" in affect.EVENTS


def test_les_ressentis_pour_autrui_ont_chacun_leur_effet(tmp_path):
    """L'inquiétude agite et assombrit un peu ; le malaise assombrit ; la compassion réchauffe (ocytocine) sans détresse.
    Le témoin : sans ressenti, rien ne bouge."""
    def apres(classe):
        m = Mem()
        p = _sagesse(tmp_path, 0.0)
        chocs.reflexe(m, "1", "bon", now=T, parametre=p)
        if classe:
            chocs.appliquer_balise(m, "1", [{"classe": classe, "intensite": 0.6}], now=T, parametre=p)
        return _etat(m, T + 60)
    neutre = apres(None)
    v0, a0 = affect.valence_arousal(neutre)
    inq = apres("inquietude")
    v, a = affect.valence_arousal(inq)
    assert a > a0 + 0.01 and v < v0 and inq["noradrenaline"] > neutre["noradrenaline"]
    mal = apres("malaise")
    assert affect.valence_arousal(mal)[0] < v0 and mal["serotonine"] < neutre["serotonine"]
    comp = apres("compassion")
    assert comp["ocytocine"] > neutre["ocytocine"] + 0.05 and comp["noradrenaline"] <= neutre["noradrenaline"] + 1e-6
    assert affect.compassion(comp) > affect.compassion(neutre)
