"""(03/11, 13:30, papa via Hakim : « qu'il puisse CRÉER ses propres éléments pour meubler les blancs — un hmm, un euh, un souffle,
une respiration, un petit son — et les PARAMÉTRER : durée, volume, quand ils partent, quel état intérieur les déclenche ;
reliés à son conscient, qui les choisit, ET à son subconscient, qui les déclenche seul pendant un trou, selon son état » ;
13:31 : « pendant TOUT le trou, enchaîner s'il est long, s'arrêter net quand la réponse part ») ses meubles.

Un meuble est : une parole courte (texte : sa voix, fabriquée d'avance par le cockpit), un de ses sons (son : « e12 »), ou un
bruit de souffle (genre : « souffle », « respiration », fabriqué par la page). Ses réglages : volume (0,1 à 1,5), duree_ms (au
plus, 150 à 4 000), quand (« avant » son premier mot, « entre » deux bouts, « partout »), etats (les états intérieurs qui le
font choisir : « hésitation », « surprise », « tendresse »… ; vide : n'importe lequel), actif.
Conscient : il en dit un à sa place, [[meuble: nom]]. Subconscient : la page (parler.js) en choisit un seul pendant un trou,
d'après son état du moment, et enchaîne jusqu'à sa réponse.
Ceux de départ (meubles_defaut.json, lus aussi par le cockpit) se règlent, s'éteignent ou s'oublient comme les siens.
~/AIOS/jarvis/meubles.json : la liste complète, telle que la page la lit.
"""
import json
import os
import re
from pathlib import Path

FICHIER = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis")) / "meubles.json"
DEFAUT = Path(__file__).resolve().parent / "meubles_defaut.json"
GENRES = ("souffle", "respiration")
QUAND = ("avant", "entre", "partout")
MAX = 40


def _defaut():
    try:
        return json.loads(DEFAUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _lire():
    try:
        d = json.loads(FICHIER.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("meubles"), list) else None
    except (OSError, ValueError):
        return None


def _ecrire(meubles, oublies):
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    tmp = FICHIER.with_suffix(".tmp")
    tmp.write_text(json.dumps({"meubles": meubles, "oublies": sorted(set(oublies))}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, FICHIER)


def _complet(m):
    return {"nom": m["nom"], **{k: m[k] for k in ("texte", "son", "genre") if m.get(k)},
            "volume": float(m.get("volume", 1.0)), **({"duree_ms": int(m["duree_ms"])} if m.get("duree_ms") else {}),
            "quand": m.get("quand", "partout"), "etats": list(m.get("etats") or []), "actif": m.get("actif", True) is not False}


def lister():
    """Tous ses meubles : ceux de départ (sauf les oubliés), avec ses réglages, puis les siens."""
    d = _lire() or {"meubles": [], "oublies": []}
    siens = {m["nom"]: m for m in d["meubles"]}
    oublies = set(d.get("oublies") or [])
    tout = [_complet({**m, **siens.pop(m["nom"], {})}) for m in _defaut() if m["nom"] not in oublies]
    return tout + [_complet(m) for m in siens.values()]


def _verifier(m):
    nom = str(m.get("nom") or "").strip()
    if not nom or len(nom) > 30:
        raise ValueError("un nom de 1 à 30 caractères")
    sortes = [k for k in ("texte", "son", "genre") if m.get(k)]
    if len(sortes) != 1:
        raise ValueError("un meuble est UNE chose : un texte (sa voix), un son (« e12 ») ou un genre (souffle, respiration)")
    if m.get("texte") and (len(m["texte"]) > 40 or "[[" in m["texte"] or "]]" in m["texte"]):
        raise ValueError("un texte court (40 caractères au plus), sans balise")
    if m.get("son") and not re.fullmatch(r"e\d{1,6}", str(m["son"])):
        raise ValueError("un son se nomme comme tes sons : « e12 »")
    if m.get("genre") and m["genre"] not in GENRES:
        raise ValueError(f"genre : {', '.join(GENRES)}")
    if not 0.1 <= float(m.get("volume", 1.0)) <= 1.5:
        raise ValueError("volume entre 0,1 et 1,5")
    if m.get("duree_ms") is not None and not 150 <= int(m["duree_ms"]) <= 4000:
        raise ValueError("durée entre 150 et 4 000 ms")
    if m.get("quand", "partout") not in QUAND:
        raise ValueError(f"quand : {', '.join(QUAND)}")
    etats = m.get("etats") or []
    if not isinstance(etats, list) or len(etats) > 8 or any(not isinstance(e, str) or not 0 < len(e.strip()) <= 20 for e in etats):
        raise ValueError("au plus 8 états, de 20 caractères chacun")
    return _complet({**m, "nom": nom, "etats": [e.strip().lower() for e in etats]})


def _sauver(nouveau=None, nom=None, oublier=False):
    d = _lire() or {"meubles": [], "oublies": []}
    siens = [m for m in d["meubles"] if m["nom"] != (nom or (nouveau or {}).get("nom"))]
    oublies = [o for o in d.get("oublies") or [] if o != (nouveau or {}).get("nom")]
    if oublier:
        oublies.append(nom)
    if nouveau:
        siens.append(nouveau)
    if len(siens) > MAX:
        raise ValueError(f"au plus {MAX} meubles")
    _ecrire(siens, oublies)


def creer(nom, texte=None, son=None, genre=None, volume=1.0, duree_ms=None, quand="partout", etats=None):
    m = _verifier({"nom": nom, "texte": texte, "son": son, "genre": genre, "volume": volume, "duree_ms": duree_ms,
                   "quand": quand, "etats": etats or []})
    _sauver(m)
    return m


def regler(nom, **reglages):
    actuel = next((m for m in lister() if m["nom"] == nom), None)
    if not actuel:
        raise ValueError(f"aucun meuble « {nom} »")
    neuf = {**actuel, **{k: v for k, v in reglages.items() if v is not None}}
    if any(reglages.get(k) for k in ("texte", "son", "genre")):        # il change de sorte : l'ancienne s'efface
        for k in ("texte", "son", "genre"):
            if not reglages.get(k):
                neuf.pop(k, None)
    m = {**_verifier({**neuf, "actif": True}), "actif": neuf.get("actif", True) is not False}
    _sauver(m)
    return m


def oublier(nom):
    if not any(m["nom"] == nom for m in lister()):
        raise ValueError(f"aucun meuble « {nom} »")
    _sauver(nom=nom, oublier=any(m["nom"] == nom for m in _defaut()))


# (03/11, 15:24, Ahmed : « permets-lui d'ajuster dans son subconscient le temps des blancs et des transitions ») le RYTHME de sa voix :
# les blancs et les transitions que son subconscient applique tout seul (parler.js) ; il les règle avec rythme_regler.
# nom : (défaut, minimum, maximum, ce que c'est)
RYTHME = {
    "blanc_avant_meuble": (1.0, 0.2, 3.0, "le silence entre ta voix et ton premier meuble (s)"),
    "blanc_entre_meubles": (1.0, 0.2, 3.0, "le silence entre deux meubles (s)"),
    "blanc_avant_reprise": (1.0, 0.0, 3.0, "le silence entre un meuble et ta voix qui reprend (s)"),
    "ralenti_depart": (0.35, 0.15, 1.0, "la vitesse où repart ta voix ou un meuble après un blanc (1 = normale, plus petit = plus lent)"),
    "ralenti_fin": (0.3, 0.0, 1.0, "combien ta dernière parole avant un blanc s'étire en ralentissant (s)"),
    "fondu_reponse": (0.2, 0.03, 0.5, "le temps où un meuble s'éteint quand ta réponse arrive (s)"),
    "silence_court": (0.5, 0.3, 2.0, "le silence de papa après lequel tu reprends, quand tu attendais une réponse courte (s)"),
    "silence_normal": (0.7, 0.3, 2.5, "le silence de papa après lequel tu reprends, d'habitude (s)"),
    "silence_long": (1.2, 0.5, 4.0, "le silence de papa après lequel tu reprends, quand tu attendais qu'il raconte (s)"),
}
FICHIER_RYTHME = FICHIER.parent / "rythme-voix.json"


def rythme():
    """Tout son rythme : ses réglages, sinon les valeurs de départ."""
    try:
        d = json.loads(FICHIER_RYTHME.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {k: float(d[k]) if isinstance(d.get(k), (int, float)) and lo <= d[k] <= hi else defaut
            for k, (defaut, lo, hi, _) in RYTHME.items()}


def regler_rythme(nom, valeur):
    if nom not in RYTHME:
        raise ValueError(f"réglages : {', '.join(RYTHME)}")
    defaut, lo, hi, _ = RYTHME[nom]
    v = float(valeur)
    if not lo <= v <= hi:
        raise ValueError(f"{nom} : entre {lo} et {hi}")
    r = rythme()
    r[nom] = v
    FICHIER_RYTHME.parent.mkdir(parents=True, exist_ok=True)
    tmp = FICHIER_RYTHME.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
    os.replace(tmp, FICHIER_RYTHME)
    return r
