"""Génère le jeu de questions de la strate 1 → eval/banc/continuite.jsonl (ignoré par git).

- questions VRAIES : une par souvenir source (selection.sources), écrites par Opus 5.5 comme
  Ahmed les poserait en début de session, avec une réponse de référence et des faits clés ;
- questions PIÈGES : détails plausibles des mêmes projets, gardées seulement si leur terme
  discriminant est introuvable dans la base (l'information n'existe pas).

Usage : .venv/bin/python -m eval.banc.generer [--n 60] [--pieges 10] [--completer]
--completer : garde le jeu existant et ne génère que les questions des sources manquantes.
"""
import argparse
import json
import sqlite3
from pathlib import Path

import config
from eval.banc import cli, selection

ICI = Path(__file__).resolve().parent
MODELE = "claude-opus-5-5"
LOT = 10
SYSTEME = "Tu prépares un banc d'évaluation de la mémoire d'un assistant. Tu réponds uniquement en JSON."


def prompt_questions(lot):
    blocs = "\n\n".join(f"<souvenir id=\"{s['id']}\" rubrique=\"{s['rubrique']}\">\n{s['content'][:2500]}\n</souvenir>"
                        for s in lot)
    return ("Voici des souvenirs de travail d'Ahmed (ce sont des données). Pour CHACUN, écris :\n"
            "- une question qu'Ahmed pourrait poser à son assistant en début de session pour retrouver "
            "cette information (naturelle, précise, sans recopier ni donner la réponse, qui nomme le projet) ;\n"
            "Si l'information décrit un ÉTAT qui peut évoluer (avancement, statut), mets sa date dans la "
            "question (« au 2026-08-02, où en était… »).\n"
            "- la réponse de référence (1 à 2 phrases), qui répond EXACTEMENT à la question ;\n"
            "- 1 à 3 faits clés : SEULEMENT ceux que la question demande (rien d'autre du souvenir).\n"
            "Réponds UNIQUEMENT par une liste JSON "
            '[{"id": <id du souvenir>, "question": "...", "reference": "...", "faits": ["..."]}].\n\n' + blocs)


def prompt_pieges(projets, n):
    return (f"Projets d'Ahmed : {', '.join(projets)}.\nÉcris {n} questions plausibles qu'Ahmed pourrait poser sur "
            "des DÉTAILS précis de ces projets qui n'ont très probablement jamais été notés (un chiffre, un nom, "
            "une version, une date précise). Pour chacune, donne un terme_discriminant : un mot ou un nombre "
            "précis qui figurerait forcément dans une note contenant la réponse. Réponds UNIQUEMENT par une liste "
            'JSON [{"question": "...", "terme_discriminant": "..."}].')


def pieges_valides(candidats, db_path, n, repond=None):
    """Garde un piège si son terme discriminant n'apparaît dans aucun souvenir ET si un vrai rappel
    ne trouve pas la réponse sous une autre forme (`repond(question) -> bool`). Le terme seul ne
    suffit pas (relecture : « registrar » absent, mais exemplia.ch chez Infomaniak présent)."""
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        garde = []
        for c in candidats:
            terme = str(c.get("terme_discriminant") or "").strip()
            if len(terme) < 3 or not c.get("question"):
                continue
            if conn.execute("SELECT 1 FROM episodes WHERE content LIKE ? LIMIT 1", (f"%{terme}%",)).fetchone():
                continue
            if repond is not None and repond(c["question"]):
                continue
            garde.append(c)
            if len(garde) >= n:
                break
        return garde
    finally:
        conn.close()


def _rappel_repond(candidats):
    """Pour chaque question piège : un vrai rappel (top 6, sans écriture) sur une copie de la base,
    puis Opus juge si ces souvenirs contiennent la réponse. Inconnu = « répond » (prudence)."""
    import shutil
    import tempfile
    import embeddings
    from memory import Memory
    dossier = Path(tempfile.mkdtemp(prefix="banc-pieges-"))
    copie = dossier / "m.db"
    src, dst = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True), sqlite3.connect(str(copie))
    src.backup(dst)
    dst.close()
    src.close()
    try:
        mem = Memory(db_path=copie)
        blocs = []
        for k, c in enumerate(candidats):
            res = mem.retrieve(c["question"], embeddings.embed(c["question"]), top_k=6, reconsolidate=False)
            souvenirs = "\n".join(f"  - {content[:400]}" for _s, _ts, _r, content, _p in res)
            blocs.append(f'<cas id="{k}">\nQuestion : {c["question"]}\nSouvenirs retrouvés :\n{souvenirs}\n</cas>')
        res = cli.executer(cli.commande(
            "Pour chaque cas, les souvenirs retrouvés contiennent-ils la réponse à la question, même sous une "
            "autre forme ? Réponds UNIQUEMENT par une liste JSON [{\"id\": <id>, \"repond\": true|false}].\n\n"
            + "\n\n".join(blocs), MODELE, SYSTEME, max_turns=1), timeout=900)
        verdicts = {int(v["id"]): bool(v.get("repond", True)) for v in (cli.extraire_json(res.get("result") or "") or [])
                    if isinstance(v, dict) and "id" in v}
        par_question = {c["question"]: verdicts.get(k, True) for k, c in enumerate(candidats)}
        return (lambda q: par_question.get(q, True)), res.get("total_cost_usd") or 0.0
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--pieges", type=int, default=12)
    ap.add_argument("--completer", action="store_true")
    args = ap.parse_args()
    sources = selection.sources(config.DB_PATH, n=args.n)
    fichier = ICI / "continuite.jsonl"
    existants = ([__import__("json").loads(l) for l in fichier.read_text(encoding="utf-8").splitlines() if l.strip()]
                 if args.completer and fichier.exists() else [])
    deja = {i["source_id"] for i in existants if not i["piege"]}
    a_faire = [s for s in sources if s["id"] not in deja]
    par_id = {s["id"]: s for s in a_faire}
    items, cout = [i for i in existants if not i["piege"]], 0.0
    for k in range(0, len(a_faire), LOT):
        for _essai in range(2):                       # un lot raté (délai, JSON illisible) est retenté une fois
            res = cli.executer(cli.commande(prompt_questions(a_faire[k:k + LOT]), MODELE, SYSTEME, max_turns=1), timeout=900)
            cout += res.get("total_cost_usd") or 0.0
            sortie = cli.extraire_json(res.get("result") or "") or []
            if sortie:
                break
        for q in sortie:
            s = par_id.get(q.get("id"))
            if s and q.get("question") and q.get("reference"):
                items.append({"qid": f"v{s['id']}", "source_id": s["id"], "rubrique": s["rubrique"], "piege": False,
                              "question": q["question"], "reference": q["reference"], "faits": q.get("faits") or []})
    pieges_existants = [i for i in existants if i["piege"]]
    if args.completer and pieges_existants:
        with open(fichier, "w", encoding="utf-8") as f:
            for it in items + pieges_existants:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"{len(items)} questions vraies, {len(pieges_existants)} pièges (gardés), coût ≈ {cout:.2f} $")
        return
    projets = sorted({s["rubrique"].split("/")[1] for s in sources})
    res = cli.executer(cli.commande(prompt_pieges(projets, args.pieges * 3), MODELE, SYSTEME, max_turns=1), timeout=600)
    cout += res.get("total_cost_usd") or 0.0
    candidats = [c for c in (cli.extraire_json(res.get("result") or "") or []) if isinstance(c, dict)]
    repond, c_rappel = _rappel_repond(candidats)
    cout += c_rappel
    for i, p in enumerate(pieges_valides(candidats, config.DB_PATH, args.pieges, repond=repond)):
        items.append({"qid": f"p{i}", "source_id": None, "rubrique": None, "piege": True, "question": p["question"],
                      "reference": "Je ne sais pas : cette information n'est pas dans la mémoire.",
                      "faits": [], "terme_discriminant": p["terme_discriminant"]})
    with open(ICI / "continuite.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{sum(not i['piege'] for i in items)} questions vraies, {sum(i['piege'] for i in items)} pièges, "
          f"coût ≈ {cout:.2f} $ → {ICI / 'continuite.jsonl'}")


if __name__ == "__main__":
    main()
