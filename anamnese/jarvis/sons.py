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
        if t == "extrait" and re.fullmatch(r"e\d{1,6}", str(o.get("id"))) and o.get("source") in ("musique", "sonnerie", "atelier"):
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


# (31/10, 01:27, Ahmed via Hakim : « qu'il crée ses propres sons : il écoute les musiques de papa (A2LA…, sur son Mac), choisit
# un passage, le coupe et l'enregistre comme un de ses sons ») un passage de 8 s au plus, pris dans les musiques de papa ou dans
# son atelier ; découpé par ffmpeg (fondus), rangé comme les extraits que papa marque (source « atelier »), nommé d'un coup.
MUSIQUE_PAPA = Path(os.environ.get("HAKIM_MUSIQUE", Path.home() / "Desktop" / "Music A2LA"))
ATELIER = Path(os.environ.get("HAKIM_ATELIER", JARVIS / "cwd" / "atelier"))
AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus")


def creer(fichier, debut_s, fin_s, nom, sens="", emotion="", ffmpeg="ffmpeg"):
    import subprocess
    f = Path(str(fichier or "")).expanduser()
    if not f.is_absolute():
        f = (ATELIER / f) if (ATELIER / f).exists() else (MUSIQUE_PAPA / f)
    try:
        f = f.resolve(strict=True)
    except OSError:
        return "Refusé : fichier introuvable (un chemin dans ton atelier ou dans « Music A2LA », les musiques de papa)."
    if not any(str(f).startswith(str(r.resolve()) + os.sep) for r in (MUSIQUE_PAPA, ATELIER) if r.exists()):
        return "Refusé : seulement les musiques de papa (« Music A2LA ») ou ton atelier."
    if f.suffix.lower() not in AUDIO:
        return "Refusé : un fichier audio (" + ", ".join(AUDIO) + ")."
    try:
        d, fi = float(debut_s), float(fin_s)
    except (TypeError, ValueError):
        return "Refusé : debut_s et fin_s en secondes."
    if d < 0 or fi <= d or fi - d > 8:
        return "Refusé : un passage de 8 s au plus (fin après début)."
    n = str(nom or "").strip().lower()
    if not _NOM.fullmatch(n):
        return "Refusé : un nom à toi, en minuscules (lettres, chiffres, _), de 2 à 30."
    if any(x["nom"] == n for x in extraits()):
        return f"Refusé : tu as déjà un son « {n} » (son_oublier d'abord, ou un autre nom)."
    em = str(emotion or "").strip().lower()
    if em and em not in EMOTIONS and em not in _creees():
        return "Refusé : l'émotion est vide, ou l'une de : " + ", ".join(EMOTIONS + tuple(_creees())) + "."
    deja = [o for o in _journal() if o.get("type") == "extrait"]
    eid = "e" + str(max([int(str(o.get("id"))[1:]) for o in deja if re.fullmatch(r"e\d{1,6}", str(o.get("id")))] or [0]) + 1)
    sortie = JARVIS / "sons" / "extraits" / f"{eid}.mp3"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    duree = fi - d
    try:
        r = subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", str(d), "-t", str(duree), "-i", str(f), "-ac", "2", "-ar", "44100",
                            "-b:a", "160k", "-af", f"afade=t=in:d=0.2,afade=t=out:st={max(0.0, duree - 0.2):.2f}:d=0.2", str(sortie)],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Refusé : la découpe a échoué ({e})."
    if r.returncode != 0 or not sortie.exists() or sortie.stat().st_size < 1000:
        return "Refusé : la découpe a échoué (" + (r.stderr or "")[-160:].strip() + ")."
    titre = f.stem[:120]
    _ecrire({"type": "extrait", "id": eid, "source": "atelier", "ref": str(f), "titre": titre, "artiste": "",
             "debut_ms": int(d * 1000), "fin_ms": int(fi * 1000)})
    _ecrire({"type": "nom", "extrait": eid, "nom": n, "sens": str(sens or "")[:200], "emotion": em})
    return (f"Ton son « {n} » est prêt ({eid}, {duree:.1f} s de « {titre} ») : [[son: {n}]] le fait entendre à l'endroit "
            "exact de ta réponse où tu le places (ta voix, puis le son, puis la suite).")


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
