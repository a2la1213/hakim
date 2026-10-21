"""Routage des épisodes vers les rubriques — règles corrigées + centroïde, SANS LLM.

Deux mécanismes, dans cet ordre :
1. RÈGLES déterministes sur (role, content). Correction du misroute historique :
   les `reference` façon Unification (Al-Husban, Soluno, charge topologique…)
   vont dans `projets/unification`, PAS dans `savoir-applecture` ; seules les
   références coraniques EXPLICITES vont dans applecture — et la règle AppLecture
   est évaluée AVANT la règle Unification (un paper coranique citant
   incidemment « al-husban » reste dans applecture) ; les autres `reference`
   ne matchent AUCUNE règle et sont laissées au centroïde.
2. CENTROÏDE : cosinus de l'embedding vs les centroïdes non vides des rubriques
   (+ bonus additif doux si `rubrics.kind_hint == role`). PLANCHER (1B-harden) :
   meilleure conf <= 0 -> (None, 0.0) — jamais d'attache à conf négative, jamais
   de centroïde contaminé par un vecteur anti-corrélé. Le fallback GROSSIER au
   parent ne s'applique qu'à `0 < conf < config.ROUTE_MIN_CONF` ;
   racine sous seuil ou aucun centroïde -> (None, 0.0).

`route_all` = bootstrap en 2 PASSES : la passe règles attache d'abord (ça
construit les premiers centroïdes via rubrics.attach_episode), puis la passe
centroïde route les épisodes restants. Jamais de bucket « divers » :
`rubric_id NULL` est l'état neutre VALIDE (rejouable). Reprenable : un épisode
déjà routé n'est pas re-routé sauf `force=True`.

Toutes les fonctions prennent une connexion sqlite3 DÉJÀ OUVERTE sur une base
migrée + squelette seedé. L'attach/centroïde est délégué à rubrics.attach_episode
(jamais réimplémenté ici). Rien ne s'exécute à l'import.
"""

import re
import sqlite3
import unicodedata

import numpy as np

import config
import rubrics
from rubrics import _parse_embedding  # même parsing tolérant que l'attach
from salience import cosine

# Bonus additif doux quand rubrics.kind_hint == rôle de l'épisode (prior léger :
# il départage les quasi-ex-æquo sans jamais écraser une vraie différence).
KIND_HINT_BONUS = 0.05

# Mots-clés (minuscules, match par FRONTIÈRE DE MOT sur content.lower() —
# jamais en sous-chaîne brute : « interstellaire » ne matche pas « stellaire »).
# 1B-harden : les mots-clés Unification sont des noms propres SPÉCIFIQUES
# uniquement — les génériques (genesis, unification, cosmogonie, stellaire)
# causaient du cross-talk (« Cosmogonie coranique », « Genesis of black hole
# binaries » -> unification à tort). Une règle déterministe à conf 0.9 ne doit
# se déclencher que sur un signal SANS ambiguïté ; les papers génériques sont
# routés par centroïde (passe 2), pas par règle.
UNIFICATION_KEYWORDS = (
    "al-husban",
    "soluno",
    "soluno-stellaire",
    "charge topologique",
    "charge-topologique",
)
QURAN_KEYWORDS = (
    "coran",
    "quran",
    "applecture",
    "sourate",
    "verset",
    "racine arabe",
    # translittérations usuelles
    "surah",
    "ayah",
    "tafsir",
    "bismillah",
)

# Projets connus nommables dans un `reasoning` : (mot-clé, rubrique).
PROJECT_KEYWORDS = (
    ("atelier3d", "projets/atelier3d"),
    ("anamnèse", "projets/anamnese"),
    ("anamnese", "projets/anamnese"),
    ("unification", "projets/unification"),
    ("applecture", "savoir-applecture"),
)


# Patterns compilés par mot-clé (cache module) : \b<kw>\b, métacaractères
# échappés. Les mots-clés multi-mots (« charge topologique ») restent matchés
# comme séquence, avec frontières aux deux bouts.
_KW_PATTERNS = {}


def _kw_pattern(kw):
    pat = _KW_PATTERNS.get(kw)
    if pat is None:
        pat = _KW_PATTERNS[kw] = re.compile(r"\b" + re.escape(kw) + r"\b")
    return pat


def _word_match(content, kw):
    """Mot-clé présent sur frontières de mot (insensible à la casse)."""
    return _kw_pattern(kw).search((content or "").lower()) is not None


def _contains_any(content, keywords):
    low = (content or "").lower()
    return any(_kw_pattern(kw).search(low) for kw in keywords)


# Règles ORDONNÉES (le premier match gagne) : (match_fn(role, content) -> bool,
# rubric_path, conf, keywords). `keywords` = les mots-clés susceptibles de
# déclencher la règle (None pour les règles purement par rôle) — utilisé par
# `route_report` pour attribuer chaque hit à son mot-clé déclencheur.
# L'ordre porte la correction : AppLecture est testée AVANT Unification —
# un paper coranique explicite (quran/sourate/…) qui cite incidemment le
# « calendrier al-husban » (#431/#432) doit gagner applecture, alors que le
# vrai paper Unification (Al-Husban Soluno-Stellaire, sans mot-clé coranique)
# traverse la règle AppLecture sans matcher et tombe sur Unification. Un
# `reasoning` qui nomme un projet est testé AVANT le `reasoning` générique.
RULES = (
    [
        (
            lambda role, content: role == "reference"
            and _contains_any(content, QURAN_KEYWORDS),
            "savoir-applecture",
            0.9,
            QURAN_KEYWORDS,
        ),
        (
            lambda role, content: role == "reference"
            and _contains_any(content, UNIFICATION_KEYWORDS),
            "projets/unification",
            0.9,
            UNIFICATION_KEYWORDS,
        ),
        (
            lambda role, content: role in ("reflection", "outreach", "dream", "thought"),
            "relation-identite",
            0.8,
            None,
        ),
    ]
    + [
        (
            lambda role, content, _kw=kw: role == "reasoning"
            and _word_match(content, _kw),
            path,
            0.75,
            (kw,),
        )
        for kw, path in PROJECT_KEYWORDS
    ]
    + [
        (lambda role, content: role == "reasoning", "meta-apprentissage", 0.7, None),
    ]
)


def route_by_rules(role, content):
    """Première règle qui matche -> (rubric_path, conf) ; sinon None."""
    for match_fn, rubric_path, conf, _keywords in RULES:
        if match_fn(role, content):
            return rubric_path, conf
    return None


# --- Routage v2 (2026-10-15), corrigé après relecture indépendante ---------------------------
# Mesure : eval/route_bench.py (variante « production » = decider, centroïdes leave-one-out).
# La décision est une fonction PURE (decider), appelée à l'identique par route_episode et par
# le banc : ce qui est mesuré est ce qui tourne.
ROLES_HUMAINS = ("semantic", "episodic", "reasoning", "project", "reference")
EN_TETE = 100                    # caractères où chercher le projet (« [OpenRasm, 2026-10-15] … »)
CONF_PROJET_EN_TETE = 0.75
CENTRAGE_MIN_RUBRIQUES = 10      # en dessous, une moyenne n'a pas de sens : cosinus brut historique
CENTRAGE_MIN_N = 100
SEUIL_DESCENTE = 0.3             # score centré minimal pour descendre sous la racine du projet (banc, tour 4)
_GENERIQUES = {"qa", "design", "frontend", "architecture", "audit", "pilotage", "devops", "seo",
               "securite", "contenu", "conformite", "db", "web", "mobile", "core", "paiements",
               "redaction", "dev", "statistiques", "perf", "i18n", "a11y", "ux", "ia", "3d",
               "projets", "savoir", "personnel", "papers", "reservation", "metier-audio",
               "conformite-ch", "juridique-produit", "caisse-compta", "pricing-stripe", "modelisation",
               # mots courants relevés par la relecture (aimants à faux positifs)
               "physique", "strategies", "compression", "astronomie", "microstructure", "speculatif"}


def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFKD", (texte or "").lower())
                   if not unicodedata.combining(c))


def _projet(path):
    seg = (path or "").split("/")
    return "/".join(seg[:2]) if seg[0] == "projets" and len(seg) > 1 else seg[0]


def mots_cles_projets(paths):
    """{mot-clé normalisé: path} dérivés des segments spécifiques de l'arbre des rubriques.
    Segments génériques exclus ; 4 caractères minimum, 3 pour un nom de projet (« lvx »)."""
    paths = list(paths)
    kw = {}
    for p in sorted(paths, key=lambda x: (x.count("/"), x)):      # le plus profond écrase
        seg = p.split("/")
        for i, nom in enumerate(seg):
            mini = 3 if (i == 1 and seg[0] == "projets") else 4
            if i == 0 or nom in _GENERIQUES or len(nom) < mini:
                continue
            cible = "/".join(seg[: i + 1])
            for v in {nom, nom.replace("-", " "), nom.replace("-", "")}:
                kw[sans_accents(v)] = cible
    if "projets/chantier3d" in paths:                                # ancien nom de Chantier3D
        kw["atelier3d"] = "projets/chantier3d"
    return kw


def _debut_de_mot(t, i):
    """Frontière avant t[i], sur le texte d'ORIGINE : début, séparateur, ou camelCase
    (« jarvisX|Anamnèse »), mais pas l'intérieur d'un mot en capitales (« RÉ|UNIFICATION »)."""
    if i == 0 or not t[i - 1].isalnum():
        return True
    if t[i].isupper() and t[i - 1].islower():
        return True
    return t[i].isupper() and t[i - 1].isupper() and i + 1 < len(t) and t[i + 1].islower()


def _fin_de_mot(t, j):
    if j + 1 >= len(t) or not t[j + 1].isalnum():
        return True
    return t[j + 1].isupper() and t[j].islower()


def projet_en_tete(content, kw):
    """Rubrique du projet nommé dans l'en-tête, ou None.

    Convention des souvenirs : « [Projet, date] … ». Si l'en-tête commence par un crochet, seuls
    les mots-clés trouvés DANS ce crochet comptent ; sinon, tous ceux des EN_TETE premiers
    caractères. Si ce groupe nomme plusieurs projets : pas de décision. Dans le projet retenu,
    le mot-clé le plus profond l'emporte (« [Anamnèse daemon-consolidation] »)."""
    t = (content or "")[:EN_TETE]
    norm, origine = [], []
    for i, c in enumerate(t):
        for ch in sans_accents(c):
            norm.append(ch)
            origine.append(i)
    norm = "".join(norm)
    trouves = []
    for k, path in kw.items():
        pos = norm.find(k)
        while pos >= 0:
            a, b = origine[pos], origine[pos + len(k) - 1]
            if _debut_de_mot(t, a) and _fin_de_mot(t, b):
                trouves.append((a, path))
                break
            pos = norm.find(k, pos + 1)
    debut = len(t) - len(t.lstrip())
    fin_crochet = t.find("]", debut) if t[debut:debut + 1] == "[" else -1
    dans = [m for m in trouves if fin_crochet >= 0 and m[0] <= fin_crochet]
    groupe = dans or trouves
    if not groupe or len({_projet(p) for _, p in groupe}) > 1:
        return None
    return max(groupe, key=lambda m: (m[1].count("/"), -m[0]))[1]


def scorer_centroides(embedding, rubriques, kind_hint_role=None, parmi=None, centrer=True):
    """(path, conf) du centroïde le plus proche. `rubriques` : [(path, kind_hint, centroïde, n)].
    `parmi` : chemins autorisés pour l'argmax (la moyenne reste calculée sur tout l'arbre).

    Mode centré quand l'arbre est peuplé : l'espace model2vec est anisotrope (cosinus ≈ 0,7
    entre sujets sans rapport), on soustrait la moyenne pondérée des centroïdes (= moyenne des
    épisodes rangés). Dans ce mode, pas de seuil ni de repli au parent : seul le plancher ≤ 0
    donne None. Mode brut (arbre peu peuplé) : comportement historique, seuil ROUTE_MIN_CONF."""
    if not embedding:
        return None, 0.0
    x = np.asarray(embedding, dtype=np.float64)
    if not np.all(np.isfinite(x)) or np.linalg.norm(x) < 1e-9:
        return None, 0.0
    valides = []
    for p, kh, c, n in rubriques:
        if not c or len(c) != len(x):
            continue
        v = np.asarray(c, dtype=np.float64)
        if np.all(np.isfinite(v)) and np.linalg.norm(v) > 1e-12:
            valides.append((p, kh, v, n or 0))
    if not valides:
        return None, 0.0
    C = np.stack([v for _, _, v, _ in valides])
    poids = np.array([n for _, _, _, n in valides], dtype=np.float64)
    centre = centrer and len(valides) >= CENTRAGE_MIN_RUBRIQUES and poids.sum() >= CENTRAGE_MIN_N
    if centre:
        mu = (C * poids[:, None]).sum(axis=0) / poids.sum()
        x, C = x - mu, C - mu
    sims = (C @ x) / (np.linalg.norm(C, axis=1) * np.linalg.norm(x) + 1e-12)
    if kind_hint_role is not None:
        sims = sims + np.array([KIND_HINT_BONUS if kh == kind_hint_role else 0.0 for _, kh, _, _ in valides])
    if parmi is not None:
        sims = np.where([p in parmi for p, _, _, _ in valides], sims, -np.inf)
        if not np.isfinite(sims).any():
            return None, 0.0
    j = int(np.argmax(sims))
    best_path, best_sim = valides[j][0], float(sims[j])
    if best_sim <= 0:
        # Plancher : un cosinus <= 0 signifie « aucune affinité » — attacher
        # (même au parent) créerait une conf négative ET contaminerait le
        # centroïde avec un vecteur anti-corrélé. NULL est l'état neutre.
        return None, 0.0
    conf = min(best_sim, 1.0)
    if centre or conf >= config.ROUTE_MIN_CONF:
        return best_path, conf
    if "/" in best_path:  # mode brut, 0 < conf < seuil : rattachement grossier au parent
        return best_path.rsplit("/", 1)[0], conf
    return None, 0.0  # racine sous seuil : NULL, jamais de « divers »


def _rubriques(conn):
    return [(path, kind_hint, _parse_embedding(raw), n) for path, kind_hint, raw, n in conn.execute(
        "SELECT path, kind_hint, centroid, centroid_n FROM rubrics WHERE centroid IS NOT NULL")]


def route_by_centroid(conn, embedding, kind_hint_role=None, parmi=None):
    """Rubrique au centroïde le plus proche -> (rubric_path, conf). Voir scorer_centroides."""
    return scorer_centroides(embedding, _rubriques(conn), kind_hint_role, parmi)


def decider(role, content, embedding, paths, rubriques):
    """Décision de routage, PURE (même code pour route_episode et pour le banc).
    - rôles humains : le projet de l'en-tête, puis la sous-rubrique par centroïde centré dans
      son sous-arbre ; sinon la règle historique d'un reasoning/reference qui nomme un projet
      ou un corpus ; sinon le centroïde ;
    - autres rôles (démon, thought) : règles historiques, sinon centroïde en cosinus BRUT ;
    - une règle qui vise une rubrique disparue (projets/atelier3d) est ignorée."""
    existants = set(paths)
    ruled = route_by_rules(role, content)
    if ruled is not None and ruled[0] not in existants:
        ruled = None
    if role in ROLES_HUMAINS:
        projet = projet_en_tete(content, mots_cles_projets(paths))
        if projet is not None:
            sous_arbre = {p for p in paths if p == projet or p.startswith(projet + "/")}
            path, score = scorer_centroides(embedding, rubriques, role, parmi=sous_arbre)
            if path is None or (path != projet and score < SEUIL_DESCENTE):
                path = projet          # la sous-rubrique doit le mériter : le parent est dilué
            return path, CONF_PROJET_EN_TETE
        if ruled is not None and ruled[0] != "meta-apprentissage" and role in ("reasoning", "reference"):
            return ruled
        return scorer_centroides(embedding, rubriques, role)
    if ruled is not None:
        return ruled
    # Rôles du démon (insight…) : cosinus BRUT historique. Le centrage, non mesuré pour eux,
    # créait un aimant (152 insights simulés vers projets/synod-it/qa).
    return scorer_centroides(embedding, rubriques, role, centrer=False)


def route_episode(conn, episode_row):
    """(rubric_path|None, conf) pour un épisode — voir decider.

    `episode_row` : mapping (sqlite3.Row ou dict) exposant au moins
    'role', 'content', 'embedding' (JSON brut).
    """
    paths = [r[0] for r in conn.execute("SELECT path FROM rubrics")]
    return decider(episode_row["role"], episode_row["content"],
                   _parse_embedding(episode_row["embedding"]), paths, _rubriques(conn))


def route_report(conn):
    """Rapport LECTURE SEULE de ce que la passe RÈGLES ferait — n'écrit RIEN.

    Pour chaque épisode de la base : ce que `route_by_rules` retournerait.
    La passe centroïde n'est PAS simulée (les centroïdes sont vides tant que
    rien n'a été routé — la simuler ici n'aurait pas de sens). Retourne :
      {"by_rule_counts": {rubric_path: n, ...},
       "by_keyword": {keyword: [episode_id, ...], ...},
       "unmatched": n}
    `by_keyword` groupe les hits par mot-clé déclencheur — tous les mots-clés
    de la règle GAGNANTE qui matchent l'épisode (pour relecture ciblée des
    cas limites avant le run réel). Ne modifie ni episodes ni rubrics :
    uniquement des SELECT.
    """
    report = {"by_rule_counts": {}, "by_keyword": {}, "unmatched": 0}
    for eid, role, content in conn.execute(
        "SELECT id, role, content FROM episodes ORDER BY id"
    ):
        for match_fn, rubric_path, _conf, keywords in RULES:
            if match_fn(role, content):
                report["by_rule_counts"][rubric_path] = (
                    report["by_rule_counts"].get(rubric_path, 0) + 1
                )
                for kw in keywords or ():
                    if _word_match(content, kw):
                        report["by_keyword"].setdefault(kw, []).append(eid)
                break
        else:
            report["unmatched"] += 1
    return report


def route_all(conn, now, episodes=None, force=False):
    """Bootstrap en 2 passes ; retourne {"by_rules", "by_centroid", "left_null"}.

    - `episodes` : ids à traiter (None = tous les épisodes de la table) ;
    - passe 1 (RÈGLES) : attache tous les matchés — c'est elle qui construit
      les premiers centroïdes ; passe 2 (CENTROÏDE) : route le reste ;
    - sans rubrique trouvée : `rubric_id` reste NULL (état neutre, rejouable) ;
    - reprenable : un épisode déjà routé (`rubric_id` non NULL) est sauté,
      sauf `force=True`.
    """
    stats = {"by_rules": 0, "by_centroid": 0, "left_null": 0}

    cur = conn.cursor()
    cur.row_factory = sqlite3.Row  # local au curseur : la connexion n'est pas mutée
    sql = "SELECT id, role, content, embedding, rubric_id FROM episodes"
    params = []
    if episodes is not None:
        ids = list(episodes)
        if not ids:
            return stats
        sql += " WHERE id IN (%s)" % ",".join("?" * len(ids))
        params = ids
    rows = cur.execute(sql + " ORDER BY id", params).fetchall()

    # Passe 1 — RÈGLES (construit les premiers centroïdes via attach_episode)
    remaining = []
    for row in rows:
        if row["rubric_id"] is not None and not force:
            continue
        ruled = route_by_rules(row["role"], row["content"])
        if ruled is not None:
            rubrics.attach_episode(conn, row["id"], ruled[0], ruled[1], now)
            stats["by_rules"] += 1
        else:
            remaining.append(row)

    # Passe 2 — CENTROÏDE sur le reste
    for row in remaining:
        embedding = _parse_embedding(row["embedding"])
        path, conf = route_by_centroid(conn, embedding, kind_hint_role=row["role"])
        if path is not None:
            rubrics.attach_episode(conn, row["id"], path, conf, now)
            stats["by_centroid"] += 1
        else:
            stats["left_null"] += 1  # NULL = état neutre valide, jamais « divers »

    return stats
