"""Simulation de vitesse de la voix de Hakim (27/10) : critères figés dans eval/vitesse/criteres.md AVANT de lancer.

Rejoue les 30 derniers messages oraux d'Ahmed (avec leur contexte) dans un cerveau Opus au persona de Hakim, en quatre
bras (effort actuel ou bas ; « parler avant l'outil » ou non), mesure le temps du premier mot, puis fait juger la
qualité par un Claude Opus neutre, à l'aveugle, dans les deux ordres. Reprenable ; résultats dans data/ (non versionné :
ils citent les conversations).

  .venv/bin/python -B eval/vitesse/simuler.py [--n 30] [--paralleles 3]
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
import config  # noqa: E402

CONVERSATION = Path.home() / "AIOS" / "jarvis" / "conversation.json"
PERSONA = RACINE / "jarvis" / "persona.md"
CLAUDE = os.environ.get("CLAUDE_BIN") or str(Path.home() / ".npm-global" / "bin" / "claude")
MESURES = config.DATA_DIR / "vitesse-sim.jsonl"
JUGEMENTS = config.DATA_DIR / "vitesse-sim-juge.jsonl"
RAPPORT = config.DATA_DIR / "vitesse-sim.md"
AVANT_OUTIL = ("- À l'oral (27/10, essai de vitesse) : si tu dois chercher avec un outil avant de répondre (mémoire, "
               "fichiers, web, courrier), dis d'abord à Ahmed une courte phrase naturelle, quelques mots sur ce que tu "
               "vas faire, PUIS cherche : ta première phrase part tout de suite à la voix.\n")
BRAS = {"A": {"effort": None, "avant": False}, "B": {"effort": "low", "avant": False},
        "C": {"effort": None, "avant": True}, "D": {"effort": "low", "avant": True}}
_verrou = threading.Lock()


def selection(n):
    m = json.loads(CONVERSATION.read_text(encoding="utf-8"))["messages"]
    out = []
    for k, x in enumerate(m):
        if x.get("qui") == "u" and x.get("oral") and len(str(x.get("texte", "")).split()) >= 6:
            ctx = [f"{'Ahmed' if y.get('qui') == 'u' else 'Hakim'} : {str(y.get('texte', ''))[:400]}" for y in m[max(0, k - 10):k]]
            out.append({"id": str(x["id"]), "ts": x.get("ts"), "texte": x["texte"], "contexte": ctx})
    return out[-n:]


def prompt(msg):
    quand = time.strftime("%A %d %B %Y, %H:%M", time.localtime((msg.get("ts") or 0) / 1000))
    return (f"[Horloge — {quand}]\n[Vos derniers échanges]\n" + "\n".join(msg["contexte"])
            + f"\n\n[Message oral d'Ahmed]\n{msg['texte']}")


def persona(avant):
    p = PERSONA.read_text(encoding="utf-8")
    return p + ("\n" + AVANT_OUTIL if avant else "")


def commande(b, texte, mcp):
    c = [CLAUDE, "-p", texte, "--model", "opus", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
         "--restricted", "--tools", "", "--strict-mcp-config", "--mcp-config", mcp, "--permission-mode", "dontAsk",
         "--allowedTools", "mcp__anamnese", "--max-turns", "4", "--no-session-persistence",
         "--append-system-prompt", persona(BRAS[b]["avant"])]
    return c + (["--effort", BRAS[b]["effort"]] if BRAS[b]["effort"] else [])


def env():
    e = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}      # le forfait, jamais l'API payante
    e["ANAMNESE_HEADLESS"] = "1"
    return e


def mesurer(cmd, cwd):
    """Temps depuis l'initialisation de claude : premier texte, premier outil, fin ; et le texte de la réponse."""
    r = {"t_init": None, "premier_mot_s": None, "premier_outil_s": None, "total_s": None, "texte": "", "outils": [],
         "tours": None, "erreur": None, "modeles": []}
    t0 = None
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, cwd=cwd, env=env(),
                         stdin=subprocess.DEVNULL)
    debut = time.monotonic()
    try:
        for ligne in p.stdout:
            maintenant = time.monotonic()
            if maintenant - debut > 300:
                r["erreur"] = "délai"
                break
            try:
                o = json.loads(ligne)
            except ValueError:
                continue
            if o.get("type") == "system" and o.get("subtype") == "init" and t0 is None:
                t0 = maintenant
            ev = o.get("event") or {}
            if o.get("type") == "stream_event" and t0 is not None and not o.get("parent_tool_use_id"):
                if ev.get("type") == "content_block_start" and (ev.get("content_block") or {}).get("type") == "tool_use":
                    r["outils"].append(ev["content_block"].get("name"))
                    if r["premier_outil_s"] is None:
                        r["premier_outil_s"] = round(maintenant - t0, 2)
                elif ev.get("type") == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
                    t = ev["delta"].get("text", "")
                    if t.strip() and r["premier_mot_s"] is None:
                        r["premier_mot_s"] = round(maintenant - t0, 2)
            if o.get("type") == "result":
                r.update(total_s=round(maintenant - (t0 or debut), 2), tours=o.get("num_turns"), texte=str(o.get("result") or ""),
                         modeles=sorted((o.get("modelUsage") or {}).keys()), erreur=r["erreur"] or (o.get("subtype") if o.get("is_error") else None))
    finally:
        if p.poll() is None:
            p.kill()                                                     # par son PID (Popen), jamais par motif
        p.wait()
    return r


def deja(f):
    out = {}
    try:
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            out[o["cle"]] = o
    except (OSError, ValueError):
        pass
    return out


def _ajouter(f, o):
    with _verrou, open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")


def juger_paire(msg, r1, r2):
    """'1', '2' ou 'egal' : quelle réponse est meilleure pour Ahmed (juge neutre, sans persona ni outils)."""
    texte = ("Tu évalues deux réponses possibles d'une IA, Hakim, à un message ORAL d'Ahmed (sa réponse sera lue à voix "
             "haute). Hakim tutoie Ahmed, il est chaleureux, direct, complice, avec des phrases courtes et naturelles à "
             "l'oral, et il est juste sur le fond.\n\nContexte récent :\n" + "\n".join(msg["contexte"])
             + f"\n\nMessage oral d'Ahmed :\n{msg['texte']}\n\nRÉPONSE 1 :\n{r1}\n\nRÉPONSE 2 :\n{r2}\n\n"
             "Laquelle est la meilleure réponse pour Ahmed (justesse, pertinence, ton de Hakim, adaptée à l'oral) ? "
             "Réponds sur la première ligne exactement « 1 », « 2 » ou « égal », puis une phrase de raison.")
    with tempfile.TemporaryDirectory(prefix="juge-") as vide:
        try:
            r = subprocess.run([CLAUDE, "-p", texte, "--model", "opus", "--restricted", "--tools", "", "--strict-mcp-config",
                                "--no-session-persistence", "--max-turns", "1"], capture_output=True, text=True, timeout=300,
                               cwd=vide, env=env(), stdin=subprocess.DEVNULL)
        except subprocess.SubprocessError:
            return None
    t = (r.stdout or "").strip().splitlines()
    if not t:
        return None
    x = t[0].strip().strip("«»*\" ").lower()
    return "1" if x.startswith("1") else ("2" if x.startswith("2") else ("egal" if x.startswith(("égal", "egal")) else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--paralleles", type=int, default=3)
    a = ap.parse_args()
    msgs = selection(a.n)
    faits = deja(MESURES)
    with tempfile.TemporaryDirectory(prefix="vitesse-") as dossier:
        mcp = str(Path(dossier) / "mcp.json")
        Path(mcp).write_text(json.dumps({"mcpServers": {"anamnese": {
            "command": str(RACINE / ".venv" / "bin" / "python"), "args": [str(RACINE / "mcp_server.py")],
            "env": {"ANAMNESE_SOURCE": "hakim", "ANAMNESE_LECTURE_SEULE": "1", "ANAMNESE_HEADLESS": "1"}}}}))
        travaux = [(m, b) for m in msgs for b in BRAS if f"{m['id']}:{b}" not in faits]

        def faire(t):
            m, b = t
            r = mesurer(commande(b, prompt(m), mcp), dossier)
            o = {"cle": f"{m['id']}:{b}", "id": m["id"], "bras": b, **r}
            _ajouter(MESURES, o)
            print(f"{o['cle']} : premier mot {r['premier_mot_s']} s, outil {r['premier_outil_s']}, {r['erreur'] or 'ok'}", flush=True)
        with ThreadPoolExecutor(a.paralleles) as ex:
            list(ex.map(faire, travaux))
    faits = deja(MESURES)
    juges = deja(JUGEMENTS)
    paires = [(m, x, y, ordre) for m in msgs for x, y in (("A", "B"), ("A", "C")) for ordre in (0, 1)
              if f"{m['id']}:{x}{y}:{ordre}" not in juges]

    def juger(t):
        m, x, y, ordre = t
        rx, ry = faits.get(f"{m['id']}:{x}", {}).get("texte"), faits.get(f"{m['id']}:{y}", {}).get("texte")
        if not rx or not ry:
            return
        v = juger_paire(m, rx, ry) if ordre == 0 else juger_paire(m, ry, rx)
        gagnant = None if v is None else ("egal" if v == "egal" else ((x if v == "1" else y) if ordre == 0 else (y if v == "1" else x)))
        _ajouter(JUGEMENTS, {"cle": f"{m['id']}:{x}{y}:{ordre}", "id": m["id"], "paire": x + y, "ordre": ordre, "gagnant": gagnant})
        print(f"juge {m['id']} {x}{y} ordre {ordre} : {gagnant}", flush=True)
    with ThreadPoolExecutor(a.paralleles) as ex:
        list(ex.map(juger, paires))
    rapport(msgs, deja(MESURES), deja(JUGEMENTS))
    print(f"Rapport : {RAPPORT}")


def rapport(msgs, faits, juges):
    med = lambda v: round(statistics.median(v), 2) if v else None
    L = ["# Simulation de vitesse de la voix — " + time.strftime("%d/%m %H:%M"), "",
         "Critères figés avant : eval/vitesse/criteres.md. Écarts entre bras seulement (contexte réduit).", "",
         "| bras | n | premier mot (médiane) | dont tours avec outil | outil avant le premier mot | erreurs |", "|---|---|---|---|---|---|"]
    for b in BRAS:
        r = [faits[f"{m['id']}:{b}"] for m in msgs if f"{m['id']}:{b}" in faits]
        pm = [x["premier_mot_s"] for x in r if x["premier_mot_s"] is not None]
        avec = [x["premier_mot_s"] for x in r if x["outils"] and x["premier_mot_s"] is not None]
        avant = sum(1 for x in r if x["premier_outil_s"] is not None and (x["premier_mot_s"] is None or x["premier_outil_s"] < x["premier_mot_s"]))
        L.append(f"| {b} | {len(r)} | {med(pm)} s | {med(avec)} s ({len(avec)}) | {avant} | {sum(1 for x in r if x['erreur'])} |")
    # gains appariés
    for x, y in (("A", "B"), ("A", "C"), ("A", "D")):
        d = [faits[f"{m['id']}:{x}"]["premier_mot_s"] - faits[f"{m['id']}:{y}"]["premier_mot_s"] for m in msgs
             if faits.get(f"{m['id']}:{x}", {}).get("premier_mot_s") is not None and faits.get(f"{m['id']}:{y}", {}).get("premier_mot_s") is not None]
        L.append(f"\nGain apparié {x}→{y} (premier mot) : médiane {med(d)} s sur {len(d)} messages.")
    d = [faits[f"{m['id']}:A"]["premier_mot_s"] - faits[f"{m['id']}:C"]["premier_mot_s"] for m in msgs
         if faits.get(f"{m['id']}:A", {}).get("premier_outil_s") is not None
         and (faits[f"{m['id']}:A"]["premier_mot_s"] or 1e9) > faits[f"{m['id']}:A"]["premier_outil_s"]
         and faits.get(f"{m['id']}:C", {}).get("premier_mot_s") is not None and faits[f"{m['id']}:A"].get("premier_mot_s") is not None]
    L.append(f"Gain A→C sur les messages où A a pris un outil avant de parler : médiane {med(d)} s sur {len(d)}.")
    for x, y in (("A", "B"), ("A", "C")):
        v = {}
        for m in msgs:
            g = [juges.get(f"{m['id']}:{x}{y}:{o}", {}).get("gagnant") for o in (0, 1)]
            if None in g:
                continue
            v[m["id"]] = g[0] if g[0] == g[1] else "egal"
        n = len(v)
        L.append(f"\nQualité {x} contre {y} ({n} paires, préférence comptée seulement si elle tient dans les deux ordres) : "
                 f"{x} préféré {sum(1 for g in v.values() if g == x)}, {y} préféré {sum(1 for g in v.values() if g == y)}, "
                 f"égal {sum(1 for g in v.values() if g == 'egal')}.")
    RAPPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
