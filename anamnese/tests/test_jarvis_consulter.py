"""Parler directement à Argon (Gemini) : liste blanche, budget, rien de privé, réponse enveloppée, journal
(jarvis/consulter.py, lot H point 31 de la liste du 2026-10-19). Aucun appel réseau : l'appel est simulé."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import consulter  # noqa: E402


def test_rien_de_prive_ne_part_et_la_reponse_est_une_donnee(tmp_path):
    envoye = []
    r = consulter.consulter("argon", "Ahmed (ahmed@exemple.ch, +41 79 123 45 67, CH93 0076 2011 6238 5295 7) demande : "
                            "la clé sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd marche ? Et n_s pour Starobinsky ?",
                            journal=tmp_path / "j.jsonl", cle="k", appeler=lambda m, c, q: envoye.append(q) or "n_s ≈ 0,9633")
    q = envoye[0]
    assert "ahmed@exemple.ch" not in q and "79 123 45 67" not in q and "CH93" not in q and "sk-ant-api03-ABCDEF" not in q
    assert "Starobinsky" in q
    assert r.startswith("⟦CONTENU EXTERNE") and "0,9633" in r
    ligne = json.loads((tmp_path / "j.jsonl").read_text().splitlines()[0])
    assert ligne["ia"] == "argon" and "ahmed@exemple.ch" not in ligne["question"]


def test_liste_blanche_budget_et_cle(tmp_path, monkeypatch):
    with pytest.raises(consulter.Refus):
        consulter.consulter("chatgpt", "bonjour", journal=tmp_path / "j.jsonl", cle="k", appeler=lambda *a: "x")
    monkeypatch.setattr(consulter, "_cle", lambda s: None)
    with pytest.raises(consulter.Refus, match="trousseau"):
        consulter.consulter("argon", "bonjour", journal=tmp_path / "j.jsonl", appeler=lambda *a: "x")
    monkeypatch.setattr(consulter, "CONSULTATIONS_JOUR", 2)
    for _ in range(2):
        consulter.consulter("argon", "bonjour", journal=tmp_path / "j.jsonl", cle="k", appeler=lambda *a: "x")
    with pytest.raises(consulter.Refus, match="budget"):
        consulter.consulter("argon", "bonjour", journal=tmp_path / "j.jsonl", cle="k", appeler=lambda *a: "x")


def test_l_expurgation_masque_le_prive_sans_casser_les_calculs():
    """Relecture Opus du 2026-10-20 : dates et décimales étaient masquées ; des numéros et adresses passaient."""
    import consulter
    t = consulter.expurger("Le 2026-10-19 on a trouvé pi = 3.14159265358 et phi = 1.6180339887 ; 12 345 678 tests.")
    assert "2026-10-19" in t and "3.14159265358" in t and "1.6180339887" in t and "12 345 678" in t
    for prive in ("06/12/34/56/78", "06 12 34 56 78", "+41 79 123 45 67", "+33612345678", "079 123 45 67",
                  "ahmed (at) gmail (dot) com", "ahmed@gmail.com", "ahmed [at] exemple [dot] fr"):
        assert prive not in consulter.expurger(f"contacte {prive} demain"), prive
    assert "Soleil2024!" not in consulter.expurger("mdp Gmail: Soleil2024!")
    assert "CH93 0076 2011 6238 5295 7" not in consulter.expurger("IBAN CH93 0076 2011 6238 5295 7")


def test_quota_atteint_sur_pro_on_passe_a_flash(tmp_path):
    import urllib.error
    vus = []
    def appeler(modele, cle, q):
        vus.append(modele)
        if "pro" in modele:
            raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
        return "réponse de Flash"
    r = consulter.consulter("argon", "question", journal=tmp_path / "j.jsonl", cle="k", appeler=appeler)
    assert vus == ["gemini-pro-latest", "gemini-flash-latest"] and "réponse de Flash" in r
    def jamais(modele, cle, q):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    with pytest.raises(consulter.Refus, match="quota"):
        consulter.consulter("argon", "question", journal=tmp_path / "j2.jsonl", cle="k", appeler=jamais)


def test_lenteur_distinguee_du_quota(tmp_path):
    def lent(modele, cle, q):
        raise TimeoutError("timed out")
    with pytest.raises(consulter.Refus, match="trop lent"):
        consulter.consulter("argon", "question", journal=tmp_path / "j.jsonl", cle="k", appeler=lent)
    assert not (tmp_path / "j.jsonl").exists()                               # ratée : pas comptée
