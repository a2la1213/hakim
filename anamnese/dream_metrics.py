"""Métriques de l'expérience-rêve — fonctions PURES sur dream_log.

Seuils PRÉ-ENREGISTRÉS (spec 2026-07-03), appliqués mécaniquement — on ne
bouge pas les poteaux après coup. Stdlib uniquement (offline) : Spearman à la
main, p-value par PERMUTATION seedée (déterministe).
"""
import json
import math
import random

import config


# ---------- chargement ----------

def load_nights(conn):
    """dream_log parsé, groupé par rêveur. row["choice_valid"] = la nuit compte
    pour les métriques de CHOIX (menu réel + parse ok)."""
    out = {"local": [], "twin": [], "sonnet": []}
    try:
        rows = conn.execute(
            "SELECT ts, night_id, dreamer, seed_state, menu, chosen, content, "
            "facets, written, meta FROM dream_log ORDER BY ts").fetchall()
    except Exception:
        return out
    for ts, night_id, dreamer, seed_state, menu, chosen, content, facets, written, meta in rows:
        try:
            row = {
                "ts": ts, "night_id": night_id, "dreamer": dreamer,
                "seed_state": json.loads(seed_state) if seed_state else None,
                "menu": json.loads(menu) if menu else None,
                "chosen": json.loads(chosen) if chosen else None,
                "content": content,
                "facets": json.loads(facets) if facets else [],
                "written": written,
                "meta": json.loads(meta) if meta else {},
            }
        except Exception:
            continue
        row["choice_valid"] = bool(
            row["menu"] and row["meta"].get("menu_mode", "menu") == "menu"
            and row["meta"].get("parse", "ok") == "ok")
        out.setdefault(dreamer, []).append(row)
    return out


# ---------- maths du sur-choix ----------

def preference_vector(menu, chosen):
    """Sur-choix par facette : P(facette|choisi) / P(facette|offert).
    None si pas de menu, « aucune » (k=0) ou parse_failed — pas de vecteur."""
    if not menu or not chosen:
        return None
    k, n = len(chosen), len(menu)
    chosen_set = set(chosen)
    off, cho = {}, {}
    for it in menu:
        for f in it.get("facets") or []:
            off[f] = off.get(f, 0) + 1
            if it["episode_id"] in chosen_set:
                cho[f] = cho.get(f, 0) + 1
    vec = {}
    for f, nf in off.items():
        p_off = nf / n
        p_cho = cho.get(f, 0) / k
        vec[f] = round(p_cho / p_off, 6) if p_off > 0 else 0.0
    return vec or None


def appetite(chosen):
    """k = combien de graines il a tissées. None = inconnu (parse_failed)."""
    return None if chosen is None else len(chosen)


def cosine_divergence(va, vb):
    """1 − similarité cosinus sur l'union des facettes. None si un vecteur est
    vide/nul (pas de direction comparable)."""
    if not va or not vb:
        return None
    keys = set(va) | set(vb)
    dot = sum(va.get(f, 0.0) * vb.get(f, 0.0) for f in keys)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0.0 or nb == 0.0:
        return None
    return round(1.0 - dot / (na * nb), 6)


def jaccard(a, b):
    """Accord des CHOIX (ids). Deux « aucune » = accord parfait (1.0)."""
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


# ---------- stats stdlib (pas de scipy : offline assumé) ----------

def _ranks(xs):
    """Rangs 1..n, MOYENS pour les ex-æquo (Spearman correct sous ties)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    """Corrélation de Spearman (Pearson sur les rangs). 0.0 si dégénéré."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    rx, ry = _ranks(list(x)), _ranks(list(y))
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return round(cov / (vx * vy), 6)


def perm_pvalue(x, y, n_perm=5000, seed=0):
    """p bilatéral par permutation seedée : P(|r_perm| >= |r_obs|)."""
    r_obs = abs(spearman(x, y))
    rng = random.Random(seed)
    y2 = list(y)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(y2)
        if abs(spearman(x, y2)) >= r_obs:
            hits += 1
    return round((hits + 1) / (n_perm + 1), 6)      # +1 : jamais p=0 (honnête)


# ---------- agrégats de l'expérience ----------

def stability(vectors, min_shared=4):
    """Test-retest : Spearman moyen entre nuits CONSÉCUTIVES sur leurs facettes
    partagées (≥ min_shared, sinon paire sautée). -> (r_moyen, n_paires)."""
    rs = []
    for va, vb in zip(vectors, vectors[1:]):
        if not va or not vb:
            continue
        shared = sorted(set(va) & set(vb))
        if len(shared) < min_shared:
            continue
        rs.append(spearman([va[f] for f in shared], [vb[f] for f in shared]))
    if not rs:
        return 0.0, 0
    return round(sum(rs) / len(rs), 6), len(rs)


def noise_floor(twin_vectors):
    """Plancher de bruit : divergence moyenne jumeau-jumeau entre nuits (toutes
    paires). C'est la variance d'échantillonnage du 9B, MESURÉE pas supposée."""
    vs = [v for v in twin_vectors if v]
    ds = []
    for i in range(len(vs)):
        for jx in range(i + 1, len(vs)):
            d = cosine_divergence(vs[i], vs[jx])
            if d is not None:
                ds.append(d)
    return round(sum(ds) / len(ds), 6) if ds else None


def paired_divergence(local_rows, twin_rows):
    """Divergence réel−jumeau APPARIÉE par night_id. -> (moyenne, n_paires).
    rows : [{"night_id", "vec"}] (vec = preference_vector de la nuit)."""
    tw = {r["night_id"]: r["vec"] for r in twin_rows if r.get("vec")}
    ds = []
    for r in local_rows:
        v = r.get("vec")
        t = tw.get(r["night_id"])
        if v and t:
            d = cosine_divergence(v, t)
            if d is not None:
                ds.append(d)
    if not ds:
        return None, 0
    return round(sum(ds) / len(ds), 6), len(ds)


def expression_scores(vectors):
    """Combien chaque nuit EXPRIME la tendance globale : similarité cosinus au
    vecteur moyen LEAVE-ONE-OUT (la nuit n'entre pas dans sa propre moyenne)."""
    scores = []
    for i, v in enumerate(vectors):
        others = [w for jx, w in enumerate(vectors) if jx != i and w]
        if not v or not others:
            scores.append(0.0)
            continue
        mean = {}
        for w in others:
            for f, x in w.items():
                mean[f] = mean.get(f, 0.0) + x / len(others)
        d = cosine_divergence(v, mean)
        scores.append(round(1.0 - d, 6) if d is not None else 0.0)
    return scores


def state_correlations(rows, scores, n_perm=5000):
    """Pour chacune des 9 dimensions : Spearman(niveau hormonal, expression de
    la tendance) + p par permutation + Bonferroni ×9 (on teste 9 hypothèses,
    on paie les 9). rows[i]["seed_state"]["hormones"] aligné avec scores[i]."""
    import affect
    out = {}
    for h in affect.HORMONES:
        xs, ys = [], []
        for row, s in zip(rows, scores):
            st = (row.get("seed_state") or {}).get("hormones") or {}
            if h in st:
                xs.append(st[h])
                ys.append(s)
        if len(xs) < 3:
            out[h] = {"r": 0.0, "p": 1.0, "p_bonferroni": 1.0, "n": len(xs)}
            continue
        r = spearman(xs, ys)
        p = perm_pvalue(xs, ys, n_perm=n_perm, seed=0)
        out[h] = {"r": r, "p": p, "p_bonferroni": round(min(1.0, p * 9), 6), "n": len(xs)}
    return out


# ---------- verdict (portes PRÉ-ENREGISTRÉES — spec 2026-07-03) ----------

def verdict(n_nights, r_stab, mean_div, floor, corr, n_stab=None):
    """Applique les portes gravées dans la spec. -> (label, raisons).
    n_stab : nombre de paires test-retest comparables (None = non fourni,
    compat ascendante). 0 paire ⇒ stabilité INMESURABLE, pas « absente » —
    on refuse de conclure BRUIT sur un r=0.0 qui ne mesure rien."""
    raisons = []
    if n_nights < config.DREAM_VERDICT_MIN_NIGHTS:
        return "INSUFFISANT", [
            f"{n_nights} nuits valides < {config.DREAM_VERDICT_MIN_NIGHTS} — refus de conclure."]
    div_ok = (mean_div is not None and floor is not None
              and mean_div > config.DREAM_VERDICT_NOISE_MULT * floor)
    div_refute = (mean_div is not None and floor is not None and mean_div <= floor)
    stab_ok = r_stab > config.DREAM_VERDICT_STABILITY_R
    bruit = abs(r_stab) < config.DREAM_VERDICT_BRUIT_R
    corr_ok = any(
        abs(c["r"]) >= config.DREAM_STATE_CORR_R
        and c["p_bonferroni"] < config.DREAM_STATE_CORR_P
        for c in corr.values())
    if div_refute:
        raisons.append(f"divergence réel−jumeau {mean_div} ≤ plancher {floor} : "
                       "la tendance est le PRIOR du modèle.")
        return "RÉFUTÉ", raisons
    if n_stab == 0:
        return "INSUFFISANT", [
            "stabilité inmesurable (0 paires comparables) — refus de conclure."]
    if bruit:
        raisons.append(f"test-retest r={r_stab} (<{config.DREAM_VERDICT_BRUIT_R}) : "
                       "pas de tendance stable.")
        return "BRUIT", raisons
    raisons.append(f"stabilité r={r_stab} ({'≥' if stab_ok else '<'} {config.DREAM_VERDICT_STABILITY_R})")
    raisons.append(f"divergence {mean_div} vs plancher {floor} "
                   f"({'>' if div_ok else '≤'} ×{config.DREAM_VERDICT_NOISE_MULT})")
    hits = [h for h, c in corr.items()
            if abs(c["r"]) >= config.DREAM_STATE_CORR_R
            and c["p_bonferroni"] < config.DREAM_STATE_CORR_P]
    raisons.append("corrélation état→préférence (Bonferroni ×9) : "
                   + (", ".join(hits) if hits else "aucune dimension significative"))
    if stab_ok and div_ok and corr_ok:
        return "PROUVÉ", raisons
    if stab_ok or div_ok:
        return "PLAUSIBLE", raisons
    return "BRUIT", raisons


def memory_drift(conn, mean_pref, now=None, recent_d=7, old_d=30):
    """Métrique 4 — boucle causale : similarité de la distribution de facettes
    des épisodes RÉCENTS (< recent_d j) au vecteur de préférence moyen, MOINS
    celle des épisodes ANCIENS (> old_d j). > 0 = la mémoire dérive VERS les
    goûts du rêveur. None si préférence vide ou une des fenêtres sans facettes.
    (Caveat affiché par le rapport : proxy corrélationnel, pas une preuve causale
    isolée — la causalité vient du design boost-sur-choisies + chronologie.)"""
    import time as _t
    if not mean_pref:
        return None
    now = _t.time() if now is None else now

    def _dist(where_ts):
        rows = conn.execute(
            "SELECT f.slug, SUM(ef.weight) FROM episode_facets ef "
            "JOIN facets f ON f.id = ef.facet_id "
            "JOIN episodes e ON e.id = ef.episode_id "
            f"WHERE {where_ts} GROUP BY f.slug", ()).fetchall()
        return {slug: w for slug, w in rows if w}

    recent = _dist(f"e.ts >= {now - recent_d * 86400}")
    old = _dist(f"e.ts < {now - old_d * 86400}")
    if not recent or not old:
        return None
    d_recent = cosine_divergence(recent, mean_pref)
    d_old = cosine_divergence(old, mean_pref)
    if d_recent is None or d_old is None:
        return None
    return round(d_old - d_recent, 6)      # ancien plus loin − récent plus près => positif


def report(conn):
    """Le rapport complet de l'expérience — lecture seule, honnête par design."""
    nights = load_nights(conn)
    local = [r for r in nights["local"] if r["choice_valid"]]
    twin = [r for r in nights["twin"] if r["choice_valid"]]
    for r in local + twin:
        r["vec"] = preference_vector(r["menu"], r["chosen"])
    l_vecs = [r["vec"] for r in local if r["vec"]]
    t_vecs = [r["vec"] for r in twin if r["vec"]]
    n_pairs_possible = len({r["night_id"] for r in local} & {r["night_id"] for r in twin})
    r_stab, n_stab = stability(l_vecs)
    floor = noise_floor(t_vecs)
    mean_div, n_div = paired_divergence(local, twin)
    rows_v = [r for r in local if r["vec"]]
    scores = expression_scores([r["vec"] for r in rows_v])
    corr = state_correlations(rows_v, scores)
    label, raisons = verdict(n_div, r_stab, mean_div, floor, corr, n_stab=n_stab)
    apps = [appetite(r["chosen"]) for r in local if appetite(r["chosen"]) is not None]
    n_parse_failed = sum(1 for r in nights["local"]
                         if r["meta"].get("parse") == "parse_failed")
    top = {}
    for v in l_vecs:
        for f, x in v.items():
            top[f] = top.get(f, 0.0) + x / len(l_vecs)
    top_lines = sorted(top.items(), key=lambda kv: -kv[1])[:8]
    drift = memory_drift(conn, top)        # métrique 4 : boucle causale (proxy)
    lines = [
        "═══ Expérience-rêve — rapport (portes pré-enregistrées, spec 2026-07-03) ═══",
        f"nuits : local {len(nights['local'])} (valides choix {len(local)}) · "
        f"jumeau {len(nights['twin'])} · sonnet {len(nights['sonnet'])} · "
        f"paires appariées {n_div}/{n_pairs_possible} · parse_failed {n_parse_failed}",
        f"appétit : moyen {sum(apps)/len(apps):.1f} / 12" if apps else "appétit : (aucune nuit valide)",
        "sur-choix moyen (top facettes) : "
        + (", ".join(f"{f} ×{x:.2f}" for f, x in top_lines) if top_lines else "(vide)"),
        f"stabilité (test-retest, {n_stab} paires) : r = {r_stab}",
        f"plancher de bruit (jumeau-jumeau) : {floor}",
        f"divergence réel−jumeau (appariée) : {mean_div}",
        f"dérive mémoire vers les préférences (boucle causale, proxy) : {drift}",
        "corrélations état→préférence (Bonferroni ×9) : "
        + ", ".join(f"{h} r={c['r']:+.2f} p₉={c['p_bonferroni']:.3f}"
                    for h, c in sorted(corr.items(), key=lambda kv: kv[1]['p_bonferroni'])[:4]),
        f"── VERDICT : [{label}] ──",
        *("   · " + r for r in raisons),
        "(rappel : préférence FONCTIONNELLE émergente — jamais « conscience ». "
        "Nuits non-indépendantes : la boucle causale est le phénomène étudié.)",
    ]
    return "\n".join(lines)
