"""Le rappel automatique (2026-10-21, idée d'Ahmed) : à chaque message, avant que Hakim réponde, toute sa mémoire est
balayée — sans rien lire en entier — pour retrouver ce qui peut s'y rapporter, de près ou de loin. Trois étapes :

1. le BALAYAGE large (ici) : les mots-clés du message (les mots rares pèsent plus, IDF) ET le sens général
   (embeddings model2vec, le même rappel que memory_recall), fusionnés par rang (RRF) ; seulement le vécu et le
   savoir (échanges, faits, références, raisonnements), jamais ses pensées de fond ni ses rêves ;
2. l'ÉLAGAGE : d'abord par score (un seuil réglé sur les 35 requêtes-vérité, eval/rappel_auto.py), puis par sa
   CONSCIENCE (Claude) qui voit la liste courte et ne garde que ce qui compte. Gemma (le subconscient) n'élague pas :
   un 12 B à charger (~8 Go) coûterait plusieurs secondes par message et disputerait la mémoire à la voix ;
3. la PRÉCISION : Hakim relit le détail de ce qui compte (memory_lire), seulement quand il en a besoin.

Lecture seule ; rien n'est renforcé par ce balayage (reconsolidate=False).
"""
import json
import math
import re
import time
from pathlib import Path


ROLES = ("episodic", "semantic", "user", "reference", "project", "reasoning")
MOTS_VIDES = set("""
a à au aux avec ce ces cet cette ça ca c d de des du elle elles en et eu il ils je j l la le les leur lui m ma mais me
mes moi mon même n ne ni nos notre nous on ou où par pas pour qu que qui quoi s sa sans se ses si son sur t ta te tes
toi ton tu un une vos votre vous y est sont suis es était étais été être avoir ai as avons avez ont avait fait faire
dit dire va vais vas aller peux peut veux veut faut tout tous toute toutes très trop plus moins bien bon bonne comme
quand alors donc aussi encore déjà juste vraiment rien chose truc trucs ok oui non merci frero frérot frère salut hey
hakim jarvis stp please the and you for this that with what have just j'ai c'est d'accord vas-y parfait ouai ouais
voilà bah bref genre fréro frerot fréro frere barakallahofik barakallah hamdoulillah inchallah machallah wallah
mashallah salam peux-tu est-ce qu'il qu'on t'as attends capté capte vient viens changer ailleurs content contente
truc chose fais faisons regarde dis-moi écoute bref
""".split())
K_RRF = 60
ALIAS_CLE, ALIAS_VERSION, SEP_ALIAS = "rappel_alias", "rappel_alias_v", "\n⟦alias⟧ "
# La porte (réglée sur les requêtes-vérité et des messages banals, eval/rappel_auto.py) : le rang seul (RRF) ne sait
# pas dire « rien de pertinent » — le premier du classement existe toujours. Un candidat passe s'il partage des mots
# RARES avec le message (somme des IDF ≥ PORTE_MOTS), ou si son sens est très proche (≥ PORTE_SENS) ; « ok », « merci »,
# « bonne nuit » n'apportent rien.
PORTE_MOTS = 6.5
PORTE_SENS = 0.70
JOUR_MAX = 3
MOT_RARE = 0.45         # le mot le plus rare en commun doit l’être un peu (IDF ≥ 0,45 × son maximum ; 0,6 coûtait 23 points de rappel)
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def dates_du_jour(now=None):
    """La date du jour écrite en toutes lettres dans un souvenir : « 21 octobre » (pas « 21/10 » : c'est l'en-tête
    de chaque échange du jour)."""
    t = time.localtime(time.time() if now is None else now)
    mois = MOIS[t.tm_mon - 1]
    return [f" {t.tm_mday} {mois}"] + ([f" 1er {mois}"] if t.tm_mday == 1 else [])
SEUIL = 0.0
LIGNES_MAX = 8


class Index:
    """Le texte (en minuscules) du vécu et du savoir, gardé en mémoire par le processus du cockpit : le balayage par
    mots-clés passe de ~200 ms (8 requêtes LIKE sur toute la base) à quelques millisecondes. Rafraîchi à chaque appel
    pour les souvenirs neufs, et en entier toutes les 10 minutes (les souvenirs fusionnés, rangés, effacés)."""
    def __init__(self):
        self.lignes, self.max_id, self.complet_ts = {}, 0, 0.0
        self.alias_v, self.avec_alias = None, set()
        self.vecteurs, self._mat, self._ids = {}, None, []

    def rafraichir(self, mem, now=None):
        now = time.time() if now is None else now
        marques = ",".join("?" * len(ROLES))
        archives = "(r.path IS NULL OR (r.path != 'archives' AND r.path NOT LIKE 'archives/%'))"
        if self.lignes and now - self.complet_ts > 600:
            # toutes les 10 min, une synchronisation LÉGÈRE (les numéros seulement) : ce qui a été effacé, fusionné ou
            # rangé dans « archives » sort ; les embeddings déjà lus restent (une reconstruction prenait ~0,8 s)
            valides = {r[0] for r in mem.db.execute(f"""SELECT e.id FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id
                WHERE e.role IN ({marques}) AND {archives}""", ROLES)}
            for eid in [e for e in self.lignes if e not in valides]:
                self.lignes.pop(eid, None)
                self.vecteurs.pop(eid, None)
                self._mat = None
            self.complet_ts = now
        elif not self.lignes:
            self.complet_ts = now
        # le vécu et le savoir, hors « archives » (doublons fusionnés, faits périmés : rangés à la main)
        rows = mem.db.execute(f"""SELECT e.id, e.ts, lower(e.content), e.embedding FROM episodes e
            LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id > ? AND e.role IN ({marques})
            AND {archives}""", (self.max_id, *ROLES)).fetchall()
        import json
        import numpy as np
        for eid, ts, c, emb in rows:
            self.lignes[eid] = (ts, c or "")
            self.max_id = max(self.max_id, eid)
            try:
                v = np.asarray(json.loads(emb or "[]"), dtype=np.float32)
                n = float(np.linalg.norm(v))
                if v.size and n:
                    self.vecteurs[eid] = v / n
            except (ValueError, TypeError):
                pass
            self._mat = None
        self._alias(mem)
        return self

    def _alias(self, mem):
        """(2026-10-22) les alias appris des ratés (rappels_rates.py) : des mots ajoutés au texte que le balayage par
        mots consulte — jamais au souvenir lui-même. Relus quand leur version change."""
        try:
            v = mem.kv_get(ALIAS_VERSION, "") or ""
        except Exception:
            return
        if v == self.alias_v:
            return
        import json
        try:
            a = json.loads(mem.kv_get(ALIAS_CLE, "") or "{}")
            a = {int(k): [str(m).lower() for m in x] for k, x in a.items()} if isinstance(a, dict) else {}
        except (ValueError, TypeError):
            a = {}
        for eid in self.avec_alias | set(a):
            if eid in self.lignes:
                ts, c = self.lignes[eid]
                c = c.split(SEP_ALIAS)[0]
                self.lignes[eid] = (ts, c + (SEP_ALIAS + " ".join(a[eid]) if a.get(eid) else ""))
        self.avec_alias, self.alias_v = {e for e in a if a[e]}, v

    def sens(self, q, exclus, avant_ts, limite=30):
        """[(id, cosinus)] des plus proches par le sens (une multiplication de matrice sur ~4 000 souvenirs)."""
        import numpy as np
        if self._mat is None:
            self._ids = [e for e in self.vecteurs]
            dims = {self.vecteurs[e].size for e in self._ids}
            if len(dims) != 1:
                d = max(dims, key=lambda x: sum(1 for e in self._ids if self.vecteurs[e].size == x)) if dims else 0
                self._ids = [e for e in self._ids if self.vecteurs[e].size == d]
            self._mat = np.stack([self.vecteurs[e] for e in self._ids]) if self._ids else np.zeros((0, 1), np.float32)
        q = np.asarray(q, dtype=np.float32)
        if not len(self._ids) or q.size != self._mat.shape[1] or not np.linalg.norm(q):
            return []
        sims = self._mat @ (q / np.linalg.norm(q))
        ordre = np.argsort(-sims)
        out = []
        for i in ordre:
            eid = self._ids[i]
            if eid in exclus or self.lignes[eid][0] >= avant_ts:
                continue
            out.append((eid, float(sims[i])))
            if len(out) >= limite:
                break
        return out


NOM_VOIX = re.compile(r"\[([^\[\]\d]{2,30})\]")


def noms_entendus(texte):
    """Les voix connues nommées dans la transcription (« [Nora] bonjour ») : ni Ahmed, ni une « voix 2 » anonyme."""
    out = []
    for n in NOM_VOIX.findall(texte or ""):
        n = n.strip()
        if n and n.lower() not in ("ahmed",) and n.lower() not in out:
            out.append(n.lower())
    return out


def mots_cles(texte, maximum=8):
    """Les mots porteurs du message : sans les mots vides, 4 lettres au moins (ou un nombre), du plus long au plus court."""
    vus, out = set(), []
    for m in re.findall(r"[\w'-]+", (texte or "").lower()):
        m = m.strip("'-")
        if m in vus or m in MOTS_VIDES or not (len(m) >= 4 or m.isdigit()):
            continue
        vus.add(m)
        out.append(m)
    return sorted(out, key=len, reverse=True)[:maximum]


def _par_mots(index, mots, exclus, avant_ts, limite=40):
    """{id: score} : chaque mot trouvé pèse son IDF (un mot rare dans la mémoire pèse plus qu'un mot courant)."""
    if not mots or not index.lignes:
        return {}
    total = len(index.lignes)
    scores, rares = {}, {}
    for m in mots:
        ids = [eid for eid, (ts, c) in index.lignes.items() if m in c]
        if not ids or len(ids) >= 400:                       # absent, ou présent partout : ne départage rien
            continue
        idf = math.log(1 + total / len(ids))
        for eid in ids:
            if eid not in exclus and index.lignes[eid][0] < avant_ts:
                scores[eid] = scores.get(eid, 0.0) + idf
                rares[eid] = max(rares.get(eid, 0.0), idf / math.log(1 + total))   # rareté relative (0..1)
    garde = dict(sorted(scores.items(), key=lambda x: -x[1])[:limite])
    _par_mots.rares = {eid: rares[eid] for eid in garde}
    return garde


# (26/10, Ahmed : « balayer large, puis choisir ») 150 candidats par le sens et 100 par les mots au lieu de 30 et 40 :
# gratuit (eval/rappel_large.py : même bruit, +0,7 point de rappel, le temps ne bouge pas) ; la porte reste celle réglée
LIMITE_SENS, LIMITE_MOTS = 150, 100


def candidats(mem, texte, now=None, exclus=(), recent_h=3.0, embed=None, limite=LIMITE_SENS, index=None, limite_mots=None):
    """[(id, score_fusion, sem, mots)] : le balayage large, fusionné par rang. Rien de plus récent que recent_h heures
    (c'est déjà dans la conversation), rien de ce qui a déjà été proposé (exclus)."""
    now = time.time() if now is None else now
    avant_ts = now - recent_h * 3600
    exclus = set(exclus or ())
    if embed is None:
        import embeddings
        embed = embeddings.embed
    index = (index or Index()).rafraichir(mem, now=time.time())
    try:
        sem = {eid: (rang, cos) for rang, (eid, cos) in enumerate(index.sens(embed(texte), exclus, avant_ts, limite))}
    except Exception:
        sem = {}
    mots = _par_mots(index, mots_cles(texte), exclus, avant_ts, limite=limite_mots or LIMITE_MOTS)
    rangs_mots = {eid: i for i, eid in enumerate(mots)}
    fusion = {}
    for eid in set(sem) | set(mots):
        s = 0.0
        if eid in sem:
            s += 1.0 / (K_RRF + sem[eid][0])
        if eid in rangs_mots:
            s += 1.0 / (K_RRF + rangs_mots[eid])
        fusion[eid] = s
    rares = getattr(_par_mots, "rares", {})
    # (2026-10-21, vu au premier essai d'Ahmed : « j'ai un anniversaire » ne retrouvait pas celui de sa fille, noté
    # « fait 6 ans le 21 octobre ») : ce qui porte la DATE DU JOUR remonte (anniversaires, échéances, promesses) ;
    # la conscience fait le lien avec le message
    dates = dates_du_jour(now)
    du_jour = set()
    for eid, (ts, c) in index.lignes.items():
        if eid not in exclus and ts < avant_ts and any(d in c for d in dates):
            du_jour.add(eid)
            fusion.setdefault(eid, 1.0 / (K_RRF + 30))
    # (2026-10-21) une voix CONNUE entendue (son nom dans la transcription) : ce qui la nomme remonte, même si son nom
    # seul ne pèse pas assez pour la porte des mots rares
    noms = noms_entendus(texte)
    avec_nom = {eid for eid in fusion if noms and any(n in index.lignes.get(eid, (0, ""))[1] for n in noms)}
    for n in noms:                                          # et ce qui la nomme sans être dans les deux classements
        for eid, (ts, c) in index.lignes.items():
            if n in c and eid not in exclus and ts < avant_ts and eid not in fusion:
                fusion[eid] = 1.0 / (K_RRF + 30)
                avec_nom.add(eid)
    out = [(eid, s, sem.get(eid, (None, 0.0))[1], mots.get(eid, 0.0),
            "jour" if eid in du_jour else ("voix" if eid in avec_nom else ""), rares.get(eid, 0.0))
           for eid, s in fusion.items()]
    ordre = sorted(out, key=lambda x: -x[1])
    return ordre[:limite] + [x for x in ordre[limite:] if x[4] == "jour"]     # la date du jour n'est jamais coupée


def passe(x, porte_mots=None, porte_sens=None):
    """La porte : au moins un mot RARE en commun (et assez de poids), ou un sens très proche, ou une voix connue
    nommée, ou la date du jour. Plusieurs mots de conversation (« capté », « changer », « content ») ne suffisent plus :
    vu au premier essai d'Ahmed, ils faisaient remonter des échanges sans rapport."""
    sem, mots = x[2], x[3]
    special = x[4] if len(x) > 4 else False
    rare = x[5] if len(x) > 5 else 1.0
    return (special or (mots >= (PORTE_MOTS if porte_mots is None else porte_mots) and rare >= MOT_RARE)
            or sem >= (PORTE_SENS if porte_sens is None else porte_sens))


# (26/10, Ahmed : « montre-lui 200 souvenirs détaillés minimum ; c'est à lui de trier le hors-sujet ») en plus de la liste
# courte (8, au-dessus de la porte), LE DOSSIER DU THÈME : les 200 souvenirs suivants dans l'ordre du balayage (sens + mots),
# SANS porte, quel que soit leur âge, détaillés comme la liste courte ; Hakim trie. Seulement pour un message qui porte
# quelque chose (la liste courte a trouvé, ou au moins 3 mots porteurs) : un « ok » n'ouvre pas de dossier. Mesuré à la
# porte (26/10) : 0,72 → 0,87 de rappel avec ~75 lignes ; sans porte, tout ce que le balayage trouve est là.
# (26/10, 14:21, Ahmed : « 100 souvenirs, pour protéger mon budget de jetons ; on ajuste à l'usage ») et LE TRI À PART :
# le dossier ne va plus dans sa conversation, un Sonnet à part le trie (cockpit, trierSouvenirs) et Hakim ne reçoit que
# les souvenirs gardés, en DÉTAIL (DETAIL caractères). Les mots balaient aussi large que le dossier : mesuré le 26/10
# (eval/rappel_taille.py), le plafond de 100 candidats par les mots coûtait 5 points de rappel à 500 souvenirs.
THEME_CANDIDATS, THEME_MAX = 600, 100
DETAIL = 450

# (26/10, Ahmed : « modulaire et intelligent selon le besoin : pas de temps perdu sur les petits trucs ; s'il s'agit
# d'interactions avec des gens, il doit vraiment réfléchir ; sur des maths en cours, il a déjà dans sa conversation ce qu'il
# faut, sauf demande explicite de chercher profondément ; et il considère d'abord ce qui est déjà dans son espace »)
# LA PROFONDEUR, décidée SANS appel de modèle (quelques millisecondes : le balayage lui-même prend ~60 ms, c'est le tri
# par Sonnet qui coûte ~4 s, et un Sonnet de plus pour décider coûterait autant que le tri) :
#   leger   — la liste courte seule (au-dessus de la porte), aucun tri, aucune attente ;
#   normal  — la liste courte + THEME_MAX souvenirs, triés à part (~4 s) ;
#   profond — la liste courte + THEME_PROFOND souvenirs (mesuré le 26/10 : 96 % des bons gardés à 500), triés à part (~5 s).
THEME_PROFOND = 500
_B = r"(?<![a-z0-9])"
DEMANDE_PROFONDE = re.compile(_B + r"(rappelle[- ]?toi|tu te (rappelles|souviens)|souviens[- ]?toi|cherche (bien|profond|partout|"
                              r"dans ta memoire)|fouille|en profondeur|profondement|la derniere fois|tu m.avais (dit|parle)|"
                              r"on (avait|s.etait) dit|on en avait parle|ta memoire|tes souvenirs|qu.est.ce que tu sais)")
# (vu sur ses 300 derniers messages : « frère / frérot » est sa façon de parler à Hakim, « ta mère / ta maman » c'est
# Claude Code, « j'aimerais » une envie : aucun ne parle de gens)
GENS = re.compile(_B + r"(famille|femme|mari|epou|fille|fils|enfant|bebe|(?<!ta )(?<!ta )(mere|maman)|pere|papa|soeur|cousin|"
                  r"oncle|tante|neveu|niece|ami|amie|pote|copain|copine|collegue|voisin|client|patron|relation|dispute|"
                  r"conflit|fache|amour|triste|tristesse|peur|colere|jalou|blesse|ressen|sentiment|emotion|pardon|confiance|mariage|"
                  r"rencontr|invite|les gens|quelqu.un|rancune|decu|souffr|pleur|heureu|anniversaire|naissance|deces|enterrement)")
TECHNIQUE = re.compile(_B + r"(calcul|equation|formule|derive|integrale|matrice|vecteur|theoreme|demonstr|maths?|mathematique|"
                       r"fonction|variable|code|script|python|javascript|bug|serveur|api|requete|compil|courbe|algorithme|"
                       r"simulation|parametre|commit|github|fichier|terminal|commande|graphe?)")
NOUVEAUTE_MIN, HAUT = 0.3, 30


def profondeur(texte, suite=False, haut=(), espace=()):
    """(niveau, raison) : « profond » sur demande explicite ou quand il s'agit de gens (une personne connue nommée, la
    famille, les émotions, une relation) ; « leger » pour un message court (« ok merci frero »), un sujet technique dans
    une conversation en cours (c'est déjà dans son contexte), ou quand presque tout le haut du balayage est déjà dans son
    espace ; « normal » sinon."""
    t = _plat(texte)
    if DEMANDE_PROFONDE.search(t):
        return "profond", "demande explicite de chercher dans sa mémoire"
    if GENS.search(t) or personnes_nommees(re.sub(r"(?i)\bta (m[eè]re|maman)\b", "", texte or "")):
        return "profond", "il s'agit de gens (personnes, relations, émotions)"
    if len(mots_cles(texte)) < 3:
        return "leger", "message court : la liste courte suffit"
    if suite and TECHNIQUE.search(t):
        return "leger", "sujet technique dans une conversation en cours : c'est déjà dans son contexte"
    haut = list(haut)[:HAUT]
    espace = set(espace or ())
    if suite and haut and espace and sum(1 for i in haut if i not in espace) / len(haut) < NOUVEAUTE_MIN:
        return "leger", "presque tout le haut du balayage est déjà dans son espace de conversation"
    return "normal", "sujet ordinaire"


def _lignes(mem, ids, n, marquer=False):
    """{id: « #id · date · rubrique · extrait »}, l'extrait coupé à n caractères ; marquer : la marque EXTERNE (un
    contenu de tiers, une citation) pour le détail que Hakim reçoit."""
    if not ids:
        return {}
    marques = ",".join("?" * len(ids))
    rows = {r[0]: r for r in mem.db.execute(
        f"SELECT e.id, e.ts, e.content, r.path FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id IN ({marques})", ids)}
    ext = set()
    if marquer:
        import provenance
        ext = provenance.externes(mem.db, list(rows))
    import retractation                             # (26/10) une source rétractée se voit aussi dans le balayage
    ret = retractation.marques(mem.db, list(rows))
    return {i: f"#{i} · {time.strftime('%d/%m/%y', time.localtime(rows[i][1]))}{' · ' + rows[i][3] if rows[i][3] else ''}"
               f"{' · EXTERNE (une citation, pas un fait)' if i in ext else ''} · "
               f"{retractation.marque_texte(ret[i]) if i in ret else ''}"
               f"{' '.join(str(rows[i][2] or '').split())[:n]}" for i in ids if i in rows}


def lignes_courtes(mem, ids, n=90):
    d = _lignes(mem, ids, n)
    return [d[i] for i in ids if i in d]


def rappel(mem, texte, now=None, exclus=(), seuil=SEUIL, lignes_max=LIGNES_MAX, embed=None, index=None, recent_h=3.0,
           suite=False, espace=()):
    """{"lignes": [...], "ids": [...], "scores": [...], "theme": [...], "theme_ids": [...], "details": {id: ligne},
    "profondeur": {niveau, raison}} : la liste courte pour sa conscience et le dossier du thème (à la taille du niveau),
    ou rien. suite : la conversation est en cours ; espace : les souvenirs déjà dans son espace de conversation."""
    t0 = time.time()
    niveau, raison = profondeur(texte, suite=suite)
    taille = THEME_PROFOND if niveau == "profond" else THEME_MAX

    def balayer(n):
        return candidats(mem, texte, now=now, exclus=exclus, embed=embed, index=index, recent_h=recent_h,
                         limite=max(THEME_CANDIDATS, n + LIGNES_MAX), limite_mots=max(LIMITE_MOTS, n))
    larges = balayer(taille)
    if niveau == "normal":
        niveau, raison = profondeur(texte, suite=suite, haut=[x[0] for x in larges][:taille], espace=espace)
    if niveau == "leger":
        taille = 0
    prof = {"niveau": niveau, "raison": raison}
    tous = [x for x in larges if x[1] >= seuil and passe(x)]
    # ce qui porte la date du jour : 3 au plus (une fois par conversation), le reste de la place au message
    jour = [x for x in tous if len(x) > 4 and x[4] == "jour"][:JOUR_MAX]
    c = (jour + [x for x in tous if not (len(x) > 4 and x[4] == "jour")])[:lignes_max]
    if not c:
        if len(mots_cles(texte)) >= 3 and taille:            # rien au-dessus de la porte, mais un vrai message : le dossier
            theme = [x[0] for x in larges][:taille]
            return {"lignes": [], "ids": [], "scores": [], "theme": lignes_courtes(mem, theme, 160), "theme_ids": theme,
                    "details": _lignes(mem, theme, DETAIL, marquer=True), "profondeur": prof,
                    "ms": round(1000 * (time.time() - t0))}
        return {"lignes": [], "ids": [], "scores": [], "profondeur": prof, "ms": round(1000 * (time.time() - t0))}
    import provenance
    ids = [x[0] for x in c]
    jour = {x[0] for x in c if len(x) > 4 and x[4] == "jour"}
    externes = provenance.externes(mem.db, ids)
    marques = ",".join("?" * len(ids))
    rows = {r[0]: r for r in mem.db.execute(
        f"SELECT e.id, e.ts, e.content, r.path FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id IN ({marques})", ids)}
    lignes = []
    for eid in ids:
        if eid not in rows:
            continue
        _i, ts, content, path = rows[eid]
        extrait = " ".join(str(content or "").split())[:160]
        lignes.append(f"#{eid} · {time.strftime('%d/%m/%Y', time.localtime(ts))}{' · ' + path if path else ''}"
                      f"{' · porte la date du jour' if eid in jour else ''}"
                      f"{' · EXTERNE (une citation, pas un fait)' if eid in externes else ''} · {extrait}")
    pris = set(ids)
    theme = [x[0] for x in larges if x[0] not in pris][:taille]
    return {"lignes": lignes, "ids": ids, "scores": [round(x[1], 4) for x in c], "theme": lignes_courtes(mem, theme, 160),
            "theme_ids": theme, "details": _lignes(mem, ids + theme, DETAIL, marquer=True), "profondeur": prof,
            "ms": round(1000 * (time.time() - t0))}


# (25/10, Ahmed : « balayer aussi le carnet d'erreurs avant chaque réponse, TOUTES les erreurs pertinentes, pas 2-3 ») le
# carnet passe au même balayage : le sens (model2vec) et les mots du message rares dans le carnet (IDF), score = cosinus
# + 0,35 × mots ; tout ce qui passe la porte remonte, sans nombre fixe, sous un garde-fou de taille. Porte réglée le 26/10
# sur des messages types : « une barre de progression pour ton calcul » sort les 5 erreurs de barre (≥ 0,80), « t'es
# fatigué après ce live » celle du 25/10 (0,93), « bonne nuit » celle du repos imposé (0,65) ; « salam ça va » rien (0,32).
PORTE_ERREURS = 0.65
POIDS_MOTS_ERREURS = 0.35
ERREURS_MAX, ERREURS_CARACTERES_MAX = 12, 3500


def _plat(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()


class IndexErreurs:
    """Le carnet d'erreurs en mémoire : relu (et ses nouvelles lignes vectorisées) quand le fichier change."""
    def __init__(self, fichier=None):
        self.fichier, self.signature, self.items, self.mat, self.mots = fichier, None, [], None, []

    def rafraichir(self, embed):
        import numpy as np
        import carnet
        f = Path(self.fichier or carnet.ERREURS)
        try:
            sig = (f.stat().st_mtime, f.stat().st_size)
        except OSError:
            self.items, self.mat, self.mots = [], None, []
            return self
        if sig != self.signature:
            self.items = [e for e in carnet.erreurs(f) if e.get("quoi")]
            textes = [f"{e.get('quoi', '')} {e.get('correction', '')}" for e in self.items]
            m = np.array([embed(t) for t in textes], dtype=np.float32) if textes else np.zeros((0, 1), np.float32)
            n = np.linalg.norm(m, axis=1, keepdims=True) if len(m) else None
            self.mat = m / np.where(n == 0, 1, n) if len(m) else m
            self.mots = [set(re.findall(r"[a-z0-9]{4,}", _plat(t))) for t in textes]
            self.signature = sig
        return self


def erreurs_pertinentes(texte, embed=None, index=None, exclus=()):
    """{"lignes", "ids", "scores"} : toutes les erreurs du carnet qui passent la porte, de la plus proche à la moins
    proche, sans celles déjà dites dans la conversation (exclus), au plus ERREURS_MAX et ERREURS_CARACTERES_MAX."""
    import numpy as np
    if embed is None:
        import embeddings
        embed = embeddings.embed
    index = (index or IndexErreurs()).rafraichir(embed)
    if not index.items:
        return {"lignes": [], "ids": [], "scores": []}
    q = np.asarray(embed(texte), dtype=np.float32)
    if not q.size or q.size != index.mat.shape[1] or not np.linalg.norm(q):
        return {"lignes": [], "ids": [], "scores": []}
    cos = index.mat @ (q / np.linalg.norm(q))
    n = len(index.items)
    mots = {_plat(w) for w in mots_cles(texte)}
    idf = {w: math.log((n + 1) / (1 + sum(w in d for d in index.mots))) for w in mots}
    norme = math.log(n + 1) or 1.0
    exclus = set(exclus or ())
    scores = sorted(((float(cos[i]) + POIDS_MOTS_ERREURS * sum(idf[w] for w in mots if w in index.mots[i]) / norme, i)
                     for i in range(n) if str(index.items[i].get("id")) not in exclus), reverse=True)
    lignes, ids, gardes, taille = [], [], [], 0
    for s, i in scores:
        if s < PORTE_ERREURS or len(lignes) >= ERREURS_MAX:
            break
        e = index.items[i]
        quand = time.strftime("%d/%m", time.localtime(float(e.get("ts") or 0)))
        ligne = (f"{quand} · {'de mauvaise foi' if e.get('colonne') == 'disquette' else 'de bonne foi'} · "
                 f"{' '.join(str(e.get('quoi', '')).split())[:260]} → correction : {' '.join(str(e.get('correction', '')).split())[:260]}")
        if taille + len(ligne) > ERREURS_CARACTERES_MAX and lignes:
            break
        lignes.append(ligne); ids.append(str(e.get("id"))); gardes.append(round(s, 3)); taille += len(ligne)
    return {"lignes": lignes, "ids": ids, "scores": gardes}


# (26/10, Ahmed : « le balayage est trop étroit » ; à 13:17 Hakim a nié devant Nora ce qu'il avait dit d'elle à 08:37) quand
# un message NOMME une personne connue (une voix enregistrée, ou une voix nommée dans la transcription), une section « ce que
# tu sais d'elle » : ses souvenirs les plus récents (même du jour) et les passages du journal brut du jour qui la nomment.
VOIX_CONNUES = Path.home() / "AIOS" / "jarvis" / "voix-connues.json"
JOURNAL_DU_JOUR = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
PERSONNE_SOUVENIRS, PERSONNE_JOURNAL = 4, 3


def personnes_nommees(texte, voix=None):
    """Les personnes connues nommées dans le message (leur nom, ou une voix nommée « [Nora] ») ; jamais Ahmed."""
    noms = []
    try:
        noms = [str(v.get("nom") or "") for v in json.loads(Path(voix or VOIX_CONNUES).read_text())]
    except (OSError, ValueError, AttributeError):
        pass
    plat_t = " " + _plat(texte) + " "
    out, vus = [], set()
    for n in noms:                                           # leur nom tel qu'enregistré (« Nora », « Légendaire »)
        pn = _plat(n).strip()
        if pn and pn != "ahmed" and pn not in vus and re.search(r"(?<![a-z0-9])" + re.escape(pn) + r"(?![a-z0-9])", plat_t):
            out.append(n.strip()); vus.add(pn)
    for n in noms_entendus(texte):                           # une voix nommée dans la transcription, hors de la liste
        if _plat(n) not in vus:
            out.append(n); vus.add(_plat(n))
    return out[:3]


def ce_que_je_sais(mem, nom, now=None, journal=None):
    """[lignes] : souvenirs (les plus récents d'abord) et passages du journal du jour qui nomment cette personne."""
    now = time.time() if now is None else now
    lignes = []
    try:
        rows = mem.db.execute("SELECT id, ts, content FROM episodes WHERE content LIKE ? ORDER BY ts DESC LIMIT ?",
                              (f"%{nom}%", PERSONNE_SOUVENIRS)).fetchall()
    except Exception:
        rows = []
    for eid, ts, c in rows:
        lignes.append(f"souvenir #{eid} · {time.strftime('%d/%m %H:%M', time.localtime(ts))} · {' '.join(str(c).split())[:180]}")
    debut_jour = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
    trouves = []
    try:
        with open(journal or JOURNAL_DU_JOUR, encoding="utf-8") as f:
            for l in f:
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                t = (o.get("ts") or 0) / 1000
                if debut_jour <= t <= now - 60 and _plat(nom) in _plat(o.get("texte", "")):
                    trouves.append((t, o.get("qui"), " ".join(str(o.get("texte", "")).split())))
    except OSError:
        pass
    for t, qui, x in trouves[-PERSONNE_JOURNAL:][::-1]:
        lignes.append(f"journal · {time.strftime('%H:%M', time.localtime(t))} · {'Ahmed' if qui == 'ahmed' else 'toi'} : « {x[:220]} »")
    return lignes


def serveur(entree=None, sortie=None):
    """Le processus que le cockpit garde ouvert : une requête JSON par ligne {texte, exclus, now}, une réponse par
    ligne. Le modèle d'embeddings et la base restent chargés : quelques dizaines de millisecondes par message."""
    import json
    import sys
    from memory import Memory
    entree, sortie = entree or sys.stdin, sortie or sys.stdout
    mem = Memory()
    index, index_erreurs = Index(), IndexErreurs()
    for ligne in entree:
        try:
            q = json.loads(ligne)
            texte = str(q.get("texte") or "")[:4000]
            # (26/10) au 1er message d'une conversation, rien n'est encore dans son contexte : les souvenirs récents comptent aussi
            r = rappel(mem, texte, now=q.get("now"), exclus=[int(x) for x in (q.get("exclus") or [])][-3000:], index=index,
                       recent_h=0.0 if q.get("demarrage") else 3.0, suite=not q.get("demarrage"),
                       espace={int(x) for x in (q.get("espace") or [])[-5000:]})
            try:
                personnes = {n: ce_que_je_sais(mem, n) for n in personnes_nommees(texte)
                             if n not in set(q.get("exclus_personnes") or [])}
                r["personnes"] = {n: l for n, l in personnes.items() if l}
            except Exception as ex:
                r["erreur_personnes"] = f"{type(ex).__name__}: {ex}"[:200]
            try:
                e = erreurs_pertinentes(texte, index=index_erreurs, exclus=[str(x) for x in (q.get("exclus_erreurs") or [])][:500])
                r.update(erreurs=e["lignes"], erreurs_ids=e["ids"], erreurs_scores=e["scores"])
            except Exception as ex:
                r["erreur_carnet"] = f"{type(ex).__name__}: {ex}"[:200]
            if q.get("demarrage"):                     # (26/10) le 1er message d'une conversation : ses carnets à règles
                try:
                    import carnets_regles
                    r["carnets"] = carnets_regles.demarrage()[:3000]
                except Exception:
                    pass
        except Exception as e:
            r = {"lignes": [], "ids": [], "erreur": f"{type(e).__name__}: {e}"[:200]}
        sortie.write(json.dumps(r, ensure_ascii=False) + "\n")
        sortie.flush()
