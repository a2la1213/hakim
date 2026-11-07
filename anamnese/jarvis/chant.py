"""Hakim compose et chante (accord d'Ahmed, 2026-11-06 : « T'as mon accord pour ACE-Step, et tout faire bien pour que
Hakim puisse chanter »).

Des paroles, un style, une durée → un vrai morceau chanté (voix et instrumental), calculé SUR LE MAC par ACE-Step 1.5
(MIT, code et poids ; https://github.com/ace-step/ACE-Step-1.5), gratuit et hors ligne une fois les poids là.

Deux rôles dans ce fichier :
- `lancer` (importé par mcp_server.py, venv d'Anamnèse, sans torch) : vérifie la demande, l'écrit comme une TÂCHE DE
  FOND ordinaire dans ~/AIOS/jarvis/cwd/taches (même forme que jarvis/taches.py) et détache le calcul. Le cockpit
  voit donc la chanson comme toute tâche : jauge (lignes PROGRESSION), avis à Ahmed quand elle finit, et réveil de
  Hakim, qui la lui envoie avec fichier_joindre ;
- `generer` (lancé à part : `nice -n 10 .venv-chant/bin/python chant.py generer <tâche>`) : charge ACE-Step, compose,
  encode en MP3 dans ~/AIOS/jarvis/chansons/AAAAMMJJ-HHMMSS-titre.mp3 avec un JSON à côté (paroles, style, durée,
  temps de calcul), et en dépose une copie dans l'atelier (atelier/chansons/…) : c'est de là que fichier_joindre
  la prend.
Une chanson à la fois (16 Go partagés avec Ollama, Demucs et le cockpit).
"""
import fcntl
import json
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
CHANSONS = JARVIS / "chansons"
TACHES = JARVIS / "cwd" / "taches"
ATELIER = JARVIS / "cwd" / "atelier" / "chansons"
ACE = Path(os.environ.get("JARVIS_ACE_STEP", JARVIS / "ace-step" / "ACE-Step-1.5"))
PYTHON_CHANT = Path(os.environ.get("JARVIS_PYTHON_CHANT", ICI / ".venv-chant" / "bin" / "python"))
PYTHON_SEPARATION = Path(os.environ.get("JARVIS_PYTHON_SEPARATION", ICI / ".venv-separation" / "bin" / "python"))
FFMPEG = os.environ.get("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg")

DUREE_MIN, DUREE_MAX, DUREE_DEFAUT = 10, 240, 60
PAROLES_MAX = 4000
DELAI_S = 40 * 60                       # au-delà, le calcul est arrêté (une chanson de 4 min prend quelques minutes)
MAX_TACHES = 3                          # comme jarvis/taches.py
# (07/11, Hakim, avec l'accord d'Ahmed : « bloquée 3 min à PROGRESSION 1/5 chargement ; y a-t-il un timeout au chargement ? ») le chargement des
# modèles (DiT puis LM) a sa propre limite : au-delà, la chanson s'arrête et dit pourquoi (la mémoire du Mac, le plus souvent), au lieu d'attendre
# les 40 min du délai entier. Sa durée est notée dans le journal de la tâche (« Chargé en … s »), pour savoir ce qui est normal.
CHARGEMENT_MAX_S = int(os.environ.get("JARVIS_CHANT_CHARGEMENT_S", 6 * 60))
CHARGEMENT = {"depuis": None}

# Les styles : le mot de Hakim → la description qu'ACE-Step comprend le mieux (en anglais, genre + instruments + voix).
# Un style absent passe tel quel : « jazz manouche, guitare, voix douce » marche aussi.
STYLES = {
    "rap": "french rap, hip-hop, boom bap drums, deep 808 bass, dark piano loop, confident male rap vocals",
    "trap": "french trap, rolling hi-hats, heavy 808 bass, dark synth pads, rhythmic male rap vocals",
    "drill": "uk drill, sliding 808 bass, syncopated drill hi-hats and snares, dark strings, aggressive male rap vocals",
    "rai": "algerian rai, oriental synthesizers, darbuka and bendir percussion, accordion, emotional male vocals with melismas",
    "chaabi": "algerian chaabi, mandole, banjo, oud, violin, darbuka, traditional north african male vocals",
    "pop": "french pop, catchy melody, bright synths, acoustic guitar, punchy drums, warm male vocals",
    "rnb": "contemporary r&b, smooth groove, soft electric piano, sub bass, sensual male vocals with harmonies",
    "nasheed": "islamic nasheed, male vocals, layered vocal harmonies, soft daf frame drum, reverb, no melodic instruments",
    "gnawa": "moroccan gnawa, guembri bass lute, qraqeb metal castanets, hypnotic call and response male vocals",
    "andalou": "arabo-andalusian music, oud, qanun, violin, darbuka, refined male vocals",
    "ballade": "acoustic ballad, piano and strings, slow tempo, tender male vocals",
    "reggae": "roots reggae, offbeat guitar skank, deep bass, one drop drums, relaxed male vocals",
    "afro": "afrobeats, syncopated percussion, warm bass, bright guitar riffs, smooth male vocals",
    "electro": "electronic dance music, four on the floor kick, side-chained synth pads, male vocals",
    "rock": "rock, distorted electric guitars, live drums, bass guitar, powerful male vocals",
    "berceuse": "lullaby, soft music box, gentle acoustic guitar, whispered warm male vocals, slow",
}
ALIAS = {"raï": "rai", "chaâbi": "chaabi", "chaabi algérois": "chaabi", "r'n'b": "rnb", "r&b": "rnb", "rnb": "rnb",
         "hip-hop": "rap", "hip hop": "rap", "nachid": "nasheed", "anachid": "nasheed", "nasheed": "nasheed",
         "andalous": "andalou", "rap français": "rap", "drill uk": "drill", "electro": "electro", "électro": "electro", "afrobeat": "afro", "afrobeats": "afro"}


class Refus(Exception):
    pass


def _cle(s):
    return " ".join(str(s or "").lower().split())


def description(style):
    """Le style de Hakim → la description donnée à ACE-Step (512 caractères au plus)."""
    s = _cle(style)
    if not s:
        raise Refus("un style, par exemple : " + ", ".join(sorted(STYLES)))
    cle = ALIAS.get(s, s)
    if cle in STYLES:
        return STYLES[cle]
    sans_accent = "".join(c for c in unicodedata.normalize("NFD", cle) if unicodedata.category(c) != "Mn")
    return STYLES.get(ALIAS.get(sans_accent, sans_accent), " ".join(str(style).split()))[:512]


def langue_de(paroles, langue=""):
    """La langue chantée : donnée, sinon l'arabe dès que l'écriture arabe domine, sinon le français."""
    if langue:
        return str(langue).strip().lower()[:8]
    lettres = [c for c in paroles if c.isalpha()]
    arabes = sum(1 for c in lettres if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ")
    return "ar" if lettres and arabes / len(lettres) > 0.4 else "fr"


def structurer(paroles):
    """ACE-Step attend des sections ([verse], [chorus]…) ; des paroles nues deviennent un couplet."""
    p = str(paroles or "").replace("\r\n", "\n").strip()
    if not p:
        raise Refus("des paroles (ou « [instrumental] » pour un morceau sans voix)")
    if len(p) > PAROLES_MAX:
        raise Refus(f"paroles trop longues ({len(p)} caractères ; {PAROLES_MAX} au plus)")
    return p if re.search(r"^\s*\[[^\]]+\]", p, re.M) else "[verse]\n" + p


def nom_de(titre, quand=None):
    t = unicodedata.normalize("NFD", str(titre or "chanson").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9؀-ۿ]+", "-", t).strip("-")[:40].strip("-") or "chanson"
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(quand or time.time())) + "-" + t


def preparer(paroles, style, duree_s=DUREE_DEFAUT, titre="", langue="", autotune=False, bpm=0, pour_studio=False):
    """La demande vérifiée et mise en forme (aucun effet de bord). bpm : 0 = au choix d'ACE-Step (sinon 30 à 300)."""
    try:
        d = int(round(float(duree_s or DUREE_DEFAUT)))
    except (TypeError, ValueError):
        raise Refus(f"une durée en secondes ({DUREE_MIN} à {DUREE_MAX})")
    if not DUREE_MIN <= d <= DUREE_MAX:
        raise Refus(f"durée de {DUREE_MIN} à {DUREE_MAX} secondes (demandé : {d})")
    instrumental = _cle(paroles) in ("[instrumental]", "instrumental")
    texte = "[Instrumental]" if instrumental else structurer(paroles)
    titre = " ".join(str(titre or "").split())[:80] or "Sans titre"
    try:
        bpm = int(round(float(bpm or 0)))
    except (TypeError, ValueError):
        raise Refus("un tempo en BPM (30 à 300), ou 0 pour le laisser choisir")
    if bpm and not 30 <= bpm <= 300:
        raise Refus(f"tempo de 30 à 300 BPM (demandé : {bpm})")
    desc = description(style)
    if autotune:
        desc = (desc + ", " + TAG_AUTOTUNE)[:512]
    return {"titre": titre, "style": " ".join(str(style or "").split())[:200], "description": desc, "autotune": bool(autotune),
            "paroles": texte, "langue": "unknown" if instrumental else langue_de(texte, langue), "duree_s": d,
            "instrumental": instrumental, "nom": nom_de(titre), "bpm": bpm, "pour_studio": bool(pour_studio)}


# ---------------------------------------------------------------------------------------------------- l'autotune
# (06/11, Ahmed : « qu'il rappe, et qu'il chante, mon fiston, avec autotune et sans ») avec autotune, deux gestes : le
# tag « auto-tuned vocals » dans la description (ACE-Step a appris ce son), PUIS une vraie correction de hauteur sur la
# voix seule (Demucs la sépare, WORLD la recale note par note sur la gamme du morceau, puis on remixe).
TAG_AUTOTUNE = "auto-tuned vocals, autotune pitch correction"
NOTES = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8,
         "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11, "cb": 11, "e#": 5, "fb": 4, "b#": 0}
MAJEURE, MINEURE = (0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10)


def gamme(tonalite):
    """« C Major », « F# minor », « Am », « B♭ min » → les classes de hauteur (0-11) ; inconnue → les 12 (chromatique)."""
    t = str(tonalite or "").strip().lower().replace("♯", "#").replace("♭", "b")
    m = re.match(r"^([a-g])\s*([#b]?)\s*(.*)$", t)
    if not m or (m.group(1) + m.group(2)) not in NOTES:
        return tuple(range(12))
    racine, mode = NOTES[m.group(1) + m.group(2)], m.group(3).strip()
    mineur = mode.startswith("min") or mode == "m" or mode.startswith("m ") or "minor" in mode
    return tuple(sorted((racine + i) % 12 for i in (MINEURE if mineur else MAJEURE)))


def caler(f0, classes, force=1.0):
    """La hauteur (Hz par trame, 0 = non voisé) recalée sur la note permise la plus proche. force 1 = autotune dur."""
    import math
    sortie = []
    for f in f0:
        if not f or f <= 0:
            sortie.append(0.0)
            continue
        m = 69 + 12 * math.log2(f / 440.0)
        base = math.floor(m)
        cible = min((n for n in range(base - 2, base + 3) if n % 12 in classes), key=lambda n: abs(n - m))
        sortie.append(440.0 * 2 ** ((m + force * (cible - m) - 69) / 12))
    return sortie


def separer_voix(melange, voix, reste):
    """(.venv-separation) Demucs htdemucs : le mélange → la voix et le reste (WAV)."""
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    x, sr = sf.read(melange, dtype="float32", always_2d=True)
    m = get_model("htdemucs").eval()
    if sr != m.samplerate:
        raise RuntimeError(f"taux {sr} ≠ {m.samplerate}")
    appareil = "mps" if torch.backends.mps.is_available() else "cpu"
    with torch.no_grad():
        p = apply_model(m.to(appareil), torch.tensor(np.ascontiguousarray(x.T))[None], device=appareil, progress=False)[0].cpu().numpy()
    v = p[m.sources.index("vocals")].T
    sf.write(voix, v, sr)
    sf.write(reste, x - v, sr)


def autotuner(melange, sortie, tonalite):
    """(.venv-chant) sépare (Demucs, dans .venv-separation), recale la voix (WORLD), remixe. Rend la gamme utilisée."""
    import numpy as np
    import pyworld as pw
    import soundfile as sf
    d = Path(sortie).parent
    voix, reste = d / "voix.wav", d / "reste.wav"
    melange44 = d / "melange44.wav"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(melange), "-ar", "44100", "-ac", "2",
                    str(melange44)], check=True, timeout=300)
    subprocess.run([str(PYTHON_SEPARATION), "-B", str(Path(__file__).resolve()), "separer", str(melange44), str(voix),
                    str(reste)], check=True, timeout=1200)
    v, sr = sf.read(voix, dtype="float64", always_2d=True)
    r, _ = sf.read(reste, dtype="float64", always_2d=True)
    classes = gamme(tonalite)
    mono = np.ascontiguousarray(v.mean(axis=1))
    f0, t = pw.dio(mono, sr, f0_floor=70.0, f0_ceil=900.0, frame_period=5.0)
    f0 = pw.stonemask(mono, f0, t, sr)
    sp, ap = pw.cheaptrick(mono, f0, t, sr), pw.d4c(mono, f0, t, sr)
    y = pw.synthesize(np.array(caler(f0, classes), dtype=np.float64), sp, ap, sr, 5.0)[: len(mono)]
    y = np.pad(y, (0, len(mono) - len(y)))
    gain = np.sqrt((mono ** 2).mean() / max(1e-12, (y ** 2).mean()))   # même niveau que la voix d'origine
    mix = r + (y * gain)[:, None]
    mix *= min(1.0, 0.89 / max(1e-9, np.abs(mix).max()))             # crête à -1 dB
    sf.write(sortie, mix.astype(np.float32), sr)
    return classes


# ---------------------------------------------------------------------------------------------------- la tâche

def _ecrire(p, d):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _vivant(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError, ValueError):
        return False


def _en_cours(dossier):
    vus = []
    for p in sorted(Path(dossier).glob("T-*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("etat") == "en cours" and (not d.get("superviseur") or _vivant(d["superviseur"])):
            vus.append(d)
    return vus


def _demarrer(args, log):
    """Détache le calcul (son propre groupe : un Stop du cerveau ne le tue pas). Rend son pid."""
    with open(log, "ab") as sortie:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=sortie, stderr=subprocess.STDOUT,
                             start_new_session=True, close_fds=True, cwd=str(ACE) if ACE.is_dir() else None,
                             env={**os.environ, "TOKENIZERS_PARALLELISM": "false", "ACESTEP_LM_BACKEND": "mlx",
                                  "PYTORCH_ENABLE_MPS_FALLBACK": "1", "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1"})
    return p.pid


def _studio_occupe():
    """(06/11) le studio calcule-t-il (Demucs, un mix) ? Jamais deux gros calculs à la fois sur 16 Go."""
    try:
        sys.path.insert(0, str(ICI))
        import studio
        return studio.occupe()
    except Exception:                                        # noqa: BLE001 — sans studio lisible, on ne bloque pas
        return None


def lancer(paroles, style, duree_s=DUREE_DEFAUT, titre="", langue="", autotune=False, dossier=None, chansons=None,
           demarrer=None, bpm=0, pour_studio=False):
    """Lance la composition en tâche de fond ; rend {tache, nom, …} tout de suite."""
    demande = preparer(paroles, style, duree_s, titre, langue, autotune, bpm, pour_studio)
    dossier, chansons = Path(dossier or TACHES), Path(chansons or CHANSONS)
    if demarrer is None and not (PYTHON_CHANT.exists() and (ACE / "checkpoints").is_dir()):
        raise Refus("ACE-Step n'est pas installé sur le Mac (demande à Ahmed ou à Nour)")
    dossier.mkdir(parents=True, exist_ok=True)
    chansons.mkdir(parents=True, exist_ok=True)
    verrou = open(dossier / ".verrou", "w")                   # le même verrou que jarvis/taches.py
    fcntl.flock(verrou, fcntl.LOCK_EX)
    try:
        en_cours = _en_cours(dossier)
        chants = [e for e in en_cours if e.get("chanson")]
        if chants:
            raise Refus(f"je compose déjà « {chants[0]['chanson'].get('titre')} » ({chants[0]['id']}) : une chanson à la fois")
        visuels = [e for e in en_cours if e.get("visuel")]          # (06/11) l'Atelier visuel : une image, un clip
        if visuels:
            raise Refus(f"l'atelier crée « {visuels[0]['visuel'].get('titre')} » ({visuels[0]['id']}) : attends qu'il finisse "
                        "(une grosse tâche à la fois)")
        if demarrer is None and _studio_occupe():
            raise Refus("le studio calcule un mix ou une instru : attends qu'il finisse (une grosse tâche à la fois)")
        if len(en_cours) >= MAX_TACHES:
            raise Refus(f"déjà {len(en_cours)} tâches de fond en cours : attends qu'une finisse")
        tid = f"T-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        avec = ", autotune" if demande["autotune"] else ""
        d = {"id": tid, "commande": f"chanter « {demande['titre']} » ({demande['style'][:60]}{avec}, {demande['duree_s']} s)",
             "debut": time.time(), "etat": "en cours", "delai_s": DELAI_S, "atelier": str(ATELIER), "chanson": demande}
        _ecrire(dossier / f"{tid}.json", d)
        _ecrire(chansons / f"{demande['nom']}.json", {**demande, "etat": "en cours", "tache": tid, "debut": d["debut"]})
        args = ["/usr/bin/nice", "-n", "10", str(PYTHON_CHANT), "-B", str(Path(__file__).resolve()), "generer", tid, str(dossier)]
        pid = (demarrer or _demarrer)(args, dossier / f"{tid}.log")
        d.update(pid=pid, superviseur=pid)
        _ecrire(dossier / f"{tid}.json", d)
        return {"tache": tid, **demande}
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def finir(tid, dossier=None, chansons=None, atelier=None, erreur=None, mp3=None, calcul_s=None, raison=None, telephone=None):
    """L'état final de la tâche et de la fiche de la chanson ; la copie dans l'atelier. Rend la ligne de fin."""
    dossier, chansons, atelier = Path(dossier or TACHES), Path(chansons or CHANSONS), Path(atelier or ATELIER)
    d = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))
    c = d["chanson"]
    fiche_p = chansons / f"{c['nom']}.json"
    try:
        fiche = json.loads(fiche_p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        fiche = dict(c)
    fin = time.time()
    if erreur or raison or not mp3:
        ligne = f"CHANSON RATÉE : {raison or erreur or 'aucun fichier produit'}"
        d.update(etat="arrêtée" if raison else "finie", raison=raison, code=0 if raison else 1)
        fiche.update(etat="ratée", erreur=str(raison or erreur)[:500])
    else:
        atelier.mkdir(parents=True, exist_ok=True)
        copie = atelier / Path(mp3).name
        shutil.copyfile(mp3, copie)
        rel = f"atelier/chansons/{copie.name}"
        ligne = (f"CHANSON PRÊTE : « {c['titre']} » ({c['style']}, {c['duree_s']} s, calculée en {round(calcul_s or 0)} s). "
                 f"Envoie-la à papa : fichier_joindre(\"{rel}\", \"{c['titre']}\")")
        if c.get("pour_studio"):
            ligne = (f"INSTRU PRÊTE pour le studio de papa : « {c['titre']} » ({c['style']}, {c['duree_s']} s). Elle l'attend "
                     "dans la page Studio, inutile de la joindre.")
        d.update(etat="finie", raison=None, code=0, fichier=rel)
        fiche.update(etat="prête", mp3=str(mp3), atelier=rel, calcul_s=round(calcul_s or 0, 1), taille=Path(mp3).stat().st_size)
        # (06/11, Ahmed : « dans quel dossier je trouve ses sons sur le smartphone ») une copie dans Hakim/Chansons
        try:
            sys.path.insert(0, str(ICI))
            import studio
            tel = studio.copier_au_telephone(mp3, telephone)
            fiche["telephone"] = str(tel) if tel else None
        except Exception as e:                               # noqa: BLE001 — la chanson reste prête sans la copie
            fiche["telephone_erreur"] = str(e)[:200]
    d.update(fin=fin, duree_s=round(fin - d["debut"], 1))
    fiche["fin"] = fin
    _ecrire(fiche_p, fiche)
    _ecrire(dossier / f"{tid}.json", d)
    return ligne


# ---------------------------------------------------------------------------------------------------- le calcul

def raison_arret(stop, maintenant, debut, chargement_depuis):
    """Pourquoi arrêter maintenant (None : continuer) : à la demande, chargement trop long, ou délai entier dépassé."""
    if stop:
        return "arrêtée à la demande (Ahmed ou Hakim)"
    if chargement_depuis is not None and maintenant - chargement_depuis > CHARGEMENT_MAX_S:
        return (f"bloquée au chargement des modèles (plus de {CHARGEMENT_MAX_S // 60} min) : la mémoire du Mac était sans doute pleine ; "
                "relance-la quand le Mac est plus calme")
    if maintenant - debut > DELAI_S:
        return f"trop longue (plus de {DELAI_S // 60} min)"
    return None


def _veiller(tid, dossier, debut):
    """Arrêt demandé (arreter_tache), chargement trop long ou délai dépassé : l'état est écrit, puis le processus s'arrête net."""
    while True:
        time.sleep(1)
        raison = raison_arret((dossier / f"{tid}.stop").exists(), time.time(), debut, CHARGEMENT["depuis"])
        if raison:
            print(finir(tid, dossier, raison=raison), flush=True)
            try:
                (dossier / f"{tid}.stop").unlink()
            except OSError:
                pass
            os._exit(3)


def alleger(dit):
    """Sur Apple Silicon, ACE-Step garde le DiT DEUX fois : en PyTorch float32 sur MPS (~9 Go) et converti en MLX, qui
    fait seul la diffusion. Sur 16 Go, la première chanson est morte « MPS backend out of memory » (06/11, 11,7 Go MPS
    + 10 Go MLX). La copie PyTorch du décodeur ne sert qu'aux LoRA et aux scores de paroles : on la libère."""
    import gc
    import torch
    if not (getattr(dit, "use_mlx_dit", False) and getattr(dit, "mlx_decoder", None) is not None):
        return
    dit.model.decoder = dit.model.decoder.to("meta")
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
        print(f"MPS après allègement : {torch.mps.current_allocated_memory() / 2**30:.1f} Go", flush=True)


def composer(c, sortie_dir):
    """ACE-Step : la demande → un WAV. Rend le chemin du WAV (venv du chant seulement)."""
    sys.path.insert(0, str(ACE))
    os.chdir(ACE)
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    print("PROGRESSION 1/5 chargement", flush=True)
    CHARGEMENT["depuis"] = time.time()
    dit, lm = AceStepHandler(), LLMHandler()
    msg, ok = dit.initialize_service(project_root=str(ACE), config_path="acestep-v15-turbo", device="auto")
    if not ok:
        raise RuntimeError(f"DiT : {msg}")
    alleger(dit)
    # 0.6B par défaut (06/11, mesuré) : paroles aussi nettes que le 1.7B sur le même couplet (Whisper : 4 % d'erreur
    # de mots), 2,3 Go de moins sur un Mac de 16 Go qui swappait à 30 Go pendant une chanson avec le 1.7B
    lm_modele = os.environ.get("JARVIS_CHANT_LM", "acestep-5Hz-lm-0.6B")
    msg, ok = lm.initialize(checkpoint_dir=str(ACE / "checkpoints"), lm_model_path=lm_modele, backend="mlx", device="auto")
    if not ok:
        raise RuntimeError(f"LM : {msg}")
    print(f"Chargé en {time.time() - CHARGEMENT['depuis']:.0f} s", flush=True)
    CHARGEMENT["depuis"] = None
    print("PROGRESSION 2/5 composition", flush=True)
    params = GenerationParams(caption=c["description"], lyrics=c["paroles"], duration=float(c["duree_s"]),
                              vocal_language=c["langue"], instrumental=bool(c.get("instrumental")), inference_steps=8,
                              **({"bpm": int(c["bpm"])} if c.get("bpm") else {}))
    r = generate_music(dit, lm, params, GenerationConfig(batch_size=1, audio_format="wav"), save_dir=str(sortie_dir))
    if not r.success or not r.audios:
        raise RuntimeError(f"ACE-Step : {getattr(r, 'error', None) or 'aucun son'}")
    try:
        import mlx.core as mx
        import torch
        print(f"Mémoire : MLX crête {mx.get_peak_memory() / 2**30:.1f} Go, "
              f"MPS {torch.mps.driver_allocated_memory() / 2**30:.1f} Go", flush=True)
    except (ImportError, AttributeError, RuntimeError):
        pass
    tonalite = params.keyscale or getattr(params, "cot_keyscale", "") or ""
    print(f"Tonalité : {tonalite or 'inconnue'}", flush=True)
    return r.audios[0]["path"], tonalite


def en_mp3(wav, mp3):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-codec:a", "libmp3lame",
                    "-b:a", "192k", "-metadata", "artist=Hakim", str(mp3)], check=True, timeout=300)
    return mp3


def generer(tid, dossier=None):
    dossier = Path(dossier or TACHES)
    debut = time.time()
    threading.Thread(target=_veiller, args=(tid, dossier, debut), daemon=True).start()
    c = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))["chanson"]
    print(f"Je compose « {c['titre']} » : {c['style']} → {c['description']} ; {c['duree_s']} s ; langue {c['langue']}", flush=True)
    travail = CHANSONS / f".{c['nom']}"
    travail.mkdir(parents=True, exist_ok=True)
    try:
        wav, tonalite = composer(c, travail)
        if c.get("autotune"):
            en_mp3(wav, CHANSONS / f"{c['nom']}-sans-correction.mp3")       # la prise brute, pour comparer
            print("PROGRESSION 3/5 autotune", flush=True)
            classes = autotuner(wav, travail / "autotune.wav", tonalite)
            print(f"Autotune sur la gamme {tonalite or 'chromatique'} : classes {list(classes)}", flush=True)
            wav = travail / "autotune.wav"
        print("PROGRESSION 4/5 encodage", flush=True)
        mp3 = en_mp3(wav, CHANSONS / f"{c['nom']}.mp3")
        print("PROGRESSION 5/5 prête", flush=True)
        print(finir(tid, dossier, mp3=mp3, calcul_s=time.time() - debut), flush=True)
    except Exception as e:                                       # noqa: BLE001 — toute panne finit la tâche proprement
        print(f"{type(e).__name__}: {e}", flush=True)
        print(finir(tid, dossier, erreur=f"{type(e).__name__}: {str(e)[:300]}"), flush=True)
    finally:
        shutil.rmtree(travail, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "separer":
        separer_voix(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) >= 3 and sys.argv[1] == "generer":
        generer(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
