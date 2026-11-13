"""La chaîne « studio pro » de chaque voix (13/11, 18:40, Ahmed : « est-ce que Hakim peut faire un mix et master pro pour chaque voix,
avec tous les nettoyages et les modifs […] pour que ça fasse effet studio pro ? »).

LE PRINCIPE : on MESURE d'abord (diagnostic), on ne corrige que ce que la mesure justifie. Une voix déjà propre ressort inchangée,
échantillon pour échantillon, des étapes qui ne la concernent pas. Chaque étape a trois modes : « auto » (la mesure décide), « oui »
(forcée), « non » (coupée), et ses réglages.

LES ÉTAPES, dans l'ordre d'un atelier de restauration :
  continu       le décalage continu (DC), retiré s'il dépasse −60 dBFS ;
  ecretage      les crêtes écrêtées (plateaux d'au moins 3 échantillons au maximum), reconstruites par adeclip (modèle AR), seulement
                autour des plateaux trouvés ;
  clics         les clics de bouche (bouffées de moins de 2 ms, 18 dB au-dessus de leur voisinage dans les aigus), réparés par adeclick,
                seulement autour des clics trouvés ;
  ronflement    le 50 Hz (ou 60 Hz) et ses harmoniques, s'ils dépassent leurs voisins de 10 dB dans les silences : chaque harmonique
                estimée (amplitude, phase) par blocs d'une seconde et SOUSTRAITE (pas un filtre coupe-bande : la voix autour reste) ;
  souffle       le souffle et le bruit de fond, avec un PROFIL APPRIS sur les silences de la prise ; le débruiteur est choisi au banc
                (studio_pro_banc.py : afftdn à profil appris, Wiener à profil appris, DeepFilterNet 3) ;
  plosives      les « p » et les « b » : les bouffées de grave (sous 100 Hz) soudaines, adoucies par un coupe-bas à phase nulle de
                150 Hz, seulement pendant la bouffée (fondus de 10 ms) ;
  respirations  les respirations (souffle non voisé, plus de 150 ms, à côté d'un silence, sans sifflante) BAISSÉES de 8 dB (réglable),
                jamais supprimées ;
  porte         un expandeur doux entre les phrases (ratio 2, au plus −12 dB), seuil mesuré sur le bruit de fond, seulement si le
                fond reste audible (au-dessus de −75 dBFS) ;
  nivellement   le « vocal rider » : le niveau de la voix ramené vers sa médiane, phrase par phrase (au plus ±6 dB, lissé sur 300 ms),
                AVANT la compression, seulement si son niveau varie de plus de 3 dB.
Le calage des doubles et des backs (sur la voix principale, phrase par phrase, et sur la grille s'il y a un tempo) : caler_phrases.

Chaque étape se COUPE pour les témoins (COUPE, ou la variable STUDIO_PRO_COUPE) : son test doit alors échouer.
Numpy et ffmpeg seulement (ce module sert dans le venv d'Anamnèse, celui du chant et celui de la page).
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
FFMPEG = os.environ.get("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg")
SR = 44100
VERSION = 1                                   # le cache des voix nettoyées change avec elle
COUPE = frozenset(x for x in os.environ.get("STUDIO_PRO_COUPE", "").split(",") if x)
ETAPES = ("continu", "ecretage", "clics", "ronflement", "souffle", "plosives", "respirations", "porte", "nivellement")
MODES = ("auto", "oui", "non")
TYPES_VOIX = ("principale", "double", "back", "adlib")
DEBRUITEURS = ("auto", "afftdn", "wiener", "deepfilternet")
# le débruiteur gardé quand « auto » : celui qui a GAGNÉ au banc du 13/11 (studio_pro_banc.py, bruit rose à 30/20/10 dB sous la voix,
# SI-SDR gagné) : Wiener à profil appris +4,1/+4,9/+6,1 dB sur une voix CHANTÉE de Hakim, +4,0/+4,6/+5,6 sur le rap de papa ;
# afftdn à profil appris +0,4 à +0,7 ; DeepFilterNet 3 (appris sur de la parole) détruit le chant (−22 dB à 30 dB de rapport) et
# abîme le rap (−14 dB à 30 dB) : il reste au choix (« deepfilternet », son venv à part), jamais par défaut
DEBRUITEUR_PAR_DEFAUT = "wiener"
PYTHON_DFN = Path(os.environ.get("JARVIS_PYTHON_DEBRUITAGE", ICI / ".venv-debruitage" / "bin" / "python"))


def reglages_defaut():
    """Les réglages pro d'une voix : chaque étape en « auto », et ses réglages."""
    return {"actif": True, "type": "principale",
            **{e: "auto" for e in ETAPES},
            "debruiteur": "auto", "souffle_db": 18.0, "respirations_db": -8.0, "porte_plage_db": -12.0, "nivellement_db": 6.0,
            "plosives_hz": 150.0, "calage": "auto", "delai_jete": "auto"}


def borner(r, base=None):
    """Des réglages pro (dict) bornés ; les clés inconnues ignorées. base : les réglages d'avant (sinon les défauts)."""
    out = dict(base or reglages_defaut())
    r = dict(r or {})
    if "actif" in r:
        v = r["actif"]
        out["actif"] = v.lower() in ("1", "oui", "vrai", "true", "on") if isinstance(v, str) else bool(v)
    if r.get("type") in TYPES_VOIX:
        out["type"] = r["type"]
    for e in (*ETAPES, "calage", "delai_jete"):
        if e in r:
            v = r[e]
            v = {True: "oui", False: "non"}.get(v, v) if isinstance(v, bool) else str(v).strip().lower()
            v = {"on": "oui", "off": "non", "1": "oui", "0": "non", "vrai": "oui", "faux": "non", "aucun": "non"}.get(v, v)
            if v in MODES:
                out[e] = v
    if r.get("debruiteur") in DEBRUITEURS:
        out["debruiteur"] = r["debruiteur"]
    for k, (a, b) in {"souffle_db": (3, 40), "respirations_db": (-30, 0), "porte_plage_db": (-30, 0), "nivellement_db": (1, 12),
                      "plosives_hz": (80, 300)}.items():
        if k in r:
            try:
                x = float(r[k])
                if not (math.isnan(x) or math.isinf(x)):
                    out[k] = round(max(a, min(b, x)), 1)
            except (TypeError, ValueError):
                pass
    return out


# ------------------------------------------------------------------------------------------------ outils
def _mono(x):
    x = np.asarray(x, np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


def _2d(x):
    x = np.asarray(x, np.float64)
    return x[:, None] if x.ndim == 1 else x


def _ff(x, af, sr=SR, timeout=1800):
    """Un filtre ffmpeg sur un tableau (n, canaux) : même longueur rendue (complétée ou coupée)."""
    x = _2d(x)
    ch = x.shape[1]
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "f32le", "-ar", str(sr), "-ac", str(ch), "-i", "-",
                        "-af", af, "-f", "f32le", "-ar", str(sr), "-ac", str(ch), "-"],
                       input=np.ascontiguousarray(x, np.float32).tobytes(), capture_output=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg ({af[:60]}) : {r.stderr.decode(errors='ignore')[-300:]}")
    y = np.frombuffer(r.stdout, np.float32).astype(np.float64).reshape(-1, ch)
    if len(y) < len(x):
        y = np.vstack([y, np.zeros((len(x) - len(y), ch))])
    return y[: len(x)]


def niveaux_db(m, sr=SR, fenetre_s=0.02, pas_s=0.01):
    """Le niveau efficace (dBFS) par trames (fenêtre, pas) d'un son mono."""
    n, p = int(sr * fenetre_s), int(sr * pas_s)
    if len(m) < n:
        return np.array([-120.0])
    k = 1 + (len(m) - n) // p
    c = np.concatenate([[0.0], np.cumsum(np.asarray(m, np.float64) ** 2)])
    i = np.arange(k) * p
    e = (c[i + n] - c[i]) / n
    return 10 * np.log10(np.maximum(e, 1e-12))


def fond_et_voix(m, sr=SR):
    """(le bruit de fond, le niveau haut de la voix) en dBFS : 3e et 95e centiles des trames de 20 ms. (Le banc du 13/11 : une voix
    de rap ou un refrain chanté couvrent 90 % du temps ; le 10e centile tombait dans la voix, à −34 dBFS.)"""
    l = niveaux_db(m, sr)
    vivant = l[l > -115]
    if len(vivant) < 10:
        return -120.0, float(l.max())
    return float(np.percentile(vivant, 3)), float(np.percentile(vivant, 95))


def bruit_des_silences(m, sr=SR):
    """Ce qu'il y a dans les silences : leur durée, et leur voisement moyen. Un vrai fond (souffle, pièce) n'est pas voisé ; une
    queue de réverbération, une voix douce ou une fuite d'instrument le sont (on ne les « débruite » pas : ce serait abîmer)."""
    sil = silences(m, sr)
    duree = sum(b - a for a, b in sil) / sr
    if duree < 0.25:
        return {"silences_s": round(duree, 2), "voisement": None, "bruit": False}
    v = _voisement(m, sr)
    p = int(sr * 0.01)
    sel = np.zeros(len(v), bool)
    for a, b in sil:
        sel[a // p: max(a // p + 1, b // p - 3)] = True
    vm = float(v[sel].mean()) if sel.any() else 1.0
    return {"silences_s": round(duree, 2), "voisement": round(vm, 2), "bruit": vm < 0.45}


def silences(m, sr=SR, au_dessus_db=6.0, min_s=0.12):
    """Les silences de la prise (ni voix ni respiration : à moins de 6 dB du fond), en échantillons [(a, b)], du plus long au plus court."""
    l = niveaux_db(m, sr)
    fond, voix = fond_et_voix(m, sr)
    calme = l < fond + au_dessus_db
    out, debut = [], None
    p = int(sr * 0.01)
    for i, v in enumerate(list(calme) + [False]):
        if v and debut is None:
            debut = i
        elif not v and debut is not None:
            if (i - debut) * 0.01 >= min_s:
                out.append((debut * p, min(len(m), i * p + int(sr * 0.01))))
            debut = None
    return sorted(out, key=lambda ab: ab[0] - ab[1])


def _filtre_fft(m, sr, gain_de_f):
    """Un filtre à phase nulle (FFT du signal entier) : gain_de_f(fréquences) → gains."""
    n = len(m)
    N = 1 << int(math.ceil(math.log2(max(2, n))))
    X = np.fft.rfft(m, N)
    f = np.fft.rfftfreq(N, 1 / sr)
    return np.fft.irfft(X * gain_de_f(f), N)[:n]


def _butter_mag(f, fc, ordre, haut=True):
    r = (np.maximum(f, 1e-9) / fc) if not haut else (fc / np.maximum(f, 1e-9))
    return 1.0 / np.sqrt(1.0 + r ** (2 * ordre))


def _masque_evenements(n, evts, sr, avant_ms, apres_ms, fondu_ms):
    """Un masque (n,) à 1 autour des événements [(a, b)] (échantillons), 0 ailleurs, avec des fondus en cosinus."""
    g = np.zeros(n)
    fa = max(1, int(sr * fondu_ms / 1000))
    rampe = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fa))
    for a, b in evts:
        a = max(0, a - int(sr * avant_ms / 1000))
        b = min(n, b + int(sr * apres_ms / 1000))
        g[a:b] = 1.0
        a0 = max(0, a - fa)
        g[a0:a] = np.maximum(g[a0:a], rampe[fa - (a - a0):])
        b1 = min(n, b + fa)
        g[b:b1] = np.maximum(g[b:b1], rampe[::-1][: b1 - b])
    return g


def _runs(bool_arr):
    """Les plages (début, fin exclue) où un tableau booléen est vrai."""
    b = np.concatenate([[False], np.asarray(bool_arr, bool), [False]])
    d = np.flatnonzero(np.diff(b.astype(np.int8)))
    return list(zip(d[0::2], d[1::2]))


# ------------------------------------------------------------------------------------------------ les mesures
def si_sdr(reference, estimee):
    """Le SI-SDR (dB) d'une estimée contre la vérité (mono, même longueur) : 10·log10(‖αs‖² / ‖αs − ŝ‖²), α = ⟨ŝ, s⟩ / ‖s‖²."""
    s, e = _mono(reference), _mono(estimee)
    n = min(len(s), len(e))
    s, e = s[:n], e[:n]
    a = float(np.dot(e, s) / (np.dot(s, s) + 1e-20))
    cible = a * s
    err = cible - e
    return round(10 * math.log10(max(1e-20, float(np.dot(cible, cible))) / max(1e-20, float(np.dot(err, err)))), 2)


def decalage_echantillons(a, b, max_n=2000):
    """Le retard de b sur a (échantillons), par intercorrélation (FFT) : pour vérifier qu'une étape n'ajoute aucune latence."""
    a, b = _mono(a), _mono(b)
    n = min(len(a), len(b))
    N = 1 << int(math.ceil(math.log2(2 * n)))
    c = np.fft.irfft(np.fft.rfft(b[:n], N) * np.conj(np.fft.rfft(a[:n], N)), N)
    lags = np.concatenate([np.arange(0, max_n + 1), np.arange(-max_n, 0)])
    v = np.concatenate([c[: max_n + 1], c[-max_n:]])
    return int(lags[int(np.argmax(v))])


# ------------------------------------------------------------------------------------------------ 1. le décalage continu
def mesure_continu(x):
    x = _2d(x)
    moy = x.mean(axis=0)
    pire = float(np.abs(moy).max())
    return {"dbfs": round(20 * math.log10(max(pire, 1e-12)), 1), "present": pire > 10 ** (-60 / 20)}


def retirer_continu(x):
    x = _2d(x)
    return x - x.mean(axis=0)


# ------------------------------------------------------------------------------------------------ 2. l'écrêtage
def mesure_ecretage(x, sr=SR):
    """Les plateaux écrêtés : au moins 3 échantillons de suite à ≥ 99,5 % du maximum du canal, de même signe."""
    x = _2d(x)
    plateaux = []
    for c in range(x.shape[1]):
        v = x[:, c]
        pic = float(np.abs(v).max())
        if pic < 1e-4:
            continue
        for signe in (1, -1):
            haut = (signe * v) >= 0.995 * pic
            for a, b in _runs(haut):
                if b - a >= 3:
                    plateaux.append((int(a), int(b)))
    plateaux.sort()
    n = sum(b - a for a, b in plateaux)
    return {"plateaux": len(plateaux), "echantillons": int(n), "present": len(plateaux) >= 3, "_plateaux": plateaux}


def reparer_ecretage(x, mes, sr=SR):
    """adeclip (modèle AR), gardé seulement autour des plateaux (±5 ms) : le reste de la prise ne bouge pas."""
    x = _2d(x)
    y = _ff(x, "adeclip=w=55:o=75:a=8:t=10:n=1000", sr)
    g = _masque_evenements(len(x), mes["_plateaux"], sr, 5, 5, 3)[:, None]
    return x + g * (y - x)


# ------------------------------------------------------------------------------------------------ 3. les clics de bouche
def mesure_clics(x, sr=SR, seuil_db=20.0, max_ms=2.0):
    """Les clics : dans les aigus (> 3 kHz), une bouffée de 0,5 à 2 ms ISOLÉE, au moins 20 dB au-dessus du plus fort de ses voisins
    (de 2 à 20 ms avant ET après). Les impulsions de la glotte reviennent à chaque période (≤ 12 ms) : leurs voisines les égalent ;
    une consonne dure plus de 2 ms ; un clic, lui, est seul. (Le banc du 13/11 : à 6 dB, 48 « clics » dans 100 s d'une voix de Hakim
    sans clic ajouté, jusqu'à 19 dB ; les clics ajoutés entre les phrases dépassent 27 dB. Un clic noyé dans le chant n'est pas vu.)"""
    m = _mono(x)
    h = _filtre_fft(m, sr, lambda f: _butter_mag(f, 3000.0, 4, True))
    p = max(1, int(sr * 0.0005))                         # trames de 0,5 ms
    k = len(h) // p
    if k < 100:
        return {"clics": 0, "present": False, "_clics": []}
    e = 10 * np.log10(np.maximum((h[: k * p].reshape(k, p) ** 2).mean(axis=1), 1e-14))
    garde, loin = 4, 40                                  # 2 ms de garde, 20 ms de voisinage
    ep = np.pad(e, (loin, loin), mode="edge")
    mx = np.lib.stride_tricks.sliding_window_view(ep, loin - garde).max(axis=1)   # mx[j] = max(ep[j : j + loin - garde])
    avant = mx[:k]                                       # e[i − loin … i − garde − 1]
    apres = mx[loin + garde + 1: loin + garde + 1 + k]   # e[i + garde + 1 … i + loin]
    if len(apres) < k:
        apres = np.pad(apres, (0, k - len(apres)), mode="edge")
    med = np.maximum(avant, apres)
    if "clics_isoles" in COUPE:                          # témoin : la médiane du voisinage (les impulsions de la glotte passent pour des clics)
        med = np.median(np.lib.stride_tricks.sliding_window_view(ep, 2 * loin + 1), axis=1)[:k]
    fond, _ = fond_et_voix(m, sr)
    haut = (e > med + seuil_db) & (e > fond + 15)
    clics = []
    for a, b in _runs(haut):
        if (b - a) * 0.5 <= max_ms:
            clics.append((int(a * p), int(b * p)))
    return {"clics": len(clics), "present": len(clics) >= 1, "_clics": clics}


def reparer_clics(x, mes, sr=SR):
    """adeclick (modèle AR) en deux forces : franc (seuil 2) autour des clics trouvés (±3 ms), doux (seuil 8) partout ailleurs, pour
    les clics noyés dans le chant que la mesure ne voit pas. (Le banc du 13/11 : le seuil 2 partout abîme une voix propre — SI-SDR
    22 à 29 dB — ; le seuil 8 partout la laisse à 44-59 dB et retire 5 à 6 dB des clics noyés.) Une prise sans clic trouvé n'est pas
    touchée du tout (l'étape ne s'active pas)."""
    x = _2d(x)
    y = _ff(x, "adeclick=w=55:o=75:a=2:t=2:b=2", sr)
    g = _masque_evenements(len(x), mes["_clics"], sr, 3, 3, 1)[:, None]
    if "clics_noyes" in COUPE:
        return x + g * (y - x)
    doux = _ff(x, "adeclick=w=55:o=75:a=2:t=8:b=2", sr)
    return x + g * (y - x) + (1 - g) * (doux - x)


# ------------------------------------------------------------------------------------------------ 4. le ronflement (50/60 Hz)
def _spectre_long(m, sr, n=1 << 17):
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    pas = n // 2
    k = 1 + (len(m) - n) // pas
    w = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    for i in range(k):
        acc += np.abs(np.fft.rfft(m[i * pas: i * pas + n] * w)) ** 2
    return np.fft.rfftfreq(n, 1 / sr), acc / k


def mesure_ronflement(x, sr=SR):
    """Le 50 Hz (ou 60 Hz) et ses harmoniques, mesurés dans les SILENCES (la voix n'y masque rien ; à défaut, la prise entière) :
    la saillance de chaque harmonique (sa crête à ±1,5 Hz contre la médiane de ses voisines à 4-12 Hz). Présent si au moins deux des
    quatre premières dépassent 10 dB. f0 affinée sur l'harmonique la plus nette."""
    m = _mono(x)
    sil = silences(m, sr)
    calme = np.concatenate([m[a:b] for a, b in sil]) if sum(b - a for a, b in sil) > sr * 1.5 else m
    f, P = _spectre_long(calme, sr)
    df = f[1]
    meilleur = None
    for base in (50.0, 60.0):
        sal = []
        for k in range(1, 13):
            c = base * k
            pic = (f > c - 1.5) & (f < c + 1.5)
            vois = ((f > c - 12) & (f < c - 4)) | ((f > c + 4) & (f < c + 12))
            if not pic.any() or not vois.any():
                sal.append((k, 0.0, c))
                continue
            i = np.flatnonzero(pic)[int(np.argmax(P[pic]))]
            s = 10 * math.log10(P[i] / (np.median(P[vois]) + 1e-30) + 1e-30)
            fi = f[i]
            if 0 < i < len(P) - 1:                         # interpolation parabolique (en dB)
                a1, b1, c1 = (10 * math.log10(P[j] + 1e-30) for j in (i - 1, i, i + 1))
                d = a1 - 2 * b1 + c1
                fi = f[i] + (0.5 * (a1 - c1) / d * df if d else 0)
            sal.append((k, s, fi))
        n_nets = sum(1 for k, s, _ in sal[:4] if s >= 10)
        score = sum(max(0.0, s) for _, s, _ in sal[:4])
        if meilleur is None or score > meilleur[0]:
            meilleur = (score, base, sal, n_nets)
    score, base, sal, n_nets = meilleur
    k0, s0, f0k = max(sal[:6], key=lambda t: t[1])
    f0 = f0k / k0 if s0 >= 10 else base
    harm = [k for k, s, _ in sal if s >= 6]
    return {"hz": base, "f0": round(float(f0), 3), "saillance_db": [round(s, 1) for _, s, _ in sal[:6]], "harmoniques": harm,
            "present": n_nets >= 2}


def _phase_secteur(m, sr, f0, kr, bloc_s=1.0):
    """La phase du secteur au fil du temps : la fréquence du réseau dérive (±0,05 Hz), et une harmonique 9 décroche alors de presque
    un demi-tour par seconde. La phase de l'harmonique la plus nette (kr), mesurée par blocs, déroulée, donne la fréquence de chaque
    bloc ; sa somme donne φ(t), et chaque harmonique k suit k·φ(t)."""
    n = int(sr * bloc_s)
    pas = n // 2
    N = len(m)
    t = np.arange(N) / sr
    w = np.hanning(n)
    centres, th, poids = [], [], []
    ref = np.exp(-2j * np.pi * kr * f0 * t)
    for d in range(0, max(1, N - n + 1), pas):
        c = np.dot(w * m[d:d + n], ref[d:d + n])
        centres.append((d + n / 2) / sr)
        th.append(np.angle(c))
        poids.append(abs(c))
    if len(th) < 3:
        return 2 * np.pi * f0 * t
    th = np.unwrap(np.array(th))
    dt = np.diff(centres)
    df = np.diff(th) / (2 * np.pi * kr * dt)            # l'écart de fréquence entre deux blocs (Hz)
    if len(df) >= 5:                                     # une médiane glissante : un bloc où la voix domine ne fait pas dériver
        dp = np.pad(df, (2, 2), mode="edge")
        df = np.median(np.lib.stride_tricks.sliding_window_view(dp, 5), axis=1)
    mil = (np.array(centres[:-1]) + np.array(centres[1:])) / 2
    f = f0 + np.interp(t, mil, np.clip(df, -0.5, 0.5))
    return 2 * np.pi * np.cumsum(f) / sr


def _blocs_calmes(m, sr, bloc_s=0.25, au_dessus_db=2.5):
    """Les blocs de 250 ms entièrement dans les silences STRICTS (à moins de 2,5 dB du fond) : là, le secteur est seul. (Le banc du
    13/11 : à 4 dB, les queues douces d'une voix de Hakim passaient pour du silence et faussaient l'estimation.)"""
    n = int(sr * bloc_s)
    out = []
    for a, b in sorted(silences(m, sr, au_dessus_db, bloc_s)):
        for d in range(a, b - n + 1, n):
            out.append(d)
    return out, n


def retirer_ronflement(x, mes, sr=SR, bloc_s=1.0):
    """Le secteur APPRIS DANS LES SILENCES puis soustrait. (Le banc du 13/11 : estimé par blocs d'une seconde sur toute la prise, il
    emportait les partiels d'une voix en sol ou en ré, 98 et 147 Hz, voisins de 100 et 150 Hz : −47 dB de dégâts, autant que le
    ronflement lui-même.) Dans chaque bloc calme de 250 ms : la phase de la fondamentale (déroulée d'un bloc à l'autre : le réseau
    dérive) et la forme de chaque harmonique mesurée dans les silences (saillance ≥ 6 dB) ; entre deux blocs calmes, l'une et l'autre
    interpolées. Moins de 1 s de silence : estimé par blocs d'une seconde sur toute la prise (_retirer_ronflement_partout)."""
    x = _2d(x).copy()
    m = _mono(x)
    f0 = float(mes["f0"])
    ks = [k for k in (mes.get("harmoniques") or []) if k * f0 < 1500] or [1, 2, 3]
    blocs, n = _blocs_calmes(m, sr)
    if len(blocs) * n < sr or "ronflement_silences" in COUPE:
        return _retirer_ronflement_partout(x, mes, sr, bloc_s)
    sal = mes.get("saillance_db") or [0.0]
    kr = next((k for k in (1, 2, 3) if k <= len(sal) and sal[k - 1] >= 10), 1)
    N = len(x)
    t = np.arange(N) / sr
    tb = np.arange(n) / sr
    w = np.hanning(n)
    centres = np.array([(d + n / 2) / sr for d in blocs])

    def phases(f):                                       # la phase de l'harmonique de référence, bloc par bloc (temps absolu)
        return np.array([np.angle(np.dot(w * m[d:d + n], np.exp(-2j * np.pi * kr * f * (d / sr + tb)))) for d in blocs])
    # la vraie fréquence du réseau : la pente de la phase entre deux blocs calmes voisins (250 ms : sans ambiguïté jusqu'à ±2 Hz) ;
    # (le banc : la crête du spectre des silences mis bout à bout se trompait de 0,2 Hz, et le déroulé décrochait)
    f0 = float(mes.get("hz") or f0)
    psi = phases(f0)
    pentes = [math.remainder(psi[j + 1] - psi[j], 2 * math.pi) / (2 * math.pi * kr * n / sr)
              for j in range(len(blocs) - 1) if blocs[j + 1] - blocs[j] == n]
    if pentes:
        f0 += float(np.median(pentes))
        psi = phases(f0)
    # la phase du réseau, suivie sur TOUTE la prise (blocs d'une seconde, l'harmonique de référence : la voix n'a presque rien à 50 Hz) ;
    # (le banc du 13/11 : interpolée entre deux silences éloignés de 80 s, elle décrochait pendant le chant et doublait l'erreur)
    if "suivi_phase" in COUPE:                           # témoin : la phase interpolée entre les blocs calmes seulement
        phi = 2 * np.pi * f0 * t + np.interp(t, centres, np.unwrap(psi) / kr)
    else:
        phi = _phase_secteur(m, sr, f0, kr, 1.0)
    for c in range(x.shape[1]):
        v = x[:, c]
        hum = np.zeros(N)
        for k in ks:
            B = []
            for j, d in enumerate(blocs):
                ph = k * phi[d:d + n]
                cc, ss = np.cos(ph), np.sin(ph)
                A = np.array([[np.dot(cc, cc), np.dot(cc, ss)], [np.dot(ss, cc), np.dot(ss, ss)]])
                y = np.array([np.dot(cc, v[d:d + n]), np.dot(ss, v[d:d + n])])
                B.append(np.linalg.solve(A + 1e-9 * np.eye(2), y))
            B = np.array(B)
            if len(B) >= 5:                              # une médiane glissante sur 5 blocs : un bloc où la voix traîne ne compte pas
                Bp = np.pad(B, ((2, 2), (0, 0)), mode="edge")
                B = np.median(np.lib.stride_tricks.sliding_window_view(Bp, 5, axis=0), axis=2)
            a_t, b_t = np.interp(t, centres, B[:, 0]), np.interp(t, centres, B[:, 1])
            hum += a_t * np.cos(k * phi) + b_t * np.sin(k * phi)
        x[:, c] = v - hum
    return x


def _retirer_ronflement_partout(x, mes, sr=SR, bloc_s=1.0):
    """(une prise sans silence) chaque harmonique suivie en phase, estimée par blocs d'une seconde sur toute la prise."""
    x = _2d(x).copy()
    f0 = float(mes["f0"])
    ks = [k for k in (mes.get("harmoniques") or []) if k * f0 < 1500] or [1, 2, 3]
    sal = mes.get("saillance_db") or []
    kr = max(range(1, len(sal) + 1), key=lambda k: sal[k - 1]) if sal else 1
    n = int(sr * bloc_s)
    pas = n // 2
    w = np.hanning(n + 1)[:-1]                          # périodique : les fenêtres à moitié recouvertes somment à 1
    N = len(x)
    phi = _phase_secteur(_mono(x), sr, f0, kr, bloc_s)
    debuts = list(range(-pas, N, pas))
    for c in range(x.shape[1]):
        v = x[:, c]
        hum = np.zeros(N)
        for k in ks:
            co, si = np.cos(k * phi), np.sin(k * phi)
            for d in debuts:
                a, b = max(0, d), min(N, d + n)
                if b - a < 32:
                    continue
                ww = w[a - d: b - d]
                cc, ss = co[a:b], si[a:b]
                A = np.array([[np.dot(ww * cc, cc), np.dot(ww * cc, ss)], [np.dot(ww * ss, cc), np.dot(ww * ss, ss)]])
                y = np.array([np.dot(ww * cc, v[a:b]), np.dot(ww * ss, v[a:b])])
                try:
                    ab = np.linalg.solve(A + 1e-9 * np.eye(2), y)
                except np.linalg.LinAlgError:
                    continue
                hum[a:b] += ww * (ab[0] * cc + ab[1] * ss)
        x[:, c] = v - hum
    return x


# ------------------------------------------------------------------------------------------------ 5. le souffle (profil appris sur les silences)
def mesure_souffle(x, sr=SR):
    """Le bruit de fond (dBFS, 3e centile des trames de 20 ms) et l'écart à la voix (dB). Présent si le fond dépasse −80 dBFS, reste
    à moins de 50 dB de la voix (une compression de 10 dB plus le master le remonteraient à l'oreille), et si les silences sont du
    BRUIT (non voisés) : le profil s'apprend là, il ne doit pas apprendre la voix."""
    m = _mono(x)
    fond, voix = fond_et_voix(m, sr)
    b = bruit_des_silences(m, sr)
    return {"fond_dbfs": round(fond, 1), "voix_dbfs": round(voix, 1), "ecart_db": round(voix - fond, 1), **b,
            "present": fond > -80 and (voix - fond) < 50 and b["bruit"]}


def _stft(m, n=2048, pas=512):
    w = np.hanning(n + 1)[:-1]
    mp = np.pad(m, (n, n + n))
    k = 1 + (len(mp) - n) // pas
    idx = np.arange(n)[None, :] + pas * np.arange(k)[:, None]
    return np.fft.rfft(mp[idx] * w, axis=1).astype(np.complex64)


def _istft(X, longueur, n=2048, pas=512):
    w = np.hanning(n + 1)[:-1]
    fr = np.fft.irfft(X, n=n, axis=1) * w
    k = X.shape[0]
    tot = pas * (k - 1) + n
    out = np.zeros(tot)
    norm = np.zeros(tot)
    r = n // pas
    for j in range(r):                                  # les trames j, j+r, j+2r… ne se recouvrent pas : posées d'un bloc
        sel = fr[j::r]
        a = j * pas
        out[a: a + sel.size] += sel.ravel()
        norm[a: a + sel.size] += np.tile(w * w, len(sel))
    out /= np.maximum(norm, 1e-9)
    return out[n: n + longueur]


def _profil_bruit(X, m, sr, pas=512, n=2048):
    """La densité du bruit par fréquence : la moyenne |X|² des trames entièrement dans les silences."""
    sil = silences(m, sr)
    k = X.shape[0]
    centre = np.arange(k) * pas - n + n // 2            # (le signal est décalé de n par le bourrage)
    garde = np.zeros(k, bool)
    for a, b in sil:
        garde |= (centre - n // 2 >= a) & (centre + n // 2 <= b)
    if garde.sum() < 4:
        return None
    return (np.abs(X[garde]) ** 2).mean(axis=0)


def debruiter_wiener(x, sr=SR, reduction_db=18.0, alpha=0.98):
    """Wiener à décision dirigée (Ephraim-Malah) avec le PROFIL appris sur les silences de CHAQUE canal (les silences repérés sur le
    mono), plancher de gain (au plus reduction_db) : le bruit baisse sans « bruit musical » ni voix trouée. (Le banc du 13/11 : le
    profil du mono sous-estimait de 3 dB un bruit indépendant sur deux canaux — 7 dB de moins retirés entre les phrases — ; un
    lissage des gains sur 3 fréquences coûtait 1,2 à 2,6 dB de SI-SDR : retiré.)"""
    x = _2d(x)
    m = _mono(x)
    out = np.empty_like(x)
    g_min = 10 ** (-reduction_db / 20)
    for c in range(x.shape[1]):
        X = _stft(x[:, c])
        N = _profil_bruit(X, m, sr)
        if N is None:
            return x.copy()
        N = N + 1e-20
        P = np.abs(X) ** 2
        G = np.empty(P.shape, np.float32)
        prec = np.zeros(P.shape[1])
        for i in range(P.shape[0]):
            gamma = P[i] / N
            xi = alpha * prec / N + (1 - alpha) * np.maximum(gamma - 1, 0)
            g = np.maximum(xi / (1 + xi), g_min)
            G[i] = g
            prec = (g * g) * P[i]
        out[:, c] = _istft(X * G, len(x))
    return out


def debruiter_afftdn(x, sr=SR, reduction_db=18.0):
    """afftdn de ffmpeg, son profil APPRIS sur le plus long silence (recopié devant la prise le temps de l'apprendre)."""
    x = _2d(x)
    m = _mono(x)
    sil = silences(m, sr)
    if not sil:
        return x.copy()
    a, b = sil[0]
    b = min(b, a + 2 * sr)
    pref = x[a:b]
    fond, _ = fond_et_voix(m, sr)
    xx = np.vstack([pref, x])
    t1 = len(pref) / sr
    af = (f"asendcmd=c='0.0 afftdn sn start;{max(0.05, t1 - 0.02):.3f} afftdn sn stop',"
          f"afftdn=nr={reduction_db:.1f}:nf={max(-80, min(-20, fond)):.1f}:tn=0")
    # (le banc du 13/11) afftdn RETARDE sa sortie (1102 échantillons à 44,1 kHz) : la latence est mesurée et retirée
    pad = 8192
    y = _ff(np.vstack([xx, np.zeros((pad, xx.shape[1]))]), af, sr)
    lag = max(0, decalage_echantillons(xx, y[: len(xx)], 4096))
    return y[len(pref) + lag: len(pref) + lag + len(x)]


def debruiter_dfn(x, sr=SR, reduction_db=18.0, python=None):
    """DeepFilterNet 3 (MIT/Apache, un venv à part : JARVIS_PYTHON_DEBRUITAGE), atténuation limitée à reduction_db."""
    import tempfile
    py = Path(python or PYTHON_DFN)
    if not py.exists():
        raise RuntimeError(f"DeepFilterNet absent ({py})")
    x = _2d(x)
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.f32", Path(d) / "b.f32"
        np.ascontiguousarray(x, np.float32).tofile(a)
        r = subprocess.run(["/usr/bin/nice", "-n", "10", str(py), "-B", str(ICI / "studio_pro_dfn.py"), str(a), str(b), str(sr),
                            str(x.shape[1]), str(reduction_db)], capture_output=True, text=True, timeout=3600)
        if r.returncode:
            raise RuntimeError(f"DeepFilterNet : {r.stderr.strip()[-300:]}")
        y = np.fromfile(b, np.float32).astype(np.float64).reshape(-1, x.shape[1])
    if len(y) < len(x):
        y = np.vstack([y, np.zeros((len(x) - len(y), x.shape[1]))])
    return y[: len(x)]


def debruiter(x, sr=SR, methode="auto", reduction_db=18.0):
    methode = DEBRUITEUR_PAR_DEFAUT if methode == "auto" else methode
    if methode == "afftdn":
        return debruiter_afftdn(x, sr, reduction_db)
    if methode == "deepfilternet":
        try:
            return debruiter_dfn(x, sr, reduction_db)
        except RuntimeError:
            return debruiter_wiener(x, sr, reduction_db)
    return debruiter_wiener(x, sr, reduction_db)


# ------------------------------------------------------------------------------------------------ 6. les plosives
def mesure_plosives(x, sr=SR):
    """Les plosives : une bouffée de grave (20-100 Hz) de 20 à 150 ms, 15 dB au-dessus de la médiane de ses graves et au moins au
    niveau de ses médiums (300 Hz-3 kHz) moins 6 dB, et nettement au-dessus du fond."""
    m = _mono(x)
    lf = _filtre_fft(m, sr, lambda f: _butter_mag(f, 100.0, 4, False) * _butter_mag(f, 20.0, 2, True))
    md = _filtre_fft(m, sr, lambda f: _butter_mag(f, 3000.0, 2, False) * _butter_mag(f, 300.0, 2, True))
    llf, lmd = niveaux_db(lf, sr), niveaux_db(md, sr)
    fond, voix = fond_et_voix(m, sr)
    vivant = llf[llf > -110]
    med = float(np.median(vivant)) if len(vivant) else -120.0
    haut = (llf > med + 15) & (llf > lmd - 6) & (llf > fond + 20) & (llf > voix - 30)
    p = int(sr * 0.01)
    out = []
    for a, b in _runs(haut):
        if 2 <= b - a <= 15:
            out.append((int(a * p), int(b * p + int(sr * 0.02))))
    return {"plosives": len(out), "present": len(out) >= 1, "_plosives": out, "graves_mediane_db": round(med, 1)}


def adoucir_plosives(x, mes, sr=SR, fc=150.0):
    """Un coupe-bas à phase nulle (fc, 4e ordre) appliqué seulement pendant chaque bouffée (10 ms avant, 30 ms après, fondus de
    10 ms) : la voix garde ses graves partout ailleurs."""
    x = _2d(x).copy()
    for a, b in mes["_plosives"]:
        a0 = max(0, a - int(sr * 0.05))
        b0 = min(len(x), b + int(sr * 0.08))
        seg = x[a0:b0]
        g = _masque_evenements(b0 - a0, [(a - a0, b - a0)], sr, 10, 30, 10)[:, None]
        hp = np.column_stack([_filtre_fft(seg[:, c], sr, lambda f: _butter_mag(f, fc, 4, True)) for c in range(seg.shape[1])])
        x[a0:b0] = seg + g * (hp - seg)
    return x


# ------------------------------------------------------------------------------------------------ 7. les respirations
def _voisement(m, sr, pas_s=0.01, fen_s=0.04):
    """Le voisement de chaque trame (0 à 1) : le pic de l'autocorrélation normalisée entre 1 et 14 ms (70 Hz à 1 kHz), sur le signal
    DÉRIVÉ (la différence première : +6 dB/oct). (Le banc du 13/11 : un bruit rose, très corrélé aux petits décalages, passait pour
    « voisé » à 0,5 ; dérivé, il ne l'est plus, une voix le reste.)"""
    if "voisement_derive" not in COUPE:
        m = np.diff(np.asarray(m, np.float64), prepend=float(m[0]) if len(m) else 0.0)
    n, p = int(sr * fen_s), int(sr * pas_s)
    k = max(1, 1 + (len(m) - n) // p)
    idx = np.arange(n)[None, :] + p * np.arange(k)[:, None]
    idx = np.minimum(idx, len(m) - 1)
    F = m[idx] * np.hanning(n)
    N = 1 << int(math.ceil(math.log2(2 * n)))
    S = np.fft.rfft(F, N, axis=1)
    ac = np.fft.irfft(np.abs(S) ** 2, N, axis=1)[:, :n]
    ac0 = ac[:, :1] + 1e-12
    lo, hi = int(sr / 1000), int(sr / 70)
    return (ac[:, lo:hi].max(axis=1) / ac0[:, 0]).clip(0, 1)


def mesure_respirations(x, sr=SR):
    """Les respirations : des trames non voisées (autocorrélation < 0,4), au-dessus du fond de 12 dB, sous la voix de 10 dB, sans
    sifflante (moins d'énergie au-dessus de 4,5 kHz qu'entre 0,5 et 4,5 kHz), sur au moins 150 ms, À CÔTÉ D'UN SILENCE (une
    respiration se prend entre deux phrases ; une consonne est dans la phrase)."""
    m = _mono(x)
    pas = 0.01
    l = niveaux_db(m, sr, 0.02, pas)
    fond, voix = fond_et_voix(m, sr)
    v = _voisement(m, sr)
    k = min(len(l), len(v))
    l, v = l[:k], v[:k]
    hf = niveaux_db(_filtre_fft(m, sr, lambda f: _butter_mag(f, 4500.0, 4, True)), sr)[:k]
    md = niveaux_db(_filtre_fft(m, sr, lambda f: _butter_mag(f, 4500.0, 4, False) * _butter_mag(f, 500.0, 2, True)), sr)[:k]
    souffle = (v < 0.4) & (l > fond + 12) & (l < voix - 10) & (hf < md)
    souffle = np.convolve(souffle.astype(float), np.ones(3), "same") >= 2        # un trou d'une trame comblé
    calme = l < fond + 8
    p = int(sr * pas)
    out = []
    for a, b in _runs(souffle):
        if (b - a) * pas < 0.15:
            continue
        avant = calme[max(0, a - 6):a].any()
        apres = calme[b:b + 6].any()
        if avant or apres:
            out.append((int(a * p), int(min(len(m), b * p + int(sr * 0.02)))))
    return {"respirations": len(out), "present": len(out) >= 1, "_respirations": out}


def baisser_respirations(x, mes, sr=SR, gain_db=-8.0):
    """Chaque respiration baissée de gain_db (fondus de 15 ms), jamais supprimée."""
    x = _2d(x)
    g = _masque_evenements(len(x), mes["_respirations"], sr, 0, 0, 15)
    return x * (1 + g * (10 ** (gain_db / 20) - 1))[:, None]


# ------------------------------------------------------------------------------------------------ 8. la porte douce (expandeur)
def _detecteur_porte(m, sr):
    """Ce qu'écoute l'expandeur : la voix sans ses graves (coupe-bas 100 Hz) : un grondement grave ne l'ouvre pas."""
    return _filtre_fft(m, sr, lambda f: _butter_mag(f, 100.0, 2, True))


def mesure_porte(x, sr=SR):
    """Le seuil de l'expandeur : 3 dB au-dessus du 90e centile des silences (le bruit qui reste, ses bouffées comprises ; le banc du
    13/11 : après un débruitage, le résidu a des bouffées de 13 dB au-dessus de sa médiane, et un seuil posé sur la médiane laissait
    passer l'essentiel), écouté sans ses graves. Présente si ce bruit reste audible (au-dessus de −75 dBFS), si c'est du bruit (pas
    une voix douce ni une réverbération : on ne les ferme pas), et si la voix passe 15 dB au-dessus du seuil."""
    m = _mono(x)
    fond, voix = fond_et_voix(m, sr)
    b = bruit_des_silences(m, sr)
    sil = silences(m, sr)
    l = niveaux_db(_detecteur_porte(m, sr), sr)
    p = int(sr * 0.01)
    sel = np.zeros(len(l), bool)
    for a, bb in sil:
        sel[a // p: max(a // p + 1, bb // p - 1)] = True
    bruit = float(np.percentile(l[sel], 90)) if sel.any() else fond
    seuil = bruit + 3.0
    return {"fond_dbfs": round(fond, 1), "bruit_dbfs": round(bruit, 1), "seuil_dbfs": round(seuil, 1), "voisement": b["voisement"],
            "present": bruit > -75 and b["bruit"] and voix - seuil >= 15}


def expandeur(x, mes, sr=SR, plage_db=-12.0, ratio=4.0, attaque_ms=2.0, relache_ms=120.0, anticipation_ms=5.0):
    """Un expandeur vers le bas : sous le seuil, chaque dB de moins en fait `ratio` (4 : 4 dB sous le seuil, −12 dB) ; au plus
    plage_db (doux : jamais fermé). Enveloppe efficace de 10 ms,
    ouverture anticipée de 5 ms (rien n'est rogné aux attaques), fermeture lente (120 ms)."""
    x = _2d(x)
    m = _detecteur_porte(_mono(x), sr)
    p = int(sr * 0.001)                                 # trames de 1 ms
    k = len(m) // p + 1
    mp = np.pad(m, (0, k * p - len(m)))
    e = (mp.reshape(k, p) ** 2).mean(axis=1)
    w = 10
    e = np.convolve(e, np.ones(w) / w, "same")
    l = 10 * np.log10(np.maximum(e, 1e-14))
    seuil = mes["seuil_dbfs"]
    gdb = np.where(l < seuil, np.maximum(plage_db, (l - seuil) * (ratio - 1)), 0.0)
    a = int(anticipation_ms)
    if a > 0:                                           # anticipation : le gain le plus ouvert des a ms qui viennent
        gp = np.pad(gdb, (0, a), mode="edge")
        gdb = np.lib.stride_tricks.sliding_window_view(gp, a + 1).max(axis=1)
    ca = math.exp(-1 / max(0.1, attaque_ms))
    cr = math.exp(-1 / max(0.1, relache_ms))
    out = np.empty_like(gdb)
    g = 0.0
    for i, v in enumerate(gdb):                         # ouvre vite (vers 0 dB), referme lentement
        c = ca if v > g else cr
        g = c * g + (1 - c) * v
        out[i] = g
    gain = np.repeat(10 ** (out / 20), p)[: len(m)]
    return x * gain[:, None]


# ------------------------------------------------------------------------------------------------ 9. le nivellement (vocal rider)
def _chante(m, sr, l, fond, voix):
    """Les trames (pas de 10 ms) où la voix CHANTE : voisées (autocorrélation ≥ 0,5), au-dessus du fond de 20 dB et à moins de 30 dB
    du haut de la voix. Les respirations, les sifflantes et le fond n'en sont pas : le nivellement ne les remonte pas."""
    v = _voisement(m, sr)
    k = min(len(l), len(v))
    out = np.zeros(len(l), bool)
    out[:k] = (v[:k] >= 0.5) & (l[:k] > max(fond + 20, voix - 30))
    return out


def mesure_nivellement(x, sr=SR):
    """Combien le niveau de la voix varie d'une phrase à l'autre : l'écart-type (dB) de son niveau lissé sur 300 ms, sur les trames
    où elle chante. Présent au-delà de 3 dB."""
    m = _mono(x)
    l = niveaux_db(m, sr, 0.05, 0.01)
    fond, voix = fond_et_voix(m, sr)
    vivant = _chante(m, sr, l, fond, voix)
    if vivant.sum() < 50:
        return {"ecart_type_db": 0.0, "present": False}
    lis = _lisse_vivant(l, vivant, 30)
    v = lis[vivant]
    return {"ecart_type_db": round(float(v.std()), 1), "mediane_dbfs": round(float(np.median(v)), 1), "present": float(v.std()) > 3.0}


def _lisse_vivant(l, vivant, w):
    """La moyenne glissante (en puissance) des trames vivantes seulement, sur w trames."""
    p = np.where(vivant, 10 ** (l / 10), 0.0)
    c = np.convolve(p, np.ones(w), "same")
    n = np.convolve(vivant.astype(float), np.ones(w), "same")
    return 10 * np.log10(np.maximum(c / np.maximum(n, 1e-9), 1e-14))


def niveler(x, mes, sr=SR, max_db=6.0):
    """Le niveau ramené vers la médiane (au plus ±max_db), lissé sur 300 ms, seulement sur la voix (les silences gardent le gain de
    la phrase voisine : le fond ne monte pas)."""
    x = _2d(x)
    m = _mono(x)
    l = niveaux_db(m, sr, 0.05, 0.01)
    fond, voix = fond_et_voix(m, sr)
    vivant = _chante(m, sr, l, fond, voix)
    if vivant.sum() < 50:
        return x.copy()
    lis = _lisse_vivant(l, vivant, 30)
    cible = float(np.median(lis[vivant]))
    g = np.clip(cible - lis, -max_db, max_db)
    g = np.where(vivant, g, np.nan)
    # les trames muettes prennent le gain de la trame vivante la plus proche (pas de pompage du fond), mais jamais une HAUSSE : (la démo
    # du 13/11) une phrase douce remontée de 6 dB remontait aussi le souffle et la queue de réverb qui la suivent (+3,7 dB dans les
    # silences de Moujahid 3.2)
    i = np.flatnonzero(~np.isnan(g))
    g = np.where(vivant, np.interp(np.arange(len(g)), i, g[i]), np.minimum(0.0, np.interp(np.arange(len(g)), i, g[i])))
    g = np.convolve(np.pad(g, (10, 10), mode="edge"), np.ones(21) / 21, "valid")      # lissé sur 200 ms
    p = int(sr * 0.01)
    t = np.arange(len(m)) / p - 2.0                      # le centre de chaque trame de 50 ms
    gain = np.interp(t, np.arange(len(g)), g)
    return x * (10 ** (gain / 20))[:, None]


# ------------------------------------------------------------------------------------------------ la chaîne
MESURES = {"continu": lambda x, sr: mesure_continu(x), "ecretage": mesure_ecretage, "clics": mesure_clics, "ronflement": mesure_ronflement,
           "souffle": mesure_souffle, "plosives": mesure_plosives, "respirations": mesure_respirations, "porte": mesure_porte,
           "nivellement": mesure_nivellement}


def _appliquer(etape, x, mes, sr, r):
    if etape == "continu":
        return retirer_continu(x)
    if etape == "ecretage":
        return reparer_ecretage(x, mes, sr) if mes.get("_plateaux") else x
    if etape == "clics":
        return reparer_clics(x, mes, sr) if mes.get("_clics") else x
    if etape == "ronflement":
        return retirer_ronflement(x, mes, sr)
    if etape == "souffle":
        return debruiter(x, sr, r.get("debruiteur", "auto"), float(r.get("souffle_db", 18)))
    if etape == "plosives":
        return adoucir_plosives(x, mes, sr, float(r.get("plosives_hz", 150))) if mes.get("_plosives") else x
    if etape == "respirations":
        return baisser_respirations(x, mes, sr, float(r.get("respirations_db", -8))) if mes.get("_respirations") else x
    if etape == "porte":
        return expandeur(x, mes, sr, float(r.get("porte_plage_db", -12)))
    if etape == "nivellement":
        return niveler(x, mes, sr, float(r.get("nivellement_db", 6)))
    return x


def _public(mes):
    return {k: v for k, v in mes.items() if not k.startswith("_")}


def diagnostic(x, sr=SR):
    """Toutes les mesures d'une voix brute (rien n'est changé)."""
    return {e: _public(MESURES[e](x, sr)) for e in ETAPES}


def traiter(x, sr=SR, reglages=None, journal=None):
    """La chaîne pro sur une voix : chaque étape mesurée sur la voix TELLE QU'ELLE ARRIVE à cette étape (après les précédentes), puis
    appliquée si son mode le dit (« auto » : si la mesure le justifie). Rend (voix traitée, rapport par étape)."""
    r = borner(reglages)
    say = journal or (lambda s: None)
    x = _2d(x).copy()
    rapport = {}
    if not r.get("actif", True):
        return x, {"actif": False}
    for e in ETAPES:
        mode = r.get(e, "auto")
        if mode == "non" or e in COUPE:
            rapport[e] = {"actif": False, "raison": "coupé" if mode == "non" else "témoin"}
            continue
        mes = MESURES[e](x, sr)
        actif = mode == "oui" or bool(mes.get("present"))
        info = {"actif": actif, "mode": mode, "mesure": _public(mes)}
        if actif:
            avant = x
            x = _appliquer(e, x, mes, sr, r)
            d = x - avant
            info["change_db"] = round(10 * math.log10(max(1e-20, float((d ** 2).mean())) / max(1e-20, float((avant ** 2).mean()))), 1)
            say(f"{e} : {info['mesure']}")
        rapport[e] = info
    return x, rapport


def traiter_fichier(entree, sortie, reglages=None, sr=SR):
    """Une voix (fichier) → sa version traitée (WAV flottant 32 bits : les crêtes reconstruites peuvent dépasser 0 dBFS). Rend le
    rapport (avec le fond et la crête, avant et après)."""
    sys.path.insert(0, str(ICI))
    import studio_mesures as M
    x, _ = M.lire(entree, sr)
    y, rapport = traiter(x, sr, reglages)
    M.ecrire_wav(sortie, y, sr, 32)
    fa, _ = fond_et_voix(_mono(x), sr)
    fb, _ = fond_et_voix(_mono(y), sr)
    rapport["_fond"] = {"avant_dbfs": round(fa, 1), "apres_dbfs": round(fb, 1)}
    return rapport


def resume(rapport):
    """Le rapport en mots courts : ce qui a été fait, mesuré."""
    if not rapport or rapport.get("actif") is False:
        return "chaîne pro coupée"
    mots = []
    for e in ETAPES:
        i = rapport.get(e) or {}
        if not i.get("actif"):
            continue
        m = i.get("mesure") or {}
        if e == "continu":
            mots.append(f"décalage continu retiré ({m.get('dbfs')} dBFS)")
        elif e == "ecretage":
            mots.append(f"{m.get('plateaux')} crêtes écrêtées reconstruites")
        elif e == "clics":
            mots.append(f"{m.get('clics')} clics réparés")
        elif e == "ronflement":
            mots.append(f"ronflement {m.get('hz'):.0f} Hz retiré ({len(m.get('harmoniques') or [])} harmoniques)")
        elif e == "souffle":
            mots.append(f"souffle débruité (fond {m.get('fond_dbfs')} dBFS, {m.get('ecart_db')} dB sous la voix)")
        elif e == "plosives":
            mots.append(f"{m.get('plosives')} plosives adoucies")
        elif e == "respirations":
            mots.append(f"{m.get('respirations')} respirations baissées")
        elif e == "porte":
            mots.append(f"expandeur doux sous {m.get('seuil_dbfs')} dBFS")
        elif e == "nivellement":
            mots.append(f"niveau nivelé (il variait de {m.get('ecart_type_db')} dB)")
    f = rapport.get("_fond")
    if f:
        mots.append(f"fond {f['avant_dbfs']} → {f['apres_dbfs']} dBFS")
    return ", ".join(mots) if mots else "voix déjà propre : rien à corriger"


# ------------------------------------------------------------------------------------------------ le calage des doubles
def phrases(m, sr=SR, trou_s=0.15, min_s=0.3):
    """Les phrases d'une voix (au-dessus du fond de 15 dB), séparées par des trous d'au moins 150 ms : [(a, b)] en secondes."""
    l = niveaux_db(_mono(m), sr, 0.02, 0.01)
    fond, voix = fond_et_voix(_mono(m), sr)
    on = l > max(fond + 15, voix - 40)
    w = int(trou_s / 0.01)
    on = np.convolve(on.astype(float), np.ones(w), "same") > 0          # les trous plus courts que 150 ms comblés
    return [(round(a * 0.01, 3), round(b * 0.01, 3)) for a, b in _runs(on) if (b - a) * 0.01 >= min_s]


def _enveloppe(m, sr, pas_s=0.001):
    """L'enveloppe d'attaques (la montée du niveau en dB, trames de 1 ms) : ce que l'oreille cale."""
    p = int(sr * pas_s)
    k = len(m) // p
    if k < 4:
        return np.zeros(1)
    e = 10 * np.log10(np.maximum((m[: k * p].reshape(k, p) ** 2).mean(axis=1), 1e-12))
    e = np.convolve(e, np.ones(5) / 5, "same")
    return np.maximum(np.diff(e, prepend=e[0]), 0)


def caler_phrases(principale, double, sr=SR, max_ms=80.0, min_nettete=0.3):
    """Chaque phrase du double calée sur la voix principale : le décalage (ms, + : le double est en retard) qui aligne au mieux ses
    attaques sur celles de la principale autour de la même phrase (±max_ms). Rend [{debut_s, fin_s, decalage_ms, nettete}] ; une
    phrase sans pic net (aucune voix principale en face) garde 0."""
    a, b = _mono(principale), _mono(double)
    out = []
    for d0, f0 in phrases(b, sr):
        i0, i1 = int(d0 * sr), int(f0 * sr)
        m = int(sr * max_ms / 1000)
        pa = a[max(0, i0 - m): min(len(a), i1 + m)]
        pb = b[i0:i1]
        ea, eb = _enveloppe(pa, sr), _enveloppe(pb, sr)
        off = (i0 - max(0, i0 - m)) // int(sr * 0.001)
        L = int(max_ms)
        cs = []
        for lag in range(-L, L + 1):
            j = off - lag                                # le double en retard de lag ms : il commence lag ms après la principale
            if j < 0 or j + len(eb) > len(ea):
                cs.append(-1.0)
                continue
            cs.append(float(np.dot(ea[j:j + len(eb)], eb)))
        cs = np.array(cs)
        if (cs > 0).sum() < 3 or cs.max() <= 0:
            out.append({"debut_s": d0, "fin_s": f0, "decalage_ms": 0.0, "nettete": 0.0})
            continue
        k = int(np.argmax(cs))
        nett = float((cs.max() - np.median(cs[cs >= 0])) / (cs[cs >= 0].std() + 1e-12)) / 6
        dk = 0.0
        if 0 < k < len(cs) - 1 and cs[k - 1] >= 0 and cs[k + 1] >= 0:
            den = cs[k - 1] - 2 * cs[k] + cs[k + 1]
            dk = 0.5 * (cs[k - 1] - cs[k + 1]) / den if den else 0.0
        lag = (k - L) + dk
        ok = nett >= min_nettete
        out.append({"debut_s": d0, "fin_s": f0, "decalage_ms": round(float(lag), 1) if ok else 0.0, "nettete": round(min(1.0, nett), 2)})
    return out
