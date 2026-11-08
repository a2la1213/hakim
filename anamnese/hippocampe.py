"""L'hippocampe de Hakim (08/11/2026, Ahmed : « rajoute-lui un hippocampe et améliore sa remémorisation » ; « fais un test et réponds à ta
question » ; « ouiii »).

Mesuré avant (banc de 24 vrais souvenirs de plus d'un jour, une question comme papa la poserait) : 6 sur 24 retrouvés dans les 8 lignes de
son rappel automatique, 0 sur 6 pour ce que papa a dit les jours d'avant. Chaque échange est gardé avec tout ce qu'il vivait (la musique, ses
notes, ses sensations : 1 700 caractères en moyenne, dont 330 pour les paroles) : son sens, et ses mots, sont noyés.

L'hippocampe garde, à côté de chaque échange (jamais à sa place), une TRACE courte : le jour et le moment (« vendredi 30 octobre 2026, le
soir »), le genre (une promesse, un live, la crypto, la musique, la famille…), et les paroles de papa et les siennes ; son sens à part. Il la
retrouve par un indice : un mot, un sens proche, une date (« hier », « le 29 », « samedi », « le 3 novembre »). Le rappel automatique
(rappel.py) l'écoute comme un troisième balayage. Traces sans modèle (« lite ») : immédiates, pour tous les échanges, d'hier comme de
demain (remplies au passage). Lecture seule sur ses souvenirs : rien n'est renforcé ni changé.
"""
import json
import math
import re
import time

TABLE = """CREATE TABLE IF NOT EXISTS hippocampe (
    episode_id INTEGER PRIMARY KEY,
    ts         REAL NOT NULL,
    jour       TEXT NOT NULL,
    trace      TEXT NOT NULL,
    genres     TEXT NOT NULL DEFAULT '',
    embedding  TEXT NOT NULL DEFAULT '[]',
    source     TEXT NOT NULL DEFAULT 'lite',
    maj        REAL NOT NULL
)"""
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
TRACE_MAX = 700
GENRES = [
    ("promesse", re.compile(r"\b(je te (le )?promets|promis|promesse|je m.engage|je te jure|c.est juré)", re.I)),
    ("live", re.compile(r"\b(live|tiktok|en direct|spectateurs?|abonnés?|invités?)\b", re.I)),
    ("crypto", re.compile(r"\b(xrp|btc|bitcoin|eth|crypto\w*|backtest\w*|trading|trade|ordre|engrais|floraison|levier)\b", re.I)),
    ("musique", re.compile(r"\b(feat|instru\w*|morceau|chanson|studio|rap|clip|mix\w*|refrain|couplet|beat)\b", re.I)),
    ("famille", re.compile(r"\b(famille|maman|ta mère|ma mère|soeur|sœur|frère|cousin|oncle|tante|fille|fils|femme|mari|bébé)\b", re.I)),
    ("foi", re.compile(r"\b(allah|coran|verset|sourate|prière|dieu|tadabour|tadabbur|mosquée|ramadan|dua)\b", re.I)),
    ("santé", re.compile(r"\b(malade|médecin|docteur|opération|hôpital|douleur|fatigu\w*|dormir|sommeil)\b", re.I)),
    ("travail", re.compile(r"\b(code|script|appli|cockpit|serveur|bug|github|projet|client|site)\b", re.I)),
]
_ENTETE = re.compile(r"^\s*\[[^\]]*\]\s*")
_FIN_ECHANGE = re.compile(r"\s·\s(?:Ce qu'il vivait|Le fil|Ce que tu entends|Au même moment)\b")
_MOT = re.compile(r"[\w']+", re.U)


def mots(t):
    return [m for m in _MOT.findall(str(t or "").lower()) if len(m) > 2]


def moment(heure):
    return "la nuit" if heure < 6 else "le matin" if heure < 12 else "l'après-midi" if heure < 18 else "le soir"


def jour_texte(ts):
    t = time.localtime(ts)
    return f"{JOURS[t.tm_wday]} {t.tm_mday} {MOIS[t.tm_mon - 1]} {t.tm_year}, {moment(t.tm_hour)}"


def tracer(ts, content):
    """(trace, genres) : le jour et le moment, le genre, les paroles (sans le vécu qui suit)."""
    c = " ".join(str(content or "").split())
    entete = (_ENTETE.match(c).group(0) if _ENTETE.match(c) else "")
    corps = c[len(entete):]
    m = _FIN_ECHANGE.search(corps)
    paroles = corps[:m.start()] if m else corps
    paroles = paroles.replace("Ahmed : «", "papa : «")
    genres = [g for g, rx in GENRES if rx.search(paroles)]
    ou = []
    if re.search(r"à l.oral", entete): ou.append("à l'oral")
    if re.search(r"\blive\b", entete, re.I): ou.append("en live")
    tete = jour_texte(ts) + (f" ({', '.join(ou)})" if ou else "") + (f" · {', '.join(genres)}" if genres else "")
    return f"{tete} · {paroles}"[:TRACE_MAX], genres


def _table(mem):
    mem.db.execute(TABLE)
    mem.db.execute("CREATE INDEX IF NOT EXISTS hippocampe_jour ON hippocampe(jour)")


def remplir(mem, embed=None, limite=None):
    """Une trace pour chaque échange qui n'en a pas encore (d'avant comme de demain) ; rend combien."""
    _table(mem)
    if embed is None:
        import embeddings
        embed = embeddings.embed
    rows = mem.db.execute("""SELECT e.id, e.ts, e.content FROM episodes e LEFT JOIN hippocampe h ON h.episode_id = e.id
        WHERE h.episode_id IS NULL AND e.role = 'episodic' AND e.content LIKE '[Échange avec Ahmed%' ORDER BY e.id"""
                          + (f" LIMIT {int(limite)}" if limite else "")).fetchall()
    maintenant = time.time()
    for eid, ts, content in rows:
        trace, genres = tracer(ts, content)
        jour = time.strftime("%Y-%m-%d", time.localtime(ts))
        mem.db.execute("INSERT OR IGNORE INTO hippocampe(episode_id, ts, jour, trace, genres, embedding, source, maj) VALUES (?,?,?,?,?,?,?,?)",
                       (eid, ts, jour, trace, ",".join(genres), json.dumps([round(float(x), 5) for x in embed(trace)]), "lite", maintenant))
    if rows:
        mem.db.commit()
    return len(rows)


# ---------- les dates d'un indice
_JOUR_NUM = re.compile(r"\b(?:le|du|au|depuis le)\s+(1er|[0-3]?\d)(?:\s+(" + "|".join(MOIS) + r"))?\b", re.I)


def dates_demandees(texte, now=None):
    """Les jours (AAAA-MM-JJ) qu'une question désigne : hier, avant-hier, ce matin, le 29, le 3 novembre, samedi (dernier)."""
    now = time.time() if now is None else now
    t = str(texte or "").lower()
    jours = set()
    d0 = time.localtime(now)
    jour = lambda delta: time.strftime("%Y-%m-%d", time.localtime(now - delta * 86400))
    if re.search(r"\bavant[- ]hier\b", t):
        jours.add(jour(2))
    elif re.search(r"\bhier\b", t):
        jours.add(jour(1))
    if re.search(r"\b(aujourd.hui|ce matin|cette nuit|tout à l.heure|ce soir)\b", t):
        jours.add(jour(0))
    for k, nom in enumerate(JOURS):
        if re.search(rf"\b{nom}\b", t):
            delta = (d0.tm_wday - k) % 7 or 7                       # le dernier passé (jamais aujourd'hui)
            jours.add(jour(delta))
    for num, mois in _JOUR_NUM.findall(t):
        n = 1 if num == "1er" else int(num)
        if not 1 <= n <= 31:
            continue
        if mois:
            m = MOIS.index(mois) + 1
            annee = d0.tm_year if (m, n) <= (d0.tm_mon, d0.tm_mday) else d0.tm_year - 1
            jours.add(f"{annee:04d}-{m:02d}-{n:02d}")
        else:                                                         # le dernier « n » passé
            m, a = d0.tm_mon, d0.tm_year
            if n > d0.tm_mday:
                m, a = (12, a - 1) if m == 1 else (m - 1, a)
            jours.add(f"{a:04d}-{m:02d}-{n:02d}")
    return jours


# ---------- la recherche (gardée en mémoire par le processus du rappel)
class _Index:
    def __init__(self):
        self.ids, self.ts, self.jours, self.textes, self.mat, self.max_id = [], [], [], [], None, 0

    def rafraichir(self, mem):
        import numpy as np
        _table(mem)
        rows = mem.db.execute("SELECT episode_id, ts, jour, trace, embedding FROM hippocampe WHERE episode_id > ? ORDER BY episode_id",
                              (self.max_id,)).fetchall()
        if not rows:
            return self
        vec = []
        for eid, ts, jour, trace, emb in rows:
            try:
                v = np.asarray(json.loads(emb or "[]"), dtype=np.float32)
            except ValueError:
                v = np.zeros(0, np.float32)
            n = float(np.linalg.norm(v)) if v.size else 0.0
            self.ids.append(eid); self.ts.append(ts); self.jours.append(jour); self.textes.append(trace.lower())
            vec.append(v / n if n else v)
            self.max_id = max(self.max_id, eid)
        dims = {v.size for v in vec if v.size}
        d = max(dims) if dims else 0
        neufs = np.stack([v if v.size == d else np.zeros(d, np.float32) for v in vec]) if d else None
        if neufs is not None:
            self.mat = neufs if self.mat is None or self.mat.shape[1] != d else np.vstack([self.mat, neufs])
        return self


_INDEX = {}


def chercher(mem, texte, now=None, embed=None, exclus=(), avant_ts=None, limite=150):
    """[(episode_id, score, special)] : par le sens de la trace (cosinus), et tout ce que la date désigne (special « date »)."""
    import numpy as np
    now = time.time() if now is None else now
    if embed is None:
        import embeddings
        embed = embeddings.embed
    remplir(mem, embed=embed, limite=2000)                         # les échanges neufs ont leur trace au passage
    cle = id(mem.db)
    index = _INDEX.get(cle) or _INDEX.setdefault(cle, _Index())
    index.rafraichir(mem)
    exclus = set(exclus or ())
    avant = now if avant_ts is None else avant_ts
    out = []
    jours = dates_demandees(texte, now)
    if jours:
        for i, j in enumerate(index.jours):
            if j in jours and index.ids[i] not in exclus and index.ts[i] < avant:
                out.append((index.ids[i], 1.0, "date"))
    if index.mat is not None and len(index.ids):
        q = np.asarray(embed(texte), dtype=np.float32)
        if q.size == index.mat.shape[1] and float(np.linalg.norm(q)):
            sims = index.mat @ (q / np.linalg.norm(q))
            dates = {e for e, _, _ in out}
            for i in np.argsort(-sims):
                eid = index.ids[i]
                if eid in exclus or eid in dates or index.ts[i] >= avant:
                    continue
                out.append((eid, float(sims[i]), ""))
                if len(out) - len(dates) >= limite:
                    break
    return out
