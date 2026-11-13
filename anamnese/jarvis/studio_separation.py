"""La séparation de qualité du studio multipiste (13/11, Ahmed : « qu'il puisse séparer correctement les voix de l'instru et garder ce
que je lui demande sur l'instru » ; l'instru de « Moujahid 3.2 » tirée le 12/11 « sort mal »).

Avant (studio.extraire_instru, chant.separer_voix) : Demucs htdemucs, un seul passage, deux pistes (la voix, et le reste = mélange − voix).
Ici : 4 ou 6 pistes (htdemucs_ft : un modèle affiné PAR piste ; htdemucs_6s : guitare et piano en plus), le décalage aléatoire moyenné
(shifts), un ensemble de modèles (la moyenne de leurs voix), et l'instru composée de ce que papa garde (« garde la batterie et la
basse, enlève la mélodie ») : tout le non-vocal = mélange − voix (rien de l'instru n'est perdu) ; une partie = la somme des pistes gardées.

Lancé dans le venv de la séparation (torch, demucs, soundfile) :
  .venv-separation/bin/python studio_separation.py separer <entrée> <dossier> [--modeles htdemucs_ft] [--shifts 1] [--format flac]
Rend une ligne JSON : {pistes: {drums: chemin, …}, instru: chemin, modeles, calcul_s}.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

SOURCES_4 = ("drums", "bass", "other", "vocals")
NOMS = {"drums": "batterie", "bass": "basse", "other": "mélodie et autres", "vocals": "voix", "guitar": "guitare", "piano": "piano"}
MODELES = ("htdemucs", "htdemucs_ft", "htdemucs_6s")


def appareil():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def lire(entree, sr=44100):
    """Le son en 44,1 kHz stéréo (n, 2) : soundfile s'il sait, sinon ffmpeg (un MP3)."""
    try:
        import soundfile as sf
        x, s = sf.read(str(entree), dtype="float32", always_2d=True)
        if s == sr:
            return (np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]).astype(np.float32)
    except Exception:                                       # noqa: BLE001 — MP3, autre taux : ffmpeg
        pass
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import studio_mesures as M
    x, _ = M.lire(entree, sr, 2)
    return x.astype(np.float32)


def separer_tableau(x, modele="htdemucs_ft", shifts=1, overlap=0.25, dev=None):
    """(n, 2) à 44,1 kHz → {source: (n, 2)} par un modèle Demucs (la normalisation de la commande demucs : moyenne/écart du mono)."""
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    m = get_model(modele)
    m.eval()
    dev = dev or appareil()
    w = torch.tensor(np.ascontiguousarray(x.T))
    ref = w.mean(0)
    mu, sd = float(ref.mean()), float(ref.std()) or 1.0
    with torch.no_grad():
        out = apply_model(m, ((w - mu) / sd)[None], device=dev, shifts=int(shifts), split=True, overlap=float(overlap),
                          progress=False)[0]
    out = out * sd + mu
    r = {s: out[i].cpu().numpy().T.astype(np.float32) for i, s in enumerate(m.sources)}
    del m, out
    if dev == "mps":
        torch.mps.empty_cache()
    return r


def separer_ensemble(x, modeles=("htdemucs_ft",), shifts=1, overlap=0.25):
    """Plusieurs modèles : chaque piste commune est la moyenne de leurs estimations ; la guitare et le piano (htdemucs_6s) restent à
    part s'il est seul, sinon ils rejoignent « other » (pour moyenner sur les mêmes 4 pistes)."""
    res = [separer_tableau(x, m, shifts, overlap) for m in modeles]
    if len(res) == 1:
        return res[0]
    out = {}
    for s in SOURCES_4:
        l = []
        for r in res:
            if s == "other" and "guitar" in r:
                l.append(r["other"] + r["guitar"] + r["piano"])
            elif s in r:
                l.append(r[s])
        out[s] = np.mean(l, axis=0).astype(np.float32)
    return out


def instru_de(x, pistes, garder=None):
    """L'instru : sans liste (ou toutes les pistes non vocales) = le mélange moins la voix (rien de l'instru perdu, même ce
    qu'aucune piste n'a pris) ; sinon la somme des pistes gardées."""
    non_vocales = [s for s in pistes if s != "vocals"]
    g = [s for s in (garder or non_vocales) if s in pistes and s != "vocals"]
    if set(g) == set(non_vocales):
        return (x - pistes["vocals"]).astype(np.float32)
    if not g:
        return np.zeros_like(x)
    return np.sum([pistes[s] for s in g], axis=0).astype(np.float32)


def porte_voix(x, v, seuil_db=-30.0, seuil_mix_db=None, fenetre_s=0.05, maintien_s=0.25, rampe_s=0.08, sr=44100):
    """La voix estimée, gardée seulement là où quelqu'un chante : ailleurs, ce que le modèle a mis dans « vocals » (le ney, l'oud, une
    flûte, un chœur synthétique) reste dans l'instru. Une fenêtre est « chantée » si la voix y dépasse seuil_db sous son pic (ou,
    avec seuil_mix_db, sous le mélange de cette fenêtre) ; tenue maintien_s (les queues de voix), fondue sur rampe_s."""
    m = np.asarray(v, np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    w = max(1, int(sr * fenetre_s))
    k = len(m) // w
    if k < 4:
        return v
    ev = 10 * np.log10((m[: k * w].reshape(k, w) ** 2).mean(axis=1) + 1e-12)
    if seuil_mix_db is not None:
        xm = np.asarray(x, np.float64)
        xm = xm.mean(axis=1) if xm.ndim == 2 else xm
        ex = 10 * np.log10((xm[: k * w].reshape(k, w) ** 2).mean(axis=1) + 1e-12)
        on = (ev - ex > seuil_mix_db) & (ev > ev.max() - 45)
    else:
        on = ev > ev.max() + seuil_db
    h = max(1, int(round(maintien_s / fenetre_s)))
    on = np.convolve(on.astype(float), np.ones(2 * h + 1), mode="same") > 0          # tenue avant et après
    r = max(1, int(round(rampe_s / fenetre_s)))
    g = np.convolve(on.astype(float), np.hanning(2 * r + 1) / np.hanning(2 * r + 1).sum(), mode="same")
    g = np.clip(g, 0, 1)
    gs = np.interp(np.arange(len(m)), np.arange(k) * w + w / 2, g, left=g[0], right=g[-1])
    return (np.asarray(v) * (gs[:, None] if np.asarray(v).ndim == 2 else gs)).astype(np.float32)


def nettoyer(instru, modele="htdemucs_ft", shifts=1):
    """Un second passage sur l'instru : la voix qui y reste encore est retirée (au prix d'un peu d'artefacts : mesuré)."""
    p = separer_tableau(instru, modele, shifts)
    return (instru - p["vocals"]).astype(np.float32)


def ecrire(chemin, x, sr=44100):
    import soundfile as sf
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".flac":
        sf.write(str(chemin), np.clip(x, -1, 1), sr, subtype="PCM_16", format="FLAC")
    else:
        sf.write(str(chemin), x, sr, subtype="FLOAT")
    return str(chemin)


def separer_fichier(entree, dossier, modeles=("htdemucs_ft",), shifts=1, overlap=0.25, format_="flac", garder=None,
                    second_passage=False, porte=None):
    t0 = time.time()
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    x = lire(entree)
    p = separer_ensemble(x, tuple(modeles), shifts, overlap)
    if porte is not None:                                   # la voix retirée seulement là où elle chante
        p["vocals"] = porte_voix(x, p["vocals"], seuil_db=float(porte))
    ext = "." + format_.lstrip(".")
    pistes = {s: ecrire(dossier / f"{s}{ext}", v) for s, v in p.items()}
    inst = instru_de(x, p, garder)
    if second_passage:
        inst = nettoyer(inst, modeles[0], shifts)
    instru = ecrire(dossier / f"instru{ext}", inst)
    v = p["vocals"]
    return {"pistes": pistes, "instru": instru, "modeles": list(modeles), "shifts": int(shifts), "garder": list(garder or []), "porte": porte,
            "second_passage": bool(second_passage), "duree_s": round(len(x) / 44100, 2), "calcul_s": round(time.time() - t0, 1),
            "voix_db": round(float(10 * np.log10((v.astype(np.float64) ** 2).mean() + 1e-20)), 1)}


if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("action")
    a.add_argument("entree")
    a.add_argument("dossier")
    a.add_argument("--modeles", default="htdemucs_ft")
    a.add_argument("--shifts", type=int, default=1)
    a.add_argument("--overlap", type=float, default=0.25)
    a.add_argument("--format", default="flac")
    a.add_argument("--garder", default="")
    a.add_argument("--second", action="store_true")
    a.add_argument("--porte", type=float, default=None)
    o = a.parse_args()
    if o.action != "separer":
        print("usage : studio_separation.py separer <entrée> <dossier> [--modeles …]", file=sys.stderr)
        sys.exit(2)
    ms = [m for m in o.modeles.split(",") if m in MODELES] or ["htdemucs_ft"]
    r = separer_fichier(o.entree, o.dossier, ms, max(0, min(5, o.shifts)), max(0.0, min(0.9, o.overlap)), o.format,
                        [g for g in o.garder.split(",") if g] or None, o.second, o.porte)
    print(json.dumps(r, ensure_ascii=False))
