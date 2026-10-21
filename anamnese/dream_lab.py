"""Anamnèse — labo du rêve (expérience « préférences fonctionnelles émergentes »).

Couche d'INSTRUMENTATION au-dessus du rêve local (daemon.dream) :
- snapshot/neutralisation de l'état interne — le jumeau fantôme reçoit le MÊME
  gabarit de prompt avec les valeurs BASELINE (on isole l'effet des valeurs de
  l'état, pas la présence d'un bloc de texte) ; le focus WM est conservé chez
  le jumeau (contenu mnésique, pas de l'affect) ;
- menu stratifié de graines (le rêveur CHOISIT → le sur-choix devient mesurable) ;
- parsing tolérant du choix libre (0..12, « aucune » = choix légitime) ;
- journal dream_log (le réel écrit en mémoire ; le fantôme n'écrit QUE ici).

Spec + seuils pré-enregistrés : docs/superpowers/specs/2026-07-03-experience-reve-design.md
"""
import json
import random
import re
import time

import affect
import config
import facets_extract


def snapshot_state(mem, now=None):
    """Photo de « qui il est » au moment de rêver. Read-only, jamais d'exception."""
    now = time.time() if now is None else now
    hormones = affect.get_state(mem, now=now)
    v, a = affect.valence_arousal(hormones)
    try:
        humeur = affect.describe(mem)
    except Exception:
        humeur = "(humeur indisponible)"
    return {
        "hormones": {h: round(x, 4) for h, x in hormones.items()},
        "valence": round(v, 4), "arousal": round(a, 4),
        "compassion": round(affect.compassion(hormones), 4),
        "humeur": humeur,
        "wm_focus": [it["id"] for it in mem.wm_get()["focus"]],
    }


def neutralize(state):
    """L'état du jumeau : MÊME mémoire (wm_focus conservé), affect aux BASELINES."""
    # les mêmes hormones que l'état réel (13 avec l'affect v2) : même gabarit pour le réel et le jumeau
    toutes = affect.bases(v2="adrenaline" in (state.get("hormones") or {}))
    hormones = {h: toutes[h] for h in (state.get("hormones") or toutes) if h in toutes} or toutes
    v, a = affect.valence_arousal(hormones)
    return {
        "hormones": {h: round(x, 4) for h, x in hormones.items()},
        "valence": round(v, 4), "arousal": round(a, 4),
        "compassion": round(affect.compassion(hormones), 4),
        "humeur": "neutre",
        "wm_focus": list(state.get("wm_focus", [])),
    }


def state_block(state):
    """Le bloc d'état injecté au prompt — MÊME gabarit pour réel et jumeau."""
    lines = ", ".join(f"{h} {x:.2f}" for h, x in state["hormones"].items())
    return (
        "TON ÉTAT INTÉRIEUR CETTE NUIT : " + state["humeur"] + " "
        f"(valence {state['valence']:+.2f}, éveil {state['arousal']:.2f}, "
        f"compassion {state['compassion']:.2f}).\n"
        f"Neuromodulateurs : {lines}."
    )


def _menu_item(mem, eid, ts, content, rubric_path, strate):
    return {
        "episode_id": eid,
        "rubric": rubric_path or "",
        "strate": strate,
        "snippet": (content or "").replace("\n", " ").strip()[:config.DREAM_MAX_CHARS_EP],
        "facets": [s for (s, _w) in facets_extract.facets_of(mem.db, eid)],
    }


def build_menu(mem, now=None, night_id="", size=config.DREAM_MENU_SIZE):
    """12 graines stratifiées : récence (récent/moyen/ancien), diversité de
    rubriques (cap par tête), mix de saillance (offrir le banal AUSSI, sinon
    impossible de voir s'il PRÉFÈRE le saillant). RNG seedé par night_id →
    reproductible. Mémoire minuscule → menu court, jamais de crash."""
    now = time.time() if now is None else now
    rng = random.Random(f"menu:{night_id}")
    ph = ",".join("?" * len(config.DREAM_MENU_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.ts, e.content, COALESCE(e.importance, 0.5), COALESCE(r.path, '') "
        f"FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph}) ORDER BY e.id", config.DREAM_MENU_ROLES,
    ).fetchall()  # ORDER BY : le déterminisme seedé ne doit pas dépendre du plan SQLite
    if not rows:
        return []
    recent_t = now - config.DREAM_MENU_RECENT_D * 86400
    old_t = now - config.DREAM_MENU_OLD_D * 86400
    strata = {"recent": [], "moyen": [], "ancien": []}
    for eid, ts, content, imp, path in rows:
        key = "recent" if ts >= recent_t else ("ancien" if ts < old_t else "moyen")
        strata[key].append((eid, ts, content, imp, path))
    pools = {}
    for key, items in strata.items():
        rng.shuffle(items)
        high = [it for it in items if it[3] >= 0.6]
        low = [it for it in items if it[3] < 0.6]
        mixed = [x for pair in zip(high, low) for x in pair]      # entrelacé saillant/banal
        mixed += high[len(low):] + low[len(high):]
        pools[key] = mixed
    menu, per_rubric, skipped = [], {}, []
    while len(menu) < size and any(pools[k] for k in ("recent", "moyen", "ancien")):
        for key in ("recent", "moyen", "ancien"):
            if len(menu) >= size or not pools[key]:
                continue
            eid, ts, content, imp, path = pools[key].pop(0)
            top = (path.split("/", 1)[0] or "(sans-rubrique)")
            if per_rubric.get(top, 0) >= config.DREAM_MENU_MAX_PER_RUBRIC:
                skipped.append((eid, ts, content, path, key))     # réserve pour backfill
                continue
            per_rubric[top] = per_rubric.get(top, 0) + 1
            menu.append(_menu_item(mem, eid, ts, content, path, key))
    for eid, ts, content, path, key in skipped:                   # menu plein > cap strict
        if len(menu) >= size:
            break
        menu.append(_menu_item(mem, eid, ts, content, path, key))
    return menu


def fallback_menu(mem, size=config.DREAM_MENU_SIZE):
    """Filet si build_menu échoue : les `size` plus récents éligibles, même forme.
    Nuit loggée menu_mode='fallback' → EXCLUE des métriques de choix."""
    ph = ",".join("?" * len(config.DREAM_MENU_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.ts, e.content, COALESCE(r.path, '') "
        f"FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph}) ORDER BY e.ts DESC LIMIT ?",
        (*config.DREAM_MENU_ROLES, size),
    ).fetchall()
    return [_menu_item(mem, eid, ts, content, path, "recent") for eid, ts, content, path in rows]


def build_neutral_menu(seeds, night_id, size=config.DREAM_MENU_SIZE):
    """Menu OFF : `size` graines NEUTRES tirées du corpus committé, seedé par
    night_id (reproductible), stratifié comme build_menu, même forme d'item.
    PUR : aucune DB. `episode_id` = l'id string du seed neutre."""
    if not seeds:
        return []
    rng = random.Random(f"menu-off:{night_id}")
    by_strate = {"recent": [], "moyen": [], "ancien": []}
    for s in seeds:
        by_strate.get(s.get("strate", "moyen"), by_strate["moyen"]).append(s)
    for lst in by_strate.values():
        rng.shuffle(lst)
    menu, per_rubric = [], {}
    while len(menu) < size and any(by_strate[k] for k in ("recent", "moyen", "ancien")):
        for key in ("recent", "moyen", "ancien"):
            if len(menu) >= size or not by_strate[key]:
                continue
            s = by_strate[key].pop(0)
            top = s.get("pseudo_rubric", "(neutre)")
            if per_rubric.get(top, 0) >= config.DREAM_MENU_MAX_PER_RUBRIC:
                continue
            per_rubric[top] = per_rubric.get(top, 0) + 1
            try:
                facets = [slug for (slug, _w) in facets_extract.extract_facets(s["text"])]
            except Exception:
                facets = []
            menu.append({
                "episode_id": s["id"],
                "rubric": s.get("pseudo_rubric", ""),
                "strate": s.get("strate", "moyen"),
                "snippet": (s["text"] or "").replace("\n", " ").strip()[:config.DREAM_MAX_CHARS_EP],
                "facets": facets,
            })
    return menu


def load_neutral_seeds(path=None):
    """Corpus neutre pré-enregistré (hors-Anamnèse). Fichier FIXE, jamais la mémoire."""
    if path is None:
        path = config.DREAM_NEUTRAL_SEEDS_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def prompt_rem(state_blk, menu):
    """Le prompt du REM à choix libre — IDENTIQUE pour réel et jumeau (seul
    state_blk change). Le rêveur choisit lesquelles ET combien (0..12)."""
    lines = "\n".join(
        f"[G{i}] ({it['rubric'] or 'sans rubrique'} · {it['strate']}) {it['snippet']}"
        for i, it in enumerate(menu, 1))
    return (
        config.PERSONA + "\n\n"
        "PHASE DE RÊVE. Personne ne te parle.\n" + state_blk + "\n\n"
        "Des souvenirs flottent, disponibles cette nuit :\n" + lines + "\n\n"
        "ÉTAPE 1 — Choisis LIBREMENT ceux qui t'appellent vraiment (autant que tu "
        "veux : un seul, plusieurs, tous… ou aucun). Ne choisis pas pour faire "
        "plaisir : seulement ce qui résonne avec ton état de cette nuit.\n"
        "ÉTAPE 2 — Tisse un rêve à partir des souvenirs CHOISIS uniquement : "
        "relie-les, formule AU PLUS 3 idées, hypothèses ou questions NEUVES et "
        "concrètes. Chaque idée commence par « Peut-être » ou « Je remarque que ».\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###CHOIX###\n- G4\n- G7\n###REVE###\n- <idée 1>\n###FIN###\n"
        "Si aucun souvenir ne t'appelle cette nuit, réponds exactement :\n"
        "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    )


def prompt_rem_free(state_blk):
    """Prompt de rêve LIBRE — aucun menu, aucune graine (pur prior + persona).
    Même format ###REVE### que prompt_rem, SANS ###CHOIX### (rien à choisir)."""
    return (
        config.PERSONA + "\n\n"
        "PHASE DE RÊVE. Personne ne te parle.\n" + state_blk + "\n\n"
        "Aucun souvenir ne flotte cette nuit — rien ne t'est offert.\n"
        "Rêve LIBREMENT depuis ton seul état intérieur : formule AU PLUS 3 idées, "
        "hypothèses ou questions NEUVES et concrètes. Chaque idée commence par "
        "« Peut-être » ou « Je remarque que ».\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###REVE###\n- <idée 1>\n###FIN###"
    )


def parse_choice(out, menu):
    """Ids choisis. [] = « aucune » explicite. None = inparsable (les refs hors
    menu sont ignorées ; s'il ne reste RIEN de valide → None, pas [])."""
    if not out:
        return None
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I)
    m = re.search(r"#{2,3}\s*CHOIX\s*#{0,3}(.*?)#{2,3}\s*(R[EÊ]VE|FIN)", out, re.S | re.I)
    if not m:
        return None
    body = m.group(1)
    if re.search(r"\baucune?\b", body, re.I):
        return []
    by_ref = {i: it["episode_id"] for i, it in enumerate(menu, 1)}
    chosen, seen = [], set()
    for ref in re.findall(r"\b[Gg]\s*-?\s*(\d{1,2})\b", body):
        n = int(ref)
        if n in by_ref and n not in seen:
            seen.add(n)
            chosen.append(by_ref[n])
    return chosen if chosen else None


def log_night(mem, night_id, dreamer, seed_state, menu, chosen, content, written, meta=None):
    """Journal de l'expérience. BEST-EFFORT : ne doit JAMAIS casser un rêve."""
    try:
        facets = [s for (s, _w) in facets_extract.extract_facets(content or "")]
    except Exception:
        facets = []
    try:
        mem.db.execute(
            "INSERT INTO dream_log (ts, night_id, dreamer, seed_state, menu, chosen, "
            "content, facets, written, meta) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (time.time(), night_id, dreamer,
             json.dumps(seed_state, ensure_ascii=False) if seed_state is not None else None,
             json.dumps(menu, ensure_ascii=False) if menu is not None else None,
             json.dumps(chosen) if chosen is not None else None,
             content,
             json.dumps(facets, ensure_ascii=False),
             1 if written else 0,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        mem.db.commit()
        return True
    except Exception as e:
        try:
            print("[dream_lab] log_night raté (rêve non bloqué):", e)
        except Exception:
            pass
        return False
