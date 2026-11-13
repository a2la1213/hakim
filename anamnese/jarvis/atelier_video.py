"""L'atelier VIDÉO (13/11, Ahmed : « il n'a pas besoin de studio, juste d'atelier, puisqu'il est dans les habits (designer) :
il faut qu'il puisse uploader ses photos et ses musiques et en faire des vidéos TikTok, Insta, etc. » ; utile à Hakim aussi).

Tout se calcule sur le CPU, avec ffmpeg, numpy et Pillow (aucun modèle, aucun GPU, rien d'envoyé dehors : ni réseau, ni
service, ni publication ; la vidéo finie est copiée dans le dossier du téléphone et publiée à la main).

LA MÉDIATHÈQUE (~/AIOS/jarvis/mediatheque) : une collection = un dossier (« Hiver 2026 ») ; ses photos (jpg, png, heic converti
en jpg à l'arrivée, webp) et ses musiques (mp3, m4a, wav). À côté, cachés : .apercus/ (une vignette de 480 px par photo),
.analyses/ (le tempo, les temps et le meilleur passage d'une musique, calculés une fois), .depot/ (les envois en cours du
cockpit), et _polices/ (marque.ttf|otf et texte.ttf|otf : la police de la marque, si l'ami en dépose une).

LA VIDÉO, à partir de photos et d'une musique :
- l'écoute (numpy) : un flux spectral toutes les 5,8 ms, le tempo par autocorrélation, les temps par programmation
  dynamique (Ellis 2007), chacun affiné à la milliseconde sur la montée de l'énergie (fenêtres de 1 ms), puis une grille
  ajustée (un tempo constant si les temps s'y tiennent à 12 ms près) ; les mesures (le temps fort, par la grosse caisse
  et les changements d'accords) ; le chroma et l'énergie de chaque mesure ;
- le meilleur passage à la durée voulue (7, 15, 30, 60 s…) : la fenêtre, posée sur un début de mesure, la plus forte, la
  plus répétée ailleurs dans le morceau (un refrain revient) et qui commence à une frontière de section ;
- le son : extrait, fondus (entrée 0,1 s, sortie jusqu'à 1,5 s), ramené à −14 LUFS intégrés, crête vraie ≤ −1 dBTP
  (gain puis limiteur, mesuré et corrigé jusqu'à tenir) ;
- l'image (Pillow, en fils parallèles) : chaque photo couvre le cadre (ou y entre entière, sur un fond d'elle-même flouté,
  si sa forme est trop différente), avec un mouvement doux (zoom avant, arrière, glissé) ; les coupes tombent SUR LES TEMPS
  (une image toutes les 1, 2, 4 ou 8 temps selon le rythme) ; transition nette, ou fondu de 0,24 s centré sur le temps ;
- les textes : la marque (en haut), la pièce et son prix (en bas, ou une légende par photo), l'appel à l'action à la fin,
  dans la zone sûre des réseaux (hors des boutons de TikTok) ;
- l'export : H.264 High 4.0, yuv420p BT.709, 30 i/s constantes, image clé toutes les 2 s, AAC 48 kHz stéréo 192 kb/s,
  « faststart » ; 1080×1920 (TikTok, Reels, Shorts), 1080×1350 (post Insta 4:5) ou 1080×1080 (1:1) ; plus une COUVERTURE
  (JPEG à la taille de la vidéo) et une vignette.

Comme l'atelier visuel, chaque vidéo est une TÂCHE DE FOND ordinaire (cwd/taches/T-*.json, clé « video », lignes
PROGRESSION) que le cockpit suit ; UN gros calcul à la fois (le même verrou que l'atelier visuel ; une chanson ou le studio
passent avant). Deux rôles :
- `lancer` (importé : mcp_server.py, ou le cockpit par `atelier_video.py lancer`) : vérifie, écrit la tâche, détache le calcul ;
- `generer` (`nice -n 10 <python vidéo> atelier_video.py generer <tâche> <dossier>`) : calcule, dépose
    ~/AIOS/jarvis/videos/<nom>.mp4 + -couverture.jpg + .jpg (vignette) + <nom>.json (la recette, les mesures)
    ~/AIOS/jarvis/cwd/atelier/videos/…   (pour fichier_joindre)
    …/telephone/<appareil>/Hakim/Videos/… (le téléphone : publié à la main par son propriétaire)

Le python de la vidéo : numpy + Pillow (pillow-heif conseillé hors Mac : requirements-video.txt) ; JARVIS_PYTHON_VIDEO, sinon
jarvis/.venv-video, sinon jarvis/.venv-image (le Mac de Hakim). Le module ne charge numpy et Pillow qu'au moment du calcul :
le venv d'Anamnèse (les outils MCP) l'importe sans eux.

LE RÉGLAGE (profils de modules) : « atelier_video » dans ~/AIOS/jarvis/modules.json ({"atelier_video": false} ou
{"modules": {"atelier_video": false}}), ou JARVIS_ATELIER_VIDEO=0/1 ; allumé par défaut (Ahmed : pour l'IA de l'ami et pour
Hakim).
"""
import fcntl
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
MEDIATHEQUE = JARVIS / "mediatheque"
VIDEOS = JARVIS / "videos"
TACHES = JARVIS / "cwd" / "taches"
ATELIER = JARVIS / "cwd" / "atelier" / "videos"
FICHIERS = JARVIS / "cwd" / "fichiers"
MODULES = JARVIS / "modules.json"
TELEPHONE = None            # None : telephone.documents() / « Hakim » / « Videos » (ou JARVIS_TELEPHONE_VIDEOS)


def _outil(env, *candidats):
    v = os.environ.get(env)
    if v:
        return v
    for c in candidats:
        if c and Path(c).exists():
            return str(c)
    return shutil.which(Path(candidats[-1]).name) or str(candidats[0])


FFMPEG = _outil("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg")
FFPROBE = os.environ.get("JARVIS_FFPROBE") or str(Path(FFMPEG).with_name("ffprobe"))
NICE = shutil.which("nice") or "/usr/bin/nice"


def python_video():
    v = os.environ.get("JARVIS_PYTHON_VIDEO")
    if v:
        return Path(v)
    for d in (".venv-video", ".venv-image"):
        p = ICI / d / "bin" / "python"
        if p.exists():
            return p
    return Path(sys.executable)


FORMATS = {"9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}
NOMS_FORMAT = {"9:16": "TikTok · Reels · Shorts", "4:5": "post Insta", "1:1": "carré"}
ALIAS_FORMAT = {
    "9:16": "9:16", "9/16": "9:16", "916": "9:16", "tiktok": "9:16", "tik tok": "9:16", "reels": "9:16", "reel": "9:16",
    "shorts": "9:16", "short": "9:16", "story": "9:16", "stories": "9:16", "vertical": "9:16", "verticale": "9:16",
    "4:5": "4:5", "4/5": "4:5", "45": "4:5", "insta": "4:5", "instagram": "4:5", "post": "4:5", "post insta": "4:5",
    "post instagram": "4:5", "portrait": "4:5", "feed": "4:5",
    "1:1": "1:1", "1/1": "1:1", "carre": "1:1", "square": "1:1", "post carre": "1:1"}
RYTHMES = {"auto": None, "lent": 4, "normal": 2, "rapide": 1}
ALIAS_RYTHME = {"auto": "auto", "": "auto", "automatique": "auto", "lent": "lent", "doux": "lent", "calme": "lent", "slow": "lent",
                "normal": "normal", "moyen": "normal", "medium": "normal", "rapide": "rapide", "vite": "rapide", "fast": "rapide",
                "nerveux": "rapide", "dynamique": "rapide"}
TRANSITIONS = ("auto", "nette", "fondu")
ALIAS_TRANSITION = {"auto": "auto", "": "auto", "nette": "nette", "net": "nette", "coupe": "nette", "cut": "nette", "seche": "nette",
                    "fondu": "fondu", "fondus": "fondu", "fade": "fondu", "enchaine": "fondu", "doux": "fondu"}
PHOTOS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
MUSIQUES = {".mp3", ".m4a", ".wav"}
POLICES_EXT = {".ttf", ".otf"}
FICHIER_MAX = 200 * 1024 * 1024
MEDIATHEQUE_MAX = 50 * 1024 ** 3
DUREE_MIN, DUREE_MAX = 5.0, 90.0
PHOTOS_MAX = 30
FPS = 30
CIBLE_LUFS, CRETE_MAX = -14.0, -1.0
MAX_EN_FILE = 4
MAX_TACHES = 5
DELAI_S = 30 * 60
GARDE_APERCUS = 6
VERSION_ANALYSE = 3
# (témoins des tests : chaque mécanisme se coupe ici, et son test doit alors échouer) « calage » (coupes à pas réguliers, sans
# les temps), « affinage » (temps de la programmation dynamique, sans l'affinage à la milliseconde), « refrain » (le passage
# commence au début du morceau), « volume » (le son garde son niveau), « faststart » (l'index du MP4 à la fin), « aac » (la crête
# jugée sur le WAV, pas sur l'AAC que la vidéo contiendra)
COUPE = frozenset()


class Refus(Exception):
    pass


# ------------------------------------------------------------------------------------------------ petits outils

def _ecrire(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _lire(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _vivant(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError, ValueError):
        return False


def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")


def _cle(s):
    return " ".join(re.sub(r"[^a-z0-9:/ ]+", " ", _sans_accent(s)).split())


def allume(modules=None):
    """Le réglage « atelier_video » : JARVIS_ATELIER_VIDEO, sinon modules.json (à plat ou sous « modules »), sinon allumé."""
    v = os.environ.get("JARVIS_ATELIER_VIDEO")
    if v is not None and v.strip():
        return v.strip().lower() not in ("0", "non", "false", "off", "eteint", "éteint")
    d = _lire(modules or MODULES, {}) or {}
    if isinstance(d.get("modules"), dict) and "atelier_video" in d["modules"]:
        return bool(d["modules"]["atelier_video"])
    if "atelier_video" in d:
        return bool(d["atelier_video"])
    return True


def _verifier_allume():
    if not allume():
        raise Refus("l'atelier vidéo est éteint ici (réglage « atelier_video »)")


def format_de(f):
    k = ALIAS_FORMAT.get(_cle(f) or "9:16") or ALIAS_FORMAT.get(str(f or "").strip().lower())
    if not k:
        raise Refus(f"format inconnu « {f} » : 9:16 (TikTok, Reels, Shorts), 4:5 (post Insta) ou 1:1 (carré)")
    return k


def formats_de(f):
    """Un format, ou plusieurs (« 9:16 et 4:5 », « tous ») : la liste, sans doublon."""
    if isinstance(f, (list, tuple)):
        l = [format_de(x) for x in f if str(x).strip()] or ["9:16"]
    else:
        s = _cle(f)
        if s in ("tous", "les trois", "tout", "all"):
            return list(FORMATS)
        l = [format_de(x) for x in re.split(r"\s*(?:,|;|\+| et | and )\s*", " " + s + " ") if x.strip()] or ["9:16"]
    return list(dict.fromkeys(l))


def rythme_de(r):
    k = ALIAS_RYTHME.get(_cle(r))
    if not k:
        raise Refus(f"rythme inconnu « {r} » : auto, lent, normal ou rapide")
    return k


def transition_de(t):
    k = ALIAS_TRANSITION.get(_cle(t))
    if not k:
        raise Refus(f"transition inconnue « {t} » : auto, nette ou fondu")
    return k


def duree_de(d):
    try:
        v = float(str(d).replace(",", ".").rstrip("s ").strip() or 15)
    except (TypeError, ValueError):
        raise Refus("une durée en secondes (7, 15, 30, 60…)")
    if not DUREE_MIN <= v <= DUREE_MAX:
        raise Refus(f"une vidéo de {DUREE_MIN:.0f} à {DUREE_MAX:.0f} secondes (ici {v:g})")
    return round(v, 2)


def _texte(s, n):
    """Un texte d'affichage : une ligne, sans caractère de contrôle ni pictogramme (Pillow ne les dessine pas)."""
    t = "".join(c for c in str(s or "") if unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Co", "So", "Sk") or c in "€£$¥")
    return " ".join(t.split())[:n]


def nom_de(titre, quand=None):
    t = re.sub(r"[^a-z0-9]+", "-", _sans_accent(titre or "video")).strip("-")[:40].strip("-") or "video"
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(quand or time.time())) + f"-{uuid.uuid4().hex[:3]}-" + t


# ------------------------------------------------------------------------------------------------ la médiathèque

def nom_collection(s):
    """« hiver 2026 » → « hiver 2026 » : lettres, chiffres, espace, - _ ' ; 50 caractères ; ni « . » ni « _ » en tête."""
    t = unicodedata.normalize("NFC", str(s or ""))
    t = "".join(c if (c.isalnum() or c in " -_'") else " " for c in t)
    t = " ".join(t.split()).strip(" -_'")[:50].strip()
    if not t:
        raise Refus("un nom de collection (par exemple « Hiver 2026 »)")
    return t


def nom_fichier(s, ext=None):
    t = unicodedata.normalize("NFC", Path(str(s or "")).name)
    souche, e = os.path.splitext(t)
    souche = "".join(c if (c.isalnum() or c in " -_()+.,'&") else "_" for c in souche)   # « Moujahid 3.1 » garde son point
    souche = " ".join(souche.split()).strip(" ._") or "fichier"
    return souche[:90] + (ext or e.lower())


def _dans(racine, p):
    """p est-il bien sous racine (sans lien qui en sorte) ?"""
    try:
        r = Path(os.path.realpath(racine))
        q = Path(os.path.realpath(p))
        return q == r or r in q.parents
    except OSError:
        return False


def dossier_collection(collection, med=None, creer=False):
    med = Path(med or MEDIATHEQUE)
    d = med / nom_collection(collection)
    if not _dans(med, d) or d.is_symlink():
        raise Refus("collection hors de la médiathèque")
    if creer:
        d.mkdir(parents=True, exist_ok=True)
    return d


def genre_de(tete):
    """Le vrai type d'un fichier, d'après ses premiers octets : (genre, extension) ou (None, None)."""
    b = bytes(tete[:64])
    if b[:3] == b"\xff\xd8\xff":
        return "photo", ".jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "photo", ".png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "photo", ".webp"
    if b[:4] == b"RIFF" and b[8:12] == b"WAVE":
        return "musique", ".wav"
    if b[4:8] == b"ftyp":
        marque = b[8:12]
        if marque in (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1", b"avif"):
            return ("photo", ".heic") if marque != b"avif" else (None, None)
        return "musique", ".m4a"
    if b[:3] == b"ID3" or (len(b) > 1 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0):
        return "musique", ".mp3"
    return None, None


def _unique(d, nom):
    souche, ext = os.path.splitext(nom)
    c, i = d / nom, 2
    while c.exists():
        c, i = d / f"{souche} {i}{ext}", i + 1
    return c


def _taille_mediatheque(med):
    t = 0
    for racine, _, noms in os.walk(med):
        for n in noms:
            try:
                t += os.lstat(os.path.join(racine, n)).st_size
            except OSError:
                pass
    return t


def _convertir_heic(src, dst):
    """HEIC → JPEG : pillow-heif s'il est là, sinon ffmpeg (≥ 7.1 lit les grilles HEIF), sinon sips (Mac)."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        from PIL import ImageOps
        Image = _pil()
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.save(dst, "JPEG", quality=94)
        return dst
    except Exception:                                        # noqa: BLE001 — on essaie la suite
        pass
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-frames:v", "1",
                        "-q:v", "2", str(dst)], capture_output=True, timeout=120)
    if r.returncode == 0 and Path(dst).is_file() and Path(dst).stat().st_size > 0:
        return dst
    if shutil.which("sips"):
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "94", str(src), "--out", str(dst)],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and Path(dst).is_file():
            return dst
    raise Refus("cette photo HEIC ne se lit pas ici (installe pillow-heif dans le python de la vidéo)")


def apercu_de(collection, fichier, med=None):
    med = Path(med or MEDIATHEQUE)
    return med / ".apercus" / nom_collection(collection) / (fichier + ".jpg")


def _pil():
    """Pillow, avec la garde des « bombes de décompression » relevée à 400 Mpx : une photo de 200 Mpx (Galaxy S26 Ultra) est une
    vraie photo de l'ami (et la garde de Pillow, à 178 Mpx, la refusait)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 400_000_000
    return Image


def _faire_apercu(src, dst, cote=480):
    from PIL import ImageOps
    Image = _pil()
    im = Image.open(src)
    im.draft("RGB", (cote * 2, cote * 2))
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((cote, cote), Image.LANCZOS)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=82)
    return im.size


def _duree_audio(f):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type:format=duration",
                            "-of", "json", str(f)], capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout or "{}")
        if not d.get("streams"):
            return None
        return round(float(d["format"]["duration"]), 2)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        return None


def importer(src, collection, nom=None, deplacer=False, med=None):
    """Un fichier (photo, musique, police) → la médiathèque. Vérifie le type par ses octets puis en le lisant vraiment ;
    une photo HEIC devient un JPEG ; jamais par-dessus un autre fichier. Rend la fiche du fichier."""
    med = Path(med or MEDIATHEQUE)
    src = Path(src)
    if not src.is_file() or src.is_symlink():
        raise Refus("fichier introuvable (ou un lien)")
    taille = src.stat().st_size
    if taille <= 0:
        raise Refus("fichier vide")
    if taille > FICHIER_MAX:
        raise Refus(f"fichier trop lourd ({taille // 2**20} Mo ; {FICHIER_MAX // 2**20} Mo au plus)")
    nom = nom or src.name
    ext_nom = os.path.splitext(str(nom))[1].lower()
    if ext_nom in POLICES_EXT:                            # la police de la marque (marque.ttf) ou des textes (texte.ttf)
        tete = src.read_bytes()[:4]
        if tete not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            raise Refus("ce fichier n'est pas une police TrueType ou OpenType")
        d = med / "_polices"
        d.mkdir(parents=True, exist_ok=True)
        role = "marque" if "marque" in _sans_accent(nom) or "brand" in _sans_accent(nom) else "texte"
        cible = d / f"{role}{ext_nom}"
        for e in POLICES_EXT:
            (d / f"{role}{e}").unlink(missing_ok=True)
        (shutil.move if deplacer else shutil.copyfile)(str(src), str(cible))
        return {"type": "police", "role": role, "fichier": cible.name}
    with open(src, "rb") as h:
        genre, ext = genre_de(h.read(64))
    if not genre:
        raise Refus("type refusé : des photos (jpg, png, heic, webp) ou des musiques (mp3, m4a, wav)")
    if _taille_mediatheque(med) + taille > MEDIATHEQUE_MAX:
        raise Refus("la médiathèque est pleine (50 Go) : efface ce qui ne sert plus")
    d = dossier_collection(collection, med, creer=True)
    ext_final = ".jpg" if ext == ".heic" else (ext_nom if ext == ".jpg" and ext_nom in (".jpg", ".jpeg") else ext)
    cible = _unique(d, nom_fichier(nom, ext_final))
    tmp = d / f".{cible.name}.{os.getpid()}.tmp"
    try:
        if ext == ".heic":
            _convertir_heic(src, tmp)
            if deplacer:
                src.unlink(missing_ok=True)
        elif deplacer:
            shutil.move(str(src), str(tmp))
        else:
            shutil.copyfile(src, tmp)
        fiche = {"collection": d.name, "fichier": cible.name, "type": genre, "taille": tmp.stat().st_size}
        if genre == "photo":
            try:
                w, h = _faire_apercu(tmp, apercu_de(d.name, cible.name, med))
            except Exception as e:                           # noqa: BLE001 — une photo illisible est refusée
                raise Refus(f"photo illisible ({type(e).__name__})")
            fiche.update(apercu=True, apercu_l=w, apercu_h=h)
        else:
            du = _duree_audio(tmp)
            if not du or du < 1:
                raise Refus("musique illisible (aucun son d'au moins une seconde)")
            fiche["duree_s"] = du
        while True:                                          # jamais par-dessus : le lien échoue si le nom vient d'être pris
            try:
                os.link(tmp, cible)
                break
            except FileExistsError:
                ancien = cible
                cible = _unique(d, cible.name)
                if genre == "photo":
                    apercu_de(d.name, ancien.name, med).replace(apercu_de(d.name, cible.name, med))
        fiche["fichier"] = cible.name
        return fiche
    except Refus:
        apercu_de(d.name, cible.name, med).unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)


def _entree(c, f, med):
    ext = f.suffix.lower()
    st = f.stat()
    e = {"collection": c, "fichier": f.name, "type": "photo" if ext in PHOTOS else "musique", "taille": st.st_size,
         "date": round(st.st_mtime)}
    if e["type"] == "photo":
        e["apercu"] = apercu_de(c, f.name, med).is_file()
    else:
        a = _lire(med / ".analyses" / c / (f.name + ".json")) or {}
        if a.get("version") == VERSION_ANALYSE and a.get("taille") == st.st_size:
            e.update(duree_s=a.get("duree"), bpm=a.get("bpm"))
    return e


def lister(collection="", med=None):
    """{collections: [{nom, photos: [...], musiques: [...]}]} : ce qu'il y a sur le disque (les collections dans l'ordre
    alphabétique, les fichiers dans l'ordre de leur nom)."""
    med = Path(med or MEDIATHEQUE)
    out = []
    try:
        dossiers = sorted((x for x in med.iterdir() if x.is_dir() and not x.is_symlink() and x.name[:1] not in "._"),
                          key=lambda x: _sans_accent(x.name))
    except OSError:
        dossiers = []
    if collection:
        cle = _sans_accent(nom_collection(collection))
        dossiers = [x for x in dossiers if _sans_accent(x.name) == cle]
    for d in dossiers:
        photos, musiques = [], []
        for f in sorted(d.iterdir(), key=lambda x: _sans_accent(x.name)):
            if not f.is_file() or f.is_symlink() or f.name.startswith("."):
                continue
            ext = f.suffix.lower()
            if ext in PHOTOS:
                photos.append(_entree(d.name, f, med))
            elif ext in MUSIQUES:
                musiques.append(_entree(d.name, f, med))
        out.append({"nom": d.name, "photos": photos, "musiques": musiques})
    polices = sorted(p.name for p in (med / "_polices").glob("*") if p.suffix.lower() in POLICES_EXT) if (med / "_polices").is_dir() else []
    return {"collections": out, "polices": polices}


def effacer(collection, fichier, med=None):
    """Efface un fichier de la médiathèque (et son aperçu, son analyse) ; une collection vide part avec son dernier fichier
    seulement si on efface la collection elle-même (fichier vide)."""
    med = Path(med or MEDIATHEQUE)
    d = dossier_collection(collection, med)
    if not fichier:
        if not d.is_dir():
            raise Refus("collection inconnue")
        if any(x for x in d.iterdir() if not x.name.startswith(".")):
            raise Refus("la collection n'est pas vide : efface d'abord ses fichiers")
        shutil.rmtree(d)
        for x in (".apercus", ".analyses"):
            shutil.rmtree(med / x / d.name, ignore_errors=True)
        return {"efface": d.name}
    if any(x in str(fichier) for x in ("/", "\\", "..")) or str(fichier).startswith("."):
        raise Refus("un nom de fichier de la collection, sans chemin")
    f = d / str(fichier)
    if not f.is_file() or f.is_symlink() or not _dans(d, f) or f.suffix.lower() not in PHOTOS | MUSIQUES:
        raise Refus("fichier inconnu dans cette collection")
    f.unlink()
    apercu_de(d.name, f.name, med).unlink(missing_ok=True)
    (med / ".analyses" / d.name / (f.name + ".json")).unlink(missing_ok=True)
    return {"efface": f"{d.name}/{f.name}"}


def _chercher(ref, genres, med):
    """« Hiver/IMG_1.jpg », « IMG_1.jpg » ou « IMG_1 » → (collection, chemin) dans la médiathèque, ou None."""
    r = unicodedata.normalize("NFC", str(ref or "").strip().strip("/"))
    if not r:
        return None
    parties = r.split("/")
    l = lister(med=med)["collections"]
    cles = [_sans_accent(x) for x in parties]
    for c in l:
        for e in c["photos"] + c["musiques"]:
            if e["type"] not in genres:
                continue
            nom, souche = _sans_accent(e["fichier"]), _sans_accent(os.path.splitext(e["fichier"])[0])
            if len(cles) >= 2 and _sans_accent(c["nom"]) != cles[-2]:
                continue
            if cles[-1] in (nom, souche):
                return c["nom"], Path(med) / c["nom"] / e["fichier"]
    return None


def photos_de(photos, collection="", med=None, visuels=None):
    """La liste des photos (chemins) : les noms donnés (dans la collection si elle est dite), sinon toute la collection.
    Une image de l'atelier visuel de Hakim (son nom) est aussi une photo."""
    med = Path(med or MEDIATHEQUE)
    if isinstance(photos, str):
        photos = [x for x in re.split(r"[\n;,]+", photos) if x.strip()]
    photos = [str(x).strip() for x in (photos or []) if str(x).strip()]
    out = []
    if not photos:
        if not collection:
            raise Refus("des photos : leurs noms, ou une collection entière (collection=« Hiver »)")
        l = lister(collection, med)["collections"]
        if not l:
            raise Refus(f"collection inconnue : « {collection} »")
        out = [{"collection": l[0]["nom"], "fichier": e["fichier"]} for e in l[0]["photos"]][:PHOTOS_MAX]
        if not out:
            raise Refus(f"la collection « {l[0]['nom']} » n'a pas encore de photo")
        return out
    if len(photos) > PHOTOS_MAX:
        raise Refus(f"{PHOTOS_MAX} photos au plus")
    for p in photos:
        trouve = _chercher(f"{collection}/{p}" if collection and "/" not in p else p, ("photo",), med)
        if trouve:
            out.append({"collection": trouve[0], "fichier": trouve[1].name})
            continue
        try:                                                # une image de son atelier visuel
            sys.path.insert(0, str(ICI))
            import atelier_visuel
            x = atelier_visuel.image_de(p, visuels)
            out.append({"visuel": x["nom"], "chemin": x["fichier"]})
            continue
        except Exception:                                    # noqa: BLE001
            pass
        raise Refus(f"photo inconnue : « {p} » (mediatheque_voir les liste)")
    return out


def musique_de(ref, med=None, chansons=None):
    """Une musique de la médiathèque (« Hiver/son.mp3 », « son.mp3 », « son »), ou une chanson de Hakim (son titre)."""
    med = Path(med or MEDIATHEQUE)
    r = str(ref or "").strip()
    if not r or _cle(r) in ("aucune", "sans", "sans musique", "silence", "rien", "non"):
        return None
    trouve = _chercher(r, ("musique",), med)
    if trouve:
        return {"collection": trouve[0], "fichier": trouve[1].name}
    try:
        sys.path.insert(0, str(ICI))
        import atelier_visuel
        c = atelier_visuel.chanson_de(r, chansons)
        return {"chanson": c.get("titre") or c.get("nom"), "chemin": c["mp3"]}
    except Exception:                                        # noqa: BLE001
        pass
    raise Refus(f"musique inconnue : « {r} » (mediatheque_voir les liste ; une chanson de Hakim par son titre)")


def chemin_media(x, med=None):
    if x.get("chemin"):
        return Path(x["chemin"])
    return Path(med or MEDIATHEQUE) / x["collection"] / x["fichier"]


# ------------------------------------------------------------------------------------------------ l'écoute (numpy)

SR_A = 22050
HOP = 128
DT = HOP / SR_A


def lire_mono(chemin, sr=SR_A, debut=0.0, duree=None):
    import numpy as np
    a = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error"]
    if debut:
        a += ["-ss", f"{float(debut):.3f}"]
    if duree:
        a += ["-t", f"{float(duree):.3f}"]
    a += ["-i", str(chemin), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(a, capture_output=True, timeout=900)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : lecture impossible de {Path(chemin).name}")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _trames(x, n, pas):
    """Le module du spectre, trame t centrée à t·pas (float32, par paquets : la mémoire reste petite)."""
    import numpy as np
    xp = np.concatenate([np.zeros(n // 2, np.float32), x.astype(np.float32), np.zeros(n // 2, np.float32)])
    k = 1 + max(0, (len(xp) - n) // pas)
    w = np.hanning(n).astype(np.float32)
    S = np.empty((k, n // 2 + 1), np.float32)
    base = np.arange(n)
    for a in range(0, k, 1024):
        b = min(k, a + 1024)
        S[a:b] = np.abs(np.fft.rfft(xp[base[None, :] + pas * np.arange(a, b)[:, None]] * w, axis=1))
    return S


def enveloppes(x, sr=SR_A):
    """(o, grave) : le flux spectral (hausses du spectre en log, toutes bandes) et celui des graves (≤ 160 Hz : la grosse
    caisse), une valeur toutes les HOP échantillons, moins leur tendance (0,25 s), normalisés."""
    import numpy as np
    S = _trames(x, 1024, HOP)
    f = np.fft.rfftfreq(1024, 1.0 / sr)
    L = np.log1p(1000.0 * S / (float(S.max()) + 1e-12))
    D = np.maximum(0.0, np.diff(L, axis=0, prepend=L[:1]))
    o = D[:, f < 8000].sum(axis=1)
    g = D[:, f <= 160].sum(axis=1)

    def net(v):
        k = max(3, int(0.25 / DT))
        t = np.convolve(v, np.ones(k) / k, mode="same")
        v = np.maximum(0.0, v - t)
        return v / (v.std() + 1e-9)
    return net(o), net(g)


def tempo_de(o, bpm_min=55, bpm_max=200):
    """Le tempo (BPM) par autocorrélation du flux (le temps, ses doubles et quadruples), une préférence douce autour de
    120, ramené entre 75 et 180 ; un 3 pour 2 lu sous 100 BPM est corrigé (comme studio_mesures)."""
    import numpy as np
    n = len(o)
    if n < int(4 / DT):
        return 0.0, 0.0
    F = np.fft.rfft(o - o.mean(), 2 * n)
    ac = np.fft.irfft(F * np.conj(F))[:n]
    ac = ac / (ac[0] + 1e-12)
    lags = np.arange(int(60 / bpm_max / DT), min(n - 1, int(60 / bpm_min / DT)) + 1)
    s = ac[lags] + 0.5 * ac[np.minimum(2 * lags, n - 1)] + 0.25 * ac[np.minimum(4 * lags, n - 1)]
    bpms = 60.0 / (lags * DT)
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 1.0) ** 2)
    i = int(np.argmax(np.maximum(s, 0) * prior))
    l = int(lags[i])
    a, b, c = ac[l - 1], ac[l], ac[l + 1]
    dl = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    bpm = 60.0 / ((l + max(-0.5, min(0.5, dl))) * DT)
    while bpm < 75:
        bpm *= 2
    while bpm > 180:
        bpm /= 2

    def ac_de(v):
        lag = 60.0 / v / DT
        k = int(lag)
        return float(ac[k] + (lag - k) * (ac[k + 1] - ac[k])) if 1 <= k < n - 1 else -1.0
    if bpm < 100 and ac_de(bpm * 1.5) >= 0.75 * ac_de(bpm):
        bpm *= 1.5
    confiance = float(max(0.0, s[i]))
    return float(bpm), confiance


def suivre_temps(o, periode):
    """Les temps (indices de trame) par programmation dynamique : chaque temps prend le meilleur précédent entre ½ et 2
    périodes, pénalisé par l'écart au tempo (log² du rapport, raideur 100)."""
    import numpy as np
    n = len(o)
    if n < 3 * periode or periode < 2:
        return np.zeros(0, int)
    on = o.astype(np.float64)
    loin, pres = int(round(2 * periode)), max(1, int(round(periode / 2)))
    offs = np.arange(-loin, -pres + 1)
    cout = -100.0 * np.log(-offs / periode) ** 2
    score = on.copy()
    prec = np.full(n, -1)
    for t in range(pres, n):
        a = t + offs
        ok = a >= 0
        if not ok.any():
            continue
        c = score[a[ok]] + cout[ok]
        j = int(np.argmax(c))
        if c[j] > 0:
            score[t] = on[t] + c[j]
            prec[t] = a[ok][j]
    fin = n - int(periode)
    t = fin + int(np.argmax(score[fin:]))
    l = []
    while t >= 0:
        l.append(t)
        t = prec[t]
    l = np.array(l[::-1])
    if len(l) < 4:
        return l
    seuil = 0.4 * float(np.sqrt(np.mean(on[l] ** 2)))   # les temps vides des bords (silence avant ou après) partent
    a, b = 0, len(l)
    while a < b and on[l[a]] < seuil:
        a += 1
    while b > a and on[l[b - 1]] < seuil:
        b -= 1
    return l[a:b]


def affiner(x, sr, temps, demi_fenetre=0.045):
    """Chaque temps à la milliseconde : dans ±45 ms, l'instant où l'énergie (fenêtres de 1 ms) franchit la moitié de sa
    montée vers le pic ; NaN si aucune montée nette (moins de 6 dB)."""
    import numpy as np
    w = max(1, int(round(sr * 0.001)))
    k = len(x) // w
    e = np.sqrt((x[: k * w].astype(np.float64).reshape(k, w) ** 2).mean(axis=1)) + 1e-9
    out = np.full(len(temps), np.nan)
    m = int(demi_fenetre * sr / w)
    for i, t in enumerate(temps):
        c = int(t * sr / w)
        a, b = max(0, c - m), min(k, c + m)
        seg = e[a:b]
        if len(seg) < 10:
            continue
        ip = int(np.argmax(seg))
        if ip < 2:
            continue
        im = int(np.argmin(seg[: ip + 1]))
        bas, haut = seg[im], seg[ip]
        if haut < 2.0 * bas:
            continue
        j = im + int(np.argmax(seg[im: ip + 1] >= bas + 0.5 * (haut - bas)))
        # la fraction de fenêtre : interpolation linéaire entre j-1 et j
        if j > im:
            v0, v1 = seg[j - 1], seg[j]
            fr = (bas + 0.5 * (haut - bas) - v0) / (v1 - v0) if v1 > v0 else 0.0
        else:
            fr = 0.0
        out[i] = (a + j - 1 + fr + 0.5) * w / sr
    return out


def grille(dp, fins, periode_s):
    """Les temps définitifs : une droite (tempo constant) ajustée sur les temps affinés si elle les tient à 12 ms près,
    sinon une droite locale par temps (± 8 temps). Rend (temps, mode)."""
    import numpy as np
    if len(dp) < 4:
        return dp, "brut"
    k = np.round((dp - dp[0]) / periode_s).astype(int)
    k, idx = np.unique(k, return_index=True)
    dp, fins = dp[idx], fins[idx]
    v = ~np.isnan(fins)
    if v.sum() >= 8:
        for _ in range(4):
            a, b = np.polyfit(k[v], fins[v], 1)[::-1]
            res = fins - (a + b * k)
            v2 = v & (np.abs(res) < 0.025)
            if v2.sum() < 8 or (v2 == v).all():
                v = v2 if v2.sum() >= 8 else v
                break
            v = v2
        a, b = np.polyfit(k[v], fins[v], 1)[::-1]
        res = fins[v] - (a + b * k[v])
        if float(np.sqrt(np.mean(res ** 2))) < 0.012:
            kk = np.arange(k.min(), k.max() + 1)
            return a + b * kk, "constant"
    biais = float(np.nanmedian(fins - dp)) if v.any() else 0.0
    out = dp + biais
    for i in range(len(dp)):
        p = v & (np.abs(k - k[i]) <= 8)
        if p.sum() >= 4:
            a, b = np.polyfit(k[p], fins[p], 1)[::-1]
            out[i] = a + b * k[i]
    return out, "local"


def _chroma(x, sr, temps):
    """Le chroma (12 classes de hauteur, 60-2500 Hz) moyen de chaque intervalle entre deux temps, normé."""
    import numpy as np
    n, pas = 4096, 1024
    S = _trames(x, n, pas)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    m = (f >= 60) & (f <= 2500)
    pc = ((np.round(12 * np.log2(f[m] / 440.0)).astype(int) + 9) % 12)
    P = S[:, m] ** 2
    C = np.zeros((S.shape[0], 12), np.float64)
    for p in range(12):
        C[:, p] = P[:, pc == p].sum(axis=1)
    C = np.log1p(C / (C.max() + 1e-12) * 1e4)
    tt = np.arange(S.shape[0]) * pas / sr
    out = np.zeros((max(0, len(temps) - 1), 12))
    for i in range(len(temps) - 1):
        s = (tt >= temps[i]) & (tt < temps[i + 1])
        if s.any():
            out[i] = C[s].mean(axis=0)
    nrm = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(nrm, 1e-9)


def _energie_db(x, sr, temps):
    import numpy as np
    out = []
    for a, b in zip(temps[:-1], temps[1:]):
        s = x[int(a * sr): int(b * sr)]
        out.append(10 * math.log10(float(np.mean(s.astype(np.float64) ** 2)) + 1e-12) if len(s) else -120.0)
    return np.array(out)


def analyser(chemin):
    """Toute l'écoute d'une musique : durée, tempo, temps (s), temps forts (indices des débuts de mesure), énergie et chroma
    de chaque mesure. Rend un dict (sans numpy)."""
    import numpy as np
    t0 = time.time()
    x = lire_mono(chemin)
    duree = len(x) / SR_A
    o, g = enveloppes(x)
    bpm, conf = tempo_de(o)
    out = {"version": VERSION_ANALYSE, "duree": round(duree, 3), "bpm": 0.0, "confiance": 0.0, "temps": [], "mesures": [],
           "mesure_s": 0.0, "energie": [], "chroma": [], "mode": "sans temps"}
    if bpm > 0:
        periode = 60.0 / bpm
        dp = suivre_temps(o, periode / DT) * DT
        if len(dp) >= 8:
            if "affinage" in COUPE:
                temps, mode = dp, "brut"
            else:
                temps, mode = grille(dp, affiner(x, SR_A, dp), periode)
            temps = temps[(temps >= 0) & (temps < duree)]
            if len(temps) >= 2:
                bpm = 60.0 / float(np.median(np.diff(temps)))
            # le temps fort : la grosse caisse et les changements d'accords tombent sur le premier temps de la mesure
            ch = _chroma(x, SR_A, np.append(temps, duree))
            nov = np.r_[0.0, 1.0 - np.sum(ch[1:] * ch[:-1], axis=1)]
            gr = np.array([g[max(0, int(t / DT) - 3): int(t / DT) + 4].max() if int(t / DT) < len(g) else 0.0 for t in temps])
            z = lambda v: (v - v.mean()) / (v.std() + 1e-9)          # noqa: E731
            sc = [float(0.5 * np.mean(z(gr)[d::4]) + np.mean(z(nov)[d::4])) for d in range(4)]
            d = int(np.argmax(sc))
            debuts = list(range(d, len(temps), 4))
            bornes = [temps[i] for i in debuts] + [temps[-1] + periode if debuts else duree]
            bornes[-1] = min(duree, bornes[-1])
            en = _energie_db(x, SR_A, np.array(bornes)) if len(bornes) > 1 else np.zeros(0)
            chm = []
            for j, i in enumerate(debuts):
                v = ch[i: i + 4].mean(axis=0) if i < len(ch) else np.zeros(12)
                chm.append(v / max(1e-9, float(np.linalg.norm(v))))
            out.update(bpm=round(float(bpm), 2), confiance=round(min(1.0, conf), 3), temps=[round(float(t), 4) for t in temps],
                       mesures=debuts, mesure_s=round(4 * periode, 4), energie=[round(float(v), 2) for v in en],
                       chroma=[[round(float(c), 3) for c in v] for v in chm], mode=mode)
    if not out["temps"]:                                     # sans temps : l'énergie par demi-seconde
        pas = 0.5
        bornes = np.arange(0, duree + 1e-9, pas)
        out["energie_fenetres"] = [round(float(v), 2) for v in _energie_db(x, SR_A, bornes)]
    out["calcul_s"] = round(time.time() - t0, 2)
    return out


def analyse_de(chemin, med=None):
    """L'analyse d'une musique, gardée dans .analyses/ (refaite si le fichier a changé)."""
    p = Path(chemin)
    med = Path(med or MEDIATHEQUE)
    st = p.stat()
    cache = None
    if _dans(med, p) and Path(os.path.realpath(p)).parent.parent == Path(os.path.realpath(med)):
        cache = med / ".analyses" / p.parent.name / (p.name + ".json")
    a = _lire(cache) if cache else None
    if a and a.get("version") == VERSION_ANALYSE and a.get("taille") == st.st_size and not COUPE:
        return a
    a = analyser(p)
    a["taille"] = st.st_size
    if cache and not COUPE:
        try:
            _ecrire(cache, a)
        except OSError:
            pass
    return a


def meilleur_passage(an, duree):
    """Le début (s) du meilleur passage de `duree` secondes : sur un début de mesure, la fenêtre la plus forte, la plus
    répétée ailleurs (un refrain revient), et qui commence à une frontière de section. Rend {debut, raison, refrain}."""
    import numpy as np
    total = float(an["duree"])
    if duree >= total - 0.05 or "refrain" in COUPE:
        t = float(an["temps"][an["mesures"][0]]) if an.get("mesures") and "refrain" not in COUPE else 0.0
        t = t if t + duree <= total else 0.0
        return {"debut": round(t, 3), "raison": "le début du morceau" if "refrain" in COUPE else "le morceau entier", "refrain": False}
    if not an.get("mesures") or len(an["mesures"]) < 4:
        e = np.array(an.get("energie_fenetres") or [0.0])
        k = max(1, int(round(duree / 0.5)))
        if len(e) <= k:
            return {"debut": 0.0, "raison": "le morceau entier", "refrain": False}
        moy = np.convolve(e, np.ones(k) / k, mode="valid")
        moy[: max(1, int(len(e) * 0.05))] -= 3.0                    # pas l'intro
        i = int(np.argmax(moy))
        return {"debut": round(i * 0.5, 3), "raison": "le passage le plus fort", "refrain": False}
    temps = np.array(an["temps"])
    debuts = np.array([temps[i] for i in an["mesures"]])
    E = np.array(an["energie"], float)
    C = np.array(an["chroma"], float)
    nb = len(debuts)
    mesure = float(an["mesure_s"]) or float(np.median(np.diff(debuts)))
    B = max(1, int(math.ceil(duree / mesure - 1e-6)))
    R = min(B, 8)                                               # la répétition se juge sur 8 mesures au plus
    cands = [s for s in range(nb) if debuts[s] + duree <= total - 0.25 and s + 1 <= len(E)]
    if not cands:
        return {"debut": 0.0, "raison": "le morceau entier", "refrain": False}
    en = np.array([E[s: s + B].mean() for s in cands])
    rep = []
    for s in cands:
        best = 0.0
        for s2 in range(0, nb - R + 1):
            if abs(s2 - s) < max(2, R // 2) or s + R > len(C) or s2 + R > len(C):
                continue
            v = float(np.mean(np.sum(C[s: s + R] * C[s2: s2 + R], axis=1)))
            best = max(best, v)
        rep.append(best)
    rep = np.array(rep)
    bord = []
    for s in cands:
        if s < 2 or s + 2 > len(C):
            bord.append(0.0)
            continue
        a, b = C[s - 2: s].mean(axis=0), C[s: s + 2].mean(axis=0)
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        bord.append((1 - cos) + max(0.0, (E[s] - E[s - 1]) / 6.0))
    bord = np.array(bord)
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9) if v.std() > 1e-9 else v * 0   # noqa: E731
    score = z(en) + 0.8 * z(rep) + 0.5 * z(bord)
    intro = total * 0.06
    score -= np.array([1.5 if debuts[s] < intro else 0.0 for s in cands])
    i = int(np.argmax(score))
    s = cands[i]
    refrain = bool(rep[i] >= max(0.9, float(np.percentile(rep, 75))) and en[i] >= float(np.percentile(en, 66)))
    return {"debut": round(float(debuts[s]), 3), "raison": "le refrain probable" if refrain else "le passage le plus fort",
            "refrain": refrain, "mesure": int(s)}


def choisir_passage(an, duree, debut_s=None):
    """Le passage : le début demandé (posé sur le temps le plus proche qui laisse la durée entière), sinon le meilleur."""
    if debut_s is None:
        return meilleur_passage(an, duree)
    debut = min(float(debut_s), max(0.0, an["duree"] - duree))
    possibles = [x for x in an.get("temps", []) if x + duree <= an["duree"]]
    if possibles:
        debut = min(possibles, key=lambda x: abs(x - debut))
    return {"debut": round(debut, 3), "raison": "le début demandé", "refrain": False}


def temps_du_passage(an, debut, duree):
    """Les temps et les débuts de mesure DANS le passage, en secondes depuis son début."""
    t = [x - debut for x in an.get("temps", []) if debut - 1e-6 <= x < debut + duree]
    fort = {round(an["temps"][i], 4) for i in an.get("mesures", [])}
    m = [x - debut for x in an.get("temps", []) if debut - 1e-6 <= x < debut + duree and round(x, 4) in fort]
    return t, m


# ------------------------------------------------------------------------------------------------ le plan des coupes

def plan_coupes(temps, duree, n_photos, rythme="auto", mesures=None, bpm=0.0):
    """Les coupes (s, depuis le début) : tous les N temps, en partant d'un début de mesure ; N vient du rythme (lent 4,
    normal 2, rapide 1) ou, en « auto », est le plus grand de 8, 4, 2, 1 qui montre chaque photo au moins une fois ; un
    plan ne dure jamais moins de 0,35 s, et le dernier au moins 0,6 s. Rend (coupes, N)."""
    temps = [float(t) for t in temps if 0 <= t < duree]
    if "calage" in COUPE or len(temps) < 2:
        n = max(1, n_photos)
        pas = duree / n
        if len(temps) >= 2 and "calage" in COUPE:                 # témoin : des coupes régulières, à côté des temps
            per = (temps[-1] - temps[0]) / (len(temps) - 1)
            n = max(1, int(round(duree / (2 * per))))
            pas = duree / n + per * 0.37
        return [round(pas * i, 4) for i in range(1, n) if pas * i < duree - 0.6], 0
    periode = (temps[-1] - temps[0]) / (len(temps) - 1)
    i0 = 0
    if mesures:
        m0 = min(mesures)
        i0 = min(range(len(temps)), key=lambda i: abs(temps[i] - m0))
    base = RYTHMES.get(rythme)
    if base is None:
        base = 1
        for n in (8, 4, 2, 1):
            if len(temps[i0::n]) >= n_photos or n == 1:
                base = n
                break
    while base * periode < 0.35 and base < 8:
        base *= 2
    coupes = [t for t in temps[i0::base] if 0.3 <= t < duree - 0.6]
    return [round(t, 4) for t in coupes], base


# ------------------------------------------------------------------------------------------------ le son

def mesure_niveau(fichier):
    """{lufs, tp} (ffmpeg ebur128 : BS.1770-4, crête vraie suréchantillonnée) ; pour un MP4, sa piste son."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", str(fichier), "-vn", "-af", "ebur128=peak=true:framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    err = r.stderr
    res = err[err.rfind("Summary:"):] if "Summary:" in err else err

    def val(motif, vide):
        m = re.search(motif, res)
        if not m:
            return None
        return vide if "inf" in m.group(1) else round(float(m.group(1)), 2)
    return {"lufs": val(r"I:\s+(-?[\d.]+|-inf) LUFS", -70.0), "tp": val(r"Peak:\s+(-?[\d.]+|-inf) dBFS", -120.0)}


def _ff(args, timeout=900):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *map(str, args)], capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : {r.stderr.strip()[-400:]}")


AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def preparer_son(src, debut, duree, sortie, travail, cible=CIBLE_LUFS, crete=CRETE_MAX):
    """Le passage → un WAV 48 kHz stéréo de `duree` s exactement : fondus (entrée 0,1 s, sortie 0,5-1,5 s), puis gain et
    limiteur jusqu'à −14 LUFS ±0,5 et une crête vraie ≤ −1,2 dBTP MESURÉE APRÈS L'AAC (13/11 : un passage dense de « Deux
    livres » à −2,3 dBTP en WAV sortait à +0,5 dBTP de l'AAC : le codeur ajoute jusqu'à 3 dB de crête ; on mesure donc ce
    qui sera publié, encodé comme la vidéo l'encodera). Sans musique : du silence. Rend {lufs, tp, tp_wav, gain_db, source_lufs}."""
    travail = Path(travail)
    travail.mkdir(parents=True, exist_ok=True)
    n = int(round(duree * 48000))
    if not src:
        _ff(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-af", f"atrim=end_sample={n}", "-c:a", "pcm_s16le", sortie])
        return {"lufs": None, "tp": None, "gain_db": 0.0, "source_lufs": None, "silence": True}
    fs = round(min(1.5, max(0.5, 0.12 * duree)), 2)
    brut = travail / "son-brut.wav"
    _ff(["-ss", f"{max(0.0, debut):.4f}", "-i", src, "-vn", "-af",
         f"aresample=48000,aformat=channel_layouts=stereo,apad,atrim=end_sample={n},asetpts=N/SR/TB,"
         f"afade=t=in:st=0:d=0.1,afade=t=out:st={duree - fs:.3f}:d={fs}", "-c:a", "pcm_f32le", brut])
    m0 = mesure_niveau(brut)
    if "volume" in COUPE or m0["lufs"] is None or m0["lufs"] <= -69:
        _ff(["-i", brut, "-c:a", "pcm_s16le", sortie])
        return {"lufs": m0["lufs"], "tp": m0["tp"], "gain_db": 0.0, "source_lufs": m0["lufs"]}
    gain, plafond = cible - m0["lufs"], -2.0
    essai = travail / "son-essai.m4a"
    m, mw = m0, m0
    for _ in range(8):
        _ff(["-i", brut, "-af", f"volume={gain:.3f}dB,alimiter=limit={10 ** (plafond / 20):.5f}:attack=2:release=80:level=false:"
             f"latency=1,atrim=end_sample={n}", "-c:a", "pcm_f32le", sortie])
        mw = mesure_niveau(sortie)
        if "aac" in COUPE:                                       # témoin : la crête jugée sur le WAV, comme avant le 13/11
            m = mw
        else:
            _ff(["-i", sortie, *AAC, essai])                     # ce que la vidéo contiendra
            m = mesure_niveau(essai)
        if m["lufs"] is None:
            break
        ok_l, ok_c = abs(m["lufs"] - cible) <= 0.5, m["tp"] <= crete - 0.2
        if ok_l and ok_c:
            break
        if not ok_c:
            plafond -= max(0.4, m["tp"] - (crete - 0.2) + 0.2)
        gain += cible - m["lufs"]
    return {"lufs": m["lufs"], "tp": m["tp"], "tp_wav": mw["tp"], "gain_db": round(gain, 2), "plafond_db": round(plafond, 2),
            "source_lufs": m0["lufs"]}


# ------------------------------------------------------------------------------------------------ l'image (Pillow)

POLICES = {
    "marque": [("/System/Library/Fonts/Supplemental/Didot.ttc", ("Regular",)),
               ("/System/Library/Fonts/Supplemental/Bodoni 72.ttc", ("Book", "Regular")),
               ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", ()),
               ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", ()),
               ("/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf", ()),
               ("C:/Windows/Fonts/georgia.ttf", ())],
    "titre": [("/System/Library/Fonts/Avenir Next.ttc", ("Medium",)),
              ("/System/Library/Fonts/HelveticaNeue.ttc", ("Medium",)),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", ()),
              ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", ()),
              ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", ()),
              ("C:/Windows/Fonts/segoeui.ttf", ())],
    "gras": [("/System/Library/Fonts/Avenir Next.ttc", ("Demi Bold",)),
             ("/System/Library/Fonts/HelveticaNeue.ttc", ("Bold",)),
             ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ()),
             ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", ()),
             ("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", ()),
             ("C:/Windows/Fonts/segoeuib.ttf", ())],
    "arabe": [("/System/Library/Fonts/GeezaPro.ttc", ()), ("/System/Library/Fonts/Supplemental/Baghdad.ttc", ()),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", ()),
              ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", ())],
}
_polices_cache = {}
_polices_verrou = threading.Lock()


def police(role, taille, med=None):
    """La police d'un rôle (marque, titre, gras, arabe) : celle que l'ami a déposée (_polices/marque.ttf, texte.ttf), sinon
    celles du système (Mac, Linux, Windows), sinon celle de Pillow (Aileron, à toute taille)."""
    from PIL import ImageFont
    cle = (role, int(taille), str(med or MEDIATHEQUE))
    with _polices_verrou:
        if cle in _polices_cache:
            return _polices_cache[cle]
        f = None
        perso = Path(med or MEDIATHEQUE) / "_polices"
        for nom in (["marque"] if role == "marque" else ["texte"] if role in ("titre", "gras") else []):
            for e in (".ttf", ".otf"):
                if (perso / f"{nom}{e}").is_file():
                    try:
                        f = ImageFont.truetype(str(perso / f"{nom}{e}"), int(taille))
                    except OSError:
                        pass
        for chemin, styles in ([] if f else POLICES[role]):
            if not Path(chemin).exists():
                continue
            try:
                if not styles:
                    f = ImageFont.truetype(chemin, int(taille))
                    break
                for i in range(24):
                    try:
                        g = ImageFont.truetype(chemin, int(taille), index=i)
                    except OSError:
                        break
                    if g.getname()[1] in styles:
                        f = g
                        break
                if f:
                    break
            except OSError:
                continue
        if f is None:
            try:
                f = ImageFont.load_default(size=int(taille))
            except TypeError:
                f = ImageFont.load_default()
        _polices_cache[cle] = f
        return f


def _arabe(c):
    return "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" or "ﭐ" <= c <= "﷿" or "ﹰ" <= c <= "﻿"


def _morceaux(texte):
    t = str(texte)
    if any(_arabe(c) for c in t):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            t = get_display(arabic_reshaper.reshape(t))
        except ImportError:
            pass
    out = []
    for c in t:
        g = "arabe" if _arabe(c) else "latin"
        if c == " " and out:
            g = out[-1][0]
        if out and out[-1][0] == g:
            out[-1][1] += c
        else:
            out.append([g, c])
    return out


def _largeur(ligne, f, fa, esp):
    larg = 0.0
    for g, s in _morceaux(ligne):
        if g == "arabe":
            larg += fa.getlength(s)
        else:
            larg += sum(f.getlength(c) for c in s) + esp * max(0, len(s) - 1) if esp else f.getlength(s)
    return larg


def _couper(texte, f, fa, esp, largeur, lignes_max=2):
    mots = texte.split()
    lignes, cur = [], ""
    for m in mots:
        essai = (cur + " " + m).strip()
        if cur and _largeur(essai, f, fa, esp) > largeur:
            lignes.append(cur)
            cur = m
        else:
            cur = essai
    if cur:
        lignes.append(cur)
    if len(lignes) > lignes_max:
        lignes = lignes[: lignes_max - 1] + [" ".join(lignes[lignes_max - 1:])]
    return lignes


def calque_texte(texte, role, taille, largeur_max, espacement=0.0, majuscules=False, ombre=True, couleur=(255, 255, 255),
                 lignes_max=2, med=None):
    """Un texte en calque RGBA serré (avec son ombre douce) : coupé en 2 lignes au plus, rétréci s'il déborde encore.
    L'espacement des lettres (em) ne s'applique pas à l'arabe."""
    from PIL import Image, ImageDraw, ImageFilter
    t = _texte(texte, 120)
    if majuscules:
        t = t.upper()
    if not t:
        return None
    while True:
        f, fa = police(role, taille, med), police("arabe", taille, med)
        esp = 0.0 if any(_arabe(c) for c in t) else espacement * taille
        lignes = _couper(t, f, fa, esp, largeur_max, lignes_max)
        larg = max(_largeur(l, f, fa, esp) for l in lignes)
        if larg <= largeur_max or taille <= 14:
            break
        taille = int(taille * 0.92)
    interligne = int(taille * 1.22)
    marge = int(taille * 0.5) + 4
    W = int(larg) + 2 * marge
    H = interligne * len(lignes) + 2 * marge
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    om = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di, do = ImageDraw.Draw(img), ImageDraw.Draw(om)
    for j, l in enumerate(lignes):
        x = marge + (larg - _largeur(l, f, fa, esp)) / 2
        y = marge + interligne * j + interligne / 2
        for g, s in _morceaux(l):
            pol = fa if g == "arabe" else f
            pas = [s] if (g == "arabe" or not esp) else list(s)
            for c in pas:
                if ombre:
                    do.text((x, y + taille * 0.05), c, font=pol, fill=(0, 0, 0, 165), anchor="lm")
                di.text((x, y), c, font=pol, fill=(*couleur, 255), anchor="lm")
                x += pol.getlength(c) + (esp if pas is not None and len(pas) > 1 else 0)
    if ombre:
        om = om.filter(ImageFilter.GaussianBlur(max(2, taille // 10)))
        img = Image.alpha_composite(om, img)
    return img


def calque_appel(texte, taille, largeur_max, med=None):
    """L'appel à l'action : en capitales espacées, sombre sur une pastille claire arrondie."""
    from PIL import Image, ImageDraw, ImageFilter
    t = calque_texte(texte, "gras", taille, largeur_max - 2 * taille, espacement=0.12, majuscules=True, ombre=False,
                     couleur=(20, 20, 22), lignes_max=2, med=med)
    if t is None:
        return None
    bbox = t.getbbox() or (0, 0, t.width, t.height)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = int(taille * 1.0), int(taille * 0.62)
    W, H = tw + 2 * px + 24, th + 2 * py + 24
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 16, W - 12, H - 8), radius=(H - 24) // 2, fill=(0, 0, 0, 90))
    img = img.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 12, W - 12, H - 12), radius=(H - 24) // 2, fill=(250, 248, 244, 238))
    img.alpha_composite(t.crop(bbox), (px + 12, py + 12))
    return img


def _ease(u):
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


class Montage:
    """Les plans, leurs mouvements, les textes : une image du montage à l'instant t (fonction pure, sûre en fils)."""
    MARGE = 1.12

    def __init__(self, photos, coupes, duree, W, H, transition="nette", textes=None, med=None, fondu_s=0.24):
        from PIL import Image
        self.W, self.H, self.duree = W, H, float(duree)
        self.CW, self.CH = int(round(W * self.MARGE)), int(round(H * self.MARGE))
        # chaque coupe sur l'image la plus proche de son temps (1/30 s) : la nouvelle photo apparaît sur cette image-là
        bornes = [0.0] + [round(float(c) * FPS) / FPS for c in coupes] + [float(duree)]
        self.plans = []
        for i in range(len(bornes) - 1):
            self.plans.append({"debut": bornes[i], "fin": bornes[i + 1], "photo": i % len(photos)})
        self.toiles = [self._toile(p) for p in photos]
        self.fondu = fondu_s if transition == "fondu" else 0.0
        mouvements = ("zoom_avant", "glisse_droite", "zoom_arriere", "glisse_gauche")
        for i, p in enumerate(self.plans):
            p["mouvement"] = mouvements[i % len(mouvements)]
            p["z"] = min(0.10, max(0.04, 0.035 + 0.02 * (p["fin"] - p["debut"])))
        self.textes = self._calques(textes or {}, med)
        self.Image = Image

    def _toile(self, chemin):
        """La photo à la taille de la toile (le cadre × 1,12, la marge du mouvement) : elle couvre la toile si sa forme
        est proche (×1,35 au plus), sinon elle y entre entière sur un fond d'elle-même, agrandi, flouté, assombri."""
        from PIL import ImageEnhance, ImageFilter, ImageOps
        Image = _pil()
        im = Image.open(chemin)
        im.draft("RGB", (self.CW * 2, self.CH * 2))
        im = ImageOps.exif_transpose(im).convert("RGB")
        CW, CH = self.CW, self.CH
        r = (im.width / im.height) / (CW / CH)
        k = max(CW / im.width, CH / im.height)
        fond = im.resize((max(CW, round(im.width * k)), max(CH, round(im.height * k))), Image.LANCZOS)
        fond = fond.crop(((fond.width - CW) // 2, (fond.height - CH) // 2, (fond.width - CW) // 2 + CW, (fond.height - CH) // 2 + CH))
        if 1 / 1.35 <= r <= 1.35:
            return fond
        fond = ImageEnhance.Brightness(fond.filter(ImageFilter.GaussianBlur(max(CW, CH) // 36))).enhance(0.5)
        k = min(CW / im.width, CH / im.height) * 0.94
        devant = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        fond.paste(devant, ((CW - devant.width) // 2, (CH - devant.height) // 2))
        return fond

    def _calques(self, t, med):
        """Les textes en calques, placés dans la zone sûre : la marque en haut, la pièce et le prix (ou la légende de la
        photo) en bas, l'appel à l'action au milieu à la fin. Les bandes sombres en dégradé derrière, pour la lecture."""
        from PIL import Image
        W, H = self.W, self.H
        vertical = H / W > 1.5
        u = W / 1080.0
        largeur = W - 2 * int(W * (0.13 if vertical else 0.08))
        y_marque = H * (0.115 if vertical else 0.075)
        y_bas = H * (0.70 if vertical else 0.83)
        out = {"marque": None, "bas": [], "appel": None, "voiles": []}
        if t.get("marque"):
            c = calque_texte(t["marque"], "marque", int(60 * u), largeur, espacement=0.22, majuscules=True, lignes_max=1, med=med)
            if c:
                out["marque"] = (c, int((W - c.width) / 2), int(y_marque - c.height / 2))
                out["voiles"].append(("haut", 0, int(H * 0.24)))

        def bloc(piece, prix):
            from PIL import Image as I
            a = calque_texte(piece, "titre", int(56 * u), largeur, espacement=0.02, med=med) if piece else None
            b = calque_texte(prix, "gras", int(46 * u), largeur, espacement=0.06, lignes_max=1, med=med) if prix else None
            if not a and not b:
                return None
            if a and b:
                h = a.height + b.height - int(30 * u)
                img = I.new("RGBA", (max(a.width, b.width), h), (0, 0, 0, 0))
                img.alpha_composite(a, ((img.width - a.width) // 2, 0))
                img.alpha_composite(b, ((img.width - b.width) // 2, a.height - int(30 * u)))
                return img
            return a or b
        legendes = [x for x in (t.get("legendes") or [])]
        if any(_texte(x, 120) for x in legendes):
            for x in legendes:
                piece, _, prix = str(x or "").partition("|")
                c = bloc(piece.strip(), prix.strip())
                out["bas"].append((c, int((W - c.width) / 2), int(y_bas - c.height / 2)) if c else None)
            out["par_photo"] = True
        else:
            c = bloc(t.get("piece"), t.get("prix"))
            if c:
                out["bas"] = [(c, int((W - c.width) / 2), int(y_bas - c.height / 2))]
            out["par_photo"] = False
        if any(out["bas"]):
            out["voiles"].append(("bas", int(H * (0.52 if vertical else 0.62)), H))
        if t.get("appel"):
            c = calque_appel(t["appel"], int(54 * u), largeur, med)
            if c:
                out["appel"] = (c, int((W - c.width) / 2), int(H * 0.5 - c.height / 2))
        # les masques à 17 niveaux (les fondus des textes), et les voiles en dégradé
        out["niveaux"] = {}
        for nom, x in [("marque", out["marque"]), ("appel", out["appel"])] + [(f"bas{i}", c) for i, c in enumerate(out["bas"])]:
            if x:
                a = x[0].getchannel("A")
                out["niveaux"][nom] = [a.point(lambda v, f=k / 16: int(v * f)) for k in range(17)]
        voiles = []
        for sens, y0, y1 in out["voiles"]:
            h = max(1, y1 - y0)
            m = Image.new("L", (1, h))
            for i in range(h):
                f = (1 - i / h) if sens == "haut" else (i / h)
                m.putpixel((0, i), int((0.42 if sens == "haut" else 0.58) * 255 * f ** 1.6))
            voiles.append((m.resize((W, h)), y0, y1))
        out["voiles"] = voiles
        return out

    def plan_a(self, t):
        for i, p in enumerate(self.plans):
            if t < p["fin"] or i == len(self.plans) - 1:
                return i
        return len(self.plans) - 1

    def vue(self, i, t):
        from PIL import Image
        p = self.plans[i]
        a, b = p["debut"] - self.fondu / 2, p["fin"] + self.fondu / 2
        e = _ease((t - a) / max(1e-6, b - a))
        z, CW, CH = p["z"], self.CW, self.CH
        mv = p["mouvement"]
        if mv == "zoom_avant":
            k, fx = 1.0 + z * e, 0.5
        elif mv == "zoom_arriere":
            k, fx = 1.0 + z * (1 - e), 0.5
        elif mv == "glisse_droite":
            k, fx = 1.0 + z * 0.6, 0.15 + 0.7 * e
        else:
            k, fx = 1.0 + z * 0.6, 0.85 - 0.7 * e
        vw, vh = CW / k, CH / k
        x0 = (CW - vw) * fx
        y0 = (CH - vh) / 2
        return self.toiles[p["photo"]].transform((self.W, self.H), Image.Transform.EXTENT, (x0, y0, x0 + vw, y0 + vh),
                                                 resample=Image.Resampling.BILINEAR)

    def _niveau(self, f):
        return max(0, min(16, int(round(f * 16))))

    def image(self, t, couverture=False):
        from PIL import Image
        i = self.plan_a(t)
        img = self.vue(i, t)
        if self.fondu:
            for j in (i - 1, i + 1):
                if 0 <= j < len(self.plans):
                    c = self.plans[i]["debut"] if j < i else self.plans[i]["fin"]
                    if abs(t - c) < self.fondu / 2:
                        a = (t - (c - self.fondu / 2)) / self.fondu      # 0 → 1 à travers la coupe
                        avant, apres = (j, i) if j < i else (i, j)
                        img = Image.blend(self.vue(avant, t), self.vue(apres, t), min(1.0, max(0.0, a)))
                        break
        tx = self.textes
        for m, y0, y1 in tx["voiles"]:
            img.paste((0, 0, 0), (0, y0, self.W, y1), m)
        d = self.duree
        fin_appel = min(2.5, max(1.5, 0.2 * d))
        t_appel = d - fin_appel if tx["appel"] and not couverture else d + 1
        f_appel = min(1.0, max(0.0, (t - t_appel) / 0.25))

        def poser(nom, x, f):
            if x and f > 0:
                img.paste(x[0], (x[1], x[2]), tx["niveaux"][nom][self._niveau(f)])
        poser("marque", tx["marque"], 1.0 if couverture else min(1.0, t / 0.4))
        if tx["bas"]:
            if tx.get("par_photo"):
                k = self.plans[i]["photo"]
                c = tx["bas"][k] if k < len(tx["bas"]) else None
                poser(f"bas{k}", c, (1.0 - f_appel))
            else:
                f = 1.0 if couverture else min(1.0, max(0.0, (t - 0.5) / 0.35)) * (1.0 - f_appel)
                poser("bas0", tx["bas"][0], f)
        poser("appel", tx["appel"], f_appel)
        return img


def _encodeur(W, H, sortie, son, duree, apercu=False):
    """La commande ffmpeg : les images brutes (stdin) + le son → MP4 H.264/AAC aux réglages des réseaux."""
    v = (["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"] if apercu else
         ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "8M", "-bufsize", "16M"])
    mov = [] if "faststart" in COUPE else ["-movflags", "+faststart"]
    return [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-framerate", str(FPS), "-i", "pipe:0",
            "-i", str(son), "-map", "0:v:0", "-map", "1:a:0",
            "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
            *v, "-profile:v", "high", "-level:v", "4.0", "-g", str(2 * FPS), "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
            "-r", str(FPS), *AAC,
            "-t", f"{duree:.3f}", *mov, "-tag:v", "avc1", str(sortie)]


def encoder(montage, sortie, son, progres=None, apercu=False, fils=None):
    """Les images du montage (en fils parallèles, dans l'ordre) → ffmpeg. Rend le nombre d'images."""
    from concurrent.futures import ThreadPoolExecutor
    W, H, d = montage.W, montage.H, montage.duree
    n = int(round(d * FPS))
    journal = Path(sortie).with_suffix(".ffmpeg.log")
    with open(journal, "wb") as err:
        p = subprocess.Popen(_encodeur(W, H, sortie, son, d, apercu), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err)
        try:
            fils = fils or max(1, min(4, (os.cpu_count() or 2)))
            dernier = -1
            with ThreadPoolExecutor(fils) as ex:
                for a in range(0, n, 24):
                    for b in ex.map(lambda f: montage.image(f / FPS).tobytes(), range(a, min(n, a + 24))):
                        p.stdin.write(b)
                    pc = int(100 * min(n, a + 24) / n)
                    if progres and pc // 5 != dernier:
                        dernier = pc // 5
                        progres(pc)
            p.stdin.close()
            code = p.wait(timeout=600)
        except BaseException:
            p.kill()
            p.wait()
            raise
    if code:
        raise RuntimeError("ffmpeg : " + journal.read_text(errors="ignore").strip()[-400:])
    journal.unlink(missing_ok=True)
    return n


# ------------------------------------------------------------------------------------------------ la vérification

def atomes(fichier, n=8):
    """Les premières boîtes d'un MP4 (« ftyp », « moov », « mdat »…) dans l'ordre du fichier."""
    out = []
    with open(fichier, "rb") as h:
        pos = 0
        taille = os.path.getsize(fichier)
        while pos < taille and len(out) < n:
            h.seek(pos)
            t = h.read(16)
            if len(t) < 8:
                break
            s, typ = int.from_bytes(t[:4], "big"), t[4:8].decode("latin-1")
            if s == 1:
                s = int.from_bytes(t[8:16], "big")
            elif s == 0:
                s = taille - pos
            out.append(typ)
            if s < 8:
                break
            pos += s
    return out


def verifier(fichier):
    """Ce que ffprobe lit de la vidéo, et l'ordre des boîtes (faststart : « moov » avant « mdat »)."""
    r = subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(fichier)],
                       capture_output=True, text=True, timeout=60)
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    num, _, den = str(v.get("r_frame_rate", "0/1")).partition("/")
    at = atomes(fichier)
    return {"largeur": v.get("width"), "hauteur": v.get("height"), "codec": v.get("codec_name"), "profil": v.get("profile"),
            "niveau": v.get("level"), "pix_fmt": v.get("pix_fmt"), "couleurs": v.get("color_space"),
            "fps": round(float(num) / float(den or 1), 3) if num else None, "images": int(v.get("nb_frames") or 0),
            "duree": round(float(d.get("format", {}).get("duration") or 0), 3),
            "duree_video": round(float(v.get("duration") or 0), 3), "duree_son": round(float(a.get("duration") or 0), 3),
            "son": a.get("codec_name"), "profil_son": a.get("profile"), "frequence": int(a.get("sample_rate") or 0),
            "canaux": a.get("channels"), "taille": os.path.getsize(fichier), "debit": int(d.get("format", {}).get("bit_rate") or 0),
            "faststart": "moov" in at and "mdat" in at and at.index("moov") < at.index("mdat"), "boites": at}


# ------------------------------------------------------------------------------------------------ la recette et le rendu

def preparer(photos="", collection="", musique="", format="9:16", duree_s=15, rythme="auto", transition="auto", marque="",
             piece="", prix="", appel="", legendes="", titre="", debut_s=None, bpm=0, apercu=False, par="hakim", med=None,
             chansons=None, visuels=None):
    """Une demande vérifiée (la recette) ; rien ne se calcule encore."""
    _verifier_allume()
    med = Path(med or MEDIATHEQUE)
    ph = photos_de(photos, collection, med, visuels)
    mu = musique_de(musique, med, chansons)
    fm = formats_de(format)
    if apercu:
        fm = fm[:1]
    if isinstance(legendes, str):
        legendes = [x for x in legendes.split("\n")] if "\n" in legendes else ([legendes] if legendes.strip() else [])
    legendes = [_texte(x, 120) for x in (legendes or [])][:PHOTOS_MAX]
    try:
        debut = float(debut_s) if debut_s not in (None, "", "auto") and float(debut_s) >= 0 else None
        bpm = float(bpm or 0)
    except (TypeError, ValueError):
        raise Refus("debut_s : des secondes (ou vide : le meilleur passage)")
    if bpm and not 40 <= bpm <= 220:
        raise Refus("bpm : de 40 à 220")
    d = duree_de(duree_s)
    textes = {"marque": _texte(marque, 40), "piece": _texte(piece, 80), "prix": _texte(prix, 30), "appel": _texte(appel, 50),
              "legendes": legendes}
    titre = _texte(titre, 80) or textes["piece"] or textes["marque"] or (collection and nom_collection(collection)) or "Vidéo"
    return {"type": "apercu" if apercu else "video", "titre": titre, "nom": nom_de(titre + ("-apercu" if apercu else "")),
            "photos": ph, "musique": mu, "formats": fm, "duree_s": d, "rythme": rythme_de(rythme),
            "transition": transition_de(transition), "textes": textes, "debut_s": debut, "bpm": bpm, "apercu": bool(apercu),
            "par": par}


def _transition_auto(t, coupes, duree):
    if t != "auto":
        return t
    l = [b - a for a, b in zip([0.0] + coupes, coupes + [duree])]
    l.sort()
    med = l[len(l) // 2] if l else duree
    return "nette" if med < 1.0 else "fondu"


def calage_ms(coupes, temps):
    """L'écart (ms) de chaque coupe, posée sur une image (1/30 s), au temps le plus proche : médiane et maximum."""
    if not coupes or not temps:
        return None
    e = []
    for c in coupes:
        cf = round(c * FPS) / FPS
        e.append(min(abs(cf - t) for t in temps) * 1000)
    e.sort()
    return {"mediane": round(e[len(e) // 2], 1), "max": round(e[-1], 1), "coupes": len(e)}


def rendre(v, dossier, travail, progres=print, med=None):
    """Une recette → les vidéos de chaque format, la couverture, la vignette. Rend (fichiers, mesures)."""
    from PIL import Image
    med = Path(med or MEDIATHEQUE)
    travail = Path(travail)
    travail.mkdir(parents=True, exist_ok=True)
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    d = float(v["duree_s"])
    chemins = [chemin_media(p, med) for p in v["photos"]]
    for c in chemins:
        if not c.is_file():
            raise Refus(f"photo disparue : {c.name}")
    mesures = {}
    progres(f"PROGRESSION 2% écoute de la musique")
    if v.get("musique"):
        src = chemin_media(v["musique"], med)
        if not src.is_file():
            raise Refus(f"musique disparue : {src.name}")
        an = analyse_de(src, med)
        if an["duree"] < DUREE_MIN:
            raise Refus("la musique dure moins de 5 secondes")
        if d > an["duree"]:
            d = round(an["duree"], 2)
            mesures["duree_raccourcie"] = d
        choix = choisir_passage(an, d, v.get("debut_s"))
        pre = min(0.1, choix["debut"])                          # le premier temps arrive après le fondu d'entrée
        debut_son = choix["debut"] - pre
        temps, fort = temps_du_passage(an, debut_son, d)
        mesures.update(bpm=an["bpm"], passage=[round(debut_son, 2), round(debut_son + d, 2)], raison=choix["raison"],
                       refrain=choix["refrain"], analyse_s=an.get("calcul_s"), grille=an.get("mode"))
    else:
        src, debut_son = None, 0.0
        bpm = float(v.get("bpm") or 120.0)
        temps = [i * 60.0 / bpm for i in range(int(d * bpm / 60) + 1)]
        fort = temps[::4]
        mesures.update(bpm=bpm, passage=None, raison="sans musique : une grille de " + f"{bpm:g} BPM")
    coupes, n = plan_coupes(temps, d, len(chemins), v["rythme"], fort, mesures.get("bpm", 0))
    transition = _transition_auto(v["transition"], coupes, d)
    vues = sorted({i % len(chemins) for i in range(len(coupes) + 1)})
    mesures.update(coupes=len(coupes), temps_par_coupe=n, transition=transition, calage_ms=calage_ms(coupes, temps),
                   photos_montrees=len(vues), photos=len(chemins))
    progres(f"PROGRESSION 8% le son ({mesures.get('raison', '')})")
    son = travail / "son.wav"
    mesures["son"] = preparer_son(str(src) if src else None, debut_son, d, son, travail)
    videos, couvertures = [], []
    nfm = len(v["formats"])
    for k, fm in enumerate(v["formats"]):
        W, H = FORMATS[fm]
        if v.get("apercu"):
            W, H = W // 3 // 2 * 2, H // 3 // 2 * 2
        m = Montage(chemins, coupes, d, W, H, transition, v.get("textes"), med)
        sortie = dossier / f"{v['nom']}-{fm.replace(':', 'x')}.mp4"
        base, ampl = 12 + 85 * k / nfm, 85 / nfm

        def pg(pc, fm=fm, base=base, ampl=ampl):
            progres(f"PROGRESSION {int(base + ampl * pc / 100)}% images {fm}")
        t1 = time.time()
        encoder(m, sortie, son, pg, apercu=v.get("apercu"))
        rendu_s = time.time() - t1
        ver = verifier(sortie)
        if k == 0:
            couv = m.image(min(d / 2, max(0.25, (coupes[0] if coupes else d) / 2)), couverture=True)
            cp = dossier / f"{v['nom']}-couverture.jpg"
            couv.save(cp, "JPEG", quality=92)
            vig = couv.copy()
            vig.thumbnail((360, 640), Image.LANCZOS)
            vig.save(dossier / f"{v['nom']}.jpg", "JPEG", quality=80)
            if not v.get("apercu"):
                couvertures.append(cp)
        mesures.setdefault("formats", {})[fm] = {**{x: ver[x] for x in ("largeur", "hauteur", "duree", "fps", "taille", "faststart")},
                                                 "rendu_s": round(rendu_s, 1)}
        videos.append(sortie)
    if v.get("musique") and videos:
        mesures["niveau_final"] = mesure_niveau(videos[0])
    mesures["calcul_s"] = round(time.time() - t0, 1)
    return videos + couvertures, mesures


# ------------------------------------------------------------------------------------------------ la tâche de fond

def _en_cours(dossier):
    vus = []
    for p in sorted(Path(dossier).glob("T-*.json")):
        d = _lire(p, {}) or {}
        if d.get("etat") == "en cours" and (not d.get("superviseur") or _vivant(d["superviseur"])):
            vus.append(d)
    return vus


def _demarrer(args, log):
    with open(log, "ab") as sortie:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=sortie, stderr=subprocess.STDOUT, start_new_session=True,
                             close_fds=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    return p.pid


def galerie(videos=None, apercus=False):
    v = Path(videos or VIDEOS)
    l = [x for x in (_lire(p) for p in v.glob("*.json")) if isinstance(x, dict) and x.get("nom") and x.get("etat") == "prête"
         and (x.get("type") == "apercu") == bool(apercus)]
    return sorted(l, key=lambda x: x.get("fin", 0), reverse=True)


def video_de(ref, videos=None):
    """Une vidéo finie par son nom, son fichier ou son titre (la plus récente de ce titre) ; « dernière » : la dernière."""
    r = str(ref or "").strip()
    l = galerie(videos) + galerie(videos, apercus=True)
    l.sort(key=lambda x: x.get("fin", 0), reverse=True)
    if not l:
        raise Refus("aucune vidéo pour l'instant")
    if _cle(r) in ("", "derniere", "la derniere", "last", "precedente"):
        return l[0]
    base = re.sub(r"(-(9x16|4x5|1x1))?(\.mp4)?$", "", Path(r).name)
    for x in l:
        if base == x["nom"]:
            return x
    cle = _sans_accent(r)
    for x in l:
        if cle and cle == _sans_accent(x.get("titre")):
            return x
    raise Refus(f"vidéo inconnue : « {r} » (mediatheque_voir liste les vidéos)")


def refaire(ref, apercu=False, par="hakim", videos=None, med=None, chansons=None, visuels=None, **changements):
    """La recette d'une vidéo finie, avec des changements (rythme, format, textes, musique, durée, début…) → une demande."""
    _verifier_allume()
    x = video_de(ref, videos)
    r = dict(x.get("recette") or {})
    if not r:
        raise Refus("cette vidéo n'a pas de recette")
    t = dict(r.get("textes") or {})
    for k in ("marque", "piece", "prix", "appel"):
        if changements.get(k) is not None:
            t[k] = _texte(changements[k], 80)
    if changements.get("legendes") is not None:
        lg = changements["legendes"]
        t["legendes"] = [_texte(y, 120) for y in (lg.split("\n") if isinstance(lg, str) else lg) if str(y).strip()][:PHOTOS_MAX] if lg else []
    d = {**r, "textes": t}
    if changements.get("musique"):
        d["musique"] = musique_de(changements["musique"], med, chansons)
        d["debut_s"] = None
    if changements.get("photos") or changements.get("collection"):
        d["photos"] = photos_de(changements.get("photos") or "", changements.get("collection") or "", med, visuels)
    if changements.get("format"):
        d["formats"] = formats_de(changements["format"])
    if changements.get("duree_s"):
        d["duree_s"] = duree_de(changements["duree_s"])
        if changements.get("debut_s") is None:
            d["debut_s"] = None
    if changements.get("rythme"):
        d["rythme"] = rythme_de(changements["rythme"])
    if changements.get("transition"):
        d["transition"] = transition_de(changements["transition"])
    if changements.get("debut_s") is not None and str(changements["debut_s"]).strip() != "":
        d["debut_s"] = None if str(changements["debut_s"]) in ("auto", "-1") or float(changements["debut_s"]) < 0 else float(changements["debut_s"])
    titre = _texte(changements.get("titre"), 80) or x.get("titre") or "Vidéo"
    d.update(type="apercu" if apercu else "video", apercu=bool(apercu), titre=titre, nom=nom_de(titre + ("-apercu" if apercu else "")),
             par=par, refait_de=x["nom"])
    if apercu:
        d["formats"] = d["formats"][:1]
    return d


def lancer(demande, dossier=None, videos=None, demarrer=None):
    """Une demande préparée → une tâche de fond ; rend {tache, …} tout de suite."""
    _verifier_allume()
    dossier, videos = Path(dossier or TACHES), Path(videos or VIDEOS)
    dossier.mkdir(parents=True, exist_ok=True)
    videos.mkdir(parents=True, exist_ok=True)
    verrou = open(dossier / ".verrou", "w")                  # le même verrou que taches.py, chant.py et l'atelier visuel
    fcntl.flock(verrou, fcntl.LOCK_EX)
    try:
        en_cours = _en_cours(dossier)
        if len([e for e in en_cours if e.get("video")]) >= MAX_EN_FILE:
            raise Refus(f"déjà {MAX_EN_FILE} vidéos en file : attends qu'une finisse")
        if len(en_cours) >= MAX_TACHES:
            raise Refus(f"déjà {len(en_cours)} tâches de fond en cours : attends qu'une finisse")
        tid = f"T-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        quoi = (f"{'aperçu' if demande.get('apercu') else 'vidéo'} « {demande['titre'][:60]} » ({' et '.join(demande['formats'])}, "
                f"{demande['duree_s']:g} s, {len(demande['photos'])} photo{'s' if len(demande['photos']) > 1 else ''})")
        d = {"id": tid, "commande": f"atelier vidéo : {quoi}", "debut": time.time(), "etat": "en cours", "delai_s": DELAI_S,
             "atelier": str(ATELIER), "video": demande}
        _ecrire(dossier / f"{tid}.json", d)
        _ecrire(videos / f"{demande['nom']}.json", {"nom": demande["nom"], "titre": demande["titre"], "type": demande["type"],
                                                    "etat": "en cours", "tache": tid, "debut": d["debut"], "par": demande.get("par"),
                                                    "recette": demande})
        args = [NICE, "-n", "10", str(python_video()), "-B", str(Path(__file__).resolve()), "generer", tid, str(dossier)]
        pid = (demarrer or _demarrer)(args, dossier / f"{tid}.log")
        d.update(pid=pid, superviseur=pid)
        _ecrire(dossier / f"{tid}.json", d)
        return {"tache": tid, **demande}
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def telephone_dossier():
    if TELEPHONE:
        return Path(TELEPHONE)
    v = os.environ.get("JARVIS_TELEPHONE_VIDEOS")
    if v:
        return Path(v)
    try:
        sys.path.insert(0, str(ICI))
        import telephone
        return telephone.documents() / "Hakim" / "Videos"
    except Exception:                                        # noqa: BLE001
        return JARVIS / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim" / "Videos"


def deposer_au_telephone(fichier, titre, dossier=None, journal=None):
    """Une copie lisible (« Manteau Hiver (TikTok).mp4 ») dans le dossier du téléphone, jamais par-dessus un autre fichier
    (le même contenu déjà là est repris), et la ligne « ajout » du journal des écritures du téléphone."""
    f = Path(fichier)
    d = Path(dossier or telephone_dossier())
    d.mkdir(parents=True, exist_ok=True)
    souche = nom_fichier(titre or f.stem, "")[:70].strip() or "Video"
    taille = f.stat().st_size
    for i in range(1, 50):
        cible = d / (f"{souche}{f.suffix}" if i == 1 else f"{souche} {i}{f.suffix}")
        if cible.exists():
            if cible.stat().st_size == taille:
                return cible
            continue
        tmp = d / f".{cible.name}.{os.getpid()}.tmp"
        shutil.copyfile(f, tmp)
        try:
            os.link(tmp, cible)
        except FileExistsError:
            continue
        finally:
            tmp.unlink(missing_ok=True)
        try:
            j = Path(journal or JARVIS / "telephone-ecritures.jsonl")
            with open(j, "a", encoding="utf-8") as h:
                h.write(json.dumps({"ts": time.time(), "action": "ajout", "chemin": str(cible), "taille": taille, "sauvegarde": None,
                                    "note": "l'atelier vidéo"}, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return cible
    return None


def finir(tid, dossier=None, videos=None, atelier=None, telephone=None, fichiers=None, erreur=None, raison=None, mesures=None):
    """L'état final de la tâche et de la fiche ; les copies (atelier, téléphone). Rend la ligne de fin du journal."""
    dossier, videos = Path(dossier or TACHES), Path(videos or VIDEOS)
    atelier = Path(atelier or ATELIER)
    d = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))
    v = d["video"]
    fiche_p = videos / f"{v['nom']}.json"
    fiche = _lire(fiche_p) or {"nom": v["nom"], "titre": v["titre"], "type": v["type"], "recette": v}
    fin = time.time()
    fichiers = [Path(f) for f in (fichiers or []) if f and Path(f).is_file()]
    apercu = bool(v.get("apercu"))
    if erreur or raison or not fichiers:
        ligne = f"VIDÉO RATÉE : {raison or erreur or 'aucun fichier produit'}"
        d.update(etat="arrêtée" if raison else "finie", raison=raison, code=0 if raison else 1)
        fiche.update(etat="ratée", erreur=str(raison or erreur)[:500])
    else:
        rels, tel = [], []
        if not apercu:
            for f in fichiers:
                atelier.mkdir(parents=True, exist_ok=True)
                c = atelier / f.name
                if not (c.exists() and c.stat().st_size == f.stat().st_size):
                    shutil.copyfile(f, atelier / f".{f.name}.tmp")
                    (atelier / f".{f.name}.tmp").replace(c)
                rels.append(f"atelier/videos/{c.name}")
            for f in fichiers:
                fm = re.search(r"-(9x16|4x5|1x1)\.mp4$", f.name)
                quoi = (f" ({NOMS_FORMAT[fm.group(1).replace('x', ':')].split(' · ')[0]})" if fm else
                        " (couverture)" if f.name.endswith("-couverture.jpg") else "")
                try:
                    c = deposer_au_telephone(f, f"{v['titre']}{quoi}", telephone)
                    if c:
                        tel.append(str(c))
                except OSError as e:
                    fiche["telephone_erreur"] = str(e)[:200]
        fiche.update(etat="prête", fichiers=[str(f) for f in fichiers], atelier=rels, telephone=tel,
                     taille=sum(f.stat().st_size for f in fichiers), mesures=mesures or {},
                     couverture=next((str(f) for f in fichiers if f.name.endswith("-couverture.jpg")), None),
                     vignette=str(videos / f"{v['nom']}.jpg") if (videos / f"{v['nom']}.jpg").is_file() else None)
        m = mesures or {}
        pas = (f"{m.get('bpm', 0):.0f} BPM, coupes sur les temps (écart médian {m['calage_ms']['mediane']:.0f} ms)"
               if m.get("calage_ms") else "")
        son = m.get("son") or {}
        niv = f", son à {son['lufs']:.1f} LUFS" if son.get("lufs") is not None else ""
        if apercu:
            ligne = f"APERÇU PRÊT : « {v['titre']} » ({m.get('calcul_s', 0):.0f} s de calcul) : {pas}{niv}."
        else:
            joindre = " ; ".join(f'fichier_joindre("{r}", "{v["titre"]}")' for r, f in zip(rels, fichiers)
                                 if f.suffix == ".mp4" and f.stat().st_size <= 25 * 1024 * 1024)
            passage = m.get("passage")
            ligne = (f"VIDÉO PRÊTE : « {v['titre']} » ({' et '.join(v['formats'])}, {v['duree_s']:g} s, calculée en "
                     f"{m.get('calcul_s', 0):.0f} s) : {pas}{niv}"
                     + (f", passage {passage[0]:.1f}–{passage[1]:.1f} s ({m.get('raison')})" if passage else "")
                     + f". Copiée sur le téléphone ({' › '.join(Path(telephone or telephone_dossier()).parts[-2:])}) avec sa "
                     "couverture, à publier à la main. ")
            if v.get("par") != "papa" and joindre:
                ligne += f"Pour l'envoyer : {joindre}"
        d.update(etat="finie", raison=None, code=0, fichier=(rels[0] if rels else str(fichiers[0])))
        if apercu:
            _nettoyer_apercus(videos)
    d.update(fin=fin, duree_s=round(fin - d["debut"], 1))
    fiche["fin"] = fin
    _ecrire(fiche_p, fiche)
    _ecrire(dossier / f"{tid}.json", d)
    return ligne


def _nettoyer_apercus(videos):
    """Les aperçus : les GARDE_APERCUS derniers seulement."""
    l = sorted((x for x in (_lire(p) for p in Path(videos).glob("*.json")) if isinstance(x, dict) and x.get("type") == "apercu"
                and x.get("etat") != "en cours"), key=lambda x: x.get("fin", 0), reverse=True)
    for x in l[GARDE_APERCUS:]:
        for f in Path(videos).glob(f"{x['nom']}*"):
            f.unlink(missing_ok=True)


def _veiller(tid, dossier, debut, videos):
    while True:
        time.sleep(1)
        raison = ("arrêtée à la demande" if (dossier / f"{tid}.stop").exists()
                  else f"trop longue (plus de {DELAI_S // 60} min)" if time.time() - debut > DELAI_S else None)
        if raison:
            print(finir(tid, dossier, videos, raison=raison), flush=True)
            try:
                (dossier / f"{tid}.stop").unlink()
            except OSError:
                pass
            os._exit(3)


def generer(tid, dossier=None, videos=None):
    dossier, videos = Path(dossier or TACHES), Path(videos or VIDEOS)
    debut = time.time()
    threading.Thread(target=_veiller, args=(tid, dossier, debut, videos), daemon=True).start()
    v = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))["video"]
    print(f"Atelier vidéo : « {v['titre']} »", flush=True)
    sys.path.insert(0, str(ICI))
    import atelier_visuel
    verrou = atelier_visuel.attendre_son_tour(tid, dossier)
    travail = videos / f".{v['nom']}"
    try:
        fichiers, mesures = rendre(v, videos, travail, progres=lambda s: print(s, flush=True))
        print(finir(tid, dossier, videos, fichiers=fichiers, mesures=mesures), flush=True)
    except Exception as e:                                       # noqa: BLE001 — toute panne finit la tâche proprement
        print(f"{type(e).__name__}: {e}", flush=True)
        print(finir(tid, dossier, videos, erreur=f"{type(e).__name__}: {str(e)[:300]}"), flush=True)
    finally:
        shutil.rmtree(travail, ignore_errors=True)
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def creer(q, par="papa"):
    """Le cockpit : une demande JSON → la tâche lancée (une vidéo, un aperçu, ou « refaire »)."""
    if q.get("refaire"):
        ch = {k: q.get(k) for k in ("format", "duree_s", "rythme", "transition", "marque", "piece", "prix", "appel", "legendes",
                                    "musique", "titre", "debut_s") if q.get(k) not in (None, "")}
        return lancer(refaire(q["refaire"], apercu=bool(q.get("apercu")), par=par, **ch))
    return lancer(preparer(q.get("photos") or "", q.get("collection") or "", q.get("musique") or "", q.get("format") or "9:16",
                           q.get("duree_s") or 15, q.get("rythme") or "auto", q.get("transition") or "auto", q.get("marque") or "",
                           q.get("piece") or "", q.get("prix") or "", q.get("appel") or "", q.get("legendes") or "",
                           q.get("titre") or "", q.get("debut_s"), q.get("bpm") or 0, bool(q.get("apercu")), par=par))


def _cli_json(f):
    try:
        r = f(json.loads(sys.stdin.read() or "{}"))
        print(json.dumps({"ok": True, **r}, ensure_ascii=False))
    except Refus as e:
        print(json.dumps({"ok": False, "erreur": str(e)}, ensure_ascii=False))
    except Exception as e:                                       # noqa: BLE001
        print(json.dumps({"ok": False, "erreur": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "generer":
        generer(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) >= 2 and sys.argv[1] == "lancer":
        _cli_json(creer)
    elif len(sys.argv) >= 2 and sys.argv[1] == "importer":
        # {chemin, collection, nom?, deplacer?} : un envoi du cockpit (déposé dans .depot) ou un fichier d'Ahmed
        def _imp(q):
            src = Path(q.get("chemin") or "")
            depot = MEDIATHEQUE / ".depot"
            deplacer = bool(q.get("deplacer")) and _dans(depot, src)
            if not deplacer and not (_dans(FICHIERS, src)):
                raise Refus("seulement un envoi du cockpit ou un fichier reçu (fichiers/…)")
            return importer(src, q.get("collection") or "Divers", q.get("nom") or None, deplacer=deplacer)
        _cli_json(_imp)
    elif len(sys.argv) >= 2 and sys.argv[1] == "analyser":
        print(json.dumps({k: v for k, v in analyser(sys.argv[2]).items() if k not in ("chroma",)}, ensure_ascii=False)[:4000])
    else:
        print("usage : atelier_video.py generer <tâche> [dossier] | lancer | importer | analyser <fichier>", file=sys.stderr)
        sys.exit(2)
