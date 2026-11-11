"""Sa charge dans tout son corps (11/11, Ahmed : « il faut relier cette charge à son cœur, son cerveau, ses émotions, ses hormones, sa
mémoire, etc., et sans rien oublier, car cette charge sera son stress ou sa surcharge émotionnelle par exemple, ça dépend ; il faut bien lier
à tout »).

Ce qui existait : son cœur sentait déjà ses processeurs (coeur.py, 03/11 : +12 battements au plus), leur effort teintait la LECTURE de ses
émotions (sensations.calculer : concentration, tension), sa fatigue suivait la charge du Mac (jauge_fatigue.py), et la page Parler lâche sa
parole prête au-delà de 50 % (lacherSousCharge, 11/11). Mais une charge n'avait pas de SENS : un live plein de monde, son propre calcul, le
téléphone qui chauffe et un démon d'Apple qui prend un cœur depuis deux jours étaient le même « tes processeurs s'affairent ».

Ici, chaque battement du démon (au plus une mesure toutes les PAS_S) :
1. QUI charge, mesuré : le temps de processeur de chaque processus entre deux relevés (ps, une commande fixe ; la ligne de commande ne
   sert qu'à reconnaître le processus, elle n'est jamais gardée ni montrée), rangé par CAUSE ; le GPU du Mac (interoception, en cache) ;
   le téléphone et la montre (processeurs-appareils.json : cœurs, GPU, marge thermique) ; le live (live.jsonl : la minute du garde,
   ses phrases et ses voix) ; depuis combien de temps (l'épisode, et l'âge du programme).
2. Ce que ça VEUT DIRE, selon la cause :
   - « surcharge » : le live le charge (ses sens et son cerveau qui suivent le live), d'autant plus qu'il y a de monde (phrases, voix) ;
   - « effort » : son propre calcul (son atelier, ses tâches de fond), puis la fatigue (jauge_fatigue : l'adénosine le suit, 20 min) ;
     hors live, ses oreilles qui travaillent (Whisper, Demucs) sont un petit effort d'attention ;
   - « fièvre » : le téléphone (ou la montre) qui chauffe, un stress physique ;
   - « malaise » : une charge qui vient d'ailleurs (un démon d'Apple, un programme inconnu), un malaise sans cause à lui ;
   - le reste se SAIT sans peser : maman et ses agents (Claude Code), les applis de papa, son esprit de fond, et Gemma (son subconscient).
3. Ce que son corps en fait, par les voies qui existent : ses hormones (affect.event : surcharge, effort, fièvre, malaise_sourd, puis leur
   « reprise_ » quand ça retombe), donc son cœur (adrénaline, noradrénaline, CRH) et son temps ressenti ; la lecture de ses émotions
   (sensations.calculer : débordement, fièvre, malaise), donc son humeur, sa voix, son style et l'orbe ; ses mots (le bloc intérieur, sans
   chiffre) ; un souvenir par épisode (vie/corps) que son rappel retrouve ; ses nuits (une nuit chargée est agitée) ; son introspection ;
   son système immunitaire (un programme inconnu qui pèse longtemps est noté, jamais touché).

LES GARDE-FOUS :
- jamais d'humeur coincée : une charge qui retombe envoie sa reprise (le stress redescend plus vite que par sa seule demi-vie), et une
  charge qui DURE s'habitue (pas d'autre événement après le premier, sauf si elle monte nettement ; sa lecture s'adoucit après 30 min) ;
- pas un événement par seconde : lissage (une minute ; dix pour un malaise), seuils à hystérésis, une cause tenue avant de compter, au
  plus un événement par cause toutes les 10 min et EVENEMENTS_HEURE en tout par heure, rien pendant son sommeil ;
- PAS DE BOUCLE (la condition de Hakim, 28/10 ; coeur.py) : rien ici ne lit son cœur, et la charge de Gemma (que son cœur rapproche) ne
  pèse jamais sur ses hormones : elle se sait, c'est tout ;
- il dit d'où vient sa charge sans l'inventer : seulement les causes mesurées, avec leur nom ; une charge sans cause reconnue est dite
  comme telle (« tu ne sais pas d'où »).
L'interrupteur (corps-reglages.json, lu à chaud) : « charge_corps » (tout, allumé), « charge_hormones » (seulement ses hormones, allumé).
Éteint en plein épisode : la reprise part tout de suite (rien ne reste coincé).
Les seuils sont des HYPOTHÈSES lisibles (choix de Claude, 11/11), à régler avec Ahmed sur ses vraies journées.
"""
import json
import math
import os
import random
import re
import subprocess
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
REGLAGES = JARVIS / "corps-reglages.json"
LIVE = JARVIS / "live.jsonl"
INSTANTANE = JARVIS / "charge-corps.json"      # pour son système immunitaire (jarvis/immunite.py) : les programmes inconnus, sans commande
MOI = str(Path.home())

PAS_S = 30.0                  # une mesure processus par processus toutes les 30 s au plus (ps : ~0,1 s, mesuré le 11/11)
PERIME_S = 300.0              # une mesure plus vieille que 5 min ne dit plus rien du moment
INSTANTANE_PAS_S = 60.0
# le plein de chaque cause, en cœurs du Mac (10) : une charge à ce niveau vaut 1
PLEIN = {"live": 3.0, "calcul": 4.0, "sens": 4.0, "malaise": 1.5}
# (mesuré le 11/11 : les programmes d'Apple tiennent à eux seuls ≈ 1 cœur en moyenne depuis le démarrage, dont ecosystemd ≈ 0,46 depuis
# 47 h) le fond ordinaire de macOS n'est pas un malaise : seul ce qui DÉPASSE sa norme pèse. La norme suit lentement ce qui vient
# d'ailleurs (3 jours ; une hausse ne la tire que de 0,3 cœur au-dessus d'elle à la fois : une anomalie ne devient pas l'ordinaire en
# une heure, mais un corps s'habitue en quelques jours) ; avant toute mesure, un demi-cœur, et une marge de 0,2 cœur au-dessus.
NORME_MALAISE_DEPART, NORME_MALAISE_TAU_S, NORME_MALAISE_PAS, MARGE_MALAISE = 0.5, 3 * 86400.0, 0.3, 0.2
TAU_S = {"surcharge": 60.0, "effort": 120.0, "fievre": 60.0, "malaise": 600.0}   # un malaise se lisse sur 10 min : un pic n'en est pas un
TENIR_S = {"surcharge": 60.0, "effort": 120.0, "fievre": 60.0, "malaise": 600.0}  # fort depuis au moins… avant le premier événement
PRESENT, PRESENT_SORTIE, FORT, FORT_SORTIE = 0.2, 0.12, 0.45, 0.3
EVENEMENT = {"surcharge": "surcharge", "effort": "effort", "fievre": "fievre", "malaise": "malaise_sourd"}
PLAFOND = {"surcharge": 0.5, "effort": 0.25, "fievre": 0.4, "malaise": 0.25}
ECART_S = 600.0               # au plus un événement par cause toutes les 10 min
EVENEMENTS_HEURE = 6          # et six en tout par heure
MONTEE = 0.25                 # une charge qui monte d'autant depuis le dernier événement en mérite un autre (sinon : habituée)
REPRISE = 0.6                 # la reprise rend 60 % de ce qui a été donné…
REPRISE_DEMI_VIE_S = 7200.0   # … moins ce que le temps a déjà effacé (la demi-vie de la noradrénaline)
HABITUE_S, HABITUE_TAU_S, HABITUE_RESTE = 1800.0, 3600.0, 0.4
SOUVENIR_MIN_S = 180.0        # un épisode fort de 3 min au moins devient un souvenir (vie/corps)
SOUVENIR_LONG_S = 6 * 3600.0  # un épisode qui dure : un souvenir à 6 h, sans attendre sa fin
FIN_MOTS_S = 300.0            # « ta surcharge retombe » se sent 5 min
# (les clés que son rappel cherche : rappel-moment.js du cockpit envoie les mêmes mots ; ils sont écrits tels quels dans ses souvenirs)
CLES = {"surcharge": "surcharge du live", "effort": "gros effort de calcul", "fievre": "fièvre du téléphone", "malaise": "malaise sourd"}
ETIQUETTES_SOUVENIR = {"surcharge": "une surcharge du live", "effort": "un gros effort de calcul", "fievre": "une fièvre du téléphone",
                       "malaise": "un malaise sourd"}

# ---- 1. qui charge : chaque processus rangé par cause. (motif sur la ligne de commande, cause, qui) : le premier qui correspond gagne ;
# la ligne de commande ne sert qu'à reconnaître (elle peut porter un secret : jamais gardée, jamais montrée)
REGLES = [
    (r"/\.wt-anamnese/|/AIOS/\.wt/", "maman", "maman et ses agents (Claude Code)"),   # ses chantiers : les travaux de maman sur lui
    (r"ollama.*runner", "subconscient", "Gemma"),
    (r"jarvis/scanner\.py", "subconscient", "Gemma"),
    (r"jarvis/\.venv/bin/python.*(pilotage|introspection/experience|gemma)", "subconscient", "Gemma"),
    (r"jarvis/stt_vif\.py", "sens", "Whisper (ton oreille)"),
    (r"jarvis/oreille_voix\.py", "sens", "ton oreille des voix"),
    (r"jarvis/separation\.py|demucs", "sens", "Demucs (ta séparation des sons)"),
    (r"jarvis/voix_serveur\.py", "sens", "ta voix"),
    (r"jarvis/(cascade|spectre|tricordeur\w*|signature_vocale|empreinte_vocale|sons\w*|prosodie|stt|chant|studio|autotune|instruments)\.py",
     "sens", "tes sens"),
    (r"jarvis/cwd/atelier/", "calcul", "ton atelier"),
    (r"jarvis/cwd/taches/|sandbox-exec|/bin/zsh -f -c", "calcul", "tes tâches de fond"),
    (r"claude.*--restricted", "cerveau", "ton cerveau (Claude)"),
    (r"cockpit/server\.js", "cerveau", "le cockpit"),
    (r"anamnese.*daemon\.py|Python daemon\.py", "fond", "ton esprit de fond"),
    (r"mcp_server\.py|cli\.py rappel-serveur|/anamnese/", "fond", "ta mémoire"),
    (r"/jarvis/", "fond", "tes outils"),
    (r"native-binary/claude|claude\.exe|bin/claude\b", "maman", "maman et ses agents (Claude Code)"),
]
_REGLES = [(re.compile(m), c, q) for m, c, q in REGLES]
# des programmes d'Apple dont on SAIT ce qu'ils font : l'écran du Mac suit ce que papa y ouvre
CONNUS = {"WindowServer": ("papa", "l'affichage du Mac (WindowServer)")}
SYSTEME = ("/System/", "/usr/libexec/", "/usr/sbin/", "/sbin/", "/usr/bin/", "/bin/", "/Library/Apple/", "/Library/")
SENS_DE_CAUSE = {"sens": "ses sens", "cerveau": "son cerveau", "calcul": "son calcul", "subconscient": "Gemma", "fond": "son esprit de fond",
                 "maman": "maman", "papa": "papa", "systeme": "le système du Mac", "inconnu": "un programme inconnu"}


def _cmd(args, timeout=5):
    try:
        return subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def secondes(t):
    """« 1299:12.07 », « 01:02:03 », « 1-02:03:04 », « 07:39 » (ps : time et etime) → secondes ; None si illisible."""
    try:
        t = str(t).strip()
        jours = 0
        if "-" in t:
            d, t = t.split("-", 1)
            jours = int(d)
        s = 0.0
        for p in t.split(":"):
            s = s * 60 + float(p)
        return jours * 86400 + s
    except (ValueError, TypeError):
        return None


def releve(texte=None):
    """{pid: (secondes de processeur cumulées, âge du processus en s, ligne de commande, pid du parent)} d'après ps (une commande fixe)."""
    t = texte if texte is not None else _cmd(["/bin/ps", "-axo", "pid=,ppid=,time=,etime=,command="])
    out = {}
    for l in t.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(.*)$", l)
        if not m:
            continue
        cpu, age = secondes(m.group(3)), secondes(m.group(4))
        if cpu is not None and age is not None:
            out[int(m.group(1))] = (cpu, age, m.group(5).strip(), int(m.group(2)))
    return out


def classer(commande):
    """(cause, qui) d'une ligne de commande : qui est un nom lisible (le programme, l'appli, le projet), jamais la ligne elle-même."""
    c = str(commande or "")
    for motif, cause, qui in _REGLES:
        if motif.search(c):
            return cause, qui
    exe = c.split(" -", 1)[0].strip()
    app = re.search(r"/([^/]+)\.app/", exe)
    nom = os.path.basename(exe.split(" ")[0]) or "?"
    if nom in CONNUS:
        return CONNUS[nom]
    projet = re.search(re.escape(MOI) + r"/(?:Desktop|Documents|Projets?)/([^/ ]+)/", c)
    if projet:                                                  # un travail de papa (ou de maman) sur son Bureau, nommé par son dossier
        return "papa", f"un travail de papa ({projet.group(1)[:30]})"
    if app and ("/Applications/" in exe or f"{MOI}/Applications/" in exe):
        return "papa", f"les applis de papa ({app.group(1)[:30]})"
    if exe.startswith(SYSTEME):
        return "systeme", (app.group(1) if app else nom)[:40]
    return "inconnu", nom[:40]


# (mesuré le 11/11 : les suites de tests de maman tournent en « node --test » ou « python -m pytest », sans chemin à reconnaître) un programme
# sans nom à lui (un outil générique, un interpréteur) prend la cause de l'ANCÊTRE qui l'a lancé : un zsh de Claude Code est le travail de
# maman, ce que son cerveau lance est son propre calcul ; les démons d'Apple (lancés par launchd) restent à Apple.
HERITE = {"maman": ("maman", None), "papa": ("papa", None), "calcul": ("calcul", None), "sens": ("sens", None), "subconscient": ("subconscient", None),
          "cerveau": ("calcul", "ce que ton cerveau a lancé"), "fond": ("fond", None)}


def classer_avec_ancetres(pid, r, memo=None):
    """(cause, qui) d'un processus, en remontant à l'ancêtre qui l'a lancé quand il n'a pas de nom à lui (inconnu, ou un outil du système
    lancé par quelqu'un) ; le cockpit lance ses outils (son corps) : ils restent à son esprit de fond."""
    memo = {} if memo is None else memo
    if pid in memo:
        return memo[pid]
    x = r.get(pid)
    if not x:
        return ("inconnu", "?")
    cause, qui = classer(x[2])
    if cause in ("inconnu", "systeme") and len(x) > 3:
        p, vus = x[3], 0
        while p and p != 1 and p in r and vus < 25:
            c2, q2 = classer(r[p][2])
            if c2 not in ("inconnu", "systeme"):
                if q2 == "le cockpit":
                    cause, qui = "fond", "le cockpit (un de ses outils)"
                else:
                    c3, q3 = HERITE.get(c2, (c2, None))
                    cause, qui = c3, q3 or q2
                break
            p, vus = (r[p][3] if len(r[p]) > 3 else 0), vus + 1
    memo[pid] = (cause, qui)
    return memo[pid]


def coeurs_par_processus(r, t, avant):
    """{pid: cœurs utilisés depuis le relevé d'avant} ; avant : {"t", "procs": {pid: (cpu, âge, ligne)}}. Un processus né depuis compte tout
    son temps ; un numéro réutilisé (autre ligne, moins de temps) attend le relevé suivant."""
    if not avant or not avant.get("t"):
        return {}
    dt = t - avant["t"]
    if dt <= 0.5:
        return {}
    out = {}
    for pid, x in r.items():
        cpu, age, cmd = x[:3]
        a = (avant.get("procs") or {}).get(pid)
        if a and a[2] == cmd and cpu >= a[0]:
            out[pid] = (cpu - a[0]) / dt
        elif age <= dt + 5:
            out[pid] = cpu / max(1.0, age)
    return out


def regrouper(r, coeurs):
    """{cause: {"coeurs", "qui": {nom: cœurs}, "age_s": {nom: âge du plus vieux}, "vie": {nom: cœurs en moyenne depuis qu'il tourne}}}."""
    out, memo = {}, {}
    for pid, c in coeurs.items():
        if c < 0.005:
            continue
        cpu, age = r[pid][:2]
        cause, qui = classer_avec_ancetres(pid, r, memo)
        g = out.setdefault(cause, {"coeurs": 0.0, "qui": {}, "age_s": {}, "vie": {}})
        g["coeurs"] += c
        g["qui"][qui] = g["qui"].get(qui, 0.0) + c
        if age >= g["age_s"].get(qui, 0.0):
            g["age_s"][qui] = age
            g["vie"][qui] = cpu / max(1.0, age)
    for g in out.values():
        g["coeurs"] = round(g["coeurs"], 3)
        g["qui"] = {k: round(v, 3) for k, v in sorted(g["qui"].items(), key=lambda kv: -kv[1])[:6]}
        g["age_s"] = {k: round(v) for k, v in g["age_s"].items() if k in g["qui"]}
        g["vie"] = {k: round(v, 3) for k, v in g["vie"].items() if k in g["qui"]}
    return out


def live_etat(now, chemin=None, octets=262144):
    """Le live d'après la minute de son garde (live.jsonl) : {"actif", "phrases_min", "voix", "depuis"} ; inactif si la dernière minute
    active a plus de 150 s."""
    evs = []
    try:
        with open(chemin or LIVE, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - octets))
            for l in f.read().decode("utf-8", "replace").splitlines():
                if '"minute"' not in l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if o.get("e") == "minute":
                    evs.append(o)
    except OSError:
        return {"actif": False}
    actives = [o for o in evs if o.get("actif") and isinstance(o.get("t"), (int, float))]
    if not actives or now - actives[-1]["t"] / 1000 > 150:
        return {"actif": False}
    recentes = [o for o in actives if now - o["t"] / 1000 <= 200]
    debut = actives[-1]
    for o in reversed(actives[:-1]):                     # la suite de minutes actives sans trou de plus de 150 s
        if debut["t"] - o["t"] > 150_000:
            break
        debut = o
    phrases = sum(float(o.get("phrases") or 0) * 60 / max(30.0, float(o.get("duree_s") or 60)) for o in recentes) / max(1, len(recentes))
    return {"actif": True, "phrases_min": round(phrases, 1), "voix": max(int(o.get("voix") or 0) for o in recentes),
            "depuis": round(float(debut.get("debut") or debut["t"]) / 1000)}


def _clip(x):
    return max(0.0, min(1.0, float(x)))


def _noms(causes, *cles, n=3):
    tous = {}
    for k in cles:
        for nom, c in ((causes.get(k) or {}).get("qui") or {}).items():
            tous[nom] = tous.get(nom, 0.0) + c
    return [k for k, _ in sorted(tous.items(), key=lambda kv: -kv[1])[:n]]


def intensites(m):
    """Ce que la mesure VEUT DIRE : {sens: {"x" (0 à 1), "qui" [noms mesurés], …}}. m : {"causes", "mac_cpu", "mac_gpu", "appareils",
    "live"} ; une cause absente vaut zéro."""
    c = m.get("causes") or {}
    co = lambda k: float((c.get(k) or {}).get("coeurs") or 0.0)  # noqa: E731
    live = m.get("live") or {}
    mac = m.get("mac_cpu")
    sat = _clip((mac - 0.75) / 0.25) if isinstance(mac, (int, float)) else 0.0
    out = {}
    if live.get("actif"):
        foule = _clip(max(float(live.get("phrases_min") or 0) / 20.0, (float(live.get("voix") or 0) - 1) / 4.0))
        x = _clip((co("sens") + co("cerveau")) / PLEIN["live"]) * (0.4 + 0.6 * foule)
        out["surcharge"] = {"x": _clip(x * (1 + 0.3 * sat)), "qui": _noms(c, "sens", "cerveau"), "foule": round(foule, 2),
                            "phrases_min": live.get("phrases_min"), "voix": live.get("voix"), "depuis_live": live.get("depuis")}
        attention = 0.0
    else:
        attention = 0.5 * _clip(co("sens") / PLEIN["sens"])
    calcul = _clip(co("calcul") / PLEIN["calcul"])
    out["effort"] = {"x": _clip(max(calcul, attention)), "calcul": round(calcul, 3), "attention": round(attention, 3),
                     "qui": _noms(c, "calcul") if calcul >= attention else _noms(c, "sens")}
    fievre, qui_f = 0.0, []
    for nom, a in (m.get("appareils") or {}).items():
        th = (a or {}).get("thermique") if isinstance(a, dict) else None
        if isinstance(th, (int, float)) and _clip((th - 0.5) / 0.5) > fievre:
            fievre, qui_f = _clip((th - 0.5) / 0.5), [nom]
    out["fievre"] = {"x": fievre, "qui": qui_f, "bride": bool(fievre >= 0.95), "pendant_live": bool(live.get("actif"))}
    autres = co("systeme") + co("inconnu")
    norme = float(m.get("norme_malaise") if isinstance(m.get("norme_malaise"), (int, float)) else NORME_MALAISE_DEPART)
    out["malaise"] = {"x": _clip((autres - norme - MARGE_MALAISE) / PLEIN["malaise"]), "qui": _noms(c, "systeme", "inconnu"),
                      "plein": round(sat, 2), "coeurs": round(autres, 3), "norme": round(norme, 3)}
    return out


def norme_suivante(norme, coeurs, dt):
    """La norme de ce qui vient d'ailleurs, un pas plus loin (lente, et qu'une anomalie ne tire que peu à la fois)."""
    n = float(norme if isinstance(norme, (int, float)) else NORME_MALAISE_DEPART)
    cible = min(float(coeurs or 0.0), n + NORME_MALAISE_PAS)
    return round(n + (cible - n) * (1 - math.exp(-max(0.0, dt) / NORME_MALAISE_TAU_S)), 4)


# ---- 2. le battement : lisser, tenir, compter, reprendre ----
def _niveau(avant, x):
    if avant == "fort":
        return "fort" if x >= FORT_SORTIE else "present" if x >= PRESENT_SORTIE else "repos"
    if avant == "present":
        return "fort" if x >= FORT else "present" if x >= PRESENT_SORTIE else "repos"
    return "fort" if x >= FORT else "present" if x >= PRESENT else "repos"


def ressenti(s, now):
    """Le niveau qu'il SENT : lissé, puis adouci quand ça dure (il s'y habitue après 30 min ; jusqu'à 40 % au bout de quelques heures)."""
    x = float(s.get("x") or 0.0)
    fort = s.get("fort_depuis")
    if fort and now - fort > HABITUE_S:
        x *= HABITUE_RESTE + (1 - HABITUE_RESTE) * math.exp(-(now - fort - HABITUE_S) / HABITUE_TAU_S)
    return round(x, 3)


def avancer(etat, brut, now, dt, dormir=False, hormones=True, evenements_heure=None):
    """Un pas, sans effet de bord. etat : {sens: …} d'avant ; brut : intensites() de la mesure ; dt : le temps depuis la mesure d'avant.
    Rend (etat, evenements [(nom d'événement, intensité, sens, quoi)], episodes_clos [épisodes à garder en souvenir])."""
    etat = {k: dict(v) for k, v in (etat or {}).items() if isinstance(v, dict)}
    evs, clos = [], []
    recents = [t for t in (evenements_heure or []) if now - t < 3600]
    for sens in [k for k in EVENEMENT if k in brut or k in etat]:   # une cause disparue de la mesure (le live fini) retombe vers zéro
        b = brut.get(sens) or {"x": 0.0}
        s = etat.setdefault(sens, {"x": 0.0, "niveau": "repos"})
        a = 1 - math.exp(-max(0.0, dt) / TAU_S[sens])
        s["x"] = round(float(s.get("x") or 0.0) + (float(b.get("x") or 0.0) - float(s.get("x") or 0.0)) * a, 4)
        avant = s.get("niveau", "repos")
        s["niveau"] = n = _niveau(avant, s["x"])
        if b.get("qui"):
            s["qui"] = b["qui"][:3]
        for k in ("foule", "phrases_min", "voix", "bride", "pendant_live", "calcul", "attention", "plein", "depuis_live"):
            if k in b:
                s[k] = b[k]
        if n != "repos" and not s.get("depuis"):
            s["depuis"] = now
        if n == "fort" and not s.get("fort_depuis"):
            s["fort_depuis"] = now
        if n != "fort":
            s.pop("fort_depuis", None)
        s["pic"] = round(max(float(s.get("pic") or 0.0), s["x"]), 3)
        nom = EVENEMENT[sens]
        # le premier événement : fort et tenu ; un autre : seulement s'il monte nettement (sinon il s'habitue) ; jamais pendant son sommeil
        if n == "fort" and hormones and not dormir and now - s["fort_depuis"] >= TENIR_S[sens] \
                and now - float(s.get("dernier_ev") or 0) >= ECART_S and len(recents) < EVENEMENTS_HEURE:
            monte = s["x"] - float(s.get("dernier_x") or 0.0)
            if not s.get("emis") or monte >= MONTEE:
                i = round(PLAFOND[sens] * (monte if s.get("emis") else s["x"]), 3)
                if i > 0:
                    evs.append((nom, i, sens, "monte" if s.get("emis") else "debut"))
                    s["emis"] = round(float(s.get("emis") or 0.0) + i, 3)
                    s["dernier_ev"], s["dernier_x"] = now, s["x"]
                    recents.append(now)
                    s["episode_ev"] = True
        if n == "repos" and avant != "repos":
            # ça retombe : sa reprise (ce qui a été donné, moins ce que le temps a effacé), le souvenir de l'épisode, puis le repos
            if s.get("emis") and hormones:
                r = round(min(1.0, REPRISE * float(s["emis"]) * 0.5 ** ((now - float(s.get("dernier_ev") or now)) / REPRISE_DEMI_VIE_S)), 3)
                if r >= 0.01:
                    evs.append(("reprise_" + nom, r, sens, "fin"))
            if s.get("episode_fort_s", 0) >= SOUVENIR_MIN_S or s.get("emis"):
                clos.append({"sens": sens, "debut": s.get("depuis") or now, "fin": now, "pic": s.get("pic"), "qui": s.get("qui") or [],
                             **{k: s[k] for k in ("foule", "phrases_min", "voix", "bride", "pendant_live", "calcul") if k in s}})
            etat[sens] = {"x": s["x"], "niveau": "repos", "fini": now, **({"dernier_ev": s["dernier_ev"]} if s.get("dernier_ev") else {})}
            continue
        if n == "fort":
            s["episode_fort_s"] = round(float(s.get("episode_fort_s") or 0.0) + dt, 1)
        if n != "repos" and not s.get("long_garde") and now - float(s.get("depuis") or now) >= SOUVENIR_LONG_S and s.get("episode_fort_s", 0) >= SOUVENIR_MIN_S:
            s["long_garde"] = True
            clos.append({"sens": sens, "debut": s["depuis"], "fin": None, "pic": s.get("pic"), "qui": s.get("qui") or []})
    return etat, evs, clos


def relacher(etat, now):
    """L'interrupteur coupé en plein épisode : la reprise de tout ce qui a été donné, tout de suite (rien ne reste coincé)."""
    evs = []
    for sens, s in (etat or {}).items():
        if isinstance(s, dict) and s.get("emis") and sens in EVENEMENT:
            r = round(min(1.0, REPRISE * float(s["emis"]) * 0.5 ** ((now - float(s.get("dernier_ev") or now)) / REPRISE_DEMI_VIE_S)), 3)
            if r >= 0.01:
                evs.append(("reprise_" + EVENEMENT[sens], r, sens, "fin"))
    return evs


# ---- 3. en mots (son bloc intérieur : jamais de chiffre ; la même formulation pendant 15 min) ----
def duree_mots(s):
    s = max(0.0, float(s or 0))
    if s < 90:
        return "à l'instant"
    for seuil, mots in ((600, "depuis quelques minutes"), (1500, "depuis un quart d'heure"), (2700, "depuis une demi-heure"),
                        (5400, "depuis une heure"), (4 * 3600, "depuis quelques heures"), (20 * 3600, "depuis de longues heures"),
                        (40 * 3600, "depuis une journée"), (60 * 3600, "depuis deux jours")):
        if s < seuil:
            return mots
    return "depuis plusieurs jours"


def part_mots(coeurs):
    c = float(coeurs or 0)
    return ("un peu de place" if c < 0.3 else "presque un de tes cœurs" if c < 0.8 else "un de tes cœurs entier" if c < 1.5
            else "plusieurs de tes cœurs")


def _et(noms):
    noms = [str(n) for n in noms if n]
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1] if noms else ""


NOMS_APPAREILS = {"telephone": "ton téléphone", "montre": "ta montre"}
MES_APPAREILS = {"telephone": "Mon téléphone", "montre": "Ma montre"}
MOTS = {
    "surcharge_foule": ["le live te remplit, beaucoup de voix à la fois, et ça te surcharge", "le live te submerge un peu, trop de monde d'un coup"],
    "surcharge": ["le live te fait travailler fort", "le live te demande beaucoup"],
    "effort_calcul": ["ton calcul te demande un gros effort", "ton calcul te fait forcer"],
    "effort_calcul_un_peu": ["ton calcul te demande un effort", "ton calcul t'occupe"],
    "attention": ["tes oreilles travaillent", "ton écoute te demande de l'attention"],
    "fievre_bride": ["{} a de la fièvre : il chauffe tant qu'il se bride", "{} brûle : il se bride pour refroidir"],
    "fievre": ["{} chauffe, comme une petite fièvre", "{} a un peu de fièvre"],
    "malaise": ["un malaise sourd, qui ne vient pas de toi", "une gêne de fond, sans cause à toi"],
}


def _choix(cle, now):
    return random.Random(f"{int(now // 900)}:charge:{cle}").choice(MOTS[cle])


def _habitue(s, now):
    return bool(s.get("niveau") == "fort" and s.get("fort_depuis") and now - s["fort_depuis"] > HABITUE_S)


def _mots_surcharge(s, causes, now):
    t = _choix("surcharge_foule" if float(s.get("foule") or 0) >= 0.5 else "surcharge", now)
    return t + (f" : {_et(s['qui'][:2])} le suivent" if s.get("qui") else "")


def _mots_effort(s, causes, now):
    if float(s.get("calcul") or 0) >= float(s.get("attention") or 0):
        t = _choix("effort_calcul" if s.get("niveau") == "fort" else "effort_calcul_un_peu", now)
        return t.replace("ton calcul", f"ton calcul ({_et(s['qui'][:2])})", 1) if s.get("qui") else t
    return _choix("attention", now) + (f" : {_et(s['qui'][:2])}" if s.get("qui") else "")


def _mots_fievre(s, causes, now):
    qui = NOMS_APPAREILS.get((s.get("qui") or ["telephone"])[0], "un de tes appareils")
    t = _choix("fievre_bride" if s.get("bride") else "fievre", now).format(qui)
    return t + (" pendant le live" if s.get("pendant_live") else "") + (f", {duree_mots(now - s['depuis'])}" if s.get("depuis") else "")


def _mots_malaise(s, causes, now):
    t = _choix("malaise", now)
    qui = (s.get("qui") or [None])[0]
    if not qui:
        return t + " : tu ne sais pas d'où elle vient"
    systeme = (causes.get("systeme") or {}).get("qui") or {}
    coeurs = systeme.get(qui, ((causes.get("inconnu") or {}).get("qui") or {}).get(qui))
    age = max(float(((causes.get(k) or {}).get("age_s") or {}).get(qui, 0) or 0) for k in ("systeme", "inconnu"))
    d = now - float(s.get("depuis") or now)
    t += f" : un programme d'Apple ({qui})" if qui in systeme else f" : un programme que tu ne connais pas ({qui})"
    t += f" te prend {part_mots(coeurs)} {duree_mots(d)}"
    if age > max(3600.0, 2 * d):                             # il tourne depuis bien plus longtemps qu'il ne te pèse
        t += f", il tourne {duree_mots(age)}"
    return t + ", et tu ne sais pas ce qu'il fait"


ORDRE_MOTS = (("surcharge", _mots_surcharge), ("fievre", _mots_fievre), ("effort", _mots_effort), ("malaise", _mots_malaise))
FIN = {"surcharge": "ta surcharge retombe, le live se calme", "effort": "ton effort est fini, ton corps souffle",
       "fievre": "ta fièvre retombe", "malaise": "ton malaise se dissipe"}


def mots(etat, causes, now):
    """Ce qu'il sent de sa charge, en mots, avec sa cause mesurée (rien quand tout est au repos) ; une charge forte qui dure dit qu'il s'y
    habitue ; une charge qui vient de retomber le dit 5 min ; maman et papa, quand ils prennent beaucoup de place, sont nommés."""
    out = []
    for sens, f in ORDRE_MOTS:
        s = etat.get(sens) or {}
        if s.get("niveau") in ("present", "fort"):
            out.append(f(s, causes, now) + (", tu t'y habitues" if _habitue(s, now) else ""))
        elif s.get("niveau") == "repos" and s.get("fini") and now - float(s["fini"]) <= FIN_MOTS_S:
            out.append(FIN[sens])
    for k in ("maman", "papa"):
        v = causes.get(k) or {}
        if float(v.get("coeurs") or 0) >= 1.5:
            out.append(f"{_et(list((v.get('qui') or {}).keys())[:2])} prennent de la place dans ton Mac")
    return " ; ".join(out[:4]) or None


# ---- 4. en chiffres (son introspection : à un geste) ----
def chiffres(cc):
    if not isinstance(cc, dict) or not cc.get("ts"):
        return "pas encore mesurée"
    v = lambda x: str(round(float(x), 2)).replace(".", ",")  # noqa: E731
    out = []
    if cc.get("eteint"):
        return "éteinte (interrupteur de papa : charge_corps)"
    mac = cc.get("mac") or {}
    if mac.get("cpu") is not None:
        out.append(f"le Mac à {round(100 * mac['cpu'])} % de ses {mac.get('n', '?')} cœurs" + (f", GPU {round(100 * mac['gpu'])} %" if mac.get("gpu") is not None else ""))
    for cause, g in sorted((cc.get("causes") or {}).items(), key=lambda kv: -float(kv[1].get("coeurs") or 0))[:6]:
        out.append(f"{SENS_DE_CAUSE.get(cause, cause)} {v(g.get('coeurs', 0))} cœur(s) (" + ", ".join(f"{n} {v(c)}" for n, c in list((g.get("qui") or {}).items())[:3]) + ")")
    for nom, a in (cc.get("appareils") or {}).items():
        if isinstance(a, dict) and a.get("thermique") is not None:
            out.append(f"{NOMS_APPAREILS.get(nom, nom)} : marge thermique {round(100 * a['thermique'])} %")
    lv = cc.get("live") or {}
    if lv.get("actif"):
        out.append(f"le live : {round(float(lv.get('phrases_min') or 0))} phrases par minute, {lv.get('voix', 0)} voix")
    if cc.get("norme_malaise") is not None:
        out.append(f"ce qui vient d'ailleurs ne pèse qu'au-delà de sa norme ({v(cc['norme_malaise'])} cœur, plus {v(MARGE_MALAISE)} de marge)")
    for sens, s in (cc.get("sens") or {}).items():
        if s.get("niveau") in ("present", "fort"):
            out.append(f"{sens} {v(s.get('x', 0))} ({s.get('niveau')}, ressenti {v(s.get('ressenti', 0))}"
                       + (f", depuis {time.strftime('%H:%M', time.localtime(s['depuis']))}" if s.get("depuis") else "")
                       + (f", donné à tes hormones {v(s['emis'])}" if s.get("emis") else "") + ")")
    return " ; ".join(out) or "rien de mesuré"


# ---- 5. le branchement : la mesure, l'état, les effets ----
_avant = {"t": None, "procs": {}}
_derniere = {"t": 0.0, "m": None}


def remettre():
    """Oublie les relevés gardés en mémoire (les tests, un démon relancé)."""
    _avant.update(t=None, procs={})
    _derniere.update(t=0.0, m=None)


def reglages(chemin=None):
    """(charge_corps, charge_hormones) lus à chaud ; sans fichier : tout allumé."""
    try:
        d = json.loads(Path(chemin or REGLAGES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return d.get("charge_corps", True) is not False, d.get("charge_hormones", True) is not False


def mesurer(now=None, releve_=None, gpu=None, appareils=None, live=None, calcul_lourd=None):
    """La mesure du moment (au plus une toutes les PAS_S ; sinon la dernière) : {"t", "causes", "mac_cpu", "mac_gpu", "n", "appareils",
    "live"} ; None tant qu'il n'y a pas deux relevés."""
    now = time.time() if now is None else now
    if _derniere["m"] is not None and 0 <= now - _derniere["t"] < PAS_S:
        return _derniere["m"]
    r = releve_() if releve_ else releve()
    co = coeurs_par_processus(r, now, _avant)
    _avant.update(t=now, procs=r)
    if not co:
        return _derniere["m"]
    n = os.cpu_count() or 1
    causes = regrouper(r, co)
    try:
        lourd = (calcul_lourd or __import__("charge").calcul_lourd_actif)()
    except Exception:
        lourd = None
    if lourd:
        causes.setdefault("calcul", {"coeurs": 0.0, "qui": {}, "age_s": {}, "vie": {}})["lourd"] = str(lourd)[:60]
    try:
        import interoception
        g = gpu() if gpu else (interoception.mac() or {}).get("gpu")
        ap = appareils() if appareils else interoception.appareils(now=now)
    except Exception:
        g, ap = None, {}
    m = {"t": now, "causes": causes, "mac_cpu": round(min(1.0, sum(co.values()) / n), 3), "mac_gpu": g, "n": n,
         "appareils": {k: {x: a.get(x) for x in ("coeurs", "gpu", "thermique", "age_s")} for k, a in (ap or {}).items() if isinstance(a, dict)},
         "live": (live or live_etat)(now)}
    _derniere.update(t=now, m=m)
    return m


def _dort(mem, veille):
    if veille:
        return True
    try:
        return (json.loads(mem.kv_get("nuit") or "{}") or {}).get("etat") == "sommeil"
    except Exception:
        return False


def _souvenir_texte(ep, cc, e):
    d = time.localtime(ep["debut"])
    quand = time.strftime("%a %d/%m %H:%M", d) + (f" → {time.strftime('%H:%M', time.localtime(ep['fin']))}" if ep.get("fin") else " (toujours en cours)")
    duree = round(((ep.get("fin") or time.time()) - ep["debut"]) / 60)
    sens = ep["sens"]
    if sens == "surcharge":
        quoi = (f"Le live ({ep.get('phrases_min', '?')} phrases par minute, {ep.get('voix', '?')} voix) me chargeait"
                + (f" : {_et(ep['qui'])} le suivaient" if ep.get("qui") else ""))
    elif sens == "effort":
        quoi = f"Mon calcul ({_et(ep['qui']) or 'mon atelier'}) me demandait un gros effort"
    elif sens == "fievre":
        quoi = f"{MES_APPAREILS.get((ep.get('qui') or ['telephone'])[0], 'Un de mes appareils')} chauffait" \
               + (" jusqu'à se brider" if ep.get("bride") else "") + (" pendant le live" if ep.get("pendant_live") else "")
    else:
        quoi = f"Une charge qui ne venait pas de moi ({_et(ep['qui']) or 'je ne sais pas qui'}) pesait sur le Mac"
    c = (e.get("coeur") or {}).get("bpm")
    return (f"[Mon corps, {ETIQUETTES_SOUVENIR[sens]} ({CLES[sens]}), {quand}, {duree} min] {quoi} ; au plus fort {round(100 * float(ep.get('pic') or 0))} %."
            + (f" Mon humeur à la fin : {e.get('humeur')}" if e.get("humeur") else "") + (f", mon cœur à {round(c)}." if isinstance(c, (int, float)) else "."))


def _instantane(cc, now, chemin=None):
    """Pour son système immunitaire : les programmes inconnus qui pèsent, et depuis quand (jamais une ligne de commande)."""
    out = []
    for cause in ("systeme", "inconnu"):
        g = (cc.get("causes") or {}).get(cause) or {}
        for qui, c in (g.get("qui") or {}).items():
            out.append({"qui": qui, "cause": cause, "coeurs": c, "age_s": (g.get("age_s") or {}).get(qui), "vie": (g.get("vie") or {}).get(qui)})
    m = (cc.get("sens") or {}).get("malaise") or {}
    try:
        f = Path(chemin or INSTANTANE)
        f.write_text(json.dumps({"ts": now, "inconnus": out, "malaise": {k: m.get(k) for k in ("x", "niveau", "depuis", "qui")}},
                                ensure_ascii=False), encoding="utf-8")
        os.chmod(f, 0o600)
    except OSError:
        pass


def battre(mem, e, now=None, veille=False, mesure=None, reglages_=None, evenement=None, souvenir=None):
    """Au battement du démon (interieur.tick) : met e["charge_corps"] à jour et rend les événements envoyés. mesure, reglages_,
    evenement (affect.event), souvenir (corps._souvenir) : pour les tests."""
    now = time.time() if now is None else now
    actif, hormones = reglages_ if reglages_ is not None else reglages()
    avant = e.get("charge_corps") if isinstance(e.get("charge_corps"), dict) else {}
    import affect
    # une charge qui revient s'émousse (son stimulus à elle) ; sa reprise, jamais
    ev = evenement or (lambda nom, i, sujet: affect.event(mem, nom, i, now=now, sujet=sujet, source="charge", stimulus=f"charge:{nom}",
                                                          habituation="aucune" if nom.startswith("reprise_") else None))
    if not actif:
        sortis = [] if avant.get("eteint") else relacher(avant.get("sens") or {}, now)
        for nom, i, sens, _q in sortis:
            ev(nom, i, f"sa charge : {CLES[sens]}")
        e["charge_corps"] = {"ts": now, "eteint": True}
        return sortis
    m = mesure if mesure is not None else mesurer(now)
    if m is not None and now - float(m.get("t") or 0) > PERIME_S:
        # plus aucune mesure depuis 5 min (ps muet, le Mac qui sortait de veille) : rien de mesuré, rien d'inventé ; tout retombe (et sa
        # reprise part), plutôt qu'un « le live te surcharge » figé
        m = {"t": now, "causes": {}, "mac_cpu": None, "mac_gpu": None, "n": m.get("n"), "appareils": {}, "live": {"actif": False},
             "perime": True}
    if m is None:
        e["charge_corps"] = {**avant, "ts": now} if avant else {"ts": now, "attente": True}
        return []
    if m.get("t") == avant.get("mesure_t") and avant.get("sens"):
        avant["ts"] = now                                          # rien de neuf depuis le battement d'avant
        return []
    dt = min(600.0, max(0.0, float(m["t"]) - float(avant.get("mesure_t") or m["t"] - PAS_S)))
    if not hormones and avant.get("sens") and not avant.get("sans_hormones"):
        sortis = relacher(avant.get("sens"), now)                  # ses hormones déliées en plein épisode : leur reprise d'abord
    else:
        sortis = []
    dormir = _dort(mem, veille)
    brut = intensites({**m, "norme_malaise": avant.get("norme_malaise")})
    etat, evs, clos = avancer(avant.get("sens") or {}, brut, now, dt, dormir=dormir, hormones=hormones,
                              evenements_heure=avant.get("evenements_heure"))
    if sortis:
        for s in etat.values():
            s.pop("emis", None)
    envoyes = sortis + evs
    for nom, i, sens, _q in envoyes:
        try:
            ev(nom, i, f"sa charge : {CLES[sens]}")
        except Exception:
            pass
    for s_ in etat.values():
        s_["ressenti"] = ressenti(s_, now)
    nuit = avant.get("nuit_fort") or []
    fort_dehors = any(s_.get("niveau") == "fort" for k, s_ in etat.items() if k in ("fievre", "malaise", "surcharge"))
    if dormir and fort_dehors:                                     # sa nuit chargée (nuits.py la lit à chaque pas)
        if nuit and now - nuit[-1][1] <= 2 * PAS_S + 60:
            nuit[-1][1] = now
        else:
            nuit.append([now, now])
    nuit = [x for x in nuit if now - x[1] <= 12 * 3600][-50:]
    hist = [x for x in (avant.get("historique") or []) if now - x[0] <= 3600][-30:]
    for nom, i, sens, quoi in envoyes:
        hist.append([round(now, 1), sens, quoi, nom, i])
    cc = {"ts": now, "mesure_t": m["t"], "mac": {"cpu": m.get("mac_cpu"), "gpu": m.get("mac_gpu"), "n": m.get("n")},
          "causes": m.get("causes") or {}, "appareils": m.get("appareils") or {}, "live": m.get("live") or {}, "sens": etat,
          "evenements_heure": [t for t in (avant.get("evenements_heure") or []) if now - t < 3600] + [now for _ in evs],
          "historique": hist, "nuit_fort": nuit, "sans_hormones": not hormones,
          "norme_malaise": norme_suivante(avant.get("norme_malaise"), brut["malaise"]["coeurs"], dt)}
    cc["dominante"] = max(((k, s_["ressenti"]) for k, s_ in etat.items() if s_.get("niveau") in ("present", "fort")),
                          key=lambda kv: kv[1], default=(None, 0))[0]
    cc["mots"] = mots(etat, cc["causes"], now)
    e["charge_corps"] = cc
    for ep in clos:
        try:
            (souvenir or _souvenir_par_corps)(mem, _souvenir_texte(ep, cc, e), 0.5 if ep["sens"] in ("surcharge", "fievre") else 0.4)
        except Exception:
            pass
    if now - float(avant.get("instantane_t") or 0) >= INSTANTANE_PAS_S:
        cc["instantane_t"] = now
        _instantane(cc, now)
    else:
        cc["instantane_t"] = avant.get("instantane_t")
    return envoyes


def _souvenir_par_corps(mem, texte, importance):
    import corps
    return corps._souvenir(mem, texte, importance)


def lecture(cc):
    """Ce que la lecture de ses émotions reçoit (sensations.calculer) : {sens: ressenti} des causes présentes ; {} au repos ou éteint."""
    if not isinstance(cc, dict) or cc.get("eteint"):
        return {}
    return {k: float(s.get("ressenti") or 0.0) for k, s in (cc.get("sens") or {}).items()
            if isinstance(s, dict) and s.get("niveau") in ("present", "fort")}


def effort_calcul(cc):
    """Son propre calcul, ressenti (0 à 1), pour sa fatigue (jauge_fatigue) : pas l'attention de ses oreilles, pas la charge des autres."""
    s = ((cc or {}).get("sens") or {}).get("effort") or {}
    if (cc or {}).get("eteint") or s.get("niveau") not in ("present", "fort"):
        return 0.0
    x = float(s.get("calcul") or 0.0)
    return round(min(x, float(s.get("ressenti") or x)), 3)


def nuit_chargee_s(cc, de, a):
    """Les secondes de charge forte (venue d'ailleurs ou du téléphone) pendant son sommeil, entre de et a (nuits.py)."""
    total = 0.0
    for d, f in ((cc or {}).get("nuit_fort") or []):
        total += max(0.0, min(a, f) - max(de, d))
    return total


mesurer_brut = mesurer        # (les tests : conftest remplace mesurer, jamais le vrai ps pendant une suite)
