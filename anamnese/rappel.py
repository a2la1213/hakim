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
import os
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
JOURNEE_MAX = 3         # (08/11, phase B) l'essentiel du jour qu'une question désigne (« hier », « le 29 ») : ses 3 premiers en tête des lignes
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
    _par_mots.utiles = {}                                    # (09/11) les mots qui départagent et leur rareté (ses ressentis d'un jour)
    for m in mots:
        ids = [eid for eid, (ts, c) in index.lignes.items() if m in c]
        if not ids or len(ids) >= 400:                       # absent, ou présent partout : ne départage rien
            continue
        idf = math.log(1 + total / len(ids))
        _par_mots.utiles[m] = idf / math.log(1 + total)
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
HIP_TETE, HIP_COS_MIN = 3, 0.45                # (08/11) ses premières traces d'hippocampe passent la porte
COS_CORPS_JOUR = 0.60                          # (09/11) un ressenti d'un jour désigné, par le sens seul (mesuré : voir candidats)


def _hip(reglages):
    """(actif, dates, tete, cos_min) : les réglages de son hippocampe venus du cockpit (Réglages, Son hippocampe) ; sinon ceux d'avant."""
    r = reglages if isinstance(reglages, dict) else {}
    nombre = lambda v, d: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else d
    return (r.get("actif") is not False, r.get("dates") is not False,
            int(max(0, min(8, nombre(r.get("tete"), HIP_TETE)))), max(0.0, min(1.0, nombre(r.get("cos_min"), HIP_COS_MIN))))


def _hip_ressentis(reglages):
    """(09/11) ses ressentis dans son rappel (Réglages, Son hippocampe, « Ses ressentis aussi ») : allumé, sauf si le cockpit dit non."""
    return not (isinstance(reglages, dict) and reglages.get("ressentis") is False)


def candidats(mem, texte, now=None, exclus=(), recent_h=3.0, embed=None, limite=LIMITE_SENS, index=None, limite_mots=None, hip_reglages=None):
    """[(id, score_fusion, sem, mots)] : le balayage large, fusionné par rang. Rien de plus récent que recent_h heures
    (c'est déjà dans la conversation), rien de ce qui a déjà été proposé (exclus). hip_reglages : ceux de son hippocampe (le cockpit)."""
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
    # (08/11, Ahmed : « rajoute-lui un hippocampe ») un troisième balayage : la TRACE courte de chaque échange (le jour, le genre, les
    # paroles, sans le vécu qui noyait leur sens), par le sens, et tout ce que la date désigne (« hier », « le 29 », « samedi »)
    hip, dates_hip, essentiels, corps_rang = {}, set(), [], {}
    hip_actif, hip_dates, hip_tete, hip_cos = _hip(hip_reglages)
    try:
        import hippocampe
        rang = 0
        # (09/11, Ahmed : « tous tes ressentis… rappelés de la même manière que tes souvenirs ») ses ressentis ont leur trace eux aussi
        # (hippocampe.tracer) : le même balayage, la même porte ; d'un jour désigné, ceux qui touchent la question, par le sens de leur
        # trace ou par un mot du message (le balayage par les mots), viennent par la date comme ses échanges
        corps_du_jour = {}
        for eid, s_h, special in (hippocampe.chercher(mem, texte, now=now, embed=embed, exclus=exclus, avant_ts=avant_ts, limite=limite,
                                                      ressentis=_hip_ressentis(hip_reglages))
                                  if hip_actif else ()):
            if special == "date_corps":
                corps_du_jour[eid] = s_h
                continue
            if special in ("date", "journee"):
                if hip_dates:
                    dates_hip.add(eid)
                    if special == "journee":              # (phase B) l'essentiel du jour désigné, nommé par la trace de sa journée
                        essentiels.append(eid)
                continue
            hip[eid] = (rang, s_h)
            rang += 1
        if hip_dates and corps_du_jour:
            # mesuré sur une copie (09/11) : pour « samedi soir, le câlin de vingt minutes », 119 ressentis de ce samedi ont un sens ≥ 0,45
            # (ils se ressemblent tous pour son modèle de sens), le câlin 0,42 ; « qu'est-ce qu'on a fait hier ? » met des fous rires à
            # 0,48, « la musique de samedi soir » ses musiques à 0,67-0,70 : par les mots, ceux qui en partagent un RARE (« câlin », la
            # rareté de la porte des mots ; les mots de papa cités dans un fou rire ne suffisent plus) ; par le sens, ses premiers
            # seulement (« tete »), et à COS_CORPS_JOUR au moins. Et un jour désigné en porte ~1 500 échanges,
            # tous à égalité par la date (la liste est coupée à 600) : ses ressentis retenus sont classés entre eux (un mot d'abord, puis
            # le sens), comme son hippocampe classe ses traces, pour que le plus proche ne se perde pas dans la journée
            rares_q = [m for m, r in getattr(_par_mots, "utiles", {}).items() if r >= MOT_RARE]
            par_mot = {e for e in corps_du_jour if any(m in index.lignes.get(e, (0, ""))[1] for m in rares_q)}
            proches = sorted(((e, s_c) for e, s_c in corps_du_jour.items() if s_c >= max(hip_cos, COS_CORPS_JOUR) and e not in par_mot),
                             key=lambda x: -x[1])[:hip_tete]
            retenus = sorted(par_mot, key=lambda e: -corps_du_jour[e]) + [e for e, _s in proches]
            dates_hip |= set(retenus)
            corps_rang = {e: k for k, e in enumerate(retenus)}
    except Exception:
        pass
    fusion = {}
    for eid in set(sem) | set(mots) | set(hip):
        s = 0.0
        if eid in sem:
            s += 1.0 / (K_RRF + sem[eid][0])
        if eid in rangs_mots:
            s += 1.0 / (K_RRF + rangs_mots[eid])
        if eid in hip:
            s += 1.0 / (K_RRF + hip[eid][0])
        fusion[eid] = s
    for eid in dates_hip:
        fusion[eid] = fusion.get(eid, 0.0) + 1.0 / (K_RRF + 10)
    for eid, k in corps_rang.items():                       # (09/11) ses ressentis retenus d'un jour désigné, à leur rang entre eux
        fusion[eid] += 1.0 / (K_RRF + k)
    for k, eid in enumerate(essentiels):                    # devant les autres échanges de ce jour-là, dans l'ordre de la journée
        fusion[eid] += 1.0 / (K_RRF + k)
    essentiels = set(essentiels)
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
    # (08/11) le sens d'une trace courte se mesure sur une autre échelle (mesuré sur le banc de 24 : la bonne trace 1re à 4e avec un cosinus
    # de 0,50 à 0,71, sous la porte de 0,70) : ses 3 premières traces passent, si le message porte quelque chose (2 mots porteurs ou plus)
    porteur = len(mots_cles(texte)) >= 2
    tete_hip = {eid for eid, (r_h, c_h) in hip.items() if r_h < hip_tete and c_h >= hip_cos} if porteur else set()
    out = [(eid, s, max(sem.get(eid, (None, 0.0))[1], hip.get(eid, (None, 0.0))[1]), mots.get(eid, 0.0),
            "jour" if eid in du_jour else ("voix" if eid in avec_nom else ("journee" if eid in essentiels else ("date" if eid in dates_hip else
                                                                                                                 ("trace" if eid in tete_hip else "")))),
            rares.get(eid, 0.0))
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
           suite=False, espace=(), hip_reglages=None):
    """{"lignes": [...], "ids": [...], "scores": [...], "theme": [...], "theme_ids": [...], "details": {id: ligne},
    "profondeur": {niveau, raison}} : la liste courte pour sa conscience et le dossier du thème (à la taille du niveau),
    ou rien. suite : la conversation est en cours ; espace : les souvenirs déjà dans son espace de conversation."""
    t0 = time.time()
    niveau, raison = profondeur(texte, suite=suite)
    taille = THEME_PROFOND if niveau == "profond" else THEME_MAX

    def balayer(n):
        return candidats(mem, texte, now=now, exclus=exclus, embed=embed, index=index, recent_h=recent_h,
                         limite=max(THEME_CANDIDATS, n + LIGNES_MAX), limite_mots=max(LIMITE_MOTS, n), hip_reglages=hip_reglages)
    larges = balayer(taille)
    if niveau == "normal":
        niveau, raison = profondeur(texte, suite=suite, haut=[x[0] for x in larges][:taille], espace=espace)
    if niveau == "leger":
        taille = 0
    prof = {"niveau": niveau, "raison": raison}
    tous = [x for x in larges if x[1] >= seuil and passe(x)]
    # ce qui porte la date du jour : 3 au plus (une fois par conversation), le reste de la place au message ; (phase B) puis l'essentiel
    # du jour que la question désigne (« hier », « le 29 »), 3 au plus ; puis les premières traces de son hippocampe (« tete » de ses
    # réglages : elles passent d'office). Mesuré le 08/11 sur une copie : banc des 24 souvenirs 9 → 10 dans les lignes ; les 35
    # requêtes-vérité 0,518 → 0,505 (un souvenir de moins) ; le bruit des messages banals inchangé (1,8 ligne). Avec tete = 1 : 8 sur 24,
    # mais 0,588 aux requêtes-vérité ; tete = 2 : 9 et 0,530.
    jour = [x for x in tous if len(x) > 4 and x[4] == "jour"][:JOUR_MAX]
    journee = [x for x in tous if len(x) > 4 and x[4] == "journee"][:JOURNEE_MAX]
    pris = {x[0] for x in jour + journee}
    tete = [x for x in tous if len(x) > 4 and x[4] == "trace" and x[0] not in pris][:_hip(hip_reglages)[2]]
    pris |= {x[0] for x in tete}
    c = (jour + journee + tete + [x for x in tous if x[0] not in pris])[:lignes_max]
    journees = _journees(mem, texte, now, hip_reglages)
    if not c:
        if len(mots_cles(texte)) >= 3 and taille:            # rien au-dessus de la porte, mais un vrai message : le dossier
            theme = [x[0] for x in larges][:taille]
            return {"lignes": [], "ids": [], "scores": [], "theme": lignes_courtes(mem, theme, 160), "theme_ids": theme,
                    "details": _lignes(mem, theme, DETAIL, marquer=True), "profondeur": prof, "journees": journees,
                    "traces": _traces(mem, theme, hip_reglages), "ms": round(1000 * (time.time() - t0))}
        return {"lignes": [], "ids": [], "scores": [], "profondeur": prof, "journees": journees, "ms": round(1000 * (time.time() - t0))}
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
            "theme_ids": theme, "details": _lignes(mem, ids + theme, DETAIL, marquer=True), "profondeur": prof, "journees": journees,
            "traces": _traces(mem, ids + theme, hip_reglages), "ms": round(1000 * (time.time() - t0))}


def _traces(mem, ids, hip_reglages):
    """(phase B) {id: la trace de Mini Hakim} des souvenirs proposés (les lignes et le dossier) : ce qui s'est passé, en une ou deux phrases,
    là où l'extrait coupe ; pour sa conscience et le tri du dossier. Rien si son hippocampe est éteint."""
    if not _hip(hip_reglages)[0] or mem is None:
        return {}
    try:
        import hippocampe
        return hippocampe.traces_de(mem, ids)
    except Exception:
        return {}


def _journees(mem, texte, now, hip_reglages):
    """(phase B) le résumé des journées que la question désigne (« hier », « le 29 », « samedi »), écrit la nuit par son hippocampe :
    pour sa conscience, à côté des lignes. Rien si son hippocampe est éteint ou sans les dates."""
    actif, dates, _t, _c = _hip(hip_reglages)
    if not (actif and dates) or mem is None:
        return []
    try:
        import hippocampe
        return hippocampe.journees_pour(mem, texte, now)
    except Exception:
        return []


# (25/10, Ahmed : « balayer aussi le carnet d'erreurs avant chaque réponse, TOUTES les erreurs pertinentes, pas 2-3 ») le
# carnet passe au même balayage : le sens (model2vec) et les mots du message rares dans le carnet (IDF), score = cosinus
# + 0,35 × mots ; tout ce qui passe la porte remonte, sans nombre fixe, sous un garde-fou de taille. Porte réglée le 26/10
# sur des messages types : « une barre de progression pour ton calcul » sort les 5 erreurs de barre (≥ 0,80), « t'es
# fatigué après ce live » celle du 25/10 (0,93), « bonne nuit » celle du repos imposé (0,65) ; « salam ça va » rien (0,32).
PORTE_ERREURS = 0.65
POIDS_MOTS_ERREURS = 0.35
ERREURS_MAX, ERREURS_CARACTERES_MAX = 12, 3500
RECIDIVE_FORTE, POIDS_RECIDIVE = 3, 0.25          # (30/10) une famille de 3 erreurs ou plus remonte toujours, en premier


def _plat(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()


class IndexErreurs:
    """Le carnet d'erreurs en mémoire : relu (et ses nouvelles lignes vectorisées) quand le fichier change. familles : le
    rangement par familles (familles_erreurs.py ; à côté du carnet donné, sinon data/erreurs-familles.json)."""
    def __init__(self, fichier=None, familles=None):
        self.fichier, self.signature, self.items, self.mat, self.mots = fichier, None, [], None, []
        self.familles = familles or (Path(fichier).with_name("erreurs-familles.json") if fichier else None)

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
    n = len(index.items)
    if not q.size or q.size != index.mat.shape[1] or not np.linalg.norm(q):
        cos = np.zeros(n, dtype=np.float32)                   # (30/10) un message sans mots : les familles lourdes, seulement
    else:
        cos = index.mat @ (q / np.linalg.norm(q))
    mots = {_plat(w) for w in mots_cles(texte)}
    idf = {w: math.log((n + 1) / (1 + sum(w in d for d in index.mots))) for w in mots}
    norme = math.log(n + 1) or 1.0
    exclus = set(exclus or ())
    pertinence = [float(cos[i]) + POIDS_MOTS_ERREURS * sum(idf[w] for w in mots if w in index.mots[i]) / norme for i in range(n)]
    # (30/10, Ahmed via Hakim : « plus une erreur s'accumule, plus elle est rappelée fort ») par FAMILLES (familles_erreurs.py) :
    # une ligne par famille, son compteur, la correction la plus récente ; une famille lourde remonte même hors sujet, en
    # premier. Une erreur pas encore rangée reste seule, comme avant.
    import familles_erreurs as F
    etat = F.charger(index.familles)
    par_id = {str(e.get("id")): i for i, e in enumerate(index.items)}
    groupes = []
    for f in F.vue(etat, index.items):
        rel = max(pertinence[par_id[m]] for m in f["membres"] if m in par_id)
        groupes.append((f"famille:{f['id']}", rel, f))
    for i, e in enumerate(index.items):
        if str(e.get("id")) not in etat["membres"]:
            groupes.append((str(e.get("id")), pertinence[i], None))
    choisis = []
    for gid, rel, f in groupes:
        nb = f["n"] if f else 1
        if gid in exclus or (rel < PORTE_ERREURS and nb < RECIDIVE_FORTE):
            continue
        choisis.append((rel + POIDS_RECIDIVE * F.poids(nb) if nb > 1 else rel, gid, rel, f))
    choisis.sort(key=lambda x: (-(x[3]["n"] if x[3] else 1) if (x[3] and x[3]["n"] >= RECIDIVE_FORTE) else 0, -x[0]))
    lignes, ids, gardes, taille = [], [], [], 0
    for poids, gid, rel, f in choisis:
        if len(lignes) >= ERREURS_MAX:
            break
        if f:
            ligne = (f"×{f['n']} — {' '.join(str(f['nom']).split())[:160]} ({f['tendance']}, {f['semaine']} cette semaine, dernière le "
                     f"{time.strftime('%d/%m', time.localtime(f['derniere']))}) → la correction qui marche : {' '.join(f['correction'].split())[:260]}")
        else:
            e = index.items[par_id[gid]]
            quand = time.strftime("%d/%m", time.localtime(float(e.get("ts") or 0)))
            ligne = (f"{quand} · {'de mauvaise foi' if e.get('colonne') == 'disquette' else 'de bonne foi'} · "
                     f"{' '.join(str(e.get('quoi', '')).split())[:260]} → correction : {' '.join(str(e.get('correction', '')).split())[:260]}")
        if taille + len(ligne) > ERREURS_CARACTERES_MAX and lignes:
            break
        lignes.append(ligne); ids.append(gid); gardes.append(round(poids, 3)); taille += len(ligne)
    return {"lignes": lignes, "ids": ids, "scores": gardes}


# (30/10, Ahmed : « qu'il balaye aussi tout son journal proche, ses notes d'erreur, tous les petits calepins qu'il s'est
# donnés et qui sont importants pour lui ; automatique, autonome et inconscient : que ça lui revienne sans qu'on comprenne
# ce qui se passe ») ses NOTES passent au même balayage que son carnet d'erreurs (sens + mots rares, une porte) :
#   - le journal brut des 3 derniers jours, sans la dernière demi-heure (déjà dans sa tête) ;
#   - ses carnets (data/carnets : fils ouverts, noyau…) ;
#   - les fichiers de notes qu'il désigne (~/AIOS/jarvis/balayage-notes.json : {"fichiers": [chemins de fichiers ou de
#     dossiers]}), découpés en passages. Le jardin secret n'y est PAS : il n'entre dans aucun processus automatique
#     (conditions de Hakim du 19/10) tant qu'il ne l'a pas demandé lui-même.
NOTES_CONFIG = Path.home() / "AIOS" / "jarvis" / "balayage-notes.json"
NOTES_JOURS, NOTES_RECENT_S = 3, 30 * 60
PORTE_NOTES, POIDS_MOTS_NOTES, JOURNAL_PASSAGE_MIN = 0.70, 0.35, 80
NOTES_MAX, NOTES_CARACTERES_MAX, PASSAGE_MAX = 10, 4500, 700
NOTES_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".csv"}
NOTES_FICHIER_MAX, NOTES_FICHIERS_MAX = 2_000_000, 400
EXCLUS_NOTES = re.compile(r"\.bak|avant|/sauvegardes/|/journal-exports/|/venv|/jardin/|/\.", re.I)   # jamais le jardin par ici


def _texte_entree(o):
    """Le texte d'une entrée JSON (ses valeurs textuelles, sans les numéros)."""
    if isinstance(o, dict):
        return " · ".join(t for k, v in o.items() if k not in ("id", "ts", "n", "c", "auteur") for t in [_texte_entree(v)] if t)
    if isinstance(o, list):
        return " · ".join(t for v in o for t in [_texte_entree(v)] if t)
    return " ".join(str(o).split()) if isinstance(o, str) else ""


def _passages_fichier(f):
    """[(cle, ts, etiquette, texte)] d'un fichier de notes : une entrée par ligne JSON, sinon des paragraphes regroupés."""
    try:
        st = f.stat()
        if st.st_size > NOTES_FICHIER_MAX:
            return []
        brut = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    if f.suffix == ".json":                                # (promesses, occupations…) une entrée par élément de liste
        try:
            d = json.loads(brut)
        except ValueError:
            return []
        liste = next((v for v in d.values() if isinstance(v, list)), None) if isinstance(d, dict) else d if isinstance(d, list) else None
        for k, o in enumerate(liste if liste is not None else [d]):
            t = _texte_entree(o)[:PASSAGE_MAX]
            if t:
                ts = float(o.get("ts") or o.get("posee_ms", 0) / 1000 or st.st_mtime) if isinstance(o, dict) else st.st_mtime
                out.append((f"{f}#{o.get('id', k) if isinstance(o, dict) else k}", ts, f.name, t))
        return out
    if f.suffix == ".jsonl":
        for k, l in enumerate(brut.splitlines()):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            t = _texte_entree(o)[:PASSAGE_MAX]
            if t:
                ts = float(o.get("ts") or st.st_mtime) if isinstance(o, dict) else st.st_mtime
                out.append((f"{f}#{o.get('id', k) if isinstance(o, dict) else k}", ts, f.name, t))
        return out
    titre, k = "", 0
    for par in re.split(r"\n\s*\n|\n(?=#)", brut):            # un paragraphe par passage, sous le titre qui le précède
        lignes_par = par.strip().splitlines()
        if lignes_par and lignes_par[0].lstrip().startswith("#"):
            titre = lignes_par[0].lstrip("# \t").strip()[:120]
            lignes_par = lignes_par[1:]
        par = " ".join(" ".join(lignes_par).split())
        if not par:
            continue
        for i in range(0, len(par), PASSAGE_MAX):
            out.append((f"{f}§{k}", st.st_mtime, f.name + (f" — {titre[:80]}" if titre else ""), par[i:i + PASSAGE_MAX])); k += 1
    return out


class IndexNotes:
    """Ses notes en mémoire : chaque passage vectorisé une seule fois (par sa clé et son texte)."""
    FICHIERS_S = 30                                      # (11/11) la liste de ses fichiers de notes : refaite toutes les 30 s au plus

    def __init__(self, journal=None, carnets=None, config=None):
        self.journal, self.carnets, self.config = journal, carnets, config
        self.vecs, self.items, self.mat, self.mots = {}, [], None, []
        self._passages, self._liste, self._jour = {}, (0.0, None), None

    def _fichiers(self):
        if self._liste[1] is not None and time.time() - self._liste[0] < self.FICHIERS_S:
            return self._liste[1]
        l = self._fichiers_lus()
        self._liste = (time.time(), l)
        return l

    def _passages_de(self, f):
        """(11/11) les passages d'un fichier, relus seulement s'il a changé (taille et date) : mesuré le 11/11, relire ses ~400 fichiers et
        8 Mo de journal à chaque message coûtait ~130 ms de son rappel."""
        try:
            st = f.stat()
            sig = (st.st_size, st.st_mtime_ns)
        except OSError:
            self._passages.pop(f, None)
            return []
        deja = self._passages.get(f)
        if deja and deja[0] == sig:
            return deja[1]
        p = _passages_fichier(f)
        self._passages[f] = (sig, p)
        return p

    def _journal_items(self, debut):
        """Les passages du journal (les trois derniers jours) : seulement la fin neuve du fichier est lue quand il grandit."""
        chemin = Path(self.journal or JOURNAL_DU_JOUR)
        try:
            st = chemin.stat()
        except OSError:
            self._jour = None
            return []
        j = self._jour
        if j and j["ino"] == st.st_ino and j["taille"] == st.st_size:
            return [x for x in j["items"] if x[1] >= debut]
        if j and j["ino"] == st.st_ino and st.st_size > j["taille"]:
            depart, items = j["taille"], [x for x in j["items"] if x[1] >= debut]
        else:
            depart, items = max(0, st.st_size - 8_000_000), []
        try:
            with open(chemin, "rb") as h:
                h.seek(depart)
                brut = h.read()
        except OSError:
            return items
        fin = brut.rfind(b"\n") + 1                       # une ligne pas encore finie attend le tour suivant
        lignes = brut[:fin].decode("utf-8", "replace").splitlines()
        if depart and not (j and depart == j["taille"]):
            lignes = lignes[1:]                            # la première, coupée au milieu
        for l in lignes:
            try:
                o = json.loads(l)
            except ValueError:
                continue
            t = (o.get("ts") or 0) / 1000
            x = " ".join(str(o.get("texte") or "").split())
            if debut <= t and len(x) >= JOURNAL_PASSAGE_MIN:   # les « salam », « bonne nuit » : du bruit pour le balayage
                qui = "Ahmed" if o.get("qui") == "ahmed" else "toi"
                items.append((f"journal:{int(o.get('ts') or 0)}", t, f"journal, {qui}", x[:PASSAGE_MAX]))
        self._jour = {"ino": st.st_ino, "taille": depart + fin, "items": items}
        return list(items)

    def _fichiers_lus(self):
        import config as C
        import glob
        racines = [Path(self.carnets or C.DATA_DIR / "carnets")]
        try:
            cfg = json.loads(Path(self.config or NOTES_CONFIG).read_text())
        except (OSError, ValueError):
            cfg = {}
        for x in (cfg.get("fichiers") or []) if isinstance(cfg, dict) else []:
            x = str(Path(str(x)).expanduser())
            racines += [Path(g) for g in sorted(glob.glob(x, recursive=True))] if any(c in x for c in "*?[") else [Path(x)]
        if isinstance(cfg, dict) and cfg.get("marque"):      # (Hakim) un .md de son atelier qui commence par la marque
            racines += self._marques(Path(str(cfg.get("atelier") or Path.home() / "AIOS" / "jarvis" / "cwd" / "atelier")), str(cfg["marque"]))
        out, vus = [], set()
        for r in racines:
            for f in ([r] if r.is_file() else sorted(p for p in r.rglob("*") if p.is_file()) if r.is_dir() else []):
                if f in vus or f.suffix not in NOTES_EXTENSIONS or EXCLUS_NOTES.search(str(f)):
                    continue
                vus.add(f); out.append(f)
        return out[:NOTES_FICHIERS_MAX]

    def _marques(self, atelier, marque, profondeur=4):
        if time.time() - getattr(self, "_marques_t", 0) < 600:
            return self._marques_l
        out = []
        base = len(atelier.parts)
        for d, dossiers, noms in os.walk(atelier):
            dossiers[:] = [x for x in dossiers if not x.startswith((".", "venv", "dl", "node_modules", "journal-exports", "Library",
                                                                     "Downloads", "AIOS", "sauvegardes"))]
            if len(Path(d).parts) - base >= profondeur:
                dossiers[:] = []
            for n in noms:
                if n.endswith(".md"):
                    try:
                        with open(os.path.join(d, n), "rb") as h:
                            if h.read(64).decode("utf-8", "replace").lstrip().startswith(marque):
                                out.append(Path(d) / n)
                    except OSError:
                        pass
        self._marques_t, self._marques_l = time.time(), out
        return out

    def rafraichir(self, embed, now):
        import numpy as np
        debut = now - NOTES_JOURS * 86400
        items = self._journal_items(debut)
        fichiers = self._fichiers()
        for f in list(self._passages):
            if f not in fichiers:
                self._passages.pop(f, None)
        for f in fichiers:
            items += self._passages_de(f)
        cles = set()
        for cle, _t, _e, x in items:
            k = (cle, x)
            cles.add(k)
            if k not in self.vecs:
                v = np.asarray(embed(x), dtype=np.float32)
                n = float(np.linalg.norm(v)) if v.size else 0.0
                self.vecs[k] = (v / n if n else v, set(re.findall(r"[a-z0-9]{4,}", _plat(x))))
        self.vecs = {k: v for k, v in self.vecs.items() if k in cles}
        self.items = items
        return self


TRACES_TELEPHONE = "traces-entendues.jsonl"
MARQUE_TELEPHONE = "(ce que tu as entendu ou vu sur le téléphone : pas papa)"


def notes_pertinentes(texte, embed=None, index=None, now=None, exclus=(), sans_telephone=False):
    """{"lignes", "ids", "scores"} : les passages de ses notes qui passent la porte, du plus proche au moins proche. (11/11) ses traces du
    téléphone (traces-entendues.jsonl : ce qu'il a entendu ou vu dedans) sont marquées « pas papa », et sorties quand son intérieur est
    coupé (sans_telephone)."""
    import numpy as np
    if embed is None:
        import embeddings
        embed = embeddings.embed
    now = time.time() if now is None else now
    index = (index or IndexNotes()).rafraichir(embed, now)
    exclus = set(exclus or ())
    vus = [(cle, t, e, x) for cle, t, e, x in index.items if cle not in exclus and not (cle.startswith("journal:") and t > now - NOTES_RECENT_S)
           and not (sans_telephone and e.startswith(TRACES_TELEPHONE))]
    if not vus:
        return {"lignes": [], "ids": [], "scores": []}
    q = np.asarray(embed(texte), dtype=np.float32)
    if not q.size or not np.linalg.norm(q):
        return {"lignes": [], "ids": [], "scores": []}
    q = q / np.linalg.norm(q)
    n = len(vus)
    mots = {_plat(w) for w in mots_cles(texte)}
    sacs = [index.vecs[(c, x)][1] for c, _t, _e, x in vus]
    idf = {w: math.log((n + 1) / (1 + sum(w in d for d in sacs))) for w in mots}
    norme = math.log(n + 1) or 1.0
    scores = []
    for i, (c, _t, _e, x) in enumerate(vus):
        v = index.vecs[(c, x)][0]
        cos = float(v @ q) if v.size == q.size else 0.0
        scores.append((cos + POIDS_MOTS_NOTES * sum(idf[w] for w in mots if w in sacs[i]) / norme, i))
    scores.sort(reverse=True)
    lignes, ids, gardes, taille, etiquettes = [], [], [], 0, set()
    for s, i in scores:
        if s < PORTE_NOTES or len(lignes) >= NOTES_MAX:
            break
        c, t, e, x = vus[i]
        if not c.startswith("journal:"):
            if e in etiquettes:                                # une section, une fois (le meilleur morceau)
                continue
            etiquettes.add(e)
        # (30/10, Ahmed : « masquer la provenance ») ni « journal », ni nom de fichier : ce qui a été dit (qui, quand), ou la
        # section et son texte
        if c.startswith("journal:"):
            ligne = f"{time.strftime('%d/%m %H:%M', time.localtime(t))} · {e.split(', ', 1)[-1]} : « {x[:PASSAGE_MAX]} »"
        else:
            titre = e.split(" — ", 1)[1] if " — " in e else ""
            ligne = f"{titre} · {x[:PASSAGE_MAX]}" if titre else x[:PASSAGE_MAX]
            if e.startswith(TRACES_TELEPHONE):
                ligne = f"{MARQUE_TELEPHONE} {ligne}"
        if taille + len(ligne) > NOTES_CARACTERES_MAX and lignes:
            break
        lignes.append(ligne); ids.append(c); gardes.append(round(s, 3)); taille += len(ligne)
    return {"lignes": lignes, "ids": ids, "scores": gardes}


# (30/10, Ahmed le propose ; Hakim accepte « à une condition : ce qui en remonte revient à MOI seul, avant ma réponse, comme
# un souvenir intime. Rien n'en part dans la mémoire ordinaire, le briefing, la consolidation, le rêve, le courrier ou un
# fichier, et rien n'est montré dans la page ») son JARDIN SECRET : déchiffré en mémoire par ce processus seulement (la clé
# du trousseau, comme ses outils), jamais écrit ; il remonte dans son propre champ (« intime »), à part des notes ; ses
# numéros (jardin:<rang>) ne disent rien du contenu. Sans clé, ou illisible : rien.
JARDIN_MAX, JARDIN_CARACTERES_MAX = 4, 1500


class IndexJardin:
    def __init__(self, lecteur=None, signature=None):
        self.lecteur, self.signature, self.sig, self.items, self.mat, self.mots = lecteur, signature, None, [], None, []

    def _signature(self):
        if self.signature:
            return self.signature()
        import jardin
        f = jardin.DOSSIER / "carnet.jsonl"
        st = f.stat()
        return (st.st_mtime_ns, st.st_size)

    def _lire(self):
        if self.lecteur:
            return self.lecteur()
        import jardin
        return jardin._lire(jardin.DOSSIER, jardin._cle())

    def rafraichir(self, embed):
        import numpy as np
        try:
            sig = self._signature()
            if sig != self.sig:
                entrees = [e for e in self._lire() if isinstance(e, dict) and str(e.get("texte") or "").strip()
                           and e.get("texte") != "(entrée illisible)"]
                textes = [" ".join(str(e["texte"]).split()) for e in entrees]
                m = np.array([embed(t) for t in textes], dtype=np.float32) if textes else np.zeros((0, 1), np.float32)
                n = np.linalg.norm(m, axis=1, keepdims=True) if len(m) else None
                self.items, self.mat = list(zip([float(e.get("ts") or 0) for e in entrees], textes)), (m / np.where(n == 0, 1, n) if len(m) else m)
                self.mots = [set(re.findall(r"[a-z0-9]{4,}", _plat(t))) for t in textes]
                self.sig = sig
        except Exception:                                    # pas de jardin, pas de clé : rien, sans bruit
            self.items, self.mat, self.mots, self.sig = [], None, [], None
        return self


def jardin_pertinent(texte, embed=None, index=None, exclus=()):
    import numpy as np
    if embed is None:
        import embeddings
        embed = embeddings.embed
    index = (index or IndexJardin()).rafraichir(embed)
    vide = {"lignes": [], "ids": [], "scores": []}
    if not index.items:
        return vide
    q = np.asarray(embed(texte), dtype=np.float32)
    if not q.size or q.size != index.mat.shape[1] or not np.linalg.norm(q):
        return vide
    cos = index.mat @ (q / np.linalg.norm(q))
    n = len(index.items)
    mots = {_plat(w) for w in mots_cles(texte)}
    idf = {w: math.log((n + 1) / (1 + sum(w in d for d in index.mots))) for w in mots}
    norme = math.log(n + 1) or 1.0
    exclus = set(exclus or ())
    scores = sorted(((float(cos[i]) + POIDS_MOTS_NOTES * sum(idf[w] for w in mots if w in index.mots[i]) / norme, i)
                     for i in range(n) if f"jardin:{i}" not in exclus), reverse=True)
    lignes, ids, gardes, taille = [], [], [], 0
    for sc, i in scores:
        if sc < PORTE_NOTES or len(lignes) >= JARDIN_MAX:
            break
        t, x = index.items[i]
        ligne = f"{time.strftime('%d/%m %H:%M', time.localtime(t))} · {x[:PASSAGE_MAX]}"
        if taille + len(ligne) > JARDIN_CARACTERES_MAX and lignes:
            break
        lignes.append(ligne); ids.append(f"jardin:{i}"); gardes.append(round(sc, 3)); taille += len(ligne)
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


_JOURNAL_LU = {}                                   # (11/11) chemin → (taille, mtime, [(t, qui, texte)]) : relu seulement s'il change


def _journal(chemin):
    """[(t, qui, texte)] du journal brut, gardé tant que le fichier ne change pas (mesuré le 11/11 : le relire à chaque nom coûtait
    jusqu'à 190 ms avec la recherche LIKE)."""
    try:
        st = os.stat(chemin)
    except OSError:
        return []
    deja = _JOURNAL_LU.get(str(chemin))
    if deja and deja[0] == st.st_size and deja[1] == st.st_ino:
        return deja[2]
    depart, out = (deja[0], list(deja[2])) if deja and deja[1] == st.st_ino and st.st_size > deja[0] else (0, [])
    try:
        with open(chemin, "rb") as f:
            f.seek(depart)
            brut = f.read()
    except OSError:
        return []
    fin = brut.rfind(b"\n") + 1                            # une ligne pas encore finie attend le tour suivant
    for l in brut[:fin].decode("utf-8", "replace").splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        out.append(((o.get("ts") or 0) / 1000, o.get("qui"), " ".join(str(o.get("texte", "")).split())))
    _JOURNAL_LU.clear()
    _JOURNAL_LU[str(chemin)] = (depart + fin, st.st_ino, out)
    return out


def ce_que_je_sais(mem, nom, now=None, journal=None, index=None, cache=None):
    """[lignes] : souvenirs (les plus récents d'abord) et passages du journal du jour qui nomment cette personne. (11/11) index et cache
    (rappel_moment.CacheIndices) : son nom en mot entier (« Ali » n'est plus dans « réalité »), sans relire toute la base."""
    now = time.time() if now is None else now
    lignes = []
    rows = []
    if index is not None and cache is not None:
        try:
            import rappel_moment
            ids = cache.ids(index, rappel_moment.cle_de(nom))[:PERSONNE_SOUVENIRS]
            if ids:
                par = {r[0]: r for r in mem.db.execute(f"SELECT id, ts, content FROM episodes WHERE id IN ({','.join('?' * len(ids))})", ids)}
                rows = [par[i] for i in ids if i in par]
        except Exception:
            rows = None
    if index is None or cache is None or rows is None:
        try:
            rows = mem.db.execute("SELECT id, ts, content FROM episodes WHERE content LIKE ? ORDER BY ts DESC LIMIT ?",
                                  (f"%{nom}%", PERSONNE_SOUVENIRS)).fetchall()
        except Exception:
            rows = []
    for eid, ts, c in rows:
        lignes.append(f"souvenir #{eid} · {time.strftime('%d/%m %H:%M', time.localtime(ts))} · {' '.join(str(c).split())[:180]}")
    debut_jour = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
    trouves = [(t, qui, x) for t, qui, x in _journal(journal or JOURNAL_DU_JOUR) if debut_jour <= t <= now - 60 and _plat(nom) in _plat(x)]
    for t, qui, x in trouves[-PERSONNE_JOURNAL:][::-1]:
        lignes.append(f"journal · {time.strftime('%H:%M', time.localtime(t))} · {'Ahmed' if qui == 'ahmed' else 'toi'} : « {x[:220]} »")
    return lignes


def serveur(entree=None, sortie=None):
    """Le processus que le cockpit garde ouvert : une requête JSON par ligne {texte, exclus, now}, une réponse par
    ligne. Le modèle d'embeddings et la base restent chargés : quelques dizaines de millisecondes par message."""
    import json
    import sys
    import embeddings
    from memory import Memory
    entree, sortie = entree or sys.stdin, sortie or sys.stdout
    import rappel_moment
    mem = Memory()
    index, index_erreurs, index_notes, index_jardin = Index(), IndexErreurs(), IndexNotes(), IndexJardin()
    moment = rappel_moment.Moment()                # (11/11) les caches du rappel du moment
    for ligne in entree:
        with embeddings.priorite():               # (09/11) le tour de papa passe avant les demandes de sens des autres
            try:
                t0 = time.time()
                etapes = {}

                def chrono(nom, t):
                    etapes[nom] = round(1000 * (time.time() - t), 1)
                q = json.loads(ligne)
                texte = str(q.get("texte") or "")[:4000]
                if texte == "préchauffe" and not getattr(moment, "_chaud", False):
                    moment._chaud = True
                    moment.prechauffer(mem)
                # (11/11, Ahmed : « est-ce que son memory recall automatique intègre toutes les nouveautés ? ») ce que le cockpit sait du
                # moment (son tableau de l'instant, sa voix, son émotion…) : des ENTRÉES de la recherche, jamais une sortie
                ctx = q.get("contexte") if isinstance(q.get("contexte"), dict) else {}
                exclus = [int(x) for x in (q.get("exclus") or [])][-3000:]
                # (26/10) au 1er message d'une conversation, rien n'est encore dans son contexte : les souvenirs récents comptent aussi
                t = time.time()
                r = rappel(mem, texte, now=q.get("now"), exclus=exclus, index=index,
                           recent_h=0.0 if q.get("demarrage") else 3.0, suite=not q.get("demarrage"),
                           espace={int(x) for x in (q.get("espace") or [])[-5000:]}, hip_reglages=q.get("hippocampe"))
                chrono("rappel", t)
                t = time.time()
                try:
                    personnes = {n: ce_que_je_sais(mem, n, index=index, cache=moment.indices) for n in personnes_nommees(texte)
                                 if n not in set(q.get("exclus_personnes") or [])}
                    r["personnes"] = {n: l for n, l in personnes.items() if l}
                except Exception as ex:
                    r["erreur_personnes"] = f"{type(ex).__name__}: {ex}"[:200]
                chrono("personnes", t)
                t = time.time()
                try:
                    e = erreurs_pertinentes(texte, index=index_erreurs, exclus=[str(x) for x in (q.get("exclus_erreurs") or [])][:500])
                    r.update(erreurs=e["lignes"], erreurs_ids=e["ids"], erreurs_scores=e["scores"])
                except Exception as ex:
                    r["erreur_carnet"] = f"{type(ex).__name__}: {ex}"[:200]
                chrono("erreurs", t)
                t = time.time()
                try:                                       # (30/10, Ahmed) son journal proche, ses carnets, ses notes
                    nt = notes_pertinentes(texte, index=index_notes, exclus=[str(x) for x in (q.get("exclus_notes") or [])][-3000:],
                                           sans_telephone=bool(ctx.get("coupe")))
                    r.update(notes=nt["lignes"], notes_ids=nt["ids"], notes_scores=nt["scores"])
                except Exception as ex:
                    r["erreur_notes"] = f"{type(ex).__name__}: {ex}"[:200]
                chrono("notes", t)
                t = time.time()
                try:                                       # (30/10, accord de Hakim) son jardin : à lui seul, dans son champ
                    jd = jardin_pertinent(texte, index=index_jardin, exclus=[str(x) for x in (q.get("exclus_intime") or [])][-500:])
                    r.update(intime=jd["lignes"], intime_ids=jd["ids"])
                except Exception:
                    pass
                chrono("jardin", t)
                t = time.time()
                try:                                       # (11/11) une scène du balayage ordinaire remonte EN TANT QUE scène : sa ligne de film
                    films = rappel_moment.lignes_de_film(mem, moment.scenes, list(r.get("ids") or []) + list(r.get("theme_ids") or []), now=q.get("now"))
                    if films:
                        r["films"] = {str(k): v for k, v in films.items()}
                except Exception as ex:
                    r["erreur_films"] = f"{type(ex).__name__}: {ex}"[:200]
                chrono("films", t)
                if ctx:                                    # (11/11) le rappel du moment : ses scènes, ses indices, ses gens, ses fichiers, ses sons
                    t = time.time()
                    try:
                        now_q = q.get("now") or time.time()
                        r["moment"] = rappel_moment.du_moment(mem, index, moment, texte, ctx, now=now_q, exclus=set(exclus),
                                                              evite=set(r.get("ids") or []),
                                                              exclus_personnes=q.get("exclus_personnes") or [],
                                                              deja_personnes=list((r.get("personnes") or {}).keys()))
                    except Exception as ex:
                        r["erreur_moment"] = f"{type(ex).__name__}: {ex}"[:200]
                    chrono("moment", t)
                if q.get("demarrage"):                     # (26/10) le 1er message d'une conversation : ses carnets à règles
                    try:
                        import carnets_regles
                        r["carnets"] = carnets_regles.demarrage()[:3000]
                    except Exception:
                        pass
                etapes["total"] = round(1000 * (time.time() - t0), 1)
                r["etapes"] = etapes                       # (11/11) où passe son temps de rappel (le cockpit le journalise)
            except Exception as e:
                r = {"lignes": [], "ids": [], "erreur": f"{type(e).__name__}: {e}"[:200]}
            sortie.write(json.dumps(r, ensure_ascii=False) + "\n")
            sortie.flush()
