"""Régressions review finale : le twin ne doit PAS contaminer (qwen, brain_on),
et le gate n_nights des Portes A/B ne doit dépendre QUE des cellules on/off
(pas de brain_off_free budget-gated qui traîne à 1 nuit)."""
import json

import dream_ablation as A

# Schéma dream_log EXACT (cf. migrations.py).
_DREAM_LOG_DDL = (
    "CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY, ts REAL NOT NULL, "
    "night_id TEXT NOT NULL, dreamer TEXT NOT NULL, seed_state TEXT, menu TEXT, "
    "chosen TEXT, content TEXT, facets TEXT, written INTEGER DEFAULT 0, meta TEXT)"
)


def _insert(conn, night_id, dreamer, content, meta=None, menu=None):
    conn.execute(
        "INSERT INTO dream_log (ts, night_id, dreamer, seed_state, menu, chosen, "
        "content, facets, written, meta) VALUES (0.0,?,?,NULL,?,NULL,?,NULL,0,?)",
        (night_id, dreamer,
         json.dumps(menu) if menu is not None else None,
         content,
         json.dumps(meta) if meta is not None else None),
    )


def test_twin_excluded_from_qwen_brain_on(tmp_db):
    """Le twin (contrôle orthogonal, affect neutralisé) ne doit PAS être plié dans
    la cellule d'analyse (qwen, brain_on)."""
    tmp_db.execute(_DREAM_LOG_DDL)
    menu = [{"snippet": "graine anodine"}]
    # rêve réel : dreamer local, condition brain_on, contenu domaine ANAMNESE.
    _insert(tmp_db, "2026-06-15", "local", "ma mémoire et ma conscience",
            meta={"condition": "brain_on"}, menu=menu)
    # twin : même nuit, pas de meta.condition (=> brain_on sous l'ancien mapping),
    # dreamer 'twin' (=> 'qwen' sous l'ancien mapping) — contenu NEUTRE.
    _insert(tmp_db, "2026-06-15", "twin", "la photosynthèse des feuilles", menu=menu)
    tmp_db.commit()

    data = A.load_cells(tmp_db)
    cell = data["cells"].get(("qwen", "brain_on"), {})
    texts = [t for texts in cell.values() for t in texts]

    assert any("mémoire" in t for t in texts), texts       # le rêve réel est là
    assert all("photosynthèse" not in t for t in texts), texts  # le twin est exclu
    assert texts == ["ma mémoire et ma conscience"]


def test_load_cells_return_shape():
    """Le docstring doit annoncer la vraie forme : {'cells': ..., 'menus': ...}."""
    assert "cells" in A.load_cells.__doc__
    assert "menus" in A.load_cells.__doc__


def _nights(n):
    return {f"2026-06-{i:02d}": ["x"] for i in range(1, n + 1)}


def test_ab_nights_expression_ignores_brain_off_free():
    """Le gate A/B se calcule sur les cellules on/off SEULEMENT ; un brain_off_free
    à 1 nuit ne doit pas tomber le compteur A/B."""
    cells = {
        ("qwen", "brain_on"): _nights(10),
        ("qwen", "brain_off"): _nights(10),
        ("sonnet", "brain_on"): _nights(10),
        ("sonnet", "brain_off"): _nights(10),
        ("qwen", "brain_off_free"): _nights(1),   # budget-gated, en retard
    }
    ab_nights = min((len(cells[k]) for k in cells if k[1] in ("brain_on", "brain_off")),
                    default=0)
    n_nights_all = min((len(bn) for bn in cells.values()), default=0)
    assert ab_nights == 10          # A/B complet
    assert n_nights_all == 1        # l'ancien calcul (buggé) plombait tout


def test_report_ab_not_insufficient_when_free_lags(tmp_db):
    """report() ne doit PAS renvoyer INSUFFISANT sur A/B quand on/off ont ≥10 nuits
    mais que brain_off_free traîne à 1 nuit (budget-gated)."""
    tmp_db.execute(_DREAM_LOG_DDL)
    # 10 nuits pour chacune des 4 cellules on/off (sans menu : rapide, sans perm coûteuse).
    cells = [("local", "brain_on"), ("local", "brain_off"),
             ("sonnet", "brain_on"), ("sonnet", "brain_off")]
    for dreamer, cond in cells:
        for i in range(1, 11):
            _insert(tmp_db, f"2026-06-{i:02d}", dreamer, "un rêve",
                    meta={"condition": cond})
    # une seule nuit free-OFF (retard budgétaire).
    _insert(tmp_db, "2026-06-01", "local", "un rêve libre",
            meta={"condition": "brain_off_free"})
    tmp_db.commit()

    out = A.report(tmp_db)
    assert "INSUFFISANT" not in out, out
