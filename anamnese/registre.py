"""Registre avec retour arrière — idée centrale de Prime Agent, adaptée à Anamnèse (2026-10-16).

Une ENTRÉE regroupe tous les changements d'un acteur (une passe de nuit, une annulation…) :
identité (cœur, évolution), compétences, souvenirs créés, rubriques créées, mutations de
taxonomie, curseur de consolidation, chacun avec son état AVANT et APRÈS. `annuler` les défait
en sens inverse.

- On n'enregistre QUE dans un processus où ANAMNESE_REGISTRE désigne une entrée OUVERTE : la
  passe de nuit le transmet à `claude -p`, qui le transmet au serveur MCP (vérifié par une
  sonde). Le démon et les sessions ne sont jamais mêlés à une nuit, et un processus qui survit
  à la fermeture n'écrit plus dans l'entrée.
- Une annulation ne détruit jamais ce qui a changé depuis : chaque changement est comparé à
  l'état qu'il a laissé (identité en bloc, souvenir à sa rubrique de fin d'entrée, taxonomie à
  son état après mutation) ; en cas d'écart, conflit noté et rien d'écrit pour lui. Une erreur
  imprévue sur un changement devient un conflit, jamais l'échec du tout. Une entrée déjà
  annulée ou encore ouverte est refusée. La simulation exécute le vrai algorithme puis annule
  la transaction : elle dit exactement ce que ferait l'annulation.
- Une annulation s'enregistre comme entrée : elle est annulable. Limites assumées : un souvenir
  recréé retrouve contenu, rubrique et date de rangement, pas ses facettes, sa co-activation,
  sa position 3D ni ses liens d'insights ; une mutation de taxonomie annulée ne se ré-applique
  pas (signalé).
- Les compétences gardent leur historique (competences_versions), y compris la version défaite.

Aucune fonction ne committe, sauf ouvrir, fermer et annuler : les notes partent dans la
transaction de l'écriture qu'elles décrivent.
"""
import json
import os
import secrets
import time

import rubrics

ENV = "ANAMNESE_REGISTRE"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS registre (id TEXT PRIMARY KEY, ts REAL NOT NULL, origine TEXT, resume TEXT, "
    "justification TEXT, resultat_attendu TEXT, annule TEXT, annule_par TEXT, ferme_ts REAL)",
    "CREATE TABLE IF NOT EXISTS registre_changements (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "registre_id TEXT NOT NULL, ts REAL NOT NULL, objet TEXT NOT NULL, cle TEXT NOT NULL, avant TEXT, apres TEXT)",
    "CREATE INDEX IF NOT EXISTS idx_registre_ch ON registre_changements(registre_id)",
    "CREATE TABLE IF NOT EXISTS competences_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
    "ts REAL, description TEXT, content TEXT, remplace_ts REAL)",
)
CLES_IDENTITE = ("self_core", "self_evolution", "self_evolution_ts", "self_model")


class Conflit(Exception):
    pass


def _assurer(conn):
    for stmt in _SCHEMA:            # execute (pas executescript, qui committerait la transaction en cours)
        conn.execute(stmt)


def _table(conn, nom):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nom,)).fetchone() is not None


def _j(v):
    return None if v is None else json.dumps(v, ensure_ascii=False)


def _l(v):
    return None if v is None else json.loads(v)


def courant():
    return os.environ.get(ENV) or None


def _creer(conn, origine, resume):
    _assurer(conn)
    rid = time.strftime("reg_%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    conn.execute("INSERT INTO registre (id, ts, origine, resume) VALUES (?,?,?,?)", (rid, time.time(), origine, resume))
    return rid


def ouvrir(conn, origine, resume="", justification="", resultat_attendu=""):
    rid = _creer(conn, origine, resume)
    conn.execute("UPDATE registre SET justification=?, resultat_attendu=? WHERE id=?", (justification, resultat_attendu, rid))
    conn.commit()
    return rid


def fermer(conn, rid, resume=None, suite=None):
    """Ferme l'entrée. `suite` s'ajoute au résumé (ex. le compte rendu du modèle) au lieu de
    l'écraser. Fige la rubrique de fin d'entrée des souvenirs créés (contrôle de l'annulation)."""
    for ch_id, cle, apres in conn.execute(
            "SELECT id, cle, apres FROM registre_changements WHERE registre_id=? AND objet='episode' "
            "AND avant IS NULL", (rid,)).fetchall():
        ligne = _ligne_episode(conn, int(cle))
        if ligne is not None:
            conn.execute("UPDATE registre_changements SET apres=? WHERE id=?",
                         (_j({**(_l(apres) or {}), "rubrique_fin": ligne.get("path")}), ch_id))
    if suite:
        actuel = (conn.execute("SELECT resume FROM registre WHERE id=?", (rid,)).fetchone() or [""])[0] or ""
        resume = (resume or actuel) + " — " + " ".join(str(suite).split())
    if resume is None:
        conn.execute("UPDATE registre SET ferme_ts=? WHERE id=?", (time.time(), rid))
    else:
        conn.execute("UPDATE registre SET ferme_ts=?, resume=? WHERE id=?", (time.time(), resume[:2000], rid))
    conn.commit()


def _ouverte(conn, rid):
    if not _table(conn, "registre"):
        return False
    row = conn.execute("SELECT ferme_ts, annule_par FROM registre WHERE id=?", (rid,)).fetchone()
    return row is not None and row[0] is None and row[1] is None


def noter(conn, objet, cle, avant, apres, rid=None):
    """Note un changement dans l'entrée courante (ou `rid`), si elle est OUVERTE. Ne committe pas."""
    rid = rid or courant()
    if not rid or conn is None or not _ouverte(conn, rid):
        return
    conn.execute("INSERT INTO registre_changements (registre_id, ts, objet, cle, avant, apres) VALUES (?,?,?,?,?,?)",
                 (rid, time.time(), objet, str(cle), _j(avant), _j(apres)))


# --- accroches appelées par les écrivains --------------------------------------------------

def _versionner(conn, name, description, content, ts):
    _assurer(conn)
    conn.execute("INSERT INTO competences_versions (name, ts, description, content, remplace_ts) VALUES (?,?,?,?,?)",
                 (name, ts, description, content, time.time()))


def avant_competence(conn, name, description, content):
    """Avant d'écrire une compétence : versionne l'ancienne (si elle change) et note le changement."""
    row = conn.execute("SELECT description, content, ts FROM skills WHERE name=?", (name,)).fetchone()
    avant = {"description": row[0], "content": row[1]} if row else None
    if row and (row[0], row[1]) != (description, content):
        _versionner(conn, name, row[0], row[1], row[2])
    noter(conn, "skill", name, avant, {"description": description, "content": content})


def versions_competence(conn, name):
    if not _table(conn, "competences_versions"):
        return []
    return [{"description": d, "content": c, "ts": ts} for d, c, ts in conn.execute(
        "SELECT description, content, ts FROM competences_versions WHERE name=? ORDER BY id", (name,))]


def etat_taxonomie(conn, inv):
    """L'état que laisse une mutation (appelé juste APRÈS elle) ; comparé à l'annulation."""
    op = (inv or {}).get("op")
    if op == "reclassify":
        ligne = _ligne_episode(conn, inv.get("episode_id"))
        return {"episode": inv.get("episode_id"), "rubrique": ligne.get("path") if ligne else "(supprimé)"}
    if op == "relabel":
        row = conn.execute("SELECT label FROM rubrics WHERE path=?", (inv.get("path"),)).fetchone()
        return {"path": inv.get("path"), "label": row[0] if row else None}
    if op == "rename":
        return {"present": rubrics.get_rubric_id(conn, inv.get("old")) is not None,
                "absent": rubrics.get_rubric_id(conn, inv.get("new")) is None}
    if op == "unmerge":
        return {"dst": rubrics.get_rubric_id(conn, inv.get("dst")) is not None,
                "src_absente": rubrics.get_rubric_id(conn, inv.get("src")) is None}
    return None


# --- lecture -------------------------------------------------------------------------------

def entrees(conn, n=20):
    if not _table(conn, "registre"):
        return []
    rows = conn.execute(
        "SELECT r.id, r.ts, r.origine, r.resume, r.annule, r.annule_par, r.ferme_ts, "
        "(SELECT count(*) FROM registre_changements c WHERE c.registre_id = r.id) "
        "FROM registre r ORDER BY r.ts DESC, r.rowid DESC LIMIT ?", (n,)).fetchall()
    return [{"id": i, "ts": ts, "origine": o, "resume": r, "annule": a, "annule_par": ap,
             "ferme": f is not None, "changements": n_ch} for i, ts, o, r, a, ap, f, n_ch in rows]


def changements(conn, rid):
    if not _table(conn, "registre_changements"):
        return []
    return [{"id": i, "objet": o, "cle": k, "avant": _l(av), "apres": _l(ap)} for i, o, k, av, ap in conn.execute(
        "SELECT id, objet, cle, avant, apres FROM registre_changements WHERE registre_id=? ORDER BY id", (rid,))]


# --- annulation ----------------------------------------------------------------------------

def _kv(conn, cle):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (cle,)).fetchone()
    return row[0] if row else None


def _skill(conn, name):
    row = conn.execute("SELECT description, content FROM skills WHERE name=?", (name,)).fetchone()
    return {"description": row[0], "content": row[1]} if row else None


def _ligne_episode(conn, eid):
    if eid is None:
        return None
    cur = conn.execute("SELECT e.*, r.path FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id=?", (eid,))
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def _purger_journal_taxonomie(conn, eid):
    """Retire du journal de taxonomie les entrées qui citent un souvenir supprimé (sinon
    taxonomy_undo resterait bloqué sur « épisode inexistant »)."""
    row = conn.execute("SELECT value FROM kv WHERE key='taxonomy_log'").fetchone()
    if not row:
        return
    try:
        entrees_log = json.loads(row[0])
    except ValueError:
        return

    def cite(e):
        inv = e.get("inverse") if isinstance(e, dict) else None
        if not isinstance(inv, dict):
            return False
        return inv.get("episode_id") == eid or any(isinstance(x, list) and x and x[0] == eid
                                                   for x in inv.get("episodes", []))
    restes = [e for e in entrees_log if not cite(e)]
    if len(restes) != len(entrees_log):
        conn.execute("UPDATE kv SET value=? WHERE key='taxonomy_log'", (json.dumps(restes, ensure_ascii=False),))


def _liens(conn, eid):
    if not _table(conn, "insight_edges"):
        return {"sources": [], "derives": []}
    return {"sources": [r[0] for r in conn.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (eid,))],
            "derives": [r[0] for r in conn.execute("SELECT insight_id FROM insight_edges WHERE source_id=?", (eid,))]}


def _supprimer_episode(conn, eid):
    ligne = _ligne_episode(conn, eid)
    ligne["_liens"] = _liens(conn, eid)       # provenance, restaurée si l'annulation est annulée
    if ligne["rubric_id"] is not None:
        rubrics._detach_from(conn, ligne["rubric_id"], rubrics._parse_embedding(ligne["embedding"]))
    for table, condition in (("episode_facets", "episode_id=?"), ("brain_layout", "episode_id=?"),
                             ("coactivation", "a_id=? OR b_id=?"), ("insight_edges", "insight_id=? OR source_id=?")):
        if _table(conn, table):
            conn.execute(f"DELETE FROM {table} WHERE {condition}", (eid,) * condition.count("?"))
    conn.execute("DELETE FROM episodes WHERE id=?", (eid,))
    _purger_journal_taxonomie(conn, eid)
    return ligne


def _recreer_episode(conn, ligne, now):
    colonnes = [c for c in ligne if c not in ("path", "rubric_id", "rubric_conf", "routed_ts", "_liens")]
    conn.execute(f"INSERT INTO episodes ({', '.join(colonnes)}) VALUES ({', '.join('?' * len(colonnes))})",
                 [ligne[c] for c in colonnes])
    if ligne.get("path") and rubrics.get_rubric_id(conn, ligne["path"]) is not None:
        rubrics._attach_core(conn, ligne["id"], ligne["path"],
                             ligne.get("rubric_conf") if ligne.get("rubric_conf") is not None else 0.9, now)
        if ligne.get("routed_ts") is not None:
            conn.execute("UPDATE episodes SET routed_ts=? WHERE id=?", (ligne["routed_ts"], ligne["id"]))
    liens = ligne.get("_liens") or {}
    if _table(conn, "insight_edges"):
        paires = [(ligne["id"], s) for s in liens.get("sources", [])] + [(d, ligne["id"]) for d in liens.get("derives", [])]
        for a, b in paires:
            if conn.execute("SELECT 1 FROM episodes WHERE id=?", (b if a == ligne["id"] else a,)).fetchone():
                conn.execute("INSERT OR IGNORE INTO insight_edges (insight_id, source_id) VALUES (?,?)", (a, b))


def _defaire(conn, ch, nouvel, now, crees=frozenset()):
    """Défait UN changement et note son inverse dans l'entrée `nouvel`. Lève Conflit si l'état
    a changé depuis l'entrée."""
    objet, cle, avant, apres = ch["objet"], ch["cle"], ch["avant"], ch["apres"]
    if objet == "kv":
        if _kv(conn, cle) != apres:
            raise Conflit(f"{cle} a changé depuis")
        if avant is None:
            conn.execute("DELETE FROM kv WHERE key=?", (cle,))
        else:
            conn.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)", (cle, avant, now))
        noter(conn, "kv", cle, apres, avant, rid=nouvel)
    elif objet == "skill":
        actuel = _skill(conn, cle)
        if actuel != apres:
            raise Conflit(f"compétence {cle} modifiée depuis")
        if actuel is not None:                    # la version défaite reste dans l'historique
            _versionner(conn, cle, actuel["description"], actuel["content"], None)
        if avant is None:
            conn.execute("DELETE FROM skills WHERE name=?", (cle,))
        else:
            conn.execute("INSERT OR REPLACE INTO skills (ts, name, description, content) VALUES (?,?,?,?)",
                         (now, cle, avant["description"], avant["content"]))
        noter(conn, "skill", cle, apres, avant, rid=nouvel)
    elif objet == "episode":
        ligne = _ligne_episode(conn, int(cle))
        if avant is None:                         # créé → le supprimer, s'il n'a pas été retouché
            if ligne is None:
                raise Conflit(f"souvenir #{cle} déjà supprimé")
            if apres and "rubrique_fin" in apres and ligne.get("path") != apres["rubrique_fin"]:
                raise Conflit(f"souvenir #{cle} rangé ailleurs depuis ({ligne.get('path')})")
            dependants = [d for d in _liens(conn, int(cle))["derives"] if d not in crees]
            if dependants:
                raise Conflit(f"souvenir #{cle} est la source de faits plus récents ({dependants[:3]})")
            noter(conn, "episode", cle, _supprimer_episode(conn, int(cle)), None, rid=nouvel)
        else:                                     # supprimé (par une annulation) → le recréer
            if ligne is not None:
                raise Conflit(f"souvenir #{cle} existe déjà")
            _recreer_episode(conn, avant, now)
            noter(conn, "episode", cle, None, {"role": avant.get("role"), "content": (avant.get("content") or "")[:300]},
                  rid=nouvel)
    elif objet == "rubrique":
        rid_rub = rubrics.get_rubric_id(conn, cle)
        if avant is None:                         # créée → la supprimer si vide
            if rid_rub is None:
                raise Conflit(f"rubrique {cle} déjà supprimée")
            occupee = conn.execute("SELECT 1 FROM episodes WHERE rubric_id=? LIMIT 1", (rid_rub,)).fetchone() or \
                conn.execute("SELECT 1 FROM rubrics WHERE parent_id=? LIMIT 1", (rid_rub,)).fetchone()
            if occupee:
                raise Conflit(f"rubrique {cle} n'est plus vide")
            conn.execute("DELETE FROM rubrics WHERE id=?", (rid_rub,))
            noter(conn, "rubrique", cle, apres, None, rid=nouvel)
        else:                                     # supprimée → la recréer, étiquette et indice compris
            if rid_rub is not None:
                raise Conflit(f"rubrique {cle} existe déjà")
            import taxonomy
            taxonomy._create_rubric_core(conn, cle, now, label=avant.get("label"), kind_hint=avant.get("kind_hint"))
            noter(conn, "rubrique", cle, None, avant, rid=nouvel)
    elif objet == "taxonomie":
        if avant is not None:
            raise Conflit("une mutation de taxonomie annulée ne se ré-applique pas")
        attendu = apres.get("etat")
        if attendu is None or etat_taxonomie(conn, apres["inverse"]) != attendu:
            raise Conflit(f"taxonomie modifiée depuis : {cle}")
        import taxonomy
        taxonomy.appliquer_inverse(conn, apres["inverse"], ts=apres.get("ts"))
        noter(conn, "taxonomie", cle, apres, None, rid=nouvel)
    else:
        raise Conflit(f"objet inconnu : {objet}")


def annuler(conn, rid, simulation=False, force=False):
    """Défait l'entrée `rid` en sens inverse. Retourne {registre, total, annules, conflits}.
    simulation=True : même algorithme, puis la transaction est annulée (rien n'est écrit).
    force=True : accepte une entrée déjà annulée ou encore ouverte."""
    row = conn.execute("SELECT ferme_ts, annule_par FROM registre WHERE id=?", (rid,)).fetchone() \
        if _table(conn, "registre") else None
    if row is None:
        raise ValueError(f"entrée de registre inconnue : {rid}")
    if row[1] and not force:
        raise ValueError(f"entrée déjà annulée par {row[1]}")
    if row[0] is None and not force:
        raise ValueError("entrée encore ouverte (passe en cours ou interrompue) : --force pour l'annuler quand même")
    chs = list(reversed(changements(conn, rid)))
    rapport = {"registre": None, "total": len(chs), "annules": 0, "conflits": []}
    now = time.time()
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        nouvel = _creer(conn, "annulation", f"annulation de {rid}")

        crees = frozenset(int(c["cle"]) for c in chs if c["objet"] == "episode" and c["avant"] is None)

        def un(ch, nom):
            conn.execute(f"SAVEPOINT {nom}")
            try:
                _defaire(conn, ch, nouvel, now, crees)
                conn.execute(f"RELEASE {nom}")
                return None
            except Exception as e:                # Conflit ou erreur imprévue : ce changement seul
                conn.execute(f"ROLLBACK TO {nom}")
                conn.execute(f"RELEASE {nom}")
                return str(e) if isinstance(e, Conflit) else f"erreur : {e}"

        # Identité en BLOC : self_model = assemble(cœur, évolution) — tout ou rien.
        ident = [ch for ch in chs if ch["objet"] == "kv" and ch["cle"] in CLES_IDENTITE]
        if ident:
            conn.execute("SAVEPOINT identite")
            raisons = [r for r in (un(ch, "un_changement") for ch in ident) if r]
            if raisons:
                conn.execute("ROLLBACK TO identite")
                for ch in ident:
                    rapport["conflits"].append({"cle": ch["cle"], "objet": "kv",
                                                "raison": f"identité modifiée depuis (en bloc) : {raisons[0]}"})
            else:
                rapport["annules"] += len(ident)
            conn.execute("RELEASE identite")
        for ch in chs:
            if ch in ident:
                continue
            raison = un(ch, "un_changement")
            if raison:
                rapport["conflits"].append({"cle": ch["cle"], "objet": ch["objet"], "raison": raison})
            else:
                rapport["annules"] += 1
        resume = (f"annulation de {rid} : {rapport['annules']}/{rapport['total']} changements défaits, "
                  f"{len(rapport['conflits'])} conflit(s)")
        conn.execute("UPDATE registre SET annule_par=? WHERE id=?", (nouvel, rid))
        conn.execute("UPDATE registre SET annule=?, ferme_ts=?, resume=? WHERE id=?", (rid, time.time(), resume, nouvel))
        if simulation:
            conn.rollback()
        else:
            conn.commit()
            rapport["registre"] = nouvel
    except BaseException:
        conn.rollback()
        raise
    return rapport
