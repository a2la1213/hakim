"""Les recettes de calcul de Hakim (demande de Hakim, 2026-10-20 08:58, accord d'Ahmed) : une chaîne qui a marché
(ex. quasi-cristal : construction par cellules → lumière → analyse), sauvée sous un nom, relancée en une phrase avec
d'autres paramètres.

- Une recette = une commande zsh (la chaîne entière, enchaînée par &&) avec des paramètres {nom} et leurs valeurs
  par défaut ; rangée dans son atelier (atelier/recettes/<nom>.json), qu'il peut relire et corriger lui-même.
- recette_lancer(nom, params) remplit la commande (chaque valeur passée entre guillemets du shell ; un paramètre
  placé DANS des guillemets doubles est refusé, car le shell y développerait « $(…) » — relecture Opus du 2026-10-20)
  et la lance en TÂCHE DE FOND, dans le même bac à sable que son terminal (aucun droit de plus que lui) ;
  Ahmed est prévenu à la fin, et Hakim réveillé pour en dire le résultat, comme pour toute tâche de fond.
"""
import json
import re
import shlex
import time
from pathlib import Path

import terminal

DOSSIER = terminal.ATELIER / "recettes"
NOM = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
PARAM = re.compile(r"\{([a-z_][a-z0-9_]{0,30})\}")


class Refus(Exception):
    pass


def _fichier(nom, dossier=None):
    if not NOM.match(str(nom or "")):
        raise Refus("nom de recette : minuscules, chiffres, - et _ (2 à 41 caractères)")
    return Path(dossier or DOSSIER) / f"{nom}.json"


def _entre_guillemets_doubles(commande):
    """Les {param} placés entre guillemets doubles (où le shell développe $(…) et `…`)."""
    dedans, simple, trouves, i = False, False, [], 0
    while i < len(commande):
        c = commande[i]
        if c == "\\" and not simple:
            i += 2
            continue
        if c == "'" and not dedans:
            simple = not simple
        elif c == '"' and not simple:
            dedans = not dedans
        elif c == "{" and dedans:
            m = PARAM.match(commande, i)
            if m:
                trouves.append(m.group(1))
        i += 1
    return trouves


def sauver(nom, commande, description="", parametres=None, dossier=None):
    """Sauve (ou remplace) une recette. `commande` contient des {param} ; `parametres` leurs valeurs par défaut."""
    f = _fichier(nom, dossier)
    commande = str(commande or "").strip()
    if not commande or len(commande) > 20_000:
        raise Refus("commande vide ou trop longue (20 000 caractères au plus)")
    parametres = {str(k): str(v) for k, v in (parametres or {}).items()}
    doubles = _entre_guillemets_doubles(commande)
    if doubles:
        raise Refus(f"paramètre entre guillemets doubles ({', '.join(sorted(set(doubles)))}) : laisse-le hors des guillemets, "
                    "il est cité d'office")
    attendus = set(PARAM.findall(commande))
    inconnus = set(parametres) - attendus
    if inconnus:
        raise Refus(f"paramètres absents de la commande : {', '.join(sorted(inconnus))}")
    r = {"nom": nom, "description": str(description or "")[:500], "commande": commande, "parametres": parametres,
         "sauvee": time.strftime("%Y-%m-%d %H:%M"), "lancements": 0}
    try:
        r["lancements"] = json.loads(f.read_text(encoding="utf-8")).get("lancements", 0)
    except (OSError, ValueError):
        pass
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    manquants = sorted(attendus - set(parametres))
    return r, manquants


def remplir(recette, params=None):
    """La commande avec ses paramètres (valeurs par défaut, puis celles données), chacune citée pour le shell."""
    valeurs = {**recette.get("parametres", {}), **{str(k): str(v) for k, v in (params or {}).items()}}
    inconnus = set(params or {}) - set(PARAM.findall(recette["commande"]))
    if inconnus:
        raise Refus(f"paramètres inconnus pour cette recette : {', '.join(sorted(inconnus))}")
    manquants = [p for p in PARAM.findall(recette["commande"]) if p not in valeurs]
    if manquants:
        raise Refus(f"paramètres sans valeur : {', '.join(sorted(set(manquants)))}")
    if _entre_guillemets_doubles(recette["commande"]):
        raise Refus("un paramètre est entre guillemets doubles dans cette recette : corrige-la (recette_sauver)")
    return PARAM.sub(lambda m: shlex.quote(valeurs[m.group(1)]), recette["commande"])


def lire(nom, dossier=None):
    try:
        return json.loads(_fichier(nom, dossier).read_text(encoding="utf-8"))
    except OSError:
        raise Refus(f"recette inconnue : {nom}")
    except ValueError:
        raise Refus(f"recette illisible : {nom} (corrige son fichier dans atelier/recettes)")


def lancer(nom, params=None, delai_s=3600, dossier=None, lanceur=None):
    r = lire(nom, dossier)
    commande = remplir(r, params)
    import taches
    tid = (lanceur or taches.lancer)(commande, delai_s)
    r["lancements"] = int(r.get("lancements", 0)) + 1
    r["dernier"] = {"quand": time.strftime("%Y-%m-%d %H:%M"), "params": {str(k): str(v) for k, v in (params or {}).items()}, "tache": tid}
    _fichier(nom, dossier).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return tid, commande


def liste(dossier=None):
    d = Path(dossier or DOSSIER)
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        p = ", ".join(f"{k}={v}" for k, v in r.get("parametres", {}).items())
        out.append(f"- {r.get('nom')} : {r.get('description') or '(sans description)'}" + (f" — paramètres : {p}" if p else "")
                   + f" — lancée {r.get('lancements', 0)} fois")
    return "\n".join(out) or "Aucune recette (recette_sauver pour en créer une)."
