"""(04/11, Ahmed, 18:55 → 19:10 : « s'il trouve des voix, le background qui contient des voix est aussi séparé en voix et background
(qui vont vers le 2e cœur CPU pour le processing des paroles par le ribosome), et ainsi de suite jusqu'à 8 voix en background » ;
« 2 process : un pour background = voix + bruit, un pour la musique ; les 2 sont activés par la détection de la première bande-son » ;
« un instrument par cœur CPU ; dans la musique il extrait en premier les basses » ; « chaque voix est séparée selon le volume et le
timbre ») la séparation en CASCADE de ce que Hakim entend (design : docs/superpowers/specs/2026-11-04-separation-en-cascade-design.md).

- L'AIGUILLAGE : après la première séparation de Demucs (voix / accompagnement), la parole va à la route des voix, la musique (des
  hauteurs qui durent, une basse, une batterie) à la route de la musique, les deux s'il y a les deux ; un bruit (sans hauteur tenue) ne
  réveille aucun cœur.
- La ROUTE DES VOIX, en cascade : l'empreinte WeSpeaker de fenêtres de 1,5 s (pas de 0,25 s) ; à chaque étage, la fenêtre la plus FORTE
  qui parle encore donne la graine, les fenêtres du même TIMBRE la rejoignent, les trames qui leur ressemblent sortent ; le reste descend
  à l'étage suivant ; on s'arrête quand il ne reste que du bruit, ou à 8 voix. Deux voix au timbre trop proche ne font qu'une (jamais la
  voix de papa coupée en deux). Mesuré le 04/11 sur des mélanges des voix du Mac (vérité connue) : en alternance, 1 à 8 voix retrouvées
  avec leurs mots ; quand elles parlent EN MÊME TEMPS, la cascade ne sort que la plus forte (ou deux, quand l'une est 3 dB plus
  forte) : leurs mots se mêlent dans sa voix ; la séparation par les harmoniques a été essayée, elle sortait des voix fantômes.
- La ROUTE DE LA MUSIQUE : Demucs htdemucs_6s, un instrument par cœur, la basse d'abord, puis la batterie, la guitare, le piano, le
  reste ; pour chacun, des mots (ses notes, sa tonalité, son rythme, ses graves / médiums / aigus), jamais le son.
Tout en numpy : le modèle (Demucs) et l'empreinte (WeSpeaker) sont donnés par l'appelant (jarvis/separation.py)."""
import numpy as np

TAUX = 16000
HOP = 160                                   # trames de 10 ms
FEN, PAS = 150, 25                          # fenêtres d'empreinte : 1,5 s, pas de 0,25 s (en trames)
MAX_VOIX = 8
SEUIL_TIMBRE = 0.55                         # même timbre (fenêtres entre elles, mesuré : 0,69 à 0,87 pour une même voix du Mac
                                            # d'une moitié de phrase à l'autre, 0,46 au plus entre deux voix différentes)
SEUIL_FUSION = 0.62                         # deux voix sorties plus proches : la même personne
VOIX_MIN_S = 0.5                            # moins de 0,5 s de parole : pas une voix
PLANCHER_DB = 20                            # une voix 20 dB sous la plus forte : du bruit


def _runs(m):
    d = np.diff(np.concatenate([[0], np.asarray(m).astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _lisser(m, trou, bout):
    """Comble les trous de moins de `trou` trames (entre deux paroles), enlève les bouts de moins de `bout` trames."""
    m = np.asarray(m, bool).copy()
    for a, b in _runs(~m):
        if a > 0 and b < len(m) and b - a < trou:
            m[a:b] = True
    for a, b in _runs(m):
        if b - a < bout:
            m[a:b] = False
    return m


def trames_db(x):
    x = np.asarray(x, np.float32)
    n = len(x) // HOP
    return 10 * np.log10((x[:n * HOP].reshape(n, HOP).astype(np.float64) ** 2).mean(1) + 1e-12)


def parole_trames(e):
    """Les trames qui parlent : 8 dB au-dessus du plancher, à moins de 35 dB de la plus forte (et au-dessus de −70 dBFS)."""
    e = np.asarray(e, float)
    if not len(e):
        return np.zeros(0, bool)
    seuil = max(np.percentile(e, 10) + 8, e.max() - 35, -70)
    return _lisser(e > seuil, 15, 8)


def _scores(fen, sims, n):
    """La ressemblance de chaque trame : la moyenne des fenêtres qui la couvrent, pondérée vers leur centre (des frontières nettes
    entre deux voix qui se suivent)."""
    som, poids = np.zeros(n), np.zeros(n)
    for (a, b), s in zip(fen, sims):
        w = np.hanning(b - a + 2)[1:-1]
        som[a:b] += w * s
        poids[a:b] += w
    return np.where(poids > 0, som / np.maximum(poids, 1e-9), -1.0)


def cascade(x, empreintes, max_voix=MAX_VOIX, seuil=SEUIL_TIMBRE, journal=None):
    """x : la voix séparée par Demucs, 16 kHz. empreintes(liste d'audios de 1,5 s) → (k, d) vecteurs normés.
    Rend les voix, de la plus forte à la plus faible : [{"masque": bool par trame, "rms_db", "c": son timbre}]."""
    x = np.asarray(x, np.float32)
    e = trames_db(x)
    parle = parole_trames(e)
    n = len(parle)
    if parle.sum() < VOIX_MIN_S * 100:
        return []
    debuts = list(range(0, max(1, n - FEN + 1), PAS)) if n >= FEN else [0]
    fen = [(s, min(n, s + FEN)) for s in debuts]
    fen = [(a, b) for a, b in fen if parle[a:b].mean() >= 0.3]
    if not fen:
        return []
    E = np.asarray(empreintes([np.pad(x[a * HOP:b * HOP], (0, FEN * HOP - len(x[a * HOP:b * HOP]))) for a, b in fen]), float)
    lin = 10 ** (e / 10)
    reste = parle.copy()
    voix = []
    for _ in range(4 * max_voix):                                  # (une graine sans voix est consommée : la boucle finit)
        if len(voix) >= max_voix or reste.sum() < VOIX_MIN_S * 100:
            break
        force = np.array([lin[a:b][reste[a:b]].sum() if reste[a:b].mean() >= 0.3 else -1.0 for a, b in fen])
        if force.max() <= 0:
            break
        g = int(np.argmax(force))                                  # la plus FORTE d'abord
        c = E[g].copy()
        for _ in range(3):                                         # son TIMBRE : les fenêtres qui lui ressemblent
            mb = (E @ c) >= seuil
            mb[g] = True
            c = E[mb].mean(0)
            c /= np.linalg.norm(c) or 1.0
        m = reste & (_scores(fen, E @ c, n) >= seuil)
        m = _lisser(m, 10, 20) & reste
        if m.sum() < VOIX_MIN_S * 100:
            a, b = fen[g]
            reste[a:b] = False
            continue
        voix.append({"masque": m, "rms_db": float(10 * np.log10(lin[m].mean() + 1e-12)), "c": c})
        reste &= ~m                                                # le reste descend à l'étage suivant
        if journal is not None:
            journal.append(("voix", len(voix), int(m.sum())))
    voix = sorted(fusionner(voix, lin), key=lambda v: -v["rms_db"])
    # (04/11, mesuré : dans un bruit rose, une « voix » 29,5 dB sous les autres, que Whisper a lue « Thank you. ») trop faible
    # pour être quelqu'un : du bruit, pas une voix à qui répondre
    return [v for v in voix if v["rms_db"] >= voix[0]["rms_db"] - PLANCHER_DB] if voix else []


def fusionner(voix, lin):
    """Deux voix sorties au timbre trop proche (≥ SEUIL_FUSION) : une seule personne, la plus longue garde les trames de l'autre.
    Un filet : un étage dont la graine était une fenêtre à cheval sur deux voix peut laisser la même voix à l'étage suivant."""
    fus = []
    for v in sorted(voix, key=lambda v: -v["masque"].sum()):
        w = next((w for w in fus if float(v["c"] @ w["c"]) >= SEUIL_FUSION), None)
        if w is None:
            fus.append(v)
        else:
            w["masque"] = w["masque"] | v["masque"]
            w["rms_db"] = float(10 * np.log10(lin[w["masque"]].mean() + 1e-12))
    return fus


def segments(masque, colle=30):
    """[[début, fin]] en secondes ; deux paroles à moins de 0,3 s l'une de l'autre ne font qu'un segment."""
    fus = []
    for a, b in _runs(masque):
        if fus and a - fus[-1][1] < colle:
            fus[-1] = (fus[-1][0], b)
        else:
            fus.append((a, b))
    return [[round(float(a) / 100, 2), round(float(b) / 100, 2)] for a, b in fus]


def compacter(x, masque, marge=10, blanc=0.25):
    """(04/11, vu : Whisper rendait « ... » sur une voix seule au milieu de 18 s de silence, et ses mots sur la même voix mise bout
    à bout) le court fichier d'une voix : ses moments de parole mis bout à bout, 0,25 s de silence entre deux, fondus."""
    x = np.asarray(x, np.float32)
    g = np.repeat(np.asarray(masque, np.float32), HOP)
    g = np.pad(g, (0, max(0, len(x) - len(g))))[:len(x)]
    k = np.hanning(161)
    g = np.convolve(g, k / k.sum(), "same")
    y = x * g
    blanc_n = np.zeros(int(blanc * TAUX), np.float32)
    morceaux = [blanc_n]
    for a, b in segments(masque):
        i, j = max(0, int(a * 100) - marge) * HOP, min(len(x), (int(b * 100) + marge) * HOP)
        morceaux += [y[i:j], blanc_n]
    return np.concatenate(morceaux).astype(np.float32)


# ---- l'aiguillage ----

def _db(x):
    x = np.asarray(x, np.float64)
    return float(10 * np.log10((x ** 2).mean() + 1e-12)) if len(x) else -120.0


def hauteurs_tenues(x, sr):
    """La part de l'énergie (80 Hz à 4 kHz) dans des pics qui durent au moins 4 trames de 23 ms : 0,45 à 0,48 pour une musique
    (mesuré le 04/11), 0,00 pour un bruit rose, un ronflement ou une parole laissée par Demucs."""
    x = np.asarray(x, np.float32)
    n, h = 4096, 1024
    if len(x) < n + 4 * h:
        return 0.0
    t = np.lib.stride_tricks.sliding_window_view(x, n)[::h] * np.hanning(n).astype(np.float32)
    S = np.abs(np.fft.rfft(t, axis=1))
    f = np.fft.rfftfreq(n, 1 / sr)
    S = S[:, (f > 80) & (f < 4000)]
    lm = np.log(S + 1e-9)
    noyau = np.ones(31) / 31
    env = np.apply_along_axis(lambda r: np.convolve(r, noyau, "same"), 1, lm)
    pic = (lm - env) > 2.0
    dure = pic[:-3] & pic[1:-2] & pic[2:-1] & pic[3:]
    e = S ** 2
    return float((e[:-3] * dure).sum() / (e.sum() + 1e-12))


def aiguiller(melange, voix, accompagnement, sr, pistes=None):
    """La première écoute : {"voix", "musique", "bruit"} (booléens) et ses mesures. pistes (optionnel) : les pistes de Demucs
    (drums, bass…), une basse ou une batterie suffisent à dire « musique »."""
    md, vd, ad = _db(melange), _db(voix), _db(accompagnement)
    tenu = hauteurs_tenues(accompagnement, sr) if ad > -60 else 0.0
    rythme = max((_db(pistes[k]) for k in ("drums", "bass") if pistes and k in pistes), default=-120.0)
    present = ad > max(-60.0, md - 25)
    musique = present and (tenu >= 0.15 or rythme >= max(-55.0, ad - 8))
    return {"voix": vd > max(-55.0, md - 30), "musique": bool(musique), "bruit": bool(present and not musique),
            "mesures": {"melange_db": round(md, 1), "voix_db": round(vd, 1), "fond_db": round(ad, 1), "tenues": round(tenu, 2),
                        "rythme_db": round(rythme, 1)}}


# ---- la route de la musique : un instrument par cœur, la basse d'abord ----

ORDRE = [("bass", "la basse"), ("drums", "la batterie"), ("guitar", "la guitare"), ("piano", "le piano"), ("other", "le reste")]
NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
REGISTRES = {"bass": (30, 400), "guitar": (80, 1500), "piano": (50, 2500), "other": (80, 2000), "drums": (40, 2000)}


def _attaques(S, dt):
    flux = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(axis=1)
    if not len(flux) or flux.max() <= 0:
        return 0.0
    seuil = flux.mean() + flux.std()
    pics = (flux[1:-1] > seuil) & (flux[1:-1] >= flux[:-2]) & (flux[1:-1] >= flux[2:])
    return float(pics.sum() / (len(flux) * dt))


def analyser_instrument(nom, x, sr, tonalite, analyser_fond):
    """Un instrument séparé, en nombres : ses notes (les classes de hauteur les plus fortes de son registre), sa tonalité, ses attaques
    par seconde, son tempo et ses bandes (analyser_fond de separation.py)."""
    x = np.asarray(x, np.float32)
    fond = analyser_fond(x, sr)
    n, h = 4096, 1024
    a = {"volume_db": round(_db(x), 1), "bpm": fond.get("bpm"), "bandes": fond["bandes"]}
    if len(x) < n + h:
        return {**a, "notes": [], "tonalite": None, "attaques_s": 0.0}
    t = np.lib.stride_tricks.sliding_window_view(x, n)[::h] * np.hanning(n).astype(np.float32)
    S = np.abs(np.fft.rfft(t, axis=1))
    f = np.fft.rfftfreq(n, 1 / sr)
    lo, hi = REGISTRES.get(nom, (60, 2000))
    m = (f >= lo) & (f <= hi)
    classes = np.round(69 + 12 * np.log2(f[m] / 440)).astype(int) % 12
    chroma = np.bincount(classes, weights=(S[:, m] ** 2).sum(axis=0), minlength=12)
    notes = []
    if nom != "drums" and chroma.sum() > 0:
        ordre = np.argsort(chroma)[::-1]
        notes = [NOTES[i] for i in ordre[:3] if chroma[i] >= 0.3 * chroma[ordre[0]]]
    return {**a, "notes": notes, "tonalite": tonalite(chroma) if nom != "drums" else None,
            "attaques_s": round(_attaques(S, h / sr), 1)}


def notes_du_temps(nom, x, sr, pas=1.0):
    """(06/11, Ahmed : « il sait que c'est telle note, ou telle note et tel piano ou telle guitare ») les notes d'un instrument séparé,
    seconde par seconde, avec leur octave : [[t0 (s), ["La2"]], …] ; la basse : sa note la plus forte ; le piano, la guitare, le reste :
    leurs deux plus fortes (un pic de spectre à moins de 25 % du premier est laissé) ; la batterie n'a pas de note. Une seconde trop
    faible (20 dB sous l'instrument) : rien."""
    if nom == "drums":
        return []
    x = np.asarray(x, np.float32)
    n = max(1, int(pas * sr))
    lo, hi = REGISTRES.get(nom, (60, 2000))
    tout = _db(x)
    out = []
    for i in range(0, len(x) - n // 2, n):
        seg = x[i:i + n]
        if _db(seg) < max(-60.0, tout - 20):
            continue
        N = 8192
        S = np.abs(np.fft.rfft(np.pad(seg[:N], (0, max(0, N - len(seg[:N])))) * np.hanning(N)))
        f = np.fft.rfftfreq(N, 1 / sr)
        m = (f >= lo) & (f <= hi)
        if not m.any():
            continue
        Sm, fm = S[m], f[m]
        pics = [k for k in range(1, len(Sm) - 1) if Sm[k] >= Sm[k - 1] and Sm[k] >= Sm[k + 1]]
        pics.sort(key=lambda k: -Sm[k])
        noms = []
        for k in pics[: 8]:
            if Sm[k] < 0.25 * Sm[pics[0]]:
                break
            midi = int(round(69 + 12 * np.log2(fm[k] / 440)))
            nn = f"{NOTES[midi % 12]}{midi // 12 - 1}"
            if nn not in noms:
                noms.append(nn)
            if len(noms) >= (1 if nom == "bass" else 2):
                break
        if noms:
            out.append([round(i / sr, 2), noms])
    return out


def instrument_en_mots(nom, a):
    lien = dict(ORDRE).get(nom, nom)
    morceaux = []
    if a.get("notes"):
        morceaux.append(", ".join(a["notes"]) + (f" ({a['tonalite']})" if a.get("tonalite") else ""))
    if a.get("bpm"):
        morceaux.append(f"~{a['bpm']} BPM")
    if a.get("attaques_s"):
        r = a["attaques_s"]
        morceaux.append("des notes posées" if r < 1.5 else "un rythme régulier" if r < 4 else "des attaques rapides")
    b = a.get("bandes") or {}
    if b:
        morceaux.append(f"graves {b['graves']}, médiums {b['mediums']}, aigus {b['aigus']}")
    return f"{lien} : " + " ; ".join(morceaux) if morceaux else lien


def instruments_presents(pistes, fond_db):
    """Les instruments qui s'entendent (à moins de 20 dB du fond, au-dessus de −60 dBFS), dans l'ordre : la basse d'abord."""
    out = []
    for cle, _ in ORDRE:
        if cle in pistes and _db(pistes[cle]) > max(-60.0, fond_db - 20):
            out.append(cle)
    return out


# ---- qui parle : un nom sur une voix, en LECTURE seule ----

def references(fichier_ahmed=None, fichier_connues=None, fichier_moi=None):
    """(04/11, l'idée d'Ahmed : « tu peux utiliser les voix des lives qu'on a faits pour discerner ») les timbres qu'il connaît : papa
    (empreinte-vocale.json), les voix nommées (voix-connues.json, dont celles de ses lives), et la sienne (empreinte-moi.json, l'écho
    de sa voix). Lues, jamais écrites ; la salle (voix-salle.json) reste au serveur de voix."""
    import empreinte_vocale as ev
    refs = []
    d = ev._lire(fichier_ahmed)
    if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2:
        refs.append({"nom": ev.NOM_PAPA, "genre": "papa", "d": d})
    if fichier_connues is not None:
        for x in ev.connues(fichier_connues):
            refs.append({"nom": x["nom"], "genre": "connue", "v": np.array(x["moyenne"], float)})
    else:
        # (10/11) chaque voix d'une signature (sauf la voix 1, l'empreinte de papa, déjà là) : le nom de sa personne, ou le doute d'une voix
        # partagée (« papa ou Ali ? ») ; lu, jamais écrit
        try:
            reg = ev.registre_voix()
        except (OSError, ValueError):
            reg = None
        for k, x in sorted((reg or {}).get("voix", {}).items(), key=lambda kx: int(kx[0])):
            o = [n for n, _ in ev.S.proprietaires(reg, k)]
            if o and x.get("c") is not None:
                refs.append({"nom": ev.S.etiquette(o), "genre": "connue", "v": np.array(x["c"], float)})
    for m in ev.moyennes_moi(fichier_moi).values():                 # (06/11) chacune de ses voix : rap, Azure, celle d'avant
        refs.append({"nom": "moi", "genre": "moi", "v": np.asarray(m, float)})
    return refs


def nommer(v, refs):
    """Le nom d'un timbre parmi les références (les seuils de empreinte_vocale : 0,55 pour une personne, 0,5 pour sa propre voix) ;
    sans ressemblance assez forte : None. Mesuré le 04/11 : les 8 voix du Mac contre papa, les 16 voix connues et sa voix, 0,35 au
    plus, aucune prise à tort."""
    if v is None or not refs:
        return {"nom": None, "score": None}
    import empreinte_vocale as ev
    v = np.asarray(v, float)
    v = v / (np.linalg.norm(v) or 1.0)
    notes = []
    for r in refs:
        s = ev.score_ahmed(v, r["d"]) if r["genre"] == "papa" else float(v @ r["v"])
        notes.append((s, r))
    s, r = max(notes, key=lambda p: p[0])
    seuil = ev.SEUIL_MOI if r["genre"] == "moi" else ev.SEUIL_AHMED
    if s < seuil:
        return {"nom": None, "score": round(s, 2)}
    # (06/11) sa propre voix seulement 0,05 au-dessus de toute autre (comme etiqueter) : papa n'est jamais pris pour son écho
    if r["genre"] == "moi" and any(x >= s - 0.05 for x, y in notes if y["genre"] != "moi"):
        autre = max(((x, y) for x, y in notes if y["genre"] != "moi"), key=lambda p: p[0])
        return {"nom": autre[1]["nom"], "score": round(autre[0], 2)} if autre[0] >= ev.SEUIL_AHMED else {"nom": None, "score": round(s, 2)}
    return {"nom": r["nom"], "score": round(s, 2)}


def voix_en_mots(voix):
    """« 3 voix : papa, voix 2, Karim » (la plus forte d'abord ; sa propre voix, l'écho, n'est pas comptée)."""
    vs = [v for v in voix if not v.get("moi")]
    if not vs:
        return ""
    noms = []
    for v in vs:
        n = v.get("nom") or f"voix {v['numero']}"
        noms.append(n)
    return f"{len(vs)} voix : " + ", ".join(noms)


