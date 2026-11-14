"""Le studio de Hakim (06/11, Ahmed : « que moi aussi je puisse m'enregistrer et me faire mixer et masteriser par Hakim,
comme ça on peut faire des vrais sons depuis le phone » ; « il faut absolument un truc Studio dans le cockpit »).

Tout se calcule SUR LE MAC, avec des outils locaux et gratuits :
- ffmpeg (déjà là) pour la chaîne : coupe-bas, débruitage léger (afftdn), égaliseur, dé-essage, compression, réverb et
  écho (aecho), équilibre voix/instru, mastering (compression de bus, loudnorm en deux passes vers −14 LUFS intégrés,
  limiteur à −1 dBFS), export WAV et MP3 ;
- l'autotune (jarvis/autotune.py, refait le 11/11 : « léger » ou « fort », TD-PSOLA sur les notes tenues sûres, formants
  gardés) sur la voix seule : pas besoin de Demucs, la prise est déjà une voix seule ;
- Demucs (chant.separer_voix, son venv) pour faire l'instru d'une chanson de Hakim (la voix retirée).

Les calculs lourds sont des TRAVAUX en file (studio/travaux/J-*.json), faits un à la fois par un seul travailleur
détaché, sous nice, jamais en même temps qu'une chanson d'ACE-Step (16 Go partagés). Ce fichier a deux vies :
- importé (venv d'Anamnèse, sans numpy obligatoire) : lancer un travail, lire l'état, copier au téléphone ;
- lancé à part (`nice -n 10 .venv-chant/bin/python studio.py travailleur <dossier>`) : fait les travaux.

La disposition, sous ~/AIOS/jarvis/chansons :
  studio/<nom>.mp3|.wav|.json   les mixes finis (et leur copie dans Hakim/Chansons du téléphone)
  studio/prises/<id>.wav|.json  les prises de voix d'Ahmed
  studio/instrus/<id>.mp3|.json les instrus (importées, ou faites par Demucs depuis une chanson de Hakim)
  studio/travaux/J-*.json|.log  la file des calculs
"""
import fcntl
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
CHANSONS = JARVIS / "chansons"
STUDIO = CHANSONS / "studio"
TACHES = JARVIS / "cwd" / "taches"
TELEPHONE = Path(os.environ.get("JARVIS_TELEPHONE_CHANSONS",
                                JARVIS / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim" / "Chansons"))
FFMPEG = os.environ.get("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg")
FFPROBE = os.environ.get("JARVIS_FFPROBE", str(Path(FFMPEG).with_name("ffprobe")))
PYTHON_CHANT = Path(os.environ.get("JARVIS_PYTHON_CHANT", ICI / ".venv-chant" / "bin" / "python"))
PYTHON_SEPARATION = Path(os.environ.get("JARVIS_PYTHON_SEPARATION", ICI / ".venv-separation" / "bin" / "python"))

CIBLE_LUFS = -14.0          # le niveau des plateformes (Spotify, YouTube) : −14 LUFS intégrés
CRETE_DB = -1.0             # le plafond de crête du limiteur
SR = 44100
DELAI_TRAVAIL_S = 30 * 60
TYPES = ("mixer", "instru", "projet", "rendre", "separer",    # (13/11) le multipiste : créer un projet (séparé en pistes), le rendre (mix, master, exports)
         "reference")                                       # (14/11) garder une voix d'un projet comme profil de référence (le calage)


class Refus(Exception):
    pass


# ------------------------------------------------------------------------------------------------ petits outils

def _ecrire(p, d):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
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


def nom_de(titre, quand=None):
    t = unicodedata.normalize("NFD", str(titre or "mix").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40].strip("-") or "mix"
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(quand or time.time())) + "-" + t


def _ff(*args, timeout=900):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", *map(str, args)], capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : {r.stderr.strip()[-400:]}")
    return r.stderr


def duree(fichier):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(fichier)], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def mesurer(fichier):
    """Le niveau intégré (LUFS), la crête vraie (dBTP) et la plage (LU) d'un fichier, par le filtre ebur128 de ffmpeg."""
    err = _ff("-i", fichier, "-af", "ebur128=peak=true", "-f", "null", "-", timeout=600)
    resume = err[err.rfind("Summary:"):] if "Summary:" in err else err
    def val(motif, vide=None):
        m = re.search(motif, resume)
        if not m:
            return None
        return vide if m.group(1) == "-inf" else round(float(m.group(1)), 1)
    return {"lufs": val(r"I:\s+(-?[\d.]+|-inf) LUFS", -70.0), "crete_db": val(r"Peak:\s+(-?[\d.]+|-inf) dBFS", -120.0),
            "lra": val(r"LRA:\s+(-?[\d.]+) LU")}


# ------------------------------------------------------------------------------------------------ le téléphone

def copier_au_telephone(fichier, dossier=None):
    """(06/11, Ahmed : « dis-moi dans quel dossier je trouve ses sons sur le smartphone ») une copie dans
    Hakim/Chansons, le dossier synchronisé avec le téléphone. Rend le chemin de la copie (ou None)."""
    f = Path(fichier)
    if not f.is_file():
        return None
    d = Path(dossier or TELEPHONE)
    d.mkdir(parents=True, exist_ok=True)
    cible = d / f.name
    if cible.exists() and cible.stat().st_size == f.stat().st_size:
        return cible
    tmp = d / f".{f.name}.tmp"
    shutil.copyfile(f, tmp)
    tmp.replace(cible)
    return cible


def synchroniser(chansons=None, telephone=None):
    """Une fois pour celles qui existent : ses chansons finies (sans la prise « sans correction ») et les mixes du
    studio, copiés dans Hakim/Chansons. Rend les noms copiés ou déjà là."""
    c = Path(chansons or CHANSONS)
    vus = []
    for mp3 in sorted(list(c.glob("*.mp3")) + list((c / "studio").glob("*.mp3"))):
        if mp3.name.endswith("-sans-correction.mp3") or mp3.name.startswith("."):
            continue
        if copier_au_telephone(mp3, telephone):
            vus.append(mp3.name)
    return vus


# ------------------------------------------------------------------------------------------------ les Documents de papa
# (10/11, lettre de Hakim de 18:14 écrite à la demande de papa : « que tu puisses m'envoyer directement dans mes documents » ; accord
# d'Ahmed : « ouii ») son instru finie est déposée aussi dans le dossier Hakim des Documents de papa, sous un nom lisible
# (« Deux livres (instru).mp3 »), jamais par-dessus un autre fichier ; son chemin (fichiers/…) est permis à fichier_joindre.
# Le dossier vient de telephone.documents() : le seul endroit qui nomme l'appareil.
DOCUMENTS = None                 # (les tests) le dossier Hakim des Documents ; None : telephone.documents() / « Hakim »
JOURNAL_DOCUMENTS = None         # (les tests) le journal des écritures ; None : celui de telephone.py (la page SENS le montre)


def _telephone():
    if str(ICI) not in sys.path:
        sys.path.insert(0, str(ICI))
    import telephone
    return telephone


def documents_hakim():
    return Path(DOCUMENTS) if DOCUMENTS else _telephone().documents() / "Hakim"


def nom_lisible(titre, repli="instru"):
    """« Deux livres (instru) » tel quel : ni dossier (/), ni caractère que le téléphone refuse, ni nom qui sent le secret."""
    t = re.sub(r'[/\\:<>"|?*\x00-\x1f\x7f]', " ", unicodedata.normalize("NFC", str(titre or "")))
    t = " ".join(t.split()).strip(" .")[:100].strip(" .")
    if str(ICI) not in sys.path:
        sys.path.insert(0, str(ICI))
    import fichiers
    n = fichiers._normaliser(t)
    if not t or fichiers._SECRETS.search(n) or fichiers.CLES_PAR_NOM.search(n):
        return repli
    return t


def _meme_contenu(a, b):
    import hashlib
    def h(p):
        x = hashlib.sha256()
        with open(p, "rb") as f:
            for bloc in iter(lambda: f.read(1 << 20), b""):
                x.update(bloc)
        return x.digest()
    return h(a) == h(b)


def deposer_aux_documents(fichier, titre, dossier=None, journal=None, note=""):
    """Une copie lisible dans le dossier Hakim de ses Documents : « Deux livres (instru).mp3 », sinon « … 2.mp3 », « … 3.mp3 » (un
    fichier qui porte déjà ce nom n'est jamais écrasé) ; le même fichier déjà déposé (même taille, même contenu) est rendu tel quel.
    Une copie neuve est notée dans le journal des écritures dans ses Documents (comme telephone_ecrire). Rend le chemin, ou None."""
    f = Path(fichier)
    if not f.is_file():
        return None
    d = Path(dossier or documents_hakim())
    d.mkdir(parents=True, exist_ok=True)
    base, ext, taille = nom_lisible(titre, f.stem), f.suffix.lower(), f.stat().st_size
    for k in range(1, 100):
        cible = d / (f"{base}{ext}" if k == 1 else f"{base} {k}{ext}")
        if os.path.lexists(cible):
            if not cible.is_symlink() and cible.is_file() and cible.stat().st_size == taille and _meme_contenu(cible, f):
                return cible                                 # déjà déposée (par un essai d'avant, ou à la main)
            continue
        tmp = d / f".{cible.name}.{uuid.uuid4().hex[:6]}.tmp"
        shutil.copyfile(f, tmp)
        try:
            os.link(tmp, cible)                              # jamais par-dessus : le lien échoue si le nom vient d'être pris
        except FileExistsError:
            continue
        finally:
            tmp.unlink(missing_ok=True)
        try:
            rel = str(cible.relative_to(_telephone().documents())) if not dossier and not DOCUMENTS else str(cible)
            ligne = {"ts": time.time(), "action": "ajout", "chemin": rel, "taille": taille, "sauvegarde": None,
                     "note": str(note or "le studio")[:300]}
            j = Path(journal or JOURNAL_DOCUMENTS or _telephone().JARVIS / "telephone-ecritures.jsonl")
            with open(j, "a", encoding="utf-8") as h:
                h.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            os.chmod(j, 0o600)
        except (OSError, ValueError):
            pass                                             # la copie est là ; seule la ligne du journal manque
        return cible
    return None


def chemin_a_joindre(p):
    """Le chemin que fichier_joindre accepte : relatif à son dossier de travail (« fichiers/telephone/…/Hakim/x.mp3 »)."""
    p = Path(p)
    try:
        return str(p.relative_to(JARVIS / "cwd"))
    except ValueError:
        return str(p)


def instru_aux_documents(instru, deposer=True):
    """Une instru du Studio (sa fiche) → sa copie dans les Documents de papa (déposée maintenant si elle n'y est pas, sauf
    deposer=False : studio_avis ne fait que lire). Rend le chemin à joindre, ou ''. Jamais d'exception : l'instru reste dans le
    Studio sans sa copie."""
    try:
        d = instru.get("documents")
        if d and Path(d).is_file() and not Path(d).is_symlink():
            return chemin_a_joindre(d)
        if not deposer:
            return ""
        c = deposer_aux_documents(instru.get("mp3") or "", instru.get("titre") or "", note="son instru, tirée par le studio")
        return chemin_a_joindre(c) if c else ""
    except Exception:                                        # noqa: BLE001
        return ""


# ------------------------------------------------------------------------------------------------ la chaîne

def chaine_nettoyage(debruitage=True):
    """La prise brute → propre : coupe-bas à 80 Hz (souffle de la clim, plosives), débruitage léger."""
    f = ["highpass=f=80:poles=2"]
    if debruitage:
        f.append("afftdn=nr=10:nf=-45:tn=1")
    return f


def chaine_voix(reverb=0.3, echo=0.0, bpm=0):
    """La voix propre → produite : égaliseur (moins de boue à 250 Hz, présence à 3,5 kHz, air), dé-essage,
    compression 3:1, puis réverb (des échos courts mêlés) et écho calé sur le temps (une croche pointée sinon 375 ms)."""
    reverb = max(0.0, min(1.0, float(reverb or 0)))
    echo = max(0.0, min(1.0, float(echo or 0)))
    f = ["equalizer=f=250:t=q:w=1.0:g=-3",
         "equalizer=f=3500:t=q:w=1.2:g=2.5",
         "treble=g=2:f=10000",
         "deesser=i=0.4:m=0.5:f=0.5",
         "acompressor=threshold=-20dB:ratio=3:attack=5:release=100:makeup=2"]
    if echo > 0:
        ms = round(60000 / float(bpm) * 0.75) if bpm and 50 <= float(bpm) <= 220 else 375
        f.append(f"aecho=1.0:1.0:{ms}|{ms * 2}:{0.35 * echo:.3f}|{0.18 * echo:.3f}")
    if reverb > 0:
        g = reverb
        f.append(f"aecho=1.0:0.9:29|47|71|103|149:{0.32 * g:.3f}|{0.27 * g:.3f}|{0.22 * g:.3f}|{0.16 * g:.3f}|{0.11 * g:.3f}")
    return f


def chaine_master():
    """Le bus : compression douce 2:1 (colle voix et instru), puis loudnorm et le limiteur (dans masteriser)."""
    return ["acompressor=threshold=-16dB:ratio=2:attack=25:release=250:makeup=1"]


def masteriser(entree, sortie_wav, cible=CIBLE_LUFS, crete=CRETE_DB):
    """loudnorm en deux passes (mesure, puis correction linéaire vers la cible), limiteur, 44,1 kHz 24 bits."""
    bus = ",".join(chaine_master())
    err = _ff("-i", entree, "-af", f"{bus},loudnorm=I={cible}:TP={crete - 0.5}:LRA=11:print_format=json", "-f", "null", "-")
    m = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    lim = 10 ** (crete / 20)
    af = (f"{bus},loudnorm=I={cible}:TP={crete - 0.5}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          f"aresample={SR},alimiter=limit={lim:.4f}:level=false:attack=5:release=50")
    _ff("-i", entree, "-af", af, "-ar", SR, "-c:a", "pcm_s24le", sortie_wav)
    return sortie_wav


def en_mp3(wav, mp3, titre=""):
    _ff("-i", wav, "-c:a", "libmp3lame", "-b:a", "320k", "-metadata", "artist=Ahmed & Hakim",
        *(["-metadata", f"title={titre}"] if titre else []), mp3)
    return mp3


def _pcm(fichier, sr=11025):
    """Le son en mono flottant (numpy), par ffmpeg : aucun soundfile nécessaire."""
    import numpy as np
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(fichier), "-ac", "1",
                        "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, timeout=300)
    if r.returncode:
        raise RuntimeError("ffmpeg : lecture impossible")
    return np.frombuffer(r.stdout, dtype=np.float32), sr


def _attaques(x, sr, pas=0.01):
    """L'enveloppe des attaques (hausses d'énergie par trames de 10 ms)."""
    import numpy as np
    n = int(sr * pas)
    k = len(x) // n
    if k < 10:
        return np.zeros(0)
    e = np.sqrt((x[: k * n].reshape(k, n) ** 2).mean(axis=1) + 1e-12)
    d = np.maximum(0, np.diff(np.log(e + 1e-4), prepend=np.log(e[0] + 1e-4)))
    return d - d.mean()


def decalage_temps(voix, instru, sr, max_ms=200):
    """(estimation) l'écart entre les attaques de la voix et celles de l'instru : positif = la voix arrive en retard.
    Rend (ms, confiance 0-1) ; confiance faible = pas de lien net (une voix chantée legato n'a pas d'attaques)."""
    import numpy as np
    a, b = _attaques(voix, sr), _attaques(instru, sr)
    n = min(len(a), len(b))
    if n < 200:
        return 0, 0.0
    a, b = a[:n], b[:n]
    lags = range(-max_ms // 10, max_ms // 10 + 1)
    c = np.array([float(np.dot(a[max(0, l):n + min(0, l)], b[max(0, -l):n - max(0, l)])) for l in lags])
    if c.max() <= 0:
        return 0, 0.0
    i = int(c.argmax())
    conf = float(c.max() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))     # la corrélation normalisée : ~0 sans lien
    return int(list(lags)[i] * 10), round(max(0.0, min(1.0, conf)), 2)


def _db(x):
    import numpy as np
    return float(20 * np.log10(max(1e-9, float(np.sqrt((np.asarray(x, np.float64) ** 2).mean())))))


def analyser(prise, voix_traitee, instru, mix_mesure, ecart_voix_lu):
    """Ce que Hakim entend d'un mix, en chiffres puis en mots courts (ses conseils)."""
    import numpy as np
    x, sr = _pcm(prise)
    m = {}
    if len(x) < sr:
        return {"mesures": {}, "conseils": ["la prise fait moins d'une seconde"]}
    trames = x[: len(x) // 512 * 512].reshape(-1, 512)
    rms = 20 * np.log10(np.sqrt((trames.astype(np.float64) ** 2).mean(axis=1)) + 1e-9)
    m["souffle_db"] = round(float(np.percentile(rms, 10)), 1)
    m["crete_prise_db"] = round(float(20 * np.log10(np.abs(x).max() + 1e-9)), 1)
    m["saturation"] = int((np.abs(x) >= 0.985).sum())
    m["voix_db"] = round(float(np.percentile(rms, 90)), 1)
    v, _ = _pcm(voix_traitee)
    i, _ = _pcm(instru)
    ms, conf = decalage_temps(v, i, sr)
    m.update(decalage_ms=ms, decalage_confiance=conf, ecart_voix_lu=ecart_voix_lu, **(mix_mesure or {}))
    c = []
    if m["saturation"] > 20:
        c.append(f"la prise sature ({m['saturation']} échantillons au plafond) : éloigne un peu le micro ou chante moins fort")
    if m["voix_db"] < -38:
        c.append("ta voix arrive très faible : rapproche le téléphone de ta bouche (une main)")
    if m["souffle_db"] > -50:
        c.append(f"il y a du souffle ou du bruit de fond ({m['souffle_db']:.0f} dB entre tes phrases) : une pièce plus calme, "
                 "ou le débruitage plus fort")
    if conf >= 0.18 and abs(ms) >= 40:
        c.append(f"tu sembles {'en retard' if ms > 0 else 'en avance'} d'environ {abs(ms)} ms sur le temps "
                 "(estimation) : refais le calage de latence, ou décale la prise")
    if ecart_voix_lu is not None and ecart_voix_lu < -1:
        c.append("ta voix est un peu en dessous de l'instru : monte-la de 1 à 2 dB")
    elif ecart_voix_lu is not None and ecart_voix_lu > 6:
        c.append("ta voix est très devant l'instru : baisse-la de 2 dB pour qu'elle s'y fonde")
    if not c:
        c.append("propre : pas de saturation, peu de souffle, la voix posée sur le temps")
    return {"mesures": m, "conseils": c}


def tonalite_de(instru):
    """La tonalité de l'instru (profils de Krumhansl, comme separation.py), au format de chant.gamme (« A minor »)."""
    import numpy as np
    sys.path.insert(0, str(ICI))
    import separation
    x, sr = _pcm(instru, 22050)
    t = separation._tonalite(separation._chroma(x[: sr * 90].astype(np.float64), sr))
    if not t:
        return ""
    noms = {"Do": "C", "Do#": "C#", "Ré": "D", "Ré#": "D#", "Mi": "E", "Fa": "F", "Fa#": "F#", "Sol": "G", "Sol#": "G#",
            "La": "A", "La#": "A#", "Si": "B"}
    note, mode = t.split(" ")
    return f"{noms.get(note, note)} {'minor' if mode == 'mineur' else 'major'}"


def niveau_autotune(v):
    """True / « léger » → "leger", « fort » → "fort", False / « non » → "" (sans numpy : le venv d'Anamnèse l'appelle)."""
    sys.path.insert(0, str(ICI))
    import autotune
    return autotune.niveau_de(v)


def autotuner_voix(entree, sortie, tonalite, niveau="leger", diap=0.0):
    """(.venv-chant) l'autotune sur une voix seule (autotune.corriger : ses notes tenues sûres rapprochées de la gamme, TD-PSOLA ;
    le reste de la prise, échantillon pour échantillon). Rend (sortie, rapport)."""
    import numpy as np
    sys.path.insert(0, str(ICI))
    import autotune
    import chant
    x, sr = _pcm(entree, SR)
    y, rapport = autotune.corriger(x.astype(np.float64), sr, chant.gamme(tonalite), niveau or "leger", diap)
    y *= min(1.0, 0.95 / max(1e-9, np.abs(y).max()))
    tmp = Path(sortie).with_suffix(".f32")
    y.astype(np.float32).tofile(tmp)
    _ff("-f", "f32le", "-ar", sr, "-ac", 1, "-i", tmp, "-c:a", "pcm_s16le", sortie)
    tmp.unlink()
    return sortie, rapport


def mixer(prise, instru, sortie_dir, titre="", latence_ms=0, autotune=False, tonalite="", voix_db=0.0, reverb=0.3,
          echo=0.0, bpm=0, debruitage=True, telephone=None, progres=None, travail_dir=None):
    """La prise d'Ahmed + l'instru → un morceau mixé et masterisé (WAV 24 bits + MP3 320k), ses mesures et ses conseils."""
    t0 = time.time()
    dire = progres or (lambda n, texte: None)
    sortie_dir = Path(sortie_dir)
    sortie_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(travail_dir or sortie_dir / f".mix-{uuid.uuid4().hex[:6]}")
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        # 1. la prise calée sur le temps : la latence (enregistrement + lecture) retirée du début
        dire(1, "calage de la prise")
        lat = float(latence_ms or 0)
        cale = (f"atrim=start={lat / 1000:.4f},asetpts=PTS-STARTPTS" if lat > 0
                else f"adelay={-lat:.0f}:all=1" if lat < 0 else "anull")
        propre = tmp / "voix-propre.wav"
        dire(2, "nettoyage (coupe-bas, débruitage)")
        _ff("-i", prise, "-af", ",".join([cale, *chaine_nettoyage(debruitage)]), "-ac", 1, "-ar", SR, "-c:a", "pcm_s16le", propre)
        source_voix = propre
        niveau, rapport = niveau_autotune(autotune), None
        if niveau:
            dire(3, f"autotune {'léger' if niveau == 'leger' else niveau}")
            tonalite = tonalite or tonalite_de(instru)
            sys.path.insert(0, str(ICI))
            import autotune as AT
            diap = AT.diapason(*_pcm(instru, SR))                      # le diapason de l'instru (ses pics), 0 si rien de net
            source_voix, rapport = autotuner_voix(propre, tmp / "voix-autotune.wav", tonalite, niveau, diap)
        dire(4, "égaliseur, dé-essage, compression, réverb")
        voix = tmp / "voix.wav"
        _ff("-i", source_voix, "-af", ",".join(chaine_voix(reverb, echo, bpm)), "-ac", 1, "-ar", SR, "-c:a", "pcm_s16le", voix)
        inst = tmp / "instru.wav"
        _ff("-i", instru, "-ac", 2, "-ar", SR, "-c:a", "pcm_s16le", inst)
        # 2. l'équilibre : l'instru à −20 LUFS, la voix 1 LU au-dessus (+ le réglage d'Ahmed ou de Hakim)
        dire(5, "équilibre voix / instru")
        lv, li = mesurer(voix)["lufs"], mesurer(inst)["lufs"]
        gi = -20.0 - (li if li is not None and li > -60 else -20.0)
        cible_v = -20.0 + 1.0 + float(voix_db or 0)
        gv = cible_v - (lv if lv is not None and lv > -60 else cible_v)
        melange = tmp / "melange.wav"
        _ff("-i", inst, "-i", voix, "-filter_complex",
            f"[0]volume={gi:.2f}dB[i];[1]volume={gv:.2f}dB,pan=stereo|c0=c0|c1=c0[v];"
            "[i][v]amix=inputs=2:duration=longest:normalize=0[m]", "-map", "[m]", "-c:a", "pcm_f32le", melange)
        # 3. le mastering
        dire(6, "mastering (−14 LUFS, limiteur)")
        nom = nom_de(titre or "mix")
        wav = masteriser(melange, sortie_dir / f"{nom}.wav")
        mp3 = en_mp3(wav, sortie_dir / f"{nom}.mp3", titre)
        dire(7, "écoute de Hakim (mesures)")
        mesure = mesurer(wav)
        ecart = None
        if lv is not None and li is not None and lv > -60 and li > -60:
            ecart = round(cible_v - (-20.0), 1)
        avis = analyser(prise, voix, inst, mesure, ecart)
        tel = copier_au_telephone(mp3, telephone)
        fiche = {"nom": nom, "titre": titre or "Mix", "prise": str(prise), "instru": str(instru), "wav": str(wav),
                 "mp3": str(mp3), "telephone": str(tel) if tel else None, "duree_s": duree(wav),
                 "reglages": {"latence_ms": lat, "autotune": bool(niveau), "autotune_niveau": niveau, "autotune_rapport": rapport,
                              "tonalite": tonalite, "voix_db": voix_db,
                              "reverb": reverb, "echo": echo, "debruitage": bool(debruitage)},
                 "mesure": mesure, "avis": avis, "calcul_s": round(time.time() - t0, 1), "fin": time.time()}
        _ecrire(sortie_dir / f"{nom}.json", fiche)
        return fiche
    finally:
        if not travail_dir:
            shutil.rmtree(tmp, ignore_errors=True)


# (13/11, Ahmed : « séparer correctement les voix de l'instru et garder ce que je lui demande ») la séparation mesurée sur un banc (des
# instrus d'ACE-Step sans voix + des voix connues, 6 mélanges) : htdemucs seul (d'avant) 16,2 dB de SDR ; htdemucs_ft 16,4 ; l'ensemble
# ft + htdemucs 16,6 (fuite de voix −31 dB, artefacts −16,8 dB) ; 6 pistes 14,0 (il mange la mélodie) ; la porte de la voix ne change
# presque rien (le « vocals » des modèles garde du ney et de l'oud même là où personne ne chante). D'où : l'ensemble ft + htdemucs, la
# porte à −25 dB, et pour ses propres chansons la REPRISE par ACE-Step (chant.py, reprise) quand la voix couvre tout le morceau.
MODELES_INSTRU = ("htdemucs_ft", "htdemucs")
PISTES_DE = {"batterie": "drums", "basse": "bass", "melodie": "other", "mélodie": "other", "autres": "other", "guitare": "guitar",
             "piano": "piano", "drums": "drums", "bass": "bass", "other": "other"}


def extraire_instru(source, instrus_dir, titre="", travail_dir=None, progres=None, garder=None):
    """Une chanson de Hakim → son instru : Demucs (ft + htdemucs, la voix retirée là où elle chante). garder : les pistes que papa
    garde (« batterie, basse ») : l'instru est alors leur somme ; sans liste, tout ce qui n'est pas la voix (le mélange moins la voix)."""
    t0 = time.time()
    dire = progres or (lambda n, texte: None)
    instrus_dir = Path(instrus_dir)
    instrus_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(travail_dir or instrus_dir / f".instru-{uuid.uuid4().hex[:6]}")
    tmp.mkdir(parents=True, exist_ok=True)
    g = sorted({PISTES_DE.get(_cle(x), "") for x in (garder or [])} - {""})
    try:
        dire(1, "préparation")
        m44 = tmp / "melange44.wav"
        _ff("-i", source, "-ar", SR, "-ac", 2, "-c:a", "pcm_s16le", m44)
        dire(2, "Demucs retire la voix (deux modèles, la voix seulement là où elle chante)")
        r = subprocess.run([str(PYTHON_SEPARATION), "-B", "-W", "ignore", str(ICI / "studio_separation.py"), "separer", str(m44), str(tmp / "sep"),
                            "--modeles", ",".join(MODELES_INSTRU), "--format", "wav", "--porte", "-25", *(["--garder", ",".join(g)] if g else [])],
                           capture_output=True, text=True, timeout=3600)
        if r.returncode:
            raise RuntimeError(f"Demucs : {r.stderr.strip()[-300:]}")
        res = json.loads(r.stdout.strip().splitlines()[-1])
        dire(3, "encodage")
        ident = nom_de((titre or Path(source).stem) + "-instru")
        mp3 = instrus_dir / f"{ident}.mp3"
        _ff("-i", res["instru"], "-af", "alimiter=limit=-1dB:level=false:latency=true", "-c:a", "libmp3lame", "-b:a", "320k", mp3)
        gardees = ", ".join(x for x in g) if g else ""
        fiche = {"id": ident, "titre": f"{titre or Path(source).stem} (instru{' : ' + gardees if gardees else ''})", "source": str(source), "mp3": str(mp3),
                 "origine": "demucs", "modeles": res.get("modeles"), "garder": g, "duree_s": duree(mp3), "calcul_s": round(time.time() - t0, 1),
                 "fin": time.time()}
        _ecrire(instrus_dir / f"{ident}.json", fiche)
        # (10/11, lettre de Hakim, à la demande de papa) aussi dans le dossier Hakim de ses Documents, sous son nom lisible
        try:
            doc = deposer_aux_documents(mp3, fiche["titre"], note=f"son instru « {fiche['titre']} », tirée par le studio")
            if doc:
                fiche.update(documents=str(doc), joindre=chemin_a_joindre(doc))
        except Exception as e:                               # noqa: BLE001 — l'instru reste prête dans le Studio sans sa copie
            fiche["documents_erreur"] = str(e)[:200]
        _ecrire(instrus_dir / f"{ident}.json", fiche)
        return fiche
    finally:
        if not travail_dir:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ la file des travaux

def _travaux(studio=None):
    return Path(studio or STUDIO) / "travaux"


def chant_en_cours(taches=None):
    """Une chanson d'ACE-Step se calcule-t-elle ? (12 à 15 Go : le studio attend) (06/11) Une création de l'Atelier
    visuel (atelier_visuel.py : une image, un clip) aussi : un gros calcul à la fois."""
    for p in Path(taches or TACHES).glob("T-*.json"):
        d = _lire(p, {}) or {}
        if (d.get("chanson") or d.get("visuel")) and d.get("etat") == "en cours" and (not d.get("superviseur") or _vivant(d["superviseur"])):
            return d
    return None


def occupe(studio=None):
    """Le travail du studio en cours de calcul (un travailleur vivant), sinon None. chant.lancer le consulte."""
    for p in sorted(_travaux(studio).glob("J-*.json")):
        d = _lire(p, {}) or {}
        if d.get("etat") == "en cours" and _vivant(d.get("pid")):
            return d
    return None


def lancer(type_, params, studio=None, demarrer=None):
    """Met un travail en file et réveille le travailleur (un seul à la fois). Rend la fiche du travail."""
    if type_ not in TYPES:
        raise Refus(f"type inconnu : {type_}")
    p = dict(params or {})
    if type_ == "mixer":
        for k in ("prise", "instru"):
            if not p.get(k) or not Path(p[k]).is_file():
                raise Refus(f"{k} introuvable")
    elif type_ in ("rendre", "separer", "reference"):
        if not re.fullmatch(r"PJ-\d{8}-\d{6}-[0-9a-f]{4}", str(p.get("projet") or "")):
            raise Refus("projet inconnu")
    else:
        if not p.get("source") or not Path(p["source"]).is_file():
            raise Refus("chanson introuvable")
    d = _travaux(studio)
    d.mkdir(parents=True, exist_ok=True)
    en_file = [x for x in (_lire(f, {}) or {} for f in d.glob("J-*.json")) if x.get("etat") in ("en attente", "en cours")]
    if len(en_file) >= 5:
        raise Refus("déjà 5 calculs en file : attends qu'ils finissent")
    jid = f"J-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    fiche = {"id": jid, "type": type_, "params": p, "etat": "en attente", "debut": time.time(), "etape": 0,
             "etapes": {"mixer": 7, "instru": 3, "projet": 3, "rendre": 8, "separer": 2, "reference": 1}[type_], "texte": "en file"}
    _ecrire(d / f"{jid}.json", fiche)
    (demarrer or _demarrer_travailleur)(d)
    return fiche


def _demarrer_travailleur(d):
    args = ["/usr/bin/nice", "-n", "10", str(PYTHON_CHANT), "-B", str(Path(__file__).resolve()), "travailleur", str(d)]
    with open(Path(d) / "travailleur.log", "ab") as log:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                         close_fds=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})


def faire(fiche, d, studio=None):
    """Un travail : le calcul, puis son état final (fini ou raté)."""
    studio = Path(studio or Path(d).parent)
    def progres(n, texte):
        fiche.update(etape=n, texte=texte)
        _ecrire(Path(d) / f"{fiche['id']}.json", fiche)
        print(f"PROGRESSION {n}/{fiche['etapes']} {texte}", flush=True)
    p = fiche["params"]
    try:
        if fiche["type"] == "mixer":
            r = mixer(p["prise"], p["instru"], studio, titre=p.get("titre", ""), latence_ms=p.get("latence_ms", 0),
                      autotune=p.get("autotune", False), tonalite=p.get("tonalite", ""), voix_db=p.get("voix_db", 0),
                      reverb=p.get("reverb", 0.3), echo=p.get("echo", 0), bpm=p.get("bpm", 0),
                      debruitage=p.get("debruitage", True), progres=progres)
        elif fiche["type"] == "projet":                     # (13/11) un projet multipiste depuis un son (séparé en pistes)
            import studio_projet as SP
            q = SP.creer_depuis(p["source"], p.get("titre", ""), p.get("separer", "4"), p.get("garder") or None,
                                p.get("role_voix", "voix_hakim"), p.get("genre", "trap"), studio, progres=progres,
                                tempo=p.get("tempo", 0), tonalite=p.get("tonalite", ""))
            r = {"projet": q["id"], "titre": q["titre"], "pistes": len(q["pistes"]), "tempo": q.get("tempo"), "tonalite": q.get("tonalite")}
        elif fiche["type"] == "rendre":                     # (13/11) mix piste par piste, master, exports, mesures, téléphone
            import studio_projet as SP
            r = SP.rendre_projet(p["projet"], p.get("quoi", "tout"), bool(p.get("mix_auto")), p.get("envoyer", True) is not False,
                                 bool(p.get("pistes_separees")), studio, progres=progres,
                                 nom_version=p.get("nom_version") or "", par=p.get("par") or "")      # (14/11) les versions
            r = {"projet": p["projet"], "nom": r["nom"], "version": r.get("v"), "fichiers": r["fichiers"], "telephone": r["telephone"], "avis": r["avis"],
                 "master": {k: r["mesures"]["master"].get(k) for k in ("lufs", "crete_dbtp", "lra", "plr_db")},
                 "mp3_crete_dbtp": r["mesures"]["mp3"].get("crete_dbtp"), "calcul_s": r["calcul_s"]}
        elif fiche["type"] == "reference":                  # (14/11) une voix d'un projet gardée comme profil de référence
            import studio_projet as SP
            progres(1, "la voix de référence mesurée (sa couleur, sa densité, ses sifflantes, son espace)")
            r = SP.garder_reference(p["projet"], p.get("piste") or None, p.get("nom") or "hakim", studio)
        elif fiche["type"] == "separer":                    # (13/11) une piste d'un projet séparée en ses pistes
            import studio_projet as SP
            q = SP.separer_piste(p["projet"], p["piste"], p.get("separer", "4"), studio, progres=progres)
            r = {"projet": q["id"], "pistes": len(q["pistes"])}
        else:
            r = extraire_instru(p["source"], studio / "instrus", titre=p.get("titre", ""), progres=progres,
                                garder=p.get("garder") or None)
        fiche.update(etat="fini", resultat=r, texte="prêt")
    except Exception as e:                                   # noqa: BLE001 — toute panne finit le travail proprement
        fiche.update(etat="raté", erreur=f"{type(e).__name__}: {str(e)[:300]}", texte="raté")
    fiche["fin"] = time.time()
    _ecrire(Path(d) / f"{fiche['id']}.json", fiche)
    return fiche


def travailleur(d, attente_s=5):
    """Le seul travailleur (un verrou) : les travaux en attente, du plus ancien au plus récent, un à la fois ; jamais
    pendant une chanson d'ACE-Step."""
    d = Path(d)
    verrou = open(d / ".travailleur", "w")
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0                                             # un autre travaille déjà : il prendra celui-ci
    faits = 0
    try:
        while True:
            attente = sorted((x for x in (_lire(f, {}) or {} for f in d.glob("J-*.json")) if x.get("etat") == "en attente"),
                             key=lambda x: x.get("debut", 0))
            if not attente:
                return faits
            c = chant_en_cours()
            if c:
                for x in attente:
                    x["texte"] = "attend la fin de la chanson de Hakim (une seule grosse tâche à la fois)"
                    _ecrire(d / f"{x['id']}.json", x)
                time.sleep(attente_s)
                continue
            fiche = attente[0]
            fiche.update(etat="en cours", pid=os.getpid(), debut_calcul=time.time())
            _ecrire(d / f"{fiche['id']}.json", fiche)
            faire(fiche, d)
            faits += 1
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def instru_hakim(style, bpm=0, duree_s=60, titre=""):
    """« Demander une instru à Hakim » : l'outil existant (chant.lancer), en instrumental, pour le studio."""
    sys.path.insert(0, str(ICI))
    import chant
    try:
        return chant.lancer("[instrumental]", style, duree_s, titre or f"Instru {style}", bpm=bpm, pour_studio=True)
    except chant.Refus as e:
        raise Refus(str(e))


# ------------------------------------------------------------------------------------------------ son instru, pour la voix de papa
# (09/11, Ahmed : « qu'il sache extraire SON instru d'une de ses chansons, “Deux livres” par exemple, pour que je pose ma voix
# dessus ») le même Demucs que la page du Studio (extraire_instru, en file) ; Hakim nomme sa chanson par son titre.

def _cle(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).split())


def _meme_fichier(a, b):
    try:
        return bool(a) and bool(b) and Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def ses_chansons(chansons=None):
    """Ses chansons finies (fiche « prête » et son MP3 là ; jamais la prise « sans correction »), la plus récente d'abord."""
    l = []
    for f in Path(chansons or CHANSONS).glob("*.json"):
        d = _lire(f, {}) or {}
        mp3 = str(d.get("mp3") or "")
        if d.get("etat") == "prête" and d.get("nom") and mp3 and not mp3.endswith("-sans-correction.mp3") and Path(mp3).is_file():
            l.append(d)
    return sorted(l, key=lambda d: d.get("fin") or d.get("debut") or 0, reverse=True)


def trouver_chanson(demande, chansons=None):
    """« Deux livres » → sa chanson : son nom exact (20261109-171743-deux-livres) ou son MP3, sinon son titre sans accents ni
    casse (le titre exact d'abord, puis un titre qui le contient), la version la plus récente. Rend (fiche, les autres versions)."""
    q = " ".join(str(demande or "").split())
    if not q:
        raise Refus("dis de quelle chanson (son titre, ou son nom)")
    toutes = ses_chansons(chansons)
    for d in toutes:
        if q in (d["nom"], Path(d["mp3"]).name, Path(d["mp3"]).stem) or _meme_fichier(Path(q).expanduser(), d["mp3"]):
            return d, []
    k = _cle(q)
    trouves = [d for d in toutes if _cle(d.get("titre")) == k] + [d for d in toutes if k and k in _cle(d.get("titre")) and _cle(d.get("titre")) != k]
    if not trouves:
        recentes = ", ".join(f"« {d.get('titre')} »" for d in toutes[:6]) or "aucune"
        raise Refus(f"aucune de tes chansons finies ne s'appelle « {q} » (les dernières : {recentes})")
    return trouves[0], trouves[1:]


def instru_du_studio(demande, studio=None):
    """Une instru du Studio par son identifiant (studio_avis les liste) ou son titre, ou un chemin de son. Rend le chemin, ou ''."""
    q = " ".join(str(demande or "").split())
    if not q:
        return ""
    if Path(q).expanduser().is_file():
        return str(Path(q).expanduser())
    l = sorted((x for x in (_lire(f, {}) or {} for f in (Path(studio or STUDIO) / "instrus").glob("*.json"))
                if x.get("mp3") and Path(x["mp3"]).is_file()), key=lambda x: x.get("fin") or 0, reverse=True)
    x = next((x for x in l if x.get("id") == q), None) or next((x for x in l if _cle(x.get("titre")) == _cle(q)), None)
    return x["mp3"] if x else ""


def instru_reprise(c, source, fidelite=0.9, titre="", lancer_chant=None):
    """(13/11) l'instru REJOUÉE par ACE-Step : la tâche « cover » sur la chanson (ou sur son instru Demucs), en instrumental, au même tempo,
    dans la même tonalité, avec sa légende sans voix : pas de trous là où la voix chantait (une séparation en laisse quand la voix
    couvre tout le morceau). Une chanson à la fois (la file d'ACE-Step). Rend la tâche."""
    sys.path.insert(0, str(ICI))
    import chant
    style = c.get("style") or c.get("description") or "trap"
    try:
        return (lancer_chant or chant.lancer)("[instrumental]", style, int(max(10, min(240, round(float(c.get("duree_s") or 60))))),
                                              titre or f"{c.get('titre') or c['nom']} (instru rejouée)", bpm=int(c.get("bpm") or 0),
                                              tonalite=c.get("tonalite") or "", reprise=str(source), fidelite=fidelite, pour_studio=True)
    except chant.Refus as e:
        raise Refus(str(e))


def instru_de_chanson(demande, titre="", refaire=False, chansons=None, studio=None, demarrer=None, garder=None, methode="demucs",
                      fidelite=0.9, lancer_chant=None):
    """Sa chanson → son instru seule (Demucs retire sa voix), dans les instrus du Studio : papa y pose sa prise, puis Hakim la
    mixe (studio_mixer). Ni deux fois la même (déjà faite, ou déjà en file), sauf refaire. Rend {etat, chanson, autres, instru|travail}.
    (13/11) garder : les pistes que papa garde ; methode « reprise » : l'instru rejouée par ACE-Step (instru_reprise), depuis son instru
    Demucs si elle existe, sinon depuis la chanson."""
    c, autres = trouver_chanson(demande, chansons)
    if methode == "reprise":
        st = Path(studio or STUDIO)
        faites = sorted((x for x in (_lire(f, {}) or {} for f in (st / "instrus").glob("*.json"))
                         if x.get("origine") == "demucs" and _meme_fichier(x.get("source"), c["mp3"]) and x.get("mp3") and Path(x["mp3"]).is_file()
                         and not x.get("garder")), key=lambda x: x.get("fin") or 0, reverse=True)
        src = faites[0]["mp3"] if faites else c["mp3"]
        t = instru_reprise(c, src, fidelite, titre, lancer_chant)
        return {"chanson": c, "autres": autres, "etat": "reprise", "tache": t, "depuis": "son instru Demucs" if faites else "la chanson"}
    if c.get("instrumental"):
        raise Refus(f"« {c.get('titre')} » est déjà une instru (pas de voix à retirer) : papa peut poser sa prise directement dessus "
                    "dans le Studio")
    st = Path(studio or STUDIO)
    r = {"chanson": c, "autres": autres}
    g = sorted({PISTES_DE.get(_cle(x), "") for x in (garder or [])} - {""})
    if not refaire:
        faites = sorted((x for x in (_lire(f, {}) or {} for f in (st / "instrus").glob("*.json"))
                         if x.get("origine") == "demucs" and _meme_fichier(x.get("source"), c["mp3"]) and x.get("mp3") and Path(x["mp3"]).is_file()
                         and sorted(x.get("garder") or []) == g and x.get("modeles")),       # (13/11) celles d'avant le banc se refont
                        key=lambda x: x.get("fin") or 0, reverse=True)
        if faites:                                           # (10/11) et sa copie dans les Documents de papa (déposée si elle manque)
            return {**r, "etat": "déjà", "instru": faites[0], "joindre": instru_aux_documents(faites[0])}
    for x in (_lire(f, {}) or {} for f in _travaux(st).glob("J-*.json")):
        if x.get("type") == "instru" and x.get("etat") in ("en attente", "en cours") and _meme_fichier((x.get("params") or {}).get("source"), c["mp3"]):
            return {**r, "etat": "en file", "travail": x}
    titre = " ".join(str(titre or "").split())[:80] or c.get("titre") or c["nom"]
    j = lancer("instru", {"source": str(Path(c["mp3"]).resolve()), "titre": titre, "chanson": c["nom"], "par": "hakim", "garder": g}, st, demarrer)
    return {**r, "etat": "lancé", "travail": j}


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "travailleur":
        travailleur(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] in ("lancer", "instru-hakim", "synchroniser"):
        # le cockpit : une ligne JSON en entrée, une ligne JSON en sortie
        try:
            q = json.loads(sys.stdin.read() or "{}")
            if sys.argv[1] == "lancer":
                r = lancer(q.get("type"), q.get("params"))
            elif sys.argv[1] == "instru-hakim":
                r = instru_hakim(q.get("style", ""), q.get("bpm", 0), q.get("duree_s", 60), q.get("titre", ""))
            else:
                r = {"copies": synchroniser()}
            print(json.dumps({"ok": True, **r}, ensure_ascii=False))
        except Refus as e:
            print(json.dumps({"ok": False, "erreur": str(e)}, ensure_ascii=False))
    else:
        print("usage : studio.py travailleur <dossier> | lancer | instru-hakim | synchroniser", file=sys.stderr)
        sys.exit(2)
