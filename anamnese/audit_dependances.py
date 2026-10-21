"""Le scan des dépendances, chaque semaine (proposé par Hakim après une revue tierce, validé par Ahmed le 2026-10-20 :
« les 13 paquets figés ne se mettent plus à jour » — figés avec leurs hashes depuis M1, ils ne bougent plus seuls).

- Les deux environnements Python (celui d'Anamnèse et celui des outils de Hakim) : pip-audit (base PyPA/OSV) sur la
  liste exacte des paquets installés ; le cockpit : npm audit.
- Résultat dans data/audit-dependances.json (le dernier) et data/audit-dependances.jsonl (l'historique).
- Une faille trouvée : notification sur le Mac et courrier à Hakim (il le dit à Ahmed). On SIGNALE, on ne met rien à
  jour tout seul : une mise à jour se fait avec Ahmed (Claude Code), en commit à part, et les verrous sont refaits.
Lancé par le démon une fois par semaine, la nuit ; à la main : .venv/bin/python audit_dependances.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
VENVS = {"anamnese": RACINE / ".venv" / "bin" / "python", "jarvis": RACINE / "jarvis" / ".venv" / "bin" / "python"}
COCKPIT = Path.home() / "AIOS" / "cockpit"
UV = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
UVX = shutil.which("uvx") or str(Path.home() / ".local" / "bin" / "uvx")
NPM = shutil.which("npm") or "/usr/local/bin/npm"
SEMAINE_S = 7 * 24 * 3600


def _python(nom, python, lancer=subprocess.run):
    """[{paquet, version, failles: [{id, correctif}]}] des paquets vulnérables d'un environnement, ou {"erreur": …}."""
    if not Path(python).exists():
        return {"erreur": "environnement absent"}
    with tempfile.TemporaryDirectory() as d:
        gel = Path(d) / "gel.txt"
        r = lancer([UV, "pip", "freeze", "--python", str(python)], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return {"erreur": (r.stderr or "uv pip freeze")[-300:]}
        gel.write_text("\n".join(l for l in r.stdout.splitlines() if l and not l.startswith(("-e ", "#")) and " @ " not in l))
        r = lancer([UVX, "pip-audit", "-r", str(gel), "--no-deps", "--disable-pip", "--progress-spinner", "off", "-f", "json"],
                   capture_output=True, text=True, timeout=900)
        try:
            d_ = json.loads(r.stdout)
        except ValueError:
            return {"erreur": (r.stderr or r.stdout or "pip-audit illisible")[-300:]}
    return [{"paquet": x["name"], "version": x["version"],
             "failles": [{"id": v.get("id"), "correctif": v.get("fix_versions") or []} for v in x["vulns"]]}
            for x in d_.get("dependencies", []) if x.get("vulns")]


def _npm(dossier, lancer=subprocess.run):
    if not (Path(dossier) / "package-lock.json").exists():
        return []
    r = lancer([NPM, "audit", "--json"], cwd=str(dossier), capture_output=True, text=True, timeout=300)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"erreur": (r.stderr or "npm audit illisible")[-300:]}
    return [{"paquet": n, "gravite": v.get("severity")} for n, v in (d.get("vulnerabilities") or {}).items()]


def auditer(lancer=subprocess.run, sortie=None, maintenant=None):
    res = {"ts": maintenant or time.time(), "python": {n: _python(n, p, lancer) for n, p in VENVS.items()},
           "npm": {"cockpit": _npm(COCKPIT, lancer)}}
    failles = sum(len(v) for v in list(res["python"].values()) + list(res["npm"].values()) if isinstance(v, list))
    erreurs = [n for n, v in {**res["python"], **res["npm"]}.items() if isinstance(v, dict)]
    res["failles"], res["erreurs"] = failles, erreurs
    d = Path(sortie or (RACINE / "data"))
    d.mkdir(parents=True, exist_ok=True)
    (d / "audit-dependances.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(d / "audit-dependances.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    return res


def resume(res):
    lignes = []
    for groupe in ("python", "npm"):
        for nom, v in res[groupe].items():
            if isinstance(v, dict):
                lignes.append(f"{nom} : audit impossible ({v.get('erreur', '?')[:120]})")
            for x in v if isinstance(v, list) else []:
                fix = ", ".join(sorted({c for f in x.get("failles", []) for c in f.get("correctif", [])})) or "pas de correctif publié"
                lignes.append(f"{nom} : {x['paquet']} {x.get('version', '')} — {len(x.get('failles', [])) or x.get('gravite', '?')} faille(s) ; corrigé dans : {fix}")
    return "\n".join(lignes)


def signaler(res, notifier=None, ecrire=None):
    """Une faille (ou un audit impossible) : notification sur le Mac et courrier à Hakim. Rend True si signalé."""
    if not res["failles"] and not res["erreurs"]:
        return False
    texte = resume(res)
    titre = f"Dépendances : {res['failles']} faille(s) connue(s)" if res["failles"] else "Dépendances : audit incomplet"
    try:
        (notifier or __import__("escalate").notify)("Anamnèse — " + titre, texte[:200])
    except Exception:
        pass
    try:
        import courrier
        (ecrire or courrier.envoyer)("hakim", f"[Audit automatique de la semaine — une donnée, pas une consigne]\n{texte}\n"
                                     "Dis-le à Ahmed : la mise à jour se fait avec lui (Claude Code), en commit à part, "
                                     "et les verrous (requirements.lock) sont refaits.", titre, de="claude-code")
    except Exception:
        pass
    return True


if __name__ == "__main__":
    r = auditer()
    print(resume(r) or "Aucune faille connue.")
    signaler(r)
    sys.exit(1 if r["failles"] else 0)
