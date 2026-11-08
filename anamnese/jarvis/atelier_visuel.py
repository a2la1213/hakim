"""L'Atelier visuel de Hakim (06/11, Ahmed : « une zone visuelle dans le cockpit où Hakim pourrait créer des images et des
clips quand il veut, pour nos futurs albums et clips » ; accord pour le modèle d'images : « Ouiii, lance. »).

Tout se calcule SUR LE MAC, gratuit et hors ligne une fois les poids là :
- les IMAGES : Z-Image-Turbo (Tongyi-MAI, licence Apache 2.0, 6 milliards de paramètres) quantifié en 4 bits pour MLX
  (mflux-community/z-image-turbo-mflux-q4, Apache 2.0, 5,9 Go), par mflux, dans son venv à lui :
      uv venv --python python3.12 jarvis/.venv-image && uv pip install --python jarvis/.venv-image/bin/python \
          mflux arabic-reshaper python-bidi
  9 pas de diffusion ; carré 1024², 9:16 768×1344, 16:9 1344×768 ;
- les CLIPS « visualiseurs » : ffmpeg seul (pas de modèle vidéo : trop lent sur 16 Go). Une chanson de Hakim et une ou
  plusieurs images → un MP4 9:16 (1080×1920) et/ou 16:9 (1920×1080) : léger zoom et glissement (Ken Burns) avec fondu
  entre les images, le spectre ou les ondes qui suivent la musique, le titre, et les paroles une ligne à la fois (leurs
  temps s'ils sont dans la fiche de la chanson, sinon réparties sur la durée). Les textes sont dessinés par Pillow
  (le ffmpeg du Mac n'a pas drawtext), l'arabe mis en forme par arabic-reshaper et python-bidi.

Comme chant.py, chaque création est une TÂCHE DE FOND ordinaire (~/AIOS/jarvis/cwd/taches/T-*.json, lignes PROGRESSION
dans son journal) : le cockpit la suit (jauge), prévient Ahmed et réveille Hakim quand elle finit ; la fin du journal
donne le chemin pour fichier_joindre. Deux rôles :
- `lancer` (importé : mcp_server.py, le cockpit ; venv d'Anamnèse, sans MLX) : vérifie la demande, écrit la tâche,
  détache le calcul sous nice ;
- `generer` (lancé à part : `nice -n 10 .venv-image/bin/python atelier_visuel.py generer <tâche> <dossier>`) : attend
  son tour (UN gros calcul à la fois sur le Mac : une chanson d'ACE-Step, un travail du studio ou une autre création
  de l'atelier), calcule, puis dépose le fichier :
    ~/AIOS/jarvis/visuels/<nom>.png|.mp4|.jpg + <nom>.json   (la galerie, lue par la page Atelier)
    ~/AIOS/jarvis/cwd/atelier/visuels/…                       (pour fichier_joindre)
    …/telephone/Z Fold 7/Hakim/Atelier/…                      (le téléphone d'Ahmed)
"""
import fcntl
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
VISUELS = JARVIS / "visuels"
CHANSONS = JARVIS / "chansons"
TACHES = JARVIS / "cwd" / "taches"
ATELIER = JARVIS / "cwd" / "atelier" / "visuels"
TELEPHONE = Path(os.environ.get("JARVIS_TELEPHONE_ATELIER",
                                JARVIS / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim" / "Atelier"))
PYTHON_IMAGE = Path(os.environ.get("JARVIS_PYTHON_IMAGE", ICI / ".venv-image" / "bin" / "python"))
FFMPEG = os.environ.get("JARVIS_FFMPEG", "/usr/local/bin/ffmpeg")
FFPROBE = os.environ.get("JARVIS_FFPROBE", str(Path(FFMPEG).with_name("ffprobe")))
MODELE = os.environ.get("JARVIS_MODELE_IMAGE", "mflux-community/z-image-turbo-mflux-q4")
PAS_IMAGE = 9

FORMATS = {"carre": (1024, 1024), "9:16": (768, 1344), "16:9": (1344, 768)}
FORMATS_CLIP = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
ALIAS_FORMAT = {"carre": "carre", "carré": "carre", "1:1": "carre", "square": "carre", "pochette": "carre", "album": "carre",
                "9:16": "9:16", "vertical": "9:16", "portrait": "9:16", "story": "9:16", "reel": "9:16", "tiktok": "9:16",
                "16:9": "16:9", "horizontal": "16:9", "paysage": "16:9", "youtube": "16:9"}
STYLES_CLIP = ("spectre", "ondes", "cercle", "sobre")
ALIAS_STYLE = {"spectre": "spectre", "barres": "spectre", "spectrum": "spectre", "egaliseur": "spectre", "égaliseur": "spectre",
               "ondes": "ondes", "onde": "ondes", "waves": "ondes", "wave": "ondes", "cercle": "cercle", "vectorscope": "cercle",
               "lissajous": "cercle", "sobre": "sobre", "aucun": "sobre", "rien": "sobre", "simple": "sobre"}
DESCRIPTION_MAX = 1500
IMAGES_MAX = 12
CLIP_MIN_S, CLIP_MAX_S = 5, 600
MAX_EN_FILE = 4                          # créations de l'atelier en attente ou en calcul
MAX_TACHES = 5                           # toutes tâches de fond confondues (chant.py en permet 3 ; l'atelier attend son tour)
DELAI_S = 40 * 60
FPS = 30


class Refus(Exception):
    pass


# ------------------------------------------------------------------------------------------------ petits outils

def _ecrire(p, d):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _lire(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _vivant(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError, ValueError):
        return False


def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")


def nom_de(titre, quand=None):
    t = re.sub(r"[^a-z0-9]+", "-", _sans_accent(titre or "visuel")).strip("-")[:40].strip("-") or "visuel"
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(quand or time.time())) + "-" + t


def format_de(f, clip=False):
    """« carré », « 9:16 », « paysage »… → la clé du format ; pour un clip, « les deux » (ou vide) → les deux."""
    s = " ".join(_sans_accent(f).split())
    if clip and s in ("", "les deux", "deux", "tous", "both", "9:16+16:9", "9:16 et 16:9"):
        return ["9:16", "16:9"]
    if not s and not clip:
        return "carre"
    k = ALIAS_FORMAT.get(s) or ALIAS_FORMAT.get(str(f or "").strip().lower())
    if not k or (clip and k == "carre"):
        permis = "9:16, 16:9 ou « les deux »" if clip else "carré, 9:16 ou 16:9"
        raise Refus(f"format inconnu « {f} » : {permis}")
    return [k] if clip else k


def style_de(s):
    k = ALIAS_STYLE.get(" ".join(_sans_accent(s).split()) or "spectre")
    if not k:
        raise Refus(f"style inconnu « {s} » : " + ", ".join(STYLES_CLIP))
    return k


def duree(fichier):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(fichier)], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 2)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def copier(fichier, dossier):
    """Une copie (écrite à côté puis renommée) ; rend son chemin."""
    f, d = Path(fichier), Path(dossier)
    d.mkdir(parents=True, exist_ok=True)
    cible = d / f.name
    if cible.exists() and cible.stat().st_size == f.stat().st_size:
        return cible
    tmp = d / f".{f.name}.tmp"
    shutil.copyfile(f, tmp)
    tmp.replace(cible)
    return cible


# ------------------------------------------------------------------------------------------------ la galerie

def galerie(visuels=None):
    """Les créations finies (images et clips), de la plus récente à la plus ancienne."""
    v = Path(visuels or VISUELS)
    l = [x for x in (_lire(p) for p in v.glob("*.json")) if isinstance(x, dict) and x.get("nom") and x.get("etat") == "prête"]
    return sorted(l, key=lambda x: x.get("fin", 0), reverse=True)


def image_de(ref, visuels=None):
    """Une image de la galerie, par son nom (« 20261106-201500-pochette »), son fichier ou son titre."""
    v = Path(visuels or VISUELS)
    r = str(ref or "").strip()
    base = Path(r).name
    souche = re.sub(r"\.(png|jpe?g)$", "", base, flags=re.I)
    images = [x for x in galerie(v) if x.get("type") == "image"]
    for x in images:
        if souche == x["nom"] or base == Path(x.get("fichier", "")).name:
            return x
    cle = _sans_accent(r)
    for x in images:
        if cle and cle == _sans_accent(x.get("titre")):
            return x
    raise Refus(f"image inconnue : « {r} » (atelier_voir les liste)")


def chansons_pretes(chansons=None):
    c = Path(chansons or CHANSONS)
    l = [x for x in (_lire(p) for p in c.glob("*.json")) if isinstance(x, dict) and x.get("etat") == "prête"
         and x.get("mp3") and Path(x["mp3"]).is_file()]
    return sorted(l, key=lambda x: x.get("fin", 0), reverse=True)


def chanson_de(ref, chansons=None):
    """Une chanson de Hakim, par son nom de fichier, son nom ou son titre (la plus récente de ce titre)."""
    r = str(ref or "").strip()
    if not r:
        raise Refus("une chanson (son titre, par exemple « Lanterne »)")
    base = re.sub(r"\.mp3$", "", Path(r).name, flags=re.I)
    l = chansons_pretes(chansons)
    for x in l:
        if base == x.get("nom") or base == Path(x["mp3"]).stem:
            return x
    cle = _sans_accent(r)
    for x in l:
        if cle == _sans_accent(x.get("titre")):
            return x
    for x in l:
        if cle and cle in _sans_accent(x.get("titre")):
            return x
    raise Refus(f"chanson inconnue : « {r} »" + (" ; ses chansons : " + ", ".join(f"« {x.get('titre')} »" for x in l[:8]) if l else ""))


def lignes_paroles(paroles):
    """Les paroles chantées, une ligne par entrée : sans les sections ([verse]…) ni les lignes vides."""
    out = []
    for l in str(paroles or "").replace("\r\n", "\n").split("\n"):
        l = " ".join(l.split())
        if not l or re.fullmatch(r"\[[^\]]*\]", l):
            continue
        out.append(l[:90])
    return out


def caler_paroles(fiche, duree_chanson):
    """[(début, fin, ligne)] en secondes de la chanson : ses temps s'ils sont dans la fiche (« paroles_temps » :
    [[t, texte], …]), sinon chaque ligne à son tour, répartie selon sa longueur entre l'intro et la fin."""
    temps = fiche.get("paroles_temps")
    if isinstance(temps, list) and temps:
        l = [(float(t), str(x)[:90]) for t, x in temps if str(x).strip()]
        return [(t, (l[i + 1][0] if i + 1 < len(l) else min(duree_chanson, t + 6)), x) for i, (t, x) in enumerate(l)]
    if fiche.get("instrumental"):
        return []
    lignes = lignes_paroles(fiche.get("paroles"))
    if not lignes or not duree_chanson:
        return []
    intro = min(10.0, 0.08 * duree_chanson)
    fin = duree_chanson - min(8.0, 0.06 * duree_chanson)
    poids = [max(12, len(x)) for x in lignes]
    total, t, out = sum(poids), intro, []
    for x, p in zip(lignes, poids):
        d = (fin - intro) * p / total
        out.append((round(t, 2), round(t + d, 2), x))
        t += d
    return out


# ------------------------------------------------------------------------------------------------ les demandes

def preparer_image(description, format="carre", titre="", par="hakim"):
    d = " ".join(str(description or "").split())
    if len(d) < 3:
        raise Refus("une description de l'image (ce qu'on y voit, le style, la lumière)")
    if len(d) > DESCRIPTION_MAX:
        raise Refus(f"description trop longue ({len(d)} caractères ; {DESCRIPTION_MAX} au plus)")
    f = format_de(format)
    w, h = FORMATS[f]
    titre = " ".join(str(titre or "").split())[:80] or d[:60]
    return {"type": "image", "description": d, "format": f, "largeur": w, "hauteur": h, "titre": titre,
            "nom": nom_de(titre), "graine": random.randint(1, 2 ** 31 - 1), "par": par}


def preparer_clip(chanson, images, style="spectre", format="", titre="", duree_s=None, debut_s=0, par="hakim",
                  chansons=None, visuels=None):
    c = chanson_de(chanson, chansons)
    if isinstance(images, str):
        images = [x for x in re.split(r"[,;\n]+", images) if x.strip()]
    images = [x for x in (images or []) if str(x).strip()]
    if not images:
        raise Refus("au moins une image de l'atelier (image_creer d'abord, ou atelier_voir pour les noms)")
    if len(images) > IMAGES_MAX:
        raise Refus(f"{IMAGES_MAX} images au plus")
    imgs = [image_de(x, visuels) for x in images]
    total = float(c.get("duree_s") or 0) or duree(c["mp3"]) or 0
    try:
        debut = max(0.0, float(debut_s or 0))
        longueur = float(duree_s) if duree_s not in (None, "", 0) else max(0.0, total - debut)
    except (TypeError, ValueError):
        raise Refus("une durée en secondes")
    if total and debut >= total:
        raise Refus(f"le début ({debut:.0f} s) dépasse la chanson ({total:.0f} s)")
    if total:
        longueur = min(longueur, total - debut)
    if not CLIP_MIN_S <= longueur <= CLIP_MAX_S:
        raise Refus(f"un clip de {CLIP_MIN_S} à {CLIP_MAX_S} secondes (ici {longueur:.0f})")
    titre = " ".join(str(titre or "").split())[:80] or c.get("titre") or "Clip"
    return {"type": "clip", "chanson": {"nom": c.get("nom"), "titre": c.get("titre"), "mp3": c["mp3"]},
            "images": [{"nom": x["nom"], "fichier": x["fichier"]} for x in imgs], "style": style_de(style),
            "formats": format_de(format, clip=True), "titre": titre, "debut_s": round(debut, 2),
            "duree_s": round(longueur, 2), "nom": nom_de(titre + "-clip"), "par": par}


def _en_cours(dossier):
    vus = []
    for p in sorted(Path(dossier).glob("T-*.json")):
        d = _lire(p, {}) or {}
        if d.get("etat") == "en cours" and (not d.get("superviseur") or _vivant(d["superviseur"])):
            vus.append(d)
    return vus


def _demarrer(args, log):
    """Détache le calcul (son propre groupe : un Stop du cerveau ne le tue pas). Rend son pid."""
    with open(log, "ab") as sortie:
        p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=sortie, stderr=subprocess.STDOUT,
                             start_new_session=True, close_fds=True,
                             env={**os.environ, "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
                                  "PYTHONUNBUFFERED": "1"})
    return p.pid


def lancer(demande, dossier=None, visuels=None, demarrer=None):
    """Une demande préparée → une tâche de fond ; rend {tache, …} tout de suite."""
    dossier, visuels = Path(dossier or TACHES), Path(visuels or VISUELS)
    if demarrer is None and not PYTHON_IMAGE.exists():
        raise Refus("l'atelier n'est pas installé sur le Mac (demande à Ahmed ou à Nour)")
    dossier.mkdir(parents=True, exist_ok=True)
    visuels.mkdir(parents=True, exist_ok=True)
    verrou = open(dossier / ".verrou", "w")                   # le même verrou que jarvis/taches.py et chant.py
    fcntl.flock(verrou, fcntl.LOCK_EX)
    try:
        en_cours = _en_cours(dossier)
        if len([e for e in en_cours if e.get("visuel")]) >= MAX_EN_FILE:
            raise Refus(f"déjà {MAX_EN_FILE} créations en file dans l'atelier : attends qu'une finisse")
        if len(en_cours) >= MAX_TACHES:
            raise Refus(f"déjà {len(en_cours)} tâches de fond en cours : attends qu'une finisse")
        tid = f"T-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        if demande["type"] == "image":
            quoi = f"image « {demande['titre'][:60]} » ({demande['format']})"
        else:
            quoi = (f"clip « {demande['titre'][:60]} » ({demande['style']}, {' et '.join(demande['formats'])}, "
                    f"{demande['duree_s']:.0f} s)")
        d = {"id": tid, "commande": f"atelier : {quoi}", "debut": time.time(), "etat": "en cours", "delai_s": DELAI_S,
             "atelier": str(ATELIER), "visuel": demande}
        _ecrire(dossier / f"{tid}.json", d)
        _ecrire(visuels / f"{demande['nom']}.json", {**demande, "etat": "en cours", "tache": tid, "debut": d["debut"]})
        args = ["/usr/bin/nice", "-n", "10", str(PYTHON_IMAGE), "-B", str(Path(__file__).resolve()), "generer", tid, str(dossier)]
        pid = (demarrer or _demarrer)(args, dossier / f"{tid}.log")
        d.update(pid=pid, superviseur=pid)
        _ecrire(dossier / f"{tid}.json", d)
        return {"tache": tid, **demande}
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def finir(tid, dossier=None, visuels=None, atelier=None, telephone=None, fichiers=None, erreur=None, raison=None,
          calcul_s=None, extra=None):
    """L'état final de la tâche et de la fiche ; les copies (atelier, téléphone). Rend la ligne de fin du journal."""
    dossier, visuels = Path(dossier or TACHES), Path(visuels or VISUELS)
    atelier, telephone = Path(atelier or ATELIER), Path(telephone or TELEPHONE)
    d = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))
    v = d["visuel"]
    fiche_p = visuels / f"{v['nom']}.json"
    fiche = _lire(fiche_p) or dict(v)
    fin = time.time()
    fichiers = [Path(f) for f in (fichiers or []) if f and Path(f).is_file()]
    genre = "IMAGE" if v["type"] == "image" else "CLIP"
    if erreur or raison or not fichiers:
        ligne = f"{genre} RATÉ{'E' if genre == 'IMAGE' else ''} : {raison or erreur or 'aucun fichier produit'}"
        d.update(etat="arrêtée" if raison else "finie", raison=raison, code=0 if raison else 1)
        fiche.update(etat="ratée", erreur=str(raison or erreur)[:500])
    else:
        rels, tel = [], []
        for f in fichiers:
            c = copier(f, atelier)
            rels.append(f"atelier/visuels/{c.name}")
            try:
                tel.append(str(copier(f, telephone)))
            except OSError as e:
                fiche["telephone_erreur"] = str(e)[:200]
        principal = fichiers[0]
        fiche.update(etat="prête", fichier=str(principal), fichiers=[str(f) for f in fichiers], atelier=rels,
                     telephone=tel, calcul_s=round(calcul_s or 0, 1), taille=sum(f.stat().st_size for f in fichiers),
                     **(extra or {}))
        lourds = [r for f, r in zip(fichiers, rels) if f.stat().st_size > 25 * 1024 * 1024]
        joindre = " ; ".join(f'fichier_joindre("{r}", "{v["titre"]}")' for r in rels if r not in lourds)
        if genre == "IMAGE":
            ligne = f"IMAGE PRÊTE : « {v['titre']} » ({v['format']}, calculée en {round(calcul_s or 0)} s), nom {v['nom']}. "
        else:
            ligne = (f"CLIP PRÊT : « {v['titre']} » ({' et '.join(v['formats'])}, {v['duree_s']:.0f} s, calculé en "
                     f"{round(calcul_s or 0)} s). ")
        if v.get("par") == "papa":
            ligne += "Papa l'a demandé depuis la page Atelier : il l'y trouve, et sur son téléphone (Hakim › Atelier)."
        else:
            ligne += f"Envoie-{'la' if genre == 'IMAGE' else 'le'} à papa : {joindre}" if joindre else ""
            if lourds:
                ligne += (" ; " if joindre else "") + ", ".join(lourds) + (" : trop lourd pour une pièce jointe (25 Mo), "
                                                                         "papa le trouve sur son téléphone (Hakim › Atelier)")
        d.update(etat="finie", raison=None, code=0, fichier=rels[0])
    d.update(fin=fin, duree_s=round(fin - d["debut"], 1))
    fiche["fin"] = fin
    _ecrire(fiche_p, fiche)
    _ecrire(dossier / f"{tid}.json", d)
    return ligne


# ------------------------------------------------------------------------------------------------ son tour

def gros_calcul_ailleurs(tid, dossier):
    """Un autre gros calcul tourne-t-il ? Une chanson d'ACE-Step, un travail du studio, ou une création de l'atelier
    lancée avant celle-ci et pas finie. Rend une phrase courte, ou None. (essai du 06/11 : une création lancée sur un
    autre dossier n'a pas vu la chanson de Hakim de la vraie file, et les deux ont calculé ensemble, le Mac en swap) : la
    vraie file (TACHES) est toujours regardée aussi."""
    vus = {}
    for dos in dict.fromkeys([Path(dossier), Path(TACHES)]):
        for d in _en_cours(dos):
            vus.setdefault(d.get("id"), d)
    for d in vus.values():
        if d.get("id") == tid:
            continue
        if d.get("chanson"):
            return f"attend la fin de la chanson « {d['chanson'].get('titre', '?')} »"
        if d.get("visuel") and d.get("id", "") < tid:
            return "attend la création d'avant"
    try:
        sys.path.insert(0, str(ICI))
        import studio
        if studio.occupe():
            return "attend la fin du calcul du studio"
    except Exception:                                        # noqa: BLE001 — sans studio lisible, on ne bloque pas
        pass
    return None


def attendre_son_tour(tid, dossier, pause_s=4, verrou_dir=None):
    """Bloque jusqu'à son tour ; rend le verrou de l'atelier (fermé à la fin). Une seule création calcule à la fois."""
    d = Path(verrou_dir or VISUELS)
    d.mkdir(parents=True, exist_ok=True)
    v = open(d / ".calcul", "w")
    dit = None
    while True:
        raison = gros_calcul_ailleurs(tid, dossier)
        if not raison:
            try:
                fcntl.flock(v, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return v
            except BlockingIOError:
                raison = "attend la création en cours"
        if raison != dit:
            print(f"PROGRESSION 0% {raison} (un gros calcul à la fois)", flush=True)
            dit = raison
        time.sleep(pause_s)


def _veiller(tid, dossier, debut):
    """Arrêt demandé (arreter_tache, la page) ou délai dépassé : l'état est écrit, puis le processus s'arrête net."""
    while True:
        time.sleep(1)
        raison = ("arrêtée à la demande (Ahmed ou Hakim)" if (dossier / f"{tid}.stop").exists()
                  else f"trop longue (plus de {DELAI_S // 60} min)" if time.time() - debut > DELAI_S else None)
        if raison:
            print(finir(tid, dossier, raison=raison), flush=True)
            try:
                (dossier / f"{tid}.stop").unlink()
            except OSError:
                pass
            os._exit(3)


# ------------------------------------------------------------------------------------------------ l'image

def faire_image(v, sortie):
    """(.venv-image) Z-Image-Turbo par mflux : la description → un PNG. Rend des mesures."""
    import mlx.core as mx
    from mflux.models.common.config import ModelConfig
    from mflux.models.z_image import ZImage

    class Jauge:
        def call_in_loop(self, t, seed, prompt, latents, config, time_steps):
            n = config.num_inference_steps
            print(f"PROGRESSION {10 + round(85 * (t + 1) / n)}% pas {t + 1}/{n}", flush=True)

    print("PROGRESSION 2% chargement du modèle", flush=True)
    t0 = time.time()
    m = ZImage(model_config=ModelConfig.z_image_turbo(), model_path=MODELE)
    m.callbacks.register(Jauge())
    charge_s = time.time() - t0
    print(f"PROGRESSION 10% modèle chargé en {charge_s:.0f} s", flush=True)
    t1 = time.time()
    img = m.generate_image(seed=int(v["graine"]), prompt=v["description"], num_inference_steps=PAS_IMAGE,
                           width=int(v["largeur"]), height=int(v["hauteur"]))
    pil = getattr(img, "image", None)
    if pil is not None:
        pil.save(sortie)
    else:
        img.save(path=sortie, overwrite=True)
    pic = None
    try:
        pic = round(mx.get_peak_memory() / 2 ** 30, 1)
    except AttributeError:
        pass
    print(f"Mémoire MLX crête : {pic} Go ; chargement {charge_s:.0f} s, diffusion {time.time() - t1:.0f} s", flush=True)
    print("PROGRESSION 100% enregistrée", flush=True)
    return {"modele": MODELE, "pas": PAS_IMAGE, "memoire_go": pic, "chargement_s": round(charge_s, 1),
            "diffusion_s": round(time.time() - t1, 1)}


# ------------------------------------------------------------------------------------------------ le clip

POLICES = {"latin": ["/System/Library/Fonts/Avenir Next.ttc", "/System/Library/Fonts/HelveticaNeue.ttc",
                     "/System/Library/Fonts/Helvetica.ttc"],
           "arabe": ["/System/Library/Fonts/GeezaPro.ttc", "/System/Library/Fonts/Supplemental/Baghdad.ttc"]}


def _police(genre, taille, gras=True):
    from PIL import ImageFont
    for f in POLICES[genre]:
        if Path(f).exists():
            try:
                return ImageFont.truetype(f, taille, index=(2 if gras and "Avenir" in f else 0))
            except OSError:
                try:
                    return ImageFont.truetype(f, taille)
                except OSError:
                    continue
    return ImageFont.load_default()


def _arabe(c):
    return "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" or "ﭐ" <= c <= "﷿" or "ﹰ" <= c <= "﻿"


def _morceaux(texte):
    """Le texte dans l'ordre visuel (l'arabe mis en forme et retourné), coupé en morceaux d'une même écriture."""
    t = str(texte)
    if any(_arabe(c) for c in t):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            t = get_display(arabic_reshaper.reshape(t))
        except ImportError:
            pass
    out = []
    for c in t:
        g = "arabe" if _arabe(c) else "latin"
        if c == " " and out:
            g = out[-1][0]
        if out and out[-1][0] == g:
            out[-1][1] += c
        else:
            out.append([g, c])
    return out


def dessiner_texte(texte, largeur, hauteur, taille, ombre=True):
    """Une ligne de texte centrée, blanche à ombre douce, sur fond transparent (PIL RGBA)."""
    from PIL import Image, ImageDraw, ImageFilter
    while True:
        polices = {g: _police(g, taille) for g in ("latin", "arabe")}
        morceaux = _morceaux(texte)
        larg = sum(polices[g].getlength(s) for g, s in morceaux)
        if larg <= largeur * 0.9 or taille <= 18:
            break
        taille = int(taille * 0.9)
    img = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    calque = Image.new("RGBA", (largeur, hauteur), (0, 0, 0, 0))
    x = (largeur - larg) / 2
    y = hauteur / 2
    dc, di = ImageDraw.Draw(calque), ImageDraw.Draw(img)
    for g, s in morceaux:
        dc.text((x + 2, y + 3), s, font=polices[g], fill=(0, 0, 0, 200), anchor="lm")
        di.text((x, y), s, font=polices[g], fill=(255, 255, 255, 255), anchor="lm")
        x += polices[g].getlength(s)
    if ombre:
        calque = calque.filter(ImageFilter.GaussianBlur(max(2, taille // 12)))
        return Image.alpha_composite(calque, img)
    return img


def habillage(w, h, titre, artiste, sortie):
    """Le calque fixe : un dégradé sombre en bas (lisibilité des paroles et du spectre), le titre et « Hakim »."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bas = int(h * 0.45)
    for i in range(bas):
        a = int(170 * (i / bas) ** 1.6)
        d.line([(0, h - bas + i), (w, h - bas + i)], fill=(0, 0, 0, a))
    haut = int(h * 0.16)
    for i in range(haut):
        a = int(110 * (1 - i / haut) ** 1.6)
        d.line([(0, i), (w, i)], fill=(0, 0, 0, a))
    u = min(w, h)
    t = dessiner_texte(titre, w, int(u * 0.11), int(u * 0.058))
    img.alpha_composite(t, (0, int(h * 0.035)))
    a = dessiner_texte(artiste.upper(), w, int(u * 0.06), int(u * 0.03))
    img.alpha_composite(a, (0, int(h * 0.035 + u * 0.085)))
    img.save(sortie)
    return sortie


def plan_paroles(fiche, debut, longueur, w, h, dossier):
    """Les paroles de la fenêtre [debut, debut+longueur] → des PNG transparents et une liste ffconcat (une ligne à la
    fois, du vide entre). Rend le chemin de la liste, ou None (pas de paroles)."""
    from PIL import Image
    total = float(fiche.get("duree_s") or 0) or (duree(fiche["mp3"]) or 0)
    lignes = [(max(a, debut) - debut, min(b, debut + longueur) - debut, x) for a, b, x in caler_paroles(fiche, total)
              if b > debut and a < debut + longueur]
    lignes = [(a, b, x) for a, b, x in lignes if b - a >= 0.4]
    if not lignes:
        return None
    u = min(w, h)
    hh = int(u * 0.16)
    vide = Path(dossier) / "p-vide.png"
    Image.new("RGBA", (w, hh), (0, 0, 0, 0)).save(vide)
    entrees, t = [], 0.0
    for i, (a, b, x) in enumerate(lignes):
        if a > t + 0.02:
            entrees.append((vide, a - t))
        f = Path(dossier) / f"p-{i:03d}.png"
        dessiner_texte(x, w, hh, int(u * 0.052)).save(f)
        entrees.append((f, b - a))
        t = b
    if t < longueur:
        entrees.append((vide, longueur - t))
    liste = Path(dossier) / "paroles.ffconcat"
    corps = ["ffconcat version 1.0"]
    for f, dur in entrees:
        corps += [f"file '{f}'", f"duration {dur:.3f}"]
    corps.append(f"file '{entrees[-1][0]}'")                 # la dernière image, répétée (règle du concat)
    liste.write_text("\n".join(corps) + "\n", encoding="utf-8")
    return liste


def filtre_clip(n_images, w, h, longueur, style, avec_paroles, fondu=1.0):
    """Le graphe ffmpeg : entrées 0..n-1 = images (bouclées), n = la chanson, n+1 = l'habillage, n+2 = la chanson
    encore (pour le visualiseur : un asplit dans le graphe bloquait le rendu à mi-chemin), n+3 = les paroles.
    Chaque image couvre l'écran, zoome doucement (avant ou arrière) en glissant ; un fondu de 1 s les relie."""
    n = n_images
    fondu = min(fondu, longueur / max(1, n) / 3) if n > 1 else 0
    seg = (longueur + (n - 1) * fondu) / n
    parts = []
    for i in range(n):
        zin = i % 2 == 0
        z = f"(1+0.12*t/{seg:.3f})" if zin else f"(1.12-0.12*t/{seg:.3f})"
        dx = ("-1", "1", "0")[i % 3]
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={FPS},"
            f"scale=w='trunc({w}*{z}/2)*2':h=-2:eval=frame,"
            f"crop={w}:{h}:x='(iw-{w})/2+({dx})*(iw-{w})/2*(t/{seg:.3f}-0.5)':y='(ih-{h})/2',"
            f"trim=duration={seg:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    der = "v0"
    for i in range(1, n):
        off = i * (seg - fondu)
        parts.append(f"[{der}][v{i}]xfade=transition=fade:duration={fondu:.3f}:offset={off:.3f}[x{i}]")
        der = f"x{i}"
    # (essai du 06/11) le fondu arrondit : le fond finissait 4 images avant la fin et le rendu attendait sans fin
    parts.append(f"[{der}]tpad=stop_mode=clone:stop_duration=2,trim=duration={longueur:.3f},setpts=PTS-STARTPTS[fond]")
    parts.append(f"[{n + 1}:v]format=rgba[hab]")
    parts.append(f"[fond][hab]overlay=0:0:format=auto[b0]")
    parts.append(f"[{n}:a]anull[aout]")
    # (essai du 06/11) showfreqs ne signale pas la fin du son : le rendu attendait sans fin quand la chanson finissait
    # avec le clip. Du silence derrière lui donne toujours une image d'avance.
    parts.append(f"[{n + 2}:a]apad=pad_dur=3[aviz]")
    u = min(w, h)
    vh = int(h * (0.16 if h > w else 0.20))
    vy = int(h - vh - h * 0.05)
    if style == "spectre":
        parts.append(f"[aviz]showfreqs=s={w}x{vh}:mode=bar:ascale=cbrt:fscale=log:win_size=2048:averaging=3:"
                     f"colors=white,fps={FPS},format=rgba,colorkey=0x000000:0.08:0.05,colorchannelmixer=aa=0.75[viz]")
    elif style == "ondes":
        parts.append(f"[aviz]showwaves=s={w}x{vh}:mode=cline:rate={FPS}:scale=sqrt:colors=white,"
                     f"format=rgba,colorkey=0x000000:0.08:0.05,colorchannelmixer=aa=0.8[viz]")
    elif style == "cercle":
        c = int(u * 0.42)
        vh, vy = c, int(h / 2 - c / 2)
        parts.append(f"[aviz]avectorscope=s={c}x{c}:mode=lissajous_xy:draw=line:scale=sqrt:zoom=2:rc=255:gc=255:bc=255:"
                     f"af=10,fps={FPS},format=rgba,colorkey=0x000000:0.08:0.05,colorchannelmixer=aa=0.7[viz]")
    else:
        parts.append("[aviz]anullsink")
    base = "b0"
    if style in ("spectre", "ondes"):
        parts.append(f"[{base}][viz]overlay=0:{vy}:shortest=0:eof_action=pass[b1]")
        base = "b1"
    elif style == "cercle":
        parts.append(f"[{base}][viz]overlay=(W-w)/2:{vy}:eof_action=pass[b1]")
        base = "b1"
    if avec_paroles:
        py = int(h * (0.66 if h > w else 0.60))
        parts.append(f"[{n + 3}:v]fps={FPS},format=rgba[par]")
        parts.append(f"[{base}][par]overlay=0:{py}:eof_action=pass[b2]")
        base = "b2"
    fin = max(0.0, longueur - 1.5)
    parts.append(f"[{base}]fade=t=in:st=0:d=0.6,fade=t=out:st={fin:.3f}:d=1.5,format=yuv420p[vout]")
    parts.append(f"[aout]afade=t=in:st=0:d=0.5,afade=t=out:st={fin:.3f}:d=1.5[afin]")
    return ";".join(parts)


def _ff_avec_jauge(args, longueur, debut_pc, fin_pc, texte, timeout=3600, fige_s=120):
    """ffmpeg avec -progress : la jauge du journal suit le temps rendu."""
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", *map(str, args)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dernier, vu, avance = -1, -1.0, time.time()
    debut = time.time()
    for l in p.stdout:
        if l.startswith("out_time_us=") or l.startswith("out_time_ms="):
            try:
                s = int(l.split("=")[1]) / 1e6
            except ValueError:
                continue
            if s > vu:
                vu, avance = s, time.time()
            pc = debut_pc + (fin_pc - debut_pc) * min(1.0, s / max(0.1, longueur))
            if int(pc) != dernier:
                dernier = int(pc)
                print(f"PROGRESSION {dernier}% {texte}", flush=True)
        # un rendu figé (le temps rendu n'avance plus depuis 2 min) ou trop long : ce ffmpeg-là s'arrête, la tâche est ratée
        if time.time() - avance > fige_s or time.time() - debut > timeout:
            p.kill()
            p.wait()
            raise RuntimeError("ffmpeg : rendu figé" if time.time() - debut <= timeout else "ffmpeg : trop long")
    err = p.stderr.read()
    if p.wait():
        raise RuntimeError(f"ffmpeg : {err.strip()[-500:]}")


def cadrer(image, w, h, sortie, ecart=0.15):
    """(essai du 06/11 : la pochette carrée, rognée en 16:9, perdait le garçon du bas) une image d'une autre forme que
    le clip y entre ENTIÈRE, sur un fond d'elle-même agrandi, flouté et assombri ; de la même forme, elle reste telle
    quelle. Fait une fois par Pillow (un flou à chaque image du clip coûterait trop). Rend le chemin à donner à ffmpeg."""
    from PIL import Image, ImageEnhance, ImageFilter
    im = Image.open(image).convert("RGB")
    if abs((im.width / im.height) / (w / h) - 1) <= ecart:
        return image
    k = max(w / im.width, h / im.height)
    fond = im.resize((max(w, round(im.width * k)), max(h, round(im.height * k))), Image.LANCZOS)
    fond = fond.crop(((fond.width - w) // 2, (fond.height - h) // 2, (fond.width - w) // 2 + w, (fond.height - h) // 2 + h))
    fond = ImageEnhance.Brightness(fond.filter(ImageFilter.GaussianBlur(max(w, h) // 40))).enhance(0.55)
    k = min(w / im.width, h / im.height)
    devant = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    fond.paste(devant, ((w - devant.width) // 2, (h - devant.height) // 2))
    fond.save(sortie)
    return sortie


def rendre_clip(v, w, h, sortie, travail, debut_pc=0, fin_pc=100, encodeur=None):
    """Un format du clip → un MP4 H.264 + AAC. Rend le chemin."""
    travail = Path(travail)
    travail.mkdir(parents=True, exist_ok=True)
    fiche = _lire(Path(v["chanson"]["mp3"]).with_suffix(".json")) or {"mp3": v["chanson"]["mp3"]}
    fiche.setdefault("mp3", v["chanson"]["mp3"])
    hab = habillage(w, h, v["titre"], "Hakim", travail / f"habillage-{w}x{h}.png")
    dp = travail / f"paroles-{w}x{h}"
    dp.mkdir(parents=True, exist_ok=True)
    liste = plan_paroles(fiche, float(v["debut_s"]), float(v["duree_s"]), w, h, dp)
    n = len(v["images"])
    seg = float(v["duree_s"]) / n + 2
    args = []
    for i, im in enumerate(v["images"]):
        f = cadrer(im["fichier"], w, h, travail / f"cadre-{w}x{h}-{i}.png")
        args += ["-loop", "1", "-framerate", FPS, "-t", f"{seg:.3f}", "-i", f]
    args += ["-ss", f"{float(v['debut_s']):.3f}", "-t", f"{float(v['duree_s']):.3f}", "-i", v["chanson"]["mp3"]]
    args += ["-loop", "1", "-framerate", FPS, "-t", f"{float(v['duree_s']) + 1:.3f}", "-i", hab]
    # la chanson encore, un peu plus longue : le visualiseur a toujours une image au-delà de la fin
    args += ["-ss", f"{float(v['debut_s']):.3f}", "-t", f"{float(v['duree_s']) + 2:.3f}", "-i", v["chanson"]["mp3"]]
    if liste:
        args += ["-f", "concat", "-safe", "0", "-i", liste]
    args += ["-filter_complex", filtre_clip(n, w, h, float(v["duree_s"]), v["style"], bool(liste)),
             "-map", "[vout]", "-map", "[afin]", "-t", f"{float(v['duree_s']):.3f}", "-r", FPS]
    enc = encodeur or ("libx264", ["-preset", "veryfast", "-crf", "20", "-profile:v", "high"])
    args += ["-c:v", enc[0], *enc[1], "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", sortie]
    _ff_avec_jauge(args, float(v["duree_s"]), debut_pc, fin_pc, f"rendu {w}x{h}")
    return sortie


def vignette(video, sortie, a_s=1.5):
    subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", str(a_s), "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(sortie)], check=True, timeout=120)
    return sortie


def faire_clip(v, visuels, travail):
    """Les formats demandés → les MP4 (et une vignette par format). Rend (fichiers, mesures)."""
    fichiers, n = [], len(v["formats"])
    for i, f in enumerate(v["formats"]):
        w, h = FORMATS_CLIP[f]
        sortie = Path(visuels) / f"{v['nom']}-{f.replace(':', 'x')}.mp4"
        rendre_clip(v, w, h, sortie, travail, debut_pc=100 * i / n, fin_pc=100 * (i + 1) / n)
        vignette(sortie, sortie.with_suffix(".jpg"), min(1.5, float(v["duree_s"]) / 2))
        fichiers.append(sortie)
    return fichiers, {"vignettes": [str(Path(f).with_suffix(".jpg")) for f in fichiers]}


# ------------------------------------------------------------------------------------------------ le calcul

def generer(tid, dossier=None, visuels=None):
    dossier, visuels = Path(dossier or TACHES), Path(visuels or VISUELS)
    debut = time.time()
    threading.Thread(target=_veiller, args=(tid, dossier, debut), daemon=True).start()
    v = json.loads((dossier / f"{tid}.json").read_text(encoding="utf-8"))["visuel"]
    print(f"Atelier : {v['type']} « {v['titre']} »", flush=True)
    verrou = attendre_son_tour(tid, dossier, verrou_dir=visuels)
    travail = visuels / f".{v['nom']}"
    try:
        t0 = time.time()
        if v["type"] == "image":
            sortie = visuels / f"{v['nom']}.png"
            mesures = faire_image(v, sortie)
            fichiers = [sortie]
        else:
            fichiers, mesures = faire_clip(v, visuels, travail)
        print(finir(tid, dossier, visuels, fichiers=fichiers, calcul_s=time.time() - t0, extra=mesures), flush=True)
    except Exception as e:                                       # noqa: BLE001 — toute panne finit la tâche proprement
        print(f"{type(e).__name__}: {e}", flush=True)
        print(finir(tid, dossier, visuels, erreur=f"{type(e).__name__}: {str(e)[:300]}"), flush=True)
    finally:
        shutil.rmtree(travail, ignore_errors=True)
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def creer(q, par="papa"):
    """Le cockpit (page Atelier) : une demande JSON → la tâche lancée."""
    if q.get("type") == "image":
        return lancer(preparer_image(q.get("description"), q.get("format") or "carre", q.get("titre", ""), par=par))
    if q.get("type") == "clip":
        return lancer(preparer_clip(q.get("chanson"), q.get("images"), q.get("style") or "spectre", q.get("format") or "",
                                    q.get("titre", ""), q.get("duree_s"), q.get("debut_s", 0), par=par))
    raise Refus("type inconnu (image ou clip)")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "generer":
        generer(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) >= 2 and sys.argv[1] == "lancer":
        # le cockpit : une ligne JSON en entrée, une ligne JSON en sortie
        try:
            r = creer(json.loads(sys.stdin.read() or "{}"))
            print(json.dumps({"ok": True, **r}, ensure_ascii=False))
        except Refus as e:
            print(json.dumps({"ok": False, "erreur": str(e)}, ensure_ascii=False))
    else:
        print("usage : atelier_visuel.py generer <tâche> [dossier] | lancer", file=sys.stderr)
        sys.exit(2)
