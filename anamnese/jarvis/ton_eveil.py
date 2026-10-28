"""Le ton de la voix en direct : l'ÉVEIL seulement (27/10). Le test figé sur la voix d'Ahmed (eval/ton_voix, f4da4e1 →
415a46d) : l'éveil sépare une voix animée d'une voix calme (AUC 0,97, darija 0,96) ; la valence ne distingue pas la joie de
la tension, elle n'est donc jamais utilisée. Ahmed, 22:48 : « parfait, je suis tout à fait d'accord » (éveil seulement, avec
son doute, et un point au bout de quelques jours : si ça embrouille Hakim, on l'enlève).

Le modèle local audEERING wav2vec2-large-robust-12-ft-emotion-msp-dim (CC BY-NC-SA 4.0, usage personnel), sur le CPU (MPS
est à Whisper et à la voix de Hakim), chargé à côté au lancement du processus voix, jamais par le réseau. Il normalise chaque extrait : il ne
voit pas le volume. Seul un nombre sort d'ici ; l'audio n'est jamais gardé. Interrupteur : JARVIS_TON_VOIX=0."""
import os
import threading

import numpy as np

MODELE = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
TAUX = 16000
MIN_S, MAX_S = 1.5, 8.0
_charge = {}
_verrou = threading.Lock()


def prechauffer():
    """Au lancement du processus voix : le modèle se charge à côté (3,7 s), pas pendant la première phrase d'Ahmed."""
    if os.environ.get("JARVIS_TON_VOIX", "1") != "0":
        threading.Thread(target=lambda: _essayer(charger), daemon=True).start()


def _essayer(f):
    try:
        f()
    except Exception:
        pass


def charger():
    with _verrou:
        return _charger()


def _charger():
    if "m" in _charge:
        return _charge["fe"], _charge["m"]
    import torch
    from torch import nn
    from transformers import Wav2Vec2FeatureExtractor
    from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

    class TeteRegression(nn.Module):
        def __init__(self, config):
            super().__init__()
            self.dense = nn.Linear(config.hidden_size, config.hidden_size)
            self.dropout = nn.Dropout(config.final_dropout)
            self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

        def forward(self, x):
            return self.out_proj(self.dropout(torch.tanh(self.dense(self.dropout(x)))))

    class ModeleEmotion(Wav2Vec2PreTrainedModel):        # la classe de la fiche du modèle (noms des poids inchangés)
        def __init__(self, config):
            super().__init__(config)
            self.wav2vec2 = Wav2Vec2Model(config)
            self.classifier = TeteRegression(config)
            self.post_init()

        def forward(self, input_values):
            return self.classifier(torch.mean(self.wav2vec2(input_values)[0], dim=1))

    torch.set_num_threads(2)
    fe = Wav2Vec2FeatureExtractor.from_pretrained(MODELE, local_files_only=True)
    m = ModeleEmotion.from_pretrained(MODELE, local_files_only=True).eval()
    _charge.update(fe=fe, m=m)
    return fe, m


def _mesurer(x):
    import torch
    fe, m = charger()
    with torch.inference_mode():
        return float(m(fe(x, sampling_rate=TAUX, return_tensors="pt").input_values)[0][0])   # 0 = arousal (id2label)


def eveil(brut):
    """L'éveil d'un morceau de parole à 16 kHz (0 calme → 1 animé), sur ses 8 dernières secondes ; None si trop court,
    coupé par l'interrupteur, ou en panne (jamais bloquant)."""
    if os.environ.get("JARVIS_TON_VOIX", "1") == "0" or brut is None or len(brut) < MIN_S * TAUX:
        return None
    try:
        x = np.asarray(brut, dtype=np.float32)[-int(MAX_S * TAUX):]
        return round(min(1.0, max(0.0, _mesurer(x))), 3)
    except Exception:
        return None
