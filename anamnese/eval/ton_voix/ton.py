"""Le ton d'une voix (27/10 ; demande d'Ahmed relayée par Hakim à 20:26, approche validée par Ahmed : « pour l'instant ça
fait l'affaire »). Un modèle local d'émotion de la parole, audEERING wav2vec2-large-robust-12-ft-emotion-msp-dim
(CC BY-NC-SA 4.0 : usage personnel, non commercial), donne trois nombres de 0 à 1 par extrait : l'ÉVEIL (calme → animé),
la DOMINANCE (effacé → affirmé) et la VALENCE (négatif → positif). Rien ne sort du Mac.

Ici, seulement ce qu'il faut pour le test d'étalonnage sur la voix d'Ahmed (eval/ton_voix/criteres.md, figé avant) :
lire un WAV, le mesurer, et les statistiques (AUC, intervalle par bootstrap, permutation). Le venv de la voix
(jarvis/.venv, arm64 : torch et transformers) le fait tourner ; rien n'y est installé."""
import io
import math
import random
import wave

import numpy as np

MODELE = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
TAUX = 16000
DIMENSIONS = ("arousal", "dominance", "valence")      # l'ordre de config.json (id2label)

_charge = {}


def charger():
    """Le modèle (une fois), sur le CPU : MPS est à Whisper et à la voix de Hakim."""
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
            h = self.wav2vec2(input_values)[0]
            return self.classifier(torch.mean(h, dim=1))

    torch.set_num_threads(4)
    fe = Wav2Vec2FeatureExtractor.from_pretrained(MODELE)
    m = ModeleEmotion.from_pretrained(MODELE).eval()
    _charge.update(fe=fe, m=m)
    return fe, m


def lire_wav(source):
    """Un WAV PCM 16 bits (chemin ou octets) → signal mono float32 à 16 kHz."""
    with wave.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("WAV 16 bits attendu")
        n, taux = w.getnchannels(), w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if n > 1:
        x = x.reshape(-1, n).mean(axis=1)
    if taux != TAUX:
        from scipy.signal import resample_poly
        g = math.gcd(TAUX, taux)
        x = resample_poly(x, TAUX // g, taux // g).astype(np.float32)
    return x


def mesurer(signal):
    """{arousal, dominance, valence} d'un signal à 16 kHz (de 0 à 1 environ)."""
    import torch
    fe, m = charger()
    v = fe(signal, sampling_rate=TAUX, return_tensors="pt").input_values
    with torch.inference_mode():
        y = m(v)[0].tolist()
    return {d: round(float(y[i]), 4) for i, d in enumerate(DIMENSIONS)}


# ---------- les statistiques (critères figés)
def auc(pos, neg):
    """P(un extrait « pos » a une valeur plus haute qu'un « neg »), les égalités comptent pour moitié."""
    if not pos or not neg:
        return float("nan")
    s = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
    return s / (len(pos) * len(neg))


def bootstrap_ic(pos, neg, n=2000, graine=27102026):
    """Intervalle à 95 % de l'AUC, en retirant les extraits avec remise dans chaque groupe."""
    r = random.Random(graine)
    vals = sorted(auc([r.choice(pos) for _ in pos], [r.choice(neg) for _ in neg]) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def permutation_p(pos, neg, n=5000, graine=27102026):
    """p unilatéral : la part des étiquettes mélangées qui donnent une AUC au moins aussi haute (le témoin négatif)."""
    r = random.Random(graine)
    obs, tout, k = auc(pos, neg), list(pos) + list(neg), 0
    for _ in range(n):
        r.shuffle(tout)
        if auc(tout[:len(pos)], tout[len(pos):]) >= obs:
            k += 1
    return (k + 1) / (n + 1)
