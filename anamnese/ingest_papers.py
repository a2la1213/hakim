#!/usr/bin/env python3
"""ingest_papers.py — range les distillations de papers (produites par le workflow
Claude qui a lu les PDF) dans la MÉMOIRE externe d'Anamnèse (RAG), comme CONNAISSANCE.

Ce sont des FAITS/connaissances -> kind='reference' (jamais dans un LoRA).
Granularité fine : 1 entrée résumé + 1 entrée par affirmation-clé, chacune embeddée
(model2vec, offline) et taguée [Paper · <fichier>] pour la citation.

Usage : PYTHONPATH=~/Desktop/anamnese .venv/bin/python ingest_papers.py <workflow_output.json>
"""
import sys
import json

import config  # noqa: F401 (assure le bon sys.path / ROOT)
import embeddings
from memory import Memory


def main(out_path):
    data = json.load(open(out_path, encoding="utf-8"))
    dists = (data.get("result") or {}).get("distillations") or []
    mem = Memory()
    n_papers, n_entries, skipped = 0, 0, []
    for d in dists:
        if not d.get("readOk"):
            skipped.append(d.get("file", "?"))
            continue
        file = (d.get("file") or "").strip()
        title = (d.get("title") or "").strip()
        head = f"[Paper · {file}] {title}".strip()
        topics = ", ".join(d.get("topics") or [])
        refs = ", ".join(d.get("quranRefs") or [])
        main = f"{head}\n{(d.get('oneLine') or '').strip()}\n{(d.get('summary') or '').strip()}".strip()
        if refs:
            main += f"\nRéfs coraniques : {refs}"
        if topics:
            main += f"\nThèmes : {topics}"
        mem.add("reference", main, importance=0.6, embedding=embeddings.embed(main))
        n_entries += 1
        for claim in (d.get("keyClaims") or []):
            c = (claim or "").strip()
            if len(c) < 15:
                continue
            entry = f"{head} — {c}"
            mem.add("reference", entry, importance=0.5, embedding=embeddings.embed(entry))
            n_entries += 1
        n_papers += 1
    print(f"✅ Ingéré {n_papers} papers → {n_entries} entrées 'reference' dans la mémoire.")
    if skipped:
        print(f"⚠️  Non lus ({len(skipped)}) : {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: ingest_papers.py <workflow_output.json>")
        sys.exit(1)
    main(sys.argv[1])
