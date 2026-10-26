"""Chaque échange avec Ahmed est mémorisé, automatiquement (demande d'Ahmed, 2026-10-20 : « de façon automatique,
légère et efficace, tout s'encre et soit mémorisé pour chaque échange ; c'est la consolidation qui fait qu'un
souvenir disparaît ou reste ; une couche d'attention et d'intérêt qui encre le souvenir plus ou moins fort ;
sans que je doive lui dire de mémoriser et sans qu'il me demande l'autorisation » — Hakim avait oublié qu'ils
étaient en live, parce qu'il n'avait rien mémorisé).

- Le cockpit dépose chaque échange (message d'Ahmed + réponse de Hakim, ou ce que Hakim dit de lui-même) dans
  une file : ~/AIOS/jarvis/echanges-a-memoriser.jsonl (ajout seul) — jamais bloquant pour la conversation.
- Le démon la lit à chaque passage : un souvenir ÉPISODIQUE par échange (court : le texte entier reste dans
  le journal brut), avec son embedding, routé dans sa rubrique, estampillé de l'humeur du moment.
- L'ATTENTION fixe la force d'encrage (l'importance, 0,2 à 0,95) : une demande explicite (« retiens »,
  « n'oublie pas »), les proches, les événements de la vie (un live, un rendez-vous, la santé), une
  décision, l'émotion, la nouveauté (loin de ce qu'il sait déjà), la longueur. Ensuite, comme pour tout
  souvenir, l'oubli et le renforcement font leur travail : la consolidation de nuit distille ce qui compte,
  ce qui n'est jamais rappelé s'efface du rappel, ce qui est rappelé se renforce.
- Aucun modèle de langage : quelques millisecondes par échange (embedding model2vec).
"""
import json
import math
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import config

FILE = Path.home() / "AIOS" / "jarvis" / "echanges-a-memoriser.jsonl"
CLE_CURSEUR = "echanges_curseur"
TEXTE_MAX = 600                       # par côté ; le texte entier reste dans le journal brut
ROUTAGE_CONF_MIN = 0.70               # (2026-10-21) un échange mal reconnu reste sans rubrique (pas d'aimant) ; le
                                      # rangement de nuit (ranger_nuit.py) le lit et le range au bon endroit
PAR_PASSAGE = 200
AGE_EMOTION_MAX_S = 10 * 60                  # (26/10) au-delà, un message ne déclenche plus d'émotion (voir _emotion)

_EXPLICITE = re.compile(r"\b(retiens|retenir|n'?oublie (pas|jamais)|souviens[- ]toi|rappelle[- ]toi|m[ée]moris\w*|"
                        r"c'est (tr[eè]s )?important|note bien|garde ([çc]a )?en (t[eê]te|m[ée]moire)|pour plus tard)\b", re.I)
_PROCHES = re.compile(r"\b(maman|ma m[eè]re|mon p[eè]re|papa|ma fille|mon fils|mes enfants|ma femme|mon fr[eè]re|"
                      r"ma s(œ|oe)ur|ma famille|mes parents|mon pote|mon ami)\b", re.I)
# Les PRÉNOMS des proches ne sont pas dans le code (dépôt public, 2026-10-21) : un par ligne dans data/proches.txt,
# local, jamais versionné.
PROCHES_FICHIER = config.DATA_DIR / "proches.txt"
_proches_cache = [None, None]



# (26/10, Hakim : « 69 % de mes événements problème n'ont aucun sujet ») sans rubrique sûre, le sujet vient des deux mots
# porteurs du message (les plus longs, hors mots vides, triés) : « mots:calcul+cockpit ». Le même souci qui revient a donc
# le même sujet, et la familiarité peut jouer (sans sujet, seule la peur généralisée par type s'apprenait : la réaction
# MONTAIT à chaque répétition au lieu de baisser).
REMPLISSAGE = {"toujours", "encore", "jamais", "quand", "alors", "apres", "avant", "pourquoi", "comment", "quelque", "chose",
               "truc", "trucs", "machin", "genre", "voila", "frerot", "frero", "wesh", "inchallah", "nchallah", "aussi", "plutot",
               "juste", "deja", "maintenant", "aujourd", "demain", "pense", "crois", "faire", "avoir", "etre", "dire"}


def sujet_par_les_mots(texte):
    try:
        import rappel
        # (26/10, « mots:evidemment+resultats ») pas les adverbes en -ment ni les mots de remplissage : un sujet nomme une chose
        mots = [rappel._plat(m) for m in rappel.mots_cles(texte, maximum=10)]
        mots = sorted([m for m in mots if not m.endswith("ment") and m not in REMPLISSAGE][:2])
    except Exception:
        return None
    return ("mots:" + "+".join(mots))[:80] if mots else None

def _prenoms_proches():
    try:
        mtime = PROCHES_FICHIER.stat().st_mtime
    except OSError:
        return None
    if _proches_cache[0] != mtime:
        noms = [l.strip() for l in PROCHES_FICHIER.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        _proches_cache[:] = [mtime, re.compile(r"\b(" + "|".join(re.escape(n) for n in noms) + r")\b", re.I) if noms else None]
    return _proches_cache[1]
_VIE = re.compile(r"\b(live|en direct|stream|concert|album|morceau|clip|anniversaire|urgences?|h[ôo]pital|m[ée]decin|"
                  r"malade|sant[ée]|d[ée]c[eè]s|mariage|naissance|rendez-vous|rdv|demain|ce soir|vacances|voyage|"
                  r"d[ée]m[ée]nag\w*|travail|boulot|client|contrat|devis|argent)\b", re.I)
_DECISION = re.compile(r"\b(on fait|on garde|on laisse|j'ai d[ée]cid[ée]|c'est d[ée]cid[ée]|valid[ée]|d'accord pour|"
                       r"oui [àa] tous?|on part sur|on met)\b", re.I)
_EMOTION = re.compile(r"(\b(content|heureux|triste|peur|stress\w*|[ée]nerv[ée]|fier|d[ée][çc]u|incroyable|g[ée]nial|"
                      r"inquiet|fatigu[ée]|merci|barakallah\w*|hamdoulillah|machallah)\b|[❤😘😍😢😭😡🔥]|!!)", re.I)


def attention(ahmed, hakim="", nouveaute=0.0):
    """La force d'encrage (importance) d'un échange, de 0,2 à 0,95, et ses raisons (pour l'introspection)."""
    a = str(ahmed or "")
    tout = f"{a} {hakim or ''}"
    score, raisons = 0.25, []
    for motif, poids, nom in ((_EXPLICITE, 0.35, "demande explicite"), (_PROCHES, 0.12, "ses proches"),
                              (_VIE, 0.10, "un événement de sa vie"), (_DECISION, 0.10, "une décision"),
                              (_EMOTION, 0.06, "de l'émotion")):
        trouve = motif.search(a if motif is _EXPLICITE else tout)
        if not trouve and motif is _PROCHES:
            prenoms = _prenoms_proches()
            trouve = prenoms is not None and prenoms.search(tout)
        if trouve:
            score += poids
            raisons.append(nom)
    if nouveaute > 0.35:
        raisons.append("du nouveau")
    score += 0.25 * max(0.0, min(1.0, nouveaute))
    score += min(0.10, len(a) / 2000)
    return round(max(0.2, min(0.95, score)), 2), raisons


def _court(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= TEXTE_MAX else t[:TEXTE_MAX].rsplit(" ", 1)[0] + " […]"


# (2026-10-20, au nettoyage des journaux) la règle était trop large : un horodatage, un numéro de tâche ou un calcul
# de 13 chiffres et plus passait pour une carte, et « find-generic-password -s x » pour un mot de passe dit. Désormais :
# le mot de passe dit exige son séparateur (« c'est », « est », « : », « = ») ; une carte, c'est 4 groupes de 4
# chiffres (dictée), ou une suite valide (clé de Luhn) annoncée par « carte », « CB », « visa »…
def _luhn(chiffres):
    d = [int(c) for c in chiffres][::-1]
    return sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0


_CARTE_GROUPEE = re.compile(r"(?<![\d-])\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,3})?(?![\d-])")
_CARTE_ANNONCEE = re.compile(r"(?i)\b(carte|cb|visa|mastercard|amex|card)\b([^\d\n]{0,25})((?:\d[ -]?){13,19})(?!\d)")


def _cartes(t):
    t = _CARTE_GROUPEE.sub("[numéro de carte masqué]", t)
    def un(m):
        n = m.group(3)
        reste = n[len(n.rstrip(" -")):]                   # l'espace qui suit le numéro reste
        return m.group(1) + m.group(2) + ("[numéro de carte masqué]" + reste if _luhn(re.sub(r"\D", "", n)) else n)
    return _CARTE_ANNONCEE.sub(un, t)


_SECRETS_DITS = [(re.compile(r"(?i)\b(mdp|mots? de passe|password|passwd|code pin|code secret|cvv|cvc)\b\s*(?:c'est|est|:|=)\s*\S+"), r"\1 [masqué]"),
                 (re.compile(r"\btskey-[A-Za-z0-9_-]+"), "[clé masquée]")]


def _masquer(t):
    try:
        ici = str(Path(__file__).resolve().parent / "jarvis")
        if ici not in sys.path:
            sys.path.append(ici)
        import fichiers
        t = fichiers.masquer(t)
    except Exception:
        pass
    for motif, rempl in _SECRETS_DITS:
        t = motif.sub(rempl, str(t))
    return _cartes(t)


def deposer(echange, fichier=None):
    """Côté producteur (bancs, outils Python) : ajoute un échange à la file. Le cockpit écrit la même ligne."""
    f = Path(fichier or FILE)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(echange, ensure_ascii=False) + "\n")


def _nouveaute(mem, emb):
    """1 − la plus forte proximité avec les 60 derniers souvenirs épisodiques (0 = déjà connu, 1 = tout neuf)."""
    if not emb:
        return 0.0
    try:
        import salience
        rows = mem.db.execute("SELECT embedding FROM episodes WHERE role='episodic' ORDER BY id DESC LIMIT 60").fetchall()
        proches = [salience.cosine(emb, json.loads(r[0])) for r in rows if r[0] and r[0] != "[]"]
        proches = [p for p in proches if isinstance(p, (int, float)) and not math.isnan(p)]
        return max(0.0, 1.0 - max(proches)) if proches else 1.0
    except Exception:
        return 0.0


def _texte_souvenir(e):
    try:
        ts = float(e.get("ts") or time.time() * 1000) / 1000
    except (TypeError, ValueError):
        ts = time.time()
    quand = time.strftime("%a %d/%m %H:%M", time.localtime(ts))
    cadre = [quand]
    if e.get("oral"):
        cadre.append("à l'oral")
    if e.get("appareil"):
        cadre.append(f"depuis {e['appareil']}")
    if e.get("externe"):                          # (H6 + X1) ce tour a lu un contenu de tiers
        cadre.append("après lecture de contenu externe (" + ", ".join(_nom_outil(o) for o in e["externe"][:5]) + ")")
    if e.get("de_lui_meme"):
        return f"[Hakim, de lui-même — {', '.join(cadre)}] {_court(_masquer(e.get('hakim', '')))}"
    if e.get("voix") == "autre":                 # l'empreinte vocale : probablement pas Ahmed (un invité, la télé)
        return (f"[Échange — {', '.join(cadre)}, voix qui n'est probablement pas celle d'Ahmed] Quelqu'un : "
                f"« {_court(_masquer(e.get('ahmed', '')))} » · Hakim : « {_court(_masquer(e.get('hakim', '')))} »")
    return (f"[Échange avec Ahmed — {', '.join(cadre)}] Ahmed : « {_court(_masquer(e.get('ahmed', '')))} » · "
            f"Hakim : « {_court(_masquer(e.get('hakim', '')))} »")


def _nom_outil(o):
    o = str(o)
    return o.rsplit("__", 1)[-1] if o.startswith("mcp__") else o


def memoriser(mem, e, embed=None):
    """Un échange → un souvenir épisodique encré selon l'attention. Rend l'id (ou None si rien à garder)."""
    ahmed, hakim = str(e.get("ahmed") or "").strip(), str(e.get("hakim") or "").strip()
    if not ahmed and not hakim:
        return None
    texte = _texte_souvenir(e)
    if embed is None:
        import embeddings
        embed = embeddings.embed
    try:
        emb = embed(texte)
    except Exception:
        emb = None
    # le même échange déposé deux fois (renvoi du même message) : gardé une fois
    if mem.db.execute("SELECT 1 FROM episodes WHERE role='episodic' AND content=? LIMIT 1", (texte,)).fetchone():
        return None
    imp, raisons = attention(ahmed if e.get("voix") != "autre" else "", hakim, _nouveaute(mem, emb))
    if e.get("de_lui_meme"):
        imp = round(max(0.2, imp - 0.1), 2)
    imp = _emotion(mem, e, ahmed, texte, emb, imp, raisons)
    eid = mem.add("episodic", texte, importance=imp, embedding=emb or [], dedup=False, conf_min=ROUTAGE_CONF_MIN)
    if e.get("externe"):
        import provenance
        provenance.marquer(mem.db, eid)
    try:
        import evenements
        evenements.ajouter("memoire", {"id": eid, "kind": "episodic", "auto": True, "attention": imp,
                                       "raisons": raisons}, source="hakim-auto")
    except Exception:
        pass
    return eid


def _emotion(mem, e, ahmed, texte, emb, imp, raisons):
    """(Affect v2 seulement, 2026-10-21) ses mots déclenchent les émotions de Hakim (parole_affect, sujet = la rubrique
    où l'échange sera rangé), puis l'échange est encré d'autant plus fort qu'il est vécu avec émotion. Rend
    l'importance ; jamais bloquant."""
    try:
        import affect
        if not affect.v2_actif(mem):
            return imp
        import chocs
        exclure, facteur, avec_chocs = set(), None, chocs.actif(mem)
        if avec_chocs and ahmed and not e.get("de_lui_meme"):
            # (chocs, 2026-10-23) seule la VOIX d'Ahmed nourrit le lexique (le « merci » d'un invité n'est pas le sien) ;
            # ce que la balise de Hakim a vu (attaque, soutien) écarte les lectures contraires ; la colère d'Ahmed qui
            # le défend n'est pas un échec ; un « merci » de plus pèse moins quand la jauge est déjà pleine
            siens = [x["texte"] for x in chocs.segments(ahmed, bool(e.get("oral")), e.get("voix")) if x["qui"] == "ahmed"]
            vus = chocs.classes_du_tour(mem, e.get("cle")) if e.get("cle") else set()
            if any(chocs.evaluer(x)["soutien"] for x in siens):
                vus.add("soutien")
            if "attaque" in vus:
                exclure |= {"succes", "chaleur_user", "nouveaute"}
            if "soutien" in vus:
                exclure |= {"echec", "probleme"}
            etat_j = affect.get_state(mem)
            plein = chocs.jauge(etat_j, time.time())
            # (23/10, levier 1 de Hakim) le « parfait » répété aussi : simulé, le temps au plafond passe de 41 % à 31 %
            facteur = lambda nom: (1 - plein) if nom in ("chaleur_user", "succes") else 1.0      # noqa: E731
            ahmed = " ".join(siens)
        if ahmed and (avec_chocs or e.get("voix") != "autre") and not e.get("de_lui_meme"):
            import parole_affect
            sujet = None
            try:
                import routing
                sujet, conf = routing.route_episode(mem.db, {"role": "episodic", "content": texte,
                                                             "embedding": json.dumps(emb or [])})
                if (conf or 0.0) < ROUTAGE_CONF_MIN:
                    sujet = None                                   # un sujet mal reconnu : l'émotion compte par type
            except Exception:
                pass
            if not sujet:
                sujet = sujet_par_les_mots(ahmed)
            try:
                ts = float(e.get("ts") or time.time() * 1000) / 1000
            except (TypeError, ValueError):
                ts = time.time()
            # (26/10 22:35, choix de Hakim, accord d'Ahmed) un message écrit en retard (après un long rêve : ~40 d'un coup,
            # 24 émotions en 4 s, un faux pic de peur) ne déclenche plus d'émotion : l'amygdale réagit à ce qui arrive,
            # pas à un arriéré. L'échange, lui, est toujours écrit.
            if time.time() - ts > AGE_EMOTION_MAX_S:
                raisons.append("message ancien : pas d'émotion à l'écriture")
            else:
                faits = parole_affect.appliquer(mem, ahmed, sujet, ts, exclure=exclure, facteur=facteur)
                if faits:
                    raisons.append("ses mots : " + ", ".join(n for n, _i in faits))
        charge = affect.trace(mem)["c"]
        if charge >= 0.3:
            raisons.append("vécu avec émotion")
        return round(min(0.95, imp + affect.MEM_ENCODAGE * charge), 2)
    except Exception:
        return imp


ECHECS_VERROU = 0                                         # passages de suite bloqués par « database is locked »


def passage(mem, fichier=None, embed=None, maximum=PAR_PASSAGE):
    """Lit la file depuis le curseur (kv), mémorise chaque échange neuf. Rend le nombre de souvenirs écrits."""
    global ECHECS_VERROU
    f = Path(fichier or FILE)
    try:
        taille = f.stat().st_size
    except OSError:
        return 0
    try:
        curseur = int(mem.kv_get(CLE_CURSEUR, "0") or 0)
    except (TypeError, ValueError):
        curseur = 0
    if curseur > taille:                                   # la file a été remplacée : on repart du début
        curseur = 0
    if curseur == taille:
        return 0
    n = 0
    with open(f, "rb") as h:
        h.seek(curseur)
        for _ in range(maximum):
            ligne = h.readline()
            if not ligne or not ligne.endswith(b"\n"):        # ligne en cours d'écriture : au prochain passage
                break
            curseur += len(ligne)
            try:
                e = json.loads(ligne.decode("utf-8"))
                if isinstance(e, dict) and memoriser(mem, e, embed=embed):
                    n += 1
            except sqlite3.OperationalError as err:        # (2026-10-21) la base verrouillée n'est pas la faute de la
                import traceback                           # ligne : pas de quarantaine, on réessaie au prochain passage
                ECHECS_VERROU += 1
                print(f"[echanges] base occupée, nouvel essai au prochain passage : {err}\n"
                      + "".join(traceback.format_exc().splitlines(True)[-8:]), file=sys.stderr)
                try:
                    mem.db.rollback()
                except Exception:
                    pass
                return n
            except Exception as err:                       # relecture du 2026-10-20 : une seule ligne bloquait tout
                try:
                    fd = os.open(f.with_name(f.name + ".quarantaine"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                    with os.fdopen(fd, "ab") as q:                 # lisible par Ahmed seul (relecture du 2026-10-20)
                        q.write(ligne)
                except OSError:
                    pass
                print(f"[echanges] ligne mise en quarantaine : {type(err).__name__}: {err}", file=sys.stderr)
            mem.kv_set(CLE_CURSEUR, str(curseur))         # le curseur avance ligne par ligne
            ECHECS_VERROU = 0
    return n
