"""Le corps hors du Mac (13/11) : ce qu'interoception.py lit sur le Mac par pmset, ioreg, sysctl, memory_pressure, top et
host_processor_info, lu ici par /proc et /sys ; sous WSL2, la batterie et la chaleur sont celles de Windows (powershell.exe,
par l'interopérabilité de WSL), lues au plus une fois par minute (powershell met ~1 s à démarrer).
Tout reste en lecture seule ; une mesure illisible rend None ou « illisible », jamais une erreur."""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import est_wsl

POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
_cache = {}


def _lire(chemin):
    try:
        return Path(chemin).read_text(errors="replace")
    except OSError:
        return ""


def ticks():
    """[[user, système, repos, nice], …] par cœur depuis /proc/stat (même forme que interoception._ticks : le repos en 3e)."""
    out = []
    for l in _lire("/proc/stat").splitlines():
        if re.match(r"cpu\d+\s", l):
            v = [int(x) for x in l.split()[1:]]
            v += [0] * (8 - len(v))
            user, nice, systeme, repos, iowait, irq, softirq, vole = v[:8]
            out.append([user, systeme + irq + softirq + vole, repos + iowait, nice])
    return out or None


def meminfo():
    d = {}
    for l in _lire("/proc/meminfo").splitlines():
        m = re.match(r"(\w+):\s+(\d+)", l)
        if m:
            d[m.group(1)] = int(m.group(2))             # en Ko
    return d


def memoire_totale_mo():
    return meminfo().get("MemTotal", 0) / 1024


def memoire_libre_pourcent():
    m = meminfo()
    return round(100 * m["MemAvailable"] / m["MemTotal"], 1) if m.get("MemTotal") and "MemAvailable" in m else None


def swap_mo():
    m = meminfo()
    if "SwapTotal" not in m:
        return None, None
    return m["SwapTotal"] / 1024, (m["SwapTotal"] - m.get("SwapFree", 0)) / 1024


def _powershell(script, cle, duree_s=60):
    """La sortie JSON d'un petit script PowerShell (sous WSL seulement), gardée duree_s secondes."""
    c = _cache.get(cle)
    if c and time.time() - c[0] < duree_s:
        return c[1]
    val = None
    if est_wsl() and Path(POWERSHELL).exists():
        try:
            r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                               text=True, errors="replace", timeout=15, stdin=subprocess.DEVNULL, cwd="/")
            val = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
        except (OSError, subprocess.SubprocessError, ValueError):
            val = None
    _cache[cle] = (time.time(), val)
    return val


def temperatures():
    """Les températures lisibles (°C) : les zones thermiques de Linux ; sous WSL, celles de Windows (ACPI, souvent réservées
    à l'administrateur : alors rien)."""
    t = []
    for z in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        v = _lire(z / "temp").strip()
        if v.lstrip("-").isdigit():
            t.append(round(int(v) / 1000, 1))
    if not t and est_wsl():
        w = _powershell("Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | "
                        "Select-Object -ExpandProperty CurrentTemperature | ConvertTo-Json -Compress", "chaleur")
        for k in ([w] if isinstance(w, (int, float)) else w if isinstance(w, list) else []):
            if isinstance(k, (int, float)) and k > 0:
                t.append(round(k / 10 - 273.15, 1))     # dixièmes de kelvin
    return t


def chaleur():
    t = temperatures()
    if not t:
        return "illisible (aucune sonde de température accessible" + (" depuis WSL" if est_wsl() else "") + ")"
    return f"{max(t)} °C au plus chaud ({len(t)} sonde{'s' if len(t) > 1 else ''})"


def batterie():
    """Comme pmset : « 87 %, sur secteur, se charge », ou « pas de batterie (sur secteur) »."""
    for b in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        cap, etat = _lire(b / "capacity").strip(), _lire(b / "status").strip()
        if cap.isdigit():
            et = {"Discharging": "sur batterie, se décharge", "Charging": "sur secteur, se charge", "Full": "sur secteur, chargée",
                  "Not charging": "sur secteur, branchée"}.get(etat, etat or "état inconnu")
            return f"{cap} %, {et}"
    if est_wsl():
        w = _powershell("Get-CimInstance -ClassName Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus | "
                        "ConvertTo-Json -Compress", "batterie")
        w = w[0] if isinstance(w, list) and w else w
        if isinstance(w, dict) and w.get("EstimatedChargeRemaining") is not None:
            st = {1: "sur batterie, se décharge", 2: "sur secteur", 3: "sur secteur, chargée", 6: "sur secteur, se charge",
                  7: "sur secteur, se charge", 8: "sur secteur, se charge", 9: "sur secteur, se charge"}.get(w.get("BatteryStatus"), "état inconnu")
            return f"{w['EstimatedChargeRemaining']} %, {st}"
        return "pas de batterie (sur secteur)"
    return "pas de batterie (sur secteur)"


def disque():
    """(libre, total) en octets : le disque de Windows (C:) sous WSL, sinon la racine."""
    for chemin in (["/mnt/c"] if est_wsl() else []) + ["/"]:
        try:
            u = shutil.disk_usage(chemin)
            return u.free, u.total
        except OSError:
            continue
    return None, None


def empreintes():
    """pid → (mémoire réelle en Mo, nom court) d'après ps (la forme d'interoception.empreintes)."""
    try:
        t = subprocess.run(["/bin/ps", "-axo", "pid=,rss=,comm="], capture_output=True, text=True, errors="replace", timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for l in t.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)$", l)
        if m:
            out[int(m.group(1))] = (int(m.group(2)) / 1024, m.group(3).strip())
    return out


def coeurs_logiques():
    return os.cpu_count() or 0
