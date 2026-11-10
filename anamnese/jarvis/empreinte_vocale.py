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

import signature_vocale as S

MODELE =Path(os.environ.get("JARVIS_EMPREINTE_MODELE", Path.home() / "AIOS" / "jarvis" / "modeles" / "voxceleb_resnet34_LM.onnx"))
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
    return apprendre_vecteur(v, fichier, registre, guide)


def apprendre_vecteur(v, fichier=None, registre=None, guide=False):
    """(03/11) la même chose, pour un vecteur déjà calculé (une voix de la salle rattachée à papa)."""
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
    out = {"score": round(s, 2), "verdict": "ahmed" if s >= SEUIL_AHMED else "doute" if s >= SEUIL_DOUTE else "autre"}
    return {**out, **verdict_signature(v, lambda x: score_ahmed(x, d))}


def verdict_signature(v, papa, reg=None):
    """(10/11) ce que les signatures changent au verdict d'un morceau entier (rien quand aucune voix d'une signature n'est à 0,55) :
    - une voix PARTAGÉE avec papa, ou une voix d'une autre personne à moins de 0,08 de la sienne : « doute » (jamais papa vérifié), avec
      "partagee" (les personnes, papa d'abord) et "voix_n" ;
    - une voix à papa seul : « ahmed » seulement avec une force sûre (FORCE_SURE), sinon « doute » ;
    - la voix d'une autre personne nettement devant : « autre », avec "qui"."""
    try:
        reg = reg or registre_voix()
    except (OSError, ValueError):
        return {}
    r = S.reconnaitre(v, reg, papa)
    if not r:
        return {}
    if r["papa"] and r["partagee"]:
        return {"verdict": "doute", "partagee": r["personnes"], "voix_n": r["voix"]}
    if r["papa"]:
        return {"verdict": "ahmed" if r["verifie"] else "doute", **({"voix_n": r["voix"]} if r["voix"] != S.VOIX_PAPA else {}),
                **({} if r["verifie"] else {"a_reconfirmer": True})}
    return {"verdict": "autre", "qui": r["personnes"], "voix_n": r["voix"]}


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
# (04/11, Ahmed : « que son attention s'étale sur plusieurs minutes ») mesuré de 13 h à 14 h 45 : 16 messages sur 216
# étiquetés « [voix N] », 15 numéros différents, dont au moins un de papa lui-même. Une voix inconnue n'est plus une personne
# au premier bout : c'est une CANDIDATE (son vecteur moyen, ses instants de parole [[t, secondes]…]). Elle devient « voix N »
# quand elle a parlé CONFIRMER_S dans les CANDIDATE_DUREE_S dernières secondes ; avant, ses mots vont à la voix d'avant (ou
# à papa). Une candidate qui n'a rien dit depuis CANDIDATE_DUREE_S est oubliée.
CONFIRMER_S = 4.0
CANDIDATE_DUREE_S = 300
_salle = {"voix": [], "ts": 0.0, "dernier": None, "candidates": []}


def _ecrire(f, d):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)


def _mtime(f):
    try:
        return os.stat(f).st_mtime_ns
    except OSError:
        return None


def _charger_salle(t, salle=None):
    # (09/11, Ahmed : « reconnaître les signatures vocales en temps réel pendant le live et pouvoir les enregistrer à la volée ») la salle
    # est tenue par PLUSIEURS processus (l'oreille des voix, le serveur de voix, l'outil voix_nommer) : relue dès que son fichier a
    # changé sous lui (avant : lue une fois, puis écrasée par la copie en mémoire d'un autre processus ; un nom donné se perdait)
    f = salle or SALLE
    m = _mtime(f)
    if (_salle["voix"] or _salle["ts"]) and (m is None or _salle.get("_fichier") != str(f) or _salle.get("_mtime") in (None, m)):
        return                                           # rien de neuf dans SON fichier : la mémoire tient (comme avant)
    _salle.update(voix=[], ts=0.0, candidates=[])        # (04/11) la salle se relit en entier du fichier, candidates comprises
    _salle["_fichier"], _salle["_mtime"] = str(f), _mtime(f)
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if t - d.get("ts", 0) <= SALLE_DUREE_S:
            _salle.update(ts=d["ts"], dernier=d.get("dernier"),
                          voix=[{"nom": x["nom"], "c": np.array(x["c"]), "n": x["n"], "m": x.get("m", 0)} for x in d.get("voix", [])],
                          # un fichier d'avant le 04/11 n'a pas de clé « candidates » : aucune candidate
                          # (09/11) une candidate peut porter son numéro temporaire (« nom »)
                          candidates=[{"c": np.array(x["c"]), "n": x.get("n", 1), "m": x.get("m", 0),
                                       "parole": [[float(u), float(s)] for u, s in x.get("parole", [])],
                                       **({"nom": str(x["nom"])} if x.get("nom") else {})}
                                      for x in d.get("candidates", [])])
    except (OSError, ValueError, KeyError, TypeError):
        pass


def _sauver_salle(salle=None):
    f = salle or SALLE
    _ecrire(f, {"ts": _salle["ts"], "dernier": _salle["dernier"],
                "voix": [{"nom": x["nom"], "c": np.round(x["c"], 5).tolist(), "n": x["n"], "m": x.get("m", 0)}
                         for x in _salle["voix"]],
                "candidates": [{"c": np.round(x["c"], 5).tolist(), "n": x["n"], "m": x.get("m", 0), "parole": x["parole"],
                                **({"nom": x["nom"]} if x.get("nom") else {})}
                               for x in _salle.get("candidates", [])]})
    _salle["_fichier"], _salle["_mtime"] = str(f), _mtime(f)


def _numeros_salle():
    return [int(m.group(1)) for x in _salle["voix"] + _salle.get("candidates", []) for m in [re.fullmatch(r"voix (\d+)", str(x.get("nom") or ""))] if m]


def _prochain_numero(moyenne_papa=True):
    """Le numéro qui suit le plus grand de la salle, candidates à numéro temporaire comprises (09/11) ; une voix rattachée à papa ne
    laisse pas son numéro à une autre. (10/11) ni une voix d'une signature, ni une voix proposée : leurs numéros sont pour toujours."""
    nums = _numeros_salle()
    try:
        base = S.numero_max(registre_voix())
    except (OSError, ValueError):
        base = S.VOIX_PAPA
    if base > S.VOIX_PAPA:
        return f"voix {max(nums + [base]) + 1}"
    return f"voix {max(nums) + 1 if nums else (2 if moyenne_papa else 1)}"


# ---- (10/11, ~23:00, Ahmed : « ma voix est reconnue sous 19 voix différentes, qui sont ma signature vocale… papa et tonton Ali partagent
# tous les deux la voix 127 ») la signature vocale de chaque personne (signature_vocale.py) : le registre vit à côté de voix-connues.json,
# migré au premier chargement (une sauvegarde avant ; l'empreinte de papa et la salle ne sont jamais réécrites par la migration).

def _sig(connues_f=None):
    c = Path(connues_f or CONNUES)
    return c.with_name("voix-signatures.json"), c


def registre_voix(connues_f=None):
    f, c = _sig(connues_f)
    return S.charger(f, c, FICHIER, SALLE)


def _modifier(fn, papa_present=False, demander_presence=False, connues_f=None):
    registre_voix(connues_f)                              # migré d'abord s'il le faut
    f, c = _sig(connues_f)
    return S.modifier(fn, f, c, papa_present=papa_present, demander_presence=demander_presence)


def qui_de(r):
    """Le nom que rend etiqueter pour une reconnaissance du registre : « Ahmed » (papa vérifié), « papa ? » (une voix à papa seul, mais à
    reconfirmer), « papa ou Ali ? » (une voix partagée, ou deux trop proches), « Ali »."""
    if r["partagee"]:
        return r["etiquette"]
    if r["papa"]:
        return "Ahmed" if r["verifie"] else f"{NOM_PAPA} ?"
    return r["etiquette"]


def doute_de_papa(qui):
    """« papa ? », « papa ou Ali ? » : un doute qui comprend papa (jamais papa vérifié, peut-être papa)."""
    q = str(qui or "").strip()
    return q.endswith("?") and NOM_PAPA in [n.strip() for n in q[:-1].split(" ou ")]


def verdict_du_morceau(resume, verdict_bloc):
    """Le verdict d'un morceau étiqueté (le chemin Whisper, stt.py, et le chemin Azure, etiqueter_bloc) : « moi » (rien que sa voix),
    « plusieurs » (papa et d'autres), « doute » (seulement des doutes qui comprennent papa : « papa ou Ali ? », 10/11), « autre », ou celui
    du morceau entier."""
    if not resume["voix"]:
        return "moi"
    if resume["plusieurs"] and resume["ahmed"]:
        return "plusieurs"
    if not resume["ahmed"]:
        return "doute" if all(doute_de_papa(q) for q in resume["voix"]) else "autre"
    return verdict_bloc or "ahmed"


_a_compter, _compte_ts = {}, [0.0]
COMPTER_S = 30


def _noter_entendues(compte, surs, t, musique=False):
    """Les voix des signatures entendues : leur compte (écrit au plus toutes les 30 s), et un vecteur SÛR qui enrichit leur timbre (une
    fois toutes les 2 min au plus par voix, jamais pendant la musique du téléphone, jamais une voix de papa : rien ne s'apprend tout seul
    sur sa voix ; son empreinte, la voix 1, garde son propre apprentissage « appris seul »)."""
    for k, n in compte.items():
        _a_compter[k] = _a_compter.get(k, 0) + n
    enrichir = {}
    if not musique:
        for k, v in surs.items():
            if t - _appris.get(("voix", k), 0) >= APPRENDRE_S:
                _appris[("voix", k)] = t
                enrichir[k] = v
    if not _a_compter and not enrichir:
        return
    if not enrichir and t - _compte_ts[0] < COMPTER_S:
        return
    a = dict(_a_compter)
    _a_compter.clear()
    _compte_ts[0] = t

    def fn(d):
        for k in set(a) | set(enrichir):
            S.entendre(d, k, a.get(k, 0), v=enrichir.get(k), t=t)
    try:
        _modifier(fn)
    except (OSError, ValueError):
        pass


def _parole(x, t):
    """(04/11) les secondes de parole d'une candidate dans les CANDIDATE_DUREE_S dernières secondes."""
    return round(sum(s for u, s in x["parole"] if t - u <= CANDIDATE_DUREE_S), 3)


def connues(fichier=None):
    """Les personnes nommées (papa à part) : [{nom, moyenne (leur voix la plus entendue), n, cree, voix: [N…]}], la vue de leurs signatures
    (10/11). Un fichier donné (une copie, un banc) se lit tel quel, sans registre."""
    if fichier is not None:
        try:
            return [x for x in json.loads(Path(fichier).read_text(encoding="utf-8")) if x.get("moyenne")]
        except (OSError, ValueError):
            return []
    try:
        return S.vue_connues(registre_voix())
    except (OSError, ValueError):
        return []


def _prenom(nom):
    """(29/10, relecture du système immunitaire) un prénom : des lettres, espaces, traits d'union et apostrophes, 40 au
    plus ; jamais « Ahmed » ni « voix N » : un nom avec des crochets forgerait une étiquette de la transcription."""
    nom = " ".join(str(nom or "").split())[:40]
    if not nom or not all(c.isalpha() or c in " -'’" for c in nom) or nom.casefold() == "ahmed" \
            or nom.casefold() == "papa" or re.fullmatch(r"voix\s*\d*", nom, re.IGNORECASE):
        raise ValueError("un prénom (lettres, espaces, traits d'union), autre qu'Ahmed")
    return nom


def nommer(numero, nom, salle=None, fichier=None, maintenant=None):
    """« voix 2 » → « Karim » : la voix de la conversation devient une voix connue, pour toujours (nommer_detail : proposée, si Karim
    a déjà sa signature)."""
    return nommer_detail(numero, nom, salle=salle, fichier=fichier, maintenant=maintenant)["nom"]


def nommer_detail(numero, nom, salle=None, fichier=None, maintenant=None, par="hakim"):
    """(10/11) « voix 2 » → « Karim » : {"nom", "voix": N, "propose": bool, "id"}.
    - Karim est NOUVEAU : sa signature naît tout de suite avec cette voix (force FORCE_HAKIM, pas encore validée par papa ; à la volée,
      comme le 09/11), et la voix quitte la salle (le registre la reconnaît désormais) ;
    - Karim a DÉJÀ sa signature : la voix lui est PROPOSÉE (papa valide, page Voix) ; elle garde son numéro dans la salle d'ici là, et
      son vecteur dans la proposition. Jamais papa : _prenom refuse « papa » et « Ahmed »."""
    nom = _prenom(nom)
    t = time.time() if maintenant is None else maintenant
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
    # (09/11, Ahmed : « pouvoir les enregistrer à la volée ») une voix encore candidate (son numéro temporaire, dès sa première phrase) :
    # nommée tout de suite, sans attendre ses 4 s de parole ; elle entre dans la salle
    k = next((c for c in _salle.get("candidates", []) if str(c.get("nom") or "").lower() == cherche), None) if x is None else None
    if k is not None:
        _salle["candidates"] = [c for c in _salle["candidates"] if c is not k]   # (09/11) par identité : comparer deux candidates (leurs tableaux) levait une erreur
        x = {"nom": k["nom"], "c": k["c"], "n": k["n"], "m": k.get("m", 0)}
        _salle["voix"].append(x)
    if x is None:
        presentes = ", ".join(v["nom"] for v in _salle["voix"][-8:] + [c for c in _salle.get("candidates", []) if c.get("nom")][-4:]) or "aucune"
        raise ValueError(f"aucune « {numero} » dans la conversation des 3 dernières heures (voix présentes : {presentes})")
    numero = x["nom"]
    m = re.fullmatch(r"voix (\d+)", str(numero))
    reg = registre_voix(fichier)
    num = int(m.group(1)) if m else None
    if num is None or str(num) in reg["voix"]:            # une voix de la salle déjà nommée à l'ancienne, ou un numéro déjà pris
        num = max(S.numero_max(reg), *(_numeros_salle() or [0])) + 1
    deja = S.trouver(reg, nom)
    if deja is not None:
        # (10/11) une personne qui a déjà sa signature : Hakim propose, papa valide ; la voix reste « voix N » dans la conversation
        if k is not None:
            _sauver_salle(salle)                              # la candidate nommée est entrée dans la salle : gardée
        p = _modifier(lambda d: S.proposer(d, "ajouter", deja, num, par=par, raison=f"« {numero} », c'est {deja}",
                                           c=x["c"], n=x["n"], m=x.get("m", 0), t=t), connues_f=fichier)
        return {"nom": deja, "voix": num, "propose": True, "id": p["id"]}
    _modifier(lambda d: S.lier(d, nom, num, S.FORCE_HAKIM, par, c=x["c"], n=x["n"], m=x.get("m", 0), t=t), connues_f=fichier)
    _salle["voix"] = [v for v in _salle["voix"] if v is not x]   # le registre la reconnaît désormais (par son nom)
    if _salle["dernier"] == numero:
        _salle["dernier"] = nom
    _sauver_salle(salle)
    return {"nom": nom, "voix": num, "propose": False, "id": None}


def renommer(ancien, nouveau, fichier=None):
    """« Machine à café » → « Inconnu » : une voix connue change de nom et garde son empreinte (29/10 : sans cet outil,
    Hakim a dû oublier la voix pour la renommer). (10/11) toute sa signature la suit ; papa garde son nom."""
    nouveau = _prenom(nouveau)
    return _modifier(lambda d: S.renommer(d, str(ancien).strip(), nouveau), connues_f=fichier)


def oublier(nom, fichier=None):
    """(10/11) toute la signature d'une personne ; ses voix partagées restent aux autres (une voix de papa qui ne devient « à lui seul »
    que par cet oubli garde une force basse : elle ne vaut papa vérifié qu'après son geste). Jamais papa (ValueError)."""
    return _modifier(lambda d: S.oublier(d, str(nom).strip()), connues_f=fichier)


# ---- (03/11, Ahmed : « micro ouvert, jamais fermé ; il doit apprendre de lui-même à écouter et focaliser son attention ; si
# plusieurs voix se mélangent, il doit pouvoir séparer chaque voix selon son timbre ») ----
# - SA propre voix : apprise de ce qu'il dit (sa voix de synthèse, voix_serveur « dire »), sans rien demander à personne ;
#   ce qui sonne comme lui est mis de côté (« moi ») : c'est l'écho de sa voix, pas papa qui parle.
# - Mot à mot : quand Whisper date les mots, le segment est écouté par fenêtres de 1,5 s (pas de 0,75 s) ; chaque mot va à
#   la voix de la fenêtre la plus proche de son instant, même au milieu d'une phrase. Une fenêtre isolée qui ne ressemble à
#   personne (à cheval sur deux voix) ne crée pas de voix : il en faut deux de suite.
MOI = Path.home() / "AIOS" / "jarvis" / "empreinte-moi.json"
NOM_PAPA = "papa"
# (03/11, Ahmed : « la reconnaissance du premier abord est consciente ; puis le tri et la reconnaissance se font dans le subconscient,
# qui envoie juste le nom de celui qui parle, ou son doute entre qui et qui ; plus les voix parlent, plus il note que c'est moi »)
# - une voix SÛRE (au moins 0,7, et 0,15 au-dessus de toute autre) enrichit seule son empreinte : celle de papa (registre « appris
#   seul ») ou celle d'une voix nommée ; une fois toutes les 2 min au plus par personne, jamais pendant la musique du téléphone ;
# - deux personnes connues trop proches (au moins 0,5 chacune, moins de 0,08 d'écart) : « [papa ou Ali ?] ».
SUR, MARGE_SURE, APPRENDRE_S = 0.7, 0.15, 120
SEUIL_DOUTE_ENTRE, ECART_DOUTE = 0.5, 0.08
_appris = {}                                             # qui → la dernière fois que son empreinte s'est enrichie seule
MOI_MAX, SEUIL_MOI = 40, 0.5
FENETRE_S, PAS_S = 1.5, 0.75


def apprendre_moi(audio, fichier=None, registre=None):
    """Un échantillon de SA voix (ce qu'il vient de dire) ; rend le nombre d'échantillons de ce registre, ou None si trop court.
    (06/11, Ahmed : « il entend sa propre voix et ça le perturbe ; il faut qu'il reconnaisse sa voix comme étant la sienne ») registre :
    laquelle de SES voix (« rap » : Chatterbox et sa référence ; « azure-… » : sa voix Azure ; sans : sa voix Chatterbox d'avant,
    « mac ») ; chacune a sa moyenne, il se reconnaît dans la plus proche (deux timbres si différents ne se moyennent pas)."""
    v = embedding(audio)
    if v is None:
        return None
    return apprendre_moi_vecteur(v, fichier, registre)


def _registre_moi(registre):
    r = re.sub(r"[^\w.-]+", "-", str(registre or "").strip().lower())[:60]
    return r if r and r != "mac" else None


def apprendre_moi_vecteur(v, fichier=None, registre=None):
    f = Path(fichier or MOI)
    d = _lire(f) or {"vecteurs": []}
    reg = _registre_moi(registre)
    cible = d if reg is None else d.setdefault("registres", {}).setdefault(reg, {"vecteurs": []})
    cible["vecteurs"] = (cible.get("vecteurs", []) + [np.asarray(v, float).round(5).tolist()])[-MOI_MAX:]
    m = np.mean(np.array(cible["vecteurs"]), axis=0)
    cible["moyenne"] = (m / (np.linalg.norm(m) or 1.0)).round(5).tolist()
    cible["maj"] = d["maj"] = time.time()
    _ecrire(f, d)
    return len(cible["vecteurs"])


def moyennes_moi(fichier=None):
    """Ses voix connues : {registre : moyenne} (au moins 3 échantillons chacune ; « mac » : celle d'avant)."""
    d = _lire(fichier or MOI) or {}
    out = {}
    if d.get("moyenne") and len(d.get("vecteurs", [])) >= 3:
        out["mac"] = np.array(d["moyenne"])
    for k, r in (d.get("registres") or {}).items():
        if r and r.get("moyenne") and len(r.get("vecteurs", [])) >= 3:
            out[k] = np.array(r["moyenne"])
    return out


def score_moi(v, moyennes):
    """(score, registre) : la plus proche de ses voix ; (-1, None) sans voix connue."""
    if not moyennes or v is None:
        return -1.0, None
    return max((float(np.dot(v, m)), k) for k, m in moyennes.items())


def _moyenne_moi(fichier=None):
    d = _lire(fichier or MOI)
    return np.array(d["moyenne"]) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 3 else None


def qui_parle(audio, fichier=None, moi=None):
    """(06/11) tout un morceau (l'oreille Azure ne date pas les mots) : par fenêtres de 1,5 s, chacune est-elle SA voix (au moins SEUIL_MOI
    et 0,05 au-dessus de papa) ? {"moi": meilleur score de soi, "ahmed": meilleur score de papa, "part_moi", "registre", "verdict":
    « moi » quand au moins 80 % des fenêtres sont lui, sinon None}. Jamais « moi » quand papa est reconnu (au moins SEUIL_AHMED)."""
    a = np.asarray(audio, dtype=np.float32)
    mes = moyennes_moi(moi)
    if not mes:
        return {"verdict": None, "raison": "sa voix pas encore apprise"}
    d = _lire(fichier)
    papa = (lambda v: score_ahmed(v, d)) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2 else (lambda v: -1.0)
    n, pas = int(FENETRE_S * 16000), int(PAS_S * 16000)
    debuts = list(range(0, max(1, len(a) - n + 1), pas)) if len(a) >= n else [0]
    fen = [embedding(a[i:i + n], min_s=1.0) for i in debuts]
    fen = [v for v in fen if v is not None]
    if not fen:
        return {"verdict": None, "raison": "court"}
    sm = [score_moi(v, mes) for v in fen]
    sa = [papa(v) for v in fen]
    sont_moi = [s >= SEUIL_MOI and s > p + 0.05 for (s, _), p in zip(sm, sa)]
    part = sum(sont_moi) / len(fen)
    meilleur = max(sm)
    verdict = "moi" if part >= 0.8 and max(sa) < SEUIL_AHMED else None
    return {"moi": round(meilleur[0], 2), "registre": meilleur[1], "ahmed": round(max(sa), 2), "part_moi": round(part, 2), "verdict": verdict}


def etiqueter(audio, segments, nouveau_tour=True, fichier=None, maintenant=None, moi=None, musique=False, numeroter=False):
    """segments : [{start, end, text[, words]}] (gardés par stt). Rend (texte étiqueté, résumé) ; résumé = {"voix": [...],
    "plusieurs": bool, "ahmed": bool, "autres": [...], "moi": ce qu'il a entendu de SA voix ou ""}. Le texte rendu peut
    être vide (tout était sa voix). Sans voix reconnaissable : (None, None).
    numeroter (09/11, Ahmed : « qu'il ne prenne jamais les paroles des autres pour les miennes » ; « mesure la latence d'attribution d'une
    voix inconnue (numéro temporaire) ») : une voix inconnue reçoit tout de suite son NUMÉRO TEMPORAIRE (celui qu'elle gardera si elle
    se confirme, et que voix_nommer accepte déjà) au lieu de prêter ses mots à la voix d'avant ou à papa."""
    t = time.time() if maintenant is None else maintenant
    _charger_salle(t)
    if t - _salle["ts"] > SALLE_DUREE_S:
        _salle["voix"] = []
    _salle["ts"] = t
    if nouveau_tour:
        _salle["dernier"] = None
    # (04/11) une candidate qui n'a rien dit depuis 5 min est oubliée ; sa parole plus ancienne ne compte plus
    for k in _salle["candidates"]:
        k["parole"] = [p for p in k["parole"] if t - p[0] <= CANDIDATE_DUREE_S]
    _salle["candidates"] = [k for k in _salle["candidates"] if k["parole"]]
    d = _lire(fichier)
    moyenne = np.array(d["moyenne"]) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2 else None
    ahmed = (lambda v: score_ahmed(v, d)) if moyenne is not None else None
    mes_voix = moyennes_moi(moi)                          # (06/11) toutes ses voix (rap, Azure, celle d'avant)
    try:
        reg = registre_voix()                             # (10/11) les signatures : papa (sa voix 1 et ses autres voix), les personnes nommées
    except (OSError, ValueError):
        reg = S.minimal()                                 # illisible : papa par son empreinte, comme avant
    a = np.asarray(audio, dtype=np.float32)

    def connu(v):
        """La voix d'un vecteur parmi celles qu'il connaît (lui, les signatures, celles de la salle) ; None : inconnue.
        (10/11) une voix d'une signature donne le nom de sa personne ; une voix partagée (« papa et Ali ont la voix 127 »), ou deux voix
        de personnes différentes trop proches (moins de 0,08), donnent le doute : « papa ou Ali ? »."""
        sm = score_moi(v, mes_voix)[0]
        sa = ahmed(v) if ahmed else -1.0
        proches = [(float(np.dot(v, x["c"])), x) for x in _salle["voix"]]
        s, x = max(proches, key=lambda p: p[0]) if proches else (-1.0, None)
        r = S.reconnaitre(v, reg, ahmed) if reg else None
        sn = S.score_autres(v, reg) if reg else -1.0
        if sm >= SEUIL_MOI and sm > max(sa, s, sn, r["score"] if r else -1.0) + 0.05:
            return "moi", None
        if r:
            entendues[r["voix"]] = entendues.get(r["voix"], 0) + 1
            qui = qui_de(r)
            if r["partagee"]:
                partagees.setdefault(qui, {"etiquette": qui, "voix": r["voix"], "personnes": r["personnes"]})
            elif r["score"] >= SUR and min(r["marge"], r["score"] - max(s, sm)) >= MARGE_SURE:
                if r["voix"] == S.VOIX_PAPA and r["verifie"]:
                    surs["Ahmed"] = v                     # son empreinte s'enrichit seule, comme avant (registre « appris seul »)
                elif not r["papa"]:
                    surs[r["voix"]] = v                   # une voix d'une personne nommée
            return qui, None
        if sa >= SEUIL_DOUTE and sa > max(s, sn) + 0.1:
            # (2026-10-20) une phrase d'Ahmed dans un registre inhabituel : plus proche de lui que de toute autre voix
            # entendue — c'est lui, pas une « voix 3 »
            return "Ahmed", None
        if x is not None and s >= SEUIL_MEME_VOIX:
            return x["nom"], x
        return None, None

    def ajouter(v, x=None, n=1, sous_musique=None, nom_temporaire=None):
        # (03/11) « m » : combien de fois cette voix a été entendue pendant que le téléphone jouait de la musique
        if x is not None:
            x["c"] = (x["c"] * x["n"] + v) / (x["n"] + 1)
            x["c"] /= (np.linalg.norm(x["c"]) or 1.0)
            x["n"] += 1
            x["m"] = x.get("m", 0) + (1 if musique else 0)
            return x["nom"]
        # le numéro qui suit le plus grand de la salle (une voix rattachée à papa ne laisse pas son numéro à une autre) ; (09/11) une
        # candidate confirmée garde son numéro temporaire
        nom = nom_temporaire or _prochain_numero(moyenne is not None)
        _salle["voix"].append({"nom": nom, "c": v / (np.linalg.norm(v) or 1.0), "n": n,
                               "m": (1 if musique else 0) if sous_musique is None else sous_musique})
        return nom

    def provisoire(vs, secondes):
        """(04/11) une voix inconnue (ses vecteurs vs, sa durée) nourrit la candidate qui lui ressemble, ou une nouvelle ;
        rend « voix N » quand la candidate a assez parlé (elle entre dans la salle), sinon None : pas encore une personne."""
        somme = np.sum(vs, axis=0)
        v = somme / (np.linalg.norm(somme) or 1.0)
        proches = [(float(np.dot(v, k["c"])), k) for k in _salle["candidates"]]
        s, k = max(proches, key=lambda p: p[0]) if proches else (-1.0, None)
        if k is None or s < SEUIL_MEME_VOIX:
            k = {"c": v, "n": 0, "m": 0, "parole": []}
            _salle["candidates"].append(k)
        c = k["c"] * k["n"] + somme
        k["c"] = c / (np.linalg.norm(c) or 1.0)
        k["n"] += len(vs)
        k["m"] += len(vs) if musique else 0
        k["parole"].append([t, round(float(secondes), 3)])
        if _parole(k, t) < CONFIRMER_S:
            if numeroter:                                 # (09/11) son numéro temporaire, dès sa première fenêtre
                k["nom"] = k.get("nom") or _prochain_numero(moyenne is not None)
                return k["nom"]
            return None
        _salle["candidates"] = [c for c in _salle["candidates"] if c is not k]   # (09/11) par identité : comparer deux candidates (leurs tableaux) levait une erreur
        return ajouter(k["c"], n=k["n"], sous_musique=k["m"], nom_temporaire=k.get("nom"))

    def qui_segment(brut):
        repli = _salle["dernier"] or ("Ahmed" if moyenne is not None else "voix 1")
        v = embedding(brut, SEGMENT_MIN_S) if len(brut) >= SEGMENT_MIN_S * TAUX else None
        if v is None:
            return repli
        q, x = connu(v)
        if q in ("moi", "Ahmed") or (q and x is None):
            return q
        if x is not None:
            return ajouter(v, x)
        return provisoire([v], len(brut) / TAUX) or repli      # (04/11) une candidate : ses mots à la voix d'avant

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
                # ses voisines qui lui ressemblent : la même voix ; (04/11) une candidate, chaque fenêtre pour 0,75 s de parole,
                # « » (pas encore une personne) tant qu'elle n'est pas confirmée
                groupe = [w for w in fen[k:] if w[1] is None and w[0] is not None and float(np.dot(v, w[0])) >= SEUIL_MEME_VOIX]
                nom = provisoire([w[0] for w in groupe], len(groupe) * PAS_S) or ""
                for w in groupe:
                    w[1] = nom
            elif voisine:
                fen[k][1] = next((w[1] for w in voisine if w[1]), None)
        for v, q, x in fen:                           # les voix de la salle apprennent de chaque fenêtre
            if v is not None and x is not None:
                ajouter(v, x)
        sortie = []
        for w, ma, mb in mots:
            k = min(range(len(centres)), key=lambda i: abs(centres[i] - (ma + mb) / 2))
            q = fen[k][1]
            if q == "":                               # (04/11) une candidate : la voix qui parlait juste avant dans la phrase
                q = next((s for s, _ in reversed(sortie) if s != "moi"), None)
            q = q or _salle["dernier"] or ("Ahmed" if moyenne is not None else "voix 1")
            if sortie and sortie[-1][0] == q:
                sortie[-1][1].append(w)
            else:
                sortie.append((q, [w]))
        return [(q, " ".join(ws)) for q, ws in sortie]

    morceaux, vus, de_moi = [], [], []
    surs = {}                                             # (03/11) qui → un vecteur sûr de ce morceau, pour l'enrichir seul
    entendues, partagees = {}, {}                         # (10/11) les voix des signatures entendues ; les voix partagées (le doute)
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
            # (03/11, Ahmed : « que ça s'appelle papa ») ce que Hakim lit : « [papa] », jamais « [Ahmed] »
            morceaux.append(f"[{NOM_PAPA if qui == 'Ahmed' else qui}] {bout}" if etiquette else bout)
            _salle["dernier"] = qui
    try:
        _sauver_salle()
    except OSError:
        pass
    if not musique and "Ahmed" in surs and t - _appris.get("Ahmed", 0) >= APPRENDRE_S:   # (03/11) son empreinte enrichie seule
        _appris["Ahmed"] = t
        try:
            apprendre_vecteur(surs["Ahmed"], fichier, registre="appris seul")
        except (OSError, ValueError):
            pass
    # (10/11) les voix des signatures : leur compte, et les timbres sûrs des personnes nommées (jamais une voix de papa)
    _noter_entendues(entendues, {k: v for k, v in surs.items() if isinstance(k, int)}, t, musique)
    autres = [q for q in vus if q != "Ahmed"]
    resume = {"voix": vus, "plusieurs": len(vus) >= 2, "ahmed": "Ahmed" in vus, "autres": autres, "moi": " ".join(de_moi),
              "doute": [q for q in vus if q.endswith(" ?")],
              "partagees": [x for q, x in partagees.items() if q in vus]}
    if de_moi:
        return " ".join(morceaux), resume
    if not morceaux:
        return None, None
    if moyenne is None and len(vus) < 2:                    # sans empreinte, une seule voix : rien à dire
        return None, None
    return " ".join(morceaux), resume


def _zone_parlee(a, trame=480):
    """(début, fin) en secondes de ce qui sonne dans un morceau : les trames de 30 ms au-dessus de max(0,003 ; 10 % du 95e centile)."""
    n = len(a) // trame
    if n < 1:
        return 0.0, len(a) / TAUX
    rms = np.sqrt(np.mean(np.square(a[:n * trame].reshape(n, trame)), axis=1))
    idx = np.nonzero(rms >= max(0.003, 0.1 * float(np.percentile(rms, 95))))[0]
    if not len(idx):
        return 0.0, len(a) / TAUX
    return idx[0] * trame / TAUX, (idx[-1] + 1) * trame / TAUX


def etiqueter_bloc(audio, texte, fichier=None, maintenant=None, moi=None, musique=False, nouveau_tour=True):
    """(09/11, Ahmed, 19:29-19:32 : « il faut que tu dissocies ce que disent les autres de mes paroles » ; « la reconnaissance vocale aussi,
    optimisée ») un morceau du micro de papa transcrit par Azure, qui ne dit ni qui parle ni le temps des mots. Avant : rien ne vérifiait
    sa voix sur ce chemin (seule SA propre voix était cherchée, et seulement quand l'oreille vive était libre) ; une citation du live, une
    chanson, une voix de la pièce passaient pour papa. Ici, la même reconnaissance que le chemin Whisper : l'empreinte du morceau entier
    (reconnaitre) et ses voix fenêtre par fenêtre (etiqueter), les mots répartis également sur ce qui sonne ; une voix inconnue reçoit son
    numéro temporaire tout de suite (numeroter). Rend ce que rendait stt.transcrire : {texte (étiqueté « [voix 3] … » s'il le faut),
    voix: {score, verdict, locuteurs…}, moi}."""
    a = np.asarray(audio, dtype=np.float32)
    texte = " ".join(str(texte or "").split())
    v = reconnaitre(a, fichier)
    pas_apprise = etat(fichier)["echantillons"] < 2
    sortie = {"texte": texte, "voix": {**(v or {"raison": "pas_apprise" if pas_apprise else "court"}), "duree_s": round(len(a) / TAUX, 1)}}
    mots = texte.split()
    if not mots or pas_apprise:
        return sortie
    d0, d1 = _zone_parlee(a)
    pas = (d1 - d0) / len(mots)
    seg = {"start": d0, "end": d1, "text": texte,
           "words": [{"word": w, "start": d0 + i * pas, "end": d0 + (i + 1) * pas} for i, w in enumerate(mots)]}
    etiquete, resume = etiqueter(a, [seg], nouveau_tour=nouveau_tour, fichier=fichier, maintenant=maintenant, moi=moi,
                                 musique=musique, numeroter=True)
    if resume and resume.get("moi"):                        # sa propre voix entendue : mise de côté (son écho)
        sortie["moi"] = resume["moi"]
    # (09/11, mesuré sur les voix du Mac : une citation arabe d'une autre voix à 0,41 de l'empreinte de papa passait pour lui par la règle
    # du « registre inhabituel ») le morceau entier ne ressemble pas assez à papa (moins de 0,55) : ce qui lui était prêté est marqué
    # « [papa ?] » ; jamais affirmé, jamais retiré (ses propres mots restent, Hakim sait qu'il doit douter)
    if etiquete and resume and resume["ahmed"] and v and v.get("verdict") in ("doute", "autre"):
        douteux = etiquete.replace(f"[{NOM_PAPA}] ", f"[{NOM_PAPA} ?] ")
        etiquete = douteux if douteux.startswith("[") else f"[{NOM_PAPA} ?] {douteux}"
        resume = {**resume, "voix": [("papa ?" if q == "Ahmed" else q) for q in resume["voix"]], "autres": resume["autres"] or ["papa ?"]}
    if etiquete is not None and resume and (resume["autres"] or resume["plusieurs"] or resume.get("moi")):
        sortie["texte"] = etiquete
        sortie["voix"] = {**sortie["voix"], "locuteurs": resume["voix"], "verdict": verdict_du_morceau(resume, sortie["voix"].get("verdict", "ahmed"))}
    elif resume:
        sortie["voix"]["locuteurs"] = resume["voix"]
    partager(sortie["voix"], resume)
    return sortie


def partager(voix, resume):
    """(10/11) les voix partagées entendues dans le morceau (« papa ou Ali ? ») : [{etiquette, voix, personnes}], pour son tour."""
    l = list((resume or {}).get("partagees") or [])
    if voix.get("partagee") and not any(x["voix"] == voix.get("voix_n") for x in l):
        l.append({"etiquette": S.etiquette(voix["partagee"]), "voix": voix.get("voix_n"), "personnes": voix["partagee"]})
    if l:
        voix["partagees"] = l[:4]
    return voix


def _enrichir_connue(nom, v, fichier=None):
    """(03/11) une voix nommée, reconnue sûrement : son empreinte suit doucement (la moyenne de ses 200 dernières fois au plus).
    (10/11) la voix de sa signature la plus proche de v (jamais papa) ; rend son nombre de fois, ou None."""
    reg = registre_voix(fichier)
    p = S.trouver(reg, nom)
    if p is None or p == S.PAPA:
        return None
    siennes = [(float(np.dot(np.asarray(v), np.asarray(reg["voix"][k]["c"]))), k) for k in reg["personnes"][p]["voix"]
               if reg["voix"].get(k, {}).get("c") is not None and len(reg["voix"][k]["c"]) == len(v)]
    if not siennes:
        return None
    k = max(siennes)[1]
    _modifier(lambda d: S.entendre(d, k, 1, v=v), connues_f=fichier)
    return int(registre_voix(fichier)["voix"][k]["n"])


def rattacher_a_papa(qui="toutes", registre="chant", fichier=None, maintenant=None):
    """(03/11, Ahmed via Hakim : « toutes ces voix temporaires (voix 56, 63, 64…), c'est moi, surtout quand je chante ou que la
    musique brouille : un seul registre, papa ») les voix sans nom de la salle (« toutes », ou « voix 56, voix 63 ») rejoignent
    papa, dans un registre (« chant » par défaut) ; celles nées surtout pendant la musique du téléphone sont écartées
    (la musique ne doit pas fausser sa voix). La confirmation (sa voix reconnue, ou un écrit de lui ; ou sa présence, le geste « soi »
    de son système immunitaire) est vérifiée avant, par l'appelant : c'est papa lui-même.
    (10/11, Ahmed : « ma voix est reconnue sous 19 voix différentes, qui sont ma signature vocale ») chacune devient une voix de SA
    SIGNATURE (son numéro gardé, force FORCE_PAPA, le registre noté), au lieu de se fondre dans son empreinte où elle se perdait : ses
    60 échantillons s'emplissaient de « appris seul » (mesuré le 10/11 : les 15 voix N rattachées par « soi » depuis le 04/11 n'y étaient
    plus). Une voix d'une autre signature nommée par son numéro (« voix 127 ») devient PARTAGÉE : « papa ou Ali ? ».
    Rend {"rattachees", "ecartees_musique", "inconnues", "partagees"}."""
    t = time.time() if maintenant is None else maintenant
    _charger_salle(t)
    voulues = None if str(qui or "toutes").strip().lower() in ("toutes", "tout", "") else \
        {f"voix {n}" for n in re.findall(r"\d+", str(qui))}
    reg = registre_voix()
    r = {"rattachees": [], "ecartees_musique": [], "inconnues": [], "partagees": [], "ecartees_autres": []}
    garde, liens = [], []
    e = _lire(fichier)
    papa = (lambda v: score_ahmed(v, e)) if e and e.get("moyenne") and len(e.get("vecteurs", [])) >= 2 else (lambda v: -1.0)
    for x in _salle["voix"]:
        m = re.fullmatch(r"voix (\d+)", x["nom"])
        if not m or (voulues is not None and x["nom"] not in voulues):
            garde.append(x)
            continue
        if x.get("m", 0) > x["n"] / 2:
            r["ecartees_musique"].append(x["nom"])
            garde.append(x)
            continue
        c = np.asarray(x["c"], dtype=np.float64)
        if voulues is None and S.score_autres(c, reg) >= SEUIL_DOUTE_ENTRE and S.score_autres(c, reg) > papa(c):
            # (10/11) « toutes » : une voix plus proche de la signature d'une autre personne que de lui reste à part (une voix du live, de la
            # pièce : devenue sa voix vérifiée, elle donnerait des ordres en son nom) ; nommée par son numéro, elle le rejoint quand même
            r["ecartees_autres"].append(x["nom"])
            garde.append(x)
            continue
        num = int(m.group(1))
        if str(num) in reg["voix"]:                       # un numéro déjà pris au registre (jamais en principe) : un neuf
            num = max(S.numero_max(reg), *(_numeros_salle() or [0])) + 1
        liens.append((num, x))
        r["rattachees"].append(x["nom"])
    for nom in sorted(voulues - {x["nom"] for x in _salle["voix"]}, key=lambda n: int(n.split()[1])) if voulues else []:
        num = int(nom.split()[1])
        if str(num) in reg["voix"] and num != S.VOIX_PAPA:
            liens.append((num, None))
            r["rattachees"].append(nom)
            autres = [n for n, _ in S.proprietaires(reg, num) if n != S.PAPA]
            if autres:
                r["partagees"].append({"voix": num, "personnes": [S.PAPA] + autres})
        elif num != S.VOIX_PAPA:
            r["inconnues"].append(nom)
    if liens:
        reg_txt = str(registre or "chant")[:40]

        def fn(d):
            for num, x in liens:
                S.lier(d, S.PAPA, num, S.FORCE_PAPA, "papa", c=None if x is None else x["c"], n=1 if x is None else x["n"],
                       m=0 if x is None else x.get("m", 0), registre=reg_txt, t=t)
        _modifier(fn, papa_present=True)
    pris = {id(x) for _, x in liens if x is not None}
    _salle["voix"] = [x for x in garde if id(x) not in pris]
    if _salle.get("dernier") in r["rattachees"]:
        _salle["dernier"] = "Ahmed"
    try:
        _sauver_salle()
    except OSError:
        pass
    return r


def _voix_de_la_salle(numero, t=None):
    """(10/11) une voix sans nom de la conversation, par son numéro : (N, son entrée) ou (N, None)."""
    _charger_salle(time.time() if t is None else t)
    n = S._num(numero)
    x = next((v for v in _salle["voix"] + [c for c in _salle.get("candidates", []) if c.get("nom")] if v.get("nom") == f"voix {n}"), None)
    return n, x


def _retirer_de_la_salle(n):
    avant = len(_salle["voix"]) + len(_salle.get("candidates", []))
    _salle["voix"] = [v for v in _salle["voix"] if v.get("nom") != f"voix {n}"]
    _salle["candidates"] = [c for c in _salle.get("candidates", []) if c.get("nom") != f"voix {n}"]
    if len(_salle["voix"]) + len(_salle["candidates"]) != avant:
        try:
            _sauver_salle()
        except OSError:
            pass


def proposer_signature(geste, personne, numero, raison="", par="hakim", maintenant=None):
    """(10/11) Hakim propose, papa valide (page Voix) : ajouter ou retirer une voix de la signature d'une personne (papa compris : il
    valide de sa présence). Une voix de la conversation garde son vecteur dans la proposition. Rend la proposition."""
    t = time.time() if maintenant is None else maintenant
    reg = registre_voix()
    nom = S.trouver(reg, personne)
    if nom is None:
        if geste == "retirer":
            raise ValueError(f"aucune signature « {personne} »")
        nom = _prenom(personne)
    n, x = _voix_de_la_salle(numero, t)
    if geste == "ajouter" and x is None and str(n) not in reg["voix"]:
        raise ValueError(f"aucune voix {n} dans la conversation des 3 dernières heures ni dans les signatures")
    if geste == "retirer" and str(n) not in reg["personnes"][nom]["voix"]:
        raise ValueError(f"la voix {n} n'est pas dans la signature de {nom}")
    if n == S.VOIX_PAPA and nom != S.PAPA:
        raise ValueError("la voix 1 est l'empreinte de papa : elle n'est qu'à lui")
    return _modifier(lambda d: S.proposer(d, geste, nom, n, par=par, raison=raison, c=None if x is None else x["c"],
                                          n=1 if x is None else x["n"], m=0 if x is None else x.get("m", 0), t=t))


def signature_geste(q, maintenant=None):
    """(10/11) les gestes de papa sur les signatures (la page Voix, par l'oreille des voix) : q = {action : « voir » | « ajouter » |
    « retirer » | « valider » | « refuser », personne, voix, proposition, presence}. presence : le cockpit a vérifié sa présence (son empreinte
    digitale) ; sans elle, un geste qui rendrait une voix « papa vérifié » rend {"erreur", "presence": True} (la page la redemande).
    Rend le résumé des signatures, avec les voix sans nom de la conversation."""
    t = time.time() if maintenant is None else maintenant
    action = str(q.get("action") or "voir")
    presence = q.get("presence") is True
    try:
        if action in ("ajouter", "retirer"):
            reg = registre_voix()
            nom = S.trouver(reg, q.get("personne"))
            if nom is None:
                if action == "retirer":
                    raise ValueError(f"aucune signature « {q.get('personne')} »")
                nom = _prenom(q.get("personne"))
            n, x = _voix_de_la_salle(q.get("voix"), t)
            if action == "ajouter":
                if nom == S.PAPA and not presence:
                    raise S.PresenceRequise(f"ajouter la voix {n} à ta signature : il faut ta présence")
                _modifier(lambda d: S.lier(d, nom, n, S.FORCE_PAPA, "papa", c=None if x is None else x["c"], n=1 if x is None else x["n"],
                                           m=0 if x is None else x.get("m", 0), t=t), papa_present=presence, demander_presence=True)
                if x is not None:
                    _retirer_de_la_salle(n)
            else:
                _modifier(lambda d: S.delier(d, nom, n), papa_present=presence, demander_presence=True)
        elif action in ("valider", "refuser"):
            ident = str(q.get("proposition") or "")       # (pas « id » : l'oreille des voix s'en sert pour ses demandes)
            reg = registre_voix()
            x = next((p for p in reg.get("propositions", []) if p["id"] == ident), None)
            if action == "valider" and x and x["geste"] == "ajouter" and x["personne"] == S.PAPA and not presence:
                raise S.PresenceRequise(f"ajouter la voix {x['voix']} à ta signature : il faut ta présence")
            _modifier(lambda d: S.appliquer_proposition(d, ident, action == "valider", t=t), papa_present=presence, demander_presence=True)
            if x and action == "valider" and x["geste"] == "ajouter":
                _retirer_de_la_salle(int(x["voix"]))
        elif action != "voir":
            return {"erreur": "geste inconnu"}
    except S.PresenceRequise as e:
        return {"erreur": str(e), "presence": True}
    except (ValueError, OSError) as e:
        return {"erreur": str(e)[:200]}
    _charger_salle(t)
    salle = [{"voix": int(x["nom"].split()[1]), "n": int(x.get("n") or 0), "musique": int(x.get("m") or 0)}
             for x in _salle["voix"] if re.fullmatch(r"voix \d+", str(x.get("nom") or ""))]
    return {"ok": True, **S.resume(registre_voix()), "salle": sorted(salle, key=lambda x: -x["voix"])[:40]}


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


# ---- (06/11, Ahmed : « il faut qu'il reconnaisse sa voix comme étant la sienne ») ses voix apprises de dehors ----

def lire_wav16(fichier):
    """Un WAV PCM (Azure : 24 kHz, 16 bits, mono ; la référence de rap) en 16 kHz mono float32, sans ffmpeg."""
    import wave
    with wave.open(str(fichier), "rb") as w:
        sr, n, canaux, largeur = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        brut = w.readframes(n)
    if largeur != 2:
        raise ValueError("seulement du PCM 16 bits")
    x = np.frombuffer(brut, dtype="<i2").astype(np.float32) / 32768.0
    if canaux > 1:
        x = x.reshape(-1, canaux).mean(axis=1)
    if sr != 16000 and len(x):
        k = int(len(x) * 16000 / sr)
        x = np.interp(np.linspace(0, len(x) - 1, k), np.arange(len(x)), x).astype(np.float32)
    return x


def apprendre_moi_fichier(fichier, registre=None, fichier_moi=None, morceau_s=3.0):
    """Un fichier de SA voix, appris par morceaux de 3 s (une référence de 10 s donne 3 échantillons) ; rend le nombre d'échantillons."""
    x = lire_wav16(fichier)
    n = int(morceau_s * TAUX)
    morceaux = [x[i:i + n] for i in range(0, len(x), n) if len(x[i:i + n]) >= PAROLE_MIN_S * TAUX] or [x]
    total = None
    for m in morceaux:
        total = apprendre_moi(m, fichier=fichier_moi, registre=registre) or total
    return total


if __name__ == "__main__":
    # (06/11) le cockpit lui apprend sa voix Azure : « moi <registre> <fichier> » (le fichier, un jarvis-moi-….wav du dossier temporaire,
    # est effacé ensuite) ; « moi-semer <registre> <fichier> » : une référence gardée (sa voix de rap), jamais effacée
    import sys
    import tempfile
    if len(sys.argv) == 4 and sys.argv[1] in ("moi", "moi-semer"):
        f = Path(sys.argv[3]).resolve()
        jetable = sys.argv[1] == "moi" and f.parent == Path(tempfile.gettempdir()).resolve() and re.match(r"^jarvis-moi-[\w.-]{1,80}\.wav$", f.name)
        if sys.argv[1] == "moi" and not jetable:
            print(json.dumps({"erreur": "seulement un jarvis-moi-….wav du dossier temporaire"}))
            sys.exit(2)
        try:
            print(json.dumps({"registre": sys.argv[2], "echantillons": apprendre_moi_fichier(f, sys.argv[2])}))
        finally:
            if jetable:
                try:
                    os.unlink(f)
                except OSError:
                    pass
