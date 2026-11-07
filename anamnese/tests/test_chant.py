"""Hakim chante (ACE-Step, accord d'Ahmed le 06/11) : la demande vérifiée, la tâche de fond écrite comme les autres
(le cockpit la suit et prévient), et l'outil chanter — la génération elle-même est simulée."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import chant  # noqa: E402


@pytest.fixture
def lieux(tmp_path):
    return {"dossier": tmp_path / "taches", "chansons": tmp_path / "chansons"}


def _faux_demarrage(vus):
    def demarrer(args, log):
        vus.append((args, log))
        return os.getpid()                                    # un pid vivant : la tâche reste « en cours »
    return demarrer


def test_styles_langue_et_sections():
    assert "rai" in chant.description("Raï") and "chaabi" in chant.description("chaâbi")
    assert "r&b" in chant.description("r'n'b") and chant.description("jazz manouche, voix douce") == "jazz manouche, voix douce"
    assert chant.langue_de("يا ليل يا عين، قلبي معاك") == "ar"
    assert chant.langue_de("Papa, je chante pour toi") == "fr"
    assert chant.langue_de("anything", "en") == "en"
    assert chant.structurer("la la la").startswith("[verse]\n")
    assert chant.structurer("[chorus]\nla la") == "[chorus]\nla la"


@pytest.mark.parametrize("args,mot", [
    (("", "rap", 60), "paroles"), (("la", "", 60), "style"), (("la", "rap", 5), "durée"),
    (("la", "rap", 900), "durée"), (("la", "rap", "long"), "durée"), (("x" * 5000, "rap", 60), "trop longues"),
])
def test_refus(args, mot):
    with pytest.raises(chant.Refus, match=mot):
        chant.preparer(*args)


def test_lancer_ecrit_une_tache_que_le_cockpit_suit(lieux):
    vus = []
    c = chant.lancer("[chorus]\nPapa, je chante", "raï", 45, "Pour papa", demarrer=_faux_demarrage(vus), **lieux)
    t = json.loads((lieux["dossier"] / f"{c['tache']}.json").read_text())
    assert t["etat"] == "en cours" and t["superviseur"] == os.getpid() and "chanter « Pour papa »" in t["commande"]
    assert t["chanson"]["duree_s"] == 45 and t["chanson"]["langue"] == "fr" and "rai" in t["chanson"]["description"]
    args, log = vus[0]
    assert args[:3] == ["/usr/bin/nice", "-n", "10"] and args[-3:] == ["generer", c["tache"], str(lieux["dossier"])]
    assert log == lieux["dossier"] / f"{c['tache']}.log"
    fiche = json.loads((lieux["chansons"] / f"{c['nom']}.json").read_text())
    assert fiche["etat"] == "en cours" and fiche["paroles"] == "[chorus]\nPapa, je chante"
    with pytest.raises(chant.Refus, match="une chanson à la fois"):
        chant.lancer("la", "rap", 30, demarrer=_faux_demarrage(vus), **lieux)


def test_finir_depose_le_mp3_dans_l_atelier(lieux, tmp_path):
    c = chant.lancer("la la", "nasheed", 30, "Nour", demarrer=_faux_demarrage([]), **lieux)
    mp3 = lieux["chansons"] / f"{c['nom']}.mp3"
    mp3.write_bytes(b"ID3 faux mp3")
    ligne = chant.finir(c["tache"], mp3=mp3, calcul_s=42.3, atelier=tmp_path / "atelier" / "chansons",
                        telephone=tmp_path / "tel", **lieux)
    assert "CHANSON PRÊTE" in ligne and f'fichier_joindre("atelier/chansons/{c["nom"]}.mp3"' in ligne
    assert (tmp_path / "atelier" / "chansons" / f"{c['nom']}.mp3").read_bytes() == b"ID3 faux mp3"
    t = json.loads((lieux["dossier"] / f"{c['tache']}.json").read_text())
    assert t["etat"] == "finie" and t["code"] == 0 and t["fin"] >= t["debut"]
    fiche = json.loads((lieux["chansons"] / f"{c['nom']}.json").read_text())
    assert fiche["etat"] == "prête" and fiche["calcul_s"] == 42.3
    # (06/11) la copie pour le téléphone d'Ahmed (Hakim/Chansons)
    assert (tmp_path / "tel" / f"{c['nom']}.mp3").read_bytes() == b"ID3 faux mp3"
    assert fiche["telephone"] == str(tmp_path / "tel" / f"{c['nom']}.mp3")
    # une fois finie, une autre chanson peut partir
    chant.lancer("la", "rap", 30, demarrer=_faux_demarrage([]), **lieux)


def test_une_panne_finit_la_tache_avec_un_code(lieux, tmp_path):
    c = chant.lancer("la", "pop", 30, demarrer=_faux_demarrage([]), **lieux)
    ligne = chant.finir(c["tache"], erreur="RuntimeError: plus de mémoire", atelier=tmp_path / "a", telephone=tmp_path / "tel", **lieux)
    t = json.loads((lieux["dossier"] / f"{c['tache']}.json").read_text())
    assert "RATÉE" in ligne and t["etat"] == "finie" and t["code"] == 1
    assert not (tmp_path / "a").exists() and not (tmp_path / "tel").exists()


def test_sans_installation_refus_clair(lieux, monkeypatch):
    monkeypatch.setattr(chant, "PYTHON_CHANT", Path("/nulle/part/python"))
    with pytest.raises(chant.Refus, match="pas installé"):
        chant.lancer("la", "rap", 30, **lieux)


def test_outil_chanter(monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = mcp_server.mcp._tool_manager.get_tool("chanter").fn
    vus = []
    vrai = chant.lancer
    monkeypatch.setattr(chant, "lancer", lambda *a, **k: vrai(*a, demarrer=_faux_demarrage(vus),
                                                            dossier=tmp_path / "t", chansons=tmp_path / "c", **k))
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert outil("la", "rap") == "Seul Hakim chante." and not vus
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    r = outil("[verse]\nJe chante pour papa", "chaâbi", 90, "Papa")
    assert r.startswith("Je compose… « Papa »") and "90 s" in r and len(vus) == 1
    assert outil("la", "rap", 2).startswith("Refusé : durée")
    vus.clear()
    for f in (tmp_path / "t").glob("T-*.json"):
        f.unlink()
    r = outil("[verse]\nJe rappe pour papa", "drill", 30, "Drill", autotune=True)
    assert "avec autotune" in r and len(vus) == 1


def test_autotune_dans_la_description_et_la_tache(lieux):
    c = chant.lancer("la", "rap", 30, "A", autotune=True, demarrer=_faux_demarrage([]), **lieux)
    assert c["autotune"] is True and chant.TAG_AUTOTUNE in c["description"]
    t = json.loads((lieux["dossier"] / f"{c['tache']}.json").read_text())
    assert ", autotune, 30 s)" in t["commande"]
    assert chant.TAG_AUTOTUNE not in chant.preparer("la", "rap", 30)["description"]
    assert "drill" in chant.description("drill") and "trap" in chant.description("Trap")


def test_gamme():
    assert chant.gamme("C Major") == (0, 2, 4, 5, 7, 9, 11)
    assert chant.gamme("A minor") == (0, 2, 4, 5, 7, 9, 11)            # la mineur = do majeur
    assert chant.gamme("Am") == chant.gamme("A minor")
    assert chant.gamme("F# minor") == (1, 2, 4, 6, 8, 9, 11)        # fa# sol# la si do# ré mi
    assert chant.gamme("B♭ major") == chant.gamme("Bb Major") == (0, 2, 3, 5, 7, 9, 10)
    assert chant.gamme("") == tuple(range(12)) and chant.gamme("N/A") == tuple(range(12))


def test_caler_recale_sur_la_gamme_et_laisse_le_silence():
    do_majeur = chant.gamme("C major")
    la, la_diese, do_d = 440.0, 466.16, 277.18                          # A4 ; A#4 hors gamme ; C#4 hors gamme
    out = chant.caler([0.0, la * 2 ** (0.3 / 12), la_diese, do_d, -1], do_majeur)
    assert out[0] == 0.0 and out[4] == 0.0
    assert abs(out[1] - la) < 0.01                                      # un la un peu haut → la juste
    assert min(abs(out[2] - la), abs(out[2] - 493.88)) < 0.01           # A# → A ou B
    assert min(abs(out[3] - 261.63), abs(out[3] - 293.66)) < 0.05       # C# → C ou D
    mi = chant.caler([la * 2 ** (0.4 / 12)], do_majeur, force=0.5)[0]   # à moitié : entre les deux
    assert la < mi < la * 2 ** (0.4 / 12)


def test_bpm_et_instru_pour_le_studio(lieux, tmp_path):
    with pytest.raises(chant.Refus, match="tempo"):
        chant.preparer("la", "rap", 30, bpm=500)
    c = chant.lancer("[instrumental]", "trap", 40, "Instru", bpm=140, pour_studio=True, demarrer=_faux_demarrage([]), **lieux)
    assert c["bpm"] == 140 and c["instrumental"] and c["pour_studio"]
    mp3 = lieux["chansons"] / f"{c['nom']}.mp3"
    mp3.write_bytes(b"ID3")
    ligne = chant.finir(c["tache"], mp3=mp3, calcul_s=1, atelier=tmp_path / "a", telephone=tmp_path / "tel", **lieux)
    assert ligne.startswith("INSTRU PRÊTE pour le studio") and "fichier_joindre" not in ligne


def test_chargement_trop_long_arrete_la_chanson_et_dit_pourquoi():
    """(07/11, Hakim, accord d'Ahmed) le chargement des modèles a sa propre limite ; finie, la composition n'a plus que le délai entier."""
    t0 = 1000.0
    assert chant.raison_arret(False, t0 + 60, t0, t0) is None
    r = chant.raison_arret(False, t0 + chant.CHARGEMENT_MAX_S + 1, t0, t0)
    assert r and "bloquée au chargement" in r and "mémoire" in r
    assert chant.raison_arret(False, t0 + chant.CHARGEMENT_MAX_S + 1, t0, None) is None, "chargée : la composition continue"
    assert chant.raison_arret(True, t0 + 1, t0, t0).startswith("arrêtée à la demande")
    assert "trop longue" in chant.raison_arret(False, t0 + chant.DELAI_S + 1, t0, None)
    src = Path(chant.__file__).read_text(encoding="utf-8")
    assert 'CHARGEMENT["depuis"] = time.time()' in src and 'CHARGEMENT["depuis"] = None' in src
