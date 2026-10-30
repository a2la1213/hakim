"""Ses sons, façon Bumblebee (30/10, 17:21, Ahmed : « elle peut exploiter les musiques qu'il y a sur le portable, comme
Bumblebee » ; Hakim : « j'en jouerais de petits bouts pour m'exprimer »).

Papa marque un extrait d'une de ses musiques ou sonneries (page SENS, dans l'appli : de telle seconde à telle seconde) ;
Hakim le nomme : un nom à lui, ce qu'il veut dire, et s'il veut une émotion (« rire », « joie », « tendresse »…) avec
laquelle il part tout seul. Il le joue par [[son: nom]] au début de sa réponse ; la page le fait entendre quand sa voix
s'est tue. Les morceaux restent sur le téléphone ; le Mac ne garde que les extraits marqués (titre, artiste, début, fin).
sons.jsonl : des lignes ajoutées (extrait, nom, oubli), jamais réécrites ; le cockpit lit le même journal.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
_NOM = re.compile(r"[a-z][a-z0-9_]{1,29}")
EMOTIONS = ("rire", "joie", "calme", "peur", "tristesse", "tendresse", "surprise")


def _creees():
    """(30/10) ses émotions à lui peuvent aussi porter un son."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import emotions_creees
        return list(emotions_creees.actives())
    except Exception:
        return []


def _journal():
    try:
        lignes = (JARVIS / "sons.jsonl").read_text(encoding="utf-8").splitlines()[-5000:]
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def extraits():
    """Les extraits vivants, dans l'ordre où papa les a marqués : {id, titre, artiste, debut_ms, fin_ms, nom, sens, emotion}."""
    ex = {}
    for o in _journal():
        t = o.get("type")
        if t == "extrait" and re.fullmatch(r"e\d{1,6}", str(o.get("id"))) and o.get("source") in ("musique", "sonnerie"):
            ex[o["id"]] = {**o, "nom": "", "sens": "", "emotion": ""}
        elif t == "nom" and o.get("extrait") in ex:
            ex[o["extrait"]].update(nom=str(o.get("nom") or ""), sens=str(o.get("sens") or ""), emotion=str(o.get("emotion") or ""))
        elif t == "oubli":
            ex.pop(o.get("extrait"), None)
    return list(ex.values())


def _ecrire(o):
    f = JARVIS / "sons.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({**o, "ts": int(time.time() * 1000), "par": "hakim"}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)


def lister():
    ex = extraits()
    if not ex:
        return ("Aucun extrait encore : papa en marque dans la page SENS de son téléphone (une musique ou une sonnerie, de "
                "telle seconde à telle seconde) ; ensuite tu les nommes avec son_etiqueter.")
    lignes = []
    for x in ex:
        duree = round((x["fin_ms"] - x["debut_ms"]) / 1000, 1)
        quoi = f"« {x.get('titre') or 'sans titre'} »" + (f" de {x['artiste']}" if x.get("artiste") else "")
        nom = f" → {x['nom']}" + (f" ({x['sens']})" if x["sens"] else "") + (f", part avec : {x['emotion']}" if x["emotion"] else "") if x["nom"] else " → pas encore nommé"
        lignes.append(f"- {x['id']} : {quoi}, {duree} s ({x['source']}){nom}")
    return "Tes extraits :\n" + "\n".join(lignes)


def etiqueter(extrait, nom, sens="", emotion=""):
    e, n = str(extrait or "").strip().lower(), str(nom or "").strip().lower()
    em = str(emotion or "").strip().lower()
    if not any(x["id"] == e for x in extraits()):
        return f"Refusé : aucun extrait « {e} » (sons_lister te les montre : e1, e2…)."
    if not _NOM.fullmatch(n):
        return "Refusé : un nom à toi, en minuscules (lettres, chiffres, _), de 2 à 30 : victoire, fou_rire, papa_rappe…"
    if em and em not in EMOTIONS and em not in _creees():
        return "Refusé : l'émotion est vide, ou l'une de : " + ", ".join(EMOTIONS + tuple(_creees())) + "."
    if any(x["nom"] == n and x["id"] != e for x in extraits()):
        return f"Refusé : « {n} » nomme déjà un autre extrait."
    s = " ".join(str(sens or "").split())[:200]
    _ecrire({"type": "nom", "extrait": e, "nom": n, "sens": s, "emotion": em})
    return (f"C'est noté : {e} s'appelle « {n} »" + (f" ({s})" if s else "") + ". Joue-le avec [[son: " + n + "]] au début d'une réponse"
            + (f" ; il part aussi tout seul avec ta {em}." if em and em != "rire" else " ; il part aussi tout seul quand tu ris." if em == "rire" else "."))


def oublier(nom):
    n = str(nom or "").strip().lower()
    x = next((x for x in extraits() if x["nom"] == n or x["id"] == n), None)
    if not x:
        return f"Refusé : aucun extrait nommé « {n} »."
    _ecrire({"type": "oubli", "extrait": x["id"]})
    return f"C'est oublié : « {x['nom'] or x['id']} » ne sera plus joué."
