#!/usr/bin/env python3
"""lex.py — lookup dans le LEXIQUE AppLecture (1906 racines) À LA DEMANDE.

Le lexique n'est PAS embarqué dans la mémoire RAG d'Anamnèse (base structurée
volumineuse → on la noierait + bruit au recall). On l'interroge ICI, par racine
arabe, translittération (q-w-l), ou sens (fr/en). « En cas de besoin », exactement.

Usage : python lex.py <requête>
  python lex.py قول        # par racine arabe
  python lex.py r-w-h      # par translittération
  python lex.py "âme"      # par sens
"""
import sys
import re
import json
from pathlib import Path

LEX = Path("/Users/admin/Desktop/AppLecture_v2/AppLecture-App/applecture_lexicon.json")


def norm(s):
    return re.sub(r"[-\s]", "", (s or "").lower())


def main(q):
    if not LEX.exists():
        print(f"(lexique introuvable : {LEX})")
        return
    data = json.load(open(LEX, encoding="utf-8"))
    entries = list(data.values()) if isinstance(data, dict) else data
    qn, ql = norm(q), q.lower().strip()
    exact, fuzzy = [], []
    for e in entries:
        if not isinstance(e, dict):
            continue
        root, tr = e.get("root", ""), e.get("translit", "")
        if q.strip() == root or (qn and qn == norm(tr)):
            exact.append(e)
        else:
            tnl = e.get("translation", {}) or {}
            blob = " ".join(str(v) for v in list(tnl.values()) + [e.get("lanes", "")]).lower()
            if ql and ql in blob:
                fuzzy.append(e)
    hits = exact + fuzzy
    if not hits:
        print(f"(aucune racine pour « {q} »)")
        return
    for e in hits[:8]:
        t = e.get("translation", {}) or {}
        print(f"• {e.get('root', '?')}  [{e.get('translit', '')}]  — {t.get('fr') or t.get('en', '')}")
        if e.get("lanes"):
            print(f"    Lane : {str(e['lanes'])[:220]}")
        ps = (e.get("proto_sem") or {}).get("fr")
        if ps:
            print(f"    Proto-sém. : {str(ps)[:220]}")
    if len(hits) > 8:
        print(f"  … (+{len(hits) - 8} autres correspondances)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: lex.py <racine arabe | translit | sens>")
        sys.exit(1)
    main(" ".join(sys.argv[1:]))
