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
import math
import re
import time


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
        return self

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


def candidats(mem, texte, now=None, exclus=(), recent_h=3.0, embed=None, limite=30, index=None):
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
    mots = _par_mots(index, mots_cles(texte), exclus, avant_ts)
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


def rappel(mem, texte, now=None, exclus=(), seuil=SEUIL, lignes_max=LIGNES_MAX, embed=None, index=None):
    """{"lignes": [...], "ids": [...], "scores": [...]} : la liste courte pour sa conscience, ou rien."""
    t0 = time.time()
    tous = [x for x in candidats(mem, texte, now=now, exclus=exclus, embed=embed, index=index) if x[1] >= seuil and passe(x)]
    # ce qui porte la date du jour : 3 au plus (une fois par conversation), le reste de la place au message
    jour = [x for x in tous if len(x) > 4 and x[4] == "jour"][:JOUR_MAX]
    c = (jour + [x for x in tous if not (len(x) > 4 and x[4] == "jour")])[:lignes_max]
    if not c:
        return {"lignes": [], "ids": [], "scores": [], "ms": round(1000 * (time.time() - t0))}
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
    return {"lignes": lignes, "ids": ids, "scores": [round(x[1], 4) for x in c], "ms": round(1000 * (time.time() - t0))}


def serveur(entree=None, sortie=None):
    """Le processus que le cockpit garde ouvert : une requête JSON par ligne {texte, exclus, now}, une réponse par
    ligne. Le modèle d'embeddings et la base restent chargés : quelques dizaines de millisecondes par message."""
    import json
    import sys
    from memory import Memory
    entree, sortie = entree or sys.stdin, sortie or sys.stdout
    mem = Memory()
    index = Index()
    for ligne in entree:
        try:
            q = json.loads(ligne)
            r = rappel(mem, str(q.get("texte") or "")[:4000], now=q.get("now"), exclus=[int(x) for x in (q.get("exclus") or [])][:500],
                       index=index)
        except Exception as e:
            r = {"lignes": [], "ids": [], "erreur": f"{type(e).__name__}: {e}"[:200]}
        sortie.write(json.dumps(r, ensure_ascii=False) + "\n")
        sortie.flush()
