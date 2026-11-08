"""L'index PAR LE SENS des fichiers d'Ahmed (lot E, point 43 de la liste de Hakim du 2026-10-19).

Hakim peut déjà chercher un fichier par son nom ou par un mot exact. Ici, il cherche par le SENS : « le
document où je parlais du devis du site », « mes notes sur le robot ». Chaque document lisible (texte,
markdown, PDF, Word, PowerPoint, Excel, code léger) a une empreinte de sens (embedding model2vec, local,
gratuit) calculée sur son nom et son début. Lecture seule ; les secrets sont masqués dans les extraits
(jarvis/fichiers.masquer) ; les dossiers cachés, Library, node_modules, venvs et sauvegardes sont exclus.
Incrémental : un fichier inchangé (même date de modification) n'est pas relu ; un fichier disparu sort de
l'index. Construit la nuit par le démon, par tranches bornées en temps.
"""
import functools
import re
import sqlite3
import struct
import sys
import time
from pathlib import Path

import config

BASE = config.DATA_DIR / "index_fichiers.db"
RACINES = [Path.home() / d for d in ("Desktop", "Documents", "Downloads")] + [
    Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs", Path.home() / "AIOS" / "jarvis" / "cwd" / "fichiers",
    Path.home() / "AIOS" / "jarvis" / "cwd" / "atelier"]                  # le travail de Hakim lui-même (maths, plans…)
# des DOCUMENTS et du code ; pas les données (.json, .csv : 28 000 fichiers sur 34 000 le 19/10, du bruit)
EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".tex", ".py", ".js", ".ts", ".tsx", ".sh", ".pdf", ".docx",
              ".doc", ".rtf", ".odt", ".pptx", ".xlsx"}
DOSSIERS_EXCLUS = {"node_modules", "__pycache__", "venv", "env", "dist", "build", "Library", "backups", "site-packages",
                   "Pods", "DerivedData", "target", "vendor"}
TAILLE_MAX = 20 * 1024 * 1024
EXTRAIT = 4000


def _embed(texte):
    import embeddings
    return embeddings.embed(texte)


_FICHIERS = None


def _fichiers():
    global _FICHIERS
    if _FICHIERS is None:
        ici = str(Path(__file__).resolve().parent / "jarvis")
        if ici not in sys.path:
            sys.path.append(ici)
        import fichiers
        _FICHIERS = fichiers
    return _FICHIERS


def _ouvrir(base):
    Path(base).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(base))
    db.execute("CREATE TABLE IF NOT EXISTS fichiers (chemin TEXT PRIMARY KEY, mtime REAL, taille INTEGER, titre TEXT, "
               "extrait TEXT, vecteur BLOB, indexe REAL)")
    return db


def _candidats(racines):
    for racine in racines:
        racine = Path(racine)
        if not racine.is_dir():
            continue
        pile = [racine]
        while pile:
            d = pile.pop()
            try:
                entrees = list(d.iterdir())
            except OSError:
                continue
            for p in entrees:
                if p.name.startswith(".") or p.is_symlink():
                    continue
                f = _fichiers()
                if p.is_dir():
                    # (relecture Opus du 2026-10-20) ni dossier protégé (sans casse), ni intérieur de Hakim
                    if p.name not in DOSSIERS_EXCLUS and not f._dossier_interdit(p.name) \
                            and not (f._interieur(p) and not f._mene_a_une_exception(p)) \
                            and not p.name.endswith((".app", ".photoslibrary", ".venv")) and not _secret(p.name):
                        pile.append(p)
                elif p.suffix.lower() in EXTENSIONS and not _secret(p.name) and not f._interieur(p):
                    yield p


@functools.lru_cache(maxsize=65536)
def _secret(nom):
    """Relecture Opus du 2026-10-20 : l'index contournait la garde des secrets de preparer_fichier (« wallet-seed-
    phrase.md » sortait en entier) : la même garde par le nom, pour indexer ET pour répondre."""
    f = _fichiers()
    return bool(f._SECRETS.search(f._normaliser(str(nom))))


def _texte(p):
    import occupations
    try:
        if p.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".sh"}:
            return occupations.texte_document(p)
        # (relecture indépendante du 27/10, B) dans ses dossiers, une copie privée vérifiée, jamais le chemin énuméré
        # des minutes plus tôt (un dossier échangé entre-temps contre un lien faisait indexer ce qui est fermé)
        with _fichiers().copie_privee(p, TAILLE_MAX) as q:
            return _fichiers().masquer(q.read_bytes()[:EXTRAIT * 2].decode("utf-8", errors="replace"))
    except Exception:
        return ""


def indexer(racines=None, base=None, budget_s=600, limite=5000):
    """Une tranche d'indexation (au plus budget_s secondes). Rend le nombre de fichiers (ré)indexés."""
    t0 = time.time()
    db = _ouvrir(base or BASE)
    connus = dict(db.execute("SELECT chemin, mtime FROM fichiers"))
    vus = set()
    faits = 0
    for p in sorted(_candidats(racines or RACINES), key=lambda x: -x.stat().st_mtime if x.exists() else 0):
        cle = str(p)
        vus.add(cle)
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_size > TAILLE_MAX or connus.get(cle) == st.st_mtime:
            continue
        if time.time() - t0 > budget_s or faits >= limite:
            break
        texte = _texte(p)[:EXTRAIT]
        titre = p.stem.replace("_", " ").replace("-", " ")
        v = _embed(f"{titre}\n{texte[:2000]}")
        db.execute("INSERT OR REPLACE INTO fichiers VALUES (?,?,?,?,?,?,?)",
                   (cle, st.st_mtime, st.st_size, titre, texte[:1200], struct.pack(f"{len(v)}f", *v), time.time()))
        faits += 1
        if faits % 50 == 0:
            db.commit()                                   # jamais une transaction de 15 min (relecture du 2026-10-20)
    else:
        # parcours complet : les fichiers disparus (ou devenus secrets par leur nom) sortent de l'index
        for cle in set(connus) - vus:
            if not Path(cle).exists() or any(_secret(x) for x in Path(cle).parts) or _fichiers()._interieur(Path(cle)):
                db.execute("DELETE FROM fichiers WHERE chemin=?", (cle,))
    db.commit()
    db.close()
    return faits


def chercher(question, base=None, n=10):
    """Les fichiers les plus proches par le sens : [{chemin, score, titre, extrait}]."""
    import numpy as np
    db = _ouvrir(base or BASE)
    lignes = [x for x in db.execute("SELECT chemin, titre, extrait, vecteur FROM fichiers").fetchall()
              if not any(_secret(n) for n in Path(x[0]).parts) and not _fichiers()._interieur(Path(x[0]))]
    db.close()
    if not lignes:
        return []
    q = np.asarray(_embed(question), dtype=np.float32)
    # toutes les proximités d'un coup (avant : une boucle Python, ~1 s pour 7 000 fichiers)
    m = np.vstack([np.frombuffer(b, dtype=np.float32) for *_, b in lignes])
    sens = (m @ q) / ((np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-12)
    # Le sens seul rate les noms propres (vu le 19/10 : « papier Al-Husban » ne trouvait pas le papier
    # Al-Husban) : les mots de la question présents dans le nom du fichier ou dans son début comptent aussi.
    mots = [m for m in _sans_accents(question).replace("-", " ").split() if len(m) >= 4]
    res = []
    for (chemin, titre, extrait, _), score in zip(lignes, sens.tolist()):
        if mots:
            nom = _sans_accents(" ".join(Path(chemin).parts[-3:]) + " " + (titre or ""))   # le dossier compte aussi
            debut = _sans_accents((extrait or "")[:1200])
            score += 0.25 * sum(m in nom for m in mots) / len(mots) + 0.15 * sum(m in debut for m in mots) / len(mots)
        res.append({"chemin": chemin, "score": score, "titre": titre, "extrait": (extrait or "")[:300]})
    return sorted(res, key=lambda x: -x["score"])[:n]


_MARQUES = re.compile("[\u0300-\u036f\u064b-\u065f\u0670]")      # accents latins, voyelles brèves arabes


def _sans_accents(t):
    import unicodedata
    return _MARQUES.sub("", unicodedata.normalize("NFD", str(t).lower()))


if __name__ == "__main__":
    t = time.time()
    print(f"{indexer(budget_s=float(sys.argv[1]) if len(sys.argv) > 1 else 600)} fichier(s) indexé(s) en {time.time() - t:.0f} s")
