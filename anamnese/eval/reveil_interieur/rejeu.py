"""Rejeu du juge du réveil intérieur sur les pensées et occupations passées (27/10). Lit la base en lecture seule,
juge chaque épisode avec Gemma, reprend là où il s'est arrêté, et écrit le rapport dans data/ (non versionné : il
cite les pensées de Hakim). Ne tourne que quand Ahmed ne parle pas à Hakim (feu vert d'Ahmed, 27/10 00:59 : « un trou
d'environ 30 minutes ») : avant chaque jugement, il attend que son dernier message ait au moins --calme-min minutes.

  nice -n 10 .venv/bin/python -B eval/reveil_interieur/rejeu.py --du 2026-10-18 --au 2026-10-26
"""
import argparse
import datetime
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

import config  # noqa: E402
import reveil_interieur  # noqa: E402
from engine import Engine  # noqa: E402

CONVERSATION = Path.home() / "AIOS" / "jarvis" / "conversation.json"
FAITS = config.DATA_DIR / "reveil-interieur-rejeu.jsonl"
RAPPORT = config.DATA_DIR / "reveil-interieur-rejeu.md"
SEUILS = (5, 6, 7, 8, 9)


def dernier_message_ahmed():
    try:
        m = [x for x in json.loads(CONVERSATION.read_text(encoding="utf-8")).get("messages", []) if x.get("qui") == "u"]
        return float(m[-1].get("ts") or m[-1].get("id")) / 1000.0 if m else 0.0
    except (OSError, ValueError, TypeError, IndexError):
        return 0.0


def attendre_le_calme(calme_s):
    annonce = False
    while time.time() - dernier_message_ahmed() < calme_s:
        if not annonce:
            print("Ahmed parle à Hakim : j'attends le calme…", flush=True)
            annonce = True
        time.sleep(60)


def episodes(du, au):
    db = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    debut = datetime.datetime.strptime(du, "%Y-%m-%d").timestamp()
    fin = (datetime.datetime.strptime(au, "%Y-%m-%d") + datetime.timedelta(days=1)).timestamp()
    return [{"id": i, "ts": ts, "texte": c} for i, ts, c in db.execute(
        "SELECT id, ts, content FROM episodes WHERE role='reflection' AND ts >= ? AND ts < ? "
        "AND (content LIKE '(pensée%' OR content LIKE '(occupation%') ORDER BY ts", (debut, fin))]


def deja_faits():
    out = {}
    try:
        for l in FAITS.read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            out[o["id"]] = o
    except (OSError, ValueError):
        pass
    return out


def rapport(eps, faits, du, au):
    jours = sorted({time.strftime("%Y-%m-%d", time.localtime(e["ts"])) for e in eps})
    lignes = [f"# Rejeu du juge du réveil intérieur — {du} au {au}", "",
              f"{len(eps)} épisodes ; jugés : {sum(1 for e in eps if e['id'] in faits)} ; illisibles : "
              f"{sum(1 for e in eps if e['id'] in faits and faits[e['id']]['jugement'] is None)}.", "",
              "| jour | épisodes | " + " | ".join(f"≥ {s}" for s in SEUILS) + " |",
              "|---|---|" + "---|" * len(SEUILS)]
    for j in jours + ["total"]:
        sel = [faits[e["id"]] for e in eps if e["id"] in faits
               and (j == "total" or time.strftime("%Y-%m-%d", time.localtime(e["ts"])) == j)]
        notes = [f["jugement"]["score"] for f in sel if f["jugement"]]
        lignes.append(f"| {j} | {len(sel)} | " + " | ".join(str(sum(1 for n in notes if n >= s)) for s in SEUILS) + " |")
    ok = [f for f in faits.values() if f["jugement"] and f["id"] in {e["id"] for e in eps}]
    for genre in ("pensée", "occupation"):
        g = [f for f in ok if f["texte"].startswith("(" + genre)]
        lignes.append(f"\n{genre}s : {len(g)} jugées, {sum(1 for f in g if f['jugement']['score'] >= 7)} à 7 ou plus.")
    lignes += ["", "Raisons à 7 ou plus : " + ", ".join(f"{r} {n}" for r, n in Counter(
        f["jugement"]["raison"] for f in ok if f["jugement"]["score"] >= 7).most_common()), "",
               "## Tous les jugements, du plus haut au plus bas", ""]
    for f in sorted(ok, key=lambda f: (-f["jugement"]["score"], f["ts"])):
        quand = time.strftime("%d/%m %H:%M", time.localtime(f["ts"]))
        lignes.append(f"- **{f['jugement']['score']}** {f['jugement']['raison']} — {quand} — "
                      f"{f['jugement']['pourquoi']}\n  > {f['texte'][:160]}")
    RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du", required=True)
    ap.add_argument("--au", required=True)
    ap.add_argument("--calme-min", type=float, default=10.0)
    ap.add_argument("--juge", choices=("claude", "gemma"), default="claude")      # comme en vrai : Claude, Gemma en secours
    a = ap.parse_args()
    eps = episodes(a.du, a.au)
    faits = deja_faits()
    eng = Engine(chat_model=config.DAEMON_MODEL)
    claude_fn = None
    if a.juge == "claude":
        import daemon
        claude_fn = daemon._claude_isole
    for k, e in enumerate(eps, 1):
        if e["id"] in faits:
            continue
        attendre_le_calme(a.calme_min * 60)
        j = reveil_interieur.juger(eng, e["texte"], "inconnue", 0, claude_fn=claude_fn)
        faits[e["id"]] = {"id": e["id"], "ts": e["ts"], "texte": e["texte"], "jugement": j}
        with open(FAITS, "a", encoding="utf-8") as h:
            h.write(json.dumps(faits[e["id"]], ensure_ascii=False) + "\n")
        print(f"{k}/{len(eps)} : {j['score'] if j else 'illisible'} ({j['juge'] if j else '-'})", flush=True)
    rapport(eps, faits, a.du, a.au)
    print(f"Rapport : {RAPPORT}")


if __name__ == "__main__":
    main()
