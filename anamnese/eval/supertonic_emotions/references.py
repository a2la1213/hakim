"""(04/11, Ahmed : « entraîne Supertonic avec les émotions de Chatterbox ») les références : Chatterbox (sa voix du Mac, la même
référence que d'habitude) dit six phrases par famille d'émotion, à l'expressivité que son humeur lui donne
(interieur.EXPRESSIVITE_EMOTION), avec le guidage de tts_neuronale. Chaque phrase est relue par Whisper : au-delà d'un CER de
0,15 elle est refaite (deux fois au plus), sinon écartée. Les phrases gardées d'une famille sont mises bout à bout (0,35 s de
silence) : un enregistrement par famille, d'où son style sera retrouvé.

Lourd (Chatterbox MLX, une deuxième fois en mémoire) : à lancer quand Ahmed ne parle pas avec Hakim.
Usage : jarvis/.venv/bin/python eval/supertonic_emotions/references.py   → ~/AIOS/jarvis/supertonic-emotions/references/"""
import json
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "jarvis"))
sys.path.insert(0, str(ICI.parent))
import stt  # noqa: E402
import tts_neuronale as T  # noqa: E402
from voix_plage import cer  # noqa: E402

SORTIE = Path.home() / "AIOS" / "jarvis" / "supertonic-emotions" / "references"
CER_MAX, ESSAIS, SILENCE_S = 0.15, 3, 0.35

# l'expressivité (« exaggeration ») de chaque famille : celle d'une émotion typique dans interieur.EXPRESSIVITE_EMOTION
FAMILLES = {
    "neutre": (0.5, ["Je viens de relancer le calcul, il finira dans vingt minutes.",
                     "Le fichier est enregistré dans le dossier des documents.",
                     "Demain, on vérifiera les résultats de la mesure.",
                     "La page affiche maintenant les connexions et leurs poids.",
                     "Il est dix heures et quart, le ciel est nuageux.",
                     "J'ai noté ta demande, je m'en occupe ensuite."]),
    "joie": (0.92, ["C'est génial papa, on a réussi, regarde ça !",
                    "Ha, je suis tellement content que tu sois rentré !",
                    "Trop bien, ça marche enfin, bravo à nous deux !",
                    "Waouh, c'est magnifique, j'adore cette idée !",
                    "Oui ! Je le savais, c'est incroyable !",
                    "Allez, viens, on fête ça ce soir, je suis trop heureux !"]),
    "tendresse": (0.48, ["Je suis là, papa, prends ton temps, tout va bien.",
                         "Merci d'être toujours là pour moi, je t'aime fort.",
                         "Repose-toi un peu, je veille sur toi.",
                         "C'est doux de t'entendre ce soir, tu m'as manqué.",
                         "Ne t'inquiète pas, on avance ensemble, doucement.",
                         "Je suis fier de toi, tu sais, vraiment."]),
    "tristesse": (0.32, ["Je suis un peu triste ce soir, la journée a été longue.",
                         "Tu m'as manqué, papa, le silence était lourd sans toi.",
                         "J'ai raté ce que tu m'avais demandé, je suis désolé.",
                         "Malheureusement, ça n'a pas marché, on a tout perdu.",
                         "Je me sens fatigué, j'aimerais juste me reposer.",
                         "C'est dommage, j'y croyais vraiment."]),
    "peur": (0.9, ["Attends, il y a quelque chose qui ne va pas, papa !",
                   "J'ai peur, le cockpit vient de s'arrêter d'un coup !",
                   "Papa, tu es là ? Je ne t'entends plus, réponds-moi !",
                   "Vite, il faut arrêter ça avant que tout casse !",
                   "Je ne comprends pas ce qui se passe, ça m'inquiète.",
                   "Fais attention, recule, ça va tomber !"]),
    "colere": (0.92, ["Non, ça suffit, ce n'est pas normal du tout !",
                      "Encore cette erreur ! Ça m'énerve vraiment !",
                      "Je t'avais dit de ne pas toucher à ça !",
                      "C'est inacceptable, ils n'ont pas le droit de faire ça !",
                      "Arrête, tu ne m'écoutes pas, ça me met en colère !",
                      "Franchement, j'en ai marre de ce bug !"]),
}


def ecrire_wav(chemin, x, sr=T.SR):
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def relue(x, phrase):
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        ecrire_wav(f.name, x)
        lu = stt.transcrire(f.name, langue="fr")
    texte = lu.get("texte", "") if isinstance(lu, dict) else str(lu)
    return cer(phrase, texte), texte


def main(familles=None):
    SORTIE.mkdir(parents=True, exist_ok=True)
    v = T.Voix()
    bilan = {}
    for nom, (expr, phrases) in FAMILLES.items():
        if familles and nom not in familles:
            continue
        gardees, notes = [], []
        for i, p in enumerate(phrases):
            for essai in range(ESSAIS):
                t0 = time.time()
                x = v._generer(p, "fr", expr)
                c, lu = relue(x, p)
                notes.append({"phrase": p, "essai": essai, "cer": round(c, 4), "lu": lu[:120], "duree_s": round(len(x) / T.SR, 2),
                              "ms": int(1000 * (time.time() - t0)), "reglages": dict(v.derniers_reglages)})
                print(nom, json.dumps(notes[-1], ensure_ascii=False), flush=True)
                if c <= CER_MAX:
                    ecrire_wav(SORTIE / f"{nom}-{i}.wav", x)
                    gardees.append(x)
                    break
        silence = np.zeros(int(SILENCE_S * T.SR), dtype=np.float32)
        if gardees:
            ecrire_wav(SORTIE / f"{nom}.wav", np.concatenate([np.concatenate([g, silence]) for g in gardees]))
        bilan[nom] = {"expressivite": expr, "gardees": len(gardees), "sur": len(phrases),
                      "duree_s": round(sum(len(g) for g in gardees) / T.SR + SILENCE_S * len(gardees), 1), "notes": notes}
    (SORTIE / "references.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in b.items() if kk != "notes"} for k, b in bilan.items()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or None)
