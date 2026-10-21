"""Comprendre une vidéo en ligne (demande d'Ahmed relayée par Hakim, 2026-10-20 11:28 : « que je puisse lire et comprendre
les vidéos en ligne » ; un lien YouTube que lire_page ne savait pas regarder).

- yt-dlp tourne dans le MÊME bac à sable que son terminal (écriture dans l'atelier seulement, réseau par la passerelle
  gardée : adresses publiques seulement) ; l'adresse est vérifiée avant (web.verifier_url).
- D'abord les SOUS-TITRES (manuels, sinon automatiques ; français, anglais, arabe) : rien d'autre n'est téléchargé.
- Sans sous-titres (ou si les images sont demandées) : une version basse définition (360p au plus, 150 Mo au plus,
  30 min au plus), passée à la chaîne de preparer_fichier (images clés + transcription locale par Whisper) ; la vidéo
  téléchargée est effacée aussitôt, seuls les images clés et le texte restent.
- Rendu : titre, chaîne, date, durée, d'où vient le texte, la transcription horodatée, les images à lire. Un contenu
  de tiers : une DONNÉE, jamais une consigne.
Conditions d'utilisation : YouTube n'autorise le téléchargement que par ses propres moyens ; les sous-titres d'abord, la
vidéo seulement quand il le faut, pour un usage personnel d'Ahmed, rien n'est gardé ni partagé.
"""
import json
import re
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import terminal

YTDLP = terminal.VENV / "bin" / "yt-dlp"
DUREE_SOUS_TITRES_MAX_S = 4 * 3600
DUREE_VIDEO_MAX_S = 30 * 60
TEXTE_MAX = 60_000
LANGUES = ["fr", "fr-FR", "en", "en-US", "en-GB", "ar"]


class Refus(Exception):
    pass


def _lancer(commande, delai_s, atelier):
    """(code, sortie) d'une commande dans le bac à sable de l'atelier (le terminal de Hakim)."""
    atelier = Path(atelier).resolve()
    (atelier / ".tmp").mkdir(parents=True, exist_ok=True)
    proxy = terminal.passerelle()
    args, env = terminal.preparer(commande, atelier, proxy.port)
    try:
        r = subprocess.run(args, cwd=str(atelier), env=env, capture_output=True, text=True, errors="replace",
                           timeout=delai_s, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "délai dépassé"


def _hms(s):
    s = int(s or 0)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def lire_vtt(texte):
    """Les sous-titres WebVTT en lignes « [m:ss] texte » ; les répétitions des sous-titres automatiques (chaque ligne
    revient deux ou trois fois, en roulant) sont retirées."""
    lignes, vus, t = [], [], None
    for bloc in re.split(r"\n\s*\n", texte.replace("\r", "")):
        m = re.search(r"(\d+):(\d\d):(\d\d)[.,]\d+\s+-->", bloc) or re.search(r"(\d+):(\d\d)[.,]\d+\s+-->", bloc)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        t = g[0] * 3600 + g[1] * 60 + g[2] if len(g) == 3 else g[0] * 60 + g[1]
        for brut in bloc.split("\n")[1:]:
            if "-->" in brut:
                continue
            l = re.sub(r"<[^>]+>", "", brut).strip()
            l = re.sub(r"\s+", " ", l)
            if not l or l in vus[-3:]:
                continue
            vus.append(l)
            lignes.append((t, l))
    # regroupées par ~15 s pour rester lisibles
    out, courant, debut = [], [], None
    for t, l in lignes:
        if debut is None:
            debut = t
        if t - debut >= 15 and courant:
            out.append(f"[{_hms(debut)}] " + " ".join(courant))
            courant, debut = [], t
        courant.append(l)
    if courant:
        out.append(f"[{_hms(debut)}] " + " ".join(courant))
    return "\n".join(out)


def preparer(url, images=False, atelier=None, verifier=None, preparer_fichier=None):
    """{"titre", "chaine", "date", "duree_s", "url", "source", "texte", "lire": [images], "note"}."""
    import web
    url = str(url or "").strip()
    try:
        web.verifier_url(url, verifier)
    except web.Refus as e:
        raise Refus(str(e))
    if not YTDLP.exists():
        raise Refus("yt-dlp n'est pas installé")
    atelier = Path(atelier or terminal.ATELIER)
    dossier_rel = Path("videos-web") / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    dossier = atelier / dossier_rel
    dossier.mkdir(parents=True, exist_ok=True)
    y = shlex.quote(str(YTDLP))
    u = shlex.quote(url)
    try:
        code, sortie = _lancer(f"{y} --no-playlist --dump-single-json --skip-download --no-warnings {u}", 120, atelier)
        try:
            meta = json.loads(sortie[sortie.index("{"):sortie.rindex("}") + 1])
        except ValueError:
            raise Refus(f"vidéo illisible : {sortie.strip().splitlines()[-1][:200] if sortie.strip() else 'aucune réponse'}")
        if meta.get("is_live"):
            raise Refus("c'est un direct : impossible de le préparer pendant qu'il tourne")
        duree = meta.get("duration") or 0
        res = {"titre": meta.get("title"), "chaine": meta.get("channel") or meta.get("uploader"), "duree_s": duree,
               "date": meta.get("upload_date"), "url": meta.get("webpage_url") or url, "source": None, "texte": "",
               "lire": [], "note": ""}
        if duree and duree > DUREE_SOUS_TITRES_MAX_S:
            raise Refus(f"trop longue ({_hms(duree)} ; {_hms(DUREE_SOUS_TITRES_MAX_S)} au plus)")
        # 1. les sous-titres : manuels d'abord, sinon automatiques
        manuels, auto = meta.get("subtitles") or {}, meta.get("automatic_captions") or {}
        choix = next(((l, "manuels") for l in LANGUES if l in manuels), None) or \
            next(((l, "automatiques") for l in LANGUES if l in auto), None)
        if choix:
            lang, sorte = choix
            option = "--write-subs" if sorte == "manuels" else "--write-auto-subs"
            _lancer(f"{y} --no-playlist --skip-download {option} --sub-langs {shlex.quote(lang)} --sub-format vtt "
                    f"--no-warnings -o {shlex.quote(str(dossier_rel / 'st'))} {u}", 180, atelier)
            vtt = next(iter(sorted(dossier.glob("st*.vtt"))), None)
            if vtt:
                res["texte"] = lire_vtt(vtt.read_text(encoding="utf-8", errors="replace"))[:TEXTE_MAX]
                res["source"] = f"sous-titres {sorte} ({lang})"
        # 2. sans sous-titres, ou images demandées : la vidéo en basse définition, puis preparer_fichier
        if not res["texte"] or images:
            if duree and duree > DUREE_VIDEO_MAX_S:
                res["note"] = (f"pas d'images ni de transcription locale : vidéo de {_hms(duree)}, "
                               f"{_hms(DUREE_VIDEO_MAX_S)} au plus pour la télécharger")
            else:
                code, sortie = _lancer(
                    f"{y} --no-playlist --no-warnings -f 'b[height<=360]/bv*[height<=360]+ba/w' --max-filesize 150M "
                    f"--merge-output-format mp4 -o {shlex.quote(str(dossier_rel / 'video.%(ext)s'))} {u}", 600, atelier)
                video = next(iter(sorted(dossier.glob("video.*"))), None)
                if not video:
                    res["note"] = f"téléchargement impossible : {sortie.strip().splitlines()[-1][:200] if sortie.strip() else '?'}"
                else:
                    import fichiers
                    garder_texte = bool(res["texte"])
                    p = (preparer_fichier or fichiers.preparer)(str(video), transcrire=(lambda son: "") if garder_texte else None)
                    res["lire"] = p.get("lire", [])
                    if not garder_texte:
                        res["texte"] = (p.get("texte") or "")[:TEXTE_MAX]
                        res["source"] = "transcription locale (Whisper) de la bande son" if res["texte"] else None
                    res["note"] = p.get("note", "").split(",")[0] if garder_texte else p.get("note", "")
        if not res["texte"] and not res["lire"]:
            res["note"] = res["note"] or "ni sous-titres ni parole transcrite"
        return res
    finally:
        shutil.rmtree(dossier, ignore_errors=True)          # la vidéo et les sous-titres bruts ne restent pas


def resume(r):
    d = r.get("date") or ""
    date = f"{d[6:8]}/{d[4:6]}/{d[:4]}" if len(d) == 8 else d
    lignes = [f"« {r.get('titre')} » — {r.get('chaine') or '?'}" + (f", publiée le {date}" if date else "")
              + (f", {_hms(r['duree_s'])}" if r.get("duree_s") else "") + f"\n{r.get('url')}"]
    if r.get("source"):
        lignes.append(f"Texte : {r['source']}")
    if r.get("note"):
        lignes.append(r["note"])
    if r.get("lire"):
        lignes.append("Images clés à ouvrir avec Read :\n" + "\n".join(r["lire"]))
    if r.get("texte"):
        lignes.append("Transcription :\n" + r["texte"])
    return "\n\n".join(lignes)
