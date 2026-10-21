"""synthesis.py — Moteur de liens génératifs (synthèse abductive).
Cœur AGNOSTIQUE au modèle : chat_fn(prompt)->str injectable (9B local OU claude -p).
L'intelligence vit dans l'orchestration (sélection-code + crible adversarial), pas
dans le modèle. Fonctions pures en tête (stdlib), orchestration + I/O ensuite."""
import json as _json
import math
import re
import time

import config
import embeddings

# ---------- pur ----------

def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def grounding_ok(insight_emb, emb_a, emb_b, floor):
    """L'insight est-il relié en EMBEDDING aux DEUX sources (≥ floor) ? Ancrage
    sémantique, pas lexical (une vraie synthèse reformule) → tue le non-sequitur."""
    return _cos(insight_emb, emb_a) >= floor and _cos(insight_emb, emb_b) >= floor


def novelty(insight_emb, existing_embs):
    """1 − max cosinus aux souvenirs existants. 1.0 si aucun (∈ [0,1])."""
    if not existing_embs:
        return 1.0
    return round(1.0 - max(_cos(insight_emb, e) for e in existing_embs), 6)


def parse_hypothesis(out):
    """Hypothèse extraite, ou None si NONE/vide/charabia."""
    if not out:
        return None
    t = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I).strip()
    if not t or re.match(r"(?i)^\W*none\b", t):
        return None
    return t


def parse_verdict(out):
    """PREMIER verdict d'un sceptique : REFUTE / VALIDE / None. Le prompt exige le
    verdict d'ABORD ; la raison qui suit contient souvent 'valide/réfut' → prendre
    le PREMIER match (pas le dernier) préserve le vote-kill du crible anti-slop."""
    m = re.findall(r"(?i)(r[eé]fut\w*|valid\w*)", out or "")
    if not m:
        return None
    return "REFUTE" if m[0][:1].lower() == "r" else "VALIDE"


def majority_kill(votes, n_refute_kill):
    """Vrai si ≥ n_refute_kill votes 'REFUTE' → l'insight est tué."""
    return sum(1 for v in votes if v == "REFUTE") >= n_refute_kill


def fertility_score(cos, cross_rubric, coact_weight):
    """Fertilité d'une paire : pic à mi-distance (centre 0.475), bonus inter-rubriques,
    malus si déjà co-activée. Plus haut = plus prometteur pour un lien NEUF."""
    central = max(0.0, 1.0 - abs(cos - 0.475))
    return round(central + (0.30 if cross_rubric else 0.0) - min(0.5, coact_weight or 0.0), 4)


# ---------- étapes face-modèle (chat_fn injectable) ----------

def _gen_prompt(a_text, b_text):
    return (
        "Voici DEUX souvenirs éloignés :\n"
        f"[A] {a_text}\n[B] {b_text}\n\n"
        "Une hypothèse, solution ou question CONCRÈTE émerge-t-elle en les COMBINANT — "
        "quelque chose que ni A ni B ne dit seul ? Si oui : formule-la en 1-2 phrases, "
        "puis « [test: <comment la vérifier concrètement>] ». Sois neuf et précis, pas de banalité.\n"
        "Si la connexion est forcée, vide ou triviale, réponds EXACTEMENT : NONE")

def _skeptic_prompt(hypothesis, a_text, b_text):
    return (
        "Sois un SCEPTIQUE dur. Voici deux souvenirs et une hypothèse censée émerger de leur combinaison :\n"
        f"[A] {a_text}\n[B] {b_text}\nHYPOTHÈSE : {hypothesis}\n\n"
        "Est-ce un VRAI pont (neuf, concret, réellement ancré dans A ET B) ou une connexion "
        "FORCÉE / hallucinée / banale ? Par défaut, doute. Réponds par UN mot : RÉFUTÉ ou VALIDE, "
        "puis une raison courte.")

def generate(chat_fn, a_text, b_text, n_samples):
    """n_samples générations abductives ; garde les hypothèses non-NONE."""
    prompt = _gen_prompt(a_text, b_text)
    hyps = []
    for _ in range(max(1, n_samples)):
        try:
            h = parse_hypothesis(chat_fn(prompt))
        except Exception:
            h = None
        if h:
            hyps.append(h)
    return hyps

def verify(chat_fn, hypothesis, a_text, b_text, n_skeptics):
    """n_skeptics passes « réfute ceci ». -> (kept, n_refute). kept = pas de majorité réfutante."""
    prompt = _skeptic_prompt(hypothesis, a_text, b_text)
    votes = []
    for _ in range(max(1, n_skeptics)):
        try:
            votes.append(parse_verdict(chat_fn(prompt)))
        except Exception:
            votes.append(None)
    n_refute = sum(1 for v in votes if v == "REFUTE")
    return (not majority_kill(votes, config.SYNTH_REFUTE_KILL), n_refute)


# ---------- sélection des paires fertiles (lecture seule sur mem.db) ----------

SUBSTANTIAL_ROLES = ("semantic", "reasoning", "thought", "insight")


def _load_substantial(mem):
    """(id, embedding, top_rubric) des souvenirs substantiels embeddés."""
    ph = ",".join("?" * len(SUBSTANTIAL_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.embedding, COALESCE(r.path,'') FROM episodes e "
        f"LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph}) AND e.embedding IS NOT NULL AND e.embedding != '[]'",
        SUBSTANTIAL_ROLES).fetchall()
    out = []
    for eid, emb, path in rows:
        try:
            v = _json.loads(emb)
        except Exception:
            continue
        if v:
            out.append((eid, v, (path.split("/", 1)[0] or "")))
    return out


def _coact_weights(mem):
    """{(a,b) canonique: weight} des arêtes de coactivation existantes."""
    try:
        return {(min(a, b), max(a, b)): w
                for a, b, w in mem.db.execute("SELECT a_id, b_id, weight FROM coactivation")}
    except Exception:
        return {}


def select_fertile_pairs(mem, n, lo=config.SYNTH_MID_LO, hi=config.SYNTH_MID_HI):
    items = _load_substantial(mem)
    coact = _coact_weights(mem)
    scored = []
    for i in range(len(items)):
        ida, va, ra = items[i]
        for j in range(i + 1, len(items)):
            idb, vb, rb = items[j]
            cos = _cos(va, vb)
            if not (lo <= cos <= hi):           # SEULE porte dure : la mi-distance embedding
                continue
            cross = (ra != rb)                  # cross-rubrique = BONUS de fertilité, pas filtre
            w = coact.get((min(ida, idb), max(ida, idb)), 0.0)
            scored.append((ida, idb, fertility_score(cos, cross, w)))
    scored.sort(key=lambda p: -p[2])
    return scored[:n]


# ---------- stockage + pipeline complet (écriture sur mem.db, best-effort) ----------

def store_insight(mem, hypothesis, source_ids, backend):
    """Épisode role='insight' (préfixe backend) + arêtes insight_edges + rétroaction
    coactivation entre les sources. Retourne l'insight_id (ou None si échec)."""
    import provenance
    herite = provenance.externes(mem.db, source_ids)      # (H6 + X1) une source externe : l'idée l'est aussi
    content = f"(insight·{backend}{'·externe' if herite else ''}) {hypothesis}"
    try:
        iid = mem.add("insight", content, importance=config.DREAM_IDEA_IMPORTANCE,
                      embedding=embeddings.embed(content))
    except Exception:
        return None
    if not iid:
        return None
    if herite:
        provenance.marquer(mem.db, iid)
    try:
        mem.db.executemany("INSERT OR IGNORE INTO insight_edges (insight_id, source_id) VALUES (?,?)",
                           [(iid, s) for s in source_ids])
        mem.db.commit()
    except Exception:
        pass
    try:
        mem.log_coactivation(list(source_ids), time.time(), boost=config.SYNTH_COACT_BOOST)
    except Exception:
        pass
    return iid


def _text_of(mem, eid):
    r = mem.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()
    return (r[0] if r else "") or ""


def _emb_of(mem, eid):
    r = mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (eid,)).fetchone()
    try:
        return _json.loads(r[0]) if r and r[0] else []
    except Exception:
        return []


def _existing_insight_embs(mem):
    """Embeddings des insights DÉJÀ stockés (pour la nouveauté : ne pas re-générer
    un insight déjà connu). La nouveauté se mesure aux souvenirs existants, PAS aux
    sources — que l'ancrage exige au contraire proches (cf. docstring novelty)."""
    try:
        rows = mem.db.execute(
            "SELECT embedding FROM episodes WHERE role='insight' "
            "AND embedding IS NOT NULL AND embedding != '[]'").fetchall()
    except Exception:
        return []
    out = []
    for (emb,) in rows:
        try:
            v = _json.loads(emb) if emb else []
        except Exception:
            v = []
        if v:
            out.append(v)
    return out


def run(mem, chat_fn, backend, n_pairs, n_samples=config.SYNTH_SAMPLES,
        n_skeptics=config.SYNTH_SKEPTICS):
    """Pipeline complet, best-effort. Retourne les insight_ids créés."""
    created = []
    try:
        pairs = select_fertile_pairs(mem, n_pairs)
    except Exception:
        return created
    for ida, idb, _fert in pairs:
        try:
            a_text, b_text = _text_of(mem, ida), _text_of(mem, idb)
            emb_a, emb_b = _emb_of(mem, ida), _emb_of(mem, idb)
            for hyp in generate(chat_fn, a_text, b_text, n_samples):
                ins_emb = embeddings.embed(hyp)
                if not grounding_ok(ins_emb, emb_a, emb_b, config.SYNTH_GROUNDING_FLOOR):
                    continue
                if novelty(ins_emb, _existing_insight_embs(mem)) < config.SYNTH_NOVELTY_MIN:
                    continue
                kept, _n = verify(chat_fn, hyp, a_text, b_text, n_skeptics)
                if not kept:
                    continue
                iid = store_insight(mem, hyp, [ida, idb], backend)
                if iid:
                    created.append(iid)
                break                                   # une hypothèse retenue par paire suffit
        except Exception:
            continue
    return created
