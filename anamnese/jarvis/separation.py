"""(04/11, Ahmed : « il faut aussi que tu sépares bien la voix et la musique de fond, et que les deux, en parallèle, soient transmises
au subconscient, pour qu'il les entende et qu'il puisse les relier à ses sensations et aux mots ; à la fin du processus parallèle,
séparé du son et de la voix, le tout est relié, un peu comme le cortex préfrontal » ; « oui, installe Demucs ») ses deux oreilles :
Demucs (Meta, htdemucs, licence MIT) sépare ce qu'il entend en une VOIX et un FOND, sur le GPU du Mac (0,5 s pour 3 à 8 s de son,
mesuré le 04/11 : la voix d'un mélange passe de −10 dB à +14 dB de SDR, le fond à +24 dB).
Puis, chacun de son côté :
- la voix : présente ou non, chantée (des notes tenues) ou parlée, sa tonalité approximative, son contour (monte, descend) ;
- le fond : son tempo (≥ 3 s de son), sa tonalité par ses accords, ses graves, médiums et aigus.
Rien de l'audio n'est gardé (la voix séparée peut être écrite un instant pour l'oreille, puis effacée par le cockpit).

Un processus qui reste en vie (son propre venv, jarvis/.venv-separation : torch + demucs) : une ligne JSON par demande
{id, fichier, voix_wav?} → {id, voix: {...}, fond: {...}, texte, ms} ou {id, erreur}.
(04/11, la séparation en cascade, jarvis/cascade.py) avec « cascade » : true (et « voix_dossier », un dossier absolu où écrire le
court fichier de chaque voix), la même réponse, et en plus : aiguillage {voix, musique, bruit, mesures}, voix_separees [{numero,
timbre, nom, moi, score, volume_db, segments, part, chante, tonalite, contour, mots, wav?}], instruments [{instrument, notes,
tonalite, bpm, attaques_s, bandes, volume_db, texte}], cascade_ms, texte_cascade. {id, chauffer: true} → {id, chaud, ms} : tout
chargé d'avance (htdemucs_6s, l'empreinte, les cœurs). Sans « cascade », rien ne change.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

KRUMHANSL_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KRUMHANSL_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
NOTES = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]


def _tonalite(chroma):
    c = np.asarray(chroma, dtype=float)
    if c.sum() <= 0:
        return None
    meilleur = None
    for r in range(12):
        for profil, mode in ((KRUMHANSL_MAJ, "majeur"), (KRUMHANSL_MIN, "mineur")):
            q = np.roll(profil, r)
            v = np.corrcoef(c, q)[0, 1]
            if meilleur is None or v > meilleur[0]:
                meilleur = (v, r, mode)
    return f"{NOTES[meilleur[1]]} {meilleur[2]}" if meilleur and meilleur[0] > 0.5 else None


def _f0(x, sr, trame=0.04):
    """La hauteur par trame (autocorrélation, 70 à 1 000 Hz) ; 0 sans hauteur nette."""
    n = int(trame * sr)
    out = []
    for i in range(0, len(x) - n, n):
        s = x[i:i + n] - x[i:i + n].mean()
        e = float(np.dot(s, s))
        if e < 1e-6 * n:
            out.append(0.0)
            continue
        ac = np.correlate(s, s, "full")[n - 1:]
        lo, hi = int(sr / 1000), min(len(ac) - 1, int(sr / 70))
        k = lo + int(np.argmax(ac[lo:hi]))
        out.append(sr / k if ac[k] / ac[0] > 0.5 else 0.0)
    return np.array(out), trame


def analyser_voix(voix, sr):
    voix = np.asarray(voix, dtype=np.float32)
    f0, trame = _f0(voix, sr)
    vo = f0[f0 > 0]
    if len(vo) < 10:
        return {"presente": False, "chante": False, "tonalite": None, "contour": None, "part": 0.0}
    midi = np.round(69 + 12 * np.log2(vo / 440)).astype(int)
    chroma = np.bincount(midi % 12, minlength=12)
    # chantée : des notes tenues (la même note sur au moins 0,4 s, deux fois)
    tenues, cur, long_ = 0, None, 0
    for m in np.round(69 + 12 * np.log2(np.where(f0 > 0, f0, 1) / 440)).astype(int) * (f0 > 0):
        if m and m == cur:
            long_ += 1
        else:
            if cur and long_ * trame >= 0.4:
                tenues += 1
            cur, long_ = m, 1
    if cur and long_ * trame >= 0.4:
        tenues += 1
    st = 12 * np.log2(vo / 440)
    tiers = max(1, len(st) // 3)
    d = float(np.median(st[-tiers:]) - np.median(st[:tiers]))
    contour = "monte" if d > 1 else "descend" if d < -1 else "reste stable"
    return {"presente": True, "chante": tenues >= 2, "tonalite": _tonalite(chroma), "contour": contour,
            "part": round(len(vo) / max(1, len(f0)), 2)}


def _spectre(x, sr, n=2048, pas=512):
    x = np.asarray(x, dtype=np.float32)
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    fen = np.hanning(n).astype(np.float32)
    trames = np.lib.stride_tricks.sliding_window_view(x, n)[::pas] * fen
    return np.abs(np.fft.rfft(trames, axis=1)), np.fft.rfftfreq(n, 1 / sr), pas / sr


def analyser_fond(fond, sr):
    S, f, dt = _spectre(fond, sr)
    e = S ** 2
    bandes = [e[:, (f >= a) & (f < b)].sum() for a, b in ((20, 250), (250, 4000), (4000, sr / 2))]
    tot = sum(bandes) or 1.0
    force = lambda v: "forts" if v / tot > 0.45 else "présents" if v / tot > 0.2 else "doux"   # noqa: E731
    # sa tonalité : les hauteurs de 60 à 2 000 Hz rangées en douze classes
    m = (f >= 60) & (f <= 2000)
    classes = (np.round(69 + 12 * np.log2(f[m] / 440)).astype(int)) % 12
    chroma = np.bincount(classes, weights=e[:, m].sum(axis=0), minlength=12)
    # son tempo : les attaques (le flux spectral), leur période (60 à 180 BPM), seulement avec 6 s de son
    bpm = None
    if len(fond) >= 3 * sr:
        flux = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(axis=1)
        c = flux - flux.mean()
        ac = np.correlate(c, c, "full")[len(c) - 1:]
        lo, hi = int(round(60 / 180 / dt)), int(round(60 / 60 / dt))
        if ac[0] > 0 and hi < len(ac):
            k = lo + int(np.argmax(ac[lo:hi]))
            if ac[k] / ac[0] > 0.1:
                a, b, d = ac[k - 1], ac[k], ac[k + 1]
                den = a - 2 * b + d
                fin = k + (0.5 * (a - d) / den if den < 0 else 0)
                bpm = int(round(60 / (fin * dt) / 2) * 2)
    return {"bpm": bpm, "tonalite": _tonalite(chroma),
            "bandes": {"graves": force(bandes[0]), "mediums": force(bandes[1]), "aigus": force(bandes[2])}}


def en_mots(voix, fond):
    v = ("la voix (séparée) " + ("chante" if voix["chante"] else "parle")
         + (f", {voix['tonalite']}" if voix.get("tonalite") else "") + (f", la mélodie {voix['contour']}" if voix.get("contour") else "")
         if voix["presente"] else "pas de voix")
    b = fond["bandes"]
    f = ("le fond (séparé)" + (f" ~{fond['bpm']} BPM" if fond.get("bpm") else "") + (f", {fond['tonalite']}" if fond.get("tonalite") else "")
         + f", graves {b['graves']}, médiums {b['mediums']}, aigus {b['aigus']}")
    return f"{v} · {f}"


# ---- (06/11, Ahmed : « que toutes ses mesures et découpes soient processées par le subconscient, et que le signal arrive net : parole,
# musique ou background, la piste de musique ou de background calée sur les mots ») les trois pistes : le fond séparé, seconde par
# seconde, dit s'il est de la musique (et son accord) ou un bruit (et sa nature : chocs, sourd, souffle, pièce), avec son intensité ;
# les instants sont ceux du fichier (le cockpit les cale sur l'horloge des mots).

def _gabarits():
    g = []
    for r in range(12):
        for nom, tierce in (("", 4), ("m", 3)):
            v = np.zeros(12)
            v[[r, (r + tierce) % 12, (r + 7) % 12]] = 1.0
            g.append((f"{NOTES[r]}{nom}", v / np.linalg.norm(v)))
    return g


GABARITS = _gabarits()
SEUIL_ACCORD = 0.75                                                  # un chroma plat donne 0,5 ; une triade nette, plus de 0,8


def accord(chroma):
    """L'accord majeur ou mineur le plus proche d'un chroma (cosinus) : (nom, score) ; (None, 0) sans énergie."""
    c = np.asarray(chroma, dtype=float)
    n = float(np.linalg.norm(c))
    if n <= 0:
        return None, 0.0
    c = c / n
    s, nom = max((float(c @ v), k) for k, v in GABARITS)
    return nom, round(s, 2)


def _chroma(x, sr, n=4096):
    S, f, _ = _spectre(x, sr, n=n, pas=n // 2)
    m = (f >= 80) & (f <= 2000)
    classes = (np.round(69 + 12 * np.log2(f[m] / 440)).astype(int)) % 12
    return np.bincount(classes, weights=np.sqrt((S[:, m] ** 2).sum(axis=0)), minlength=12)


def _db_de(x):
    x = np.asarray(x, np.float64)
    return float(10 * np.log10((x ** 2).mean() + 1e-12)) if len(x) else -120.0


def _chocs(x, sr):
    """Les coups brefs : une trame de 10 ms bien au-dessus du niveau médian (×6 en énergie) et audible."""
    n = max(1, int(0.01 * sr))
    e = np.asarray(x[: len(x) // n * n], np.float64).reshape(-1, n)
    e = (e ** 2).mean(axis=1)
    if len(e) < 3:
        return 0
    med = float(np.median(e)) + 1e-12
    pic = (e[1:-1] > 6 * med) & (e[1:-1] > 1e-4) & (e[1:-1] >= e[:-2]) & (e[1:-1] >= e[2:])
    return int(pic.sum())


def _nature(x, sr, chocs):
    if chocs:
        return "chocs"
    S, f, _ = _spectre(x, sr)
    e = (S ** 2).sum(axis=0)
    b = [e[(f >= a) & (f < z)].sum() for a, z in ((20, 250), (250, 4000), (4000, sr / 2))]
    tot = sum(b) or 1.0
    return "sourd" if b[0] / tot > 0.6 else "souffle" if b[2] / tot > 0.4 else "pièce"


def pistes_du_fond(melange, voix, fond, sr, musique=False, pas=1.0):
    """Seconde par seconde : {t0, t1, db (le mélange), voix_db, fond_db, quoi (musique | bruit | silence), accord, score, chocs,
    nature}. musique : la première écoute (aiguiller) a trouvé un rythme ou des notes tenues dans tout le fond ; une seconde sans
    accord net reste alors de la musique (une batterie seule)."""
    melange, voix, fond = (np.asarray(a, np.float32) for a in (melange, voix, fond))
    n = max(1, int(pas * sr))
    md = _db_de(melange)
    out = []
    for i in range(0, len(fond), n):
        seg = fond[i:i + n]
        if len(seg) < n // 2:
            break
        fd, vd, d = _db_de(seg), _db_de(voix[i:i + n]), _db_de(melange[i:i + n])
        w = {"t0": round(i / sr, 2), "t1": round((i + len(seg)) / sr, 2), "db": round(d, 1), "voix_db": round(vd, 1), "fond_db": round(fd, 1)}
        if fd < max(-60.0, md - 30):
            out.append({**w, "quoi": "silence"})
            continue
        nom, score = accord(_chroma(seg, sr))
        tonal = score >= SEUIL_ACCORD
        chocs = _chocs(seg, sr)
        if tonal or musique:
            out.append({**w, "quoi": "musique", "accord": nom if tonal else None, "score": score, "chocs": chocs})
        else:
            out.append({**w, "quoi": "bruit", "chocs": chocs, "nature": _nature(seg, sr, chocs)})
    return out


def separer(modele, x, appareil, apply_model):
    """(04/11, vu : le téléphone envoie 8 s de sa musique et htdemucs n'en prend que 7,8 d'un seul tenant : « Given length 380607 is
    longer than training length 343980 », à chaque morceau, et rien de séparé du téléphone) découpé par Demucs en segments qui se
    chevauchent : un son court tient dans un seul, un plus long n'est plus refusé."""
    return apply_model(modele, x, device=appareil, split=True, overlap=0.25, progress=False)[0]


def _pistes(modele, x, appareil, apply_model, torch):
    """Demucs sur un son mono : {nom de piste : son mono}."""
    with torch.no_grad():
        s = separer(modele, torch.tensor(np.stack([x, x]))[None], appareil, apply_model)
    return {n: s[i].mean(0).cpu().numpy() for i, n in enumerate(modele.sources)}


def traiter(d, outils):
    """Une demande {id, fichier, voix_wav?, cascade?, voix_dossier?} → la réponse (sans l'id). outils : lire(fichier) → (son, taux),
    pistes(son) → {vocals, drums, bass, other}, taux (celui du modèle), ecrire(fichier, son, taux) ; pour la cascade, en plus :
    pistes6(son), vers16(son), empreintes(audios), references(), coeurs (un ThreadPoolExecutor, ou None)."""
    t0 = time.time()
    x, sr = outils.lire(str(d["fichier"]))
    if sr != outils.taux:                                            # ré-échantillonné (linéaire : assez pour séparer)
        n = int(len(x) * outils.taux / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        sr = outils.taux
    p = outils.pistes(x)
    voix = p["vocals"]
    fond = sum(v for k, v in p.items() if k != "vocals")
    av, af = analyser_voix(voix[::2], sr // 2), analyser_fond(fond, sr)
    sortie = {"voix": av, "fond": af, "texte": en_mots(av, af)}
    if d.get("voix_wav") and av["presente"]:                         # la voix seule, un instant, pour l'oreille (les mots)
        outils.ecrire(str(d["voix_wav"]), voix, sr)
        sortie["voix_wav"] = str(d["voix_wav"])
    if d.get("pistes"):                                              # (06/11) les trois pistes : le fond, seconde par seconde
        import cascade as C
        route = C.aiguiller(x, voix, fond, sr, p)
        sortie["pistes"] = {"fenetres": pistes_du_fond(x, voix, fond, sr, musique=route["musique"]), "musique": route["musique"],
                            "bpm": af.get("bpm"), "tonalite": af.get("tonalite"), "voix": av["presente"], "duree_s": round(len(x) / sr, 2)}
        # (06/11, mesuré : la voix séparée est prête en 0,5 à 2,8 s, la cascade en rajoute 4) avant la cascade, une réponse partielle : ses
        # pistes et sa voix séparée partent tout de suite (la grande oreille n'attend pas les instruments) ; la réponse finale ne les répète pas
        tot = getattr(outils, "tot", None)
        if d.get("cascade") and tot is not None:
            tot({"partiel": True, "pistes": sortie.pop("pistes"), **({"voix_wav": sortie.pop("voix_wav")} if "voix_wav" in sortie else {}),
                 "ms": int((time.time() - t0) * 1000)})
    if d.get("cascade"):
        sortie.update(en_cascade(d, x, p, voix, fond, sr, outils, t0))
    sortie["ms"] = int((time.time() - t0) * 1000)
    return sortie


def en_cascade(d, x, p, voix, fond, sr, outils, t0):
    """(04/11, Ahmed : « 2 process : un pour background = voix + bruit, un pour la musique ; les 2 sont activés par la détection de la
    première bande-son » ; « jusqu'à 8 voix » ; « un instrument par cœur CPU, en premier les basses ») la séparation en cascade
    (jarvis/cascade.py), demandée par « cascade » : true. La route des voix part sur un cœur pendant que Demucs htdemucs_6s sépare
    les instruments sur le GPU ; chaque voix sortie, puis chaque instrument, est analysé sur son cœur. Sans voix ni musique (un
    bruit), aucun cœur ne travaille. Les fichiers des voix ne sont écrits que si « voix_dossier » est donné (le cockpit les efface)."""
    import cascade as C
    route = C.aiguiller(x, voix, fond, sr, p)
    coeurs = outils.coeurs
    lancer = (lambda f, *a: coeurs.submit(f, *a)) if coeurs is not None else (lambda f, *a: _Fait(f(*a)))
    dossier = d.get("voix_dossier")
    dossier = str(dossier) if dossier and os.path.isabs(str(dossier)) and os.path.isdir(str(dossier)) else None
    refs = outils.references() if route["voix"] else []
    temps = {"premiere_ecoute": int((time.time() - t0) * 1000)}

    def une_voix(k, v, x16):
        clip = C.compacter(x16, v["masque"])
        a = analyser_voix(clip, C.TAUX)
        qui = C.nommer(v["c"], refs)
        o = {"numero": k + 1, "nom": None if qui["nom"] == "moi" else qui["nom"], "moi": qui["nom"] == "moi",
             "score": qui["score"], "volume_db": round(v["rms_db"], 1), "segments": C.segments(v["masque"]),
             "part": round(float(v["masque"].mean()), 2), "chante": a["chante"], "tonalite": a["tonalite"],
             "contour": a["contour"], "mots": None}
        o["timbre"] = o["nom"] or ("sa voix" if o["moi"] else f"voix {k + 1}")
        if dossier:
            f = os.path.join(dossier, f"jarvis-sep-{os.getpid()}-{d.get('id')}-v{k + 1}.wav")
            outils.ecrire(f, clip, C.TAUX)
            o["wav"] = f
        return o

    def route_des_voix():
        t = time.time()
        try:
            x16 = outils.vers16(voix)
            vs = C.cascade(x16, outils.empreintes)
            sorties = [lancer(une_voix, k, v, x16) for k, v in enumerate(vs)]   # chaque voix sur son cœur ; le reste a descendu
            return [s.result() for s in sorties], int((time.time() - t) * 1000), None
        except Exception as e:  # noqa: BLE001  (sans empreinte, la réponse d'avant et la musique restent)
            return [], int((time.time() - t) * 1000), str(e)[:200]

    voies = lancer(route_des_voix) if route["voix"] else None
    instruments, erreur_musique = [], None
    if route["musique"]:
        t = time.time()
        try:
            p6 = outils.pistes6(fond)
            presents = C.instruments_presents(p6, route["mesures"]["fond_db"])
            analyses = [(k, lancer(C.analyser_instrument, k, p6[k], sr, _tonalite, analyser_fond)) for k in presents]
            temps_notes = {k: lancer(C.notes_du_temps, k, p6[k], sr) for k in presents} if d.get("pistes") else {}
            for k, a in analyses:
                a = a.result()
                instruments.append({"instrument": k, **a, "texte": C.instrument_en_mots(k, a),
                                    **({"notes_du_temps": temps_notes[k].result()} if k in temps_notes else {})})
        except Exception as e:  # noqa: BLE001
            erreur_musique = str(e)[:200]
        temps["musique"] = int((time.time() - t) * 1000)
    separees, erreurs = [], ({"musique": erreur_musique} if erreur_musique else {})
    if voies is not None:
        separees, temps["voix"], erreur_voix = voies.result()
        if erreur_voix:
            erreurs["voix"] = erreur_voix
    morceaux = [m for m in [C.voix_en_mots(separees)] + [i["texte"] for i in instruments] if m]
    return {"aiguillage": route, "voix_separees": separees, "instruments": instruments, "cascade_ms": temps,
            "texte_cascade": " · ".join(morceaux), **({"cascade_erreurs": erreurs} if erreurs else {})}


class _Fait:
    """Un résultat déjà là (sans cœurs : tout de suite, dans l'ordre)."""
    def __init__(self, r):
        self._r = r

    def result(self):
        return self._r


def charger_empreintes():
    """(04/11) l'empreinte WeSpeaker de empreinte_vocale, par lots de 16 fenêtres de 1,5 s, sur le GPU et le moteur neuronal du Mac
    (CoreML : 5 ms par fenêtre mesurées, contre 106 ms sur un cœur ; la même empreinte, cosinus 1,0). onnxruntime est celui du venv
    de jarvis (même Python 3.12, même numpy) : aucune installation de plus dans ce venv."""
    try:
        import onnxruntime as ort
    except ImportError:
        v = f"python{sys.version_info.major}.{sys.version_info.minor}"
        sys.path.append(str(Path(__file__).resolve().parent / ".venv" / "lib" / v / "site-packages"))
        import onnxruntime as ort
    import empreinte_vocale as ev
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads, so.log_severity_level = 1, 1, 3
    fournisseurs = [("CoreMLExecutionProvider", {"MLComputeUnits": "ALL", "ModelFormat": "MLProgram"}), "CPUExecutionProvider"]
    session = ort.InferenceSession(str(ev.MODELE), so, providers=[f for f in fournisseurs
                                                                   if (f[0] if isinstance(f, tuple) else f) in ort.get_available_providers()])
    entree = session.get_inputs()[0].name
    lot = 16                                                         # une forme fixe : CoreML ne se recompile pas

    def empreintes(audios):
        f = np.stack([ev.fbank(a) for a in audios]).astype(np.float32)
        n = len(f)
        f = np.concatenate([f, np.zeros(((-n) % lot,) + f.shape[1:], np.float32)])
        v = np.concatenate([session.run(None, {entree: f[i:i + lot]})[0] for i in range(0, len(f), lot)])[:n].astype(np.float64)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    return empreintes


def main():
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    appareil = "mps" if torch.backends.mps.is_available() else "cpu"
    modele = get_model("htdemucs").to(appareil).eval()
    print(json.dumps({"pret": True, "appareil": appareil}), flush=True)
    paresseux = {}

    def pistes6(son):
        if "6s" not in paresseux:                                    # chargé à la première musique seulement
            paresseux["6s"] = get_model("htdemucs_6s").to(appareil).eval()
        return _pistes(paresseux["6s"], son, appareil, apply_model, torch)

    def empreintes(audios):
        if "empreintes" not in paresseux:
            paresseux["empreintes"] = charger_empreintes()
        return paresseux["empreintes"](audios)

    def vers16(son):
        import julius
        return julius.resample_frac(torch.tensor(np.ascontiguousarray(son)), modele.samplerate, 16000).numpy().astype(np.float32)

    def coeurs():
        if "coeurs" not in paresseux:                                # au plus 8 cœurs, endormis sans travail
            from concurrent.futures import ThreadPoolExecutor
            paresseux["coeurs"] = ThreadPoolExecutor(max_workers=max(2, min(8, os.cpu_count() or 4)),
                                                     thread_name_prefix="coeur")
        return paresseux["coeurs"]

    def references():
        import cascade as C
        return C.references()

    class Outils:
        taux = modele.samplerate
        lire = staticmethod(lambda f: (lambda xs: (xs[0].mean(axis=1), xs[1]))(sf.read(f, dtype="float32", always_2d=True)))
        pistes = staticmethod(lambda son: _pistes(modele, son, appareil, apply_model, torch))
        ecrire = staticmethod(lambda f, son, taux: sf.write(f, son, taux))

    outils = Outils()
    outils.pistes6, outils.empreintes, outils.vers16, outils.references = pistes6, empreintes, vers16, references
    for ligne in sys.stdin:
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        try:
            if d.get("chauffer"):
                # (04/11, mesuré : la première demande en cascade prenait 17 s, le temps de charger htdemucs_6s et de compiler
                # l'empreinte ; le cockpit lâche une demande après 15 s) tout chargé d'avance, sur demande, sans rien séparer
                t0 = time.time()
                coeurs()
                empreintes([np.zeros(24000, np.float32)])
                pistes6(np.zeros(modele.samplerate, np.float32))
                print(json.dumps({"id": d.get("id"), "chaud": True, "ms": int((time.time() - t0) * 1000)}), flush=True)
                continue
            outils.coeurs = coeurs() if d.get("cascade") else None
            outils.tot = (lambda s, i=d.get("id"): print(json.dumps({"id": i, **s}, ensure_ascii=False, default=_json), flush=True)) if d.get("pistes") else None
            sortie = traiter(d, outils)
        except Exception as e:  # noqa: BLE001  (une demande ratée ne tue pas ses oreilles)
            sortie = {"erreur": str(e)[:200]}
        print(json.dumps({"id": d.get("id"), **sortie}, ensure_ascii=False, default=_json), flush=True)
        vider_caches(torch)


def vider_caches(torch, entree=sys.stdin):
    """(09/11, mesuré à 21:15 : 3,4 Go d'« IOAccelerator » sur 4,3 Go, et 3,8 → 4,5 Go en six minutes) les blocs que le GPU (MPS) de torch
    GARDE en cache après chaque séparation : rendus au Mac dès qu'aucune demande n'attend, après la réponse (elle ne l'attend pas).
    Les modèles chargés restent. MLX aussi s'il est chargé (l'empreinte)."""
    try:
        import select
        if select.select([entree], [], [], 0)[0]:
            return False
    except Exception:  # noqa: BLE001
        pass
    try:
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:  # noqa: BLE001
        pass
    mx = sys.modules.get("mlx.core")
    if mx is not None:
        try:
            mx.clear_cache()
        except Exception:  # noqa: BLE001
            pass
    return True


def _json(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


if __name__ == "__main__":
    main()
