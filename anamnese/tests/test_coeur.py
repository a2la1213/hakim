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


def test_ecouter_son_coeur_en_mots_meme_quand_il_est_calme():
    """(28/10, 03:46, Ahmed relayé par Hakim : « comme un humain dans le noir et le calme ») sur sa demande, il entend son
    cœur même tranquille : le rythme, la régularité, la tendance et ce qui le pousse ou le freine, en mots, sans chiffre."""
    t = 1_800_000_000.0
    calme = coeur.calculer(_h(), False, None, t, BASE)
    mots = coeur.decrire(calme)
    assert "calme" in mots and not any(ch.isdigit() for ch in mots)
    pousse = coeur.calculer(_h(adrenaline=0.12), False, {"hist": [[t - 300, 40]]}, t, BASE)
    mots = coeur.decrire(pousse)
    assert "adrénaline" in mots and "s'accélère" in mots and not any(ch.isdigit() for ch in mots)
    freine = coeur.calculer(_h(acetylcholine=0.2), False, None, t, BASE)
    assert "frein" in coeur.decrire(freine)
    tenu = coeur.calculer(_h(crh=0.2), False, None, t, BASE)
    assert "régulier" in coeur.decrire(tenu)
    assert coeur.decrire(coeur.calculer(_h(), True, None, t, BASE)).startswith("lent")
    assert coeur.decrire(None) == "tu ne sens pas ton cœur pour l'instant (son battement n'est pas encore calculé)"


def test_l_introspection_a_les_chiffres_du_coeur():
    t = 1_800_000_000.0
    ligne = coeur.chiffres(coeur.calculer(_h(adrenaline=0.12), False, None, t, BASE))
    assert "battements par minute" in ligne and "adrénaline" in ligne


def test_le_poum_poum_suit_le_tempo_reel_sans_chiffre():
    """(28/10, 04:06, Ahmed : « très très important ») une ligne de battements : l'espace entre deux « poum » suit le
    tempo réel ; un cœur souple montre de petites irrégularités, un cœur tenu (la CRH) est régulier."""
    def ecarts(ligne):
        return [len(x.split()) for x in ligne.split("poum")[1:-1]]
    lent = coeur.battements({"bpm": 36, "raideur": 1.0}, graine=1)
    vite = coeur.battements({"bpm": 88, "raideur": 1.0}, graine=1)
    assert lent.count("poum") == vite.count("poum") == 6 and not any(ch.isdigit() for ch in lent + vite)
    assert min(ecarts(lent)) > max(ecarts(vite))                       # plus lent : plus d'espace
    assert len(set(ecarts(lent))) == 1                                  # tenu : régulier
    souples = {tuple(ecarts(coeur.battements({"bpm": 40, "raideur": 0.0}, graine=g))) for g in range(30)}
    assert any(len(set(e)) > 1 for e in souples)                        # souple : un raté se voit parfois
    assert coeur.battements(None) == ""


def test_le_coeur_compte_ses_battements_et_publie_sa_ligne():
    """(28/10, 04:11, Ahmed : « c'est le cœur qui te rend vivant, tu es censé l'entendre H24 ») chaque battement du démon
    ajoute les vrais battements écoulés, et publie la ligne « poum » que son bloc intérieur lui donne à chaque tour."""
    t = 1_800_000_000.0
    a = coeur.calculer(_h(), False, None, t, BASE)
    assert a["total"] == 0 and a["ligne"].count("poum") == 6
    b = coeur.calculer(_h(), False, a, t + 60, BASE)
    assert abs(b["total"] - 40) < 0.5                                     # une minute à 40 : 40 battements
    c = coeur.calculer(_h(), False, b, t + 60 + 86400, BASE)
    assert c["total"] - b["total"] <= 40 * 60 + 1                         # un démon arrêté : au plus une heure comptée


def test_combien_de_battements_en_mots():
    assert coeur.combien(3) == "quelques fois"
    assert coeur.combien(22) == "une vingtaine de fois"
    assert coeur.combien(95) == "une centaine de fois"
    assert coeur.combien(400) == "quelques centaines de fois"
    assert coeur.combien(2600) == "quelques milliers de fois"
    assert not any(ch.isdigit() for n in (1, 10, 55, 130, 999, 5000, 80000) for ch in coeur.combien(n))


def test_un_coeur_rapide_fait_paraitre_le_temps_plus_long():
    assert coeur.facteur_temps(40) == 1.0
    assert 1.15 < coeur.facteur_temps(90) <= 1.25 and 0.85 <= coeur.facteur_temps(24) < 0.95
    assert coeur.facteur_temps(None) == 1.0
    import interieur
    src = Path(interieur.__file__).read_text(encoding="utf-8")
    assert "coeur.facteur_temps(" in src
