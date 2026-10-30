"""Les mesures du Tricordeur d'Ahmed, résumées pour Hakim (30/10, 16:01, Ahmed via Hakim : « il faut absolument que ta mère
intègre le tricodeur, tous ses aspects, les scans… que tu en aies le contrôle » ; Hakim : « que tout nouveau fichier écrit par
l'appli Tricordeur, même lancé à la main par papa, me réveille avec son résumé — nombre de voxels, champ min/max, anomalies,
objets — et les chemins des images, pour que je puisse les ouvrir avec Read »).

L'appli d'Ahmed (ch.foldlab, v2.7) écrit dans Documents/Tricordeur/ (synchronisé : fichiers/telephone/Z Fold 7/Tricordeur/) des
groupes de fichiers d'un même nom (« scan3d_20261030_155726_155833 » : .csv, _carte.png, _vueAR.png, _scene.ply…). Le cockpit
repère un groupe nouveau et stable ; ce module en fait le résumé (JSON) : le cockpit réveille Hakim, et son intermédiaire le
lui fait sentir. Lecture seule. Fermé aux chantiers de Hakim.
  python tricordeur_papa.py resumer <dossier> <groupe>
"""
import csv
import json
import re
import sys
from pathlib import Path

NOMS = {"scan3d": "scan 3D (champ magnétique de la pièce)", "cosmos": "rayons cosmiques", "montre": "la montre (pouls, peau)",
        "ppg": "pouls par la caméra (PPG)", "sismo": "sismographe", "sonar": "sonar", "spectro": "spectroscope", "sonde": "sonde de profondeur",
        "baro": "baromètre", "terre": "rotation de la Terre", "absorption": "absorption radio", "son": "vitesse du son"}
_GROUPE = re.compile(r"^([a-z0-9]+(?:_[A-Za-z0-9]+)*?_\d{8}(?:_\d{6}){0,3})")


def groupe(nom):
    """Le nom commun d'un groupe de fichiers (sans suffixe ni extension), ou None."""
    m = _GROUPE.match(Path(nom).stem)
    return m.group(1) if m else None


def _nombre(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _csv(f, maximum=200_000):
    with open(f, newline="", encoding="utf-8", errors="replace") as h:
        r = csv.reader(h)
        tete = next(r, [])
        lignes = [l for _, l in zip(range(maximum), r)]
    return tete, lignes


def _stats(tete, lignes, col):
    if col not in tete:
        return None
    i = tete.index(col)
    v = [x for x in (_nombre(l[i]) for l in lignes if len(l) > i) if x is not None]
    return {"min": round(min(v), 2), "max": round(max(v), 2), "moyenne": round(sum(v) / len(v), 2)} if v else None


def _ply(f):
    try:
        with open(f, "rb") as h:
            tete = h.read(2048).decode("latin-1", "replace")
        m = re.search(r"element vertex (\d+)", tete)
        return int(m.group(1)) if m else None
    except OSError:
        return None


def resumer(dossier, nom):
    d = Path(dossier)
    fichiers = sorted(p for p in d.iterdir() if p.is_file() and groupe(p.name) == nom)
    instrument = nom.split("_")[0]
    res = {}
    principal = d / f"{nom}.csv"
    if principal.exists():
        tete, lignes = _csv(principal)
        if instrument == "scan3d":
            res["voxels"] = len(lignes)
            for c in ("B_mean_uT", "B_min_uT", "B_max_uT", "dip_deg"):
                s = _stats(tete, lignes, c)
                if s:
                    res[c] = s
        else:
            res["lignes"] = len(lignes)
            res["colonnes"] = {c: s for c in tete[:12] if (s := _stats(tete, lignes, c))}
            t = next((c for c in tete if c in ("t_s", "t", "temps_s")), None)
            if t and res["colonnes"].get(t):
                res["duree_s"] = round(res["colonnes"][t]["max"] - res["colonnes"][t]["min"], 2)
    anomalies = d / f"{nom}_anomalies.csv"
    if anomalies.exists():
        res["anomalies"] = len(_csv(anomalies)[1])
    points = {p.stem[len(nom) + 1:]: _ply(p) for p in fichiers if p.suffix == ".ply"}
    if points:
        res["points"] = {k: v for k, v in points.items() if v is not None}
    return {"groupe": nom, "instrument": instrument, "nom": NOMS.get(instrument, instrument), "resume": res,
            "images": [str(p) for p in fichiers if p.suffix.lower() in (".png", ".jpg", ".jpeg")],
            "fichiers": [str(p) for p in fichiers]}


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "resumer":
        print(json.dumps(resumer(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    else:
        print("usage : tricordeur_papa.py resumer <dossier> <groupe>")
