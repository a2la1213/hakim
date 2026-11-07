"""(07/11, Hakim, avec l'accord d'Ahmed : « lance tout, a b c d ») ÉCOUTER VRAIMENT un morceau : chaque instrument séparé, nommé, avec son
rythme et ses notes, pour que ses instrus collent aux originaux (GTR, MBS…) au lieu de mots génériques.

  a. UN tempo et UNE tonalité par morceau : la batterie donne le tempo (autocorrélation de ses attaques), la somme des instruments à
     hauteur donne la tonalité (profils de Krumhansl) ; chaque piste se lit sur cette même grille (avant : trois tempos pour un morceau).
  b. Le RYTHME : la batterie redécoupée en kick (graves), caisse claire (médiums) et hi-hats (aigus), placés sur une grille de doubles
     croches (16 cases par mesure) ; ses roulements (des coups plus serrés qu'une double croche) ; la 808 avec ses notes et ses glissés.
  c. NOMMER chaque instrument : CLAP (laion/clap-htsat-unfused, local) compare chaque piste à des noms (darbuka, oud, mandole, cordes…) ;
     sa BIBLIOTHÈQUE (instruments-connus.json) garde l'empreinte de chaque instrument appris, et il peut en apprendre d'autres
     (« apprendre ») ; une empreinte connue l'emporte sur un nom deviné.
  d. Le RÉSULTAT : une légende anglaise précise pour ACE-Step, un résumé en mots pour lui, et une RESSEMBLANCE entre deux analyses
     (son instru contre l'original) : tempo, tonalité, instruments, motif de batterie.

Un instrument par cœur : chaque piste s'analyse sur son cœur, en parallèle. Les parties numpy se testent sans modèle ; Demucs et CLAP ne
se chargent que dans le venv de la séparation (jarvis/.venv-separation).

  python instruments.py analyser <fichier> [debut_s] [duree_s]      → JSON
  python instruments.py apprendre <nom> <fichier> [debut_s] [duree_s] [piste]
  python instruments.py comparer <analyse_a.json> <analyse_b.json>
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
BIBLIOTHEQUE = JARVIS / "instruments-connus.json"
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTES_FR = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
KS_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
# ce que CLAP cherche dans chaque piste (des noms anglais, ceux qu'il a appris) ; la bibliothèque en ajoute
NOMS = ["piano", "electric piano", "synth bell", "synth pad", "synth lead", "strings section", "violin", "cello", "flute", "ney flute",
        "oud", "mandolin", "banjo", "acoustic guitar", "electric guitar", "accordion", "qanun", "choir", "female vocal chop",
        "male vocals", "808 bass", "sub bass", "bass guitar", "trap hi-hats", "snare drum", "kick drum", "hand clap", "darbuka",
        "bendir frame drum", "tambourine", "brass", "saxophone", "organ", "harp", "music box", "vinyl crackle"]
PISTES_HAUTEUR = ("bass", "guitar", "piano", "other")
SEUIL_CONNU = 0.82                                   # une empreinte de la bibliothèque à ce point proche : c'est lui


# ------------------------------------------------------------------------------------------------- a. tempo et tonalité
def spectre(x, sr, n=4096, hop=1024):
    x = np.asarray(x, np.float32)
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    k = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(k)[:, None]
    S = np.abs(np.fft.rfft(x[idx] * np.hanning(n), axis=1))
    return S, np.fft.rfftfreq(n, 1 / sr), sr / hop


def enveloppe(x, sr, lo, hi, n=2048, hop=512):
    """La force des attaques dans une bande (flux spectral positif), à fps = sr / hop."""
    S, f, fps = spectre(x, sr, n, hop)
    m = (f >= lo) & (f < hi)
    e = np.log1p(S[:, m]).sum(1)
    d = np.maximum(0.0, np.diff(e, prepend=e[:1]))
    return d / (d.max() + 1e-9), fps


def tempo(env, fps, lo=60.0, hi=200.0):
    """Le tempo (BPM) par autocorrélation des attaques, ramené dans 70–180 (un trap à 140 n'est pas lu 70 ni 280)."""
    env = np.asarray(env, float) - np.mean(env)
    if len(env) < 4 or not np.any(env):
        return None
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    lags = np.arange(len(ac))
    bpm = 60.0 * fps / np.maximum(lags, 1)
    m = (bpm >= lo) & (bpm <= hi)
    if not m.any():
        return None
    b = float(bpm[m][np.argmax(ac[m])])
    while b < 70:
        b *= 2
    while b > 180:
        b /= 2
    return round(b, 1)


def chroma(x, sr):
    S, f, _ = spectre(x, sr, 8192, 2048)
    m = (f >= 55) & (f <= 4000)
    midi = np.round(69 + 12 * np.log2(f[m] / 440.0)).astype(int) % 12
    c = np.zeros(12)
    np.add.at(c, midi, (S[:, m] ** 2).sum(0))
    return c / (c.sum() + 1e-12)


def tonalite(c):
    """(note, 'major' | 'minor', score) : la meilleure corrélation de Krumhansl sur les 24 tonalités."""
    c = np.asarray(c, float)
    if not np.any(c):
        return None
    best = None
    for k in range(12):
        for mode, prof in (("major", KS_MAJ), ("minor", KS_MIN)):
            r = float(np.corrcoef(c, np.roll(prof, k))[0, 1])
            if best is None or r > best[2]:
                best = (NOTES[k], mode, round(r, 3))
    return best


# ------------------------------------------------------------------------------------------------- b. le rythme
def attaques(env, fps, seuil=0.3, ecart_s=0.05):
    """Les instants (s) où la bande frappe : un pic local au-dessus du seuil, 50 ms au moins entre deux."""
    env = np.asarray(env, float)
    out, dernier = [], -1e9
    s = max(seuil, float(np.mean(env) + 1.5 * np.std(env)))
    for i in range(1, len(env) - 1):
        if env[i] >= s and env[i] >= env[i - 1] and env[i] >= env[i + 1] and (i / fps - dernier) >= ecart_s:
            out.append(i / fps)
            dernier = i / fps
    return out


def grille(t_attaques, bpm, t0=0.0, cases=16, part=0.4):
    """Le motif d'une mesure (4 temps, `cases` cases) : « x » là où la bande frappe dans au moins `part` des mesures, « . » ailleurs."""
    if not t_attaques or not bpm:
        return "." * cases
    mesure = 4 * 60.0 / bpm
    pas = mesure / cases
    nb = max(1, int((max(t_attaques) - t0) // mesure) + 1)
    comptes = np.zeros(cases)
    vus = set()
    for t in t_attaques:
        if t < t0:
            continue
        i = int(round((t - t0) / pas))
        b, c = divmod(i, cases)
        if (b, c) not in vus:
            vus.add((b, c))
            comptes[c] += 1
    return "".join("x" if comptes[c] / nb >= part else "." for c in range(cases))


def roulements(t_attaques, bpm):
    """La part des coups plus serrés qu'une double croche (roulements de hi-hats en triples croches ou triolets)."""
    if len(t_attaques) < 3 or not bpm:
        return 0.0
    dc = 60.0 / bpm / 4
    d = np.diff(np.asarray(t_attaques, float))
    return round(float(np.mean(d < 0.8 * dc)), 2)


def rythme(drums, sr, bpm):
    bandes = {"kick": (30, 120), "caisse": (150, 2500), "hihats": (6000, 16000)}
    out = {}
    t_kick = None
    for nom, (lo, hi) in bandes.items():
        e, fps = enveloppe(drums, sr, lo, hi)
        t = attaques(e, fps)
        if nom == "kick":
            t_kick = t
        out[nom] = t
    t0 = t_kick[0] if t_kick else 0.0
    return {"motifs": {k: grille(v, bpm, t0) for k, v in out.items()}, "roulements_hihats": roulements(out["hihats"], bpm),
            "coups": {k: len(v) for k, v in out.items()}}


def suivre_basse(bass, sr, pas_s=0.05, lo=30, hi=400):
    """La hauteur de la basse toutes les 50 ms (Hz, None quand elle se tait)."""
    x = np.asarray(bass, np.float32)
    n, hop = 8192, int(pas_s * sr)
    out = []
    plafond = np.max(np.abs(x)) if len(x) else 0
    for i in range(0, max(1, len(x) - n), hop):
        seg = x[i:i + n]
        if np.max(np.abs(seg)) < 0.05 * (plafond + 1e-9):
            out.append(None)
            continue
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
        f = np.fft.rfftfreq(n, 1 / sr)
        m = (f >= lo) & (f <= hi)
        out.append(float(f[m][np.argmax(S[m])]) if m.any() else None)
    return out


def glisses(hauteurs, pas_s=0.05, demi_tons=2.0, fenetre_s=0.25):
    """Combien de fois la basse GLISSE (une 808 « slide ») : 2 demi-tons ou plus en 0,25 s, sans se taire, par petits pas (2 demi-tons au
    plus d'une trame à l'autre, et au moins 3 pas qui bougent) : un saut franc d'une note à l'autre n'est pas un glissé."""
    h = [None if v is None else 12 * np.log2(v / 440.0) for v in hauteurs]
    k = max(2, int(fenetre_s / pas_s))
    n, i = 0, 0
    while i + k < len(h):
        seg = h[i:i + k + 1]
        pas = [abs(b - a) for a, b in zip(seg, seg[1:])] if all(v is not None for v in seg) else []
        if pas and abs(seg[-1] - seg[0]) >= demi_tons and max(pas) <= 2.0 and sum(1 for d in pas if d >= 0.3) >= 3:
            n += 1
            i += k
        else:
            i += 1
    return n


def notes_principales(hauteurs, combien=4):
    """Les notes les plus tenues de la basse (noms anglais), dans l'ordre d'importance."""
    c = {}
    for v in hauteurs:
        if v is None:
            continue
        k = int(round(69 + 12 * np.log2(v / 440.0))) % 12
        c[k] = c.get(k, 0) + 1
    return [NOTES[k] for k, _ in sorted(c.items(), key=lambda z: -z[1])[:combien]]


# ------------------------------------------------------------------------------------------------- c. nommer (CLAP + bibliothèque)
def lire_bibliotheque(fichier=None):
    try:
        d = json.loads(Path(fichier or BIBLIOTHEQUE).read_text(encoding="utf-8"))
        return [x for x in d if isinstance(x, dict) and x.get("nom") and isinstance(x.get("empreinte"), list)]
    except (OSError, ValueError):
        return []


def ecrire_bibliotheque(l, fichier=None):
    f = Path(fichier or BIBLIOTHEQUE)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(l, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


def cosinus(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def reconnaitre(empreinte, bibliotheque, seuil=SEUIL_CONNU):
    """Le nom connu le plus proche (et sa proximité), s'il dépasse le seuil ; sinon None."""
    best = None
    for x in bibliotheque:
        s = cosinus(empreinte, x["empreinte"])
        if best is None or s > best[1]:
            best = (x["nom"], round(s, 3))
    return best if best and best[1] >= seuil else None


def apprendre_empreinte(bibliotheque, nom, empreinte):
    """Ajoute (ou affine : la moyenne) l'empreinte d'un instrument ; rend la bibliothèque."""
    nom = " ".join(str(nom).split())[:60]
    for x in bibliotheque:
        if x["nom"].lower() == nom.lower():
            n = int(x.get("n", 1))
            x["empreinte"] = list((np.asarray(x["empreinte"], float) * n + np.asarray(empreinte, float)) / (n + 1))
            x["n"] = n + 1
            return bibliotheque
    bibliotheque.append({"nom": nom, "empreinte": [float(v) for v in empreinte], "n": 1, "appris": time.strftime("%Y-%m-%d")})
    return bibliotheque


class Clap:
    """CLAP chargé une fois : empreintes de sons et de noms (48 kHz, 10 s au plus par extrait)."""

    def __init__(self):
        import torch
        from transformers import ClapModel, ClapProcessor
        self.torch = torch
        self.m = ClapModel.from_pretrained("laion/clap-htsat-unfused").eval()
        self.p = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
        self._textes = {}

    def son(self, x, sr):
        x = np.asarray(x, np.float32)
        if sr != 48000:
            n = int(len(x) * 48000 / sr)
            x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        x = x[: 48000 * 10]
        with self.torch.no_grad():
            e = self.m.get_audio_features(**self.p(audio=[x], sampling_rate=48000, return_tensors="pt"))
        e = e.pooler_output if hasattr(e, "pooler_output") else e
        return e[0].numpy()

    def textes(self, noms):
        cle = tuple(noms)
        if cle not in self._textes:
            with self.torch.no_grad():
                e = self.m.get_text_features(**self.p(text=[f"the sound of {n}" for n in noms], return_tensors="pt", padding=True))
            e = e.pooler_output if hasattr(e, "pooler_output") else e
            self._textes[cle] = e.numpy()
        return self._textes[cle]

    def deviner(self, empreinte, noms=NOMS, combien=3):
        t = self.textes(noms)
        a = np.asarray(empreinte, float)
        s = (t @ a) / (np.linalg.norm(t, axis=1) * np.linalg.norm(a) + 1e-12)
        p = np.exp(s * 100 - np.max(s * 100))
        p = p / p.sum()
        return [(noms[i], round(float(p[i]), 2)) for i in np.argsort(-p)[:combien]]


# ------------------------------------------------------------------------------------------------- d. légende, mots, ressemblance
def legende(a):
    """L'analyse → la légende anglaise donnée à ACE-Step (512 caractères au plus)."""
    p = []
    if a.get("tempo"):
        p.append(f"{int(round(a['tempo']))} BPM")
    if a.get("tonalite"):
        p.append(f"{a['tonalite'][0]} {a['tonalite'][1]}")
    r = a.get("rythme") or {}
    m = r.get("motifs") or {}
    if m:
        p.append(f"drums pattern kick {m.get('kick', '')}, snare {m.get('caisse', '')}, hi-hats {m.get('hihats', '')}")
    if (r.get("roulements_hihats") or 0) >= 0.15:
        p.append("fast rolling trap hi-hat triplets")
    b = a.get("basse") or {}
    if b.get("notes"):
        p.append(("sliding 808 bass" if (b.get("glisses") or 0) >= 2 else "deep bass") + " on " + ", ".join(b["notes"]))
    for i in a.get("instruments") or []:
        if i.get("piste") in ("drums", "bass"):
            continue
        n = i.get("connu") or (i.get("noms") or [[None]])[0][0]
        if n:
            p.append(f"{n} melody" + (f" ({', '.join(i['notes'][:4])})" if i.get("notes") else ""))
    return ", ".join(x for x in p if x)[:512]


def en_mots(a):
    """L'analyse → quelques mots pour Hakim (français)."""
    p = []
    if a.get("tempo"):
        p.append(f"~{int(round(a['tempo']))} BPM")
    if a.get("tonalite"):
        k = NOTES.index(a["tonalite"][0])
        p.append(f"{NOTES_FR[k]} {'mineur' if a['tonalite'][1] == 'minor' else 'majeur'}")
    r = a.get("rythme") or {}
    if r.get("motifs"):
        m = r["motifs"]
        p.append(f"batterie : kick {m.get('kick')}, caisse {m.get('caisse')}, hi-hats {m.get('hihats')}"
                 + (f", roulements {int(100 * r.get('roulements_hihats', 0))} %" if r.get("roulements_hihats") else ""))
    b = a.get("basse") or {}
    if b.get("notes"):
        p.append(f"basse : {', '.join(b['notes'])}" + (f", {b['glisses']} glissés" if b.get("glisses") else ""))
    for i in a.get("instruments") or []:
        n = i.get("connu") or ", ".join(f"{x[0]} {int(100 * x[1])} %" for x in (i.get("noms") or [])[:2])
        if n:
            p.append(f"{i['piste']} : {n}")
    return " · ".join(p)


def _noms_de(a):
    s = set()
    for i in a.get("instruments") or []:
        if i.get("connu"):
            s.add(i["connu"].lower())
        for n, pr in (i.get("noms") or [])[:2]:
            if pr >= 0.2:
                s.add(n.lower())
    return s


def _motif_proche(x, y):
    if not x or not y or len(x) != len(y):
        return 0.0
    return sum(1 for a, b in zip(x, y) if a == b) / len(x)


def ressemblance(a, b):
    """0 à 1, et le détail : tempo (même, moitié ou double à 3 % près), tonalité (même, relative), instruments, motifs de batterie."""
    d = {}
    ta, tb = a.get("tempo"), b.get("tempo")
    if ta and tb:
        r = min(abs(ta - tb), abs(ta - 2 * tb), abs(2 * ta - tb)) / max(ta, tb)
        d["tempo"] = round(max(0.0, 1 - r / 0.06), 2)
    ka, kb = a.get("tonalite"), b.get("tonalite")
    if ka and kb:
        ia, ib = NOTES.index(ka[0]), NOTES.index(kb[0])
        relative = (ka[1] != kb[1]) and ((ka[1] == "minor" and (ia + 3) % 12 == ib) or (ka[1] == "major" and (ia + 9) % 12 == ib))
        d["tonalite"] = 1.0 if (ia == ib and ka[1] == kb[1]) else (0.7 if relative else 0.0)
    na, nb = _noms_de(a), _noms_de(b)
    if na or nb:
        d["instruments"] = round(len(na & nb) / max(1, len(na | nb)), 2)
    ma, mb = (a.get("rythme") or {}).get("motifs") or {}, (b.get("rythme") or {}).get("motifs") or {}
    if ma and mb:
        d["batterie"] = round(float(np.mean([_motif_proche(ma.get(k), mb.get(k)) for k in ("kick", "caisse", "hihats")])), 2)
    poids = {"tempo": 0.25, "tonalite": 0.2, "instruments": 0.3, "batterie": 0.25}
    tot = sum(poids[k] for k in d)
    return {"score": round(sum(d[k] * poids[k] for k in d) / tot, 2) if tot else 0.0, **d}


# ------------------------------------------------------------------------------------------------- l'analyse entière
def lire(fichier, debut=30.0, duree=30.0):
    import soundfile as sf
    x, sr = sf.read(str(fichier), dtype="float32", always_2d=True)
    x = x.mean(1)
    a, b = int(max(0, debut) * sr), int(max(0, debut + duree) * sr)
    if a >= len(x):                                          # morceau plus court : depuis le début
        a, b = 0, int(duree * sr)
    return x[a:b], sr


def separer(x, sr):
    """Demucs htdemucs_6s : {drums, bass, guitar, piano, other, vocals} (mono, au taux du modèle)."""
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    m = get_model("htdemucs_6s").eval()
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    m.to(dev)
    if sr != m.samplerate:
        n = int(len(x) * m.samplerate / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    with torch.no_grad():
        s = apply_model(m, torch.tensor(np.stack([x, x]))[None].to(dev), device=dev, progress=False)[0]
    return {n: s[i].mean(0).cpu().numpy() for i, n in enumerate(m.sources)}, m.samplerate


def _db(x):
    return float(10 * np.log10(np.mean(np.asarray(x, float) ** 2) + 1e-12))


def analyser(fichier, debut=30.0, duree=30.0, clap=None, bibliotheque=None):
    t0 = time.time()
    x, sr = lire(fichier, debut, duree)
    pistes, sr = separer(x, sr)
    sys.path.insert(0, str(ICI))
    import cascade as C
    plancher = max(_db(v) for v in pistes.values()) - 25
    presentes = {k: v for k, v in pistes.items() if _db(v) > max(-60.0, plancher)}
    drums = presentes.get("drums")
    env, fps = enveloppe(drums if drums is not None else x, sr, 30, 16000)
    bpm = tempo(env, fps)
    c = sum(chroma(presentes[k], sr) * (10 ** (_db(presentes[k]) / 20)) for k in PISTES_HAUTEUR if k in presentes) \
        if any(k in presentes for k in PISTES_HAUTEUR) else chroma(x, sr)
    ton = tonalite(c)
    a = {"fichier": str(fichier), "debut_s": debut, "duree_s": round(len(x) / sr, 1), "tempo": bpm, "tonalite": ton}
    clap = clap if clap is not None else Clap()
    biblio = bibliotheque if bibliotheque is not None else lire_bibliotheque()

    def une(nom, son):                                       # un instrument par cœur
        e = clap.son(son, sr)
        i = {"piste": nom, "db": round(_db(son), 1), "noms": clap.deviner(e)}
        k = reconnaitre(e, biblio)
        if k:
            i["connu"], i["proche"] = k
        if nom in PISTES_HAUTEUR and nom != "bass":
            notes = [n for _, l in C.notes_du_temps(nom, son, sr) for n in l]
            if notes:
                vus = []
                for n in notes:
                    n2 = NOTES[NOTES_FR.index(n.rstrip("0123456789-"))] if n.rstrip("0123456789-") in NOTES_FR else n
                    if n2 not in vus:
                        vus.append(n2)
                i["notes"] = vus[:6]
        return i

    with ThreadPoolExecutor(max_workers=max(2, min(6, os.cpu_count() or 4)), thread_name_prefix="coeur") as cx:
        futs = [cx.submit(une, k, v) for k, v in presentes.items() if k != "vocals" or _db(v) > plancher + 10]
        if drums is not None:
            fr = cx.submit(rythme, drums, sr, bpm)
        if "bass" in presentes:
            fb = cx.submit(suivre_basse, presentes["bass"], sr)
        a["instruments"] = [f.result() for f in futs]
        if drums is not None:
            a["rythme"] = fr.result()
        if "bass" in presentes:
            h = fb.result()
            a["basse"] = {"notes": notes_principales(h), "glisses": glisses(h)}
    a["legende"] = legende(a)
    a["mots"] = en_mots(a)
    a["ms"] = int((time.time() - t0) * 1000)
    return a


def apprendre(nom, fichier, debut=0.0, duree=10.0, piste=None):
    x, sr = lire(fichier, debut, duree)
    if piste:
        p, sr = separer(x, sr)
        x = p[piste]
    clap = Clap()
    b = apprendre_empreinte(lire_bibliotheque(), nom, clap.son(x, sr))
    ecrire_bibliotheque(b)
    return {"nom": nom, "connus": len(b)}


def main(argv):
    if len(argv) >= 2 and argv[0] == "analyser":
        print(json.dumps(analyser(argv[1], *(float(v) for v in argv[2:4])), ensure_ascii=False))
    elif len(argv) >= 3 and argv[0] == "apprendre":
        print(json.dumps(apprendre(argv[1], argv[2], *(float(v) for v in argv[3:5]), *(argv[5:6] or [None])), ensure_ascii=False))
    elif len(argv) == 3 and argv[0] == "comparer":
        a, b = (json.loads(Path(f).read_text(encoding="utf-8")) for f in argv[1:3])
        print(json.dumps(ressemblance(a, b), ensure_ascii=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
