"""Harness LongMemEval-S — PROXY DE RAPPEL offline, par catégorie de question.

CAVEAT CENTRAL : ce harness mesure le RAPPEL DE LA PREUVE (au moins un tour
d'une evidence session dans le top-k récupéré), PAS la justesse-de-réponse
LLM du leaderboard LongMemEval (~71-77%). Les chiffres ne se comparent
qu'ENTRE EUX (baseline plat vs live) — ils servent à cibler les catégories
faibles (multi-session, knowledge-update, temporal-reasoning, ...) pour
prioriser TMP2/TMP3.

Protocole par question :
  1. Anamnèse temporaire NEUVE (DB temp migrée 2.0 — JAMAIS data/memory.db) ;
  2. chaque tour du haystack est ingéré comme épisode via le VRAI
     `Memory.add` (rôle user/assistant, embedding), en gardant la trace
     episode_id → session_id d'origine ;
  3. `Memory.retrieve(question, embed(question), top_k=K)` (K défaut 10) ;
  4. hit si au moins un épisode récupéré appartient à une evidence session.
recall@k = proportion de questions hit, par catégorie + global, pour DEUX
armes : baseline plat (cosine seul) vs live (le vrai retrieve recalibré) —
même logique que le harness maison (eval/run_eval.py).

Données : eval/data/longmemeval_s.json (gitignoré), téléchargé depuis le
miroir HuggingFace officiel (datasets/xiaowu0162/longmemeval). Schéma réel
observé : question_id, question_type (6 catégories), question, answer,
question_date, haystack_dates, haystack_session_ids, haystack_sessions
(liste de sessions = listes de tours {role, content[, has_answer]}),
answer_session_ids. Les 30 questions d'abstention (`question_id` *_abs)
sont EXCLUES du sous-échantillon (loguées) : leur réponse n'est pas dans le
haystack, le proxy de rappel n'y a pas de sens.

Offline sauf le download initial. Rien ne s'exécute à l'import (le modèle
d'embeddings ne charge qu'au 1er embed).
"""

import argparse
import json
import pathlib
import random
import sys
import tempfile
import time

# Permet `python eval/longmemeval.py` depuis n'importe où (sys.path[0] = eval/).
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import migrations
import salience
from memory import Memory

DATA_PATH = pathlib.Path(__file__).resolve().parent / "data" / "longmemeval_s.json"
DEFAULT_K = 10

CAVEAT = (
    "CAVEAT : proxy de RAPPEL interne (evidence session dans le top-k ?) — "
    "PAS la justesse-de-réponse LLM du leaderboard LongMemEval (~71-77%). "
    "Comparer uniquement plat vs live, et les catégories entre elles."
)


# --- Chargement + sous-échantillon équilibré, déterministe, LOGUÉ -------------


def load_lme(path=DATA_PATH, sample_per_type=10, seed=0, log=print):
    """Charge longmemeval_s.json et sous-échantillonne ~sample_per_type
    questions par question_type (équilibré, déterministe via seed).

    Les questions d'abstention (*_abs, réponse ABSENTE du haystack) sont
    exclues. TOUT est logué (retenu/disponible par type) : aucune
    troncature silencieuse.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    abs_n = sum(1 for it in data if str(it.get("question_id", "")).endswith("_abs"))
    answerable = [
        it for it in data if not str(it.get("question_id", "")).endswith("_abs")
    ]
    by_type = {}
    for it in answerable:
        by_type.setdefault(it["question_type"], []).append(it)
    log(
        f"LongMemEval-S : {len(data)} questions, {abs_n} abstention (_abs) "
        f"exclues (réponse absente du haystack : proxy de rappel sans objet)"
    )
    rng = random.Random(seed)
    kept = []
    for qtype in sorted(by_type):
        items = sorted(by_type[qtype], key=lambda it: str(it["question_id"]))
        take = (
            list(items)
            if len(items) <= sample_per_type
            else rng.sample(items, sample_per_type)
        )
        take.sort(key=lambda it: str(it["question_id"]))
        kept.extend(take)
        log(f"  {qtype}: {len(take)}/{len(items)} retenues")
    log(
        f"Sous-échantillon : {len(kept)} questions "
        f"(sample_per_type={sample_per_type}, seed={seed})"
    )
    return kept


# --- Anamnèse temporaire NEUVE (jamais data/memory.db) ------------------------


def build_memory(db_path):
    """Memory sur DB temporaire migrée 2.0. REFUSE la vraie DB (data/memory.db)."""
    db_path = pathlib.Path(db_path)
    if db_path.resolve() == pathlib.Path(config.DB_PATH).resolve():
        raise ValueError(
            "INTERDIT : le harness LongMemEval ne doit JAMAIS ouvrir data/memory.db"
        )
    mem = Memory(db_path=db_path)
    migrations.migrate(mem.db)
    mem.db.execute("PRAGMA synchronous=OFF")  # DB jetable : commits sans fsync
    return mem


# --- Ingestion du haystack : episode_id → session_id d'origine ----------------


def ingest_haystack(mem, item, embed_fn):
    """Ingère chaque tour du haystack comme épisode via le VRAI Memory.add
    (embedding compris) et retourne {episode_id: session_id d'origine}.
    """
    ep2sess = {}
    session_ids = item.get("haystack_session_ids") or []
    sessions = item.get("haystack_sessions") or []
    for sid, turns in zip(session_ids, sessions):
        for turn in turns or []:
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            role = turn.get("role") or "user"
            eid = mem.add(role, content, importance=0.5, embedding=embed_fn(content))
            if eid:
                ep2sess[int(eid)] = sid
    return ep2sess


# --- Récupération : ids du top-k (live = vrai retrieve ; plat = cosine seul) ---


def retrieve_ids_live(mem, question, query_emb, k=DEFAULT_K):
    """Ids du top-k du VRAI `Memory.retrieve` (lecture seule, scoring live).

    retrieve retourne (score, ts, role, content, comps) sans id : on remonte
    l'id par correspondance exacte (ts, role, content) — ts vient de
    time.time() à l'insertion, unique en pratique.
    """
    rows = mem.retrieve(question, query_emb, top_k=k)
    ids = []
    for _score, ts, role, content, _comps in rows:
        for (eid,) in mem.db.execute(
            "SELECT id FROM episodes WHERE ts=? AND role=? AND content=?",
            (ts, role, content),
        ).fetchall():
            if eid not in ids:
                ids.append(eid)
    return ids[:k]


def retrieve_ids_flat(mem, query_emb, k=DEFAULT_K):
    """Ids du top-k du baseline PLAT : cosine(query, épisode) seul (tri stable)."""
    rows = mem.db.execute("SELECT id, embedding FROM episodes ORDER BY id").fetchall()
    scored = []
    for eid, emb_json in rows:
        emb = json.loads(emb_json) if emb_json else None
        rel = (
            salience.cosine(query_emb, emb)
            if (query_emb and emb and len(emb) == len(query_emb))
            else 0.0
        )
        scored.append((rel, eid))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [eid for _rel, eid in scored[:k]]


# --- Métrique ------------------------------------------------------------------


def is_hit(retrieved_ids, ep2sess, evidence_session_ids):
    """Hit ssi AU MOINS un épisode récupéré vient d'une evidence session.

    Sans evidence (liste vide/None) : miss compté, jamais d'exception.
    """
    evidence = set(evidence_session_ids or [])
    if not evidence:
        return False
    return any(ep2sess.get(int(eid)) in evidence for eid in retrieved_ids or [])


def evaluate_question(item, embed_fn=None, k=DEFAULT_K, db_dir=None):
    """Évalue UNE question : Anamnèse temp neuve → ingestion → retrieve → hit.

    Retourne {question_id, question_type, hit_flat, hit_live, n_sessions,
    n_turns}. db_dir=None → répertoire jetable (tempfile), nettoyé après.
    """
    embed_fn = embed_fn or _default_embed
    if db_dir is None:
        with tempfile.TemporaryDirectory(prefix="anamnese-lme-") as tmp:
            return _evaluate_in(item, embed_fn, k, pathlib.Path(tmp))
    db_dir = pathlib.Path(db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    return _evaluate_in(item, embed_fn, k, db_dir)


def _evaluate_in(item, embed_fn, k, db_dir):
    mem = build_memory(db_dir / "lme.db")
    try:
        ep2sess = ingest_haystack(mem, item, embed_fn)
        question = item["question"]
        query_emb = embed_fn(question)
        evidence = item.get("answer_session_ids") or []
        ids_flat = retrieve_ids_flat(mem, query_emb, k=k)
        ids_live = retrieve_ids_live(mem, question, query_emb, k=k)
        return {
            "question_id": item.get("question_id"),
            "question_type": item.get("question_type"),
            "hit_flat": is_hit(ids_flat, ep2sess, evidence),
            "hit_live": is_hit(ids_live, ep2sess, evidence),
            "n_sessions": len(item.get("haystack_sessions") or []),
            "n_turns": len(ep2sess),
        }
    finally:
        mem.db.close()


def recall_by_category(results):
    """{question_type: {n, recall_flat, recall_live}} + '_overall' (si non vide)."""
    by_type = {}
    for r in results:
        by_type.setdefault(r["question_type"], []).append(r)

    def _agg(rows):
        n = len(rows)
        return {
            "n": n,
            "recall_flat": sum(1 for r in rows if r["hit_flat"]) / n,
            "recall_live": sum(1 for r in rows if r["hit_live"]) / n,
        }

    out = {qtype: _agg(rows) for qtype, rows in sorted(by_type.items())}
    if results:
        out["_overall"] = _agg(results)
    return out


# --- Embeddings réels (model2vec), avec cache : les sessions se répètent ------

_EMB_CACHE = {}


def _default_embed(text):
    vec = _EMB_CACHE.get(text)
    if vec is None:
        import os

        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        import embeddings  # import tardif : ne charge model2vec qu'ici

        vec = embeddings.embed(text)
        _EMB_CACHE[text] = vec
    return vec


# --- CLI -------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="LongMemEval-S — proxy de rappel Anamnèse (plat vs live)"
    )
    parser.add_argument("--path", default=str(DATA_PATH))
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--sample-per-type", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    print(CAVEAT + "\n")
    questions = load_lme(
        args.path, sample_per_type=args.sample_per_type, seed=args.seed
    )
    print()

    results = []
    total_sessions = total_turns = 0
    t0 = time.time()
    for i, item in enumerate(questions, start=1):
        r = evaluate_question(item, k=args.k)
        results.append(r)
        total_sessions += r["n_sessions"]
        total_turns += r["n_turns"]
        print(
            f"[{i}/{len(questions)}] {r['question_id']} ({r['question_type']}) "
            f"tours={r['n_turns']} plat={'HIT' if r['hit_flat'] else 'miss'} "
            f"live={'HIT' if r['hit_live'] else 'miss'} "
            f"({time.time() - t0:.0f}s)"
        )

    table = recall_by_category(results)
    print(f"\ncatégorie | n | recall@{args.k} plat | recall@{args.k} live")
    print("-" * 64)
    for qtype, agg in table.items():
        if qtype == "_overall":
            continue
        print(
            f"{qtype:<28} | {agg['n']:>3} | {agg['recall_flat']:>6.3f} | "
            f"{agg['recall_live']:>6.3f}"
        )
    overall = table.get("_overall", {"n": 0, "recall_flat": 0.0, "recall_live": 0.0})
    print("-" * 64)
    print(
        f"{'OVERALL':<28} | {overall['n']:>3} | {overall['recall_flat']:>6.3f} | "
        f"{overall['recall_live']:>6.3f}"
    )
    print(
        f"\nIngéré : {len(results)} questions, {total_sessions} sessions, "
        f"{total_turns} tours (k={args.k}, seed={args.seed}, "
        f"{time.time() - t0:.0f}s)."
    )
    print(CAVEAT)
    return table


if __name__ == "__main__":
    main()
