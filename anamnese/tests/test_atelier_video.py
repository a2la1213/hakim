"""L'atelier VIDÉO (13/11, Ahmed : « uploader ses photos et ses musiques et en faire des vidéos TikTok, Insta ») : la médiathèque
(types vérifiés par leurs octets, HEIC converti, aperçus, collections, effacement, jamais hors de la médiathèque), l'écoute
(temps à la milliseconde, meilleur passage = le refrain), le son (−14 LUFS, crête vraie ≤ −1 dBTP), les coupes sur les temps,
l'export (ffprobe : dimensions, durée, H.264 High, AAC 48 kHz, BT.709, faststart), la tâche de fond, le réglage, les outils.

Chaque mécanisme a son TÉMOIN : le même test, mécanisme coupé (atelier_video.COUPE), doit échouer à la même mesure.
Les sons et les images viennent de atelier_video_synthese.py (vérité connue, aucune photo privée). Les rendus tournent dans
le python de la vidéo (Pillow), comme en vrai ; ils sont sautés s'il manque."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ICI = Path(__file__).resolve().parent
JARVIS_CODE = ICI.parent / "jarvis"
sys.path.insert(0, str(JARVIS_CODE))
sys.path.insert(0, str(ICI))
import atelier_video as av  # noqa: E402
import atelier_video_synthese as syn  # noqa: E402

PY = av.python_video()
FF = Path(av.FFMPEG).exists() and Path(av.FFPROBE).exists()
A_PILLOW = FF and PY.exists() and subprocess.run([str(PY), "-c", "import PIL, numpy"], capture_output=True).returncode == 0
rendu = pytest.mark.skipif(not A_PILLOW, reason="python de la vidéo (Pillow + numpy) ou ffmpeg absent")
ffmpeg = pytest.mark.skipif(not FF, reason="ffmpeg absent")

PILOTE = r'''
import json, os, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
import atelier_video as av
av.COUPE = frozenset(x for x in os.environ.get("COUPE", "").split(",") if x)
q = json.loads(sys.argv[3])
op = q.pop("op")
if op == "photos":
    import atelier_video_synthese as s
    for i, c in enumerate(q["chemins"]):
        s.photo(q.get("depart", 0) + i, *q.get("taille", [600, 800]), chemin=c)
    r = {}
elif op == "importer":
    try:
        r = av.importer(q["src"], q["collection"], q.get("nom"))
    except av.Refus as e:
        r = {"refus": str(e)}
elif op == "garde":
    r = {"pixels": av._pil().MAX_IMAGE_PIXELS}
elif op == "calques":
    from PIL import Image
    Image.new("RGB", (600, 800), (90, 90, 90)).save(q["photo"])
    r = {}
    for fm, (W, H) in av.FORMATS.items():
        m = av.Montage([q["photo"]], [1.0], 4.0, W, H, "nette", q["textes"])
        boites = {}
        for nom, x in [("marque", m.textes["marque"]), ("appel", m.textes["appel"])] + [("bas", c) for c in m.textes["bas"]]:
            if x:
                b = x[0].getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
                boites[nom] = [x[1] + b[0], x[2] + b[1], x[1] + b[2], x[2] + b[3]]
        r[fm] = boites
elif op == "rendre":
    v = av.preparer(**q["demande"])
    f, m = av.rendre(v, q["sortie"], q["travail"], progres=lambda s: None)
    r = {"fichiers": [str(x) for x in f], "mesures": m, "recette": v}
print("RESULTAT " + json.dumps(r, ensure_ascii=False, default=str))
'''


def pilote(jarvis, op, coupe=(), timeout=300, **q):
    env = {**os.environ, "JARVIS_DIR": str(jarvis), "COUPE": ",".join(coupe), "JARVIS_TELEPHONE_VIDEOS": str(Path(jarvis) / "tel")}
    env.pop("JARVIS_ATELIER_VIDEO", None)
    r = subprocess.run([str(PY), "-B", "-c", PILOTE, str(JARVIS_CODE), str(ICI), json.dumps({"op": op, **q})], capture_output=True,
                       text=True, timeout=timeout, env=env)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.split("RESULTAT ", 1)[1])


@pytest.fixture
def lieux(tmp_path, monkeypatch):
    """Jamais la vraie médiathèque, les vraies vidéos, la vraie file, l'atelier ni le téléphone."""
    J = tmp_path / "jarvis"
    d = {"jarvis": J, "med": J / "mediatheque", "videos": J / "videos", "taches": J / "cwd" / "taches",
         "atelier": J / "cwd" / "atelier" / "videos", "fichiers": J / "cwd" / "fichiers", "tel": J / "tel"}
    for k in ("med", "videos", "taches", "fichiers"):
        d[k].mkdir(parents=True)
    for nom, k in (("JARVIS", "jarvis"), ("MEDIATHEQUE", "med"), ("VIDEOS", "videos"), ("TACHES", "taches"),
                   ("ATELIER", "atelier"), ("FICHIERS", "fichiers"), ("TELEPHONE", "tel")):
        monkeypatch.setattr(av, nom, d[k])
    monkeypatch.setattr(av, "MODULES", J / "modules.json")
    monkeypatch.setattr(av, "COUPE", frozenset())
    monkeypatch.delenv("JARVIS_ATELIER_VIDEO", raising=False)
    return d


def _wav(chemin, secondes=3.0, f=220.0, amp=0.3):
    t = np.arange(int(secondes * 44100)) / 44100
    return syn.ecrire(chemin, (amp * np.sin(2 * np.pi * f * t)).astype(np.float32))


# ------------------------------------------------------------------------------------------------ les réglages, les formats

def test_formats_rythmes_durees():
    assert av.format_de("TikTok") == "9:16" and av.format_de("reels") == "9:16" and av.format_de("Shorts") == "9:16"
    assert av.format_de("post insta") == "4:5" and av.format_de("carré") == "1:1" and av.format_de("") == "9:16"
    assert av.formats_de("9:16 et 4:5") == ["9:16", "4:5"] and av.formats_de("tous") == ["9:16", "4:5", "1:1"]
    assert av.FORMATS["9:16"] == (1080, 1920) and av.FORMATS["4:5"] == (1080, 1350) and av.FORMATS["1:1"] == (1080, 1080)
    assert av.rythme_de("Rapide") == "rapide" and av.rythme_de("") == "auto" and av.transition_de("fondu") == "fondu"
    for d in (7, 15, 30, 60):
        assert av.duree_de(d) == d
    for mauvais in ("16:9 cinéma", "paysage"):
        with pytest.raises(av.Refus):
            av.format_de(mauvais)
    for d in (2, 120, "beaucoup"):
        with pytest.raises(av.Refus):
            av.duree_de(d)


def test_reglage_atelier_video(lieux, monkeypatch):
    """Allumé par défaut ; « atelier_video » à plat ou sous « modules » (profils de modules) l'éteint ; la variable d'environnement
    passe devant. Éteint : aucune vidéo ne se lance."""
    assert av.allume()
    (lieux["jarvis"] / "modules.json").write_text(json.dumps({"atelier_video": False, "studio": False}))
    assert not av.allume()
    (lieux["jarvis"] / "modules.json").write_text(json.dumps({"modules": {"atelier_video": False}}))
    assert not av.allume()
    with pytest.raises(av.Refus, match="éteint"):
        av.preparer(photos="x.jpg")
    monkeypatch.setenv("JARVIS_ATELIER_VIDEO", "1")
    assert av.allume()
    (lieux["jarvis"] / "modules.json").write_text(json.dumps({"modules": {"atelier_video": True, "studio": False}}))
    monkeypatch.delenv("JARVIS_ATELIER_VIDEO")
    assert av.allume()


def test_textes_d_affichage_propres():
    assert av._texte("Manteau 🧥 laine\n  bouillie", 80) == "Manteau laine bouillie"
    assert av._texte("189 €", 20) == "189 €" and av._texte("\x00x‮", 9) == "x"


# ------------------------------------------------------------------------------------------------ la médiathèque

def test_noms_de_collection_et_de_fichier_restent_dans_la_mediatheque(lieux):
    med = lieux["med"]
    assert av.nom_collection("  Hiver   2026 ") == "Hiver 2026"
    for brut in ("../../etc", "/etc/passwd", "..", "Hiver/../../x", ".cache", "_polices"):
        try:
            d = av.dossier_collection(brut, med)
        except av.Refus:
            continue
        assert av._dans(med, d) and d.parent == med and not d.name.startswith((".", "_"))
    assert av.nom_fichier("../../IMG 0001 (1).JPG") == "IMG 0001 (1).jpg"
    assert av.nom_fichier("Moujahid 3.1 (Hakim).m4a") == "Moujahid 3.1 (Hakim).m4a"
    assert av.nom_fichier("...cache.mp3") == "cache.mp3"
    assert "/" not in av.nom_fichier("a/b\\c<d>.png")


def test_le_type_se_lit_dans_les_octets():
    assert av.genre_de(b"\xff\xd8\xff\xe0" + b"\0" * 20) == ("photo", ".jpg")
    assert av.genre_de(b"\x89PNG\r\n\x1a\n" + b"\0" * 8) == ("photo", ".png")
    assert av.genre_de(b"\0\0\0\x18ftypheic" + b"\0" * 8) == ("photo", ".heic")
    assert av.genre_de(b"\0\0\0\x18ftypM4A " + b"\0" * 8) == ("musique", ".m4a")
    assert av.genre_de(b"RIFF\0\0\0\0WAVEfmt ") == ("musique", ".wav")
    assert av.genre_de(b"ID3\x04\0") == ("musique", ".mp3")
    assert av.genre_de(b"MZ\x90\0") == (None, None) and av.genre_de(b"<html>") == (None, None)


@ffmpeg
def test_importer_une_musique_et_refuser_le_reste(lieux, tmp_path):
    src = _wav(tmp_path / "son du défilé.wav")
    f = av.importer(src, "Hiver", med=lieux["med"])
    assert f["type"] == "musique" and f["fichier"] == "son du défilé.wav" and 2.9 < f["duree_s"] < 3.1
    assert (lieux["med"] / "Hiver" / "son du défilé.wav").is_file() and src.is_file()       # copié, l'original reste
    f2 = av.importer(src, "Hiver", med=lieux["med"])
    assert f2["fichier"] == "son du défilé 2.wav"                                           # jamais par-dessus
    faux = tmp_path / "photo.jpg"
    faux.write_text("ceci n'est pas une photo")
    with pytest.raises(av.Refus, match="type refusé"):
        av.importer(faux, "Hiver", med=lieux["med"])
    vide = tmp_path / "vide.mp3"
    vide.write_bytes(b"")
    with pytest.raises(av.Refus, match="vide"):
        av.importer(vide, "Hiver", med=lieux["med"])
    tronque = tmp_path / "tronque.mp3"
    tronque.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 50)
    with pytest.raises(av.Refus, match="illisible"):
        av.importer(tronque, "Hiver", med=lieux["med"])
    assert sorted(x.name for x in (lieux["med"] / "Hiver").iterdir()) == ["son du défilé 2.wav", "son du défilé.wav"]


@rendu
def test_importer_des_photos_jpg_png_heic_avec_apercu(lieux, tmp_path):
    J = lieux["jarvis"]
    srcs = [str(tmp_path / f"p{i}.{e}") for i, e in enumerate(("jpg", "png", "webp"))]
    pilote(J, "photos", chemins=srcs)
    for s in srcs:
        r = pilote(J, "importer", src=s, collection="Été 2027", nom=Path(s).name)
        assert r.get("type") == "photo", r
        assert (lieux["med"] / "Été 2027" / r["fichier"]).is_file()
        assert av.apercu_de("Été 2027", r["fichier"], lieux["med"]).is_file() and max(r["apercu_l"], r["apercu_h"]) == 480
    # un faux JPEG (le bon début, puis rien) : refusé, et aucun aperçu ne reste
    casse = tmp_path / "casse.jpg"
    casse.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 40)
    r = pilote(J, "importer", src=str(casse), collection="Été 2027")
    assert "illisible" in r.get("refus", ""), r
    assert not (lieux["med"] / "Été 2027" / "casse.jpg").exists()
    # le HEIC (fabriqué par sips sur le Mac) devient un JPEG
    if subprocess.run(["which", "sips"], capture_output=True).returncode == 0:
        heic = tmp_path / "IMG_0001.HEIC"
        subprocess.run(["sips", "-s", "format", "heic", srcs[0], "--out", str(heic)], capture_output=True, check=True)
        r = pilote(J, "importer", src=str(heic), collection="Été 2027")
        assert r.get("fichier") == "IMG_0001.jpg", r
        assert (lieux["med"] / "Été 2027" / "IMG_0001.jpg").read_bytes()[:3] == b"\xff\xd8\xff"
    l = av.lister(med=lieux["med"])["collections"]
    assert [c["nom"] for c in l] == ["Été 2027"] and all(p["apercu"] for p in l[0]["photos"])


@rendu
def test_une_photo_de_200_mpx_n_est_pas_une_bombe(lieux):
    """Le Galaxy S26 Ultra fait des photos de 200 Mpx : la garde de Pillow (178 Mpx) les aurait refusées."""
    assert pilote(lieux["jarvis"], "garde")["pixels"] >= 200_000_000


@ffmpeg
def test_lister_chercher_et_effacer(lieux, tmp_path):
    med = lieux["med"]
    av.importer(_wav(tmp_path / "a.wav"), "Hiver", med=med)
    (med / "Hiver" / "look 1.jpg").write_bytes(b"\xff\xd8\xff faux")
    (med / ".depot").mkdir()
    (med / "_polices").mkdir()
    (med / "Vide").mkdir()
    l = av.lister(med=med)
    assert [c["nom"] for c in l["collections"]] == ["Hiver", "Vide"]
    assert [p["fichier"] for p in l["collections"][0]["photos"]] == ["look 1.jpg"]
    assert av._chercher("Hiver/look 1.jpg", ("photo",), med)[1].name == "look 1.jpg"
    assert av._chercher("look 1", ("photo",), med)[0] == "Hiver" and av._chercher("a", ("photo",), med) is None
    assert av.photos_de("", "hiver", med) == [{"collection": "Hiver", "fichier": "look 1.jpg"}]
    assert av.musique_de("a.wav", med) == {"collection": "Hiver", "fichier": "a.wav"} and av.musique_de("sans musique", med) is None
    with pytest.raises(av.Refus, match="inconnue"):
        av.musique_de("n'existe pas", med, chansons=tmp_path / "rien")
    for mauvais in ("../a.wav", "../../modules.json", "a.txt"):
        with pytest.raises(av.Refus):
            av.effacer("Hiver", mauvais, med)
    with pytest.raises(av.Refus, match="pas vide"):
        av.effacer("Hiver", "", med)
    av.effacer("Hiver", "a.wav", med)
    av.effacer("Hiver", "look 1.jpg", med)
    av.effacer("Hiver", "", med)
    assert [c["nom"] for c in av.lister(med=med)["collections"]] == ["Vide"]


# ------------------------------------------------------------------------------------------------ l'écoute

def _ecart_ms(detectes, vrais):
    return np.array([np.min(np.abs(np.asarray(vrais) - t)) for t in detectes]) * 1000


def _calage(tmp_path, bpm, debut, coupe=frozenset()):
    x, vrais, _ = syn.morceau(bpm, 30, debut, seed=3)
    f = syn.ecrire(tmp_path / f"m{bpm}.mp3", x)
    av.COUPE = coupe
    try:
        an = av.analyser(f)
    finally:
        av.COUPE = frozenset()
    t = np.array(an["temps"])
    e = _ecart_ms(t[t < 29], vrais)
    return an, e


@ffmpeg
@pytest.mark.parametrize("bpm,debut", [(123.7, 0.371), (92.3, 0.8), (140.0, 0.05)])
def test_temps_a_la_milliseconde(tmp_path, bpm, debut):
    """Une musique de synthèse au tempo et aux temps connus (MP3 192k : le décodeur décale aussi) : chaque temps trouvé
    tombe à moins de 3 ms d'un vrai temps (médiane), 6 ms au pire des 95 %, et le tempo est juste à 0,2 BPM."""
    an, e = _calage(tmp_path, bpm, debut)
    assert abs(an["bpm"] - bpm) < 0.2, an["bpm"]
    assert len(an["temps"]) >= 0.9 * (30 - debut) * bpm / 60
    assert np.median(e) < 3.0 and np.percentile(e, 95) < 6.0, (np.median(e), np.percentile(e, 95))


@ffmpeg
def test_temoin_sans_affinage_les_temps_derivent(tmp_path):
    """TÉMOIN : sans l'affinage à la milliseconde (les temps de la programmation dynamique seuls), la même mesure échoue."""
    an, e = _calage(tmp_path, 123.7, 0.371, frozenset({"affinage"}))
    assert not (np.median(e) < 3.0 and np.percentile(e, 95) < 6.0), np.median(e)


SECTIONS = [("intro", 4), ("couplet", 8), ("refrain", 8), ("couplet", 8), ("refrain", 8), ("pont", 4), ("refrain", 8), ("outro", 4)]


def _chanson_structuree(tmp_path, bpm, seed):
    per = 60 / bpm
    x, vrais, bornes = syn.morceau(bpm, 0.5 + sum(m for _, m in SECTIONS) * 4 * per + 1, 0.5, seed=seed, sections=SECTIONS)
    return syn.ecrire(tmp_path / f"s{bpm}.mp3", x), vrais, bornes, 4 * per


@ffmpeg
@pytest.mark.parametrize("bpm,seed", [(120.0, 1), (98.0, 2), (128.0, 4)])
def test_le_meilleur_passage_est_un_refrain(tmp_path, bpm, seed):
    """Intro douce, couplets, refrains plus forts aux accords à eux, pont, outro : le passage de 7, 15 ou 30 s commence au
    début d'un refrain (à une mesure près) ; jamais dans l'intro."""
    f, vrais, bornes, mesure = _chanson_structuree(tmp_path, bpm, seed)
    an = av.analyser(f)
    refrains = [t for n, t in bornes if n == "refrain"]
    for d in (7, 15, 30):
        ch = av.meilleur_passage(an, d)
        assert min(abs(ch["debut"] - r) for r in refrains) <= mesure * 1.01, (d, ch, refrains)


@ffmpeg
def test_temoin_sans_choix_le_passage_tombe_dans_l_intro(tmp_path):
    f, vrais, bornes, mesure = _chanson_structuree(tmp_path, 120.0, 1)
    an = av.analyser(f)
    av.COUPE = frozenset({"refrain"})
    try:
        ch = av.meilleur_passage(an, 15)
    finally:
        av.COUPE = frozenset()
    refrains = [t for n, t in bornes if n == "refrain"]
    assert not min(abs(ch["debut"] - r) for r in refrains) <= mesure * 1.01


def test_le_debut_demande_se_pose_sur_un_temps_et_garde_la_duree():
    an = {"duree": 60.0, "temps": [0.25 + 0.5 * i for i in range(119)]}
    assert av.choisir_passage(an, 15, 20.1)["debut"] == 20.25
    fin = av.choisir_passage(an, 15, 58.0)
    assert fin["debut"] + 15 <= 60.0 and fin["debut"] == 44.75 and fin["raison"] == "le début demandé"
    assert av.choisir_passage({"duree": 10.0, "temps": []}, 15, 3.0)["debut"] == 0.0


def test_plan_des_coupes():
    temps = [0.1 + 0.5 * i for i in range(60)]                     # 120 BPM, 30 s
    c, n = av.plan_coupes(temps, 30, 10, "auto", temps[::4])
    assert n == 4 and len(c) + 1 >= 10                              # chaque photo au moins une fois
    assert all(min(abs(x - t) for t in temps) < 1e-9 for x in c)    # chaque coupe sur un temps
    assert av.plan_coupes(temps, 30, 10, "rapide")[1] == 1 and av.plan_coupes(temps, 30, 10, "lent")[1] == 4
    vite = [0.3 * i for i in range(100)]                            # 200 BPM : jamais un plan sous 0,35 s
    assert av.plan_coupes(vite, 30, 4, "rapide")[1] == 2
    c, _ = av.plan_coupes(temps, 7, 3, "normal")
    assert c[-1] < 7 - 0.6 and all(x >= 0.3 for x in c)


def test_temoin_plan_des_coupes_sans_calage(monkeypatch):
    temps = [0.1 + 0.5 * i for i in range(60)]
    monkeypatch.setattr(av, "COUPE", frozenset({"calage"}))
    c, _ = av.plan_coupes(temps, 30, 10, "auto", temps[::4])
    assert not all(min(abs(x - t) for t in temps) < 0.02 for x in c)


# ------------------------------------------------------------------------------------------------ le son

def _source(tmp_path, nom, gain, ecrase=False):
    x, _, _ = syn.morceau(120, 20, 0.5, seed=7)
    x = x * gain
    if ecrase:
        x = np.tanh(12 * x) * 0.999
    return syn.ecrire(tmp_path / nom, x.astype(np.float32))


@ffmpeg
@pytest.mark.parametrize("gain,ecrase", [(0.04, False), (1.0, True)])
def test_le_son_a_moins_14_lufs_et_crete_sous_1_dbtp(tmp_path, gain, ecrase):
    """Une source très douce (≈ −36 LUFS) et une source écrasée (≈ −7 LUFS, crête à 0) : toutes deux sortent à −14 LUFS
    ±0,5 et sous −1 dBTP, à la bonne durée."""
    src = _source(tmp_path, "src.wav", gain, ecrase)
    m = av.preparer_son(str(src), 2.0, 15, tmp_path / "o.wav", tmp_path / "t")
    assert abs(m["source_lufs"] - av.CIBLE_LUFS) > 4                    # loin de la cible au départ
    assert abs(m["lufs"] - av.CIBLE_LUFS) <= 0.5 and m["tp"] <= av.CRETE_MAX, m
    mesure = av.mesure_niveau(tmp_path / "o.wav")
    assert abs(mesure["lufs"] + 14) <= 0.5 and mesure["tp"] <= -1.0
    r = subprocess.run([av.FFPROBE, "-v", "error", "-show_entries", "stream=sample_rate,channels,duration", "-of", "json",
                        str(tmp_path / "o.wav")], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    assert s["sample_rate"] == "48000" and s["channels"] == 2 and abs(float(s["duration"]) - 15) < 0.001


@ffmpeg
def test_temoin_sans_reglage_de_volume(tmp_path, monkeypatch):
    src = _source(tmp_path, "src.wav", 0.04)
    monkeypatch.setattr(av, "COUPE", frozenset({"volume"}))
    m = av.preparer_son(str(src), 2.0, 15, tmp_path / "o.wav", tmp_path / "t")
    assert not abs(m["lufs"] - av.CIBLE_LUFS) <= 0.5


def _crete_aac(wav, tmp_path):
    m4a = tmp_path / "o.m4a"
    av._ff(["-i", str(wav), *av.AAC, str(m4a)])
    return av.mesure_niveau(m4a)["tp"]


@ffmpeg
def test_la_crete_se_juge_apres_l_aac(tmp_path):
    """(13/11, démo de 60 s sur « Deux livres » : −2,3 dBTP en WAV, +0,5 dBTP dans la vidéo) une musique dense et saturée : le son
    préparé, encodé en AAC exactement comme la vidéo l'encode, reste sous −1 dBTP."""
    src = syn.ecrire(tmp_path / "dense.wav", syn.source_dense())
    m = av.preparer_son(str(src), 1.0, 12, tmp_path / "o.wav", tmp_path / "t")
    assert abs(m["lufs"] - av.CIBLE_LUFS) <= 0.5 and m["tp"] <= av.CRETE_MAX, m
    assert _crete_aac(tmp_path / "o.wav", tmp_path) <= av.CRETE_MAX


@ffmpeg
def test_temoin_crete_jugee_sur_le_wav(tmp_path, monkeypatch):
    """TÉMOIN : la crête jugée sur le WAV (avant le 13/11) : le WAV est sous −1 dBTP, mais pas son AAC."""
    src = syn.ecrire(tmp_path / "dense.wav", syn.source_dense())
    monkeypatch.setattr(av, "COUPE", frozenset({"aac"}))
    m = av.preparer_son(str(src), 1.0, 12, tmp_path / "o.wav", tmp_path / "t")
    assert m["tp"] <= av.CRETE_MAX
    assert not _crete_aac(tmp_path / "o.wav", tmp_path) <= av.CRETE_MAX


@ffmpeg
def test_fondus_d_entree_et_de_sortie(tmp_path):
    src = _source(tmp_path, "src.wav", 0.5)
    av.preparer_son(str(src), 2.0, 7, tmp_path / "o.wav", tmp_path / "t")
    r = subprocess.run([av.FFMPEG, "-v", "error", "-i", str(tmp_path / "o.wav"), "-ac", "1", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32)
    rms = lambda a: float(np.sqrt(np.mean(a.astype(float) ** 2)))          # noqa: E731
    assert rms(x[-480:]) < 0.05 * rms(x[48000 * 3: 48000 * 4])               # les 10 dernières ms presque muettes
    assert np.abs(x[:48]).max() < 0.02                                        # la première milliseconde aussi


# ------------------------------------------------------------------------------------------------ la vidéo de bout en bout

@pytest.fixture(scope="module")
def video(tmp_path_factory):
    """UN rendu complet (python de la vidéo) : 6 photos (dont 2 en paysage), une chanson structurée à 120 BPM, 7 s, coupes
    nettes tous les 2 temps, les trois formats, tous les textes."""
    if not A_PILLOW:
        pytest.skip("python de la vidéo absent")
    base = tmp_path_factory.mktemp("video")
    J = base / "jarvis"
    (J / "mediatheque" / "Hiver").mkdir(parents=True)
    photos = [str(base / f"look {i + 1}.jpg") for i in range(6)]
    pilote(J, "photos", chemins=photos[:4], taille=[600, 800])
    pilote(J, "photos", chemins=photos[4:], taille=[800, 600], depart=4)
    for p in photos:
        pilote(J, "importer", src=p, collection="Hiver", nom=Path(p).name)
    son, vrais, bornes, mesure = _chanson_structuree(base, 120.0, 1)
    pilote(J, "importer", src=str(son), collection="Hiver", nom="defile.mp3")
    demande = {"collection": "Hiver", "musique": "defile.mp3", "format": "tous", "duree_s": 7, "rythme": "normal",
               "transition": "nette", "marque": "Maison Zayn", "piece": "Manteau laine", "prix": "189 €", "appel": "Lien en bio"}
    r = pilote(J, "rendre", demande=demande, sortie=str(base / "sortie"), travail=str(base / "travail"))
    return {"base": base, "J": J, "r": r, "vrais": np.array(vrais), "bornes": bornes, "demande": demande}


def _coupes_video(mp4, w=36, h=64):
    r = subprocess.run([av.FFMPEG, "-v", "error", "-i", str(mp4), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                       capture_output=True, check=True)
    f = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w).astype(float)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    seuil = max(6.0, 5 * float(np.median(d)))
    return np.array([(i + 1) / av.FPS for i in np.nonzero(d > seuil)[0]]), len(f)


@rendu
def test_l_export_est_celui_des_reseaux(video):
    """ffprobe : 1080×1920, 1080×1350, 1080×1080 ; 7,00 s ; H.264 High 4.0, yuv420p BT.709, 30 i/s ; AAC-LC 48 kHz stéréo ;
    « moov » avant « mdat » (faststart) ; une couverture JPEG à la taille de la vidéo."""
    vids = [Path(f) for f in video["r"]["fichiers"] if f.endswith(".mp4")]
    assert [f.name.rsplit("-", 1)[1] for f in vids] == ["9x16.mp4", "4x5.mp4", "1x1.mp4"]
    for f, (W, H) in zip(vids, av.FORMATS.values()):
        v = av.verifier(f)
        assert (v["largeur"], v["hauteur"]) == (W, H)
        assert abs(v["duree_video"] - 7) < 0.02 and abs(v["duree_son"] - 7) < 0.05 and abs(v["duree"] - 7) < 0.05, v
        assert v["images"] == 210 and v["fps"] == 30.0
        assert v["codec"] == "h264" and v["profil"] == "High" and v["niveau"] == 40 and v["pix_fmt"] == "yuv420p"
        assert v["couleurs"] == "bt709" and v["son"] == "aac" and v["profil_son"] == "LC"
        assert v["frequence"] == 48000 and v["canaux"] == 2 and v["faststart"], v
        assert v["debit"] < 9_000_000
    couv = [Path(f) for f in video["r"]["fichiers"] if f.endswith("-couverture.jpg")]
    assert len(couv) == 1 and couv[0].read_bytes()[:3] == b"\xff\xd8\xff"
    r = subprocess.run([av.FFPROBE, "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(couv[0])],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "1080,1920"


@rendu
def test_les_coupes_tombent_sur_les_temps_dans_la_video_finie(video):
    """Dans la vidéo finie : les changements d'image (lus dans les images décodées) contre les temps VRAIS de la musique
    (décalés du début du passage) et contre les attaques réentendues dans son propre son : à moins d'une image (≤ 17 ms)."""
    m = video["r"]["mesures"]
    mp4 = next(f for f in video["r"]["fichiers"] if f.endswith("9x16.mp4"))
    coupes, n = _coupes_video(mp4)
    assert len(coupes) == m["coupes"] >= 5, (coupes, m)
    vrais = video["vrais"] - m["passage"][0]
    e = _ecart_ms(coupes, vrais[(vrais > 0) & (vrais < 7)])
    assert np.median(e) <= 17.0 and e.max() <= 17.0, e
    wav = Path(video["base"]) / "son-de-la-video.wav"
    subprocess.run([av.FFMPEG, "-v", "error", "-y", "-i", mp4, "-vn", str(wav)], check=True)
    an = av.analyser(wav)
    e2 = _ecart_ms(coupes, an["temps"])
    assert np.median(e2) <= 17.0, e2
    assert m["calage_ms"]["max"] <= 17.0 and m["temps_par_coupe"] == 2


@rendu
def test_le_passage_est_le_refrain_et_le_son_aux_normes(video):
    m = video["r"]["mesures"]
    refrains = [t for n, t in video["bornes"] if n == "refrain"]
    debut_temps = m["passage"][0] + min(0.1, m["passage"][0])        # le premier temps, après la petite avance du fondu
    assert min(abs(debut_temps - r) for r in refrains) < 2.0 + 0.01, (m["passage"], refrains)
    for f in [f for f in video["r"]["fichiers"] if f.endswith(".mp4")]:
        n = av.mesure_niveau(f)
        assert abs(n["lufs"] - av.CIBLE_LUFS) <= 1.0 and n["tp"] <= av.CRETE_MAX, (f, n)


@rendu
def test_les_textes_sont_dans_l_image(video):
    """La marque en haut, la pièce en bas, l'appel à la fin : là où ils doivent être, des pixels changent par rapport au même
    instant sans textes ; jamais dans la colonne des boutons de TikTok (14 % de droite)."""
    J, base = video["J"], Path(video["base"])
    sans = dict(video["demande"], marque="", piece="", prix="", appel="", format="9:16")
    r = pilote(J, "rendre", demande=sans, sortie=str(base / "sans"), travail=str(base / "t2"))
    a = next(f for f in video["r"]["fichiers"] if f.endswith("9x16.mp4"))
    b = r["fichiers"][0]

    def image(f, t):
        x = subprocess.run([av.FFMPEG, "-v", "error", "-ss", str(t), "-i", f, "-frames:v", "1", "-vf", "format=gray", "-f",
                            "rawvideo", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(x, np.uint8).reshape(1920, 1080).astype(float)
    milieu, fin = image(a, 3.0) - image(b, 3.0), image(a, 6.6) - image(b, 6.6)
    zone = lambda d, y0, y1: float(np.abs(d[int(y0 * 1920): int(y1 * 1920), 160:920]).mean())   # noqa: E731
    assert zone(milieu, 0.08, 0.15) > 3 and zone(milieu, 0.64, 0.76) > 3          # la marque, la pièce et le prix
    assert zone(fin, 0.46, 0.54) > 10                                             # l'appel à l'action


@rendu
def test_les_textes_restent_dans_la_zone_sure(lieux, tmp_path):
    """Même longs, les textes restent dans la zone sûre : en 9:16, hors de la colonne des boutons de TikTok (13 % de chaque
    côté), sous la barre du haut (7 %) et au-dessus de la légende et des boutons du bas (78 %) ; en 4:5 et 1:1, à 6 % des bords."""
    t = {"marque": "Maison Zayn Couture Paris", "piece": "Manteau long en laine bouillie double face, col cranté",
         "prix": "1 289,00 €", "appel": "Commande en message privé", "legendes": []}
    r = pilote(lieux["jarvis"], "calques", photo=str(tmp_path / "p.jpg"), textes=t)
    for fm, boites in r.items():
        W, H = av.FORMATS[fm]
        assert set(boites) == {"marque", "bas", "appel"}, (fm, boites)
        for nom, (x0, y0, x1, y1) in boites.items():
            if fm == "9:16":
                assert x0 >= 0.12 * W and x1 <= 0.88 * W and y0 >= 0.07 * H and y1 <= 0.78 * H, (fm, nom, x0, y0, x1, y1)
            else:
                assert x0 >= 0.06 * W and x1 <= 0.94 * W and y0 >= 0.03 * H and y1 <= 0.95 * H, (fm, nom, x0, y0, x1, y1)


@rendu
def test_temoins_de_bout_en_bout_calage_et_faststart(video):
    """TÉMOINS : la même vidéo, coupes à pas réguliers (« calage » coupé) : les changements d'image ne tombent plus sur les
    temps ; index du MP4 à la fin (« faststart » coupé) : « moov » après « mdat »."""
    J, base = video["J"], Path(video["base"])
    d = dict(video["demande"], format="9:16")
    r = pilote(J, "rendre", coupe=("calage", "faststart"), demande=d, sortie=str(base / "temoin"), travail=str(base / "t3"))
    mp4 = r["fichiers"][0]
    coupes, _ = _coupes_video(mp4)
    vrais = video["vrais"] - r["mesures"]["passage"][0]
    e = _ecart_ms(coupes, vrais[(vrais > 0) & (vrais < 7)])
    assert len(coupes) >= 3 and not (np.median(e) <= 17.0 and e.max() <= 17.0), e
    assert not av.verifier(mp4)["faststart"]


@rendu
def test_un_apercu_est_petit_et_rapide(video):
    J, base = video["J"], Path(video["base"])
    r = pilote(J, "rendre", demande=dict(video["demande"], format="4:5", duree_s=15, apercu=True), sortie=str(base / "ap"),
               travail=str(base / "t4"))
    v = av.verifier(r["fichiers"][0])
    assert (v["largeur"], v["hauteur"]) == (360, 450) and abs(v["duree"] - 15) < 0.05
    assert not any(f.endswith("-couverture.jpg") for f in r["fichiers"])


# ------------------------------------------------------------------------------------------------ la tâche, la recette, les copies

def _faux_demarrage(vus):
    def demarrer(args, log):
        vus.append((args, log))
        return os.getpid()
    return demarrer


def _mediatheque_minimale(lieux):
    d = lieux["med"] / "Hiver"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (d / f"look {i + 1}.jpg").write_bytes(b"\xff\xd8\xff faux")
    (d / "son.mp3").write_bytes(b"ID3 faux")


def test_lancer_ecrit_une_tache_que_le_cockpit_suit(lieux):
    _mediatheque_minimale(lieux)
    vus = []
    t = av.lancer(av.preparer(collection="Hiver", musique="son.mp3", format="tiktok", duree_s=15, marque="Maison Zayn",
                              prix="189 €", med=lieux["med"]), demarrer=_faux_demarrage(vus))
    d = json.loads((lieux["taches"] / f"{t['tache']}.json").read_text())
    assert d["etat"] == "en cours" and d["video"]["formats"] == ["9:16"] and d["commande"].startswith("atelier vidéo : vidéo")
    assert len(d["video"]["photos"]) == 3 and d["video"]["musique"] == {"collection": "Hiver", "fichier": "son.mp3"}
    args = vus[0][0]
    assert args[:3] == [av.NICE, "-n", "10"] and args[-3:] == ["generer", t["tache"], str(lieux["taches"])]
    fiche = json.loads((lieux["videos"] / f"{t['nom']}.json").read_text())
    assert fiche["etat"] == "en cours" and fiche["recette"]["textes"]["prix"] == "189 €"
    for _ in range(av.MAX_EN_FILE - 1):
        av.lancer(av.preparer(collection="Hiver", med=lieux["med"]), demarrer=_faux_demarrage([]))
    with pytest.raises(av.Refus, match="en file"):
        av.lancer(av.preparer(collection="Hiver", med=lieux["med"]), demarrer=_faux_demarrage([]))


def test_finir_copie_dans_l_atelier_et_sur_le_telephone_sans_ecraser(lieux):
    _mediatheque_minimale(lieux)
    t = av.lancer(av.preparer(collection="Hiver", musique="son.mp3", titre="Manteau Hiver", med=lieux["med"]),
                  demarrer=_faux_demarrage([]))
    mp4 = lieux["videos"] / f"{t['nom']}-9x16.mp4"
    mp4.write_bytes(b"video" * 100)
    couv = lieux["videos"] / f"{t['nom']}-couverture.jpg"
    couv.write_bytes(b"\xff\xd8\xff jpeg")
    lieux["tel"].mkdir(parents=True)
    (lieux["tel"] / "Manteau Hiver (TikTok).mp4").write_bytes(b"une autre video")       # un fichier de l'ami : jamais écrasé
    ligne = av.finir(t["tache"], fichiers=[mp4, couv], mesures={"bpm": 120, "calage_ms": {"mediane": 8.0, "max": 16, "coupes": 7},
                                                                 "son": {"lufs": -14.1}, "passage": [42.0, 57.0], "raison": "le refrain probable"})
    assert ligne.startswith("VIDÉO PRÊTE") and f'fichier_joindre("atelier/videos/{mp4.name}"' in ligne and "−" not in ligne[:5]
    assert "Copiée sur le téléphone (jarvis › tel)" in ligne, ligne
    assert (lieux["atelier"] / mp4.name).is_file() and (lieux["atelier"] / couv.name).is_file()
    assert (lieux["tel"] / "Manteau Hiver (TikTok).mp4").read_bytes() == b"une autre video"
    assert (lieux["tel"] / "Manteau Hiver (TikTok) 2.mp4").read_bytes() == mp4.read_bytes()
    assert (lieux["tel"] / "Manteau Hiver (couverture).jpg").is_file()
    j = [json.loads(l) for l in (lieux["jarvis"] / "telephone-ecritures.jsonl").read_text().splitlines()]
    assert [x["action"] for x in j] == ["ajout", "ajout"] and all(x["note"] == "l'atelier vidéo" for x in j)
    fiche = json.loads((lieux["videos"] / f"{t['nom']}.json").read_text())
    assert fiche["etat"] == "prête" and fiche["couverture"] == str(couv)
    d = json.loads((lieux["taches"] / f"{t['tache']}.json").read_text())
    assert d["etat"] == "finie" and d["code"] == 0
    # une panne : la tâche finit, la fiche dit pourquoi
    t2 = av.lancer(av.preparer(collection="Hiver", med=lieux["med"]), demarrer=_faux_demarrage([]))
    assert av.finir(t2["tache"], erreur="ffmpeg : boum").startswith("VIDÉO RATÉE")
    assert json.loads((lieux["videos"] / f"{t2['nom']}.json").read_text())["etat"] == "ratée"


def test_refaire_garde_la_recette_et_change_ce_qu_on_demande(lieux):
    _mediatheque_minimale(lieux)
    t = av.lancer(av.preparer(collection="Hiver", musique="son.mp3", titre="Manteau", marque="Maison Zayn", prix="189 €",
                              appel="Lien en bio", rythme="lent", med=lieux["med"]), demarrer=_faux_demarrage([]))
    mp4 = lieux["videos"] / f"{t['nom']}-9x16.mp4"
    mp4.write_bytes(b"v")
    av.finir(t["tache"], fichiers=[mp4], mesures={"passage": [10.0, 25.0]})
    r = av.refaire("dernière", rythme="rapide", format="post insta", prix="", appel="Commande en DM", med=lieux["med"])
    assert r["rythme"] == "rapide" and r["formats"] == ["4:5"] and r["refait_de"] == t["nom"]
    assert r["textes"] == {**t["textes"], "prix": "", "appel": "Commande en DM"} and r["musique"] == t["musique"]
    assert r["photos"] == t["photos"] and r["duree_s"] == t["duree_s"] and r["nom"] != t["nom"]
    assert av.refaire("Manteau", duree_s=30, med=lieux["med"])["duree_s"] == 30
    with pytest.raises(av.Refus, match="inconnue"):
        av.refaire("n'existe pas")


def test_l_atelier_visuel_attend_une_video_lancee_avant(lieux, monkeypatch):
    """Un gros calcul à la fois : une image de l'atelier visuel lancée après une vidéo attend la vidéo (et la vidéo attend
    une chanson, comme toute création)."""
    import atelier_visuel
    import studio
    monkeypatch.setattr(studio, "occupe", lambda studio=None: None)
    monkeypatch.setattr(atelier_visuel, "TACHES", lieux["taches"])
    _mediatheque_minimale(lieux)
    tv = av.lancer(av.preparer(collection="Hiver", med=lieux["med"]), demarrer=_faux_demarrage([]))["tache"]
    plus_tard = "T-99999999-999999-zzzz"
    assert atelier_visuel.gros_calcul_ailleurs(plus_tard, lieux["taches"]) == "attend la création d'avant"
    assert atelier_visuel.gros_calcul_ailleurs(tv, lieux["taches"]) is None
    (lieux["taches"] / "T-00000000-000000-chan.json").write_text(json.dumps(
        {"id": "T-00000000-000000-chan", "etat": "en cours", "chanson": {"titre": "Lanterne"}}))
    assert "Lanterne" in atelier_visuel.gros_calcul_ailleurs(tv, lieux["taches"])


@rendu
def test_generer_de_bout_en_bout_par_la_vraie_commande(lieux, tmp_path):
    """La vraie commande de la tâche (`atelier_video.py generer`), dans un Jarvis à part : la vidéo, la couverture, la fiche
    prête, la tâche finie, les copies (atelier, téléphone) et la ligne de fin qui dit comment l'envoyer."""
    J = lieux["jarvis"]
    srcs = [str(tmp_path / f"p{i}.jpg") for i in range(3)]
    pilote(J, "photos", chemins=srcs)
    for s in srcs:
        pilote(J, "importer", src=s, collection="Hiver", nom=Path(s).name)
    x, _, _ = syn.morceau(110, 12, 0.3, seed=9)
    av.importer(syn.ecrire(tmp_path / "son.mp3", x), "Hiver", med=lieux["med"])
    t = av.lancer(av.preparer(collection="Hiver", musique="son.mp3", duree_s=6, marque="Zayn", appel="Lien en bio",
                              titre="Essai", med=lieux["med"]), demarrer=_faux_demarrage([]))
    env = {**os.environ, "JARVIS_DIR": str(J), "JARVIS_TELEPHONE_VIDEOS": str(lieux["tel"])}
    env.pop("JARVIS_ATELIER_VIDEO", None)
    r = subprocess.run([str(PY), "-B", str(JARVIS_CODE / "atelier_video.py"), "generer", t["tache"], str(lieux["taches"])],
                       capture_output=True, text=True, timeout=300, env=env)
    assert r.returncode == 0, r.stderr[-1000:]
    assert "VIDÉO PRÊTE" in r.stdout and "PROGRESSION" in r.stdout, r.stdout[-1500:]
    d = json.loads((lieux["taches"] / f"{t['tache']}.json").read_text())
    assert d["etat"] == "finie" and d["code"] == 0
    fiche = json.loads((lieux["videos"] / f"{t['nom']}.json").read_text())
    assert fiche["etat"] == "prête" and fiche["mesures"]["formats"]["9:16"]["faststart"]
    assert (lieux["atelier"] / f"{t['nom']}-9x16.mp4").is_file()
    assert sorted(p.name for p in lieux["tel"].iterdir()) == ["Essai (TikTok).mp4", "Essai (couverture).jpg"]
    assert not (lieux["videos"] / f".{t['nom']}").exists()                       # le dossier de travail est parti


# ------------------------------------------------------------------------------------------------ les outils de l'IA, et rien dehors

def test_outils_de_l_ia(lieux, monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server

    def _outil(nom):
        return mcp_server.mcp._tool_manager.get_tool(nom).fn
    _mediatheque_minimale(lieux)
    monkeypatch.setattr(av, "_demarrer", lambda args, log: os.getpid())
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert "Seul Hakim" in _outil("video_creer")(collection="Hiver")
    assert "Seul Hakim" in _outil("mediatheque_ajouter")("fichiers/x.jpg", "Hiver")
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    v = _outil("mediatheque_voir")()
    assert "« Hiver » — 3 photos : look 1.jpg, look 2.jpg, look 3.jpg" in v and "son.mp3" in v
    r = _outil("video_creer")(collection="Hiver", musique="son.mp3", format="tiktok", duree_s=15, marque="Maison Zayn")
    assert r.startswith("Je monte") and "9:16" in r and "3 photos" in r and "tâche T-" in r
    assert "En cours : T-" in _outil("mediatheque_voir")()
    assert _outil("video_creer")(collection="Inconnue").startswith("Refusé")
    assert _outil("mediatheque_ajouter")("/etc/passwd", "Hiver").startswith("Refusé")
    assert _outil("mediatheque_ajouter")("../../modules.json", "Hiver").startswith("Refusé")
    (lieux["jarvis"] / "modules.json").write_text(json.dumps({"modules": {"atelier_video": False}}))
    assert "éteint" in _outil("mediatheque_voir")() and "éteint" in _outil("video_creer")(collection="Hiver")


def test_rien_ne_sort_de_la_machine():
    """L'atelier vidéo n'ouvre aucune connexion : ni socket, ni requête, ni adresse web dans son code."""
    src = (JARVIS_CODE / "atelier_video.py").read_text(encoding="utf-8")
    for interdit in ("import socket", "urllib", "requests", "httpx", "http.client", "http://", "https://", "smtplib", "ftplib"):
        assert interdit not in src, interdit
