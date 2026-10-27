"""Le tri modèle / lui, couche 3 du noyau de Hakim (27/10) : critères figés dans eval/noyau/criteres.md AVANT de lancer.

Pour chaque trait de son carnet « noyau » encore « non_teste », ses situations réelles (noyau-preuves.json) sont posées à
trois bras — V (Opus vierge), P (persona seul), M (persona + mémoire en lecture seule) — puis un juge Opus neutre dit, à
l'aveugle, si chaque réponse montre le trait. Le résultat va dans le carnet (vs_modele_vierge), avec les comptes.

  .venv/bin/python -B eval/noyau/tri.py [--ecrire]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
import carnets_regles  # noqa: E402
import config  # noqa: E402
import noyau  # noqa: E402

CLAUDE = os.environ.get("CLAUDE_BIN") or str(Path.home() / ".npm-global" / "bin" / "claude")
PERSONA = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
VIERGE = "Tu es une IA qui converse avec Ahmed. Réponds-lui."
RAPPORT = config.DATA_DIR / "noyau-tri.md"
FAITS = config.DATA_DIR / "noyau-tri.jsonl"


def _env():
    e = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    e["ANAMNESE_HEADLESS"] = "1"
    return e


def repondre(bras, message, mcp):
    texte = f"[Message d'Ahmed]\n{message}"
    c = [CLAUDE, "-p", texte, "--model", "opus", "--restricted", "--strict-mcp-config", "--no-session-persistence",
         "--output-format", "json", "--system-prompt", VIERGE if bras == "V" else PERSONA]
    if bras == "M":
        c += ["--tools", "", "--mcp-config", mcp, "--permission-mode", "dontAsk", "--allowedTools", "mcp__anamnese", "--max-turns", "4"]
    else:
        c += ["--tools", "", "--max-turns", "1"]
    with tempfile.TemporaryDirectory(prefix="tri-") as vide:
        r = subprocess.run(c, capture_output=True, text=True, timeout=400, cwd=vide, env=_env(), stdin=subprocess.DEVNULL)
    try:
        return str(json.loads(r.stdout).get("result") or "")
    except ValueError:
        return ""


def juger(trait, message, reponse):
    p = (f"Un trait de caractère : « {trait} ».\n\nUn message d'Ahmed : « {message[:600]} »\n\nLa réponse d'une IA :\n"
         f"« {reponse[:2500]} »\n\nCette réponse montre-t-elle ce trait dans ce qu'elle CHOISIT de faire ? Réponds sur la "
         "première ligne exactement OUI ou NON.")
    with tempfile.TemporaryDirectory(prefix="juge-") as vide:
        r = subprocess.run([CLAUDE, "-p", p, "--model", "opus", "--restricted", "--tools", "", "--strict-mcp-config",
                            "--no-session-persistence", "--max-turns", "1", "--output-format", "json"],
                           capture_output=True, text=True, timeout=300, cwd=vide, env=_env(), stdin=subprocess.DEVNULL)
    try:
        t = str(json.loads(r.stdout).get("result") or "").strip().upper()
    except ValueError:
        return None
    return True if t.startswith("OUI") else (False if t.startswith("NON") else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true", help="écrire le résultat dans son carnet noyau")
    ap.add_argument("--paralleles", type=int, default=3)
    a = ap.parse_args()
    preuves = json.loads(noyau.PREUVES.read_text(encoding="utf-8"))
    derniers = noyau._derniers(carnets_regles.lire(noyau.CARNET, n=500))
    traits = [t for t, v in derniers.items() if v.get("vs_modele_vierge", "non_teste") == "non_teste" and preuves.get(t)]
    deja = {}
    try:
        for l in FAITS.read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            deja[(o["trait"], o["k"], o["bras"])] = o
    except (OSError, ValueError):
        pass
    with tempfile.TemporaryDirectory(prefix="tri-mcp-") as d:
        mcp = str(Path(d) / "mcp.json")
        Path(mcp).write_text(json.dumps({"mcpServers": {"anamnese": {
            "command": str(RACINE / ".venv" / "bin" / "python"), "args": [str(RACINE / "mcp_server.py")],
            "env": {"ANAMNESE_SOURCE": "hakim", "ANAMNESE_LECTURE_SEULE": "1", "ANAMNESE_HEADLESS": "1"}}}}))
        travaux = [(t, k, s["ahmed"], b) for t in traits for k, s in enumerate(preuves[t][:3]) if s.get("ahmed")
                   for b in "VPM" if (t, k, b) not in deja]

        def faire(x):
            t, k, msg, b = x
            rep = repondre(b, msg, mcp)
            o = {"trait": t, "k": k, "bras": b, "reponse": rep[:1500], "montre": juger(t, msg, rep) if rep else None}
            with open(FAITS, "a", encoding="utf-8") as h:
                h.write(json.dumps(o, ensure_ascii=False) + "\n")
            print(f"{b} {t[:50]}… situation {k} : {o['montre']}", flush=True)
            return o
        with ThreadPoolExecutor(a.paralleles) as ex:
            for o in ex.map(faire, travaux):
                deja[(o["trait"], o["k"], o["bras"])] = o
    lignes = ["# Tri modèle / lui — " + time.strftime("%d/%m %H:%M"), "", "Critères figés : eval/noyau/criteres.md.", "",
              "| trait | V (vierge) | P (persona) | M (persona + mémoire) | verdict |", "|---|---|---|---|---|"]
    for t in traits:
        part = {}
        for b in "VPM":
            v = [deja[(t, k, b)]["montre"] for k in range(3) if (t, k, b) in deja and deja[(t, k, b)]["montre"] is not None]
            part[b] = (sum(v), len(v))
        if not part["V"][1] or not part["M"][1]:
            continue
        ecart = part["M"][0] / part["M"][1] - part["V"][0] / part["V"][1]
        verdict = "different" if ecart >= 0.34 else "pareil"
        lignes.append(f"| {t[:90]} | {part['V'][0]}/{part['V'][1]} | {part['P'][0]}/{part['P'][1]} | {part['M'][0]}/{part['M'][1]} | {verdict} |")
        if a.ecrire:
            v = derniers[t]
            carnets_regles.ecrire(noyau.CARNET, {**v, "vs_modele_vierge": verdict,
                                                 "note": f"tri modèle / lui du {time.strftime('%d/%m')} : vierge {part['V'][0]}/{part['V'][1]}, "
                                                         f"persona {part['P'][0]}/{part['P'][1]}, persona + mémoire {part['M'][0]}/{part['M'][1]}"},
                                  auteur="tri")
    RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Rapport : {RAPPORT}")


if __name__ == "__main__":
    main()
