"""(30/10, accord d'Ahmed : « fais ce qu'il dit » ; « oui à tout, et que je puisse le suivre dans le cockpit ») le Tricordeur
de Hakim (signer avec SA clé, livrer dans Documents/Hakim) et l'écriture dans les Documents du téléphone : sauvegarde avant
toute modification, jamais de suppression, un journal de chaque geste. Aucun trousseau ni outil Android réel ici."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import telephone  # noqa: E402
import tricordeur  # noqa: E402


@pytest.fixture
def J(tmp_path, monkeypatch):
    j = tmp_path / "jarvis"
    (j / "cwd" / "atelier" / "tricordeur" / "build").mkdir(parents=True)
    (j / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim").mkdir(parents=True)
    monkeypatch.setattr(telephone, "JARVIS", j)
    monkeypatch.setattr(tricordeur, "JARVIS", j)
    return j


def test_ecrire_dans_ses_documents_sauvegarde_avant_et_note(J):
    doc = J / "cwd" / "fichiers" / "telephone" / "Z Fold 7"
    (doc / "papiers.txt").write_text("version d'Ahmed")
    r = telephone.ecrire("papiers.txt", texte="version de Hakim", note="une correction")
    assert (doc / "papiers.txt").read_text() == "version de Hakim"
    assert Path(r["sauvegarde"]).read_text() == "version d'Ahmed" and "telephone-sauvegardes" in r["sauvegarde"]
    assert not r["sauvegarde"].startswith(str(doc)), "la sauvegarde hors du dossier synchronisé"
    telephone.ecrire("Hakim/nouveau.txt", texte="bonjour papa")
    j = telephone.journal()
    assert [x["action"] for x in j] == ["sauvegarde", "ecriture", "ajout"]
    assert j[1]["note"] == "une correction"
    for mauvais in ("../dehors.txt", "/etc/passwd", "~/x", ".stversions/x", ""):
        with pytest.raises(telephone.Refus):
            telephone.ecrire(mauvais, texte="x")
    assert not hasattr(telephone, "supprimer"), "aucun outil ne supprime"


def test_depuis_son_atelier_et_jamais_a_travers_un_lien(J, tmp_path):
    a = J / "cwd" / "atelier"
    (a / "res.csv").write_text("a,b\n1,2\n")
    telephone.ecrire("Hakim/res.csv", depuis_atelier="res.csv")
    assert (J / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim" / "res.csv").read_text() == "a,b\n1,2\n"
    (tmp_path / "secret").write_text("x")
    (a / "lien.csv").symlink_to(tmp_path / "secret")
    with pytest.raises(telephone.Refus):
        telephone.ecrire("Hakim/x.csv", depuis_atelier="lien.csv")


def test_signer_avec_sa_cle_sans_rien_executer_de_son_atelier(J, monkeypatch):
    apk = J / "cwd" / "atelier" / "tricordeur" / "build" / "tricordeur-hakim.apk"
    apk.write_bytes(b"PK-non-signe")
    monkeypatch.setattr(tricordeur, "_mot_de_passe", lambda creer=False: "mdp")
    monkeypatch.setattr(tricordeur, "_cle", lambda env: J / "cle.keystore")
    vu = {}

    def faux(cmd, **k):
        vu["cmd"] = cmd
        vu["env"] = k.get("env", {})
        Path(cmd[cmd.index("--out") + 1]).write_bytes(b"PK-signe")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    s = tricordeur.signer("tricordeur/build/tricordeur-hakim.apk", executer=faux)
    assert s.name == "tricordeur-hakim-signe.apk" and s.read_bytes() == b"PK-signe"
    assert vu["cmd"][0].startswith(str(tricordeur.SDK_BT)), "l'outil du SDK du Mac, jamais celui de son atelier"
    assert "mdp" not in " ".join(vu["cmd"]) and vu["env"]["MDP"] == "mdp", "le mot de passe par l'environnement, jamais en clair"
    assert json.loads((J / "tricordeur-journal.jsonl").read_text().splitlines()[-1])["action"] == "signature"
    with pytest.raises(tricordeur.Refus):
        tricordeur.signer("../../etc/x.apk", executer=faux)


def test_livrer_seulement_un_apk_signe_de_sa_cle(J, monkeypatch):
    apk = J / "cwd" / "atelier" / "tricordeur" / "build" / "t-signe.apk"
    apk.write_bytes(b"PK")
    monkeypatch.setattr(tricordeur.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "Signer #1 certificate DN: CN=Tricordeur de Hakim", ""))
    vers = tricordeur.livrer("tricordeur/build/t-signe.apk", "le sismo garde ses secousses")
    dossier = J / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim" / "Tricordeur"
    assert vers.startswith("Documents/Hakim/Tricordeur/") and len(list(dossier.glob("*.apk"))) == 1
    assert "le sismo" in next(dossier.glob("*.txt")).read_text()
    monkeypatch.setattr(tricordeur.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "CN=FoldLab", ""))
    with pytest.raises(tricordeur.Refus):
        tricordeur.livrer("tricordeur/build/t-signe.apk")


def test_ses_documents_jamais_une_cle_privee(J):
    doc = J / "cwd" / "fichiers" / "telephone" / "Z Fold 7"
    (doc / "GitHubKey").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Bl\n")
    for f in (lambda: telephone.sauver("GitHubKey"), lambda: telephone.ecrire("GitHubKey", texte="x")):
        with pytest.raises(telephone.Refus):
            f()
    assert (doc / "GitHubKey").read_text().startswith("-----BEGIN")
