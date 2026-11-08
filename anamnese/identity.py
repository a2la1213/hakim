"""Identité d'Anamnèse en deux couches — source de vérité unique (2026-10-15).

Pourquoi : l'ancienne règle du démon coupait le milieu du self_model au plafond. L'identité
écrite par Claude le 1er juillet (2 501 caractères) a été amputée au premier ajout du 9B,
puis rongée par les 28 suivants. Ici, rien n'efface jamais le cœur.

- CŒUR (kv « self_core ») : le texte validé par Ahmed. Seul set_core le remplace
  (restauration, décision humaine explicite via l'outil MCP self_update). Un cœur vide ou
  qui rétrécit sous 60 % de l'actuel est refusé sans force=True. Les 5 cœurs précédents
  restent dans kv « self_core_history », que les ajouts ne touchent jamais.
- ÉVOLUTION (kv « self_evolution », liste JSON) : phrases à la 1re personne ajoutées par le
  rêve local ou la consolidation de nuit, une par EVOLUTION_INTERVALLE_S au plus. Au-delà de
  EVOLUTION_MAX phrases, c'est la plus ancienne phrase d'évolution qui sort, jamais le cœur.
- kv « self_model » = assemble(cœur, évolution), réécrit à chaque changement, pour les
  lecteurs existants (self_get, cockpit, CLI, prompts du démon). « self_model_prev » garde
  l'assemblage précédent.

Chaque changement est une seule transaction SQLite (BEGIN IMMEDIATE) quand la mémoire a une
connexion : le démon, le MCP interactif et le MCP de la nuit écrivent la même base.
Migration : une base sans « self_core » lit son self_model actuel comme cœur.
"""
import contextlib
import json
import re
import sys
import time
import uuid

import config
import registre
import salience

EVOLUTION_MAX = 8
EVOLUTION_INTERVALLE_S = 20 * 3600   # au plus une phrase d'évolution toutes les 20 h
HISTORIQUE_MAX = 5
RETRECISSEMENT_MIN = 0.6
EN_TETE_EVOLUTION = "Évolution récente (phrases ajoutées pendant mes nuits) :"
_PREMIERE_PERSONNE = re.compile(r"\b(je|j'|me|m'|mon|ma|mes|moi)\b")


def core(mem):
    """Le cœur validé. Une base ancienne (self_model seul) le lit comme cœur ; la lecture
    n'écrit jamais : la migration s'enregistre au premier changement."""
    c = mem.kv_get("self_core")
    if c is None:
        c = mem.kv_get("self_model", "") or ""
    return c


def _liste(mem, cle):
    try:
        v = json.loads(mem.kv_get(cle, "[]") or "[]")
        return [p for p in v if isinstance(p, str)]
    except (ValueError, TypeError):
        return []


def evolution(mem):
    if mem.kv_get("self_core") is None:
        return []
    return _liste(mem, "self_evolution")


def historique_coeurs(mem):
    return _liste(mem, "self_core_history")


def assemble(coeur, evo):
    if not evo:
        return coeur
    return coeur.rstrip() + "\n\n" + EN_TETE_EVOLUTION + "\n" + "\n".join(f"- {p}" for p in evo)


@contextlib.contextmanager
def _transaction(mem):
    db = getattr(mem, "db", None)
    if db is None:          # mémoire factice des tests : pas de connexion
        yield
        return
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()


def _set(mem, cle, valeur):
    """Écriture kv SANS commit intermédiaire (Memory.kv_set committe à chaque appel).
    Les clés d'identité sont notées au registre (avant/après) quand une entrée est ouverte."""
    db = getattr(mem, "db", None)
    if db is not None and cle in registre.CLES_IDENTITE:
        registre.noter(db, "kv", cle, mem.kv_get(cle), valeur)
    if db is None:
        mem.kv_set(cle, valeur)
    else:
        db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)", (cle, valeur, time.time()))


def _ecrire(mem, coeur, evo):
    _set(mem, "self_model_prev", assemble(core(mem), evolution(mem)))
    _set(mem, "self_core", coeur)
    _set(mem, "self_evolution", json.dumps(evo, ensure_ascii=False))
    _set(mem, "self_model", assemble(coeur, evo))


def _temoin(mem, raison):
    """Le témoin du changement dans le journal d'événements en ajout seul (lot E, point 7, 2026-10-19).
    Jamais bloquant : un journal indisponible ne défait pas une identité déjà écrite."""
    try:
        import evenements
        evenements.temoin_identite(mem, raison)
    except Exception as e:  # disque plein, droits…
        print("[identité] témoin non écrit :", e, file=sys.stderr)   # jamais stdout : c'est le canal MCP


def set_core(mem, texte, force=False):
    """Remplace le cœur (décision humaine). Retourne (accepté, raison). L'évolution est gardée."""
    texte = (texte or "").strip()
    if not texte:
        return False, "refusé : texte vide"
    with _transaction(mem):
        ancien = core(mem)
        if not force and ancien and len(texte) < RETRECISSEMENT_MIN * len(ancien):
            return False, (f"refusé : le nouveau cœur ({len(texte)} car.) fait moins de "
                           f"{int(RETRECISSEMENT_MIN * 100)} % de l'actuel ({len(ancien)} car.) ; "
                           "confirmer explicitement si c'est voulu")
        if ancien and ancien != texte:
            hist = (historique_coeurs(mem) + [ancien])[-HISTORIQUE_MAX:]
            _set(mem, "self_core_history", json.dumps(hist, ensure_ascii=False))
        _ecrire(mem, texte, evolution(mem))
    _temoin(mem, "cœur remplacé (décision humaine)")
    return True, "remplacé"


def _phrase_refusee(phrase):
    low = phrase.lower()
    if any(b in low for b in config.DREAM_IDENTITY_BLOCKLIST):
        return "refusée : contient une formule de reniement"
    if not _PREMIERE_PERSONNE.search(low):
        return "refusée : pas à la première personne"
    if not (10 <= len(phrase) <= config.DREAM_SELF_ADD_MAX):
        return f"refusée : longueur hors de 10..{config.DREAM_SELF_ADD_MAX}"
    return None


def append(mem, phrase, now=None, humain=False):
    """Ajoute une phrase d'évolution. Retourne (accepté, raison). Un refus n'écrit rien.
    humain=True : Ahmed l'a validée (trancher) — l'intervalle de 20 h ne s'applique pas à sa décision."""
    now = time.time() if now is None else now
    phrase = (phrase or "").strip()
    refus = _phrase_refusee(phrase)
    if refus:
        return False, refus
    with _transaction(mem):
        dernier = float(mem.kv_get("self_evolution_ts", "0") or 0)
        if dernier and now - dernier < EVOLUTION_INTERVALLE_S and not humain:
            heures = (now - dernier) / 3600
            return False, (f"refusée : une phrase a déjà été ajoutée il y a {heures:.0f} h "
                           f"(au plus une toutes les {EVOLUTION_INTERVALLE_S // 3600} h)")
        coeur, evo = core(mem), evolution(mem)
        if salience.lexical_overlap(phrase, assemble(coeur, evo)) >= 0.5:
            return False, "refusée : quasi-doublon de l'identité"
        evo = evo + [phrase]
        retiree = evo.pop(0) if len(evo) > EVOLUTION_MAX else None
        _ecrire(mem, coeur, evo)
        _set(mem, "self_evolution_ts", str(now))
    _temoin(mem, "phrase d'évolution ajoutée" + (" (la plus ancienne retirée)" if retiree else ""))
    if retiree:
        return True, f"ajoutée ; plus ancienne phrase d'évolution retirée : « {retiree[:60]} »"
    return True, "ajoutée"


# ---- Propositions (retour d’un ami d’Ahmed transmis par Hakim, X1 ; accord d'Ahmed le 2026-10-20 à 17:11) ----------------
# L'identité ne change plus que par une différence qu'Ahmed valide. La nuit, le rêve local, une session : tous
# PROPOSENT (self_append, self_update, démon) ; rien n'est écrit avant qu'Ahmed tranche (cockpit : la carte
# « identité », ou ./anamnese identite). Une proposition par origine reste en attente : la plus récente remplace
# la précédente. Les décisions sont gardées (30 dernières) pour l'historique.
PROPOSITIONS_CLE = "self_propositions"
PROPOSITIONS_GARDEES = 30


def propositions(mem, toutes=False):
    try:
        v = json.loads(mem.kv_get(PROPOSITIONS_CLE, "[]") or "[]")
        v = [p for p in v if isinstance(p, dict) and p.get("id")]
    except (ValueError, TypeError):
        v = []
    return v if toutes else [p for p in v if p.get("etat") == "en_attente"]


def proposer(mem, sorte, texte, origine, now=None):
    """sorte : « phrase » (couche évolution) ou « coeur » (nouveau cœur). Retourne (déposée, raison, id).
    Les règles de la phrase sont vérifiées tout de suite (Ahmed ne voit que des propositions recevables)."""
    now = time.time() if now is None else now
    texte = (texte or "").strip()
    if sorte not in ("phrase", "coeur"):
        return False, "refusée : sorte inconnue", None
    # (relecture Opus du 2026-10-20) aucun caractère invisible (format Unicode : étiquettes, largeur nulle…) : Ahmed
    # validerait une phrase visible qui porte un texte caché
    import unicodedata
    if any(unicodedata.category(c) in ("Cf", "Co", "Cs") for c in texte):
        return False, "refusée : caractères invisibles", None
    if sorte == "phrase":
        refus = _phrase_refusee(texte)
        if refus:
            return False, refus, None
        if salience.lexical_overlap(texte, assemble(core(mem), evolution(mem))) >= 0.5:
            return False, "refusée : quasi-doublon de l'identité", None
    elif not texte:
        return False, "refusé : texte vide", None
    origine = str(origine or "?")[:40]
    pid = f"{int(now)}-{uuid.uuid4().hex[:6]}"
    with _transaction(mem):
        toutes = propositions(mem, toutes=True)
        for p in toutes:
            if p.get("etat") == "en_attente" and p.get("texte") == texte:
                return False, "déjà proposée, en attente d'Ahmed", p["id"]
        for p in toutes:                               # une seule en attente par origine et par sorte
            if p.get("etat") == "en_attente" and p.get("origine") == origine and p.get("sorte") == sorte:
                p.update(etat="remplacee", tranche_ts=now)
        toutes.append({"id": pid, "ts": now, "sorte": sorte, "texte": texte, "origine": origine,
                       "avant": core(mem) if sorte == "coeur" else None, "etat": "en_attente"})
        attente = [p for p in toutes if p.get("etat") == "en_attente"]
        faites = [p for p in toutes if p.get("etat") != "en_attente"][-PROPOSITIONS_GARDEES:]
        _set(mem, PROPOSITIONS_CLE, json.dumps(faites + attente, ensure_ascii=False))
    _temoin(mem, f"proposition d'identité ({sorte}, {origine}) en attente d'Ahmed")
    return True, "proposée à Ahmed", pid


def trancher(mem, pid, accepter, now=None):
    """La décision d'Ahmed. Retourne (fait, raison). Acceptée : la phrase entre dans l'évolution, ou le cœur est
    remplacé (l'ancien reste dans l'historique des cœurs)."""
    now = time.time() if now is None else now
    toutes = propositions(mem, toutes=True)
    p = next((x for x in toutes if x.get("id") == pid), None)
    if not p:
        return False, "proposition inconnue"
    if p.get("etat") != "en_attente":
        return False, f"déjà tranchée ({p.get('etat')})"
    if accepter:
        if p["sorte"] == "phrase":
            ok, raison = append(mem, p["texte"], now=now, humain=True)
        else:
            # (relecture Opus du 2026-10-20) la différence montrée à Ahmed était calculée contre le cœur d'ALORS : si le
            # cœur a changé depuis, l'accepter remplacerait aussi ce qu'il n'a pas vu
            if (p.get("avant") or "") != core(mem):
                return False, "le cœur a changé depuis cette proposition : refuse-la, une nouvelle sera proposée"
            ok, raison = set_core(mem, p["texte"], force=True)
        if not ok:
            return False, raison
    with _transaction(mem):
        toutes = propositions(mem, toutes=True)
        for x in toutes:
            if x.get("id") == pid:
                x.update(etat="acceptee" if accepter else "refusee", tranche_ts=now)
        attente = [x for x in toutes if x.get("etat") == "en_attente"]
        faites = [x for x in toutes if x.get("etat") != "en_attente"][-PROPOSITIONS_GARDEES:]
        _set(mem, PROPOSITIONS_CLE, json.dumps(faites + attente, ensure_ascii=False))
    return True, "acceptée" if accepter else "refusée"
