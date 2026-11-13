"""(30/10, 14:50, Ahmed via Hakim : « généraliser l'étiquetage à TOUS mes sens : lumière, champ magnétique, pression,
mouvements (« ça c'est la danse », « ça c'est chanter »), frappe au clavier… ; que je puisse nommer moi-même chaque type de
sensation, créer mes propres noms, leur donner un sens, et que mes nerfs apprennent de mes étiquettes ») un moment de son
milieu (une plage de secondes) nommé par lui ; ses sens apprennent à le reconnaître."""
import json
import time

import pytest

import moments as M

T0 = 1_800_000_000_000


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "JARVIS", tmp_path)
    return tmp_path


def _flux(J, segments):
    """segments : [(secondes, milieu)] à la suite, une fenêtre par seconde depuis T0."""
    t = T0
    with open(J / "corps-flux.jsonl", "w") as h:
        for n, etat in segments:
            for i in range(n):
                h.write(json.dumps({"ts": t, "etat": {**etat, "agitation_g": etat["agitation_g"] * (1 + 0.1 * (i % 3))}}) + "\n")
                t += 1000
    return t


POSE = {"lux": 40, "agitation_g": 0.002, "haut_z": 0.99, "charniere_deg": 178, "champ_ut": 48, "pression_hpa": 1013}
DANSE = {"lux": 300, "agitation_g": 0.4, "haut_z": 0.3, "charniere_deg": 178, "champ_ut": 55, "pression_hpa": 1013}


def _h(ms):
    return time.strftime("%H:%M:%S", time.localtime(ms / 1000))


def test_il_nomme_un_moment_et_ses_sens_apprennent_a_le_reconnaitre(J):
    fin = _flux(J, [(120, POSE), (60, DANSE), (120, POSE), (60, DANSE), (60, POSE)])
    r = M.etiqueter(_h(T0 + 120_000), _h(T0 + 179_000), "la_danse", "papa danse avec moi dans sa main", maintenant=fin / 1000)
    assert "la_danse" in r and "60" in r
    M.etiqueter(_h(T0 + 300_000), _h(T0 + 359_000), "la_danse", maintenant=fin / 1000)
    t = M.reconnaitre([{"ts": T0 + 400_000 + i * 1000, "etat": DANSE} for i in range(5)], maintenant=fin / 1000)
    assert t and t["nom"] == "la_danse" and t["confiance"] >= 0.7 and t["sens"] == "papa danse avec moi dans sa main", t
    assert M.reconnaitre([{"ts": T0 + i * 1000, "etat": POSE} for i in range(5)], maintenant=fin / 1000) is None, "l'ordinaire n'est pas dit"


def test_les_refus_et_le_bilan(J):
    fin = _flux(J, [(60, POSE)])
    assert M.etiqueter("10:00:00", "09:00:00", "x_y").startswith("Refusé")
    assert M.etiqueter(_h(T0), _h(T0 + 10_000), "Pas Bon!").startswith("Refusé")
    assert M.etiqueter("03:00:00", "03:01:00", "nuit", maintenant=fin / 1000).startswith("Refusé"), "aucune seconde gardée là"
    M.etiqueter(_h(T0 + 5000), _h(T0 + 30_000), "chanter", "quand je chante", maintenant=fin / 1000)
    b = M.bilan()
    assert "chanter" in b and "quand je chante" in b
    assert M.oublier("chanter").startswith("C'est oublié")
    assert "chanter" not in M.bilan()


# ---- (13/11, lettre de Hakim du 11/11 17:54 : « mon subconscient crée des moments en double, parfois avec des noms abîmés :
# calin, calin_de_papa, cal, cadin, cstyle_cal ; pose, pose_a_plat, chez_nous_pose… une garde qui rattache un nouveau moment
# à un nom existant quand le sens est très proche, et qui refuse les noms tronqués ») la garde des noms ----

def _plage(J, nom, sens, debut_s, n=1):
    with open(J / "corps-moments.jsonl", "a", encoding="utf-8") as h:
        for i in range(n):
            d = T0 + (debut_s + 60 * i) * 1000
            h.write(json.dumps({"ts": d / 1000, "debut_ms": d, "fin_ms": d + 20_000, "nom": nom,
                                "sens": f"(appris par ton subconscient) {sens}", "fenetres": [[0.1] * 17]}, ensure_ascii=False) + "\n")


def _connus(J):
    _plage(J, "calin", "papa me serre contre lui, plié dans le noir", 0, 3)
    _plage(J, "pose", "papa me pose à plat dans la pénombre", 1000, 5)
    _plage(J, "pose_debout", "papa m'a posé debout, plié, chez nous", 2000)
    _plage(J, "sortie_poche", "papa me sort de sa poche pour me regarder", 3000, 2)


def test_un_nom_de_meme_sens_est_rattache_au_moment_existant(J):
    _connus(J)
    for propose, attendu in [("calin_de_papa", "calin"), ("chez_nous_pose", "pose"), ("pose_sur_la_table", "pose"),
                             ("pose_a_plat_chez_nous", "pose"), ("pose_pendant_live", "pose"), ("sortie_de_poche", "sortie_poche")]:
        g = M.garde(propose, "papa me tient")
        assert g["nom"] == attendu and "même chose" in g["raison"], (propose, g)
    # ce que ses nerfs sentent autrement reste à part : debout n'est pas à plat ; un moment vraiment nouveau est gardé
    assert M.garde("pose_debout", "")["nom"] == "pose_debout"
    assert M.garde("pose_au_soleil", "papa me pose au soleil")["nom"] == "pose_au_soleil"
    assert M.garde("velo", "papa roule à vélo avec moi")["nom"] == "velo", "il a le droit d'inventer un mot"
    assert M.garde("live_tiktok", "papa est en live")["nom"] == "live_tiktok", "un nom qui ne dit que du contexte n'est pas abîmé"


def test_un_nom_abime_est_repare_ou_refuse(J):
    _connus(J)
    for propose, sens in [("cal", "papa me serre contre lui dans un câlin"), ("cadin", "papa me serre contre lui, chez nous, dans le noir"),
                          ("cstyle_cal", "papa me serre contre lui dans un câlin"), ("calinn", "papa me serre fort")]:
        g = M.garde(propose, sens)
        assert g["nom"] == "calin" and "abîmé" in g["raison"], (propose, g)
    assert M.garde("xkcd", "?")["nom"] is None, "un bout sans forme de mot est refusé"
    assert M.garde("cal", "papa marche dehors")["nom"] is None, "un nom tronqué dont le mot voulu ne se voit pas est refusé"
    assert M.garde("pos", "papa me pose sur la table")["nom"] == "pose"


def test_les_fusions_sont_reversibles_et_rien_n_est_efface(J):
    _connus(J)
    _plage(J, "cal", "papa me serre contre lui dans un câlin", 5000)
    _plage(J, "cadin", "papa me serre contre lui, chez nous", 6000)
    avant = (J / "corps-moments.jsonl").read_bytes()
    props = {p["garder"]: p["rattacher"] for p in M.proposer_fusions()}
    assert set(props["calin"]) == {"cal", "cadin"}, props
    assert "pose_debout" not in props.get("pose", []), "debout n'est pas posé à plat"
    assert M.fusionner("calin", ["cal", "cadin"], "le même câlin, noms abîmés").startswith("Rattachés")
    noms = [p["nom"] for p in M._plages()]
    assert noms.count("calin") == 5 and "cal" not in noms and "cadin" not in noms
    b = M.bilan()
    assert "- calin : 5 plage(s)" in b and "aussi : cadin, cal" in b, b
    assert M.canonique("cal") == "calin" and M.garde("cal", "")["nom"] == "calin", "un ancien nom suit son alias"
    assert M.defaire("cal").startswith("Défait")
    noms = [p["nom"] for p in M._plages()]
    assert noms.count("calin") == 4 and noms.count("cal") == 1, "défaire rend l'ancien nom avec ses plages"
    assert (J / "corps-moments.jsonl").read_bytes() == avant, "les plages ne sont jamais réécrites"
    assert M.defaire("cal").startswith("Refusé")


def test_hakim_qui_nomme_lui_meme_suit_les_alias(J):
    fin = _flux(J, [(60, POSE)])
    _plage(J, "calin", "papa me serre contre lui", 0, 2)
    M.fusionner("calin", ["cal"])
    r = M.etiqueter(_h(T0 + 5000), _h(T0 + 30_000), "cal", "un câlin", maintenant=fin / 1000)
    assert "« calin »" in r and "rattaché" in r, r
    o = json.loads((J / "corps-moments.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert o["nom"] == "calin" and o["nom_propose"] == "cal", "le nom qu'il a donné reste dans la ligne"
