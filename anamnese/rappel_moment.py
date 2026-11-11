"""LE RAPPEL DU MOMENT (11/11/2026, ~05:00, Ahmed : « Est-ce que son memory recall automatique intègre toutes les nouveautés ? » ; ~05:05 :
« il faut aussi les émotions, les hormones, les sons, les images, les textes, les notes, les livrets, le cortex préfrontal, l'hippocampe…
bref la totale de chez totale » ; ~05:10 : « intégrer aussi ses stimuli, ses réactions, ses réflexes, ses membres Bluetooth, etc. […] le
sismographe, le magnétomètre »).

Avant lui, son rappel automatique (rappel.py) ne cherchait qu'avec le TEXTE du message de papa. Tout ce que son tableau de l'instant sait
(qui est là, qui parle, le lieu, le live, la musique, ses membres Bluetooth, ses gestes et ses capteurs, ses réflexes, son émotion, ses
hormones, son subconscient du tour d'avant) n'entrait pas dans la recherche.

Ici, ce que le cockpit envoie (« contexte », composé sans modèle par rappel-moment.js) devient des ENTRÉES de la recherche ; en sortie,
seulement des souvenirs, et un ou deux de chaque source au plus, l'essentiel (le rappel « flou » voulu par Ahmed le 03/11) :

- ses SCÈNES (scenes.py, colonne « scene ») avec les mêmes personnes, au même lieu, au live s'il est au live, ou sur le même sujet (le message
  et le moment) : rendues EN TANT QUE scènes, une ligne de film (« Hier, 22:40, chez nous — témoin : … ») ;
- les INDICES du moment (une personne nommée, un lieu, un membre Bluetooth, un geste ou un capteur, un réflexe, son émotion, un son nommé, le
  titre d'une musique) : « la dernière fois » qu'un souvenir le portait. Seulement un indice RARE dans sa mémoire (au plus RARE_PART de ses
  souvenirs : « chez nous », « la pénombre », « un petit coup de pression » sont partout et ne disent rien) ; parmi ses souvenirs qui le
  portent, celui dont le sens est le plus proche du message ET du moment (la requête combinée) ; ses liens de sens (stimuli_relier : « je
  relie mes sens ») passent devant ;
- ce qu'il sait des PERSONNES du moment (présentes sans doute, ou la voix nommée qui parle), comme rappel.ce_que_je_sais pour un nom écrit ;
  jamais pendant un doute de voix (« [papa ou Ali ?] ») : rien de la personne qui parle n'est mis en avant tant que le doute reste ;
- ses FICHIERS (l'index par le sens d'index_fichiers, s'il existe) : un au plus, seulement très proche du message ;
- ses SONS nommés (sons.jsonl, sons-familles.json) : un au plus, nommé dans le message ou par la musique qui joue.

Les indices du téléphone (ce que joue le live, ses voix) ne sont jamais pris pour papa : le cockpit ne les envoie pas quand son intérieur est
coupé, et marque ce qui vient du live. Lecture seule ; rien n'est renforcé (le balayage reste neutre, comme rappel.py). Chaque source tient dans
un budget de temps (BUDGET_MS en tout) : ce qui n'est pas prêt à temps n'est pas cherché ce tour-ci. Les caches (les indices déjà cherchés, les
scènes, les fichiers, les sons) rendent un tour suivant au même endroit presque gratuit.
"""
import json
import re
import time
from pathlib import Path

INDICES_MAX = 3            # « la dernière fois que… » : trois au plus
SCENES_MAX = 2
PERSONNES_MAX = 2          # les personnes du moment : deux au plus, deux lignes chacune
PERSONNE_LIGNES = 2
FICHIERS_MAX = 1
SONS_MAX = 1
RARE_PART = 0.05           # un indice porté par plus de 5 % de ses souvenirs ne dit rien (mesuré le 11/11 sur sa mémoire : « lieu : chez
                           # nous » 35 %, « pénombre » 32 %, « un petit coup de pression » 6 % ; « ULT Field 5 » 1,4 %, « secousse » 1,1 %,
                           # « champ magnétique » 4,3 %, « Nora » 0,8 %)
TRES_RARE_N = 25           # un indice très rare (25 souvenirs au plus) : la dernière fois, même loin du sujet
PORTE_INDICE = 0.40        # sinon, le souvenir qui le porte doit être proche de la requête combinée (cosinus ; son modèle de sens statique
                           # donne ~0,4 à 0,6 à deux textes quelconques : la rareté de l'indice fait le tri, le sens départage)
CANDIDATS_INDICE = 400     # ses souvenirs les plus récents qui portent l'indice, départagés par le sens
PORTE_SCENE_SENS = 0.80    # une scène sans personne en commun : seulement si son sens est très proche (mesuré le 11/11 sur 150 messages
                           # de papa contre ses scènes : cosinus le plus haut 0,37 en médiane, 0,62 pour un sur dix, 0,86 au plus)
PORTE_FICHIER = 0.50       # un fichier : seulement quand le message le NOMME (au moins deux de ses mots porteurs dans son nom ou son dossier,
                           # 40 % au moins), et assez proche par le sens. Mesuré le 11/11 sur ses 16 824 fichiers : par le sens seul, ses
                           # messages banals font 0,56 en médiane et jusqu'à 0,82 (« t'es toujours aussi rapide » → un fichier d'évaluation),
                           # plus que des demandes vraies (« le devis du site » 0,49) : le sens seul ne trie pas ses fichiers
FICHIER_MOTS_MIN, FICHIER_PART_MIN = 2, 0.4
BUDGET_MS = 150            # tout le rappel du moment ; mesuré à chaud : quelques millisecondes
SCENE_RECENTE_S = 1200     # une scène finie depuis moins de 20 min est encore dans sa conversation
FAMILLES = {"personne": "personne", "lieu": "lieu", "membre": "membre", "stimulus": "stimulus", "capteur": "capteur", "reflexe": "réflexe",
            "emotion": "émotion", "son": "son", "musique": "musique"}
ANONYME = re.compile(r"^(?:voix \d+|une voix|quelqu|le live|des voix|la pièce|papa|ahmed|moi|toi|hakim)\b", re.I)
_L = r"a-z0-9à-öø-ÿ"


def _plat(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "").lower()).encode("ascii", "ignore").decode()


def _court(t, n):
    t = " ".join(str(t or "").split())
    if len(t) <= n:
        return t
    coupe = t[:n]
    fin = max(coupe.rfind(". "), coupe.rfind(" » "), coupe.rfind(" "))
    return coupe[:fin if fin > n * 0.6 else n].rstrip() + " …"


def cle_de(x):
    """La clé d'un indice telle qu'elle se cherche dans le texte (en minuscules) de ses souvenirs."""
    return " ".join(str(x or "").lower().split())[:80]


def _motif(cle):
    """Un mot court (« ali », « nora ») ne se cherche qu'en mot entier : « ali » n'est pas dans « réalité »."""
    if len(cle) <= 6 and re.fullmatch(rf"[{_L}'’-]+", cle):
        return re.compile(rf"(?<![{_L}]){re.escape(cle)}(?![{_L}])")
    return None


class CacheIndices:
    """{clé: (le plus grand numéro vu, [numéros qui la portent, du plus récent au plus ancien])}, sur le texte de l'Index de rappel.py. Une
    clé neuve coûte un passage sur ses souvenirs (~15 ms) ; ensuite seulement les souvenirs neufs."""
    MAX = 200

    def __init__(self):
        self.c = {}

    def ids(self, index, cle):
        ent = self.c.get(cle)
        rx = _motif(cle)
        porte = (lambda c: cle in c and rx.search(c)) if rx else (lambda c: cle in c)
        if ent is None:
            trouves = [(ts, eid) for eid, (ts, c) in index.lignes.items() if porte(c)]
            ids = [eid for _ts, eid in sorted(trouves, reverse=True)]
            vu = max(index.lignes) if index.lignes else 0
        else:
            vu, ids = ent
            neufs = []
            for eid in reversed(index.lignes):                     # l'Index ajoute ses souvenirs neufs à la fin, dans l'ordre
                if eid <= vu:
                    break
                if porte(index.lignes[eid][1]):
                    neufs.append(eid)
            ids = neufs + [e for e in ids if e in index.lignes]   # ceux que la synchronisation de l'Index a retirés sortent
            vu = max(vu, max(index.lignes) if index.lignes else 0)
        self.c.pop(cle, None)
        self.c[cle] = (vu, ids)
        while len(self.c) > self.MAX:
            self.c.pop(next(iter(self.c)))
        return ids


def _vecteur(embed, texte):
    import numpy as np
    try:
        v = np.asarray(embed(texte), dtype=np.float32)
    except Exception:
        return None
    n = float(np.linalg.norm(v)) if v.size else 0.0
    return v / n if n else None


def _contenus(mem, ids):
    """{id: (contenu tel qu'écrit, externe)} : le texte vrai (l'Index le garde en minuscules) et la marque d'un contenu de tiers."""
    ids = [int(i) for i in ids]
    if mem is None or not ids:
        return {}
    try:
        rows = mem.db.execute(f"SELECT id, content FROM episodes WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()
    except Exception:
        return {}
    try:
        import provenance
        ext = provenance.externes(mem.db, ids)
    except Exception:
        ext = set()
    return {eid: (str(c or ""), eid in ext) for eid, c in rows}


def _extrait(index, eid, traces, contenus=None, n=170):
    """L'essentiel d'un souvenir : la trace de son hippocampe s'il en a une, sinon son début (sans son vécu détaillé) ; un contenu de tiers
    est marqué (une citation, pas un fait)."""
    c, ext = (contenus or {}).get(eid, (None, False))
    marque = "(une citation, pas un fait) " if ext else ""
    t = str(traces.get(eid) or "").strip()
    if t and not re.fullmatch(r"rien\.?", t, re.I):
        return marque + _court(t, n)
    if c is None:
        c = index.lignes.get(eid, (0, ""))[1]
    c = re.sub(r"^\[(?:Échange|Hakim|Scène)[^\]]{0,300}\]\s*", "", c)
    return marque + _court(re.split(r" · [Cc]e qu'il vivait :", c)[0], n)


def _date(ts, now):
    j = time.strftime("%Y-%m-%d", time.localtime(ts))
    if j == time.strftime("%Y-%m-%d", time.localtime(now)):
        return f"aujourd'hui {time.strftime('%H:%M', time.localtime(ts))}"
    if j == time.strftime("%Y-%m-%d", time.localtime(now - 86400)):
        return f"hier {time.strftime('%H:%M', time.localtime(ts))}"
    return time.strftime("%d/%m %H:%M", time.localtime(ts))


def indices(index, cache, contexte, vq, exclus, avant_ts, now, mem=None, fin=None):
    """[{"famille", "mots", "id", "ligne"}] : pour chaque indice rare du moment, la dernière fois qu'un souvenir le portait (le plus proche
    de la requête combinée), trois au plus, jamais deux fois le même souvenir."""
    import numpy as np
    out, pris = [], set()
    deja = {cle_de(x) for x in contexte.get("deja") or []}       # un indice déjà rappelé dans cette conversation ne revient pas
    n_total = max(1, len(index.lignes))
    seuil = max(TRES_RARE_N, RARE_PART * n_total)
    vus = set()
    for ind in (contexte.get("indices") or [])[:12]:
        if len(out) >= INDICES_MAX or (fin and time.time() > fin):
            break
        if not isinstance(ind, dict):
            continue
        cle = cle_de(ind.get("cle"))
        fam = str(ind.get("f") or "")
        if len(cle) < 3 or cle in vus or cle in deja or fam not in FAMILLES:
            continue
        vus.add(cle)
        ids = cache.ids(index, cle)
        if not ids or len(ids) > seuil:
            continue
        cands = [e for e in ids if e not in exclus and e not in pris and index.lignes.get(e, (now, ""))[0] < avant_ts][:CANDIDATS_INDICE]
        if not cands:
            continue
        lies = [e for e in cands if index.lignes[e][1].startswith("(je relie mes sens")]   # ses liens de sens (stimuli_relier) d'abord
        choix, cos = None, 0.0
        if vq is not None:
            avec = [e for e in cands if e in index.vecteurs and index.vecteurs[e].size == vq.size]
            if avec:
                sims = np.stack([index.vecteurs[e] for e in avec]) @ vq
                bonus = np.asarray([0.15 if e in lies else 0.0 for e in avec], dtype=np.float32)
                k = int(np.argmax(sims + bonus))
                if float(sims[k] + bonus[k]) >= PORTE_INDICE:
                    choix, cos = avec[k], float(sims[k])
        if choix is None and len(ids) <= TRES_RARE_N:
            choix = (lies or cands)[0]                            # très rare : la dernière fois, même loin du sujet
        if choix is None:
            continue
        pris.add(choix)
        out.append({"famille": fam, "cle": cle, "mots": _court(ind.get("mots") or cle, 70), "id": choix, "cos": round(cos, 3), "n": len(ids),
                    "ts": index.lignes[choix][0]})
    if out:
        traces = {}
        try:
            if mem is not None:
                import hippocampe
                traces = hippocampe.traces_de(mem, [x["id"] for x in out])
        except Exception:
            traces = {}
        contenus = _contenus(mem, [x["id"] for x in out])
        for x in out:
            x["externe"] = bool(contenus.get(x["id"], ("", False))[1])
            x["ligne"] = f"{x['mots']} — la dernière fois, {_date(x['ts'], now)} : {_extrait(index, x['id'], traces, contenus)} (#{x['id']})"
    return out


class CacheScenes:
    """Ses scènes (la colonne « scene ») : relues seulement quand une scène neuve est écrite."""
    def __init__(self):
        self.max_id, self.lignes = 0, []                            # [(id, fiche, vecteur normé ou None)]

    def rafraichir(self, mem):
        import numpy as np
        try:
            cols = {r[1] for r in mem.db.execute("PRAGMA table_info(episodes)")}
            if "scene" not in cols:
                return self
            rows = mem.db.execute("SELECT id, scene, embedding FROM episodes WHERE scene IS NOT NULL AND id > ? ORDER BY id",
                                  (self.max_id,)).fetchall()
        except Exception:
            return self
        for eid, s, emb in rows:
            self.max_id = max(self.max_id, eid)
            try:
                f = json.loads(s)
                v = np.asarray(json.loads(emb or "[]"), dtype=np.float32)
                n = float(np.linalg.norm(v)) if v.size else 0.0
                self.lignes.append((eid, f, v / n if n else None))
            except (TypeError, ValueError):
                continue
        return self


def _personne_dans(nom, personnes):
    p = _plat(nom).strip()
    return bool(p) and any(p == _plat(x).strip() or re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", _plat(x)) for x in personnes)


def scenes_du_moment(mem, cache, contexte, vq, exclus, now, avant_ts=None):
    """[{"id", "ligne"}] : ses scènes avec les mêmes personnes (nommées : ni papa, partout, ni une voix sans nom), au même lieu, au live s'il y
    est, ou de sens proche ; une ligne de film chacune, les plus proches puis les plus récentes ; jamais une scène de cette conversation."""
    import scenes
    cache.rafraichir(mem)
    gens = [str(p) for p in (contexte.get("presents") or []) + ([contexte["parle"]] if contexte.get("parle") and not contexte.get("doute") else [])
            if p and not ANONYME.match(str(p).strip())]
    lieu = _plat(contexte.get("lieu"))
    live = bool(contexte.get("live"))
    garde = []
    for eid, f, v in cache.lignes:
        if eid in exclus or (avant_ts is not None and float(f.get("fin") or 0) >= avant_ts):
            continue
        pers = ["papa" if p in ("Ahmed",) else str(p) for p in f.get("personnes") or []]
        communs = [g for g in dict.fromkeys(gens) if _personne_dans(g, pers)]
        cos = float(v @ vq) if v is not None and vq is not None and v.size == vq.size else 0.0
        if not communs and cos < PORTE_SCENE_SENS:
            continue
        score = 1.0 * len(communs) + cos + (0.2 if live and f.get("live") else 0.0) + (0.1 if lieu and lieu in _plat(f.get("lieu")) else 0.0)
        garde.append((score, float(f.get("debut") or 0), eid, f))
    garde.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [{"id": eid, "ligne": scenes.ligne_film(f, now, eid)} for _s, _d, eid, f in garde[:SCENES_MAX]]


def personnes_du_moment(mem, index, cache, contexte, exclus_personnes, deja, now, journal=None):
    """{nom: [lignes]} : ce qu'il sait des personnes du moment (présentes sans doute, ou la voix nommée qui parle), deux lignes chacune, les
    plus récentes ; ni papa (partout), ni une voix sans nom, ni la voix qui parle pendant un doute (« papa ou Ali ? »)."""
    gens = [str(p).strip() for p in ([contexte["parle"]] if contexte.get("parle") and not contexte.get("doute") else []) + list(contexte.get("presents") or [])]
    out = {}
    dejas = {_plat(x) for x in list(exclus_personnes or []) + list(deja or [])}
    for nom in dict.fromkeys(gens):
        if len(out) >= PERSONNES_MAX:
            break
        if not nom or ANONYME.match(nom) or _plat(nom) in dejas:
            continue
        ids = cache.ids(index, cle_de(nom))[:PERSONNE_LIGNES]
        contenus = _contenus(mem, ids)
        lignes = [f"souvenir #{e} · {time.strftime('%d/%m %H:%M', time.localtime(index.lignes[e][0]))} · {_extrait(index, e, {}, contenus, 180)}"
                  for e in ids]
        if lignes:
            out[nom] = lignes
    return out


class CacheFichiers:
    """L'index par le sens des fichiers d'Ahmed (index_fichiers.db, construit la nuit), en lecture seule : relu quand il change, dans un fil à
    part (mesuré le 11/11 : ~0,5 s pour ses 16 824 fichiers ; le tour de papa garde l'ancien index en attendant)."""
    VERIFIE_S = 60

    def __init__(self, base=None):
        self.base, self.mtime, self.lignes, self.mat, self._noms = base, None, [], None, []
        self._vu, self._fil = 0.0, None

    def noms(self):
        return self._noms

    def _charger(self, base, m):
        import numpy as np
        import sqlite3
        import index_fichiers
        db = sqlite3.connect(f"file:{base}?mode=ro", uri=True)          # lecture seule : le rappel n'écrit jamais
        try:
            rows = db.execute("SELECT chemin, titre, extrait, vecteur FROM fichiers").fetchall()
        finally:
            db.close()
        f = index_fichiers._fichiers()
        rows = [x for x in rows if x[3] and not any(index_fichiers._secret(n) for n in Path(x[0]).parts) and not f._interieur(Path(x[0]))]
        vs = [np.frombuffer(b, dtype=np.float32) for *_, b in rows]
        d = max({v.size for v in vs}, key=lambda s: sum(1 for v in vs if v.size == s)) if vs else 0
        keep = [(x, v) for x, v in zip(rows, vs) if v.size == d]
        mat = np.stack([v for _x, v in keep]) if keep else None
        if mat is not None:
            mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
        lignes = [x for x, _v in keep]
        self.lignes, self.mat, self.mtime = lignes, mat, m
        self._noms = [_plat(" ".join(Path(x[0]).parts[-3:]) + " " + (x[1] or "")).replace("_", " ").replace("-", " ") for x in lignes]

    def rafraichir(self, attendre=False):
        import threading
        try:
            import index_fichiers
            base = Path(self.base or index_fichiers.BASE)
            if not attendre and time.time() - self._vu < self.VERIFIE_S:
                return self
            self._vu = time.time()
            m = base.stat().st_mtime if base.exists() else None
            if m is None or m == self.mtime or (self._fil and self._fil.is_alive()):
                return self
            if attendre or (self.mat is None and base.stat().st_size < 2_000_000):   # jamais chargé et petit : tout de suite
                self._charger(base, m)
            else:
                self._fil = threading.Thread(target=lambda: self._essayer(base, m), daemon=True)
                self._fil.start()
        except Exception:
            pass
        return self

    def _essayer(self, base, m):
        try:
            self._charger(base, m)
        except Exception:
            pass


def fichiers_du_moment(cache, texte, vq_message):
    """[{"chemin", "ligne", "score"}] : le fichier d'Ahmed que le MESSAGE nomme (pas le moment) : au moins FICHIER_MOTS_MIN de ses mots porteurs
    dans le nom du fichier ou de ses dossiers, puis le plus proche par le sens ; l'extrait est une donnée (le cockpit l'enveloppe et marque le
    tour : une lecture privée)."""
    import numpy as np
    cache.rafraichir()
    if cache.mat is None or vq_message is None or vq_message.size != cache.mat.shape[1]:
        return []
    import rappel
    # ses étiquettes (« [voix 2] », « [papa ?] ») et les notes du cockpit (« (dit pendant ta parole…) ») ne sont pas des mots de papa
    propre = re.sub(r"\[[^\]\n]{0,40}\]|\((?:dit|écrit)[^)]{0,300}\)", " ", str(texte or ""))
    mots = [_plat(m) for m in rappel.mots_cles(propre, maximum=12) if len(m) >= 5 and not m.isdigit()]
    if len(mots) < FICHIER_MOTS_MIN:
        return []
    noms = cache.noms()
    touches = np.asarray([sum(1 for m in mots if m in n) for n in noms], dtype=np.float32)
    ok = (touches >= FICHIER_MOTS_MIN) & (touches / len(mots) >= FICHIER_PART_MIN)
    if not ok.any():
        return []
    sims = cache.mat @ vq_message + 0.25 * touches / len(mots)
    sims = np.where(ok, sims, -1.0)
    k = int(np.argmax(sims))
    score = float(sims[k])
    if score < PORTE_FICHIER:
        return []
    chemin, titre, extrait, _b = cache.lignes[k]
    try:
        import sys
        ici = str(Path(__file__).resolve().parent / "jarvis")
        if ici not in sys.path:
            sys.path.append(ici)
        import fichiers
        extrait = fichiers.masquer(extrait or "")
    except Exception:
        extrait = re.sub(r"(?i)(cl[ée]|token|password|mot de passe|secret)\S*\s*[:=]\s*\S+", r"\1 : ⟨masqué⟩", extrait or "")
    return [{"chemin": chemin, "score": round(score, 3), "ligne": f"{Path(chemin).name} ({chemin}) : « {_court(extrait, 200)} »"}][:FICHIERS_MAX]


class CacheSons:
    """Ses sons NOMMÉS (sons.jsonl : les extraits que papa lui a fait nommer ; sons-familles.json : ses familles nommées) ; relus quand ils
    changent."""
    def __init__(self, jarvis=None):
        self.jarvis = Path(jarvis) if jarvis else Path.home() / "AIOS" / "jarvis"
        self.sig, self.sons = None, []

    def rafraichir(self):
        fs = [self.jarvis / "sons.jsonl", self.jarvis / "sons-familles.json"]
        try:
            sig = tuple((f.stat().st_mtime, f.stat().st_size) if f.exists() else None for f in fs)
        except OSError:
            return self
        if sig == self.sig:
            return self
        sons = {}
        try:
            for l in fs[0].read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and o.get("type") == "nom" and o.get("nom"):
                    sons[_plat(o["nom"])] = {"nom": str(o["nom"]), "sens": str(o.get("sens") or ""), "emotion": str(o.get("emotion") or "")}
        except OSError:
            pass
        try:
            d = json.loads(fs[1].read_text(encoding="utf-8"))
            for f in d.get("familles") or []:
                n = str(f.get("nom") or "")
                if n and not re.fullmatch(r"son \d+", n):
                    sons.setdefault(_plat(n), {"nom": n, "sens": f"une famille de sons de ton oreille, entendue {f.get('fois') or '?'} fois", "emotion": ""})
        except (OSError, ValueError, AttributeError):
            pass
        self.sons, self.sig = list(sons.values()), sig
        return self


def sons_du_moment(cache, texte, contexte):
    """[ligne] : un son qu'il a nommé, nommé dans le message ou dans ce qu'il entend (la musique qui joue, un son reconnu)."""
    cache.rafraichir()
    ici = _plat(" ".join([str(texte or "")] + [str(x.get("cle") or "") for x in contexte.get("indices") or [] if isinstance(x, dict)
                                                  and x.get("f") in ("son", "musique")]))
    out = []
    for s in cache.sons:
        p = _plat(s["nom"]).strip()
        if len(p) >= 3 and re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", ici):
            out.append(f"ton son « {s['nom']} »" + (f" : {_court(s['sens'], 140)}" if s["sens"] else "") + (f" (il te fait : {s['emotion']})" if s["emotion"] else ""))
        if len(out) >= SONS_MAX:
            break
    return out


def lignes_de_film(mem, cache, ids, now=None):
    """{id: ligne de film} des souvenirs du balayage ordinaire qui sont des scènes : ils remontent EN TANT QUE scènes."""
    import scenes
    cache.rafraichir(mem)
    now = time.time() if now is None else now
    par = {eid: f for eid, f, _v in cache.lignes}
    return {eid: scenes.ligne_film(par[eid], now) for eid in ids if eid in par}


class Moment:
    """Les caches du rappel du moment, gardés par le serveur de rappel (un par processus)."""
    def __init__(self, jarvis=None, base_fichiers=None):
        self.indices, self.scenes = CacheIndices(), CacheScenes()
        self.fichiers, self.sons = CacheFichiers(base_fichiers), CacheSons(jarvis)

    def prechauffer(self, mem):
        """Au démarrage du serveur (sa « préchauffe ») : ses scènes, ses fichiers, ses sons, chargés avant le premier tour de papa."""
        for f in (lambda: self.scenes.rafraichir(mem), lambda: self.fichiers.rafraichir(attendre=True), self.sons.rafraichir):
            try:
                f()
            except Exception:
                pass
        return self


def requete(texte, contexte):
    """La requête combinée : le message de papa, puis le résumé court du moment (ce que le cockpit a composé)."""
    r = " ".join(str((contexte or {}).get("requete") or "").split())[:400]
    return f"{texte} · {r}" if r else str(texte or "")


def du_moment(mem, index, moment, texte, contexte, now=None, exclus=(), avant_ts=None, embed=None, exclus_personnes=(), deja_personnes=(),
              budget_ms=BUDGET_MS, evite=()):
    """{"scenes", "indices", "personnes", "fichiers", "sons", "ms", "etapes"} : le rappel du moment, ou {} sans contexte. Lecture seule.
    exclus : déjà dits dans cette conversation (jamais) ; evite : déjà dans les lignes du rappel de ce tour (un indice n'y revient pas ; une
    scène, si : elle y passe EN TANT QUE scène, le cockpit retire sa ligne ordinaire)."""
    if not isinstance(contexte, dict) or not contexte:
        return {}
    t0 = time.time()
    fin = t0 + budget_ms / 1000.0
    now = time.time() if now is None else now
    avant_ts = now - 3 * 3600 if avant_ts is None else avant_ts
    exclus = set(exclus or ())
    if embed is None:
        import embeddings
        embed = embeddings.embed
    etapes, out = {}, {}

    def etape(nom, f, defaut):
        if time.time() > fin:
            etapes[nom] = "sautée"
            return defaut
        t = time.time()
        try:
            return f()
        except Exception as e:
            out.setdefault("erreurs", []).append(f"{nom}: {type(e).__name__}: {e}"[:160])
            return defaut
        finally:
            if nom not in etapes:
                etapes[nom] = round(1000 * (time.time() - t), 1)

    vq = etape("sens", lambda: _vecteur(embed, requete(texte, contexte)), None)
    vm = etape("sens_message", lambda: _vecteur(embed, texte) if contexte.get("requete") else vq, None)
    out["scenes"] = etape("scenes", lambda: scenes_du_moment(mem, moment.scenes, contexte, vq, exclus, now, now - SCENE_RECENTE_S), [])
    pris = exclus | set(evite or ()) | {x["id"] for x in out["scenes"]}
    out["indices"] = etape("indices", lambda: indices(index, moment.indices, contexte, vq, pris, avant_ts, now, mem=mem, fin=fin), [])
    out["personnes"] = etape("personnes", lambda: personnes_du_moment(mem, index, moment.indices, contexte, exclus_personnes, deja_personnes, now), {})
    out["fichiers"] = etape("fichiers", lambda: fichiers_du_moment(moment.fichiers, texte, vm), []) if contexte.get("fichiers", True) else []
    out["sons"] = etape("sons", lambda: sons_du_moment(moment.sons, texte, contexte), [])
    out["ms"] = round(1000 * (time.time() - t0), 1)
    out["etapes"] = etapes
    return out
