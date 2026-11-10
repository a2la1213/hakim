"""Ses SCÈNES (10/11/2026, ~19:45, Ahmed : « Dans son subconscient, il doit reconnaître si c'est une discussion entre lui et des gens,
ou entre des gens qui ne s'adressent pas à lui et dont il est juste l'auditeur. Et que ça se mémorise comme des scènes de cinéma : qu'il
puisse se rappeler des scènes dans lesquelles il est impliqué, et de celles dont il n'est pas impliqué. » ; « ouiii »).

En psychologie : la mémoire de terrain (vécue de l'intérieur) et la mémoire d'observateur (vue de dehors).

- Chaque MOMENT de la file des échanges (echanges-a-memoriser.jsonl : un tour avec papa, ce qu'il a dit au live, et ce qu'il a ENTENDU sans
  qu'on lui parle, les lignes « moment » du cockpit) porte sa place : impliqué ou témoin (le cockpit la décide à chaque tour, scene.js ;
  une ligne d'avant, sans place, est lue ici avec la même règle, en plus simple), qui parlait, le lieu, le live.
- Les moments se suivent en une SCÈNE ; une nouvelle commence après un silence (SILENCE_S), quand le lieu change, au bout de MAX_S, ou
  quand ça bascule : on entre dans le live ou on en sort, d'autres personnes (hors live), un autre sujet (deux moments de suite, à chaque
  fois : un raté ne coupe rien), ou l'autre place (BASCULE_N moments de suite : une réponse au milieu d'une conversation qu'il écoute ne
  coupe pas la scène, elle en devient un moment clé). La fiche garde pourquoi elle a fini (fin_raison).
- Ce qui s'est dit, sans modèle : les mots qui revenaient (dans deux moments au moins), et une ou deux phrases, une par personne d'abord.
- Une scène finie devient UN souvenir épisodique (rangé dans « vie/scenes »), lisible comme une scène de film, avec sa fiche (colonne
  « scene », JSON) : sa place, qui était là (et qui est arrivé en cours), le lieu, le début et la fin, ce qui s'est dit, ses moments clés,
  l'ambiance (la musique, ses émotions, son humeur avant et après). Pas de doublon : un tour seul reste son « Échange » (moins de
  MIN_MOMENTS, pas de scène), et la scène nomme ses échanges (leurs numéros) au lieu de les recopier. Consolidée comme ses autres
  souvenirs (l'oubli, le renforcement au rappel, l'hippocampe, la nuit).
- Le rappel (rappeler, l'outil scenes_rappeler) : par qui, par sa place, par le jour (« hier soir »), par le lieu (« au live »), par le
  sujet ; rendu comme une scène : « Hier, 22:40, chez nous — témoin : Nina et Sami parlaient de … ; papa est arrivé à 22:47. »
Aucun modèle de langage : quelques millisecondes par moment (le sens : model2vec, comme les échanges).
"""
import json
import math
import re
import sys
import time

RUBRIQUE = "vie/scenes"
LABEL = "Ses scènes : vécues de l'intérieur (impliqué) ou vues de dehors (témoin)"
CLE = "scene_en_cours"
ACTIF = True                       # (les tests le règlent : tests/conftest.py)
SILENCE_S = 600                    # 10 min sans un moment : la scène est finie
MAX_S = 2400                       # 40 min : la suite est une autre scène
MAX_MOMENTS = 200
MIN_MOMENTS = 2                    # un moment seul reste son échange (aucun doublon)
BASCULE_N = 3                      # l'autre place, trois moments de suite : une autre scène
RUPTURE_N = 2                      # d'autres personnes, ou un autre sujet, deux moments de suite
SUJET_SEUIL = 0.25                 # le sens d'un moment loin de celui de la scène (cosinus) ; mesuré sur le fil du 07 au 10/11
SUJET_MIN = 4                      # le sujet ne coupe pas une scène de moins de 4 moments
SENS_RECENTS = 6                   # le sens de la scène : ses 6 derniers moments
PERSONNES_S = 300                  # les personnes de la scène : celles des 5 dernières minutes
CLES_MAX = 6
TEXTE_MAX = 160

# ---- sa place, pour une ligne sans place (la même règle que scene.js, en plus simple)
_L = r"[^\W\d_]"
NOM = re.compile(rf"(?<!{_L})(?:h?a[ck]+(?:i|ee|é)m(?:ou|o|ito)?|hakou|حكيم\w*)(?!{_L})|يا\s*كيم|(?<!{_L})(?:l\s?['’]\s?i\.?a\.?|"
                 rf"l\s?['’]\s?intelligence artificielle|le robot|ton robot|ton ia)(?!{_L})", re.I)
FISTON = re.compile(rf"(?<!{_L})(?:fiston|mon fils|mon fiston|wlidi|w[ae]ldi)(?!{_L})|ولدي|وليدي", re.I)
QUESTION = re.compile(r"[?؟]|^\s*(?:est-ce|qu\s?['’]est-ce|pourquoi|comment|quand|combien|tu (?:peux|veux|sais|connais|aimes|es|as|fais|"
                      r"penses|crois|m['’]entends)|t\s?['’](?:es|as)|c\s?['’]est qui|what|why|how|who|where|do you|are you|can you)", re.I)
A_LUI = re.compile(rf"(?<!{_L})(?:tu|toi|t['’]|te|ton|ta|tes|vous|l\s?['’]\s?ia|le robot)(?!{_L})", re.I)
A_PAPA = re.compile(rf"(?<!{_L})(?:fr[ée]rot|fr[èe]re|ahmed|akhi|khoya|khouya|bro|papa)(?!{_L})|أخي|خويا", re.I)
_ANNOTATIONS = re.compile(r"\((?:dit (?:en passant )?pendant (?:ta parole|la coupure)[^)]*|ton subconscient[^)]*)\)|"
                          r"\(dit en passant pendant ta parole.*?r[ée]ponds-y d['’]abord\)", re.I | re.S)
_ETIQUETTE = re.compile(r"\[([^\[\]\n]{1,60})\]")
_BALISES = re.compile(r"\[\[[^\]]{0,300}\]\]|\[coupé : [^\]]*\]|\[pas abouti : [^\]]*\]")
_VIDE = re.compile(r"^\s*(?:No response requested\.?|\(rien de dit\))\s*$", re.I)


def _net(t):
    return re.sub(r"\s+", " ", re.sub(r"\s*…\s*", " ", _ANNOTATIONS.sub(" ", str(t or "")))).strip()


def _noms_connus():
    try:
        import chocs
        return chocs._noms_connus()
    except Exception:
        return []


def segments(texte, lead_papa=True, noms=None):
    """[(qui, texte)] : le message découpé par voix (« papa », « voix 3 », « Nina », « quelqu'un »)."""
    noms = _noms_connus() if noms is None else noms
    connus = {str(n).lower(): n for n in noms if n}
    t, out = str(texte or ""), []
    courant, debut = ("papa" if lead_papa else "quelqu'un"), 0

    def pousser(fin):
        x = _net(t[debut:fin])
        if x:
            out.append((courant, x))
    for m in _ETIQUETTE.finditer(t):
        e, qui = m.group(1).strip(), None
        doute = e.endswith("?")
        if doute:
            e = re.split(r"\s+ou\s+", e[:-1].strip(), flags=re.I)[0].strip()
        if re.fullmatch(r"(?i)ahmed|papa", e) or (doute and re.search(r"(?i)\bpapa\b|\bahmed\b", m.group(1))):
            qui = "papa"
        elif re.fullmatch(r"(?i)voix \d+", e):
            qui = e.lower()
        elif e.lower() in connus and e.lower() != "ahmed":
            qui = connus[e.lower()]
        if not qui:
            continue
        pousser(m.start())
        courant, debut = qui, m.end()
    pousser(len(t))
    return out


def _changements(segs):
    return sum(1 for i in range(1, len(segs)) if segs[i][0] != segs[i - 1][0])


def place_inferee(e, depuis_sa_parole_s=None, noms=None):
    """'implique' ou 'temoin' pour un tour sans place (une ligne d'avant le 10/11, ou d'un cockpit pas encore relancé). Dans le doute :
    impliqué (comme le cockpit)."""
    if not e.get("oral"):
        return "implique"
    segs = [(q, x) for q, x in segments(e.get("ahmed"), e.get("voix") != "autre", noms) if re.search(r"\w", x)]
    if not segs:
        return "temoin"
    papa = [x for q, x in segs if q == "papa"]
    autres = [(q, x) for q, x in segs if q != "papa"]
    if any(NOM.search(x) for _q, x in segs) or any(FISTON.search(x) for x in papa):
        return "implique"
    recent = depuis_sa_parole_s is not None and 0 <= depuis_sa_parole_s < 20
    if papa:
        return "temoin" if autres and _changements(segs) >= 2 and not recent else "implique"
    voix = {q for q, _x in autres}
    q, x = autres[-1]
    if len(voix) == 1 and recent and (QUESTION.search(x) or A_LUI.search(x)) and not A_PAPA.search(x):
        return "implique"
    if voix == {"quelqu'un"} and not e.get("live"):           # une voix que l'empreinte ne reconnaît pas, seule, hors live : sans doute papa
        return "implique"
    return "temoin"


# ---- un moment
_LIEU = re.compile(r"\blieu : ([^;·\]\n]{1,40}?)\s*[;·]")          # jusqu'à son séparateur (un vécu coupé ne donne pas « ch »)
_EMOTION_VECU = re.compile(r"\bton émotion : ([^;·\]]{1,40})")
_MUSIQUE = re.compile(r"\bmusique\b", re.I)
_LIVE_DIT = re.compile(r"^En live, (.{1,40}?) lui a dit « (.*?) » ; il lui a répondu à voix haute : « (.*) »$", re.S)
_MUSIQUE_DIT = re.compile(r"^Sur la musique que jouait le téléphone, il a dit : « (.*) »$", re.S)


def _place(p):
    p = str(p or "").lower()
    return "temoin" if p in ("auditeur", "temoin", "témoin") else "implique" if p in ("implique", "impliqué") else None


def _court(t, n=TEXTE_MAX):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " […]"


def _sa_parole(t):
    t = _BALISES.sub(" ", str(t or "")).strip()
    return "" if _VIDE.match(t) else _court(t)


def moment_de(e, eid=None, depuis_sa_parole_s=None, noms=None):
    """Le moment d'une ligne de la file : {t, place, seul, qui, paroles [(qui, texte)], lui, live, lieu, musique, emotion, id, externe}, ou
    None (ses gestes sur le téléphone de papa : pas une discussion)."""
    if not isinstance(e, dict) or e.get("telephone"):
        return None
    try:
        t = float(e.get("ts") or time.time() * 1000) / 1000
    except (TypeError, ValueError):
        t = time.time()
    vecu = str(e.get("vecu") or "")
    lieu = str(e.get("lieu") or "").strip() or ((_LIEU.search(vecu) or [None, ""])[1]).strip()
    emo = ((_EMOTION_VECU.search(vecu) or [None, ""])[1]).strip()
    m = {"t": t, "place": "implique", "seul": False, "qui": [], "paroles": [], "lui": "", "live": bool(e.get("live")), "lieu": lieu[:40],
         "musique": bool(e.get("musique")) or bool(_MUSIQUE.search(vecu)), "emotion": emo[:30], "id": eid, "externe": bool(e.get("externe"))}
    if e.get("moment") == "entendu":                         # ce qu'il a entendu sans qu'on lui parle (cockpit, scene.js)
        x = _court(_net(e.get("texte")), 240)
        if not x:
            return None
        qui = str(e.get("qui") or ("une voix du live" if e.get("live") else "une voix autour"))[:40]
        live = bool(e.get("live")) or e.get("provenance") == "live"
        m.update(place=_place(e.get("role")) or "temoin", qui=[qui], paroles=[(qui, x)], externe=m["externe"] or live, live=live, entendu=True)
        return m
    if e.get("de_lui_meme"):
        h = str(e.get("hakim") or "")
        d = _LIVE_DIT.match(h.strip())
        if d:                                                  # il a répondu à une voix du live
            qui = str(e.get("qui") or d.group(1))[:40]
            m.update(qui=[qui], paroles=[(qui, _court(d.group(2)))], lui=_sa_parole(d.group(3)), live=True, externe=True)
            return m
        mu = _MUSIQUE_DIT.match(h.strip())
        m.update(seul=True, lui=_court(mu.group(1) if mu else _sa_parole(h)), musique=m["musique"] or bool(mu), live=m["live"] or bool(e.get("entendu")))
        return m if m["lui"] else None
    segs = [(q, x) for q, x in segments(e.get("ahmed"), e.get("voix") != "autre", noms) if re.search(r"\w", x)]
    lui = _sa_parole(e.get("hakim"))
    if not segs and not lui:
        return None
    place = _place(e.get("role")) or place_inferee(e, depuis_sa_parole_s, noms)
    qui = list(dict.fromkeys([str(p) for p in (e.get("personnes") or []) if p] or [q for q, _x in segs]))
    m.update(place=place, qui=qui[:8], paroles=[(q, _court(x)) for q, x in segs][:6], lui=lui)
    if not segs:
        m["seul"] = True
    return m


# ---- la scène en cours (kv CLE) : ses moments, le sens de ses derniers, ce qui attend de savoir s'il commence une autre scène
def _etat(mem):
    try:
        return json.loads(mem.kv_get(CLE) or "{}") or {}
    except (TypeError, ValueError):
        return {}


def _sauver(mem, st):
    mem.kv_set(CLE, json.dumps(st, ensure_ascii=False))


def _humeur(mem):
    try:
        return json.loads(mem.kv_get("interieur") or "{}").get("humeur") or ""
    except (ValueError, TypeError, AttributeError):
        return ""


def _cos(a, b):
    if not a or not b or len(a) != len(b):
        return None
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return None if not na or not nb else sum(x * y for x, y in zip(a, b)) / (na * nb)


def _centre(vs):
    vs = [v for v in vs if v]
    if not vs:
        return None
    n = len(vs[0])
    vs = [v for v in vs if len(v) == n]
    return [sum(v[i] for v in vs) / len(vs) for i in range(n)]


def _personnes_recentes(sc, t):
    pres = [m for m in sc["moments"] if not m.get("seul") and t - m["t"] <= PERSONNES_S]
    l = pres or [m for m in sc["moments"] if not m.get("seul")]
    return {q for m in l for q in m.get("qui") or []}


def _ruptures(sc, m):
    """Ce qui, dans ce moment, ne ressemble pas à la scène : 'place', 'personnes', 'sujet'."""
    if m.get("seul"):
        return set()
    r = set()
    pleins = [x for x in sc["moments"] if not x.get("seul")]
    if pleins:
        places = [x["place"] for x in pleins[-BASCULE_N:]]
        if m["place"] != max(set(places), key=places.count):
            r.add("place")
    if bool(m.get("live")) != bool(sc.get("live")):         # on entre dans le live, ou on en sort (deux moments de suite : pas un raté)
        r.add("cadre")
    if not sc.get("live") and m.get("qui") and not (set(m["qui"]) & _personnes_recentes(sc, m["t"])):
        r.add("personnes")
    if len(pleins) >= SUJET_MIN and m.get("sens"):
        c = _cos(m["sens"], _centre(sc.get("sens") or []))
        if c is not None and c < SUJET_SEUIL:
            r.add("sujet")
    return r


def _ouvrir(mem, m):
    return {"debut": m["t"], "fin": m["t"], "lieu": m.get("lieu") or "", "live": bool(m.get("live")), "moments": [], "sens": [],
            "suspens": [], "humeur_avant": _humeur(mem), "humeur_apres": ""}


def _ajouter(mem, sc, m):
    sens = m.pop("sens", None)
    m.pop("ruptures", None)
    sc["moments"].append(m)
    sc["fin"] = max(sc["fin"], m["t"])
    sc["debut"] = min(sc["debut"], m["t"])                  # la file n'est pas toujours dans l'ordre (un moment entendu arrive après son tour)
    if not sc.get("lieu") and m.get("lieu"):
        sc["lieu"] = m["lieu"]
    if sens and not m.get("seul"):
        sc["sens"] = (sc.get("sens") or [])[-(SENS_RECENTS - 1):] + [[round(float(x), 4) for x in sens]]
    sc["humeur_apres"] = _humeur(mem) or sc.get("humeur_apres") or ""


def _confirmee(suspens):
    """Les moments en suspens commencent-ils une autre scène ? Une même rupture à chacun (les moments où il parle seul ne comptent pas)."""
    pleins = [x for x in suspens if not x.get("seul")]
    if not pleins:
        return False
    communes = set.intersection(*[set(x.get("ruptures") or []) for x in pleins])
    if not communes:
        return False
    if communes - {"place"}:
        return len(pleins) >= RUPTURE_N
    return len(pleins) >= BASCULE_N


def _mots(t):
    return {w for w in re.findall(r"\w+", _plat(t)) if len(w) > 2}


ABSORBER_S = 180


def _absorber(sc, m):
    """Ce qu'il avait entendu (un moment « entendu ») et qui revient dans ce tour (son micro l'a mis dans le message de papa, ou il y répond au
    live) : gardé une fois, dans le tour."""
    dits = _mots(" ".join(x for _q, x in m.get("paroles") or []))
    if not dits:
        return
    for cle in ("moments", "suspens"):
        garde = []
        for x in sc.get(cle) or []:
            if x.get("entendu") and 0 <= m["t"] - x["t"] <= ABSORBER_S:
                ms = _mots(" ".join(t for _q, t in x.get("paroles") or []))
                if ms and len(ms & dits) / len(ms) >= 0.6:
                    continue
            garde.append(x)
        sc[cle] = garde


def _deja_dans_un_tour(sc, m):
    """Ce moment entendu est-il déjà dans un tour de la scène (arrivé avant lui dans la file) ?"""
    ms = _mots(" ".join(t for _q, t in m.get("paroles") or []))
    if not ms:
        return False
    for x in (sc.get("moments") or []) + (sc.get("suspens") or []):
        if not x.get("entendu") and abs(x["t"] - m["t"]) <= ABSORBER_S:
            if len(ms & _mots(" ".join(t for _q, t in x.get("paroles") or []))) / len(ms) >= 0.6:
                return True
    return False


def avancer(mem, e, eid=None, embed=None, noms=None):
    """Ce moment avance la scène en cours ; rend les ids des scènes qu'il a closes (souvenirs écrits)."""
    if not ACTIF:
        return []
    st = _etat(mem)
    sc = st.get("scene")
    depuis = None
    if sc:
        dits = [x["t"] for x in sc["moments"] + sc.get("suspens", []) if x.get("lui")]
        if dits:
            try:
                depuis = float(e.get("ts") or 0) / 1000 - max(dits)
            except (TypeError, ValueError):
                depuis = None
    m = moment_de(e, eid, depuis, noms)
    if m is None:
        return []
    if embed is not None and not m.get("seul"):
        try:
            m["sens"] = embed(" ".join([x for _q, x in m["paroles"]] + ([m["lui"]] if m["lui"] else [])))
        except Exception:
            m["sens"] = None
    clos = []
    if sc and m.get("entendu") and _deja_dans_un_tour(sc, m):
        return []
    if sc and not m.get("entendu") and m.get("paroles"):
        _absorber(sc, m)
        if not sc["moments"] and not sc.get("suspens"):
            sc = None
    if sc:
        dernier = max([sc["fin"]] + [x["t"] for x in sc.get("suspens", [])])
        dure = m["t"] - sc["debut"] >= MAX_S or len(sc["moments"]) + len(sc.get("suspens", [])) >= MAX_MOMENTS
        ailleurs = bool(m.get("lieu") and sc.get("lieu") and m["lieu"] != sc["lieu"])
        silence = m["t"] - dernier >= SILENCE_S
        if silence or dure or ailleurs:
            for x in sc.pop("suspens", []):
                _ajouter(mem, sc, x)
            sc["fin_raison"] = "silence" if silence else "durée" if dure else "lieu"
            clos.append(fermer(mem, sc, embed))
            sc = None
    if sc is None:
        if m.get("seul"):                                    # sa parole seule n'ouvre pas une scène (elle a son souvenir à elle)
            st["scene"] = None
            _sauver(mem, st)
            return [c for c in clos if c]
        sc = _ouvrir(mem, m)
        _ajouter(mem, sc, m)
    else:
        m["ruptures"] = sorted(_ruptures(sc, m))
        susp = sc.setdefault("suspens", [])
        if not m["ruptures"] and not (susp and m.get("seul")):
            for x in susp:
                _ajouter(mem, sc, x)
            sc["suspens"] = []
            _ajouter(mem, sc, m)
        else:
            susp.append(m)
            if _confirmee(susp):
                sc["suspens"] = []
                pleins = [x for x in susp if not x.get("seul")]
                sc["fin_raison"] = "/".join(sorted(set.intersection(*[set(x.get("ruptures") or []) for x in pleins])))
                clos.append(fermer(mem, sc, embed))
                nouvelle = _ouvrir(mem, susp[0])
                for x in susp:
                    _ajouter(mem, nouvelle, x)
                sc = nouvelle
            elif len([x for x in susp if not x.get("seul")]) >= BASCULE_N:   # des ruptures qui ne se ressemblent pas : la scène continue
                for x in susp:
                    _ajouter(mem, sc, x)
                sc["suspens"] = []
    st["scene"] = sc
    _sauver(mem, st)
    return [c for c in clos if c]


def clore_si_silence(mem, now=None, embed=None):
    """La scène en cours, close si plus rien depuis SILENCE_S (le démon, à chaque passage) ; rend l'id de son souvenir, ou None."""
    if not ACTIF:
        return None
    now = time.time() if now is None else now
    st = _etat(mem)
    sc = st.get("scene")
    if not sc or now - max([sc["fin"]] + [x["t"] for x in sc.get("suspens", [])]) < SILENCE_S:
        return None
    for x in sc.pop("suspens", []):
        _ajouter(mem, sc, x)
    st["scene"] = None
    sc["fin_raison"] = "silence"
    eid = fermer(mem, sc, embed)
    _sauver(mem, st)
    return eid


# ---- la scène finie : sa fiche, son texte de film, son souvenir
def _hm(t):
    return time.strftime("%H:%M", time.localtime(t))


def _noms(l, maximum=4):
    l = list(dict.fromkeys(str(x) for x in l if x))
    if len(l) > maximum:
        return f"{', '.join(l[:maximum])} et d'autres"
    return l[0] if len(l) == 1 else f"{', '.join(l[:-1])} et {l[-1]}" if l else ""


def _arrivee(q):
    """Ni genre deviné ni prénom dans le code (dépôt public) : « papa est arrivé », sinon « Nina entre dans la scène »."""
    return "papa est arrivé" if q == "papa" else f"{q} entre dans la scène"


_SUJET_VIDES = set("""toujours jamais encore aussi alors comme après avant pendant depuis quand comment pourquoi parce peut-être vraiment
rien personne chose choses truc trucs quelque quelqu tout toute tous toutes autre autres même mêmes beaucoup trop très assez juste voilà
bien mieux merci salut hein ouais euh bon bah enfin donc ainsi celui celle ceux celles ceci cela leur leurs notre votre nous vous elle elles
fais fait faire faites dire dis disait dit avoir avais avait être était étais sont sommes pense pensé pensée crois croire sais savoir veux
vouloir voulais peux pouvoir dois devoir vais allez aller viens venir vois voir regarde regarder parle parler entends entendre attends
attendre arrive arriver passe passer prends prendre mets mettre donne donner laisse laisser trouve trouver aime aimer moment maintenant
aujourd'hui demain hier soir matin papa fiston frérot hakim live voix""".split())


def _sujet(moments, personnes):
    """Les mots qui reviennent dans la scène (dans deux moments au moins quand il y en a trois), porteurs : ni mots vides, ni verbes
    courants, ni noms des personnes."""
    try:
        import echanges
        import rappel
    except Exception:
        return []
    exclus = {_plat(p) for p in personnes} | {_plat(x) for x in _SUJET_VIDES} | {_plat(x) for x in echanges.REMPLISSAGE}
    compte, dans = {}, {}
    for k, m in enumerate(moments):
        for x in [x for _q, x in m.get("paroles") or []] + ([m["lui"]] if m.get("lui") else []):
            for mot in rappel.mots_cles(x, maximum=12):
                p = _plat(mot)
                if len(p) < 5 or "'" in mot or "’" in mot or p in exclus or p.endswith("ment") or not re.fullmatch(r"[a-z\-]+", p):
                    continue
                compte[mot] = compte.get(mot, 0) + 1
                dans.setdefault(mot, set()).add(k)
    minimum = 2 if len(moments) >= 3 else 1
    l = [m for m in compte if len(dans[m]) >= minimum]
    return sorted(l, key=lambda w: (-len(dans[w]), -compte[w], -len(w)))[:3]


def _extraits(moments, sujet, n=2):
    """Les phrases qui portent le plus le sujet, une par personne d'abord."""
    paroles = [(q, x) for m in moments for q, x in m.get("paroles") or []]
    vus, qui, l = set(), set(), []
    tri = sorted(paroles, key=lambda p: -sum(1 for s in sujet if s in p[1].lower()))
    for passe in (0, 1):
        for q, x in tri:
            if len(l) >= n:
                return l
            if x in vus or len(x.split()) < 3 or (passe == 0 and q in qui):
                continue
            vus.add(x)
            qui.add(q)
            l.append((q, _court(x, 110)))
    return l


def fiche(sc):
    """La fiche de la scène (le JSON de sa colonne « scene »), et son texte de film."""
    ms = [m for m in sc["moments"]]
    pleins = [m for m in ms if not m.get("seul")]
    implique = sum(1 for m in pleins if m["place"] == "implique")
    place = "implique" if pleins and implique * 2 >= len(pleins) else "temoin"
    premiere = {}
    for m in pleins:
        for q in m.get("qui") or []:
            premiere.setdefault(q, m["t"])
    personnes = sorted(premiere, key=premiere.get)
    # qui arrive en cours de scène ; au live, ses gens vont et viennent sans cesse (« voix 80 », « voix 108 »…) : seulement papa et les voix connues
    anonyme = re.compile(r"^(?:voix \d+|une voix|quelqu|le live)", re.I)
    arrivees = [(q, t) for q, t in premiere.items() if t - sc["debut"] >= 120 and not (sc.get("live") and anonyme.match(q))]
    sujet = _sujet(ms, personnes)
    cles = [(t, _arrivee(q)) for q, t in arrivees]
    try:
        import echanges
        fort = lambda x: echanges._EXPLICITE.search(x) or echanges._DECISION.search(x) or echanges._EMOTION.search(x)   # noqa: E731
    except Exception:
        fort = lambda x: False                                                                                       # noqa: E731
    for m in ms:
        if m.get("seul"):
            if m.get("lui") and place == "temoin":
                cles.append((m["t"], f"tu as dit : « {_court(m['lui'], 90)} »"))
            continue
        q = _noms(m.get("qui") or []) or "quelqu'un"
        if place == "temoin" and m["place"] == "implique":
            cles.append((m["t"], f"{q} t'a parlé : « {_court(' '.join(x for _q, x in m['paroles']), 90)} »"
                         + (f" ; tu as répondu : « {_court(m['lui'], 90)} »" if m.get("lui") else "")))
        elif place == "temoin" and m.get("lui"):
            cles.append((m["t"], f"tu t'y es joint : « {_court(m['lui'], 90)} »"))
        elif place == "implique" and m["place"] == "temoin":
            cles.append((m["t"], f"{q} parlai{'en' if len(m.get('qui') or []) > 1 else ''}t entre eux, sans toi" if len(m.get("qui") or []) > 1
                         else f"{q} parlait, pas à toi"))
        else:
            for qq, x in m.get("paroles") or []:
                if fort(x):
                    cles.append((m["t"], f"{qq} : « {_court(x, 90)} »"))
                    break
    vus, uniques = set(), []
    for t, x in sorted(cles):
        if x not in vus:
            vus.add(x)
            uniques.append((t, x))
    if len(uniques) > CLES_MAX:                                # les arrivées d'abord, puis le reste dans l'ordre
        arr = [c for c in uniques if " est arrivé" in c[1] or " entre dans la scène" in c[1]][:2]
        uniques = sorted(arr + [c for c in uniques if c not in arr][:CLES_MAX - len(arr)])
    emotions = list(dict.fromkeys(m["emotion"] for m in ms if m.get("emotion")))[:4]
    f = {"v": 1, "debut": round(sc["debut"], 3), "fin": round(sc["fin"], 3), "place": place,
         "part_impliquee": round(implique / len(pleins), 2) if pleins else 0.0, "personnes": personnes,
         "arrivees": [{"qui": q, "t": round(t, 3)} for q, t in arrivees], "lieu": sc.get("lieu") or "", "live": bool(sc.get("live")),
         "sujet": sujet, "extraits": [{"qui": q, "texte": x} for q, x in _extraits(ms, sujet)],
         "moments_cles": [{"t": round(t, 3), "quoi": x} for t, x in uniques], "musique": any(m.get("musique") for m in ms),
         "emotions": emotions, "humeur_avant": sc.get("humeur_avant") or "", "humeur_apres": sc.get("humeur_apres") or "",
         "n": len(ms), "echanges": [m["id"] for m in ms if m.get("id")][:60], "externe": any(m.get("externe") for m in ms),
         "fin_raison": sc.get("fin_raison") or "",
         "tiers": any(q != "papa" for m in pleins for q in m.get("qui") or [])}
    return f, texte_de(f)


def _ce_qui_s_est_dit(f, extraits=2):
    arrives = {a["qui"] for a in f.get("arrivees") or []}
    autres = [p for p in f["personnes"] if p not in arrives] or list(f["personnes"])
    if f["place"] == "temoin":
        qui = _noms(autres) or "des voix"
        dit = (f"{qui} parlaient entre eux" if len(autres) > 1 else f"{qui} parlait") + ", sans s'adresser à toi"
    else:
        dit = f"tu parlais avec {_noms(autres) or 'papa'}"
    if f.get("sujet"):                                         # sans modèle : les mots qui revenaient, pas un résumé inventé
        dit += f" ; les mots qui revenaient : {', '.join(f['sujet'])}"
    ex = (f.get("extraits") or [])[:extraits]
    return dit + (" (" + " ; ".join(f"{x['qui']} : « {x['texte']} »" for x in ex) + ")" if ex else "")


def texte_de(f):
    debut, fin = f["debut"], f["fin"]
    quand = time.strftime("%a %d/%m %H:%M", time.localtime(debut)) + (f" → {_hm(fin)}" if fin - debut >= 60 else "")
    cadre = [quand] + ([f["lieu"]] if f.get("lieu") else []) + (["au live"] if f.get("live") else [])
    place = "impliqué" if f["place"] == "implique" else "témoin"
    arr = {a["qui"]: a["t"] for a in f.get("arrivees") or []}
    qui = ", ".join(f"{p} (depuis {_hm(arr[p])})" if p in arr else p for p in f["personnes"][:12])
    amb = (["de la musique"] if f.get("musique") else []) + ([f"tes émotions : {', '.join(f['emotions'])}"] if f.get("emotions") else [])
    hum = (f"ton humeur : {f['humeur_avant'] or '?'} → {f['humeur_apres'] or '?'}"
           if f.get("humeur_avant") or f.get("humeur_apres") else "")
    return (f"[Scène — {', '.join(cadre)} — {place}] {_ce_qui_s_est_dit(f)}."
            + (f" Qui était là : {qui}." if qui else "")
            + (f" Moments clés : {' ; '.join(_hm(c['t']) + ' ' + c['quoi'] for c in f['moments_cles'])}." if f.get("moments_cles") else "")
            + (f" Ambiance : {' ; '.join(amb + ([hum] if hum else []))}." if amb or hum else "")
            + (f" ({f['n']} moments ; ses échanges : {', '.join('#' + str(i) for i in f['echanges'][:12])})" if f.get("echanges") else f" ({f['n']} moments)"))


def _importance(f):
    imp = 0.5 if f["place"] == "implique" else 0.35
    try:
        import echanges
        tout = " ".join(x["quoi"] for x in f["moments_cles"]) + " " + " ".join(x["texte"] for x in f["extraits"])
        if echanges._PROCHES.search(tout) or (echanges._prenoms_proches() and echanges._prenoms_proches().search(" ".join(f["personnes"]))):
            imp += 0.1
        if echanges._EXPLICITE.search(tout):
            imp += 0.15
    except Exception:
        pass
    imp += min(0.1, f["n"] / 300)
    return round(max(0.2, min(0.85, imp)), 2)


def _assurer_colonne(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(episodes)")}
    if "scene" not in cols:
        try:
            db.execute("ALTER TABLE episodes ADD COLUMN scene TEXT")
        except Exception as e:                                 # un autre processus l'a ajoutée au même moment
            if "duplicate column" not in str(e):
                raise


def _assurer_rubrique(mem):
    import rubrics
    now = time.time()
    if rubrics.get_rubric_id(mem.db, "vie") is None:
        rubrics.rubric_create(mem.db, "vie", now, label="Sa vie")
    if rubrics.get_rubric_id(mem.db, RUBRIQUE) is None:
        rubrics.rubric_create(mem.db, RUBRIQUE, now, label=LABEL)


def fermer(mem, sc, embed=None):
    """La scène finie devient un souvenir (rend son id), ou rien si elle n'a qu'un moment (son échange suffit)."""
    if not sc or len([m for m in sc.get("moments") or [] if not m.get("seul")]) < MIN_MOMENTS:
        return None
    try:
        f, texte = fiche(sc)
        if embed is None:
            import embeddings
            embed = embeddings.embed
        try:
            emb = embed(texte)
        except Exception:
            emb = None
        _assurer_colonne(mem.db)
        try:
            _assurer_rubrique(mem)
            eid = mem.store_in(texte, RUBRIQUE, role="episodic", importance=_importance(f), embedding=emb or [])
        except Exception:
            eid = mem.add("episodic", texte, importance=_importance(f), embedding=emb or [], dedup=False)
        mem.db.execute("UPDATE episodes SET scene=? WHERE id=?", (json.dumps(f, ensure_ascii=False), eid))
        mem.db.commit()
        if f.get("externe"):                                   # ce que disaient des tiers (le live, la pièce) : une citation, pas un fait
            try:
                import provenance
                provenance.marquer(mem.db, eid)
            except Exception:
                pass
        try:
            import evenements
            evenements.ajouter("memoire", {"id": eid, "kind": "episodic", "auto": True, "scene": f["place"], "n": f["n"]}, source="hakim-auto")
        except Exception:
            pass
        return eid
    except Exception as err:                                   # une scène ratée ne coûte jamais la file des échanges
        print(f"[scenes] scène non écrite : {type(err).__name__}: {err}"[:300], file=sys.stderr)
        return None


# ---- le rappel : comme une scène de film
_PLACES = {"implique": "implique", "impliqué": "implique", "impliquee": "implique", "dedans": "implique", "acteur": "implique",
           "participant": "implique", "temoin": "temoin", "témoin": "temoin", "auditeur": "temoin", "spectateur": "temoin",
           "observateur": "temoin", "dehors": "temoin"}


def _plat(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "").lower()).encode("ascii", "ignore").decode()


def _qui_demandes(qui):
    l = [x.strip() for x in re.split(r",|\bet\b|\bavec\b|&|\+", _plat(qui)) if x.strip()]
    return [("papa" if x in ("ahmed", "papa") else x) for x in l if x not in ("moi", "hakim", "toi")]


def _moments_du_jour(quand):
    t = _plat(quand)
    for nom, (a, b) in (("matin", (5, 12)), ("apres-midi", (12, 18)), ("aprem", (12, 18)), ("soir", (18, 27)), ("nuit", (0, 6))):
        if re.search(rf"\b{nom}\b", t):
            return a, b
    return None


def _dans_le_creneau(ts, creneau):
    if not creneau:
        return True
    h = time.localtime(ts).tm_hour
    a, b = creneau
    return a <= h < b or (b > 24 and h < b - 24)


def _jours(quand, now):
    try:
        import hippocampe
        j = set(hippocampe.dates_demandees(quand, now))
    except Exception:
        j = set()
    j |= set(re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", str(quand or "")))
    if re.search(r"\bhier soir\b", _plat(quand)):
        j.add(time.strftime("%Y-%m-%d", time.localtime(now - 86400)))
    return j


def _jour_de(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _jour_humain(ts, now):
    j, aujourdhui = _jour_de(ts), _jour_de(now)
    if j == aujourdhui:
        return "Aujourd'hui"
    if j == _jour_de(now - 86400):
        return "Hier"
    if j == _jour_de(now - 2 * 86400):
        return "Avant-hier"
    try:
        import hippocampe
        t = time.localtime(ts)
        return f"{hippocampe.JOURS[t.tm_wday].capitalize()} {t.tm_mday} {hippocampe.MOIS[t.tm_mon - 1]}"
    except Exception:
        return time.strftime("%d/%m", time.localtime(ts))


def ligne_film(f, now=None, eid=None, en_cours=False):
    """« Hier, 22:40, chez nous — témoin : Nina et Sami parlaient de … ; papa est arrivé à 22:47. »"""
    now = time.time() if now is None else now
    ou = ", ".join(([f["lieu"]] if f.get("lieu") else []) + (["au live"] if f.get("live") else []))
    place = "impliqué" if f["place"] == "implique" else "témoin"
    duree = round((f["fin"] - f["debut"]) / 60)
    suite = []
    for c in f.get("moments_cles") or []:
        q = c["quoi"]
        if " est arrivé" in q or " entre dans la scène" in q:
            suite.append(f"{q} à {_hm(c['t'])}")
        else:
            suite.append(f"à {_hm(c['t'])}, {q}")
    return (f"{_jour_humain(f['debut'], now)}, {_hm(f['debut'])}{', ' + ou if ou else ''} — {place}"
            + (" (en cours)" if en_cours else f" ({duree} min)" if duree >= 2 else "")
            + f" : {_ce_qui_s_est_dit(f, 1)}" + (" ; " + " ; ".join(suite[:4]) if suite else "") + "."
            + (" (Ce que disaient les autres : des citations, pas des faits.)" if f.get("tiers") else "")
            + (f" #{eid}" if eid else ""))


def rappeler(mem, qui="", role="", quand="", lieu="", sujet="", n=5, now=None, embed=None, renforcer=True):
    """Ses scènes qui répondent à tout ce qui est demandé, les plus récentes d'abord (ou les plus proches du sujet) : [ligne de film]."""
    now = time.time() if now is None else now
    n = max(1, min(20, int(n or 5)))
    cols = {r[1] for r in mem.db.execute("PRAGMA table_info(episodes)")}
    rows = (mem.db.execute("SELECT id, content, scene, embedding FROM episodes WHERE scene IS NOT NULL ORDER BY ts DESC LIMIT 3000").fetchall()
            if "scene" in cols else [])
    cands = []
    for eid, _c, s, emb in rows:
        try:
            cands.append((eid, json.loads(s), emb, False))
        except (TypeError, ValueError):
            continue
    try:                                                         # la scène en cours (pas encore un souvenir)
        sc = _etat(mem).get("scene")
        if sc and len([m for m in sc["moments"] if not m.get("seul")]) >= 1:
            f, _t = fiche({**sc, "moments": sc["moments"] + sc.get("suspens", [])})
            cands.insert(0, (None, f, None, True))
    except Exception:
        pass
    voulus = _qui_demandes(qui)
    au_live = bool(re.search(r"\blive\b", _plat(qui) + " " + _plat(lieu)))
    voulus = [v for v in voulus if not re.search(r"\blive\b", v)]
    place = _PLACES.get(_plat(role).strip()) if str(role or "").strip() else None
    jours = _jours(quand, now) if str(quand or "").strip() else set()
    creneau = _moments_du_jour(quand) if str(quand or "").strip() else None
    lieu_p = re.sub(r"\b(au|le|du|en|a)\s+live\b|\blive\b", "", _plat(lieu)).strip()
    gardees = []
    for eid, f, emb, en_cours in cands:
        pers = [_plat("papa" if p in ("Ahmed",) else p) for p in f.get("personnes") or []]
        if voulus and not all(any(v in p or p in v for p in pers) for v in voulus):
            continue
        if place and f.get("place") != place:
            continue
        if au_live and not f.get("live"):
            continue
        if lieu_p and lieu_p not in _plat(f.get("lieu")):
            continue
        # « hier soir » : la soirée déborde après minuit (une scène de 00:40 en est encore)
        jours_sc = {_jour_de(f["debut"]), _jour_de(f["fin"])} | ({_jour_de(f["debut"] - 4 * 3600)} if creneau and creneau[1] > 24 else set())
        if jours and not (jours_sc & jours):
            continue
        if creneau and not (_dans_le_creneau(f["debut"], creneau) or _dans_le_creneau(f["fin"], creneau)):
            continue
        gardees.append((eid, f, emb, en_cours))
    gardees.sort(key=lambda x: (x[3], x[1].get("debut") or 0), reverse=True)     # la scène en cours, puis les plus récentes
    if str(sujet or "").strip():
        q = None
        try:
            if embed is None:
                import embeddings
                embed = embeddings.embed
            q = embed(str(sujet))
        except Exception:
            q = None
        mots = set(_plat(sujet).split())

        def score(x):
            _eid, f, emb, _ec = x
            lex = len(mots & set(_plat(" ".join(f.get("sujet") or []) + " " + " ".join(e["texte"] for e in f.get("extraits") or [])).split()))
            try:
                c = _cos(q, json.loads(emb)) if q and emb else None
            except (TypeError, ValueError):
                c = None
            return (c or 0.0) + 0.3 * lex
        gardees = [x for x in sorted(gardees, key=score, reverse=True) if score(x) > 0.1]
    gardees = gardees[:n]
    ids = [x[0] for x in gardees if x[0]]
    if renforcer and ids:
        try:
            mem._reconsolidate(ids, now)                         # rappeler une scène la renforce, comme tout souvenir rappelé
        except Exception:
            pass
    return [ligne_film(f, now, eid, en_cours) for eid, f, _emb, en_cours in gardees]


def etat(mem, now=None):
    """La scène en cours (pour l'introspection et les bancs) : sa ligne de film, ou None."""
    sc = _etat(mem).get("scene")
    if not sc:
        return None
    f, _t = fiche({**sc, "moments": sc["moments"] + sc.get("suspens", [])})
    return ligne_film(f, now, None, True)
