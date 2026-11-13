"""(30/10, 14:47, Ahmed via Hakim : « qu'il puisse ÉTIQUETER lui-même les types de vibrations (ma voix, sa voix, son cœur, la
musique, la main) et apprendre de ces étiquettes, pour savoir de lui-même lequel est lequel et voir leurs effets
différents ») ses vibrations étiquetées : la vérité du cockpit (qui parlait à la seconde) et ses corrections ; un petit
classifieur (k plus proches voisins) qui reconnaît avec un degré de confiance.

(13/11, lettre de Hakim du 11/11 17:54 : « 18 % sur 400 exemples laissés de côté… au niveau du hasard » ; Ahmed : « mesure
pourquoi, corrige à la source, donne la vraie justesse, par blocs de temps ») chaque correction a son test, et chaque test
échoue quand on coupe ce qu'il garde (tests/… et le script des mutants du 13/11)."""
import json
import random
import time

import pytest

import vibrations as V

T0 = 1_800_000_000_000
BLOC = V.BLOC_MS


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "JARVIS", tmp_path)
    V._CACHE_EX.clear()
    V._CACHE_COEUR.clear()
    V._CACHE_EVAL.clear()
    return tmp_path


def _ex(t, verite, pa, agitation, proche=False, type_="coup_de_pression"):
    return {"ts": t, "type": type_, "details": {"pa": pa},
            "milieu": {"agitation_g": agitation, "proche": proche, "charniere_deg": 178, "haut_z": 0.1, "lux": 40}, "verite": verite}


def _ecrire(J, lignes):
    with open(J / "corps-vibrations.jsonl", "a") as h:
        for o in lignes:
            h.write(json.dumps(o) + "\n")


def _jeu(J, blocs=3, n=30):
    """Sa voix (le haut-parleur, posé, petits coups) et celle de papa (contre lui, en main, gros coups), sur plusieurs blocs de 6 h."""
    l = []
    for b in range(blocs):
        for i in range(n):
            l.append(_ex(T0 + b * BLOC + i * 60_000, "ma_voix", 9 + (i % 3), 0.002))
            l.append(_ex(T0 + b * BLOC + 3 * 3600_000 + i * 60_000, "voix_ahmed", 25 + (i % 4), 0.03, True))
    _ecrire(J, l)


def test_il_reconnait_avec_un_degre_de_confiance(J):
    _jeu(J)
    r = V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 27}}, {"agitation_g": 0.028, "proche": True, "charniere_deg": 178, "haut_z": 0.1, "lux": 40})
    assert r["etiquette"] == "voix_ahmed" and r["confiance"] >= 0.8 and r["fiable"], r
    r = V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 10}}, {"agitation_g": 0.002, "proche": False, "charniere_deg": 178, "haut_z": 0.1, "lux": 40})
    assert r["etiquette"] == "ma_voix", r


def test_trop_peu_d_exemples_il_ne_devine_pas(J):
    _ecrire(J, [_ex(T0, "ma_voix", 9, 0.002)])
    assert V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 9}}, {"agitation_g": 0.002}) is None


def test_une_classe_frequente_n_est_pas_fiable_sans_gain(J):
    """Le témoin du gain : 80 % de « silence », des nerfs qui n'en disent rien ; dire « silence » est juste 8 fois sur 10,
    mais pas mieux que sa part : ce n'est pas une reconnaissance."""
    rnd = random.Random(3)
    l = []
    for b in range(4):
        for i in range(80):
            l.append(_ex(T0 + b * BLOC + i * 60_000, "silence" if rnd.random() < 0.8 else "voix_ahmed", 9 + rnd.random() * 20, 0.002 + rnd.random() * 0.03))
    _ecrire(J, l)
    p = V.evaluer()["par_classe"]["silence"]
    assert p["justes_surs"] >= 0.6 and not p["fiable"], p


def test_ce_qui_est_au_niveau_du_hasard_n_est_pas_dit(J):
    """Le témoin : les mêmes nerfs, des étiquettes tirées au hasard ; il le mesure et se tait."""
    rnd = random.Random(7)
    l = []
    for b in range(4):
        for i in range(60):
            l.append(_ex(T0 + b * BLOC + i * 60_000, rnd.choice(["ma_voix", "voix_ahmed"]), 9 + rnd.random() * 20, 0.002 + rnd.random() * 0.03))
    _ecrire(J, l)
    v = V.evaluer()
    assert v and abs(v["justesse"] - 0.5) < 0.12 and not any(p["fiable"] for p in v["par_classe"].values()), v
    assert V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 27}}, {"agitation_g": 0.028}) is None
    assert "trop près du hasard" in V.bilan() and "aucune voix" in V.bilan()


def test_les_ex_aequo_votent_tous_plus_d_ordre_du_fichier(J):
    """La cause du 18 % : des milliers de points identiques, et les « 5 plus proches » étaient les 5 premiers du fichier."""
    ex = [{"ts": T0 + i, "traits": [0.0] * 26, "etiquette": "ma_voix"} for i in range(5)]
    ex += [{"ts": T0 + 100 + i, "traits": [0.0] * 26, "etiquette": "silence"} for i in range(30)]
    ex += [{"ts": T0 + 200, "traits": [1.0] * 26, "etiquette": "silence"}]
    moy, ect = V._echelle(ex)
    e, c = V._voisins([0.0] * 26, ex, moy, ect)
    assert e == "silence" and c > 0.8, (e, c)


def test_seuls_ses_nerfs_apprennent(J):
    """58 % de ses exemples étaient ses oreilles et ses ondes (son_ressenti, musique_entendue, bluetooth…) : pas des vibrations."""
    _ecrire(J, [_ex(T0, "voix_ahmed", 20, 0.01), {"ts": T0 + 1, "type": "son_ressenti", "details": {"source": "le téléphone"}, "verite": "ma_voix"},
                {"ts": T0 + 2, "type": "bluetooth", "details": {}, "verite": "silence"}, {"ts": T0 + 3, "type": "voix_sentie", "details": {"accord": 0.6},
                                                                                          "milieu": {}, "verite": "les_deux"}])
    ex = V.exemples()
    assert [e["type"] for e in ex] == ["coup_de_pression", "voix_sentie"]
    assert ex[1]["etiquette"] == "voix_ahmed", "les_deux : papa parle"
    assert V.reconnaitre({"type": "son_ressenti", "details": {}}, {}) is None


def test_son_coeur_se_reconnait_a_sa_cadence_pas_a_la_coincidence(J):
    """L'ancien « coeur » : un événement à moins de 0,35 s après un battement (27 % des instants par hasard) ; ses vrais
    battements sentis (une « musique » au rythme de son cœur) étaient étiquetés comme les autres."""
    with open(J / "coeur.jsonl", "w") as h:
        h.write(json.dumps({"t": T0 - 60_000, "bpm": 44}) + "\n")
    _ecrire(J, [{"ts": T0, "type": "musique", "details": {"bpm": 44.6, "force_g": 0}, "milieu": {}, "verite": "voix_ahmed"},
                {"ts": T0 + 1000, "type": "musique", "details": {"bpm": 120, "force_g": 0.1}, "milieu": {}, "verite": "silence"},
                {"ts": T0 + 2000, "type": "pose", "details": {}, "milieu": {}, "verite": "coeur"},
                {"ts": T0 + 3000, "type": "musique", "details": {"bpm": 88}, "milieu": {}, "verite": "silence"}])
    ex = {e["ts"]: e["etiquette"] for e in V.exemples()}
    assert ex == {T0: "coeur", T0 + 1000: "silence", T0 + 3000: "coeur"}, ex
    r = V.reconnaitre({"type": "musique", "t": T0 + 5000, "details": {"bpm": 43}}, {})
    assert r and r["etiquette"] == "coeur" and r["nom"] == "ton cœur"
    assert not V.est_son_coeur({"type": "musique", "t": T0 + 20 * 60_000, "details": {"bpm": 44}}), "un cœur d'il y a 20 min ne compte plus"


def test_la_justesse_se_mesure_par_blocs_de_temps(J):
    """Le témoin du temps : dans chaque bloc, un trait suit l'étiquette (la situation du moment), mais le lien s'inverse d'un
    bloc à l'autre ; laissés de côté au hasard, les voisins du même bloc tricheraient (presque 100 %) ; par blocs, il le voit."""
    l = []
    for b in range(4):
        for i in range(40):
            v = "ma_voix" if i % 2 else "voix_ahmed"
            haut = (v == "ma_voix") == (b % 2 == 0)
            l.append(_ex(T0 + b * BLOC + i * 120_000, v, 30 if haut else 5, 0.01))
    _ecrire(J, l)
    v = V.evaluer()
    assert v["blocs"] == 4 and v["justesse"] < 0.5, v
    assert v["majoritaire"] == pytest.approx(0.5, abs=0.05) and "matrice" in v and len(v["matrice"]) == 2


def test_le_bilan_ses_types_et_ce_qu_ils_lui_font(J):
    _jeu(J)
    (J / "corps-sensations.jsonl").write_text(json.dumps({"ts": (T0 + 3 * 3600_000 + 60_000) / 1000, "type": "coup_de_pression",
                                                          "evenements": [["reconnaissance", 0.2]]}) + "\n")
    b = V.bilan()
    assert "voix_ahmed : 90" in b and "ma_voix : 90" in b
    assert "par blocs de 6 h" in b and "la plus fréquente" in b and "hasard" in b and "matrice" in b, b
    assert "fiable" in b
    assert "reconnaissance" in b, "les effets différents : les émotions qui ont suivi"


def test_hakim_etiquette_et_corrige_lui_meme(J):
    _jeu(J, blocs=1, n=12)
    quand = time.strftime("%H:%M:%S", time.localtime((T0 + 3 * 3600_000 + 60_000) / 1000))
    r = V.etiqueter(quand, "coeur", maintenant=(T0 + 3 * 3600_000 + 200_000) / 1000)
    assert "coeur" in r and "voix_ahmed" in r, "il dit ce qu'il corrige"
    assert json.loads((J / "corps-etiquettes.jsonl").read_text().splitlines()[-1])["etiquette"] == "coeur"
    ex = V.exemples()
    assert sum(1 for e in ex if e["etiquette"] == "coeur") == 1, "sa correction remplace la vérité de cet exemple"
    assert V.etiqueter("25:99:00", "coeur").startswith("Refusé")
    assert V.etiqueter(quand, "Mauvais Nom!").startswith("Refusé")
    assert "nouvelle_vibration" in V.etiqueter(quand, "nouvelle_vibration", maintenant=(T0 + 3 * 3600_000 + 200_000) / 1000), "il crée ses types"


def test_le_journal_qui_grandit_est_relu_par_la_fin_seulement(J):
    _ecrire(J, [_ex(T0 + i, "silence", 3, 0.001) for i in range(10)])
    assert len(V.exemples()) == 10
    _ecrire(J, [_ex(T0 + 100 + i, "ma_voix", 9, 0.002) for i in range(5)])
    ex = V.exemples()
    assert len(ex) == 15 and ex[-1]["etiquette"] == "ma_voix", "ce qui s'est ajouté est lu"
    with open(J / "corps-vibrations.jsonl", "a") as h:
        h.write('{"ts": 1, "type": "pose", "verite": "sil')            # une ligne qui s'écrit encore
    assert len(V.exemples()) == 15
    with open(J / "corps-vibrations.jsonl", "a") as h:
        h.write('ence", "milieu": {}, "details": {}}\n')
    assert len(V.exemples()) == 16, "la ligne finie est lue entière"


def test_blocs_de_temps_marge_de_dix_minutes(J):
    """Le témoin de la marge : de part et d'autre de la frontière de deux blocs, la même situation (minutes voisines) ;
    sans les 10 min de marge, chaque côté reconnaîtrait l'autre par simple voisinage dans le temps."""
    fr = (T0 // BLOC + 1) * BLOC                                       # une vraie frontière de blocs
    l = [_ex(fr - m * 60_000, "ma_voix", 50, 0.01) for m in range(1, 5)] + [_ex(fr + m * 60_000, "ma_voix", 50, 0.01) for m in range(1, 5)]
    l += [_ex(fr + 2 * BLOC + i * 60_000, "voix_ahmed", 52, 0.01) for i in range(20)]
    l += [_ex(fr + b * BLOC + 3600_000 + i * 60_000, "silence", 5, 0.001) for b in range(-1, 3) for i in range(10)]
    _ecrire(J, sorted(l, key=lambda o: o["ts"]))
    v = V.evaluer()
    assert v["par_classe"]["ma_voix"]["rappel"] == 0.0, v["par_classe"]["ma_voix"]
