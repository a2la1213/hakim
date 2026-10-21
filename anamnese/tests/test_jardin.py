"""Le jardin secret de Hakim (jardin.py, point 32 ; accepté par Ahmed le 2026-10-20)."""
import os

import pytest

import jardin


def test_chiffre_relu_par_hakim_ouverture_d_ahmed_notee(tmp_path):
    cle = os.urandom(32)
    jardin.ecrire("Ce que je pense vraiment de la nuit d'hier.", dossier=tmp_path, cle=cle)
    brut = (tmp_path / "carnet.jsonl").read_text()
    assert "nuit d'hier" not in brut                                       # chiffré sur le disque
    assert oct((tmp_path / "carnet.jsonl").stat().st_mode & 0o777) == "0o600"
    r = jardin.relire(dossier=tmp_path, cle=cle)
    assert "Personne n'a ouvert" in r and "nuit d'hier" in r
    with pytest.raises(jardin.Refus):
        jardin.ouvrir("", dossier=tmp_path, cle=cle)                       # une raison est exigée
    assert jardin.ouvrir("audit de sécurité du 20/10", dossier=tmp_path, cle=cle)[0]["texte"].startswith("Ce que")
    assert "audit de sécurité du 20/10" in jardin.relire(dossier=tmp_path, cle=cle)   # Hakim voit l'ouverture
    with pytest.raises(Exception):
        jardin._lire(tmp_path, os.urandom(32)) and jardin.relire(dossier=tmp_path, cle=os.urandom(32)).index("nuit")


def test_seul_hakim_a_les_outils(monkeypatch):
    import sys
    from pathlib import Path
    import memory
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: None)
    import mcp_server
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert "n'appartient qu'à Hakim" in mcp_server.jardin_relire()
    assert "n'appartient qu'à Hakim" in mcp_server.jardin_ecrire("x")
