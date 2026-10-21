"""Jarvis voit et lit les fichiers (demande d'Ahmed, 2026-10-16).

Claude lit seul les images courantes, les PDF et le texte (outil Read) : on les lui rend tels
quels. Le reste est PRÉPARÉ, une fois (cache par chemin, taille et date) :
- Word, RTF, ODT, HTML : textutil (fourni avec macOS) ;
- PowerPoint, Excel : le texte de leur XML (zip), sans dépendance ;
- HEIC, TIFF, BMP : sips (macOS) → JPEG ;
- vidéo : ffmpeg → au plus IMAGES_MAX images clés réparties + transcription de la bande son ;
- audio : transcription (Whisper, jarvis/stt.py).
Garde : seulement sous les racines autorisées, jamais un secret (.env, clés, .ssh, trousseau…),
pas d'évasion par lien symbolique. La garde est dans le code, pas dans la consigne.
"""
import hashlib
import html
import json
import os
import re
import shutil
import stat
import subprocess
import time
import unicodedata
import zipfile
from pathlib import Path

ACCUEIL = Path.home() / "AIOS" / "jarvis" / "cwd" / "fichiers"          # les pièces jointes de la page
# Tout le dossier d'Ahmed (demande du 2026-10-16 : « est-ce que Jarvis a accès à tous mes fichiers ? »),
# iCloud Drive et les disques branchés ; restent fermés : dossiers cachés (.ssh, .aws, .config…), la
# Bibliothèque (mails, messages, cookies, trousseaux) et les fichiers de secrets. Le contenu lu est
# MASQUÉ (clés, jetons, mots de passe) avant que Jarvis le voie.
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
RACINES = [ACCUEIL, Path.home(), ICLOUD, Path("/Volumes")]
_J = Path.home() / "AIOS" / "jarvis"
_AIOS = Path.home() / "AIOS"
# tout ~/AIOS est fermé (le cockpit et ses secrets : passkey, jeton, notifications ; la maison de Hakim), sauf son
# dossier de travail cwd (relecture JARVIS 2, H1, 2026-10-20 : ~/AIOS/cockpit était lisible)
INTERIEURS = [(_AIOS.resolve() if _AIOS.exists() else _AIOS, (_J / "cwd").resolve() if (_J / "cwd").exists() else _J / "cwd"),
              ((Path.home() / "Desktop" / "anamnese" / "data"), None)]
SORTIE = ACCUEIL / ".prepares"
IMAGES_MAX = 12
TEXTE_MAX = 120_000
COPIE_MAX = 100 * 1024 * 1024            # au-delà, on ne copie pas dans le dossier de Jarvis
TRANSCRIPTION_MAX_S = 30 * 60            # la bande son est transcrite sur ses 30 premières minutes
GARDE_PREPARES_J = 7                     # les préparations sont purgées après 7 jours
GARDE_PIECES_J = 30                      # les pièces jointes, après 30 jours
FFMPEG = shutil.which("ffmpeg") or "/usr/local/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/usr/local/bin/ffprobe"

DIRECTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".md", ".markdown", ".csv", ".tsv",
           ".json", ".yaml", ".yml", ".xml", ".py", ".js", ".ts", ".tsx", ".jsx", ".swift", ".html", ".css",
           ".sh", ".sql", ".log", ".ipynb", ".tex", ".srt", ".vtt"}
TEXTUTIL = {".docx", ".doc", ".rtf", ".rtfd", ".odt", ".webarchive", ".wordml"}
IMAGES_A_CONVERTIR = {".heic", ".heif", ".tif", ".tiff", ".bmp"}
VIDEOS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}
AUDIOS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus", ".aiff", ".aif"}

# Noms et dossiers qu'aucune demande ne fait lire (clés, mots de passe, sessions). Relecture Opus
# (2026-10-16) : liste élargie, noms normalisés (NFKC, caractères invisibles retirés) avant le test.
_SECRETS = re.compile(
    r"((^|[-_ .])\.?env(\.|$))|(^id_(rsa|dsa|ecdsa|ed25519))|(\.(pem|key|p8|p12|pfx|jks|keystore|keychain-db|keychain"
    r"|kdbx|asc|gpg|ovpn|htpasswd)$)|secret|credential|password|passwd|mots?.?de.?passe|\bmdp\b|identifiant|login"
    r"|(^|[^a-z])tokens?([^a-z]|$)|api.?key|cl[eé]s?.?api|adminsdk|service.?account|seed.?phrase|(^|[^a-z])seed([^a-z]|$)"
    r"|wallet|mnemonic|private.?key|code.{0,4}acc[eè]s|(^|[^a-z])cookies?([^a-z]|$)|\.netrc$|\.npmrc$|\.pypirc$|shadow|bitwarden|1password|lastpass"
    # (JARVIS 2, H1) : les noms français et ceux du cockpit
    r"|(^|[^a-z])jetons?([^a-z]|$)|(^|[^a-z])cl[eé]s?([^a-z]|$)|passkey|webauthn|vapid|(^|[^a-z])verrou([^a-z]|$)", re.I)
_DOSSIERS_INTERDITS = {".ssh", ".aws", ".gnupg", ".config", ".kube", ".docker", "Keychains", "Library"}


_INTERDITS_CF = {x.casefold() for x in _DOSSIERS_INTERDITS}


def _dossier_interdit(nom):
    """Un dossier caché ou protégé — sans casse (relecture Opus du 2026-10-20 : « library » passait ; APFS ignore la
    casse)."""
    return nom.startswith(".") or nom.casefold() in _INTERDITS_CF


def _sous(p, base):
    a, b = os.path.normcase(str(p)).casefold(), os.path.normcase(str(base)).casefold().rstrip("/")
    return a == b or a.startswith(b + "/")


def _interieur(p):
    """L'intérieur du système de Hakim (~/AIOS sauf son cwd, la base brute de la mémoire), sans casse."""
    return any(_sous(p, interdit) and not (sauf and _sous(p, sauf)) for interdit, sauf in INTERIEURS)


def _mene_a_une_exception(p):
    """Un dossier intérieur qui CONTIENT une exception (~/AIOS contient cwd) : on y descend, sans en lire le reste."""
    return any(sauf and _sous(sauf, p) for _i, sauf in INTERIEURS)


def _normaliser(nom):
    return "".join(c for c in unicodedata.normalize("NFKC", nom) if unicodedata.category(c) != "Cf")


class Refus(Exception):
    pass


def verifier(chemin, racines=None, accueil=None):
    """Le chemin réel (liens résolus), s'il est lisible par Jarvis ; sinon Refus avec la raison.
    Une pièce jointe (dans `accueil`) a été choisie par Ahmed lui-même : seul le test des noms de
    secrets est levé pour elle."""
    racines = [Path(r).resolve() for r in (racines or RACINES)]
    p = Path(os.path.expanduser(str(chemin)))
    try:
        reel = p.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Refus(f"fichier introuvable : {chemin}")
    if not any(reel == r or r in reel.parents for r in racines):
        raise Refus("hors des dossiers autorisés (pièces jointes, Bureau, Documents, Téléchargements, Images, Vidéos)")
    # la racine la plus précise (iCloud est dans ~/Library, refusée depuis la racine du dossier)
    racine = max((r for r in racines if reel == r or r in reel.parents), key=lambda r: len(r.parts))
    for partie in reel.relative_to(racine).parts[:-1]:
        if _dossier_interdit(partie):
            raise Refus(f"dossier protégé ou caché ({partie})")
    # L'intérieur du système de Hakim (relecture du 2026-10-20) : ses réglages et secrets techniques
    # (~/AIOS/jarvis : clés de notification, verrou du téléphone, empreinte vocale…) et la base brute de la mémoire
    # ne se lisent pas par ses outils de fichiers — sauf son dossier de travail (cwd).
    if _interieur(reel):
        raise Refus("fichier interne de Hakim (réglages, secrets techniques, base de la mémoire) : refusé")
    accueil = Path(accueil or ACCUEIL).resolve()
    jointe = reel == accueil or accueil in reel.parents
    if not jointe and _SECRETS.search(_normaliser(reel.name)):
        raise Refus("fichier protégé : il peut contenir un secret (clé, mot de passe, .env)")
    if not reel.is_file():
        raise Refus("ce n'est pas un fichier")
    return reel


def _dossier_cache(reel, sortie):
    st = reel.stat()
    cle = hashlib.sha1(f"{reel}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
    d = Path(sortie) / cle
    d.mkdir(parents=True, exist_ok=True)
    return d


OFFICE_MEMBRE_MAX = 30 * 1024 * 1024           # une « bombe zip » ne gonfle jamais la mémoire (relecture Opus)
OFFICE_TOTAL_MAX = 80 * 1024 * 1024


def _lire_membre(z, nom, lu):
    """Lit un membre du zip en refusant les tailles déraisonnables ; lu = [octets déjà lus]."""
    taille = z.getinfo(nom).file_size
    if taille > OFFICE_MEMBRE_MAX or lu[0] + taille > OFFICE_TOTAL_MAX:
        raise Refus(f"document Office trop gros une fois décompressé ({taille // (1024 * 1024)} Mo pour {nom})")
    with z.open(nom) as f:
        data = f.read(OFFICE_MEMBRE_MAX + 1)
    if len(data) > OFFICE_MEMBRE_MAX:
        raise Refus("document Office trop gros une fois décompressé")
    lu[0] += len(data)
    return data


def _texte_xml(z, noms, balise, lu=None):
    lu = lu if lu is not None else [0]
    morceaux = []
    for nom in noms:
        xml = _lire_membre(z, nom, lu).decode("utf-8", "replace")
        morceaux.append(" ".join(html.unescape(t) for t in re.findall(rf"<{balise}[^>]*>([^<]*)</{balise}>", xml)))
    return morceaux


def _num(nom):
    m = re.search(r"(\d+)\.xml$", nom)
    return int(m.group(1)) if m else 0


def _office_zip(reel):
    lu = [0]
    with zipfile.ZipFile(reel) as z:
        noms = z.namelist()
        if reel.suffix.lower() == ".pptx":
            diapos = sorted((n for n in noms if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=_num)
            return "\n".join(f"[diapo {i}] {t}" for i, t in enumerate(_texte_xml(z, diapos, "a:t", lu), 1))
        textes = _texte_xml(z, [n for n in noms if n == "xl/sharedStrings.xml"], "t", lu)
        feuilles = sorted((n for n in noms if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=_num)
        nombres = [" ".join(re.findall(r"<v>([^<]*)</v>", _lire_membre(z, f, lu).decode("utf-8", "replace"))) for f in feuilles]
        return "Textes : " + " | ".join(textes) + ("\nValeurs : " + " | ".join(nombres) if any(nombres) else "")


# ---- Relecture JARVIS 2 (2026-10-20) ----
# H2 : entre la vérification d'un chemin et sa lecture, le fichier pouvait être échangé (un lien vers ~/.aws posé en
# boucle par une tâche de fond). Désormais le fichier est OUVERT sans suivre de lien, son vrai chemin relu sur le
# descripteur (F_GETPATH) et revérifié, puis copié dans un INSTANTANÉ : tout le reste travaille sur cette copie.
# H3 : les décodeurs (ffmpeg, ffprobe, textutil, sips) traitent des fichiers venus d'internet ; ils tournent sous un bac à
# sable « tout refusé par défaut » : lecture du système et de l'instantané, écriture dans son seul dossier, pas de réseau.
INSTANTANE_MAX = 2 * 1024 * 1024 * 1024


def _instantane(reel, d, racines=None, accueil=None):
    """La copie vérifiée du fichier dans le dossier de préparation `d` (rend son chemin)."""
    try:
        # O_NONBLOCK : un fichier remplacé par un tube nommé (FIFO) ne fige pas le serveur à l'ouverture ; il est
        # ensuite refusé (pas un fichier ordinaire) — relecture Opus du 2026-10-20
        fd = os.open(reel, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e:
        raise Refus(f"fichier illisible ({e.strerror})")
    try:
        try:
            import fcntl
            vrai = Path(os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024)).split("\0", 1)[0])
        except (ImportError, AttributeError, OSError):
            vrai = Path(reel)
        if vrai != Path(reel) and verifier(vrai, racines, accueil) != vrai:
            raise Refus("le fichier a changé pendant qu'on le préparait : refusé")
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refus("ce n'est pas un fichier ordinaire")
        if st.st_size > INSTANTANE_MAX:
            raise Refus(f"trop lourd ({st.st_size // (1024 * 1024)} Mo ; {INSTANTANE_MAX // (1024 * 1024)} Mo au plus)")
        copie = Path(d) / f"source{Path(reel).suffix.lower()}"
        with open(copie, "wb") as h:
            while True:
                bloc = os.read(fd, 1 << 20)
                if not bloc:
                    break
                h.write(bloc)
        return copie
    finally:
        os.close(fd)


def _temp_utilisateur():
    """Le dossier temporaire de l'utilisateur pour macOS (sips y écrit un fichier au nom UUID, quoi que dise TMPDIR)."""
    try:
        t = subprocess.run(["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True, timeout=5).stdout.strip()
        return str(Path(t).resolve()) if t else None
    except (OSError, subprocess.SubprocessError):
        return None


def _profil_decodeur(lecture, ecriture):
    import terminal                                  # (relecture Opus du 2026-10-20) la MÊME liste que le terminal
    services = "".join(f' (global-name "{n}")' for n in terminal.SERVICES_REFUSES)
    t = _temp_utilisateur()
    # seulement des fichiers au nom d'UUID (parfois précédé d'un point) directement dans ce dossier : ceux que sips crée
    temp = f'\n(allow file-read* file-write* (regex #"^{re.escape(t)}/\\.?[0-9A-F][0-9A-F-]+[0-9A-Fa-z-]*$"))' if t else ""   # (pas de {{n}} en SBPL)
    return f"""(version 1)
(deny default)
(import "system.sb")
(allow process-fork)
(allow process-exec (subpath "/usr/bin") (subpath "/usr/local") (subpath "/opt/homebrew") (subpath "/System"))
(allow sysctl-read)
(allow system-info)
(allow file-read-metadata)
(allow file-read* (literal "/") (subpath "/usr") (subpath "/System") (subpath "/Library") (subpath "/opt") (subpath "/private/etc")
  (subpath "/private/var/db/timezone") (literal "/dev") (literal "/dev/null") (literal "/dev/zero") (literal "/dev/random") (literal "/dev/urandom") (literal "/dev/tty") (literal "/dev/dtracehelper") (literal "/dev/autofs_nowait") (regex #"^/dev/fd/") (literal "{lecture}") (subpath "{ecriture}"))
(deny file-read* (subpath "/Library/Keychains") (subpath "/Library/Application Support/com.apple.TCC"))
(allow file-write* (subpath "{ecriture}") (literal "/dev/null") (literal "/dev/dtracehelper")){temp}
(allow mach-lookup)
(deny mach-lookup{services})
(allow iokit-open)
(allow ipc-posix-shm*)
(allow user-preference-read)
"""


def _decoder(args, lecture, ecriture, timeout=120, texte=False):
    """Un décodeur sous bac à sable : il ne lit que `lecture` (et le système), n'écrit que dans `ecriture`, sans réseau."""
    regles = _profil_decodeur(Path(lecture).resolve(), Path(ecriture).resolve())
    return subprocess.run(["/usr/bin/sandbox-exec", "-p", regles, *[str(a) for a in args]], capture_output=True, text=texte,
                          timeout=timeout, stdin=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(ecriture),
                                                                           "TMPDIR": str(ecriture), "LANG": "fr_FR.UTF-8"})


def _duree(reel):
    r = _decoder([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(reel)], reel, Path(reel).parent,
                 timeout=60, texte=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError):
        return None


def _a_du_son(reel):
    r = _decoder([FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                  str(reel)], reel, Path(reel).parent, timeout=60, texte=True)
    return bool(r.stdout.strip())


def _transcrire_whisper(fichier):
    import stt
    r = stt.transcrire(str(fichier))
    return r.get("texte", "")


def preparer(chemin, racines=None, sortie=None, transcrire=None, accueil=None):
    """{"lire": [chemins à ouvrir avec Read], "texte": extrait ou transcription, "note", "duree_s"}.

    Read de Claude ne lit que dans son dossier de travail (vérifié en réel le 2026-10-16) : un
    fichier lisible tel quel mais situé ailleurs (Bureau…) est copié dans le cache, APRÈS la garde."""
    accueil = Path(accueil or ACCUEIL).resolve()
    reel = verifier(chemin, racines, accueil)
    ext = reel.suffix.lower()
    res = {"fichier": str(reel), "lire": [], "texte": "", "note": "", "duree_s": None}
    if ext in DIRECTS and (reel == accueil or accueil in reel.parents):
        res["lire"] = [str(reel)]
        return res
    purger(sortie or SORTIE, accueil)
    d = _dossier_cache(reel, sortie or SORTIE)
    if ext in DIRECTS:
        if reel.stat().st_size > COPIE_MAX:
            raise Refus(f"trop lourd pour être copié ({reel.stat().st_size // (1024 * 1024)} Mo, {COPIE_MAX // (1024 * 1024)} Mo au plus)")
        copie = d / reel.name
        if not copie.exists():
            source = _instantane(reel, d, racines, accueil)        # (H2) lu par le descripteur vérifié
            if ext in TEXTES_A_MASQUER:                    # le texte arrive à Jarvis avec ses secrets masqués
                brut = source.read_bytes()
                try:
                    texte = brut.decode("utf-8")
                except UnicodeDecodeError:                 # (relecture du 2026-10-20) jamais de copie NON masquée
                    texte = brut.decode("latin-1")
                try:
                    copie.write_text(masquer(texte), encoding="utf-8")
                finally:
                    source.unlink(missing_ok=True)
            else:
                os.replace(source, copie)
        res["lire"] = [str(copie)]
        res["note"] = "copié dans le dossier de Jarvis pour être lu" + (" (secrets masqués)" if ext in TEXTES_A_MASQUER else "")
        return res
    fait = d / "preparation.json"
    if fait.exists():
        try:
            return json.loads(fait.read_text(encoding="utf-8"))
        except ValueError:
            pass
    source = _instantane(reel, d, racines, accueil)                # (H2) tout travaille sur cette copie vérifiée
    try:
        return _preparer_depuis(source, reel, ext, d, res, fait, transcrire)
    finally:
        # (relecture Opus du 2026-10-20) l'instantané BRUT (non masqué) ne reste jamais dans le dossier de Jarvis :
        # le terminal et le Read de Hakim y lisent
        source.unlink(missing_ok=True)


def _preparer_depuis(source, reel, ext, d, res, fait, transcrire):
    if ext in TEXTUTIL:
        r = _decoder(["/usr/bin/textutil", "-convert", "txt", "-stdout", str(source)], source, d)
        res["texte"] = masquer(r.stdout.decode("utf-8", "replace"))[:TEXTE_MAX]
        res["note"] = "texte extrait (textutil)" if r.returncode == 0 else "extraction impossible"
    elif ext in (".pptx", ".xlsx"):
        try:
            res["texte"] = masquer(_office_zip(source))[:TEXTE_MAX]
            res["note"] = "texte extrait du fichier Office"
        except (zipfile.BadZipFile, KeyError) as e:
            res["note"] = f"fichier Office illisible : {e}"
    elif ext in IMAGES_A_CONVERTIR:
        jpg = d / (reel.stem + ".jpg")
        _decoder(["/usr/bin/sips", "-s", "format", "jpeg", str(source), "--out", str(jpg)], source, d)
        res["lire"] = [str(jpg)] if jpg.exists() else []
        res["note"] = "converti en JPEG" if jpg.exists() else "conversion impossible"
    elif ext in VIDEOS or ext in AUDIOS:
        transcrire = transcrire or _transcrire_whisper
        duree = _duree(source)
        res["duree_s"] = duree
        if ext in VIDEOS:
            n = IMAGES_MAX if not duree else max(1, min(IMAGES_MAX, int(duree // 2) or 1))
            pas = (duree or IMAGES_MAX) / n
            for i in range(n):
                img = d / f"image-{i + 1:02d}.jpg"
                _decoder([FFMPEG, "-loglevel", "error", "-y", "-ss", f"{(i + 0.5) * pas:.2f}", "-i", str(source),
                          "-frames:v", "1", "-vf", "scale='min(768,iw)':-2", str(img)], source, d)
                if img.exists():
                    res["lire"].append(str(img))
        if ext in AUDIOS or _a_du_son(source):
            son = d / "son.wav"
            _decoder([FFMPEG, "-loglevel", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                      "-t", str(TRANSCRIPTION_MAX_S), str(son)], source, d, timeout=600)
            if son.exists():
                res["texte"] = (transcrire(son) or "")[:TEXTE_MAX]
                son.unlink(missing_ok=True)
        res["note"] = (f"{len(res['lire'])} images clés réparties sur la vidéo" if ext in VIDEOS else "audio") + \
            (", transcription de la bande son" if res["texte"] else ", pas de parole transcrite")
    else:
        res["note"] = f"format {ext or 'sans extension'} : je ne sais pas encore le lire"
        return res
    fait.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def purger(sortie=None, accueil=None, force=False):
    """Supprime les préparations de plus de GARDE_PREPARES_J jours et les pièces jointes de plus de
    GARDE_PIECES_J jours (au plus une fois par heure, sauf force)."""
    sortie, accueil = Path(sortie or SORTIE), Path(accueil or ACCUEIL)
    marque = sortie / ".purge"
    maintenant = time.time()
    try:
        if not force and maintenant - marque.stat().st_mtime < 3600:
            return
    except OSError:
        pass
    for d in (sortie.iterdir() if sortie.is_dir() else []):
        if d.is_dir() and maintenant - d.stat().st_mtime > GARDE_PREPARES_J * 86400:
            shutil.rmtree(d, ignore_errors=True)
    for f in (accueil.iterdir() if accueil.is_dir() else []):
        if f.is_file() and maintenant - f.stat().st_mtime > GARDE_PIECES_J * 86400:
            f.unlink(missing_ok=True)
    try:
        sortie.mkdir(parents=True, exist_ok=True)
        marque.touch()
    except OSError:
        pass


# ---- les secrets masqués dans le contenu (comme le fait robot-ia avant que le modèle voie un fichier)
TEXTES_A_MASQUER = DIRECTS - {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
_MASQUES = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S), "[CLÉ PRIVÉE MASQUÉE]"),
    (re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
                r"|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"
                r"|glpat-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"),
     "[SECRET MASQUÉ]"),
    # (relecture Opus du 2026-10-20) une valeur ENTRE GUILLEMETS, même avec des espaces ou des virgules
    # (« "password": "correct horse battery" »), les variables d'environnement (PGPASSWORD=…) et les clés Web Push
    (re.compile(r"(?i)\b((?:[a-z0-9_]*_)?(?:(?:api[_-]?key|secret|token|jeton|password|passwd|pwd|mot[_ ]de[_ ]passe|access[_-]?key"
                r"|private[_-]?key|client[_-]?secret|cl[eé][_ -]?(?:api|secr[eè]te|priv[ée]e)|passkey|credential)"
                r"[a-z0-9_]*[\"']?|(?<=[\"'])cl[eé][\"'])\s*[:=]\s*)([\"'])((?:(?!\2)[^\n]){4,300})\2"), r"\1\2[MASQUÉ]\2"),
    (re.compile(r"\b([A-Z][A-Z0-9_]*(?:PASSWORD|PASSWD|_PASS|TOKEN|SECRET|_KEY|APIKEY))\s*=\s*[^\s;&|]+"), r"\1=[MASQUÉ]"),
    (re.compile(r"(?i)([\"'](?:auth|p256dh)[\"']\s*:\s*[\"'])[A-Za-z0-9_\-+/=]{8,}([\"'])"), r"\1[MASQUÉ]\2"),
    # (JARVIS 2, H1) : aussi le JSON — « "api_key": "…" » (un guillemet entre le nom et « : ») — et les noms français
    (re.compile(r"(?i)\b((?:[a-z0-9_]*_)?(?:(?:api[_-]?key|secret|token|jeton|password|passwd|pwd|mot[_ ]de[_ ]passe|access[_-]?key"
                r"|private[_-]?key|client[_-]?secret|cl[eé][_ -]?(?:api|secr[eè]te|priv[ée]e)|passkey|credential)"
                r"[a-z0-9_]*[\"']?|(?<=[\"'])cl[eé][\"'])\s*[:=]\s*)([\"']?)((?=[^\s\"',;]*\d)[^\s\"',;]{6,}|[^\s\"',;]{12,})\2"),
     r"\1\2[MASQUÉ]\2"),                      # une valeur sans chiffre doit être longue : « les tokens : quelques » n'est pas un secret
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^:/\s@]+:)([^@\s/]+)(@)"), r"\1[MASQUÉ]\3"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]{16,}=*"), r"\1[MASQUÉ]"),
]


def masquer(texte):
    """Le texte avec ses secrets masqués : clés d'API, jetons, mots de passe, clés privées."""
    for motif, remplacement in _MASQUES:
        texte = motif.sub(remplacement, texte)
    return texte


def lister(chemin=None, racines=None, maximum=200):
    """Le contenu d'un dossier (dossiers d'abord), sans les cachés ni les protégés."""
    racines = [Path(r).resolve() for r in (racines or RACINES)]
    d = Path(os.path.expanduser(str(chemin or "~"))).resolve()
    if not any(d == r or r in d.parents for r in racines if r.exists()):
        raise Refus("hors des dossiers lisibles")
    racine = max((r for r in racines if d == r or r in d.parents), key=lambda r: len(r.parts))
    for partie in d.relative_to(racine).parts:
        if _dossier_interdit(partie):
            raise Refus(f"dossier protégé ou caché ({partie})")
    # (relecture Opus du 2026-10-20) lister et chercher dans ~/AIOS ou la base de la mémoire passaient (H1a incomplet)
    if _interieur(d) and not _mene_a_une_exception(d):
        raise Refus("dossier interne de Hakim (réglages, secrets techniques, base de la mémoire) : refusé")
    if not d.is_dir():
        raise Refus("ce n'est pas un dossier")
    elements = []
    for e in sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        if _dossier_interdit(e.name) or (_interieur(e) and not _mene_a_une_exception(e)):
            continue
        try:
            st = e.stat()
        except OSError:
            continue
        if e.is_dir():
            elements.append(f"[dossier] {e.name}/")
        else:
            taille = st.st_size
            t = f"{taille} o" if taille < 1024 else (f"{taille // 1024} Ko" if taille < 1024 ** 2 else f"{taille / 1024 ** 2:.1f} Mo")
            elements.append(f"{e.name} ({t}, {time.strftime('%Y-%m-%d', time.localtime(st.st_mtime))})"
                            + ("  [secret : refusé]" if _SECRETS.search(_normaliser(e.name)) else ""))
        if len(elements) >= maximum:
            elements.append("… (liste tronquée)")
            break
    return str(d), elements


def chercher_contenu(texte, dossier=None, racines=None, maximum=40, budget_s=20, taille_max=2 * 1024 * 1024):
    """Les fichiers TEXTE sous `dossier` qui contiennent `texte` (sans casse), avec la ligne trouvée
    (masquée) ; ni cachés, ni dépendances, ni secrets ; au plus `budget_s` secondes."""
    cible = texte.lower()
    base, _ = lister(dossier, racines, maximum=1)
    t0, trouves = time.time(), []
    for rep, sous, noms in os.walk(base):
        sous[:] = [x for x in sous if not _dossier_interdit(x) and x not in _IGNORES
                   and not (_interieur(Path(rep) / x) and not _mene_a_une_exception(Path(rep) / x))]
        if time.time() - t0 > budget_s or len(trouves) >= maximum:
            break
        for n in noms:
            f = Path(rep) / n
            if n.startswith(".") or f.suffix.lower() not in TEXTES_A_MASQUER or _SECRETS.search(_normaliser(n)) or _interieur(f):
                continue
            try:
                if f.stat().st_size > taille_max:
                    continue
                with open(f, encoding="utf-8", errors="ignore") as h:
                    for i, ligne in enumerate(h, 1):
                        if cible in ligne.lower():
                            trouves.append(f"{f}:{i}: {masquer(ligne.strip())[:200]}")
                            break
            except OSError:
                continue
            if len(trouves) >= maximum:
                break
    return trouves


_IGNORES = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".next", "dist", "build", ".cache", ".prepares"}


def chercher(nom, racines=None, maximum=40, profondeur=6, budget_s=15):
    """Les fichiers dont le nom contient `nom` (sans accents ni casse) sous les racines autorisées,
    les plus récents d'abord ; ni secrets, ni dossiers cachés, ni dépendances ; au plus `budget_s` s
    (tout le dossier d'Ahmed est parcouru, le plus récent d'abord)."""
    def plat(s):
        return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    cible, trouves, t0 = plat(nom), [], time.time()
    racines = [Path(r) for r in (racines or RACINES)]
    # une racine incluse dans une autre n'est pas parcourue deux fois (sauf sous un dossier fermé : iCloud)
    uniques = [r for r in racines if not any(o != r and o in r.parents and not
                                             any(x in _DOSSIERS_INTERDITS for x in r.relative_to(o).parts) for o in racines)]
    for racine in uniques:
        if not racine.is_dir():
            continue
        base = len(racine.parts)
        for dossier, sous, noms in os.walk(racine):
            if time.time() - t0 > budget_s:
                break
            d = Path(dossier)
            sous[:] = [s for s in sous if not _dossier_interdit(s) and s not in _IGNORES
                       and not (_interieur(d / s) and not _mene_a_une_exception(d / s)) and len(d.parts) - base < profondeur]
            for n in noms:
                if cible in plat(n) and not n.startswith(".") and not _SECRETS.search(n) and not _interieur(d / n):
                    f = d / n
                    try:
                        trouves.append((f.stat().st_mtime, str(f)))
                    except OSError:
                        pass
    return [f for _m, f in sorted(trouves, reverse=True)[:maximum]]


JOURNAL_BRUT = Path.home() / "AIOS" / "jarvis"


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def chercher_journal(texte, dossier=None, maximum=20):
    """Le journal brut des conversations (vivant + archives mensuelles), du plus récent au plus ancien :
    [{ts, qui, extrait}] autour de chaque occurrence de `texte` (sans accents ni casse)."""
    dossier = Path(dossier or JOURNAL_BRUT)
    cible = _sans_accents(texte).strip()
    if not cible:
        return []
    fichiers_ = sorted((dossier / "archives").glob("journal-*.jsonl")) + [dossier / "journal.jsonl"]
    trouves = []
    for f in reversed(fichiers_):
        try:
            lignes = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for ligne in reversed(lignes):
            try:
                o = json.loads(ligne)
            except ValueError:
                continue
            t = str(o.get("texte", ""))
            i = _sans_accents(t).find(cible)
            if i >= 0:
                trouves.append({"ts": o.get("ts"), "qui": o.get("qui"), "extrait": masquer(t[max(0, i - 250):i + 350])})
                if len(trouves) >= maximum:
                    return trouves
    return trouves


def resume(res):
    """Le texte que l'outil MCP rend à Jarvis."""
    lignes = [f"Fichier : {res['fichier']}"]
    if res.get("duree_s"):
        lignes.append(f"Durée : {res['duree_s']:.1f} s")
    if res.get("note"):
        lignes.append(f"Préparation : {res['note']}")
    if res["lire"]:
        lignes.append("À regarder avec l'outil Read (dans l'ordre) :\n" + "\n".join(f"- {p}" for p in res["lire"]))
    if res.get("texte"):
        import enveloppe
        lignes.append("Contenu texte :\n" + enveloppe.enveloppe(res["texte"], res["fichier"]))
    return "\n".join(lignes)
