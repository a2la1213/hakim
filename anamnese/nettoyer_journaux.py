"""Le nettoyage des secrets dans les journaux DÉJÀ écrits (proposé par Hakim après une revue tierce, validé par Ahmed le
2026-10-20) : depuis ce jour, journal, file des échanges et évènements sont masqués à l'écriture ; ce qui a été écrit
avant ne l'était pas toujours.

- Fichiers : le journal brut des conversations (et ses archives), la file des échanges (et sa quarantaine), les
  évènements des sessions de Claude Code (cockpit) ; dans la mémoire : le texte des souvenirs.
- Seules les CHAÎNES des lignes JSON sont masquées (echanges._masquer : clés, jetons, mots de passe, cartes) ; une ligne
  sans secret est recopiée à l'identique ; chaque ligne réécrite est revérifiée (JSON lisible).
- La file des échanges est lue par le démon à un CURSEUR (en octets) : le démon doit être arrêté pendant le nettoyage
  (--demon-arrete), et le curseur est recalculé sur le nouveau fichier.
- Une sauvegarde (0600) est faite avant : elle CONTIENT les secrets — à effacer une fois le résultat vérifié.
- Les transcriptions de Claude Code (~/.claude/projects) ne sont pas touchées : ce sont les fichiers de Claude Code
  (les sessions reprennent d'elles) ; elles sont seulement comptées.
Usage : .venv/bin/python nettoyer_journaux.py [--oui --demon-arrete]
"""
import glob
import json
import os
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

import config
import echanges

H = Path.home()
JOURNAUX = [H / "AIOS" / "jarvis" / "journal.jsonl", H / "AIOS" / "cockpit" / "data" / "events.jsonl",
            H / "AIOS" / "jarvis" / "echanges-a-memoriser.jsonl.quarantaine"] + \
    [Path(p) for p in sorted(glob.glob(str(H / "AIOS" / "jarvis" / "archives" / "*.jsonl")))]
FILE_ECHANGES = H / "AIOS" / "jarvis" / "echanges-a-memoriser.jsonl"


def _m(v):
    if isinstance(v, str):
        return echanges._masquer(v)
    if isinstance(v, list):
        return [_m(x) for x in v]
    if isinstance(v, dict):
        return {k: _m(x) for k, x in v.items()}
    return v


def nettoyer_octets(brut):
    """(nouveaux octets, lignes changées, correspondance ancien décalage → nouveau aux fins de ligne)."""
    sortie, change, fins, ancien, nouveau = [], 0, {0: 0}, 0, 0
    for ligne in brut.splitlines(keepends=True):
        neuve = ligne
        if ligne.endswith(b"\n"):
            try:
                o = json.loads(ligne.decode("utf-8"))
                mo = _m(o)
                if mo != o:
                    neuve = (json.dumps(mo, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                    json.loads(neuve.decode("utf-8"))           # revérifiée
                    change += 1
            except (ValueError, UnicodeDecodeError):
                pass
        sortie.append(neuve)
        ancien += len(ligne)
        nouveau += len(neuve)
        fins[ancien] = nouveau
    return b"".join(sortie), change, fins


def reecrire(f, appliquer):
    """Nettoie un fichier vivant (le cockpit peut y ajouter pendant ce temps : la fin ajoutée est reprise)."""
    try:
        brut = f.read_bytes()
    except OSError:
        return 0, None
    neuf, change, fins = nettoyer_octets(brut)
    if appliquer and change:
        queue = f.read_bytes()[len(brut):]                   # ce que le cockpit a ajouté entre-temps
        neuf_queue, _c, _f = nettoyer_octets(queue)
        tmp = f.with_name(f.name + f".{os.getpid()}.nettoyage")
        tmp.write_bytes(neuf + neuf_queue)
        os.chmod(tmp, 0o600)
        os.replace(tmp, f)
    return change, fins


def main(appliquer=False, demon_arrete=False):
    if appliquer and not demon_arrete:
        sys.exit("arrête d'abord le démon d'Anamnèse (la file des échanges est lue à un curseur), puis --demon-arrete")
    fichiers = [f for f in JOURNAUX + [FILE_ECHANGES] if f.exists()]
    if appliquer:
        sauvegarde = H / "anamnese-backups" / f"avant-nettoyage-{time.strftime('%Y%m%d-%H%M%S')}.tgz"
        sauvegarde.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(sauvegarde, "w:gz") as t:
            for f in fichiers:
                t.add(str(f), arcname=str(f.relative_to(H)))
        os.chmod(sauvegarde, 0o600)
        db = sqlite3.connect(str(config.DB_PATH), timeout=30)
        dest = sqlite3.connect(str(sauvegarde.with_suffix(".db")))
        db.backup(dest)
        dest.close()
        os.chmod(sauvegarde.with_suffix(".db"), 0o600)
        print(f"sauvegarde (elle contient les secrets : à effacer après vérification) : {sauvegarde} et {sauvegarde.with_suffix('.db')}")
    for f in JOURNAUX:
        if f.exists():
            n, _ = reecrire(f, appliquer)
            print(f"{n:5d} ligne(s) {'masquée(s)' if appliquer else 'à masquer'} — {f}")
    # la file des échanges : le curseur du démon suit
    if FILE_ECHANGES.exists():
        db = sqlite3.connect(str(config.DB_PATH), timeout=30)
        try:
            r = db.execute("SELECT value FROM kv WHERE key=?", (echanges.CLE_CURSEUR,)).fetchone()
            curseur = int(r[0]) if r and str(r[0]).isdigit() else 0
            n, fins = reecrire(FILE_ECHANGES, appliquer)
            if appliquer and n and fins is not None:
                nouveau = fins.get(curseur)
                if nouveau is None:                               # curseur hors fin de ligne : on repart du début
                    nouveau = 0                                   # (les échanges déjà mémorisés sont dédoublonnés)
                db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)", (echanges.CLE_CURSEUR, str(nouveau), time.time()))
                db.commit()
            print(f"{n:5d} ligne(s) {'masquée(s)' if appliquer else 'à masquer'} — {FILE_ECHANGES} (curseur {curseur} → {fins.get(curseur) if fins else '?'})")
        finally:
            db.close()
    # les souvenirs
    db = sqlite3.connect(str(config.DB_PATH), timeout=30)
    try:
        lignes = [(i, c) for i, c in db.execute("SELECT id, content FROM episodes") if c and echanges._masquer(c) != c]
        if appliquer:
            db.executemany("UPDATE episodes SET content=? WHERE id=?", [(echanges._masquer(c), i) for i, c in lignes])
            db.commit()
        print(f"{len(lignes):5d} souvenir(s) {'masqué(s)' if appliquer else 'à masquer'} — memory.db")
    finally:
        db.close()
    t = 0
    for f in glob.glob(str(H / ".claude" / "projects" / "*" / "*.jsonl")):
        try:
            with open(f, encoding="utf-8", errors="replace") as h:
                if any(echanges._masquer(l) != l for l in h):
                    t += 1
        except OSError:
            pass
    print(f"{t:5d} transcription(s) de Claude Code contiennent au moins une forme de secret (non touchées)")


if __name__ == "__main__":
    main(appliquer="--oui" in sys.argv[1:], demon_arrete="--demon-arrete" in sys.argv[1:])
