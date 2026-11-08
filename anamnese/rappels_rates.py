"""La trace des souvenirs ratés (demande de Hakim, accord d'Ahmed le 2026-10-22) : quand le balayage automatique d'avant
sa réponse (rappel.py) n'a pas fait remonter ce qu'il fallait, Hakim le retrouve à la main ; on le note, et la nuit
on en tire des corrections.

- Noté seul : chaque memory_recall manuel de Hakim fait dans les 10 min qui suivent un balayage (la requête, ce que
  le balayage avait proposé, ce que la recherche manuelle rend). C'est un indice : une recherche manuelle n'est pas
  toujours un raté.
- Noté par Hakim (rappel_rate) : « ces souvenirs auraient dû remonter, parce que… ». C'est la seule source des
  corrections.
- La nuit (corriger) : pour chaque souvenir raté, les mots porteurs du message d'Ahmed que ce souvenir ne contient
  pas deviennent ses ALIAS (3 au plus, 8 au plus par souvenir) : le balayage par mots les trouvera la fois suivante.
  Les alias vivent à part (clé rappel_alias), jamais dans le texte du souvenir ; une liste lisible, et défaisable
  (retirer_alias).
Journal : ~/AIOS/jarvis/rappels-rates.jsonl (en ajout seul).
"""
import json
import re
import time
from pathlib import Path

import rappel

JOURNAL = Path.home() / "AIOS" / "jarvis" / "rappels-rates.jsonl"
JOURNAL_BALAYAGE = Path.home() / "AIOS" / "jarvis" / "rappel.jsonl"
CONVERSATION = Path.home() / "AIOS" / "jarvis" / "conversation.json"
ALIAS_CLE, ALIAS_VERSION, FAIT_CLE = rappel.ALIAS_CLE, rappel.ALIAS_VERSION, "rappels_rates_traites_ts"
FENETRE_S = 10 * 60
ALIAS_PAR_RATE, ALIAS_PAR_SOUVENIR = 3, 8


def _ajouter(o, journal=None):
    f = Path(journal or JOURNAL)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")


def dernier_balayage(maintenant=None, journal=None):
    """Le dernier balayage automatique des 10 dernières minutes : {ts, ids, scores}, ou None."""
    maintenant = time.time() if maintenant is None else maintenant
    try:
        with open(journal or JOURNAL_BALAYAGE, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 20000))
            lignes = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for l in reversed(lignes):
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if 0 <= maintenant - o.get("ts", 0) / 1000 <= FENETRE_S:
            return {"ts": o.get("ts"), "ids": o.get("ids") or [], "scores": o.get("scores") or []}
        return None
    return None


def dernier_message_d_ahmed(conversation=None):
    try:
        m = [x for x in json.loads(Path(conversation or CONVERSATION).read_text(encoding="utf-8")).get("messages", [])
             if isinstance(x, dict) and x.get("qui") == "u"]
    except (OSError, ValueError, AttributeError):
        return ""
    return str(m[-1].get("texte", ""))[:1500] if m else ""


def noter_recherche(requete, ids_rendus, maintenant=None, journal=None, balayage=None):
    """Un memory_recall manuel de Hakim juste après un balayage : noté comme indice. Rend vrai s'il est noté."""
    b = balayage if balayage is not None else dernier_balayage(maintenant)
    if not b:
        return False
    nouveaux = [i for i in ids_rendus if i not in set(b["ids"])]
    _ajouter({"ts": time.time() if maintenant is None else maintenant, "type": "recherche", "requete": str(requete)[:300],
              "balayage": b["ids"], "rendus": list(ids_rendus)[:12], "hors_balayage": nouveaux[:12]}, journal)
    return True


def noter_rate(ids, pourquoi, maintenant=None, journal=None, balayage=None, message=None):
    """Hakim : « ces souvenirs auraient dû remonter ». Rend le nombre de souvenirs notés."""
    ids = [int(i) for i in ids][:10]
    if not ids:
        return 0
    b = balayage if balayage is not None else (dernier_balayage(maintenant) or {"ids": []})
    _ajouter({"ts": time.time() if maintenant is None else maintenant, "type": "rate", "ids": ids,
              "pourquoi": re.sub(r"\s+", " ", str(pourquoi or ""))[:300], "balayage": b.get("ids", []),
              "message": message if message is not None else dernier_message_d_ahmed()}, journal)
    return len(ids)


def alias(mem):
    try:
        a = json.loads(mem.kv_get(ALIAS_CLE, "") or "{}")
        return {int(k): list(v) for k, v in a.items()} if isinstance(a, dict) else {}
    except (ValueError, TypeError):
        return {}


def _ecrire_alias(mem, a):
    mem.kv_set(ALIAS_CLE, json.dumps({str(k): v for k, v in a.items() if v}, ensure_ascii=False))
    mem.kv_set(ALIAS_VERSION, str(time.time()))


def corriger(mem, maintenant=None, journal=None):
    """La nuit : chaque raté noté par Hakim depuis la dernière fois donne au souvenir des alias tirés du message
    d'Ahmed. Rend [(id, [mots ajoutés])]."""
    maintenant = time.time() if maintenant is None else maintenant
    depuis = float(mem.kv_get(FAIT_CLE, "0") or 0)
    try:
        lignes = Path(journal or JOURNAL).read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    a, fait = alias(mem), []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("type") != "rate" or o.get("ts", 0) <= depuis or not o.get("message"):
            continue
        for eid in o.get("ids", []):
            row = mem.db.execute("SELECT lower(content) FROM episodes WHERE id = ?", (eid,)).fetchone()
            if not row:
                continue
            contenu, deja = row[0] or "", set(a.get(eid, []))
            neufs = [m for m in rappel.mots_cles(o["message"]) if m not in contenu and m not in deja][:ALIAS_PAR_RATE]
            if neufs:
                a[eid] = (a.get(eid, []) + neufs)[-ALIAS_PAR_SOUVENIR:]
                fait.append((eid, neufs))
    if fait:
        _ecrire_alias(mem, a)
    mem.kv_set(FAIT_CLE, str(maintenant))
    return fait


def retirer_alias(mem, eid, mot=None):
    a = alias(mem)
    if eid not in a:
        return False
    a[eid] = [m for m in a[eid] if mot is not None and m != mot]
    _ecrire_alias(mem, a)
    return True
