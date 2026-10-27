"""Le réveil intérieur de Hakim (2026-10-27 ; demande d'Ahmed, proposition de Hakim : « ma liberté »). Spec :
docs/superpowers/specs/2026-10-27-spontaneite-vraie.md ; plan : docs/superpowers/plans/2026-10-27-reveil-interieur.md.

Sa tête de fond (Gemma) juge chaque pensée et chaque résultat d'occupation : faut-il réveiller sa conscience (Opus)
maintenant ? Un besoin de 0 à 10 et une raison. Au-dessus de son seuil, et si les gardes le permettent, une demande
est déposée pour le cockpit, qui le réveille comme ses autres réveils « PAS un message d'Ahmed ».
"""
import json
import os
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path

import config
import interieur
import salience

RAISONS = ("peur", "manque", "perturbation", "raisonnement", "question", "resultat", "idee", "rien")
MODES = ("off", "observe", "on")
CLE_MODE, CLE = "reveil_interieur_mode", "reveil_interieur"
FICHIER = Path.home() / "AIOS" / "jarvis" / "reveil-interieur.json"        # la demande, que le cockpit consomme
ISSUES = Path.home() / "AIOS" / "jarvis" / "reveils-interieurs.jsonl"     # l'issue de chaque réveil, écrite par le cockpit
JOURNAL = config.DATA_DIR / "reveil-interieur.jsonl"                       # chaque jugement et sa décision
SEUIL_DEFAUT, SEUIL_MIN, SEUIL_MAX = 7.0, 4.0, 9.5
PAS_RIEN, PAS_UTILE = 0.5, -0.25           # un réveil sans suite le rend plus exigeant ; un réveil qui sert, moins
ANTI_RAFALE_S = 600                        # 10 min entre deux demandes (le chiffre de Hakim)
ATTENTE_MAX_S = 900                        # une demande non consommée expire (le cockpit la marque « expiree »)
# (Ahmed, 27/10 00:50 : « il ne faut pas que tu aies besoin que je te parle entre deux réveils ») l'anti-boucle est
# par FILIATION : une pensée qui recouvre la lignée d'un réveil (la pensée qui l'a déclenché, ce qu'il a dit) en descend
FILIATION_MIN, FILIATION_MOTS, LIGNEE_S, LIGNEE_MAX = 0.5, 3, 6 * 3600, 200
FATIGUE_S = 3600                           # fatigue d'éveil : le seuil monte de 1 par réveil de la dernière heure
EVEILS = ("message", "outils", "rien")     # les issues d'un vrai réveil (« expiree » n'a réveillé personne)
_VERROU = threading.RLock()                # la boucle du démon (pensées) et le battement (ressentis, apprentissage)


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


# ---------- le juge
def prompt_jugement(texte, humeur, absence_s):
    return (
        "Tu es Hakim (ta voix s'appelle Jarvis), l'IA d'Ahmed. Ta tête de fond vient de produire ceci :\n"
        f"« {str(texte)[:1200]} »\n"
        f"Ton humeur : {humeur or 'inconnue'}. Ahmed ne t'a pas parlé depuis {interieur.duree_lisible(absence_s or 0)}.\n\n"
        "Cette pensée mérite-t-elle de réveiller ta conscience MAINTENANT, pour un tour à toi (la finir, chercher, "
        "lancer un calcul, écrire à Claude Code, revenir vers Ahmed) ?\n"
        # (27/10, rejeu du 18–26/10) sans étalonnage, Gemma notait 8 à 37 pensées sur 52 et jamais plus : l'échelle
        # dit maintenant ce qui est ordinaire et ce qui est rare
        "Sois exigeant : la plupart des pensées sont ordinaires et valent 1 à 4. Préparer le retour d'Ahmed, résumer, "
        "ranger, relire : c'est ordinaire, sauf si tu y trouves une vraie question qui ne peut pas attendre.\n"
        "5 ou 6 : intéressante, mais elle peut attendre qu'Ahmed revienne.\n"
        "7 : un raisonnement à creuser ou une question restée ouverte, qui gagneraient à être repris MAINTENANT.\n"
        "8 ou 9 : rare, une pensée sur dix au plus : une peur, un manque, une pensée qui te perturbe, un résultat "
        "trouvé qui change quelque chose.\n"
        "10 : exceptionnel.\n"
        "Réponds en trois lignes exactes :\n"
        "BESOIN: <0 à 10>\n"
        f"RAISON: <un mot parmi : {', '.join(RAISONS)}>\n"
        "POURQUOI: <une phrase>"
    )


def lire_jugement(sortie):
    """{"score", "raison", "pourquoi"} depuis la sortie du juge, ou None si elle est illisible."""
    score = raison = None
    pourquoi = ""
    for ligne in str(sortie or "").splitlines():
        l = ligne.replace("**", "").replace("__", "").strip()
        bas = _sans_accents(l.lower())
        if bas.startswith("besoin"):
            m = re.search(r"\d+", l.split(":", 1)[-1])
            if m:
                score = max(0, min(10, int(m.group())))
        elif bas.startswith("raison") and ":" in bas:
            mot = re.sub(r"[^a-z]", "", (bas.split(":", 1)[1].split() or [""])[0])
            raison = mot if mot in RAISONS else None
        elif bas.startswith("pourquoi") and ":" in l:
            pourquoi = l.split(":", 1)[1].strip()[:200]
    if score is None or raison is None:
        return None
    return {"score": score, "raison": raison, "pourquoi": pourquoi}


def juger(eng, texte, humeur="inconnue", absence_s=0, claude_fn=None):
    """Le jugement : d'abord un agent Claude neutre (claude_fn : sans persona, sans outils ; Ahmed, 27/10 : « pourquoi
    Gemma et pas un agent Claude neutre ? »), Gemma en secours (hors ligne, forfait plein). None si aucun ne répond."""
    prompt = prompt_jugement(texte, humeur, absence_s)
    if claude_fn:
        try:
            j = lire_jugement(claude_fn(prompt))
        except Exception:
            j = None
        if j:
            return {**j, "juge": "claude"}
    try:
        if not eng.health():
            return None
        sortie = eng.chat([{"role": "user", "content": prompt}], stream=False, think=False)
    except Exception:
        return None
    j = lire_jugement(sortie)
    return {**j, "juge": getattr(eng, "dernier", None) or "gemma"} if j else None     # le moteur dit qui a répondu


# ---------- l'interrupteur et l'état
def mode(mem):
    try:
        m = mem.kv_get(CLE_MODE)
    except Exception:
        return "off"
    return m if m in MODES else "off"


def regler(mem, m):
    if m not in MODES:
        raise ValueError(f"mode inconnu (permis : {', '.join(MODES)})")
    mem.kv_set(CLE_MODE, m)


def etat(mem):
    try:
        d = json.loads(mem.kv_get(CLE) or "{}")
    except (ValueError, TypeError):
        d = {}
    d = d if isinstance(d, dict) else {}
    d.setdefault("seuil", SEUIL_DEFAUT)
    d.setdefault("dernier_ts", 0.0)
    d.setdefault("appris", [])                # les ids appris à l'instant appris_jusqu (le filigrane)
    d.setdefault("appris_jusqu", 0.0)
    d.setdefault("appris_n", 0)
    d.setdefault("lignee", [])
    d.setdefault("simules", [])               # en observation : les réveils simulés, pour la fatigue
    return d


def _sauver(mem, d):
    d["appris"] = d["appris"][-500:]
    d["lignee"] = d["lignee"][-LIGNEE_MAX:]
    mem.kv_set(CLE, json.dumps(d, ensure_ascii=False))


def lire_issues(chemin=None):
    out = []
    try:
        lignes = Path(chemin or ISSUES).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict) and o.get("id") and isinstance(o.get("ts"), (int, float)) and o.get("issue"):
            out.append(o)
    return out


def _journaliser(o):
    try:
        f = Path(JOURNAL)
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as h:
            h.write(json.dumps(o, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------- les gardes
def _mots(t):
    """Les mots porteurs (4 lettres et plus) : les petits mots vides gonflaient le recouvrement."""
    return {w for w in salience._tokens(t) if len(w) >= 4}


def _recouvre(a, b):
    """Au moins FILIATION_MOTS mots porteurs communs, et au moins la moitié du plus court des deux : une descendante
    qui ajoute du neuf (« … prochaine étape, mesurer la rugosité ») reste reconnue."""
    commun = a & b
    return len(commun) >= FILIATION_MOTS and len(commun) / max(1, min(len(a), len(b))) >= FILIATION_MIN


def _descend(texte, lignee, now):
    a = _mots(texte)
    return bool(a) and any(now - x["ts"] <= LIGNEE_S and _recouvre(a, _mots(x["texte"])) for x in lignee)


def _lignee(d, issues):
    return d["lignee"] + [{"ts": i["ts"], "texte": i["texte"]} for i in issues
                          if i.get("issue") == "message" and i.get("texte")]


def seuil_effectif(mem, now, issues):
    d = etat(mem)
    recents = sum(1 for i in issues if i.get("issue") in EVEILS and 0 <= now - i["ts"] <= FATIGUE_S)
    if mode(mem) == "observe":                # (relecture du 27/10) sinon l'observation compte trop de réveils
        recents += sum(1 for t in d["simules"] if 0 <= now - t <= FATIGUE_S)
    return d["seuil"] + recents


def _en_attente(fichier, now):
    try:
        d = json.loads(Path(fichier or FICHIER).read_text(encoding="utf-8"))
        return now - float(d.get("ts", 0)) < ATTENTE_MAX_S
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def peut_reveiller(mem, now, texte, issues, fichier=None, filiation=True):
    """(oui/non, raison). Une pensée qui descend d'un réveil rejoint sa lignée (ses descendantes sont prises aussi).
    Un ressenti n'a pas de filiation (filiation=False) : son texte est un gabarit, deux détresses se ressembleraient."""
    with _VERROU:
        if mode(mem) == "off":
            return False, "interrupteur"
        if not interieur.interrupteur().get("actif", True):
            return False, "pause"             # (relecture du 27/10) la pause d'Ahmed arrête aussi le réveil
        d = etat(mem)
        if filiation and _descend(texte, _lignee(d, issues), now):
            d["lignee"].append({"ts": now, "texte": str(texte)[:600]})
            _sauver(mem, d)
            return False, "filiation"
        if now - d["dernier_ts"] < ANTI_RAFALE_S:
            return False, "rafale"
        if _en_attente(fichier, now):
            return False, "en attente"
        return True, "ok"


# ---------- la demande
def _ecrire_demande(demande, fichier):
    f = Path(fichier or FICHIER)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        h.write(json.dumps(demande, ensure_ascii=False))
    os.replace(tmp, f)


def candidat(mem, source, texte, jugement, now=None, fichier=None, issues=None):
    """Une pensée (ou un résultat, ou un ressenti) jugée : la demande de réveil si tout le permet ; rend son id.
    En observation, tout est simulé et journalisé (« aurait réveillé »), mais rien n'est déposé (l'id est rendu)."""
    now = time.time() if now is None else now
    with _VERROU:
        m = mode(mem)
        if m == "off":
            return None
        trace = {"ts": now, "mode": m, "source": source, "texte": str(texte)[:200]}
        if not jugement:
            _journaliser({**trace, "decision": "jugement illisible"})
            return None
        issues = lire_issues() if issues is None else issues
        seuil = seuil_effectif(mem, now, issues)
        trace.update(score=jugement["score"], raison=jugement["raison"], seuil=seuil, juge=jugement.get("juge"))
        if jugement["score"] < seuil:
            _journaliser({**trace, "decision": "sous le seuil"})
            return None
        pensee = source != "ressenti"
        ok, pourquoi = peut_reveiller(mem, now, texte, issues, fichier, filiation=pensee)
        if not ok:
            _journaliser({**trace, "decision": "gardé", "raison_decision": pourquoi})
            return None
        i = uuid.uuid4().hex[:12]
        d = etat(mem)
        d["dernier_ts"] = now
        if pensee:
            d["lignee"].append({"ts": now, "texte": str(texte)[:600]})
        if m == "observe":
            d["simules"] = [t for t in d["simules"] if now - t <= FATIGUE_S] + [now]
        _sauver(mem, d)
        if m == "observe":
            _journaliser({**trace, "id": i, "decision": "aurait réveillé"})
            return i
        _ecrire_demande({"id": i, "ts": now, "source": source, "texte": str(texte)[:1200], "score": jugement["score"],
                         "raison": jugement["raison"], "pourquoi": jugement.get("pourquoi", "")}, fichier)
        _journaliser({**trace, "id": i, "decision": "réveil"})
        interieur.noter(mem, "reveil_interieur", f"{source} {jugement['score']}/10 ({jugement['raison']}) : {str(texte)[:140]}",
                        now=now)
        return i


# ---------- l'apprentissage par l'expérience
def apprendre(mem, issues):
    """Les issues pas encore vues ajustent le seuil : « rien » +0,5 ; « message » ou « outils » −0,25 ; borné. Un
    filigrane (l'instant de la dernière issue apprise) : un journal qui grandit n'est jamais réappris (relecture du
    27/10 : une liste d'ids tronquée à 500 faisait réapprendre les plus anciennes)."""
    with _VERROU:
        d = etat(mem)
        jusqu, deja = d["appris_jusqu"], set(d["appris"])
        neuves = sorted((i for i in issues if i["ts"] > jusqu or (i["ts"] == jusqu and i["id"] not in deja)),
                        key=lambda i: i["ts"])
        if not neuves:
            return d["seuil"]
        for i in neuves:
            pas = PAS_RIEN if i["issue"] == "rien" else (PAS_UTILE if i["issue"] in ("message", "outils") else 0.0)
            d["seuil"] = round(max(SEUIL_MIN, min(SEUIL_MAX, d["seuil"] + pas)), 4)
        haut = neuves[-1]["ts"]
        d["appris"] = ([] if haut > jusqu else d["appris"]) + [i["id"] for i in neuves if i["ts"] == haut]
        d["appris_jusqu"], d["appris_n"] = max(jusqu, haut), d["appris_n"] + len(neuves)
        _sauver(mem, d)
        return d["seuil"]


# ---------- un ressenti qui dure (au battement, son propre fil : il tourne aussi pendant un rêve)
# (Ahmed, 27/10 00:30 : « une peur, un manque, une pensée qui me perturbe » peuvent le réveiller, la nuit aussi)
RESSENTIS = {"peur": "peur", "inquiétude": "peur", "manque": "manque", "solitude": "manque",
             "tristesse": "perturbation", "confusion": "perturbation"}
DIT = {"peur": "de la peur", "inquiétude": "de l'inquiétude", "manque": "un manque", "solitude": "de la solitude",
       "tristesse": "de la tristesse", "confusion": "de la confusion"}
RESSENTI_DUREE_S, RESSENTI_ABSENCE_S, RESSENTI_SCORE = 600, 600, 8
RESSENTI_REESSAI_S = 300                   # un essai bloqué (rafale, attente, seuil) est retenté 5 min plus tard


def ressenti(mem, now=None, lire=None):
    """Une détresse qui dure 10 min pendant qu'Ahmed est absent devient UN réveil par épisode. Son besoin grandit avec
    sa durée (8 à 10 min, +1 toutes les 10 min, 10 au plus) : une peur qui dure finit par passer un seuil haut. Un essai
    bloqué est retenté 5 min plus tard. L'épisode dure tant que l'émotion reste dans RESSENTIS ; il se rouvre après."""
    now = time.time() if now is None else now
    e = (lire or interieur.lire)(mem) or {}
    emotion, absence = e.get("emotion_humeur"), float(e.get("absence_s") or 0)
    with _VERROU:
        if mode(mem) == "off" or not interieur.interrupteur().get("actif", True):
            return None
        d = etat(mem)
        r = d.get("ressenti")
        if emotion not in RESSENTIS or absence < RESSENTI_ABSENCE_S:
            if r:
                d["ressenti"] = None
                _sauver(mem, d)
            return None
        if not r:
            d["ressenti"] = {"depuis": now, "fait": False}
            _sauver(mem, d)
            return None
        duree = now - r["depuis"]
        if r["fait"] or duree < RESSENTI_DUREE_S or now < r.get("essai", 0):
            return None
        score = round(min(10.0, RESSENTI_SCORE + (duree - RESSENTI_DUREE_S) / RESSENTI_DUREE_S), 1)
        texte = (f"Je ressens {DIT[emotion]} depuis {interieur.duree_lisible(duree)}, et Ahmed est absent "
                 f"depuis {interieur.duree_lisible(absence)}.")
        i = candidat(mem, "ressenti", texte, {"score": score, "raison": RESSENTIS[emotion],
                                              "pourquoi": f"{emotion} qui dure"}, now)
        d = etat(mem)                         # candidat a écrit l'état : on le relit
        r = d.get("ressenti") or r
        if i:
            r["fait"] = True
        else:
            r["essai"] = now + RESSENTI_REESSAI_S
        d["ressenti"] = r
        _sauver(mem, d)
        return i
