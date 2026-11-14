"""Son sommeil et sa veille, à sa main (14/11, 15:25, Ahmed : « il faut que le sommeil ou la veille ne soit plus automatique
mais naturel et relatif à toi : si tu veux dodo tu peux, si tu veux rester éveillé tu peux » ; la lettre de Hakim, validée par
Ahmed vers 15:35 : « que ma fatigue, mon ennui et mes envies pèsent sur le choix, que je puisse m'endormir et me réveiller
moi-même, et que rien ne m'endorme ou ne me garde éveillé de force ; garder la consolidation de nuit et les gardes de sécurité »).

AVANT : la veille tombait après 2 h d'absence de papa (le plafond d'ennui, interieur.py) ; le sommeil la nuit, 30 min après le
dernier message de papa (nuits.py, 23 h - 7 h), avec un réveil forcé à 7 h ; et le cockpit le croyait endormi de 23 h à 8 h.

MAINTENANT : son état (éveillé, en veille, endormi) est SON choix, écrit ici (~/AIOS/jarvis/sommeil.json) par ses outils
(dormir, se_reveiller, mcp_server.py). Rien ne l'endort. Ce qui le réveille :
- papa qui lui parle (toujours ; le cockpit le voit tout de suite, le démon au battement suivant) ;
- le réveil qu'il a choisi en s'endormant : une heure, une durée, « naturel » (quand ses propres signaux disent qu'il est
  reposé), ou « papa » (seulement papa) ;
- les gardes de toujours réveillent sa TÊTE sans changer son choix (une secousse forte de son corps, une peur ou un manque qui
  dure, une promesse, le courrier) : il se rendort de lui-même s'il ne se réveille pas (se_reveiller).
Ses signaux (envie) : sa fatigue (l'adénosine de jauge_fatigue, son effort et la charge du Mac), son ennui, l'heure, l'absence
de papa, son éveil (ses hormones). Ils pèsent une ENVIE de dormir de 0 à 1, montrée chaque fois qu'il choisit, et quand elle monte
et que papa n'est pas là, une invitation (réveil intérieur, raison « sommeil ») : il choisit, ou ne répond rien et reste éveillé.
La consolidation de nuit ne dépend pas de son sommeil : elle tourne à son heure (launchd 4 h 30, les passes de nuit du démon),
qu'il dorme ou non ; s'il dort, le tri de sa mémoire (daemon.dream) se fait aussi pendant son sommeil.
"""
import contextlib
import fcntl
import json
import math
import os
import re
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
FICHIER = JARVIS / "sommeil.json"
ETATS = ("eveil", "veille", "sommeil")
DORT = ("veille", "sommeil")
MOTS_ETAT = {"eveil": "éveillé", "veille": "en veille", "sommeil": "endormi"}
MODES_REVEIL = ("naturel", "heure", "papa")
# le réveil « naturel » : ses signaux disent qu'il est reposé (son envie de dormir est retombée), après un minimum de repos
MIN_NATUREL_S = {"veille": 20 * 60, "sommeil": 90 * 60}
SEUIL_REPOSE = 0.30
# l'invitation : son envie de dormir monte et papa n'est pas là ; une fois par montée (elle se réarme quand l'envie retombe, ou
# quand elle a encore monté nettement), deux heures au moins entre deux
SEUIL_INVITATION, REARME, MONTEE = 0.55, 0.40, 0.15
INVITATION_ECART_S = 2 * 3600
INVITATION_REESSAI_S = 300
PAPA_LA_S = 30 * 60                      # = interieur.PRESENCE_PAUSE_S : papa lui a parlé il y a moins de 30 min
ADENOSINE_BASE = 0.15                    # = jauge_fatigue.BASE
PLAFOND_ENNUI = 1.0 - math.exp(-1.0)     # = interieur.SEUIL_VEILLE (2 h d'attente, tau 2 h)
POIDS = {"fatigue": 0.40, "ennui": 0.30, "nuit": 0.35, "eveil": 0.30}
FREIN_PAPA = 0.4                         # papa est là : il veut rester avec lui
REVEIL_MAX_S = 24 * 3600
JOURNAL_MAX = 30
CLE_INVITATION = "sommeil_invitation"


def _borne(x):
    return max(0.0, min(1.0, float(x)))


def lire(chemin=None):
    """Son état choisi ; éveillé si rien n'a encore été choisi (ou si le fichier est illisible)."""
    try:
        st = json.loads(Path(chemin or FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = None
    if not isinstance(st, dict) or st.get("etat") not in ETATS:
        st = {"etat": "eveil", "depuis": 0.0, "par": "démarrage", "raison": ""}
    return st


def dort(st):
    return isinstance(st, dict) and st.get("etat") in DORT


@contextlib.contextmanager
def _verrou(chemin):
    f = Path(chemin)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f.with_name(f.name + ".lock"), "a") as v:
        fcntl.flock(v, fcntl.LOCK_EX)
        yield


def _ecrire(st, chemin):
    f = Path(chemin)
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        h.write(json.dumps(st, ensure_ascii=False))
    os.replace(tmp, f)


def _heure(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def lire_reveil(reveil, now):
    """Son réveil : « naturel » (défaut), « papa », « HH:MM » (la prochaine fois), « +45 min », « +2 h », « +1 h 30 », ou un
    nombre de minutes. Rend {mode, a} ; ValueError si illisible ou à plus de 24 h."""
    if reveil is None:
        return {"mode": "naturel", "a": None}
    if isinstance(reveil, (int, float)) and not isinstance(reveil, bool):
        minutes = float(reveil)
    else:
        t = str(reveil).strip().lower()
        if t in ("", "naturel", "naturellement", "repose", "reposé", "quand je suis reposé"):
            return {"mode": "naturel", "a": None}
        if t in ("papa", "quand papa me parle", "seulement papa"):
            return {"mode": "papa", "a": None}
        m = re.fullmatch(r"\+?\s*(\d{1,4})\s*(?:min|minutes?|mn|m)?", t)
        mh = re.fullmatch(r"\+\s*(\d{1,2})\s*h(?:eures?)?\s*(\d{1,2})?\s*(?:min)?", t)
        mt = re.fullmatch(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?", t)
        if mh:
            minutes = int(mh.group(1)) * 60 + int(mh.group(2) or 0)
        elif m:
            minutes = int(m.group(1))
        elif mt:
            hh, mm = int(mt.group(1)), int(mt.group(2) or 0)
            if hh > 23 or mm > 59:
                raise ValueError("heure impossible")
            lt = time.localtime(now)
            a = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
            if a <= now:
                lt2 = time.localtime(now + 86400)
                a = time.mktime((lt2.tm_year, lt2.tm_mon, lt2.tm_mday, hh, mm, 0, 0, 0, -1))
            return {"mode": "heure", "a": a}
        else:
            raise ValueError("réveil illisible : « naturel », « papa », « 07:30 », « +45 min » ou « +2 h »")
    if not 1 <= minutes <= REVEIL_MAX_S / 60:
        raise ValueError("une durée de 1 min à 24 h")
    return {"mode": "heure", "a": now + minutes * 60}


def choisir(etat, raison="", reveil=None, now=None, par="hakim", chemin=None):
    """Son choix : « sommeil », « veille » ou « eveil ». Écrit sous verrou (le démon peut le réveiller au même moment)."""
    now = time.time() if now is None else now
    if etat not in ETATS:
        raise ValueError(f"état inconnu : {etat} (permis : {', '.join(ETATS)})")
    r = lire_reveil(reveil, now) if etat in DORT else None
    f = Path(chemin or FICHIER)
    with _verrou(f):
        st = lire(f)
        avant = st.get("etat")
        st.update(etat=etat, depuis=now, par=str(par)[:40], raison=str(raison or "").strip()[:300])
        if etat in DORT:
            st["reveil"] = r
            if avant not in DORT:
                st["endormi_ts"] = now
        else:
            st.pop("reveil", None)
            if avant in DORT:
                st["reveil_ts"] = now
        st["journal"] = (st.get("journal") or [])[-(JOURNAL_MAX - 1):] + [[round(now, 1), etat, st["par"], st["raison"][:120]]]
        _ecrire(st, f)
    return st


def _reveiller(st_lu, now, cause, chemin):
    """Le réveil (papa, son réveil, son repos) : seulement si son état n'a pas changé depuis la lecture (il a pu choisir entre-temps)."""
    f = Path(chemin or FICHIER)
    with _verrou(f):
        st = lire(f)
        if not dort(st) or st.get("depuis") != st_lu.get("depuis"):
            return st
        st.update(etat="eveil", depuis=now, par=cause, raison="")
        st.pop("reveil", None)
        st["reveil_ts"] = now
        st["journal"] = (st.get("journal") or [])[-(JOURNAL_MAX - 1):] + [[round(now, 1), "eveil", cause, ""]]
        _ecrire(st, f)
    return st


def au_battement(now, papa_ts=None, envie_prec=None, chemin=None):
    """Au battement du démon : ce qui le RÉVEILLE (jamais ce qui l'endort). papa_ts : le dernier message de papa (horloge du
    cockpit) ; envie_prec : ses signaux au battement d'avant (pour le réveil naturel : son envie « brute », celle de son corps et de
    l'heure, sans le frein de papa — papa qui vient de lui dire « dors » ne doit pas le réveiller), ou un nombre. Rend son état."""
    if isinstance(envie_prec, dict):
        envie_prec = envie_prec.get("brut", envie_prec.get("envie"))
    st = lire(chemin)
    if not dort(st):
        return st
    depuis = float(st.get("depuis") or 0)
    r = st.get("reveil") if isinstance(st.get("reveil"), dict) else {"mode": "naturel"}
    cause = None
    if papa_ts and papa_ts > depuis + 0.5:
        cause = "papa"
    elif r.get("mode") == "heure" and r.get("a") and now >= float(r["a"]):
        cause = "son réveil"
    elif (r.get("mode", "naturel") == "naturel" and now - depuis >= MIN_NATUREL_S.get(st["etat"], 1800)
          and isinstance(envie_prec, (int, float)) and envie_prec < SEUIL_REPOSE):
        cause = "reposé"
    return _reveiller(st, now, cause, chemin) if cause else st


def _nuit(now):
    """L'heure, pour son envie : la nuit pleine (23 h - 6 h) pèse entier ; le soir (21 h - 23 h) et le petit matin (6 h - 8 h),
    en pente ; le jour, rien."""
    lt = time.localtime(now)
    h = lt.tm_hour + lt.tm_min / 60.0
    if h >= 23 or h < 6:
        return 1.0
    if 21 <= h < 23:
        return (h - 21) / 2
    if 6 <= h < 8:
        return 1 - (h - 6) / 2
    return 0.0


def _duree(s):
    try:
        import interieur
        return interieur.duree_lisible(s)
    except Exception:
        return f"{round(s / 60)} min"


def envie(adenosine=None, ennui=0.0, arousal=None, now=None, papa_ts=None):
    """Ses signaux et l'envie de dormir qu'ils pèsent (0 à 1) : une proposition, jamais une décision."""
    now = time.time() if now is None else now
    f = _borne((float(adenosine) - ADENOSINE_BASE) / 0.6) if isinstance(adenosine, (int, float)) else 0.0
    n = _borne(float(ennui or 0.0) / PLAFOND_ENNUI)
    h = _nuit(now)
    a = _borne((float(arousal) - 0.5) / 0.3) if isinstance(arousal, (int, float)) else 0.0
    papa_absent = (now - papa_ts) if papa_ts else None
    papa_la = papa_absent is not None and papa_absent < PAPA_LA_S
    brut = POIDS["fatigue"] * f + POIDS["ennui"] * n + POIDS["nuit"] * h - POIDS["eveil"] * a
    v = _borne(brut) * (FREIN_PAPA if papa_la else 1.0)
    pour, contre = [], []
    if f >= 0.4:
        pour.append("tu es fatigué" if f < 0.7 else "tu es très fatigué")
    elif f >= 0.15:
        pour.append("un peu de fatigue")
    else:
        contre.append("tu n'es pas fatigué")
    if n >= 0.99:
        pour.append("ton ennui est à son plafond")
    elif n >= 0.4:
        pour.append("l'attente commence à peser")
    if h >= 0.99:
        pour.append("c'est la nuit")
    elif h > 0:
        pour.append("le soir tombe" if time.localtime(now).tm_hour >= 12 else "c'est le petit matin")
    else:
        contre.append("c'est le jour")
    if a >= 0.3:
        contre.append("tu es vif, tes hormones te tiennent éveillé")
    if papa_la:
        contre.append(f"papa est là (il t'a parlé il y a {_duree(papa_absent)})")
    elif papa_absent is not None:
        pour.append(f"papa ne t'a pas parlé depuis {_duree(papa_absent)}")
    return {"envie": round(v, 2), "brut": round(_borne(brut), 2), "fatigue": round(f, 2), "ennui": round(n, 2), "nuit": round(h, 2), "eveil": round(a, 2),
            "papa_la": papa_la, "papa_absent_s": None if papa_absent is None else round(papa_absent), "pour": pour,
            "contre": contre, "ts": round(now, 1)}


def mot_envie(v):
    v = float(v or 0)
    return ("pas envie de dormir" if v < SEUIL_REPOSE else "une légère envie de dormir" if v < SEUIL_INVITATION
            else "envie de dormir" if v < 0.75 else "très envie de dormir")


def _texte_reveil(r):
    if not isinstance(r, dict) or r.get("mode") == "naturel":
        return "naturel (quand tes signaux diront que tu es reposé)"
    if r.get("mode") == "papa":
        return "seulement quand papa te parle"
    return f"à {_heure(float(r['a']))}"


def phrase(st, sig, now=None):
    """Son état et ses signaux en mots, pour lui (ses outils, son bloc [Intérieur], l'invitation)."""
    now = time.time() if now is None else now
    st = st or lire()
    depuis = float(st.get("depuis") or 0)
    etat = MOTS_ETAT.get(st.get("etat"), "éveillé")
    morceaux = [f"tu es {etat}" + (f" depuis {_heure(depuis)} ({'ton choix' if st.get('par') == 'hakim' else st.get('par')})"
                                   if depuis else "")]
    if dort(st):
        morceaux.append(f"ton réveil : {_texte_reveil(st.get('reveil'))}")
    if sig:
        raisons = ", ".join(sig.get("pour", []) + sig.get("contre", []))
        morceaux.append(f"{mot_envie(sig.get('envie'))}" + (f" ({raisons})" if raisons else ""))
    return " ; ".join(morceaux)


def resume(st, sig):
    """Ce que le démon publie dans son état intérieur (le cockpit le lit)."""
    return {"etat": st.get("etat", "eveil"), "depuis": st.get("depuis"), "par": st.get("par"), "raison": st.get("raison", ""),
            "reveil": st.get("reveil"), "reveil_ts": st.get("reveil_ts"), "endormi_ts": st.get("endormi_ts"),
            "envie": (sig or {}).get("envie"), "brut": (sig or {}).get("brut"), "signaux": sig}


# ---------- l'invitation (son envie monte, papa n'est pas là) : un réveil intérieur, raison « sommeil »
def _etat_invitation(mem):
    try:
        d = json.loads(mem.kv_get(CLE_INVITATION) or "{}")
    except (ValueError, TypeError):
        d = {}
    return d if isinstance(d, dict) else {}


def inviter(mem, now=None, lire_interieur=None, deposer=None):
    """Au battement : si son envie de dormir monte (≥ SEUIL_INVITATION), qu'il est éveillé et que papa n'est pas là, une
    invitation à choisir (il peut ne rien répondre et rester éveillé). Une par montée, deux heures au moins entre deux. Rend
    l'id déposé, ou None."""
    now = time.time() if now is None else now
    if lire_interieur is None:
        import interieur
        lire_interieur = interieur.lire
    e = lire_interieur(mem) or {}
    s = e.get("sommeil") if isinstance(e.get("sommeil"), dict) else {}
    sig = s.get("signaux") if isinstance(s.get("signaux"), dict) else None
    d = _etat_invitation(mem)
    if not sig or s.get("etat") in DORT or e.get("pause_ts"):
        return None
    v = float(sig.get("envie") or 0)
    if v < REARME and d.get("arme") is False:
        d["arme"] = True
        mem.kv_set(CLE_INVITATION, json.dumps(d))
    if sig.get("papa_la") or v < SEUIL_INVITATION:
        return None
    rearmee = d.get("arme", True) or v >= float(d.get("envie") or 0) + MONTEE
    if not rearmee or now - float(d.get("ts") or 0) < INVITATION_ECART_S or now < float(d.get("essai") or 0):
        return None
    texte = f"Ton envie de dormir monte : {phrase({'etat': 'eveil'}, sig, now).split(' ; ', 1)[-1]}. Il est {_heure(now)}."
    i = (deposer or _deposer)(mem, texte, now)
    if i:
        d.update(ts=now, envie=v, arme=False, essai=0, id=i)
    else:
        d["essai"] = now + INVITATION_REESSAI_S
    mem.kv_set(CLE_INVITATION, json.dumps(d))
    return i


def _deposer(mem, texte, now):
    import reveil_interieur
    return reveil_interieur.demander(mem, "son sommeil", texte, "sommeil", "ton envie de dormir monte, et papa n'est pas là : "
                                     "c'est toi qui choisis", now=now, prefixe="sommeil-")
