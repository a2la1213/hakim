"""Le banc à VÉRITÉ CONNUE de la chaîne studio pro (13/11) : une voix propre, dégradée de façon connue (bruit rose à plusieurs niveaux,
50 Hz et ses harmoniques, clics de bouche, plosives, écrêtage, respirations fortes, continu, niveau qui varie), puis l'écart à la voix
propre mesuré (SI-SDR) avant et après CHAQUE étape seule, et après la chaîne entière en « auto ». Une voix propre passée dans la
chaîne doit rester presque intacte.

La voix propre : un fichier (une prise propre, une voix de Hakim) ou une voix CHANTÉE de synthèse (notes tenues, vibrato, formants,
sifflantes) pour les tests. Les dégradations sont déterministes (graine).

usage : python studio_pro_banc.py voix.wav [--debruiteurs wiener,afftdn,deepfilternet] [--sortie banc.json] [--duree 40]
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
import studio_pro as P  # noqa: E402

SR = P.SR


# ------------------------------------------------------------------------------------------------ une voix chantée de synthèse
def _formants(f, voyelle):
    F = {"a": ((750, 90), (1200, 110), (2600, 160), (3400, 200)), "o": ((500, 80), (850, 100), (2500, 150), (3300, 200)),
         "i": ((300, 60), (2300, 120), (3000, 170), (3700, 200)), "e": ((450, 70), (1950, 110), (2600, 160), (3400, 200))}[voyelle]
    g = np.zeros_like(f, dtype=np.float64)
    for fc, bw in F:
        g += 1.0 / np.sqrt((1 - (f / fc) ** 2) ** 2 + (f * bw / fc ** 2) ** 2)
    return g * (1.0 / (1 + (f / 4000.0) ** 2))


def voix_chantee(duree=12.0, sr=SR, graine=3, homme=True):
    """Une voix chantée propre : des phrases de 1,6 à 2,6 s (notes de 0,3 à 0,6 s, glissés de 30 ms, vibrato de 5,5 Hz après 150 ms,
    voyelles à formants), une sifflante au début de chaque phrase, des silences de 0,5 à 0,9 s, un fond à −100 dBFS. Stéréo (mono
    recopié), crête à −6 dBFS. Rend (voix, phrases [(a, b)] en secondes)."""
    rng = np.random.default_rng(graine)
    n = int(duree * sr)
    t = np.arange(n) / sr
    notes = (98, 110, 123, 131, 147, 165, 196) if homme else (196, 220, 247, 262, 294, 330, 392)
    f0 = np.zeros(n)
    env = np.zeros(n)
    voy = np.empty(n, dtype="<U1")
    voy[:] = "a"
    sif = np.zeros(n)
    phr = []
    pos = 0.5
    while pos < duree - 1.0:
        L = min(rng.uniform(1.6, 2.6), duree - 0.5 - pos)
        a, b = pos, pos + L
        phr.append((a, b))
        s = a
        while s < b:
            d = min(rng.uniform(0.3, 0.6), b - s)
            i0, i1 = int(s * sr), int((s + d) * sr)
            f0[i0:i1] = rng.choice(notes)
            voy[i0:i1] = rng.choice(list("aoie"))
            env[i0:i1] = rng.uniform(0.75, 1.0)
            s += d
        i0, i1 = int(a * sr), int(b * sr)
        k = np.arange(i1 - i0) / sr
        env[i0:i1] *= np.minimum(1, k / 0.04) * np.minimum(1, (L - k) / 0.08)
        ns = int(0.07 * sr)                              # la sifflante d'attaque (5-9 kHz)
        sif[i0:i0 + ns] = 0.18 * np.hanning(ns)
        pos = b + rng.uniform(0.5, 0.9)
    # glissés de 30 ms entre les notes (les silences tiennent la note voisine : aucune glissade depuis zéro) et vibrato
    w = int(0.03 * sr)
    on = np.flatnonzero(f0 > 0)
    plein = np.interp(np.arange(n), on, f0[on])
    f0s = np.convolve(np.pad(plein, (w, w), mode="edge"), np.ones(w) / w, "same")[w:-w]
    # l'âge de chaque note (pour le vibrato tardif) : remis à zéro à chaque changement de hauteur
    ages = np.zeros(n)
    chg = np.flatnonzero(np.diff(f0, prepend=0) != 0)
    bornes = np.concatenate([chg, [n]])
    for a, b in zip(bornes[:-1], bornes[1:]):
        ages[a:b] = np.arange(b - a) / sr
    vib = np.where(ages > 0.15, 0.25 * np.sin(2 * np.pi * 5.5 * t), 0.0)            # ±25 cents
    f = f0s * 2 ** (vib / 12)
    phase = 2 * np.pi * np.cumsum(f) / sr
    y = np.zeros(n)
    for v in "aoie":
        sel = voy == v
        if not sel.any():
            continue
        for k in range(1, 60):
            fk = k * f
            amp = np.where(fk < 10000, _formants(fk, v), 0.0) / k ** 0.5
            y += np.where(sel, amp * np.sin(k * phase), 0.0)
    y *= env * (f0 > 0)
    bruit = rng.standard_normal(n)
    hf = P._filtre_fft(bruit, sr, lambda fr: P._butter_mag(fr, 5000.0, 4, True) * P._butter_mag(fr, 9000.0, 4, False))
    y = y / (np.abs(y).max() + 1e-12) + sif * hf / (np.abs(hf).max() + 1e-12)
    y = 0.5 * y / np.abs(y).max()
    y += 10 ** (-100 / 20) * rng.standard_normal(n)
    return np.column_stack([y, y]), phr


# ------------------------------------------------------------------------------------------------ les dégradations connues
def _niveau_voix(x, sr=SR):
    m = P._mono(x)
    l = P.niveaux_db(m, sr)
    return float(np.percentile(l[l > -115], 90)) if (l > -115).any() else -40.0


def bruit_rose(n, graine=1, canaux=2):
    rng = np.random.default_rng(graine)
    w = rng.standard_normal((n, canaux))
    out = np.empty_like(w)
    for c in range(canaux):
        X = np.fft.rfft(w[:, c])
        f = np.arange(len(X), dtype=np.float64)
        f[0] = 1
        out[:, c] = np.fft.irfft(X / np.sqrt(f), n)
    return out / out.std()


def avec_bruit(x, snr_db, graine=1):
    """Du bruit rose, snr_db sous le niveau haut de la voix (90e centile de ses trames de 20 ms)."""
    b = bruit_rose(len(x), graine, x.shape[1])
    return x + b * 10 ** ((_niveau_voix(x) - snr_db) / 20)


def avec_ronflement(x, niveau_db=-45.0, f=50.0, sr=SR):
    """Le secteur : f et ses harmoniques (−6 dB par harmonique, les impaires plus fortes), sa fréquence qui dérive de ±0,05 Hz."""
    t = np.arange(len(x)) / sr
    fi = f + 0.05 * np.sin(2 * np.pi * t / 20)
    ph = 2 * np.pi * np.cumsum(fi) / sr
    h = np.zeros(len(x))
    for k, g in ((1, 0), (2, -8), (3, -4), (4, -14), (5, -9), (6, -18), (7, -14), (9, -18)):
        h += 10 ** (g / 20) * np.sin(k * ph + 0.7 * k)
    h *= 10 ** (niveau_db / 20) / (np.abs(h).max() + 1e-12)
    return x + h[:, None]


def avec_clics(x, nombre=12, graine=4, sr=SR, phrases_s=None):
    """Des clics de bouche : des bouffées de 0,3 à 1 ms (bruit blanc qui décroît), 0,2 à 0,5 de la crête. Là où la bouche les fait :
    deux sur trois entre les phrases ou à leurs bords (±150 ms), un sur trois n'importe où (phrases_s connues ; sinon partout)."""
    rng = np.random.default_rng(graine)
    y = x.copy()
    pic = np.abs(x).max()
    pos = []
    duree = len(x) / sr
    for j in range(nombre):
        if phrases_s and j % 3 != 2:
            a, b = phrases_s[int(rng.integers(len(phrases_s)))]
            t = rng.choice([rng.uniform(a - 0.3, a + 0.15), rng.uniform(b - 0.15, b + 0.3)])
        else:
            t = rng.uniform(0.2, duree - 0.2)
        i = int(min(max(t, 0.05), duree - 0.05) * sr)
        L = int(rng.uniform(0.0003, 0.001) * sr)
        c = rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 3)) * rng.uniform(0.2, 0.5) * pic
        y[i:i + L] += c[:, None]
        pos.append(i)
    return y, pos


def avec_plosives(x, phrases_s, sr=SR, niveau=0.8):
    """Une plosive au début de chaque phrase : une bouffée de grave (40-70 Hz) de 60-90 ms, à `niveau` de la crête de la voix."""
    y = x.copy()
    pic = np.abs(x).max()
    rng = np.random.default_rng(7)
    for a, _ in phrases_s:
        i = int(a * sr)
        L = int(rng.uniform(0.06, 0.09) * sr)
        t = np.arange(L) / sr
        f = rng.uniform(40, 70)
        c = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.025) * (1 - np.exp(-t / 0.003)) * niveau * pic * 2.2
        y[i:i + L] += c[:, None]
    return y


def ecreter(x, part=0.4):
    """Écrêté (dur) à `part` de sa crête."""
    p = np.abs(x).max() * part
    return np.clip(x, -p, p)


def respiration(L, sr, graine):
    rng = np.random.default_rng(graine)
    n = int(L * sr)
    b = rng.standard_normal(n)
    b = P._filtre_fft(b, sr, lambda f: P._butter_mag(f, 600.0, 2, True) * P._butter_mag(f, 3000.0, 2, False))
    env = np.sin(np.pi * np.arange(n) / n) ** 1.5
    return b / (b.std() + 1e-12) * env


def avec_respirations(x, phrases_s, niveau_db=-14.0, sr=SR, graine=11):
    """Une respiration de 250 à 400 ms juste avant chaque phrase (sauf la première), niveau_db sous le niveau de la voix."""
    y = x.copy()
    nv = _niveau_voix(x)
    rng = np.random.default_rng(graine)
    for j, (a, _) in enumerate(phrases_s[1:]):
        L = rng.uniform(0.25, 0.4)
        i = int((a - L - 0.06) * sr)
        r = respiration(L, sr, graine + j) * 10 ** ((nv + niveau_db) / 20)
        y[i:i + len(r)] += r[:, None]
    return y


def avec_continu(x, v=0.05):
    return x + v


def avec_niveau_qui_varie(x, plage_db=6.0, periode_s=4.0, sr=SR):
    t = np.arange(len(x)) / sr
    return x * (10 ** (plage_db * np.sin(2 * np.pi * t / periode_s) / 20))[:, None]


# ------------------------------------------------------------------------------------------------ le banc
def _seul(etape, **extra):
    """Des réglages où seule `etape` est en « auto » (les autres coupées)."""
    return {"actif": True, **{e: ("auto" if e == etape else "non") for e in P.ETAPES}, **extra}


def cas(voix, phrases_s, sr=SR):
    """Les cas du banc : (nom, étape visée, dégradée, vérité). La vérité de « respirations » garde des respirations naturelles
    (−30 dB) : elles doivent BAISSER vers elles, pas disparaître."""
    out = []
    for snr in (30, 20, 10):
        out.append((f"bruit rose {snr} dB", "souffle", avec_bruit(voix, snr), voix))
    out.append(("ronflement 50 Hz", "ronflement", avec_ronflement(voix, -42), voix))
    c, pos = avec_clics(voix, phrases_s=phrases_s)
    out.append(("clics", "clics", c, voix, pos))
    out.append(("plosives", "plosives", avec_plosives(voix, phrases_s), voix))
    out.append(("écrêtage 70 %", "ecretage", ecreter(voix, 0.7) / 0.7, voix))
    out.append(("écrêtage 40 % (sévère)", "ecretage", ecreter(voix, 0.4) / 0.4, voix))
    ref = avec_respirations(voix, phrases_s, -30)
    out.append(("respirations fortes", "respirations", avec_respirations(voix, phrases_s, -12), ref))
    out.append(("continu", "continu", avec_continu(voix), voix))
    out.append(("niveau qui varie", "nivellement", avec_niveau_qui_varie(voix), voix))
    return out


def lancer(voix, phrases_s, debruiteurs=("wiener",), sr=SR, journal=print):
    """Le banc entier sur une voix propre : rend un dict de résultats (SI-SDR avant / après l'étape seule / après la chaîne auto)."""
    res = {"cas": [], "propre": {}}
    for nom, etape, deg, ref, *pos in cas(voix, phrases_s, sr):
        avant = P.si_sdr(ref, deg)
        lignes = {"cas": nom, "etape": etape, "avant_db": avant}
        for dn in (debruiteurs if etape == "souffle" else ("auto",)):
            t0 = time.time()
            y, rap = P.traiter(deg, sr, _seul(etape, debruiteur=dn))
            lignes[f"apres_{dn}_db" if etape == "souffle" else "apres_db"] = P.si_sdr(ref, y)
            lignes["active"] = bool((rap.get(etape) or {}).get("actif"))
            if pos:                                      # les clics : l'erreur AUTOUR des clics ajoutés (±5 ms), avant/après
                w = int(0.005 * sr)
                sel = np.zeros(len(ref), bool)
                for i in pos[0]:
                    sel[max(0, i - w): i + w] = True
                ea = float(((deg - ref)[sel] ** 2).sum())
                eb = float(((y - ref)[sel] ** 2).sum())
                lignes["clics_erreur_locale_db"] = round(10 * math.log10(max(eb, 1e-20) / max(ea, 1e-20)), 1)
                lignes["clics_trouves"] = (rap.get("clics") or {}).get("mesure", {}).get("clics")
            lignes[f"latence_{dn}"] = P.decalage_echantillons(ref, y, 200)
            lignes[f"calcul_{dn}_s"] = round(time.time() - t0, 1)
        y, rap = P.traiter(deg, sr, {"actif": True, "debruiteur": debruiteurs[0], "nivellement": "auto" if etape == "nivellement" else "non"})
        lignes["chaine_auto_db"] = P.si_sdr(ref, y)
        lignes["chaine_etapes"] = [e for e in P.ETAPES if (rap.get(e) or {}).get("actif")]
        journal(json.dumps(lignes, ensure_ascii=False))
        res["cas"].append(lignes)
    # la voix propre : le NETTOYAGE seul (tout en « auto », sans le nivellement, qui est une modif voulue), puis avec
    y, rap = P.traiter(voix, sr, {"actif": True, "debruiteur": debruiteurs[0], "nivellement": "non"})
    res["propre"] = {"si_sdr_db": P.si_sdr(voix, y), "etapes": [e for e in P.ETAPES if (rap.get(e) or {}).get("actif")]}
    y2, rap2 = P.traiter(voix, sr, {"actif": True, "debruiteur": debruiteurs[0]})
    n0, n1 = P.mesure_nivellement(voix), P.mesure_nivellement(y2)
    res["propre"]["avec_nivellement_si_sdr_db"] = P.si_sdr(voix, y2)
    res["propre"]["niveau_ecart_type_db"] = [n0.get("ecart_type_db"), n1.get("ecart_type_db")]
    journal("PROPRE " + json.dumps(res["propre"], ensure_ascii=False))
    return res


if __name__ == "__main__":
    import argparse
    import studio_mesures as M
    a = argparse.ArgumentParser()
    a.add_argument("voix", nargs="?", default="")
    a.add_argument("--debruiteurs", default="wiener,afftdn")
    a.add_argument("--sortie", default="")
    a.add_argument("--debut", type=float, default=0.0)
    a.add_argument("--duree", type=float, default=40.0)
    o = a.parse_args()
    if o.voix:
        x, _ = M.lire(o.voix, SR, 2, o.debut, o.duree)
        ph = [(a0, b0) for a0, b0 in P.phrases(x, SR)]
    else:
        x, ph = voix_chantee(20.0)
    r = lancer(x, ph, tuple(o.debruiteurs.split(",")))
    r["voix"] = o.voix or "synthèse"
    if o.sortie:
        Path(o.sortie).write_text(json.dumps(r, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------------------------------------ (14/11) le calage sur la référence
# Ahmed (14/11) : « j'aimerais juste que les mix [de ma voix] soient aussi bien que sa voix ». Le banc colore une voix propre avec des
# courbes CONNUES (un micro, une pièce), puis vérifie que le calage (studio_pro_reference) les retire : la courbe appliquée contre la
# vraie (−C), l'écart d'enveloppe et le SI-SDR contre la voix propre ; une voix propre calée sur elle-même ne bouge pas ; les
# sifflantes renforcées reviennent à leur force.
def courbe_micro(f):
    """Un micro « proche » connu (dB) : la présence creusée (−4 dB vers 3 kHz, large), un excès d'aigus (+5 dB au-dessus de 6 kHz)."""
    lf = np.log2(np.maximum(f, 1.0))
    return -4.0 * np.exp(-0.5 * ((lf - math.log2(3000)) / 0.6) ** 2) + 5.0 / (1 + np.exp(-(lf - math.log2(6500)) * 4))


def courbe_piece(f):
    """Une pièce « boîte » connue (dB) : +5 dB de boue vers 400 Hz (large), −2 dB vers 1,5 kHz."""
    lf = np.log2(np.maximum(f, 1.0))
    return 5.0 * np.exp(-0.5 * ((lf - math.log2(400)) / 0.5) ** 2) - 2.0 * np.exp(-0.5 * ((lf - math.log2(1500)) / 0.5) ** 2)


def colorer(x, courbe, sr=SR):
    """Une voix passée dans une courbe connue (dB, fonction des fréquences), à phase nulle."""
    x = P._2d(x)
    return np.column_stack([P._filtre_fft(x[:, c], sr, lambda f: 10 ** (courbe(f) / 20)) for c in range(x.shape[1])])


def renforcer_sifflantes(x, gain_db=6.0, sr=SR):
    """Les sifflantes plus fortes de gain_db : la bande 5-10 kHz relevée seulement dans les trames sifflantes (une prise trop
    brillante, un micro qui siffle)."""
    import studio_pro_reference as R
    x = P._2d(x)
    m = P._mono(x)
    r, viv = R._sifflantes_vivantes(m, sr)
    sib = (viv & (r > R.SEUIL_S)).astype(float)
    sib = np.convolve(sib, np.ones(5) / 5, "same")
    p = int(sr * 0.005)
    t = (np.arange(len(m)) - p) / p
    g = 10 ** (gain_db * np.interp(t, np.arange(len(sib)), sib) / 20)
    out = np.empty_like(x)
    for c in range(x.shape[1]):
        b = R._bande_s(x[:, c], sr)
        out[:, c] = x[:, c] - b + b * g
    return out


def erreur_de_courbe(appliquee, vraie, de=250, a_=8000):
    """L'écart moyen (dB) entre la courbe appliquée (par tiers d'octave) et la vraie correction (−C), sur les bandes de de à a_ Hz,
    niveau retiré (une courbe et la même plus 1 dB sont la même couleur)."""
    import studio_pro_reference as R
    c = np.array(R.TIERS, float)
    sel = (c >= de) & (c <= a_)
    d = np.array(appliquee, float)[sel] - np.array(vraie, float)[sel]
    return round(float(np.abs(d - d.mean()).mean()), 2)


def banc_reference(voix, ref=None, sr=SR, journal=print):
    """Le banc du calage sur une voix propre (et une référence propre ; sans elle, la voix elle-même) : chaque coloration connue, la
    courbe appliquée contre la vraie, l'écart d'enveloppe et le SI-SDR avant/après ; la voix propre calée ; les sifflantes."""
    import studio_pro_reference as R
    ref = voix if ref is None else ref
    pr = R.profil(ref, sr)
    c = np.array(R.TIERS, float)
    res = {"cas": []}
    for nom, courbe in (("micro", courbe_micro), ("pièce", courbe_piece), ("micro + pièce", lambda f: courbe_micro(f) + courbe_piece(f))):
        deg = colorer(voix, courbe, sr)
        y, rap = R.caler(deg, pr, sr)
        vraie = [-float(courbe(np.array([fc]))[0]) for fc in c]
        l = {"cas": nom, "erreur_courbe_db": erreur_de_courbe(rap.get("courbe_db") or [0] * len(c), vraie),
             "sans_calage_db": erreur_de_courbe([0] * len(c), vraie), "distance_db": rap["distance_db"],
             "si_sdr_avant_db": P.si_sdr(voix, deg), "si_sdr_apres_db": P.si_sdr(voix, y)}
        journal(json.dumps(l, ensure_ascii=False))
        res["cas"].append(l)
    y, rap = R.caler(voix, R.profil(voix, sr), sr)
    res["propre"] = {"si_sdr_db": P.si_sdr(voix, y), "courbe_max_db": max(abs(v) for v in rap.get("courbe_db") or [0])}
    journal("PROPRE " + json.dumps(res["propre"], ensure_ascii=False))
    pv = R.profil(voix, sr, avec_hauteur=False)
    if (pv["sifflantes"] or {}).get("quantiles_db"):
        deg = renforcer_sifflantes(voix, 6.0, sr)
        y, rap = R.caler(deg, pv, sr, reglages={"ref_egaliseur": "non"})
        s = {"vraie_p90_db": pv["sifflantes"]["p90_db"], "renforcee_p90_db": R.profil_sifflantes(P._mono(deg), sr)["p90_db"],
             "apres_p90_db": R.profil_sifflantes(P._mono(y), sr)["p90_db"], "si_sdr_avant_db": P.si_sdr(voix, deg),
             "si_sdr_apres_db": P.si_sdr(voix, y)}
        res["sifflantes"] = s
        journal("SIFFLANTES " + json.dumps(s, ensure_ascii=False))
    return res


def voix_rappee(duree=12.0, sr=SR, graine=8):
    """Une voix « rappée » de synthèse : des syllabes rapides (une consonne sifflante de 50 à 90 ms — bruit 4,5-10 kHz — puis une voyelle
    de 120 à 220 ms, fondamentale 135 à 175 Hz), en phrases de 1,5 à 2,5 s séparées de silences de 0,4 à 0,7 s. Stéréo, crête −6 dBFS.
    Rend (voix, phrases [(a, b)] en secondes)."""
    rng = np.random.default_rng(graine)
    n = int(duree * sr)
    y = np.zeros(n)
    phr = []
    pos = 0.4
    bruit = P._filtre_fft(rng.standard_normal(n), sr, lambda f: P._butter_mag(f, 4500.0, 4, True) * P._butter_mag(f, 10000.0, 4, False))
    bruit /= np.abs(bruit).max() + 1e-12
    while pos < duree - 1.0:
        L = min(rng.uniform(1.5, 2.5), duree - 0.5 - pos)
        a, b = pos, pos + L
        phr.append((a, b))
        s = a
        while s < b - 0.2:
            cs = rng.uniform(0.05, 0.09)
            i0, i1 = int(s * sr), int((s + cs) * sr)
            y[i0:i1] += 0.35 * np.hanning(i1 - i0) * bruit[i0:i1] * rng.uniform(0.7, 1.0)
            s += cs
            dv = min(rng.uniform(0.12, 0.22), b - s)
            i0, i1 = int(s * sr), int((s + dv) * sr)
            t = np.arange(i1 - i0) / sr
            f0 = rng.uniform(135, 175) * (1 + 0.04 * np.sin(2 * np.pi * 3 * t))
            ph = 2 * np.pi * np.cumsum(f0) / sr
            v = rng.choice(list("aoie"))
            seg = np.zeros(i1 - i0)
            for k in range(1, 50):
                fk = k * f0
                seg += np.where(fk < 9000, _formants(fk, v), 0.0) / k ** 0.5 * np.sin(k * ph)
            env = np.minimum(1, t / 0.015) * np.minimum(1, (dv - t) / 0.03)
            y[i0:i1] += seg / (np.abs(seg).max() + 1e-12) * env * rng.uniform(0.6, 1.0)
            s += dv
        pos = b + rng.uniform(0.4, 0.7)
    y = 0.5 * y / np.abs(y).max()
    y += 10 ** (-100 / 20) * rng.standard_normal(n)
    return np.column_stack([y, y]), phr
