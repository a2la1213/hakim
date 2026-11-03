"""(03/11, Ahmed : « ta transcription doit se faire mot à mot ; il prend le premier mot, puis en parallèle le deuxième ;
ça doit aussi driver son attention » ; « Whisper pour la voix ») l'oreille VIVE : un petit Whisper (small, ~0,4 s pour 6 s
de voix sur le M4), à part de l'oreille principale (large-v3-turbo, qui partage son processus avec sa voix), transcrit en
continu ce que papa est EN TRAIN de dire. Ses mots sont un aperçu : la page les montre et son oreille les suit ; le texte
qui part à Hakim reste celui de la grande oreille.

Un processus qui reste en vie : une ligne JSON par demande sur l'entrée {id, fichier, langue, contexte}, une ligne par
réponse {id, texte, ms} ou {id, erreur}.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt  # noqa: E402  (l'amorce et le filtre des inventions, les mêmes que la grande oreille)

MODELE = os.environ.get("JARVIS_WHISPER_VIF", "mlx-community/whisper-small-mlx")


def transcrire(mlx_whisper, fichier, langue=None, contexte=""):
    t0 = time.time()
    base = stt.AMORCES.get(langue or "fr", stt.AMORCE)
    amorce = base + (" " + contexte.strip()[-200:] if contexte and contexte.strip() else "")
    r = mlx_whisper.transcribe(fichier, path_or_hf_repo=MODELE, initial_prompt=amorce, language=langue or None,
                               condition_on_previous_text=False)
    if not langue and r.get("language") not in stt.LANGUES_PERMISES:     # une langue qui n'est pas la sienne : en français
        r = mlx_whisper.transcribe(fichier, path_or_hf_repo=MODELE, initial_prompt=amorce, language="fr",
                                   condition_on_previous_text=False)
    texte = stt.filtrer_segments(r.get("segments") or [{"text": r.get("text")}], base)
    return {"texte": texte, "langue": r.get("language"), "ms": int((time.time() - t0) * 1000)}


def main():
    import mlx_whisper
    import numpy as np
    mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32), path_or_hf_repo=MODELE, language="fr")   # chargé d'avance
    print(json.dumps({"pret": True, "modele": MODELE}), flush=True)
    for ligne in sys.stdin:
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        try:
            sortie = transcrire(mlx_whisper, str(d["fichier"]), d.get("langue") or None, str(d.get("contexte") or ""))
        except Exception as e:  # noqa: BLE001  (une demande ratée ne tue pas l'oreille)
            sortie = {"erreur": str(e)[:200]}
        print(json.dumps({"id": d.get("id"), **sortie}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
