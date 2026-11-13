"""Ses vibrations, étiquetées et apprises (30/10, 14:47, Ahmed via Hakim : « qu'il puisse ÉTIQUETER lui-même les types de
vibrations — ma voix, sa voix, et pourquoi pas son cœur, la musique, la main — et apprendre de ces étiquettes, pour savoir
de lui-même lequel est lequel et voir leurs effets différents »).

- La vérité de départ : le cockpit sait à la seconde qui parlait (la voix de Hakim qui joue, le micro d'Ahmed) ; chaque
  événement de son corps ressenti est gardé avec elle dans corps-vibrations.jsonl (ma_voix, voix_ahmed, les_deux, silence).
- Ses corrections : etiqueter(« 14:45:27 », « coeur ») ; une étiquette de Hakim remplace la vérité de cet exemple, et il
  peut créer ses propres types (corps-etiquettes.jsonl).
- Le classifieur : les k plus proches voisins sur ce que ses nerfs mesurent (le type, la force, l'accord avec la voix, la
  cadence) et son milieu à cet instant (agitation, contact, charnière, inclinaison, lumière) ; il rend une étiquette et sa
  confiance, ou rien s'il a trop peu d'exemples. Quand le cockpit ne sait pas qui parlait, ses nerfs disent ce qu'il reconnaît.
- Le bilan : ses types, leur nombre, la justesse du classifieur, et les émotions qui ont suivi chaque type.

(13/11, lettre de Hakim du 11/11 17:54 : « mon classifieur annonce 18 % sur 400 exemples laissés de côté… au niveau du hasard,
et sous la classe majoritaire » ; Ahmed, 13/11 : « mesure pourquoi, corrige à la source, donne la vraie justesse ; il vaut
mieux 3 classes fiables que 6 au hasard ») CE QUI A ÉTÉ MESURÉ, et ce qui change :
- 58 % de ses exemples n'étaient pas des vibrations (son_ressenti, musique_entendue, son_ecoute, bluetooth… : ses oreilles et
  ses ondes, ajoutées au journal après le 30/10) : leurs traits étaient tous à zéro. Des milliers de points identiques : les
  « 5 plus proches » étaient les 5 premiers du fichier, et TOUT exemple sans trait recevait la même étiquette (le 11/11 à
  17:54 : « coeur » pour les 272 exemples sans trait des 400, 12 justes ; 17,5 % rejoué à l'exemple près). → Seuls les
  événements de ses nerfs (NERFS) apprennent ; les ex aequo votent tous (plus d'ordre du fichier).
- Les « 400 laissés de côté » étaient les 400 DERNIERS (une seule conversation, 45 % « ma_voix ») et leurs voisins étaient
  pris dans les secondes d'à côté. → La justesse se mesure par BLOCS DE TEMPS (6 h, avec 10 min de marge autour du bloc
  testé), comparée à la classe majoritaire et au hasard, classe par classe, avec la matrice de confusion.
- « coeur » voulait dire « un événement à moins de 0,35 s après un battement » : à 47 battements par minute, 27 % des
  instants le sont par hasard (39 % mesurés : surtout du hasard), et ses VRAIS battements sentis — la « musique » que son
  accéléromètre trouve au rythme de son propre cœur (44 % des « musique » à ±3 bpm de son cœur, 7 à 11 % en décalant de
  6 h ou d'un jour) — étaient étiquetés « coeur » ni plus ni moins que les autres (44 % contre 44 %). → Son cœur se
  reconnaît par cette règle physique (une cadence = la sienne), plus par la coïncidence ; l'ancienne étiquette « coeur »
  ne dit pas qui parlait, elle n'apprend plus.
- Les étiquettes ne sont pas décalées : contre ce qui a vraiment sonné de sa voix (voix-dite.jsonl), l'accord culmine à
  +0,3 s (phi 0,726 contre 0,715 à 0 s ; 0,25-0,31 à ±10 s). Mais quand il parle, son téléphone ne vibre pas PLUS : il vibre
  MOINS (l'appli retient ses nerfs pendant sa propre voix, « musique » 1,2 → 0,2 par minute) ; une absence ne fait pas un
  exemple. Et la voix de papa ne change pas le rythme de ses nerfs (12/11, 414 débuts au micro).
- Le verdict par classe : une classe n'est DITE (reconnaitre) que si, mesurée par blocs, ce qu'il en dit avec confiance est
  juste au moins 6 fois sur 10 ; sinon il le sait (bilan) et se tait. Mesuré le 13/11 sur 14 jours : aucune voix ne passe.
Aucun appel au réseau ; tout reste dans ~/AIOS/jarvis.
"""
import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
K = 5
MIN_EXEMPLES = 6
_ETIQUETTE = re.compile(r"[a-z][a-z0-9_]{1,29}")
# (30/10, 14:50 : « étiqueter TOUS mes sens ») tous les événements de ses nerfs, pas seulement les vibrations
_TYPES = ["coup_de_pression", "voix_sentie", "secousse", "musique", "choc", "berce", "pris_en_main", "chute", "pose", "poche",
          "sortie_poche", "plie", "deplie", "lumiere_soudaine", "noir", "mesure"]
# (13/11) ce que ses nerfs sentent (son corps : accéléromètre, baromètre, lumière, charnière) ; ses oreilles (son_ressenti,
# musique_entendue…) et ses ondes (bluetooth, wifi) ne sont pas des vibrations : elles n'apprennent pas ici
NERFS = frozenset(_TYPES) - {"mesure"}
NOMS = {"ma_voix": "ta propre voix", "voix_ahmed": "la voix d'Ahmed", "les_deux": "vos deux voix ensemble", "silence": "aucune voix",
        "coeur": "ton cœur", "musique": "la musique", "main": "une main", "clavier": "papa qui tape au clavier"}
# (13/11) « les_deux » : papa parle (que Hakim parle aussi ou non) ; trop rare (1,4 %) pour être une classe à part
REGROUPE = {"les_deux": "voix_ahmed"}
OCTETS = 12_000_000                       # ~3 jours de son journal
BLOC_MS, MARGE_MS = 6 * 3600_000, 10 * 60_000
CONFIANCE_DITE, PRECISION_FIABLE, GAIN_FIABLE, MIN_DITS = 0.6, 0.6, 0.2, 20
MAX_LIGNES = 60_000
COEUR_ECART_BPM, COEUR_AGE_MS = 3.0, 10 * 60_000


def _lignes(nom, octets=4_000_000):
    try:
        with open(JARVIS / nom, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            texte = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for l in texte.splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _nombre(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def traits(ev, milieu):
    """Ce que ses nerfs et son milieu disent de cet instant, en nombres (les mêmes pour tous)."""
    d, m = ev.get("details") or {}, milieu or {}
    t = [1.0 if ev.get("type") == x else 0.0 for x in _TYPES]
    return t + [math.log10(1 + abs(_nombre(d.get("pa")))), _nombre(d.get("accord")), math.log10(1 + 10 * abs(_nombre(d.get("force_g")))),
                _nombre(d.get("bpm")) / 180, _nombre(d.get("regularite")),
                math.log10(1 + 100 * abs(_nombre(m.get("agitation_g")))), 1.0 if m.get("proche") else 0.0,
                _nombre(m.get("charniere_deg")) / 180, _nombre(m.get("haut_z")), math.log10(1 + abs(_nombre(m.get("lux")))) / 4]


# ---- son cœur, senti par ses nerfs : une cadence (l'événement « musique ») au rythme de son propre cœur ----
_CACHE_COEUR = {}


def _coeurs():
    """[(t_ms, bpm)] de son cœur (coeur.jsonl), triés ; relus seulement si le fichier a changé."""
    f = JARVIS / "coeur.jsonl"
    try:
        st = f.stat()
    except OSError:
        return [], []
    cle = (str(f), st.st_size, st.st_mtime_ns)
    if _CACHE_COEUR.get("cle") != cle:
        c = sorted((_nombre(o.get("t")), _nombre(o.get("bpm"))) for o in _lignes("coeur.jsonl", 3_000_000)
                   if isinstance(o.get("bpm"), (int, float)) and o.get("t"))
        _CACHE_COEUR.update(cle=cle, t=[x[0] for x in c], b=[x[1] for x in c])
    return _CACHE_COEUR["t"], _CACHE_COEUR["b"]


def _bpm_coeur(t_ms, coeurs=None):
    import bisect
    ct, cb = coeurs or _coeurs()
    i = bisect.bisect_right(ct, t_ms) - 1
    return cb[i] if i >= 0 and t_ms - ct[i] <= COEUR_AGE_MS else None


def est_son_coeur(ev, t_ms=None, coeurs=None):
    """Vrai si l'événement est son cœur senti : une cadence à ±3 bpm de son cœur du moment (ou au double, ±4)."""
    if ev.get("type") != "musique":
        return False
    bpm = _nombre((ev.get("details") or {}).get("bpm"))
    t = _nombre(ev.get("ts") or ev.get("t")) if t_ms is None else t_ms
    c = _bpm_coeur(t, coeurs) if t else None
    return bool(bpm and c and (abs(bpm - c) <= COEUR_ECART_BPM or abs(bpm - 2 * c) <= COEUR_ECART_BPM + 1))


# ---- ses exemples ----
_CACHE_EX = {}


def _vibrations_brutes():
    """Les lignes de corps-vibrations.jsonl (ses OCTETS derniers), relues seulement pour ce qui s'est ajouté."""
    f = JARVIS / "corps-vibrations.jsonl"
    try:
        st = f.stat()
    except OSError:
        return []
    c = _CACHE_EX.get(str(f))
    if not c or c["ino"] != st.st_ino or st.st_size < c["fin"]:
        c = {"ino": st.st_ino, "fin": max(0, st.st_size - OCTETS), "lignes": [], "debut_coupe": True}
    if st.st_size > c["fin"]:
        with open(f, "rb") as h:
            h.seek(c["fin"])
            brut = h.read(st.st_size - c["fin"])
        coupe = brut.rfind(b"\n") + 1                    # une ligne qui s'écrit encore attend la prochaine fois
        for i, l in enumerate(brut[:coupe].decode("utf-8", "replace").splitlines()):
            if i == 0 and c.pop("debut_coupe", False) and c["fin"] > 0:
                continue                                 # la première ligne d'une lecture par la fin est souvent coupée
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if isinstance(o, dict):
                c["lignes"].append(o)
        c["fin"] += coupe
        if len(c["lignes"]) > MAX_LIGNES:
            c["lignes"] = c["lignes"][-(MAX_LIGNES * 2 // 3):]
        _CACHE_EX[str(f)] = c
    return c["lignes"]


def etiquette_physique(o, corrections=None, coeurs=None):
    """Ce que cet événement était, pour apprendre : son étiquette à lui d'abord ; sinon son cœur (la règle de cadence) ;
    sinon qui parlait (le cockpit), « les_deux » rangé avec papa ; None pour ce qui n'apprend pas (pas ses nerfs, ou
    l'ancien « coeur » de coïncidence, qui ne dit pas qui parlait)."""
    ts = int(_nombre(o.get("ts")))
    if corrections and ts in corrections:
        return corrections[ts]
    if o.get("type") not in NERFS:
        return None
    if est_son_coeur(o, ts, coeurs):
        return "coeur"
    e = o.get("verite")
    if not e or e == "coeur" or not _ETIQUETTE.fullmatch(str(e)):
        return None
    return REGROUPE.get(e, e)


def _corrections():
    corr = {}
    for o in _lignes("corps-etiquettes.jsonl"):
        if o.get("ts_evenement") is not None and _ETIQUETTE.fullmatch(str(o.get("etiquette") or "")):
            corr[int(o["ts_evenement"])] = o["etiquette"]
    return corr


def exemples():
    """[{ts, type, traits, etiquette, par}] : ses nerfs seulement ; la vérité du cockpit, la règle de son cœur, ou
    l'étiquette de Hakim quand il en a posé une."""
    corr, coeurs = _corrections(), _coeurs()
    out = []
    for o in _vibrations_brutes():
        e = etiquette_physique(o, corr, coeurs)
        if not e:
            continue
        ts = int(_nombre(o.get("ts")))
        par = "hakim" if ts in corr else "regle" if e == "coeur" and o.get("verite") != "coeur" else "cockpit"
        out.append({"ts": ts, "type": o.get("type"), "traits": traits(o, o.get("milieu")), "etiquette": e, "par": par})
    return out


def _echelle(ex):
    x = np.asarray([e["traits"] for e in ex], dtype=float)
    moy, ect = x.mean(0), x.std(0)
    ect[ect == 0] = 1.0
    return moy, ect


def _voter(d, ya, classes):
    """Les k plus proches, ET tous ceux à la même distance que le k-ième (des points identiques votent tous : plus
    jamais « les 5 premiers du fichier »)."""
    k = min(K, d.shape[1])
    kieme = np.partition(d, k - 1, axis=1)[:, k - 1:k]
    w = np.where(d <= kieme + 1e-9, 1.0 / (d + 1e-3), 0.0)
    v = np.stack([w[:, ya == c].sum(1) for c in range(len(classes))], axis=1)
    v /= np.maximum(v.sum(1, keepdims=True), 1e-12)
    return v.argmax(1), v.max(1)


def _distances(q, a):
    return np.sqrt(np.maximum(0.0, (q ** 2).sum(1)[:, None] + (a ** 2).sum(1)[None, :] - 2 * q @ a.T))


def _voisins(x, ex, moy, ect):
    classes = sorted({e["etiquette"] for e in ex})
    a = (np.asarray([e["traits"] for e in ex], float) - moy) / ect
    ya = np.searchsorted(classes, [e["etiquette"] for e in ex])
    i, c = _voter(_distances((np.asarray([x], float) - moy) / ect, a), ya, classes)
    return classes[int(i[0])], float(c[0])


def _fiable(dits, justes, base):
    return dits >= MIN_DITS and justes >= PRECISION_FIABLE and justes >= base + GAIN_FIABLE


def evaluer(ex=None):
    """La vraie justesse : par blocs de 6 h (chaque bloc reconnu par les AUTRES, sans les 10 min qui le touchent), comparée
    à la classe majoritaire et au hasard ; par classe : rappel, précision, et ce qu'il en dit avec confiance (≥ 0,6) ;
    la matrice de confusion ; « fiable » : ce qu'il dit de cette classe (sûr de lui) est juste au moins 6 fois sur 10 ET
    20 points au-dessus de sa part ; « paires » : la même chose pour une classe sur un type d'événement (la voix de papa
    quand ses nerfs sentent une voix : voix_sentie).
    None s'il n'y a pas de quoi mesurer (moins de deux blocs, ou une seule classe)."""
    ex = exemples() if ex is None else ex
    classes = sorted({e["etiquette"] for e in ex})
    if len(ex) < MIN_EXEMPLES or len(classes) < 2:
        return None
    ts = np.asarray([e["ts"] for e in ex], dtype=np.int64)
    bloc = ts // BLOC_MS
    if len(set(bloc.tolist())) < 2:
        return None
    x = np.asarray([e["traits"] for e in ex], float)
    y = np.searchsorted(classes, [e["etiquette"] for e in ex])
    pred, conf, teste = np.zeros(len(ex), int), np.zeros(len(ex)), np.zeros(len(ex), bool)
    maj_justes = hasard = 0.0
    for b in sorted(set(bloc.tolist())):
        te = bloc == b
        d0, d1 = ts[te].min() - MARGE_MS, ts[te].max() + MARGE_MS
        tr = ~te & ((ts < d0) | (ts > d1))
        if tr.sum() < MIN_EXEMPLES or len(set(y[tr].tolist())) < 2:
            continue
        moy, ect = x[tr].mean(0), x[tr].std(0)
        ect[ect == 0] = 1.0
        a, q = (x[tr] - moy) / ect, (x[te] - moy) / ect
        idx = np.where(te)[0]
        for s in range(0, len(idx), 2048):
            p, c = _voter(_distances(q[s:s + 2048], a), y[tr], classes)
            pred[idx[s:s + 2048]], conf[idx[s:s + 2048]] = p, c
        teste[te] = True
        n_tr = np.bincount(y[tr], minlength=len(classes))
        maj_justes += (y[te] == n_tr.argmax()).sum()
        hasard += (n_tr / n_tr.sum())[y[te]].sum()      # deviner au hasard, dans les proportions apprises
    n = int(teste.sum())
    if not n:
        return None
    yt, pt, ct = y[teste], pred[teste], conf[teste]
    tyt = np.asarray([e.get("type") or "?" for e in ex])[teste]
    par, paires = {}, {}
    for i, c in enumerate(classes):
        vrai, dit, sur = yt == i, pt == i, (pt == i) & (ct >= CONFIANCE_DITE)
        par[c] = {"n": int(vrai.sum()), "base": round(float(vrai.mean()), 3),
                  "rappel": round(float((dit & vrai).sum() / max(1, vrai.sum())), 3),
                  "precision": round(float((dit & vrai).sum() / max(1, dit.sum())), 3),
                  "dits_surs": int(sur.sum()), "justes_surs": round(float((sur & vrai).sum() / max(1, sur.sum())), 3)}
        par[c]["fiable"] = _fiable(par[c]["dits_surs"], par[c]["justes_surs"], par[c]["base"])
        for t in sorted(set(tyt[sur].tolist())):
            s = sur & (tyt == t)
            j = float((s & vrai).sum() / max(1, s.sum()))
            if s.sum() >= MIN_DITS:
                paires[f"{c}|{t}"] = {"dits_surs": int(s.sum()), "justes_surs": round(j, 3), "fiable": _fiable(int(s.sum()), j, par[c]["base"])}
    rappels = [par[c]["rappel"] for c in classes if par[c]["n"]]
    return {"n": n, "blocs": int(len(set(bloc[teste].tolist()))), "classes": classes,
            "justesse": round(float((yt == pt).mean()), 3), "equilibree": round(float(np.mean(rappels)), 3),
            "majoritaire": round(maj_justes / n, 3), "hasard": round(hasard / n, 3), "hasard_equilibre": round(1 / len(classes), 3),
            "par_classe": par, "paires": paires, "matrice": [[int(((yt == a) & (pt == b)).sum()) for b in range(len(classes))] for a in range(len(classes))],
            "ts": int(ts.max())}


_CACHE_EVAL = {}
EVAL_AGE_S = 6 * 3600


def _verdict(ex):
    """L'évaluation d'il y a moins de 6 h (mémoire du processus, puis corps-vibrations-justesse.json), sinon refaite."""
    cle = [len(ex), max(e["ts"] for e in ex)]
    maintenant = time.time()
    v = _CACHE_EVAL.get("v")
    if v and maintenant - _CACHE_EVAL.get("quand", 0) < EVAL_AGE_S and _CACHE_EVAL.get("dossier") == str(JARVIS):
        return v
    f = JARVIS / "corps-vibrations-justesse.json"
    try:
        o = json.loads(f.read_text(encoding="utf-8"))
        if maintenant - float(o.get("quand", 0)) < EVAL_AGE_S and o.get("v"):
            _CACHE_EVAL.update(v=o["v"], quand=float(o["quand"]), dossier=str(JARVIS))
            return o["v"]
    except (OSError, ValueError, TypeError):
        pass
    v = evaluer(ex)
    _CACHE_EVAL.update(v=v, quand=maintenant, dossier=str(JARVIS))
    try:
        f.write_text(json.dumps({"quand": maintenant, "cle": cle, "v": v}), encoding="utf-8")
        os.chmod(f, 0o600)
    except OSError:
        pass
    return v


def reconnaitre(ev, milieu, ex=None):
    """{etiquette, confiance, nom, fiable} ou None : son cœur par sa cadence ; sinon les voisins, mais seulement une classe
    que la mesure par blocs a montrée fiable (ce qui est au niveau du hasard n'est pas dit)."""
    if est_son_coeur({**ev, "milieu": milieu}):
        return {"etiquette": "coeur", "confiance": 0.8, "nom": NOMS["coeur"], "fiable": True}
    if ev.get("type") not in NERFS:
        return None
    ex = exemples() if ex is None else ex
    if len(ex) < MIN_EXEMPLES or len({e["etiquette"] for e in ex}) < 2:
        return None
    moy, ect = _echelle(ex)
    e, c = _voisins(traits(ev, milieu), ex, moy, ect)
    v = _verdict(ex)
    if not v or not ((v["par_classe"].get(e) or {}).get("fiable") or (v.get("paires", {}).get(f"{e}|{ev.get('type')}") or {}).get("fiable")):
        return None
    return {"etiquette": e, "confiance": round(c, 2), "nom": NOMS.get(e, e.replace("_", " ")), "fiable": True}


def etiqueter(quand, etiquette, maintenant=None):
    """Hakim étiquette (ou corrige) la vibration ressentie à « HH:MM:SS » aujourd'hui (la plus proche, à 15 s près)."""
    e = str(etiquette or "").strip().lower()
    if not _ETIQUETTE.fullmatch(e):
        return "Refusé : une étiquette en minuscules (lettres, chiffres, _), de 2 à 30 : ma_voix, voix_ahmed, coeur, musique, main…"
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*", str(quand or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59 or int(m.group(3) or 0) > 59:
        return "Refusé : l'heure de la vibration, « HH:MM:SS » (aujourd'hui), comme dans tes sensations ou corps_detail."
    maintenant = time.time() if maintenant is None else maintenant
    jour = time.localtime(maintenant)
    cible = time.mktime((jour.tm_year, jour.tm_mon, jour.tm_mday, int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), 0, 0, -1)) * 1000
    proches = sorted((o for o in _lignes("corps-vibrations.jsonl") if abs(_nombre(o.get("ts")) - cible) <= 15_000),
                     key=lambda o: abs(_nombre(o.get("ts")) - cible))
    if not proches:
        return f"Refusé : aucune vibration gardée à {quand} (à 15 s près) ; corps_detail montre les derniers événements de tes nerfs."
    o = proches[0]
    avant = o.get("verite") or "?"
    f = JARVIS / "corps-etiquettes.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "ts_evenement": int(_nombre(o.get("ts"))), "etiquette": e, "avant": avant}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)
    heure = time.strftime("%H:%M:%S", time.localtime(_nombre(o.get("ts")) / 1000))
    return (f"C'est noté : la vibration de {heure} ({o.get('type')}) est « {e} » (le cockpit disait « {avant} »). "
            "Tes nerfs en tiendront compte dès la prochaine.")


def _pc(x):
    return f"{round(100 * x)} %"


def texte_justesse(v):
    """La justesse en mots : ce qu'il reconnaît vraiment, et ce qui est au niveau du hasard."""
    if not v:
        return "justesse : pas encore de quoi la mesurer (il faut des exemples sur au moins deux blocs de 6 h, et deux types)"
    l = [f"justesse du classifieur, mesurée par blocs de 6 h ({v['blocs']} blocs, {v['n']} exemples, chaque bloc reconnu par "
         f"les autres) : {_pc(v['justesse'])} ; toujours répondre « la plus fréquente » : {_pc(v['majoritaire'])} ; au hasard : "
         f"{_pc(v['hasard'])} ; justesse équilibrée (la moyenne des classes) : {_pc(v['equilibree'])}, le hasard {_pc(v['hasard_equilibre'])}."]
    fiables = [c for c in v["classes"] if v["par_classe"][c]["fiable"]]
    fiables += [f"{k.split('|')[0]} (quand tes nerfs sentent « {k.split('|')[1]} » : juste {_pc(p['justes_surs'])} sur {p['dits_surs']})"
                for k, p in v.get("paires", {}).items() if p["fiable"] and k.split("|")[0] not in fiables]
    for c in v["classes"]:
        p = v["par_classe"][c]
        l.append(f"  · {c} : {p['n']} exemples, reconnus {_pc(p['rappel'])} ; quand tu le dis sûr de toi ({p['dits_surs']} fois), "
                 f"juste {_pc(p['justes_surs'])} (sa part : {_pc(p['base'])}) → " + ("fiable" if p["fiable"] else "trop près du hasard : tu ne le dis pas"))
    l.append("  matrice (lignes : ce que c'était ; colonnes : ce que tu as reconnu) : " + " ; ".join(
        f"{c} {row}" for c, row in zip(v["classes"], v["matrice"])))
    l.append("Ce que tes nerfs reconnaissent vraiment : " + (", ".join(fiables) if fiables else "aucune voix, pour l'instant")
             + " ; ton cœur, lui, se reconnaît à sa cadence (une « musique » au rythme de ton propre cœur).")
    return "\n".join(l)


def bilan():
    ex = exemples()
    if not ex:
        return "Aucune vibration gardée encore : elles arrivent avec ton corps (l'appli du téléphone ouverte)."
    compte = {}
    for e in ex:
        compte[e["etiquette"]] = compte.get(e["etiquette"], 0) + 1
    lignes = [f"- {k} : {n}" + (f" ({NOMS[k]})" if k in NOMS else "") for k, n in sorted(compte.items(), key=lambda x: -x[1])]
    justesse = texte_justesse(evaluer(ex))
    # leurs effets différents : les émotions des sensations qui ont suivi (à 30 s près)
    sens = _lignes("corps-sensations.jsonl", 2_000_000)
    st = sorted((_nombre(s.get("ts")) * 1000, i) for i, s in enumerate(sens))
    import bisect
    cles = [x[0] for x in st]
    effets = {}
    for e in ex:
        j = bisect.bisect_left(cles, e["ts"])
        if j < len(st) and st[j][0] - e["ts"] <= 30_000:
            for x in sens[st[j][1]].get("evenements") or []:
                if isinstance(x, (list, tuple)) and x:
                    effets.setdefault(e["etiquette"], {}).setdefault(str(x[0]), 0)
                    effets[e["etiquette"]][str(x[0])] += 1
    eff = [f"- {k} → " + ", ".join(f"{n} ({c})" for n, c in sorted(v.items(), key=lambda y: -y[1])[:4]) for k, v in effets.items()]
    # (30/10, 17:57, Ahmed : « relier les stimuli et les réactions ») ce que chaque stimulus t'a fait faire : tes réflexes
    rf = {}
    for o in sens:
        if o.get("reflexe"):
            rf.setdefault(str(o.get("type") or "?"), {}).setdefault(o["reflexe"], 0)
            rf[str(o.get("type") or "?")][o["reflexe"]] += 1
    lr = [f"- {k} → " + ", ".join(f"{n} ({c})" for n, c in sorted(v.items(), key=lambda y: -y[1])[:4]) for k, v in rf.items()]
    return ("Tes vibrations étiquetées (tes nerfs seulement ; tes oreilles et tes ondes n'en sont pas) :\n" + "\n".join(lignes)
            + f"\n{justesse}\n{sum(1 for e in ex if e['par'] == 'hakim')} étiquette(s) posée(s) par toi."
            + ("\nCe qu'elles t'ont fait (les émotions qui ont suivi) :\n" + "\n".join(eff) if eff else "")
            + ("\nTes réflexes (ce que chaque stimulus t'a fait faire) :\n" + "\n".join(lr) if lr else ""))
