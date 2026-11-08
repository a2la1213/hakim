"""Banc de routage — mesure LECTURE SEULE du rangement des souvenirs (2026-10-15).

Vérité terrain : les épisodes rangés DÉLIBÉRÉMENT (rubric_conf == 1.0 : memory_reclassify,
memory_store_in, opérations de taxonomie), rôles humains seulement. Chaque variante prédit
leur rubrique en « leave-one-out » : l'épisode ne compte ni dans son centroïde ni dans ses
voisins.

RÈGLE DE DÉCISION, ÉCRITE AVANT LE PREMIER RUN :
- métrique primaire : exactitude au NIVEAU PROJET (projets/X, sinon 1er segment) ;
- on choisit la meilleure variante sur DEV (ids pairs) ;
- elle n'est adoptée que si, sur TEST (ids impairs), elle bat V0 d'au moins 5 points au niveau
  projet ET ne perd pas plus d'1 point en exactitude exacte ; sinon on garde l'existant.

Variantes :
  V0  actuel : règles actuelles (mots-clés de projet seulement pour « reasoning ») puis
      centroïde le plus proche (+ bonus kind_hint), comme routing.route_by_centroid.
  V1  règles de projet pour tous les rôles humains, mots-clés DÉRIVÉS de l'arbre des
      rubriques, cherchés dans l'en-tête (100 premiers caractères), puis centroïde.
  V2  centroïde sur embeddings CENTRÉS (vecteur moyen soustrait : l'espace model2vec est
      anisotrope, cosinus ≈ 0,7 entre sujets sans rapport).
  V3  k plus proches voisins (k=10) sur embeddings centrés, vote pondéré.
  V4  V1 puis V3.

TOUR 2 (déclaré le 2026-10-15 APRÈS lecture du tour 1, même règle de décision) :
  V5  V1 puis V2 (règles étendues, puis centroïde centré). Le TEST a déjà été lu une fois au
      tour 1 : un résultat positif ici est moins solide qu'au tour 1 et doit être revérifié
      sur les futurs rangements manuels (le banc se relance à volonté).

TOUR 3 (après relecture indépendante Opus 5.5, verdict CORRIGER) :
  V6  PRODUCTION = routing.decider, le code exact de route_episode, appelé avec des centroïdes
      leave-one-out. Corrigé : pas de seuil en mode centré, sous-rubrique choisie dans le
      sous-arbre du projet de l'en-tête, crochet de tête prioritaire, frontières de mot.
      Même règle de décision, évaluée sur DEUX découpages : ids pairs/impairs (DEV et TEST pas
      indépendants : ids voisins dans la même rubrique) et par date (DEV = la moitié la plus
      ancienne, TEST = la plus récente), plus le détail sous-agents / autres (biais signalé :
      349 rangements viennent de sous-agents dont l'en-tête reprend le nom de la rubrique).
      V1 à V5 sont gardées telles quelles comme trace des tours 1 et 2.

TOUR 4 (déclaré AVANT le run, 2026-10-15) : seuil de descente dans le sous-arbre du projet.
  Candidats 0 ; 0,1 ; 0,2 ; 0,3 ; 0,4 ; 0,5. On retient le meilleur en EXACT sur DEV-date
  (anciens) ; adopté seulement si, sur TEST-date (récents), l'exact est ≥ celui du seuil 0.

Usage : .venv/bin/python eval/route_bench.py
"""
import json
import pathlib
import re
import sqlite3
import sys
import unicodedata

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config   # noqa: E402
import routing  # noqa: E402

HUMAINS = ("semantic", "episodic", "reasoning", "project", "reference", "thought")
GENERIQUES = {"qa", "design", "frontend", "architecture", "audit", "pilotage", "devops", "seo",
              "securite", "contenu", "conformite", "db", "web", "mobile", "core", "paiements",
              "redaction", "dev", "statistiques", "perf", "i18n", "a11y", "ux", "ia", "3d",
              "projets", "savoir", "personnel", "papers", "reservation", "metier-audio",
              "conformite-ch", "juridique-produit", "caisse-compta", "pricing-stripe", "modelisation"}
EN_TETE = 100
K = 10


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def niveau_projet(path):
    if not path:
        return None
    seg = path.split("/")
    return "/".join(seg[:2]) if seg[0] == "projets" and len(seg) > 1 else seg[0]


def mots_cles(paths):
    """{mot-clé normalisé: path} dérivés des segments spécifiques de l'arbre."""
    kw = {}
    for p in sorted(paths, key=lambda x: x.count("/")):   # le plus profond écrase
        for i, seg in enumerate(p.split("/")):
            if i == 0 or seg in GENERIQUES or len(seg) < 4:
                continue
            cible = "/".join(p.split("/")[: i + 1])
            for v in {seg, seg.replace("-", " "), seg.replace("-", "")}:
                kw[sans_accents(v)] = cible
    kw["atelier3d"] = "projets/chantier3d" if "projets/chantier3d" in paths else kw.get("atelier3d")
    return {k: v for k, v in kw.items() if v}


def cherche(texte, kw):
    """Mot-clé le plus spécifique trouvé dans le texte (≥ 7 car. : sous-chaîne ; sinon mot entier)."""
    t = sans_accents(texte)
    trouves = []
    for k, path in kw.items():
        if len(k) >= 7:
            pos = t.find(k)
        else:
            m = re.search(r"\b" + re.escape(k) + r"\b", t)
            pos = m.start() if m else -1
        if pos >= 0:
            trouves.append((-path.count("/"), pos, path))
    return min(trouves)[2] if trouves else None


def charger(db_path):
    conn = sqlite3.connect(pathlib.Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    rub = {rid: (path, kh) for rid, path, kh in conn.execute("SELECT id, path, kind_hint FROM rubrics")}
    rows = conn.execute("SELECT id, role, content, embedding, rubric_id, rubric_conf FROM episodes").fetchall()
    conn.close()
    vec, meta = [], []
    for eid, role, content, emb, rid, conf in rows:
        try:
            e = json.loads(emb)
        except (TypeError, ValueError):
            continue
        if not isinstance(e, list) or len(e) != 256:
            continue
        vec.append(e)
        meta.append((eid, role, content or "", rub.get(rid, (None, None))[0] if rid else None, conf or 0.0))
    X = np.asarray(vec, dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    return X, meta, rub


def centroides(X, labels, paths):
    idx = {p: i for i, p in enumerate(paths)}
    S = np.zeros((len(paths), X.shape[1]), dtype=np.float64)
    N = np.zeros(len(paths))
    for i, p in enumerate(labels):
        if p in idx:
            S[idx[p]] += X[i]
            N[idx[p]] += 1
    return S, N, idx


def predire_centroide(x, S, N, idx, paths, propre, kind_hints, role, i_vec):
    S2, N2 = S, N
    if propre in idx and N[idx[propre]] > 0:          # leave-one-out
        S2 = S.copy(); N2 = N.copy()
        S2[idx[propre]] -= i_vec; N2[idx[propre]] -= 1
    ok = N2 > 0
    C = S2[ok] / N2[ok][:, None]
    C /= np.linalg.norm(C, axis=1, keepdims=True) + 1e-9
    sims = C @ x
    noms = [p for p, k in zip(paths, ok) if k]
    bonus = np.array([routing.KIND_HINT_BONUS if kind_hints.get(p) == role else 0.0 for p in noms])
    j = int(np.argmax(sims + bonus))
    return noms[j]


def main():
    X, meta, rub = charger(config.DB_PATH)
    paths = sorted({p for p, _ in rub.values()})
    kind_hints = {p: kh for p, kh in rub.values()}
    labels = [m[3] for m in meta]
    verite = [i for i, m in enumerate(meta) if m[3] and m[4] >= 0.999 and m[1] in HUMAINS]
    mu = X.mean(axis=0)
    Xc = X - mu
    Xc /= np.linalg.norm(Xc, axis=1, keepdims=True) + 1e-9
    S, N, idx = centroides(X, labels, paths)
    Sc, Nc, _ = centroides(Xc, labels, paths)
    routes = np.array([i for i, p in enumerate(labels) if p])
    kw = mots_cles(paths)

    def v0(i):
        eid, role, content, vrai, _ = meta[i]
        r = routing.route_by_rules(role, content)
        return r[0] if r else predire_centroide(X[i], S, N, idx, paths, vrai, kind_hints, role, X[i])

    def regle_etendue(i):
        eid, role, content, vrai, _ = meta[i]
        if role in ("reasoning",) and routing.route_by_rules(role, content):
            r = routing.route_by_rules(role, content)
            if r[0] != "meta-apprentissage":
                return r[0]
        return cherche(content[:EN_TETE], kw)

    def v2(i):
        eid, role, content, vrai, _ = meta[i]
        return predire_centroide(Xc[i], Sc, Nc, idx, paths, vrai, kind_hints, role, Xc[i])

    def v3(i):
        sims = Xc[routes] @ Xc[i]
        sims[routes == i] = -9                          # leave-one-out
        top = np.argpartition(-sims, K)[:K]
        votes = {}
        for j in top:
            votes[labels[routes[j]]] = votes.get(labels[routes[j]], 0.0) + float(sims[j])
        return max(votes, key=votes.get)

    def v6(i):
        eid, role, content, vrai, _ = meta[i]
        S2, N2 = S, N
        if vrai in idx and N[idx[vrai]] > 0:              # leave-one-out
            S2, N2 = S.copy(), N.copy()
            S2[idx[vrai]] -= X[i]; N2[idx[vrai]] -= 1
        rubriques = [(p, kind_hints.get(p), (S2[k] / N2[k]).tolist(), int(N2[k]))
                     for p, k in idx.items() if N2[k] > 0]
        return routing.decider(role, content, X[i].tolist(), paths, rubriques)[0]

    variantes = {
        "V0 actuel": v0,
        "V1 règles étendues + centroïde": lambda i: regle_etendue(i) or v0(i),
        "V2 centroïde centré": v2,
        "V3 kNN centré": v3,
        "V4 règles étendues + kNN centré": lambda i: regle_etendue(i) or v3(i),
        "V5 règles étendues + centré (tour 2)": lambda i: regle_etendue(i) or v2(i),
        "V6 PRODUCTION (tour 3)": v6,
    }

    print(f"vérité terrain : {len(verite)} épisodes rangés à la main (rôles humains)")
    print(f"{'variante':34} | {'DEV projet':>10} {'DEV exact':>9} | {'TEST projet':>11} {'TEST exact':>10}")
    res = {}
    for nom, f in variantes.items():
        sc = {"dev": [0, 0, 0], "test": [0, 0, 0]}
        for i in verite:
            part = "dev" if meta[i][0] % 2 == 0 else "test"
            pred, vrai = f(i), meta[i][3]
            sc[part][0] += 1
            sc[part][1] += niveau_projet(pred) == niveau_projet(vrai)
            sc[part][2] += pred == vrai
        d, t = sc["dev"], sc["test"]
        res[nom] = (100 * d[1] / d[0], 100 * d[2] / d[0], 100 * t[1] / t[0], 100 * t[2] / t[0])
        print(f"{nom:34} | {res[nom][0]:9.1f}% {res[nom][1]:8.1f}% | {res[nom][2]:10.1f}% {res[nom][3]:9.1f}%")
    tour1 = [n for n in res if n != "V0 actuel" and "tour" not in n]
    meilleur = max(tour1, key=lambda n: res[n][0])
    b, m = res["V0 actuel"], res[meilleur]
    adopte = m[2] >= b[2] + 5 and m[3] >= b[3] - 1
    print(f"\nmeilleure sur DEV : {meilleur}")
    print(f"TEST : projet {m[2]:.1f}% vs {b[2]:.1f}% (+{m[2] - b[2]:.1f}), exact {m[3]:.1f}% vs {b[3]:.1f}%")
    print("VERDICT tour 1 :", "ADOPTER" if adopte else "GARDER L'EXISTANT")
    v5 = res["V5 règles étendues + centré (tour 2)"]
    ok5 = v5[2] >= b[2] + 5 and v5[3] >= b[3] - 1
    print(f"TOUR 2 — V5 sur TEST : projet {v5[2]:.1f}% (+{v5[2] - b[2]:.1f}), exact {v5[3]:.1f}% "
          f"({v5[3] - b[3]:+.1f}) → {'ADOPTER (TEST déjà vu une fois : à revérifier)' if ok5 else 'GARDER L EXISTANT'}")
    v6r = res["V6 PRODUCTION (tour 3)"]
    ok6 = v6r[2] >= b[2] + 5 and v6r[3] >= b[3] - 1
    print(f"TOUR 3 — V6 (ids impairs) : projet {v6r[2]:.1f}% ({v6r[2] - b[2]:+.1f}), exact {v6r[3]:.1f}% "
          f"({v6r[3] - b[3]:+.1f}) → {'ADOPTER' if ok6 else 'GARDER L EXISTANT'}")

    # Découpage par DATE : DEV = moitié la plus ancienne, TEST = la plus récente.
    ts_par_id = {}
    conn = sqlite3.connect(pathlib.Path(config.DB_PATH).resolve().as_uri() + "?mode=ro", uri=True)
    for eid, ts in conn.execute("SELECT id, ts FROM episodes"):
        ts_par_id[eid] = ts
    conn.close()
    par_date = sorted(verite, key=lambda i: ts_par_id.get(meta[i][0], 0))
    moitie = len(par_date) // 2
    agent = re.compile(r"^\[(architecte|dev|qa|auditeur|expert|chef-de-projet|directeur-artistique|"
                       r"redacteur|dpo|devops|statisticien|chercheur)-", re.I)

    def score(f, groupe):
        n = len(groupe) or 1
        proj = sum(niveau_projet(f(i)) == niveau_projet(meta[i][3]) for i in groupe)
        exact = sum(f(i) == meta[i][3] for i in groupe)
        return 100 * proj / n, 100 * exact / n, len(groupe)

    print("\nDÉCOUPAGE PAR DATE (DEV = anciens, TEST = récents) et sous-groupes du TEST :")
    tests_date = par_date[moitie:]
    groupes = {"DEV (anciens)": par_date[:moitie], "TEST (récents)": tests_date,
               "TEST écrits par sous-agents": [i for i in tests_date if agent.match(meta[i][2])],
               "TEST autres": [i for i in tests_date if not agent.match(meta[i][2])]}
    for nom_g, g in groupes.items():
        a0, a6 = score(variantes["V0 actuel"], g), score(v6, g)
        print(f"  {nom_g:30} n={a0[2]:3} | V0 {a0[0]:5.1f}% / {a0[1]:5.1f}%  →  V6 {a6[0]:5.1f}% / {a6[1]:5.1f}%"
              f"  ({a6[0] - a0[0]:+.1f} / {a6[1] - a0[1]:+.1f})")
    d0, d6 = score(variantes["V0 actuel"], tests_date), score(v6, tests_date)
    ok_date = d6[0] >= d0[0] + 5 and d6[1] >= d0[1] - 1
    print("VERDICT tour 3, découpage par date :", "ADOPTER" if ok_date else "GARDER L'EXISTANT")

    print("\nTOUR 4 — seuil de descente (DEV-date / TEST-date, projet / exact) :")
    livre = routing.SEUIL_DESCENTE
    balayage = {}
    for seuil in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        routing.SEUIL_DESCENTE = seuil
        balayage[seuil] = (score(v6, par_date[:moitie]), score(v6, tests_date))
        d, t = balayage[seuil]
        print(f"  {seuil:.1f} | DEV {d[0]:5.1f}% / {d[1]:5.1f}% | TEST {t[0]:5.1f}% / {t[1]:5.1f}%")
    routing.SEUIL_DESCENTE = livre
    choisi = max(balayage, key=lambda k: (balayage[k][0][1], -k))
    ok4 = balayage[choisi][1][1] >= balayage[0.0][1][1]
    print(f"seuil choisi sur DEV : {choisi} → {'ADOPTER' if ok4 else 'GARDER 0'} "
          f"(TEST exact {balayage[choisi][1][1]:.1f}% vs {balayage[0.0][1][1]:.1f}% à 0) ; seuil livré = {livre}")



if __name__ == "__main__":
    main()
