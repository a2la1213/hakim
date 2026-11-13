"""Des sons et des images à VÉRITÉ CONNUE pour les tests de l'atelier vidéo (13/11) : une musique de synthèse dont on sait
chaque temps et chaque section (intro, couplets, refrains, pont), et des « photos » libres (aplats, dégradés, silhouettes de
vêtements) faites ici, jamais une photo privée."""
import math
import random

import numpy as np

SR = 44100

def _env(n, dec):
    t = np.arange(n) / SR
    e = np.exp(-t / dec)
    a = min(n, int(0.001 * SR))
    e[:a] *= np.linspace(0, 1, a)
    return e

def kick(sr=SR):
    n = int(0.35 * sr); t = np.arange(n) / sr
    f = 45 + 75 * np.exp(-t / 0.04)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / sr) * _env(n, 0.12)

def snare(rng):
    n = int(0.18 * SR)
    x = rng.standard_normal(n) * _env(n, 0.05)
    x = np.convolve(x, [1, -0.6], mode="same")
    return 0.35 * x

def hat(rng):
    n = int(0.05 * SR)
    x = rng.standard_normal(n); x = np.diff(x, prepend=0)
    return 0.08 * x * _env(n, 0.012)

def note(freq, dur, amp=0.15, harm=(1, 0.5, 0.25)):
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(h * np.sin(2 * np.pi * freq * (k + 1) * t) for k, h in enumerate(harm))
    e = np.minimum(1, t / 0.02) * np.exp(-t / max(0.2, dur))
    return amp * x * e

def ajouter(y, x, i):
    if i >= len(y): return
    m = min(len(x), len(y) - i)
    y[i:i + m] += x[:m]

ACCORDS = {"I": [261.6, 329.6, 392.0], "V": [196.0, 246.9, 293.7], "vi": [220.0, 261.6, 329.6], "IV": [174.6, 220.0, 261.6],
           "ii": [146.8, 174.6, 220.0], "iii": [164.8, 196.0, 246.9], "bVII": [233.1, 293.7, 349.2]}

def morceau(bpm=123.7, duree=40.0, debut=0.371, seed=0, sections=None, bruit=0.003):
    """Rend (signal stéréo, temps vrais, débuts de section [(nom, t)])."""
    rng = np.random.default_rng(seed)
    per = 60.0 / bpm
    if sections is None:
        sections = [("couplet", int((duree - debut) / per / 4) + 1)]
    n = int(duree * SR)
    y = np.zeros(n)
    temps, bornes = [], []
    k = 0
    for nom, mesures in sections:
        bornes.append((nom, debut + k * per))
        prog = {"intro": ["I", "I", "IV", "IV"], "couplet": ["vi", "IV", "I", "V"], "refrain": ["I", "V", "vi", "IV"],
                "pont": ["ii", "iii", "bVII", "V"], "outro": ["I", "IV", "I", "I"]}[nom]
        force = {"intro": 0.35, "couplet": 0.6, "refrain": 1.0, "pont": 0.55, "outro": 0.3}[nom]
        for m in range(mesures):
            ch = ACCORDS[prog[m % 4]]
            t0 = debut + (k + 0) * per
            for b in range(4):
                tb = debut + k * per
                if tb >= duree: break
                temps.append(tb)
                i = int(round(tb * SR))
                if nom != "intro":
                    ajouter(y, kick() * (0.7 + 0.3 * force), i)
                    if b in (1, 3) and nom in ("refrain", "pont", "couplet"):
                        ajouter(y, snare(rng) * force, i)
                    for h in range(2 if nom != "refrain" else 4):
                        ajouter(y, hat(rng) * force, i + int(h * per / (2 if nom != "refrain" else 4) * SR))
                else:
                    ajouter(y, kick() * 0.25, i)
                ajouter(y, note(ch[0] / 4, per * 0.9, 0.12 * force), i)
                k += 1
            # l'accord tenu (pad) sur la mesure
            pad = sum(note(f, 4 * per, 0.05 * (0.5 + force), (1, 0.3)) for f in ch)
            ajouter(y, pad, int(round(t0 * SR)))
            if nom == "refrain":   # une mélodie au refrain
                for j, f in enumerate([ch[2] * 2, ch[1] * 2, ch[2] * 2, ch[0] * 2]):
                    ajouter(y, note(f, per * 0.8, 0.07, (1, 0.2)), int(round((t0 + j * per) * SR)))
    y += bruit * rng.standard_normal(n)
    y = y / (np.abs(y).max() + 1e-9) * 0.8
    st = np.stack([y, np.roll(y, 7) * 0.98], axis=1)
    return st.astype(np.float32), np.array(temps), bornes

def ecrire(chemin, x, sr=SR, ffmpeg=None):
    import subprocess
    import atelier_video
    ffmpeg = ffmpeg or atelier_video.FFMPEG
    x = np.asarray(x, np.float32)
    if x.ndim == 1: x = x[:, None]
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac", str(x.shape[1]), "-i", "-",
                    *(["-c:a", "libmp3lame", "-b:a", "192k"] if str(chemin).endswith(".mp3") else []), str(chemin)],
                   input=np.ascontiguousarray(x).tobytes(), check=True)
    return chemin


# ------------------------------------------------------------------------------------------------ les images (Pillow : le python de la vidéo)


PALETTES = [((32, 34, 46), (196, 160, 112)), ((240, 232, 220), (120, 40, 52)), ((18, 52, 60), (230, 200, 160)),
            ((90, 20, 30), (250, 220, 200)), ((230, 225, 215), (30, 30, 34)), ((40, 60, 110), (240, 190, 120)),
            ((200, 120, 90), (40, 30, 30)), ((20, 20, 22), (220, 210, 190)), ((150, 170, 150), (40, 50, 40)),
            ((250, 240, 235), (190, 90, 110)), ((60, 40, 80), (230, 200, 240)), ((210, 190, 150), (70, 50, 30))]

def degrade(w, h, a, b, angle=0.0):
    from PIL import Image
    ca, sa = math.cos(angle), math.sin(angle)
    y, x = np.mgrid[0:h, 0:w]
    u = np.clip(((x / w - 0.5) * ca + (y / h - 0.5) * sa) + 0.5, 0, 1)[..., None]
    c = np.array(a, float) + (np.array(b, float) - np.array(a, float)) * u
    return Image.fromarray(c.astype(np.uint8))


def silhouette(d, w, h, couleur, kind):
    cx = w / 2
    if kind == 0:   # un manteau
        d.polygon([(cx - w*0.18, h*0.22), (cx + w*0.18, h*0.22), (cx + w*0.30, h*0.85), (cx - w*0.30, h*0.85)], fill=couleur)
        d.polygon([(cx - w*0.18, h*0.22), (cx - w*0.34, h*0.62), (cx - w*0.27, h*0.64), (cx - w*0.12, h*0.32)], fill=couleur)
        d.polygon([(cx + w*0.18, h*0.22), (cx + w*0.34, h*0.62), (cx + w*0.27, h*0.64), (cx + w*0.12, h*0.32)], fill=couleur)
    elif kind == 1:  # une robe
        d.polygon([(cx - w*0.10, h*0.20), (cx + w*0.10, h*0.20), (cx + w*0.08, h*0.42), (cx + w*0.30, h*0.88), (cx - w*0.30, h*0.88), (cx - w*0.08, h*0.42)], fill=couleur)
    elif kind == 2:  # un t-shirt
        d.polygon([(cx - w*0.22, h*0.28), (cx + w*0.22, h*0.28), (cx + w*0.36, h*0.40), (cx + w*0.26, h*0.46), (cx + w*0.20, h*0.40),
                   (cx + w*0.20, h*0.78), (cx - w*0.20, h*0.78), (cx - w*0.20, h*0.40), (cx - w*0.26, h*0.46), (cx - w*0.36, h*0.40)], fill=couleur)
    else:            # un sac (cercle + anse)
        d.ellipse((cx - w*0.25, h*0.40, cx + w*0.25, h*0.80), fill=couleur)
        d.arc((cx - w*0.15, h*0.25, cx + w*0.15, h*0.55), 180, 360, fill=couleur, width=int(w*0.03))

def photo(i, w=1200, h=1600, chemin=None):
    from PIL import ImageDraw, ImageFilter
    a, b = PALETTES[i % len(PALETTES)]
    im = degrade(w, h, a, b, angle=0.6 * i)
    d = ImageDraw.Draw(im)
    rnd = random.Random(i)
    for _ in range(5):
        r = rnd.randint(w // 14, w // 5)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        d.ellipse((x - r, y - r, x + r, y + r), outline=tuple(min(255, c + 30) for c in b), width=3)
    silhouette(d, w, h, b if sum(b) < sum(a) else tuple(int(c * 0.35) for c in a), i % 4)
    im = im.filter(ImageFilter.SMOOTH)
    if chemin: im.save(chemin, quality=92)
    return im


def source_dense(seed=2, sat=8.0, scie=0.3, crete_db=-0.5, duree=16.0):
    """Une musique dense et saturée, avec une basse en dents de scie (riche en aigus) : là où l'AAC fait monter la crête vraie
    de 2 à 3 dB (trouvé le 13/11 : à −2,9 dBTP en WAV, −0,5 dBTP une fois en AAC)."""
    x, _, _ = morceau(140, duree, 0.2, seed=seed)
    m = np.tanh(sat * x[:, 0].astype(float))
    t = np.arange(len(m)) / SR
    y = m + scie * (2 * ((55 * t) % 1) - 1)
    y = y / np.abs(y).max() * 10 ** (crete_db / 20)
    return np.stack([y, y], 1).astype(np.float32)
