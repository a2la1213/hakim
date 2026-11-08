"""Le studio de Hakim (06/11, Ahmed : « que moi aussi je puisse m'enregistrer et me faire mixer et masteriser par Hakim,
comme ça on peut faire des vrais sons depuis le phone » ; « il faut absolument un truc Studio dans le cockpit »).

Tout se calcule SUR LE MAC, avec des outils locaux et gratuits :
- ffmpeg (déjà là) pour la chaîne : coupe-bas, débruitage léger (afftdn), égaliseur, dé-essage, compression, réverb et
  écho (aecho), équilibre voix/instru, mastering (compression de bus, loudnorm en deux passes vers −14 LUFS intégrés,
  limiteur à −1 dBFS), export WAV et MP3 ;
- l'autotune de chant.py (WORLD, recalage note par note sur la gamme) sur la voix seule : pas besoin de Demucs, la prise
  est déjà une voix seule ;
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
TYPES = ("mixer", "instru")


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


def autotuner_voix(entree, sortie, tonalite, force=1.0):
    """(.venv-chant) l'autotune de chant.py sur une voix seule : WORLD la recale note par note sur la gamme."""
    import numpy as np
    import pyworld as pw
    sys.path.insert(0, str(ICI))
    import chant
    x, sr = _pcm(entree, SR)
    x = x.astype(np.float64)
    f0, t = pw.dio(x, sr, f0_floor=70.0, f0_ceil=900.0, frame_period=5.0)
    f0 = pw.stonemask(x, f0, t, sr)
    sp, ap = pw.cheaptrick(x, f0, t, sr), pw.d4c(x, f0, t, sr)
    y = pw.synthesize(np.array(chant.caler(f0, chant.gamme(tonalite), force), dtype=np.float64), sp, ap, sr, 5.0)[: len(x)]
    y = np.pad(y, (0, len(x) - len(y)))
    y *= np.sqrt((x ** 2).mean() / max(1e-12, (y ** 2).mean()))
    y *= min(1.0, 0.95 / max(1e-9, np.abs(y).max()))
    tmp = Path(sortie).with_suffix(".f32")
    y.astype(np.float32).tofile(tmp)
    _ff("-f", "f32le", "-ar", sr, "-ac", 1, "-i", tmp, "-c:a", "pcm_s16le", sortie)
    tmp.unlink()
    return sortie


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
        if autotune:
            dire(3, "autotune")
            tonalite = tonalite or tonalite_de(instru)
            source_voix = autotuner_voix(propre, tmp / "voix-autotune.wav", tonalite)
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
                 "reglages": {"latence_ms": lat, "autotune": bool(autotune), "tonalite": tonalite, "voix_db": voix_db,
                              "reverb": reverb, "echo": echo, "debruitage": bool(debruitage)},
                 "mesure": mesure, "avis": avis, "calcul_s": round(time.time() - t0, 1), "fin": time.time()}
        _ecrire(sortie_dir / f"{nom}.json", fiche)
        return fiche
    finally:
        if not travail_dir:
            shutil.rmtree(tmp, ignore_errors=True)


def extraire_instru(source, instrus_dir, titre="", travail_dir=None, progres=None):
    """Une chanson de Hakim → son instru : Demucs (htdemucs, dans son venv) retire la voix."""
    t0 = time.time()
    dire = progres or (lambda n, texte: None)
    instrus_dir = Path(instrus_dir)
    instrus_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(travail_dir or instrus_dir / f".instru-{uuid.uuid4().hex[:6]}")
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        dire(1, "préparation")
        m44 = tmp / "melange44.wav"
        _ff("-i", source, "-ar", SR, "-ac", 2, "-c:a", "pcm_s16le", m44)
        dire(2, "Demucs retire la voix")
        r = subprocess.run([str(PYTHON_SEPARATION), "-B", str(ICI / "chant.py"), "separer", str(m44), str(tmp / "voix.wav"),
                            str(tmp / "reste.wav")], capture_output=True, text=True, timeout=1800)
        if r.returncode:
            raise RuntimeError(f"Demucs : {r.stderr.strip()[-300:]}")
        dire(3, "encodage")
        ident = nom_de((titre or Path(source).stem) + "-instru")
        mp3 = instrus_dir / f"{ident}.mp3"
        _ff("-i", tmp / "reste.wav", "-c:a", "libmp3lame", "-b:a", "320k", mp3)
        fiche = {"id": ident, "titre": f"{titre or Path(source).stem} (instru)", "source": str(source), "mp3": str(mp3),
                 "origine": "demucs", "duree_s": duree(mp3), "calcul_s": round(time.time() - t0, 1), "fin": time.time()}
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
             "etapes": 7 if type_ == "mixer" else 3, "texte": "en file"}
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
        else:
            r = extraire_instru(p["source"], studio / "instrus", titre=p.get("titre", ""), progres=progres)
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
