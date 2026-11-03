"""L'empreinte vocale d'Ahmed (point 18 de la liste du 2026-10-19 ; accord d'Ahmed pour l'installation le 2026-10-20).
Hakim sait si c'est bien la voix d'Ahmed qui parle — un INDICE de contexte (un enfant, un invité du live, la télé),
JAMAIS une autorisation : aucune action ne dépend de ce score.

- Modèle : WeSpeaker ResNet34 (VoxCeleb), 26 Mo, en ONNX, local (~/AIOS/jarvis/modeles) ; aucune donnée ne sort.
- Entrée : 80 bandes de Mel « à la Kaldi » (25 ms / 10 ms, fenêtre de Hamming, pré-accentuation 0,97), moyenne
  retirée, comme à l'entraînement de WeSpeaker → un vecteur de 256 nombres.
- Apprentissage : seulement quand Ahmed le demande (réglages : « apprendre ma voix ») ; quelques phrases suffisent.
  L'empreinte (la moyenne des vecteurs, pas l'audio) est gardée dans ~/AIOS/jarvis/empreinte-vocale.json (0600).
"""
import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np

MODELE = Path(os.environ.get("JARVIS_EMPREINTE_MODELE", Path.home() / "AIOS" / "jarvis" / "modeles" / "voxceleb_resnet34_LM.onnx"))
FICHIER = Path.home() / "AIOS" / "jarvis" / "empreinte-vocale.json"
TAUX = 16000
PAROLE_MIN_S = 1.5
SEUIL_AHMED, SEUIL_DOUTE = 0.55, 0.35
_session = None
_bancs = None


def _mel_kaldi(n_fft=512, n_mels=80, bas=20.0, haut=8000.0):
    """Les filtres triangulaires de Kaldi (échelle de Mel 1127·ln(1 + f/700), interpolation dans l'échelle de Mel)."""
    mel = lambda f: 1127.0 * np.log(1.0 + f / 700.0)
    mbas, mhaut = mel(bas), mel(haut)
    pas = (mhaut - mbas) / (n_mels + 1)
    freqs = np.arange(n_fft // 2) * TAUX / n_fft                # Kaldi ignore la bande de Nyquist
    m = mel(freqs)
    bancs = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        g, c, d = mbas + i * pas, mbas + (i + 1) * pas, mbas + (i + 2) * pas
        montee = (m - g) / (c - g)
        descente = (d - m) / (d - c)
        bancs[i, :n_fft // 2] = np.maximum(0.0, np.minimum(montee, descente))
    return bancs


def fbank(audio):
    """audio : float32 16 kHz dans [-1, 1] → (trames, 80) log-Mel à la Kaldi, moyenne retirée."""
    global _bancs
    x = np.asarray(audio, dtype=np.float64) * 32768.0
    long, pas = 400, 160
    if len(x) < long:
        return np.zeros((0, 80), dtype=np.float32)
    n = 1 + (len(x) - long) // pas
    idx = np.arange(long)[None, :] + pas * np.arange(n)[:, None]
    trames = x[idx]
    trames = trames - trames.mean(axis=1, keepdims=True)                     # composante continue retirée
    trames = np.concatenate([trames[:, :1] * (1 - 0.97), trames[:, 1:] - 0.97 * trames[:, :-1]], axis=1)
    trames *= 0.54 - 0.46 * np.cos(2 * math.pi * np.arange(long) / (long - 1))   # Hamming
    spectre = np.abs(np.fft.rfft(trames, n=512, axis=1)) ** 2
    if _bancs is None:
        _bancs = _mel_kaldi()
    e = spectre @ _bancs.T
    f = np.log(np.maximum(e, np.finfo(np.float32).eps)).astype(np.float32)
    return f - f.mean(axis=0, keepdims=True)


def embedding(audio, min_s=PAROLE_MIN_S):
    global _session
    f = fbank(audio)
    if len(f) < int(min_s * 100):
        return None
    if _session is None:
        import onnxruntime as ort
        _session = ort.InferenceSession(str(MODELE), providers=["CPUExecutionProvider"])
    entree = _session.get_inputs()[0].name
    v = _session.run(None, {entree: f[None, :, :]})[0][0].astype(np.float64)
    return v / (np.linalg.norm(v) or 1.0)


def _lire(fichier=None):
    try:
        return json.loads(Path(fichier or FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


ECHANTILLONS_MAX = 60


def apprendre(audio, fichier=None, registre=None, guide=False):
    """Ajoute un échantillon de la voix d'Ahmed ; rend le nombre d'échantillons, ou None si trop court.
    registre (calibration, demande d'Ahmed relayée par Hakim le 2026-10-20 : reconnu à 0,04-0,47 quand il parlait plus
    aigu ou plus vite depuis son téléphone) : « aigu-telephone », « vite-mac »… ; guide=True (calibration guidée,
    c'est bien lui qui parle) : pas de rejet d'un registre éloigné de sa moyenne — c'est justement ce qu'on veut apprendre."""
    v = embedding(audio)
    if v is None:
        return None
    f = Path(fichier or FICHIER)
    d = _lire(f) or {"vecteurs": []}
    if not guide and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2 and score_ahmed(v, d) < 0.3:
        return None                                      # une autre voix (un invité, la télé) : pas apprise
    registres = d.get("registres") or [None] * len(d.get("vecteurs", []))
    registres = (registres + [None] * len(d.get("vecteurs", [])))[:len(d.get("vecteurs", []))]
    d["vecteurs"] = (d.get("vecteurs", []) + [v.round(5).tolist()])[-ECHANTILLONS_MAX:]
    d["registres"] = (registres + [str(registre)[:40] if registre else None])[-ECHANTILLONS_MAX:]
    m = np.mean(np.array(d["vecteurs"]), axis=0)
    d["moyenne"] = (m / (np.linalg.norm(m) or 1.0)).round(5).tolist()
    d["maj"] = time.time()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)
    return len(d["vecteurs"])


def score_ahmed(v, d):
    """La ressemblance avec la voix d'Ahmed : la meilleure entre sa voix MOYENNE et ses registres (la moyenne des deux
    échantillons les plus proches) — une phrase aiguë ou rapide ressemble à ses échantillons aigus ou rapides plus
    qu'à sa moyenne."""
    s = float(np.dot(v, np.array(d["moyenne"])))
    ech = np.array(d.get("vecteurs") or [])
    if len(ech) >= 2:
        proches = np.sort(ech @ v)[-2:]
        s = max(s, float(np.mean(proches)))
    return s


def reconnaitre(audio, fichier=None):
    """{"score": cosinus, "verdict": "ahmed" | "doute" | "autre"} ; None si pas d'empreinte ou audio trop court."""
    d = _lire(fichier)
    if not d or not d.get("moyenne") or len(d.get("vecteurs", [])) < 2:
        return None
    v = embedding(audio)
    if v is None:
        return None
    s = score_ahmed(v, d)
    return {"score": round(s, 2), "verdict": "ahmed" if s >= SEUIL_AHMED else "doute" if s >= SEUIL_DOUTE else "autre"}


# ---- Plusieurs voix dans un même message (Ahmed, 2026-10-20 : « je lui dis un truc et mon pote me coupe… qu'il
# distingue que c'est moi qui ai dit le 1er truc et un autre le 2e, et une 3e personne aussi ») ----
# Chaque segment de Whisper (≥ 1 s) reçoit son vecteur : proche de l'empreinte d'Ahmed → Ahmed ; sinon comparé aux
# autres voix déjà entendues dans la conversation (« voix 2 », « voix 3 »…) ; un segment trop court
# prend la voix du précédent. Convention du texte : ce qui n'est pas étiqueté est d'Ahmed ; une autre voix est
# annoncée (« [voix 2] … »), et le retour d'Ahmed aussi (« [Ahmed] … »). Une voix NOMMÉE (« voix 2, c'est Karim »)
# est gardée pour toujours ; une voix sans nom, 3 h.
SEUIL_MEME_VOIX = 0.5
SEGMENT_MIN_S = 1.0
# Ahmed, 2026-10-20 : « que les numéros tiennent pour toujours du moment qu'il y a un nom sur la voix, sinon 3 h »
SALLE_DUREE_S = 3 * 3600
SALLE = Path.home() / "AIOS" / "jarvis" / "voix-salle.json"          # les voix sans nom de la conversation (3 h)
CONNUES = Path.home() / "AIOS" / "jarvis" / "voix-connues.json"      # les voix nommées (pour toujours)
_salle = {"voix": [], "ts": 0.0, "dernier": None}


def _ecrire(f, d):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)


def _charger_salle(t, salle=None):
    if _salle["voix"] or _salle["ts"]:
        return
    try:
        d = json.loads(Path(salle or SALLE).read_text(encoding="utf-8"))
        if t - d.get("ts", 0) <= SALLE_DUREE_S:
            _salle.update(ts=d["ts"], dernier=d.get("dernier"),
                          voix=[{"nom": x["nom"], "c": np.array(x["c"]), "n": x["n"]} for x in d.get("voix", [])])
    except (OSError, ValueError, KeyError):
        pass


def _sauver_salle(salle=None):
    _ecrire(salle or SALLE, {"ts": _salle["ts"], "dernier": _salle["dernier"],
                             "voix": [{"nom": x["nom"], "c": np.round(x["c"], 5).tolist(), "n": x["n"]} for x in _salle["voix"]]})


def connues(fichier=None):
    try:
        return [x for x in json.loads(Path(fichier or CONNUES).read_text(encoding="utf-8")) if x.get("moyenne")]
    except (OSError, ValueError):
        return []


def _prenom(nom):
    """(29/10, relecture du système immunitaire) un prénom : des lettres, espaces, traits d'union et apostrophes, 40 au
    plus ; jamais « Ahmed » ni « voix N » : un nom avec des crochets forgerait une étiquette de la transcription."""
    nom = " ".join(str(nom or "").split())[:40]
    if not nom or not all(c.isalpha() or c in " -'’" for c in nom) or nom.casefold() == "ahmed" \
            or re.fullmatch(r"voix\s*\d*", nom, re.IGNORECASE):
        raise ValueError("un prénom (lettres, espaces, traits d'union), autre qu'Ahmed")
    return nom


def nommer(numero, nom, salle=None, fichier=None, maintenant=None):
    """« voix 2 » → « Karim » : la voix de la conversation devient une voix connue, pour toujours."""
    nom = _prenom(nom)
    # la salle est tenue par le serveur de voix (un AUTRE processus) : relue du fichier à chaque fois, sinon le serveur de
    # mémoire de Hakim nommait d'après la salle qu'il avait lue la première fois (relecture du 2026-10-20)
    _salle.update(voix=[], ts=0.0, dernier=None)
    _charger_salle(time.time() if maintenant is None else maintenant, salle)
    # (Ahmed, 2026-10-20 : « il n'arrive pas à enregistrer le nom de la voix ») Hakim passait « 10 » pour « voix 10 » :
    # le numéro seul, « Voix 10 », « voix n°10 », « v10 » désignent la même voix
    brut = " ".join(str(numero).strip().lower().split())
    m = re.fullmatch(r"(?:voix|v)?\s*(?:n[°o]\.?\s*)?(\d+)", brut)
    cherche = f"voix {m.group(1)}" if m else brut
    x = next((v for v in _salle["voix"] if v["nom"].lower() == cherche), None)
    if x is None:
        presentes = ", ".join(v["nom"] for v in _salle["voix"][-8:]) or "aucune"
        raise ValueError(f"aucune « {numero} » dans la conversation des 3 dernières heures (voix présentes : {presentes})")
    numero = x["nom"]
    k = [v for v in connues(fichier) if v["nom"].lower() != nom.lower()]
    k.append({"nom": nom, "moyenne": np.round(x["c"], 5).tolist(), "n": x["n"], "cree": time.time()})
    _ecrire(fichier or CONNUES, k)
    x["nom"] = nom                                       # la suite de la conversation l'appelle déjà par son nom
    if _salle["dernier"] == numero:
        _salle["dernier"] = nom
    _sauver_salle(salle)
    return nom


def renommer(ancien, nouveau, fichier=None):
    """« Machine à café » → « Inconnu » : une voix connue change de nom et garde son empreinte (29/10 : sans cet outil,
    Hakim a dû oublier la voix pour la renommer)."""
    nouveau = _prenom(nouveau)
    k = connues(fichier)
    x = next((v for v in k if v["nom"].lower() == str(ancien).strip().lower()), None)
    if x is None:
        raise ValueError(f"aucune voix « {ancien} » (voix connues : {', '.join(v['nom'] for v in k) or 'aucune'})")
    if any(v is not x and v["nom"].lower() == nouveau.lower() for v in k):
        raise ValueError(f"une voix « {nouveau} » existe déjà")
    x["nom"] = nouveau
    _ecrire(fichier or CONNUES, k)
    return nouveau


def oublier(nom, fichier=None):
    k = connues(fichier)
    reste = [v for v in k if v["nom"].lower() != str(nom).strip().lower()]
    _ecrire(fichier or CONNUES, reste)
    return len(k) - len(reste)


# ---- (03/11, Ahmed : « micro ouvert, jamais fermé ; il doit apprendre de lui-même à écouter et focaliser son attention ; si
# plusieurs voix se mélangent, il doit pouvoir séparer chaque voix selon son timbre ») ----
# - SA propre voix : apprise de ce qu'il dit (sa voix de synthèse, voix_serveur « dire »), sans rien demander à personne ;
#   ce qui sonne comme lui est mis de côté (« moi ») : c'est l'écho de sa voix, pas papa qui parle.
# - Mot à mot : quand Whisper date les mots, le segment est écouté par fenêtres de 1,5 s (pas de 0,75 s) ; chaque mot va à
#   la voix de la fenêtre la plus proche de son instant, même au milieu d'une phrase. Une fenêtre isolée qui ne ressemble à
#   personne (à cheval sur deux voix) ne crée pas de voix : il en faut deux de suite.
MOI = Path.home() / "AIOS" / "jarvis" / "empreinte-moi.json"
MOI_MAX, SEUIL_MOI = 40, 0.5
FENETRE_S, PAS_S = 1.5, 0.75


def apprendre_moi(audio, fichier=None):
    """Un échantillon de SA voix (ce qu'il vient de dire) ; rend le nombre d'échantillons, ou None si trop court."""
    v = embedding(audio)
    if v is None:
        return None
    f = Path(fichier or MOI)
    d = _lire(f) or {"vecteurs": []}
    d["vecteurs"] = (d.get("vecteurs", []) + [v.round(5).tolist()])[-MOI_MAX:]
    m = np.mean(np.array(d["vecteurs"]), axis=0)
    d["moyenne"] = (m / (np.linalg.norm(m) or 1.0)).round(5).tolist()
    d["maj"] = time.time()
    _ecrire(f, d)
    return len(d["vecteurs"])


def _moyenne_moi(fichier=None):
    d = _lire(fichier or MOI)
    return np.array(d["moyenne"]) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 3 else None


def etiqueter(audio, segments, nouveau_tour=True, fichier=None, maintenant=None, moi=None):
    """segments : [{start, end, text[, words]}] (gardés par stt). Rend (texte étiqueté, résumé) ; résumé = {"voix": [...],
    "plusieurs": bool, "ahmed": bool, "autres": [...], "moi": ce qu'il a entendu de SA voix ou ""}. Le texte rendu peut
    être vide (tout était sa voix). Sans voix reconnaissable : (None, None)."""
    t = time.time() if maintenant is None else maintenant
    _charger_salle(t)
    if t - _salle["ts"] > SALLE_DUREE_S:
        _salle["voix"] = []
    _salle["ts"] = t
    if nouveau_tour:
        _salle["dernier"] = None
    d = _lire(fichier)
    moyenne = np.array(d["moyenne"]) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2 else None
    ahmed = (lambda v: score_ahmed(v, d)) if moyenne is not None else None
    sa_voix = _moyenne_moi(moi)
    nommees = [(x["nom"], np.array(x["moyenne"])) for x in connues()]
    a = np.asarray(audio, dtype=np.float32)

    def connu(v):
        """La voix d'un vecteur parmi celles qu'il connaît (lui, Ahmed, les nommées, celles de la salle) ; None : inconnue."""
        sm = float(np.dot(v, sa_voix)) if sa_voix is not None else -1.0
        sa = ahmed(v) if ahmed else -1.0
        proches = [(float(np.dot(v, x["c"])), x) for x in _salle["voix"]]
        s, x = max(proches, key=lambda p: p[0]) if proches else (-1.0, None)
        sn = max((float(np.dot(v, c)) for _n, c in nommees), default=-1.0)
        if sm >= SEUIL_MOI and sm > max(sa, s, sn) + 0.05:
            return "moi", None
        if sa >= SEUIL_AHMED:
            return "Ahmed", None
        if nommees and sn >= SEUIL_AHMED:
            return max(nommees, key=lambda p: float(np.dot(v, p[1])))[0], None          # une voix connue, par son nom
        if sa >= SEUIL_DOUTE and sa > max(s, sn) + 0.1:
            # (2026-10-20) une phrase d'Ahmed dans un registre inhabituel : plus proche de lui que de toute autre voix
            # entendue — c'est lui, pas une « voix 3 »
            return "Ahmed", None
        if x is not None and s >= SEUIL_MEME_VOIX:
            return x["nom"], x
        return None, None

    def ajouter(v, x=None):
        if x is not None:
            x["c"] = (x["c"] * x["n"] + v) / (x["n"] + 1)
            x["c"] /= (np.linalg.norm(x["c"]) or 1.0)
            x["n"] += 1
            return x["nom"]
        nom = f"voix {len(_salle['voix']) + (2 if moyenne is not None else 1)}"
        _salle["voix"].append({"nom": nom, "c": v / (np.linalg.norm(v) or 1.0), "n": 1})
        return nom

    def qui_segment(brut):
        v = embedding(brut, SEGMENT_MIN_S) if len(brut) >= SEGMENT_MIN_S * TAUX else None
        if v is None:
            return _salle["dernier"] or ("Ahmed" if moyenne is not None else "voix 1")
        q, x = connu(v)
        return q if q in ("moi", "Ahmed") or (q and x is None) else ajouter(v, x)

    def unites_mot_a_mot(sg, mots):
        """[(qui, texte)] : chaque mot à la voix de la fenêtre la plus proche de son instant."""
        debut, fin = float(sg.get("start", 0)), float(sg.get("end", 0))
        centres, fen = [], []
        p = debut
        while p + FENETRE_S <= fin + 1e-6:
            v = embedding(a[int(p * TAUX):int((p + FENETRE_S) * TAUX)], SEGMENT_MIN_S)
            fen.append([v, *(connu(v) if v is not None else (None, None))])
            centres.append(p + FENETRE_S / 2)
            p += PAS_S
        for k, (v, q, x) in enumerate(fen):          # une inconnue : une voix neuve si sa voisine est inconnue aussi
            if v is None or q is not None:
                continue
            voisine = [fen[i] for i in (k - 1, k + 1) if 0 <= i < len(fen) and fen[i][0] is not None]
            if any(w[1] is None and float(np.dot(v, w[0])) >= SEUIL_MEME_VOIX for w in voisine) or len(fen) == 1:
                nom = ajouter(v)
                for w in fen[k:]:                    # ses voisines qui lui ressemblent : la même voix
                    if w[1] is None and w[0] is not None and float(np.dot(v, w[0])) >= SEUIL_MEME_VOIX:
                        w[1] = nom
            elif voisine:
                fen[k][1] = next((w[1] for w in voisine if w[1]), None)
        for v, q, x in fen:                           # les voix de la salle apprennent de chaque fenêtre
            if v is not None and x is not None:
                ajouter(v, x)
        sortie = []
        for w, ma, mb in mots:
            k = min(range(len(centres)), key=lambda i: abs(centres[i] - (ma + mb) / 2))
            q = fen[k][1] or _salle["dernier"] or ("Ahmed" if moyenne is not None else "voix 1")
            if sortie and sortie[-1][0] == q:
                sortie[-1][1].append(w)
            else:
                sortie.append((q, [w]))
        return [(q, " ".join(ws)) for q, ws in sortie]

    morceaux, vus, de_moi = [], [], []
    for sg in segments:
        texte = str(sg.get("text") or "").strip()
        if not texte:
            continue
        mots = [(str(w.get("word") or "").strip(), float(w.get("start", 0)), float(w.get("end", 0)))
                for w in (sg.get("words") or []) if str(w.get("word") or "").strip()]
        if mots and float(sg.get("end", 0)) - float(sg.get("start", 0)) >= 2 * FENETRE_S:
            unites = unites_mot_a_mot(sg, mots)
        else:
            brut = a[int(max(0.0, sg.get("start", 0)) * TAUX):int(max(0.0, sg.get("end", 0)) * TAUX)]
            unites = [(qui_segment(brut), texte)]
        for qui, bout in unites:
            if qui == "moi":                          # sa propre voix : mise de côté
                de_moi.append(bout)
                continue
            if qui not in vus:
                vus.append(qui)
            etiquette = qui != "Ahmed" and qui != _salle["dernier"] or (qui == "Ahmed" and _salle["dernier"] not in (None, "Ahmed"))
            morceaux.append(f"[{qui}] {bout}" if etiquette else bout)
            _salle["dernier"] = qui
    try:
        _sauver_salle()
    except OSError:
        pass
    autres = [q for q in vus if q != "Ahmed"]
    resume = {"voix": vus, "plusieurs": len(vus) >= 2, "ahmed": "Ahmed" in vus, "autres": autres, "moi": " ".join(de_moi)}
    if de_moi:
        return " ".join(morceaux), resume
    if not morceaux:
        return None, None
    if moyenne is None and len(vus) < 2:                    # sans empreinte, une seule voix : rien à dire
        return None, None
    return " ".join(morceaux), resume


def reinitialiser(portee="tout", fichier=None):
    """Réinitialiser (demande d'Ahmed, 2026-10-20) — portee : « tout » (toute l'empreinte), « calibration » (les
    échantillons de calibration, tous appareils), « calibration-mac » ou « calibration-telephone ». L'ancienne empreinte
    est d'abord SAUVEGARDÉE à côté (horodatée, 0600). Rend {"sauvegarde", "avant", "apres"}."""
    f = Path(fichier or FICHIER)
    d = _lire(f) or {"vecteurs": []}
    vec = d.get("vecteurs", [])
    regs = (d.get("registres") or [None] * len(vec))[:len(vec)]
    regs += [None] * (len(vec) - len(regs))
    if portee == "tout":
        garder = []
    elif portee in ("calibration", "calibration-mac", "calibration-telephone"):
        suffixe = None if portee == "calibration" else "-" + portee.split("-", 1)[1]
        garder = [i for i, r in enumerate(regs) if not (r and (suffixe is None or r.endswith(suffixe)))]
    else:
        raise ValueError("portée : tout, calibration, calibration-mac ou calibration-telephone")
    sauvegarde = f.with_name(f"{f.stem}.sauvegarde-{time.strftime('%Y%m%d-%H%M%S')}.json")
    if f.exists():
        sauvegarde.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        os.chmod(sauvegarde, 0o600)
    n = {"vecteurs": [vec[i] for i in garder], "registres": [regs[i] for i in garder], "maj": time.time()}
    if n["vecteurs"]:
        m = np.mean(np.array(n["vecteurs"]), axis=0)
        n["moyenne"] = (m / (np.linalg.norm(m) or 1.0)).round(5).tolist()
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(n), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)
    return {"sauvegarde": str(sauvegarde) if sauvegarde.exists() else None, "avant": len(vec), "apres": len(n["vecteurs"])}


def etat(fichier=None):
    d = _lire(fichier) or {}
    regs = {}
    for r in d.get("registres") or []:
        if r:
            regs[r] = regs.get(r, 0) + 1
    return {"echantillons": len(d.get("vecteurs", [])), "registres": regs, "modele": MODELE.exists()}
