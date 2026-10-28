"""Le ton de la voix en direct (27/10 ; test figé dans eval/ton_voix : l'éveil passe, la valence non ; Ahmed, 22:48 :
« parfait, je suis tout à fait d'accord » pour l'éveil seulement). Sur chaque morceau oral : un nombre d'éveil, rien d'autre ;
l'audio n'est jamais gardé ; jamais bloquant pour la transcription."""
import inspect
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import ton_eveil as E  # noqa: E402


def test_trop_court_ou_coupe_rien_et_le_modele_n_est_pas_charge(monkeypatch):
    monkeypatch.setattr(E, "charger", lambda: (_ for _ in ()).throw(AssertionError("chargé pour rien")))
    assert E.eveil(np.zeros(16000, dtype=np.float32)) is None                 # 1 s
    monkeypatch.setenv("JARVIS_TON_VOIX", "0")
    assert E.eveil(np.zeros(16000 * 4, dtype=np.float32)) is None             # l'interrupteur


def test_au_plus_les_8_dernieres_secondes_et_un_nombre_borne(monkeypatch):
    vus = []
    monkeypatch.setattr(E, "_mesurer", lambda x: vus.append(len(x)) or 1.7)
    assert E.eveil(np.zeros(16000 * 20, dtype=np.float32)) == 1.0             # borné à [0, 1]
    assert vus == [16000 * 8]
    monkeypatch.setattr(E, "_mesurer", lambda x: 0.4321)
    assert E.eveil(np.zeros(16000 * 3, dtype=np.float32)) == 0.432


def test_une_panne_du_modele_ne_bloque_rien(monkeypatch):
    monkeypatch.setattr(E, "_mesurer", lambda x: (_ for _ in ()).throw(RuntimeError("panne")))
    assert E.eveil(np.zeros(16000 * 3, dtype=np.float32)) is None


def test_la_transcription_le_demande_seulement_en_reconnaissance():
    import stt
    src = inspect.getsource(stt.transcrire)
    reconnaitre = src[src.index('elif voix == "reconnaitre"'):]
    assert "ton_eveil.eveil(brut)" in reconnaitre and "ton_eveil" not in src[:src.index('elif voix == "reconnaitre"')]
