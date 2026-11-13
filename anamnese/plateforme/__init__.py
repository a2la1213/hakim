"""La couche de plateforme (13/11, Ahmed : « que tout le code tourne aussi sur le PC de son ami, par WSL2 ; le Mac doit rester
EXACTEMENT comme aujourd'hui »).

Tout ce qui est propre au Mac (le bac à sable sandbox-exec, le trousseau, launchd, pmset/ioreg, osascript, afplay, MLX) garde son
code tel quel ; à chaque endroit, une seule ligne demande d'abord « suis-je sur le Mac ? » et, sinon, passe ici :
- plateforme.bac_a_sable : bubblewrap (bwrap), avec au moins les mêmes interdits ;
- plateforme.cles       : les clés dans des fichiers 600 (ou secret-tool), jamais dans le code ;
- plateforme.corps      : processeurs, mémoire, batterie et chaleur par /proc, /sys et, sous WSL, powershell.exe ;
- plateforme.systeme    : rester éveillé, notifier, jouer un son, retrouver un service (systemd utilisateur) ;
- plateforme.stt_cpu    : l'écoute par faster-whisper sur le processeur (int8), quand Azure ne répond pas.

Les profils de modules (profils.json) : « complet » (Hakim, rien ne change) ou un profil plus léger pour une machine sans GPU
(studio et chant éteints, Gemma petit ou éteint, voix et écoute par Azure). Le profil actif est écrit par l'installateur dans
~/AIOS/jarvis/profil-modules.json ; sans ce fichier : « complet ».
"""
import json
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent

# « mac » ou « linux » (WSL2 compris). ANAMNESE_SYSTEME ne sert qu'aux essais.
SYSTEME = os.environ.get("ANAMNESE_SYSTEME") or ("mac" if sys.platform == "darwin" else
                                                 "linux" if sys.platform.startswith("linux") else sys.platform)
MAC = SYSTEME == "mac"
LINUX = SYSTEME == "linux"

_wsl = None


def est_wsl():
    """Linux dans Windows (WSL2) : le noyau le dit (« microsoft » dans /proc/version) ou l'interopérabilité est enregistrée."""
    global _wsl
    if _wsl is None:
        try:
            _wsl = Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists() or \
                "microsoft" in Path("/proc/version").read_text(errors="replace").lower()
        except OSError:
            _wsl = False
    return _wsl


# ---- les profils de modules ----
PROFILS = ICI / "profils.json"
PROFIL_ACTIF = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis")) / "profil-modules.json"


def _lire_json(chemin, defaut):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def profils():
    return _lire_json(PROFILS, {}).get("profils", {})


def profil_actif(fichier=None):
    """{"nom": …, "modules": {…}, …} : le profil choisi (JARVIS_PROFIL, sinon le fichier de l'installateur), ses réglages de
    modules complétés par ceux du profil « complet » ; un nom inconnu retombe sur « complet » (rien ne s'éteint par erreur)."""
    tous = profils()
    choix = _lire_json(fichier or PROFIL_ACTIF, {})
    nom = os.environ.get("JARVIS_PROFIL") or (choix.get("profil") if isinstance(choix, dict) else None) or "complet"
    if nom not in tous:
        nom = "complet"
    base = dict((tous.get("complet") or {}).get("modules") or {})
    p = tous.get(nom) or {}
    modules = {**base, **(p.get("modules") or {})}
    if isinstance(choix, dict) and isinstance(choix.get("modules"), dict):      # les retouches de l'installateur
        modules.update({k: v for k, v in choix["modules"].items() if k in base})
    return {**p, "nom": nom, "modules": modules}


def module(nom, fichier=None):
    """La valeur d'un module dans le profil actif (True/False, ou un mot : « petit », « azure »…)."""
    return profil_actif(fichier)["modules"].get(nom)


def module_actif(nom, fichier=None):
    v = module(nom, fichier)
    return bool(v) and v not in ("eteint", "non", "off")


def outils_eteints(fichier=None):
    """Les outils MCP des modules éteints (ils ne sont pas proposés au cerveau)."""
    outils = _lire_json(PROFILS, {}).get("outils_par_module", {})
    return sorted({o for m, liste in outils.items() if not module_actif(m, fichier) for o in liste})


def phrase_eteint(nom):
    return (f"Ce module ({nom}) est éteint sur cette machine (profil « {profil_actif()['nom']} ») : "
            "il demande un vrai GPU ou n'a pas été choisi à l'installation.")
