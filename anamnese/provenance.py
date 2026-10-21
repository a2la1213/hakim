"""Provenance « externe » des souvenirs (audit JARVIS 2, H6, et retour d’un ami d’Ahmed transmis par Hakim, X1 ; accord
d'Ahmed le 2026-10-20 à 17:11).

Le risque : une page piégée lue par Hakim le jour J devient, la nuit, un « fait » de la mémoire, puis une phrase de
son identité. La parade : ce qui vient d'un tiers garde sa marque, de bout en bout.

- episodes.provenance = 'externe' (NULL : interne) — colonne ajoutée à la volée si la base ne l'a pas encore.
- Entrée : un échange (echanges.py) dont le tour a lu du contenu externe (page web, recherche, vidéo, fichier,
  autre IA, agent, sortie réseau du terminal) ; un souvenir que Hakim écrit PENDANT un tel tour. La marque
  ~/AIOS/jarvis/tour-externe.jsonl (une ligne par source, en ajout seul) est posée par le cockpit au premier outil
  externe et par la passerelle du terminal à chaque sortie réseau ; le cockpit la lit et la retire à la fin du
  tour. Les commandes de Hakim (bac à sable) et ses outils de fichiers ne peuvent pas y écrire.
- Héritage : un souvenir distillé (memory_store avec sources, synthèse du démon) dont une source est externe
  est externe à son tour, et s'écrit en citation marquée — jamais en fait.
- La nuit, un fait cite ses sources : sans elles, impossible de savoir s'il hérite (refusé).
- L'identité ne bouge plus sans Ahmed (identity.proposer) : la question ne se pose donc plus pour elle.
Limite connue, dite honnêtement : la marque vaut pour le TOUR qui a lu le contenu ; ce que Hakim en garde dans
son contexte aux tours suivants n'est pas suivi (il le sait : sa persona le lui dit).
"""
import json
import os
from pathlib import Path

EXTERNE = "externe"
MARQUE = Path(os.environ.get("ANAMNESE_MARQUE_EXTERNE") or Path.home() / "AIOS" / "jarvis" / "tour-externe.jsonl")
CITATION = "(citation externe, non vérifiée) "
LU = "(d'après un contenu externe) "


def assurer(db):
    """La colonne provenance existe (ajout idempotent : une base d'avant le 2026-10-20 ne l'a pas)."""
    try:
        if "provenance" not in {r[1] for r in db.execute("PRAGMA table_info(episodes)")}:
            db.execute("ALTER TABLE episodes ADD COLUMN provenance TEXT")
            db.commit()
        return True
    except Exception:
        return False


def marquer(db, eid):
    if not eid or not assurer(db):
        return False
    try:
        db.execute("UPDATE episodes SET provenance=? WHERE id=?", (EXTERNE, int(eid)))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def externes(db, ids):
    """Les ids externes parmi ids."""
    ids = [int(i) for i in ids or []]
    if not ids or not assurer(db):
        return set()
    marques = ",".join("?" * len(ids))
    try:
        return {r[0] for r in db.execute(f"SELECT id FROM episodes WHERE provenance=? AND id IN ({marques})",
                                         (EXTERNE, *ids))}
    except Exception:
        return set()


def est_externe(db, eid):
    return bool(externes(db, [eid]))


def lire_marque(chemin=None):
    """Les sources externes notées pour le tour en cours (dans l'ordre, sans doublon) ; None sans marque."""
    try:
        lignes = Path(chemin or MARQUE).read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return None
    except OSError:
        return ["marque illisible"]
    vus = []
    for l in lignes:
        try:
            o = str(json.loads(l).get("outil") or "?")
        except Exception:
            o = "marque illisible"             # présente mais illisible : prudence, externe
        if o not in vus:
            vus.append(o)
    return vus or ["?"]


def noter(outil, chemin=None):
    """Ajoute une source externe à la marque du tour (une ligne, en ajout seul : plusieurs écrivains)."""
    import time
    p = Path(chemin or MARQUE)
    try:
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps({"outil": str(outil)[:120], "ts": time.time()}, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def tour_externe():
    """Les sources externes du tour en cours de Hakim (la marque), ou [] — seulement pour SON serveur MCP."""
    if os.environ.get("ANAMNESE_SOURCE") != "hakim":
        return []
    return (lire_marque() or [])[:12]


def prefixer(texte, prefixe):
    texte = str(texte or "")
    return texte if texte.startswith((CITATION, LU)) else prefixe + texte
