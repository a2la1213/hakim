"""Scorecard multi-paramètres — la base FACTUELLE d'une évaluation « /100 ».

Mesure FRAÎCHE (rien n'est repris d'un rapport antérieur) de 9 paramètres
objectifs du setup Anamnèse, puis imprime un tableau `paramètre | valeur |
note` et écrit `eval/scorecard.json` (machine-readable).

Paramètres :
  1. Rappel maison      — precision@6 live vs plat (réutilise eval/run_eval.py)
  2. Rappel LongMemEval — proxy recall@10 live vs plat (réutilise
                          eval/longmemeval.py, sample_per_type configurable)
  3. Latence            — médiane + p90 (ms) de Memory.retrieve() sur la VRAIE
                          base (connexion READ-ONLY), + latence embed()
  4. Couverture         — % épisodes routés, % facettés, #rubriques,
                          #arêtes de co-activation, #sessions
  5. Échelle            — #épisodes, taille DB, taille WAL
  6. Efficacité tokens  — faits STRUCTURELS (pas mesurés live) : outils MCP
                          différés (~0 token upfront), coût fixe = CLAUDE.md
  7. Garde-fous         — présence + bornes (reconsolidation, SHY, dedup,
                          kill-switches) lues dans config.py
  8. Rigueur tests      — nombre de tests collectés + suite verte ?
  9. Offline            — preuve : HF_HUB_OFFLINE=1 posé AVANT le chargement
                          du modèle, puis embed() réussit => zéro réseau

Contraintes : data/memory.db ouverte en LECTURE SEULE (URI mode=ro +
PRAGMA query_only) ; 100 % offline ; rien ne s'exécute à l'import.
"""

import argparse
import json
import math
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time

# Permet `python eval/benchmark.py` depuis n'importe où (sys.path[0] = eval/).
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config

SCORECARD_PATH = pathlib.Path(__file__).resolve().parent / "scorecard.json"


# --- Helpers PURS (testés dans tests/test_benchmark.py) ------------------------


def percentile(values, p):
    """Percentile par interpolation linéaire (convention numpy). p dans [0,100].

    Liste vide => ValueError (pas de valeur silencieuse).
    """
    if not values:
        raise ValueError("percentile d'une liste vide")
    if not 0 <= p <= 100:
        raise ValueError(f"p hors [0,100] : {p!r}")
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def median(values):
    """Médiane (percentile 50, interpolée)."""
    return percentile(values, 50)


def pct(part, whole):
    """Pourcentage 0..100 ; 0.0 si whole == 0 (jamais de ZeroDivisionError)."""
    if not whole:
        return 0.0
    return 100.0 * part / whole


def count_mcp_tools(source_text):
    """Nombre d'outils MCP = occurrences du décorateur @mcp.tool() dans la source."""
    return len(re.findall(r"@mcp\.tool\(\)", source_text))


def parse_collected(pytest_output):
    """Extrait N de « N test(s) collected » d'un `pytest --co -q`. None si absent."""
    m = re.search(r"(\d+) tests? collected", pytest_output)
    return int(m.group(1)) if m else None


# --- Accès LECTURE SEULE à la vraie base ---------------------------------------


def ro_connect(db_path=config.DB_PATH):
    """Connexion SQLite strictement lecture seule (URI mode=ro + query_only)."""
    uri = f"file:{pathlib.Path(db_path).resolve()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=1")  # ceinture + bretelles : toute écriture lève
    db.execute("PRAGMA busy_timeout=5000")
    return db


def ro_memory(db_path=config.DB_PATH):
    """Memory sur la vraie base SANS passer par __init__ (qui ouvre en R/W et
    rejoue le schéma) : l'objet reçoit une connexion mode=ro. Seul
    `retrieve(..., reconsolidate=False)` (100 % SELECT) est utilisé ici.

    ATTENTION : retrieve() (vectorisé, Durci #2) lit self._emb_cache et
    self._tok_cache, posés uniquement dans Memory.__init__ — qu'on bypasse
    exprès. Il faut donc les initialiser ici (dicts vides, comme __init__),
    sinon AttributeError au premier rappel (régression testée dans
    tests/test_benchmark.py).
    """
    from memory import Memory

    mem = Memory.__new__(Memory)
    mem.db = ro_connect(db_path)
    mem._emb_cache = {}  # embedding JSON -> ndarray (cf. Memory.__init__)
    mem._tok_cache = {}  # content -> tokens lexicaux (cf. Memory.__init__)
    return mem


# --- 1. Rappel maison (réutilise eval/run_eval.py) ------------------------------


def measure_recall_maison():
    try:
        import run_eval
    except ImportError:
        from eval import run_eval
    queries = run_eval.load_queries()
    episodes = run_eval.load_episodes()
    now = time.time()
    flat = run_eval.evaluate(run_eval.score_flat, queries, episodes)
    live = run_eval.evaluate(run_eval.make_score_live(now), queries, episodes)
    return {
        "n_queries": len(queries),
        "n_episodes": len(episodes),
        "k": run_eval.DEFAULT_K,
        "p_at_k_flat": flat["precision_at_k"],
        "p_at_k_live": live["precision_at_k"],
        "margin": live["precision_at_k"] - flat["precision_at_k"],
        "mrr_live": live["mrr"],
    }


# --- 2. Rappel LongMemEval (réutilise eval/longmemeval.py) ----------------------


def measure_longmemeval(sample_per_type=10, seed=0, k=10, log=print):
    try:
        import longmemeval as lme
    except ImportError:
        from eval import longmemeval as lme
    if not pathlib.Path(lme.DATA_PATH).exists():
        return {"na": f"dataset absent : {lme.DATA_PATH}"}
    questions = lme.load_lme(sample_per_type=sample_per_type, seed=seed,
                             log=lambda *a: None)
    results = []
    t0 = time.time()
    for i, item in enumerate(questions, start=1):
        results.append(lme.evaluate_question(item, k=k))
        log(f"  LME [{i}/{len(questions)}] {results[-1]['question_id']} "
            f"({time.time() - t0:.0f}s)")
    table = lme.recall_by_category(results)
    overall = table["_overall"]
    cats = {q: a for q, a in table.items() if q != "_overall"}
    weakest = min(cats, key=lambda q: cats[q]["recall_live"])
    return {
        "n_questions": overall["n"],
        "k": k,
        "sample_per_type": sample_per_type,
        "seed": seed,
        "recall_flat": overall["recall_flat"],
        "recall_live": overall["recall_live"],
        "per_category": cats,
        "weakest_category": weakest,
        "weakest_recall_live": cats[weakest]["recall_live"],
        "duration_s": time.time() - t0,
        "caveat": lme.CAVEAT,
    }


# --- 3. Latence (retrieve + embed) sur la vraie base, lecture seule -------------


def measure_latency(n_runs=20, log=print, db_path=config.DB_PATH):
    try:
        import run_eval
    except ImportError:
        from eval import run_eval
    import embeddings

    texts = [q["query"] for q in run_eval.load_queries()]
    if not texts:
        return {"na": "aucune requête dans eval/queries.jsonl"}

    embeddings.embed("warmup")  # au cas où le modèle n'est pas encore chargé
    t0 = time.perf_counter()
    emb_one = embeddings.embed(texts[0])
    embed_warm_ms = (time.perf_counter() - t0) * 1000.0

    mem = ro_memory(db_path)
    try:
        runs = [(texts[i % len(texts)]) for i in range(n_runs)]
        embs = {t: embeddings.embed(t) for t in set(runs)}
        timings = []
        for text in runs:
            t0 = time.perf_counter()
            mem.retrieve(text, embs[text], top_k=config.TOP_K, reconsolidate=False)
            timings.append((time.perf_counter() - t0) * 1000.0)
    finally:
        mem.db.close()
    return {
        "n_runs": n_runs,
        "retrieve_median_ms": median(timings),
        "retrieve_p90_ms": percentile(timings, 90),
        "embed_warm_ms": embed_warm_ms,   # une requête, modèle chargé
        "embedding_dim": len(emb_one),
    }


# --- 4 & 5. Couverture + échelle -------------------------------------------------


def _count(db, sql):
    try:
        return db.execute(sql).fetchone()[0]
    except sqlite3.Error:
        return None


def measure_coverage_scale():
    db = ro_connect()
    try:
        episodes = _count(db, "SELECT COUNT(*) FROM episodes") or 0
        routed = _count(db, "SELECT COUNT(*) FROM episodes WHERE rubric_id IS NOT NULL") or 0
        faceted = _count(db, "SELECT COUNT(DISTINCT episode_id) FROM episode_facets") or 0
        rubrics_n = _count(db, "SELECT COUNT(*) FROM rubrics")
        facets_n = _count(db, "SELECT COUNT(*) FROM facets")
        coact = _count(db, "SELECT COUNT(*) FROM coactivation")
        sessions_n = _count(db, "SELECT COUNT(*) FROM sessions")
    finally:
        db.close()
    db_path = pathlib.Path(config.DB_PATH)
    wal = pathlib.Path(str(db_path) + "-wal")
    return {
        "episodes": episodes,
        "routed": routed,
        "routed_pct": pct(routed, episodes),
        "faceted": faceted,
        "faceted_pct": pct(faceted, episodes),
        "rubrics": rubrics_n,
        "facets_vocab": facets_n,
        "coactivation_edges": coact,
        "sessions": sessions_n,
        "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "wal_bytes": wal.stat().st_size if wal.exists() else 0,
    }


# --- 6. Efficacité tokens (faits STRUCTURELS, pas une mesure live) ---------------


def measure_token_structure():
    mcp_src = (_ROOT / "mcp_server.py").read_text(encoding="utf-8")
    claude_md = pathlib.Path.home() / ".claude" / "CLAUDE.md"
    words = (
        len(claude_md.read_text(encoding="utf-8").split())
        if claude_md.exists()
        else None
    )
    return {
        "structural_note": (
            "FAITS STRUCTURELS (pas mesurés live) : les outils MCP sont "
            "DIFFÉRÉS (chargés à la demande via ToolSearch, ~0 token upfront) ; "
            "le coût fixe de contexte = CLAUDE.md seul."
        ),
        "mcp_tools": count_mcp_tools(mcp_src),
        "claude_md_path": str(claude_md),
        "claude_md_words": words,
    }


# --- 7. Garde-fous anti-emballement (bornes lues dans config.py) -----------------


def measure_guardrails():
    names = [
        # Reconsolidation bornée (R1)
        "RECONSOLIDATE_CAP", "RECONSOLIDATE_STEP", "RECONSOLIDATE_SPACING",
        # Downscaling SHY (R2)
        "SHY_FACTOR", "SHY_FLOOR", "SHY_PROTECT",
        # Dédup (voie MCP memory_store)
        "DEDUP_COSINE_THRESHOLD", "DEDUP_LEXICAL_THRESHOLD",
        "DEDUP_WINDOW_SEC", "DEDUP_SCAN_LIMIT",
        # Co-activation bornée + élagage
        "COACT_BOOST", "COACT_CAP", "COACT_PRUNE", "COACT_HALFLIFE_H",
        # MDT bornée
        "WM_FOCUS_CAP", "WM_HALO_CAP", "WM_FLOOR",
        # Kill-switches
        "LIVE_ROUTE", "DREAM_EVOLVE_SELF",
        # Identité bornée
        "DREAM_SELF_MODEL_MAX",
    ]
    present = {n: getattr(config, n) for n in names if hasattr(config, n)}
    missing = [n for n in names if n not in present]
    return {"present": present, "missing": missing}


# --- 8. Rigueur des tests ---------------------------------------------------------


def measure_tests(run_suite=True):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    collect = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q"],
        cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=300,
    )
    n_tests = parse_collected(collect.stdout + collect.stderr)
    out = {"n_tests": n_tests}
    if run_suite:
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(_ROOT), capture_output=True, text=True, env=env, timeout=1800,
        )
        m = re.search(r"(\d+) passed", run.stdout)
        out["suite_green"] = run.returncode == 0
        out["n_passed"] = int(m.group(1)) if m else None
        out["tail"] = (run.stdout.strip().splitlines() or [""])[-1]
    else:
        out["suite_green"] = None
        out["tail"] = "suite non relancée (--skip-tests)"
    return out


# --- 9. Offline (preuve, pas déclaration) -----------------------------------------


def force_offline_env():
    """Pose les verrous offline HuggingFace AVANT tout chargement de modèle.

    À appeler en tout début de main() : si embed() réussit ENSUITE, le rappel
    cœur (model2vec + SQLite + numpy) est prouvé sans dépendance réseau.
    """
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


def measure_offline():
    import embeddings

    t0 = time.perf_counter()
    try:
        vec = embeddings.embed("preuve offline : embed local sans réseau")
        first_embed_ms = (time.perf_counter() - t0) * 1000.0
        ok = isinstance(vec, list) and len(vec) > 0
        evidence = (
            f"HF_HUB_OFFLINE=1 posé avant chargement ; embed() OK "
            f"({len(vec)}-dim, model2vec {config.EMBED_MODEL_M2V} en cache local) ; "
            "retrieve = SQLite + numpy locaux"
        )
    except Exception as e:  # le modèle exigerait le réseau
        ok, evidence, first_embed_ms = False, f"embed() a échoué sous HF_HUB_OFFLINE=1 : {e}", None
    return {"offline": ok, "evidence": evidence, "first_embed_ms": first_embed_ms}


# --- Scorecard : impression + JSON -------------------------------------------------


def _fmt(v, digits=3):
    if v is None:
        return "N/A"
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def build_rows(s):
    """Transforme le dict de mesures en lignes (paramètre, valeur, note)."""
    rows = []
    m = s["recall_maison"]
    rows.append(("1. Rappel maison p@6 (live)", _fmt(m["p_at_k_live"]),
                 f"plat={_fmt(m['p_at_k_flat'])}, marge={m['margin']:+.3f}, "
                 f"{m['n_queries']} requêtes-vérité, {m['n_episodes']} épisodes"))
    l = s["longmemeval"]
    if "na" in l:
        rows.append(("2. LongMemEval recall@10 (live)", "N/A", l["na"]))
    else:
        rows.append((f"2. LongMemEval recall@{l['k']} (live)",
                     _fmt(l["recall_live"]),
                     f"plat={_fmt(l['recall_flat'])}, n={l['n_questions']}, "
                     f"pire catégorie : {l['weakest_category']}="
                     f"{_fmt(l['weakest_recall_live'])} — PROXY de rappel, "
                     "pas le score LLM du leaderboard"))
    lat = s["latency"]
    if "na" in lat:
        rows.append(("3. Latence retrieve()", "N/A", lat["na"]))
    else:
        rows.append(("3. Latence retrieve() médiane",
                     f"{lat['retrieve_median_ms']:.1f} ms",
                     f"p90={lat['retrieve_p90_ms']:.1f} ms sur "
                     f"{lat['n_runs']} requêtes, vraie base (mode=ro)"))
        first = s["offline"].get("first_embed_ms")
        rows.append(("   Latence embed() (chaud)",
                     f"{lat['embed_warm_ms']:.2f} ms",
                     f"1er embed (chargement modèle inclus) : "
                     f"{_fmt(first, 0)}{'' if first is None else ' ms'}, "
                     f"{lat['embedding_dim']}-dim"))
    c = s["coverage_scale"]
    rows.append(("4. Épisodes routés (rubric_id)", f"{c['routed_pct']:.1f} %",
                 f"{c['routed']}/{c['episodes']} ; {_fmt(c['rubrics'])} rubriques"))
    rows.append(("   Épisodes facettés", f"{c['faceted_pct']:.1f} %",
                 f"{c['faceted']}/{c['episodes']} ; vocab facettes="
                 f"{_fmt(c['facets_vocab'])}/{config.FACET_MAX_GLOBAL}"))
    rows.append(("   Co-activation / sessions",
                 f"{_fmt(c['coactivation_edges'])} arêtes",
                 f"{_fmt(c['sessions'])} sessions segmentées"))
    rows.append(("5. Échelle", f"{c['episodes']} épisodes",
                 f"DB={c['db_bytes'] / 1e6:.1f} Mo, WAL={c['wal_bytes'] / 1e6:.1f} Mo"))
    t = s["token_structure"]
    rows.append(("6. Outils MCP (différés)", _fmt(t["mcp_tools"]),
                 "STRUCTUREL : chargés à la demande, ~0 token upfront"))
    rows.append(("   Coût fixe contexte", f"{_fmt(t['claude_md_words'])} mots",
                 f"STRUCTUREL : CLAUDE.md seul ({t['claude_md_path']})"))
    g = s["guardrails"]["present"]
    rows.append(("7. Reconsolidation bornée",
                 f"cap={g.get('RECONSOLIDATE_CAP')}",
                 f"step={g.get('RECONSOLIDATE_STEP')}, "
                 f"spacing={g.get('RECONSOLIDATE_SPACING', 0):.0f}s"))
    rows.append(("   SHY (downscaling)", f"floor={g.get('SHY_FLOOR')}",
                 f"factor={g.get('SHY_FACTOR')}, protect={g.get('SHY_PROTECT')} rappels"))
    rows.append(("   Dédup (memory_store)",
                 f"cos>={g.get('DEDUP_COSINE_THRESHOLD')}",
                 f"lex>={g.get('DEDUP_LEXICAL_THRESHOLD')}, "
                 f"fenêtre={g.get('DEDUP_WINDOW_SEC', 0) // 86400}j"))
    rows.append(("   Kill-switches", f"LIVE_ROUTE={g.get('LIVE_ROUTE')}",
                 f"DREAM_EVOLVE_SELF={g.get('DREAM_EVOLVE_SELF')}, "
                 f"self_model<={g.get('DREAM_SELF_MODEL_MAX')} chars"
                 + (f" ; MANQUANTS : {s['guardrails']['missing']}"
                    if s["guardrails"]["missing"] else "")))
    te = s["tests"]
    rows.append(("8. Tests", f"{_fmt(te['n_tests'])} collectés",
                 f"suite verte : {_fmt(te['suite_green'])} — {te.get('tail', '')}"))
    o = s["offline"]
    rows.append(("9. Offline (rappel cœur)", _fmt(o["offline"]), o["evidence"]))
    return rows


def print_scorecard(rows):
    w_param = max(len(r[0]) for r in rows)
    w_val = max(len(r[1]) for r in rows)
    line = f"{'paramètre':<{w_param}} | {'valeur':<{w_val}} | note"
    print("\n" + "=" * 100)
    print("SCORECARD ANAMNÈSE — mesures fraîches (base réelle en lecture seule)")
    print("=" * 100)
    print(line)
    print("-" * 100)
    for param, val, note in rows:
        print(f"{param:<{w_param}} | {val:<{w_val}} | {note}")
    print("-" * 100)


def _git_sha():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(_ROOT),
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


# --- CLI ----------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Scorecard multi-paramètres Anamnèse (mesure fraîche, DB read-only)"
    )
    parser.add_argument("--lme-sample", type=int, default=10,
                        help="questions LongMemEval par catégorie (défaut 10)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--latency-runs", type=int, default=20)
    parser.add_argument("--skip-lme", action="store_true",
                        help="saute LongMemEval (long) — la ligne devient N/A")
    parser.add_argument("--skip-tests", action="store_true",
                        help="collecte les tests sans relancer la suite")
    parser.add_argument("--out", default=str(SCORECARD_PATH))
    args = parser.parse_args(argv)

    force_offline_env()  # AVANT tout chargement de modèle : la preuve offline
    t_start = time.time()

    print("Mesure 9 : preuve offline (embed sous HF_HUB_OFFLINE=1)...")
    offline = measure_offline()
    print("Mesure 1 : rappel maison (run_eval, live vs plat)...")
    maison = measure_recall_maison()
    print("Mesure 3 : latence retrieve()/embed() sur la vraie base (mode=ro)...")
    latency = measure_latency(n_runs=args.latency_runs)
    print("Mesures 4-5 : couverture + échelle (SQL read-only)...")
    coverage = measure_coverage_scale()
    print("Mesure 6 : faits structurels tokens (MCP différé, CLAUDE.md)...")
    tokens = measure_token_structure()
    print("Mesure 7 : garde-fous (config.py)...")
    guards = measure_guardrails()
    print("Mesure 8 : tests (collecte" + ("" if args.skip_tests else " + run") + ")...")
    tests = measure_tests(run_suite=not args.skip_tests)
    if args.skip_lme:
        lme_res = {"na": "sauté (--skip-lme)"}
    else:
        print(f"Mesure 2 : LongMemEval proxy (sample_per_type={args.lme_sample}, "
              f"long)...")
        lme_res = measure_longmemeval(sample_per_type=args.lme_sample,
                                      seed=args.seed)

    scorecard = {
        "meta": {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "git_sha": _git_sha(),
            "db_path": str(config.DB_PATH),
            "duration_s": round(time.time() - t_start, 1),
            "read_only": True,
        },
        "recall_maison": maison,
        "longmemeval": lme_res,
        "latency": latency,
        "coverage_scale": coverage,
        "token_structure": tokens,
        "guardrails": guards,
        "tests": tests,
        "offline": offline,
    }

    rows = build_rows(scorecard)
    print_scorecard(rows)
    print(f"\nDurée totale : {scorecard['meta']['duration_s']:.0f}s "
          f"(sha={scorecard['meta']['git_sha']})")

    out = pathlib.Path(args.out)
    out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"JSON : {out}")
    return scorecard


if __name__ == "__main__":
    main()
