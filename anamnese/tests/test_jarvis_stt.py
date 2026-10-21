"""La reconnaissance de la voix (jarvis/stt.py) : en automatique, la langue est choisie PARMI celles
d'Ahmed (français, arabe, anglais) — Whisper en détection libre prenait parfois sa voix pour de
l'islandais (signalé par Ahmed le 2026-10-18)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import stt  # noqa: E402


def test_l_islandais_n_est_jamais_choisi():
    probs = {"is": 0.46, "fr": 0.31, "no": 0.12, "en": 0.06, "ar": 0.05}
    assert stt.choisir_langue(probs) == "fr"


def test_la_plus_probable_des_trois_langues_d_ahmed():
    assert stt.choisir_langue({"ar": 0.7, "fr": 0.2, "en": 0.1}) == "ar"
    assert stt.choisir_langue({"en": 0.5, "fr": 0.4, "ar": 0.1}) == "en"
    assert stt.choisir_langue({"de": 0.9}) == "fr"                 # aucune des trois : le français par défaut
    assert stt.LANGUES_PERMISES == ("fr", "ar", "en")


# --- les inventions de Whisper (relevées dans le fil de Hakim, 18-19/10) -----------------------------

def seg(texte, **k):
    return {"text": texte, "no_speech_prob": k.get("ns", 0.0), "avg_logprob": k.get("lp", -0.2), "compression_ratio": k.get("cr", 1.0)}


def test_l_amorce_recrachee_sur_un_bruit_de_moteur_est_ecartee():
    """Reproduit en réel le 2026-10-19 : un bruit de moteur → « We talk about Anamnèse, Jarvis, the AI robot
    and Claude Code. » (l'amorce anglaise, no_speech_prob 0,0) — vu par Ahmed en voiture à 10:02, 14:06, 16:28."""
    amorce = stt.AMORCES["en"]
    assert stt.filtrer_segments([seg(" We talk about Anamnèse, Jarvis, the AI robot and Claude Code.", lp=-0.47)], amorce) == ""
    # un long passage recopié (≥ 8 mots d'affilée) ; une salutation seule, elle, passe (test plus bas)
    assert stt.filtrer_segments([seg(" Salam alaykoum frérot. Wa alaykoum salam. Inchallah, hamdoulillah, wallah, machallah")],
                                stt.AMORCES["fr"]) == ""


def test_une_vraie_phrase_qui_parle_d_anamnese_reste():
    amorce = stt.AMORCES["fr"]
    t = stt.filtrer_segments([seg(" Hakim, tu peux me dire où on en est sur Anamnèse et sur le robot ?")], amorce)
    assert t == "Hakim, tu peux me dire où on en est sur Anamnèse et sur le robot ?"


def test_les_boucles_et_les_formules_fantomes_sont_ecartees():
    amorce = stt.AMORCES["fr"]
    assert stt.filtrer_segments([seg(" de temps de temps de temps de temps de temps", cr=2.6)], amorce) == ""
    assert stt.filtrer_segments([seg(" huhuhuhuhuhuhuhuhuhuhu", cr=3.1)], amorce) == ""
    assert stt.filtrer_segments([seg(" Thank you.")], stt.AMORCES["en"]) == ""            # une moto, 19/10 17:39
    assert stt.filtrer_segments([seg(" Bonjour."), seg(" de temps de temps de temps de temps", cr=2.5)], amorce) == "Bonjour."


def test_le_silence_n_est_pas_transcrit():
    assert stt.parole_probable({"fr": 0.12, "en": 0.30, "ar": 0.02, "es": 0.15}) is False     # mesuré sur du silence
    assert stt.parole_probable({"fr": 0.99, "en": 0.01}) is True
    assert stt.parole_probable({"en": 0.64, "ru": 0.09}) is True                               # bruit de moteur : l'écho est filtré après


def test_les_vraies_salutations_d_ahmed_passent():
    """Relecture Opus du lot C (2026-10-19) : le filtre d'écho jetait les salutations d'Ahmed, parce qu'elles
    sont dans l'amorce. Seul un long passage recopié (la phrase des projets, ou 8 mots d'affilée) est un écho."""
    fr = stt.AMORCES["fr"]
    for t in ("Salam alaykoum frérot", "Salam alaykoum frérot, ça va ?", "Wa alaykoum salam",
              "Inchallah hamdoulillah wallah machallah bismillah", "Bye."):
        assert stt.filtrer_segments([seg(" " + t)], fr) == t, t
    assert stt.filtrer_segments([seg(" On parle d'Anamnèse, de Jarvis, du robot IA et de Claude Code.")], fr) == ""
    assert stt.filtrer_segments([seg(" نتكلم عن أنامنيز وجارفيس.")], stt.AMORCES["ar"]) == ""
