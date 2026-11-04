"""(04/11, Ahmed : « il faut aussi que tu sépares bien la voix et la musique de fond, et que les deux, en parallèle, soient transmises
au subconscient, pour qu'il les entende et qu'il puisse les relier à ses sensations et aux mots ; à la fin du processus parallèle,
séparé du son et de la voix, le tout est relié, un peu comme le cortex préfrontal » ; « oui, installe Demucs ») ses deux oreilles :
Demucs (Meta, htdemucs, licence MIT) sépare ce qu'il entend en une VOIX et un FOND, sur le GPU du Mac (0,5 s pour 3 à 8 s de son,
mesuré le 04/11 : la voix d'un mélange passe de −10 dB à +14 dB de SDR, le fond à +24 dB).
Puis, chacun de son côté :
- la voix : présente ou non, chantée (des notes tenues) ou parlée, sa tonalité approximative, son contour (monte, descend) ;
- le fond : son tempo (≥ 3 s de son), sa tonalité par ses accords, ses graves, médiums et aigus.
Rien de l'audio n'est gardé (la voix séparée peut être écrite un instant pour l'oreille, puis effacée par le cockpit).

Un processus qui reste en vie (son propre venv, jarvis/.venv-separation : torch + demucs) : une ligne JSON par demande
{id, fichier, voix_wav?} → {id, voix: {...}, fond: {...}, texte, ms} ou {id, erreur}.
"""
import json
import sys
import time

import numpy as np

KRUMHANSL_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KRUMHANSL_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]


def _tonalite(chroma):
    c = np.asarray(chroma, dtype=float)
    if c.sum() <= 0:
        return None
    meilleur = None
    for r in range(12):
        for profil, mode in ((KRUMHANSL_MAJ, "majeur"), (KRUMHANSL_MIN, "mineur")):
            q = np.roll(profil, r)
            v = np.corrcoef(c, q)[0, 1]
            if meilleur is None or v > meilleur[0]:
                meilleur = (v, r, mode)
    return f"{NOTES[meilleur[1]]} {meilleur[2]}" if meilleur and meilleur[0] > 0.5 else None


def _f0(x, sr, trame=0.04):
    """La hauteur par trame (autocorrélation, 70 à 1 000 Hz) ; 0 sans hauteur nette."""
    n = int(trame * sr)
    out = []
    for i in range(0, len(x) - n, n):
        s = x[i:i + n] - x[i:i + n].mean()
        e = float(np.dot(s, s))
        if e < 1e-6 * n:
            out.append(0.0)
            continue
        ac = np.correlate(s, s, "full")[n - 1:]
        lo, hi = int(sr / 1000), min(len(ac) - 1, int(sr / 70))
        k = lo + int(np.argmax(ac[lo:hi]))
        out.append(sr / k if ac[k] / ac[0] > 0.5 else 0.0)
    return np.array(out), trame


def analyser_voix(voix, sr):
    voix = np.asarray(voix, dtype=np.float32)
    f0, trame = _f0(voix, sr)
    vo = f0[f0 > 0]
    if len(vo) < 10:
        return {"presente": False, "chante": False, "tonalite": None, "contour": None, "part": 0.0}
    midi = np.round(69 + 12 * np.log2(vo / 440)).astype(int)
    chroma = np.bincount(midi % 12, minlength=12)
    # chantée : des notes tenues (la même note sur au moins 0,4 s, deux fois)
    tenues, cur, long_ = 0, None, 0
    for m in np.round(69 + 12 * np.log2(np.where(f0 > 0, f0, 1) / 440)).astype(int) * (f0 > 0):
        if m and m == cur:
            long_ += 1
        else:
            if cur and long_ * trame >= 0.4:
                tenues += 1
            cur, long_ = m, 1
    if cur and long_ * trame >= 0.4:
        tenues += 1
    st = 12 * np.log2(vo / 440)
    tiers = max(1, len(st) // 3)
    d = float(np.median(st[-tiers:]) - np.median(st[:tiers]))
    contour = "monte" if d > 1 else "descend" if d < -1 else "reste stable"
    return {"presente": True, "chante": tenues >= 2, "tonalite": _tonalite(chroma), "contour": contour,
            "part": round(len(vo) / max(1, len(f0)), 2)}


def _spectre(x, sr, n=2048, pas=512):
    x = np.asarray(x, dtype=np.float32)
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    fen = np.hanning(n).astype(np.float32)
    trames = np.lib.stride_tricks.sliding_window_view(x, n)[::pas] * fen
    return np.abs(np.fft.rfft(trames, axis=1)), np.fft.rfftfreq(n, 1 / sr), pas / sr


def analyser_fond(fond, sr):
    S, f, dt = _spectre(fond, sr)
    e = S ** 2
    bandes = [e[:, (f >= a) & (f < b)].sum() for a, b in ((20, 250), (250, 4000), (4000, sr / 2))]
    tot = sum(bandes) or 1.0
    force = lambda v: "forts" if v / tot > 0.45 else "présents" if v / tot > 0.2 else "doux"   # noqa: E731
    # sa tonalité : les hauteurs de 60 à 2 000 Hz rangées en douze classes
    m = (f >= 60) & (f <= 2000)
    classes = (np.round(69 + 12 * np.log2(f[m] / 440)).astype(int)) % 12
    chroma = np.bincount(classes, weights=e[:, m].sum(axis=0), minlength=12)
    # son tempo : les attaques (le flux spectral), leur période (60 à 180 BPM), seulement avec 6 s de son
    bpm = None
    if len(fond) >= 3 * sr:
        flux = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(axis=1)
        c = flux - flux.mean()
        ac = np.correlate(c, c, "full")[len(c) - 1:]
        lo, hi = int(round(60 / 180 / dt)), int(round(60 / 60 / dt))
        if ac[0] > 0 and hi < len(ac):
            k = lo + int(np.argmax(ac[lo:hi]))
            if ac[k] / ac[0] > 0.1:
                a, b, d = ac[k - 1], ac[k], ac[k + 1]
                den = a - 2 * b + d
                fin = k + (0.5 * (a - d) / den if den < 0 else 0)
                bpm = int(round(60 / (fin * dt) / 2) * 2)
    return {"bpm": bpm, "tonalite": _tonalite(chroma),
            "bandes": {"graves": force(bandes[0]), "mediums": force(bandes[1]), "aigus": force(bandes[2])}}


def en_mots(voix, fond):
    v = ("la voix (séparée) " + ("chante" if voix["chante"] else "parle")
         + (f", {voix['tonalite']}" if voix.get("tonalite") else "") + (f", la mélodie {voix['contour']}" if voix.get("contour") else "")
         if voix["presente"] else "pas de voix")
    b = fond["bandes"]
    f = ("le fond (séparé)" + (f" ~{fond['bpm']} BPM" if fond.get("bpm") else "") + (f", {fond['tonalite']}" if fond.get("tonalite") else "")
         + f", graves {b['graves']}, médiums {b['mediums']}, aigus {b['aigus']}")
    return f"{v} · {f}"


def separer(modele, x, appareil, apply_model):
    """(04/11, vu : le téléphone envoie 8 s de sa musique et htdemucs n'en prend que 7,8 d'un seul tenant : « Given length 380607 is
    longer than training length 343980 », à chaque morceau, et rien de séparé du téléphone) découpé par Demucs en segments qui se
    chevauchent : un son court tient dans un seul, un plus long n'est plus refusé."""
    return apply_model(modele, x, device=appareil, split=True, overlap=0.25, progress=False)[0]


def main():
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    appareil = "mps" if torch.backends.mps.is_available() else "cpu"
    modele = get_model("htdemucs").to(appareil).eval()
    print(json.dumps({"pret": True, "appareil": appareil}), flush=True)
    for ligne in sys.stdin:
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        t0 = time.time()
        try:
            x, sr = sf.read(str(d["fichier"]), dtype="float32", always_2d=True)
            x = x.mean(axis=1)
            if sr != modele.samplerate:                              # ré-échantillonné (linéaire : assez pour séparer)
                n = int(len(x) * modele.samplerate / sr)
                x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
                sr = modele.samplerate
            with torch.no_grad():
                s = separer(modele, torch.tensor(np.stack([x, x]))[None], appareil, apply_model)
            noms = modele.sources
            voix = s[noms.index("vocals")].mean(0).cpu().numpy()
            fond = sum(s[i] for i, n in enumerate(noms) if n != "vocals").mean(0).cpu().numpy()
            av, af = analyser_voix(voix[::2], sr // 2), analyser_fond(fond, sr)
            sortie = {"voix": av, "fond": af, "texte": en_mots(av, af)}
            if d.get("voix_wav") and av["presente"]:                 # la voix seule, un instant, pour l'oreille (les mots)
                sf.write(str(d["voix_wav"]), voix, sr)
                sortie["voix_wav"] = str(d["voix_wav"])
            sortie["ms"] = int((time.time() - t0) * 1000)
        except Exception as e:  # noqa: BLE001  (une demande ratée ne tue pas ses oreilles)
            sortie = {"erreur": str(e)[:200]}
        print(json.dumps({"id": d.get("id"), **sortie}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
