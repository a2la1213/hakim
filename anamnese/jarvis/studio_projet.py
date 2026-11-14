"""Le studio multipiste de Hakim et de papa (13/11, Ahmed : « un vrai studio complet avec différentes pistes et différents réglages, un
peu comme Logic Pro simplifié […] qu'il gère tout ça piste par piste pour un mix et un mastering parfaits »).

UN PROJET = un dossier sous ~/AIOS/jarvis/chansons/studio/projets/<id>/ :
  projet.json      les pistes, leurs régions sur la ligne du temps, leurs réglages, le tempo, la tonalité, les zones et les marqueurs ;
  pistes/          les sons du projet (pistes séparées, voix de Hakim, prises de papa, ajouts) ;
  rendus/          les exports (le son entier, la version « zones de papa en instru seule », les pistes séparées) et leurs mesures.

Une piste : sa voix (Hakim, papa), l'instru entière ou une de ses pistes séparées (batterie, basse, mélodie et autres, guitare, piano,
la voix d'origine), ou un ajout. Ses réglages : volume, panoramique, muet, solo, égaliseur (coupe-bas, grave, médium, aigu), compresseur,
dé-esseur, envois vers la réverbération et le délai (calé sur le tempo), autotune (léger ou fort), sidechain (creusée sous une autre
piste), et une automation de volume (des points dans le temps).

LES ZONES : « couplet de papa », « refrain de Hakim »… Dans la version pour papa, toutes les voix se taisent dans ses zones (fondus de
40 ms) : il y pose la sienne.

LE RENDU : un seul graphe ffmpeg (chaque région découpée et placée, chaque piste sa chaîne, les bus de réverbération et de délai, le
sidechain), puis le mastering en Python : égaliseur vers la courbe du genre (la moitié de l'écart, ±3 dB), compression de bus,
gain itératif vers le LUFS visé et limiteur suréchantillonné (×4) jusqu'à une crête vraie ≤ −1 dBTP, VÉRIFIÉE sur le WAV et le MP3.
Chaque étape est mesurée (studio_mesures).

Ce fichier ne dépend que de la bibliothèque standard et de numpy (et de studio_mesures) ; l'autotune passe par studio.autotuner_voix
(le venv du chant). Les calculs sont des travaux de la file du studio (studio.py : un seul travailleur, sous nice).
"""
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))

import studio  # noqa: E402  (les chemins, ffmpeg, la file, le téléphone)

FFMPEG = studio.FFMPEG
SR = 44100

ROLES = {
    "voix_hakim": "Voix de Hakim", "voix_papa": "Voix de papa", "voix_origine": "Voix d'origine", "voix": "Voix",
    "instru": "Instru", "batterie": "Batterie", "basse": "Basse", "melodie": "Mélodie et autres", "guitare": "Guitare",
    "piano": "Piano", "ajout": "Ajout",
}
ROLES_VOIX = {"voix_hakim", "voix_papa", "voix_origine", "voix"}
SOURCE_ROLE = {"vocals": "voix_origine", "drums": "batterie", "bass": "basse", "other": "melodie", "guitar": "guitare", "piano": "piano"}
COULEURS = {"voix_hakim": "#2dd4bf", "voix_papa": "#facc15", "voix_origine": "#38bdf8", "voix": "#a78bfa", "instru": "#94a3b8",
            "batterie": "#f97316", "basse": "#ef4444", "melodie": "#22c55e", "guitare": "#eab308", "piano": "#e879f9", "ajout": "#cbd5e1"}
QUI_ZONES = ("papa", "hakim", "instru", "tous")
EXT_SON = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".aac", ".webm")
MAX_PISTES = 16


class Refus(Exception):
    pass


# ------------------------------------------------------------------------------------------------ les chemins
def racine(studio_dir=None):
    return Path(studio_dir or studio.STUDIO) / "projets"


def dossier(pid, studio_dir=None):
    if not re.fullmatch(r"PJ-\d{8}-\d{6}-[0-9a-f]{4}", str(pid or "")):
        raise Refus(f"projet inconnu : {pid}")
    d = racine(studio_dir) / pid
    if not (d / "projet.json").is_file():
        raise Refus(f"projet inconnu : {pid}")
    return d


def _num(v, a, b, defaut):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defaut
    if math.isnan(x) or math.isinf(x):
        return defaut
    return max(a, min(b, x))


def _mot(v, n=80):
    return " ".join(re.sub(r"[\x00-\x1f<>]", " ", str(v or "")).split())[:n]


# ------------------------------------------------------------------------------------------------ le projet sur le disque
def pro_defaut():
    """(13/11, le studio pro) les réglages pro d'une voix : studio_pro.reglages_defaut (le nettoyage mesuré, le type de voix)."""
    import studio_pro
    return studio_pro.reglages_defaut()


def reglages_par_defaut(role):
    voix = role in ROLES_VOIX
    r = {
        "volume_db": 0.0, "pan": 0.0, "muet": False, "solo": False,
        "eq": {"coupe_bas_hz": 90.0 if voix else 0.0, "grave_db": 0.0, "grave_hz": 120.0, "medium_db": 0.0, "medium_hz": 1000.0,
               "medium_q": 1.0, "aigu_db": 0.0, "aigu_hz": 8000.0, "coupe_haut_hz": 0.0},
        "comp": {"actif": voix, "seuil_db": -20.0, "ratio": 3.0, "attaque_ms": 5.0, "relache_ms": 120.0, "gain_db": 0.0},
        # (13/11, le studio pro) la compression en deux temps : les crêtes d'abord (rapide), puis le nivellement lent (« comp »)
        "comp_rapide": {"actif": False, "seuil_db": -10.0, "ratio": 6.0, "attaque_ms": 1.0, "relache_ms": 60.0},
        "saturation": 0.0,
        "deesser": 0.0, "reverb": 0.15 if voix else 0.0, "delai": 0.0, "delai_note": "1/8.", "autotune": "",
        "sidechain": {"cle": "", "db": 0.0}, "automation": [], "jetes": [],
    }
    if voix:
        r["pro"] = pro_defaut()
    return r


def _pro(t):
    """Les réglages pro d'une piste (une voix d'un projet d'avant le 13/11 au soir : la chaîne pro coupée, rien ne change pour elle)."""
    if t.get("role") not in ROLES_VOIX:
        return None
    pr = t.get("pro")
    return pr if isinstance(pr, dict) else {"actif": False}


def nouveau(titre, tempo=0.0, tonalite="", genre="trap", studio_dir=None, source=None):
    """Un projet vide (rev 1). Rend sa fiche."""
    pid = f"PJ-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    d = racine(studio_dir) / pid
    (d / "pistes").mkdir(parents=True, exist_ok=True)
    (d / "rendus").mkdir(parents=True, exist_ok=True)
    p = {"id": pid, "titre": _mot(titre, 80) or "Projet", "rev": 1, "cree": time.time(), "modifie": time.time(),
         "tempo": float(_num(tempo, 0, 300, 0)), "premier_temps_s": 0.0, "mesure": 4, "tonalite": _mot(tonalite, 20),
         "genre": _mot(genre, 20) or "trap", "duree_s": 0.0, "source": source or {}, "pistes": [], "zones": [], "marqueurs": [],
         "reference": reference_defaut(),
         "master": {"lufs": -14.0, "crete_dbtp": -1.0, "eq_auto": True, "comp": True, "cible": "streaming", "multibande": True,
                    "largeur": "auto", "mono_graves_hz": 120, "dither16": True},
         "rendus": [], "etat": "prêt", "journal": []}
    _ecrire(d / "projet.json", p)
    return p


def _ecrire(f, p):
    f = Path(f)
    tmp = f.with_name(f".{f.name}.{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def lire(pid, studio_dir=None):
    return json.loads((dossier(pid, studio_dir) / "projet.json").read_text(encoding="utf-8"))


def modifier(pid, fonction, rev=None, studio_dir=None, note=""):
    """Lire, changer (fonction(projet) → None), réécrire, sous un verrou ; rev donné et dépassé (la page avait une version d'avant) :
    Refus. Rend le projet changé."""
    import fcntl
    d = dossier(pid, studio_dir)
    with open(d / ".verrou", "w") as v:
        fcntl.flock(v, fcntl.LOCK_EX)
        try:
            p = json.loads((d / "projet.json").read_text(encoding="utf-8"))
            if rev is not None and int(rev) != int(p.get("rev", 0)):
                raise Refus(f"le projet a changé entre-temps (version {p.get('rev')}, la tienne {rev}) : recharge-le")
            fonction(p)
            p["rev"] = int(p.get("rev", 0)) + 1
            p["modifie"] = time.time()
            if note:
                p.setdefault("journal", []).append({"t": time.time(), "quoi": _mot(note, 200)})
                p["journal"] = p["journal"][-60:]
            _ecrire(d / "projet.json", p)
            return p
        finally:
            fcntl.flock(v, fcntl.LOCK_UN)


def lister(studio_dir=None):
    l = []
    for f in racine(studio_dir).glob("PJ-*/projet.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            l.append({k: p.get(k) for k in ("id", "titre", "tempo", "tonalite", "duree_s", "modifie", "etat", "rev")} | {"pistes": len(p.get("pistes", []))})
        except (OSError, ValueError):
            pass
    return sorted(l, key=lambda x: x.get("modifie") or 0, reverse=True)


def trouver(demande, studio_dir=None):
    """Un projet par son identifiant ou son titre (le plus récent qui le porte). Rend l'identifiant."""
    q = " ".join(str(demande or "").split())
    if not q:
        l = lister(studio_dir)
        if not l:
            raise Refus("aucun projet dans le studio")
        return l[0]["id"]
    if re.fullmatch(r"PJ-\d{8}-\d{6}-[0-9a-f]{4}", q):
        dossier(q, studio_dir)
        return q
    k = studio._cle(q)
    for x in lister(studio_dir):
        if studio._cle(x["titre"]) == k:
            return x["id"]
    for x in lister(studio_dir):
        if k and k in studio._cle(x["titre"]):
            return x["id"]
    raise Refus(f"aucun projet ne s'appelle « {q} »")


# ------------------------------------------------------------------------------------------------ les pistes
def _piste_id(p):
    n = 1 + max([int(x["id"][1:]) for x in p["pistes"] if re.fullmatch(r"t\d+", x.get("id", ""))] or [0])
    return f"t{n}"


def ajouter_piste(p, fichier, role="ajout", nom="", debut_s=0.0, duree_s=None, reglages=None, origine=""):
    """Ajoute une piste au projet (en mémoire). fichier : un chemin RELATIF au dossier du projet (pistes/…). Rend la piste."""
    if len(p["pistes"]) >= MAX_PISTES:
        raise Refus(f"{MAX_PISTES} pistes au plus")
    role = role if role in ROLES else "ajout"
    t = {"id": _piste_id(p), "nom": _mot(nom, 60) or ROLES[role], "role": role, "fichier": str(fichier), "couleur": COULEURS[role],
         "origine": _mot(origine, 120), "duree_fichier_s": duree_s,
         "regions": [{"debut_s": float(_num(debut_s, 0, 3600, 0)), "source_debut_s": 0.0, "duree_s": None, "gain_db": 0.0}],
         **reglages_par_defaut(role)}
    if reglages:
        regler_piste(t, reglages)
    p["pistes"].append(t)
    return t


def piste(p, ident):
    q = str(ident or "").strip()
    for t in p["pistes"]:
        if t["id"] == q:
            return t
    k = studio._cle(q)
    for t in p["pistes"]:
        if studio._cle(t["nom"]) == k or t["role"] == q or studio._cle(ROLES.get(t["role"], "")) == k:
            return t
    for t in p["pistes"]:
        if k and (k in studio._cle(t["nom"])):
            return t
    raise Refus(f"piste inconnue : {ident} (pistes : {', '.join(t['id'] + ' ' + t['nom'] for t in p['pistes'])})")


NOTES_DELAI = {"1/4": 1.0, "1/8": 0.5, "1/8.": 0.75, "1/16": 0.25, "1/4.": 1.5, "1/2": 2.0}


def regler_piste(t, r):
    """Les réglages d'une piste, bornés (rien d'autre n'est accepté). r : un dict (les clés absentes ne changent pas)."""
    r = dict(r or {})
    if "nom" in r:
        t["nom"] = _mot(r["nom"], 60) or t["nom"]
    if "role" in r and r["role"] in ROLES:
        t["role"], t["couleur"] = r["role"], COULEURS[r["role"]]
    if "volume_db" in r:
        t["volume_db"] = round(_num(r["volume_db"], -60, 12, t["volume_db"]), 1)
    if "pan" in r:
        t["pan"] = round(_num(r["pan"], -1, 1, t["pan"]), 2)
    for k in ("muet", "solo"):
        if k in r:
            t[k] = bool(r[k]) if not isinstance(r[k], str) else r[k].lower() in ("1", "true", "oui", "vrai")
    eq = dict(r.get("eq") or {})
    for k, (a, b) in {"coupe_bas_hz": (0, 400), "grave_db": (-12, 12), "grave_hz": (40, 400), "medium_db": (-12, 12),
                      "medium_hz": (150, 8000), "medium_q": (0.3, 6), "aigu_db": (-12, 12), "aigu_hz": (2000, 16000),
                      "coupe_haut_hz": (0, 20000)}.items():
        if k in eq:
            v = round(_num(eq[k], a, b, t["eq"].get(k, 0.0)), 2)
            t["eq"][k] = (0.0 if v < 1000 else v) if k == "coupe_haut_hz" else v       # un coupe-haut sous 1 kHz : sans
    c = dict(r.get("comp") or {})
    if "actif" in c:
        t["comp"]["actif"] = bool(c["actif"])
    for k, (a, b) in {"seuil_db": (-50, 0), "ratio": (1, 20), "attaque_ms": (0.1, 200), "relache_ms": (5, 2000), "gain_db": (0, 18)}.items():
        if k in c:
            t["comp"][k] = round(_num(c[k], a, b, t["comp"][k]), 2)
    cr = dict(r.get("comp_rapide") or {})
    if cr:
        t.setdefault("comp_rapide", reglages_par_defaut("ajout")["comp_rapide"])
        if "actif" in cr:
            v = cr["actif"]
            t["comp_rapide"]["actif"] = v.lower() in ("1", "oui", "vrai", "true", "on") if isinstance(v, str) else bool(v)
        for k, (a, b) in {"seuil_db": (-50, 0), "ratio": (1, 20), "attaque_ms": (0.05, 50), "relache_ms": (5, 1000)}.items():
            if k in cr:
                t["comp_rapide"][k] = round(_num(cr[k], a, b, t["comp_rapide"][k]), 2)
    for k in ("deesser", "reverb", "delai", "saturation"):
        if k in r:
            t[k] = round(_num(r[k], 0, 1, t.get(k, 0.0)), 2)
    if "pro" in r and (t.get("role") in ROLES_VOIX or isinstance(t.get("pro"), dict)):
        import studio_pro
        t["pro"] = studio_pro.borner(r["pro"] if isinstance(r["pro"], dict) else {}, t.get("pro") or pro_defaut())
    if "jetes" in r:
        l = []
        for x in (r["jetes"] or [])[:64]:
            try:
                a, b = _num(x[0], 0, 3600, 0), _num(x[1], 0, 3600, 0)
            except (TypeError, IndexError, KeyError):
                continue
            if b - a >= 0.05:
                l.append([round(a, 3), round(b, 3)])
        t["jetes"] = sorted(l)
    if "delai_note" in r and r["delai_note"] in NOTES_DELAI:
        t["delai_note"] = r["delai_note"]
    if "autotune" in r:
        v = r["autotune"]
        t["autotune"] = studio.niveau_autotune(v) if not isinstance(v, str) or v not in ("leger", "fort", "") else v
    if "sidechain" in r:
        s = r["sidechain"] or {}
        t["sidechain"] = {"cle": _mot(s.get("cle"), 8), "db": round(_num(s.get("db"), 0, 12, 0), 1)}
    if "automation" in r:
        pts = []
        for x in (r["automation"] or [])[:64]:
            try:
                pts.append({"t": round(_num(x["t"], 0, 3600, 0), 3), "db": round(_num(x["db"], -60, 12, 0), 1)})
            except (KeyError, TypeError):
                continue
        t["automation"] = sorted(pts, key=lambda x: x["t"])
    if "regions" in r:
        rs = []
        for x in (r["regions"] or [])[:32]:
            try:
                rs.append({"debut_s": round(_num(x.get("debut_s"), 0, 3600, 0), 3),
                           "source_debut_s": round(_num(x.get("source_debut_s"), 0, 3600, 0), 3),
                           "duree_s": None if x.get("duree_s") in (None, "") else round(_num(x["duree_s"], 0.05, 3600, 1), 3),
                           "gain_db": round(_num(x.get("gain_db"), -60, 12, 0), 1)})
            except (AttributeError, TypeError):
                continue
        if rs:
            t["regions"] = sorted(rs, key=lambda x: x["debut_s"])
    return t


# ------------------------------------------------------------------------------------------------ le temps : mesures, zones
def seconde_de_mesure(p, m, temps=1.0):
    """La mesure m (1 = la première), au temps donné (1 = son premier temps) → secondes (le tempo et le premier temps du projet)."""
    bpm = float(p.get("tempo") or 0)
    if bpm <= 0:
        raise Refus("le tempo du projet n'est pas connu : donne les zones en secondes (1:17-1:41)")
    return round(float(p.get("premier_temps_s") or 0) + ((float(m) - 1) * int(p.get("mesure") or 4) + (float(temps) - 1)) * 60.0 / bpm, 3)


def _temps(p, s):
    """« 1:17 » / « 77.5 » / « 77,5 s » / « m9 » (début de la mesure 9) → secondes."""
    s = str(s).strip().lower().replace(",", ".").rstrip("s").strip()
    m = re.fullmatch(r"m(?:esure)?\s*(\d+(?:\.\d+)?)", s)
    if m:
        return seconde_de_mesure(p, float(m.group(1)))
    m = re.fullmatch(r"(\d+):(\d{1,2}(?:\.\d+)?)", s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    return float(s)


def lire_zones(p, texte):
    """« couplet de papa : 1:17-1:41 ; refrain Hakim : m9-m13 » → zones. Le « qui » se devine du nom (papa, hakim), sinon « instru ».
    Une zone en mesures s'arrête au DÉBUT de la mesure de fin (m9-m13 = 4 mesures)."""
    zones = []
    T = r"(?:m(?:esure)?\s*\d+(?:[.,]\d+)?|\d+:\d{1,2}(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*s?"
    for i, bout in enumerate(x for x in re.split(r"[;\n]+", str(texte or "")) if x.strip()):
        ms = list(re.finditer(rf"({T})\s*(?:-|–|à|->)\s*({T})", bout, re.I))
        if not ms:
            raise Refus(f"zone illisible : « {bout.strip()} » (exemple : « couplet de papa : 1:17-1:41 » ou « m9-m23 »)")
        m = ms[-1]                                            # la dernière plage (un nom peut porter un chiffre : « couplet 2 »)
        nom = bout[: m.start()].strip(" :-–\t")
        a, b = _temps(p, m.group(1)), _temps(p, m.group(2))
        if b <= a:
            raise Refus(f"zone à l'envers : « {bout.strip()} »")
        nom = _mot(nom, 60) or f"Zone {i + 1}"
        k = studio._cle(nom)
        qui = "papa" if re.search(r"\b(papa|ahmed|a2la|toi)\b", k) else "hakim" if re.search(r"\b(hakim|hk|moi)\b", k) else "instru"
        zones.append({"id": f"z{i + 1}", "nom": nom, "debut_s": round(a, 3), "fin_s": round(b, 3), "qui": qui})
    return zones


def regler_zones(p, zones):
    l = []
    for i, z in enumerate((zones or [])[:32]):
        a, b = _num(z.get("debut_s"), 0, 3600, 0), _num(z.get("fin_s"), 0, 3600, 0)
        if b - a < 0.2:
            continue
        l.append({"id": f"z{i + 1}", "nom": _mot(z.get("nom"), 60) or f"Zone {i + 1}", "debut_s": round(a, 3), "fin_s": round(b, 3),
                  "qui": z.get("qui") if z.get("qui") in QUI_ZONES else "instru"})
    p["zones"] = sorted(l, key=lambda z: z["debut_s"])
    return p["zones"]


# ------------------------------------------------------------------------------------------------ (14/11) la voix de référence
# Ahmed (14/11) : « j'aimerais juste que les mix [de ma voix] soient aussi bien que sa voix ». La référence : la voix de Hakim du projet
# (« auto » : sa première voix principale), une voix choisie (« piste »), un profil gardé (« profil » : studio/references/<nom>.json ;
# « auto » s'y replie quand le projet n'a pas de voix de Hakim), ou « aucune ». studio_pro_reference fait le calage.
SOURCES_REF = ("auto", "piste", "profil", "aucune")


def reference_defaut():
    return {"source": "auto", "piste": "", "profil": "hakim"}


def references_dir(studio_dir=None):
    return Path(studio_dir or studio.STUDIO) / "references"


def regler_reference(p, q):
    """La référence du projet, bornée : source (auto, piste, profil, aucune), piste (son identifiant), profil (son nom)."""
    r = dict(reference_defaut(), **(p.get("reference") or {}))
    if q.get("source") in SOURCES_REF:
        r["source"] = q["source"]
    if "piste" in q:
        v = str(q.get("piste") or "")
        r["piste"] = v if re.fullmatch(r"t\d{1,3}", v) else ""
    if "profil" in q:
        r["profil"] = re.sub(r"[^a-z0-9-]", "", studio._cle(str(q.get("profil") or "")).replace(" ", "-"))[:30] or "hakim"
    p["reference"] = r
    return r


def piste_reference(p):
    """La piste de référence du projet (une voix qui sonne), ou None."""
    r = dict(reference_defaut(), **(p.get("reference") or {}))
    if r["source"] in ("aucune", "profil"):
        return None
    vivantes = [t for t in p["pistes"] if t["role"] in ROLES_VOIX and not t.get("muet")]
    if r["source"] == "piste":
        return next((t for t in vivantes if t["id"] == r["piste"]), None)
    return next((t for t in vivantes if t["role"] == "voix_hakim" and type_voix(t) in ("principale", None)), None)


def profil_garde(p, studio_dir=None):
    """Le profil gardé que le projet utilise (source « profil », ou « auto » sans voix de Hakim), ou None."""
    r = dict(reference_defaut(), **(p.get("reference") or {}))
    if r["source"] in ("aucune", "piste") or (r["source"] == "auto" and piste_reference(p) is not None):
        return None
    import studio_pro_reference as R
    g = R.lire_profil(references_dir(studio_dir) / f"{r['profil']}.json")
    if g:
        g["nom"] = r["profil"]
    return g


def est_calee(t, ref_id):
    """Une voix calée sur la référence : sa chaîne pro active, son mode « oui », ou « auto » pour la voix de papa ; jamais la référence."""
    import studio_pro
    pr = _pro(t)
    if not pr or not pr.get("actif") or t["id"] == ref_id or "reference" in studio_pro.COUPE:
        return False
    mode = pr.get("reference", "auto")
    return mode == "oui" or (mode == "auto" and t["role"] == "voix_papa")


def _cle_fichier(f, *autre):
    import hashlib
    st = Path(f).stat()
    return hashlib.sha1(json.dumps([Path(f).name, st.st_mtime_ns, st.st_size, *autre], sort_keys=True, default=str).encode()).hexdigest()[:16]


def _profil_en_cache(f, dpro):
    """Le profil (studio_pro_reference.profil) d'une voix, gardé en cache à côté des voix nettoyées. Rend (profil, clé)."""
    import studio_mesures as M
    import studio_pro_reference as R
    cle = _cle_fichier(f, R.VERSION)
    c = Path(dpro) / f"ref-{cle}.json"
    if c.is_file():
        try:
            return json.loads(c.read_text(encoding="utf-8")), cle
        except ValueError:
            pass
    x, _ = M.lire(f)
    prof = R.profil(x)
    Path(dpro).mkdir(parents=True, exist_ok=True)
    c.write_text(json.dumps(prof, ensure_ascii=False, default=float), encoding="utf-8")
    return prof, cle


def _tranche(t):
    """Ce qu'une voix calée reprend de la tranche de la référence : son égaliseur (hors coupe-bas : chacun le sien), sa saturation, son
    dé-esseur, ses envois (réverbération, délai et sa note) et la forme de ses compressions (ratio, attaque, relâche ; les seuils
    restent ceux de chaque voix, posés sur son propre niveau)."""
    eq = t.get("eq") or {}
    return {"eq": {k: eq.get(k) for k in ("medium_hz", "medium_q", "medium_db", "aigu_hz", "aigu_db", "coupe_haut_hz") if k in eq},
            "saturation": t.get("saturation", 0.0), "deesser": t.get("deesser", 0.0), "reverb": t.get("reverb", 0.0),
            "delai": t.get("delai", 0.0), "delai_note": t.get("delai_note", "1/8."),
            "comp": {k: (t.get("comp") or {}).get(k) for k in ("ratio", "attaque_ms", "relache_ms") if k in (t.get("comp") or {})},
            "comp_rapide": {k: (t.get("comp_rapide") or {}).get(k) for k in ("ratio", "attaque_ms", "relache_ms")
                            if k in (t.get("comp_rapide") or {})}}


def _poser_tranche(t, tr):
    t.setdefault("eq", {}).update({k: v for k, v in (tr.get("eq") or {}).items() if v is not None})
    for k in ("saturation", "deesser", "reverb", "delai"):
        if k in tr:
            t[k] = round(_num(tr[k], 0, 1, t.get(k, 0.0)), 2)
    if tr.get("delai_note") in NOTES_DELAI:
        t["delai_note"] = tr["delai_note"]
    t.setdefault("comp", {}).update({k: v for k, v in (tr.get("comp") or {}).items() if v is not None})
    t.setdefault("comp_rapide", {}).update({k: v for k, v in (tr.get("comp_rapide") or {}).items() if v is not None})


def _rendre_seule(p, d, travail, fichiers, t, humide, nom):
    """Le rendu d'une piste seule (sans son sidechain), avec ou sans ses envois : le son que mesure le calage au mix."""
    import studio_mesures as M
    q = copy.deepcopy(p)
    tq = next(x for x in q["pistes"] if x["id"] == t["id"])
    tq["sidechain"] = {"cle": "", "db": 0.0}
    if not humide:
        tq["reverb"], tq["delai"] = 0.0, 0.0
    f = Path(travail) / f"seule-{t['id']}-{nom}.wav"
    try:
        rendre_bus(q, d, f, seules=[t["id"]], fichiers=fichiers)
        x, _ = M.lire(f)
    finally:
        f.unlink(missing_ok=True)
    return x


def cibles_reference(p, d, travail, fichiers, ref_t):
    """Les cibles au mix d'une référence : sa densité et ses sifflantes sur son rendu SEC, son espace sur son rendu avec ses envois."""
    import studio_pro_reference as R
    sec = R.mesure_mix(_rendre_seule(p, d, travail, fichiers, ref_t, False, "ref-sec"))
    hum = R.mesure_mix(_rendre_seule(p, d, travail, fichiers, ref_t, True, "ref-humide"), fins=sec["_fins"])
    return {"sec": {k: v for k, v in sec.items() if k != "_fins"}, "humide": {k: v for k, v in hum.items() if k != "_fins"}}


def caler_au_mix(p, d, travail, fichiers, rap_pro, rapport, journal=None):
    """(14/11) Le calage sur la référence, au mix, pour chaque voix principale calée, mesuré sur le rendu de la piste seule :
      la tranche de la référence (son égaliseur, sa saturation, son dé-esseur, ses envois, la forme de ses compressions) ;
      la densité : le facteur de crête du corps de la voix (250 Hz-4 kHz) vers celui de la référence, par le seuil d'un compresseur
        de crêtes rapide (attaque 0,3 ms), jamais sous le haut de la voix (son niveau court terme fort), seulement plus serré (une voix
        rappée a des crêtes qu'une voix chantée n'a pas : ce qui reste est le style, pas le traitement) ;
      la force des sifflantes : mesurée après la tranche et dite (l'étape audio l'a calée) ;
      l'espace : l'envoi de réverbération vers la traîne de la référence après les fins de phrase (le délai repris tel quel) ;
      la parité de niveau : la même hauteur au-dessus de l'instru que la référence.
    fichiers est mis à jour si une voix est recalée. Rend {piste: écart visé (LU)}."""
    import studio_pro
    import studio_pro_reference as R
    C = studio_pro.COUPE
    say = journal or (lambda s: None)
    ctx = rap_pro.get("_reference")
    calees = [t for t in p["pistes"] if t["role"] in ROLES_VOIX and not t.get("muet") and (rap_pro.get(t["id"]) or {}).get("reference")
              and type_voix(t) in ("principale", None)]
    if not calees or not ctx:
        return {}
    ref_t = next((t for t in p["pistes"] if t["id"] == ctx.get("piste")), None)
    if ref_t is not None:
        tranche, cibles, vise = _tranche(ref_t), cibles_reference(p, d, travail, fichiers, ref_t), VOIX_AU_DESSUS.get(ref_t["role"], 1.5)
    else:
        g = profil_garde(p, Path(d).parent.parent) or {}
        tranche, cibles, vise = g.get("tranche") or {}, g.get("cibles") or {}, g.get("ecart_lu")
    sec, hum = cibles.get("sec") or {}, cibles.get("humide") or {}
    vises = {}
    for t in calees:
        r = rapport.setdefault(t["id"], {}).setdefault("reference_mix", {})
        if "ref_tranche" not in C:
            _poser_tranche(t, tranche)
            r["tranche"] = {k: tranche.get(k) for k in ("saturation", "deesser", "reverb", "delai", "delai_note")}

        fins_seches = []

        def mesure(humide=False):
            x = _rendre_seule(p, d, travail, fichiers, t, humide, "humide" if humide else "sec")
            if humide:
                return R.mesure_mix(x, fins=fins_seches or None)
            m = R.mesure_mix(x)
            fins_seches[:] = m["_fins"]
            return m
        # la densité : le facteur de crête du corps de la voix
        cd = (sec.get("dynamique") or {}).get("crete_corps_db")
        if "ref_densite" not in C and cd is not None:
            m0 = mesure()["dynamique"]
            dens = {"cible_crete_db": cd, "avant_crete_db": m0["crete_corps_db"]}
            cr = t.setdefault("comp_rapide", reglages_par_defaut("ajout")["comp_rapide"])
            if m0["crete_corps_db"] > cd + 0.5:
                haut = float(t.get("comp", {}).get("seuil_db", -26.0)) + 6           # le seuil lent est posé 6 dB sous le haut
                cr.update(actif=True, attaque_ms=0.3, relache_ms=50.0, ratio=6.0)
                base = float(cr.get("seuil_db", haut + 6))

                def crete(s_db):
                    cr["seuil_db"] = round(s_db, 1)
                    return mesure()["dynamique"]["crete_corps_db"]
                # (le 14/11 : jusqu'à 12 dB sous le haut, le seuil écrasait le rap de papa — fond +10 dB — pour 0,8 dB de crête en
                # moins : ses crêtes sont du STYLE ; le compresseur de crêtes ne descend pas sous le haut de la voix)
                v, mv, _ = R.chercher(crete, max(-50.0, haut), base, cd, True, essais=5, tolerance=0.3)
                cr["seuil_db"] = round(v, 1)
                dens.update(apres_crete_db=mv, seuil_cretes_db=cr["seuil_db"])
            else:
                dens["apres_crete_db"] = m0["crete_corps_db"]
            r["densite"] = dens
        # la force des sifflantes après la tranche : mesurée et dite (le dé-esseur de l'étape audio l'a déjà calée ; le 14/11, reprendre
        # l'écart qui restait dans l'étape audio ne changeait rien sur la vraie prise de papa : la tranche décide du reste)
        ps = (sec.get("sifflantes") or {}).get("p90_db")
        if ps is not None:
            r["sifflantes"] = {"cible_p90_db": ps, "avant_p90_db": mesure()["sifflantes"].get("p90_db")}
        # l'espace : la traîne après les fins de phrase, avec les envois
        tr = (hum.get("reverberation") or {}).get("traine_db")
        if "ref_espace" not in C and tr is not None:
            def traine(k):
                t["reverb"] = round(k, 3)
                return mesure(True)["reverberation"].get("traine_db")
            r0 = float(t.get("reverb", 0.0))
            if not fins_seches:
                mesure()
            esp = {"cible_traine_db": tr, "avant_traine_db": traine(r0), "reverb_avant": r0, "fins": len(fins_seches)}
            v, mv, _ = R.chercher(traine, 0.0, 1.0, tr, True, essais=6)
            t["reverb"] = round(v, 2)
            esp.update(apres_traine_db=mv, reverb=t["reverb"], delai=t.get("delai", 0.0), delai_note=t.get("delai_note"),
                       atteinte=mv is not None and abs(mv - tr) <= 1.5)
            r["espace"] = esp
        if "ref_parite" not in C and vise is not None:
            vises[t["id"]] = float(vise)
            r["vise_lu"] = float(vise)
        say(f"{t['nom']} : calée au mix sur la référence {r}")
    return vises


# ------------------------------------------------------------------------------------------------ le rendu (un graphe ffmpeg)
def _expr_db(points):
    """L'automation (points t, db) → une expression ffmpeg du gain en dB, linéaire entre les points, constante avant/après."""
    if not points:
        return "0"
    pts = sorted(points, key=lambda x: x["t"])
    e = f"{pts[-1]['db']:.2f}"
    for a, b in reversed(list(zip(pts, pts[1:]))):
        if b["t"] - a["t"] <= 1e-3:
            continue
        pente = (b["db"] - a["db"]) / (b["t"] - a["t"])
        e = f"if(lt(t,{b['t']:.3f}),{a['db']:.2f}+({pente:.5f})*(t-{a['t']:.3f}),{e})"
    return f"if(lt(t,{pts[0]['t']:.3f}),{pts[0]['db']:.2f},{e})"


def _expr_fenetres(fenetres, rampe=0.02):
    """1 dans les fenêtres [(a, b)] (fondus de 20 ms), 0 ailleurs : le délai jeté sur les fins de phrase."""
    if not fenetres:
        return "0"
    f = [f"clip((t-{a - rampe:.3f})/{rampe},0,1)*clip(({b + rampe:.3f}-t)/{rampe},0,1)" for a, b in fenetres]
    return f"min(1,{'+'.join(f)})"


def predelai_ms(bpm):
    """Le pré-délai de la réverbération : une triple croche au tempo (140 BPM : 54 ms), entre 15 et 60 ms ; 20 ms sans tempo."""
    if not bpm or bpm <= 0:
        return 20.0
    return round(max(15.0, min(60.0, 60000.0 / bpm / 8)), 1)


def _expr_muet_zones(zones, rampe=0.04):
    """Le multiplicateur 0 dans les zones (fondus de 40 ms), 1 ailleurs."""
    if not zones:
        return "1"
    f = []
    for z in zones:
        a, b = z["debut_s"], z["fin_s"]
        f.append(f"(1-clip((t-{a - rampe:.3f})/{rampe},0,1)*clip(({b + rampe:.3f}-t)/{rampe},0,1))")
    return "*".join(f)


def _chaine_piste(t, bpm):
    """Les filtres d'une piste (après le placement de ses régions), dans l'ordre d'une tranche de console."""
    f = []
    eq = t["eq"]
    if eq.get("coupe_bas_hz", 0) >= 20:
        f.append(f"highpass=f={eq['coupe_bas_hz']:.0f}:poles=2")
    if eq.get("coupe_haut_hz", 0) >= 1000:                # (13/11) les doubles et les backs plus filtrés que la voix principale
        f.append(f"lowpass=f={eq['coupe_haut_hz']:.0f}:poles=2")
    if abs(eq.get("grave_db", 0)) >= 0.1:
        f.append(f"bass=g={eq['grave_db']:.2f}:f={eq['grave_hz']:.0f}:w=0.7")
    if abs(eq.get("medium_db", 0)) >= 0.1:
        f.append(f"equalizer=f={eq['medium_hz']:.0f}:t=q:w={eq['medium_q']:.2f}:g={eq['medium_db']:.2f}")
    if abs(eq.get("aigu_db", 0)) >= 0.1:
        f.append(f"treble=g={eq['aigu_db']:.2f}:f={eq['aigu_hz']:.0f}:w=0.7")
    # (13/11, le studio pro) la compression en deux temps : les crêtes d'abord (attaque d'1 ms, ratio 6), puis le nivellement lent
    import studio_pro
    C = studio_pro.COUPE
    cr = t.get("comp_rapide") or {}
    if cr.get("actif") and "deux_temps" not in C:
        f.append(f"acompressor=threshold={cr['seuil_db']:.1f}dB:ratio={cr['ratio']:.2f}:attack={cr['attaque_ms']:.2f}:"
                 f"release={cr['relache_ms']:.0f}:makeup=1:knee=2:detection=peak")
    c = t["comp"]
    if c.get("actif"):
        f.append(f"acompressor=threshold={c['seuil_db']:.1f}dB:ratio={c['ratio']:.2f}:attack={c['attaque_ms']:.1f}:"
                 f"release={c['relache_ms']:.0f}:makeup={max(1.0, 10 ** (c['gain_db'] / 20)):.4f}:knee=2.8")
    # une légère saturation (un excitateur : des harmoniques au-dessus de 3 kHz) pour la présence
    if "deesser_apres" in C and t.get("deesser", 0) > 0:   # témoin : le dé-esseur d'avant (devant la compression)
        f.insert(next((i for i, x in enumerate(f) if x.startswith("acompressor")), len(f)), f"deesser=i={0.2 + 0.6 * t['deesser']:.2f}:m=0.5:f=0.5")
    if t.get("saturation", 0) > 0 and "saturation" not in C:
        f.append(f"aexciter=amount={1 + 3 * t['saturation']:.2f}:drive={2 + 6 * t['saturation']:.2f}:blend=0:freq=3000:ceil=16000")
    # le dé-essage APRÈS la compression (elle remonte les sifflantes : on les reprend là)
    if t.get("deesser", 0) > 0 and "deesser_apres" not in C:
        f.append(f"deesser=i={0.2 + 0.6 * t['deesser']:.2f}:m=0.5:f=0.5")
    if t.get("profil"):                                    # (14/11) le profil de la piste (voix téléphone, radio…) : en fin de tranche
        import studio_edition
        f += studio_edition.chaine_profil(t["profil"])
    return f


def _gains_pan(pan):
    a = (float(pan) + 1) * math.pi / 4
    return math.cos(a) * math.sqrt(2), math.sin(a) * math.sqrt(2)


def reponse_impulsionnelle(chemin, sr=SR, rt60=1.6, predelai_ms=18, graine=7):
    """Une réverbération de salle (stéréo décorrélée) : un bruit qui décroît en exponentielle (−60 dB en rt60), plus sombre avec le
    temps (passe-bas qui descend), après un petit pré-délai. Écrite une fois (WAV flottant)."""
    import numpy as np
    chemin = Path(chemin)
    if chemin.is_file():
        return chemin
    rng = np.random.default_rng(graine)
    n = int(sr * rt60 * 1.1)
    t = np.arange(n) / sr
    env = 10 ** (-3 * t / rt60)
    ir = rng.standard_normal((n, 2)) * env[:, None]
    # plus sombre avec le temps : un passe-bas d'ordre 1 dont la coupure descend de 12 kHz à 2,5 kHz
    fc = 12000 * (2500 / 12000) ** (t / rt60)
    a = np.exp(-2 * np.pi * fc / sr)
    y = np.zeros_like(ir)
    for c in range(2):
        acc = 0.0
        col = ir[:, c]
        out = y[:, c]
        for i in range(n):
            acc = (1 - a[i]) * col[i] + a[i] * acc
            out[i] = acc
    pre = int(sr * predelai_ms / 1000)
    y = np.vstack([np.zeros((pre, 2)), y])
    y /= np.sqrt((y ** 2).sum(axis=0)).max() + 1e-12
    sys.path.insert(0, str(ICI))
    import studio_mesures as M
    M.ecrire_wav(chemin, y, sr, bits=32)
    return chemin


def actives(p, version="complet", seules=None):
    """Les pistes qui sonnent dans une version : complet (muet et solo respectés), papa (pareil ; les voix se taisent dans les zones de
    papa), instru (les pistes qui ne sont pas des voix), voix (les voix seules) ; seules : une liste d'identifiants (une piste exportée
    seule)."""
    l = [t for t in p["pistes"] if not t.get("muet")]
    if seules:
        return [t for t in p["pistes"] if t["id"] in seules]
    if any(t.get("solo") for t in l):
        l = [t for t in l if t.get("solo")]
    if version == "instru":
        l = [t for t in l if t["role"] not in ROLES_VOIX]
    elif version == "voix":
        l = [t for t in l if t["role"] in ROLES_VOIX]
    return l


def graphe(p, d, version="complet", seules=None, fichiers=None, ir=None, duree=None):
    """Le graphe ffmpeg d'une version : (arguments d'entrée, filter_complex, étiquette de sortie). fichiers : {piste: chemin} pour
    remplacer le son d'une piste (l'autotune déjà calculé)."""
    pistes = actives(p, version, seules)
    if not pistes:
        raise Refus("aucune piste ne sonne dans cette version")
    bpm = float(p.get("tempo") or 0)
    zones_papa = [z for z in p.get("zones", []) if z.get("qui") == "papa"] if version == "papa" else []
    entrees, chaines, sorties = [], [], []
    rev, dly, cles_voulues = [], [], {}
    import studio_pro
    bus_voix = bool((p.get("bus_voix") or {}).get("actif")) and version != "instru" and not seules and "bus_voix" not in studio_pro.COUPE
    voix_bus = []
    ids = {t["id"] for t in pistes}
    for t in pistes:
        s = t.get("sidechain") or {}
        if s.get("cle") and s.get("db", 0) > 0 and s["cle"] in ids and s["cle"] != t["id"]:
            cles_voulues.setdefault(s["cle"], []).append(t["id"])
    for t in pistes:
        f = (fichiers or {}).get(t["id"]) or str(Path(d) / t["fichier"])
        regs = t.get("regions") or [{"debut_s": 0, "source_debut_s": 0, "duree_s": None, "gain_db": 0}]
        labs = []
        for j, r in enumerate(regs):
            k = len(entrees) // 2
            entrees += ["-i", f]
            fin = "" if r.get("duree_s") is None else f":end={r['source_debut_s'] + r['duree_s']:.4f}"
            fondu = (f",afade=t=out:st={max(0.0, r['duree_s'] - 0.01):.4f}:d=0.01" if r.get("duree_s") is not None else "")
            lab = f"{t['id']}r{j}"
            chaines.append(f"[{k}:a]atrim=start={r['source_debut_s']:.4f}{fin},asetpts=PTS-STARTPTS,"
                           f"aformat=sample_fmts=fltp:sample_rates={SR}:channel_layouts=stereo,afade=t=in:d=0.005{fondu},"
                           f"volume={r.get('gain_db', 0):.2f}dB,adelay={int(round(r['debut_s'] * 1000))}:all=1,asetpts=N/SR/TB[{lab}]")
            labs.append(f"[{lab}]")
        src = f"{t['id']}src"
        chaines.append(f"{''.join(labs)}amix=inputs={len(labs)}:normalize=0:duration=longest[{src}]" if len(labs) > 1
                       else f"{labs[0]}anull[{src}]")
        ch = _chaine_piste(t, bpm)
        cur = src
        if ch:
            chaines.append(f"[{cur}]{','.join(ch)}[{t['id']}ch]")
            cur = f"{t['id']}ch"
        s = t.get("sidechain") or {}
        if s.get("cle") in cles_voulues and t["id"] in cles_voulues[s["cle"]]:
            prof = float(s["db"])
            # la profondeur visée (dB) ≈ réduction quand la clé est forte : seuil bas, ratio de la profondeur
            ratio = max(1.5, min(8.0, 1 + prof / 3))
            chaines.append(f"[{cur}][{s['cle']}cle_{t['id']}]sidechaincompress=threshold=-30dB:ratio={ratio:.2f}:attack=8:release=180:"
                           f"knee=4[{t['id']}sc]")
            cur = f"{t['id']}sc"
        gain_expr = _expr_db(t.get("automation") or [])
        mult = _expr_muet_zones(zones_papa) if (zones_papa and t["role"] in ROLES_VOIX) else "1"
        gl, gr = _gains_pan(t.get("pan", 0))
        vol = f"volume={t.get('volume_db', 0):.2f}dB"
        auto = "" if gain_expr == "0" and mult == "1" else f"asetnsamples=n=64,volume=volume='pow(10,({gain_expr})/20)*{mult}':eval=frame,"
        chaines.append(f"[{cur}]{auto}pan=stereo|c0={gl:.4f}*c0|c1={gr:.4f}*c1,{vol}[{t['id']}post]")
        outs = [f"[{t['id']}dry]"]
        if t.get("reverb", 0) > 0 and ir:
            outs.append(f"[{t['id']}rv]")
            rev.append((t["id"], t["reverb"]))
        if t.get("delai", 0) > 0 and bpm > 0:
            outs.append(f"[{t['id']}dl]")
            dly.append((t["id"], t["delai"], t.get("delai_note", "1/8."), t.get("jetes") or []))
        for cible in cles_voulues.get(t["id"], []):
            outs.append(f"[{t['id']}cle_{cible}]")
        chaines.append(f"[{t['id']}post]asplit={len(outs)}{''.join(outs)}" if len(outs) > 1 else f"[{t['id']}post]anull{outs[0]}")
        (voix_bus if (bus_voix and t["role"] in ROLES_VOIX) else sorties).append(f"[{t['id']}dry]")
    if voix_bus:
        # (13/11, le studio pro) le bus des voix : toutes les voix ensemble, une compression lente et douce qui les lie (≈ 1 à 2 dB)
        bv = p.get("bus_voix") or {}
        comp = (f"acompressor=threshold={_num(bv.get('seuil_db'), -50, 0, -22):.1f}dB:ratio={_num(bv.get('ratio'), 1, 4, 1.5):.2f}:"
                f"attack=30:release=300:knee=4:makeup={10 ** (_num(bv.get('gain_db'), 0, 6, 0) / 20):.4f}[busvoix]")
        chaines.append(f"{''.join(voix_bus)}amix=inputs={len(voix_bus)}:normalize=0,{comp}" if len(voix_bus) > 1 else f"{voix_bus[0]}{comp}")
        sorties.append("[busvoix]")
    if rev:
        k = len(entrees) // 2
        entrees += ["-i", str(ir)]
        for tid, g in rev:
            chaines.append(f"[{tid}rv]volume={20 * math.log10(max(1e-4, g)):.2f}dB[{tid}rvs]")
        lab = "".join(f"[{tid}rvs]" for tid, _ in rev)
        chaines.append(f"{lab}amix=inputs={len(rev)}:normalize=0[revin]" if len(rev) > 1 else f"{lab}anull[revin]")
        # le retour : la convolution seule (afir ne mêle pas le son sec), sans graves (coupe-bas 200 Hz : la boue reste hors de la réverb)
        # (13/11, le studio pro) et sans aigus durs (coupe-haut 8 kHz), après un pré-délai calé sur le tempo (une triple croche, 15 à
        # 60 ms) : la voix sèche passe d'abord, la salle ensuite
        pre = predelai_ms(bpm) if "predelai" not in studio_pro.COUPE else 0.0
        chaines.append(f"[revin]adelay={pre:.1f}:all=1,asetpts=N/SR/TB[revpre]" if pre > 0 else "[revin]anull[revpre]")
        haut = ",lowpass=f=8000" if "retour_filtre" not in studio_pro.COUPE else ""
        chaines.append(f"[revpre][{k}:a]afir=irnorm=-1:gtype=none,highpass=f=200{haut},volume=-6dB[revout]")
        sorties.append("[revout]")
    if dly:
        for tid, g, note, jetes in dly:
            ms = 60000.0 / bpm * NOTES_DELAI.get(note, 0.75)
            if jetes and "jete" not in studio_pro.COUPE:  # (13/11) le délai « jeté » : envoyé seulement sur les fins de phrase
                chaines.append(f"[{tid}dl]asetnsamples=n=64,volume=volume='{_expr_fenetres(jetes)}':eval=frame[{tid}dlj]")
                tid_in = f"{tid}dlj"
            else:
                tid_in = f"{tid}dl"
            chaines.append(f"[{tid_in}]volume={20 * math.log10(max(1e-4, g)):.2f}dB,asplit=3[{tid}d1][{tid}d2][{tid}d3];"
                           f"[{tid}d1]adelay={ms:.1f}:all=1,pan=stereo|c0=0.9*c0|c1=0.3*c1[{tid}e1];"
                           f"[{tid}d2]adelay={2 * ms:.1f}:all=1,volume=-6dB,pan=stereo|c0=0.3*c0|c1=0.9*c1[{tid}e2];"
                           f"[{tid}d3]adelay={3 * ms:.1f}:all=1,volume=-12dB[{tid}e3];"
                           f"[{tid}e1][{tid}e2][{tid}e3]amix=inputs=3:normalize=0,highpass=f=300,lowpass=f=6000[{tid}dlo]")
        lab = "".join(f"[{tid}dlo]" for tid, *_ in dly)
        chaines.append(f"{lab}amix=inputs={len(dly)}:normalize=0[dlyout]" if len(dly) > 1 else f"{lab}anull[dlyout]")
        sorties.append("[dlyout]")
    fin = f"asetpts=N/SR/TB,apad=whole_dur={float(duree):.3f},atrim=end={float(duree):.3f}" if duree else "anull"   # toutes les versions à la durée du projet
    if len(sorties) > 1:
        chaines.append(f"{''.join(sorties)}amix=inputs={len(sorties)}:normalize=0:duration=longest,{fin}[bus]")
    else:
        chaines.append(f"{sorties[0]}{fin}[bus]")
    return entrees, ";".join(chaines), "[bus]"


def rendre_bus(p, d, sortie, version="complet", seules=None, fichiers=None, duree=None, codec="pcm_f32le"):
    """Le bus de mix d'une version, en WAV flottant 44,1 kHz stéréo (avant le mastering)."""
    ir = reponse_impulsionnelle(racine(Path(d).parent.parent) / "reverb-salle.wav") if any(
        t.get("reverb", 0) > 0 for t in actives(p, version, seules)) else None
    entrees, fc, lab = graphe(p, d, version, seules, fichiers, ir, duree or p.get("duree_s") or None)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as g:
        g.write(fc)
        script = g.name
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *entrees, "-/filter_complex", script,
                            "-map", lab, "-ar", str(SR), "-ac", "2", "-c:a", codec, str(sortie)],
                           capture_output=True, text=True, timeout=1800)
    finally:
        os.unlink(script)
    if r.returncode:
        raise RuntimeError(f"ffmpeg (rendu) : {r.stderr.strip()[-500:]}")
    return sortie


# ------------------------------------------------------------------------------------------------ l'autotune des pistes de voix
def preparer_pro(p, d):
    """(13/11, le studio pro) chaque voix passée dans la chaîne pro (studio_pro.traiter : le nettoyage MESURÉ, le nivellement), gardée en
    cache dans pistes/.pro/ (même fichier, mêmes réglages, même version de la chaîne → déjà fait ; les trois plus récentes gardées par
    piste). Rend ({piste: chemin}, {piste: rapport})."""
    import hashlib
    import studio_pro
    out, rap = {}, {}
    for t in p["pistes"]:
        pr = _pro(t)
        if not pr or not pr.get("actif"):
            continue
        src = Path(d) / t["fichier"]
        if not src.is_file():
            continue
        st = src.stat()
        cle = hashlib.sha1(json.dumps([src.name, st.st_mtime_ns, st.st_size, pr, studio_pro.VERSION, sorted(studio_pro.COUPE)],
                                      sort_keys=True).encode()).hexdigest()[:16]
        dpro = Path(d) / "pistes" / ".pro"
        cache, fr = dpro / f"{t['id']}-{cle}.wav", dpro / f"{t['id']}-{cle}.json"
        if not (cache.is_file() and fr.is_file()):
            dpro.mkdir(parents=True, exist_ok=True)
            tmp = dpro / f".{t['id']}-{uuid.uuid4().hex[:6]}.wav"
            try:
                r = studio_pro.traiter_fichier(src, tmp, pr)
                os.replace(tmp, cache)
            finally:
                tmp.unlink(missing_ok=True)
            fr.write_text(json.dumps(r, ensure_ascii=False, default=float), encoding="utf-8")
            vieux = sorted(dpro.glob(f"{t['id']}-*.wav"), key=lambda f: f.stat().st_mtime, reverse=True)[3:]
            for f in vieux:
                f.unlink(missing_ok=True)
                f.with_suffix(".json").unlink(missing_ok=True)
        out[t["id"]] = str(cache)
        try:
            rap[t["id"]] = json.loads(fr.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rap[t["id"]] = {}
    preparer_reference(p, d, out, rap)
    return out, rap


def preparer_reference(p, d, out, rap):
    """(14/11) Les voix calées sur la référence (est_calee) : leur voix nettoyée passée dans studio_pro_reference.caler (l'égalisation
    d'appariement de l'enveloppe, les sifflantes ramenées à la force de la référence), gardée en cache dans pistes/.pro/ (même voix
    nettoyée, même référence, mêmes réglages, même version → déjà fait). out et rap sont complétés sur place ; rap["_reference"]
    garde la référence (pour le calage au mix)."""
    dpro = Path(d) / "pistes" / ".pro"
    ref_t = piste_reference(p)
    ctx = None
    if ref_t is not None:
        f_ref = Path(out.get(ref_t["id"]) or Path(d) / ref_t["fichier"])
        if f_ref.is_file():
            prof, cle = _profil_en_cache(f_ref, dpro)
            ctx = {"profil": prof, "cle": cle, "source": f"la voix « {ref_t['nom']} » du projet", "piste": ref_t["id"]}
    else:
        g = profil_garde(p, Path(d).parent.parent)
        if g:
            ctx = {"profil": g["profil"], "cle": f"profil-{g['nom']}-{g.get('t')}", "source": f"le profil gardé « {g['nom']} »", "piste": None}
    if not ctx:
        return
    rap["_reference"] = ctx
    for t in p["pistes"]:
        if not est_calee(t, ctx["piste"]):
            continue
        src = Path(out.get(t["id"]) or Path(d) / t["fichier"])
        if src.is_file():
            out[t["id"]], rap.setdefault(t["id"], {})["reference"] = caler_une(t, src, ctx, dpro)


def caler_une(t, src, ctx, dpro):
    """Une voix (sa version nettoyée, src) calée sur la référence ctx, en cache. Rend (chemin, rapport)."""
    import studio_mesures as M
    import studio_pro
    import studio_pro_reference as R
    reg = {k: v for k, v in (_pro(t) or {}).items() if k.startswith("ref_")}
    cle = _cle_fichier(src, ctx["cle"], R.VERSION, reg, sorted(studio_pro.COUPE))
    cache, fr = Path(dpro) / f"{t['id']}-ref-{cle}.wav", Path(dpro) / f"{t['id']}-ref-{cle}.json"
    if not (cache.is_file() and fr.is_file()):
        Path(dpro).mkdir(parents=True, exist_ok=True)
        x, _ = M.lire(src)
        y, rr = R.caler(x, ctx["profil"], reglages=reg)
        tmp = Path(dpro) / f".{t['id']}-{uuid.uuid4().hex[:6]}.wav"
        try:
            M.ecrire_wav(tmp, y, SR, 32)
            os.replace(tmp, cache)
        finally:
            tmp.unlink(missing_ok=True)
        fr.write_text(json.dumps(rr, ensure_ascii=False, default=float), encoding="utf-8")
        for v in sorted(Path(dpro).glob(f"{t['id']}-ref-*.wav"), key=lambda z: z.stat().st_mtime, reverse=True)[4:]:
            v.unlink(missing_ok=True)
            v.with_suffix(".json").unlink(missing_ok=True)
    try:
        rr = json.loads(fr.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rr = {}
    rr["source"] = ctx["source"]
    return str(cache), rr


def preparer_voix(p, d, travail):
    """Les voix telles qu'elles entrent dans le mix : la chaîne pro (nettoyage, nivellement), PUIS l'autotune (il entend mieux une
    voix propre). Rend ({piste: chemin}, {piste: rapport de la chaîne pro})."""
    pro, rap = preparer_pro(p, d)
    at = preparer_autotune(p, d, travail, pro)
    return {**pro, **at}, rap


def preparer_autotune(p, d, travail, sources=None):
    """Les pistes avec autotune : leur son corrigé (studio.autotuner_voix, venv du chant), gardé en cache dans pistes/.autotune/ (même
    fichier, même niveau, même tonalité → déjà fait). sources : {piste: chemin} (la voix nettoyée par la chaîne pro). Rend {piste: chemin}."""
    out = {}
    for t in p["pistes"]:
        if not t.get("autotune") or t["role"] not in ROLES_VOIX:
            continue
        src = Path((sources or {}).get(t["id"]) or Path(d) / t["fichier"])
        cle = studio._cle(f"{src.name} {src.stat().st_mtime_ns} {t['autotune']} {p.get('tonalite')}").replace(" ", "-")[:120]
        cache = Path(d) / "pistes" / ".autotune" / f"{cle}.wav"
        if not cache.is_file():
            cache.parent.mkdir(parents=True, exist_ok=True)
            ton = p.get("tonalite") or ""
            if not ton:
                inst = [Path(d) / x["fichier"] for x in p["pistes"] if x["role"] not in ROLES_VOIX]
                ton = studio.tonalite_de(inst[0]) if inst else "C major"
            tmp = Path(travail) / f"at-{t['id']}.wav"
            studio.autotuner_voix(src, tmp, ton, t["autotune"])
            shutil.move(str(tmp), cache)
        out[t["id"]] = str(cache)
    return out


# ------------------------------------------------------------------------------------------------ le mastering
def _filtre(entree, sortie, af, codec="pcm_f32le"):
    extra = ["-b:a", "320k"] if codec == "libmp3lame" else []
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(entree), "-af", af, "-ar", str(SR),
                        "-c:a", codec, *extra, str(sortie)], capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : {r.stderr.strip()[-400:]}")
    return sortie


CIBLES = {"streaming": -14.0, "club": -9.0}      # (13/11) LUFS visés : les plateformes (Spotify, YouTube, Apple), ou plus fort pour le club
BANDES_MASTER = (150, 5000)                     # la compression multibande : graves < 150 Hz < médiums < 5 kHz < aigus


def _filtre_fc(entree, sortie, fc, codec="pcm_f32le"):
    """Un graphe ffmpeg ([0:a] … [out]) sur un fichier."""
    extra = ["-b:a", "320k"] if codec == "libmp3lame" else []
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(entree), "-filter_complex", fc,
                        "-map", "[out]", "-ar", str(SR), "-c:a", codec, *extra, str(sortie)], capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : {r.stderr.strip()[-400:]}")
    return sortie


def seuils_multibande(x, sr=SR):
    """(13/11, le studio pro) les seuils de la compression multibande, MESURÉS sur le bus : chaque bande (les mêmes coupures que
    acrossover, Linkwitz-Riley d'ordre 4) découpée en fenêtres de 400 ms ; le seuil 2 dB sous son 85e centile (les 15 % les plus forts
    de chaque bande compressés de 1 à 3 dB, le reste laissé tel quel)."""
    import numpy as np
    import studio_pro
    m = x.mean(axis=1) if x.ndim == 2 else x
    b0, b1 = BANDES_MASTER
    filtres = [lambda f: studio_pro._butter_mag(f, b0, 2, False) ** 2,
               lambda f: (studio_pro._butter_mag(f, b0, 2, True) * studio_pro._butter_mag(f, b1, 2, False)) ** 2,
               lambda f: studio_pro._butter_mag(f, b1, 2, True) ** 2]
    out = []
    for g in filtres:
        y = studio_pro._filtre_fft(m, sr, g)
        l = studio_pro.niveaux_db(y, sr, 0.4, 0.2)
        vivant = l[l > l.max() - 30]
        v = float(np.percentile(vivant, 85)) - 2.0 if len(vivant) >= 5 else -20.0
        out.append(round(max(-59.5, min(-0.5, v)), 1))                  # acompressor : un seuil entre −60 et 0 dB
    return out


def chaine_master_params(bus, p):
    """Les réglages du master calculés sur le bus du son entier : l'égaliseur vers la courbe du genre (mesurée), la compression de
    bus (en trois bandes, seuils mesurés, ou en une), la largeur stéréo (les graves en mono sous 120 Hz ; resserrée si le bus est
    trop large : corrélation < 0,2), le LUFS visé (streaming −14, club −9) et le dither du WAV 16 bits. Le gain et le plafond du
    limiteur se trouvent ensuite par itération (masteriser)."""
    import studio_mesures as M
    m = p.get("master") or {}
    x, _ = M.lire(bus)
    b = M.bandes(x)
    eq = M.correction_eq(b, p.get("genre") or "trap") if m.get("eq_auto", True) else []
    corr = M.correlation_stereo(x)
    larg = m.get("largeur", "auto")
    largeur = (0.8 if corr < 0.2 else 1.0) if larg in (None, "", "auto") else float(_num(larg, 0, 1.5, 1.0))
    import studio_pro
    mb = seuils_multibande(x) if m.get("multibande", True) and "multibande" not in studio_pro.COUPE else None
    return {"eq": eq, "comp": bool(m.get("comp", True)), "lufs": float(_num(m.get("lufs"), -20, -6, -14)),
            "crete_dbtp": float(_num(m.get("crete_dbtp"), -3, -0.1, -1.0)), "bandes_avant": b, "multibande": mb,
            "largeur": round(largeur, 2), "correlation": corr,
            "mono_graves_hz": 0.0 if "mono_graves" in studio_pro.COUPE else float(_num(m.get("mono_graves_hz", 120), 0, 300, 120)),
            "dither16": bool(m.get("dither16", True)), "cible": m.get("cible") or "streaming"}


def _fc_master(params, gain_db, plafond_db):
    """Le graphe du master : égaliseur → compression (3 bandes aux seuils mesurés, ou une) → stéréo (M/S : le côté sans graves sous
    120 Hz, sa largeur) → gain → limiteur à 4× la fréquence (crête vraie). [0:a] … [out]."""
    f = [f"equalizer=f={e['hz']}:t=o:w=1:g={e['db']}" for e in params.get("eq") or []]
    tete = "[0:a]" + (",".join(f) + "," if f else "")
    mb = params.get("multibande")
    if mb:
        reg = (("2.5", 30, 250), ("2", 10, 150), ("2", 3, 80))        # graves lents, aigus rapides
        g = (f"{tete}acrossover=split={BANDES_MASTER[0]} {BANDES_MASTER[1]}:order=4th[mb0][mb1][mb2];"
             + ";".join(f"[mb{i}]acompressor=threshold={mb[i]:.1f}dB:ratio={reg[i][0]}:attack={reg[i][1]}:release={reg[i][2]}:knee=4:makeup=1[mc{i}]"
                        for i in range(3))
             + ";[mc0][mc1][mc2]amix=inputs=3:normalize=0,")
    else:
        g = tete + ("acompressor=threshold=-18dB:ratio=2:attack=30:release=250:knee=4:makeup=1," if params.get("comp") else "")
    fc = params.get("mono_graves_hz") or 0
    W = params.get("largeur", 1.0)
    if fc > 0 or abs(W - 1.0) > 1e-3:
        g += "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0-0.5*c1,"           # L/R → M/S
        if fc > 0:
            g += f"highpass=f={fc:.0f}:p=2:c=FR,highpass=f={fc:.0f}:p=2:c=FR,"   # le côté sans graves (24 dB/oct) : les graves en mono
        g += f"pan=stereo|c0=c0+{W:.3f}*c1|c1=c0-{W:.3f}*c1,"           # M/S → L/R, la largeur
    g += f"volume={gain_db:.2f}dB,"
    # le limiteur à 4× la fréquence : il voit les crêtes entre les échantillons (la crête vraie) ; la latence compensée (calage gardé)
    g += f"aresample={4 * SR},alimiter=limit={plafond_db:.2f}dB:attack=2:release=60:level=false:latency=true:asc=1,aresample={SR}[out]"
    return g


def exporter_16bits(wav, sortie, dither=True):
    """Le WAV 16 bits (CD, distributeurs) : un dither triangulaire (TPDF) avant la troncature, sinon le bruit de quantification
    devient de la distorsion sur les fondus et les passages doux."""
    import studio_pro
    dither = dither and "dither" not in studio_pro.COUPE
    return _filtre(wav, sortie, "aresample=osf=s16:dither_method=triangular" if dither else "aresample=osf=s16:dither_method=none",
                   "pcm_s16le")


def _mp3(entree, sortie, meta=()):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(entree), "-c:a", "libmp3lame", "-b:a", "320k",
                        *meta, str(sortie)], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError("ffmpeg : MP3 impossible")
    return sortie


def masteriser(bus, sortie_wav, params, mp3=None, titre="", journal=None):
    """Le mastering itératif : on cherche le gain qui donne le LUFS visé APRÈS le limiteur, et le plafond qui tient la crête vraie
    ≤ visée sur le WAV ET sur le MP3 (l'encodage MP3 remonte les crêtes). Au plus 6 essais. Rend {lufs, crete_dbtp, …, essais}."""
    import studio_mesures as M
    cible, crete = params["lufs"], params["crete_dbtp"]
    m0 = M.ebur128(bus)
    gain = cible - (m0["lufs"] if m0["lufs"] and m0["lufs"] > -60 else cible)
    plafond = crete - 0.3
    essais = []
    tmp = Path(sortie_wav).with_suffix(".essai.wav")
    try:
        meta = ["-metadata", "artist=Ahmed & Hakim"] + (["-metadata", f"title={titre}"] if titre else [])
        for k in range(6):
            _filtre_fc(bus, tmp, _fc_master(params, gain, plafond))
            m = M.ebur128(tmp)
            mm = None
            if mp3:                                         # le MP3 encodé EXACTEMENT comme celui qui part (320k) : ses crêtes mesurées
                _mp3(tmp, Path(mp3).with_suffix(".essai.mp3"), meta)
                mm = M.ebur128(Path(mp3).with_suffix(".essai.mp3"))
            essais.append({"gain_db": round(gain, 2), "plafond_db": round(plafond, 2), "lufs": m["lufs"], "crete_dbtp": m["crete_dbtp"],
                           "crete_mp3_dbtp": mm and mm["crete_dbtp"]})
            pire = max(m["crete_dbtp"], mm["crete_dbtp"] if mm else -99)
            ok_crete = pire <= crete + 1e-6
            ok_lufs = abs(m["lufs"] - cible) <= 0.3
            if ok_crete and ok_lufs:
                break
            if not ok_crete:
                plafond -= (pire - crete) + 0.1
            if not ok_lufs:
                gain += (cible - m["lufs"])
        _filtre(tmp, sortie_wav, "anull", "pcm_s24le")
        if mp3:
            os.replace(Path(mp3).with_suffix(".essai.mp3"), mp3)        # le MP3 mesuré est celui qui part
    finally:
        tmp.unlink(missing_ok=True)
        if mp3:
            Path(mp3).with_suffix(".essai.mp3").unlink(missing_ok=True)
    return {"gain_db": round(gain, 2), "plafond_db": round(plafond, 2), "essais": essais}


def appliquer_master(bus, sortie_wav, params, gain_db, plafond_db, mp3=None, titre=""):
    """La même chaîne de master (mêmes gain et plafond) sur une autre version : la version pour papa sonne au même niveau que le son
    entier (plus douce là où les voix se taisent, comme il faut)."""
    _filtre_fc(bus, sortie_wav, _fc_master(params, gain_db, plafond_db), "pcm_s24le")
    if mp3:
        r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(sortie_wav), "-c:a", "libmp3lame",
                            "-b:a", "320k", "-metadata", "artist=Ahmed & Hakim", *(["-metadata", f"title={titre}"] if titre else []),
                            str(mp3)], capture_output=True, text=True, timeout=600)
        if r.returncode:
            raise RuntimeError("ffmpeg : MP3 impossible")
    return sortie_wav


# ------------------------------------------------------------------------------------------------ le mix automatique, piste par piste
CIBLE_INSTRU_LUFS = -20.0       # le bus de l'instru (toutes ses pistes) avant le master
VOIX_AU_DESSUS = {"voix_hakim": 1.5, "voix_papa": 2.0, "voix_origine": 1.0, "voix": 1.5}   # LU au-dessus de l'instru, sur les passages chantés


def _lufs_actif(fichier, debut=0.0, duree=None):
    """Le niveau d'un son sur ses passages actifs (le gate de BS.1770 fait déjà l'essentiel : −70 et −10 LU relatifs)."""
    import studio_mesures as M
    if duree:
        tmp = Path(tempfile.mkdtemp()) / "x.wav"
        try:
            _filtre(fichier, tmp, f"atrim=start={debut}:duration={duree}")
            return M.ebur128(tmp)
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)
    return M.ebur128(fichier)


def eq_correctif_voix(b):
    """Les bandes d'octave d'une voix (studio_mesures.bandes) → son égaliseur correctif. (13/11, la démo de Moujahid 3.2) une voix n'a presque
    rien à 125 Hz : la boue (250 Hz) se juge contre 500 Hz et 1 kHz, pas contre ses voisines (sinon toute voix d'homme se faisait creuser de
    4 dB) ; la présence (2-4 kHz) manque si elle est plus de 12 dB sous les médiums (une voix naturelle descend d'environ 10 dB) ; les
    sifflantes (8 kHz) qui dépassent la présence appellent le dé-esseur."""
    boue = b[3] - (b[4] + b[5]) / 2
    presence = (b[6] + b[7]) / 2 - (b[4] + b[5]) / 2
    sifflantes = b[8] - (b[6] + b[7]) / 2
    return {"medium_db": round(-min(4.0, boue - 1.0), 1) if boue > 1.0 else 0.0,
            "aigu_db": round(min(3.0, (-presence - 12) / 2 + 1), 1) if presence < -12 else 0.0,
            "deesser": round(max(0.0, min(1.0, (sifflantes + 4) / 8)), 2) if sifflantes > -4 else 0.0,
            "boue_db": round(boue, 1), "presence_db": round(presence, 1), "sifflantes_db": round(sifflantes, 1)}


# (13/11, le studio pro) la place des voix qui ne sont pas la voix principale : plus bas (dB sous la principale, sur leurs passages),
# ouvertes à gauche et à droite (en alternance), plus filtrées ; les ad-libs avec des délais « jetés » en fin de phrase
VOIX_TYPES = {
    "double": {"sous_db": 6.0, "pan": 0.7, "coupe_bas": 200.0, "coupe_haut": 9000.0, "reverb": 0.28, "delai": 0.0, "saturation": 0.1},
    "back": {"sous_db": 8.0, "pan": 0.5, "coupe_bas": 250.0, "coupe_haut": 7500.0, "reverb": 0.35, "delai": 0.0, "saturation": 0.0},
    "adlib": {"sous_db": 4.0, "pan": 0.4, "coupe_bas": 200.0, "coupe_haut": 10000.0, "reverb": 0.25, "delai": 0.35, "saturation": 0.1},
}


def type_voix(t):
    pr = _pro(t)
    return (pr or {}).get("type", "principale") if pr is not None else None


def _sur_la_ligne(fichier, regions, duree, sr=SR):
    """Une piste posée sur la ligne du temps (mono) : chaque région découpée et placée (pour caler une voix sur une autre)."""
    import numpy as np
    import studio_mesures as M
    x, _ = M.lire(fichier, sr, 1)
    x = x[:, 0]
    y = np.zeros(int(duree * sr) + 1)
    for r in regions or []:
        a = int(r.get("source_debut_s", 0) * sr)
        n = len(x) - a if r.get("duree_s") is None else int(r["duree_s"] * sr)
        dst = int(r.get("debut_s", 0) * sr)
        n = max(0, min(n, len(x) - a, len(y) - dst))
        y[dst:dst + n] += x[a:a + n] * 10 ** (r.get("gain_db", 0) / 20)
    return y


def caler_voix(p, t, principale, fichiers, d, duree):
    """(13/11, le studio pro) le double (ou le back) calé PHRASE PAR PHRASE sur la voix principale (studio_pro.caler_phrases : ses
    attaques contre celles de la principale, ±80 ms) ; une phrase sans principale en face, calée sur la grille s'il y a un tempo
    (la médiane de ses attaques contre la case la plus proche). La piste est redécoupée en régions (une par phrase), chacune déplacée.
    Rend le rapport (les décalages en ms)."""
    import numpy as np
    import studio_mesures as M
    import studio_pro
    regs = t.get("regions") or []
    if len(regs) != 1:
        return {"cale": False, "raison": "plusieurs régions : laissée telle quelle"}
    r0 = regs[0]
    src = fichiers.get(t["id"]) or str(Path(d) / t["fichier"])
    dbl = _sur_la_ligne(src, regs, duree)
    lead = (_sur_la_ligne(fichiers.get(principale["id"]) or str(Path(d) / principale["fichier"]), principale.get("regions"), duree)
            if principale else np.zeros_like(dbl))
    ph = studio_pro.caler_phrases(lead, dbl, SR) if principale else [
        {"debut_s": a, "fin_s": b, "decalage_ms": 0.0, "nettete": 0.0} for a, b in studio_pro.phrases(dbl, SR)]
    bpm = float(p.get("tempo") or 0)
    for x in ph:                                         # la grille : les phrases sans principale en face
        if x["nettete"] > 0 or bpm <= 0:
            continue
        i0, i1 = int(x["debut_s"] * SR), int(x["fin_s"] * SR)
        ta = M.attaques_precises(dbl[i0:i1], SR) + x["debut_s"]
        if len(ta) < 3:
            continue
        case = 60.0 / bpm / 4
        e = ((ta - float(p.get("premier_temps_s") or 0) + case / 2) % case) - case / 2
        med = float(np.median(e))
        if abs(med) <= 0.4 * case:
            x["decalage_ms"], x["grille"] = round(med * 1000, 1), True
    bouge = [x for x in ph if abs(x["decalage_ms"]) >= 2.0]
    if not bouge:
        return {"cale": False, "phrases": len(ph), "decalages_ms": [x["decalage_ms"] for x in ph]}
    fin_r0 = r0["debut_s"] + ((r0["duree_s"] if r0.get("duree_s") is not None else 1e9))
    neuves = []
    for j, x in enumerate(ph):
        a = max(r0["debut_s"], x["debut_s"] - 0.05, (ph[j - 1]["fin_s"] + x["debut_s"]) / 2 if j else 0)
        b = min(fin_r0, x["fin_s"] + 0.05, (x["fin_s"] + ph[j + 1]["debut_s"]) / 2 if j + 1 < len(ph) else 1e9)
        if b - a < 0.05:
            continue
        s = x["decalage_ms"] / 1000
        source = a - r0["debut_s"] + r0["source_debut_s"]
        debut = a - s
        if debut < 0:
            source, debut = source - debut, 0.0
        neuves.append({"debut_s": round(debut, 4), "source_debut_s": round(max(0.0, source), 4), "duree_s": round(b - a, 4),
                       "gain_db": r0.get("gain_db", 0.0)})
    if neuves:
        t["regions"] = neuves
    return {"cale": True, "phrases": len(ph), "decalages_ms": [x["decalage_ms"] for x in ph],
            "sur_la_grille": sum(1 for x in ph if x.get("grille"))}


def _haut_court_terme(x):
    """Le haut du niveau court terme d'une voix (90e centile de ses fenêtres de 400 ms vivantes, dBFS)."""
    import numpy as np
    mono = x.mean(axis=1) if x.ndim == 2 else x
    n = int(0.4 * SR)
    k = len(mono) // n
    if k < 5:
        return -20.0
    rms = 20 * np.log10(np.sqrt((mono[: k * n].reshape(k, n) ** 2).mean(axis=1)) + 1e-9)
    vivant = rms[rms > rms.max() - 40]
    return float(np.percentile(vivant, 90)) if len(vivant) else -20.0


def mixer_auto(p, d, travail, journal=None):
    """Le mix piste par piste, mesuré (le projet est changé en mémoire ; rend le rapport par piste) :
    0. (13/11, le studio pro) chaque voix passe dans la chaîne pro (studio_pro : le nettoyage MESURÉ — continu, écrêtage, clics,
       ronflement, souffle, plosives, respirations baissées, expandeur doux — et le nivellement) ; les mesures suivantes se font sur la
       voix nettoyée ;
    1. gain de départ : l'instru (la somme de ses pistes, leur équilibre d'origine gardé) à −20 LUFS ; chaque voix principale 1 à 2 LU
       au-dessus ; les doubles, backs et ad-libs sous la principale (6, 8 et 4 dB), sur leurs passages ;
    2. égaliseur correctif des voix : coupe-bas, la boue (250 Hz) creusée si elle dépasse, la présence ajoutée si elle manque ; les
       doubles et les backs plus filtrés (coupe-bas 200-250 Hz, coupe-haut 7,5-9 kHz) ;
    3. compression en DEUX TEMPS : les crêtes (attaque 1 ms, ratio 6, seuil 6 dB au-dessus du haut de la voix), puis le nivellement
       lent (attaque 20 ms, ratio 2,5, seuil 6 dB sous le haut) ; une légère saturation (excitateur au-dessus de 3 kHz) ; le dé-esseur
       APRÈS la compression ;
    4. envois : réverbération (retour filtré 200 Hz-8 kHz, pré-délai calé sur le tempo) et délai calé sur le tempo ; les ad-libs avec
       des délais jetés en fin de phrase ; les doubles et les backs ouverts à gauche et à droite ;
    5. les doubles et les backs CALÉS sur la voix principale, phrase par phrase (et sur la grille s'il y a un tempo) ;
    6. sidechain : la mélodie (ou l'instru entière) se creuse de 2 dB sous la voix principale ;
    7. le bus des voix : une compression lente qui les lie (seuil mesuré).
    Le tout puis rendu et remesuré : l'écart voix/instru visé est vérifié (et corrigé une fois si besoin)."""
    import numpy as np
    import studio_mesures as M
    import studio_pro
    say = journal or (lambda s: None)
    rapport = {}
    instr = [t for t in p["pistes"] if t["role"] not in ROLES_VOIX and not t.get("muet")]
    voix = [t for t in p["pistes"] if t["role"] in ROLES_VOIX and not t.get("muet")]
    duree = float(p.get("duree_s") or 0) or max((r["debut_s"] + (r["duree_s"] or (t.get("duree_fichier_s") or 0) - r["source_debut_s"])
                                                for t in p["pistes"] for r in t["regions"]), default=0)
    # 0. la chaîne pro : chaque voix la reçoit au mix auto (sauf si on la lui a coupée)
    for t in voix:
        if not isinstance(t.get("pro"), dict):
            t["pro"] = pro_defaut()
    fichiers, rap_pro = preparer_voix(p, d, travail)
    for t in voix:
        if t["id"] in rap_pro:
            rapport.setdefault(t["id"], {})["pro"] = {"resume": studio_pro.resume(rap_pro[t["id"]]),
                                                      "etapes": [e for e in studio_pro.ETAPES if (rap_pro[t["id"]].get(e) or {}).get("actif")],
                                                      "fond": rap_pro[t["id"]].get("_fond")}
            say(f"{t['nom']} : {rapport[t['id']]['pro']['resume']}")
    # 1. l'instru : son bus mesuré tel quel (volumes à 0), puis un même gain pour toutes ses pistes
    if instr:
        for t in instr:
            t["volume_db"] = 0.0
        b = Path(travail) / "instru-brut.wav"
        rendre_bus(p, d, b, "instru")
        li = M.ebur128(b)["lufs"]
        g = round(CIBLE_INSTRU_LUFS - li, 1) if li and li > -60 else 0.0
        for t in instr:
            t["volume_db"] = g
        rapport["instru"] = {"lufs_avant": li, "gain_db": g, "pistes": [t["id"] for t in instr]}
        say(f"instru à {CIBLE_INSTRU_LUFS} LUFS (gain {g:+.1f} dB sur {len(instr)} piste(s))")
    principales = [t for t in voix if type_voix(t) in ("principale", None)]
    principale = None
    cote = {k: 1 for k in VOIX_TYPES}
    for t in voix:
        src = Path(fichiers.get(t["id"]) or Path(d) / t["fichier"])
        x, _ = M.lire(src)
        m = M.ebur128(src)
        b = M.bandes(x)
        r = rapport.setdefault(t["id"], {})
        r.update({"lufs": m["lufs"], "crete_dbtp": m["crete_dbtp"], "bandes_db": b})
        ty = type_voix(t) or "principale"
        vt = VOIX_TYPES.get(ty) if "types" not in studio_pro.COUPE else None
        # 2. l'égaliseur correctif (bandes relatives : 250 Hz = indice 3, 3-4 kHz = 6-7, 8 kHz = 8)
        eq = t["eq"]
        eq["coupe_bas_hz"] = vt["coupe_bas"] if vt else (100.0 if t["role"] == "voix_papa" else 90.0)
        eq["coupe_haut_hz"] = vt["coupe_haut"] if vt else 0.0
        # (13/11, la démo de Moujahid 3.2) une voix n'a presque rien à 125 Hz : la boue se juge contre 500 Hz et 1 kHz, pas contre ses voisins
        # (sinon toute voix d'homme se faisait creuser de 4 dB à 280 Hz) ; la présence (2-4 kHz) manque si elle est plus de 12 dB sous les
        # médiums (une voix naturelle descend d'environ 10 dB)
        c = eq_correctif_voix(b)
        boue, presence, sifflantes = c["boue_db"], c["presence_db"], c["sifflantes_db"]
        eq["medium_hz"], eq["medium_q"], eq["medium_db"] = 280.0, 1.2, c["medium_db"]
        eq["aigu_hz"], eq["aigu_db"] = 6000.0, c["aigu_db"]
        # 3. la compression en deux temps, mesurée sur le haut de son niveau court terme (90e centile sur 400 ms)
        haut = _haut_court_terme(x)
        t["comp_rapide"] = {"actif": True, "seuil_db": round(max(-40.0, min(-1.0, haut + 6)), 1), "ratio": 6.0, "attaque_ms": 1.0,
                            "relache_ms": 60.0}
        t["comp"].update(actif=True, seuil_db=round(max(-45.0, min(-6.0, haut - 6)), 1), ratio=2.5, attaque_ms=20.0, relache_ms=250.0,
                         gain_db=0.0)
        # le dé-esseur (après la compression, qui remonte les sifflantes : un cran de plus s'il en faut un)
        t["deesser"] = round(min(1.0, c["deesser"] + 0.1), 2) if c["deesser"] > 0 else 0.0
        # une légère saturation pour la présence (un peu plus si la voix est sourde)
        t["saturation"] = vt["saturation"] if vt else (0.3 if presence < -12 else 0.2)
        # 4. les envois et la place
        if vt:
            t["reverb"], t["delai"], t["delai_note"] = vt["reverb"], (vt["delai"] if p.get("tempo") else 0.0), "1/4"
            t["pan"] = round(vt["pan"] * cote[ty], 2)
            cote[ty] = -cote[ty]
        else:
            t["reverb"] = 0.12 if t["role"] == "voix_papa" else 0.22
            t["delai"] = 0.0 if t["role"] == "voix_papa" else (0.12 if p.get("tempo") else 0.0)
            t["delai_note"] = "1/8."
        jete = (t.get("pro") or {}).get("delai_jete", "auto")
        if p.get("tempo") and ((ty == "adlib" and jete != "non") or jete == "oui"):
            ligne = _sur_la_ligne(src, t["regions"], duree)
            # le dernier mot de chaque phrase (ses 400 dernières ms) part dans le délai ; le reste de la phrase reste sec
            t["jetes"] = [[round(max(0.0, bb - 0.4), 3), round(bb + 0.2, 3)] for _, bb in studio_pro.phrases(ligne, SR)][:64]
            t["delai"] = max(t["delai"], 0.35)
        else:
            t["jetes"] = []
        r.update(eq={k2: eq[k2] for k2 in ("coupe_bas_hz", "coupe_haut_hz", "medium_db", "aigu_db")}, deesser=t["deesser"],
                 seuil_db=t["comp"]["seuil_db"], seuil_rapide_db=t["comp_rapide"]["seuil_db"], saturation=t["saturation"], type=ty,
                 boue_db=round(boue, 1), presence_db=round(presence, 1), sifflantes_db=round(sifflantes, 1), jetes=len(t["jetes"]))
        if ty == "principale" and (principale is None or t["role"] in ("voix_papa", "voix_hakim") and principale["role"] == "voix_origine"):
            principale = t
    # 4 bis. (14/11) le calage sur la voix de référence, au mix : la tranche de la référence, la densité, les sifflantes et l'espace
    # appariés sur le rendu de la piste seule, la parité de niveau (studio_pro_reference, caler_au_mix)
    vises = caler_au_mix(p, d, travail, fichiers, rap_pro, rapport, say)
    # 5. le calage des doubles et des backs sur leur voix principale (la même voix si elle existe, sinon la principale du morceau)
    for t in voix:
        ty = type_voix(t)
        if ty not in ("double", "back") or (t.get("pro") or {}).get("calage") == "non" or "calage" in studio_pro.COUPE:
            continue
        lead = next((x for x in principales if x["role"] == t["role"]), principale)
        rapport[t["id"]]["calage"] = caler_voix(p, t, lead, fichiers, d, duree)
        say(f"{t['nom']} : calage {rapport[t['id']]['calage']}")
    # 6. le sidechain : la mélodie se creuse sous la voix principale (2 dB), sinon l'instru entière (1,5 dB)
    if principale:
        cible = next((t for t in instr if t["role"] == "melodie"), None) or next((t for t in instr if t["role"] == "instru"), None)
        if cible:
            cible["sidechain"] = {"cle": principale["id"], "db": 2.0 if cible["role"] == "melodie" else 1.5}
            rapport["sidechain"] = {"piste": cible["id"], "cle": principale["id"], "db": cible["sidechain"]["db"]}
    # 1 bis. l'équilibre, mesuré sur le rendu : chaque voix principale seule contre l'instru, sur les passages où elle chante ; chaque
    # double, back ou ad-lib contre sa voix principale
    p["bus_voix"] = {"actif": False}
    rendus_voix = {}

    def niveau_sur(fichier, act):
        return _lufs_actif(fichier, *act)["lufs"]
    for t in sorted(voix, key=lambda x: 0 if type_voix(x) == "principale" else 1):
        ty = type_voix(t)
        lead = None if ty == "principale" else (next((x for x in principales if x["role"] == t["role"]), principale))
        if ty == "principale" and not instr:
            continue
        for essai in range(2):
            vb = Path(travail) / f"voix-{t['id']}.wav"
            rendre_bus(p, d, vb, seules=[t["id"]], fichiers=fichiers)
            act = _passages_actifs(vb)
            if not act:
                break
            lv = niveau_sur(vb, act)
            if lead is None:
                ref = Path(travail) / "instru-ref.wav"
                if not ref.is_file():
                    rendre_bus(p, d, ref, "instru")
                vise = vises.get(t["id"], VOIX_AU_DESSUS.get(t["role"], 1.5))
            elif lead is not None and lead is not t:
                ref = Path(travail) / f"voix-ref-{lead['id']}.wav"
                if not ref.is_file():
                    rendre_bus(p, d, ref, seules=[lead["id"]], fichiers=fichiers)
                vise = -VOIX_TYPES[ty]["sous_db"]
            else:
                break
            ecart = lv - niveau_sur(ref, act)
            rapport[t["id"]].setdefault("equilibre", []).append({"ecart_lu": round(ecart, 1), "vise_lu": vise})
            if abs(ecart - vise) <= 0.5:
                break
            t["volume_db"] = round(_num(t["volume_db"] + (vise - ecart), -30, 12, 0), 1)
            if lead is None:
                for f in Path(travail).glob(f"voix-ref-{t['id']}.wav"):
                    f.unlink()
        rendus_voix[t["id"]] = True
        e = rapport[t["id"]].get("equilibre")
        say(f"{t['nom']} : {e[-1]['ecart_lu'] if e else '?'} LU {'au-dessus de l’instru' if lead is None else 'contre la principale'}")
    # 7. le bus des voix : son seuil mesuré sur toutes les voix ensemble (le haut de leur niveau court terme, ratio 1,5 : environ 1 dB de
    # réduction sur les passages forts), et son gain de rattrapage MESURÉ (la démo du 13/11 : sans lui, les voix finissaient 2,7 LU
    # plus bas que l'équilibre visé)
    if voix:
        vb, vb2 = Path(travail) / "voix-bus.wav", Path(travail) / "voix-bus-comp.wav"
        try:
            rendre_bus(p, d, vb, "voix", fichiers=fichiers)
            xb, _ = M.lire(vb)
            p["bus_voix"] = {"actif": True, "seuil_db": round(max(-50.0, min(-3.0, _haut_court_terme(xb))), 1), "ratio": 1.5, "gain_db": 0.0}
            rendre_bus(p, d, vb2, "voix", fichiers=fichiers)
            l0, l1 = M.ebur128(vb)["lufs"], M.ebur128(vb2)["lufs"]
            if l0 and l1 and l0 > -60 and l1 > -60:
                p["bus_voix"]["gain_db"] = round(max(0.0, min(6.0, l0 - l1)), 1)
            rapport["bus_voix"] = p["bus_voix"]
        except (RuntimeError, Refus):
            p["bus_voix"] = {"actif": False}
    return rapport


def _passages_actifs(fichier, seuil_db=-35.0):
    """Le plus long passage où un son est présent (fenêtres de 0,5 s au-dessus de seuil_db sous son pic) : (début, durée), ou None."""
    import numpy as np
    import studio_mesures as M
    x, _ = M.lire(fichier, 8000, 1)
    m = x[:, 0]
    w = 4000
    k = len(m) // w
    if k < 4:
        return None
    e = 10 * np.log10((m[: k * w].reshape(k, w) ** 2).mean(axis=1) + 1e-12)
    on = e > e.max() + seuil_db
    if on.sum() < 4:
        return None
    # du premier au dernier passage actif (le gate de BS.1770 retire les silences entre les phrases)
    i = np.flatnonzero(on)
    return float(i[0] * 0.5), float((i[-1] - i[0] + 1) * 0.5)


def garder_reference(pid, piste_id=None, nom="hakim", studio_dir=None):
    """(14/11) Une voix du projet (par défaut sa référence) gardée comme PROFIL DE RÉFÉRENCE (studio/references/<nom>.json) : le profil
    de sa voix nettoyée, sa tranche, ses cibles au mix (rendu de la piste seule, sec et avec ses envois) et son niveau au-dessus de
    l'instru. Un projet sans voix de Hakim s'y cale (source « auto » ou « profil »). Rend le résumé."""
    import studio_pro_reference as R
    d = dossier(pid, studio_dir)
    p = lire(pid, studio_dir)
    t = piste(p, piste_id) if piste_id else piste_reference(p)
    if t is None or t["role"] not in ROLES_VOIX:
        raise Refus("aucune voix à garder comme référence (donne la piste)")
    nom = re.sub(r"[^a-z0-9-]", "", studio._cle(str(nom or "hakim")).replace(" ", "-"))[:30] or "hakim"
    travail = Path(tempfile.mkdtemp(prefix=".ref-", dir=d))
    try:
        fichiers, _ = preparer_voix(p, d, travail)
        prof, _ = _profil_en_cache(Path(fichiers.get(t["id"]) or Path(d) / t["fichier"]), Path(d) / "pistes" / ".pro")
        cibles = cibles_reference(p, d, travail, fichiers, t)
    finally:
        shutil.rmtree(travail, ignore_errors=True)
    g = R.ecrire_profil(references_dir(studio_dir) / f"{nom}.json", prof, f"{p['titre']} — {t['nom']}", _tranche(t),
                        VOIX_AU_DESSUS.get(t["role"], 1.5), cibles)
    return {"nom": nom, "source": g["source"], "t": g["t"], "fichier": str(references_dir(studio_dir) / f"{nom}.json")}


def lister_references(studio_dir=None):
    """Les profils de référence gardés : [{nom, source, t}]."""
    import studio_pro_reference as R
    out = []
    for f in sorted(references_dir(studio_dir).glob("*.json")):
        g = R.lire_profil(f)
        if g:
            out.append({"nom": f.stem, "source": g.get("source", ""), "t": g.get("t")})
    return out


# ------------------------------------------------------------------------------------------------ le rendu complet d'un projet
def _avis(master, bus, eq, equilibre, genre, params=None, pro=None):
    """L'avis d'ingé son, en mots courts, à partir des mesures."""
    c = []
    for x in pro or []:                                  # (13/11, le studio pro) ce que la chaîne de chaque voix a fait, mesuré
        c.append(f"{x['piste']} : {x['resume']}")
    if master.get("lufs") is not None:
        c.append(f"master à {master['lufs']:.1f} LUFS, crête vraie {master['crete_dbtp']:.1f} dBTP")
    plr = master.get("plr_db")
    if plr is not None:
        c.append(f"PLR {plr:.1f} dB ({'bien pour du ' + genre if 7 <= plr <= 12 else 'un peu écrasé' if plr < 7 else 'très dynamique pour du ' + genre})")
    if eq:
        c.append("égaliseur de master : " + ", ".join(f"{e['db']:+.1f} dB à {e['hz']} Hz" for e in eq))
    r = master.get("reference")
    if r:
        c.append(f"écart moyen à la courbe du genre {r['ecart_moyen_db']:.1f} dB" + (f" (encore : {', '.join(r['mots'][:3])})" if r["mots"] else ""))
    for nom, e in equilibre:
        c.append(f"{nom} {e:+.1f} LU au-dessus de l'instru")
    q = params or {}
    if q.get("multibande"):
        c.append("compression en 3 bandes (seuils mesurés : " + " / ".join(f"{v:.0f} dB" for v in q["multibande"]) + ")")
    if q.get("mono_graves_hz"):
        c.append(f"graves en mono sous {q['mono_graves_hz']:.0f} Hz, largeur {q.get('largeur', 1.0):.2f} (corrélation du mix {q.get('correlation')})")
    if q.get("cible"):
        c.append(f"cible {q['cible']} ({q.get('lufs')} LUFS)")
    return c


def _avis_reference(rapport_mix, p):
    """(14/11) Ce que le calage sur la référence a fait au mix, en mots courts, mesuré."""
    c = []
    noms = {t["id"]: t["nom"] for t in p["pistes"]}
    for k, v in (rapport_mix or {}).items():
        r = isinstance(v, dict) and v.get("reference_mix")
        if not r:
            continue
        m = []
        dn = r.get("densite")
        if dn:
            m.append(f"densité : crête {dn['avant_crete_db']} → {dn['apres_crete_db']} dB (référence {dn['cible_crete_db']})")
        sf = r.get("sifflantes")
        if sf and sf.get("avant_p90_db") is not None:
            m.append(f"force des sifflantes {sf['avant_p90_db']} dB (référence {sf['cible_p90_db']})")
        es = r.get("espace")
        if es:
            m.append(f"espace : traîne {es['avant_traine_db']} → {es['apres_traine_db']} dB (référence {es['cible_traine_db']}, "
                     f"réverb {es['reverb']}, délai {es['delai']})")
        if r.get("vise_lu") is not None:
            m.append(f"au même niveau que la référence ({r['vise_lu']:+.1f} LU sur l'instru)")
        c.append(f"{noms.get(k, k)} calée sur la référence au mix : " + ", ".join(m))
    return c


def rendre_projet(pid, quoi="tout", mix_auto=False, envoyer=True, pistes_separees=False, studio_dir=None, telephone=None, progres=None,
                  nom_version="", par=""):
    """Mixer (piste par piste, si mix_auto), masteriser et exporter un projet : le son entier ; la version « zones de papa en instru
    seule » (s'il y a des zones de papa) ; l'instru seule ; les pistes séparées (pistes_separees). Tout est mesuré, et copié dans
    Hakim/Chansons sur le téléphone (envoyer). Rend le rendu (aussi gardé dans le projet).
    (14/11) Chaque rendu est une VERSION (v1, v2… : studio_edition) : rien n'est écrasé, ni sur le Mac ni sur le téléphone
    (« Titre v3.mp3 ») ; elle garde la photo du mix rendu ; un mix fait à la main est gardé avant que le mix automatique le refasse."""
    import studio_mesures as M
    import studio_edition as E
    dire = progres or (lambda n, s: None)
    d = dossier(pid, studio_dir)
    t0 = time.time()
    av = E.avant_rendu(pid, mix_auto, studio_dir, par)
    vn = av["v"]                                       # le numéro de cette version
    travail = Path(tempfile.mkdtemp(prefix=".rendu-", dir=d))
    journal = [f"le mix à la main gardé comme « {av['garde']} »"] if av["garde"] else []
    try:
        p = lire(pid, studio_dir)
        if not p["pistes"]:
            raise Refus("le projet n'a aucune piste")
        if not p.get("duree_s"):
            p["duree_s"] = max((r["debut_s"] + (r["duree_s"] or (t.get("duree_fichier_s") or studio.duree(d / t["fichier"]) or 0) - r["source_debut_s"])
                               for t in p["pistes"] for r in t["regions"]), default=0)
        rapport_mix = None
        if mix_auto:
            dire(1, "mix piste par piste (gains, égaliseurs, compression, envois, sidechain)")
            rapport_mix = mixer_auto(p, d, travail, journal.append)
            pistes_reglees = {t["id"]: copy.deepcopy(t) for t in p["pistes"]}

            cales = {k for k, v in (rapport_mix or {}).items() if isinstance(v, dict) and (v.get("calage") or {}).get("cale")}
            bus_voix = copy.deepcopy(p.get("bus_voix") or {"actif": False})

            def garder(q):
                for t in q["pistes"]:
                    if t["id"] in pistes_reglees:
                        # (13/11) les régions d'un double calé phrase par phrase sont gardées ; les autres restent celles de papa
                        t.update({k: v for k, v in pistes_reglees[t["id"]].items()
                                  if k not in ("fichier", "nom") and (k != "regions" or t["id"] in cales)})
                q["bus_voix"] = bus_voix
            p = modifier(pid, garder, studio_dir=studio_dir, note="mix automatique piste par piste")
        dire(2, "autotune des voix" if any(t.get("autotune") for t in p["pistes"]) else "préparation")
        fichiers, rap_pro = preparer_voix(p, d, travail)
        import studio_pro
        resumes_pro = [{"piste": t["nom"], "id": t["id"], "resume": studio_pro.resume(rap_pro[t["id"]]),
                        "fond": rap_pro[t["id"]].get("_fond")} for t in p["pistes"] if t["id"] in rap_pro]
        dire(3, "rendu du son entier (toutes les pistes)")
        bus = travail / "bus-complet.wav"
        rendre_bus(p, d, bus, "complet", fichiers=fichiers)
        mesure_bus = M.bilan(bus, p.get("genre") or "trap")
        dire(4, "mastering (égaliseur, compression de bus, limiteur, LUFS visé)")
        params = chaine_master_params(bus, p)
        nom = studio.nom_de(p["titre"])
        rd = d / "rendus"
        rd.mkdir(exist_ok=True)
        wav, mp3 = rd / f"{nom}.wav", rd / f"{nom}.mp3"
        mst = masteriser(bus, wav, params, mp3, p["titre"])
        mesure_master = M.bilan(wav, p.get("genre") or "trap")
        mesure_mp3 = M.ebur128(mp3)
        fichiers_sortie = {"complet": {"wav": str(wav), "mp3": str(mp3)}}
        if params.get("dither16"):                      # (13/11) le WAV 16 bits, avec son dither (TPDF)
            w16 = rd / f"{nom}-16bits.wav"
            exporter_16bits(wav, w16)
            fichiers_sortie["complet"]["wav16"] = str(w16)
        equilibre = []
        try:
            vb = travail / "voix-seules.wav"
            ib = travail / "instru-seule.wav"
            if actives(p, "voix") and actives(p, "instru"):
                rendre_bus(p, d, vb, "voix", fichiers=fichiers)
                rendre_bus(p, d, ib, "instru", fichiers=fichiers)
                act = _passages_actifs(vb)
                if act:
                    equilibre.append(("les voix", round(_lufs_actif(vb, *act)["lufs"] - _lufs_actif(ib, *act)["lufs"], 1)))
        except (RuntimeError, Refus, TypeError):
            pass
        if quoi in ("tout", "papa") and any(z.get("qui") == "papa" for z in p.get("zones", [])):
            dire(5, "la version pour papa (ses zones en instru seule)")
            busp = travail / "bus-papa.wav"
            rendre_bus(p, d, busp, "papa", fichiers=fichiers)
            wp, mp = rd / f"{nom}-zones-papa.wav", rd / f"{nom}-zones-papa.mp3"
            appliquer_master(busp, wp, params, mst["gain_db"], mst["plafond_db"], mp, f"{p['titre']} (zones de papa)")
            fichiers_sortie["zones_papa"] = {"wav": str(wp), "mp3": str(mp), "mesure": M.ebur128(wp),
                                             "zones": [z for z in p["zones"] if z["qui"] == "papa"]}
        if quoi in ("tout", "instru") and actives(p, "instru") and actives(p, "voix"):
            dire(6, "l'instru seule")
            busi = travail / "bus-instru.wav"
            rendre_bus(p, d, busi, "instru", fichiers=fichiers)
            wi, mi = rd / f"{nom}-instru.wav", rd / f"{nom}-instru.mp3"
            appliquer_master(busi, wi, params, mst["gain_db"], mst["plafond_db"], mi, f"{p['titre']} (instru)")
            fichiers_sortie["instru"] = {"wav": str(wi), "mp3": str(mi)}
        if pistes_separees:
            dire(7, "les pistes séparées")
            pd = rd / f"{nom}-pistes"
            pd.mkdir(exist_ok=True)
            l = {}
            for t in actives(p, "complet"):
                bt = travail / f"piste-{t['id']}.wav"
                rendre_bus(p, d, bt, seules=[t["id"]], fichiers=fichiers)
                f = pd / f"{studio.nom_lisible(t['nom'], t['id'])}.mp3"
                _filtre(bt, f, f"volume={mst['gain_db']:.2f}dB,alimiter=limit=-1dB:level=false:latency=true", "libmp3lame")
                l[t["id"]] = str(f)
            fichiers_sortie["pistes"] = l
        tel = {}
        if envoyer:
            dire(8, "copie sur le téléphone (Hakim › Chansons)")
            dt = Path(telephone or studio.TELEPHONE)
            lisible = studio.nom_lisible(p["titre"], nom) + E.suffixe(vn)          # (14/11) « Titre v3 » : jamais écrasé
            for k, v in fichiers_sortie.items():
                if k == "pistes":
                    sous = dt / f"{lisible} (pistes)"
                    tel[k] = [str(studio.copier_au_telephone(x, sous)) for x in v.values()]
                elif v.get("mp3"):
                    tmp = travail / (f"{lisible}.mp3" if k == "complet" else f"{lisible} ({'zones de papa' if k == 'zones_papa' else k}).mp3")
                    shutil.copyfile(v["mp3"], tmp)
                    c = studio.copier_au_telephone(tmp, dt)
                    tel[k] = str(c) if c else None
        rendu = {"t": time.time(), "nom": nom, "fichiers": fichiers_sortie, "telephone": tel, "calcul_s": round(time.time() - t0, 1),
                 "mesures": {"bus": mesure_bus, "master": mesure_master, "mp3": mesure_mp3, "master_essais": mst["essais"],
                             "eq_master": params["eq"], "equilibre": equilibre},
                 "mix_auto": rapport_mix, "journal": journal,
                 "pro": resumes_pro,
                 "master_reglages": {k: params.get(k) for k in ("multibande", "largeur", "correlation", "mono_graves_hz", "cible", "lufs",
                                                                "dither16")},
                 "avis": _avis(mesure_master, mesure_bus, params["eq"], equilibre, p.get("genre") or "trap", params, resumes_pro)
                 + _avis_reference(rapport_mix, p)}

        photo = E.mix_de(p)                             # (14/11) le mix tel qu'il a été rendu (la version le garde)

        def noter(q):
            E.noter_version(q, d, rendu, vn, photo, mix_auto, par, nom_version)
            q.setdefault("rendus", []).append(rendu)
            q["rendus"] = q["rendus"][-8:]
            q["duree_s"] = p["duree_s"]
        modifier(pid, noter, studio_dir=studio_dir, note=f"rendu {nom}" + (f" (v{vn})" if vn else ""))
        return rendu
    except Exception:
        E.annuler_version(pid, vn, studio_dir)
        raise
    finally:
        shutil.rmtree(travail, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ créer un projet depuis un son
def creer_depuis(source, titre="", separer="4", garder=None, role_voix="voix_hakim", genre="trap", studio_dir=None, progres=None,
                 python_separation=None, tempo=0.0, tonalite=""):
    """Un projet depuis un son : séparé (separer « 4 » htdemucs_ft, « 6 » htdemucs_6s, « non » : le son entier en une piste
    « instru »). Les pistes : batterie, basse, mélodie et autres (= le reste, pour que la somme refasse l'instru exacte : rien n'est
    perdu), [guitare, piano], et la voix (role_voix). garder : les pistes de l'instru que papa garde (les autres sont muettes).
    Tempo et tonalité mesurés. Rend le projet."""
    import numpy as np
    import studio_mesures as M
    dire = progres or (lambda n, s: None)
    source = Path(source)
    p = nouveau(titre or source.stem, tempo, tonalite, genre, studio_dir, source={"fichier": str(source)})
    d = dossier(p["id"], studio_dir)
    pistes_dir = d / "pistes"
    try:
        dire(1, "écoute (tempo, tonalité)")
        x, _ = M.lire(source)
        duree = len(x) / SR
        tp = M.tempo_et_phase(x, SR, bpm_connu=float(tempo or 0))
        ton = tonalite or studio.tonalite_de(source)
        ajout = []
        if str(separer) in ("4", "6", "2"):
            dire(2, "séparation des pistes (Demucs)")
            modeles = {"4": "htdemucs_ft", "6": "htdemucs_6s", "2": "htdemucs_ft"}[str(separer)]
            py = str(python_separation or studio.PYTHON_SEPARATION)
            r = subprocess.run(["/usr/bin/nice", "-n", "15", py, "-B", "-W", "ignore", str(ICI / "studio_separation.py"), "separer",
                                str(source), str(pistes_dir), "--modeles", modeles, "--shifts", "1", "--format", "flac"],
                               capture_output=True, text=True, timeout=3600)
            if r.returncode:
                raise RuntimeError(f"séparation : {r.stderr.strip()[-300:]}")
            res = json.loads(r.stdout.strip().splitlines()[-1])
            dire(3, "les pistes (la somme refait l'instru exacte)")
            # la mélodie (other) prend le reste : mélange − voix − les autres pistes ; l'instru exacte (mélange − voix) est leur somme
            ins, _ = M.lire(res["instru"])
            autres = [s for s in res["pistes"] if s not in ("vocals", "other")]
            reste = ins.copy()
            for s in autres:
                y, _ = M.lire(res["pistes"][s])
                n = min(len(reste), len(y))
                reste[:n] -= y[:n]
            M.ecrire_wav(pistes_dir / "other.flac", reste, SR, 16)
            os.unlink(res["instru"])
            if str(separer) == "2":
                for s in autres:
                    os.unlink(res["pistes"][s])
                os.replace(pistes_dir / "other.flac", pistes_dir / "instru.flac")
                ajout.append(("pistes/instru.flac", "instru", "Instru"))
            else:
                for s in ("drums", "bass", "guitar", "piano", "other"):
                    if s in res["pistes"] or s == "other":
                        ajout.append((f"pistes/{s}.flac", SOURCE_ROLE[s], ROLES[SOURCE_ROLE[s]]))
            ajout.append(("pistes/vocals.flac", role_voix, ROLES.get(role_voix, "Voix")))
        else:
            ext = source.suffix.lower()
            shutil.copyfile(source, pistes_dir / f"instru{ext}")
            ajout.append((f"pistes/instru{ext}", "instru", "Instru"))
        g = [studio._cle(x) for x in (garder or [])]

        def remplir(q):
            q.update(tempo=tp["bpm"], premier_temps_s=tp["premier_temps_s"], tonalite=ton, duree_s=round(duree, 2),
                     tempo_confiance=tp["confiance"])
            for f, role, nom in ajout:
                t = ajouter_piste(q, f, role, nom, duree_s=round(duree, 2), origine=f"séparée de {source.name}" if separer != "non" else source.name)
                if g and role not in ROLES_VOIX:
                    t["muet"] = not any(k in (role, studio._cle(nom)) or k in studio._cle(nom) for k in g)
            q["etat"] = "prêt"
        p = modifier(p["id"], remplir, studio_dir=studio_dir, note=f"créé depuis {source.name} ({'séparé en ' + str(separer) + ' pistes' if separer != 'non' else 'entier'})")
        return p
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise


def importer_son(pid, fichier, role="ajout", nom="", debut_s=0.0, studio_dir=None, deplacer=False):
    """Un son (une prise de papa, un ajout) → une piste du projet (copié dans pistes/). Rend le projet."""
    d = dossier(pid, studio_dir)
    f = Path(fichier)
    if not f.is_file() or f.suffix.lower() not in EXT_SON:
        raise Refus("son introuvable")
    cible = d / "pistes" / f"{role}-{uuid.uuid4().hex[:6]}{f.suffix.lower()}"
    (shutil.move if deplacer else shutil.copyfile)(str(f), str(cible))
    du = studio.duree(cible)
    return modifier(pid, lambda q: ajouter_piste(q, f"pistes/{cible.name}", role, nom, debut_s, du, origine=f.name), studio_dir=studio_dir,
                    note=f"piste ajoutée : {nom or ROLES.get(role)}")


ALIAS_REGLAGES = {"volume": "volume_db", "vol": "volume_db", "gain": "volume_db", "panoramique": "pan", "réverb": "reverb",
                  "reverbe": "reverb", "délai": "delai", "echo": "delai", "écho": "delai", "grave": "eq.grave_db", "graves": "eq.grave_db",
                  "medium": "eq.medium_db", "médium": "eq.medium_db", "mediums": "eq.medium_db", "aigu": "eq.aigu_db", "aigus": "eq.aigu_db",
                  "coupe_bas": "eq.coupe_bas_hz", "coupe-bas": "eq.coupe_bas_hz", "seuil": "comp.seuil_db", "ratio": "comp.ratio",
                  "compression": "comp.actif", "comp": "comp.actif", "attaque": "comp.attaque_ms", "relache": "comp.relache_ms",
                  "dé-esseur": "deesser", "de-esseur": "deesser", "deesseur": "deesser", "medium_hz": "eq.medium_hz", "grave_hz": "eq.grave_hz",
                  "aigu_hz": "eq.aigu_hz", "q": "eq.medium_q",
                  # (13/11, le studio pro) le nettoyage et les modifs de chaque voix
                  "coupe_haut": "eq.coupe_haut_hz", "coupe-haut": "eq.coupe_haut_hz", "coupe_haut_hz": "eq.coupe_haut_hz",
                  "comp_rapide": "comp_rapide.actif", "crêtes": "comp_rapide.actif", "cretes": "comp_rapide.actif",
                  "seuil_rapide": "comp_rapide.seuil_db", "excitateur": "saturation",
                  "nettoyage": "pro.actif", "pro": "pro.actif", "type": "pro.type", "souffle": "pro.souffle", "bruit": "pro.souffle",
                  "débruitage": "pro.souffle", "debruitage": "pro.souffle", "ronflement": "pro.ronflement", "50hz": "pro.ronflement",
                  "clics": "pro.clics", "ecretage": "pro.ecretage", "écrêtage": "pro.ecretage", "plosives": "pro.plosives",
                  "respirations": "pro.respirations", "respirations_db": "pro.respirations_db", "porte": "pro.porte",
                  "expandeur": "pro.porte", "nivellement": "pro.nivellement", "rider": "pro.nivellement", "continu": "pro.continu",
                  "calage": "pro.calage", "debruiteur": "pro.debruiteur", "débruiteur": "pro.debruiteur", "souffle_db": "pro.souffle_db",
                  "delai_jete": "pro.delai_jete", "délai_jeté": "pro.delai_jete", "jete": "pro.delai_jete", "plosives_hz": "pro.plosives_hz",
                  "nivellement_db": "pro.nivellement_db", "porte_plage_db": "pro.porte_plage_db",
                  # (14/11) le calage sur la voix de référence
                  "reference": "pro.reference", "référence": "pro.reference", "calage_reference": "pro.reference"}
PRO_TEXTE = {"pro.type", "pro.souffle", "pro.ronflement", "pro.clics", "pro.ecretage", "pro.plosives", "pro.respirations", "pro.porte",
             "pro.nivellement", "pro.continu", "pro.calage", "pro.debruiteur", "pro.delai_jete", "pro.reference"}


def _coupe_edition():
    import studio_edition
    return studio_edition.COUPE


def lire_reglages(texte):
    """« volume=-3, pan=0.2, muet=oui, medium=-2, ratio=4, reverb=0.2, autotune=léger, sidechain=t3:2 » (ou un objet JSON) → un dict
    pour regler_piste. Les valeurs sont bornées ensuite par regler_piste."""
    t = str(texte or "").strip()
    if not t:
        return {}
    if t.startswith("{"):
        try:
            return json.loads(t)
        except ValueError:
            raise Refus("réglages : un JSON illisible")
    r = {}
    for bout in re.split(r"[;,\n]+", t):
        if not bout.strip():
            continue
        if "=" not in bout and ":" not in bout:
            raise Refus(f"réglage illisible : « {bout.strip()} » (exemple : volume=-3)")
        k, _, v = bout.partition("=") if "=" in bout else bout.partition(":")
        k = ALIAS_REGLAGES.get(k.strip().lower(), k.strip().lower())
        v = v.strip()
        if k == "autotune":
            val = studio.niveau_autotune({"léger": "leger", "non": False, "aucun": False, "": False}.get(v.lower(), v))
        elif k == "sidechain":
            cle, _, dbv = v.partition(":")
            val = {"cle": cle.strip(), "db": dbv or 2}
        elif k in ("muet", "solo", "comp.actif", "comp_rapide.actif", "pro.actif"):
            val = v.lower() in ("1", "oui", "vrai", "true", "on", "auto")
        elif k == "nom" and "nom" not in _coupe_edition():   # (14/11) renommer une piste : « nom=Couplet 1 »
            val = " ".join(v.split())
        elif k == "delai_note" or k in PRO_TEXTE:
            val = v.strip().lower().replace("é", "e") if k != "pro.type" else v.strip().lower()
        else:
            try:
                val = float(v.replace(",", ".").replace("db", "").replace("dB", "").replace("hz", "").replace("Hz", "").strip())
            except ValueError:
                raise Refus(f"réglage illisible : « {bout.strip()} »")
        if k.startswith(("eq.", "comp.", "comp_rapide.", "pro.")):
            a, b = k.split(".", 1)
            r.setdefault(a, {})[b] = val
        else:
            r[k] = val
    return r


def activite_voix(fichier, seuil_db=-30.0, min_s=1.5):
    """Les passages où une voix chante (fenêtres de 0,25 s au-dessus de seuil_db sous son pic, trous de moins d'1 s comblés) : une
    aide pour poser les zones. Rend [(début, fin)]."""
    import numpy as np
    import studio_mesures as M
    x, _ = M.lire(fichier, 8000, 1)
    m = x[:, 0]
    w = 2000
    k = len(m) // w
    if k < 4:
        return []
    e = 10 * np.log10((m[: k * w].reshape(k, w) ** 2).mean(axis=1) + 1e-12)
    on = e > e.max() + seuil_db
    on = np.convolve(on.astype(float), np.ones(5), mode="same") > 0                     # trous < 1 s comblés
    l, debut = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and debut is None:
            debut = i
        elif not v and debut is not None:
            if (i - debut) * 0.25 >= min_s:
                l.append((round(debut * 0.25, 2), round(i * 0.25, 2)))
            debut = None
    return l


def separer_piste(pid, ident, separer="4", studio_dir=None, progres=None, python_separation=None):
    """Une piste (l'instru de papa, une chanson importée) séparée en ses pistes : batterie, basse, mélodie et autres (le reste), [guitare,
    piano], voix ; elles la remplacent, à la même place sur la ligne du temps (ses régions recopiées). Rend le projet."""
    import studio_mesures as M
    dire = progres or (lambda n, s: None)
    d = dossier(pid, studio_dir)
    p = lire(pid, studio_dir)
    t = piste(p, ident)
    src = d / t["fichier"]
    sortie = d / "pistes" / f"{t['id']}-sep-{uuid.uuid4().hex[:4]}"
    dire(1, f"séparation de « {t['nom']} » (Demucs)")
    py = str(python_separation or studio.PYTHON_SEPARATION)
    modele = "htdemucs_6s" if str(separer) == "6" else "htdemucs_ft"
    r = subprocess.run(["/usr/bin/nice", "-n", "15", py, "-B", "-W", "ignore", str(ICI / "studio_separation.py"), "separer", str(src),
                        str(sortie), "--modeles", modele, "--format", "flac"], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError(f"séparation : {r.stderr.strip()[-300:]}")
    res = json.loads(r.stdout.strip().splitlines()[-1])
    dire(2, "les pistes (la somme refait la piste d'origine sans sa voix)")
    ins, _ = M.lire(res["instru"])
    autres = [s for s in res["pistes"] if s not in ("vocals", "other")]
    reste = ins.copy()
    for s in autres:
        y, _ = M.lire(res["pistes"][s])
        n = min(len(reste), len(y))
        reste[:n] -= y[:n]
    M.ecrire_wav(sortie / "other.flac", reste, SR, 16)
    os.unlink(res["instru"])
    rel = lambda s: str((sortie / f"{s}.flac").relative_to(d))

    def remplacer(q):
        x = piste(q, t["id"])
        i = q["pistes"].index(x)
        q["pistes"].remove(x)
        neuves = []
        for s in [*(s for s in ("drums", "bass", "guitar", "piano") if s in res["pistes"]), "other", "vocals"]:
            role = SOURCE_ROLE[s] if s != "vocals" else ("voix_origine" if x["role"] not in ROLES_VOIX else x["role"])
            n = ajouter_piste(q, rel(s), role, f"{ROLES[role]} ({x['nom']})" if s != "vocals" else f"Voix ({x['nom']})",
                              duree_s=x.get("duree_fichier_s"), origine=f"séparée de {x['nom']}")
            n["regions"] = copy.deepcopy(x["regions"])
            n["volume_db"] = x["volume_db"]
            q["pistes"].remove(n)
            neuves.append(n)
        q["pistes"][i:i] = neuves
    return modifier(pid, remplacer, studio_dir=studio_dir, note=f"piste « {t['nom']} » séparée en {len(res['pistes'])} pistes")


def base_pour_chanter(pid, studio_dir=None):
    """L'instru du projet pour qu'ACE-Step chante dessus : la piste « instru » telle quelle si elle est seule (sans réglage), sinon
    l'instru rendue (ses pistes non vocales, réglages compris) dans pistes/base-instru.wav. Rend le chemin."""
    d = dossier(pid, studio_dir)
    p = lire(pid, studio_dir)
    inst = actives(p, "instru")
    if not inst:
        raise Refus("le projet n'a pas d'instru (aucune piste qui ne soit pas une voix)")
    t = inst[0]
    plat = (len(inst) == 1 and t["volume_db"] == 0 and not any(abs(t["eq"].get(k, 0)) >= 0.1 for k in ("grave_db", "medium_db", "aigu_db"))
            and not t["eq"].get("coupe_bas_hz") and not t["comp"].get("actif") and len(t["regions"]) == 1 and t["regions"][0]["debut_s"] == 0
            and t["regions"][0]["source_debut_s"] == 0 and not t.get("reverb") and not t.get("delai") and not t.get("automation"))
    if plat:
        return d / t["fichier"]
    f = d / "pistes" / "base-instru.wav"
    rendre_bus(p, d, f, "instru", codec="pcm_s16le")
    return f


def resume(p, court=False):
    """Le projet en mots, pour Hakim."""
    l = [f"Projet « {p['titre']} » ({p['id']}, version {p['rev']}) : {p.get('duree_s') or '?'} s, "
         f"{p.get('tempo') or '?'} BPM (premier temps à {p.get('premier_temps_s', 0)} s), {p.get('tonalite') or 'tonalité ?'}, genre {p.get('genre')}."]
    for t in p["pistes"]:
        e = []
        if t.get("muet"):
            e.append("MUETTE")
        if t.get("solo"):
            e.append("SOLO")
        e.append(f"vol {t['volume_db']:+.1f} dB")
        if t.get("pan"):
            e.append(f"pan {t['pan']:+.2f}")
        if not court:
            eq = t["eq"]
            e.append("eq " + "/".join(f"{k} {eq[k]:+g}" for k in ("grave_db", "medium_db", "aigu_db") if abs(eq.get(k, 0)) >= 0.1) if any(
                abs(eq.get(k, 0)) >= 0.1 for k in ("grave_db", "medium_db", "aigu_db")) else "eq plat")
            if eq.get("coupe_bas_hz"):
                e.append(f"coupe-bas {eq['coupe_bas_hz']:.0f} Hz")
            if t["comp"].get("actif"):
                e.append(f"comp {t['comp']['ratio']:g}:1 à {t['comp']['seuil_db']:g} dB")
            if t.get("reverb"):
                e.append(f"réverb {t['reverb']:g}")
            if t.get("delai"):
                e.append(f"délai {t['delai']:g} ({t.get('delai_note')})")
            if t.get("autotune"):
                e.append(f"autotune {t['autotune'].replace('leger', 'léger')}")
            pr = _pro(t)
            if pr is not None:
                if not pr.get("actif"):
                    e.append("nettoyage coupé")
                else:
                    import studio_pro
                    forces = [f"{k} {pr.get(k)}" for k in studio_pro.ETAPES if pr.get(k, "auto") != "auto"]
                    e.append(f"voix {pr.get('type', 'principale')}, nettoyage mesuré" + (f" ({', '.join(forces)})" if forces else ""))
                    ref = piste_reference(p)
                    if est_calee(t, ref["id"] if ref else None):
                        e.append("calée sur la référence")
            if (t.get("comp_rapide") or {}).get("actif"):
                e.append(f"crêtes {t['comp_rapide']['ratio']:g}:1 à {t['comp_rapide']['seuil_db']:g} dB")
            if t.get("saturation"):
                e.append(f"saturation {t['saturation']:g}")
            if t.get("eq", {}).get("coupe_haut_hz"):
                e.append(f"coupe-haut {t['eq']['coupe_haut_hz']:.0f} Hz")
            if t.get("jetes"):
                e.append(f"délai jeté sur {len(t['jetes'])} fins de phrase")
            if (t.get("sidechain") or {}).get("cle"):
                e.append(f"creusée sous {t['sidechain']['cle']} ({t['sidechain']['db']} dB)")
            if t.get("automation"):
                e.append(f"{len(t['automation'])} points d'automation")
            if isinstance(t.get("profil"), dict):            # (14/11) son profil (voix téléphone, radio…)
                e.append(f"profil « {t['profil'].get('nom')} »" + ("" if t["profil"].get("actif", True) else " (coupé)"))
        l.append(f"- {t['id']} {t['nom']} ({ROLES.get(t['role'], t['role'])}) : " + ", ".join(e))
    rf = dict(reference_defaut(), **(p.get("reference") or {}))
    rt = piste_reference(p)
    l.append("Référence : " + ("aucune" if rf["source"] == "aucune" else f"{rt['nom']} ({rt['id']})" if rt is not None
                               else f"le profil gardé « {rf['profil']} »" + ("" if rf["source"] == "profil" else " (s'il existe)")) + ".")
    if p.get("zones"):
        l.append("Zones : " + " ; ".join(f"{z['nom']} ({z['qui']}) {z['debut_s']:.1f}-{z['fin_s']:.1f} s" for z in p["zones"]))
    m = p.get("master") or {}
    l.append(f"Master : {m.get('cible') or 'streaming'} ({m.get('lufs', -14)} LUFS), crête ≤ {m.get('crete_dbtp', -1)} dBTP, "
             f"{'3 bandes' if m.get('multibande', True) else 'compression en une bande'}, graves mono sous {m.get('mono_graves_hz', 120)} Hz, "
             f"largeur {m.get('largeur', 'auto')}, WAV 16 bits {'avec dither' if m.get('dither16', True) else 'sans'}"
             + (f" ; bus des voix (seuil {p['bus_voix'].get('seuil_db')} dB)" if (p.get('bus_voix') or {}).get('actif') else "") + ".")
    if p.get("rendus"):
        r = p["rendus"][-1]
        m = r["mesures"]["master"]
        l.append(f"Dernier rendu ({r['nom']}{', v' + str(r['v']) if r.get('v') else ''}) : {m.get('lufs')} LUFS, crête vraie {m.get('crete_dbtp')} dBTP (MP3 {r['mesures']['mp3'].get('crete_dbtp')}), "
                 f"PLR {m.get('plr_db')} dB. Avis : " + " ; ".join(r.get("avis", [])))
    return "\n".join(l)


def _oui(v):
    return v.strip().lower() in ("1", "oui", "vrai", "true", "on") if isinstance(v, str) else bool(v)


def regler_master(p, q):
    """(13/11, le studio pro) les réglages du master : cible (« streaming » −14 LUFS, « club » −9 LUFS), multibande (oui/non),
    largeur (« auto », ou 0 à 1,5), mono_graves_hz (0 = sans, 40 à 300), dither16 (oui/non). Les clés absentes ne changent pas."""
    import studio_pro
    m = p.setdefault("master", {})
    if q.get("cible") in CIBLES and "cible" not in studio_pro.COUPE:
        m["cible"], m["lufs"] = q["cible"], CIBLES[q["cible"]]
    if "multibande" in q:
        m["multibande"] = _oui(q["multibande"])
    if "largeur" in q:
        v = q["largeur"]
        m["largeur"] = "auto" if str(v).strip().lower() in ("auto", "") else round(_num(v, 0, 1.5, 1.0), 2)
    if "mono_graves_hz" in q:
        v = _num(q["mono_graves_hz"], 0, 300, 120)
        m["mono_graves_hz"] = 0.0 if v < 40 else round(v)
    if "dither16" in q:
        m["dither16"] = _oui(q["dither16"])
    return m


# ------------------------------------------------------------------------------------------------ le cockpit (une ligne JSON)
def commande(q, studio_dir=None, demarrer=None):
    """La page Studio du cockpit : {action, …} → un dict (jamais d'exception : {ok: False, erreur})."""
    a = str(q.get("action") or "")
    try:
        if a == "edition":                                  # (14/11) renommer, les mix nommés, les versions, les profils
            import studio_edition
            return studio_edition.commande(q, studio_dir)
        if a == "lister":
            return {"ok": True, "projets": lister(studio_dir)}
        if a == "lire":
            return {"ok": True, "projet": lire(q.get("id"), studio_dir)}
        if a == "regler":
            r = q.get("reglages") or {}

            def regler(x):
                import studio_edition
                regler_piste(piste(x, q.get("piste")), r)
                studio_edition.marquer_main(x, r)          # (14/11) un réglage à la main : le mix auto ne l'effacera pas sans le garder
            p = modifier(q.get("id"), regler, q.get("rev"), studio_dir,
                         note=f"papa règle {q.get('piste')} ({', '.join(sorted(r))[:80]})" if q.get("par") == "papa" else "")
            return {"ok": True, "projet": p}
        if a == "zones":
            z = q.get("zones")
            p = modifier(q.get("id"), lambda x: regler_zones(x, lire_zones(x, z) if isinstance(z, str) else z), q.get("rev"), studio_dir,
                         note="zones changées par papa" if q.get("par") == "papa" else "zones changées")
            return {"ok": True, "projet": p}
        if a == "projet":                                   # titre, tempo, tonalité, genre, master
            def changer(x):
                if "titre" in q:
                    x["titre"] = _mot(q["titre"], 80) or x["titre"]
                if "tempo" in q:
                    x["tempo"] = round(_num(q["tempo"], 0, 300, x.get("tempo") or 0), 2)
                if "premier_temps_s" in q:
                    x["premier_temps_s"] = round(_num(q["premier_temps_s"], 0, 60, 0), 3)
                if "tonalite" in q:
                    x["tonalite"] = _mot(q["tonalite"], 20)
                if "genre" in q:
                    x["genre"] = _mot(q["genre"], 20) or x["genre"]
                if "lufs" in q:
                    x["master"]["lufs"] = round(_num(q["lufs"], -20, -6, -14), 1)
                regler_master(x, q)
            return {"ok": True, "projet": modifier(q.get("id"), changer, q.get("rev"), studio_dir, note="projet réglé")}
        if a == "importer":                                 # une prise de papa (déjà écrite sur le disque) → une piste
            f = Path(str(q.get("fichier") or ""))
            if not f.is_file() or not str(f.resolve()).startswith(str((Path(studio_dir or studio.STUDIO)).resolve()) + os.sep):
                raise Refus("prise introuvable")
            lat = _num(q.get("latence_ms"), -500, 1500, 0) / 1000
            debut = _num(q.get("debut_s"), 0, 3600, 0)
            role = q.get("role") if q.get("role") in ROLES else "voix_papa"
            p = importer_son(q.get("id"), f, role, q.get("nom") or ROLES[role], debut, studio_dir, deplacer=bool(q.get("deplacer")))
            def caler(x):                                   # la latence retirée : la prise commence lat plus loin dans son fichier
                t = x["pistes"][-1]
                if lat >= 0:
                    t["regions"][0]["source_debut_s"] = round(lat, 4)
                else:
                    t["regions"][0]["debut_s"] = round(debut - lat, 4)
                t["latence_ms"] = round(lat * 1000)
            return {"ok": True, "projet": modifier(q.get("id"), caler, None, studio_dir, note=f"prise de papa posée à {debut:.1f} s")}
        if a == "reference":                                # (14/11) la référence du projet : source, piste, profil
            return {"ok": True, "projet": modifier(q.get("id"), lambda x: regler_reference(x, q), q.get("rev"), studio_dir,
                                                   note="référence changée par papa" if q.get("par") == "papa" else "référence changée")}
        if a == "garder_reference":                         # (14/11) une voix du projet gardée comme profil de référence (en file :
            p = lire(q.get("id"), studio_dir)               # rendre la voix seule et la mesurer prend du temps)
            t = piste(p, q.get("piste")) if q.get("piste") else piste_reference(p)
            if t is None or t["role"] not in ROLES_VOIX:
                raise Refus("aucune voix à garder comme référence (choisis la piste)")
            j = studio.lancer("reference", {"projet": p["id"], "piste": t["id"], "nom": _mot(q.get("nom"), 30) or "hakim",
                                            "par": q.get("par") or "papa"}, studio_dir, demarrer)
            return {"ok": True, "travail": j, "piste": t["id"]}
        if a == "references":
            return {"ok": True, "references": lister_references(studio_dir)}
        if a == "retirer":
            def retirer(x):
                x["pistes"].remove(piste(x, q.get("piste")))
            return {"ok": True, "projet": modifier(q.get("id"), retirer, q.get("rev"), studio_dir, note=f"piste {q.get('piste')} retirée")}
        if a in ("creer", "rendre", "separer"):
            typ = {"creer": "projet", "rendre": "rendre", "separer": "separer"}[a]
            params = {k: v for k, v in (q.get("params") or {}).items() if k in (
                "source", "titre", "separer", "garder", "role_voix", "genre", "projet", "mix_auto", "envoyer", "pistes_separees", "quoi", "piste",
                "tempo", "tonalite", "nom_version")}
            params["par"] = q.get("par") or "papa"
            j = studio.lancer(typ, params, studio_dir, demarrer)
            return {"ok": True, "travail": j}
        return {"ok": False, "erreur": "action inconnue"}
    except (Refus, studio.Refus) as e:
        return {"ok": False, "erreur": str(e)}


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "commande":
        try:
            q = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            q = {}
        # (14/11) studio_edition importe « studio_projet » : le même module que celui-ci (sa classe Refus, ses fonctions), pas une copie
        sys.modules.setdefault("studio_projet", sys.modules[__name__])
        import studio_edition
        print(json.dumps(studio_edition.pour_la_page_reponse(commande(q)), ensure_ascii=False))
    else:
        print("usage : studio_projet.py commande  (une ligne JSON en entrée)", file=sys.stderr)
        sys.exit(2)
