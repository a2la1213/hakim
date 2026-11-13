"""L'ÉCHANTILLON INTELLIGENT : ce que Claude lira pour distiller le cerveau de départ (pas besoin de tout lire).

L'index par le sens couvre tout ; Claude ne lit qu'une sélection, choisie ainsi :
- un score par fichier : richesse du texte, genre (une discussion dit la façon d'écrire du papa, un document son métier),
  mots du métier (mode, collection, couture…), document écrit par le papa lui-même, fraîcheur ;
- la DIVERSITÉ par le sens : chaque nouveau choix est le meilleur compromis entre son score et sa distance aux fichiers déjà
  choisis (sélection gloutonne « max-min ») : cent devis presque identiques ne prennent qu'une place ;
- un budget de caractères (et par fichier) ; le texte complet d'un choisi est relu à la source (lecture seule, masqué).
Les photos, vidéos et morceaux ne sont jamais lus : ils donnent des AGRÉGATS calculés sur le PC (années, lieux regroupés et
numérotés sans coordonnées, appareils, artistes et genres écoutés, dossiers), qui disent la chronologie et les goûts sans
rien envoyer d'identifiant.
"""
import math
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ICI = Path(__file__).resolve().parent
for _p in (str(ICI), str(ICI.parents[1]), str(ICI.parents[1] / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

import extraction   # noqa: E402

METIER = re.compile(r"(?i)\b(mode|collection|couture|couturi|styliste|stylisme|défilé|defile|tissu|textile|patron(?:age)?s?|"
                    r"croquis|lookbook|moodboard|prêt-à-porter|pret-a-porter|fashion|atelier|toile|coupe|ourlet|broderie|"
                    r"maille|lin|soie|coton|laine|denim|vestes?|robes?|chemises?|manteaux?|capsule|showroom|fashion week|"
                    r"marque|boutique|clientes?|look|silhouette|mannequin|shooting|campagne|vitrine|retouche|sur[- ]mesure)\b")
POIDS_GENRE = {"document": 1.0, "discussion": 1.15, "courriel": 0.8}


def _norme(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def score(r, papa_noms=(), aujourd_hui=None):
    ex = r.get("extrait") or ""
    if r["genre"] not in POIDS_GENRE or len(ex.strip()) < 60:
        return 0.0
    s = math.log1p(len(ex)) / math.log1p(1500) * POIDS_GENRE[r["genre"]]
    metier = len(METIER.findall(f"{r.get('titre', '')} {ex}"))
    s += min(metier, 6) * 0.08
    auteur = (r.get("auteur") or "").lower()
    if auteur and any(n.lower() in auteur or auteur in n.lower() for n in papa_noms if n):
        s += 0.35
    try:
        a = date.fromisoformat((r.get("date") or "")[:10])
        age = ((aujourd_hui or date.today()) - a).days / 365.25
        s += 0.25 * math.exp(-max(age, 0) / 3)
    except ValueError:
        pass
    return s


def choisir(rows, papa_noms=(), max_fichiers=60, lambda_score=0.6, aujourd_hui=None):
    """Les fichiers choisis (dans l'ordre du choix) parmi les lignes de l'inventaire."""
    cands = [(score(r, papa_noms, aujourd_hui), r) for r in rows]
    cands = [(s, r) for s, r in cands if s > 0]
    if not cands:
        return []
    smax = max(s for s, _ in cands) or 1.0
    vec = {id(r): _norme(r["vecteur"]) if r.get("vecteur") else None for _, r in cands}
    choisis, reste = [], list(cands)
    dmin = {id(r): 1.0 for _, r in cands}
    while reste and len(choisis) < max_fichiers:
        meilleur = max(reste, key=lambda sr: lambda_score * sr[0] / smax + (1 - lambda_score) * dmin[id(sr[1])])
        reste.remove(meilleur)
        choisis.append(meilleur[1])
        vb = vec[id(meilleur[1])]
        for _, r in reste:
            v = vec[id(r)]
            if v is not None and vb is not None:
                d = max(0.0, 1.0 - _cos(v, vb))          # distance cosinus, dans [0, 2] ramenée à [0, 1]
                dmin[id(r)] = min(dmin[id(r)], min(d, 1.0))
    return choisis


def texte_complet(r, papa_noms=(), par_fichier=3500, masquer=None):
    """Le texte d'un fichier choisi, relu à la source (lecture seule), borné, secrets masqués. Pour une discussion :
    surtout les messages du papa (sa façon d'écrire), avec un peu de contexte."""
    ex = extraction.extraire(Path(r["chemin"]), r["genre"])
    if r["genre"] == "discussion":
        messages = ex.get("messages") or []
        siens = [m for m in messages if _est_papa(m[1], papa_noms)]
        autres = [m for m in messages if not _est_papa(m[1], papa_noms)]
        lignes = [f"[{d}] PAPA : {t}" for d, _a, t in siens[-60:]] + [f"[{d}] {a} : {t}" for d, a, t in autres[-15:]]
        texte = f"Discussion WhatsApp ({ex.get('titre')}) — {len(siens)} messages du papa sur {len(messages)}\n" + "\n".join(lignes)
    else:
        texte = ex.get("texte") or r.get("extrait") or ""
    if masquer:
        texte = masquer(texte)
    return texte[:par_fichier]


def _est_papa(auteur, papa_noms):
    a = str(auteur or "").lower()
    return any(n and (n.lower() == a or n.lower() in a.split()) for n in papa_noms)


def papa_probable(noms_releves, declares=()):
    """Les noms du papa : ceux qu'il a déclarés, sinon l'auteur de documents le plus fréquent et l'expéditeur WhatsApp
    présent dans le plus de discussions (l'exportateur est dans toutes)."""
    if declares:
        return [n for n in declares if n]
    auteurs = Counter({n: c for n, s, c in noms_releves if s == "auteur"})
    whatsapp = Counter({n: c for n, s, c in noms_releves if s == "whatsapp"})
    out = []
    if auteurs:
        out.append(auteurs.most_common(1)[0][0])
    if whatsapp:
        n, c = whatsapp.most_common(1)[0]
        if c >= 2 and n not in out:
            out.append(n)
    return out


def _grille(gps, pas=0.1):
    return (round(gps[0] / pas), round(gps[1] / pas))


def agregats(rows, papa_noms=()):
    """Ce que disent les photos, vidéos, morceaux et dossiers, sans rien d'identifiant : un texte court."""
    annees = Counter()
    par_genre_annee = Counter()
    lieux, lieux_dates = Counter(), {}
    appareils, artistes, genres_musique, dossiers = Counter(), Counter(), Counter(), Counter()
    correspondants, n_discussions = Counter(), 0
    for r in rows:
        a = (r.get("date") or "")[:4]
        if a.isdigit():
            annees[a] += 1
            par_genre_annee[(r["genre"], a)] += 1
        m = r.get("meta") or {}
        if r["genre"] in ("photo", "video"):
            if isinstance(m.get("gps"), list) and len(m["gps"]) == 2:
                g = _grille(m["gps"])
                lieux[g] += 1
                lieux_dates.setdefault(g, []).append(r.get("date") or "")
            if m.get("appareil"):
                appareils[m["appareil"]] += 1
        elif r["genre"] == "audio":
            if m.get("artiste"):
                artistes[m["artiste"]] += 1
            if m.get("genre"):
                genres_musique[m["genre"]] += 1
        elif r["genre"] == "discussion":
            n_discussions += 1
            for nom, c in (m.get("participants") or {}).items():
                if not _est_papa(nom, papa_noms):
                    correspondants[nom] += c
        parties = (r.get("affiche") or "").split("/")
        if len(parties) >= 3:
            dossiers["/".join(parties[:2])] += 1
    lignes = []
    if annees:
        lignes.append("Fichiers par année : " + ", ".join(f"{a} : {annees[a]}" for a in sorted(annees)))
        detail = []
        for a in sorted(annees):
            d = ", ".join(f"{g} {par_genre_annee[(g, a)]}" for g in ("document", "photo", "video", "discussion", "courriel", "audio")
                          if par_genre_annee[(g, a)])
            detail.append(f"{a} ({d})")
        lignes.append("Détail par année : " + " ; ".join(detail))
    if lieux:
        out = []
        for i, (g, c) in enumerate(lieux.most_common(8), 1):
            ds = sorted(d for d in lieux_dates[g] if d)
            mois = Counter(d[5:7] for d in ds if len(d) >= 7)
            out.append(f"lieu {i} : {c} photos/vidéos, de {ds[0][:7] if ds else '?'} à {ds[-1][:7] if ds else '?'}"
                       + (f", surtout les mois {', '.join(m for m, _ in mois.most_common(3))}" if mois else ""))
        lignes.append("Lieux des photos (regroupés à ~10 km, numérotés, sans coordonnées) : " + " ; ".join(out))
    if appareils:
        lignes.append("Appareils photo : " + ", ".join(f"{a} ({c})" for a, c in appareils.most_common(4)))
    if artistes:
        lignes.append("Musique — artistes les plus présents : " + ", ".join(f"{a} ({c})" for a, c in artistes.most_common(15)))
    if genres_musique:
        lignes.append("Musique — genres : " + ", ".join(f"{g} ({c})" for g, c in genres_musique.most_common(8)))
    if n_discussions:
        lignes.append(f"Discussions WhatsApp exportées : {n_discussions} ; correspondants les plus fréquents : "
                      + ", ".join(f"{n} ({c} messages)" for n, c in correspondants.most_common(10)))
    if dossiers:
        lignes.append("Dossiers les plus remplis : " + ", ".join(f"{d} ({c})" for d, c in dossiers.most_common(15)))
    return "\n".join(lignes)
