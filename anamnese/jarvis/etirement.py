"""Changer le DÉBIT d'une voix sans toucher à sa hauteur ni à son timbre (26/10, Ahmed : « fatigué, il sonne comme un ogre ;
excité, comme un hurluberlu : garde SA voix, marque l'état seulement par le rythme »). La page jouait l'audio plus vite ou
plus lentement, comme une bande : la hauteur et les formants suivaient. Ici, un étirement temporel WSOLA (des fenêtres de
30 ms recollées là où elles se ressemblent le plus) : la durée change, la hauteur reste."""
import numpy as np


def etirer(x, tempo, sr=24000):
    """L'audio x (float32) joué à tempo × la vitesse (tempo > 1 : plus rapide), à hauteur constante."""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if abs(tempo - 1.0) < 0.01 or len(x) < sr // 10:
        return x
    n, tol = int(0.030 * sr), int(0.008 * sr)
    hs = n // 2
    ha = hs * float(tempo)
    w = np.hanning(n).astype(np.float32)
    xp = np.concatenate([np.zeros(tol, np.float32), x, np.zeros(3 * n + 2 * tol, np.float32)])
    sortie = int(len(x) / tempo)
    y = np.zeros(sortie + 2 * n, np.float32)
    poids = np.zeros_like(y)
    prec, k = tol, 0
    while True:
        o = k * hs
        centre = int(round(tol + k * ha))
        if o + n > len(y) or centre + n + tol >= len(xp):
            break
        if k == 0:
            choix = centre
        else:
            naturel = xp[prec + hs: prec + hs + n]
            zone = xp[centre - tol: centre + tol + n]
            choix = centre - tol + int(np.argmax(np.correlate(zone, naturel, mode="valid")))
        y[o: o + n] += xp[choix: choix + n] * w
        poids[o: o + n] += w
        prec, k = choix, k + 1
    poids[poids < 1e-3] = 1.0
    return (y / poids)[:sortie]
