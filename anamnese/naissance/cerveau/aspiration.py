"""L'ASPIRATION du PC du papa, en LECTURE SEULE (Ahmed, 13/11 : « comment automatiquement tout récupérer du PC pour le
cerveau de base de son IA »).

- Le papa choisit ses dossiers ; par défaut Documents, Bureau, Images, Musique et Vidéos de son profil Windows, vus depuis
  WSL par /mnt/c/Users/<nom>/ (et leurs doubles OneDrive s'ils existent).
- Rien n'est copié : on lit, on garde un EXTRAIT borné (secrets masqués), une empreinte de sens et des métadonnées dans
  l'inventaire de l'IA (inventaire.db, dans SON dossier de données). Aucun fichier du PC n'est jamais ouvert en écriture.
- Les secrets sont exclus d'office (garde_secrets) AVANT qu'on en garde quoi que ce soit ; un dossier « Banque » n'est
  même pas parcouru. Chaque exclusion est notée avec son genre, jamais son contenu.
- L'index par le sens est fait EN ENTIER (chaque texte) ; la distillation ne lira qu'un échantillon (echantillon.py).
- Reprenable : un fichier inchangé (même taille, même date) n'est pas relu ; on enregistre tous les 50 fichiers ; une
  coupure (budget de temps, arrêt du PC) reprend où elle s'était arrêtée.
- Les noms des personnes (expéditeurs WhatsApp, courriels, carnet d'adresses, auteurs des documents) sont relevés pour le
  filtre d'identité (filtre.py) : ils ne partent jamais en clair chez Claude.
"""
import json
import os
import sqlite3
import struct
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
for _p in (str(ICI), str(RACINE_DEPOT), str(RACINE_DEPOT / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

import extraction            # noqa: E402
import garde_secrets         # noqa: E402

EXTRAIT = 1500                         # caractères gardés dans l'inventaire (masqués)
TAILLE_MAX = {"document": 60 * 1024 * 1024, "courriel": 20 * 1024 * 1024, "discussion": 50 * 1024 * 1024,
              "contacts": 10 * 1024 * 1024}
DOSSIERS_IGNORES = {"appdata", "$recycle.bin", "system volume information", "node_modules", "__pycache__", "venv", ".venv",
                    "site-packages", "my music", "my pictures", "my videos", "ma musique", "mes images", "mes vidéos",
                    "windowsapps", "temp", "tmp", "cache", "caches", "thumbnails"}
FICHIERS_IGNORES = {"desktop.ini", "thumbs.db", "ntuser.dat", ".ds_store"}
# Les dossiers d'un profil Windows (le nom sur le disque est anglais même sous Windows en français : « Bureau » s'affiche,
# « Desktop » existe) et leurs doubles OneDrive (« OneDrive/Bureau », « OneDrive/Documents »…)
PAR_DEFAUT = [("Documents", ["Documents"]), ("Bureau", ["Desktop", "Bureau"]), ("Images", ["Pictures", "Images"]),
              ("Musique", ["Music", "Musique"]), ("Vidéos", ["Videos", "Vidéos"])]
PROFILS_SYSTEME = {"public", "default", "default user", "all users", "defaultapppool", "wsiaccount"}


def profils_windows(racine="/mnt/c/Users"):
    """Les profils Windows vus depuis WSL (sans Public, Default…)."""
    r = Path(racine)
    try:
        return sorted(p for p in r.iterdir() if p.is_dir() and not p.is_symlink() and p.name.lower() not in PROFILS_SYSTEME
                      and not p.name.startswith((".", "$")))
    except OSError:
        return []


def dossiers_par_defaut(profil):
    """[(étiquette, chemin)] : Documents, Bureau, Images, Musique, Vidéos du profil, et leurs doubles OneDrive."""
    profil = Path(profil)
    out = []
    for etiquette, noms in PAR_DEFAUT:
        for base, prefixe in ((profil, ""), (profil / "OneDrive", "OneDrive/")):
            for n in noms:
                p = base / n
                if p.is_dir() and not p.is_symlink() and all(p.resolve() != q.resolve() for _e, q in out):
                    out.append((prefixe + etiquette, p))
                    break
    return out


def _ouvrir(base):
    Path(base).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(base))
    db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS fichiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chemin TEXT UNIQUE, affiche TEXT, genre TEXT, ext TEXT, taille INTEGER,
            mtime REAL, date TEXT, auteur TEXT, titre TEXT, extrait TEXT, meta TEXT, vecteur BLOB, indexe REAL);
        CREATE TABLE IF NOT EXISTS exclus (
            chemin TEXT PRIMARY KEY, affiche TEXT, genre TEXT, niveau TEXT, par TEXT, quand REAL);
        CREATE TABLE IF NOT EXISTS noms (nom TEXT, source TEXT, compte INTEGER, PRIMARY KEY (nom, source));
        CREATE TABLE IF NOT EXISTS etat (cle TEXT PRIMARY KEY, valeur TEXT);
    """)
    return db


def _parties(p, racine, etiquette):
    try:
        rel = Path(p).relative_to(racine)
    except ValueError:
        rel = Path(Path(p).name)
    return [etiquette] + list(rel.parts)


def parcourir(racines, journal_exclus=None):
    """Les fichiers lisibles sous les racines [(étiquette, chemin)] : (étiquette, chemin, parties). Les dossiers
    cachés, système, les liens, et les dossiers dont le NOM est un secret certain (« Banque ») ne sont pas parcourus."""
    for etiquette, racine in racines:
        racine = Path(racine)
        if not racine.is_dir():
            continue
        pile = [racine]
        while pile:
            d = pile.pop()
            try:
                entrees = sorted(os.scandir(d), key=lambda e: e.name)
            except OSError:
                continue
            for e in entrees:
                nom = e.name
                if nom.startswith((".", "~$", "$")) or nom.lower() in FICHIERS_IGNORES:
                    continue
                try:
                    if e.is_symlink():
                        continue
                    est_dossier = e.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                parties = _parties(e.path, racine, etiquette)
                if est_dossier:
                    if nom.lower() in DOSSIERS_IGNORES:
                        continue
                    niveau, genre = garde_secrets.juger_nom(parties[1:])
                    if niveau == garde_secrets.CERTAIN:
                        if journal_exclus:
                            journal_exclus(e.path, "/".join(parties), genre, niveau, "nom du dossier")
                        continue
                    pile.append(Path(e.path))
                elif extraction.type_de(nom):
                    yield etiquette, Path(e.path), parties


def windows_vers_wsl(chemin):
    """« C:\\Users\\x\\OneDrive\\a.docx » → « /mnt/c/Users/x/OneDrive/a.docx »."""
    c = str(chemin).strip().replace("\\", "/")
    if len(c) > 2 and c[1] == ":":
        return f"/mnt/{c[0].lower()}{c[2:]}"
    return c


def wsl_vers_windows(chemin):
    c = str(chemin)
    if c.startswith("/mnt/") and len(c) > 6 and c[6:7] in ("/", ""):
        return f"{c[5].upper()}:{c[6:]}".replace("/", "\\")
    return c


def en_ligne_seulement(racines, executer=None):
    """Les fichiers OneDrive « disponibles en ligne seulement » : les lire depuis WSL les ferait TÉLÉCHARGER (des Go, peut-être).
    Windows le sait (attribut RecallOnDataAccess ou Offline) ; WSL ne le voit pas : une seule question à PowerShell par
    dossier OneDrive, au début. Sans PowerShell (hors Windows), rien n'est en ligne seulement."""
    import shutil
    import subprocess
    ps = shutil.which("powershell.exe")
    if not ps and executer is None:
        return set()
    out = set()
    for _e, racine in racines:
        if "onedrive" not in str(racine).lower():
            continue
        script = (f"Get-ChildItem -LiteralPath '{wsl_vers_windows(racine).replace(chr(39), chr(39) * 2)}' -Recurse -File -Force -ErrorAction SilentlyContinue | "
                  "Where-Object {{ ($_.Attributes -band 0x400000) -or ($_.Attributes -band 0x1000) }} | "
                  "ForEach-Object {{ $_.FullName }}").replace("{{", "{").replace("}}", "}")
        try:
            r = (executer or subprocess.run)([ps or "powershell.exe", "-NoProfile", "-Command", script], capture_output=True,
                                             text=True, timeout=600)
            out |= {windows_vers_wsl(l) for l in (r.stdout or "").splitlines() if l.strip()}
        except (OSError, subprocess.SubprocessError):
            continue
    return out


def _defaut_embed():
    import embeddings
    return embeddings.embed


def _masquer(texte):
    import fichiers
    return fichiers.masquer(texte)


def _noter_noms(db, extrait):
    g, meta = extrait.get("genre"), extrait.get("meta") or {}
    noms = []
    if g == "courriel":
        noms = [(n, "courriel") for n in extraction.noms_du_courriel(meta)]
    elif g == "discussion":
        noms = [(n, "whatsapp") for n in (meta.get("participants") or {})]
    elif g == "contacts":
        noms = [(n, "contacts") for n in meta.get("noms") or []]
    elif g == "document":
        noms = [(n, "auteur") for n in {meta.get("auteur"), meta.get("modifie_par")} if n]
    for n, s in noms:
        n = str(n).strip()[:80]
        if n:
            db.execute("INSERT INTO noms VALUES (?,?,1) ON CONFLICT(nom, source) DO UPDATE SET compte = compte + 1", (n, s))


def _texte_pour_sens(ex):
    meta = ex.get("meta") or {}
    if ex["genre"] == "audio":
        return " — ".join(str(meta.get(k)) for k in ("artiste", "titre", "album", "genre") if meta.get(k))
    return f"{ex.get('titre') or ''}\n{(ex.get('texte') or '')[:2000]}"


def aspirer(racines, sortie, embed=None, juge=None, reintegres=(), budget_s=None, limite=None, decrire=None,
            decrire_max=200, journal=None, nuage=None):
    """Une passe d'aspiration (reprenable). racines : [(étiquette, chemin)]. sortie : le dossier de données de la
    naissance (inventaire.db y est écrit). juge : avis d'un modèle local pour les DOUTES (garde_secrets.juge_ollama) ;
    None = prudence. reintegres : affichages que le papa a réintégrés (doutes seulement). decrire : option coûteuse,
    une fonction (chemin) -> description d'une photo. Rend le rapport."""
    t0 = time.time()
    sortie = Path(sortie)
    db = _ouvrir(sortie / "inventaire.db")
    embed = embed or _defaut_embed()
    reintegres = set(reintegres or ())
    connus = {c: (m, t) for c, m, t in db.execute("SELECT chemin, mtime, taille FROM fichiers")}
    deja_exclus = {c for (c,) in db.execute("SELECT chemin FROM exclus")}
    nuage = en_ligne_seulement(racines) if nuage is None else set(nuage)
    rapport = {"vus": 0, "indexes": 0, "inchanges": 0, "exclus": {}, "par_genre": {}, "temps_par_genre": {}, "decrites": 0,
               "en_ligne_seulement": 0, "complet": False}

    def exclure(chemin, affiche, genre, niveau, par):
        db.execute("INSERT OR REPLACE INTO exclus VALUES (?,?,?,?,?,?)", (str(chemin), affiche, genre, niveau, par, time.time()))
        db.execute("DELETE FROM fichiers WHERE chemin=?", (str(chemin),))
        cle = f"{genre} ({par})"
        rapport["exclus"][cle] = rapport["exclus"].get(cle, 0) + 1

    vus = set()
    interrompu = False
    for etiquette, p, parties in parcourir(racines, journal_exclus=exclure):
        cle = str(p)
        vus.add(cle)
        rapport["vus"] += 1
        affiche = "/".join(parties)
        if cle in nuage:                                   # pas sur le disque : le lire le téléchargerait
            rapport["en_ligne_seulement"] += 1
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if connus.get(cle) == (st.st_mtime, st.st_size) and cle not in deja_exclus:
            rapport["inchanges"] += 1
            continue
        if (budget_s is not None and time.time() - t0 > budget_s) or (limite is not None and rapport["indexes"] >= limite):
            interrompu = True
            break
        genre = extraction.type_de(p)
        t1 = time.time()
        # 1) le NOM d'abord : un fichier certainement secret n'est jamais ouvert
        j = garde_secrets.juger(parties[1:], None, juge=None, reintegre=affiche in reintegres)
        if j.exclu and j.niveau == garde_secrets.CERTAIN:
            exclure(p, affiche, j.genre, j.niveau, j.par)
            continue
        if genre in TAILLE_MAX and st.st_size > TAILLE_MAX[genre]:
            continue
        ex = extraction.extraire(p, genre)
        # 2) le CONTENU (et le doute : l'avis du modèle local, ou la prudence)
        j = garde_secrets.juger(parties[1:], ex.get("texte") if ex.get("texte") else None, juge=juge,
                                reintegre=affiche in reintegres)
        if j.exclu:
            exclure(p, affiche, j.genre, j.niveau, j.par)
            continue
        db.execute("DELETE FROM exclus WHERE chemin=?", (cle,))
        if genre == "photo" and decrire is not None and rapport["decrites"] < decrire_max:
            try:
                ex["texte"] = str(decrire(p) or "")[:2000]
                rapport["decrites"] += 1
            except Exception:
                pass
        texte = _masquer(ex.get("texte") or "")
        ex["texte"] = texte
        a_du_sens = genre in ("document", "courriel", "discussion", "audio") or (genre == "photo" and texte)
        vecteur = None
        if a_du_sens:
            v = embed(_texte_pour_sens(ex))
            vecteur = struct.pack(f"{len(v)}f", *v) if v is not None and len(v) else None
        meta = dict(ex.get("meta") or {})
        if genre == "discussion":
            meta.pop("messages_bruts", None)
        db.execute("INSERT OR REPLACE INTO fichiers (chemin, affiche, genre, ext, taille, mtime, date, auteur, titre, extrait, "
                   "meta, vecteur, indexe) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (cle, affiche, genre, p.suffix.lower(), st.st_size, st.st_mtime, ex.get("date") or "",
                    (ex.get("auteur") or "")[:120], (ex.get("titre") or "")[:200], texte[:EXTRAIT],
                    json.dumps(meta, ensure_ascii=False)[:20000], vecteur, time.time()))
        _noter_noms(db, ex)
        rapport["indexes"] += 1
        rapport["par_genre"][genre] = rapport["par_genre"].get(genre, 0) + 1
        rapport["temps_par_genre"][genre] = rapport["temps_par_genre"].get(genre, 0.0) + (time.time() - t1)
        if rapport["indexes"] % 50 == 0:
            db.commit()
            if journal:
                journal(f"{rapport['indexes']} fichiers lus ({rapport['vus']} vus) en {time.time() - t0:.0f} s")
    if not interrompu:
        # passe complète : un fichier disparu (ou sorti du choix du papa) quitte l'inventaire
        for (c,) in db.execute("SELECT chemin FROM fichiers").fetchall():
            if c not in vus:
                db.execute("DELETE FROM fichiers WHERE chemin=?", (c,))
        rapport["complet"] = True
    rapport["duree_s"] = round(time.time() - t0, 2)
    rapport["total_inventaire"] = db.execute("SELECT COUNT(*) FROM fichiers").fetchone()[0]
    rapport["total_exclus"] = db.execute("SELECT COUNT(*) FROM exclus").fetchone()[0]
    db.execute("INSERT OR REPLACE INTO etat VALUES ('derniere_aspiration', ?)", (json.dumps(rapport, ensure_ascii=False),))
    db.execute("INSERT OR REPLACE INTO etat VALUES ('racines', ?)",
               (json.dumps([[e, str(r)] for e, r in racines], ensure_ascii=False),))
    db.commit()
    db.close()
    return rapport


def lignes(sortie, genres=None):
    """Les fichiers de l'inventaire : [{id, chemin, affiche, genre, date, auteur, titre, extrait, meta, vecteur}]."""
    db = _ouvrir(Path(sortie) / "inventaire.db")
    q = "SELECT id, chemin, affiche, genre, date, auteur, titre, extrait, meta, vecteur, taille FROM fichiers"
    args = ()
    if genres:
        q += f" WHERE genre IN ({','.join('?' * len(genres))})"
        args = tuple(genres)
    out = []
    for i, c, a, g, d, au, t, ex, m, v, ta in db.execute(q, args):
        out.append({"id": i, "chemin": c, "affiche": a, "genre": g, "date": d or "", "auteur": au or "", "titre": t or "",
                    "extrait": ex or "", "meta": json.loads(m or "{}"), "taille": ta or 0,
                    "vecteur": list(struct.unpack(f"{len(v) // 4}f", v)) if v else None})
    db.close()
    return out


def noms_releves(sortie):
    db = _ouvrir(Path(sortie) / "inventaire.db")
    out = [(n, s, c) for n, s, c in db.execute("SELECT nom, source, compte FROM noms ORDER BY compte DESC")]
    db.close()
    return out


def exclusions(sortie):
    db = _ouvrir(Path(sortie) / "inventaire.db")
    out = [{"chemin": c, "affiche": a, "genre": g, "niveau": n, "par": p}
           for c, a, g, n, p in db.execute("SELECT chemin, affiche, genre, niveau, par FROM exclus ORDER BY affiche")]
    db.close()
    return out


def chercher(sortie, question, embed=None, n=10):
    """Les fichiers les plus proches par le sens (l'index de l'IA : « le document où papa parlait de la collection »)."""
    import numpy as np
    embed = embed or _defaut_embed()
    rows = [r for r in lignes(sortie) if r["vecteur"]]
    if not rows:
        return []
    q = np.asarray(embed(question), dtype=np.float32)
    m = np.vstack([np.asarray(r["vecteur"], dtype=np.float32) for r in rows])
    sens = (m @ q) / ((np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-12)
    ordre = np.argsort(-sens)[:n]
    return [{"affiche": rows[i]["affiche"], "score": float(sens[i]), "extrait": rows[i]["extrait"][:300]} for i in ordre]
