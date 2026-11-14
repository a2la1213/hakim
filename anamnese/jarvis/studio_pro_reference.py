"""Le calage d'une voix sur une voix de RÉFÉRENCE (14/11, Ahmed : « j'aimerais juste que les mix [de ma voix] soient aussi bien que
sa voix », la voix de Hakim).

La voix de Hakim est synthétique : elle naît propre (ni pièce, ni bruit, une couleur régulière). Celle de papa passe par l'air, la
pièce et le micro. Le calage corrige la COULEUR DU MICRO ET DE LA PIÈCE, jamais la personne :
  le profil      ce qu'on mesure d'une voix : son spectre moyen par tiers d'octave (la forme, pas le niveau), sa pente, la boue
                 (200-500 Hz), la présence (2-5 kHz), les sifflantes (5-9 kHz), son fond, sa dynamique (le niveau court terme, le
                 facteur de crête), sa réverbération (la décroissance après chaque fin de phrase), sa hauteur (pour information :
                 la hauteur est la PERSONNE, on n'y touche jamais) ;
  l'égalisation  la différence des deux spectres moyens, LISSÉE sur une octave (une couleur de micro ou de pièce est large ; les
                 formants, eux, sont plus fins et bougent à chaque voyelle : lissés, ils ne passent pas dans la courbe), BORNÉE à
                 ±6 dB, sans jamais relever une bande où la voix n'a que son bruit ; un filtre à phase nulle ;
  les sifflantes un dé-esseur à bande partagée (5-10 kHz) qui ne baisse que les trames où les sifflantes dépassent ce que la
                 référence se permet (son 90e centile) ;
  et, au mix (studio_projet.mixer_auto) : la même tranche que la référence (égaliseur, saturation, envois de réverbération et de
                 délai), la densité de compression appariée (mesurée sur le rendu de la piste seule), le même espace (la traîne
                 après les fins de phrase), la parité de niveau.

RÈGLE ABSOLUE : la voix reste CELLE de la personne. Aucune étape ne déplace les formants ni ne change la hauteur ; l'empreinte
vocale (WeSpeaker, un juge indépendant) le vérifie au banc.

Chaque mécanisme se COUPE pour les témoins (studio_pro.COUPE, la variable STUDIO_PRO_COUPE) : son test doit alors échouer.
Numpy et ffmpeg seulement.
"""
import json
import math
import time
from pathlib import Path

import numpy as np

import studio_pro as P

SR = P.SR
VERSION = 1
TIERS = (50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300,
         8000, 10000, 12500, 16000)
ZONES = {"boue": (200, 500), "presence": (2000, 5000), "sifflantes": (5000, 9000), "air": (10000, 16000)}
NORME = (100, 10000)                                     # la forme d'un spectre : relative à son énergie entre 100 Hz et 10 kHz
BORNE_DB = 6.0
MODES = ("auto", "oui", "non")


def _coupe(nom):
    return nom in P.COUPE


# ------------------------------------------------------------------------------------------------ le spectre des passages actifs
def _trames(m, n, pas):
    k = max(1, 1 + (len(m) - n) // pas)
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    idx = np.arange(n)[None, :] + pas * np.arange(k)[:, None]
    return m[idx]


def spectre_actif(m, sr=SR, n=8192, pas=2048):
    """(fréquences, puissance moyenne des trames ACTIVES, puissance moyenne des trames de SILENCE) d'un son mono. Actives : à moins de
    25 dB du haut de la voix (95e centile) et 15 dB au-dessus du fond (3e centile) ; silence : à moins de 6 dB du fond."""
    m = np.asarray(m, np.float64)
    w = np.hanning(n)
    F = _trames(m, n, pas)
    lv = 10 * np.log10(np.maximum((F ** 2).mean(axis=1), 1e-14))
    fond, haut = float(np.percentile(lv, 3)), float(np.percentile(lv, 95))
    act = lv > max(haut - 25, fond + 15)
    sil = lv < fond + 6
    S = np.abs(np.fft.rfft(F * w, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    pa = S[act].mean(axis=0) if act.any() else S.mean(axis=0)
    pb = S[sil].mean(axis=0) if sil.sum() >= 2 else np.full_like(pa, 1e-20)
    return f, pa, pb


def _bande(f, p, a, b):
    sel = (f >= a) & (f < b)
    return float(p[sel].sum()) if sel.any() else 1e-30


def tiers_octave(f, p):
    """La puissance par tiers d'octave (centres TIERS), en dB."""
    return np.array([10 * math.log10(max(1e-30, _bande(f, p, c * 2 ** (-1 / 6), c * 2 ** (1 / 6)))) for c in TIERS])


# ------------------------------------------------------------------------------------------------ la dynamique
def _k_pondere(m, sr):
    """La pondération K de BS.1770 (le pré-filtre en plateau +4 dB au-dessus de 1,5 kHz et le passe-haut RLB), appliquée en phase nulle
    par sa réponse en amplitude (les biquads à 48 kHz évalués aux fréquences) : pour MESURER un niveau, pas pour écouter."""
    def biquad(b, a, f):
        z = np.exp(-1j * 2 * np.pi * f / 48000.0)
        return np.abs((b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z))
    b1, a1 = (1.53512485958697, -2.69169618940638, 1.19839281085285), (1.0, -1.69065929318241, 0.73248077421585)
    b2, a2 = (1.0, -2.0, 1.0), (1.0, -1.99004745483398, 0.99007225036621)
    return P._filtre_fft(m, sr, lambda f: biquad(b1, a1, np.minimum(f, 23999)) * biquad(b2, a2, np.minimum(f, 23999)))


def _corps(m, sr):
    return P._filtre_fft(np.asarray(m, np.float64), sr, lambda f: P._butter_mag(f, 250.0, 2, True) * P._butter_mag(f, 4000.0, 2, False))


def dynamique(m, sr=SR):
    """La densité d'une voix : l'écart-type de son niveau court terme (fenêtres K-pondérées de 3 s, pas de 0,5 s, seulement celles où la
    voix vit dans au moins 80 % des blocs de 400 ms : une fenêtre à moitié dans un silence n'est pas une variation de la voix),
    l'écart-type de son niveau sur 400 ms (les blocs où elle vit : à moins de 20 dB du haut) et son facteur de crête (crête − efficace,
    médiane sur ces blocs). Une voix plus compressée : des écarts plus petits, une crête plus basse."""
    m = np.asarray(m, np.float64)
    n4 = int(0.4 * sr)
    T4 = _trames(m, n4, n4)
    rms = np.sqrt((T4 ** 2).mean(axis=1)) + 1e-12
    pic = np.abs(T4).max(axis=1) + 1e-12
    l4 = 20 * np.log10(rms)
    viv = l4 > np.percentile(l4, 95) - 20
    k = _k_pondere(m, sr)
    n, pas = int(3 * sr), int(0.5 * sr)
    st = np.array([0.0])
    if len(k) >= n:
        T = _trames(k, n, pas)
        lst = 10 * np.log10(np.maximum((T ** 2).mean(axis=1), 1e-14)) - 0.691
        # la part de blocs vivants de chaque fenêtre (les blocs de 400 ms qui tombent dedans)
        c = np.concatenate([[0], np.cumsum(viv.astype(float))])
        deb = (np.arange(len(lst)) * pas) // n4
        fin = np.minimum(len(viv), (np.arange(len(lst)) * pas + n) // n4)
        part = (c[fin] - c[deb]) / np.maximum(1, fin - deb)
        garde = part >= 0.8
        if garde.sum() >= 2:
            st = lst[garde]
    # le facteur de crête du CORPS de la voix (250 Hz-4 kHz) : les sifflantes et les graves n'y comptent pas (le 14/11 : un dé-essage ou
    # un égaliseur changeaient l'écart du niveau sur 400 ms plus que la compression elle-même)
    c4 = _trames(_corps(m, sr), n4, n4)
    rc = np.sqrt((c4 ** 2).mean(axis=1)) + 1e-12
    pc = np.abs(c4).max(axis=1) + 1e-12
    crete_corps = round(float(np.median(20 * np.log10(pc[viv] / rc[viv]))), 2) if viv.sum() > 2 else 0.0
    return {"crete_corps_db": crete_corps, "court_terme_ecart_db": round(float(st.std()), 2),
            "court_terme_plage_db": round(float(np.percentile(st, 95) - np.percentile(st, 10)), 2) if len(st) > 2 else 0.0,
            "niveau_400ms_ecart_db": round(float(l4[viv].std()), 2) if viv.sum() > 2 else 0.0,
            "crete_db": round(float(np.median(20 * np.log10(pic[viv] / rms[viv]))), 2) if viv.sum() > 2 else 0.0}


# ------------------------------------------------------------------------------------------------ la réverbération (les fins de phrase)
def fins_de_phrase(m, sr=SR, pas_s=0.005, chute_db=20.0):
    """Les fins de phrase nettes (en trames de 5 ms) : un niveau tenu (les 100 ms d'avant à moins de 6 dB) qui retombe d'au moins
    20 dB (ou jusqu'au fond) en 250 ms au plus et reste au moins 12 dB plus bas jusqu'à 400 ms (une pause, pas un trou entre deux
    syllabes). Rend (niveaux en dB par trame, [indices des fins], fond)."""
    l = P.niveaux_db(np.asarray(m, np.float64), sr, 0.02, pas_s)
    fond, haut = P.fond_et_voix(m, sr)
    k20, k100, k400 = int(0.02 / pas_s), int(0.1 / pas_s), int(0.4 / pas_s)
    fins = []
    i = k100
    while i < len(l) - k400:
        if l[i] >= haut - 20 and l[i] - min(l[i - k100:i]) <= 6 and l[i + 1] < l[i] and max(l[i + 1:i + k20 + 1]) <= l[i]:
            apres = l[i:i + k400]
            bas = apres <= max(l[i] - chute_db, fond + 6)
            j = int(np.argmax(bas)) if bas.any() else len(apres)
            # une vraie pause : la voix retombe en 250 ms au plus, puis RESTE basse jusqu'au bout des 400 ms (le 14/11 : dans un rap,
            # le trou entre deux syllabes passait pour une fin de phrase, la syllabe suivante pour une traîne)
            reste_bas = j <= int(0.25 / pas_s) and bool((apres[j:] <= l[i] - (chute_db - 8)).all())
            if "ref_pause" in P.COUPE:                   # témoin : l'ancienne règle (descendre de 20 dB, ne pas dépasser la fin)
                reste_bas = True
            if bas.any() and reste_bas and max(apres[1:]) <= l[i] + 1:
                # la VRAIE fin : le dernier instant encore à moins de 3 dB de ce niveau (un maximum local peut précéder la fin de
                # la phrase de 200 ms : la traîne mesurée aurait compté la voix elle-même)
                proche = np.flatnonzero(apres[: max(1, j)] >= l[i] - 3)
                fin = i + (int(proche[-1]) if len(proche) else 0)
                fins.append(fin)
                i = fin + k400
                continue
        i += 1
    return l, fins, fond


def reverberation(m, sr=SR, pas_s=0.005, fins=None):
    """La pièce (ou la réverbération) dans les pauses : après chaque fin de phrase, la vitesse de décroissance (dB/s, ajustée entre
    −5 et −25 dB sous le niveau de la fin, ou jusqu'au fond), la T60 apparente (60 / vitesse) et la traîne (l'énergie de 50 à 300 ms
    après la fin, contre les 100 ms d'avant, en dB). Une voix sèche retombe vite (une traîne très basse) ; une pièce la prolonge.
    fins : les fins de phrase repérées sur la version SÈCHE de la même voix (trames de 5 ms) : une réverbération forte empêche de
    les repérer sur la version mouillée (le 14/11 : 3 fins sur 16, une mesure qui ne montait plus avec l'envoi)."""
    if fins is None or "ref_fins_seches" in P.COUPE:
        l, fins, fond = fins_de_phrase(m, sr, pas_s)
    else:
        l = P.niveaux_db(np.asarray(m, np.float64), sr, 0.02, pas_s)
        fond, _ = P.fond_et_voix(m, sr)
        k = int(0.4 / pas_s)
        fins = [i for i in fins if int(0.1 / pas_s) <= i < len(l) - k]
    vit, tra = [], []
    k100, k50, k300 = int(0.1 / pas_s), int(0.05 / pas_s), int(0.3 / pas_s)
    for i in fins:
        top = l[i]
        seg = l[i:i + int(0.4 / pas_s)]
        bas = max(top - 25, fond + 5)
        sel = (seg <= top - 5) & (seg >= bas)
        idx = np.flatnonzero(sel)
        if len(idx) >= 4 and top - bas >= 12:
            a, b = idx[0], idx[-1]
            if b - a >= 3:
                t = np.arange(a, b + 1) * pas_s
                pente = -float(np.polyfit(t, seg[a:b + 1], 1)[0])
                if pente > 0:
                    vit.append(pente)
        av = 10 ** (l[i - k100:i] / 10)
        ap = 10 ** (l[i + k50:i + k300] / 10)
        tra.append(10 * math.log10(max(1e-14, float(ap.mean())) / max(1e-14, float(av.mean()))))
    if not vit:
        return {"fins": len(fins), "decroissance_db_s": None, "t60_apparente_s": None,
                "traine_db": round(float(np.median(tra)), 1) if tra else None}
    v = float(np.median(vit))
    return {"fins": len(fins), "decroissance_db_s": round(v, 0), "t60_apparente_s": round(60.0 / v, 3),
            "traine_db": round(float(np.median(tra)), 1)}


# ------------------------------------------------------------------------------------------------ la hauteur (pour information)
def _a_16k(m, sr):
    """Un sous-échantillonnage à 16 kHz (passe-bas à phase nulle à 7 kHz, puis interpolation) : assez pour une fondamentale."""
    if sr == 16000:
        return np.asarray(m, np.float64)
    m = P._filtre_fft(np.asarray(m, np.float64), sr, lambda f: P._butter_mag(f, 7000.0, 8, False))
    t = np.arange(0, len(m) / sr, 1 / 16000)
    return np.interp(t, np.arange(len(m)) / sr, m)


def suivre_f0(m, sr=SR, pas_s=0.01):
    """La fondamentale trame par trame (YIN : la différence cumulée normalisée, 70 Hz à 800 Hz, seuil 0,15, affinée par une
    parabole ; trames de 40 ms, pas de 10 ms, à 16 kHz). Rend (f0 en Hz, voisement 0-1, niveau dB), une valeur par trame ; la trame k
    couvre [k·pas, k·pas + 40 ms[ (son centre : k·pas + 20 ms)."""
    m = _a_16k(m, sr)
    s16 = 16000
    n, p = int(s16 * 0.04), int(s16 * pas_s)
    lo, hi = int(s16 / 800), int(s16 / 70)
    F = _trames(np.pad(m, (0, n + hi)), n + hi, p)[: max(1, 1 + (len(m) - n) // p)]
    # d(τ) = Σ (x[j] − x[j+τ])² sur n échantillons, par la corrélation (FFT)
    N = 1 << int(math.ceil(math.log2(2 * (n + hi))))
    A = np.fft.rfft(F[:, :n], N, axis=1)
    B = np.fft.rfft(F, N, axis=1)
    corr = np.fft.irfft(np.conj(A) * B, N, axis=1)[:, : hi + 1]
    c2 = np.concatenate([np.zeros((len(F), 1)), np.cumsum(F ** 2, axis=1)], axis=1)
    taus = np.arange(hi + 1)
    d = c2[:, n][:, None] + (c2[:, taus + n] - c2[:, taus]) - 2 * corr
    d[:, 0] = 0
    cum = np.cumsum(d[:, 1:], axis=1) / np.arange(1, hi + 1)
    dn = np.ones_like(d)
    dn[:, 1:] = d[:, 1:] / np.maximum(cum, 1e-12)
    seg = dn[:, lo:hi]
    rg = np.arange(len(seg))
    sous = seg < 0.15
    j = np.where(sous.any(axis=1), np.argmax(sous, axis=1), np.argmin(seg, axis=1))
    for _ in range(4):                                   # descendre jusqu'au creux local
        nxt = np.minimum(j + 1, seg.shape[1] - 1)
        j = np.where(seg[rg, nxt] < seg[rg, j], nxt, j)
    a, b, c = seg[rg, np.maximum(j - 1, 0)], seg[rg, j], seg[rg, np.minimum(j + 1, seg.shape[1] - 1)]
    den = a - 2 * b + c
    ok = np.abs(den) > 1e-12
    dj = np.where(ok, 0.5 * (a - c) / np.where(ok, den, 1), 0.0)
    f0 = s16 / (j + lo + np.clip(dj, -1, 1))
    lv = 10 * np.log10(np.maximum((F[:, :n] ** 2).mean(axis=1), 1e-14))
    return f0, 1 - b, lv


def hauteur(m, sr=SR):
    """La hauteur (pour information : c'est la PERSONNE et son style, on n'y touche pas) : la fondamentale médiane des trames voisées,
    son étendue (écart interquartile en demi-tons) et sa stabilité (la variation médiane d'une trame de 10 ms à la suivante, en
    cents, dans les notes tenues)."""
    f0, v, lv = suivre_f0(m, sr)
    voise = _voisees(f0, v, lv)
    if voise.sum() < 20:
        return {"f0_hz": None, "etendue_demi_tons": None, "stabilite_cents": None, "voise": round(float(voise.mean()), 2)}
    c = 1200 * np.log2(f0 / 100.0)
    q1, q3 = np.percentile(c[voise], (25, 75))
    dc = np.abs(np.diff(c))
    tenu = voise[1:] & voise[:-1] & (dc < 100)
    return {"f0_hz": round(float(np.median(f0[voise])), 1), "etendue_demi_tons": round(float(q3 - q1) / 100, 1),
            "f0_p10_hz": round(float(np.percentile(f0[voise], 10)), 1), "f0_p90_hz": round(float(np.percentile(f0[voise], 90)), 1),
            "stabilite_cents": round(float(np.median(dc[tenu])), 1) if tenu.any() else None, "voise": round(float(voise.mean()), 2)}


def _voisees(f0, v, lv):
    """Les trames voisées : YIN net (≥ 0,8) et la voix présente (à moins de 30 dB de son haut, 20 dB au-dessus de son fond)."""
    viv = lv[lv > -115]
    if len(viv) < 10:
        return np.zeros(len(f0), bool)
    fond, haut = float(np.percentile(viv, 3)), float(np.percentile(viv, 95))
    return (v >= 0.8) & (lv > max(fond + 20, haut - 30))


# ------------------------------------------------------------------------------------------------ l'enveloppe harmonique
def enveloppe(m, sr=SR, n=2048, f_max=10000.0, support=0.2):
    """L'ENVELOPPE moyenne d'une voix, sans sa hauteur : dans chaque trame voisée et chaque tiers d'octave, l'énergie de la bande
    divisée par le nombre d'harmoniques (k·f0) qui y tombent — l'énergie d'UNE harmonique, quelle que soit la hauteur —, puis la moyenne
    en puissance sur les trames. Une bande n'est « soutenue » que si au moins `support` des trames voisées y ont une harmonique
    (au-dessus de leur fondamentale, sous f_max) : sous la fondamentale d'une voix, il n'y a rien à comparer. (Le 14/11 : le spectre moyen d'un rap à
    155 Hz contre un chant à 330 Hz différait de +12 dB à 125 Hz et de −12 dB à 200 Hz, à cause des seules hauteurs ; une égalisation
    sur ce spectre aurait creusé la fondamentale de papa.) Rend {tiers_db (None où rien n'est soutenu), support, trames}."""
    m = np.asarray(m, np.float64)
    f0, v, lv = suivre_f0(m, sr)
    voise = _voisees(f0, v, lv)
    voise_idx = np.flatnonzero(voise)
    w = np.hanning(n)
    fr = np.fft.rfftfreq(n, 1 / sr)
    bords = [(c * 2 ** (-1 / 6), c * 2 ** (1 / 6)) for c in TIERS]
    bas = np.array([b0 for b0, _ in bords])
    hauts = np.array([b1 for _, b1 in bords])
    i_bas, i_hauts = np.searchsorted(fr, bas), np.searchsorted(fr, hauts)
    acc = np.zeros(len(TIERS))
    cnt = np.zeros(len(TIERS))
    pas = int(sr * 0.01)
    for k in voise_idx:
        centre = k * pas + int(sr * 0.02)
        a = centre - n // 2
        if a < 0 or a + n > len(m):
            continue
        X = np.abs(np.fft.rfft(m[a:a + n] * w)) ** 2
        if "ref_enveloppe" in P.COUPE:                   # témoin : le spectre moyen des trames voisées, hauteur comprise
            for i, (b0, b1) in enumerate(bords):
                sel = (fr >= b0) & (fr < b1)
                if sel.any():
                    acc[i] += X[sel].mean()
                    cnt[i] += 1
            continue
        # l'énergie de la bande PAR HARMONIQUE : (l'énergie de la bande) / (le nombre d'harmoniques k·f0 qui y tombent) ; une bande sous
        # la fondamentale n'en a aucune (rien à comparer). (Le 14/11 : le pic de chaque harmonique « nette » biaisait l'enveloppe d'une
        # voix grave de +3 à +5 dB vers 8 kHz, où ses harmoniques serrées et son vibrato se mêlent : une énergie, elle, ne se trie pas.)
        f = float(f0[k])
        c = np.concatenate([[0.0], np.cumsum(X)])
        e_b = c[i_hauts] - c[i_bas]
        nh = np.floor((hauts - 1e-9) / f) - np.ceil(bas / f) + 1
        nh = np.where(bas < 0.999 * f, np.floor((hauts - 1e-9) / f), nh)          # k ≥ 1
        dedans = (nh >= 1) & (hauts <= f_max * 2 ** (1 / 6))
        acc[dedans] += e_b[dedans] / nh[dedans]
        cnt[dedans] += 1
    tot = max(1, len(voise_idx))
    sup = cnt / tot
    out = [round(float(10 * math.log10(acc[i] / cnt[i])), 2) if sup[i] >= support and cnt[i] > 0 else None for i in range(len(TIERS))]
    # la forme : relative à la moyenne (en dB) des bandes soutenues entre 500 Hz et 4 kHz
    ref = [o for c, o in zip(TIERS, out) if o is not None and 500 <= c <= 4000]
    if not ref:
        return {"tiers_db": [None] * len(TIERS), "support": [round(float(s), 2) for s in sup], "trames": int(len(voise_idx))}
    r0 = float(np.mean(ref))
    return {"tiers_db": [None if o is None else round(o - r0, 2) for o in out], "support": [round(float(s), 2) for s in sup],
            "trames": int(len(voise_idx))}


# ------------------------------------------------------------------------------------------------ le profil d'une voix
def profil(x, sr=SR, avec_hauteur=True):
    """Tout ce qu'on mesure d'une voix (rien n'est changé). Les spectres sont des FORMES (relatives à l'énergie 100 Hz-10 kHz)."""
    m = P._mono(x)
    f, pa, pb = spectre_actif(m, sr)
    norme = 10 * math.log10(max(1e-30, _bande(f, pa, *NORME)))
    t = tiers_octave(f, pa) - norme
    tb = tiers_octave(f, pb) - norme
    c = np.array(TIERS, float)
    sel = (c >= 150) & (c <= 10000)
    pente = float(np.polyfit(np.log2(c[sel]), t[sel], 1)[0])
    zones = {k: round(10 * math.log10(max(1e-30, _bande(f, pa, a, b))) - norme, 1) for k, (a, b) in ZONES.items()}
    fond, haut = P.fond_et_voix(m, sr)
    out = {"tiers_db": [round(float(v), 2) for v in t], "bruit_tiers_db": [round(float(v), 2) for v in tb],
           "pente_db_oct": round(pente, 2), **{f"{k}_db": v for k, v in zones.items()},
           "fond_dbfs": round(fond, 1), "voix_dbfs": round(haut, 1), "ecart_fond_db": round(haut - fond, 1),
           "dynamique": dynamique(m, sr), "reverberation": reverberation(m, sr), "sifflantes": profil_sifflantes(m, sr),
           "enveloppe": enveloppe(m, sr)}
    if avec_hauteur:
        out["hauteur"] = hauteur(m, sr)
    return out


# ------------------------------------------------------------------------------------------------ l'égalisation d'appariement
def courbe_appariement(src, ref, borne_db=BORNE_DB, lissage_oct=1.0, marge_bruit_db=20.0):
    """La courbe (dB par tiers d'octave) qui amène l'ENVELOPPE de `src` vers celle de `ref` (deux profils) : la différence, seulement là
    où les deux voix ont des harmoniques (ailleurs : rien à comparer, la courbe y vaut 0, avec la moitié de sa voisine sur un tiers
    d'octave pour ne pas faire de marche) ; LISSÉE sur `lissage_oct` (une couleur de micro ou de pièce est large ; les formants d'une
    personne sont plus fins) ; BORNÉE à ±borne_db ; jamais une hausse dans une bande où la voix n'est pas à `marge_bruit_db` au-dessus
    de son propre bruit (on ne remonte pas le souffle)."""
    if _coupe("ref_enveloppe"):                          # témoin : le spectre moyen (la hauteur de chacun y passe pour une couleur)
        a = np.array(src["tiers_db"], float)
        b = np.array(ref["tiers_db"], float)
    else:
        a = np.array([np.nan if v is None else v for v in (src.get("enveloppe") or {}).get("tiers_db") or [None] * len(TIERS)], float)
        b = np.array([np.nan if v is None else v for v in (ref.get("enveloppe") or {}).get("tiers_db") or [None] * len(TIERS)], float)
    d = b - a
    connu = ~np.isnan(d)
    if not connu.any():
        return [0.0] * len(TIERS)
    k = max(1, int(round(lissage_oct * 3))) if not _coupe("ref_lissage") else 1
    lisse = np.zeros(len(d))
    for i in np.flatnonzero(connu):                      # la moyenne des bandes connues de la fenêtre (une octave)
        j0, j1 = max(0, i - k // 2), min(len(d), i + k - k // 2)
        lisse[i] = float(np.nanmean(d[j0:j1]))
    for i in np.flatnonzero(~connu):                     # un tiers d'octave de transition au bord du connu
        v = [lisse[j] for j in (i - 1, i + 1) if 0 <= j < len(d) and connu[j]]
        if v:
            lisse[i] = 0.5 * float(np.mean(v))
    d = lisse
    if not _coupe("ref_borne"):
        d = np.clip(d, -borne_db, borne_db)
    if not _coupe("ref_bruit"):
        snr = np.array(src["tiers_db"], float) - np.array(src.get("bruit_tiers_db") or [-200.0] * len(TIERS), float)
        d = np.minimum(d, np.maximum(0.0, snr - marge_bruit_db))
    return [round(float(v), 2) for v in d]


def _gain_de_f(courbe):
    """La courbe par tiers d'octave → un gain linéaire à chaque fréquence (interpolé en dB sur une échelle logarithmique, constant
    au-delà des bandes extrêmes)."""
    lc = np.log2(np.array(TIERS, float))
    g = np.array(courbe, float)

    def fn(f):
        lf = np.log2(np.maximum(f, 1.0))
        return 10 ** (np.interp(lf, lc, g) / 20)
    return fn


def egaliser(x, courbe, sr=SR):
    """La courbe appliquée par un filtre à phase nulle (la voix ne bouge pas dans le temps : aucun retard, aucune phase)."""
    x = P._2d(x)
    fn = _gain_de_f(courbe)
    return np.column_stack([P._filtre_fft(x[:, c], sr, fn) for c in range(x.shape[1])])


# ------------------------------------------------------------------------------------------------ les sifflantes
BANDE_S = (5000.0, 10000.0)


def _bande_s(m, sr):
    return P._filtre_fft(m, sr, lambda f: P._butter_mag(f, BANDE_S[0], 4, True) * P._butter_mag(f, BANDE_S[1], 4, False))


def _rapports_s(m, sr, pas_s=0.005, fen_s=0.01):
    """Pour chaque trame de 5 ms : (le niveau des sifflantes 5-10 kHz moins le niveau large de la voix lissé sur 100 ms, en dB ;
    le niveau des sifflantes)."""
    s = _bande_s(m, sr)
    ls = P.niveaux_db(s, sr, fen_s, pas_s)
    lt = P.niveaux_db(m, sr, 0.1, pas_s)
    k = min(len(ls), len(lt))
    lt = np.concatenate([np.full(int(0.045 / pas_s), lt[0]), lt])[:k]         # le niveau large centré sur la trame
    return ls[:k] - lt, ls[:k]


SEUIL_S = -9.0                                           # une trame « sifflante » : sa bande 5-10 kHz à moins de 9 dB du niveau large
QUANTILES_S = (50, 60, 70, 80, 90, 95, 98, 99.5)


def _sifflantes_vivantes(m, sr):
    r, ls = _rapports_s(np.asarray(m, np.float64), sr)
    fond, haut = P.fond_et_voix(m, sr)
    viv = ls > max(fond + 10, haut - 45)
    return r, viv


def profil_sifflantes(m, sr=SR):
    """Les sifflantes d'une voix : leur PART (les trames vivantes où la bande 5-10 kHz est à moins de 9 dB du niveau large : un « s »,
    un « ch », un « f ») et leur FORCE (les centiles de ce rapport sur ces trames-là seulement). (Le 14/11 : le rap de papa a 24 % de
    trames sifflantes, le chant de Hakim 9 % ; à force égale, la part est le style — le rap a plus de consonnes —, seule la force est
    une affaire de micro et de traitement.)"""
    r, viv = _sifflantes_vivantes(m, sr)
    sib = viv & (r > SEUIL_S)
    if viv.sum() < 20 or sib.sum() < 10:
        return {"part": round(float(sib.sum() / max(1, viv.sum())), 3), "p50_db": None, "p90_db": None, "quantiles_db": None}
    q = np.percentile(r[sib], QUANTILES_S)
    return {"part": round(float(sib.sum() / viv.sum()), 3), "p50_db": round(float(q[0]), 2), "p90_db": round(float(q[4]), 2),
            "quantiles_db": [round(float(v), 2) for v in q]}


def deesser_vers(x, ref_sifflantes, sr=SR, pas_s=0.005, max_db=12.0, passes=3):
    """Le dé-esseur à bande partagée, calé sur la FORCE des sifflantes de la référence : chaque trame sifflante est ramenée, par
    appariement des centiles (sa place parmi les sifflantes de la voix → la valeur de la référence à la même place), jamais remontée,
    au plus max_db. La bande 5-10 kHz est séparée par un filtre à phase nulle (bande + reste = la voix exacte) ; seule la bande
    baisse ; gains lissés sur 15 ms. Trois passes, les centiles remesurés à chaque fois (baisser la bande baisse aussi un peu le
    niveau large auquel on la compare). Rend (voix, baisse max)."""
    x = P._2d(x)
    q_ref = np.array((ref_sifflantes or {}).get("quantiles_db") or [], float)
    if not len(q_ref):
        return x.copy(), 0.0
    m = P._mono(x)
    r, viv = _sifflantes_vivantes(m, sr)
    sib = viv & (r > SEUIL_S)
    if sib.sum() < 10:
        return x.copy(), 0.0
    bandes = [_bande_s(x[:, c], sr) for c in range(x.shape[1])]
    p = int(sr * pas_s)
    t = (np.arange(len(m)) - p) / p                      # le centre de chaque trame de 10 ms
    total = np.zeros(len(r))
    y = x
    for _ in range(passes):
        rc, _ = _sifflantes_vivantes(P._mono(y), sr)
        rc = np.concatenate([rc, np.full(max(0, len(r) - len(rc)), -99.0)])[: len(r)]
        q_src = np.percentile(rc[sib], QUANTILES_S) + np.arange(len(QUANTILES_S)) * 1e-6
        cible = np.interp(rc, q_src, q_ref, left=q_ref[0], right=q_ref[-1])
        total = np.clip(total + np.where(sib, np.minimum(0.0, cible - rc), 0.0), -max_db, 0.0)
        w = 3
        g = np.convolve(np.pad(-total, (w, w), mode="edge"), np.ones(2 * w + 1) / (2 * w + 1), "valid")
        lin = 10 ** (-np.interp(t, np.arange(len(g)), g) / 20)
        y = np.column_stack([x[:, c] - bandes[c] + bandes[c] * lin for c in range(x.shape[1])])
    return y, round(float(-total.min()), 1)


# ------------------------------------------------------------------------------------------------ le calage (l'étape audio)
def caler(x, ref, sr=SR, reglages=None, journal=None):
    """Une voix (déjà nettoyée par studio_pro.traiter) calée sur un profil de référence : l'égalisation d'appariement, puis les
    sifflantes ramenées au niveau de la référence. Rend (voix, rapport). La dynamique, l'espace et le niveau se calent au mix
    (studio_projet.mixer_auto), sur le rendu."""
    r = dict(reglages or {})
    say = journal or (lambda s: None)
    x = P._2d(x)
    src = profil(x, sr, avec_hauteur=False)
    rapport = {"avant": _resume_profil(src), "reference": _resume_profil(ref)}
    y = x
    if r.get("ref_egaliseur", "auto") != "non" and not _coupe("ref_egaliseur"):
        courbe = courbe_appariement(src, ref, float(r.get("ref_borne_db", BORNE_DB)))
        y = egaliser(y, courbe, sr)
        rapport["courbe_db"] = courbe
        say(f"égaliseur d'appariement : {', '.join(f'{c}:{v:+.1f}' for c, v in zip(TIERS, courbe) if abs(v) >= 1)}")
    rs = ref.get("sifflantes") or {}
    if rs.get("quantiles_db") and r.get("ref_sifflantes", "auto") != "non" and not _coupe("ref_sifflantes"):
        avant_s = profil_sifflantes(P._mono(y), sr)
        y, mx = deesser_vers(y, rs, sr)
        rapport["sifflantes"] = {"reference_p90_db": rs.get("p90_db"), "avant_p90_db": avant_s.get("p90_db"),
                                 "apres_p90_db": profil_sifflantes(P._mono(y), sr).get("p90_db"), "baisse_max_db": mx}
    apres = profil(y, sr, avec_hauteur=False)
    rapport["apres"] = _resume_profil(apres)
    rapport["distance_db"] = {"avant": distance_spectrale(src, ref), "apres": distance_spectrale(apres, ref)}
    return y, rapport


def distance_spectrale(a, b, de=100, a_=10000, enveloppe_=True):
    """L'écart moyen (dB, valeur absolue) entre deux voix, par tiers d'octave de 100 Hz à 10 kHz : sur leurs ENVELOPPES, là où les deux
    sont connues (enveloppe_), sinon sur leurs spectres moyens. Les deux formes sont d'abord recentrées (l'écart moyen retiré : un
    niveau n'est pas une couleur)."""
    c = np.array(TIERS, float)
    if enveloppe_ and a.get("enveloppe") and b.get("enveloppe"):
        x = np.array([np.nan if v is None else v for v in a["enveloppe"]["tiers_db"]], float)
        y = np.array([np.nan if v is None else v for v in b["enveloppe"]["tiers_db"]], float)
    else:
        x, y = np.array(a["tiers_db"], float), np.array(b["tiers_db"], float)
    sel = (c >= de) & (c <= a_) & ~np.isnan(x) & ~np.isnan(y)
    if not sel.any():
        return None
    d = x[sel] - y[sel]
    return round(float(np.abs(d - d.mean()).mean()), 2)


def _resume_profil(p):
    return {k: p.get(k) for k in ("pente_db_oct", "boue_db", "presence_db", "sifflantes_db", "air_db", "fond_dbfs", "ecart_fond_db")}


# ------------------------------------------------------------------------------------------------ le profil de référence gardé
def ecrire_profil(chemin, prof, source="", reglages_tranche=None, ecart_lu=None, cibles=None):
    """Un profil de référence gardé (JSON) : le profil mesuré de la voix nettoyée, la tranche de la référence (ses réglages de mix),
    ses cibles au mix (densité, sifflantes et espace mesurés sur le rendu de la piste seule) et son niveau au-dessus de l'instru."""
    d = {"version": VERSION, "t": time.time(), "source": str(source)[:200], "profil": prof,
         "tranche": reglages_tranche or {}, "ecart_lu": ecart_lu, "cibles": cibles or {}}
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, default=float), encoding="utf-8")
    tmp.replace(chemin)
    return d


def lire_profil(chemin):
    try:
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("profil"), dict) and d["profil"].get("tiers_db") else None


# ------------------------------------------------------------------------------------------------ au mix : ce qu'on mesure sur un rendu
def mesure_mix(x, sr=SR, fins=None):
    """Ce que le calage au mix compare sur le rendu d'une piste seule : sa densité (dynamique), la force de ses sifflantes et son
    espace (la traîne après les fins de phrase ; fins : celles de son rendu sec). Rend aussi ses fins de phrase (« _fins »)."""
    m = P._mono(x)
    if fins is None:
        fins = fins_de_phrase(m, sr)[1]
        if len(fins) < 3:                                # une voix déjà mouillée (une référence née avec sa réverbération) : elle
            fins = fins_de_phrase(m, sr, chute_db=12.0)[1]       # ne retombe pas de 20 dB en 250 ms ; 12 dB suffisent pour la repérer
    return {"dynamique": dynamique(m, sr), "sifflantes": profil_sifflantes(m, sr), "reverberation": reverberation(m, sr, fins=fins),
            "_fins": [int(i) for i in fins]}


def chercher(mesurer, lo, hi, cible, croissant, essais=6, tolerance=0.3):
    """Une recherche par dichotomie d'un réglage (entre lo et hi) dont la mesure varie dans un sens connu (croissant : la mesure monte
    avec le réglage) : le réglage dont la mesure tombe le plus près de la cible. Rend (réglage, mesure, [(réglage, mesure)])."""
    vus = []

    def m(v):
        r = mesurer(v)
        vus.append((round(float(v), 3), None if r is None else round(float(r), 2)))
        return r
    a, b = float(lo), float(hi)
    ma, mb = m(a), m(b)
    if ma is None or mb is None:
        return a, ma, vus
    # la cible hors d'atteinte : le bout le plus proche
    if (cible - ma) * (cible - mb) > 0:
        return (a, ma, vus) if abs(ma - cible) <= abs(mb - cible) else (b, mb, vus)
    meilleur = min(((a, ma), (b, mb)), key=lambda t: abs(t[1] - cible))
    for _ in range(max(0, essais - 2)):
        c = (a + b) / 2
        mc = m(c)
        if mc is None:
            break
        if abs(mc - cible) < abs(meilleur[1] - cible):
            meilleur = (c, mc)
        if abs(mc - cible) <= tolerance:
            break
        if (mc < cible) == croissant:
            a = c
        else:
            b = c
    return meilleur[0], meilleur[1], vus


def _hz(t):
    return f"{t} Hz" if t < 1000 else f"{t / 1000:g} kHz".replace(".", ",")


def resume(rap):
    """Le calage d'une voix en mots courts (l'étape audio, et ce qu'en a fait le mix s'il est là)."""
    if not rap:
        return ""
    mots = []
    c = rap.get("courbe_db")
    if c:
        forts = sorted(((v, t) for t, v in zip(TIERS, c) if abs(v) >= 1.5), key=lambda z: -abs(z[0]))[:3]
        if forts:
            mots.append("égaliseur d'appariement " + ", ".join(f"{v:+.0f} dB à {_hz(t)}" for v, t in sorted(forts, key=lambda z: z[1])))
    s = rap.get("sifflantes")
    if s and s.get("baisse_max_db"):
        mots.append(f"sifflantes ramenées à la force de la référence (jusqu'à −{s['baisse_max_db']:.0f} dB)")
    d = rap.get("distance_db")
    if d:
        mots.append(f"écart d'enveloppe à la référence {d['avant']} → {d['apres']} dB")
    src = rap.get("source")
    return f"calée sur {src or 'la référence'} : " + (", ".join(mots) if mots else "rien à corriger")
