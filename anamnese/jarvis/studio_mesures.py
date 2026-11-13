"""Les mesures du studio multipiste (13/11, Ahmed : « qu'il sache parfaitement faire des vrais mix complets, et le mastering aussi,
piste par piste »). Numpy seulement (aucune autre dépendance) : ce module sert dans les trois venvs (Anamnèse, chant, séparation).

Ce qu'il mesure, et comment :
- le niveau intégré (LUFS), la crête vraie (dBTP) et la plage (LU) : le filtre ebur128 de ffmpeg (BS.1770-4, crête suréchantillonnée) ;
- la plage dynamique « PLR » (crête vraie − LUFS) et le facteur de crête court terme ;
- l'équilibre spectral : l'énergie par bandes d'octave (31 Hz → 16 kHz), relative à la moyenne, comparée à une courbe de référence du
  genre (studio_references.json, mesurée sur des morceaux du genre) ;
- la séparation avec une vérité connue (un mélange fabriqué : une instru sans voix + une voix seule) : SDR de l'instru, la FUITE de voix
  (ce qui reste de la voix dans l'instru, en dB sous son niveau d'origine) et les ARTEFACTS (ce que la séparation abîme de l'instru, en dB
  sous l'instru) : l'erreur est projetée, fréquence par fréquence (un gain complexe par case, donc un filtre long), sur la voix ;
- sans vérité (une vraie chanson) : les « dégâts hors voix » (là où il n'y a pas de voix, l'instru tirée devrait être la chanson même) ;
- le calage d'une voix sur la grille du tempo, en millisecondes (les attaques de la voix contre les temps).
"""
import json
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np

FFMPEG = os.environ.get("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg")
SR = 44100
BANDES_HZ = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
REFERENCES = Path(__file__).resolve().parent / "studio_references.json"


# ------------------------------------------------------------------------------------------------ lire
def lire(fichier, sr=SR, canaux=2, debut=0.0, duree=None):
    """Le son en flottant (n, canaux), par ffmpeg (aucun soundfile nécessaire)."""
    a = [FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error"]
    if debut:
        a += ["-ss", f"{float(debut):.3f}"]
    if duree:
        a += ["-t", f"{float(duree):.3f}"]
    a += ["-i", str(fichier), "-ac", str(canaux), "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(a, capture_output=True, timeout=600)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : lecture impossible de {Path(fichier).name}")
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x.reshape(-1, canaux), sr


def ecrire_wav(fichier, x, sr=SR, bits=16):
    """Un WAV (ou un FLAC selon l'extension) par ffmpeg, depuis un tableau (n,) ou (n, canaux)."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    codec = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}[bits]
    ext = Path(fichier).suffix.lower()
    if ext == ".flac":
        codec, extra = "flac", ["-sample_fmt", "s16" if bits == 16 else "s32"]
    elif ext == ".mp3":
        codec, extra = "libmp3lame", ["-b:a", "320k"]
    else:
        extra = []
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac",
                        str(x.shape[1]), "-i", "-", "-c:a", codec, *extra, str(fichier)],
                       input=np.ascontiguousarray(x).tobytes(), capture_output=True, timeout=600)
    if r.returncode:
        raise RuntimeError(f"ffmpeg : écriture impossible ({r.stderr.decode(errors='ignore')[-200:]})")
    return fichier


# ------------------------------------------------------------------------------------------------ le niveau
def ebur128(fichier):
    """{lufs, crete_dbtp, lra} d'un fichier (ffmpeg ebur128, crête vraie suréchantillonnée)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", str(fichier), "-af", "ebur128=peak=true:framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    err = r.stderr
    resume = err[err.rfind("Summary:"):] if "Summary:" in err else err

    def val(motif, vide):
        m = re.search(motif, resume)
        if not m:
            return None
        return vide if m.group(1) == "-inf" else round(float(m.group(1)), 1)
    return {"lufs": val(r"I:\s+(-?[\d.]+|-inf) LUFS", -70.0), "crete_dbtp": val(r"Peak:\s+(-?[\d.]+|-inf) dBFS", -120.0),
            "lra": val(r"LRA:\s+(-?[\d.]+|-inf) LU", 0.0)}


def db(x):
    x = np.asarray(x, dtype=np.float64)
    return float(10 * np.log10(max(1e-20, float((x ** 2).mean()))))


def facteur_de_crete(x, sr=SR, fenetre_s=0.4):
    """La médiane, sur des fenêtres de 400 ms, de crête − efficace (dB) : petite = écrasé par la compression."""
    m = np.asarray(x, np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    n = int(sr * fenetre_s)
    k = len(m) // n
    if k < 3:
        return None
    t = m[: k * n].reshape(k, n)
    rms = np.sqrt((t ** 2).mean(axis=1)) + 1e-12
    pic = np.abs(t).max(axis=1) + 1e-12
    vivants = rms > 10 ** (-50 / 20)
    if vivants.sum() < 3:
        return None
    return round(float(np.median(20 * np.log10(pic[vivants] / rms[vivants]))), 1)


def correlation_stereo(x):
    x = np.asarray(x, np.float64)
    if x.ndim != 2 or x.shape[1] < 2:
        return 1.0
    a, b = x[:, 0] - x[:, 0].mean(), x[:, 1] - x[:, 1].mean()
    d = math.sqrt(float((a * a).sum() * (b * b).sum())) + 1e-20
    return round(float((a * b).sum() / d), 2)


# ------------------------------------------------------------------------------------------------ l'équilibre spectral
def spectre_moyen(x, sr=SR, n=8192):
    """La densité spectrale moyenne (Welch, fenêtres de Hann, recouvrement de moitié), en puissance par case."""
    m = np.asarray(x, np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    pas = n // 2
    k = 1 + (len(m) - n) // pas
    w = np.hanning(n)
    acc = np.zeros(n // 2 + 1)
    for i in range(0, k, max(1, k // 600)):              # au plus ~600 fenêtres : assez pour une moyenne
        f = np.fft.rfft(m[i * pas: i * pas + n] * w)
        acc += (f.real ** 2 + f.imag ** 2)
    return np.fft.rfftfreq(n, 1 / sr), acc


def bandes(x, sr=SR):
    """L'énergie par bande d'octave (dB), relative à la moyenne des bandes : la forme, pas le niveau."""
    f, p = spectre_moyen(x, sr)
    v = []
    for c in BANDES_HZ:
        sel = (f >= c / math.sqrt(2)) & (f < c * math.sqrt(2))
        v.append(10 * math.log10(max(1e-20, float(p[sel].sum()))))
    v = np.array(v)
    return [round(float(a), 1) for a in v - v.mean()]


def references(chemin=None):
    try:
        return json.loads(Path(chemin or REFERENCES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ecart_reference(b, genre="trap", chemin=None):
    """L'écart (dB) de chaque bande à la courbe du genre, et un mot pour les plus grands (±3 dB et plus)."""
    ref = (references(chemin).get("genres") or {}).get(genre)
    if not ref or not b:
        return None
    e = [round(float(a - r), 1) for a, r in zip(b, ref["bandes"])]
    noms = ["sub-grave (31 Hz)", "grave (63 Hz)", "bas (125 Hz)", "bas-médium (250 Hz)", "médium (500 Hz)", "médium (1 kHz)",
            "haut-médium (2 kHz)", "présence (4 kHz)", "aigu (8 kHz)", "air (16 kHz)"]
    mots = [f"{noms[i]} {'+' if v > 0 else ''}{v:.0f} dB" for i, v in enumerate(e) if abs(v) >= 3]
    return {"genre": genre, "ecarts_db": e, "ecart_moyen_db": round(float(np.mean(np.abs(e))), 1), "mots": mots,
            "sources": ref.get("sources", [])}


def correction_eq(b, genre="trap", force=0.5, plafond_db=3.0, chemin=None):
    """Les gains (dB) d'un égaliseur de mastering vers la courbe du genre : la moitié de l'écart, ±3 dB au plus, et seulement les
    bandes de 63 Hz à 8 kHz (le sub-grave et l'air ne se corrigent pas à l'aveugle)."""
    e = ecart_reference(b, genre, chemin)
    if not e:
        return []
    out = []
    for i, (c, v) in enumerate(zip(BANDES_HZ, e["ecarts_db"])):
        if c < 60 or c > 9000 or abs(v) < 1.5:
            continue
        g = max(-plafond_db, min(plafond_db, -force * v))
        out.append({"hz": c, "db": round(g, 1)})
    return out


# ------------------------------------------------------------------------------------------------ la séparation, contre une vérité
def _stft(x, n=2048, pas=512):
    x = np.asarray(x, np.float64)
    x = x.mean(axis=1) if x.ndim == 2 else x
    k = 1 + max(0, (len(x) - n)) // pas
    w = np.hanning(n)
    idx = np.arange(n)[None, :] + pas * np.arange(k)[:, None]
    return np.fft.rfft(x[idx] * w, axis=1)


def separation_contre_verite(estimee, instru_vraie, voix_vraie):
    """L'instru tirée d'un mélange instru_vraie + voix_vraie. Rend :
    - sdr_db : instru / erreur (plus haut = mieux) ;
    - fuite_voix_db : l'énergie de la voix qui reste dans l'instru, sous l'énergie de la voix (plus bas = mieux ; −∞ : rien) ;
    - artefacts_db : l'erreur qui n'est pas de la voix (instru abîmée, bruits), sous l'instru (plus bas = mieux).
    La projection se fait par case de fréquence (un gain complexe constant dans le temps), comme un filtre long : une voix un peu
    filtrée ou déphasée compte encore comme de la voix."""
    n = min(len(estimee), len(instru_vraie), len(voix_vraie))
    E = _stft(np.asarray(estimee)[:n] - np.asarray(instru_vraie)[:n])
    V = _stft(np.asarray(voix_vraie)[:n])
    I = _stft(np.asarray(instru_vraie)[:n])
    vv = (V.real ** 2 + V.imag ** 2).sum(axis=0) + 1e-20
    alpha = (np.conj(V) * E).sum(axis=0) / vv                     # par case : la part de l'erreur qui est de la voix
    Ev = alpha[None, :] * V
    Ea = E - Ev
    p = lambda z: float((z.real ** 2 + z.imag ** 2).sum()) + 1e-20
    return {"sdr_db": round(10 * math.log10(p(I) / p(E)), 2), "fuite_voix_db": round(10 * math.log10(p(Ev) / p(V)), 1),
            "artefacts_db": round(10 * math.log10(p(Ea) / p(I)), 1)}


def degats_hors_voix(chanson, instru, voix_estimee, sr=SR, seuil_db=-40.0, fenetre_s=0.1):
    """Sans vérité : là où la voix est absente (sa fenêtre sous seuil_db du pic de la voix), l'instru devrait être la chanson même.
    Rend l'écart (dB sous la chanson) dans ces passages, et leur part : une séparation qui mange l'oud ou le ney là où personne ne
    chante se voit ici (plus bas = mieux)."""
    n = min(len(chanson), len(instru), len(voix_estimee))
    c = np.asarray(chanson, np.float64)[:n]
    i = np.asarray(instru, np.float64)[:n]
    v = np.asarray(voix_estimee, np.float64)[:n]
    c, i, v = (z.mean(axis=1) if z.ndim == 2 else z for z in (c, i, v))
    w = int(sr * fenetre_s)
    k = n // w
    if k < 10:
        return None
    ev = (v[: k * w].reshape(k, w) ** 2).mean(axis=1)
    pic = ev.max() + 1e-20
    libre = 10 * np.log10(ev / pic + 1e-20) < seuil_db
    ec = (c[: k * w].reshape(k, w) ** 2).mean(axis=1)
    libre &= 10 * np.log10(ec + 1e-20) > -60                   # pas le silence
    if libre.sum() < 10:
        return {"part_sans_voix": round(float(libre.mean()), 2), "ecart_db": None}
    d = ((c - i)[: k * w].reshape(k, w) ** 2).mean(axis=1)
    return {"part_sans_voix": round(float(libre.mean()), 2),
            "ecart_db": round(10 * math.log10((d[libre].sum() + 1e-20) / (ec[libre].sum() + 1e-20)), 1)}


# ------------------------------------------------------------------------------------------------ le tempo et le calage
def enveloppe_attaques(x, sr=SR, pas_s=0.005):
    """Les hausses d'énergie (flux spectral simple en bandes), une valeur toutes les 5 ms."""
    m = np.asarray(x, np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    n = 1024
    pas = int(sr * pas_s)
    k = 1 + max(0, len(m) - n) // pas
    if k < 20:
        return np.zeros(0)
    w = np.hanning(n)
    idx = np.arange(n)[None, :] + pas * np.arange(k)[:, None]
    S = np.abs(np.fft.rfft(m[idx] * w, axis=1))
    S = np.log1p(100 * S / (S.max() + 1e-12))
    d = np.maximum(0, np.diff(S, axis=0, prepend=S[:1])).sum(axis=1)
    return d - np.convolve(d, np.ones(40) / 40, mode="same")       # moins la tendance (200 ms)


def tempo_et_phase(x, sr=SR, bpm_min=60, bpm_max=200, bpm_connu=0):
    """Le tempo (BPM) et l'instant du premier temps (s), par autocorrélation des attaques puis peigne de phase.
    bpm_connu : le tempo déjà connu (la demande à ACE-Step) : seule la phase se cherche (±2 %)."""
    pas_s = 0.005
    o = enveloppe_attaques(x, sr, pas_s)
    o = np.maximum(o, 0)
    if len(o) < 400 or o.max() <= 0:
        return {"bpm": float(bpm_connu or 0), "premier_temps_s": 0.0, "confiance": 0.0}
    ac = np.correlate(o, o, mode="full")[len(o) - 1:]
    ac /= ac[0] + 1e-12
    if bpm_connu:
        lags = np.arange(int(60 / (bpm_connu * 1.02) / pas_s), int(60 / (bpm_connu * 0.98) / pas_s) + 2)
    else:
        lags = np.arange(int(60 / bpm_max / pas_s), int(60 / bpm_min / pas_s) + 1)
    lags = lags[lags < len(ac)]
    # un battement qui revient au double et au quadruple aussi (préférence au temps, pas à la double croche)
    score = np.array([ac[l] + 0.5 * ac[min(len(ac) - 1, 2 * l)] + 0.25 * ac[min(len(ac) - 1, 4 * l)] for l in lags])
    l = int(lags[int(score.argmax())])
    # affinage parabolique
    if 1 <= l < len(ac) - 1:
        a, b, c = ac[l - 1], ac[l], ac[l + 1]
        dl = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    else:
        dl = 0.0
    periode = (l + max(-0.5, min(0.5, dl))) * pas_s
    bpm = 60.0 / periode
    if not bpm_connu:
        while bpm < 80:
            bpm *= 2
        while bpm > 180:
            bpm /= 2
        # (13/11, « Le sens du vent » demandé à 140 et lu 93 : le 3 pour 2 d'un charleston en triolets) un tempo lent (sous 100) dont le
        # 3/2 revient presque aussi fort (≥ 75 % de son autocorrélation) est le 3/2 d'un vrai tempo : mesuré sur 10 chansons d'ACE-Step au
        # tempo connu (8 justes, 2 à 84 BPM lues 168 : l'octave, qui garde la grille des mesures doublée, pas cassée)
        def ac_de(b):
            lag = 60.0 / b / pas_s
            k = int(lag)
            return float(ac[k] + (lag - k) * (ac[k + 1] - ac[k])) if 1 <= k < len(ac) - 1 else -1.0
        if bpm < 100 and ac_de(bpm * 1.5) >= 0.75 * ac_de(bpm):
            bpm *= 1.5
    else:
        bpm = float(bpm_connu) if abs(bpm - bpm_connu) / bpm_connu < 0.02 else bpm
    periode = 60.0 / bpm
    # la phase : le décalage qui met le plus d'attaques sur les temps
    p = int(round(periode / pas_s))
    phases = np.arange(p)
    t = np.arange(len(o))
    sc = np.array([o[(t - ph) % p == 0].sum() for ph in phases]) if p < 400 else np.zeros(1)
    ph = int(sc.argmax())
    conf = float((sc.max() - np.median(sc)) / (sc.std() + 1e-12)) if len(sc) > 1 else 0.0
    t1 = ph * pas_s
    ta = attaques_precises(x, sr)                          # la phase affinée : l'écart médian des attaques précises au temps le plus proche
    if len(ta) >= 8:
        e = ((ta - t1 + periode / 2) % periode) - periode / 2
        proches = e[np.abs(e) < 0.04]
        if len(proches) >= 5:
            t1 = (t1 + float(np.median(proches))) % periode
    return {"bpm": round(bpm, 2), "premier_temps_s": round(t1, 3), "confiance": round(min(1.0, conf / 6), 2)}


def attaques_precises(x, sr=SR, seuil=0.25, pas_s=0.005):
    """Les instants des attaques nettes, à la milliseconde : les pics du flux (fenêtres de 23 ms, donc en avance d'une partie de la
    fenêtre) puis, autour de chacun, le premier instant où l'énergie sur 1 ms atteint la moitié de son maximum local."""
    m = np.asarray(x, np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    o = np.maximum(enveloppe_attaques(m, sr, pas_s), 0)
    if len(o) < 40 or o.max() <= 0:
        return np.zeros(0)
    haut = seuil * o.max()
    pics = [i for i in range(1, len(o) - 1) if o[i] >= haut and o[i] >= o[i - 1] and o[i] > o[i + 1]]
    garde = []
    for i in pics:                                          # au plus une attaque par 80 ms (la plus forte)
        if garde and i - garde[-1] < int(0.08 / pas_s):
            if o[i] > o[garde[-1]]:
                garde[-1] = i
            continue
        garde.append(i)
    w = max(1, int(sr * 0.001))
    k = len(m) // w
    e = np.sqrt((m[: k * w].reshape(k, w) ** 2).mean(axis=1))
    out = []
    for i in garde:                                         # (la fenêtre fait w échantillons, pas 1 ms juste : le temps se compte en échantillons)
        t = i * pas_s
        a, b = max(0, int((t - 0.010) * sr / w)), min(k, int((t + 0.045) * sr / w))
        if b - a < 3:
            continue
        seg = e[a:b]
        j = int(np.argmax(seg >= 0.5 * seg.max()))
        out.append((a + j) * w / sr)
    return np.array(out)


def calage_sur_grille(voix, sr, bpm, premier_temps_s, subdivision=4, seuil=0.25):
    """Le calage d'une voix sur la grille (en ms) : chaque attaque nette de la voix (pic de l'enveloppe au-dessus de seuil × le
    plus fort) contre la case la plus proche (le temps divisé en `subdivision` : 4 = doubles croches). Rend la médiane signée
    (+ : la voix en retard), la médiane absolue et le 90e centile absolu, sur combien d'attaques."""
    if not bpm:
        return None
    t = attaques_precises(voix, sr, seuil)
    if len(t) < 5:
        return {"attaques": len(t), "mediane_ms": None, "mediane_abs_ms": None, "p90_abs_ms": None}
    case = 60.0 / bpm / subdivision
    e = ((t - premier_temps_s + case / 2) % case) - case / 2
    ea = np.abs(e) * 1000
    return {"attaques": len(t), "mediane_ms": round(float(np.median(e) * 1000), 1), "mediane_abs_ms": round(float(np.median(ea)), 1),
            "p90_abs_ms": round(float(np.percentile(ea, 90)), 1), "case_ms": round(case * 1000, 1)}


def decalage_entre(a, b, sr=SR, max_ms=500):
    """Le décalage (ms) qui aligne b sur a, par corrélation des attaques (+ : b est en retard sur a), et la netteté du pic."""
    oa, ob = enveloppe_attaques(a, sr, 0.005), enveloppe_attaques(b, sr, 0.005)
    n = min(len(oa), len(ob))
    if n < 200:
        return 0.0, 0.0
    oa, ob = oa[:n], ob[:n]
    m = int(max_ms / 5)
    lags = np.arange(-m, m + 1)
    c = np.array([float(np.dot(oa[max(0, -l):n - max(0, l)], ob[max(0, l):n + min(0, l)])) for l in lags])
    i = int(c.argmax())
    nett = float((c.max() - np.median(c)) / (c.std() + 1e-12))
    d = 0.0
    if 0 < i < len(c) - 1:
        a1, b1, c1 = c[i - 1], c[i], c[i + 1]
        den = a1 - 2 * b1 + c1
        d = 0.5 * (a1 - c1) / den if den else 0.0
    return round(float((lags[i] + d) * 5), 1), round(min(1.0, nett / 8), 2)


# ------------------------------------------------------------------------------------------------ un bilan complet
def bilan(fichier, genre="trap"):
    """Toutes les mesures d'un fichier : LUFS, crête vraie, plage (LRA), PLR, facteur de crête, corrélation stéréo, bandes et écart au
    genre."""
    x, sr = lire(fichier)
    e = ebur128(fichier)
    b = bandes(x, sr)
    out = {**e, "plr_db": (round(e["crete_dbtp"] - e["lufs"], 1) if e.get("lufs") is not None and e.get("crete_dbtp") is not None
                           else None),
           "facteur_crete_db": facteur_de_crete(x, sr), "correlation": correlation_stereo(x), "bandes_db": b,
           "duree_s": round(len(x) / sr, 2)}
    r = ecart_reference(b, genre)
    if r:
        out["reference"] = r
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "bilan":
        print(json.dumps(bilan(sys.argv[2], *(sys.argv[3:4] or ["trap"])), ensure_ascii=False))
    else:
        print("usage : studio_mesures.py bilan <fichier> [genre]", file=sys.stderr)
        sys.exit(2)
