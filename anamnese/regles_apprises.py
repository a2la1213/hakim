"""Des erreurs aux règles, niveau 2 (proposition de Hakim, feu vert d'Ahmed le 2026-10-22 à 12:52, avec ses garde-fous).

1. Le carnet d'erreurs entier (carnet.py) est regroupé PAR LE SENS par Sonnet (le test de Hakim du 22/10 : par les mots,
   2 paires et aucun groupe ; par le sens, des groupes lisibles) ; un groupe compte à partir de 3 erreurs.
2. Pour chaque groupe, Sonnet propose UNE règle courte (25 mots au plus) avec ses sources (les erreurs d'origine), et
   dit si elle double ou contredit une règle déjà en vigueur (regles-de-session.md).
3. Les propositions attendent Ahmed (une par une, sources visibles) ; acceptée, une règle entre dans la partie
   « Règles apprises » de regles-de-session.md avec sa date et ses sources, et peut être retirée. 10 règles apprises
   actives au plus (le fichier est lu à chaque conversation : des jetons, et des risques de contradiction).
Rien n'est allumé tant qu'Ahmed n'a pas vu les groupes de ce premier essai (garde-fou 1 de Hakim).
Fichiers : ~/AIOS/jarvis/regles/ (propositions.jsonl, essais).
"""
import json
import re
import subprocess
import time
from pathlib import Path

import carnet

DOSSIER = Path.home() / "AIOS" / "jarvis" / "regles"
REGLES = Path.home() / "AIOS" / "jarvis" / "regles-de-session.md"
CLAUDE = Path.home() / ".npm-global" / "bin" / "claude"
GROUPE_MIN, MOTS_MAX, ACTIVES_MAX = 3, 25, 10

CONSIGNE = """Voici le carnet d'erreurs d'une IA (Hakim), chacune avec son identifiant et sa correction, puis les règles déjà en
vigueur. (1) Regroupe les erreurs PAR LE SENS, selon la cause commune (pas le sujet) : une erreur va dans un groupe au plus,
et un groupe n'existe qu'à partir de 3 erreurs ; les autres restent seules. (2) Pour chaque groupe, propose UNE règle courte
(25 mots au plus), concrète, qui aurait évité ces erreurs, et dis si elle DOUBLE ou CONTREDIT une règle en vigueur (son numéro).
Réponds UNIQUEMENT par un objet JSON :
{"groupes": [{"nom": "...", "cause": "...", "erreurs": ["id", ...], "regle": "...", "double": null | <n°>, "contredit": null | <n°>}],
 "seules": ["id", ...]}"""


def _prompt(erreurs, regles):
    lignes = [f"- {e['id']} : {e['quoi'][:500]}" + (f" → correction : {e['correction'][:300]}" if e.get("correction") else "")
              for e in erreurs]
    return CONSIGNE + "\n\nCARNET :\n" + "\n".join(lignes) + "\n\nRÈGLES EN VIGUEUR :\n" + (regles or "(aucune)")


def _claude(prompt):
    r = subprocess.run([str(CLAUDE), "-p", "--model", "sonnet", "--max-turns", "1", "--strict-mcp-config", "--mcp-config",
                        '{"mcpServers":{}}', "--no-session-persistence", "--allowedTools", ""],
                       input=prompt, capture_output=True, text=True, timeout=900)
    return r.stdout


def regrouper(erreurs=None, regles=None, lancer=None):
    """Rend {"groupes": [...], "seules": [...], "refus": [...]} — les groupes vérifiés (identifiants connus, 3 erreurs au
    moins, pas d'erreur dans deux groupes, règle de 25 mots au plus)."""
    erreurs = carnet.erreurs() if erreurs is None else erreurs
    if regles is None:
        try:
            regles = REGLES.read_text(encoding="utf-8")
        except OSError:
            regles = ""
    sortie = (lancer or _claude)(_prompt(erreurs, regles)) or ""
    m = re.search(r"\{[\s\S]*\}", sortie)
    try:
        d = json.loads(m.group(0)) if m else {}
    except ValueError:
        d = {}
    connus, vus, groupes, refus = {e["id"] for e in erreurs}, set(), [], []
    for g in d.get("groupes") or []:
        ids = [i for i in g.get("erreurs") or [] if i in connus and i not in vus]
        regle = re.sub(r"\s+", " ", str(g.get("regle") or "")).strip()
        if len(ids) < GROUPE_MIN:
            refus.append({"nom": g.get("nom"), "raison": f"{len(ids)} erreur(s) valides seulement"})
            continue
        if not regle or len(regle.split()) > MOTS_MAX:
            refus.append({"nom": g.get("nom"), "raison": "règle absente ou trop longue"})
            continue
        vus.update(ids)
        groupes.append({"nom": str(g.get("nom", ""))[:80], "cause": str(g.get("cause", ""))[:200], "erreurs": ids, "regle": regle,
                        "double": g.get("double"), "contredit": g.get("contredit")})
    return {"groupes": groupes, "seules": [e["id"] for e in erreurs if e["id"] not in vus], "refus": refus}


def essai(dossier=None, lancer=None):
    """Le premier essai sur le vrai carnet, écrit pour être relu à la main (rien n'est proposé ni allumé)."""
    d = Path(dossier or DOSSIER)
    d.mkdir(parents=True, exist_ok=True)
    erreurs = carnet.erreurs()
    r = regrouper(erreurs, lancer=lancer)
    par_id = {e["id"]: e for e in erreurs}
    lignes = [f"# Essai du regroupement des erreurs par le sens ({time.strftime('%Y-%m-%d %H:%M')}) — à relire à la main",
              f"{len(erreurs)} erreurs ; {len(r['groupes'])} groupe(s) de {GROUPE_MIN} ou plus ; {len(r['seules'])} seule(s).", ""]
    for k, g in enumerate(r["groupes"], 1):
        lignes += [f"## Groupe {k} : {g['nom']} ({len(g['erreurs'])} erreurs)", f"Cause : {g['cause']}",
                   f"Règle proposée : « {g['regle']} »"
                   + (f" — DOUBLE la règle {g['double']}" if g.get("double") else "") + (f" — CONTREDIT la règle {g['contredit']}" if g.get("contredit") else "")]
        lignes += [f"- {i} : {par_id[i]['quoi'][:220]}" for i in g["erreurs"]] + [""]
    if r["refus"]:
        lignes += ["## Groupes écartés par la vérification"] + [f"- {x['nom']} : {x['raison']}" for x in r["refus"]] + [""]
    f = d / f"essai-{time.strftime('%Y%m%d-%H%M')}.md"
    f.write_text("\n".join(lignes), encoding="utf-8")
    (d / "dernier-essai.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return f, r
