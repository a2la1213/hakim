"""L'audit de l'EXISTANT (proposé par Hakim après une revue tierce, validé par Ahmed le 2026-10-20) : le marquage
« externe » protège l'avenir ; les souvenirs d'AVANT le 20/10 ne le portent pas. Cet audit le pose après coup, sur
preuve seulement :

- les tours de Hakim qui ont fait entrer un contenu de tiers sont retrouvés dans les transcriptions de son cerveau
  (~/.claude/projects/-Users-admin-AIOS-jarvis-cwd/*.jsonl) — on n'en lit QUE l'heure, le nom des outils appelés et,
  pour le terminal, si la commande touche le réseau ; rien du contenu des conversations ;
- dans ces tours : l'échange mémorisé (l'en-tête « [Échange avec Ahmed — mar 20/10 17:41 …] » donne la minute) et ce
  que Hakim a mémorisé lui-même (le journal d'événements donne l'heure de chaque souvenir écrit par « hakim ») ;
- puis toute leur descendance (insight_edges) : faits distillés, synthèses.
Seule la colonne provenance change (le texte jamais). Simulation par défaut ; --oui applique après une sauvegarde de la
base, et la liste des souvenirs marqués est gardée (data/provenance-retro-<date>.json) pour pouvoir défaire.
Usage : .venv/bin/python audit_provenance.py [--oui] ; défaire : … --defaire data/provenance-retro-<date>.json
"""
import datetime
import glob
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import config
import provenance

TRANSCRIPTIONS = Path.home() / ".claude" / "projects" / "-Users-admin-AIOS-jarvis-cwd"
EXTERNES = {"WebSearch", "WebFetch", "mcp__web__lire_page", "mcp__web__cliquer", "mcp__web__consulter_ia",
            "mcp__web__preparer_video_web", "mcp__fichiers__preparer_fichier", "mcp__fichiers__chercher_dans_fichiers",
            "Task", "Agent", "mcp__terminal__suivre_tache", "mcp__anamnese__courrier_lire", "mcp__anamnese__mission_etat",
            "mcp__anamnese__fichiers_par_sens"}
RESEAU = re.compile(r"https?://|\bcurl\b|\bwget\b|\bgit\s+(clone|pull|fetch)\b|\bpip\b|\buv\b|yt-dlp|huggingface|hf_hub|\bnpm\b|\bbrew\b")
EN_TETE = re.compile(r"^\[(?:Échange(?: avec Ahmed)?|Hakim, de lui-même) — \w+\.? (\d\d)/(\d\d) (\d\d):(\d\d)")


def _ts(o):
    t = o.get("timestamp")
    try:
        return datetime.datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def tours_externes(dossier=None):
    """[(début, fin, [outils])] des tours de Hakim qui ont fait entrer un contenu de tiers."""
    tours = []
    for f in sorted(glob.glob(str(Path(dossier or TRANSCRIPTIONS) / "*.jsonl"))):
        courant = None
        for l in open(f, encoding="utf-8", errors="replace"):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            t = _ts(o)
            m = o.get("message") or {}
            contenu = m.get("content")
            if o.get("type") == "user" and t is not None and not o.get("isSidechain"):
                debut_de_tour = isinstance(contenu, str) or (isinstance(contenu, list) and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in contenu))
                if debut_de_tour:
                    if courant and courant[2]:            # la fin d'un tour : sa dernière ligne (pas le message suivant)
                        tours.append((courant[0], courant[1] or courant[0], sorted(courant[2])))
                    courant = [t, t, set()]
                    continue
            if o.get("type") == "assistant" and isinstance(contenu, list) and courant is not None:
                for b in contenu:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    nom = b.get("name")
                    if nom in EXTERNES or (nom == "Read" and "/fichiers/" in str((b.get("input") or {}).get("file_path", ""))):
                        courant[2].add(nom)
                    elif nom == "mcp__terminal__executer" and RESEAU.search(str((b.get("input") or {}).get("commande", ""))):
                        courant[2].add("terminal (réseau)")
            if t is not None and courant is not None:
                courant[1] = t
        if courant and courant[2]:
            tours.append((courant[0], courant[1] or courant[0], sorted(courant[2])))
    return tours


def _dans(t, tours, marge=0):
    return any(a - marge <= t <= b + marge for a, b, _o in tours)


def candidats(conn, tours, evenements=None):
    """{id: raison} des souvenirs à marquer (sans leur descendance)."""
    provenance.assurer(conn)
    res = {}
    # les échanges mémorisés : la minute de leur en-tête
    for eid, ts, content in conn.execute("SELECT id, ts, content FROM episodes WHERE role='episodic' AND provenance IS NULL "
                                         "AND (content LIKE '[Échange%' OR content LIKE '[Hakim, de lui-même%')"):
        m = EN_TETE.match(content or "")
        if not m:
            continue
        an = time.localtime(ts).tm_year
        try:
            minute = time.mktime((an, int(m.group(2)), int(m.group(1)), int(m.group(3)), int(m.group(4)), 0, 0, 0, -1))
        except (OverflowError, ValueError):
            continue
        # l'échange est déposé à la FIN du tour : sa minute tombe entre la minute du début et celle de la fin (+1)
        if any(a - a % 60 <= minute <= b - b % 60 + 60 for a, b, _o in tours):
            res[eid] = "échange d'un tour qui a lu un contenu de tiers"
    # ce que Hakim a mémorisé lui-même pendant ces tours (le journal d'événements)
    try:
        lignes = Path(evenements or (config.DATA_DIR / "evenements.jsonl")).read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    for l in lignes:
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "memoire" and e.get("source") == "hakim" and _dans(float(e.get("ts") or 0), tours, marge=5):
            eid = (e.get("donnees") or {}).get("id")
            if eid and conn.execute("SELECT 1 FROM episodes WHERE id=? AND provenance IS NULL", (eid,)).fetchone():
                res[int(eid)] = "écrit par Hakim pendant un tour qui a lu un contenu de tiers"
    return res


def avec_descendance(conn, ids):
    import desapprendre
    return [x for x in desapprendre.descendance(conn, ids)
            if conn.execute("SELECT 1 FROM episodes WHERE id=? AND provenance IS NULL", (x,)).fetchone()]


def main(appliquer=False, db_path=None):
    db_path = Path(db_path or config.DB_PATH)
    tours = tours_externes()
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        c = candidats(conn, tours)
        tous = avec_descendance(conn, list(c))
        print(f"{len(tours)} tour(s) de Hakim ont fait entrer un contenu de tiers (transcriptions) ;")
        print(f"{len(c)} souvenir(s) directement concernés, {len(tous)} avec leur descendance.")
        for eid in tous[:15]:
            r = conn.execute("SELECT role, substr(content, 1, 100) FROM episodes WHERE id=?", (eid,)).fetchone()
            print(f"  #{eid} ({r[0]}) {' '.join(str(r[1]).split())} — {c.get(eid, 'dérivé')}")
        if not appliquer or not tous:
            print("Simulation : rien n'a été écrit. --oui pour appliquer." if not appliquer else "Rien à marquer.")
            return tous
        sauvegarde = Path.home() / "anamnese-backups" / f"avant-provenance-retro-{time.strftime('%Y%m%d-%H%M%S')}.db"
        sauvegarde.parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(str(sauvegarde))
        conn.backup(dest)
        dest.close()
        for eid in tous:
            provenance.marquer(conn, eid)
        liste = config.DATA_DIR / f"provenance-retro-{time.strftime('%Y%m%d')}.json"
        liste.write_text(json.dumps({"ts": time.time(), "marques": tous, "raisons": {str(k): v for k, v in c.items()},
                                     "sauvegarde": str(sauvegarde)}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(tous)} souvenir(s) marqués « externe » ; sauvegarde : {sauvegarde} ; liste : {liste}")
        return tous
    finally:
        conn.close()


def defaire(liste, db_path=None):
    """Retire la marque posée par un passage (la liste qu'il a gardée)."""
    ids = json.loads(Path(liste).read_text(encoding="utf-8"))["marques"]
    conn = sqlite3.connect(str(db_path or config.DB_PATH), timeout=30)
    try:
        conn.executemany("UPDATE episodes SET provenance=NULL WHERE id=? AND provenance='externe'", [(int(i),) for i in ids])
        conn.commit()
    finally:
        conn.close()
    return len(ids)


if __name__ == "__main__":
    if "--defaire" in sys.argv[1:]:
        print(defaire(sys.argv[sys.argv.index("--defaire") + 1]), "marque(s) retirée(s)")
    else:
        main(appliquer="--oui" in sys.argv[1:])
