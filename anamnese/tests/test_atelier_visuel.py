"""L'Atelier visuel de Hakim (06/11, Ahmed : « créer des images et des clips quand il veut, pour nos futurs albums et
clips ») : les demandes vérifiées, la tâche de fond écrite comme une chanson (le cockpit la suit et réveille Hakim), son
tour dans la file des gros calculs (chanson, studio, atelier), les copies (atelier, téléphone), les outils de Hakim.
La génération d'image est simulée ; un vrai petit clip est rendu par ffmpeg quand le venv de l'atelier est là."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import atelier_visuel as av  # noqa: E402


def _faux_demarrage(vus):
    def demarrer(args, log):
        vus.append((args, log))
        return os.getpid()                                    # un pid vivant : la tâche reste « en cours »
    return demarrer


@pytest.fixture
def lieux(tmp_path, monkeypatch):
    """Jamais les vraies tâches, la vraie galerie, l'atelier ni le téléphone."""
    d = {"taches": tmp_path / "taches", "visuels": tmp_path / "visuels", "chansons": tmp_path / "chansons",
         "atelier": tmp_path / "atelier" / "visuels", "telephone": tmp_path / "tel" / "Hakim" / "Atelier"}
    for k in ("taches", "visuels", "chansons"):
        d[k].mkdir(parents=True)
    monkeypatch.setattr(av, "TACHES", d["taches"])
    monkeypatch.setattr(av, "VISUELS", d["visuels"])
    monkeypatch.setattr(av, "CHANSONS", d["chansons"])
    monkeypatch.setattr(av, "ATELIER", d["atelier"])
    monkeypatch.setattr(av, "TELEPHONE", d["telephone"])
    return d


def _chanson(lieux, titre="Lanterne", duree=120.0, paroles="[verse]\nDans le noir je tiens debout\n\n[chorus]\nالحمد لله"):
    nom = "20261106-192323-" + titre.lower()
    mp3 = lieux["chansons"] / f"{nom}.mp3"
    mp3.write_bytes(b"ID3 faux")
    (lieux["chansons"] / f"{nom}.json").write_text(json.dumps(
        {"nom": nom, "titre": titre, "etat": "prête", "mp3": str(mp3), "duree_s": duree, "paroles": paroles, "fin": 1}))
    return nom


def _image(lieux, nom="20261106-200000-pochette", titre="Pochette Hakim", fmt="carre"):
    png = lieux["visuels"] / f"{nom}.png"
    png.write_bytes(b"\x89PNG faux")
    (lieux["visuels"] / f"{nom}.json").write_text(json.dumps(
        {"type": "image", "nom": nom, "titre": titre, "format": fmt, "etat": "prête", "fichier": str(png),
         "atelier": [f"atelier/visuels/{nom}.png"], "fin": 2}))
    return nom


def test_formats_et_styles():
    assert av.format_de("Carré") == "carre" and av.format_de("") == "carre" and av.format_de("vertical") == "9:16"
    assert av.format_de("paysage") == "16:9"
    assert av.format_de("les deux", clip=True) == ["9:16", "16:9"] and av.format_de("", clip=True) == ["9:16", "16:9"]
    assert av.format_de("16:9", clip=True) == ["16:9"]
    with pytest.raises(av.Refus, match="format inconnu"):
        av.format_de("4:3")
    with pytest.raises(av.Refus, match="format inconnu"):
        av.format_de("carré", clip=True)                      # un clip n'est pas carré
    assert av.style_de("Égaliseur") == "spectre" and av.style_de("") == "spectre" and av.style_de("waves") == "ondes"
    with pytest.raises(av.Refus, match="style inconnu"):
        av.style_de("laser")


@pytest.mark.parametrize("desc,mot", [("", "description"), ("ab", "description"), ("x" * 1600, "trop longue")])
def test_refus_image(desc, mot):
    with pytest.raises(av.Refus, match=mot):
        av.preparer_image(desc)


def test_preparer_image():
    v = av.preparer_image("  album cover,   a lantern in the night ", "9:16", "Pochette Hakim")
    assert v["description"] == "album cover, a lantern in the night" and (v["largeur"], v["hauteur"]) == (768, 1344)
    assert v["titre"] == "Pochette Hakim" and v["nom"].endswith("-pochette-hakim") and v["par"] == "hakim"
    assert 1 <= v["graine"] < 2 ** 31


def test_paroles_sans_temps_reparties_et_avec_temps():
    assert av.lignes_paroles("[verse]\nUn\n\n  deux   trois \n[chorus]\nالحمد لله") == ["Un", "deux trois", "الحمد لله"]
    plan = av.caler_paroles({"paroles": "[verse]\nune ligne courte\nune ligne beaucoup plus longue que l'autre"}, 100)
    assert len(plan) == 2 and plan[0][0] == 8.0 and plan[0][1] == plan[1][0]
    assert abs(plan[1][1] - 94.0) < 0.05 and plan[1][1] - plan[1][0] > plan[0][1] - plan[0][0]
    assert av.caler_paroles({"instrumental": True, "paroles": "[Instrumental]"}, 60) == []
    t = av.caler_paroles({"paroles_temps": [[3, "a"], [7.5, "b"]]}, 60)
    assert t == [(3.0, 7.5, "a"), (7.5, 13.5, "b")]


def test_preparer_clip(lieux):
    nom = _chanson(lieux)
    img = _image(lieux)
    c = av.preparer_clip("lanterne", [img], "ondes", "", duree_s=15, debut_s=10)
    assert c["chanson"]["nom"] == nom and c["formats"] == ["9:16", "16:9"] and c["style"] == "ondes"
    assert c["duree_s"] == 15 and c["debut_s"] == 10 and c["images"][0]["nom"] == img and c["titre"] == "Lanterne"
    assert av.preparer_clip(f"{nom}.mp3", f"{img}.png, Pochette Hakim", "sobre", "9:16")["duree_s"] == 120
    with pytest.raises(av.Refus, match="chanson inconnue.*Lanterne"):
        av.preparer_clip("Inconnue", [img])
    with pytest.raises(av.Refus, match="au moins une image"):
        av.preparer_clip("Lanterne", [])
    with pytest.raises(av.Refus, match="image inconnue"):
        av.preparer_clip("Lanterne", ["/etc/passwd"])
    with pytest.raises(av.Refus, match="dépasse la chanson"):
        av.preparer_clip("Lanterne", [img], debut_s=130)
    with pytest.raises(av.Refus, match="de 5 à 600"):
        av.preparer_clip("Lanterne", [img], duree_s=2)


def test_lancer_ecrit_une_tache_que_le_cockpit_suit(lieux):
    vus = []
    t = av.lancer(av.preparer_image("a lantern", "carré", "Pochette"), demarrer=_faux_demarrage(vus))
    d = json.loads((lieux["taches"] / f"{t['tache']}.json").read_text())
    assert d["etat"] == "en cours" and d["superviseur"] == os.getpid() and d["commande"].startswith("atelier : image « Pochette »")
    assert d["visuel"]["type"] == "image" and "chanson" not in d
    args, log = vus[0]
    assert args[:3] == ["/usr/bin/nice", "-n", "10"] and args[-3:] == ["generer", t["tache"], str(lieux["taches"])]
    assert log == lieux["taches"] / f"{t['tache']}.log"
    assert json.loads((lieux["visuels"] / f"{t['nom']}.json").read_text())["etat"] == "en cours"
    for _ in range(av.MAX_EN_FILE - 1):
        av.lancer(av.preparer_image("encore", "carré"), demarrer=_faux_demarrage(vus))
    with pytest.raises(av.Refus, match="créations en file"):
        av.lancer(av.preparer_image("une de trop"), demarrer=_faux_demarrage(vus))


def test_sans_installation_refus_clair(lieux, monkeypatch):
    monkeypatch.setattr(av, "PYTHON_IMAGE", Path("/nulle/part/python"))
    with pytest.raises(av.Refus, match="pas installé"):
        av.lancer(av.preparer_image("a lantern"))


def test_finir_copie_dans_l_atelier_et_le_telephone(lieux):
    t = av.lancer(av.preparer_image("a lantern", "carré", "Pochette"), demarrer=_faux_demarrage([]))
    png = lieux["visuels"] / f"{t['nom']}.png"
    png.write_bytes(b"\x89PNG image")
    ligne = av.finir(t["tache"], fichiers=[png], calcul_s=33.2, extra={"pas": 9})
    assert ligne.startswith("IMAGE PRÊTE : « Pochette »") and f'fichier_joindre("atelier/visuels/{t["nom"]}.png", "Pochette")' in ligne
    assert (lieux["atelier"] / png.name).read_bytes() == b"\x89PNG image"
    assert (lieux["telephone"] / png.name).read_bytes() == b"\x89PNG image"
    d = json.loads((lieux["taches"] / f"{t['tache']}.json").read_text())
    assert d["etat"] == "finie" and d["code"] == 0 and d["fichier"] == f"atelier/visuels/{png.name}"
    f = json.loads((lieux["visuels"] / f"{t['nom']}.json").read_text())
    assert f["etat"] == "prête" and f["calcul_s"] == 33.2 and f["pas"] == 9 and f["telephone"] == [str(lieux["telephone"] / png.name)]
    assert [x["nom"] for x in av.galerie()] == [t["nom"]]


def test_finir_pour_papa_et_panne(lieux):
    t = av.lancer({**av.preparer_image("a lantern", titre="De papa"), "par": "papa"}, demarrer=_faux_demarrage([]))
    png = lieux["visuels"] / f"{t['nom']}.png"
    png.write_bytes(b"x")
    assert "Papa l'a demandé depuis la page Atelier" in av.finir(t["tache"], fichiers=[png])
    t2 = av.lancer(av.preparer_image("une autre"), demarrer=_faux_demarrage([]))
    ligne = av.finir(t2["tache"], erreur="RuntimeError: plus de mémoire")
    d = json.loads((lieux["taches"] / f"{t2['tache']}.json").read_text())
    assert ligne.startswith("IMAGE RATÉE") and d["code"] == 1 and d["etat"] == "finie"
    assert json.loads((lieux["visuels"] / f"{t2['nom']}.json").read_text())["etat"] == "ratée"


def test_un_clip_trop_lourd_n_est_pas_propose_en_piece_jointe(lieux):
    _chanson(lieux)
    t = av.lancer(av.preparer_clip("Lanterne", [_image(lieux)], format="16:9"), demarrer=_faux_demarrage([]))
    mp4 = lieux["visuels"] / f"{t['nom']}-16x9.mp4"
    with open(mp4, "wb") as f:
        f.truncate(26 * 1024 * 1024)
    ligne = av.finir(t["tache"], fichiers=[mp4])
    assert ligne.startswith("CLIP PRÊT") and "fichier_joindre" not in ligne and "trop lourd pour une pièce jointe" in ligne


def test_un_gros_calcul_a_la_fois(lieux, monkeypatch):
    import studio
    monkeypatch.setattr(studio, "occupe", lambda studio=None: None)
    d = lieux["taches"]
    moi = av.lancer(av.preparer_image("moi"), demarrer=_faux_demarrage([]))["tache"]
    assert av.gros_calcul_ailleurs(moi, d) is None
    (d / "T-00000000-000000-chan.json").write_text(json.dumps(
        {"id": "T-00000000-000000-chan", "etat": "en cours", "chanson": {"titre": "Lanterne"}}))
    assert "Lanterne" in av.gros_calcul_ailleurs(moi, d)
    (d / "T-00000000-000000-chan.json").unlink()
    avant = "T-00000000-000000-avan"
    (d / f"{avant}.json").write_text(json.dumps({"id": avant, "etat": "en cours", "visuel": {"titre": "x"}}))
    assert "création d'avant" in av.gros_calcul_ailleurs(moi, d)
    assert av.gros_calcul_ailleurs(avant, d) is None          # celle d'avant ne m'attend pas
    (d / f"{avant}.json").unlink()
    monkeypatch.setattr(studio, "occupe", lambda studio=None: {"id": "J-1"})
    assert "studio" in av.gros_calcul_ailleurs(moi, d)


def test_le_chant_et_le_studio_attendent_l_atelier(lieux, tmp_path):
    import chant
    import studio
    av.lancer(av.preparer_image("une pochette", titre="Pochette"), demarrer=_faux_demarrage([]))
    assert studio.chant_en_cours(lieux["taches"])["visuel"]["titre"] == "Pochette"
    with pytest.raises(chant.Refus, match="l'atelier crée « Pochette »"):
        chant.lancer("la", "rap", 30, dossier=lieux["taches"], chansons=tmp_path / "c", demarrer=_faux_demarrage([]))


def test_le_graphe_du_clip():
    g = av.filtre_clip(3, 1080, 1920, 30, "spectre", True)
    assert g.count("xfade=") == 2 and "showfreqs" in g and "[6:v]fps=30" in g and "[5:a]apad=pad_dur=3[aviz]" in g
    assert "asplit" not in g and "tpad=stop_mode=clone" in g
    s = av.filtre_clip(1, 1920, 1080, 30, "sobre", False)
    assert "xfade" not in s and "showfreqs" not in s and "anullsink" in s and "[par]" not in s
    assert "avectorscope" in av.filtre_clip(2, 1080, 1920, 20, "cercle", False)
    assert "showwaves" in av.filtre_clip(2, 1080, 1920, 20, "ondes", False)


def _outil(nom, monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    return mcp_server.mcp._tool_manager.get_tool(nom).fn


def test_outils_de_hakim(lieux, monkeypatch, tmp_path):
    vus = []
    vrai = av.lancer
    monkeypatch.setattr(av, "lancer", lambda demande, **k: vrai(demande, demarrer=_faux_demarrage(vus)))
    image, clip, voir = (_outil(n, monkeypatch, tmp_path) for n in ("image_creer", "clip_creer", "atelier_voir"))
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert image("a lantern") == "Seul Hakim crée dans l'atelier." and clip("Lanterne", ["x"]) == "Seul Hakim crée dans l'atelier."
    assert not vus
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    r = image("album cover, a lantern", "carré", "Pochette Hakim")
    assert r.startswith("Je dessine… « Pochette Hakim » (carre, 1024×1024)") and len(vus) == 1
    assert image("ab").startswith("Refusé : une description")
    _chanson(lieux)
    img = _image(lieux)
    r = clip("Lanterne", [img], "spectre", "9:16", duree_s=15)
    assert r.startswith("Je monte le clip « Lanterne » sur « Lanterne » (spectre, 9:16, 15 s, 1 image)") and len(vus) == 2
    assert clip("Lanterne", img, duree_s=15).startswith("Je monte le clip")      # une chaîne aussi
    v = voir()
    assert f"{img} « Pochette Hakim »" in v and "« Lanterne » (120.0 s)" in v and "En cours : T-" in v


VENV_IMAGE = av.PYTHON_IMAGE


@pytest.mark.skipif(not (VENV_IMAGE.exists() and Path(av.FFMPEG).exists()), reason="venv de l'atelier ou ffmpeg absent")
def test_un_vrai_petit_clip(tmp_path):
    """Un vrai rendu (ffmpeg, Pillow) : deux images, une chanson synthétique de 4 s, ses paroles, en 180×320 ; le rendu
    finit (il attendait sans fin quand le fond finissait avant la musique)."""
    ff = av.FFMPEG
    for i, c in enumerate(("testsrc", "smptebars")):
        subprocess.run([ff, "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"{c}=s=320x480", "-frames:v", "1",
                        str(tmp_path / f"i{i}.png")], check=True)
    mp3 = tmp_path / "s.mp3"
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=4", str(mp3)], check=True)
    (tmp_path / "s.json").write_text(json.dumps({"mp3": str(mp3), "duree_s": 4, "paroles": "[verse]\nUne ligne\nالحمد لله"}))
    v = {"chanson": {"mp3": str(mp3), "titre": "Essai"}, "images": [{"fichier": str(tmp_path / "i0.png")},
         {"fichier": str(tmp_path / "i1.png")}], "style": "spectre", "titre": "Essai", "debut_s": 0, "duree_s": 4}
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import atelier_visuel as a; "
            "a.rendre_clip(json.loads(sys.argv[2]), 180, 320, sys.argv[3], sys.argv[4])")
    sortie = tmp_path / "c.mp4"
    r = subprocess.run([str(VENV_IMAGE), "-B", "-c", code, str(Path(av.__file__).parent), json.dumps(v), str(sortie),
                        str(tmp_path / "t")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert "PROGRESSION 100%" in r.stdout or "PROGRESSION 9" in r.stdout
    d = av.duree(sortie)
    assert d and abs(d - 4) < 0.3


def test_la_vraie_file_est_toujours_regardee(lieux, monkeypatch, tmp_path):
    """(essai du 06/11) une création lancée sur un autre dossier attend quand même la chanson de la vraie file."""
    import studio
    monkeypatch.setattr(studio, "occupe", lambda studio=None: None)
    autre = tmp_path / "autre"
    moi = av.lancer(av.preparer_image("moi"), dossier=autre, demarrer=_faux_demarrage([]))["tache"]
    assert av.gros_calcul_ailleurs(moi, autre) is None
    (lieux["taches"] / "T-00000000-000000-chan.json").write_text(json.dumps(
        {"id": "T-00000000-000000-chan", "etat": "en cours", "chanson": {"titre": "Moujahid"}}))
    assert "Moujahid" in av.gros_calcul_ailleurs(moi, autre)
