"""Les mémoires à règles (25/10, demande d'Ahmed relayée par Hakim) : des carnets dont Hakim PROPOSE le type — un nom, des
champs, des lois —, qu'Ahmed valide d'un geste dans Parler, et que Hakim remplit ensuite. Un moteur générique : aucun code
nouveau par type (sur le modèle du carnet d'erreurs et des prédictions figées).

- Proposer : ~/AIOS/jarvis/carnets-types/propositions/<nom>.json (écrit par le serveur MCP de Hakim). Le cockpit la vérifie
  et la montre à Ahmed ; validée, elle est copiée par le cockpit dans valides/<nom>.json : seul ce dossier fait foi.
- Les lois : « ajout_seul » est toujours vraie (rien ne s'efface ni ne se modifie : une entrée se CLÔT par une autre) ;
  « chaine » (chaque entrée porte l'empreinte de la précédente : une retouche du fichier se voit) ; « echeance » (le nom
  d'un champ date : l'entrée sonne une fois sa date passée, jusqu'à ce qu'elle soit close) ; « relu_au_demarrage » (ses
  dernières entrées et ses échéances dans le briefing de chaque conversation) ; « bilan » (compté dans bilan_semaine).
  Jamais consolidé par la nuit : ce ne sont pas des souvenirs.
- Les entrées : data/carnets/<nom>.jsonl.
"""
import hashlib
import json
import re
import secrets
import time
from pathlib import Path

import config

TYPES_DIR = Path.home() / "AIOS" / "jarvis" / "carnets-types"
ENTREES_DIR = config.DATA_DIR / "carnets"
NOM = re.compile(r"^[a-z][a-z0-9_]{2,30}$")
TYPES_CHAMP = {"texte", "nombre", "date", "choix", "oui_non"}
LOIS = {"ajout_seul", "chaine", "echeance", "relu_au_demarrage", "bilan"}
TEXTE_MAX, CHAMPS_MAX = 2000, 20
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")


class Refus(ValueError):
    pass


def verifier_definition(d):
    """La définition d'un type, nettoyée ; Refus si elle ne tient pas."""
    if not isinstance(d, dict):
        raise Refus("une définition est un objet")
    nom = str(d.get("nom") or "").strip()
    if not NOM.match(nom) or nom in {"erreurs", "predictions", "prediction", "erreur"}:
        raise Refus("nom : 3 à 31 caractères, minuscules, chiffres et _, et pas un carnet qui existe déjà")
    champs = d.get("champs")
    if not isinstance(champs, list) or not 1 <= len(champs) <= CHAMPS_MAX:
        raise Refus(f"de 1 à {CHAMPS_MAX} champs")
    propres, vus = [], set()
    for c in champs:
        if not isinstance(c, dict):
            raise Refus("chaque champ est un objet {nom, type, requis}")
        n, t = str(c.get("nom") or "").strip(), str(c.get("type") or "texte").strip()
        if not NOM.match(n) or n in vus:
            raise Refus(f"champ « {n} » : nom invalide ou en double")
        if t not in TYPES_CHAMP:
            raise Refus(f"champ « {n} » : type parmi {sorted(TYPES_CHAMP)}")
        p = {"nom": n, "type": t, "requis": bool(c.get("requis", False))}
        if t == "choix":
            choix = [str(x)[:60] for x in (c.get("choix") or [])][:20]
            if len(choix) < 2:
                raise Refus(f"champ « {n} » : au moins deux choix")
            p["choix"] = choix
        propres.append(p)
        vus.add(n)
    lois = d.get("lois") or {}
    if not isinstance(lois, dict) or set(lois) - LOIS:
        raise Refus(f"lois parmi {sorted(LOIS)}")
    lois = {"ajout_seul": True, "chaine": bool(lois.get("chaine")), "relu_au_demarrage": bool(lois.get("relu_au_demarrage")),
            "bilan": bool(lois.get("bilan", True)), "echeance": str(lois.get("echeance") or "") or None}
    if lois["echeance"] and not any(c["nom"] == lois["echeance"] and c["type"] == "date" for c in propres):
        raise Refus("echeance : le nom d'un champ de type date")
    return {"nom": nom, "description": str(d.get("description") or "")[:300], "champs": propres, "lois": lois,
            "raison": str(d.get("raison") or "")[:500]}


def proposer(definition, dossier=None):
    d = verifier_definition(definition)
    d.update(id="T-" + time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2), propose_ts=time.time(), etat="proposee")
    dos = Path(dossier or TYPES_DIR) / "propositions"
    dos.mkdir(parents=True, exist_ok=True)
    if (Path(dossier or TYPES_DIR) / "valides" / f"{d['nom']}.json").exists():
        raise Refus(f"le carnet « {d['nom']} » existe déjà")
    tmp = dos / f".{d['nom']}.tmp"
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(dos / f"{d['nom']}.json")
    return d


def types(dossier=None):
    """{nom: définition} : les validés (etat « validee ») et les propositions en attente ou refusées."""
    racine, out = Path(dossier or TYPES_DIR), {}
    for sous in ("propositions", "valides"):                     # les validées l'emportent
        for f in sorted((racine / sous).glob("*.json")):
            try:
                out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return out


def _type_valide(nom, dossier=None):
    t = types(dossier).get(str(nom))
    if not t or t.get("etat") != "validee":
        raise Refus(f"« {nom} » n'est pas un carnet validé par Ahmed (carnets_types pour la liste)")
    return t


def _fichier(nom, entrees=None):
    return Path(entrees or ENTREES_DIR) / f"{nom}.jsonl"


def _lire(nom, entrees=None):
    try:
        return [json.loads(l) for l in _fichier(nom, entrees).read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def _empreinte(precedente, o):
    return hashlib.sha256((precedente or "").encode() + json.dumps(o, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _ajouter(t, o, entrees=None):
    f = _fichier(t["nom"], entrees)
    f.parent.mkdir(parents=True, exist_ok=True)
    if t["lois"].get("chaine"):
        avant = _lire(t["nom"], entrees)
        o["prec"] = avant[-1].get("empreinte") if avant else None
        o["empreinte"] = _empreinte(o["prec"], {k: v for k, v in o.items() if k not in ("prec", "empreinte")})
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")
    return o


def ecrire(nom, valeurs, auteur="hakim", dossier=None, entrees=None, now=None):
    t = _type_valide(nom, dossier)
    if not isinstance(valeurs, dict):
        raise Refus("les valeurs sont un objet {champ: valeur}")
    inconnus = set(valeurs) - {c["nom"] for c in t["champs"]}
    if inconnus:
        raise Refus(f"champs inconnus : {sorted(inconnus)}")
    propres = {}
    for c in t["champs"]:
        v = valeurs.get(c["nom"])
        if v in (None, ""):
            if c["requis"]:
                raise Refus(f"champ requis : {c['nom']}")
            continue
        if c["type"] == "nombre":
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise Refus(f"{c['nom']} : un nombre") from None
        elif c["type"] == "date":
            if not DATE.match(str(v)):
                raise Refus(f"{c['nom']} : une date AAAA-MM-JJ (ou AAAA-MM-JJ HH:MM)")
        elif c["type"] == "choix":
            if str(v) not in c["choix"]:
                raise Refus(f"{c['nom']} : parmi {c['choix']}")
        elif c["type"] == "oui_non":
            v = bool(v) if isinstance(v, bool) else str(v).strip().lower() in ("oui", "true", "1", "vrai")
        else:
            v = str(v)[:TEXTE_MAX]
        propres[c["nom"]] = v
    o = {"id": secrets.token_hex(4), "ts": round(now or time.time(), 1), "auteur": auteur, "valeurs": propres}
    return _ajouter(t, o, entrees)


def clore(nom, eid, note="", auteur="hakim", dossier=None, entrees=None, now=None):
    t = _type_valide(nom, dossier)
    if not any(e.get("id") == eid and "clot" not in e for e in _lire(nom, entrees)):
        raise Refus(f"aucune entrée {eid} dans « {nom} »")
    o = {"id": secrets.token_hex(4), "ts": round(now or time.time(), 1), "auteur": auteur, "clot": eid, "note": str(note)[:500]}
    return _ajouter(t, o, entrees)


def lire(nom, n=20, filtre="", dossier=None, entrees=None):
    _type_valide(nom, dossier)
    tout = _lire(nom, entrees)
    if filtre:
        f = filtre.lower()
        tout = [e for e in tout if f in json.dumps(e, ensure_ascii=False).lower()]
    return tout[-max(1, int(n)):]


def verifier_chaine(nom, dossier=None, entrees=None):
    """None si la chaîne tient (ou si le carnet n'est pas chaîné), sinon le rang de la première entrée retouchée."""
    t = _type_valide(nom, dossier)
    if not t["lois"].get("chaine"):
        return None
    prec = None
    for i, e in enumerate(_lire(nom, entrees)):
        corps = {k: v for k, v in e.items() if k not in ("prec", "empreinte")}
        if e.get("prec") != prec or e.get("empreinte") != _empreinte(prec, corps):
            return i
        prec = e.get("empreinte")
    return None


def echeances(now=None, dossier=None, entrees=None):
    """[(nom, entrée)] : les entrées dont la date d'échéance est passée et qui ne sont pas closes."""
    now, out = now or time.time(), []
    for nom, t in types(dossier).items():
        champ = (t.get("lois") or {}).get("echeance")
        if t.get("etat") != "validee" or not champ:
            continue
        tout = _lire(nom, entrees)
        closes = {e.get("clot") for e in tout if e.get("clot")}
        for e in tout:
            d = (e.get("valeurs") or {}).get(champ)
            if not d or e.get("id") in closes:
                continue
            try:
                quand = time.mktime(time.strptime(d, "%Y-%m-%d %H:%M" if " " in d else "%Y-%m-%d"))
            except ValueError:
                continue
            if quand <= now:
                out.append((nom, e))
    return out


def demarrage(now=None, dossier=None, entrees=None):
    """Le texte du briefing : les carnets « relu_au_demarrage » (3 dernières entrées) et toutes les échéances passées."""
    lignes = []
    for nom, t in types(dossier).items():
        if t.get("etat") != "validee" or not (t.get("lois") or {}).get("relu_au_demarrage"):
            continue
        for e in [x for x in _lire(nom, entrees) if "valeurs" in x][-3:]:
            lignes.append(f"{nom} · {time.strftime('%d/%m', time.localtime(e['ts']))} · "
                          + " ; ".join(f"{k} : {v}" for k, v in e["valeurs"].items())[:300])
    for nom, e in echeances(now, dossier, entrees):
        lignes.append(f"ÉCHÉANCE PASSÉE · {nom} · {e['id']} · " + " ; ".join(f"{k} : {v}" for k, v in e["valeurs"].items())[:300]
                      + " (clos-la avec carnet_clore quand c'est réglé)")
    return "\n".join(lignes)


def bilan(depuis, dossier=None, entrees=None):
    """{nom: nombre d'entrées depuis `depuis`} pour les carnets validés qui comptent au bilan."""
    return {nom: sum(1 for e in _lire(nom, entrees) if "valeurs" in e and e.get("ts", 0) >= depuis)
            for nom, t in types(dossier).items() if t.get("etat") == "validee" and (t.get("lois") or {}).get("bilan")}
