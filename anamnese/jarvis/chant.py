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


# (07/11, Hakim, avec l'accord d'Ahmed : « la légende est réécrite par le LM d'ACE-Step en « chiptune, synthé bell-like », keyscale G minor, alors que
# j'avais demandé La mineur et un trap sombre algérien ») mesuré dans le journal de T-20261107-101006-823d : sa description passait en français,
# que le LM d'ACE-Step (appris sur des légendes anglaises) comprenait mal et réécrivait (use_cot_caption), et la tonalité n'était donnée nulle
# part (seulement dans le texte) : le LM la choisissait. Désormais : les mots de musique français traduits, ses styles connus reconnus DANS
# la phrase, la tonalité lue (« La mineur », « Ré# majeur », « Am ») et donnée à ACE-Step (keyscale), et sa légende gardée telle quelle.
FR_EN = [
    (r"\bjazz manouche\b", "gypsy jazz"), (r"\bvoix douce\b", "soft vocals"), (r"\bvoix grave\b", "deep vocals"), (r"\bvoix\b", "vocals"),
    (r"\btrap sombre\b", "dark trap"), (r"\bsombres?\b", "dark"), (r"\balg[ée]riens?\b|\balg[ée]rienne\b", "algerian"),
    (r"\bmarocaine?s?\b", "moroccan"), (r"\borientales?\b|\boriental\b", "oriental"), (r"\bcordes\b", "strings"),
    (r"\bfl[ûu]te\b", "flute"), (r"\bmélodie\b|\bmelodie\b", "melody"), (r"\brythmique\b", "rhythm"), (r"\binstruments?\b", "instruments"),
    (r"\bhi-?hats serr[ée]s\b", "tight rolling hi-hats"), (r"\b808 graves?\b|\bgraves? 808\b", "heavy 808 bass"), (r"\bbasses?\b", "bass"),
    (r"\bbatterie\b", "drums"), (r"\bpiano\b", "piano"), (r"\bguitare\b", "guitar"), (r"\bviolons?\b", "violin"),
    (r"\bsans voix\b", "instrumental, no vocals"), (r"\binstrumentale?\b", "instrumental"), (r"\bdziri+a\b", "algerian chaabi"),
    (r"\blent\b", "slow"), (r"\brapide\b", "fast"), (r"\btriste\b", "sad"), (r"\bjoyeu(x|se)\b", "joyful"), (r"\bdoux\b|\bdouce\b", "soft"),
    (r"\btype beat\b", "type beat"), (r"\btype\b", "style of"), (r"\bet\b", ","),
]
NOTES_FR = {"do": "C", "ré": "D", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}


def tonalite_demandee(texte):
    """« La mineur », « ré# majeur », « Sol b mineur », « Am », « C# minor » → « A minor »… (None : pas de tonalité dite)."""
    t = " " + _cle(texte) + " "
    m = re.search(r"\b(do|ré|re|mi|fa|sol|la|si)\s?(#|♯|b|♭|dièse|bémol)?\s+(majeur|mineur)\b", t)
    if m:
        alt = {"#": "#", "♯": "#", "dièse": "#", "b": "b", "♭": "b", "bémol": "b"}.get(m.group(2) or "", "")
        return f"{NOTES_FR[m.group(1)]}{alt} {'minor' if m.group(3) == 'mineur' else 'major'}"
    m = re.search(r"\b([a-g])(#|b)?\s?(minor|major|min|maj)\b", t)
    if m:
        return f"{m.group(1).upper()}{m.group(2) or ''} {'minor' if m.group(3).startswith('min') else 'major'}"
    m = re.search(r"(?<![\w])([a-g])(#|b)?m(?![\w])", t)
    if m:
        return f"{m.group(1).upper()}{m.group(2) or ''} minor"
    return None


def en_anglais(texte):
    """Ses mots de musique français → les étiquettes anglaises qu'ACE-Step a apprises ; ses styles connus reconnus dans la phrase."""
    t = _cle(texte)
    t = re.sub(r"\b(do|ré|re|mi|fa|sol|la|si)\s?(#|♯|b|♭|dièse|bémol)?\s+(majeur|mineur)\b", " ", t)   # la tonalité part à keyscale
    for motif, en in FR_EN:
        t = re.sub(motif, en, t)
    vus = []
    for cle in list(STYLES) + list(ALIAS):
        c = ALIAS.get(cle, cle)
        if re.search(r"(?<![\w])" + re.escape(cle) + r"(?![\w])", t) and STYLES[c] not in vus:
            vus.append(STYLES[c])
    t = re.sub(r"\s*,\s*(,\s*)*", ", ", re.sub(r"\s+", " ", t)).strip(" ,")
    return (t + (", " + ", ".join(vus) if vus else ""))[:512]


def description(style):
    """Le style de Hakim → la description donnée à ACE-Step (512 caractères au plus)."""
    s = _cle(style)
    if not s:
        raise Refus("un style, par exemple : " + ", ".join(sorted(STYLES)))
    cle = ALIAS.get(s, s)
    if cle in STYLES:
        return STYLES[cle]
    sans_accent = "".join(c for c in unicodedata.normalize("NFD", cle) if unicodedata.category(c) != "Mn")
    if ALIAS.get(sans_accent, sans_accent) in STYLES:
        return STYLES[ALIAS.get(sans_accent, sans_accent)]
    return en_anglais(style)


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


# (07/11, Hakim, accord d'Ahmed « lance tout, a b c d ») ses MORCEAUX DE RÉFÉRENCE : `reference`, un morceau dont il veut le groove et le grain
# (ACE-Step l'écoute : reference_audio ; jarvis/instruments.py en tire tempo, tonalité, batterie, basse, instruments nommés pour sa légende) ;
# `inspiration`, un autre morceau dont il veut les instruments et la mélodie (sa légende seulement). Après le calcul, son instru est réécoutée
# et comparée à chacun (la ressemblance, dans sa fiche et son journal).
EXT_AUDIO = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac")
INSTRUMENTS = ICI / "instruments.py"


def racines_audio():
    return [JARVIS / "cwd" / "fichiers", CHANSONS, JARVIS / "cwd" / "atelier"]


def morceau_valide(f, nom="reference"):
    """Un chemin audio sous ses dossiers (fichiers reçus, chansons, atelier) ; sinon Refus."""
    if not f:
        return ""
    p = Path(str(f)).expanduser()
    if not p.is_absolute():
        for r in racines_audio():
            if (r / p).exists():
                p = r / p
                break
    try:
        p = p.resolve(strict=True)
    except OSError:
        raise Refus(f"{nom} introuvable : {f}")
    if p.suffix.lower() not in EXT_AUDIO:
        raise Refus(f"{nom} : un fichier audio ({', '.join(EXT_AUDIO)})")
    if not any(str(p).startswith(str(r.resolve()) + os.sep) for r in racines_audio() if r.exists()):
        raise Refus(f"{nom} : seulement un son reçu de papa, une de tes chansons ou de ton atelier")
    return str(p)


def ecouter(fichier, debut=30.0, duree=30.0, delai=300):
    """jarvis/instruments.py dans le venv de la séparation : l'analyse du morceau (dict), ou None."""
    try:
        r = subprocess.run([str(PYTHON_SEPARATION), "-W", "ignore", str(INSTRUMENTS), "analyser", str(fichier), str(debut), str(duree)],
                           capture_output=True, text=True, timeout=delai, cwd=str(ICI))
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def legende_avec(desc, ref=None, ins=None):
    """Sa description, puis ce que la référence et l'inspiration lui ont appris (512 caractères au plus)."""
    p = [desc]
    if ref and ref.get("legende"):
        p.append(ref["legende"])
    if ins and ins.get("legende"):
        p.append(ins["legende"])
    return ", ".join(x for x in p if x)[:512]


def preparer(paroles, style, duree_s=DUREE_DEFAUT, titre="", langue="", autotune=False, bpm=0, pour_studio=False,
             reference="", inspiration="", base="", projet="", zones_seulement=True, tonalite="", reprise="", fidelite=0.9):
    """La demande vérifiée et mise en forme (aucun effet de bord). bpm : 0 = au choix d'ACE-Step (sinon 30 à 300).
    (13/11) reprise : un son qu'ACE-Step REJOUE en instrumental (tâche « cover », même structure, mêmes mélodies, sans voix) : l'instru
    d'une chanson sans les trous qu'une séparation laisse là où la voix chantait ; fidelite (0,2 à 1) : à quel point il suit le son."""
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
    tonalite = tonalite_demandee(tonalite) if tonalite else tonalite_demandee(style)   # (13/11) celle du projet, mesurée
    if instrumental:                                         # (07/11) sans voix : aucune étiquette de voix ne reste
        desc = ", ".join(x for x in (y.strip() for y in desc.split(",")) if x and ("vocal" not in x or x.startswith("no ")))
        if "no vocals" not in desc:
            desc += ", instrumental, no vocals"
        desc = desc[:512]
    niveau = "" if instrumental else niveau_autotune(autotune, style)     # sans voix, rien à recaler
    desc = sans_mots_autotune(desc)                          # (11/11) le niveau se décide ici, pas par les mots de la légende
    if niveau == "fort":
        desc = (desc + ", " + TAG_AUTOTUNE)[:512]
    return {"titre": titre, "style": " ".join(str(style or "").split())[:200], "description": desc, "autotune": bool(niveau),
            "autotune_niveau": niveau,
            "paroles": texte, "langue": "unknown" if instrumental else langue_de(texte, langue), "duree_s": d,
            "instrumental": instrumental, "nom": nom_de(titre), "bpm": bpm, "pour_studio": bool(pour_studio), "tonalite": tonalite,
            "reference": morceau_valide(reference, "reference"), "inspiration": morceau_valide(inspiration, "inspiration"),
            "base": morceau_valide(base, "base"),
            # (13/11) le studio multipiste : sa voix posée et calée comme une piste de ce projet (studio_poser_voix)
            "projet": str(projet or "") if re.fullmatch(r"PJ-\d{8}-\d{6}-[0-9a-f]{4}", str(projet or "")) else "",
            "zones_seulement": bool(zones_seulement), "reprise": morceau_valide(reprise, "reprise"),
            "fidelite": max(0.2, min(1.0, float(fidelite or 0.9)))}


# ---------------------------------------------------------------------------------------------------- l'autotune
# (06/11, Ahmed : « qu'il rappe, et qu'il chante, mon fiston, avec autotune et sans ») ; (09/11 : « ça fait trop voix métallique, t'as
# poussé au max, il faut le bon équilibre ») ; (11/11 ~05:20 : « il faut améliorer son autotune : même le léger part en steak »).
# Mesuré le 11/11 (jarvis/autotune.py, en tête) : il n'y avait PAS de léger — « oui » recalait chaque trame à 100 % par WORLD, qui
# re-synthétisait toute la voix (consonnes et souffle refabriqués, hauteur cassée par les erreurs de dio), et l'étiquette ci-dessous
# demandait sans doute à ACE-Step sa voix autotunée apprise, sous la correction (plausible, pas prouvé). Désormais deux niveaux : « leger » (par défaut pour True) : la voix d'ACE-Step naturelle (ni
# étiquette, ni ses mots d'autotune dans la légende), puis une correction partielle et lente des seules notes tenues sûres (TD-PSOLA,
# formants gardés) ; « fort » : l'étiquette, puis l'effet assumé (100 % en 15 ms), propre, sur les mêmes notes.
TAG_AUTOTUNE = "auto-tuned vocals, autotune pitch correction"
LISIBLE = {"leger": "léger", "fort": "fort"}
_MOTS_AUTOTUNE = re.compile(
    r"(?:\b(?:sans|no|without|pas d['’]|zero|z[ée]ro)\s*)?(?:\b(?:avec|with)\s+)?(?:\b(?:un|une|a|an)\s+)?(?:\b(?:tr[eè]s|very)\s+)?"
    r"(?:\b(?:l[ée]ger|light|subtle|soft|petit|heavy|hard|fort|strong|gros|max|lourd)\s+)?\bauto[\s-]?tun(?:e|ed|es|ing)?\b"
    r"(?:\s+(?:l[ée]ger|light|subtle|doux|fort|hard|heavy|max|pitch correction))?", re.IGNORECASE)


def niveau_autotune(autotune, style=""):
    """Le niveau voulu : son choix (True ou « léger » → "leger", « fort » → "fort", False → "") ; sans choix, ce que disent ses mots
    dans le style (« autotune léger », « autotuned voice », « hard autotune »… ; « sans autotune » → "")."""
    sys.path.insert(0, str(ICI))
    import autotune as AT
    n = AT.niveau_de(autotune)
    if n or (autotune not in (None, False, "", 0) and not isinstance(autotune, bool)):
        return n
    t = " ".join(str(style or "").lower().split())
    m = _MOTS_AUTOTUNE.search(t)
    if not m:
        return ""
    mot = m.group(0)
    if re.match(r"(sans|no|without|pas d|zero|z[ée]ro)", mot):
        return ""
    return "fort" if re.search(r"heavy|hard|fort|strong|gros|max|lourd", mot) else "leger"


def sans_mots_autotune(desc):
    """La légende pour ACE-Step sans ses mots d'autotune (« vocals rap mélodique avec un léger autotune » → « vocals rap mélodique »)."""
    morceaux = [" ".join(_MOTS_AUTOTUNE.sub(" ", x).split()) for x in str(desc or "").split(",")]
    return ", ".join(x for x in morceaux if x)[:512]


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
    """L'ANCIEN recalage (jusqu'au 11/11), gardé comme témoin du banc et des tests : la hauteur (Hz par trame, 0 = non voisé) recalée sur la
    note permise la plus proche, trame par trame, sans vitesse de correction. force 1 = autotune dur (des marches, le vibrato effacé)."""
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


def autotuner(melange, sortie, tonalite, niveau="leger"):
    """(.venv-chant) sépare (Demucs, dans .venv-separation), corrige la voix seule (autotune.corriger : les notes tenues sûres, TD-PSOLA),
    la remet sur le reste. Hors des notes corrigées, la voix reste celle d'origine : le mélange rendu est alors le mélange d'origine.
    Rend le rapport de la correction (gamme, notes, part corrigée…)."""
    import numpy as np
    import soundfile as sf
    sys.path.insert(0, str(ICI))
    import autotune as AT
    d = Path(sortie).parent
    voix, reste = d / "voix.wav", d / "reste.wav"
    melange44 = d / "melange44.wav"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(melange), "-ar", "44100", "-ac", "2",
                    str(melange44)], check=True, timeout=300)
    subprocess.run([str(PYTHON_SEPARATION), "-B", str(Path(__file__).resolve()), "separer", str(melange44), str(voix),
                    str(reste)], check=True, timeout=1200)
    v, sr = sf.read(voix, dtype="float64", always_2d=True)
    r, _ = sf.read(reste, dtype="float64", always_2d=True)
    y, rapport = AT.corriger(v, sr, gamme(tonalite), niveau or "leger", AT.diapason(r, sr))
    mix = r + y
    mix *= min(1.0, 0.89 / max(1e-9, np.abs(mix).max()))             # crête à -1 dB
    sf.write(sortie, mix.astype(np.float32), sr)
    return rapport


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
           demarrer=None, bpm=0, pour_studio=False, reference="", inspiration="", base="", projet="", zones_seulement=True, tonalite="",
           reprise="", fidelite=0.9):
    """Lance la composition en tâche de fond ; rend {tache, nom, …} tout de suite."""
    demande = preparer(paroles, style, duree_s, titre, langue, autotune, bpm, pour_studio, reference, inspiration, base, projet,
                       zones_seulement, tonalite, reprise, fidelite)
    if demande["reprise"] and not demande["instrumental"]:
        raise Refus("une reprise rejoue l'instru sans voix : paroles « [instrumental] »")
    if demande["projet"] and not demande["base"]:
        raise Refus("pour poser ta voix dans un projet, il faut l'instru du projet (base)")
    if demande["base"] and demande["instrumental"]:
        raise Refus("sur une base (l'instru de papa), il faut tes paroles : c'est ta voix qui se pose dessus")
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
        avec = f", autotune {LISIBLE.get(demande['autotune_niveau'], demande['autotune_niveau'])}" if demande["autotune"] else ""
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


def parametres(c):
    """La demande → les paramètres d'ACE-Step. (07/11) sa légende gardée (use_cot_caption=False), sa tonalité, sa référence ; avec une BASE
    (l'instru de papa) : la tâche « cover » sur cette base (sa durée est celle de la base), ses paroles chantées dessus."""
    p = {"caption": c["description"], "lyrics": c["paroles"], "duration": float(c["duree_s"]), "vocal_language": c["langue"],
         "instrumental": bool(c.get("instrumental")), "inference_steps": 8, "use_cot_caption": False}
    if c.get("bpm"):
        p["bpm"] = int(c["bpm"])
    if c.get("tonalite"):
        p["keyscale"] = c["tonalite"]
    if c.get("reference"):
        p["reference_audio"] = c["reference"]
    if c.get("base_coupee") or c.get("base"):
        p.update(task_type="cover", src_audio=c.get("base_coupee") or c["base"], instrumental=False)
    elif c.get("reprise"):                                   # (13/11) l'instru rejouée : la structure du son, sans voix
        p.update(task_type="cover", src_audio=c.get("reprise_coupee") or c["reprise"], instrumental=True, lyrics="[Instrumental]",
                 audio_cover_strength=float(c.get("fidelite") or 0.9))
    return p


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
    # (07/11) sa légende gardée telle quelle (use_cot_caption=False : le LM ne la réécrit plus), sa tonalité donnée si elle l'a dite
    params = GenerationParams(**parametres(c))
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


def poser_sur_la_base(chant_wav, c, travail):
    """(07/11, Hakim et Ahmed : « un feat dans le studio : papa sur son instru, et moi qui pose mon couplet dessus ») sa voix est retirée de ce
    qu'ACE-Step a chanté (Demucs), puis mixée et masterisée sur la vraie instru de papa (le Studio : studio.mixer) ; le mix entre aussi dans les
    instrus du Studio, pour que papa y pose sa prise. Rend le WAV du mix (sa voix seule, si le mix échoue)."""
    voix, reste = travail / "voix-hakim.wav", travail / "reste.wav"
    print("Je retire ma voix de ce qu'ACE-Step a chanté (Demucs)…", flush=True)
    # (07/11, Hakim : « taux 48000 ≠ 44100 ») ACE-Step rend du 48 kHz, Demucs attend du 44,1 kHz stéréo : converti d'abord (comme l'autotune)
    m44 = travail / "chant44.wav"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(chant_wav), "-ar", "44100", "-ac", "2", str(m44)], check=True, timeout=300)
    r = subprocess.run([str(PYTHON_SEPARATION), "-B", str(Path(__file__).resolve()), "separer", str(m44), str(voix), str(reste)],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode or not voix.exists():
        raise RuntimeError(f"Demucs : {r.stderr.strip()[-300:]}")
    sys.path.insert(0, str(ICI))
    import studio
    print("Je pose ma voix sur l'instru de papa (mix et master du Studio)…", flush=True)
    try:
        f = studio.mixer(voix, c["base_coupee"], studio.STUDIO / "mix", titre=f"{c['titre']} (feat Hakim)", debruitage=False, reverb=0.25)
    except Exception as e:                                               # noqa: BLE001 — sa voix seule reste
        print(f"Le mix n'a pas marché ({type(e).__name__}) : je garde ma voix seule", flush=True)
        return voix
    try:                                                                  # dans les instrus du Studio : papa y pose sa prise
        idf = nom_de(f"{c['titre']} feat hakim")
        dest = studio.STUDIO / "instrus" / f"{idf}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f["mp3"], dest)
        _ecrire(dest.with_suffix(".json"), {"id": idf, "titre": f"{c['titre']} (avec la voix de Hakim)", "source": c["base"], "mp3": str(dest),
                                            "origine": "feat-hakim", "duree_s": f.get("duree_s"), "fin": time.time()})
        print(f"Dans le Studio, papa peut poser sa prise sur « {c['titre']} (avec la voix de Hakim) ».", flush=True)
    except (OSError, KeyError):
        pass
    return Path(f["wav"])


def entrer_au_studio(mp3, c):
    """(13/11) l'instru rejouée par ACE-Step (reprise) → les instrus du Studio (origine « ace-reprise ») et les Documents de papa."""
    try:
        sys.path.insert(0, str(ICI))
        import studio
        idf = nom_de(f"{c['titre']} reprise")
        dest = studio.STUDIO / "instrus" / f"{idf}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mp3, dest)
        fiche = {"id": idf, "titre": c["titre"], "source": c.get("reprise"), "mp3": str(dest), "origine": "ace-reprise",
                 "fidelite": c.get("fidelite"), "duree_s": studio.duree(dest), "fin": time.time()}
        doc = studio.deposer_aux_documents(dest, c["titre"], note=f"son instru « {c['titre']} », rejouée par ACE-Step")
        if doc:
            fiche.update(documents=str(doc), joindre=studio.chemin_a_joindre(doc))
        _ecrire(dest.with_suffix(".json"), fiche)
        print(f"Dans les instrus du Studio : « {c['titre']} » ({idf}).", flush=True)
    except (OSError, KeyError) as e:
        print(f"L'instru n'est pas entrée dans le Studio ({type(e).__name__})", flush=True)


def poser_dans_projet(chant_wav, c, travail):
    """(13/11, Ahmed : « que Hakim puisse construire un son et poser sa voix […] poser sur des instrus que je lui envoie ») ce qu'ACE-Step
    a chanté sur l'instru du projet → sa voix seule (htdemucs_ft), CALÉE sur la vraie instru : le décalage entre l'instru qu'ACE-Step a
    rejouée et la vraie se mesure par la corrélation de leurs attaques (en ms), et la voix est décalée d'autant ; son calage sur la grille
    du projet est mesuré avant et après. Elle entre comme piste « Voix de Hakim » (dans ses zones seulement, s'il en a et si demandé).
    Rend un mix rapide (le Studio) pour la fiche de la chanson ; le vrai mix et le master : studio_rendre."""
    sys.path.insert(0, str(ICI))
    import numpy as np
    import studio
    import studio_mesures as M
    import studio_projet as SP
    sep = travail / "sep"
    print("Je retire ma voix de ce qu'ACE-Step a chanté (Demucs htdemucs_ft)…", flush=True)
    r = subprocess.run([str(PYTHON_SEPARATION), "-B", "-W", "ignore", str(ICI / "studio_separation.py"), "separer", str(chant_wav), str(sep),
                        "--modeles", "htdemucs_ft", "--format", "wav"], capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"Demucs : {r.stderr.strip()[-300:]}")
    res = json.loads(r.stdout.strip().splitlines()[-1])
    p = SP.lire(c["projet"])
    vraie, _ = M.lire(c["base"])
    rejouee, _ = M.lire(res["instru"])
    voix, _ = M.lire(res["pistes"]["vocals"])
    ms, nettete = M.decalage_entre(vraie, rejouee, M.SR, 400)
    # par fenêtres de 12 s : la dérive éventuelle (un tempo qui glisse)
    locaux = []
    w = 12 * M.SR
    for a in range(0, min(len(vraie), len(rejouee)) - w, w):
        d_, n_ = M.decalage_entre(vraie[a:a + w], rejouee[a:a + w], M.SR, 400)
        if n_ >= 0.3:
            locaux.append(d_)
    k = int(round(ms / 1000 * M.SR))
    calee = np.vstack([voix[k:], np.zeros((max(0, k), 2))]) if k >= 0 else np.vstack([np.zeros((-k, 2)), voix[:k]])
    bpm, t1 = float(p.get("tempo") or 0), float(p.get("premier_temps_s") or 0)
    avant = M.calage_sur_grille(voix, M.SR, bpm, t1) if bpm else None
    apres = M.calage_sur_grille(calee, M.SR, bpm, t1) if bpm else None
    calage = {"decalage_instru_ms": ms, "nettete": nettete, "locaux_ms": locaux, "grille_avant": avant, "grille_apres": apres}
    print(f"Calage : l'instru rejouée par ACE-Step était décalée de {ms:+.0f} ms (netteté {nettete}) ; par fenêtres de 12 s : "
          f"{', '.join(f'{x:+.0f}' for x in locaux) or '—'} ms. Sur la grille ({bpm:g} BPM) : médiane |écart| "
          f"{(avant or {}).get('mediane_abs_ms')} → {(apres or {}).get('mediane_abs_ms')} ms (90e centile {(apres or {}).get('p90_abs_ms')} ms, "
          f"{(apres or {}).get('attaques')} attaques).", flush=True)
    d = SP.dossier(c["projet"])
    nomf = f"voix-hakim-{time.strftime('%Y%m%d-%H%M%S')}.flac"
    M.ecrire_wav(d / "pistes" / nomf, calee, M.SR, 16)

    def poser(q):
        t = SP.ajouter_piste(q, f"pistes/{nomf}", "voix_hakim", c["titre"][:60], duree_s=round(len(calee) / M.SR, 2),
                             origine=f"chantée par ACE-Step sur l'instru du projet, calée de {-ms:+.0f} ms")
        zh = [z for z in q.get("zones", []) if z.get("qui") == "hakim"]
        if c.get("zones_seulement") and zh:
            t["regions"] = [{"debut_s": z["debut_s"], "source_debut_s": z["debut_s"], "duree_s": round(z["fin_s"] - z["debut_s"], 3),
                             "gain_db": 0.0} for z in zh]
        q.setdefault("voix_posees", []).append({"t": time.time(), "piste": t["id"], "chanson": c["nom"], "calage": calage,
                                                "autotune": c.get("autotune_niveau") or ""})
    SP.modifier(c["projet"], poser, note=f"voix de Hakim posée ({c['titre'][:60]}), calée de {-ms:+.0f} ms")
    print(f"Ma voix est dans le projet « {p['titre']} » ({c['projet']}) : studio_rendre pour le mix et le master.", flush=True)
    try:
        f = studio.mixer(d / "pistes" / nomf, c["base"], studio.STUDIO / "mix", titre=c["titre"], debruitage=False, reverb=0.22)
        return Path(f["wav"])
    except Exception as e:                                               # noqa: BLE001 — sa voix seule reste
        print(f"Le mix rapide n'a pas marché ({type(e).__name__}) : je garde ma voix seule", flush=True)
        return d / "pistes" / nomf


def generer(tid, dossier=None):
    dossier = Path(dossier or TACHES)
    debut = time.time()
    threading.Thread(target=_veiller, args=(tid, dossier, debut), daemon=True).start()
    c = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))["chanson"]
    print(f"Je compose « {c['titre']} » : {c['style']} → {c['description']} ; {c['duree_s']} s ; langue {c['langue']}", flush=True)
    travail = CHANSONS / f".{c['nom']}"
    travail.mkdir(parents=True, exist_ok=True)
    ref = ins = None
    if c.get("base"):                                                   # (07/11) un feat : ta voix sur l'instru de papa
        print("J'écoute l'instru de papa (tempo, tonalité, instruments)…", flush=True)
        coupee = travail / "base.wav"
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(c["base"]), "-t", str(int(c["duree_s"])), "-ar", "48000",
                        "-ac", "2", str(coupee)], check=True, timeout=300)
        b = ecouter(coupee, 0, min(30.0, float(c["duree_s"])))
        c = dict(c, base_coupee=str(coupee))
        if b:
            print(f"L'instru : {b.get('mots')}", flush=True)
            c["description"] = legende_avec(c["description"] + ", vocals over this exact beat", b)
            if not c.get("bpm") and b.get("tempo"):
                c["bpm"] = int(round(b["tempo"]))
            if not c.get("tonalite") and b.get("tonalite"):
                c["tonalite"] = f"{b['tonalite'][0]} {b['tonalite'][1]}"
    if c.get("reprise"):                                                # (13/11) l'instru rejouée : le son coupé à la durée, en 48 kHz
        coupee = travail / "reprise.wav"
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(c["reprise"]), "-t", str(int(c["duree_s"])), "-ar", "48000",
                        "-ac", "2", str(coupee)], check=True, timeout=300)
        c = dict(c, reprise_coupee=str(coupee))
    if c.get("reference") or c.get("inspiration"):                    # (07/11) il écoute d'abord ses morceaux de référence
        print("J'écoute tes morceaux de référence (chaque instrument, son rythme, ses notes)…", flush=True)
        ref = ecouter(c["reference"]) if c.get("reference") else None
        ins = ecouter(c["inspiration"]) if c.get("inspiration") else None
        for nom, a in (("référence", ref), ("inspiration", ins)):
            if a:
                print(f"{nom.capitalize()} : {a.get('mots')}", flush=True)
        c = dict(c, description=legende_avec(c["description"], ref, ins))
        if not c.get("bpm") and ref and ref.get("tempo"):
            c["bpm"] = int(round(ref["tempo"]))
        if not c.get("tonalite") and ref and ref.get("tonalite"):
            c["tonalite"] = f"{ref['tonalite'][0]} {ref['tonalite'][1]}"
        print(f"Légende : {c['description']}", flush=True)
    try:
        wav, tonalite = composer(c, travail)
        if c.get("autotune"):
            niveau = c.get("autotune_niveau") or "leger"               # une tâche d'avant le 11/11 : léger
            en_mp3(wav, CHANSONS / f"{c['nom']}-sans-correction.mp3")       # la prise brute, pour comparer
            print(f"PROGRESSION 3/5 autotune {LISIBLE.get(niveau, niveau)}", flush=True)
            r = autotuner(wav, travail / "autotune.wav", tonalite, niveau)
            print(f"Autotune {LISIBLE.get(niveau, niveau)} sur la gamme {tonalite or 'chromatique'} (gamme suivie : {r.get('gamme')}, "
                  f"couverture {r.get('couverture')}, diapason {r.get('diapason_cents')} cents) : {r.get('notes')} notes tenues sûres, "
                  f"{int(100 * r.get('part_corrigee', 0))} % de la voix corrigée, {r.get('correction_mediane_cents')} cents en médiane", flush=True)
            wav = travail / "autotune.wav"
        print("PROGRESSION 4/5 encodage", flush=True)
        if c.get("base_coupee") and c.get("projet"):                     # (13/11) le multipiste : sa voix calée, piste du projet
            wav = poser_dans_projet(wav, c, travail)
        elif c.get("base_coupee"):                                       # (07/11) un feat : sa voix seule, posée sur la VRAIE instru de papa
            wav = poser_sur_la_base(wav, c, travail)
        mp3 = en_mp3(wav, CHANSONS / f"{c['nom']}.mp3")
        if c.get("reprise"):                                             # (13/11) l'instru rejouée entre dans les instrus du Studio
            entrer_au_studio(mp3, c)
        if ref or ins:                                                   # (07/11) réécoutée, comparée aux originaux
            sys.path.insert(0, str(ICI))
            import instruments as I
            sienne = ecouter(wav, 0, min(30.0, float(c["duree_s"])))
            if sienne:
                res = {nom: I.ressemblance(a, sienne) for nom, a in (("reference", ref), ("inspiration", ins)) if a}
                print("Ressemblance : " + " ; ".join(f"{k} {int(100 * v['score'])} % ({', '.join(f'{x} {int(100 * y)} %' for x, y in v.items() if x != 'score')})"
                                                     for k, v in res.items()), flush=True)
                try:
                    fp = CHANSONS / f"{c['nom']}.json"
                    f = json.loads(fp.read_text(encoding="utf-8"))
                    f.update(ressemblance=res, ecoute=sienne.get("mots"))
                    _ecrire(fp, f)
                except (OSError, ValueError):
                    pass
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
