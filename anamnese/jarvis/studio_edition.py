"""Le studio : l'ÉDITION et les VERSIONS (14/11, Ahmed, relayé par Hakim et validé : « pouvoir renommer les pistes de voix et
pouvoir modifier manuellement le mix […] que je puisse aussi modifier et enregistrer mes mix » ; « chaque nouveau mix ou master
s'enregistre en version v1, v2, v3 au lieu d'écraser l'ancien » ; des profils « voix téléphone », « voix radio », « voix proche »).

LES MIX NOMMÉS (projet.json « mixes ») : la photo des réglages de mix de chaque piste (volume, panoramique, muet, solo, égaliseur,
compressions, saturation, dé-esseur, envois, autotune, sidechain, automation, délais jetés, nettoyage, profil) et du projet (master,
bus des voix, référence). Ni la place des pistes sur la ligne du temps (leurs régions) ni leurs noms n'en font partie. Rappeler un
mix repose sa photo sur les pistes qu'il connaît (même identifiant ET même son) ; une piste ajoutée depuis reste telle quelle.

LES VERSIONS (projet.json « versions » ; rendus/<rendu>.version.json) : chaque rendu devient v1, v2, v3… (un numéro jamais repris) ;
ses fichiers ne sont jamais écrasés, et le téléphone reçoit « Titre v3.mp3 » ; la version garde la photo du mix rendu : « revenir »
la repose. Une version se nomme ; seul papa l'efface (les fichiers du Mac ; la copie du téléphone reste). Les rendus d'avant les
versions deviennent v1… dans leur ordre, sans photo (leurs réglages ne sont pas connus).

LE MIX À LA MAIN (« edition.mix_main ») : un réglage de piste fait à la main (papa ou Hakim), un mix rappelé, une version reprise,
un profil posé le marquent ; un rendu avec le mix automatique l'efface. Le mix automatique referait tout : AVANT, le mix à la main
est gardé comme mix nommé (« Avant le mix auto du 14/11 15:40 ») — rien ne se perd.

LES PROFILS (studio/profils.json, et quatre de départ) : une couleur de voix — la bande passante et sa pente, un égaliseur, une
compression, une saturation (écrêtage doux suréchantillonné), une sortie — posée sur une piste comme un effet en fin de tranche
(après le dé-esseur, avant le volume) ; le mix automatique ne la touche pas. L'aperçu avant/après rend sur le Mac un extrait de la
piste seule, avec le même graphe que le rendu.

Chaque mécanisme a son témoin : STUDIO_EDITION_COUPE=<nom>[,<nom>] le coupe (nom, versions, photo, rappel, main, profil, apercu).
"""
import copy
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))

import studio  # noqa: E402
import studio_projet as SP  # noqa: E402

COUPE = frozenset(x for x in os.environ.get("STUDIO_EDITION_COUPE", "").split(",") if x)
Refus = SP.Refus

# ------------------------------------------------------------------------------------------------ la photo d'un mix
MIX_PISTE = ("volume_db", "pan", "muet", "solo", "eq", "comp", "comp_rapide", "saturation", "deesser", "reverb", "delai", "delai_note",
             "autotune", "sidechain", "automation", "jetes", "pro", "profil")
TOUJOURS = {"volume_db", "pan", "muet", "solo", "eq", "comp", "deesser", "reverb", "delai", "delai_note", "autotune", "sidechain"}
MIX_PROJET = ("master", "bus_voix", "reference")
HORS_MIX = {"nom", "regions", "role"}         # un réglage de piste qui n'est pas du mix (renommer, déplacer)
MAX_MIXES = 40


def mix_de(p):
    """La photo du mix d'un projet : {pistes: {id: {fichier, réglages}}, projet: {master, bus_voix, reference}}."""
    return {"pistes": {t["id"]: {"fichier": t.get("fichier"), **{k: copy.deepcopy(t[k]) for k in MIX_PISTE if k in t}} for t in p["pistes"]},
            "projet": {k: copy.deepcopy(p[k]) for k in MIX_PROJET if k in p}}


def empreinte(mix, ids=None):
    m = mix if ids is None else {"pistes": {k: v for k, v in (mix.get("pistes") or {}).items() if k in ids}, "projet": mix.get("projet") or {}}
    return hashlib.sha1(json.dumps(m, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:16]


def appliquer_mix(p, mix):
    """Repose la photo sur le projet (en mémoire). Rend {reposees, neuves (pas dans la photo), disparues, autre_son}."""
    rap = {"reposees": [], "neuves": [], "disparues": [], "autre_son": []}
    photo = (mix or {}).get("pistes") or {}
    if "rappel" in COUPE:
        return rap
    for t in p["pistes"]:
        s = photo.get(t["id"])
        if s is None:
            rap["neuves"].append(t["id"])
            continue
        if s.get("fichier") and s.get("fichier") != t.get("fichier"):        # le même identifiant, un autre son : jamais
            rap["autre_son"].append(t["id"])
            continue
        for k in MIX_PISTE:
            if k in s:
                t[k] = copy.deepcopy(s[k])
            elif k not in TOUJOURS:
                t.pop(k, None)
        rap["reposees"].append(t["id"])
    ids = {t["id"] for t in p["pistes"]}
    rap["disparues"] = [k for k in photo if k not in ids]
    for k, v in ((mix or {}).get("projet") or {}).items():
        if k in MIX_PROJET:
            p[k] = copy.deepcopy(v)
    return rap


def _edition(p):
    e = p.get("edition")
    if not isinstance(e, dict):
        e = p["edition"] = {"mix_main": False, "mix_courant": None}
    return e


def _courant(p, nom):
    """Le mix que le projet porte maintenant (un mix nommé, une version) : son empreinte dit plus tard s'il a été modifié."""
    ids = sorted(t["id"] for t in p["pistes"])
    _edition(p)["mix_courant"] = {"nom": nom, "pistes": ids, "empreinte": empreinte(mix_de(p), set(ids))}


def marquer_main(p, reglages):
    """Un réglage de piste fait à la main (papa par la page, Hakim par studio_piste) : le mix est « à la main »."""
    if "main" in COUPE:
        return
    if set(reglages or {}) - HORS_MIX:
        _edition(p)["mix_main"] = True


def _nom(v, n=60):
    return SP._mot(v, n)


def _resume_rappel(rap, p):
    noms = {t["id"]: t["nom"] for t in p["pistes"]}
    l = [f"{len(rap['reposees'])} piste(s) reprises"]
    if rap["neuves"]:
        l.append("laissées telles quelles (ajoutées depuis) : " + ", ".join(f"{k} {noms.get(k, '')}".strip() for k in rap["neuves"]))
    if rap["autre_son"]:
        l.append("laissées (un autre son sous le même numéro) : " + ", ".join(rap["autre_son"]))
    if rap["disparues"]:
        l.append("absentes du projet : " + ", ".join(rap["disparues"]))
    return " ; ".join(l)


# ------------------------------------------------------------------------------------------------ renommer une piste
def renommer_piste(p, ident, nom):
    t = SP.piste(p, ident)
    n = _nom(nom, 60)
    if not n:
        raise Refus("donne un nom à la piste")
    if re.fullmatch(r"t\d+", n.lower()):
        raise Refus("un nom comme « t3 » se confondrait avec un numéro de piste")
    k = studio._cle(n)
    autre = next((x for x in p["pistes"] if x is not t and studio._cle(x["nom"]) == k), None)
    if autre is not None:
        raise Refus(f"« {n} » est déjà le nom de {autre['id']} : choisis-en un autre")
    t["nom"] = n
    return t


# ------------------------------------------------------------------------------------------------ les mix nommés
def lister_mixes(p):
    return [{"nom": m["nom"], "t": m.get("t"), "par": m.get("par", "")} for m in p.get("mixes") or []]


def _trouver_mix(p, nom):
    k = studio._cle(nom)
    for m in p.get("mixes") or []:
        if studio._cle(m["nom"]) == k:
            return m
    raise Refus(f"aucun mix ne s'appelle « {nom} » (tes mix : {', '.join(m['nom'] for m in p.get('mixes') or []) or 'aucun'})")


def garder_mix(p, nom, par="papa"):
    """Le mix actuel gardé sous un nom (le même nom : il est remplacé, à sa place). Rend {nom, remplace}."""
    n = _nom(nom, 60)
    if not n:
        raise Refus("donne un nom au mix")
    l = p.setdefault("mixes", [])
    m = {"nom": n, "t": time.time(), "par": par, "mix": mix_de(p)}
    k = studio._cle(n)
    i = next((i for i, x in enumerate(l) if studio._cle(x["nom"]) == k), None)
    if i is None:
        if len(l) >= MAX_MIXES:
            raise Refus(f"{MAX_MIXES} mix au plus : efface-en un")
        l.append(m)
    else:
        l[i] = m
    _courant(p, n)
    return {"nom": n, "remplace": i is not None}


def rappeler_mix(p, nom):
    m = _trouver_mix(p, nom)
    rap = appliquer_mix(p, m["mix"])
    _courant(p, m["nom"])
    _edition(p)["mix_main"] = True
    return {"nom": m["nom"], **rap}


def renommer_mix(p, nom, nouveau):
    m = _trouver_mix(p, nom)
    n = _nom(nouveau, 60)
    if not n:
        raise Refus("donne le nouveau nom")
    if any(x is not m and studio._cle(x["nom"]) == studio._cle(n) for x in p.get("mixes") or []):
        raise Refus(f"un mix s'appelle déjà « {n} »")
    ancien, m["nom"] = m["nom"], n
    c = _edition(p).get("mix_courant")
    if c and c.get("nom") == ancien:
        c["nom"] = n
    return {"nom": n, "ancien": ancien}


def supprimer_mix(p, nom):
    m = _trouver_mix(p, nom)
    p["mixes"].remove(m)
    c = _edition(p).get("mix_courant")
    if c and c.get("nom") == m["nom"]:
        _edition(p)["mix_courant"] = None
    return {"nom": m["nom"]}


# ------------------------------------------------------------------------------------------------ les versions
def _compact(v, rendu, mix_auto=None, par="", nom_version="", photo=None):
    f = rendu.get("fichiers") or {}
    m = ((rendu.get("mesures") or {}).get("master")) or {}
    return {"v": v, "nom": _nom(nom_version, 60), "rendu": rendu.get("nom"), "t": rendu.get("t"),
            "fichiers": {k: {kk: x[kk] for kk in ("wav", "mp3", "wav16") if x.get(kk)} for k, x in f.items() if k != "pistes" and isinstance(x, dict)},
            "pistes": list((f.get("pistes") or {}).values()),
            "master": {k: m.get(k) for k in ("lufs", "crete_dbtp", "plr_db", "lra")},
            "mp3_crete_dbtp": ((rendu.get("mesures") or {}).get("mp3") or {}).get("crete_dbtp"),
            "cible": (rendu.get("master_reglages") or {}).get("cible"),
            "mix_auto": mix_auto, "par": par, "photo": photo, "telephone": rendu.get("telephone") or {}}


def versions_de(p):
    """Les versions du projet ; un projet d'avant les versions : ses rendus deviennent v1… dans leur ordre (sans photo)."""
    if "versions" in p and "versions" not in COUPE:
        return p["versions"]
    return [_compact(i + 1, r) for i, r in enumerate(p.get("rendus") or [])]


def assurer_versions(p):
    """Le projet porte ses versions (les rendus d'avant deviennent v1… sans photo). Rend True s'il a changé (en mémoire)."""
    if "versions" in p or "versions" in COUPE:
        return False
    p["versions"] = versions_de(p)
    for r, v in zip(p.get("rendus") or [], p["versions"]):
        r["v"] = v["v"]
    p["version_suivante"] = len(p["versions"]) + 1
    return True


def avant_rendu(pid, mix_auto, studio_dir=None, par=""):
    """Au début d'un rendu : les versions assurées, le numéro de la version réservé, et — un mix automatique referait tout — le mix
    à la main gardé comme mix nommé. Rend {v, garde (le nom du mix gardé, ou "")}."""
    out = {"v": None, "garde": ""}

    def f(q):
        assurer_versions(q)
        e = _edition(q)
        if mix_auto and e.get("mix_main") and "main" not in COUPE:
            n = "Avant le mix auto du " + time.strftime("%d/%m %H:%M")
            garder_mix(q, n, par="auto")
            out["garde"] = n
        if "versions" not in COUPE:
            v = int(q.get("version_suivante") or len(q.get("versions") or []) + 1)
            q["version_suivante"] = v + 1
            out["v"] = v
    SP.modifier(pid, f, studio_dir=studio_dir, note="rendu : version réservée")
    return out


def annuler_version(pid, v, studio_dir=None):
    """Un rendu raté : son numéro rendu (s'il est encore le dernier réservé)."""
    if not v:
        return

    def f(q):
        if q.get("version_suivante") == v + 1 and not any(x.get("v") == v for x in q.get("versions") or []):
            q["version_suivante"] = v
    try:
        SP.modifier(pid, f, studio_dir=studio_dir)
    except Refus:
        pass


def suffixe(v):
    """« Titre v3.mp3 » sur le téléphone : un nouveau rendu n'écrase plus le précédent."""
    return f" v{v}" if v and "versions" not in COUPE else ""


def noter_version(q, d, rendu, v, mix, mix_auto, par="", nom_version=""):
    """À la fin d'un rendu (dans la modification du projet) : la version et sa photo (rendus/<rendu>.version.json)."""
    if not v or "versions" in COUPE:
        return
    rendu["v"] = v
    photo = None
    if "photo" not in COUPE:
        f = Path(d) / "rendus" / f"{rendu['nom']}.version.json"
        SP._ecrire(f, {"v": v, "rendu": rendu, "mix": mix})
        photo = f"rendus/{f.name}"
    assurer_versions(q)
    q.setdefault("versions", []).append(_compact(v, rendu, bool(mix_auto), par, nom_version, photo))
    q["version_suivante"] = max(int(q.get("version_suivante") or 0), v + 1)
    e = _edition(q)
    if mix_auto:
        e["mix_main"] = False
    ids = sorted(mix["pistes"])
    e["mix_courant"] = {"nom": f"v{v}", "pistes": ids, "empreinte": empreinte(mix, set(ids))}


def _version(p, v):
    try:
        n = int(str(v).strip().lower().lstrip("v"))
    except (TypeError, ValueError):
        n = None
    for x in versions_de(p):
        if x["v"] == n or (n is None and x.get("nom") and studio._cle(x["nom"]) == studio._cle(v)):
            return x
    raise Refus(f"version inconnue : {v} (versions : {', '.join('v' + str(x['v']) for x in versions_de(p)) or 'aucune'})")


def nommer_version(p, v, nom):
    assurer_versions(p)
    x = _version(p, v)
    x["nom"] = _nom(nom, 60)
    return {"v": x["v"], "nom": x["nom"]}


def photo_de(d, x):
    if not x.get("photo"):
        return None
    f = (Path(d) / x["photo"]).resolve()
    if not str(f).startswith(str((Path(d) / "rendus").resolve()) + os.sep):
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("mix")
    except (OSError, ValueError):
        return None


def revenir(p, d, v):
    """Le mix d'une version reposé sur le projet (en mémoire)."""
    assurer_versions(p)
    x = _version(p, v)
    mix = photo_de(d, x)
    if not mix:
        raise Refus(f"v{x['v']} vient d'avant les versions : ses réglages n'ont pas été gardés (on peut l'écouter, pas y revenir)")
    rap = appliquer_mix(p, mix)
    _courant(p, f"v{x['v']}")
    _edition(p)["mix_main"] = True
    return {"v": x["v"], **rap}


def supprimer_version(p, d, v):
    """(papa seul) Les fichiers d'une version effacés du Mac (rendus/ seulement ; la copie du téléphone reste) ; son numéro n'est
    jamais repris."""
    assurer_versions(p)
    x = _version(p, v)
    rd = (Path(d) / "rendus").resolve()
    effaces = 0
    chemins = [y for f in (x.get("fichiers") or {}).values() for y in f.values()] + list(x.get("pistes") or [])
    if x.get("photo"):
        chemins.append(str(Path(d) / x["photo"]))
    for c in chemins:
        f = Path(c).resolve()
        if str(f).startswith(str(rd) + os.sep) and f.is_file():
            f.unlink()
            effaces += 1
    p["versions"].remove(x)
    p["rendus"] = [r for r in p.get("rendus") or [] if r.get("nom") != x.get("rendu")]
    return {"v": x["v"], "effaces": effaces}


def _aplatir(x, pre=""):
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            out.update(_aplatir(v, f"{pre}.{k}" if pre else str(k)))
        return out
    return {pre: x}


def differences(a, b, noms=None, n=40):
    """Ce qui change d'une photo de mix à l'autre, en lignes courtes."""
    noms = noms or {}
    l = []
    pa, pb = (a or {}).get("pistes") or {}, (b or {}).get("pistes") or {}
    for tid in sorted(set(pa) | set(pb), key=lambda s: int(s[1:]) if s[1:].isdigit() else 0):
        if tid not in pa or tid not in pb:
            l.append(f"{tid} {noms.get(tid, '')} : seulement dans {'la seconde' if tid not in pa else 'la première'}".replace("  ", " "))
            continue
        fa, fb = _aplatir({k: v for k, v in pa[tid].items() if k != "fichier"}), _aplatir({k: v for k, v in pb[tid].items() if k != "fichier"})
        ch = [f"{k} {fa.get(k)} → {fb.get(k)}" for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
        if ch:
            l.append(f"{tid} {noms.get(tid, '')} : " + ", ".join(ch[:8]) + (f" (+{len(ch) - 8})" if len(ch) > 8 else ""))
    fa, fb = _aplatir((a or {}).get("projet") or {}), _aplatir((b or {}).get("projet") or {})
    ch = [f"{k} {fa.get(k)} → {fb.get(k)}" for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
    if ch:
        l.append("projet : " + ", ".join(ch[:8]))
    return l[:n]


def comparer(p, d, a, b):
    """Deux versions : leurs mesures et ce qui change dans leurs réglages (si leurs photos sont connues)."""
    x, y = _version(p, a), _version(p, b)
    noms = {t["id"]: t["nom"] for t in p["pistes"]}
    ma, mb = photo_de(d, x), photo_de(d, y)
    return {"a": x, "b": y, "differences": differences(ma, mb, noms) if ma and mb else None}


# ------------------------------------------------------------------------------------------------ les profils
PROFIL_BORNES = {"coupe_bas_hz": (0, 1000), "coupe_haut_hz": (0, 20000), "pente": (12, 24), "grave_db": (-12, 12), "grave_hz": (40, 400),
                 "medium_db": (-12, 12), "medium_hz": (150, 8000), "medium_q": (0.3, 6), "aigu_db": (-12, 12), "aigu_hz": (2000, 16000),
                 "seuil_db": (-50, 0), "ratio": (1, 20), "attaque_ms": (0.1, 200), "relache_ms": (5, 2000), "saturation": (0, 1),
                 "sortie_db": (-24, 12)}
PROFIL_NEUTRE = {"coupe_bas_hz": 0.0, "coupe_haut_hz": 0.0, "pente": 12, "grave_db": 0.0, "grave_hz": 120.0, "medium_db": 0.0,
                 "medium_hz": 1000.0, "medium_q": 1.0, "aigu_db": 0.0, "aigu_hz": 8000.0, "seuil_db": -20.0, "ratio": 1.0, "attaque_ms": 5.0,
                 "relache_ms": 120.0, "saturation": 0.0, "sortie_db": 0.0}
# Les profils de départ (des points de départ sensés, à régler à l'oreille) : la bande d'un téléphone (300-3400 Hz, la norme du
# réseau), celle d'un vieux poste de radio (plus large, plus saturé), une voix tout contre le micro (l'effet de proximité, l'air, une
# compression douce), un mégaphone (bande étroite, médium nasal, saturé). Leur sortie rattrape ce que la bande retire (mesuré le
# 14/11 sur la prise de papa au Steinberg, t8 du projet du 14/11 : à ±1 dB de la voix sans profil, pour garder l'équilibre du mix).
PROFILS_DEPART = {
    "voix téléphone": {"coupe_bas_hz": 300, "coupe_haut_hz": 3400, "pente": 24, "medium_db": 4, "medium_hz": 1500, "medium_q": 1.0,
                       "seuil_db": -24, "ratio": 4, "attaque_ms": 5, "relache_ms": 100, "saturation": 0.3, "sortie_db": 3},
    "voix radio": {"coupe_bas_hz": 450, "coupe_haut_hz": 4500, "pente": 24, "medium_db": 3, "medium_hz": 2000, "medium_q": 0.8,
                   "seuil_db": -26, "ratio": 6, "attaque_ms": 3, "relache_ms": 80, "saturation": 0.45, "sortie_db": 5},
    "voix proche": {"coupe_bas_hz": 60, "pente": 12, "grave_db": 3, "grave_hz": 150, "medium_db": -2, "medium_hz": 400, "medium_q": 1.2,
                    "aigu_db": 2.5, "aigu_hz": 9000, "seuil_db": -22, "ratio": 3, "attaque_ms": 10, "relache_ms": 120, "saturation": 0.1,
                    "sortie_db": 1},
    "voix mégaphone": {"coupe_bas_hz": 600, "coupe_haut_hz": 3000, "pente": 24, "medium_db": 6, "medium_hz": 1800, "medium_q": 1.4,
                       "seuil_db": -24, "ratio": 8, "attaque_ms": 2, "relache_ms": 60, "saturation": 0.7, "sortie_db": 7},
}
ALIAS_PROFIL = {"coupe_bas": "coupe_bas_hz", "coupe-bas": "coupe_bas_hz", "bas": "coupe_bas_hz", "coupe_haut": "coupe_haut_hz",
                "coupe-haut": "coupe_haut_hz", "haut": "coupe_haut_hz", "grave": "grave_db", "graves": "grave_db", "medium": "medium_db",
                "médium": "medium_db", "mediums": "medium_db", "q": "medium_q", "aigu": "aigu_db", "aigus": "aigu_db", "seuil": "seuil_db",
                "attaque": "attaque_ms", "relache": "relache_ms", "relâche": "relache_ms", "sortie": "sortie_db", "gain": "sortie_db",
                "volume": "sortie_db", "sat": "saturation", "distorsion": "saturation"}


def borner_profil(r, base=None):
    """Les réglages d'un profil, bornés ; les clés absentes gardent celles de base (sinon celles d'un profil neutre)."""
    out = dict(PROFIL_NEUTRE, **{k: v for k, v in (base or {}).items() if k in PROFIL_BORNES})
    for k, (a, b) in PROFIL_BORNES.items():
        if k in (r or {}):
            out[k] = round(SP._num(r[k], a, b, out[k]), 2)
    out["pente"] = 24 if float(out["pente"]) >= 18 else 12
    out["coupe_haut_hz"] = 0.0 if out["coupe_haut_hz"] < 1000 else out["coupe_haut_hz"]
    out["coupe_bas_hz"] = 0.0 if out["coupe_bas_hz"] < 20 else out["coupe_bas_hz"]
    return out


def lire_profil(texte):
    """« bande=300-3400, pente=24, medium=+4, medium_hz=1500, seuil=-24, ratio=4, saturation=0.3, sortie=+2 » (ou un JSON) → un dict."""
    t = str(texte or "").strip()
    if not t:
        return {}
    if t.startswith("{"):
        try:
            return json.loads(t)
        except ValueError:
            raise Refus("profil : un JSON illisible")
    r = {}
    for bout in re.split(r"[;,\n]+", t):
        if not bout.strip():
            continue
        k, _, v = bout.partition("=") if "=" in bout else bout.partition(":")
        k = k.strip().lower()
        v = v.strip().lower().replace(",", ".").replace("db", "").replace("hz", "").strip()
        if k in ("bande", "bande_passante"):
            m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-|–|à)\s*(\d+(?:\.\d+)?)", v)
            if not m:
                raise Refus(f"bande illisible : « {bout.strip()} » (exemple : bande=300-3400)")
            r["coupe_bas_hz"], r["coupe_haut_hz"] = float(m.group(1)), float(m.group(2))
            continue
        k = ALIAS_PROFIL.get(k, k)
        if k not in PROFIL_BORNES:
            raise Refus(f"réglage de profil inconnu : « {k} » (bande, pente, grave, medium, medium_hz, q, aigu, seuil, ratio, attaque, "
                        "relache, saturation, sortie)")
        try:
            r[k] = float(v)
        except ValueError:
            raise Refus(f"réglage illisible : « {bout.strip()} »")
    return r


def profils_fichier(studio_dir=None):
    return Path(studio_dir or studio.STUDIO) / "profils.json"


def _lire_profils(studio_dir=None):
    try:
        x = json.loads(profils_fichier(studio_dir).read_text(encoding="utf-8"))
        return x if isinstance(x.get("profils"), dict) else {"profils": {}}
    except (OSError, ValueError, AttributeError):
        return {"profils": {}}


def _changer_profils(fonction, studio_dir=None):
    f = profils_fichier(studio_dir)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f.with_name(".profils.verrou"), "w") as v:
        fcntl.flock(v, fcntl.LOCK_EX)
        try:
            x = _lire_profils(studio_dir)
            r = fonction(x["profils"])
            SP._ecrire(f, x)
            return r
        finally:
            fcntl.flock(v, fcntl.LOCK_UN)


def lister_profils(studio_dir=None):
    """Les profils : ceux de départ (réglés à la main : leur version gardée), puis ceux de papa et de Hakim."""
    gardes = _lire_profils(studio_dir)["profils"]
    out = []
    for nom, r in PROFILS_DEPART.items():
        g = gardes.get(studio._cle(nom))
        out.append({"nom": nom, "reglages": borner_profil((g or {}).get("reglages") or r), "depart": True, "modifie": bool(g),
                    "t": (g or {}).get("t"), "par": (g or {}).get("par", "")})
    cles = {studio._cle(n) for n in PROFILS_DEPART}
    for k, g in sorted(gardes.items(), key=lambda kv: kv[1].get("t") or 0):
        if k not in cles and isinstance(g, dict) and g.get("nom"):
            out.append({"nom": g["nom"], "reglages": borner_profil(g.get("reglages") or {}), "depart": False, "modifie": False,
                        "t": g.get("t"), "par": g.get("par", "")})
    return out


def trouver_profil(nom, studio_dir=None):
    k = studio._cle(nom)
    for x in lister_profils(studio_dir):
        if studio._cle(x["nom"]) == k:
            return x
    raise Refus(f"aucun profil ne s'appelle « {nom} » (profils : {', '.join(x['nom'] for x in lister_profils(studio_dir))})")


def garder_profil(nom, reglages, studio_dir=None, par="papa"):
    n = _nom(nom, 40)
    if not n:
        raise Refus("donne un nom au profil")
    r = borner_profil(reglages)

    def f(gardes):
        if len(gardes) >= 60 and studio._cle(n) not in gardes:
            raise Refus("60 profils au plus : efface-en un")
        gardes[studio._cle(n)] = {"nom": n, "reglages": r, "t": time.time(), "par": par}
    _changer_profils(f, studio_dir)
    return trouver_profil(n, studio_dir)


def supprimer_profil(nom, studio_dir=None):
    """Un profil de papa ou de Hakim effacé ; un profil de départ réglé à la main revient à ses réglages de départ."""
    x = trouver_profil(nom, studio_dir)
    if x["depart"] and not x["modifie"]:
        raise Refus(f"« {x['nom']} » est un profil de départ : il ne s'efface pas (règle-le, ou garde une copie sous un autre nom)")
    _changer_profils(lambda g: g.pop(studio._cle(x["nom"]), None), studio_dir)
    return {"nom": x["nom"], "reinitialise": x["depart"]}


def appliquer_profil(t, x):
    """Le profil x ({nom, reglages}) posé sur la piste t (une copie : régler le profil plus tard ne change pas la piste)."""
    t["profil"] = {"nom": x["nom"], "actif": True, **borner_profil(x["reglages"])}
    return t["profil"]


def regler_profil_piste(t, r):
    """Le profil d'une piste réglé à la main (borné) ; actif=non le coupe sans l'oublier."""
    pr = t.get("profil")
    if not isinstance(pr, dict):
        raise Refus(f"la piste {t['id']} n'a pas de profil : pose-en un d'abord")
    if "actif" in r:
        v = r["actif"]
        pr["actif"] = v.lower() in ("1", "oui", "vrai", "true", "on") if isinstance(v, str) else bool(v)
    pr.update(borner_profil(r, pr))
    return pr


def chaine_profil(pr, sr=SP.SR):
    """Les filtres ffmpeg d'un profil posé sur une piste (en fin de tranche) : la bande passante (12 ou 24 dB par octave),
    l'égaliseur, la compression, la saturation (un écrêtage doux tanh à 4× la fréquence : il ne touche pas un signal faible, il arrondit
    les crêtes poussées par la saturation, puis le même gain retiré), la sortie."""
    if not isinstance(pr, dict) or not pr.get("actif", True) or "profil" in COUPE:
        return []
    x = borner_profil(pr)
    f = []
    n = 2 if x["pente"] >= 24 else 1
    if x["coupe_bas_hz"] >= 20:
        f += [f"highpass=f={x['coupe_bas_hz']:.0f}:poles=2"] * n
    if x["coupe_haut_hz"] >= 1000:
        f += [f"lowpass=f={x['coupe_haut_hz']:.0f}:poles=2"] * n
    if abs(x["grave_db"]) >= 0.1:
        f.append(f"bass=g={x['grave_db']:.2f}:f={x['grave_hz']:.0f}:w=0.7")
    if abs(x["medium_db"]) >= 0.1:
        f.append(f"equalizer=f={x['medium_hz']:.0f}:t=q:w={x['medium_q']:.2f}:g={x['medium_db']:.2f}")
    if abs(x["aigu_db"]) >= 0.1:
        f.append(f"treble=g={x['aigu_db']:.2f}:f={x['aigu_hz']:.0f}:w=0.7")
    if x["ratio"] > 1.01:
        f.append(f"acompressor=threshold={x['seuil_db']:.1f}dB:ratio={x['ratio']:.2f}:attack={x['attaque_ms']:.2f}:"
                 f"release={x['relache_ms']:.0f}:makeup=1:knee=2.8")
    if x["saturation"] > 0:
        g = 30.0 * x["saturation"]
        f += [f"volume={g:.2f}dB", f"aresample={4 * sr}", "asoftclip=type=tanh", f"aresample={sr}", f"volume={-g:.2f}dB"]
    if abs(x["sortie_db"]) >= 0.1:
        f.append(f"volume={x['sortie_db']:.2f}dB")
    return f


# ------------------------------------------------------------------------------------------------ l'aperçu avant/après
def _voix_prete(p, d, t):
    """Le son d'une voix tel qu'il entre au mix s'il est DÉJÀ calculé (le nettoyage, l'autotune : leurs caches), sinon la prise brute.
    Rend (chemin, « nettoyée » | « brute »). (Mêmes clés que studio_projet.preparer_pro et preparer_autotune.)"""
    import studio_pro
    src = Path(d) / t["fichier"]
    etat = "brute"
    pr = SP._pro(t)
    if pr and pr.get("actif") and src.is_file():
        st = src.stat()
        cle = hashlib.sha1(json.dumps([src.name, st.st_mtime_ns, st.st_size, pr, studio_pro.VERSION, sorted(studio_pro.COUPE)],
                                      sort_keys=True).encode()).hexdigest()[:16]
        c = Path(d) / "pistes" / ".pro" / f"{t['id']}-{cle}.wav"
        if c.is_file():
            src, etat = c, "nettoyée"
    if t.get("autotune") and t.get("role") in SP.ROLES_VOIX and src.is_file():
        cle = studio._cle(f"{src.name} {src.stat().st_mtime_ns} {t['autotune']} {p.get('tonalite')}").replace(" ", "-")[:120]
        c = Path(d) / "pistes" / ".autotune" / f"{cle}.wav"
        if c.is_file():
            src, etat = c, etat + ", autotune"
    return str(src), etat


def _longueur(d, t, r):
    if r.get("duree_s") is not None:
        return float(r["duree_s"])
    du = t.get("duree_fichier_s") or studio.duree(Path(d) / t["fichier"]) or 0
    return max(0.0, float(du) - float(r.get("source_debut_s") or 0))


def debut_extrait(p, d, t, debut_s=None, duree=12.0):
    """Où commence l'extrait de l'aperçu : là où est la lecture si la piste y sonne, sinon le premier passage où elle sonne."""
    regs = t.get("regions") or [{"debut_s": 0.0, "source_debut_s": 0.0, "duree_s": None}]
    spans = [(float(r["debut_s"]), float(r["debut_s"]) + _longueur(d, t, r), r) for r in regs]
    if debut_s is not None:
        a = float(debut_s)
        for x, y, _ in spans:
            if x <= a < y - 1.0:
                return round(a, 2)
    try:
        act = SP.activite_voix(Path(d) / t["fichier"])
    except Exception:              # noqa: BLE001 — l'aperçu part du début de la région
        act = []
    for x, y, r in spans:
        s0 = float(r.get("source_debut_s") or 0)
        for a, b in act:
            if b > s0 + 0.5:
                return round(x + max(0.0, a - s0), 2)
    return round(spans[0][0], 2) if spans else 0.0


def _extrait(p, t, d, a, duree):
    """Une copie du projet où ne reste que la piste t, ses régions ramenées à l'extrait [a, a + durée] (posé à 0)."""
    q = copy.deepcopy(p)
    tq = next(x for x in q["pistes"] if x["id"] == t["id"])
    regs = []
    for r in tq.get("regions") or [{"debut_s": 0.0, "source_debut_s": 0.0, "duree_s": None, "gain_db": 0.0}]:
        deb, lon = float(r["debut_s"]), _longueur(d, t, r)
        if deb + lon <= a or deb >= a + duree:
            continue
        coupe = max(0.0, a - deb)
        regs.append({"debut_s": round(max(0.0, deb - a), 4), "source_debut_s": round(float(r.get("source_debut_s") or 0) + coupe, 4),
                     "duree_s": round(min(lon - coupe, a + duree - max(deb, a)), 4), "gain_db": r.get("gain_db", 0.0)})
    if not regs:
        raise Refus("la piste ne sonne pas à cet endroit")
    tq["regions"] = regs
    tq["sidechain"] = {"cle": "", "db": 0.0}
    tq["automation"] = [{"t": round(x["t"] - a, 3), "db": x["db"]} for x in tq.get("automation") or []]
    tq["jetes"] = [[round(x - a, 3), round(y - a, 3)] for x, y in tq.get("jetes") or [] if y > a]
    tq["muet"], tq["solo"] = False, False
    q["pistes"] = [tq]
    q["zones"] = []
    return q, tq


def apercu(pid, ident, profil=None, debut_s=None, duree=12.0, studio_dir=None):
    """L'aperçu AVANT/APRÈS d'un profil sur une piste : un extrait de la piste seule rendu deux fois sur le Mac (le même graphe que le
    rendu) — avant : la piste telle qu'elle est ; après : avec le profil donné (un nom, ou des réglages), ou, sans profil donné, avec
    le sien (avant : sans). Les deux MP3 dans rendus/apercus/ (les 12 derniers gardés), leurs niveaux mesurés. Rend la fiche."""
    import studio_mesures as M
    d = SP.dossier(pid, studio_dir)
    p = SP.lire(pid, studio_dir)
    t = SP.piste(p, ident)
    if isinstance(profil, str) and profil.strip():
        x = trouver_profil(profil, studio_dir)
        apres_pr = {"nom": x["nom"], "actif": True, **x["reglages"]}
        avant_pr = t.get("profil")
    elif isinstance(profil, dict) and profil:
        base = (t.get("profil") if isinstance(t.get("profil"), dict) else None) or {}
        apres_pr = {"nom": _nom(profil.get("nom") or base.get("nom") or "réglé à la main", 40), "actif": True, **borner_profil(profil, base)}
        avant_pr = t.get("profil")
    elif isinstance(t.get("profil"), dict):
        apres_pr, avant_pr = dict(t["profil"], actif=True), None
    else:
        raise Refus("quel profil essayer ? (la piste n'en a pas)")
    if "apercu" in COUPE:
        avant_pr = apres_pr
    duree = float(SP._num(duree, 3, 30, 12))
    a = debut_extrait(p, d, t, debut_s, duree)
    q, tq = _extrait(p, t, d, a, duree)
    src, etat = _voix_prete(p, d, t)
    out = Path(d) / "rendus" / "apercus"
    out.mkdir(parents=True, exist_ok=True)
    jeton = uuid.uuid4().hex[:6]
    travail = Path(tempfile.mkdtemp(prefix=".apercu-", dir=d))
    fiche = {"piste": t["id"], "nom": t["nom"], "profil": apres_pr.get("nom"), "debut_s": a, "duree_s": duree, "voix": etat}
    try:
        for cote, pr in (("avant", avant_pr), ("apres", apres_pr)):
            if isinstance(pr, dict):
                tq["profil"] = dict(pr)
            else:
                tq.pop("profil", None)
            w = travail / f"{cote}.wav"
            SP.rendre_bus(q, d, w, seules=[t["id"]], fichiers={t["id"]: src}, duree=duree + 1.5)
            mp = out / f"{t['id']}-{jeton}-{cote}.mp3"
            SP._filtre(w, mp, "anull", "libmp3lame")
            m = M.ebur128(w)
            fiche[cote] = str(mp)
            fiche[f"lufs_{cote}"] = m["lufs"]
            fiche[f"crete_{cote}_dbtp"] = m["crete_dbtp"]
    finally:
        shutil.rmtree(travail, ignore_errors=True)
    la, lb = fiche.get("lufs_avant"), fiche.get("lufs_apres")
    fiche["ecart_db"] = round(lb - la, 1) if la is not None and lb is not None and la > -70 and lb > -70 else None
    for f in sorted(out.glob("*.mp3"), key=lambda z: z.stat().st_mtime, reverse=True)[24:]:
        f.unlink(missing_ok=True)
    return fiche


# ------------------------------------------------------------------------------------------------ pour la page
def pour_la_page(p):
    """Ce que la page voit en plus : les versions (celles d'avant numérotées), l'état du mix (à la main, le mix porté et s'il a été
    modifié depuis), les mix nommés sans leurs photos (la page n'en a pas besoin)."""
    if not isinstance(p, dict) or "pistes" not in p:
        return p
    q = dict(p)
    e = p.get("edition") if isinstance(p.get("edition"), dict) else {}
    c = e.get("mix_courant")
    etat = {"mix_main": bool(e.get("mix_main")), "mix_courant": None, "modifie": False}
    if isinstance(c, dict) and c.get("nom"):
        ids = set(c.get("pistes") or [])
        etat.update(mix_courant=c["nom"], modifie=empreinte(mix_de(p), ids) != c.get("empreinte"))
    q["edition_etat"] = etat
    q["mixes"] = lister_mixes(p)
    q["versions"] = versions_de(p)
    return q


def pour_la_page_reponse(r):
    if isinstance(r, dict) and isinstance(r.get("projet"), dict):
        r = dict(r, projet=pour_la_page(r["projet"]))
    return r


# ------------------------------------------------------------------------------------------------ la commande (page et Hakim)
QUOI = ("renommer", "mixes", "garder_mix", "rappeler_mix", "renommer_mix", "supprimer_mix", "versions", "nommer_version", "revenir",
        "supprimer_version", "comparer", "profils", "garder_profil", "supprimer_profil", "appliquer_profil", "retirer_profil",
        "regler_profil", "apercu")


def commande(q, studio_dir=None):
    """{action: "edition", quoi, id, rev, …} → un dict (jamais d'exception : {ok: False, erreur})."""
    quoi = str(q.get("quoi") or "")
    par = "hakim" if q.get("par") == "hakim" else "papa"
    rev = q.get("rev")
    try:
        if quoi not in QUOI:
            return {"ok": False, "erreur": "édition inconnue"}
        if quoi == "profils":
            return {"ok": True, "profils": lister_profils(studio_dir)}
        if quoi == "garder_profil" and not q.get("piste"):
            return {"ok": True, "profil": garder_profil(q.get("nom"), q.get("reglages") or {}, studio_dir, par), "profils": lister_profils(studio_dir)}
        if quoi == "supprimer_profil":
            return {"ok": True, **supprimer_profil(q.get("nom"), studio_dir), "profils": lister_profils(studio_dir)}
        pid = q.get("id")
        d = SP.dossier(pid, studio_dir)
        out = {}

        def faire(fonction, note, avec_rev=True):
            def f(x):
                out.update(fonction(x) or {})
            return SP.modifier(pid, f, rev if avec_rev else None, studio_dir, note=note)
        if quoi == "renommer":
            p = faire(lambda x: {"piste": renommer_piste(x, q.get("piste"), q.get("nom"))["id"]},
                      f"{q.get('piste')} renommée « {_nom(q.get('nom'), 60)} » ({par})")
            return {"ok": True, "projet": p, **out}
        if quoi == "mixes":
            return {"ok": True, "mixes": lister_mixes(SP.lire(pid, studio_dir))}
        if quoi == "garder_mix":
            p = faire(lambda x: garder_mix(x, q.get("nom"), par), f"mix gardé : « {_nom(q.get('nom'))} » ({par})", False)
            return {"ok": True, "projet": p, **out}
        if quoi == "rappeler_mix":
            p = faire(lambda x: rappeler_mix(x, q.get("nom")), f"mix rappelé : « {_nom(q.get('nom'))} » ({par})")
            return {"ok": True, "projet": p, **out, "dit": _resume_rappel(out, p)}
        if quoi == "renommer_mix":
            p = faire(lambda x: renommer_mix(x, q.get("nom"), q.get("nouveau")), f"mix renommé ({par})", False)
            return {"ok": True, "projet": p, **out}
        if quoi == "supprimer_mix":
            p = faire(lambda x: supprimer_mix(x, q.get("nom")), f"mix effacé : « {_nom(q.get('nom'))} » ({par})", False)
            return {"ok": True, "projet": p, **out}
        if quoi == "versions":
            return {"ok": True, "versions": versions_de(SP.lire(pid, studio_dir))}
        if quoi == "nommer_version":
            p = faire(lambda x: nommer_version(x, q.get("v"), q.get("nom")), f"version {q.get('v')} nommée ({par})", False)
            return {"ok": True, "projet": p, **out}
        if quoi == "revenir":
            p = faire(lambda x: revenir(x, d, q.get("v")), f"retour au mix de la version {q.get('v')} ({par})")
            return {"ok": True, "projet": p, **out, "dit": _resume_rappel(out, p)}
        if quoi == "supprimer_version":
            if par != "papa":
                return {"ok": False, "erreur": "seul papa efface une version"}
            p = faire(lambda x: supprimer_version(x, d, q.get("v")), f"version {q.get('v')} effacée du Mac", False)
            return {"ok": True, "projet": p, **out}
        if quoi == "comparer":
            return {"ok": True, **comparer(SP.lire(pid, studio_dir), d, q.get("a"), q.get("b"))}
        if quoi == "garder_profil":                   # le profil d'une piste (réglé à la main) gardé sous un nom
            t = SP.piste(SP.lire(pid, studio_dir), q.get("piste"))
            if not isinstance(t.get("profil"), dict):
                raise Refus("cette piste n'a pas de profil à garder")
            x = garder_profil(q.get("nom") or t["profil"].get("nom"), t["profil"], studio_dir, par)

            def nommer(y):
                SP.piste(y, t["id"])["profil"]["nom"] = x["nom"]
            p = SP.modifier(pid, nommer, None, studio_dir, note=f"profil « {x['nom']} » gardé ({par})")
            return {"ok": True, "profil": x, "profils": lister_profils(studio_dir), "projet": p}
        if quoi == "appliquer_profil":
            x = trouver_profil(q.get("nom"), studio_dir)

            def poser(y):
                appliquer_profil(SP.piste(y, q.get("piste")), x)
                _edition(y)["mix_main"] = True
            p = faire(poser, f"profil « {x['nom']} » posé sur {q.get('piste')} ({par})")
            return {"ok": True, "projet": p}
        if quoi == "retirer_profil":
            def retirer(y):
                SP.piste(y, q.get("piste")).pop("profil", None)
                _edition(y)["mix_main"] = True
            return {"ok": True, "projet": faire(retirer, f"profil retiré de {q.get('piste')} ({par})")}
        if quoi == "regler_profil":
            def regler(y):
                regler_profil_piste(SP.piste(y, q.get("piste")), q.get("reglages") or {})
                _edition(y)["mix_main"] = True
            return {"ok": True, "projet": faire(regler, f"profil de {q.get('piste')} réglé ({par})")}
        if quoi == "apercu":
            pr = q.get("reglages") if isinstance(q.get("reglages"), dict) and q.get("reglages") else (q.get("nom") or None)
            return {"ok": True, "apercu": apercu(pid, q.get("piste"), pr, q.get("debut_s"), q.get("duree_s") or 12.0, studio_dir)}
        return {"ok": False, "erreur": "édition inconnue"}
    except (Refus, studio.Refus) as e:
        return {"ok": False, "erreur": str(e)}
