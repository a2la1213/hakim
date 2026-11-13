"""L'EXTRACTION, en lecture seule, de ce qu'un fichier du PC dit (texte) et de ce qu'il sait de lui-même (métadonnées).

Rien n'est copié : on lit le début d'un fichier (borné), on le décode en mémoire, on rend un petit dictionnaire. Aucune
bibliothèque à installer : docx/pptx/xlsx/odt se lisent par leur zip (bornes anti « bombe zip »), les courriels par le
module email, les exports WhatsApp par leurs lignes, les photos par leur EXIF (JPEG, et HEIC quand l'EXIF est trouvable),
les vidéos et les morceaux par ffprobe s'il est là (sinon la date du fichier et le nom). Les PDF par pdftotext (paquet
poppler-utils sous WSL) s'il est là, sinon un repli approximatif sur les flux de texte.
Chaque fichier qui ne se lit pas rend un texte vide, jamais une exception.
"""
import email
import email.utils
import email.policy
import html
import json
import re
import shutil
import struct
import subprocess
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

TEXTES = {".txt", ".md", ".markdown", ".csv", ".tsv", ".html", ".htm", ".rtf", ".log"}
OFFICE = {".docx", ".pptx", ".xlsx", ".odt", ".ods", ".odp"}
DOCUMENTS = TEXTES | OFFICE | {".pdf"}
COURRIELS = {".eml"}
CONTACTS = {".vcf"}
PHOTOS = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tif", ".tiff", ".webp"}
VIDEOS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".webm", ".wmv"}
AUDIOS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma", ".opus"}
ARCHIVES_WHATSAPP = {".zip"}            # seulement un export WhatsApp (son nom le dit) ; jamais une archive quelconque

LECTURE_MAX = 400_000                   # octets lus d'un texte
TEXTE_MAX = 60_000                      # caractères gardés en mémoire d'un document (l'index n'en garde qu'un extrait)
OFFICE_MEMBRE_MAX = 30 * 1024 * 1024
OFFICE_TOTAL_MAX = 80 * 1024 * 1024
FFPROBE = shutil.which("ffprobe")
PDFTOTEXT = shutil.which("pdftotext")
PDFINFO = shutil.which("pdfinfo")


def type_de(p):
    """Le genre d'un fichier : document, discussion, courriel, contacts, photo, video, audio, ou None (ignoré)."""
    ext = Path(p).suffix.lower()
    nom = Path(p).name.lower()
    if ext in ARCHIVES_WHATSAPP:
        return "discussion" if "whatsapp" in nom else None
    if ext == ".txt" and _nom_whatsapp(nom):
        return "discussion"
    if ext in DOCUMENTS:
        return "document"
    if ext in COURRIELS:
        return "courriel"
    if ext in CONTACTS:
        return "contacts"
    if ext in PHOTOS:
        return "photo"
    if ext in VIDEOS:
        return "video"
    if ext in AUDIOS:
        return "audio"
    return None


def _nom_whatsapp(nom):
    return bool(re.search(r"whatsapp|^_chat\.txt$|discussion.?whatsapp", nom))


# ---------------------------------------------------------------- textes
def _decoder(b):
    if b.startswith((b"\xff\xfe", b"\xfe\xff")):
        return b.decode("utf-16", errors="replace")
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", errors="replace")
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace")      # le Bloc-notes de Windows d'avant 2019


def _lire_debut(p, n=LECTURE_MAX):
    with open(p, "rb") as f:
        return f.read(n)


def _sans_balises(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>", "\n", t)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


def _rtf(t):
    t = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), t)
    t = re.sub(r"\\par[d]?\b", "\n", t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?|[{}]", "", t)
    return t


def _propre(t):
    t = re.sub(r"[ \t\u00a0]+", " ", str(t or ""))
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()


# ---------------------------------------------------------------- office
class TropGros(Exception):
    pass


def _membre(z, nom, lu):
    taille = z.getinfo(nom).file_size
    if taille > OFFICE_MEMBRE_MAX or lu[0] + taille > OFFICE_TOTAL_MAX:
        raise TropGros(nom)
    with z.open(nom) as f:
        data = f.read(OFFICE_MEMBRE_MAX + 1)
    if len(data) > OFFICE_MEMBRE_MAX:
        raise TropGros(nom)
    lu[0] += len(data)
    return data.decode("utf-8", "replace")


def _num(nom):
    m = re.search(r"(\d+)\.xml$", nom)
    return int(m.group(1)) if m else 0


def _meta_core(xml):
    def un(balise):
        m = re.search(rf"<{balise}[^>]*>([^<]*)</{balise}>", xml)
        return html.unescape(m.group(1)).strip() if m else ""
    return {"auteur": un("dc:creator") or un("meta:initial-creator"), "modifie_par": un("cp:lastModifiedBy") or un("dc:creator"),
            "cree": un("dcterms:created") or un("meta:creation-date"), "modifie": un("dcterms:modified") or un("dc:date"),
            "titre": un("dc:title")}


def _office(p):
    lu = [0]
    ext = p.suffix.lower()
    meta = {}
    with zipfile.ZipFile(p) as z:
        noms = z.namelist()
        if "docProps/core.xml" in noms:
            meta = _meta_core(_membre(z, "docProps/core.xml", lu))
        elif "meta.xml" in noms:
            meta = _meta_core(_membre(z, "meta.xml", lu))
        if ext == ".docx":
            xml = _membre(z, "word/document.xml", lu) if "word/document.xml" in noms else ""
            texte = "\n".join("".join(html.unescape(t) for t in re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
                              for p in re.split(r"</w:p>", xml))
        elif ext == ".pptx":
            diapos = sorted((n for n in noms if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=_num)
            texte = "\n".join(f"[diapo {i}] " + " ".join(html.unescape(t) for t in re.findall(r"<a:t>([^<]*)</a:t>", _membre(z, d, lu)))
                              for i, d in enumerate(diapos, 1))
        elif ext == ".xlsx":
            chaines = []
            if "xl/sharedStrings.xml" in noms:
                chaines = [html.unescape(t) for t in re.findall(r"<t[^>]*>([^<]*)</t>", _membre(z, "xl/sharedStrings.xml", lu))]
            feuilles = sorted((n for n in noms if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=_num)
            valeurs = []
            for f in feuilles[:6]:
                valeurs += re.findall(r"<v>([^<]*)</v>", _membre(z, f, lu))[:400]
            texte = "Textes : " + " | ".join(chaines[:2000]) + ("\nValeurs : " + " ".join(valeurs[:800]) if valeurs else "")
        else:                                              # OpenDocument
            xml = _membre(z, "content.xml", lu) if "content.xml" in noms else ""
            texte = _sans_balises(re.sub(r"</text:p>|</text:h>", "\n", xml))
    return texte, meta


# ---------------------------------------------------------------- pdf
def _pdf(p):
    texte, meta = "", {}
    if PDFTOTEXT:
        try:
            r = subprocess.run([PDFTOTEXT, "-l", "30", "-enc", "UTF-8", str(p), "-"], capture_output=True, timeout=120)
            texte = r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            texte = ""
    else:
        texte = _pdf_approximatif(p)
    if PDFINFO:
        try:
            r = subprocess.run([PDFINFO, str(p)], capture_output=True, timeout=30)
            for l in r.stdout.decode("utf-8", "replace").splitlines():
                k, _, v = l.partition(":")
                k, v = k.strip().lower(), v.strip()
                if k == "author":
                    meta["auteur"] = v
                elif k == "title":
                    meta["titre"] = v
                elif k == "creationdate":
                    meta["cree"] = v
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        b = _lire_debut(p, 2_000_000)
        m = re.search(rb"/Author\s*\(([^)]{0,200})\)", b)
        if m:
            meta["auteur"] = _decoder(m.group(1))
        m = re.search(rb"/CreationDate\s*\(D:(\d{8})", b)
        if m:
            meta["cree"] = m.group(1).decode()
    return texte, meta


def _pdf_approximatif(p):
    """Sans pdftotext : les chaînes des opérateurs Tj/TJ des flux (décompressés si FlateDecode). Approximatif (polices
    à encodage propre illisibles), mais mieux que rien pour un PDF écrit par un traitement de texte."""
    b = _lire_debut(p, 20_000_000)
    morceaux = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", b, re.S):
        flux = m.group(1)
        try:
            flux = zlib.decompress(flux)
        except zlib.error:
            pass
        for s in re.findall(rb"\(((?:[^()\\]|\\.){1,400})\)\s*Tj|\[((?:[^\]]){1,2000})\]\s*TJ", flux):
            brut = s[0] or b"".join(re.findall(rb"\(((?:[^()\\]|\\.)*)\)", s[1]))
            morceaux.append(re.sub(rb"\\([()\\])", rb"\1", brut).decode("latin-1", "replace"))
        if sum(len(x) for x in morceaux) > TEXTE_MAX:
            break
    return " ".join(morceaux)


# ---------------------------------------------------------------- courriels, contacts, discussions
def _courriel(p):
    msg = email.message_from_bytes(_lire_debut(p, 2_000_000), policy=email.policy.default)
    corps = ""
    try:
        partie = msg.get_body(preferencelist=("plain", "html"))
        if partie is not None:
            corps = partie.get_content()
            if partie.get_content_type() == "text/html":
                corps = _sans_balises(corps)
    except Exception:
        corps = ""
    meta = {"de": str(msg.get("From") or ""), "a": str(msg.get("To") or ""), "cc": str(msg.get("Cc") or ""),
            "sujet": str(msg.get("Subject") or ""), "date": str(msg.get("Date") or "")}
    texte = f"Courriel — De : {meta['de']} — À : {meta['a']} — Sujet : {meta['sujet']} — Date : {meta['date']}\n\n{corps}"
    return texte, meta


def noms_du_courriel(meta):
    """Les noms affichés des personnes d'un courriel (« Sarah Benali <s@x.ch> » → « Sarah Benali »)."""
    out = []
    for champ in ("de", "a", "cc"):
        for nom, _adr in email.utils.getaddresses([meta.get(champ) or ""]):
            nom = nom.strip().strip('"')
            if nom and "@" not in nom and nom not in out:
                out.append(nom)
    return out


def _contacts(p):
    t = _decoder(_lire_debut(p, 2_000_000))
    noms = [l.split(":", 1)[1].strip() for l in t.splitlines() if l.upper().startswith("FN") and ":" in l]
    return "Carnet d'adresses : " + ", ".join(noms[:500]), {"noms": noms[:2000]}


_MSG = re.compile(r"^\u200e?\[?(\d{1,2}[./]\d{1,2}[./]\d{2,4}),?\s(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap]\.?[Mm]\.?)?)\]?"
                  r"\s(?:-\s)?([^:\n]{1,60}?):\s(.*)$")


def lire_whatsapp(texte):
    """[(date jj/mm/aaaa, auteur, message)] d'un export WhatsApp (Android ou iPhone, français ou anglais)."""
    messages = []
    for l in str(texte or "").splitlines():
        m = _MSG.match(l.strip("\ufeff"))
        if m:
            messages.append([m.group(1), m.group(3).strip("\u200e ").strip(), m.group(4)])
        elif messages and l.strip():
            messages[-1][2] += "\n" + l                       # un message sur plusieurs lignes
    return [tuple(x) for x in messages]


def _discussion(p):
    if p.suffix.lower() == ".zip":
        lu = [0]
        with zipfile.ZipFile(p) as z:
            txt = [n for n in z.namelist() if n.lower().endswith(".txt")]
            brut = _membre(z, txt[0], lu) if txt else ""
    else:
        brut = _decoder(_lire_debut(p, 4_000_000))
    messages = lire_whatsapp(brut)
    compte = {}
    for _d, a, _m in messages:
        compte[a] = compte.get(a, 0) + 1
    avec = re.sub(r"(?i)^(whatsapp chat (with|-) |discussion whatsapp avec |whatsapp )|\.(txt|zip)$", "", p.name).strip()
    meta = {"participants": compte, "avec": avec, "premier": messages[0][0] if messages else "",
            "dernier": messages[-1][0] if messages else "", "messages": len(messages)}
    texte = "\n".join(f"[{d}] {a} : {m}" for d, a, m in messages[-1500:])
    return texte, meta, messages


# ---------------------------------------------------------------- photos (EXIF sans bibliothèque)
_TAILLES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def _tiff(d):
    if len(d) < 8 or d[:2] not in (b"II", b"MM"):
        return {}
    o = "<" if d[:2] == b"II" else ">"

    def ifd(off):
        out = {}
        if off <= 0 or off + 2 > len(d):
            return out
        n = struct.unpack_from(o + "H", d, off)[0]
        for k in range(min(n, 400)):
            e = off + 2 + 12 * k
            if e + 12 > len(d):
                break
            tag, typ, cnt = struct.unpack_from(o + "HHI", d, e)
            taille = _TAILLES.get(typ, 1) * cnt
            vo = e + 8 if taille <= 4 else struct.unpack_from(o + "I", d, e + 8)[0]
            if vo + taille > len(d) or cnt > 10000:
                continue
            if typ == 2:
                out[tag] = d[vo:vo + cnt].split(b"\0")[0].decode("latin-1", "replace").strip()
            elif typ == 3:
                out[tag] = struct.unpack_from(o + "H", d, vo)[0]
            elif typ in (4, 9):
                out[tag] = struct.unpack_from(o + ("I" if typ == 4 else "i"), d, vo)[0]
            elif typ in (5, 10):
                f = "II" if typ == 5 else "ii"
                out[tag] = [(lambda a, b: a / b if b else 0.0)(*struct.unpack_from(o + f, d, vo + 8 * i)) for i in range(min(cnt, 3))]
            elif typ in (1, 7):
                out[tag] = d[vo:vo + min(cnt, 8)]
        return out

    racine = ifd(struct.unpack_from(o + "I", d, 4)[0])
    exif = ifd(racine.get(0x8769, 0)) if isinstance(racine.get(0x8769), int) else {}
    gps = ifd(racine.get(0x8825, 0)) if isinstance(racine.get(0x8825), int) else {}
    meta = {}
    date = exif.get(0x9003) or exif.get(0x9004) or racine.get(0x0132)
    if isinstance(date, str) and re.match(r"\d{4}:\d{2}:\d{2}", date):
        meta["date"] = date[:10].replace(":", "-")
    appareil = " ".join(x for x in (racine.get(0x010F), racine.get(0x0110)) if isinstance(x, str)).strip()
    if appareil:
        meta["appareil"] = appareil[:60]

    def deg(v, ref):
        if not isinstance(v, list) or len(v) < 3:
            return None
        x = v[0] + v[1] / 60 + v[2] / 3600
        r = ref.decode("latin-1", "replace") if isinstance(ref, bytes) else str(ref or "")
        return -x if r[:1] in ("S", "W") else x
    lat, lon = deg(gps.get(2), gps.get(1)), deg(gps.get(4), gps.get(3))
    if lat is not None and lon is not None and (lat or lon):
        meta["gps"] = [round(lat, 5), round(lon, 5)]
    return meta


def exif(p):
    """Date de prise de vue, appareil et coordonnées GPS d'une photo (JPEG, TIFF ; HEIC si l'EXIF est dans le premier Mo).
    On lit le moins possible (sous WSL, /mnt/c passe par un pont lent) : l'EXIF d'un JPEG tient dans ses 64 premiers Ko."""
    ext = p.suffix.lower()
    if ext not in (".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff"):
        return {}
    try:
        b = _lire_debut(p, 1_000_000 if ext in (".heic", ".heif") else 131_072)
    except OSError:
        return {}
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(b) and b[i] == 0xFF:
            marque = b[i + 1]
            if marque in (0xD8, 0x01) or 0xD0 <= marque <= 0xD7:
                i += 2
                continue
            longueur = int.from_bytes(b[i + 2:i + 4], "big")
            if marque == 0xE1 and b[i + 4:i + 10] == b"Exif\x00\x00":
                return _tiff(b[i + 10:i + 2 + longueur])
            if marque == 0xDA:
                break
            i += 2 + longueur
        return {}
    k = b.find(b"Exif\x00\x00")
    while k >= 0:
        meta = _tiff(b[k + 6:k + 6 + 200_000])
        if meta:
            return meta
        k = b.find(b"Exif\x00\x00", k + 1)
    return {}


# ---------------------------------------------------------------- vidéos et morceaux
def _ffprobe(p):
    if not FFPROBE:
        return {}
    try:
        r = subprocess.run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", str(p)], capture_output=True, timeout=30)
        return json.loads(r.stdout.decode("utf-8", "replace") or "{}").get("format", {})
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}


def _iso6709(s):
    m = re.match(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", str(s or ""))
    return [round(float(m.group(1)), 5), round(float(m.group(2)), 5)] if m else None


def _video(p):
    f = _ffprobe(p)
    tags = {k.lower(): v for k, v in (f.get("tags") or {}).items()}
    meta = {}
    if tags.get("creation_time"):
        meta["date"] = str(tags["creation_time"])[:10]
    if f.get("duration"):
        try:
            meta["duree_s"] = round(float(f["duration"]))
        except ValueError:
            pass
    loc = _iso6709(tags.get("com.apple.quicktime.location.iso6709") or tags.get("location") or tags.get("location-eng"))
    if loc:
        meta["gps"] = loc
    return meta


def _id3(p):
    """Titre, artiste, album, genre d'un MP3 (ID3v2.3/2.4) sans ffprobe."""
    b = _lire_debut(p, 131_072)
    if b[:3] != b"ID3":
        return {}
    v = b[3]
    taille = (b[6] << 21) | (b[7] << 14) | (b[8] << 7) | b[9]
    i, fin, out = 10, min(10 + taille, len(b)), {}
    noms = {b"TIT2": "titre", b"TPE1": "artiste", b"TALB": "album", b"TCON": "genre", b"TYER": "annee", b"TDRC": "annee"}
    while i + 10 <= fin:
        cadre, t = b[i:i + 4], b[i + 4:i + 8]
        if not cadre.strip(b"\0"):
            break
        n = ((t[0] << 21) | (t[1] << 14) | (t[2] << 7) | t[3]) if v == 4 else int.from_bytes(t, "big")
        corps = b[i + 10:i + 10 + n]
        if cadre in noms and corps:
            enc = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}.get(corps[0], "latin-1")
            out[noms[cadre]] = corps[1:].decode(enc, "replace").strip("\0 ")
        i += 10 + n
    return out


def _audio(p):
    # un MP3 se lit sans lancer de programme (des milliers de morceaux : ffprobe coûte ~50 ms chacun) ; ffprobe pour le reste
    meta = {k: v[:80] for k, v in _id3(p).items() if v} if p.suffix.lower() == ".mp3" else {}
    if not meta:
        f = _ffprobe(p)
        tags = {k.lower(): v for k, v in (f.get("tags") or {}).items()}
        meta = {k: str(tags[t])[:80] for k, t in (("titre", "title"), ("artiste", "artist"), ("album", "album"),
                                                  ("genre", "genre"), ("annee", "date")) if tags.get(t)}
    if not meta.get("artiste"):
        a, sep, t = p.stem.partition(" - ")
        if sep:
            meta.setdefault("artiste", a.strip()[:80])
            meta.setdefault("titre", t.strip()[:80])
    return meta


# ---------------------------------------------------------------- l'entrée
def _date_iso(s):
    s = str(s or "").strip()
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except Exception:
        pass
    m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s)
    if m:
        a = int(m.group(3))
        a = a + 2000 if a < 100 else a
        return f"{a:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def extraire(p, genre=None):
    """{genre, texte, meta, date, auteur, titre, messages?}. Lecture seule, bornée ; jamais d'exception."""
    p = Path(p)
    genre = genre or type_de(p)
    out = {"genre": genre, "texte": "", "meta": {}, "date": "", "auteur": "", "titre": p.stem}
    try:
        st = p.stat()
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).date().isoformat()
        ext = p.suffix.lower()
        if genre == "document":
            if ext in OFFICE:
                texte, meta = _office(p)
            elif ext == ".pdf":
                texte, meta = _pdf(p)
            else:
                texte, meta = _decoder(_lire_debut(p)), {}
                if ext in (".html", ".htm"):
                    texte = _sans_balises(texte)
                elif ext == ".rtf":
                    texte = _rtf(texte)
            out.update(texte=_propre(texte)[:TEXTE_MAX], meta=meta, auteur=meta.get("auteur", ""),
                       titre=meta.get("titre") or p.stem, date=_date_iso(meta.get("cree")) or mtime)
        elif genre == "courriel":
            texte, meta = _courriel(p)
            out.update(texte=_propre(texte)[:TEXTE_MAX], meta=meta, titre=meta.get("sujet") or p.stem,
                       date=_date_iso(meta.get("date")) or mtime)
        elif genre == "contacts":
            texte, meta = _contacts(p)
            out.update(texte=texte[:TEXTE_MAX], meta=meta, date=mtime)
        elif genre == "discussion":
            texte, meta, messages = _discussion(p)
            out.update(texte=texte[-TEXTE_MAX:], meta=meta, messages=messages, titre=f"WhatsApp avec {meta['avec']}",
                       date=_date_iso(meta.get("dernier")) or mtime)
        elif genre == "photo":
            meta = exif(p)
            out.update(meta=meta, date=meta.get("date") or mtime)
        elif genre == "video":
            meta = _video(p)
            out.update(meta=meta, date=meta.get("date") or mtime)
        elif genre == "audio":
            meta = _audio(p)
            out.update(meta=meta, date=mtime, titre=meta.get("titre") or p.stem)
        else:
            out["date"] = mtime
    except (OSError, zipfile.BadZipFile, TropGros, KeyError, ValueError, struct.error, RuntimeError, LookupError):
        pass
    return out
