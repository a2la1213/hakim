"""Routage v2 (2026-10-15), corrigé après relecture indépendante (Opus 5.5, verdict CORRIGER).

Mesure : eval/route_bench.py, variante « production » = routing.decider (même code que
route_episode), centroïdes leave-one-out. Les chiffres et leurs limites sont dans le banc.

1. L'en-tête (« [OpenRasm, 2026-10-15] … ») choisit le PROJET : mots-clés dérivés de l'arbre,
   frontières de mot (camelCase compris : « JarvisXAnamnèse »), projet le plus tôt cité ;
   si l'en-tête nomme deux projets → pas de décision. La sous-rubrique est ensuite choisie par
   centroïde centré DANS le sous-arbre du projet.
2. Centroïde centré (moyenne pondérée des centroïdes soustraite) quand l'arbre est peuplé ;
   en mode centré, aucun seuil ni repli au parent (ils envoyaient 28 % des insights à la
   racine « projets ») : seul le plancher ≤ 0 donne None.
3. Gardes : centroïdes non finis écartés ; vecteur nul → None.
4. Une règle historique vers une rubrique disparue (projets/atelier3d) est ignorée.
5. « thought » garde son comportement historique (relation-identite).

Prédiction écrite avant le correctif : les tests de collisions, de sous-arbre, de seuil,
de NaN, de vecteur nul, de atelier3d et de thought échouent sur la version relue.
"""

import json
import sqlite3

import numpy as np

import config
import routing

ARBRE = ["projets", "projets/anamnese", "projets/anamnese/daemon-consolidation", "projets/robot-ia",
         "projets/quran-study", "projets/quran-study/openrasm", "projets/quran-study/histoire-du-texte",
         "projets/proxipro", "projets/proxipro/qa", "projets/labmarches", "projets/labmarches/strategies",
         "projets/axai-distillation", "projets/axai-distillation/compression", "projets/chantier3d",
         "projets/synod-it", "projets/synod-it/astronomie", "projets/studiostudioclient", "projets/lvx",
         "projets/unification", "sciences", "sciences/physique", "relation-identite", "meta-apprentissage"]
KW = routing.mots_cles_projets(ARBRE)


def test_mots_cles_derives_de_l_arbre():
    assert KW["openrasm"] == "projets/quran-study/openrasm"
    assert KW["robot-ia"] == "projets/robot-ia" and KW["robot ia"] == "projets/robot-ia"
    assert KW["anamnese"] == "projets/anamnese"
    assert KW["lvx"] == "projets/lvx"                                  # nom de projet de 3 lettres
    for generique in ("qa", "projets", "physique", "strategies", "compression", "astronomie"):
        assert generique not in KW


def test_projet_en_tete():
    cas = {
        "[OpenRasm, 2026-10-15] Préférence d'Ahmed…": "projets/quran-study/openrasm",
        "[JarvisXAnamnèse, 2026-10-15] Lot 0 fait": "projets/anamnese",
        "[robot-ia T4b] mémoire du robot": "projets/robot-ia",
        "[Anamnèse daemon-consolidation] trace": "projets/anamnese/daemon-consolidation",
        "[LVX] niveau 3 du jeu": "projets/lvx",
        # collisions relevées par la relecture : le projet nommé en premier l'emporte
        "[Proxipro] Stratégies de prix": "projets/proxipro",
        "[Anamnèse] compression des souvenirs": "projets/anamnese",
        "[Chantier3D] astronomie du chantier": "projets/chantier3d",
        "[Studiostudioclient] histoire du texte des paroles": "projets/studiostudioclient",
        # frontières de mot
        "Réflexion métaphysique sur le temps": None,
        "RÉUNIFICATION des sciences": None,
        # le crochet de tête désigne le projet ; sans crochet, deux projets = pas de décision
        "[OpenRasm] lien avec [Robot IA]": "projets/quran-study/openrasm",
        "Lien entre OpenRasm et le Robot IA": None,
        "[JarvisXAnamnèseXRobotIA] voix": None,
        # projet cité APRÈS l'en-tête
        "Préférence générale de travail. " + "x " * 60 + "lien avec openrasm": None,
    }
    for texte, attendu in cas.items():
        assert routing.projet_en_tete(texte, KW) == attendu, texte


def _rubriques(n_rub, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    commun = rng.normal(size=dim) * 4                      # composante partagée (anisotropie)
    out = []
    for i in range(n_rub):
        v = commun + rng.normal(size=dim)
        v /= np.linalg.norm(v)
        out.append((f"projets/r{i}/sous", None, v.tolist(), 20))
    return out


def test_centrage_seulement_si_arbre_peuple():
    peu = _rubriques(3)
    x = (np.array(peu[1][2]) + 0.01).tolist()
    _, c_brut = routing.scorer_centroides(x, peu)
    xs = np.array(x)
    attendu = max(float(np.dot(xs, np.array(v)) / (np.linalg.norm(xs) * np.linalg.norm(v))) for _, _, v, _ in peu)
    assert abs(c_brut - min(attendu, 1.0)) < 1e-6                      # cosinus brut historique


def test_centrage_formule_exacte():
    beaucoup = _rubriques(routing.CENTRAGE_MIN_RUBRIQUES + 5)
    rng = np.random.default_rng(1)
    x = np.array(beaucoup[7][2]) + 0.2 * rng.normal(size=16)
    C = np.array([v for _, _, v, _ in beaucoup])
    n = np.array([k for _, _, _, k in beaucoup], dtype=float)
    mu = (C * n[:, None]).sum(axis=0) / n.sum()
    sims = ((C - mu) @ (x - mu)) / (np.linalg.norm(C - mu, axis=1) * np.linalg.norm(x - mu))
    path, conf = routing.scorer_centroides(x.tolist(), beaucoup)
    assert path == beaucoup[int(np.argmax(sims))][0]
    assert abs(conf - float(sims.max())) < 1e-9
    brut = (C @ x) / (np.linalg.norm(C, axis=1) * np.linalg.norm(x))
    assert brut.max() > 0.9 > sims.max()


def test_mode_centre_sans_repli_au_parent():
    """Un score centré faible mais positif garde la meilleure rubrique (pas son parent)."""
    beaucoup = _rubriques(routing.CENTRAGE_MIN_RUBRIQUES + 5)
    C = np.array([v for _, _, v, _ in beaucoup])
    mu = C.mean(axis=0)
    Cc = C - mu
    u3 = Cc[3] / np.linalg.norm(Cc[3])
    w = np.linalg.svd(Cc)[2][-1]                           # direction orthogonale à tous les centroïdes centrés
    x = mu + 0.2 * u3 + 1.0 * w
    path, conf = routing.scorer_centroides(x.tolist(), beaucoup)
    assert path == "projets/r3/sous" and 0 < conf < config.ROUTE_MIN_CONF


def test_gardes_nan_et_vecteur_nul():
    beaucoup = _rubriques(routing.CENTRAGE_MIN_RUBRIQUES + 5)
    x = beaucoup[4][2]
    sain = routing.scorer_centroides(x, beaucoup)
    avec_nan = beaucoup + [("projets/casse", None, [float("nan")] * 16, 20)]
    assert routing.scorer_centroides(x, avec_nan) == sain
    assert routing.scorer_centroides([0.0] * 16, beaucoup) == (None, 0.0)


def test_parmi_restreint_l_argmax_sans_changer_la_moyenne():
    beaucoup = _rubriques(routing.CENTRAGE_MIN_RUBRIQUES + 5)
    x = beaucoup[2][2]
    path, _ = routing.scorer_centroides(x, beaucoup, parmi={"projets/r9/sous", "projets/r11/sous"})
    assert path in {"projets/r9/sous", "projets/r11/sous"}


def _base(tmp_path, centroides=None):
    conn = sqlite3.connect(str(tmp_path / "r.db"))
    conn.execute("CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT, kind_hint TEXT, "
                 "centroid TEXT, centroid_n INTEGER)")
    for i, p in enumerate(ARBRE):
        c = (centroides or {}).get(p)
        conn.execute("INSERT INTO rubrics VALUES (?,?,?,?,?)", (i + 1, p, None, json.dumps(c) if c else None, 20 if c else 0))
    return conn


def test_en_tete_puis_sous_rubrique_par_centroide(tmp_path):
    base = np.eye(16)
    centroides = {"projets/anamnese": (base[0] + base[1]).tolist(),
                  "projets/anamnese/daemon-consolidation": (base[0] + base[2]).tolist(),
                  "projets/robot-ia": (base[0] + base[3]).tolist()}
    conn = _base(tmp_path, centroides)
    emb = (base[0] + base[2] + 0.1 * base[5]).tolist()
    row = {"role": "semantic", "content": "[Anamnèse, 2026-10-15] la nuit tourne", "embedding": json.dumps(emb)}
    assert routing.route_episode(conn, row) == ("projets/anamnese/daemon-consolidation", routing.CONF_PROJET_EN_TETE)
    # projet sans centroïde dans son sous-arbre : la racine du projet
    row = {"role": "semantic", "content": "[OpenRasm] règle de droits", "embedding": json.dumps(emb)}
    assert routing.route_episode(conn, row) == ("projets/quran-study/openrasm", routing.CONF_PROJET_EN_TETE)
    conn.close()


def test_regle_vers_rubrique_disparue_ignoree(tmp_path):
    conn = _base(tmp_path)
    row = {"role": "reasoning", "content": "[Anamnèse] debug : on avait corrigé ça dans Atelier3D",
           "embedding": json.dumps([0.1] * 16)}
    assert routing.route_episode(conn, row) == ("projets/anamnese", routing.CONF_PROJET_EN_TETE)
    conn.close()


def test_roles_du_demon_et_thought_gardent_l_historique(tmp_path):
    conn = _base(tmp_path)
    for role in ("reflection", "thought"):
        row = {"role": role, "content": "[OpenRasm] je me demande…", "embedding": json.dumps([0.1] * 16)}
        assert routing.route_episode(conn, row)[0] == "relation-identite", role
    conn.close()


# --- tour 4 (2026-10-15, avant re-rangement de masse) -------------------------------------
# Constats sur la simulation : (a) les insights centrés convergent vers un « aimant »
# (152 vers projets/synod-it/qa) → les rôles hors humains gardent le cosinus brut historique ;
# (b) dans un sous-arbre, la jeune sous-rubrique pointue bat le parent dilué → on ne descend
# que si son score dépasse SEUIL_DESCENTE (choisi par le banc).

def test_roles_hors_humains_en_cosinus_brut():
    beaucoup = _rubriques(routing.CENTRAGE_MIN_RUBRIQUES + 5)
    x = (np.array(beaucoup[6][2]) + 0.3 * np.random.default_rng(3).normal(size=16)).tolist()
    paths = [p for p, _, _, _ in beaucoup]
    attendu = routing.scorer_centroides(x, beaucoup, "insight", centrer=False)
    assert routing.decider("insight", "(insight·claude) un motif", x, paths, beaucoup) == attendu


def test_descente_sous_le_seuil_reste_au_projet(monkeypatch):
    base = np.eye(16)
    rub = [("projets/anamnese", None, (base[0] + base[1]).tolist(), 50),
           ("projets/anamnese/daemon-consolidation", None, (base[0] + base[2]).tolist(), 5)]
    rub += [(f"projets/autre{i}", None, (base[0] + base[3 + i % 10]).tolist(), 20) for i in range(12)]
    paths = [p for p, _, _, _ in rub]
    x = (base[0] + 0.3 * base[2] + 0.9 * base[14]).tolist()        # faible affinité avec la sous-rubrique
    monkeypatch.setattr(routing, "SEUIL_DESCENTE", 0.0)
    assert routing.decider("semantic", "[Anamnèse] état", x, paths, rub)[0] == "projets/anamnese/daemon-consolidation"
    monkeypatch.setattr(routing, "SEUIL_DESCENTE", 0.9)
    assert routing.decider("semantic", "[Anamnèse] état", x, paths, rub)[0] == "projets/anamnese"
