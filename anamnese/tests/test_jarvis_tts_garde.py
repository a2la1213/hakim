"""La garde de la voix neuronale (jarvis/tts_garde.py, 2026-10-22) : plus de parole inventée après la phrase."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import tts_garde as G  # noqa: E402


def test_le_plafond_suit_la_longueur_du_texte():
    court, long_ = G.jetons_max("Oui.", "fr"), G.jetons_max("Je te propose de commencer par la voix, " * 3, "fr")
    assert 37 <= court <= 50                         # « Oui. » : moins de 2 s de parole permise, pas 40 s
    assert long_ > 5 * court and long_ <= G.JETONS_MAX
    assert G.jetons_max("x" * 5000) == G.JETONS_MAX


def test_le_plafond_laisse_le_temps_a_une_parole_lente():
    phrase = "Il est quatorze heures trente et j'ai douze mille francs suisses sur le compte."
    secondes = G.jetons_max(phrase, "fr") / G.JETONS_PAR_S
    assert secondes >= len(phrase.replace(" ", "")) / 9      # même lu à 9 caractères par seconde, rien n'est coupé


def test_l_arabe_ne_compte_pas_ses_voyelles_notees():
    nu, vocalise = "بسم الله الرحمن الرحيم", "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
    assert G.jetons_max(nu, "ar") == G.jetons_max(vocalise, "ar")
    assert G.jetons_max(nu, "ar") > G.jetons_max(nu, "fr")      # l'arabe récité va plus lentement


def test_une_phrase_toujours_finie_et_jamais_vide():
    assert G.phrase_finie("Oui") == "Oui."
    assert G.phrase_finie("  Vraiment ?  ") == "Vraiment ?"
    assert G.phrase_finie("« C'est ça. »") == "« C'est ça. »"
    assert G.phrase_finie("الحمد لله") == "الحمد لله."
    for vide in ("", "  ", "…", "!!", "12 ."):
        assert G.phrase_finie(vide) is None
