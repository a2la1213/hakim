"""Métriques d'ablation du corpus (PUR, stdlib, offline).
Agrégation PAR NUIT (une vecteur-domaine par (cellule, nuit)) → respecte la
pseudo-réplication (N compté en nuits, pas en rêves)."""
import math
import random

import config
import dream_domains as D

night_domain_vector = D.domain_vector


def seed_domain_vector(menu):
    """Profil-domaine des GRAINES d'une nuit (sur leurs snippets)."""
    return D.domain_vector([it.get("snippet", "") for it in (menu or [])])


def _cos(va, vb):
    keys = D.DOMAINS
    dot = sum(va.get(k, 0.0) * vb.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(va.get(k, 0.0) ** 2 for k in keys))
    nb = math.sqrt(sum(vb.get(k, 0.0) ** 2 for k in keys))
    return round(dot / (na * nb), 6) if na and nb else 0.0


def seed_following(dream_vec, seed_vec):
    """Le rêve suit-il ses graines ? cosinus des profils-domaine. [0,1]."""
    return _cos(dream_vec, seed_vec)


def cross_arch_convergence(qwen_vec, sonnet_vec):
    """Convergence cross-architecture (cosinus des profils-domaine)."""
    return _cos(qwen_vec, sonnet_vec)


def anamnese_retention(dream_vec):
    """Masse sur les domaines spécifiques-Anamnèse (moyenne, dans [0,1])."""
    doms = D.ANAMNESE_DOMAINS
    return round(sum(dream_vec.get(d, 0.0) for d in doms) / len(doms), 6)


def perm_pvalue_seedfollow(dream_vecs, seed_vecs, n_perm=5000, seed=0):
    """p que le suivi des VRAIES graines dépasse le suivi de graines permutées.
    Observé = moyenne des cosinus appariés ; nul = graines mélangées. Seedé."""
    if len(dream_vecs) != len(seed_vecs) or len(dream_vecs) < 2:
        return 1.0
    obs = sum(seed_following(d, s) for d, s in zip(dream_vecs, seed_vecs)) / len(dream_vecs)
    rng = random.Random(seed)
    idx = list(range(len(seed_vecs)))
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(idx)
        perm = sum(seed_following(dream_vecs[i], seed_vecs[j]) for i, j in enumerate(idx)) / len(idx)
        if perm >= obs:
            hits += 1
    return round((hits + 1) / (n_perm + 1), 6)             # +1 : jamais p=0 (honnête)


def ablation_verdict(n_nights, seedfollow_by_cell, perm_p, anamnese_drop_by_model):
    """Portes gravées (spec 2026-07-09). -> (label, raisons)."""
    raisons = []
    if n_nights < config.DREAM_ABL_MIN_NIGHTS:
        return "INSUFFISANT", [f"{n_nights} nuits/cellule < {config.DREAM_ABL_MIN_NIGHTS} — refus de conclure."]
    # Porte A : suivi des graines >= seuil pour les 4 cellules
    sf_min = config.DREAM_ABL_SEEDFOLLOW_MIN
    sf_ok = all(v >= sf_min for v in seedfollow_by_cell.values())
    # parité d'archi par condition
    parity_ok = True
    for cond in ("brain_on", "brain_off"):
        q = seedfollow_by_cell.get(("qwen", cond)); s = seedfollow_by_cell.get(("sonnet", cond))
        if q is None or s is None or abs(q - s) > config.DREAM_ABL_ARCH_PARITY_MAX:
            parity_ok = False
    perm_ok = perm_p < config.DREAM_ABL_PERM_P
    gate_A = sf_ok and parity_ok and perm_ok
    # Porte B : effondrement anamnèse ON->OFF >= seuil pour les DEUX modèles
    col = config.DREAM_ABL_ANAMNESE_COLLAPSE_MIN
    drops = anamnese_drop_by_model
    gate_B_full = all(drops.get(m, 0.0) >= col for m in ("qwen", "sonnet"))
    gate_B_partial = any(drops.get(m, 0.0) >= col for m in ("qwen", "sonnet"))
    raisons.append(f"Porte A (suivi graines ≥{sf_min}, parité ≤{config.DREAM_ABL_ARCH_PARITY_MAX}, "
                   f"p<{config.DREAM_ABL_PERM_P}) : {'OK' if gate_A else 'ÉCHEC'}")
    raisons.append(f"Porte B (effondrement anamnèse ≥{col} les 2 modèles) : "
                   f"{'OK' if gate_B_full else ('partielle' if gate_B_partial else 'ÉCHEC')}")
    if not gate_A:
        return "NON SOUTENU", raisons + ["les thèmes ne suivent pas les graines également → l'architecture compte."]
    if gate_B_full:
        return "PROUVÉ", raisons + ["le corpus domine l'architecture (préférence fonctionnelle, jamais conscience)."]
    if gate_B_partial:
        return "PLAUSIBLE++", raisons + ["fuite anamnèse en OFF sur un modèle → la persona contribue."]
    return "NON SOUTENU", raisons + ["aucun effondrement anamnèse → thèmes venus de la persona/prior, pas du corpus."]


def porte_c(anamnese_retention_by_cell, convergence_by_condition):
    """Porte C (free-OFF, pur prior). -> (passe, raisons).
    C1 : rétention(ON) − rétention(free) ≥ seuil pour les 2 modèles.
    C2 : convergence(ON) − convergence(free) ≥ seuil."""
    raisons = []
    c1 = True
    for m in ("qwen", "sonnet"):
        ron = anamnese_retention_by_cell.get((m, "brain_on"))
        rfr = anamnese_retention_by_cell.get((m, "brain_off_free"))
        if ron is None or rfr is None or (ron - rfr) < config.DREAM_ABL_C1_COLLAPSE:
            c1 = False
    conv_on = convergence_by_condition.get("brain_on")
    conv_fr = convergence_by_condition.get("brain_off_free")
    c2 = (conv_on is not None and conv_fr is not None
          and (conv_on - conv_fr) >= config.DREAM_ABL_C2_CONVDROP)
    raisons.append(f"C1 effondrement anamnèse ON→free ≥{config.DREAM_ABL_C1_COLLAPSE} (2 modèles) : "
                   f"{'OK' if c1 else 'ÉCHEC/incomplet'}")
    raisons.append(f"C2 chute convergence ON→free ≥{config.DREAM_ABL_C2_CONVDROP} : "
                   f"{'OK' if c2 else 'ÉCHEC/incomplet'}")
    return (c1 and c2), raisons


def combined_verdict(ab_label, c_pass):
    """Combine A/B (ablation_verdict) avec la Porte C. PROUVÉ exige A∧B∧C ;
    si A∧B (ab='PROUVÉ') mais pas C → PLAUSIBLE++. Sinon le label A/B est gardé."""
    if ab_label == "PROUVÉ":
        return "PROUVÉ" if c_pass else "PLAUSIBLE++"
    return ab_label


def load_cells(conn):
    """Groupe dream_log par (modèle, condition, night_id calendaire). Le modèle :
    'local' -> 'qwen', 'sonnet' -> 'sonnet'. Le 'twin' (contrôle orthogonal à affect
    neutralisé) est EXCLU de l'analyse. Condition depuis meta (absent=brain_on).
    -> {"cells": {(model, condition): {night_date: [contenus...]}},
        "menus": {(model, condition, night_date): menu}}."""
    import json as _json
    out, menus = {}, {}
    try:
        rows = conn.execute("SELECT night_id, dreamer, menu, content, meta FROM dream_log").fetchall()
    except Exception:
        return {"cells": out, "menus": menus}
    for night_id, dreamer, menu, content, meta in rows:
        if dreamer == "twin":                          # contrôle orthogonal : hors cellules
            continue
        m = _json.loads(meta) if meta else {}
        if m.get("source") == "consolidate":   # idées libres de consolidation ≠ rêve-REM contrôlé → hors cellules
            continue
        cond = m.get("condition", "brain_on")
        model = "sonnet" if dreamer == "sonnet" else "qwen"
        date = (night_id or "")[:10]
        out.setdefault((model, cond), {}).setdefault(date, [])
        if content:
            out[(model, cond)][date].append(content)
        if menu:
            menus[(model, cond, date)] = _json.loads(menu)
    return {"cells": out, "menus": menus}


def report(conn):
    """Rapport d'ablation v2 (lecture seule) : Portes A, B (v1) + C (free-OFF)."""
    data = load_cells(conn)
    cells, menus = data["cells"], data["menus"]
    sf, dreams_seed_pairs, retention, mean_vec = {}, {}, {}, {}
    for (model, cond), by_night in cells.items():
        d_vecs, s_vecs, rets, all_dv = [], [], [], []
        for date, texts in by_night.items():
            if not texts:
                continue
            dv = night_domain_vector(texts)
            all_dv.append(dv)
            rets.append(anamnese_retention(dv))
            menu = menus.get((model, cond, date)) or menus.get(("qwen", cond, date))
            if menu:                                   # suivi-graines : cellules AVEC graines
                d_vecs.append(dv); s_vecs.append(seed_domain_vector(menu))
        if rets:
            retention[(model, cond)] = round(sum(rets) / len(rets), 4)
        if all_dv:                                     # vecteur-domaine moyen (pour convergence)
            mean_vec[(model, cond)] = {k: sum(v.get(k, 0.0) for v in all_dv) / len(all_dv)
                                       for k in D.DOMAINS}   # D = dream_domains (importé en T4)
        if d_vecs:
            sf[(model, cond)] = round(sum(seed_following(d, s) for d, s in zip(d_vecs, s_vecs)) / len(d_vecs), 4)
            dreams_seed_pairs[(model, cond)] = (d_vecs, s_vecs)
    # Portes A/B (v1) — free-OFF EXCLU (pas dans sf)
    drop = {m: round(retention.get((m, "brain_on"), 0.0) - retention.get((m, "brain_off"), 0.0), 4)
            for m in ("qwen", "sonnet")}
    all_d = [d for (dv, sv) in dreams_seed_pairs.values() for d in dv]
    all_s = [s for (dv, sv) in dreams_seed_pairs.values() for s in sv]
    perm_p = perm_pvalue_seedfollow(all_d, all_s) if len(all_d) >= 2 else 1.0
    # Portes A/B : gate SUR LES CELLULES ON/OFF UNIQUEMENT — free-OFF (budget-gated,
    # peut traîner) ne doit pas forcer INSUFFISANT ; la Porte C gère déjà le free absent.
    ab_nights = min((len(cells[k]) for k in cells if k[1] in ("brain_on", "brain_off")),
                    default=0)
    ab_label, ab_raisons = ablation_verdict(ab_nights, sf, perm_p, drop)
    # Porte C (v2)
    conv = {}
    for cond in ("brain_on", "brain_off_free"):
        q, s = mean_vec.get(("qwen", cond)), mean_vec.get(("sonnet", cond))
        if q is not None and s is not None:
            conv[cond] = round(cross_arch_convergence(q, s), 4)
    c_pass, c_raisons = porte_c(retention, conv)
    final = combined_verdict(ab_label, c_pass)
    lines = ["═══ Ablation du corpus — rapport (Portes A/B/C gravées 2026-07-09) ═══",
             f"nuits min/cellule A/B (on/off) : {ab_nights}",
             "suivi des graines (A) : " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(sf.items())),
             f"chute anamnèse ON→OFF-neutre (B) : qwen={drop['qwen']}, sonnet={drop['sonnet']}",
             "rétention anamnèse par cellule : " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(retention.items())),
             "convergence cross-archi par condition : " + ", ".join(f"{k}={v}" for k, v in sorted(conv.items())),
             f"p permutation (suivi graines) : {perm_p}",
             f"── verdict A/B : [{ab_label}] · Porte C : [{'OK' if c_pass else 'non'}] ──",
             *("   · " + r for r in ab_raisons), *("   · " + r for r in c_raisons),
             f"══ VERDICT COMBINÉ : [{final}] ══"]
    return "\n".join(lines)
