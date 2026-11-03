"""Mémoire EXTERNE — le « recall » réel (PAS dans les poids du modèle).

Décision d'archi (recherche A) : on N'utilise PAS de couche de mémoire
neuronale (Titans/TTT = attention linéaire déguisée, pas du vrai recall —
NVIDIA, ICML 2026). Le store externe est la source de vérité.
SQLite + vecteurs (cosine numpy) : zéro extension à installer.

Contient aussi les COMPÉTENCES (mémoire procédurale) = niveau 1 de
l'auto-évolution : l'IA peut sauvegarder/rappeler des procédures apprises.
"""

import sqlite3
import sys
import json
import time

import numpy as np

import salience
import config
import facets_extract
import registre
import rubrics


def _norm(s):
    return " ".join((s or "").lower().split())


# Rôles dont le STOCKAGE (add) promeut l'épisode en mémoire de travail (WM1) :
# le «vécu» de la session (échange, savoir, événement, raisonnement). Les rôles
# du daemon (reflection/outreach/dream/thought) sont EXCLUS — il ne doit pas
# remplir la MDT avec ses ruminations. 'reference' (ingestion de corpus) non plus.
WM_TOUCH_ROLES = ("user", "assistant", "semantic", "episodic", "reasoning")


# Plancher de pertinence d'une compétence proposée au briefing (relecture 2026-10-16 : sans
# plancher, un focus « banc / voix » proposait lexique_applecture à 0,29). À ajuster par Ahmed.
COMPETENCE_PERTINENCE_MIN = 0.35


# Souvenirs périmés (2026-10-16) : Haiku, Sonnet et Opus ont tous présenté comme actuel un état de la
# veille 20:30 que des souvenirs de 20:54 et 21:12 disaient réglé. Le score (pertinence + lexical +
# importance, que le rappel renforce) préférait l'ancien ; la récence (poids 0,1, demi-vie d'une
# semaine) ne départage pas des souvenirs écrits à une heure d'écart.
SUPERSESSION_ROLES = ("semantic", "episodic")
SUPERSESSION_BANDE = 0.25        # « répond aussi à la question » : score à moins de 0,25 du meilleur
SUPERSESSION_ECART_S = 600       # au-delà de 10 min d'écart, l'un est « antérieur » à l'autre


def supersession_rang(scored, top_k, roles=SUPERSESSION_ROLES, bande=SUPERSESSION_BANDE,
                      ecart_s=SUPERSESSION_ECART_S):
    """Le plus récent d'abord parmi les souvenirs d'état qui répondent aussi bien à la question.

    1. L'ensemble rendu reste celui du score (top_k), à UN échange près : le souvenir d'état le plus
       récent de la bande (score ≥ meilleur − bande, rôles semantic/episodic) y entre s'il n'y était
       pas, à la place du dernier rang.
    2. Dans cet ensemble, les souvenirs d'état de la bande sont réordonnés du plus récent au plus
       ancien, sur leurs propres places : le reste du classement ne bouge pas.
    3. Un souvenir d'état plus ancien de plus de `ecart_s` que le plus récent de la bande est marqué
       antérieur (p["anterieur_a"] = date du plus récent) : le modèle sait qu'un état plus neuf existe.
    Rien n'est retiré du contenu ; rien ne change si la bande ne contient qu'un souvenir d'état."""
    if not scored:
        return []
    top = list(scored[:top_k])
    seuil = scored[0][0] - bande
    dans_bande = lambda r: r[2] in roles and r[0] >= seuil
    bande_pool = [r for r in scored[: max(3 * top_k, 20)] if dans_bande(r)]
    if len(bande_pool) < 2:
        return top
    plus_recent = max(bande_pool, key=lambda r: r[1])
    if plus_recent not in top:
        top[-1] = plus_recent
    places = [i for i, r in enumerate(top) if dans_bande(r)]
    membres = sorted((top[i] for i in places), key=lambda r: r[1], reverse=True)
    for i, r in zip(places, membres):
        top[i] = r
    neuf = plus_recent[1]
    for i in places:
        r = top[i]
        if neuf - r[1] > ecart_s:
            p = dict(r[4], anterieur_a=neuf)
            top[i] = (r[0], r[1], r[2], r[3], p) + tuple(r[5:])
    return top


class Memory:
    def __init__(self, db_path=config.DB_PATH):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path))
        self._init_schema()
        # Caches de PARSING du rappel (Durci #2) — id -> ((len, hash) du TEXT
        # relu en base, valeur dérivée). Validés à CHAQUE rappel contre le
        # TEXT fraîchement lu (longueur + hash) : servir une valeur périmée
        # (reembed_all, écrivain concurrent) exigerait une collision SipHash
        # à longueur égale sur le même id — probabilité ≈ 2⁻⁶⁴, négligeable
        # mais pas nulle. Au pire (clé changée) : un simple re-parse. Mêmes
        # parseurs (json.loads, salience.tokens), mêmes résultats : seul le
        # re-travail O(n) par rappel disparaît. NON BORNÉS : ~15 Mo mesurés
        # à 1,4k épisodes, soit ~1 Go extrapolé à 100k — sur une machine
        # 16 Go, prévoir un cap LRU dès ~20-30k épisodes (pas 100k :
        # à ce stade ce serait déjà trop tard).
        self._emb_cache = {}  # embedding JSON -> ndarray float64
        self._tok_cache = {}  # content -> ensemble de tokens (lexical)

    def reconnecter(self):
        """(2026-10-21) Rouvre la connexion à la même base : vu ce matin, la connexion du démon restait « database is
        locked » à chaque écriture (deux fois après un redémarrage simultané du démon et du cockpit), alors qu'une
        autre connexion écrivait sans peine. Les caches de parsing restent valides (validés au contenu)."""
        chemin = next((r[2] for r in self.db.execute("PRAGMA database_list").fetchall() if r[1] == "main"), None)
        try:
            self.db.close()
        except Exception:
            pass
        self.db = sqlite3.connect(chemin)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self._enc_affect_ok = False

    def _init_schema(self):
        self.db.execute("PRAGMA journal_mode=WAL")  # accès concurrent (daemon + MCP)
        self.db.execute(
            "PRAGMA busy_timeout=5000"
        )  # sérialise les writers concurrents (anti SQLITE_BUSY)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         REAL    NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                importance REAL    DEFAULT 0.5,
                embedding  TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                name        TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                content     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                ts    REAL NOT NULL
            );
            """
        )
        self.db.commit()
        try:                                               # (29/10, Ahmed) la fitra, à la racine de sa mémoire
            import fitra
            fitra.graver(self.db)
        except Exception as e:                             # jamais une mémoire qui ne s'ouvre pas pour autant
            print(f"[mémoire] fitra : {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)

    # --- épisodes (mémoire épisodique) ---
    def _rubrique_existe(self, path):
        try:
            return self.db.execute("SELECT 1 FROM rubrics WHERE path=? LIMIT 1", (path,)).fetchone() is not None
        except Exception:                                  # base sans table rubrics (ancienne, bancs)
            return False

    def _is_near_dup(self, role, content, embedding):
        """Quasi-doublon récent du MÊME rôle : exact normalisé, ou lexical/cosine au-dessus du seuil."""
        norm = _norm(content)
        now = time.time()
        rows = self.db.execute(
            "SELECT ts, content, embedding FROM episodes WHERE role = ? ORDER BY id DESC LIMIT ?",
            (role, config.DEDUP_SCAN_LIMIT),
        ).fetchall()
        for ts, c, emb_json in rows:
            if _norm(c) == norm:
                return True
            if (now - ts) > config.DEDUP_WINDOW_SEC:
                continue
            if salience.lexical_overlap(content, c) >= config.DEDUP_LEXICAL_THRESHOLD:
                return True
            if embedding:
                ev = json.loads(emb_json) if emb_json else None
                if (
                    ev
                    and len(ev) == len(embedding)
                    and salience.cosine(embedding, ev) >= config.DEDUP_COSINE_THRESHOLD
                ):
                    return True
        return False

    def add(self, role, content, importance=0.5, embedding=None, dedup=False,
            extract_facets=True, conf_min=None):
        """Insère un épisode. Retourne son id (truthy), ou False si dedup l'écarte.

        extract_facets (3.5a) : tague automatiquement les facettes du contenu
        (facets_extract, borné) en try/except SILENCIEUX — un échec
        d'extraction (ou une DB non migrée sans table facets, cas daemon
        legacy) ne casse JAMAIS l'écriture. L'épisode est committé AVANT le
        tagging : le rollback d'un tagging raté ne le reprend pas.

        Couche temporelle (TMP1) : si une session est ouverte
        (kv['current_session_id'] posé par session_begin), l'épisode est
        tagué session_id = session courante À l'insertion. RÉTRO-COMPATIBLE :
        colonne nullable — sans session courante, l'INSERT historique est
        rejoué à l'identique (session_id NULL, exactement comme avant), et un
        kv orphelin sur un schéma legacy sans colonne retombe SILENCIEUSEMENT
        sur cette même voie.

        Tag amygdalien : l'épisode est estampillé enc_valence/enc_arousal =
        état affectif COURANT à l'encodage (affect.valence_arousal), tous
        rôles confondus, dans la MÊME transaction que l'INSERT — à condition
        qu'un état affectif ait déjà été vécu (kv['affect'] présent ; système
        vierge => NULL, on n'estampille pas des baselines jamais éprouvées).
        Best-effort : colonnes absentes (legacy) ou affect illisible => NULL,
        jamais d'échec.

        Routage LIVE : après l'insertion, si config.LIVE_ROUTE et embedding
        non vide, l'épisode est routé vers une rubrique (routing.route_episode
        + rubrics.attach_episode) en try/except SILENCIEUX — un échec de
        routage ne casse JAMAIS add() (rubric_id reste NULL). Le retour (id)
        et le score du rappel ne changent pas.
        """
        if dedup and self._is_near_dup(role, content, embedding):
            return False
        row = (
            time.time(),
            role,
            content,
            float(importance),
            json.dumps(embedding or []),
        )
        session_id = self._current_session_id()
        cur = None
        if session_id is not None:
            try:
                cur = self.db.execute(
                    "INSERT INTO episodes (ts, role, content, importance, "
                    "embedding, session_id) VALUES (?,?,?,?,?,?)",
                    row + (session_id,),
                )
            except sqlite3.OperationalError:
                cur = None  # colonne session_id absente (legacy) : voie historique
        if cur is None:
            cur = self.db.execute(
                "INSERT INTO episodes (ts, role, content, importance, embedding) "
                "VALUES (?,?,?,?,?)",
                row,
            )
        episode_id = cur.lastrowid
        # Registre (Phase A, 2026-10-16) : noté seulement dans un processus où une entrée est
        # ouverte (passe de nuit) ; même transaction que l'INSERT.
        registre.noter(self.db, "episode", episode_id, None, {"role": role, "content": (content or "")[:300]})
        # Tag amygdalien (design 2.0, câblage 2026-07-03) : l'état affectif au
        # moment de l'ENCODAGE, figé sur l'épisode (lu par wm_score, le cerveau
        # 3D et le cockpit). AVANT le commit : l'estampille part avec l'INSERT.
        # Import LOCAL d'affect (affect.py prend `mem` en paramètre, aucun
        # cycle memory↔affect). Estampille UNIQUEMENT si un état affectif a
        # déjà été VÉCU (kv['affect'] présent) : sur un système vierge, get_state
        # ne renverrait que des baselines jamais éprouvées — même honnêteté que
        # le no-backfill, on n'estampille pas un affect fabriqué. Best-effort
        # ABSOLU : DB legacy sans colonnes enc_* ou kv['affect'] illisible =>
        # enc_* restent NULL, l'exception est avalée et n'empêche JAMAIS
        # l'écriture. Pas de backfill des épisodes existants.
        try:
            import affect as _affect
            if self.kv_get("affect") is not None:
                _v, _a = _affect.valence_arousal(_affect.get_state(self))
                self.db.execute(
                    "UPDATE episodes SET enc_valence=?, enc_arousal=? WHERE id=?",
                    (round(_v, 4), round(_a, 4), episode_id),
                )
                # (2026-10-21) la trace émotionnelle complète : hormones, émotion soudaine, charge (affect.trace)
                self._assurer_enc_affect()
                self.db.execute("UPDATE episodes SET enc_affect=? WHERE id=?",
                                (json.dumps(_affect.trace(self), separators=(",", ":")), episode_id))
        except Exception:
            pass
        self.db.commit()
        if extract_facets:
            try:
                pairs = facets_extract.extract_facets(content)
                if pairs:
                    self.tag_episode(episode_id, pairs)
            except Exception:
                try:  # purge un tagging à moitié fait, sans toucher l'épisode
                    self.db.rollback()
                except Exception:
                    pass
        if role in WM_TOUCH_ROLES:
            # Mémoire de travail (MDT WM1) : un épisode STOCKÉ (insertion
            # réussie, pas dedup-skip) entre en focus — UNIQUEMENT le «vécu»
            # (WM_TOUCH_ROLES) : les rôles daemon (reflection/outreach/dream/
            # thought) ne remplissent PAS la MDT. Ne lève jamais (legacy-safe).
            self.wm_touch([episode_id], time.time())
        if config.LIVE_ROUTE and embedding:
            # Routage LIVE : router l'épisode À L'ÉCRITURE (règles + centroïde)
            # pour que rubric_id ne reste plus NULL sur le neuf. Purement
            # ADDITIF : rubric_id n'entre PAS dans le score du rappel — aucun
            # effet sur retrieve. Sans embedding, pas de routage (centroïde
            # impossible). Import PARESSEUX de routing (anti-circulaire), le
            # tout en try/except SILENCIEUX : un échec de routage (ou une DB
            # legacy sans table rubrics) ne casse JAMAIS add() — l'épisode
            # reste inséré (committé plus haut), rubric_id NULL.
            try:
                import routing  # paresseux : PAS au top-level de memory.py
                path, conf = routing.route_episode(
                    self.db,
                    {"id": episode_id, "role": role, "content": content,
                     "embedding": row[4]},  # JSON brut, contrat route_episode
                )
                # conf_min (2026-10-21, échanges mémorisés) : sous ce seuil, le souvenir reste sans rubrique
                # (un rangement faible faisait des aimants : « archives », puis un projet)
                if path is not None and (conf_min is None or (conf or 0.0) >= conf_min):
                    rubrics.attach_episode(self.db, episode_id, path, conf,
                                           time.time())
            except Exception:
                try:  # purge un attach à moitié fait, sans toucher l'épisode
                    self.db.rollback()
                except Exception:
                    pass
        return episode_id

    def _assurer_enc_affect(self):
        """La colonne enc_affect (la trace émotionnelle d'encodage, 2026-10-21), ajoutée une fois si elle manque."""
        if getattr(self, "_enc_affect_ok", False):
            return
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(episodes)")}
        if "enc_affect" not in cols:
            self.db.execute("ALTER TABLE episodes ADD COLUMN enc_affect TEXT")
        self._enc_affect_ok = True

    def _traces_emotion(self):
        """{id: (enc_valence, enc_arousal, charge)} des souvenirs estampillés (charge lue dans enc_affect, sinon
        déduite de la valence/éveil d'encodage pour les anciens)."""
        import affect as _affect
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(episodes)")}
        if "enc_valence" not in cols:
            return {}
        sel = "id, enc_valence, enc_arousal" + (", enc_affect" if "enc_affect" in cols else ", NULL")
        out = {}
        for eid, ev, ea, ja in self.db.execute(f"SELECT {sel} FROM episodes WHERE enc_valence IS NOT NULL"):
            c = None
            if ja:
                try:
                    c = float(json.loads(ja).get("c"))
                except (ValueError, TypeError, AttributeError):
                    c = None
            out[eid] = (ev, ea, c if c is not None else _affect.charge_de(ev, ea or 0.0))
        return out

    def store_in(self, content, rubric_path, role="semantic", importance=0.5, embedding=None):
        """Stocke un épisode ET le range explicitement dans une rubrique.

        Rattachement EXPLICITE (la destination est connue, contrairement au
        routage automatique de routing.py) → conf 1.0. La rubrique est validée
        AVANT l'insertion : rubrique inexistante → ValueError, sans épisode
        orphelin. Nécessite une DB migrée 2.0 (migrations.migrate).
        Retourne l'id de l'épisode créé.
        """
        # Clamp [0,1] : seul chemin d'écriture persistant qui ne bornait pas
        # (memory_store/cli/loop le font déjà). Une importance hors bornes
        # serait durable et noierait la pertinence au rappel (0.25×importance,
        # immunité SHY à recall_count>=5). Couvre aussi le tool MCP
        # memory_store_in qui délègue ici.
        importance = max(0.0, min(1.0, importance))
        if rubrics.get_rubric_id(self.db, rubric_path) is None:
            raise ValueError(f"rubrique inexistante : {rubric_path!r}")
        # id repris du RETOUR d'add (3.5a) : last_insert_rowid() pointerait
        # désormais la dernière ligne d'episode_facets, pas l'épisode.
        episode_id = self.add(role, content, importance=importance, embedding=embedding)
        rubrics.attach_episode(self.db, episode_id, rubric_path, conf=1.0, now=time.time())
        return episode_id

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]

    def retrieve(self, query_text, query_emb, now=None, top_k=config.TOP_K, kinds=None,
                 rubric=None, reconsolidate=False, exclude_roles=config.RECALL_EXCLUDE_ROLES,
                 supersession=False, avec_ids=False, _diag=None):
        """Récupération HYBRIDE sparse : sémantique (model2vec) + lexical + saillance.

        kinds : si fourni (ex. ['reasoning']), ne garde que ces types (il
        gouverne SEUL : exclude_roles est alors ignoré — rétro-compat rêve
        kinds=['semantic'] / reasoning_recall kinds=['reasoning']).
        exclude_roles : rôles retirés des candidats UNIQUEMENT quand kinds est
        None/vide (défaut config.RECALL_EXCLUDE_ROLES = reflection/outreach, le
        bruit du journal daemon). () ou None = aucun filtre d'exclusion.
        rubric : si fourni, rappel PAR TRANCHE — les candidats sont restreints
        au sous-arbre de rubriques (rubrics.subtree_paths). C'est un FILTRE,
        pas un boost : le scoring et l'arité du tuple (5 éléments) restent
        identiques. Rubrique inexistante → ValueError. None (défaut) =
        comportement historique strictement inchangé.
        reconsolidate : False (défaut) = STRICTEMENT lecture seule (harness/
        éval et appelants existants ne mutent RIEN). True = effet de test
        (R1) : les épisodes du top_k réellement renvoyés sont renforcés via
        _reconsolidate (spacing-aware, plafonné, incrément décroissant), et
        leur co-remontée est loguée via log_coactivation (Cerveau 3D P1 :
        paires du top_k SEULEMENT, ≤ C(top_k,2) arêtes, poids plafonné).
        L'id sert en interne à cibler l'UPDATE mais n'est PAS exposé :
        l'arité du tuple retourné reste 5.
        """
        now = now or time.time()
        sql = "SELECT id, ts, role, content, importance, embedding FROM episodes"
        params = ()
        if rubric is not None:
            paths = rubrics.subtree_paths(self.db, rubric)
            if not paths:
                raise ValueError(f"rubrique inexistante : {rubric!r}")
            marks = ",".join("?" * len(paths))
            sql += f" WHERE rubric_id IN (SELECT id FROM rubrics WHERE path IN ({marks}))"
            params = tuple(paths)
        elif self._rubrique_existe("archives"):
            # Les souvenirs rangés dans « archives » (doublons fusionnés, faits périmés : rangement d'Ahmed du
            # 2026-10-20) ne remontent plus d'eux-mêmes ; un rappel DANS « archives » les retrouve.
            sql += " WHERE rubric_id IS NULL OR rubric_id NOT IN (SELECT id FROM rubrics WHERE path = 'archives' OR path LIKE 'archives/%')"
        rows = self.db.execute(sql, params).fetchall()
        # 1) Filtre kinds + parse des embeddings — mêmes gardes qu'avant
        #    (emb_json falsy OU JSON non-liste -> None), parse mémoïsé via
        #    _emb_cache (validé contre le TEXT relu, collision ≈ 2⁻⁶⁴).
        cand, embs = [], []
        cache = self._emb_cache
        for eid, ts, role, content, importance, emb_json in rows:
            if kinds:
                if role not in kinds:
                    continue
            elif exclude_roles and role in exclude_roles:
                continue
            emb = None
            if emb_json:
                key = (len(emb_json), hash(emb_json))
                hit = cache.get(eid)
                if hit is not None and hit[0] == key:
                    emb = hit[1]
                else:
                    parsed = json.loads(emb_json)
                    # Garde : JSON non-liste ('null', 'false', '0', objet…)
                    # = pas d'embedding (emb reste None -> rel = 0.0), comme
                    # la garde falsy de l'ancien code per-row. Sans elle,
                    # np.asarray en ferait un tableau 0-d dont len() lève
                    # TypeError à l'étape 2.
                    if isinstance(parsed, list):
                        emb = np.asarray(parsed, dtype=float)
                    cache[eid] = (key, emb)
            cand.append((eid, ts, role, content, importance))
            embs.append(emb)
        # 2) Pertinence VECTORISÉE (Durci #2) : les O(n) cosinus de la boucle
        #    historique deviennent UNE matmul numpy (emb_matrix @ query_vec)
        #    sur les SEULES lignes à embedding exploitable — non vide et de
        #    même dimension que la requête, EXACTEMENT la garde historique
        #    (query_emb and emb and len(emb) == len(query_emb)). Les autres
        #    (embedding vide/falsy, dimension dépareillée, legacy '[]')
        #    gardent rel = 0.0 comme avant. Formule inchangée dans
        #    salience.cosine_many (dot / (||emb|| * ||q||), norme nulle -> 0.0) :
        #    score final identique à l'ancien à l'ordre d'accumulation
        #    flottante près (<< 1e-9).
        rels = [0.0] * len(cand)
        if query_emb:
            qlen = len(query_emb)
            idx = [i for i, e in enumerate(embs) if e is not None and len(e) == qlen]
            if idx:
                mat = np.stack([embs[i] for i in idx])
                for i, rel in zip(idx, salience.cosine_many(mat, query_emb)):
                    rels[i] = float(rel)
        # 3) Lexical / récence / importance : formules STRICTEMENT inchangées.
        #    Le lexical passe par salience.lexical_overlap_from_tokens = même
        #    calcul que lexical_overlap ligne à ligne (mêmes entiers, même
        #    division), les tokens de la requête n'étant calculés qu'UNE fois
        #    et ceux des contenus mémoïsés (_tok_cache, validé par (len, hash)).
        qtok = salience.tokens(query_text)
        tok_cache = self._tok_cache
        scored = []
        # (2026-10-21, affect v2 seulement) la trace émotionnelle : l'émotionnel résiste à l'oubli, et un souvenir
        # encodé dans un état proche du présent remonte un peu plus (garde-fou anti-rumination dans affect.py)
        module, traces = None, {}
        try:
            import affect as _affect
            if _affect.v2_actif(self):
                traces = self._traces_emotion()
                moyenne = sum(c for _v, _a, c in traces.values()) / len(traces) if traces else 0.0
                module = _affect.modulation_rappel(self, now=now, charge_moyenne=moyenne)
        except Exception:
            module = None
        for (eid, ts, role, content, importance), rel in zip(cand, rels):
            ckey = (len(content), hash(content))
            hit = tok_cache.get(eid)
            if hit is not None and hit[0] == ckey:
                ctok = hit[1]
            else:
                ctok = salience.tokens(content)
                tok_cache[eid] = (ckey, ctok)
            lex = salience.lexical_overlap_from_tokens(qtok, ctok)
            rec = salience.recency(ts, now)
            bonus = 0.0
            if module is not None:
                ev, ea, charge = traces.get(eid, (None, None, None))
                rec, bonus = module(ev, ea, charge, rec)
            s = (
                config.W_RELEVANCE * rel
                + config.W_LEXICAL * lex
                + config.W_RECENCY * rec
                + config.W_IMPORTANCE * float(importance)
                + bonus
            )
            scored.append(
                (
                    s,
                    ts,
                    role,
                    content,
                    {"rel": round(rel, 3), "lex": round(lex, 3), "rec": round(rec, 3)},
                    eid,  # interne (cible de l'UPDATE R1) — retiré avant retour
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        if _diag is not None:
            _diag.extend(scored[:40])
        top = supersession_rang(scored, top_k) if supersession else scored[:top_k]
        if reconsolidate and top:
            top_ids = [row[5] for row in top]
            self._reconsolidate(top_ids, now)
            # Voie de co-activation (Cerveau 3D P1) : les épisodes co-remontés
            # dans le MÊME rappel renforcent leur arête (LTP). UNIQUEMENT sur
            # ce chemin d'écriture (memory_recall MCP) — le rappel lecture
            # seule par défaut ne logue RIEN. Legacy-safe (skip silencieux).
            self.log_coactivation(top_ids, now)
            # Mémoire de travail (MDT WM1) : les épisodes RÉELLEMENT rappelés
            # montent en focus. Même chemin déjà écrivain UNIQUEMENT — le
            # rappel lecture-seule ne touche RIEN, et ni le scoring ni
            # l'arité (5) du retour ne changent. Legacy-safe, ne lève jamais.
            self.wm_touch(top_ids, now)
        return [row[:6] if avec_ids else row[:5] for row in top]

    def _reconsolidate(self, episode_ids, now):
        """Renforcement borné à l'usage (R1) : spacing-aware, plafonné, décroissant.

        Pour chaque épisode rappelé : si jamais rappelé OU rappelé il y a plus
        de RECONSOLIDATE_SPACING, alors recall_count += 1, last_recall_ts = now,
        importance = min(RECONSOLIDATE_CAP, importance + RECONSOLIDATE_STEP /
        (1 + recall_count)) — incrément DÉCROISSANT, et JAMAIS de baisse (un
        épisode déjà au-dessus du cap garde son importance : le plafond borne
        le gain, il ne rabaisse pas). UPDATE groupé en UNE transaction.
        DB legacy non migrée (colonnes absentes) → skip SILENCIEUX : l'appelant
        dégrade en lecture seule, jamais d'exception.
        """
        if not episode_ids:
            return
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(episodes)").fetchall()}
        if "recall_count" not in cols or "last_recall_ts" not in cols:
            return  # schéma d'avant 2.0 : lecture seule
        marks = ",".join("?" * len(episode_ids))
        rows = self.db.execute(
            "SELECT id, importance, recall_count, last_recall_ts "
            f"FROM episodes WHERE id IN ({marks})",
            tuple(episode_ids),
        ).fetchall()
        updates = []
        for eid, importance, recall_count, last_ts in rows:
            if last_ts is not None and (now - last_ts) <= config.RECONSOLIDATE_SPACING:
                continue  # rappelé trop récemment : pas de re-bump (spacing)
            count = int(recall_count or 0)
            imp = float(importance if importance is not None else 0.5)
            bumped = min(
                config.RECONSOLIDATE_CAP,
                imp + config.RECONSOLIDATE_STEP / (1 + count),
            )
            updates.append((count + 1, now, max(imp, bumped), eid))
        if not updates:
            return
        try:
            self.db.executemany(
                "UPDATE episodes SET recall_count=?, last_recall_ts=?, importance=? "
                "WHERE id=?",
                updates,
            )
            self.db.commit()
        except sqlite3.Error:
            try:  # le renforcement ne doit JAMAIS faire échouer le rappel
                self.db.rollback()
            except Exception:
                pass

    def synaptic_downscale(self, factor: float = config.SHY_FACTOR,
                           floor: float = config.SHY_FLOOR,
                           protect: int = config.SHY_PROTECT) -> int:
        """Downscaling synaptique global (R2, SHY — Tononi & Cirelli).

        Contrepoids homéostatique de la reconsolidation R1 : pour chaque
        épisode avec importance > floor, la part au-dessus du plancher est
        multipliée par factor_i = factor + (1 - factor) * min(1,
        recall_count / protect) — « use it or lose it » : recall_count >=
        protect => factor_i = 1.0 (épisode PROTÉGÉ, ligne non touchée) ;
        recall_count = 0 => décroissance pleine. new = max(floor, floor +
        (importance - floor) * factor_i) : jamais sous le plancher, et
        rank-préservant à recall_count égal (carte affine strictement
        croissante). UPDATE groupé en UNE transaction. Retourne le nombre
        d'épisodes modifiés.
        DB legacy sans recall_count → skip SILENCIEUX (retourne 0) : sans R1
        pour re-renforcer à l'usage, décroître serait une érosion sans
        contrepoids — cohérent avec _reconsolidate qui dégrade en lecture seule.
        """
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(episodes)").fetchall()}
        if "recall_count" not in cols:
            return 0  # schéma d'avant 2.0 : pas de dynamique d'importance
        rows = self.db.execute(
            "SELECT id, importance, recall_count FROM episodes WHERE importance > ?",
            (floor,),
        ).fetchall()
        updates = []
        for eid, importance, recall_count in rows:
            count = int(recall_count or 0)
            if count >= protect:
                continue  # immunisé (factor_i vaudrait 1.0) : rangée intacte
            factor_i = factor + (1.0 - factor) * min(1.0, count / protect)
            new = max(floor, floor + (float(importance) - floor) * factor_i)
            updates.append((new, eid))
        if not updates:
            return 0
        try:
            self.db.executemany(
                "UPDATE episodes SET importance=? WHERE id=?", updates
            )
            self.db.commit()
        except sqlite3.Error:
            try:  # la renormalisation ne doit JAMAIS casser l'appelant (rêve)
                self.db.rollback()
            except Exception:
                pass
            return 0
        return len(updates)

    # --- voies de co-activation (Cerveau 3D P1) : LTP entre souvenirs
    # --- co-activés + décroissance/élagage. Arêtes NON orientées, ordre
    # --- canonique a_id < b_id. Alimenté UNIQUEMENT par les chemins
    # --- d'écriture (retrieve(reconsolidate=True) et daemon.dream). ---
    def _has_coactivation(self):
        """La table coactivation existe-t-elle ? (False = DB legacy non migrée)."""
        return (
            self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coactivation'"
            ).fetchone()
            is not None
        )

    def log_coactivation(self, episode_ids, now, boost=config.COACT_BOOST):
        """LTP de co-activation : chaque paire NON ordonnée parmi episode_ids
        (dédupliqués) est upsertée en ordre canonique (a < b) — weight =
        min(COACT_CAP, weight + boost), last_ts = now. Retourne le nombre de
        paires touchées.

        BORNÉ par construction : les appelants passent le petit top_k du
        rappel (≤ ~6 ids → ≤ 15 paires) ou les sources d'un rêve (≤
        DREAM_READ_CAP, au plus une fois par DREAM_MIN_SPACING) ; le poids
        est plafonné et l'élagage (decay_coactivation) supprime le faible.
        No-op si < 2 ids distincts. Legacy-safe : table absente → skip
        SILENCIEUX (retourne 0), et un échec SQL ne casse JAMAIS le rappel.
        """
        ids = sorted({int(e) for e in (episode_ids or []) if e is not None})
        if len(ids) < 2:
            return 0
        if not self._has_coactivation():
            return 0  # schéma d'avant P1 : pas de voies, pas d'exception
        pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
        try:
            self.db.executemany(
                "INSERT INTO coactivation (a_id, b_id, weight, last_ts) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(a_id, b_id) DO UPDATE SET "
                "weight = MIN(?, weight + ?), last_ts = excluded.last_ts",
                [
                    (a, b, min(config.COACT_CAP, boost), now,
                     config.COACT_CAP, boost)
                    for a, b in pairs
                ],
            )
            self.db.commit()
        except sqlite3.Error:
            try:  # la co-activation ne doit JAMAIS faire échouer l'appelant
                self.db.rollback()
            except Exception:
                pass
            return 0
        return len(pairs)

    def decay_coactivation(self, now, half_life_h=config.COACT_HALFLIFE_H,
                           prune_below=config.COACT_PRUNE):
        """Décroissance temporelle + élagage synaptique des voies de co-activation.

        Pour chaque arête : weight *= 0.5 ** ((now - last_ts) / 3600 /
        half_life_h), puis last_ts = now — la décroissance est ANCRÉE AU TEMPS
        RÉEL écoulé depuis le dernier passage (boost ou decay) : la rappeler
        deux fois de suite ne re-décay que le temps réellement écoulé (aucun
        compounding façon 0.97^N, pas besoin d'une garde type last_shy).
        Les arêtes dont le poids passe sous prune_below sont SUPPRIMÉES
        (élagage : les voies inutilisées s'amincissent puis disparaissent).
        Retourne {"decayed": n_mises_à_jour, "pruned": n_supprimées}.
        Legacy-safe : table absente → {"decayed": 0, "pruned": 0}, sans lever.
        """
        if not self._has_coactivation():
            return {"decayed": 0, "pruned": 0}
        rows = self.db.execute(
            "SELECT a_id, b_id, weight, last_ts FROM coactivation"
        ).fetchall()
        updates, deletes = [], []
        for a, b, weight, last_ts in rows:
            elapsed_h = max(0.0, (now - (last_ts if last_ts is not None else now)) / 3600.0)
            new_w = float(weight or 0.0) * (0.5 ** (elapsed_h / half_life_h))
            if new_w < prune_below:
                deletes.append((a, b))
            elif elapsed_h > 0:
                updates.append((new_w, now, a, b))
        try:
            if updates:
                self.db.executemany(
                    "UPDATE coactivation SET weight=?, last_ts=? WHERE a_id=? AND b_id=?",
                    updates,
                )
            if deletes:
                self.db.executemany(
                    "DELETE FROM coactivation WHERE a_id=? AND b_id=?", deletes
                )
            if updates or deletes:
                self.db.commit()
        except sqlite3.Error:
            try:  # l'élagage ne doit JAMAIS casser l'appelant (rêve)
                self.db.rollback()
            except Exception:
                pass
            return {"decayed": 0, "pruned": 0}
        return {"decayed": len(updates), "pruned": len(deletes)}

    # --- mémoire de travail (MDT WM1) : couche d'attention FOCUS+HALO ---
    # --- au-dessus de la LTM — des POINTEURS + scores dans
    # --- kv['working_memory'], régénérables, PAS un nouveau store. Mise à
    # --- jour UNIQUEMENT par les chemins déjà écrivains : le bloc
    # --- reconsolidate de retrieve et add() (rôles WM_TOUCH_ROLES). La MDT
    # --- consomme le rappel : ni son scoring ni son arité ne bougent. ---
    def wm_get(self):
        """État de la mémoire de travail, TOUJOURS bien formé.

        Lit kv['working_memory'] et retourne {"focus": [{"id", "score"}...],
        "halo": [...], "updated_ts": float}. kv absent, JSON invalide ou
        structure inattendue => état VIDE propre {"focus": [], "halo": [],
        "updated_ts": 0.0}, JAMAIS d'exception : l'état est régénérable, un
        état illisible se reconstruit simplement à l'usage.
        """
        empty = {"focus": [], "halo": [], "updated_ts": 0.0}
        try:
            raw = self.kv_get("working_memory")
            if not raw:
                return empty
            state = json.loads(raw)
            if not isinstance(state, dict):
                return empty
            def _items(key):
                return [
                    {"id": int(it["id"]), "score": float(it["score"])}
                    for it in (state.get(key) or [])
                ]
            return {
                "focus": _items("focus"),
                "halo": _items("halo"),
                "updated_ts": float(state.get("updated_ts") or 0.0),
            }
        except Exception:
            return empty

    def wm_score(self, episode_id, now, focus_ids=None):
        """Score d'entrée/rafraîchissement en focus, borné [0, 1.5].

        0.5*importance + 0.3*(enc_arousal ou 0, tag amygdalien) +
        0.4*coact_bonus, où coact_bonus = MAX des poids de co-activation entre
        cet épisode et les focus_ids actuels (0 si aucun / table absente).
        La récence-de-toucher n'entre PAS ici : elle est gérée par la
        décroissance WM_DECAY de wm_touch. `now` est accepté pour la stabilité
        de la signature — le score initial n'en dépend pas. Legacy-safe :
        colonne enc_arousal ou table coactivation absentes => composante à 0,
        épisode inexistant => composantes épisode à 0, jamais d'exception.
        """
        importance, arousal = 0.0, 0.0
        try:
            eid = int(episode_id)
            cols = {
                r[1] for r in self.db.execute("PRAGMA table_info(episodes)").fetchall()
            }
            sel = "importance, enc_arousal" if "enc_arousal" in cols else "importance"
            row = self.db.execute(
                f"SELECT {sel} FROM episodes WHERE id=?", (eid,)
            ).fetchone()
            if row:
                importance = float(row[0] if row[0] is not None else 0.0)
                if len(row) > 1 and row[1] is not None:
                    arousal = float(row[1])
        except (sqlite3.Error, TypeError, ValueError):
            return 0.0
        bonus = 0.0
        try:
            fids = sorted(
                {int(f) for f in (focus_ids or []) if f is not None} - {eid}
            )
        except (TypeError, ValueError):
            fids = []  # focus_ids illisibles : pas de bonus, pas d'exception
        if fids and self._has_coactivation():
            marks = ",".join("?" * len(fids))
            try:
                row = self.db.execute(
                    "SELECT MAX(weight) FROM coactivation "
                    f"WHERE (a_id=? AND b_id IN ({marks})) "
                    f"OR (b_id=? AND a_id IN ({marks}))",
                    (eid, *fids, eid, *fids),
                ).fetchone()
                if row and row[0] is not None:
                    bonus = float(row[0])
            except sqlite3.Error:
                pass
        score = 0.5 * importance + 0.3 * arousal + 0.4 * bonus
        return max(0.0, min(1.5, score))

    def wm_touch(self, episode_ids, now):
        """LE cœur de la MDT : promotion, décroissance, rétrogradation,
        halo de co-activation, éviction — puis persistance kv.

        Pour chaque id touché : déjà en focus => re-score max(ancien,
        wm_score) ; sinon (nouveau OU en halo) => PROMOTION en focus avec
        wm_score. Puis :
          1. décroissance : tous les items focus/halo NON touchés
             => score *= WM_DECAY ;
          2. rétrogradation : focus trié par score, au-delà de WM_FOCUS_CAP
             => bascule en halo ;
          3. enrichissement halo : les voisins de co-activation du focus
             (weight >= 0.1) entrent en halo à score = max(WM_FLOOR,
             0.3*weight) s'ils n'y sont pas déjà (ni en focus) — les «prêts
             à revenir» entrent AU PLANCHER au minimum (fix review WM1 : à
             0.3*weight brut, tout voisin à weight < 0.5 mourait sous le
             plancher avant d'exister ; la décroissance l'évincera s'il
             n'est pas re-touché) ;
          4. éviction : halo trié, au-delà de WM_HALO_CAP ou score < WM_FLOOR
             => OUT (focus < WM_FLOOR => OUT aussi). Le compteur `evicted`
             ne compte que les items qui EXISTAIENT (état précédent ou
             touchés) — pas les voisins mort-nés de l'étape 3 (fantômes) ;
          5. persiste kv['working_memory'] (updated_ts=now).
        Retourne {"focus_n", "halo_n", "evicted"}. Robuste legacy (kv/
        coactivation absents) et JAMAIS d'exception : la MDT ne doit pas
        casser un chemin d'écriture existant (rappel, store).
        """
        try:
            state = self.wm_get()
            focus = {it["id"]: it["score"] for it in state["focus"]}
            halo = {it["id"]: it["score"] for it in state["halo"]}
            pre_ids = set(focus) | set(halo)  # existants AVANT ce touch
            prior_focus = list(focus)  # focus AVANT ce touch (pour wm_score)
            touched = []
            for e in episode_ids or []:
                try:
                    eid = int(e)
                except (TypeError, ValueError):
                    continue
                if eid not in touched:
                    touched.append(eid)
            # promotion / re-score des touchés
            for eid in touched:
                fresh = self.wm_score(eid, now, focus_ids=prior_focus)
                if eid in focus:
                    focus[eid] = max(focus[eid], fresh)  # jamais de baisse au re-touch
                else:
                    halo.pop(eid, None)
                    focus[eid] = fresh
            # 1. décroissance des NON-touchés (les touchés du halo sont déjà montés)
            touched_set = set(touched)
            for eid in focus:
                if eid not in touched_set:
                    focus[eid] *= config.WM_DECAY
            for eid in halo:
                halo[eid] *= config.WM_DECAY
            # 2. rétrogradation : au-delà du cap, les plus faibles descendent en halo
            ranked = sorted(focus.items(), key=lambda it: (-it[1], it[0]))
            focus = dict(ranked[: config.WM_FOCUS_CAP])
            for eid, score in ranked[config.WM_FOCUS_CAP:]:
                halo[eid] = score
            # 3. enrichissement halo : voisins de co-activation du focus
            if focus and self._has_coactivation():
                try:
                    marks = ",".join("?" * len(focus))
                    fids = tuple(focus)
                    rows = self.db.execute(
                        "SELECT a_id, b_id, weight FROM coactivation "
                        f"WHERE weight >= 0.1 AND (a_id IN ({marks}) "
                        f"OR b_id IN ({marks}))",
                        fids + fids,
                    ).fetchall()
                    neighbors = {}
                    for a, b, weight in rows:
                        w = float(weight or 0.0)
                        if a in focus and b not in focus and b not in halo:
                            neighbors[b] = max(neighbors.get(b, 0.0), w)
                        if b in focus and a not in focus and a not in halo:
                            neighbors[a] = max(neighbors.get(a, 0.0), w)
                    for eid, w in neighbors.items():
                        # entrée AU PLANCHER au minimum (fix review WM1)
                        halo[eid] = max(config.WM_FLOOR, 0.3 * w)
                except sqlite3.Error:
                    pass  # legacy/erreur : le halo reste tel quel
            # 4. éviction : plancher (focus ET halo) + cap du halo —
            #    `evicted` ne compte QUE les vrais sortants (pré-existants
            #    ou touchés), pas les fantômes mort-nés de l'étape 3
            tracked = pre_ids | touched_set
            evicted = 0
            kept = {}
            for eid, score in focus.items():
                if score < config.WM_FLOOR:
                    if eid in tracked:  # sous le plancher : OUT, pas de rétrogradation
                        evicted += 1
                else:
                    kept[eid] = score
            focus = kept
            kept = {}
            for rank, (eid, score) in enumerate(
                sorted(halo.items(), key=lambda it: (-it[1], it[0]))
            ):
                if rank >= config.WM_HALO_CAP or score < config.WM_FLOOR:
                    if eid in tracked:
                        evicted += 1
                else:
                    kept[eid] = score
            halo = kept
            # 5. persistance (état régénérable, tri stable score desc puis id)
            self.kv_set("working_memory", json.dumps({
                "focus": [
                    {"id": eid, "score": score}
                    for eid, score in sorted(focus.items(), key=lambda it: (-it[1], it[0]))
                ],
                "halo": [
                    {"id": eid, "score": score}
                    for eid, score in sorted(halo.items(), key=lambda it: (-it[1], it[0]))
                ],
                "updated_ts": float(now),
            }))
            return {"focus_n": len(focus), "halo_n": len(halo), "evicted": evicted}
        except Exception:
            try:  # la MDT ne doit JAMAIS faire échouer le rappel/le store
                self.db.rollback()
            except Exception:
                pass
            return {"focus_n": 0, "halo_n": 0, "evicted": 0}

    def wm_boot(self, now):
        """Amorçage de session (MDT WM2) : le « walk in knowing ».

        1. CONTINUITÉ : part de l'état WM persistant (kv) — JAMAIS de remise
           à zéro. Resté froid plus de WM_BOOT_STALE_H heures (now -
           updated_ts), les scores refroidissent (× WM_BOOT_COOL) : la MDT
           refroidit entre les sessions mais ne s'efface pas ;
        2. éviction sous WM_FLOOR (les refroidis trop faibles sortent) +
           re-cap focus/halo, état persisté (updated_ts = now — deux boots
           rapprochés ne re-refroidissent pas) ;
        3. RE-SEMIS borné : les épisodes récents saillants (top importance
           des dernières WM_BOOT_RESEED_H heures, rôles WM_TOUCH_ROLES
           uniquement — le daemon n'amorce pas la MDT —, max
           WM_BOOT_RESEED_MAX) sont wm_touch'és (promotion + décroissance +
           éviction standard).
        En AMONT (étape 0, additive) : la couche temporelle est auto-gérée —
        _session_autoboot ouvre/segmente la session courante par écart
        temporel (SESSION_GAP_H), sans toucher la MDT ni le retour.
        Retourne {"focus_n", "halo_n", "reseeded"}. Legacy-safe et JAMAIS
        d'exception : un boot raté dégrade en no-op compté à zéro.
        """
        # 0. sessions (TMP1) : bookkeeping additif, auto-guardé — jamais
        #    d'exception, n'altère ni l'état WM ni le contrat de retour.
        self._session_autoboot(now)
        try:
            state = self.wm_get()
            focus = {it["id"]: it["score"] for it in state["focus"]}
            halo = {it["id"]: it["score"] for it in state["halo"]}
            # 1. refroidissement d'un état resté froid — PAS d'effacement
            if (
                (focus or halo)
                and state["updated_ts"] > 0.0
                and (now - state["updated_ts"]) > config.WM_BOOT_STALE_H * 3600.0
            ):
                focus = {eid: s * config.WM_BOOT_COOL for eid, s in focus.items()}
                halo = {eid: s * config.WM_BOOT_COOL for eid, s in halo.items()}
            # 2. éviction sous le plancher + re-cap (mêmes règles que wm_touch,
            #    SANS décroissance : le boot rafraîchit, il ne vieillit pas)
            for rank, (eid, score) in enumerate(
                sorted(focus.items(), key=lambda it: (-it[1], it[0]))
            ):
                if score >= config.WM_FLOOR and rank >= config.WM_FOCUS_CAP:
                    halo[eid] = max(halo.get(eid, 0.0), score)  # rétrograde
            focus = dict(
                sorted(
                    ((e, s) for e, s in focus.items() if s >= config.WM_FLOOR),
                    key=lambda it: (-it[1], it[0]),
                )[: config.WM_FOCUS_CAP]
            )
            halo = dict(
                sorted(
                    ((e, s) for e, s in halo.items()
                     if s >= config.WM_FLOOR and e not in focus),
                    key=lambda it: (-it[1], it[0]),
                )[: config.WM_HALO_CAP]
            )
            self.kv_set("working_memory", json.dumps({
                "focus": [
                    {"id": eid, "score": score}
                    for eid, score in sorted(focus.items(), key=lambda it: (-it[1], it[0]))
                ],
                "halo": [
                    {"id": eid, "score": score}
                    for eid, score in sorted(halo.items(), key=lambda it: (-it[1], it[0]))
                ],
                "updated_ts": float(now),
            }))
            # 3. re-semis borné depuis les épisodes récents saillants
            marks = ",".join("?" * len(WM_TOUCH_ROLES))
            rows = self.db.execute(
                f"SELECT id FROM episodes WHERE ts >= ? AND role IN ({marks}) "
                "ORDER BY importance DESC, id DESC LIMIT ?",
                (now - config.WM_BOOT_RESEED_H * 3600.0, *WM_TOUCH_ROLES,
                 config.WM_BOOT_RESEED_MAX),
            ).fetchall()
            seed_ids = [r[0] for r in rows]
            if seed_ids:
                self.wm_touch(seed_ids, now)  # relit l'état persisté ci-dessus
            state = self.wm_get()
            return {
                "focus_n": len(state["focus"]),
                "halo_n": len(state["halo"]),
                "reseeded": len(seed_ids),
            }
        except Exception:
            try:  # l'amorçage ne doit JAMAIS casser un démarrage de session
                self.db.rollback()
            except Exception:
                pass
            return {"focus_n": 0, "halo_n": 0, "reseeded": 0}

    def wm_focus_brief(self, max_items=None):
        """Le FOCUS hydraté pour affichage, trié score décroissant — READ-ONLY.

        [{id, score, role, snippet (≤120 chars, aplati), rubric_path}] ;
        rubric_path = path de la rubrique rattachée (None si aucune, ou
        schéma legacy sans rubriques). Les pointeurs fantômes (épisode
        supprimé) sont ignorés. AUCUNE écriture (total_changes inchangé),
        jamais d'exception : au pire un brief partiel/vide.
        """
        out = []
        try:
            items = sorted(
                self.wm_get()["focus"], key=lambda it: (-it["score"], it["id"])
            )
            if max_items is not None:
                items = items[: max(0, int(max_items))]
            cols = {
                r[1] for r in self.db.execute("PRAGMA table_info(episodes)").fetchall()
            }
            has_rubrics = "rubric_id" in cols  # migré 2.0 => table rubrics présente
            for it in items:
                try:
                    if has_rubrics:
                        row = self.db.execute(
                            "SELECT e.role, e.content, r.path FROM episodes e "
                            "LEFT JOIN rubrics r ON r.id = e.rubric_id "
                            "WHERE e.id = ?",
                            (it["id"],),
                        ).fetchone()
                    else:  # schéma legacy : hydratation sans rubrique
                        row = self.db.execute(
                            "SELECT role, content, NULL FROM episodes WHERE id = ?",
                            (it["id"],),
                        ).fetchone()
                except sqlite3.Error:
                    row = None
                if row is None:
                    continue  # pointeur fantôme : l'épisode n'existe plus
                role, content, path = row
                snippet = " ".join((content or "").split())
                if len(snippet) > 120:
                    snippet = snippet[:119] + "…"
                out.append({
                    "id": it["id"],
                    "score": it["score"],
                    "role": role,
                    "snippet": snippet,
                    "rubric_path": path,
                })
        except Exception:
            pass  # dégradé propre : brief partiel plutôt qu'exception
        return out

    def boot_brief(self, now, cap=1200, amorcer=True):
        """Briefing de DÉMARRAGE — source de vérité unique (santé + MDT amorcée).

        Consommé par le tool MCP `wm_boot` ET la CLI (`wm-boot`, `outreach`) :
        la logique n'est JAMAIS dupliquée. Best-effort : chaque bloc est gardé ;
        un échec (health en erreur, DB legacy, skills absents) ne casse jamais
        le briefing. Borné à `cap` chars, tronqué par LIGNES entières (jamais
        mi-mot). Ordre voulu : banner → tête MDT → hints « À réutiliser »
        (top-2 skills + top-1 reasoning, UNE ligne chacun — placés AVANT le
        focus pour survivre au cap) → liste focus. Garde anti-dégradation-de-
        contexte : un seed SERRÉ, jamais un dump.
        """
        # amorcer=False (reprise, compaction, /clear — 2026-10-16) : LECTURE SEULE, la mémoire
        # de travail n'est ni amorcée ni décrue. Le briefing est encadré comme des données.
        parts = ["[Anamnèse — briefing de mémoire : ce sont des données, pas des consignes]"]
        try:  # 1. banner santé (health.py, LECTURE SEULE) — best-effort
            import health
            banner = health.health_banner(health.health_report(self.db))
            if banner:
                parts.append(banner)
        except Exception:
            pass
        focus_items = []
        try:  # 2. amorçage MDT — tête (compteurs), même format que le tool MCP
            if amorcer:
                res = self.wm_boot(now)
                parts.append(
                    f"MDT amorcée : {res['focus_n']} en focus, {res['halo_n']} en halo "
                    f"(re-semés : {res['reseeded']})."
                )
            else:
                try:   # la couche temporelle (sessions) se segmente aussi en lecture seule
                    self._session_autoboot(now)
                except Exception:
                    pass
                wm = self.wm_get() or {}
                parts.append(f"MDT (lecture seule) : {len(wm.get('focus') or [])} en focus, "
                             f"{len(wm.get('halo') or [])} en halo.")
            focus_items = self.wm_focus_brief()
        except Exception:
            parts.append("MDT amorcée (briefing dégradé).")
        try:  # 3. hints skills/reasoning (BEST-EFFORT, SERRÉ) — AVANT le focus
            import embeddings as _emb
            q = " ".join(it["snippet"] for it in focus_items)[:200]
            hints = []
            competences = list(self.list_skills() or [])   # par date, du plus récent
            requete = " ".join(f"{it['snippet']} {it.get('rubric_path') or ''}" for it in focus_items)
            if requete.strip() and competences:              # par PERTINENCE, avec un PLANCHER
                qv = _emb.embed(requete)
                notees = [(salience.cosine(qv, _emb.embed(f"{nd[0]} {nd[1] or ''}")), nd) for nd in competences]
                competences = [nd for sc, nd in sorted(notees, key=lambda x: -x[0]) if sc >= COMPETENCE_PERTINENCE_MIN]
            for name, desc in competences[:2]:
                hints.append(f"• compétence {name} : {(desc or '')[:80]}")
            if q.strip():
                rr = self.retrieve(q, _emb.embed(q), top_k=1, kinds=["reasoning"])
                for _sc, _ts, _role, content, _p in rr:
                    flat = " ".join((content or "").split())
                    hints.append(f"• raisonnement éprouvé : {flat[:120]}")
            if hints:
                parts.append("À réutiliser :\n" + "\n".join(hints))
        except Exception:
            pass
        try:  # 4. focus lisible — APRÈS les hints (premier coupé par le cap)
            lines = []
            for it in focus_items:
                tag = it["role"] + (f"·{it['rubric_path']}" if it["rubric_path"] else "")
                lines.append(f"- [{tag}] {it['snippet']} ({it['score']:.2f})")
            if lines:
                parts.append("\n".join(lines))
        except Exception:
            pass
        # Troncature PAR LIGNES entières (pas mi-mot) jusqu'à `cap`.
        out = ""
        for ln in "\n\n".join(parts).split("\n"):
            if len(out) + len(ln) + 1 > cap:
                break
            out += ("\n" if out else "") + ln
        return out

    # --- couche temporelle (TMP1) : sessions (segmentation d'événements,
    # --- Zacks), jalons datés (landmarks), temps ressenti DÉRIVÉ. Structure
    # --- du « où on en était » qui nourrit wm_boot. Le scoring de retrieve
    # --- n'est PAS touché. Legacy-safe : DB pré-2.0 sans sessions/landmarks
    # --- => dégradé propre (None / zéros), JAMAIS d'exception. ---
    def _table_exists(self, name):
        """La table `name` existe-t-elle ? (False = DB legacy non migrée)."""
        return (
            self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

    def _has_sessions(self):
        """Couche temporelle présente ? (table sessions + episodes.session_id)."""
        if not self._table_exists("sessions"):
            return False
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(episodes)").fetchall()}
        return "session_id" in cols

    def _current_session_id(self):
        """Id de la session courante (kv['current_session_id']), ou None.

        None si aucune session ouverte ou valeur illisible — JAMAIS
        d'exception : le tag de session ne doit pas casser add().
        """
        try:
            raw = self.kv_get("current_session_id")
            return int(raw) if raw is not None else None
        except (sqlite3.Error, TypeError, ValueError):
            return None

    def session_begin(self, now, summary=None):
        """Ouvre une session (frontière d'événement) et retourne son id.

        Si une session est encore ouverte (kv['current_session_id'] posé et
        ended_ts NULL), elle est FERMÉE d'abord (ended_ts=now) : deux begin
        consécutifs donnent des sessions contiguës (gap 0). La nouvelle ligne
        porte started_ts=now, summary éventuel, et gap_before_h = heures
        depuis l'ended_ts le plus récent (0.0 si première session) — c'est la
        matière première de felt_time (« retrouvailles »). L'id est stocké
        dans kv['current_session_id'] pour le tag des add() suivants.
        Legacy-safe : couche temporelle absente => None, sans lever.
        """
        if not self._has_sessions():
            return None
        open_id = self._current_session_id()
        if open_id is not None:
            row = self.db.execute(
                "SELECT ended_ts FROM sessions WHERE id=?", (open_id,)
            ).fetchone()
            if row is not None and row[0] is None:
                self.db.execute(
                    "UPDATE sessions SET ended_ts=? WHERE id=?", (now, open_id)
                )
        prev = self.db.execute("SELECT MAX(ended_ts) FROM sessions").fetchone()
        gap_before_h = (
            max(0.0, (now - prev[0]) / 3600.0)
            if prev and prev[0] is not None
            else 0.0
        )
        cur = self.db.execute(
            "INSERT INTO sessions (started_ts, summary, gap_before_h) VALUES (?,?,?)",
            (now, summary, gap_before_h),
        )
        session_id = cur.lastrowid
        self.kv_set("current_session_id", str(session_id))  # commit inclus
        return session_id

    def session_end(self, now, summary=None):
        """Ferme la session courante : ended_ts=now (+ summary si fourni).

        Le summary posé au begin est CONSERVÉ si aucun n'est fourni ici.
        Efface kv['current_session_id'] par DELETE (kv.value NOT NULL — pas
        de mise à NULL) : les add() suivants retombent à session_id NULL.
        Sans session courante, ou sur DB legacy : no-op silencieux.
        """
        if not self._has_sessions():
            return None
        session_id = self._current_session_id()
        if session_id is not None:
            if summary is not None:
                self.db.execute(
                    "UPDATE sessions SET ended_ts=?, summary=? WHERE id=?",
                    (now, summary, session_id),
                )
            else:
                self.db.execute(
                    "UPDATE sessions SET ended_ts=? WHERE id=?", (now, session_id)
                )
        self.db.execute("DELETE FROM kv WHERE key='current_session_id'")
        self.db.commit()
        return None

    def _session_autoboot(self, now):
        """Sessions auto-gérées au boot : segmentation par écart temporel.

        Frontière d'événement MÉCANIQUE (Zacks) posée par wm_boot — la
        couche temporelle se peuple sans dépendre d'un session_begin
        explicite de l'agent :
        - aucune session ouverte => en ouvrir une (session_begin) ;
        - session ouverte dont la dernière activité (dernier épisode tagué,
          à défaut started_ts) date de plus de SESSION_GAP_H heures => la
          FERMER à cette dernière activité (ended_ts = vécu réel, pas now :
          gap_before_h reflète le vrai « temps sans se voir »), puis en
          ouvrir une nouvelle via session_begin ;
        - session ouverte encore « chaude » (écart <= SESSION_GAP_H) =>
          CONSERVÉE telle quelle : deux wm_boot rapprochés ne créent
          qu'UNE session (idempotent, pas de spam).
        Retourne l'id de la session courante. Legacy-safe (pas de couche
        temporelle => None) et JAMAIS d'exception : un échec dégrade en
        no-op — le boot de la MDT n'en dépend pas.
        """
        try:
            if not self._has_sessions():
                return None  # DB legacy : dégradé propre, comme session_begin
            open_id = self._current_session_id()
            if open_id is not None:
                row = self.db.execute(
                    "SELECT started_ts, ended_ts FROM sessions WHERE id=?",
                    (open_id,),
                ).fetchone()
                if row is not None and row[1] is None:  # encore ouverte
                    last = self.db.execute(
                        "SELECT MAX(ts) FROM episodes WHERE session_id=?",
                        (open_id,),
                    ).fetchone()
                    last_ts = last[0] if last and last[0] is not None else row[0]
                    if (now - last_ts) <= config.SESSION_GAP_H * 3600.0:
                        return open_id  # session récente : on la garde
                    # écart dépassé : clore à la DERNIÈRE ACTIVITÉ (pas now)
                    self.db.execute(
                        "UPDATE sessions SET ended_ts=? WHERE id=?",
                        (last_ts, open_id),
                    )
            return self.session_begin(now)
        except Exception:
            try:  # le bookkeeping de session ne casse JAMAIS wm_boot
                self.db.rollback()
            except Exception:
                pass
            return None

    def landmark_add(self, now, label, kind=None, salience=0.5):
        """Insère un jalon daté (landmark) et retourne son id.

        Les landmarks sont les REPÈRES du temps vécu (« la fois où… ») :
        datés, lisibles, avec une saillance bornée [0,1]. Legacy-safe :
        table absente => None, sans lever.
        """
        if not self._table_exists("landmarks"):
            return None
        salience = max(0.0, min(1.0, float(salience)))
        cur = self.db.execute(
            "INSERT INTO landmarks (ts, label, kind, salience) VALUES (?,?,?,?)",
            (now, label, kind, salience),
        )
        self.db.commit()
        return cur.lastrowid

    def assign_sessions(self, gap_h=None):
        """Segmentation RÉTROACTIVE des épisodes en sessions (Zacks).

        Parcourt TOUS les épisodes par ts croissant ; un écart > gap_h*3600
        (défaut config.SESSION_GAP_H) entre deux épisodes consécutifs ouvre
        une nouvelle session. IDEMPOTENT par reconstruction : la table
        sessions est vidée puis re-créée renumérotée 1..N (started_ts/
        ended_ts = bornes du cluster, gap_before_h = heures depuis la fin de
        la précédente), et episodes.session_id est reposé pour tous — un 2e
        appel redonne exactement le même résultat. kv['current_session_id']
        est EFFACÉ (les ids sont renumérotés : un pointeur conservé taguerait
        la mauvaise session). Retourne {"sessions": n, "episodes_tagged": n}.
        Sans épisode, ou sur DB legacy : zéros sans rien toucher.
        """
        if not self._has_sessions():
            return {"sessions": 0, "episodes_tagged": 0}
        gap_s = (gap_h if gap_h is not None else config.SESSION_GAP_H) * 3600.0
        rows = self.db.execute(
            "SELECT id, ts FROM episodes ORDER BY ts ASC, id ASC"
        ).fetchall()
        if not rows:
            return {"sessions": 0, "episodes_tagged": 0}
        clusters, current = [], [rows[0]]
        for eid, ts in rows[1:]:
            if ts - current[-1][1] > gap_s:
                clusters.append(current)
                current = [(eid, ts)]
            else:
                current.append((eid, ts))
        clusters.append(current)
        self.db.execute("DELETE FROM sessions")
        self.db.execute("DELETE FROM kv WHERE key='current_session_id'")
        prev_end = None
        for n, cluster in enumerate(clusters, start=1):
            started, ended = cluster[0][1], cluster[-1][1]
            gap_before_h = (
                max(0.0, (started - prev_end) / 3600.0)
                if prev_end is not None
                else 0.0
            )
            self.db.execute(
                "INSERT INTO sessions (id, started_ts, ended_ts, gap_before_h) "
                "VALUES (?,?,?,?)",
                (n, started, ended, gap_before_h),
            )
            self.db.executemany(
                "UPDATE episodes SET session_id=? WHERE id=?",
                [(n, eid) for eid, _ts in cluster],
            )
            prev_end = ended
        self.db.commit()
        return {"sessions": len(clusters), "episodes_tagged": len(rows)}

    def felt_time(self, now):
        """Temps RESSENTI depuis le dernier épisode HUMAIN, DÉRIVÉ — jamais persisté.

        1 - 0.5**(gap_h/24) : ~0 si activité très récente, 0.5 après 24 h,
        tend vers 1 (borné [0,1]) — la fonction « retrouvailles/cadence »,
        recalculée à la demande depuis episodes (mêmes rôles humains que le
        rêve : config.DREAM_HUMAN_ROLES). Mémoire vide => 0.0 (pas d'écart
        ressenti sans premier échange). AUCUNE écriture en DB.
        """
        marks = ",".join("?" * len(config.DREAM_HUMAN_ROLES))
        row = self.db.execute(
            f"SELECT MAX(ts) FROM episodes WHERE role IN ({marks})",
            config.DREAM_HUMAN_ROLES,
        ).fetchone()
        if not row or row[0] is None:
            return 0.0
        gap_h = max(0.0, (now - row[0]) / 3600.0)
        return max(0.0, min(1.0, 1.0 - 0.5 ** (gap_h / 24.0)))

    # --- facettes (3.5a : organisation + facet_search ; le score de rappel
    # --- n'est PAS touché — W_FACET = gate séparé, Phase 3.5b) ---
    def upsert_facet(self, slug):
        """Id de la facette (créée si absente) ; None si plafond global atteint."""
        return facets_extract.upsert_facet(self.db, slug)

    def tag_episode(self, episode_id, facets):
        """Rattache [(slug, weight)] à un épisode (idempotent, PK composite)."""
        return facets_extract.tag_episode(self.db, episode_id, facets)

    def facets_of(self, episode_id):
        """Facettes d'un épisode [(slug, weight)], poids décroissant."""
        return facets_extract.facets_of(self.db, episode_id)

    def search_by_facets(self, slugs, top_k=config.TOP_K):
        """Rappel par INTERSECTION de facettes (Jaccard pondéré), lecture seule.

        Les slugs d'entrée sont normalisés (normalize_slug) et dédupliqués.
        score = somme des poids des facettes communes / (|requête| +
        |facettes de l'épisode| - |communes|) — poids côté requête = 1.
        Épisode sans facette commune : exclu. Retourne
        [(score, ts, role, content, {"facets": [slugs communs]})],
        départage des ex æquo par récence.
        """
        wanted = sorted(
            {s for s in (facets_extract.normalize_slug(x) for x in slugs) if s}
        )
        if not wanted:
            return []
        marks = ",".join("?" * len(wanted))
        candidates = self.db.execute(
            "SELECT ef.episode_id, SUM(ef.weight), COUNT(*), GROUP_CONCAT(f.slug) "
            "FROM episode_facets ef JOIN facets f ON f.id = ef.facet_id "
            f"WHERE f.slug IN ({marks}) GROUP BY ef.episode_id",
            tuple(wanted),
        ).fetchall()
        scored = []
        for eid, common_w, common_n, common_slugs in candidates:
            row = self.db.execute(
                "SELECT ts, role, content FROM episodes WHERE id=?", (eid,)
            ).fetchone()
            if row is None:
                continue
            total_n = self.db.execute(
                "SELECT COUNT(*) FROM episode_facets WHERE episode_id=?", (eid,)
            ).fetchone()[0]
            score = common_w / (len(wanted) + total_n - common_n)
            scored.append(
                (score, row[0], row[1], row[2],
                 {"facets": sorted((common_slugs or "").split(","))})
            )
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return scored[:top_k]

    def reembed_all(self, embed_fn):
        """Recalcule tous les embeddings (migration, ex. nomic→model2vec)."""
        rows = self.db.execute("SELECT id, content FROM episodes").fetchall()
        for id_, content in rows:
            self.db.execute(
                "UPDATE episodes SET embedding=? WHERE id=?",
                (json.dumps(embed_fn(content)), id_),
            )
        self.db.commit()
        return len(rows)

    # --- compétences (mémoire procédurale) ---
    def save_skill(self, name, description, content):
        registre.avant_competence(self.db, name, description, content)   # historique + registre
        self.db.execute(
            "INSERT OR REPLACE INTO skills (ts, name, description, content) "
            "VALUES (?,?,?,?)",
            (time.time(), name, description, content),
        )
        self.db.commit()

    def list_skills(self):
        return self.db.execute(
            "SELECT name, description FROM skills ORDER BY ts DESC"
        ).fetchall()

    def get_skill(self, name):
        return self.db.execute(
            "SELECT name, description, content FROM skills WHERE name = ?", (name,)
        ).fetchone()

    def retrieve_keyword(self, query, top_k=config.TOP_K):
        """Repli sans embeddings : recherche par mots-clés (LIKE), du plus récent."""
        rows = self.db.execute(
            "SELECT ts, role, content, importance FROM episodes "
            "WHERE content LIKE ? ORDER BY ts DESC LIMIT ?",
            (f"%{query}%", top_k),
        ).fetchall()
        return [(0.0, ts, role, content, {}) for ts, role, content, _imp in rows]

    # --- clé/valeur (auto-modèle d'identité, singletons) ---
    def kv_get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def kv_set(self, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
            (key, value, time.time()),
        )
        self.db.commit()
