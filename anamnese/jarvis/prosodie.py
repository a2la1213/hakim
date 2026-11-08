"""La prosodie d'Ahmed mot par mot, pour le [Présent vécu] (demande d'Ahmed relayée par Hakim, 2026-10-20 : « les mots
où sa voix monte nettement ou qu'il appuie, et le contour de fin de phrase ») — des INDICES, jamais des émotions.

- La hauteur (F0, autocorrélation sur des trames de 40 ms, pas de 10 ms) et l'énergie, calculées sur l'audio déjà
  reçu pour la transcription : rien de plus à enregistrer, aucun modèle.
- Les mots : Whisper donne le temps de chaque SEGMENT ; demander le temps de chaque mot coûte environ une seconde de
  plus par transcription (mesuré le 2026-10-20 : 1,1 s → 2,0 s pour 1,5 s d'audio), trop pour la conversation.
  Chaque segment est donc partagé entre ses mots au prorata de leur longueur, sur ses seules trames de voix :
  un mot repéré « appuyé » est approché (un mot voisin, parfois), d'où « vers » dans le texte rendu.
- Le contour de fin (montant, descendant, plat) ne dépend pas des mots : les dernières 600 ms de voix.
"""
import re

import numpy as np

TAUX = 16000
TRAME, PAS = 640, 160                       # 40 ms, 10 ms
F0_MIN, F0_MAX = 70.0, 400.0
VIDES = set("alors aussi avec avoir bien cette comme dans donc elle elles encore être fait faire leur mais même nous "
            "parce pour quand quel quelle quoi sans sous tout tous très vous était ceci cela juste plus moins peut "
            "les des une est sont ont que qui pas sur ses son sa mon ma mes ton ta tes nos vos aux par".split())


def trames(audio):
    """(f0 en Hz ou nan, énergie en dB) par trame de 10 ms."""
    a = np.asarray(audio, dtype=np.float32)
    n = max(0, 1 + (len(a) - TRAME) // PAS)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    idx = np.arange(TRAME)[None, :] + PAS * np.arange(n)[:, None]
    fr = a[idx] * np.hanning(TRAME)[None, :]
    db = 10 * np.log10(np.mean(fr ** 2, axis=1) + 1e-10)
    spec = np.fft.rfft(fr, n=2 * TRAME)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:, :TRAME]
    lo, hi = int(TAUX / F0_MAX), int(TAUX / F0_MIN)
    seg = ac[:, lo:hi] / (ac[:, :1] + 1e-10)
    k = np.argmax(seg, axis=1)
    pic = seg[np.arange(n), k]
    f0 = TAUX / (k + lo)
    voix = (pic > 0.45) & (db > db.max() - 35)
    return np.where(voix, f0, np.nan), db


def mots_par_prorata(segments, f0):
    """[(mot, début s, fin s)] : chaque segment partagé entre ses mots au prorata de leur longueur, sur ses trames de voix."""
    out = []
    for sg in segments:
        mots = re.findall(r"[\w'’-]+", str(sg.get("text") or ""))
        if not mots:
            continue
        d, f = float(sg.get("start", 0)), float(sg.get("end", 0))
        i0, i1 = int(d * 100), max(int(d * 100) + 1, int(f * 100))
        voixs = [i for i in range(i0, min(i1, len(f0))) if not np.isnan(f0[i])]
        if len(voixs) < len(mots):
            voixs = list(range(i0, min(i1, len(f0))))
        if not voixs:
            continue
        poids = np.array([len(m) + 1 for m in mots], dtype=float)
        bornes = np.round(np.cumsum(np.r_[0, poids]) / poids.sum() * len(voixs)).astype(int)
        for m, a, b in zip(mots, bornes[:-1], bornes[1:]):
            if b > a:
                out.append((m, voixs[a] / 100, voixs[b - 1] / 100 + 0.01))
    return out


def analyser(audio, segments, mots=None):
    """{"appuyes": [mots], "fin": "montante" | "descendante" | "plate" | None, "approche": bool} ; None sans voix.
    mots : [(mot, début, fin)] exacts s'ils sont connus (horodatage de Whisper) ; sinon le prorata."""
    f0, db = trames(audio)
    if not len(f0) or np.all(np.isnan(f0)):
        return None
    approche = mots is None
    mots = mots if mots is not None else mots_par_prorata(segments, f0)
    mesures = []
    for m, a, b in mots:
        i, j = int(a * 100), max(int(a * 100) + 1, int(b * 100))
        h = f0[i:j]
        h = h[~np.isnan(h)]
        if len(h) >= 3:
            mesures.append((m, (a + b) / 2, float(np.median(h)), float(np.max(db[i:j]))))
    appuyes = []
    if len(mesures) >= 3:
        # la voix descend naturellement au fil d'une phrase (déclinaison) : un mot « monte » par rapport à la droite
        # de sa phrase, pas par rapport à sa moyenne (sinon le premier mot sortirait toujours)
        t = np.array([x[1] for x in mesures])
        lf = np.log([x[2] for x in mesures])
        pente, origine = np.polyfit(t, lf, 1) if np.ptp(t) > 0 else (0.0, float(np.mean(lf)))
        ref_db = float(np.median([x[3] for x in mesures]))
        notes = []
        for (m, tc, h, e), l in zip(mesures, lf):
            if len(m) < 3 or m.lower() in VIDES:
                continue
            s = max((l - (pente * tc + origine)) / np.log(1.12), (e - ref_db) / 6.0)
            if s >= 1.0:
                notes.append((s, m))
        appuyes = [m for _s, m in sorted(notes, reverse=True)[:3]]
    voixs = np.where(~np.isnan(f0))[0]
    fin = None
    if len(voixs) >= 20:
        # le contour de fin : les 150 dernières ms de voix contre les 450 qui les précèdent (une question monte
        # souvent sur la toute fin)
        dernier = voixs[-1]
        bout = voixs[voixs > dernier - 15]
        avant = voixs[(voixs <= dernier - 15) & (voixs > dernier - 60)]
        if len(bout) >= 5 and len(avant) >= 10:
            r = np.median(f0[bout]) / np.median(f0[avant]) - 1
            fin = "montante" if r > 0.10 else "descendante" if r < -0.10 else "plate"
    if not appuyes and fin is None:
        return None
    return {"appuyes": appuyes, "fin": fin, "approche": approche}


def texte(p):
    """« appuyé vers : génial, maths ; fin montante » (indices), ou ''."""
    if not p:
        return ""
    r = []
    if p.get("appuyes"):
        r.append(("appuyé vers : " if p.get("approche") else "appuyé : ") + ", ".join(p["appuyes"]))
    if p.get("fin"):
        r.append(f"fin {p['fin']}")
    return " ; ".join(r)
