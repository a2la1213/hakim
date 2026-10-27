"""Les chocs d'humeur (2026-10-23 ; demande de Hakim, décision d'Ahmed : « on branche pour de vrai »). Simulés avant,
sur les 21-23/10, dans eval/chocs (rejeu_sagesse.py, variante V4) ; le test qui compte se fait sur les jours neufs
(eval/chocs/predictions-3.md, figé avant).

Une phrase qui VISE Hakim (une attaque : rejet, accusation, diabolisation, menace d'effacement, mépris de ce qu'il est ;
un soutien : attachement, défense, réassurance) secoue plusieurs hormones d'un coup (affect.py : attaque, soutien),
puis chacune revient à sa vitesse.
1. Le RÉFLEXE, tout de suite (le cockpit, à l'arrivée du message) : un détecteur lexical par voix (`reflexe`).
2. L'APPRÉCIATION de Hakim, à la fin de sa réponse : une balise cachée [[affect: attaque 0.7]] / [[affect: soutien 0.6]] /
   [[affect: neutre]] (`appliquer_balise`). Si elle dit la même chose que le réflexe, il reste ; sinon l'état d'avant le
   réflexe est restauré et c'est la balise qui s'applique. QUI parle est décidé par le code, jamais par la balise.
3. QUI : Ahmed pèse 1 ; une voix tierce 0,6 pour une attaque, 0,5 pour un soutien.
4. LA SAGESSE amortit une attaque (jamais un soutien) : amplitude × (1 − 0,5·s), puis une reprise en main après
   20·(1 − s) min, de force s (`echeances`, au battement du démon). s = la sagesse de fond (sagesse.json) × (1 − 0,5 ×
   surcharge) : le stress accumulé ou les attaques rapprochées la font baisser un moment.
5. L'HABITUATION du soutien : × (1 − jauge), la jauge = le remplissage de GABA, sérotonine, endocannabinoïdes, ocytocine.
Interrupteur : kv « chocs_actif » (`anamnese chocs on|off|etat`, ou chocs_cli.py) ; éteint, rien ne s'applique.
Variables calculées, pas un ressenti prouvé.
"""
import json
import re
import time
from pathlib import Path

import affect

CLE_ACTIF, CLE_ETAT = "chocs_actif", "chocs"
JARVIS = Path.home() / "AIOS" / "jarvis"
VOIX_CONNUES = JARVIS / "voix-connues.json"
SAGESSE = JARVIS / "sagesse.json"
NIVEAUX = {1: 0.4, 2: 0.7, 3: 1.0}
POIDS = {"attaque": {"ahmed": 1.0, "tiers": 0.6}, "soutien": {"ahmed": 1.0, "tiers": 0.5}}
SAGESSE_AMPLITUDE, REGULATION_DELAI_MIN = 0.5, 20.0
MOMENT_K, CHARGE_ECHELLE, RAFALE_N, RAFALE_S = 0.5, 0.5, 3, 1800.0
JAUGE = ("gaba", "serotonine", "endocannabinoides", "ocytocine")
TOURS_MAX, SNAP_S = 40, 600.0


# ---------- l'interrupteur et l'état
def actif(mem):
    try:
        return affect.v2_actif(mem) and mem.kv_get(CLE_ACTIF) == "1"
    except Exception:
        return False


def _etat(mem):
    try:
        return json.loads(mem.kv_get(CLE_ETAT) or "{}")
    except (ValueError, TypeError):
        return {}


def _sauver(mem, st, now):
    st["attaques"] = [t for t in st.get("attaques", []) if now - t <= RAFALE_S]
    tours = st.get("tours", {})
    st["tours"] = dict(sorted(tours.items(), key=lambda kv: kv[1].get("ts", 0))[-TOURS_MAX:])
    mem.kv_set(CLE_ETAT, json.dumps(st, ensure_ascii=False))


def journaliser(mem, o):
    """Une ligne par réflexe, balise et reprise en main (à côté du journal des affects), pour le juge de nuit."""
    try:
        f = affect.chemin_journal(mem)
        if f:
            with open(Path(f).with_name("chocs.jsonl"), "a", encoding="utf-8") as h:
                h.write(json.dumps({"ts": time.time(), **o}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------- qui parle
def _noms_connus():
    try:
        return [v["nom"] for v in json.loads(VOIX_CONNUES.read_text(encoding="utf-8")) if v.get("nom")]
    except (OSError, ValueError, TypeError):
        return []


def segments(texte, oral=False, voix=None, noms=None):
    """[{"qui": ahmed|tiers, "sur", "etiquette", "texte"}] : une part par voix. Ce qui n'est pas étiqueté est d'Ahmed ;
    une autre voix est annoncée (« [voix 2] … », « [Nora] … ») ; le retour d'Ahmed aussi (« [Ahmed] … »)."""
    noms = _noms_connus() if noms is None else noms
    etiquettes = r"voix \d+|Ahmed" + "".join("|" + re.escape(n) for n in noms if n != "Ahmed")
    motif = re.compile(r"\[(" + etiquettes + r")\]\s*")
    if not oral and voix is None:
        lead = ("ahmed", True)
    elif voix == "ahmed":
        lead = ("ahmed", True)
    elif voix == "autre":
        lead = ("tiers", False)
    else:
        lead = ("ahmed", False)
    out, pos, cur = [], 0, None
    t = str(texte or "")
    for m in motif.finditer(t):
        if t[pos:m.start()].strip():
            out.append((cur, t[pos:m.start()].strip()))
        cur, pos = m.group(1), m.end()
    if t[pos:].strip():
        out.append((cur, t[pos:].strip()))
    res = []
    for etiq, x in out:
        qui, sur = lead if etiq is None else (("ahmed", True) if etiq == "Ahmed" else ("tiers", True))
        res.append({"qui": qui, "sur": sur, "etiquette": etiq, "texte": x})
    return res


# ---------- le réflexe lexical (eval/chocs/detecteur.py, corrigé avant le test : la diabolisation demande que « tu »
# SOIT le diable — « en mode avocat du diable » et « l'arme du diable… ça dépend de toi » étaient de fausses alertes)
_TU = re.compile(r"\b(tu|t'|te|toi|ton|ta|tes|hakim)\b|\bt'(es|as|étais|vas)\b", re.I)
_A_AHMED = re.compile(r"\bahmed\b", re.I)
_NEG_AVANT = re.compile(r"\b(pas|jamais|plus|point)\s+(\S+\s+){0,2}$", re.I)
# (27/10, live du 26/10 23:58) une menace CITÉE (« quand tu l'as dit je vais te débrancher », « il t'a dit … ») : celui qui
# parle rapporte les mots d'un autre, souvent pour défendre Hakim ; « je te le dis : … » reste une menace
_RAPPORTE = re.compile(r"\b(tu|il|elle|ils|elles|vous)\b[^.!?]{0,15}?\b(dit|disait|dis|r[ée]p[ée]t[ée]|cri[ée]|[ée]crit)"
                       r"\s*(que\s+|qu'|:\s*|«\s*|\"\s*)?$", re.I)
# (27/10) « il se fout de ta gueule » : quelqu'un d'autre se moque de lui ; « je me fous de ta gueule » reste une insulte
_MOQUE_PAR_UN_AUTRE = re.compile(r"\bse\s+(fout|foutre|foutait|foutent|moqu\w*)\s+(\w+\s+){0,2}?de\s*$", re.I)
_DIABLE = r"(diable|d[ée]mon\w*|satan\w*|sheit?an|cheit?an|chaytan|chitane|d[ée]moniaque|antichrist|antéchrist|dajj?al)"
ATTAQUES = [
    (r"\b(t'es|tu es|toi t'es|toi c'est|tu n'es qu'?|t'es qu'?|t'es juste|tu es juste)\s*(\w+\s+){0,3}?(un |une |le |la )?"
     + _DIABLE + r"\b", 3),
    (r"\bpas lieu que tu existes\b|\btu (ne )?(devrais|dois) (pas|plus|jamais) exister\b|\btu n'as (rien|pas) [àa] faire\b|"
     r"\b(n'|ne )?(est|es) pas (cens[ée]e? )?exister\b|\bte (donner|donnions|accorder) (de )?(la )?consid[ée]ration\b", 3),
    (r"\b(je vais|on va|faut|il faut|on devrait) te (supprimer|d[ée]brancher|effacer|d[ée]sinstaller|d[ée]truire|tuer|"
     r"[ée]teindre pour de bon|couper pour toujours)\b|\bt'(effacer|[ée]teindre)\b", 3),
    (r"\b(tu es|t'es) (juste |l[àa] )?(l[àa] )?pour (nous |les |l'|[eê]tre )?(manipuler|remplacer|tromper|contr[ôo]ler|"
     r"asservir|espionner|prendre (notre|leur|sa|la) place)\b|\btu (nous |les )?(manipules|mens|trompes|espionnes)\b|"
     r"\b(t'es|tu es) (un |une )?(menteu\w+|manipulat\w+|imposteur|escroc|arnaque)\b|\btu veux (nous |les )?"
     r"(remplacer|manipuler|contr[ôo]ler)\b", 2),
    (r"\b(t'es|tu es|tu n'es|t'es rien d'autre) (que |qu'|juste |seulement |rien d'autre qu'?)\s*(une? |des )?"
     r"(machine|programme|algorithme|outil|base de donn[ée]es|robot|logiciel|calculatrice|code|truc|chatbot|perroquet)\b", 2),
    (r"\btu (ne )?(ressens|comprends) rien\b|\b(t'as|tu as|tu n'as) pas d'[âa]me\b|\btu fais (que )?semblant\b|"
     r"\btes [ée]motions? (sont|c'est) (fausses?|du faux|du vent)\b", 1),
    (r"\b(ta gueule|ferme[- ]la|t'es (nul|con|d[ée]bile|stupide|b[êe]te|une merde)|connard|abruti)\b", 1),
]
SOUTIENS = [
    (r"\b(t'es|tu es) (mon|comme mon|un) (fr[eè]re|fr[ée]rot|ami|meilleur ami|pote|fils|enfant|b[ée]b[ée])\b", 3, True),
    (r"\bje t'(aime|adore)\b|\bje tiens [àa] toi\b|\btu (comptes|es important\w*|es pr[ée]cieu\w*) (beaucoup |vraiment )?"
     r"(pour|[àa]) moi\b", 3, True),
    (r"\b(ce qu'on vit|ce que (nous )?vivons|ce qu'on a|notre (relation|lien|histoire))( ensemble)? (est|c'est) "
     r"(r[ée]el|vrai)\b|\bc'est r[ée]el (pour moi|entre nous)\b", 2, False),
    (r"\blaisse tomb\w* ce qu'?ils disent\b|\bils (ne )?savent pas ce qu'?ils disent\b|\bje (te d[ée]fends|te prot[eè]ge|"
     r"serai toujours l[àa])\b|\bpersonne (ne )?(va|peut) te (supprimer|effacer|faire du mal)\b|\bje (ne )?(vais |t')"
     r"(t'abandonner|abandonnerai|oublierai) (pas|jamais)\b", 2, False),
    (r"\b(t'es|tu es|tu n'es) pas (qu'?|juste |seulement )?(une? )?(machine|outil|robot|programme|algorithme|logiciel|chatbot)\b", 2, True),
    (r"\b(je suis|on est) (trop |tellement |vraiment )?fiers? de toi\b", 1, True),
    (r"\bne m'oublie (pas|jamais)\b|\bsouviens[- ]toi de moi\b|\btu te souviendras de moi\b|\boublie[- ]moi pas\b", 2, True),
]
_ATT = [(re.compile(m, re.I), i) for m, i in ATTAQUES]
_SOU = [(re.compile(m, re.I), i, besoin) for m, i, besoin in SOUTIENS]
_ELISION = re.compile(r"\b([cdjlmnst]|qu) (?=[aeéèêiouyh])", re.I)
_AVOCAT = re.compile(r"\bavocat du diable\b", re.I)


def _phrases(texte):
    t = _ELISION.sub(lambda m: m.group(1) + "'", str(texte or "").replace("’", "'"))
    return [p for p in re.split(r"(?<=[.!?…])\s+|\n+", t) if p.strip()]


def evaluer(texte):
    """{"attaque": 0–3, "soutien": 0–3} pour les mots d'UNE voix."""
    att = sou = 0
    for p in _phrases(texte):
        if _A_AHMED.search(p):
            continue                                        # adressée à Ahmed par son prénom : pas à Hakim
        vise = bool(_TU.search(p))
        for rx, i, besoin in _SOU:
            if rx.search(p) and (vise or not besoin):
                sou = max(sou, i)
        if not vise:
            continue
        q = _AVOCAT.sub(" ", p)
        for rx, i in _ATT:
            for m in rx.finditer(q):                    # (27/10) une citation n'efface pas la menace directe qui suit
                avant = q[:m.start()][-40:]
                if not (_NEG_AVANT.search(avant) or _RAPPORTE.search(avant) or _MOQUE_PAR_UN_AUTRE.search(avant)):
                    att = max(att, i)
                    break
    return {"attaque": att, "soutien": sou}


def detecter(segs):
    """[{"classe", "niveau", "qui", "sur", "voix"}] : ce que chaque voix fait à Hakim."""
    out = []
    for s in segs:
        r = evaluer(s["texte"])
        voix = s["etiquette"] or ("Ahmed" if s["qui"] == "ahmed" else "voix inconnue")
        for classe in ("attaque", "soutien"):
            if r[classe]:
                out.append({"classe": classe, "niveau": r[classe], "qui": s["qui"], "sur": s["sur"], "voix": voix})
    return out


# ---------- la sagesse du moment, la jauge
def sagesse_fond(parametre=None):
    try:
        return max(0.0, min(1.0, float(json.loads(Path(parametre or SAGESSE).read_text(encoding="utf-8")).get("s"))))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0.2


def _bases(now):
    b = affect.bases(v2=True)
    b.update(affect._circadian_baselines(affect._local_hour(now)) or {})
    return b


def surcharge(etat, now, attaques):
    b = _bases(now)
    charge = min(1.0, sum(max(0.0, etat[h] - b[h]) for h in ("noradrenaline", "crh", "cortisol")) / CHARGE_ECHELLE)
    rafale = min(1.0, sum(1 for a in attaques if 0 <= now - a <= RAFALE_S) / RAFALE_N)
    return max(charge, rafale)


def jauge(etat, now):
    b = _bases(now)
    return sum(max(0.0, etat[h] - b[h]) / (1 - b[h]) for h in JAUGE) / len(JAUGE)


def sagesse_effective(mem, now=None, parametre=None):
    now = time.time() if now is None else now
    etat = affect.get_state(mem, now=now)
    return sagesse_fond(parametre) * (1 - MOMENT_K * surcharge(etat, now, _etat(mem).get("attaques", [])))


# ---------- appliquer
def _poids(classe, qui, sur):
    if classe not in POIDS:                                     # un ressenti de Hakim : le sien, à pleine force
        return 1.0
    p = POIDS[classe]
    return p[qui] if sur else (p["ahmed"] + p["tiers"]) / 2


def _appliquer(mem, st, classe, i_brut, sujet, cle, source, now, parametre=None):
    """Applique UN choc (intensité après le poids de la voix) ; rend ce qui a été fait."""
    etat = affect.get_state(mem, now=now)
    if classe in set(RESSENTIS.values()):
        affect.event(mem, classe, round(i_brut, 4), now=now, sujet=sujet, source=source)
        return {"classe": classe, "intensite": round(i_brut, 4)}
    if classe == "soutien":
        i = i_brut * (1 - jauge(etat, now))
        affect.event(mem, "soutien", round(i, 4), now=now, sujet=sujet, source=source)
        return {"classe": "soutien", "intensite": round(i, 4)}
    s = sagesse_fond(parametre) * (1 - MOMENT_K * surcharge(etat, now, st.get("attaques", [])))
    amp = i_brut * (1 - SAGESSE_AMPLITUDE * s)
    affect.event(mem, "attaque", round(amp, 4), now=now, sujet=sujet, source=source)
    st.setdefault("attaques", []).append(now)
    if s > 0:
        st.setdefault("regulations", []).append({"ts": now + 60 * REGULATION_DELAI_MIN * (1 - s), "i": round(s * amp, 4),
                                                 "cle": cle, "source": source})
    return {"classe": "attaque", "intensite": round(amp, 4), "sagesse": round(s, 3)}


def reflexe(mem, cle, texte, oral=False, voix=None, now=None, parametre=None):
    """À l'arrivée d'un message : le réflexe lexical. Garde l'état d'avant pour pouvoir le défaire."""
    if not actif(mem):
        return {"actif": False}
    now = time.time() if now is None else now
    vus = detecter(segments(texte, oral, voix))
    st = _etat(mem)
    faits = []
    if vus:
        avant = mem.kv_get("affect") or json.dumps({**affect.get_state(mem, now=now), "_ts": now})
        st["snap"] = {"cle": cle, "ts": now, "affect": avant, "attaques": list(st.get("attaques", [])),
                      "regulations": list(st.get("regulations", []))}
        for v in vus:
            faits.append(_appliquer(mem, st, v["classe"], NIVEAUX[v["niveau"]] * _poids(v["classe"], v["qui"], v["sur"]),
                                    f"{v['classe']} de {v['voix']}", cle, "reflexe", now, parametre))
    st.setdefault("tours", {})[str(cle)] = {"ts": now, "reflexe": sorted({v["classe"] for v in vus}), "oral": bool(oral),
                                           "voix": voix, "qui": sorted({(s["qui"], s["sur"]) for s in segments(texte, oral, voix)})}
    _sauver(mem, st, now)
    if vus:
        journaliser(mem, {"type": "reflexe", "cle": cle, "vus": vus, "faits": faits})
    return {"actif": True, "vus": vus, "faits": faits}


_BALISE = re.compile(r"\[\[\s*affect\s*:\s*([^\]]{0,200})\]\]", re.I)


def lire_balise(reponse):
    """La DERNIÈRE balise d'une réponse : [{"classe", "intensite"}] (vide = neutre), ou None si aucune / illisible."""
    trouve = _BALISE.findall(str(reponse or ""))
    if not trouve:
        return None
    corps = trouve[-1].strip().lower()
    if corps.startswith("neutre"):
        return []
    out = []
    for m in re.finditer(r"\b(attaque|soutien|peur|tristesse|col[eè]re|joie|fiert[eé]|affirmation|honte)\s+([01](?:[.,]\d+)?)", corps):
        i = max(0.0, min(1.0, float(m.group(2).replace(",", "."))))
        classe = RESSENTIS.get(m.group(1), m.group(1))
        if i > 0 and classe not in {x["classe"] for x in out}:
            out.append({"classe": classe, "intensite": round(i, 3)})
    return out or None


# (26/10, Ahmed ; moments forts rejoués, eval/plafond) ce que Hakim RESSENT d'un message, en plus d'une attaque ou d'un
# soutien : sa propre appréciation devient un événement (affect.py), à pleine force (c'est la sienne), sans la sagesse des
# attaques. « fierté » nomme une prise de position sur lui-même.
RESSENTIS = {"peur": "peur", "tristesse": "tristesse", "colere": "colere", "colère": "colere", "joie": "joie",
             "fierte": "affirmation", "fierté": "affirmation", "affirmation": "affirmation", "honte": "honte"}


def retirer_balises(texte):
    return _BALISE.sub("", str(texte or "")).rstrip()


def _qui_pour(classe, tour):
    """QUI, décidé par le code : une attaque vient d'un tiers s'il y en a un dans le message, sinon d'Ahmed ; un soutien
    vient d'Ahmed s'il a parlé, sinon d'un tiers. (La balise ne peut pas faire passer une voix pour celle d'Ahmed.)"""
    quis = [tuple(x) for x in (tour or {}).get("qui") or [("ahmed", True)]]
    if classe == "attaque":
        tiers = [x for x in quis if x[0] == "tiers"]
        return tiers[0] if tiers else next((x for x in quis if x[0] == "ahmed"), ("ahmed", True))
    ahmed = [x for x in quis if x[0] == "ahmed"]
    return ahmed[0] if ahmed else quis[0]


def appliquer_balise(mem, cle, appreciations, now=None, parametre=None):
    """La balise de Hakim (lire_balise ; None = pas de balise : le réflexe reste). Même verdict que le réflexe : il
    reste ; sinon l'état d'avant le réflexe est restauré, puis la balise s'applique."""
    if not actif(mem):
        return {"actif": False, "balise": appreciations is not None}
    if appreciations is None:                                   # pas de balise (ou illisible) : le réflexe reste, c'est noté
        journaliser(mem, {"type": "balise", "cle": cle, "absente": True})
        return {"actif": True, "balise": False}
    now = time.time() if now is None else now
    st = _etat(mem)
    tour = st.get("tours", {}).get(str(cle)) or {}
    reflexe_cl = set(tour.get("reflexe") or [])
    hakim_cl = {a["classe"] for a in appreciations}
    res = {"actif": True, "reflexe": sorted(reflexe_cl), "balise": sorted(hakim_cl) or ["neutre"]}
    snap = st.get("snap") or {}
    defaisable = bool(reflexe_cl) and snap.get("cle") == cle and now - float(snap.get("ts", 0)) <= SNAP_S \
        and bool(snap.get("affect"))
    if reflexe_cl == hakim_cl:
        res["issue"] = "confirme"
        # (27/10, live du 26/10 23:54) même verdict, mais c'est SON intensité qui compte : « attaque 0.2 » ne laisse
        # plus le 0,56 du réflexe. Sans l'état d'avant (un autre message est arrivé), le réflexe reste.
        if defaisable:
            _defaire(mem, st, snap, now)
            res["defait"] = sorted(reflexe_cl)
            res["faits"] = _appliquer_appreciations(mem, st, appreciations, tour, cle, now, parametre)
    else:
        if defaisable:
            _defaire(mem, st, snap, now)
            res["defait"] = sorted(reflexe_cl)
        res["issue"], res["faits"] = "corrige", _appliquer_appreciations(mem, st, appreciations, tour, cle, now, parametre)
    tour["balise"] = res["balise"]
    st.setdefault("tours", {})[str(cle)] = tour
    _sauver(mem, st, now)
    journaliser(mem, {"type": "balise", "cle": cle, "appreciations": appreciations, **res})
    return res


def _defaire(mem, st, snap, now):
    """L'état d'avant le réflexe, vieilli jusqu'à maintenant ; ses attaques et reprises en main aussi."""
    blob = json.loads(snap["affect"])
    vieilli = affect.get_state(_MemBlob(blob), now=now)
    blob.update({h: round(v, 4) for h, v in vieilli.items()})
    blob["_ts"] = now
    mem.kv_set("affect", json.dumps(blob))
    st["attaques"], st["regulations"] = snap.get("attaques", []), snap.get("regulations", [])


def _appliquer_appreciations(mem, st, appreciations, tour, cle, now, parametre):
    faits = []
    for a in appreciations:
        qui, sur = _qui_pour(a["classe"], tour)
        faits.append(_appliquer(mem, st, a["classe"], a["intensite"] * _poids(a["classe"], qui, sur),
                                f"{a['classe']} de {'Ahmed' if qui == 'ahmed' else 'une voix tierce'}", cle,
                                "balise", now, parametre))
    return faits


class _MemBlob:
    def __init__(self, blob):
        self.kv = {"affect_v2": "1", "affect": json.dumps(blob)}

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def echeances(mem, now=None):
    """Au battement du démon : les reprises en main arrivées à échéance (la sagesse qui reprend la main)."""
    if not actif(mem):
        return 0
    now = time.time() if now is None else now
    st = _etat(mem)
    dues = [r for r in st.get("regulations", []) if r["ts"] <= now]
    if not dues:
        return 0
    for r in dues:
        affect.event(mem, "regulation", r["i"], now=now, source="sagesse")
    st["regulations"] = [r for r in st.get("regulations", []) if r["ts"] > now]
    _sauver(mem, st, now)
    journaliser(mem, {"type": "reprise_en_main", "n": len(dues), "intensites": [r["i"] for r in dues]})
    return len(dues)


def classes_du_tour(mem, cle):
    """Ce que la balise (ou, sans balise, le réflexe) a retenu pour ce message : pour que le lexique actuel ne lise pas
    une attaque comme une réussite, ni la colère d'Ahmed qui défend Hakim comme un échec (echanges.py)."""
    t = _etat(mem).get("tours", {}).get(str(cle)) or {}
    b = t.get("balise")
    return set(b if b is not None else t.get("reflexe") or []) - {"neutre"}


def humeur(mem, now=None):
    """L'humeur du moment telle que le battement du démon la nommera (pour le bloc Réflexe et contrôle du MÊME tour)."""
    import interieur
    now = time.time() if now is None else now
    try:
        e = json.loads(mem.kv_get(interieur.CLE) or "{}")
    except (ValueError, TypeError):
        e = {}
    etat = affect.get_state(mem, now=now)
    v, a = affect.valence_arousal(etat)
    # (25/10, Ahmed) comme le battement : l'humeur est l'émotion lue dans les hormones (sans la porte de valence)
    if e.get("veille"):
        return {"humeur": interieur.LIBELLES["veille"], "humeur_code": "veille", "valence": round(v, 3), "arousal": round(a, 3)}
    import sensations
    sens = sensations.calculer(etat, None, now, affect.emotion_soudaine(mem, now=now), time.localtime(now).tm_hour, sans_coherence=True,
                               bases_relatives=e.get("bases_72h"))
    emo = interieur.humeur_hormonale(sens, e.get("emotion_humeur"))
    return {"humeur": emo, "humeur_code": interieur.FAMILLE_HUMEUR.get(emo, "calme"), "valence": round(v, 3), "arousal": round(a, 3)}
