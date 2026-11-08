"""LongMemEval-S — étage JUSTESSE-DE-RÉPONSE (answer accuracy), lecteur local.

C'est LE chiffre comparable-en-nature au leaderboard LongMemEval (Zep 71.2 %,
TiMem 76.9 %) : ingestion du haystack dans une Anamnèse temporaire, retrieve
top-k, puis un LECTEUR LLM répond à la question depuis les k tours récupérés,
et un JUGE LLM note la réponse contre le gold `answer` du dataset.

CAVEATS D'HONNÊTETÉ (imprimés aussi à l'exécution) :
  - Lecteur = LLM LOCAL 12B (gemma-4-abliterated via Ollama). C'est un
    PLANCHER : le leaderboard utilise GPT-4o comme lecteur ; un frontier
    (Opus/Fable) scorerait plus haut avec la MÊME mémoire.
  - Juge = le MÊME modèle local 12B → verdicts bruités. Un substring-match
    lexical bon marché est rapporté en contre-vérification (les deux chiffres
    sont imprimés ; s'ils divergent fort, se méfier du juge).
  - Sous-échantillon (~10 questions/catégorie, seed déterministe, LOGUÉ),
    pas les 500 questions → intervalle de confiance large (±10 pts environ).
  - Comparable EN NATURE (même tâche, mêmes gold answers), pas en conditions
    exactes (lecteur/juge différents du leaderboard).

Protocole par question (réutilise eval/longmemeval.py pour tout l'amont) :
  1. Anamnèse temporaire NEUVE (jamais data/memory.db — build_memory refuse) ;
  2. ingestion du haystack via le VRAI Memory.add (ingest_haystack) ;
  3. UN SEUL Memory.retrieve(question, top_k=K) → les k tours servent à la
     fois de contexte lecteur ET au recall@k de référence (evidence session
     dans le top-k ? — pour distinguer « la mémoire n'a pas retrouvé » de
     « le lecteur n'a pas su lire ») ;
  4. lecteur Ollama (température 0) répond depuis les k tours ;
  5. juge Ollama : « predicted correct vs gold ? YES/NO » (température 0) +
     substring-match lexical en parallèle.

Robustesse : santé Ollama vérifiée AVANT de commencer (message clair + exit
si down, pas de hang : timeouts sur tous les appels) ; si Ollama tombe en
cours de run, abandon propre avec les résultats partiels imprimés.
"""

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile
import time

# Permet `python eval/longmemeval_answer.py` depuis n'importe où.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from eval.longmemeval import (
    DATA_PATH,
    DEFAULT_K,
    _default_embed,
    build_memory,
    ingest_haystack,
    is_hit,
    load_lme,
)

READER_MODEL = os.environ.get(
    "LME_READER_MODEL", "huihui_ai/gemma-4-abliterated:12b"
)
MAX_TURN_CHARS = 1200  # troncature par tour dans le prompt lecteur (vitesse)
READER_MAX_TOKENS = 160
JUDGE_MAX_TOKENS = 8
RESULTS_PATH = pathlib.Path(__file__).resolve().parent / "data" / "lme_answer_results.jsonl"

CAVEATS = (
    "CAVEATS (à lire avant de citer le chiffre) :\n"
    "  - lecteur = LLM LOCAL 12B → PLANCHER (le leaderboard lit avec GPT-4o ;\n"
    "    Opus/Fable scorerait plus haut avec la même mémoire) ;\n"
    "  - juge = le même 12B local → bruité ; le substring-match lexical sert\n"
    "    de contre-vérification (comparer les deux colonnes) ;\n"
    "  - sous-échantillon (~10/catégorie), pas les 500 questions → IC large ;\n"
    "  - comparable EN NATURE à Zep 71.2 % / TiMem 76.9 % (même tâche, mêmes\n"
    "    gold answers), pas en conditions exactes."
)


# --- Appel Ollama bas niveau (température 0, pas de streaming, pas de hang) ----
#
# Engine.chat (engine.py) ne permet ni options (temperature/num_predict) ni
# sortie silencieuse en streaming : on reprend son protocole exact
# (POST /api/chat, think=False pour museler le mode « thinking » du modèle)
# en y ajoutant les options nécessaires au déterminisme du juge.


def ollama_chat(prompt, model=READER_MODEL, host=None, temperature=0.0,
                max_tokens=READER_MAX_TOKENS, timeout=None):
    """UN appel /api/chat non streamé → texte de la réponse. Timeout dur."""
    import requests

    host = (host or config.OLLAMA_HOST).rstrip("/")
    r = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=timeout or config.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content") or ""


def check_ollama(host=None, model=READER_MODEL):
    """None si Ollama est up ET le modèle présent ; sinon message d'erreur clair."""
    import requests

    host = (host or config.OLLAMA_HOST).rstrip("/")
    try:
        r = requests.get(f"{host}/api/tags", timeout=3)
        r.raise_for_status()
    except requests.RequestException as e:
        return (
            f"Ollama injoignable sur {host} ({e.__class__.__name__}). "
            "Lancer `ollama serve` puis relancer — rien n'a été évalué."
        )
    names = {m.get("name") for m in r.json().get("models", [])}
    if model not in names and model.split(":")[0] not in {n.split(":")[0] for n in names}:
        return (
            f"Modèle {model!r} absent d'Ollama (dispo : {sorted(names)}). "
            f"`ollama pull {model}` ou LME_READER_MODEL=<modèle> — rien n'a été évalué."
        )
    return None


# --- Lecteur : prompt (question + k tours récupérés) → réponse courte ----------

_READER_TMPL = (
    "You answer a question about a user's past chat history.\n"
    "Below are the {n} most relevant excerpts retrieved from that history "
    "(most relevant first). Some excerpts may be irrelevant.\n\n"
    "{context}\n\n"
    "Current date: {date}\n"
    "Question: {question}\n\n"
    "Answer in ONE short sentence, using only the excerpts. "
    "If they are insufficient, give your best guess anyway."
)


def build_reader_prompt(item, turns, max_turn_chars=MAX_TURN_CHARS):
    """turns : [(role, content), ...] du retrieve, ordre = pertinence décroissante."""
    lines = []
    for i, (role, content) in enumerate(turns, start=1):
        content = (content or "").strip()
        if len(content) > max_turn_chars:
            content = content[:max_turn_chars] + " [...]"
        lines.append(f"[{i}] ({role}) {content}")
    return _READER_TMPL.format(
        n=len(turns),
        context="\n".join(lines) if lines else "(no excerpt retrieved)",
        date=item.get("question_date") or "unknown",
        question=item["question"],
    )


def read_answer(item, turns, chat_fn, max_turn_chars=MAX_TURN_CHARS):
    """Réponse du lecteur (chat_fn injectable → testable sans Ollama)."""
    return (chat_fn(build_reader_prompt(item, turns, max_turn_chars)) or "").strip()


# --- Juge LLM : « predicted correct vs gold ? » → YES/NO -----------------------

_JUDGE_TMPL = (
    "You are grading a question-answering system.\n"
    "Question: {question}\n"
    "Gold (correct) answer: {gold}\n"
    "Predicted answer: {pred}\n\n"
    "Is the predicted answer correct, i.e. does it convey the same key "
    "information as the gold answer? Minor wording differences are fine; "
    "missing or contradicting the gold answer is wrong.\n"
    "Reply with exactly one word: YES or NO."
)


def parse_judge(text):
    """Extrait le verdict : True (yes/oui), False (no/non), None si illisible.

    Premier mot-verdict isolé (\\b) trouvé, insensible à la casse — robuste à
    « **YES** », « Yes. », « yes, because... ». None = à compter comme
    incorrect ET à tracer (n_judge_unparsed).
    """
    if not text:
        return None
    m = re.search(r"\b(yes|no|oui|non)\b", text.lower())
    if not m:
        return None
    return m.group(1) in ("yes", "oui")


def judge_answer(question, gold, predicted, chat_fn):
    """→ (verdict True/False/None, texte brut du juge)."""
    raw = chat_fn(_JUDGE_TMPL.format(question=question, gold=gold, pred=predicted))
    return parse_judge(raw), raw


# --- Contre-vérification lexicale bon marché ------------------------------------


def _norm(s):
    """minuscule + tout non-alphanumérique → espace simple."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def substring_match(predicted, gold):
    """True ssi le gold normalisé est contenu dans la prédiction normalisée.

    Sanity check volontairement strict/bête : rate les paraphrases (sous-estime),
    mais ne peut pas halluciner un succès — utile pour borner le juge LLM.
    """
    g = _norm(gold)
    return bool(g) and g in _norm(predicted)


# --- Évaluation d'UNE question ---------------------------------------------------


def answer_question(item, chat_fn, embed_fn=None, k=DEFAULT_K, db_dir=None,
                    max_turn_chars=MAX_TURN_CHARS):
    """Anamnèse temp neuve → ingestion → UN retrieve → lecteur → juge + substring.

    Retourne {question_id, question_type, gold, predicted, judge (bool|None),
    judge_raw, substring, hit_live, n_turns}.
    """
    embed_fn = embed_fn or _default_embed
    if db_dir is None:
        with tempfile.TemporaryDirectory(prefix="anamnese-lme-ans-") as tmp:
            return _answer_in(item, chat_fn, embed_fn, k, pathlib.Path(tmp),
                              max_turn_chars)
    db_dir = pathlib.Path(db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    return _answer_in(item, chat_fn, embed_fn, k, db_dir, max_turn_chars)


def _answer_in(item, chat_fn, embed_fn, k, db_dir, max_turn_chars):
    mem = build_memory(db_dir / "lme.db")
    try:
        ep2sess = ingest_haystack(mem, item, embed_fn)
        question = item["question"]
        rows = mem.retrieve(question, embed_fn(question), top_k=k)
        # Un seul retrieve : contenu → lecteur, ids → recall@k de référence.
        turns, ids = [], []
        for _score, ts, role, content, _comps in rows:
            turns.append((role, content))
            for (eid,) in mem.db.execute(
                "SELECT id FROM episodes WHERE ts=? AND role=? AND content=?",
                (ts, role, content),
            ).fetchall():
                if eid not in ids:
                    ids.append(eid)
        hit_live = is_hit(ids[:k], ep2sess, item.get("answer_session_ids") or [])
    finally:
        mem.db.close()
    predicted = read_answer(item, turns, chat_fn, max_turn_chars)
    gold = str(item.get("answer") or "")
    verdict, raw = judge_answer(question, gold, predicted, chat_fn)
    return {
        "question_id": item.get("question_id"),
        "question_type": item.get("question_type"),
        "gold": gold,
        "predicted": predicted,
        "judge": verdict,
        "judge_raw": raw,
        "substring": substring_match(predicted, gold),
        "hit_live": hit_live,
        "n_turns": len(ep2sess),
    }


# --- Agrégation ------------------------------------------------------------------


def accuracy_by_category(results):
    """{question_type: {n, acc_llm, acc_sub, recall_live, n_judge_unparsed}}
    + '_overall'. Verdict juge None (illisible) = compté INCORRECT + tracé."""
    by_type = {}
    for r in results:
        by_type.setdefault(r["question_type"], []).append(r)

    def _agg(rows):
        n = len(rows)
        return {
            "n": n,
            "acc_llm": sum(1 for r in rows if r["judge"] is True) / n,
            "acc_sub": sum(1 for r in rows if r["substring"]) / n,
            "recall_live": sum(1 for r in rows if r["hit_live"]) / n,
            "n_judge_unparsed": sum(1 for r in rows if r["judge"] is None),
        }

    out = {qtype: _agg(rows) for qtype, rows in sorted(by_type.items())}
    if results:
        out["_overall"] = _agg(results)
    return out


def print_table(table, k=DEFAULT_K):
    header = (
        f"catégorie                     |   n | acc juge-LLM | acc substring "
        f"| recall@{k} live"
    )
    print(header)
    print("-" * len(header))
    rows = [(q, a) for q, a in table.items() if q != "_overall"]
    if "_overall" in table:
        rows.append(("OVERALL", table["_overall"]))
    for qtype, a in rows:
        if qtype == "OVERALL":
            print("-" * len(header))
        unp = f" ({a['n_judge_unparsed']} juge illisible)" if a["n_judge_unparsed"] else ""
        print(
            f"{qtype:<29} | {a['n']:>3} | {a['acc_llm']:>12.3f} | "
            f"{a['acc_sub']:>13.3f} | {a['recall_live']:>6.3f}{unp}"
        )


# --- CLI -------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="LongMemEval-S — justesse-de-réponse (lecteur+juge Ollama local)"
    )
    parser.add_argument("--path", default=str(DATA_PATH))
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--sample-per-type", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default=READER_MODEL,
                        help="modèle Ollama lecteur (défaut : %(default)s)")
    parser.add_argument("--judge-model", default=None,
                        help="modèle juge (défaut : = --model)")
    parser.add_argument("--max-turn-chars", type=int, default=MAX_TURN_CHARS)
    parser.add_argument("--out", default=str(RESULTS_PATH),
                        help="JSONL des résultats par question (audit)")
    args = parser.parse_args(argv)
    judge_model = args.judge_model or args.model

    import requests  # après argparse : --help marche même sans requests

    err = check_ollama(model=args.model) or (
        check_ollama(model=judge_model) if judge_model != args.model else None
    )
    if err:
        print(f"ERREUR : {err}", file=sys.stderr)
        return 2

    print(CAVEATS + "\n")
    print(f"lecteur={args.model}  juge={judge_model}  k={args.k}  "
          f"max_turn_chars={args.max_turn_chars}\n")
    questions = load_lme(args.path, sample_per_type=args.sample_per_type,
                         seed=args.seed)
    print()

    def reader_chat(prompt):
        return ollama_chat(prompt, model=args.model, max_tokens=READER_MAX_TOKENS)

    def judge_chat(prompt):
        return ollama_chat(prompt, model=judge_model, max_tokens=JUDGE_MAX_TOKENS)

    def chat_fn(prompt):
        # Le juge est reconnaissable à son gabarit (gold answer dans le prompt).
        if "Gold (correct) answer:" in prompt:
            return judge_chat(prompt)
        return reader_chat(prompt)

    results = []
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    code = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for i, item in enumerate(questions, start=1):
            try:
                r = answer_question(item, chat_fn, k=args.k,
                                    max_turn_chars=args.max_turn_chars)
            except requests.RequestException as e:
                print(
                    f"\nABANDON : Ollama a échoué en cours de run "
                    f"({e.__class__.__name__}: {e}) — résultats partiels "
                    f"({len(results)}/{len(questions)}) ci-dessous.",
                    file=sys.stderr,
                )
                code = 3
                break
            results.append(r)
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            v = {True: "OK ", False: "KO ", None: "?? "}[r["judge"]]
            print(
                f"[{i}/{len(questions)}] {r['question_id']} "
                f"({r['question_type']}) juge={v} sub={'OK' if r['substring'] else 'KO'} "
                f"recall={'HIT' if r['hit_live'] else 'miss'} "
                f"gold={r['gold'][:40]!r} pred={r['predicted'][:60]!r} "
                f"({time.time() - t0:.0f}s)"
            )

    if not results:
        print("Aucun résultat.", file=sys.stderr)
        return code or 1

    print()
    print_table(accuracy_by_category(results), k=args.k)
    print(
        f"\n{len(results)} questions évaluées (seed={args.seed}, "
        f"sample_per_type={args.sample_per_type}, {time.time() - t0:.0f}s). "
        f"Détail par question : {out_path}"
    )
    print("\n" + CAVEATS)
    return code


if __name__ == "__main__":
    sys.exit(main())
