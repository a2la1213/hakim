# tests/test_dream_free_prompt.py
import dream_lab, config

def test_prompt_rem_free_has_no_menu_choice():
    p = dream_lab.prompt_rem_free("TON ÉTAT : neutre.")
    assert "###CHOIX###" not in p            # rien à choisir
    assert "###REVE###" in p and "###FIN###" in p
    assert "TON ÉTAT : neutre." in p         # l'état est injecté
    assert config.PERSONA.split("\n")[0] in p

def test_prompt_rem_free_says_no_seeds_and_free():
    p = dream_lab.prompt_rem_free("x").lower()
    assert "aucun souvenir" in p and "librement" in p
