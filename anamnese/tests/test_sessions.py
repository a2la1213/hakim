"""Tests TMP1 — couche temporelle : sessions + landmarks + cycle de vie.

Segmentation d'événements (Zacks) : bornes de session (begin/end), jalons
datés (landmarks), rattachement des épisodes à leur session (tag session_id
sur add, rétro-compatible : sans session courante → NULL comme avant), et
segmentation RÉTROACTIVE idempotente (assign_sessions, écart > SESSION_GAP_H).
felt_time = temps ressenti DÉRIVÉ (jamais persisté) depuis le dernier épisode
HUMAIN. Le scoring de retrieve n'est PAS touché.

DB temporaire migrée (ou legacy pour le cas 8) — JAMAIS data/memory.db
(garde autouse dans conftest.py). mcp_server est importé DANS la fixture,
`_mem` monkeypatché. Tout est offline et déterministe.
"""

import time

import pytest

import config
import memory
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (sessions/landmarks présentes)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


@pytest.fixture
def srv(tmp_path, monkeypatch):
    """(module mcp_server, Memory temp migrée) — `_mem` monkeypatché, embed neutralisé."""
    m = Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(m.db)
    # 1er import de mcp_server : son `_mem = Memory()` doit tomber sur la DB temp.
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", m)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, m
    m.db.close()


def _fn(mod, name):
    """La fonction d'un outil réellement ENREGISTRÉ auprès de FastMCP."""
    return mod.mcp._tool_manager.get_tool(name).fn


def _insert_at(m, ts, role="user", content="episode"):
    """Épisode inséré à un ts CONTRÔLÉ (add() utilise time.time())."""
    cur = m.db.execute(
        "INSERT INTO episodes (ts, role, content, importance, embedding) "
        "VALUES (?,?,?,?,?)",
        (ts, role, content, 0.5, "[]"),
    )
    m.db.commit()
    return cur.lastrowid


def _session_row(m, sid):
    """(started_ts, ended_ts, summary, gap_before_h) de la session sid."""
    return m.db.execute(
        "SELECT started_ts, ended_ts, summary, gap_before_h FROM sessions WHERE id=?",
        (sid,),
    ).fetchone()


def _session_of(m, episode_id):
    """session_id de l'épisode."""
    return m.db.execute(
        "SELECT session_id FROM episodes WHERE id=?", (episode_id,)
    ).fetchone()[0]


# --- Cas 1 : session_begin crée + kv posé ; 2e appel ferme la 1re + gap correct ---
def test_session_begin_creates_closes_previous_and_computes_gap(mem):
    t0 = 1_000_000.0
    s1 = mem.session_begin(t0)

    assert isinstance(s1, int)
    assert mem.kv_get("current_session_id") == str(s1)
    assert _session_row(mem, s1) == (t0, None, None, 0.0)  # 1re session : gap 0

    t1 = t0 + 3 * 3600.0
    s2 = mem.session_begin(t1)

    assert s2 != s1
    assert mem.kv_get("current_session_id") == str(s2)
    # le 2e appel FERME la 1re à now — les deux sessions sont contiguës
    assert _session_row(mem, s1)[1] == pytest.approx(t1)
    assert _session_row(mem, s2)[3] == pytest.approx(0.0)  # fermée à l'instant : gap 0

    # gap RÉEL : fin explicite, puis reprise 5 h plus tard
    t2 = t1 + 3600.0
    mem.session_end(t2)
    s3 = mem.session_begin(t2 + 5 * 3600.0)

    assert _session_row(mem, s3)[3] == pytest.approx(5.0)


# --- Cas 2 : session_end pose ended_ts+summary et EFFACE current_session_id ---
def test_session_end_sets_ended_summary_and_clears_kv(mem):
    t0 = 1_000_000.0
    sid = mem.session_begin(t0, summary="debut : couche temporelle")

    mem.session_end(t0 + 1800.0, summary="fini : sessions posees")

    started, ended, summary, _gap = _session_row(mem, sid)
    assert (started, ended, summary) == (t0, t0 + 1800.0, "fini : sessions posees")
    # kv.value NOT NULL → la clé est SUPPRIMÉE, pas mise à NULL
    assert mem.kv_get("current_session_id") is None
    assert mem.db.execute(
        "SELECT 1 FROM kv WHERE key='current_session_id'"
    ).fetchone() is None

    # sans session courante : no-op silencieux (ne lève pas)
    mem.session_end(t0 + 3600.0)

    # summary non fourni à la fin → celui du begin est CONSERVÉ
    s2 = mem.session_begin(t0 + 7200.0, summary="resume du begin")
    mem.session_end(t0 + 9000.0)
    assert _session_row(mem, s2)[1:3] == (t0 + 9000.0, "resume du begin")


# --- Cas 3 : add tague session_id = session courante ; sans session → NULL ---
def test_add_tags_current_session_else_null(mem):
    before = mem.add("user", "avant toute session", embedding=[1.0, 0.0],
                     extract_facets=False)
    assert _session_of(mem, before) is None  # comportement historique intact

    sid = mem.session_begin(1_000_000.0)
    during = mem.add("assistant", "pendant la session", embedding=[1.0, 0.0],
                     extract_facets=False)
    assert _session_of(mem, during) == sid

    mem.session_end(1_000_100.0)
    after = mem.add("user", "apres la session", embedding=[1.0, 0.0],
                    extract_facets=False)
    assert _session_of(mem, after) is None  # session close → NULL comme avant


# --- Cas 4 : assign_sessions — 2 clusters >2 h d'écart → 2 sessions, idempotent ---
def test_assign_sessions_two_clusters_all_tagged_idempotent(mem):
    t0 = 1_000_000.0
    cluster_a = [_insert_at(mem, t0), _insert_at(mem, t0 + 600.0),
                 _insert_at(mem, t0 + 1200.0)]
    t1 = t0 + 1200.0 + 3 * 3600.0  # 3 h > SESSION_GAP_H (2 h)
    cluster_b = [_insert_at(mem, t1), _insert_at(mem, t1 + 300.0)]

    res = mem.assign_sessions()

    assert res == {"sessions": 2, "episodes_tagged": 5}
    assert {_session_of(mem, e) for e in cluster_a} == {1}  # renuméroté 1..N
    assert {_session_of(mem, e) for e in cluster_b} == {2}
    assert _session_row(mem, 1) == (t0, t0 + 1200.0, None, 0.0)
    started, ended, _sum, gap = _session_row(mem, 2)
    assert (started, ended) == (t1, t1 + 300.0)
    assert gap == pytest.approx(3.0)  # heures depuis la fin de la session 1

    # IDEMPOTENT : 2e appel = même résultat, mêmes lignes, mêmes tags
    res2 = mem.assign_sessions()

    assert res2 == res
    assert mem.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    assert {_session_of(mem, e) for e in cluster_a} == {1}
    assert {_session_of(mem, e) for e in cluster_b} == {2}

    # gap_h explicite : 10 h > 3 h d'écart → un seul bloc
    res3 = mem.assign_sessions(gap_h=10.0)
    assert res3 == {"sessions": 1, "episodes_tagged": 5}
    assert {_session_of(mem, e) for e in cluster_a + cluster_b} == {1}


# --- Cas 5 : landmark_add insère un jalon lisible (défauts compris) ---
def test_landmark_add_inserts_readable_landmark(mem):
    lid = mem.landmark_add(1_000_000.0, "premiere consolidation reussie",
                           kind="victoire", salience=0.8)

    assert isinstance(lid, int)
    assert mem.db.execute(
        "SELECT ts, label, kind, salience FROM landmarks WHERE id=?", (lid,)
    ).fetchone() == (1_000_000.0, "premiere consolidation reussie", "victoire", 0.8)

    lid2 = mem.landmark_add(1_000_100.0, "jalon minimal")  # défauts
    assert mem.db.execute(
        "SELECT label, kind, salience FROM landmarks WHERE id=?", (lid2,)
    ).fetchone() == ("jalon minimal", None, 0.5)


# --- Cas 6 : felt_time — ~0 récent, monte avec le gap, borné [0,1], DÉRIVÉ ---
def test_felt_time_near_zero_recent_grows_bounded_derived(mem):
    now = 1_000_000.0
    assert mem.felt_time(now) == 0.0  # mémoire vide : aucun écart ressenti

    _insert_at(mem, now - 60.0, role="user", content="dernier echange humain")

    v_recent = mem.felt_time(now)
    v_24h = mem.felt_time(now + 24 * 3600.0)
    v_72h = mem.felt_time(now + 72 * 3600.0)
    v_year = mem.felt_time(now + 365 * 24 * 3600.0)

    assert v_recent == pytest.approx(0.0, abs=0.01)  # ~0 si activité récente
    assert v_recent < v_24h < v_72h < v_year  # monte avec le gap
    assert v_24h == pytest.approx(0.5, abs=0.01)  # 1 - 0.5**(24/24)
    for v in (v_recent, v_24h, v_72h, v_year):
        assert 0.0 <= v <= 1.0  # borné [0,1]

    # seul le dernier épisode HUMAIN compte : une rumination daemon fraîche
    # ne remet pas le temps ressenti à zéro
    _insert_at(mem, now + 72 * 3600.0, role="reflection", content="rumination")
    assert mem.felt_time(now + 72 * 3600.0) == pytest.approx(v_72h)

    # DÉRIVÉ, pas persisté : aucune écriture en DB
    before = mem.db.total_changes
    mem.felt_time(now + 24 * 3600.0)
    assert mem.db.total_changes == before


# --- Cas 7 : outils MCP session_begin/session_end/landmark_add (tool.fn) ---
def test_mcp_session_and_landmark_tools(srv):
    mod, m = srv

    out = _fn(mod, "session_begin")("reprise du projet anamnese")
    sid = int(m.kv_get("current_session_id"))
    assert str(sid) in out
    started, ended, summary, _gap = _session_row(m, sid)
    assert ended is None and summary == "reprise du projet anamnese"

    eid = m.add("user", "message pendant la session", embedding=[1.0, 0.0],
                extract_facets=False)
    assert _session_of(m, eid) == sid  # la voie MCP tague bien les épisodes

    _fn(mod, "session_end")("fin de soiree")
    assert m.kv_get("current_session_id") is None
    _started, ended, summary, _gap = _session_row(m, sid)
    assert ended is not None and summary == "fin de soiree"

    out2 = _fn(mod, "landmark_add")("migration 2.0 terminee", "milestone", 0.9)
    assert "migration 2.0 terminee" in out2
    assert m.db.execute(
        "SELECT label, kind, salience FROM landmarks"
    ).fetchone() == ("migration 2.0 terminee", "milestone", 0.9)


# --- Cas 8 : legacy — DB pré-2.0 (sans sessions/landmarks) → rien ne lève ---
def test_legacy_db_methods_do_not_raise(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    tables = {r[0] for r in m.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "sessions" not in tables and "landmarks" not in tables

    assert m.session_begin(2000.0) is None          # dégradé propre, pas d'exception
    m.session_end(2100.0)                           # no-op silencieux
    assert m.landmark_add(2200.0, "jalon") is None  # pas de table → None
    assert m.assign_sessions() == {"sessions": 0, "episodes_tagged": 0}
    v = m.felt_time(2000.0)  # seed humain à ts~1000 : dérivable même en legacy
    assert 0.0 <= v <= 1.0

    # add() reste rétro-compatible : insertion intacte sur le schéma d'origine
    eid = m.add("user", "ajout sur schema legacy", extract_facets=False)
    assert eid
    assert m.db.execute(
        "SELECT content FROM episodes WHERE id=?", (eid,)
    ).fetchone() == ("ajout sur schema legacy",)
    m.db.close()


def _session_count(m):
    """Nombre total de lignes dans sessions."""
    return m.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


# --- Cas 9 : wm_boot AUTO-gère les sessions — ouvre, idempotent, segmente ---
def test_wm_boot_autosession_opens_idempotent_and_segments_by_gap(mem):
    t0 = 1_000_000.0
    res = mem.wm_boot(t0)

    # le contrat WM de wm_boot est INCHANGÉ (mêmes clés, mêmes zéros à vide)
    assert res == {"focus_n": 0, "halo_n": 0, "reseeded": 0}
    # ... et exactement UNE session s'est ouverte mécaniquement
    assert _session_count(mem) == 1
    s1 = int(mem.kv_get("current_session_id"))
    assert _session_row(mem, s1) == (t0, None, None, 0.0)

    # IDEMPOTENT : un 2e boot dans la foulée NE crée PAS de 2e session
    mem.wm_boot(t0 + 60.0)

    assert _session_count(mem) == 1
    assert int(mem.kv_get("current_session_id")) == s1
    assert _session_row(mem, s1)[1] is None  # toujours ouverte

    # écart > SESSION_GAP_H (2 h) : frontière d'événement — nouvelle session,
    # l'ancienne close à sa DERNIÈRE ACTIVITÉ (t0), gap_before_h fidèle
    t1 = t0 + 3 * 3600.0
    mem.wm_boot(t1)

    assert _session_count(mem) == 2
    s2 = int(mem.kv_get("current_session_id"))
    assert s2 != s1
    assert _session_row(mem, s1)[1] == pytest.approx(t0)  # close au vécu, pas à now
    started, ended, _sum, gap = _session_row(mem, s2)
    assert (started, ended) == (t1, None)
    assert gap == pytest.approx(3.0)  # heures RÉELLES depuis la dernière activité

    # la dernière ACTIVITÉ (dernier épisode tagué) prime sur started_ts :
    # un épisode récent garde la session chaude même si elle a > 2 h d'âge
    e = _insert_at(mem, t1 + 1.5 * 3600.0)
    mem.db.execute("UPDATE episodes SET session_id=? WHERE id=?", (s2, e))
    mem.db.commit()
    mem.wm_boot(t1 + 2.5 * 3600.0)  # 2.5 h après started, 1 h après l'épisode

    assert _session_count(mem) == 2  # conservée : pas de spam de sessions
    assert int(mem.kv_get("current_session_id")) == s2

    # nouveau gap > 2 h depuis l'épisode : close à l'épisode, gap correct
    mem.wm_boot(t1 + 1.5 * 3600.0 + 3 * 3600.0)

    assert _session_count(mem) == 3
    s3 = int(mem.kv_get("current_session_id"))
    assert _session_row(mem, s2)[1] == pytest.approx(t1 + 1.5 * 3600.0)
    assert _session_row(mem, s3)[3] == pytest.approx(3.0)


# --- Cas 10 : legacy — wm_boot sans table sessions ne lève pas, zéro artefact ---
def test_wm_boot_legacy_db_without_sessions_does_not_raise(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    tables = {r[0] for r in m.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "sessions" not in tables

    res = m.wm_boot(time.time())  # seeds ts~1000 hors fenêtre : rien à semer

    assert res == {"focus_n": 0, "halo_n": 0, "reseeded": 0}  # contrat intact
    assert m.kv_get("current_session_id") is None  # aucun artefact de session
    m.db.close()
