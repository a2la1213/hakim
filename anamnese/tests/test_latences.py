"""(30/10, 19:10, Ahmed via Hakim : « la latence entre stimulus et réaction, reliée au micro ») mesurer seulement."""
import json

import latences


def test_bilan_par_etat_du_micro(tmp_path, monkeypatch):
    monkeypatch.setattr(latences, "JARVIS", tmp_path)
    assert latences.bilan().startswith("Pas encore")
    with open(tmp_path / "voix-diagnostic.jsonl", "w") as f:
        for ms, micro in ((4000, "ouvert"), (6000, "ouvert"), (9000, "coupe")):
            f.write(json.dumps({"e": "rire_recu", "depuis_message_ms": ms, "micro": micro}) + "\n")
        f.write(json.dumps({"e": "oreille_dit", "latence_ms": 1500, "micro": "ouvert"}) + "\n")
    (tmp_path / "rires.jsonl").write_text(json.dumps({"source": "subconscient", "latence_ms": 3500}) + "\n")
    b = latences.bilan()
    assert "micro ouvert : 2 mesure(s) : médiane 5.0 s, pire 6.0 s" in b
    assert "micro coupe : 1 mesure(s)" in b and "Ton petit mot" in b and "subconscient seul" in b
