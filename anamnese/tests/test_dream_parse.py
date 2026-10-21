"""Choix libre : parsing tolérant (valide / partiel / « aucune » / invalide / cassé)."""
import dream_lab

MENU = [{"episode_id": 100 + i, "rubric": "projets/demo", "strate": "recent",
         "snippet": f"graine {i}", "facets": []} for i in range(1, 13)]


def test_parse_valide():
    out = "###CHOIX###\n- G4\n- G7\n- G11\n###REVE###\n- Peut-être X\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [104, 107, 111]


def test_parse_tolerant_formats():
    out = "###CHOIX###\n1. [g2]\n* G 5\n- G2\n###REVE###\n- idée\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [102, 105]      # dédup + casse + espaces


def test_parse_aucune():
    out = "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == []


def test_parse_refs_invalides_ignorees():
    out = "###CHOIX###\n- G13\n- G0\n- G3\n###REVE###\n- idée\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [103]


def test_parse_inparsable():
    assert dream_lab.parse_choice("je rêve librement sans format", MENU) is None
    assert dream_lab.parse_choice(None, MENU) is None
    assert dream_lab.parse_choice("###CHOIX###\n- G99\n###REVE###\n- x\n###FIN###", MENU) is None


def test_parse_marqueur_reve_accentue():
    # ###RÊVE### accentué : le corps du rêve ne doit PAS fuir dans le bloc CHOIX
    # (sinon un « aucune » ou un « G7 » du rêve contamine le choix).
    out = "###CHOIX###\n- G4\n###RÊVE###\n- Peut-être G7, mais aucune certitude\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [104]


def test_parse_refs_ancrees():
    # Le « g » de « rang » + newline ne doit pas fabriquer un G1 fantôme.
    out = "###CHOIX###\n- le souvenir de rang\n1. G5\n###REVE###\n- idée\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [105]
    # G112 n'est pas G11 : ref hors menu → rien de valide → None.
    out2 = "###CHOIX###\n- G112\n###REVE###\n- x\n###FIN###"
    assert dream_lab.parse_choice(out2, MENU) is None


def test_prompt_contient_les_graines_et_le_format():
    p = dream_lab.prompt_rem("ÉTAT: neutre", MENU)
    assert "[G1]" in p and "[G12]" in p and "###CHOIX###" in p and "###REVE###" in p
    assert "aucun" in p.lower()                                  # la porte de sortie est offerte
