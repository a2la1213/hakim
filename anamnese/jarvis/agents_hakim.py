"""Ses agents (architecte, codeur, juge… lancés avec l'outil Task) : les lister, en arrêter un (demande de Hakim, accord
d'Ahmed, 2026-10-23). Le cockpit tient la liste de ceux qui tournent (agents-en-cours.json) et fait l'arrêt lui-même :
cet outil n'écrit qu'une demande (agents-arreter.jsonl), que le cockpit lit, puis attend sa réponse (agents-arrets.jsonl).
Seuls SES agents peuvent être arrêtés : ceux de la liste. Ahmed voit chaque arrêt dans Parler.

Leur vie (29/10, Ahmed : « on ne les tue pas, on les met en sommeil », « chaque agent choisit son nom », « un juge ne
peut plus juger le même travail », « il faudra qu'il puisse être récompensé ») : le cockpit tient leur registre
(registre-agents.json : travaille, dort, parti, arrete, coupe) ; ce module tient leurs fiches (agents-fiches.json :
prénom, travaux jugés, trouvailles confirmées), que la garde de SendMessage (cockpit/garde-message.js) lit aussi.
"""
import fcntl
import json
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))


def _agents(dossier=None):
    try:
        d = json.loads((Path(dossier or JARVIS) / "agents-en-cours.json").read_text(encoding="utf-8"))
        return d.get("agents", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def lister(dossier=None, maintenant=None):
    if _registre(dossier)[0]:
        return lister_vies(dossier)
    l = _agents(dossier)
    if not l:
        return "Aucun de tes agents ne tourne."
    maintenant = time.time() if maintenant is None else maintenant
    lignes = []
    for a in l:
        depuis = f", depuis {round((maintenant - a['ts'] / 1000) / 60)} min" if a.get("ts") else ""
        lignes.append(f"- {a.get('id')} : « {a.get('description', '?')} » (agent {a.get('type') or '?'}{depuis})")
    return "Tes agents en cours :\n" + "\n".join(lignes)


def trouver(agent, dossier=None):
    """L'agent désigné par son numéro, ou par sa description (exacte, sinon le seul qui la contient)."""
    l = _agents(dossier)
    a = str(agent or "").strip()
    exact = [x for x in l if x.get("id") == a or str(x.get("description", "")).casefold() == a.casefold()]
    if exact:
        return exact[0]
    proches = [x for x in l if a and a.casefold() in str(x.get("description", "")).casefold()]
    return proches[0] if len(proches) == 1 else None


def demander_arret(agent, raison, dossier=None, attente_s=6.0, pas_s=0.3):
    d = Path(dossier or JARVIS)
    a = trouver(agent, d)
    if not a:
        return f"Je ne trouve pas « {agent} » parmi tes agents en cours.\n{lister(d)}"
    if not str(raison or "").strip():
        return "Donne une raison : elle est notée dans le journal, et Ahmed la voit dans Parler."
    demande = uuid.uuid4().hex[:12]
    with (d / "agents-arreter.jsonl").open("a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "id": a["id"], "raison": str(raison)[:300], "demande": demande},
                           ensure_ascii=False) + "\n")
    fin = time.time() + attente_s
    while time.time() < fin:
        try:
            for l in (d / "agents-arrets.jsonl").read_text(encoding="utf-8").splitlines()[-50:]:
                o = json.loads(l)
                if o.get("demande") == demande:
                    return (f"Agent « {a.get('description')} » arrêté ; Ahmed le voit dans Parler." if o.get("ok")
                            else f"Arrêt impossible : {o.get('erreur')}")
        except (OSError, ValueError):
            pass
        time.sleep(pas_s)
    return f"Demande d'arrêt envoyée pour « {a.get('description')} », sans confirmation du cockpit pour l'instant."


# ---- leur vie (29/10)

PRENOMS_INTERDITS = {"ahmed", "hakim", "maman", "papa", "claude", "jarvis", "gemma", "opus", "sonnet", "fable", "haiku",
                     "anthropic", "dieu", "allah", "agent", "juge", "codeur", "architecte"}
_PRENOM = re.compile(r"[^\W\d_](?:[^\W\d_]|[ '’-](?=[^\W\d_]))+")
# une nouvelle version d'un travail reste le même travail
_VERSION = re.compile(r"(?:\s+(?:v\s?\d+|version\s*\d+|bis|ter|corrigee?s?|revue?s?|nouvelle version|reprise))+$")
_ETATS = {"travaille": "au travail", "dort": "endormi", "parti": "parti de lui-même", "arrete": "arrêté", "coupe": "coupé"}


try:                                                # les sosies (cyrillique, grec…) de la sentinelle
    from immunite import _SOSIES
except Exception:                                   # noqa: BLE001
    _SOSIES = {}


def _plat(texte):
    """(relecture Opus) toutes les écritures gardées (arabe, hébreu…), accents retirés, sosies ramenés au latin."""
    t = unicodedata.normalize("NFKD", str(texte or "")).casefold()
    t = "".join(c for c in t if not unicodedata.combining(c)).translate(_SOSIES)
    return re.sub(r"[\W_]+", " ", t).strip()


def _ecritures(texte):
    """Les écritures des lettres d'un prénom (LATIN, ARABIC, CYRILLIC…) : un prénom n'en mélange pas deux."""
    return {unicodedata.name(c, "?").split()[0] for c in str(texte) if c.isalpha()}


class _Illisible(Exception):
    pass


def _registre(dossier=None):
    try:
        d = json.loads((Path(dossier or JARVIS) / "registre-agents.json").read_text(encoding="utf-8"))
        a = d.get("agents") if isinstance(d, dict) else None
        return (a if isinstance(a, dict) else {}), (d.get("session_courante") if isinstance(d, dict) else None)
    except (OSError, ValueError):
        return {}, None


def _lire_fiches(d, strict=False):
    """strict (avant d'écrire) : une fiche illisible n'est jamais écrasée (relecture Opus : elle effaçait les prénoms,
    les travaux jugés et les récompenses)."""
    try:
        f = json.loads((Path(d) / "agents-fiches.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        if strict:
            raise _Illisible()
        return {}
    a = f.get("agents") if isinstance(f, dict) else None
    if not isinstance(a, dict) and strict:
        raise _Illisible()
    return a if isinstance(a, dict) else {}


def _changer_fiches(d, changer):
    """changer(fiches) -> réponse ; sous verrou, écrit en entier ou pas du tout."""
    d = Path(d)
    with open(d / "agents-fiches.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        try:
            fiches = _lire_fiches(d, strict=True)
        except _Illisible:
            return ("Refusé : la fiche de tes agents (agents-fiches.json) est illisible ; je n'écris rien par-dessus. "
                    "Dis-le à Ahmed ou à Claude Code.")
        reponse = changer(fiches)
        if not reponse.startswith("Refusé"):
            tmp = d / f"agents-fiches.json.{os.getpid()}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as h:
                json.dump({"agents": fiches, "maj_ms": int(time.time() * 1000)}, h, ensure_ascii=False)
                h.flush()
                os.fsync(h.fileno())
            os.replace(tmp, d / "agents-fiches.json")
        return reponse


def trouver_au_registre(agent, dossier=None):
    """Un agent du registre par son numéro, son prénom, ou sa description (exacte, sinon la seule qui la contient)."""
    d = Path(dossier or JARVIS)
    agents, _ = _registre(d)
    fiches = _lire_fiches(d)
    a = str(agent or "").strip()
    if a in agents:
        return agents[a]
    cle = _plat(a)
    if not cle:
        return None
    exact = [x for i, x in agents.items() if _plat(fiches.get(i, {}).get("prenom_base", "")) == cle
             or _plat(x.get("description", "")) == cle]
    if exact:
        return exact[0]
    proches = [x for x in agents.values() if cle in _plat(x.get("description", ""))]
    return proches[0] if len(proches) == 1 else None


def _nom(fiche, a):
    return fiche.get("prenom") or f"l'agent « {a.get('description', '?')} »"


def nommer(agent, prenom, dossier=None, avec_naissance=False):
    """Le prénom qu'un agent a choisi (d'homme ou de femme), tous différents. avec_naissance : quand tous les prénoms
    sont épuisés, un prénom déjà porté revient avec sa date de naissance (« Léa du 29/10/2026 à 16:04 »)."""
    d = Path(dossier or JARVIS)
    a = trouver_au_registre(agent, d)
    if not a:
        return f"Refusé : je ne trouve pas « {agent} » parmi tes agents (agents_lister)."
    p = unicodedata.normalize("NFC", str(prenom or "").strip())
    if not (2 <= len(p) <= 30 and _PRENOM.fullmatch(p)) or len(_ecritures(p)) != 1:
        return ("Refusé : un prénom, ce sont des lettres d'une seule écriture (avec au plus une espace, un tiret ou une "
                "apostrophe entre elles), de 2 à 30.")
    try:
        reserves = {_plat(x) for x in json.loads((d / "prenoms-reserves.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError, TypeError):
        reserves = set()
    if _plat(p) in PRENOMS_INTERDITS | reserves:
        return f"Refusé : « {p} » est réservé (la famille, ou un nom qui prêterait à confusion). Propose-lui trois autres prénoms."
    agents, _ = _registre(d)

    def changer(fiches):
        f = fiches.setdefault(a["id"], {})
        if f.get("prenom"):
            return f"Refusé : il s'appelle déjà {f['prenom']}, et garde le prénom qu'il a choisi."
        pris = [i for i, x in fiches.items() if i != a["id"] and x.get("prenom_base") and _plat(x["prenom_base"]) == _plat(p)]
        nom = p
        if pris and not avec_naissance:
            autre = agents.get(pris[0], {})
            return (f"Refusé : {p} est déjà porté (l'agent « {autre.get('description', '?')} »). "
                    "Propose-lui trois autres prénoms, il en choisit un.")
        if pris:
            ne = datetime.fromtimestamp((a.get("ne_ms") or time.time() * 1000) / 1000)
            nom = f"{p} du {ne.strftime('%d/%m/%Y à %H:%M')}"
        f.update(prenom=nom, prenom_base=p)
        return f"C'est noté : l'agent « {a.get('description', '?')} » s'appelle {nom}."
    return _changer_fiches(d, changer)


def _cle_travail(dossier):
    return _VERSION.sub("", _plat(dossier)).strip()


def juger(agent, dossier, dossier_jarvis=None, maintenant=None):
    """Déclare le travail qu'un juge va juger. Un juge ne juge jamais deux fois le même travail (une nouvelle version
    compte comme le même). Pour réveiller un juge endormi, la garde de SendMessage exige un travail déclaré ainsi."""
    d = Path(dossier_jarvis or JARVIS)
    a = trouver_au_registre(agent, d)
    if not a:
        return f"Refusé : je ne trouve pas « {agent} » parmi tes agents (agents_lister)."
    if a.get("type") != "juge":
        return f"Refusé : « {a.get('description', '?')} » n'est pas un juge."
    libelle = re.sub(r"\s+", " ", str(dossier or "")).strip()[:200]
    cle = _cle_travail(libelle)
    if len(cle) < 2:
        return "Refusé : nomme le travail à juger (son nom, pas sa version : « portée par contact », pas « … v2 »)."
    ts_ms = int((time.time() if maintenant is None else maintenant) * 1000)

    def changer(fiches):
        f = fiches.setdefault(a["id"], {})
        deja = [x for x in f.get("dossiers", []) if x.get("cle") == cle]
        if deja:
            return (f"Refusé : {_nom(f, a)} a déjà jugé « {deja[0].get('libelle')} ». Un juge ne juge jamais deux fois le même "
                    "travail : choisis un autre juge, ou lances-en un neuf.")
        f.setdefault("dossiers", []).append({"cle": cle, "libelle": libelle, "ts_ms": ts_ms})
        etat = "il travaille : écris-lui avec SendMessage" if a.get("etat") == "travaille" else "réveille-le maintenant avec SendMessage"
        return f"C'est noté : {_nom(f, a)} juge « {libelle} » ; {etat} (son numéro : {a['id']})."
    return _changer_fiches(d, changer)


def trouvaille(agent, quoi, confirmee_par, dossier=None, rien_a_signaler=False):
    """Sa récompense : une trouvaille CONFIRMÉE ensuite (par un test, par Ahmed, par le résultat), ou un « rien à
    signaler » juste. Rien de ce qui n'est pas confirmé ne compte : sinon on élève un juge qui invente."""
    d = Path(dossier or JARVIS)
    a = trouver_au_registre(agent, d)
    if not a:
        return f"Refusé : je ne trouve pas « {agent} » parmi tes agents (agents_lister)."
    q, par = str(quoi or "").strip()[:300], str(confirmee_par or "").strip()[:100]
    if not q or not par:
        return "Refusé : dis ce qui a été trouvé, et qui l'a confirmé (un test, Ahmed, le résultat)."

    def changer(fiches):
        f = fiches.setdefault(a["id"], {})
        f.setdefault("trouvailles", []).append({"quoi": q, "confirmee_par": par, "rien_a_signaler": bool(rien_a_signaler),
                                                "ts_ms": int(time.time() * 1000)})
        return f"C'est noté. {_nom(f, a)} : {_palmares(f)}."
    return _changer_fiches(d, changer)


def _palmares(f):
    t = f.get("trouvailles", [])
    n, r = sum(1 for x in t if not x.get("rien_a_signaler")), sum(1 for x in t if x.get("rien_a_signaler"))
    morceaux = [f"{n} trouvaille{'s' if n > 1 else ''} confirmée{'s' if n > 1 else ''}"]
    if r:
        morceaux.append(f"{r} « rien à signaler » juste{'s' if r > 1 else ''}")
    j = len(f.get("dossiers", []))
    if j:
        morceaux.append(f"{j} travail jugé" if j == 1 else f"{j} travaux jugés")
    return ", ".join(morceaux)


def lister_vies(dossier=None, n=30):
    d = Path(dossier or JARVIS)
    agents, session = _registre(d)
    fiches = _lire_fiches(d)
    groupes = {"travaille": [], "dort": [], "ancien": [], "parti": [], "autre": []}
    for a in sorted(agents.values(), key=lambda x: -(x.get("ne_ms") or 0))[:n]:
        f = fiches.get(a.get("id"), {})
        ne = datetime.fromtimestamp((a.get("ne_ms") or 0) / 1000).strftime("%d/%m à %H:%M")
        ligne = (f"- {f.get('prenom') or '(sans prénom)'} — {a.get('id')} : « {a.get('description', '?')} » "
                 f"(agent {a.get('type', '?')}, né le {ne} ; {_palmares(f)})")
        etat = a.get("etat")
        if etat == "parti":
            groupes["parti"].append(ligne + f" : « {a.get('depart', '')} »")
        elif etat in ("travaille", "dort", "coupe") and session and a.get("session") != session:
            groupes["ancien"].append(ligne)
        elif etat in ("travaille", "dort"):
            groupes[etat].append(ligne)
        elif etat == "coupe":                       # mort avec son cerveau : il se réveille (Hakim l'a fait le 29/10)
            groupes["dort"].append(ligne + " (coupé par un redémarrage)")
        else:
            groupes["autre"].append(ligne + f" ({_ETATS.get(etat, etat)})")
    titres = {"travaille": "Au travail (tes messages leur arrivent entre deux étapes)",
              "dort": "Endormis, réveillables avec SendMessage (leur numéro)",
              "ancien": "Endormis dans une ancienne conversation (plus joignables depuis l'allègement)",
              "parti": "Partis d'eux-mêmes (on ne les réveille plus)", "autre": "Arrêtés (plus réveillables)"}
    blocs = [f"{titres[k]} :\n" + "\n".join(v) for k, v in groupes.items() if v]
    return "\n\n".join(blocs) if blocs else "Aucun agent au registre."
