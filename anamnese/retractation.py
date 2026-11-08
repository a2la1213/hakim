"""Rétracter un souvenir SANS le supprimer (26/10/2026 ; accord d'Ahmed « oui », 18:45).

Le banc eval/retractation.py (commit 734c16d) a montré trois choses :
- la nuit ne propage rien : le fait distillé d'une source fausse reste rappelé comme actuel, sans aucune marque ;
- la seule voie existante (desapprendre) SUPPRIME la source et toute sa descendance ;
- Hakim a dit « j'ai retiré l'info de ma mémoire » alors qu'aucun outil ne le lui permet.

Ce que fait ce module :
- une rétractation vise un souvenir SOURCE (table retractions : raison, correction, qui, quand) ;
- tout ce qui en dérive (insight_edges, à toute profondeur, y compris ce que les nuits suivantes en tireront) porte la
  marque « source rétractée ». La marque est calculée à la LECTURE : rien à propager, rien à réécrire, rien de supprimé ;
- le rappel (memory_recall, memory_lire, le balayage du cockpit) l'affiche et fait passer la correction devant ; la nuit
  voit la marque dans son lot ;
- Hakim PROPOSE (outil retractation_proposer, fichier dans ~/AIOS/jarvis/retractations/propositions) ; Ahmed tranche
  dans Parler (le cockpit passe par « anamnese retractation accepter|refuser ») ;
- « anamnese retracter <#id…> --raison … [--correction #id] [--oui] » en direct, « anamnese retablir <#id…> » pour défaire.
"""
import json
import secrets
import time
import unicodedata
from pathlib import Path

DOSSIER = Path.home() / "AIOS" / "jarvis" / "retractations"
RAISON_MAX = 500
ANCETRES_MAX = 200                    # une remontée bornée : un graphe de dérivation bouclé ne bloque jamais le rappel


def assurer(db):
    db.execute("CREATE TABLE IF NOT EXISTS retractions (source_id INTEGER PRIMARY KEY, ts REAL NOT NULL, raison TEXT, "
               "correction_id INTEGER, par TEXT)")


def _raison(raison):
    r = " ".join(str(raison or "").split())
    if not r:
        raise ValueError("une rétractation dit pourquoi (raison)")
    if any(unicodedata.category(c) in ("Cf", "Co", "Cs") for c in r):
        raise ValueError("caractères invisibles dans la raison")
    return r[:RAISON_MAX]


def _existants(db, ids):
    ids = [int(i) for i in dict.fromkeys(ids)]
    if not ids:
        return []
    connus = {r[0] for r in db.execute(f"SELECT id FROM episodes WHERE id IN ({','.join('?' * len(ids))})", ids)}
    return [i for i in ids if i in connus]


def retracter(db, ids, raison, correction=None, par="ahmed", now=None):
    """Les ids existants rétractés (la liste rendue) ; rien n'est supprimé."""
    r = _raison(raison)
    assurer(db)
    faits = _existants(db, ids)
    corr = _existants(db, [correction])[0] if correction and _existants(db, [correction]) else None
    t = time.time() if now is None else now
    db.executemany("INSERT OR REPLACE INTO retractions (source_id, ts, raison, correction_id, par) VALUES (?,?,?,?,?)",
                   [(i, t, r, corr, str(par)[:80]) for i in faits])
    db.commit()
    return faits


def retablir(db, ids):
    assurer(db)
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    n = db.execute(f"DELETE FROM retractions WHERE source_id IN ({','.join('?' * len(ids))})", ids).rowcount
    db.commit()
    return n


def _sources(db):
    try:
        return {r[0]: {"ts": r[1], "raison": r[2], "correction": r[3], "par": r[4]}
                for r in db.execute("SELECT source_id, ts, raison, correction_id, par FROM retractions")}
    except Exception:                 # table absente (base ancienne, lecture seule) : rien n'est rétracté
        return {}


def marques(db, ids):
    """{id: {source, direct, ts, raison, correction, par}} pour les ids rétractés ou qui dérivent d'une source rétractée."""
    rs = _sources(db)
    if not rs:
        return {}
    out = {}
    for i in dict.fromkeys(int(x) for x in ids):
        vus, file, trouve = set(), [i], None
        while file and len(vus) < ANCETRES_MAX:
            x = file.pop(0)
            if x in vus:
                continue
            vus.add(x)
            if x in rs:
                trouve = x
                break
            file.extend(r[0] for r in db.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (x,)))
        if trouve is not None:
            out[i] = {"source": trouve, "direct": trouve == i, **rs[trouve]}
    return out


def marque_texte(m):
    quand = time.strftime("%d/%m/%y", time.localtime(m["ts"]))
    corr = f" — correction : #{m['correction']}" if m.get("correction") else ""
    if m["direct"]:
        return f"[RÉTRACTÉ le {quand} : {m['raison']}{corr} — ne pas le tenir pour vrai] "
    return (f"[SOURCE RÉTRACTÉE — dérive de #{m['source']}, rétracté le {quand} : {m['raison']}{corr} — "
            "ne pas le tenir pour vrai] ")


# ---------------------------------------------------------------- les propositions de Hakim, tranchées par Ahmed
def _fichier(pid, dossier=None):
    return Path(dossier or DOSSIER) / "propositions" / f"{pid}.json"


def proposer(db, ids, raison, correction=None, origine="hakim", dossier=None, now=None):
    """(déposée, message, id). Ne rétracte RIEN : Ahmed tranche."""
    try:
        r = _raison(raison)
    except ValueError as e:
        return False, f"refusée : {e}", None
    faits = _existants(db, ids)
    if not faits:
        return False, "refusée : aucun de ces souvenirs n'existe", None
    import desapprendre
    tous = desapprendre.descendance(db, faits)
    corr = _existants(db, [correction])[0] if correction and _existants(db, [correction]) else None
    pid = secrets.token_hex(6)
    p = {"id": pid, "ts": time.time() if now is None else now, "origine": str(origine)[:40], "ids": faits, "raison": r,
         "correction": corr, "descendance": [x for x in tous if x not in faits], "apercu": desapprendre.apercu(db, faits),
         "etat": "en_attente"}
    f = _fichier(pid, dossier)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, "déposée", pid


def propositions(dossier=None, toutes=False):
    d = Path(dossier or DOSSIER) / "propositions"
    out = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(p, dict) and p.get("id") == f.stem and (toutes or p.get("etat") == "en_attente"):
            out.append(p)
    return sorted(out, key=lambda p: p.get("ts", 0))


def trancher(db, pid, accepter, dossier=None, now=None):
    """La décision d'Ahmed : (fait, message)."""
    f = _fichier(str(pid), dossier)
    try:
        p = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "proposition inconnue"
    if p.get("etat") != "en_attente":
        return False, f"déjà tranchée ({p.get('etat')})"
    if accepter:
        try:
            p["retractes"] = retracter(db, p.get("ids") or [], p.get("raison"), correction=p.get("correction"),
                                       par=f"ahmed (proposé par {p.get('origine', '?')})", now=now)
        except ValueError as e:
            return False, str(e)
    p.update(etat="acceptee" if accepter else "refusee", tranche_ts=time.time() if now is None else now)
    f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, p["etat"]
