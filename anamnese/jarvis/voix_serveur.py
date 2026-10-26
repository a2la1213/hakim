"""Processus voix de Jarvis (feuille de route, étapes 5 et 5 bis).

Il garde les modèles en mémoire (Whisper pour écouter, une voix neuronale pour parler) et répond
au cockpit par l'entrée et la sortie standard, une requête JSON par ligne. Aucun port réseau :
seul le cockpit, qui le lance, peut lui parler.

Requêtes : {"id": 1, "op": "transcrire", "fichier": "<audio>", "langue": null}
           {"id": 2, "op": "dire", "texte": "...", "langue": "fr" | "ar", "fichier": "<sortie.wav>"}
           {"id": 3, "op": "etat"}
Réponses : {"id": 1, "texte": "...", "langue": "fr", "ms": 812}, {"id": 2, "fichier": "...", "ms": ..,
           "duree_s": ..}, {"id": 3, "stt": true, "tts": true, ...} ou {"id": n, "erreur": "..."}

Il s'arrête seul après INACTIVITE_S sans requête, pour rendre la mémoire unifiée du Mac (Gemma,
le robot) ; le cockpit le relance à la demande.
"""
import contextlib
import json
import os
import re
import select
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt  # noqa: E402

INACTIVITE_S = float(os.environ.get("JARVIS_VOIX_INACTIVITE_S", "900"))
# (24/10, 17:43, Hakim : sa voix tenait 10 Go sans rien faire, le Mac swappait à 14,6 Go) : 9,4 Go étaient des tampons
# Metal que MLX GARDE en cache après chaque synthèse ou transcription (« IOAccelerator » de footprint). Le cache est borné,
# vidé après chaque demande ; les modèles chargés restent (pas de rechargement).
CACHE_MAX_OCTETS = int(os.environ.get("JARVIS_VOIX_CACHE_MO", "512")) * 1024 * 1024


def borner_cache():
    try:
        import mlx.core as mx
        mx.set_cache_limit(CACHE_MAX_OCTETS)
    except Exception:
        pass


def vider_cache():
    try:
        import mlx.core as mx
        mx.clear_cache()
    except Exception:
        pass
_SORTIE = sys.stdout                # les réponses ; tout le reste (barres de progression…) va sur stderr
_tts = None


def _charger_tts():
    """La voix neuronale (étape 5 bis). None si elle n'est pas installée."""
    global _tts
    if _tts is None:
        try:
            import tts_neuronale
            _tts = tts_neuronale.Voix()
        except Exception as e:  # pas installée, modèle absent…
            print(f"[voix] synthèse neuronale indisponible : {type(e).__name__}: {e}", file=sys.stderr)
            _tts = False
    return _tts or None


def sortie_permise(fichier):
    """(audit du 2026-10-23) la voix n'écrit que là où le cockpit la fait écrire : un « jarvis-voix-….wav » du dossier
    temporaire, jamais un chemin choisi par quelqu'un d'autre."""
    try:
        f = os.path.realpath(str(fichier or ""))
        return (re.fullmatch(r"jarvis-voix-[A-Za-z0-9_.-]{1,120}\.wav", os.path.basename(f)) is not None
                and os.path.dirname(f) == os.path.realpath(tempfile.gettempdir()))
    except (OSError, ValueError):
        return False


def traiter(req):
    op = req.get("op")
    if op == "etat":                     # sans charger la voix (4,7 Go en mémoire) : est-elle installée ?
        import importlib.util
        return {"stt": stt.disponible(), "tts": importlib.util.find_spec("mlx_audio") is not None,
                "tts_chargee": bool(_tts), "modele_stt": stt.MODELE}
    if op == "transcrire":
        if not stt.disponible():
            return {"erreur": "mlx-whisper n'est pas installé"}
        return stt.transcrire(req["fichier"], req.get("langue"), req.get("contexte") or "", req.get("voix"))
    if op == "empreinte_reinitialiser":       # (2026-10-20) sans charger aucun modèle
        import empreinte_vocale
        return empreinte_vocale.reinitialiser(str(req.get("portee") or "tout"))
    if op == "dire":
        if not sortie_permise(req.get("fichier")):
            return {"erreur": "fichier de sortie refusé (seulement un jarvis-voix-….wav du dossier temporaire)"}
        voix = _charger_tts()
        if voix is None:
            return {"erreur": "synthèse neuronale indisponible"}
        t0 = time.time()
        duree = voix.dire(str(req["texte"]), req.get("langue") or "fr", req["fichier"], req.get("exaggeration"), req.get("tempo"))
        return {"fichier": req["fichier"], "ms": int((time.time() - t0) * 1000), "duree_s": duree}
    return {"erreur": f"opération inconnue : {op}"}


def repondre(obj):
    _SORTIE.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _SORTIE.flush()


def main():
    borner_cache()
    dernier = time.time()
    while True:
        prets, _, _ = select.select([sys.stdin], [], [], 5.0)
        if not prets:
            if time.time() - dernier > INACTIVITE_S:
                return 0
            continue
        ligne = sys.stdin.readline()
        if not ligne:                       # le cockpit est parti
            return 0
        dernier = time.time()
        try:
            req = json.loads(ligne)
        except ValueError:
            continue
        try:
            with contextlib.redirect_stdout(sys.stderr):
                rep = traiter(req)
        except Exception as e:
            rep = {"erreur": f"{type(e).__name__}: {e}"[:300]}
        rep["id"] = req.get("id")
        repondre(rep)
        vider_cache()                       # (24/10) les tampons de cette demande ne restent pas en mémoire


if __name__ == "__main__":
    sys.exit(main())
