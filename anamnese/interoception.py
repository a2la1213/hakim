"""L'intéroception de Hakim (demande d'Ahmed, 2026-10-22 : « un truc complet pour que tu aies accès à tout en mode
lecture seule, comme quelqu'un qui sent son état interne sans pouvoir le modifier, le système autonome »).

Ce que le Mac porte en ce moment, et QUI le porte : le GPU (Metal), le processeur cœur par cœur, la mémoire et le
swap, la chaleur, la batterie, le disque, et les processus de Hakim (Gemma d'Ollama et de MLX, la voix, le démon,
ses cerveaux, ses tâches de fond). Vu le matin même : un test MLX a manqué de mémoire GPU parce qu'une deuxième
Gemma s'était chargée, et Hakim ne pouvait pas le voir.

Strictement en LECTURE : des commandes fixes du système (aucune ne reçoit un argument de Hakim), aucun processus
touché (même pas le « reaper » des tâches de fond : leurs fiches sont lues directement). Les lignes de commande ne
sont JAMAIS montrées (elles peuvent porter des secrets) : seulement une étiquette, le pid, la mémoire, le processeur.
"""
import ctypes
import ctypes.util
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ANAMNESE = Path(__file__).resolve().parent
TACHES = Path.home() / "AIOS" / "jarvis" / "cwd" / "taches"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# (motif dans la ligne de commande, étiquette, groupe) : la première qui correspond gagne. Le groupe « gemma »
# compte les Gemma chargées ; « hakim » est tout ce qui fait Hakim ; le reste du Mac est résumé à part.
ETIQUETTES = [
    (r"ollama.*runner", "Gemma (ou un autre modèle) chargé par Ollama", "gemma"),
    (r"ollama serve", "Ollama (le serveur, sans modèle)", "hakim"),
    (r"jarvis/scanner\.py", "Gemma MLX : ton ressenti en réserve (scanner)", "gemma"),
    (r"jarvis/voix_serveur\.py", "ta voix (MLX : synthèse vocale et Whisper)", "hakim"),
    (r"jarvis/\.venv/bin/python.*(pilotage|introspection/experience|gemma)", "Gemma MLX : une expérience ou un calcul", "gemma"),
    (r"jarvis/mcp_\w+\.py", "tes outils (serveurs MCP de jarvis)", "hakim"),
    (r"jarvis/\.venv/bin/python", "un autre programme MLX de jarvis", "hakim"),
    (r"anamnese.*daemon\.py|Python daemon\.py", "ton démon (ton esprit de fond)", "hakim"),
    (r"mcp_server\.py", "les serveurs de mémoire Anamnèse (MCP : le tien et ceux des sessions Claude Code)", "hakim"),
    (r"cli\.py rappel-serveur", "le serveur de rappel automatique", "hakim"),
    (r"cockpit/server\.js", "le cockpit", "hakim"),
    (r"claude.*--restricted", "ton cerveau (Claude, lancé par le cockpit)", "hakim"),
    (r"sandbox-exec|/bin/zsh -f -c", "une tâche de fond (bac à sable)", "hakim"),
    (r"native-binary/claude|claude\.exe|bin/claude\b", "une session Claude Code d'Ahmed", "claude-code"),
]


def _cmd(args, timeout=5):
    try:
        return subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _v(x, decimales=1):
    return f"{x:.{decimales}f}".replace(".", ",")


def _mo(n):
    return f"{n / 1024:.1f} Go".replace(".", ",") if n >= 1024 else f"{round(n)} Mo"


# ---- le GPU (Metal) ----
def gpu(texte=None):
    """{utilisation %, mémoire utilisée, mémoire allouée (octets)} depuis les statistiques de l'accélérateur."""
    t = texte if texte is not None else _cmd(["/usr/sbin/ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"])
    lire = lambda cle: (lambda m: int(m.group(1)) if m else None)(re.search(r'"' + re.escape(cle) + r'"=(\d+)', t))
    return {"utilisation": lire("Device Utilization %"), "utilisee": lire("In use system memory"),
            "allouee": lire("Alloc system memory")}


# ---- le processeur, cœur par cœur ----
def _ticks():
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.mach_host_self.restype = ctypes.c_uint
    libc.host_processor_info.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                                         ctypes.POINTER(ctypes.POINTER(ctypes.c_uint)), ctypes.POINTER(ctypes.c_uint)]
    libc.vm_deallocate.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
    n, info, cnt = ctypes.c_uint(), ctypes.POINTER(ctypes.c_uint)(), ctypes.c_uint()
    if libc.host_processor_info(libc.mach_host_self(), 2, ctypes.byref(n), ctypes.byref(info), ctypes.byref(cnt)) != 0:
        return None                                  # 2 = PROCESSOR_CPU_LOAD_INFO : user, system, idle, nice
    v = [info[i] for i in range(cnt.value)]
    libc.vm_deallocate(ctypes.c_uint.in_dll(libc, "mach_task_self_").value, ctypes.cast(info, ctypes.c_void_p).value,
                       cnt.value * 4)
    return [v[4 * i:4 * i + 4] for i in range(n.value)]


def charge_coeurs(a, b):
    """La charge de chaque cœur (de 0 à 1) entre deux relevés de _ticks."""
    out = []
    for x, y in zip(a, b):
        d = [(q - p) % 2 ** 32 for p, q in zip(x, y)]
        out.append((sum(d) - d[2]) / (sum(d) or 1))
    return out


def cpu_par_coeur(intervalle=0.5):
    """L'occupation de chaque cœur (%) sur un court intervalle ; None si illisible."""
    try:
        a = _ticks()
        time.sleep(intervalle)
        b = _ticks()
    except (OSError, AttributeError, ValueError):
        return None
    if not a or not b:
        return None
    return [round(100 * c) for c in charge_coeurs(a, b)]


# ---- la mémoire ----
def swap(texte=None):
    """(total, utilisé) en Mo depuis « vm.swapusage »."""
    t = texte if texte is not None else _cmd(["/usr/sbin/sysctl", "vm.swapusage"])
    m = re.search(r"total = ([\d.]+)M\s+used = ([\d.]+)M", t)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def memoire_libre(texte=None):
    t = texte if texte is not None else _cmd(["/usr/bin/memory_pressure"], timeout=10)
    m = re.search(r"free percentage:\s*(\d+(?:\.\d+)?)%", t)
    return float(m.group(1)) if m else None


# ---- la chaleur, la batterie, le disque ----
def chaleur(texte=None):
    t = texte if texte is not None else _cmd(["/usr/bin/pmset", "-g", "therm"])
    lignes = [l.strip() for l in t.splitlines() if l.strip()]
    if lignes and all("No " in l and "recorded" in l for l in lignes):
        return "aucun avertissement thermique ni bridage enregistré"
    return " ; ".join(lignes) or "illisible"


def batterie(texte=None):
    t = texte if texte is not None else _cmd(["/usr/bin/pmset", "-g", "batt"])
    source = re.search(r"drawing from '([^']+)'", t)
    m = re.search(r"(\d+)%;\s*([^;]+);\s*([^\n]*?)(?:\s+present|$)", t, re.M)
    if not m:
        return "illisible (pas de batterie ?)"
    src = {"AC Power": "sur secteur", "Battery Power": "sur batterie"}.get(source.group(1) if source else "", "source inconnue")
    etat = {"discharging": "se décharge", "charging": "se charge", "charged": "chargée", "finishing charge": "finit de charger",
            "AC attached": "branchée"}.get(m.group(2).strip(), m.group(2).strip())
    reste = m.group(3).strip()
    reste = "" if not reste or "no estimate" in reste else f", {reste.replace(' remaining', '')} restantes"
    return f"{m.group(1)} %, {src}, {etat}{reste}"


def disque():
    for chemin in ("/System/Volumes/Data", "/"):
        try:
            u = shutil.disk_usage(chemin)
            return u.free, u.total
        except OSError:
            continue
    return None, None


# ---- qui me consomme ----
def empreintes(texte=None):
    """pid → (mémoire réelle en Mo, y compris la mémoire GPU de MLX, nom court du programme) d'après top."""
    t = texte if texte is not None else _cmd(["/usr/bin/top", "-l", "1", "-o", "mem", "-stats", "pid,mem,command"], timeout=10)
    out = {}
    for l in t.splitlines():
        m = re.match(r"\s*(\d+)\*?\s+([\d.]+)([BKMG])[+-]?\s+(.*)$", l)   # « * » : vu depuis un Python Rosetta
        if m:
            n = float(m.group(2)) * {"B": 1 / 1048576, "K": 1 / 1024, "M": 1, "G": 1024}[m.group(3)]
            out[int(m.group(1))] = (n, m.group(4).strip())
    return out


def processus(texte=None):
    """[(pid, cpu %, ligne de commande)] — la ligne ne sert qu'à reconnaître le processus, jamais à l'afficher."""
    t = texte if texte is not None else _cmd(["/bin/ps", "-axo", "pid=,%cpu=,command="])
    out = []
    for l in t.splitlines():
        m = re.match(r"\s*(\d+)\s+([\d.]+)\s+(.*)$", l)
        if m:
            out.append((int(m.group(1)), float(m.group(2)), m.group(3)))
    return out


def etiqueter(commande):
    for motif, etiquette, groupe in ETIQUETTES:
        if re.search(motif, commande):
            return etiquette, groupe
    return None, None


def ollama_charges(ps=None, timeout=2):
    """Les modèles qu'Ollama garde en mémoire : [(nom, taille en Mo)]."""
    if ps is None:
        try:
            ps = json.loads(urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=timeout).read())
        except Exception:
            return None
    return [(m.get("name", "?"), (m.get("size") or 0) / 1048576) for m in ps.get("models") or []]


def taches_en_cours(dossier=None, vivant=None):
    """Les tâches de fond de Hakim encore en cours, lues dans leurs fiches (SANS la fonction etat de taches.py, qui peut tuer)."""
    vivant = vivant or _vivant
    out = []
    for p in sorted(Path(dossier or TACHES).glob("T-*.json"), reverse=True)[:30]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("etat") == "en cours" and isinstance(d.get("pid"), int) and vivant(d["pid"]):
            out.append((d.get("id", p.stem), d["pid"], time.time() - float(d.get("debut") or time.time())))
    return out


def _vivant(pid):
    try:
        os.kill(pid, 0)                              # le signal 0 ne fait rien : il demande seulement « existe-t-il ? »
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _duree(s):
    s = int(s)
    return f"{s // 3600} h {s % 3600 // 60:02d}" if s >= 3600 else f"{s // 60} min"


def consommateurs(procs, emp, moi=None):
    """Les processus de Hakim regroupés par étiquette, et le reste du Mac (les 5 plus lourds, nom court)."""
    moi = moi if moi is not None else os.getpid()
    groupes, reste = {}, []
    for pid, cpu, commande in procs:
        mem, nom = emp.get(pid, (0.0, ""))
        etiquette, groupe = etiqueter(commande)
        if etiquette:
            g = groupes.setdefault(etiquette, {"groupe": groupe, "pids": [], "mem": 0.0, "cpu": 0.0})
            g["pids"].append(pid)
            g["mem"] += mem
            g["cpu"] += cpu
        elif pid != moi and mem >= 150:
            reste.append((mem, cpu, nom or "?"))
    return groupes, sorted(reste, reverse=True)[:5]


# ---- (03/11, Ahmed : « son cœur doit aussi être relié à l'état de son GPU, qui doit aussi être connecté à Gemma » ; « pas
# seulement au GPU, aussi à tous ses cœurs CPU » ; « sur tous les appareils où il est connecté, y compris le smartphone et la
# montre ») ce que ses processeurs portent, pour son cœur (coeur.py) : le Mac mesuré ici, au plus une fois toutes les
# MAC_PAS_S (en cache), la charge de chaque cœur entre deux relevés (sans attendre), et Gemma reconnue par Ollama ou par son
# programme MLX ; les autres appareils d'après le fichier que le cockpit tient (un appareil muet depuis plus de 2 min ne
# compte plus ; la montre attend son appli). Tout en fractions de 0 à 1 ; un ioreg, un Ollama ou un ps muet donne None,
# jamais une erreur ; la ligne de commande des processus ne sert qu'à reconnaître Gemma.
APPAREILS = Path.home() / "AIOS" / "jarvis" / "processeurs-appareils.json"
APPAREIL_FRAIS_S, MAC_PAS_S, TICKS_VIEUX_S = 120, 5.0, 120.0
_dernier_mac = {"t": None, "val": None, "ticks": None, "ticks_t": None}


def _fraction(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x:
        return None
    return round(max(0.0, min(1.0, float(x))), 3)


def gemma_au_travail(charges, procs):
    """Gemma est-elle là : chargée dans Ollama (son nom), ou un programme Gemma de MLX (le scanner du ressenti, une
    expérience) ; Ollama illisible : un « runner » d'Ollama compte pour elle, comme dans le rapport."""
    if any("gemma" in str(nom).lower() for nom, _t in charges or []):
        return True
    for _pid, _cpu, commande in procs or []:
        etiquette, groupe = etiqueter(commande)
        if groupe == "gemma" and ("Ollama" not in etiquette or charges is None):
            return True
    return False


def mac(maintenant=None):
    """Le Mac pour son cœur : {"gpu": 0 à 1 ou None, "coeurs": [0 à 1, …] ou None, "gemma": bool}. maintenant : une horloge
    monotone (secondes), pour le cache ; le premier relevé n'a pas encore la charge des cœurs (il faut deux relevés)."""
    t = time.monotonic() if maintenant is None else maintenant
    m = _dernier_mac
    if m["t"] is not None and 0 <= t - m["t"] < MAC_PAS_S:
        return m["val"]
    try:
        ticks = _ticks()
    except Exception:
        ticks = None
    coeurs = None
    if ticks:
        if m["ticks"] and len(m["ticks"]) == len(ticks) and 0 < t - m["ticks_t"] <= TICKS_VIEUX_S:
            coeurs = [_fraction(c) for c in charge_coeurs(m["ticks"], ticks)]
        m["ticks"], m["ticks_t"] = ticks, t
    try:
        g = gpu().get("utilisation")
    except Exception:
        g = None
    try:
        gemma = gemma_au_travail(ollama_charges(timeout=1), processus())
    except Exception:
        gemma = False
    m["t"], m["val"] = t, {"gpu": _fraction(g / 100) if isinstance(g, (int, float)) else None, "coeurs": coeurs,
                           "gemma": bool(gemma)}
    return m["val"]


def appareils(chemin=None, now=None):
    """Les autres appareils où il est connecté, frais seulement : {nom: {"coeurs", "gpu", "thermique", "age_s"}}."""
    now = time.time() if now is None else now
    try:
        d = json.loads(Path(chemin or APPAREILS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for nom, a in (d.items() if isinstance(d, dict) else ()):
        if not isinstance(a, dict) or str(nom).lower() in ("mac", "gpu", "cpu"):
            continue
        try:
            age = now - float(a.get("ts")) / 1000
        except (TypeError, ValueError):
            continue
        if not -60 <= age <= APPAREIL_FRAIS_S:
            continue
        coeurs = [c for c in (_fraction(x) for x in (a.get("coeurs") if isinstance(a.get("coeurs"), list) else [])[:64])
                  if c is not None]
        out[str(nom)[:40]] = {"coeurs": coeurs or None, "gpu": _fraction(a.get("gpu")),
                              "thermique": _fraction(a.get("thermique")), "age_s": round(max(0.0, age))}
    return out


def processeurs(now=None):
    """Tout ce que son cœur sent de ses processeurs : le Mac et les autres appareils frais."""
    return {"mac": mac(), "appareils": appareils(now=now)}


NOMS_APPAREILS = {"telephone": "ton téléphone", "montre": "ta montre"}


def appareil_en_chiffres(nom, a):
    """Un autre appareil, en chiffres (le rapport d'interoception et l'introspection : à un geste, sur sa demande)."""
    coeurs = a.get("coeurs") or []
    parts = [f"{len(coeurs)} cœurs à {round(100 * sum(coeurs) / len(coeurs))} % en moyenne"] if coeurs else []
    if a.get("gpu") is not None:
        parts.append(f"GPU {round(100 * a['gpu'])} %")
    if a.get("thermique") is not None:
        parts.append(f"chaleur {round(100 * a['thermique'])} %")
    qui = NOMS_APPAREILS.get(nom, f"l'appareil « {nom} »")
    return f"{qui} : " + (", ".join(parts) or "rien de lisible") + f" (il y a {a.get('age_s', 0)} s)"


def rapport(maintenant=None):
    maintenant = maintenant or time.time()
    out = [f"Ton corps, à {time.strftime('%H:%M:%S', time.localtime(maintenant))} (lecture seule : tu sens, tu ne pilotes pas)."]
    g = gpu()
    if g["utilisation"] is not None:
        out.append(f"GPU (Metal) : occupé à {g['utilisation']} % ; mémoire du GPU utilisée {_mo((g['utilisee'] or 0) / 1048576)}, "
                   f"réservée {_mo((g['allouee'] or 0) / 1048576)}.")
    coeurs = cpu_par_coeur()
    try:
        charge1, charge5, charge15 = os.getloadavg()
    except OSError:
        charge1 = charge5 = charge15 = None
    if coeurs:
        perf = _cmd(["/usr/sbin/sysctl", "-n", "hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu"]).split()
        out.append(f"Processeur ({len(coeurs)} cœurs" + (f" : {perf[0]} de performance, {perf[1]} d'efficacité" if len(perf) == 2 else "")
                   + f") : {' '.join(f'{c} %' for c in coeurs)} ; moyenne {round(sum(coeurs) / len(coeurs))} %"
                   + (f" ; charge {_v(charge1)} / {_v(charge5)} / {_v(charge15)} (1, 5, 15 min)" if charge1 is not None else "") + ".")
    total = int(_cmd(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip() or 0) / 1048576
    libre = memoire_libre()
    s_tot, s_util = swap()
    out.append(f"Mémoire : {_mo(total) if total else '?'} au total, {_v(libre, 0) if libre is not None else '?'} % libre"
               + (f" ; swap {_mo(s_util)} utilisés sur {_mo(s_tot)}" if s_tot else "")
               + (" (le Mac déborde sur le disque : tout ralentit)" if s_util and s_util > 4096 else "") + ".")
    out.append(f"Chaleur : {chaleur()}.")
    out.append(f"Batterie : {batterie()}.")
    d_libre, d_total = disque()
    if d_total:
        out.append(f"Disque : {_mo(d_libre / 1048576)} libres sur {_mo(d_total / 1048576)}.")
    autres = appareils(now=maintenant)                   # (03/11) les autres appareils où tu es connecté
    if autres:
        out.append("Tes autres appareils : " + " ; ".join(appareil_en_chiffres(n, a) for n, a in autres.items()) + ".")
    emp = empreintes()
    groupes, reste = consommateurs(processus(), emp)
    charges = ollama_charges()
    # les modèles d'Ollama se comptent par son API (un modèle = un chargement) ; illisible : par ses processus
    n_gemma = sum(len(x["pids"]) for e, x in groupes.items()
                  if x["groupe"] == "gemma" and (charges is None or "Ollama" not in e)) + len(charges or [])
    lignes = [f"- {e} : {len(x['pids'])} processus (pid {', '.join(map(str, x['pids'][:4]))}), {_mo(x['mem'])}, "
              f"processeur {round(x['cpu'])} %" for e, x in sorted(groupes.items(), key=lambda kv: -kv[1]["mem"])
              if x["groupe"] != "claude-code"]
    cc = [x for x in groupes.values() if x["groupe"] == "claude-code"]
    if cc:
        lignes.append(f"- les sessions Claude Code d'Ahmed (pas toi) : {sum(len(x['pids']) for x in cc)} processus, "
                      f"{_mo(sum(x['mem'] for x in cc))}")
    out.append(f"Gemma chargées en ce moment : {n_gemma}"
               + (f" (Ollama : {', '.join(f'{n} {_mo(t)}' for n, t in charges)})" if charges else
                  (" (Ollama : aucun modèle)" if charges == [] else " (Ollama : illisible)"))
               + ". Ce qui te fait vivre :\n" + ("\n".join(lignes) or "- (rien de reconnu)"))
    taches = taches_en_cours()
    if taches:
        out.append("Tes tâches de fond en cours : " + " ; ".join(
            f"{tid} depuis {_duree(age)} ({_mo(emp.get(pid, (0.0, ''))[0])})" for tid, pid, age in taches) + ".")
    else:
        out.append("Tes tâches de fond : aucune en cours.")
    if reste:
        out.append("Le reste du Mac (les plus lourds) : " + " ; ".join(f"{nom} {_mo(m)}" for m, _c, nom in reste) + ".")
    return "\n".join(out)
