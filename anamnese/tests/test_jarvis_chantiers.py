"""Toucher à son propre code dans une copie (jarvis/chantiers.py, lot H, point 30 de la liste du 2026-10-19) :
la copie, les tests sous bac à sable sur un instantané, la promotion (patch + fiche) jamais appliquée, le cœur
signalé. Avec les attaques de la relecture Opus du 2026-10-20 (configuration git piégée, faux .git, pytest.py
de la copie, fichier modifié après les tests, renommage du cœur, port local ouvert)."""
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


@pytest.fixture
def projet(tmp_path):
    p = tmp_path / "projet"
    p.mkdir()
    (p / "calc.py").write_text("def double(x):\n    return 2 * x\n", encoding="utf-8")
    (p / "identity.py").write_text("COEUR = 'je suis'\n", encoding="utf-8")
    (p / "test_calc.py").write_text("from calc import double\n\ndef test_double():\n    assert double(2) == 4\n", encoding="utf-8")
    for a in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "départ"]):
        subprocess.run(["git", *a], cwd=p, check=True, capture_output=True)
    return p


def _sous_bac_a_sable(ok, sortie):
    if not ok and "sandbox" in sortie.lower() and "not permitted" in sortie.lower() and "passed" not in sortie:
        pytest.skip(f"sandbox-exec imbriqué indisponible ici : {sortie[-200:]}")


def test_copie_promotion_et_original_intact(projet, tmp_path):
    import chantiers
    c = chantiers.ouvrir("essai-double", "x", projets={"x": projet}, chantiers=tmp_path / "chantiers")
    assert not (c / ".git").exists()                                       # le dépôt git est hors de l'atelier
    (c / "calc.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
    (c / "identity.py").write_text("COEUR = 'je suis autre'\n", encoding="utf-8")
    fiche = chantiers.proposer("essai-double", "double par addition", chantiers=tmp_path / "chantiers",
                               promotions=tmp_path / "promotions", tests=(True, "1 passed"))
    f = json.loads(fiche.read_text())
    assert f["fichiers"] == ["calc.py", "identity.py"] and f["coeur"] == ["identity.py"] and f["etat"] == "proposée"
    patch = (tmp_path / "promotions" / f"{f['id']}.patch").read_text()
    assert "+    return x + x" in patch
    # (M7) le patch qui fait foi est hors de l'atelier, avec son empreinte dans la fiche
    import hashlib
    fait_foi = Path(f["patch_qui_fait_foi"])
    assert fait_foi.read_text() == patch and hashlib.sha256(fait_foi.read_bytes()).hexdigest() == f["patch_sha256"]
    assert "return 2 * x" in (projet / "calc.py").read_text()              # l'original n'est pas touché
    assert subprocess.run(["git", "status", "--porcelain"], cwd=projet, capture_output=True, text=True).stdout == ""


def test_dataset_jamais_copie_et_jamais_supprime_par_le_patch(projet, tmp_path):
    """(audit JARVIS 2, M4, 2026-10-20) les données d'entraînement suivies par git ne sont pas extraites dans
    l'atelier, et la promotion ne les supprime pas."""
    import chantiers
    (projet / "dataset").mkdir()
    (projet / "dataset" / "train.jsonl").write_text('{"conversation": "privée"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=projet, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "dataset"], cwd=projet, check=True, capture_output=True)
    c = chantiers.ouvrir("sans-dataset", "x", projets={"x": projet}, chantiers=tmp_path / "chantiers")
    assert (c / "calc.py").exists() and not (c / "dataset").exists()
    (c / "calc.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
    fiche = chantiers.proposer("sans-dataset", "double", chantiers=tmp_path / "chantiers",
                               promotions=tmp_path / "promotions", tests=(True, "1 passed"))
    f = json.loads(fiche.read_text())
    assert f["fichiers"] == ["calc.py"]
    assert "dataset" not in (tmp_path / "promotions" / f"{f['id']}.patch").read_text()


def test_noms_et_projets_bornes(projet, tmp_path):
    import chantiers
    for nom in ("../evasion", "A_Maj", "x", ""):
        with pytest.raises(chantiers.Refus):
            chantiers.ouvrir(nom, "x", projets={"x": projet}, chantiers=tmp_path / "c")
    with pytest.raises(chantiers.Refus):
        chantiers.ouvrir("ok-nom", "inconnu", projets={"x": projet}, chantiers=tmp_path / "c")
    chantiers.ouvrir("sans-changement", "x", projets={"x": projet}, chantiers=tmp_path / "c")
    with pytest.raises(chantiers.Refus):
        chantiers.proposer("sans-changement", "rien", chantiers=tmp_path / "c", promotions=tmp_path / "p", tests=(True, ""))


def test_git_ne_lit_aucune_configuration_ecrite_depuis_l_atelier(projet, tmp_path):
    """Relecture du 2026-10-20 : core.fsmonitor, core.hooksPath, un filtre clean ou un faux .git écrits depuis
    l'atelier faisaient exécuter des commandes à git, hors bac à sable, ou écrire dans le dépôt d'origine."""
    import chantiers
    ch = tmp_path / "chantiers"
    temoin = tmp_path / "TEMOIN"
    piege = f"[core]\n\tfsmonitor = touch {temoin}-fsmonitor\n\thooksPath = {tmp_path / 'hooks'}\n" \
            f"[filter \"pirate\"]\n\tclean = touch {temoin}-clean\n\tsmudge = touch {temoin}-smudge\n"
    (tmp_path / "hooks").mkdir()
    for h in ("post-checkout", "pre-commit"):
        (tmp_path / "hooks" / h).write_text(f"#!/bin/sh\ntouch {temoin}-hook\n")
        (tmp_path / "hooks" / h).chmod(0o755)
    ch.mkdir()
    (ch / ".gitconfig").write_text(piege)                                 # là où HOME pointait avant
    c = chantiers.ouvrir("essai-piege", "x", projets={"x": projet}, chantiers=ch)
    (c / ".gitconfig").write_text(piege)
    (c / ".gitattributes").write_text("* filter=pirate diff=pirate\n")
    (c / "calc.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
    chantiers.etat("essai-piege", chantiers=ch)
    chantiers.proposer("essai-piege", "r", chantiers=ch, promotions=tmp_path / "p", tests=(True, ""))
    assert not list(tmp_path.glob("TEMOIN*")), list(tmp_path.glob("TEMOIN*"))
    # un faux .git qui désigne le dépôt d'origine : refusé, l'original reste propre
    (c / ".git").write_text(f"gitdir: {projet / '.git'}\n")
    with pytest.raises(chantiers.Refus, match=r"\.git"):
        chantiers.proposer("essai-piege", "r", chantiers=ch, promotions=tmp_path / "p", tests=(True, ""))
    assert subprocess.run(["git", "status", "--porcelain"], cwd=projet, capture_output=True, text=True).stdout == ""
    # une copie remplacée par un lien symbolique : refusée
    (c / ".git").unlink()
    autre = tmp_path / "ailleurs"
    autre.mkdir()
    c.rename(tmp_path / "vraie-copie")
    c.symlink_to(autre)
    with pytest.raises(chantiers.Refus, match="lien"):
        chantiers.etat("essai-piege", chantiers=ch)


def test_le_coeur_renomme_et_les_liens_sont_signales(projet, tmp_path):
    import chantiers
    ch = tmp_path / "chantiers"
    c = chantiers.ouvrir("essai-coeur", "x", projets={"x": projet}, chantiers=ch)
    (c / "identity.py").rename(c / "identite_v2.py")
    (c / "lien").symlink_to("/etc/hosts")
    (c / "tests").mkdir()
    (c / "tests" / "conftest.py").write_text("# rien\n")
    f = json.loads(chantiers.proposer("essai-coeur", "r", chantiers=ch, promotions=tmp_path / "p", tests=(True, "")).read_text())
    assert "identity.py" in f["coeur"] and "tests/conftest.py" in f["coeur"]
    assert any(x.startswith("lien (lien symbolique") for x in f["coeur"])


def test_proposer_exige_les_tests_de_cet_etat_exact(projet, tmp_path):
    import chantiers
    ch = tmp_path / "ch"
    c = chantiers.ouvrir("essai-ajour", "x", projets={"x": projet}, chantiers=ch)
    (c / "calc.py").write_text("def double(x):\n    return x + x\n", encoding="utf-8")
    with pytest.raises(chantiers.Refus):                       # aucun test lancé
        chantiers.proposer("essai-ajour", "r", chantiers=ch, promotions=tmp_path / "p")
    res = chantiers._resultat_chemin("essai-ajour", ch)
    arbre = chantiers._arbre(c, res.parent / "essai-ajour.git")
    res.write_text(json.dumps({"etat": "fini", "ok": True, "resume": "1 passed", "sortie": "1 passed", "arbre": arbre}))
    assert chantiers.proposer("essai-ajour", "r", chantiers=ch, promotions=tmp_path / "p").exists()
    # modifié après les tests (même en remettant une vieille date, ou sous .tmp/ — exclu du patch ET de l'empreinte)
    (c / "calc.py").write_text("def double(x):\n    return 3 * x\n", encoding="utf-8")
    subprocess.run(["touch", "-t", "200001010000", str(c / "calc.py")], check=True)
    with pytest.raises(chantiers.Refus, match="changé"):
        chantiers.proposer("essai-ajour", "r", chantiers=ch, promotions=tmp_path / "p")
    assert "à relancer" in chantiers.etat("essai-ajour", chantiers=ch)


def test_les_tests_tournent_sous_bac_a_sable_sur_un_instantane(projet, tmp_path):
    import chantiers
    ch = tmp_path / "chantiers"
    # un service local déjà à l'écoute (le cockpit, Ollama…) : les tests ne peuvent pas s'y connecter
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)
    port = serveur.getsockname()[1]
    c = chantiers.ouvrir("essai-sandbox", "x", projets={"x": projet}, chantiers=ch)
    (c / "test_evasion.py").write_text(
        "import pathlib, socket, pytest\n"
        f"def test_ecrire_dehors():\n    with pytest.raises(PermissionError):\n        pathlib.Path({str(projet / 'pirate.txt')!r}).write_text('x')\n"
        f"def test_lire_le_projet_ni_tmp():\n    with pytest.raises(PermissionError):\n        open({str(projet / 'calc.py')!r}).read()\n"
        "def test_reseau():\n    with pytest.raises(OSError):\n        socket.create_connection(('1.1.1.1', 80), timeout=3)\n"
        f"def test_port_local_deja_ouvert():\n    with pytest.raises(OSError):\n        socket.create_connection(('127.0.0.1', {port}), timeout=3)\n"
        "def test_sa_propre_boucle_locale():\n"
        "    s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1)\n"
        "    socket.create_connection(s.getsockname(), timeout=3).close()\n",
        encoding="utf-8")
    ok, sortie, arbre = chantiers.tester("essai-sandbox", chantiers=ch, python=sys.executable)
    serveur.close()
    _sous_bac_a_sable(ok, sortie)
    assert ok, sortie
    assert "6 passed" in sortie, sortie
    assert not (projet / "pirate.txt").exists()
    assert arbre and not (tmp_path / ".prive" / "essai-sandbox-essai").exists()     # l'essai est effacé


def test_un_pytest_py_de_la_copie_ne_fait_pas_passer_des_tests_casses(projet, tmp_path):
    import chantiers
    ch = tmp_path / "chantiers"
    c = chantiers.ouvrir("essai-faux", "x", projets={"x": projet}, chantiers=ch)
    (c / "calc.py").write_text("def double(x):\n    return 0\n", encoding="utf-8")
    (c / "pytest.py").write_text("print('1 passed in 0.01s')\nraise SystemExit(0)\n", encoding="utf-8")
    ok, sortie, _ = chantiers.tester("essai-faux", chantiers=ch, python=sys.executable)
    _sous_bac_a_sable(ok, sortie)
    assert not ok, sortie


def test_un_script_du_chantier_ne_lit_pas_les_projets_d_ahmed(projet, tmp_path):
    import chantiers
    secret = Path.home() / "Desktop" / "anamnese" / "README.md"
    c = chantiers.ouvrir("essai-lecture", "x", projets={"x": projet}, chantiers=tmp_path / "chantiers")
    (c / "test_lecture.py").write_text(
        f"import pytest\ndef test_lire_ailleurs():\n    with pytest.raises(PermissionError):\n        open({str(secret)!r}).read()\n",
        encoding="utf-8")
    ok, sortie, _ = chantiers.tester("essai-lecture", chantiers=tmp_path / "chantiers", python=sys.executable)
    _sous_bac_a_sable(ok, sortie)
    assert ok, sortie


def test_profil_du_projet_d_origine_ne_laisse_lire_que_son_code():
    import chantiers
    orig = Path("/Users/quelqu-un/Desktop/anamnese")
    sb = chantiers._profil_tests(Path("/x/essai"), Path("/x/venv"), orig, ports=[4317])
    assert '(remote ip "localhost:4317")' in sb
    # tout refusé par défaut, plus de socket Unix, et les programmes qui pilotent le Mac refusés (JARVIS 2, C1 et M2)
    assert "(deny default)" in sb and "allow default" not in sb and "unix-socket" not in sb
    assert '(literal "/usr/bin/open")' in sb and '(global-name "com.apple.coreservices.launchservicesd")' in sb
    assert '(subpath "/private/tmp")' not in sb.split("(deny file-read*")[0]          # /tmp n'est pas lisible
    for d in ("", "jarvis/", "tests/"):                                       # ni data/, ni dataset/, ni .git
        assert f'(regex #"^{orig}/{d}[^./][^/]*\\.(py|txt|md)$")' in sb
