"""La voix neuronale de Jarvis (feuille de route, étape 5 bis) : Chatterbox Multilingual V3 (Resemble
AI, licence MIT, 23 langues dont le français et l'arabe) via mlx-audio, en local et gratuit.

Mesuré le 2026-10-16 sur le M4 (rapport de l'agent, fichiers dans le scratchpad de la session) :
- la partie texte (T3) quantifiée en 8 bits, en mémoire : facteur temps réel 0,75 à 0,95 (une
  réplique courte de 2,1 s calculée en 2,0 s) ; 4 bits écarté (25 % de caractères faux) ;
- relecture Whisper identique au texte en français et en arabe ;
- la même voix parle les deux langues (similarité 0,90 à 0,95) : seule `langue` change par appel ;
- pas de vrai flux : le cockpit envoie phrase par phrase.
Voix : celle de Resemble par défaut, ou un échantillon d'environ 10 s (une personne, son propre)
déposé dans REFERENCE, rechargé dès qu'il change.
"""
import os
import wave
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from huggingface_hub import hf_hub_download, snapshot_download
from mlx_audio.tts.models.chatterbox.chatterbox import Conditionals
from mlx_audio.tts.models.chatterbox.t3.cond_enc import T3Cond
from mlx_audio.tts.utils import load_model
from mlx_audio.utils import load_audio

import tts_garde

MODELE = "mlx-community/chatterbox-multilingual-v3"
FICHIERS = ["model.safetensors", "tokenizer.json", "config.json", "Cangjie5_TC.json"]
SR = 24000
REFERENCE = Path(os.environ.get("JARVIS_VOIX_REFERENCE", Path.home() / "AIOS" / "jarvis" / "voix-reference.wav"))
LANGUES = {"fr", "ar", "en", "es", "de", "it", "pt", "nl", "tr", "ru", "hi", "ja", "ko", "zh", "he", "pl",
           "sv", "da", "fi", "no", "el", "ms", "sw"}
REGLAGES = {"exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8}


def _local_dabord(fonction, *args, **kw):
    """Le cache d'abord (marche hors ligne), le réseau seulement s'il manque quelque chose."""
    try:
        return fonction(*args, local_files_only=True, **kw)
    except Exception:
        return fonction(*args, **kw)


class Voix:
    def __init__(self):
        self.modele = load_model(Path(_local_dabord(snapshot_download, MODELE, allow_patterns=FICHIERS)))
        nn.quantize(self.modele.t3, bits=8, group_size=64,          # le squelette Llama de T3 seulement
                    class_predicate=lambda p, m: isinstance(m, nn.Linear) and "tfmr.model.layers" in p)
        mx.eval(self.modele.parameters())
        # Pas du décodeur (flow matching) : 10 par défaut. Mesuré le 2026-10-16 (machine qui swappait) :
        # 6 pas donnent un facteur temps réel de 0,62 au lieu de 0,81 sur une longue phrase, et une
        # relecture Whisper comparable ; 4 pas déforment des mots. 6 : la voix reste fluide en flux.
        self.modele.s3gen.flow.n_timesteps = int(os.environ.get("JARVIS_TTS_PAS", "6"))
        self._defaut = self._voix_resemble()
        self.conds, self._ref_mtime = self._defaut, None
        self._suivre_reference()
        self._generer("Bonjour.", "fr")                              # chauffe les noyaux Metal

    @staticmethod
    def _voix_resemble():
        d = mx.load(_local_dabord(hf_hub_download, "mlx-community/chatterbox-fp16", "conds.safetensors"))
        t3 = T3Cond(speaker_emb=d["t3.speaker_emb"], cond_prompt_speech_tokens=d.get("t3.cond_prompt_speech_tokens"),
                    emotion_adv=d.get("t3.emotion_adv", mx.ones((1, 1, 1)) * 0.5))
        gen = {k[4:]: v for k, v in d.items() if k.startswith("gen.")}
        gen["prompt_feat_len"] = mx.array([gen["prompt_feat"].shape[1]])
        return Conditionals(t3, gen)

    def _suivre_reference(self):
        """Clone la voix de REFERENCE (une fois par version du fichier) ; sans fichier, voix par défaut."""
        try:
            mtime = REFERENCE.stat().st_mtime_ns
        except OSError:
            self.conds, self._ref_mtime = self._defaut, None
            return
        if mtime != self._ref_mtime:
            ref = load_audio(str(REFERENCE), sample_rate=SR)
            self.conds = self.modele.prepare_conditionals(ref, SR, exaggeration=REGLAGES["exaggeration"])
            self._ref_mtime = mtime

    def _generer(self, texte, langue, exaggeration=None):
        reglages = dict(REGLAGES)
        if isinstance(exaggeration, (int, float)):               # l'humeur s'entend (éveil → expressivité)
            reglages["exaggeration"] = max(0.3, min(0.8, float(exaggeration)))
            # conseil de Chatterbox : plus d'expressivité → moins de guidage (cfg), sinon le débit s'emballe ;
            # plus calme → un peu plus de guidage (diction posée). 0,5 → 0,5 ; 0,75 → 0,3 ; 0,35 → 0,55.
            reglages["cfg_weight"] = round(max(0.3, min(0.55, 0.5 - (reglages["exaggeration"] - 0.5) * 0.8)), 3)
        # (2026-10-22) un plafond de jetons proportionnel au texte : plus de parole inventée après la phrase
        self.derniers_reglages = reglages                       # (2026-10-23) notés avec les nombres du morceau
        res = next(self.modele.generate(texte, conds=self.conds, lang_code=langue, verbose=False,
                                        max_new_tokens=tts_garde.jetons_max(texte, langue), **reglages))
        return np.array(res.audio, dtype=np.float32).reshape(-1)

    def dire(self, texte, langue, fichier, exaggeration=None):
        """Écrit un WAV 24 kHz mono 16 bits ; rend sa durée en secondes."""
        self._suivre_reference()
        texte = tts_garde.phrase_finie(texte)
        if texte is None:                                         # rien à dire : un silence, jamais une invention
            audio = np.zeros(int(0.05 * SR), dtype=np.float32)
        else:
            audio = self._generer(texte, langue if langue in LANGUES else "fr", exaggeration)
        audio = _rogner(audio)
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(fichier), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        if texte is not None:                                     # (2026-10-23) durée, énergie, hauteur : sans le son
            try:
                import voix_nombres
                voix_nombres.noter(audio, SR, texte, langue, getattr(self, "derniers_reglages", None))
            except Exception:
                pass
        return round(len(audio) / SR, 3)


def _rogner(audio, seuil=0.01, marge_s=0.08):
    """Coupe le silence du début et de la fin (0,36 à 0,6 s mesurés) pour enchaîner les phrases."""
    fort = np.flatnonzero(np.abs(audio) > seuil)
    if not len(fort):
        return audio
    marge = int(marge_s * SR)
    return audio[max(0, fort[0] - marge): min(len(audio), fort[-1] + marge)]
