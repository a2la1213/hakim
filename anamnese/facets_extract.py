"""Facettes Anamnèse 2.0 (Phase 3.5a) — tags fins BORNÉS, extraits du contenu.

Complément des rubriques (arbre grossier) : la précision fine passe par les
facettes. Extraction purement lexicale (offline, déterministe, sans LLM) :
- tokens saillants, entités techniques PRÉSERVÉES par le tokenizer composé
  (`three.js`, `orbit-controls`, `memory.py` restent un seul token) ;
- normalisation : minuscule, sans accents, tirets ; stopwords FR+EN ;
  longueur mini `config.FACET_MIN_TOKEN_LEN` ;
- poids = fréquence normalisée (0..1] ; cap `config.FACET_MAX_PER_EPISODE`
  (garde les plus lourds) ; vocabulaire borné par `config.FACET_MAX_GLOBAL`.

Les primitives DB prennent une connexion sqlite3 DÉJÀ OUVERTE sur une base
migrée (cf. migrations.migrate) — même convention que rubrics.py. memory.py
les expose en méthodes ; eval/backfill_facets.py les réutilise telles quelles.
Cette phase ne touche PAS le score de rappel (W_FACET = gate Phase 3.5b).
Rien ne s'exécute à l'import.
"""

import re
import unicodedata

import config

# Token « composé » : mots (accentués ou non) éventuellement joints par
# `.`/`-`/`_` — capture three.js, orbit-controls, memory.py en UN token.
_TOKEN_RE = re.compile(r"[A-Za-z0-9À-ɏ]+(?:[._\-][A-Za-z0-9À-ɏ]+)*")

# Caractères admis dans un slug final (après minuscule + désaccentuation).
_SLUG_JUNK_RE = re.compile(r"[^a-z0-9.\-]")
_SPACES_RE = re.compile(r"[\s_]+")

# Stopwords FR+EN, stockés SANS accents (comparés après normalize_slug).
# Les mots < FACET_MIN_TOKEN_LEN sont déjà écartés par la longueur.
STOPWORDS = frozenset(
    """
    ainsi alors apres assez aucun aucune auquel aussi autre autres aux avant
    avec avoir beaucoup bien car ceci cela celle celles celui cependant certain
    certaine certaines certains ces cet cette ceux chaque chez comme comment
    dans deja depuis des donc dont duquel elle elles encore enfin entre est
    etaient etait etant ete etre eux faire fait faites fois font hors ici ils
    jusqu juste laquelle lequel les leur leurs lors lui mais malgre meme memes
    mes mieux moins mon nos notamment notre nous par parce parfois pas pendant
    peu peut peut-etre peuvent plus plusieurs pour pourquoi pres puis quand
    quel quelle quelles quelques quels que qui quoi rien sans selon serait
    ses seulement sinon soit son sont sous souvent sur tandis tant tel telle
    telles tels tes ton toujours tous tout toute toutes tres trop une vers
    voici voila vos votre vous
    about above after again against all also among and any are around because
    been before being below between both but can cannot could did does doing
    down during each few for from further had has have having her here hers
    him his how into its itself just more most much must not now off once
    only other our ours out over own same she should some soon still such
    than that the their theirs them then there these they this those through
    under until upon very was were what when where which while who whom why
    will with without would you your yours
    """.split()
)


def normalize_slug(s):
    """Slug canonique : minuscule, sans accents, espaces/underscores -> tirets.

    Garde points et tirets (entités techniques : three.js, orbit-controls).
    « Caméra » -> « camera » ; « Three.JS » -> « three.js ».
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = _SPACES_RE.sub("-", s.lower().strip())
    return _SLUG_JUNK_RE.sub("", s).strip(".-")


def extract_facets(content):
    """Facettes candidates [(slug, weight)] d'un texte, triées poids décroissant.

    Dédup par slug (les graphies fusionnent), poids = fréquence / fréquence
    max (0..1], cap config.FACET_MAX_PER_EPISODE — les plus lourds gagnent,
    départage alphabétique (déterministe).
    """
    counts = {}
    for token in _TOKEN_RE.findall(content or ""):
        slug = normalize_slug(token)
        if len(slug) < config.FACET_MIN_TOKEN_LEN or slug in STOPWORDS:
            continue
        counts[slug] = counts.get(slug, 0) + 1
    if not counts:
        return []
    max_count = max(counts.values())
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        (slug, count / max_count)
        for slug, count in ranked[: config.FACET_MAX_PER_EPISODE]
    ]


# --- primitives DB (connexion ouverte, base migrée — convention rubrics.py) ---


def upsert_facet(conn, slug):
    """Id de la facette `slug` (créée si absente) — INSERT OR IGNORE, commit.

    Plafond global config.FACET_MAX_GLOBAL : une facette NOUVELLE au-delà
    n'est PAS créée (retourne None) — borne l'explosion du vocabulaire.
    Une facette existante reste toujours résolue, plafond atteint ou non.
    """
    row = conn.execute("SELECT id FROM facets WHERE slug=?", (slug,)).fetchone()
    if row:
        return row[0]
    total = conn.execute("SELECT COUNT(*) FROM facets").fetchone()[0]
    if total >= config.FACET_MAX_GLOBAL:
        return None
    conn.execute("INSERT OR IGNORE INTO facets (slug) VALUES (?)", (slug,))
    conn.commit()
    row = conn.execute("SELECT id FROM facets WHERE slug=?", (slug,)).fetchone()
    return row[0] if row else None


def tag_episode(conn, episode_id, facets):
    """Rattache des facettes [(slug, weight)] à un épisode. Commit inclus.

    INSERT OR IGNORE sur la PK composite (episode_id, facet_id) -> idempotent
    (un re-tag ne duplique rien et conserve le poids d'origine). Facette
    refusée par le plafond global -> sautée. Retourne le nombre de liens
    RÉELLEMENT créés par cet appel.
    """
    inserted = 0
    for slug, weight in facets:
        facet_id = upsert_facet(conn, slug)
        if facet_id is None:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO episode_facets (episode_id, facet_id, weight) "
            "VALUES (?,?,?)",
            (episode_id, facet_id, float(weight)),
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def facets_of(conn, episode_id):
    """Facettes d'un épisode [(slug, weight)], poids décroissant puis slug."""
    return conn.execute(
        "SELECT f.slug, ef.weight FROM episode_facets ef "
        "JOIN facets f ON f.id = ef.facet_id "
        "WHERE ef.episode_id=? ORDER BY ef.weight DESC, f.slug",
        (episode_id,),
    ).fetchall()
