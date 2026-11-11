"""L'AUTOTUNE DE HAKIM, refait (11/11 ~05:20, Ahmed : « il faut améliorer son autotune : même le léger part en steak » ; le 09/11 déjà :
« ça fait trop voix métallique, t'as poussé au max, il faut le bon équilibre »).

Ce qui faisait « steak » (mesuré le 11/11 sur trois de ses chansons, voix séparées par Demucs, extraits de 30 s ; chiffres dans le commit) :
 1. IL N'Y AVAIT PAS DE LÉGER. `autotune` était un oui/non ; ses mots « autotune léger » allaient dans le style, et « oui » recalait chaque
    trame de 5 ms à 100 % sur la note (chant.caler, force 1, sans vitesse de correction) : des marches entre les notes (118 à 288 sauts de
    plus de 50 cents en 10 ms par minute, contre 24 à 66 d'origine), le vibrato effacé (2,3-2,8 cents contre 6,3-6,5) ;
 2. WORLD (dio + CheapTrick + D4C) re-synthétisait TOUTE la voix séparée, même là où rien ne bougeait : rien qu'analysée puis refaite, la
    hauteur suivait les erreurs de dio (écart à la tendance des notes 48-58 cents contre 15-25), les consonnes et le souffle refabriqués
    (7,7-8,1 dB d'écart spectral), l'enveloppe lissée (0,9 dB) ;
 3. dio voyait des notes dans les consonnes et le souffle (6 à 14 % de ses trames voisées n'ont pas de période nette) et se trompait
    d'octave (2 à 8 % contre Harvest) ; rien ne le vérifiait ;
 4. la gamme dite (celle d'ACE-Step) laissait 13 à 16 % des notes tenues dehors : recalées dans la gamme, d'un demi-ton entier ;
 5. plausible, pas prouvé : l'étiquette « auto-tuned vocals, autotune pitch correction » demandait à ACE-Step la voix autotunée qu'il a
    apprise, sous la correction (ses voix « sans correction » ont plus de sauts nets que sa voix naturelle, mais ce sont d'autres
    chansons). Elle reste pour « fort », plus pour « léger ».

Désormais, deux niveaux (NIVEAUX) :
 - LÉGER : le centre de chaque note (la médiane de sa hauteur) rapproché de 40 % de la note ; la correction part de zéro et s'installe en
   80 ms (la vitesse de correction), les passages d'une note à l'autre adoucis sur 80 ms ; le vibrato, les ornements et les glissés
   restent les siens (un glissé efface la correction) ; seulement les voyelles tenues (120 ms au moins) dont la hauteur est SÛRE
   (périodicité ≥ 0,8, creux de YIN net — deux voix mêlées n'en ont pas —, assez forte, Harvest d'accord à 50 cents près quand pyworld
   est là, pas de saut d'octave) ; tout le reste (consonnes, souffle, notes douteuses) n'est pas touché ;
 - FORT : l'effet assumé (100 % vers la note en 15 ms, le vibrato aplati à 85 %), sur les mêmes notes sûres, et propre.
Le déplacement de hauteur : TD-PSOLA (des grains de deux périodes, pris sur les marques de période du son d'origine, recollés à la
nouvelle période) : les formants restent (ni canard ni vocodeur). Seules les suites voisées qui portent une note corrigée sont refaites ;
après la note, les grains suivent avec un décalage constant (un retard de moins d'une demi-période, la forme d'onde intacte) et la main
revient à l'original dans le sourd ou le silence, au plus faible, par un fondu de 5 ms : ni clic ni trou de phase ; ailleurs, l'original
exact. La gamme : celle du morceau si la voix la chante (85 % de ses notes tenues dedans), sinon les 12 demi-tons ; une note chantée
nettement hors gamme (à 25 cents d'un demi-ton) reste la sienne, la gamme ne départage que les ambiguës ; le diapason : celui de l'instru
(ses pics), sinon 440 Hz.

numpy seul (pyworld, s'il est là — .venv-chant —, sert de second détecteur : Harvest). Tests : tests/test_autotune.py.
"""
import math
import unicodedata

try:                                                         # niveau_de sert aussi sans numpy (le venv d'Anamnèse, studio importé)
    import numpy as np
except ImportError:                                          # pragma: no cover
    np = None

TRAME_MS = 5.0
SR_ANALYSE = 16000
F0_MIN, F0_MAX = 65.0, 1000.0

NIVEAUX = {
    # force : la part du chemin vers la note ; aplatir : la part des variations rapides (vibrato) effacée ; retune_ms : la vitesse de
    # correction (le temps pour faire 63 % du chemin) ; tendance_ms : la fenêtre de la tendance (au-dessus, le vibrato n'y entre pas) ;
    # tenue_min_ms : une note plus courte n'est pas touchée (consonnes voisées, notes de passage) ; confiance_min : la périodicité exigée ;
    # glisse_cents_s : au-delà de cette pente, un glissé (la correction s'efface) ; max_cents : jamais plus ; bords_ms : fondus de la correction
    "leger": {"force": 0.4, "aplatir": 0.0, "retune_ms": 80.0, "tendance_ms": 150.0, "tenue_min_ms": 120.0, "confiance_min": 0.8,
              "glisse_cents_s": 400.0, "max_cents": 60.0, "bords_ms": 40.0, "note_min_ms": 60.0, "creux_max": 0.12},
    "fort": {"force": 1.0, "aplatir": 0.85, "retune_ms": 15.0, "tendance_ms": 60.0, "tenue_min_ms": 60.0, "confiance_min": 0.7,
             "glisse_cents_s": 0.0, "max_cents": 120.0, "bords_ms": 15.0, "creux_max": 0.15},
}
_SANS = {"", "non", "no", "0", "false", "faux", "aucun", "sans", "none", "off", "naturel", "naturelle", "nature"}
_FORT = ("fort", "hard", "max", "dur", "robot", "t-pain", "tpain", "heavy", "strong", "full", "assum", "plein", "100")


def niveau_de(v):
    """True / « léger » / « light »… → "leger" ; « fort » / « hard » / « max » / « robot »… → "fort" ; False / « non » / vide → ""."""
    if v is None or v is False:
        return ""
    if v is True:
        return "leger"
    if isinstance(v, (int, float)):
        return "" if v <= 0 else ("fort" if v >= 2 else "leger")
    s = "".join(c for c in unicodedata.normalize("NFD", str(v).strip().lower()) if unicodedata.category(c) != "Mn")
    if s in _SANS:
        return ""
    return "fort" if any(m in s for m in _FORT) else "leger"


# ---------------------------------------------------------------------------------------------------- la hauteur

def _mono(x):
    x = np.asarray(x, dtype=np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


def reechantillonner(x, sr, cible=SR_ANALYSE):
    """Par la FFT (numpy seul). Rend (y, taux exact)."""
    n = len(x)
    m = max(1, int(round(n * cible / sr)))
    if m == n:
        return np.asarray(x, np.float64), float(sr)
    X = np.fft.rfft(x)
    Y = np.zeros(m // 2 + 1, dtype=complex)
    c = min(len(Y), len(X))
    Y[:c] = X[:c]
    return np.fft.irfft(Y, m) * (m / n), sr * m / n


def yin(y, sr, f0_min=F0_MIN, f0_max=F0_MAX, pas_ms=TRAME_MS, fen_ms=25.0, seuil=0.15, lot=512):
    """YIN par trames (centrées sur k × pas_ms), vectorisé. Rend (f0 Hz — 0 : pas de hauteur —, périodicité 0..1, force RMS, creux : la
    différence normalisée de YIN à la période choisie — près de 0 pour une voix seule, 0,2 et plus pour deux voix qui se mêlent)."""
    y = np.asarray(y, np.float64)
    W = int(round(sr * fen_ms / 1000))
    tmax = int(math.ceil(sr / f0_min))
    tmin = max(2, int(math.floor(sr / f0_max)))
    L = W + tmax + 2
    h = sr * pas_ms / 1000.0
    nt = int(len(y) / h) + 1
    pad = np.concatenate([np.zeros(W // 2), y, np.zeros(L + W)])
    debuts = np.round(np.arange(nt) * h).astype(np.int64)
    nfft = 1 << int(math.ceil(math.log2(L + W)))
    f0, per, rms, creux = np.zeros(nt), np.zeros(nt), np.zeros(nt), np.ones(nt)
    taus = np.arange(tmax + 2)
    for i0 in range(0, nt, lot):
        idx = debuts[i0:i0 + lot]
        b = len(idx)
        rang = np.arange(b)
        seg = pad[idx[:, None] + np.arange(L)[None, :]]
        A = np.fft.rfft(seg[:, :W], nfft)
        S = np.fft.rfft(seg, nfft)
        c = np.fft.irfft(np.conj(A) * S, nfft)[:, :tmax + 2]
        q = np.concatenate([np.zeros((b, 1)), np.cumsum(seg ** 2, axis=1)], axis=1)
        E1 = q[:, W]
        E2 = q[:, taus + W] - q[:, taus]
        d = np.maximum(E1[:, None] + E2 - 2 * c, 0.0)
        d[:, 0] = 0.0
        cum = np.cumsum(d[:, 1:], axis=1)
        dp = np.ones_like(d)
        dp[:, 1:] = d[:, 1:] * taus[1:] / np.maximum(cum, 1e-12)
        fen = dp[:, tmin:tmax + 1]
        sous = fen < seuil
        a_un = sous.any(axis=1)
        tau = np.where(a_un, sous.argmax(axis=1) + tmin, 0)
        for _ in range(tmax):                                  # descendre jusqu'au creux
            suiv = np.minimum(tau + 1, tmax + 1)
            va = a_un & (tau < tmax) & (dp[rang, suiv] < dp[rang, tau])
            if not va.any():
                break
            tau = np.where(va, tau + 1, tau)
        gm = fen.argmin(axis=1) + tmin                         # le repli de YIN : le plus profond, s'il reste net
        tau = np.where(a_un, tau, np.where(dp[rang, gm] < 0.35, gm, 0))
        # l'octave du dessus prise à tort (un « a » à 330 Hz lu à 660 : son premier formant double la note) : si le creux du double est
        # bien plus net, c'est lui la période
        t2 = np.minimum(2 * tau, tmax)
        mieux = (tau > 0) & (2 * tau <= tmax) & (dp[rang, tau] > 0.05) & (dp[rang, t2] < 0.5 * dp[rang, tau])
        tau = np.where(mieux, t2, tau)
        ok = tau > 0
        t1 = np.clip(tau, 1, tmax)
        a_, b_, c_ = dp[rang, t1 - 1], dp[rang, t1], dp[rang, t1 + 1]
        den = a_ - 2 * b_ + c_
        tf = np.where(den > 0, t1 + 0.5 * (a_ - c_) / np.where(den > 0, den, 1), t1)
        f0[i0:i0 + b] = np.where(ok, sr / np.maximum(tf, 1e-9), 0.0)
        per[i0:i0 + b] = np.where(ok, c[rang, t1] / np.sqrt(E1 * E2[rang, t1] + 1e-20), 0.0)
        rms[i0:i0 + b] = np.sqrt(E1 / W)
        creux[i0:i0 + b] = np.where(ok, dp[rang, t1], 1.0)
    return f0, np.clip(per, 0.0, 1.0), rms, creux


def _harvest(y, sr, nt):
    try:
        import pyworld as pw
    except ImportError:
        return None
    f, _ = pw.harvest(np.ascontiguousarray(y, dtype=np.float64), int(round(sr)), f0_floor=F0_MIN, f0_ceil=F0_MAX, frame_period=TRAME_MS)
    out = np.zeros(nt)
    m = min(nt, len(f))
    out[:m] = f[:m]
    return out


def analyser(x, sr, second=True):
    """La voix (mono ou stéréo) → ses trames : f0 (YIN), périodicité, force, et f0 de Harvest (None sans pyworld, ou second=False)."""
    y, s2 = reechantillonner(_mono(x), sr)
    f0, per, rms, creux = yin(y, s2)
    hv = _harvest(y, s2, len(f0)) if second else None
    return {"f0": f0, "periodicite": per, "rms": rms, "creux": creux, "harvest": hv, "sr": sr, "n": len(_mono(x))}


def _demitons(f):
    return 69.0 + 12.0 * np.log2(np.maximum(f, 1e-9) / 440.0)


def sures(A, P):
    """Les trames dont la hauteur est sûre : périodique, assez forte, (les deux détecteurs d'accord), sans saut d'octave isolé."""
    f0, per, rms = A["f0"], A["periodicite"], A["rms"]
    v = (f0 > 0) & (per >= P["confiance_min"])
    if "creux" in A:                                         # un creux de YIN pas net : deux voix (un chœur), ou du souffle
        v &= A["creux"] <= P.get("creux_max", 0.12)
    if not v.any():
        return v
    ref = np.percentile(rms[v], 95)
    v &= rms >= ref * 10 ** (-35 / 20)                       # la réverbération, les fuites, le souffle lointain : trop faibles
    hv = A.get("harvest")
    if hv is not None:
        v &= (hv > 0) & (np.abs(1200 * np.log2(np.maximum(f0, 1e-9) / np.maximum(hv, 1e-9))) < 50)
    m = _demitons(f0)
    idx = np.flatnonzero(v)
    for k in idx:                                            # une trame loin de ses voisines sûres (octave, note fantôme) : douteuse
        vois = [m[j] for j in range(max(0, k - 3), min(len(m), k + 4)) if j != k and v[j]]
        if len(vois) >= 2 and abs(m[k] - float(np.median(vois))) > 1.0:
            v[k] = False
    return v


def notes_tenues(v, f0, P):
    """Les suites de trames sûres et continues (moins de 70 cents d'une trame à l'autre) d'au moins tenue_min_ms : [(i, j)]."""
    m = _demitons(f0)
    out, i, n = [], 0, len(v)
    while i < n:
        if not v[i]:
            i += 1
            continue
        j = i + 1
        while j < n and v[j] and abs(m[j] - m[j - 1]) < 0.7:
            j += 1
        if (j - i) * TRAME_MS >= P["tenue_min_ms"]:
            out.append((i, j))
        i = j
    return out


# ---------------------------------------------------------------------------------------------------- la gamme et le diapason

def diapason(x, sr, n=8192, max_s=90.0):
    """Le diapason d'une instru, en cents par rapport à 440 Hz (−50..50) : la moyenne circulaire de ses pics (200-4000 Hz) ; 0 si rien de net."""
    x = _mono(x)
    if len(x) > max_s * sr:
        a = int((len(x) - max_s * sr) / 2)
        x = x[a:a + int(max_s * sr)]
    if len(x) < n:
        return 0.0
    w = np.hanning(n)
    trames = np.lib.stride_tricks.sliding_window_view(x, n)[:: n // 2]
    S = np.abs(np.fft.rfft(trames * w, axis=1))
    f = np.fft.rfftfreq(n, 1 / sr)
    k0, k1 = int(200 * n / sr), int(4000 * n / sr)
    Z, poids = 0j, 0.0
    for s in S:
        if s.max() <= 0:
            continue
        l = np.log(s + 1e-12)
        pic = (s[k0:k1] > s[k0 - 1:k1 - 1]) & (s[k0:k1] >= s[k0 + 1:k1 + 1]) & (s[k0:k1] > s.max() * 10 ** (-30 / 20))
        for k in np.flatnonzero(pic) + k0:
            den = l[k - 1] - 2 * l[k] + l[k + 1]
            dk = 0.5 * (l[k - 1] - l[k + 1]) / den if den < 0 else 0.0
            fk = (k + dk) * sr / n
            c = 1200 * math.log2(fk / 440.0)
            Z += s[k] * np.exp(2j * math.pi * c / 100.0)
            poids += s[k]
    if poids <= 0 or abs(Z) / poids < 0.15:
        return 0.0
    return float(np.angle(Z) * 100 / (2 * math.pi))


def gamme_verifiee(f0, tenues, classes, diap=0.0, couverture_min=0.85):
    """La gamme dite, si la voix la chante (couverture_min de ses notes tenues dedans, pondérées par leur durée) ; sinon les 12. Rend
    (classes, couverture)."""
    classes = tuple(sorted(set(int(c) % 12 for c in classes))) or tuple(range(12))
    if len(classes) == 12 or not tenues:
        return tuple(range(12)), 1.0
    pcs = []
    for i, j in tenues:
        m = _demitons(f0[i:j]) - diap / 100.0
        pcs.extend((np.round(m).astype(int) % 12).tolist())
    if not pcs:
        return tuple(range(12)), 1.0
    dedans = sum(1 for p in pcs if p in classes) / len(pcs)
    return (classes, dedans) if dedans >= couverture_min else (tuple(range(12)), dedans)


# ---------------------------------------------------------------------------------------------------- la courbe de correction

def _moyenne_glissante(v, n):
    n = max(1, int(n))
    c = np.concatenate([[0.0], np.cumsum(v)])
    k = np.arange(len(v))
    a, b = np.maximum(0, k - n // 2), np.minimum(len(v), k + n // 2 + 1)
    return (c[b] - c[a]) / (b - a)


def _note_proche(m, classes, nette=0.25):
    """La note la plus proche dans la gamme ; mais une note chantée nettement (à 25 cents d'un demi-ton) reste la sienne, même hors de la
    gamme : la gamme ne départage que les notes ambiguës (mesuré le 11/11 : 13 à 16 % de ses notes tenues hors de la gamme dite)."""
    r = int(round(m))
    if r % 12 in classes or abs(m - r) <= nette:
        return r
    base = math.floor(m)
    return min((n for n in range(base - 2, base + 4) if n % 12 in classes), key=lambda n: abs(n - m))


def _notes_visees(tr, classes, hysteresis=0.1):
    """La note visée, trame par trame, sur la tendance : on ne change de note qu'une fois passé le milieu de 10 cents (pas de va-et-vient)."""
    out = np.empty(len(tr))
    cur = None
    for k, m in enumerate(tr):
        cand = _note_proche(m, classes)
        if cur is None or (cand != cur and abs(m - cur) > abs(cand - cur) / 2 + hysteresis):
            cur = cand
        out[k] = cur
    return out


def _centres(m, note, P):
    """LÉGER : chaque note (une suite de trames visant la même note, 60 ms au moins) déplacée d'un bloc, force × (sa note − son centre) ;
    son centre : la médiane de sa hauteur. Le vibrato, les ornements et les glissés à l'intérieur restent tels quels ; une note de passage
    (plus courte) n'est pas touchée."""
    c = np.zeros(len(m))
    u = 0
    while u < len(m):
        v = u + 1
        while v < len(m) and note[v] == note[u]:
            v += 1
        if (v - u) * TRAME_MS >= P.get("note_min_ms", 60.0):
            c[u:v] = P["force"] * (note[u] - float(np.median(m[u:v])))
        u = v
    return c


def correction(A, P, classes, diap=0.0, v=None, tenues=None):
    """La correction (demi-tons, une valeur par trame ; 0 hors des notes tenues sûres) et ses notes. Rend (corr, tenues).
    LÉGER (aplatir = 0) : le centre de chaque note rapproché de force × l'écart, les passages d'une note à l'autre adoucis sur retune_ms
    (pas de traînée de la note d'avant qui tirerait à contre-sens) ; FORT : chaque trame tirée vers la note, la note suivie en retune_ms,
    le vibrato aplati (aplatir)."""
    f0 = A["f0"]
    if v is None:
        v = sures(A, P)
    if tenues is None:
        tenues = notes_tenues(v, f0, P)
    corr = np.zeros(len(f0))
    a = 1 - math.exp(-TRAME_MS / max(1e-3, P["retune_ms"]))
    nr = max(1, int(round(P["retune_ms"] / TRAME_MS)))
    nb = max(1, int(round(P["bords_ms"] / TRAME_MS)))
    for i, j in tenues:
        m = _demitons(f0[i:j]) - diap / 100.0
        tr = _moyenne_glissante(m, round(P["tendance_ms"] / TRAME_MS) | 1)
        note = _notes_visees(tr, classes)
        if P["aplatir"] > 0:
            cible, s = np.empty(len(tr)), tr[0]              # la vitesse de correction : partie de là où il chante, vers la note
            for k in range(len(tr)):
                s += a * (note[k] - s)
                cible[k] = s
            c = P["force"] * (cible - tr) + P["aplatir"] * (tr - m)
        else:
            c = _moyenne_glissante(_moyenne_glissante(_centres(m, note, P), nr | 1), nr | 1)
            c = c * (1 - np.exp(-np.arange(len(c)) * TRAME_MS / max(1e-3, P["retune_ms"])))   # la vitesse : de zéro, en retune_ms
        if P["glisse_cents_s"] > 0:                          # un glissé (sa pente) : la correction s'efface, le glissé reste le sien
            pente = np.abs(np.gradient(tr)) * 100 / (TRAME_MS / 1000)
            g0 = P["glisse_cents_s"] / 2                     # entière sous la moitié du seuil, nulle au seuil
            c = c * _moyenne_glissante(np.clip(1 - (pente - g0) / g0, 0, 1), 9)
        c = np.clip(c, -P["max_cents"] / 100, P["max_cents"] / 100)
        k = min(nb, len(c) // 2)
        if k:
            r = 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
            c[:k] *= r
            c[len(c) - k:] *= r[::-1]
        corr[i:j] = c
    return corr, tenues


# ---------------------------------------------------------------------------------------------------- TD-PSOLA

def _passe_bas(x, sr, fc=1000.0, n=101):
    t = np.arange(n) - n // 2
    h = np.sinc(2 * fc / sr * t) * np.hanning(n)
    return np.convolve(x, h / h.sum(), mode="same")


def f0_des_marques(A):
    """La hauteur qui pose les marques de période : celle de Harvest quand il est là (plus continue), sinon YIN ; ses sauts d'octave (et de
    quinte) isolés ramenés sur la médiane de ses voisines (9 trames) ; 0 hors de la voix (périodicité < 0,5). Mesuré le 11/11 : des marques
    posées sur un YIN qui sautait de 138 à 414 Hz faisaient des grains de tailles folles, donc des clics."""
    if "_f0_marques" in A:
        return A["_f0_marques"]
    vo = (A["f0"] > 0) & (A["periodicite"] >= 0.5)
    hv = A.get("harvest")
    f = np.where((hv > 0) if hv is not None else False, hv if hv is not None else 0.0, A["f0"])
    f = np.where(vo & (f > 0), f, 0.0)
    l = np.where(f > 0, np.log2(np.maximum(f, 1e-9)), np.nan)
    for k in np.flatnonzero(f > 0):
        w = l[max(0, k - 4):k + 5]
        w = w[np.isfinite(w)]
        if len(w) >= 3:
            med = float(np.median(w))
            r = l[k] - med
            if abs(r) > 0.45:                                 # plus d'une quarte de ses voisines : la même note à l'octave près, ou douteuse
                q = r - round(r)
                f[k] = 2 ** (med + q) if abs(q) < 0.1 else 2 ** med
    A["_f0_marques"] = f
    return f


def _f0_echantillon(A, i):
    k = int(round(i / (A["sr"] * TRAME_MS / 1000)))
    f = f0_des_marques(A)
    return f[k] if 0 <= k < len(f) else 0.0


def marques(x, sr, A, a, b):
    """Les marques de période dans [a, b) : le haut de chaque période (sur le son adouci), à 0,8-1,2 période de la précédente ; sans
    hauteur, une marque toutes les 5 ms. [(i, demi_largeur, voisée)]"""
    lp = _passe_bas(x[a:b], sr)
    sourd = max(1, int(round(sr * 0.005)))
    out, i, prev = [], a, None
    while i < b:
        f = _f0_echantillon(A, i)
        if f > 0:
            T = sr / f
            if prev and prev[2]:
                u, w = int(prev[0] + 0.8 * T), int(prev[0] + 1.2 * T) + 1
            else:
                u, w = i, int(i + T) + 1
            u, w = max(u, a), min(w, b)
            if w <= u:
                break
            m = u + int(np.argmax(lp[u - a:w - a]))
            if prev and m <= prev[0]:
                m = prev[0] + max(1, int(round(T)))
            if m >= b:
                break
            prev = (m, max(2, int(round(T))), True)
            out.append(prev)
            i = m + max(1, int(0.5 * T))
            continue
        m = i if not prev else max(i, prev[0] + (prev[1] if prev[2] else sourd))
        if m >= b:
            break
        prev = (m, sourd, False)
        out.append(prev)
        i = m + sourd
    return out


def _regions(tenues, A, n, trou_ms=40.0, marge_ms=40.0):
    """Les zones à re-synthétiser : pour chaque note corrigée, toute la suite voisée qui la porte (un trou de détection de 40 ms au plus,
    au milieu d'une voix qui reprend, ne la coupe pas), jusqu'aux consonnes ou au silence qui l'entourent ; ses bords posés au plus faible
    de la force dans les 40 ms d'à côté. Pourquoi : déplacer la hauteur décale les périodes de synthèse par rapport à celles d'origine (au
    plus une demi-période) ; une fois la correction finie, ce décalage reste constant, et un décalage constant n'est qu'un retard (les
    grains recopient le son tel quel) ; on ne rend la main à l'original que dans le sourd ou le silence, au plus bas : jamais de recollage
    en pleine voyelle (ni trou de phase, ni clic), et aucune période étirée pour se recaler."""
    h = A["sr"] * TRAME_MS / 1000
    vo = (A["f0"] > 0) & (A["periodicite"] >= 0.5)
    rms = A["rms"]
    nt, nm, ng = len(vo), max(1, int(marge_ms / TRAME_MS)), int(trou_ms / TRAME_MS)

    def suite(k, pas):
        while 0 <= k + pas < nt:
            if vo[k + pas]:
                k += pas
                continue
            g = 1
            while g <= ng and 0 <= k + pas * g < nt and not vo[k + pas * g]:
                g += 1
            if g <= ng and 0 <= k + pas * g < nt:
                k += pas * g
                continue
            break
        return k
    out = []
    for i, j in tenues:
        i, j = suite(i, -1), suite(j - 1, 1) + 1
        u = np.arange(max(0, i - nm), i + 1)
        w = np.arange(j, min(nt, j + nm + 1)) if j < nt else np.array([nt - 1])
        i = int(u[np.argmin(rms[u])]) if len(u) else i
        j = int(w[np.argmin(rms[w])]) if len(w) else j
        a, b = max(0, int(i * h)), min(n, int(j * h) + 1)
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        elif b > a:
            out.append((a, b))
    return out


def plan_psola(x, sr, A, corr, a, b):
    """Les grains d'une zone : [(source, destination, demi-largeur)].
    Dans une note corrigée, les marques de synthèse avancent de (l'écart des marques d'origine) / rapport, et chacune prend le grain de la
    marque d'origine la plus proche (répété ou sauté d'une période : la hauteur change, la forme de chaque grain — les formants — reste).
    Partout ailleurs (correction nulle, sourd, voix douteuse), chaque grain suit le précédent avec le même décalage : un décalage constant
    n'est qu'un retard (les grains recopient le son tel quel), jamais un saut, quelles que soient les marques."""
    M = marques(x, sr, A, a, b)
    if len(M) < 3:
        return []
    h = sr * TRAME_MS / 1000
    pos = np.array([m[0] for m in M], dtype=np.float64)

    def corr_a(t):
        k = int(round(t / h))
        return corr[k] if 0 <= k < len(corr) else 0.0
    plan, s, j = [], float(M[0][0]), 0
    while s < b:
        m, T, voisee = M[j]
        plan.append((m, int(round(s)), T))
        if j + 1 >= len(M):
            break
        c = corr_a(s)
        if abs(c) < 1e-4 or not voisee or not M[j + 1][2]:
            s += pos[j + 1] - pos[j]                         # le grain suivant, le même décalage
            j += 1
            continue
        s += (pos[j + 1] - pos[j]) / (2 ** (c / 12))
        while j + 1 < len(M) and abs(pos[j + 1] - s) <= abs(pos[j] - s):
            j += 1
    return plan


def appliquer(x, plan, a, b, sr=44100, fondu_ms=5.0):
    """Les grains (fenêtre de Hann de 2 demi-largeurs) recollés et normalisés par la somme des fenêtres (là où les grains ont le même
    décalage, c'est le son d'origine retardé, exactement, même au bord d'une fenêtre) ; un trou entre deux grains (une marque voisée loin
    d'une marque sourde) : le son d'origine au décalage du grain d'avant — jamais l'original sans décalage au milieu de grains décalés
    (mesuré le 11/11 : c'était le dernier clic, au passage voisé ↔ sourd). Avant le premier grain et après le dernier : l'original."""
    x = np.asarray(x, np.float64)
    deux = x.ndim == 2
    X = x if deux else x[:, None]
    n = len(X)
    y = np.zeros((b - a, X.shape[1]))
    w = np.zeros(b - a)
    dec = np.full(b - a, -1 << 40, dtype=np.int64)
    for src, dst, T in plan:
        k = np.arange(-T, T + 1)
        sv, dv = src + k, dst + k
        ok = (sv >= 0) & (sv < n) & (dv >= a) & (dv < b)
        if not ok.any():
            continue
        h = 0.5 + 0.5 * np.cos(np.pi * k[ok] / T)
        y[dv[ok] - a] += h[:, None] * X[sv[ok]]
        w[dv[ok] - a] += h
        dec[dv[ok] - a] = dst - src
    sortie = X[a:b].copy()
    bon = w > 1e-9
    sortie[bon] = y[bon] / w[bon, None]
    if bon.any():
        p0, p1 = np.flatnonzero(bon)[[0, -1]]
        trous = np.flatnonzero(~bon[p0:p1 + 1]) + p0
        if len(trous):
            connu = np.where(dec > -1 << 39, np.arange(b - a), -1)
            dernier = np.maximum.accumulate(connu)[trous]
            src = np.clip(a + trous - dec[dernier], 0, n - 1)
            sortie[trous] = X[src]
    # les bords de la zone (dans le sourd ou le silence) : un fondu de 5 ms vers l'original
    f = min(int(sr * fondu_ms / 1000) + 1, (b - a) // 4)
    if f > 1:
        r = (0.5 - 0.5 * np.cos(np.pi * np.arange(f) / f))[:, None]
        sortie[:f] = X[a:a + f] * (1 - r) + sortie[:f] * r
        sortie[-f:] = X[b - f:b] * r + sortie[-f:] * (1 - r)
    return sortie if deux else sortie[:, 0]


# ---------------------------------------------------------------------------------------------------- l'ensemble

def corriger(x, sr, classes=tuple(range(12)), niveau="leger", diap=0.0, second=True, reglages=None):
    """La voix seule (mono ou stéréo, flottants) recalée au niveau donné. Rend (y, rapport). niveau "" : la voix telle quelle."""
    x = np.asarray(x, np.float64)
    niveau = niveau_de(niveau) if niveau not in NIVEAUX else niveau
    if not niveau:
        return x.copy(), {"niveau": "", "notes": 0}
    P = {**NIVEAUX[niveau], **(reglages or {})}
    A = analyser(x, sr, second=second)
    v = sures(A, P)
    tenues = notes_tenues(v, A["f0"], P)
    gamme, couverture = gamme_verifiee(A["f0"], tenues, classes, diap)
    corr, tenues = correction(A, P, gamme, diap, v, tenues)
    mono = _mono(x)
    y = x.copy()
    for a, b in _regions(tenues, A, len(mono)):
        plan = plan_psola(mono, sr, A, corr, a, b)
        if plan:
            y[a:b] = appliquer(x, plan, a, b, sr)
    voisees = int((A["f0"] > 0).sum())
    touchees = int((np.abs(corr) > 1e-4).sum())
    return y, {"niveau": niveau, "gamme": list(gamme), "gamme_dite": list(classes), "couverture": round(float(couverture), 3),
               "diapason_cents": round(float(diap), 1), "notes": len(tenues), "second_detecteur": A["harvest"] is not None,
               "trames_voisees": voisees, "trames_corrigees": touchees,
               "part_corrigee": round(touchees / max(1, voisees), 3),
               "correction_mediane_cents": round(float(np.median(np.abs(corr[np.abs(corr) > 1e-4])) * 100), 1) if touchees else 0.0}


# ---------------------------------------------------------------------------------------------------- les mesures (banc, tests)

def hauteur_cents(x, sr, second=False):
    """La hauteur trame par trame en cents (MIDI × 100), NaN hors voix sûre (périodicité ≥ 0,8)."""
    A = analyser(x, sr, second=second)
    c = np.full(len(A["f0"]), np.nan)
    ok = (A["f0"] > 0) & (A["periodicite"] >= 0.8)
    c[ok] = _demitons(A["f0"][ok]) * 100
    return c


def ecart_aux_notes(c, diap=0.0):
    """L'écart de chaque trame à son demi-ton le plus proche (cents, −50..50)."""
    c = c[np.isfinite(c)] - diap
    return (c + 50) % 100 - 50


def clics(x, sr, ref=None, seuil=8.0, facteur=2.0):
    """Les clics (blocs de 20 ms) : la dérivée seconde y dépasse seuil fois sa médiane locale. Avec ref (le son d'origine, même longueur) :
    seulement les clics NOUVEAUX, ceux qui dépassent aussi facteur fois le plus fort de ref autour (± 20 ms)."""
    def blocs(s):
        d = np.abs(np.diff(_mono(s), 2))
        n = max(1, int(0.02 * sr))
        k = len(d) // n
        if not k:
            return np.zeros(0, bool), np.zeros(0)
        b = d[: k * n].reshape(k, n)
        mx = b.max(axis=1)
        return (mx > seuil * np.maximum(np.median(b, axis=1), np.median(d) + 1e-9)) & (mx > 1e-3), mx
    p, mx = blocs(x)
    if ref is None:
        return int(p.sum())
    _, mr = blocs(ref)
    k = min(len(mx), len(mr))
    if not k:
        return 0
    voisins = np.maximum.reduce([mr[:k], np.concatenate([[0.0], mr[:k - 1]]), np.concatenate([mr[1:k], [0.0]])])
    return int((p[:k] & (mx[:k] > facteur * voisins)).sum())


def enveloppe_lpc(x, sr, ordre=12, n=512, sr_lpc=11025):
    """L'enveloppe spectrale (LPC, autocorrélation, sur le son ramené à 11 kHz) d'un passage : (fréquences, dB)."""
    x, sr = reechantillonner(_mono(x), sr, sr_lpc)
    x = np.append(x[0], x[1:] - 0.9 * x[:-1]) * np.hanning(len(x))           # pré-accentuation, fenêtre
    r = np.correlate(x, x, "full")[len(x) - 1:len(x) + ordre]
    a = np.zeros(ordre + 1)
    a[0], e = 1.0, r[0]
    for i in range(1, ordre + 1):                             # Levinson-Durbin
        k = -(r[i] + np.dot(a[1:i], r[i - 1:0:-1])) / max(e, 1e-12)
        a[1:i + 1] = a[1:i + 1] + k * np.concatenate([a[i - 1:0:-1], [1.0]])
        e *= 1 - k * k
    f = np.linspace(0, sr / 2, n)
    H = np.abs(np.polyval(a[::-1], np.exp(-2j * np.pi * f / sr)))
    return f, -20 * np.log10(H + 1e-12)


def formants(x, sr, nb=3):
    """Les premiers formants (Hz) : les pics de l'enveloppe LPC au-dessus de 200 Hz."""
    f, db = enveloppe_lpc(x, sr)
    pics = [f[k] for k in range(1, len(db) - 1) if db[k] > db[k - 1] and db[k] >= db[k + 1] and f[k] > 200]
    return pics[:nb]
