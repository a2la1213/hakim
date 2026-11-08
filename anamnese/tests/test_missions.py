"""Les missions confiées par Hakim à Claude Code : ce que Hakim peut proposer (le cockpit, lui, ne lance rien sans
l'accord d'Ahmed — banc du cockpit, contrôle 42)."""
import json

import pytest

import missions


@pytest.fixture
def maison(tmp_path):
    for d in ("Desktop/projet", "Desktop/.cache", "Desktop/anamnese/jarvis", "AIOS/cockpit/data", "AIOS/jarvis/cwd/calculs", "AIOS/jarvis/journal", "Documents/x"):
        (tmp_path / d).mkdir(parents=True)
    return tmp_path


def test_projets_permis(maison):
    assert missions.projet_permis(maison / "Desktop" / "projet", maison) == (maison / "Desktop" / "projet").resolve()
    assert missions.projet_permis(maison / "AIOS" / "jarvis" / "cwd" / "calculs", maison)
    (maison / "Desktop" / "a,b").mkdir()
    for refuse in ("Desktop", "AIOS", "AIOS/jarvis", "AIOS/jarvis/journal", "Documents/x", "Desktop/.cache", "nexiste/pas",
                   "AIOS/cockpit", "AIOS/cockpit/data", "Desktop/a,b"):
        with pytest.raises(missions.Refus):
            missions.projet_permis(maison / refuse, maison)


def test_lien_symbolique_hors_projets(maison):
    (maison / "Desktop" / "lien").symlink_to(maison / "Documents" / "x")
    with pytest.raises(missions.Refus):
        missions.projet_permis(maison / "Desktop" / "lien", maison)


def test_proposer_et_limites(maison, tmp_path):
    d = tmp_path / "missions"
    m = missions.proposer("Relire le module X", "Lis le module X et dis-moi s'il a des bugs évidents.", maison / "Desktop" / "projet",
                          dossier=d, maison=maison)
    assert m["etat"] == "proposee" and m["ecriture"] is False and m["modele"] == "sonnet"
    assert json.loads((d / f"{m['id']}.json").read_text())["consigne"].startswith("Lis le module X")
    with pytest.raises(missions.Refus):
        missions.proposer("ok", "consigne assez longue pour passer le seuil", maison / "Desktop" / "projet", dossier=d, maison=maison)
    with pytest.raises(missions.Refus):
        missions.proposer("Titre", "Utilise la clé sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123 pour tester.", maison / "Desktop" / "projet",
                          dossier=d, maison=maison)
    with pytest.raises(missions.Refus):
        missions.proposer("Titre", "consigne assez longue pour passer le seuil", maison / "Desktop" / "projet", modele="haiku",
                          dossier=d, maison=maison)
    j = tmp_path / "missions.jsonl"
    ids = [m["id"]]
    for k in range(missions.EN_ATTENTE_MAX - 1):
        ids.append(missions.proposer(f"Mission {k}", "consigne assez longue pour passer le seuil", maison / "Desktop" / "projet",
                                     dossier=d, maison=maison, journal=j)["id"])
    with pytest.raises(missions.Refus):
        missions.proposer("Une de trop", "consigne assez longue pour passer le seuil", maison / "Desktop" / "projet", dossier=d, maison=maison, journal=j)
    # Ahmed tranche (journal du cockpit) : de la place se libère (relecture Opus, A6)
    j.write_text(json.dumps({"id": ids[0], "etat": "proposee"}) + "\n" + json.dumps({"id": ids[0], "etat": "refusee"}) + "\n")
    assert missions.proposer("Après la décision", "consigne assez longue pour passer le seuil", maison / "Desktop" / "projet",
                             dossier=d, maison=maison, journal=j)


def test_etat_suit_le_journal_du_cockpit(maison, tmp_path):
    d, j = tmp_path / "missions", tmp_path / "missions.jsonl"
    m = missions.proposer("Relire le module X", "Lis le module X et dis-moi s'il a des bugs évidents.", maison / "Desktop" / "projet",
                          dossier=d, maison=maison)
    assert "proposee" in missions.etat(j, d)
    j.write_text(json.dumps({"id": m["id"], "etat": "acceptee"}) + "\n" + json.dumps({"id": m["id"], "etat": "finie", "resume": "Deux bugs."}) + "\n")
    e = missions.etat(j, d)
    assert "finie" in e and "Deux bugs." in e


def test_son_propre_code_en_lecture_seule(maison, tmp_path):
    d = tmp_path / "missions"
    m = missions.proposer("Relire son code", "Relis le module jarvis et dis ce qui te semble fragile.", maison / "Desktop" / "anamnese" / "jarvis",
                          dossier=d, maison=maison)
    assert m["ecriture"] is False
    with pytest.raises(missions.Refus):
        missions.proposer("Modifier son code", "Corrige le module jarvis toi-même directement.", maison / "Desktop" / "anamnese" / "jarvis",
                          ecriture=True, dossier=d, maison=maison)


def test_pas_d_ecriture_dans_l_atelier(maison, tmp_path):
    with pytest.raises(missions.Refus):
        missions.proposer("Corriger mes calculs", "Corrige le script de calcul directement dans mon atelier.", maison / "AIOS" / "jarvis" / "cwd" / "calculs",
                          ecriture=True, dossier=tmp_path / "m", maison=maison)


def test_pas_d_ecriture_dans_ce_que_launchd_execute(maison, tmp_path):
    """(audit du cockpit, C-H5) Un dossier lancé par launchd (le script, et les dossiers qu'il nomme) : lecture seule."""
    import plistlib
    for d in ("AIOS/bin", "Desktop/lance/src", "Library/LaunchAgents"):
        (maison / d).mkdir(parents=True)
    (maison / "AIOS/bin/tache.sh").write_text('#!/bin/bash\ncd "$HOME/Desktop/lance" && ./run.sh >> ~/Desktop/.\n')
    (maison / "Library/LaunchAgents/com.essai.plist").write_bytes(plistlib.dumps(
        {"Label": "com.essai", "ProgramArguments": ["/bin/bash", str(maison / "AIOS/bin/tache.sh")]}))
    for refuse in ("AIOS/bin", "Desktop/lance", "Desktop/lance/src"):
        assert "launchd" in (missions.refus_ecriture(maison / refuse, maison) or "")
        with pytest.raises(missions.Refus, match="launchd"):
            missions.proposer("Corriger la tâche", "Corrige le script lancé chaque nuit par le Mac.", maison / refuse,
                              ecriture=True, dossier=tmp_path / "m", maison=maison)
    assert missions.refus_ecriture(maison / "Desktop" / "projet", maison) is None
    assert missions.proposer("Relire la tâche", "Relis le script lancé chaque nuit et dis ce qui cloche.", maison / "Desktop" / "lance",
                             dossier=tmp_path / "m", maison=maison)["ecriture"] is False


def test_launchd_formes_courantes(maison, tmp_path):
    """(relecture Opus du 2026-10-20) bash -c "cd DIR", "$HOME"/x, script sans #!, script appelé par un script ;
    plist illisible : refus par prudence."""
    import plistlib
    for d in ("Desktop/cdc", "Desktop/guille", "Desktop/sansdiese", "Desktop/niveau2", "AIOS/bin", "Library/LaunchAgents"):
        (maison / d).mkdir(parents=True, exist_ok=True)
    a, b = maison / "AIOS/bin/a.sh", maison / "AIOS/bin/b.sh"
    a.write_text(f'cd "$HOME"/Desktop/guille && ./x\n{b}\n'); a.chmod(0o755)
    b.write_text("#!/bin/sh\ncd ~/Desktop/niveau2 && make\n"); b.chmod(0o755)
    (maison / "Desktop/sansdiese/run.sh").write_text("echo pas de diese\n")
    la = maison / "Library/LaunchAgents"
    (la / "a.plist").write_bytes(plistlib.dumps({"Label": "a", "ProgramArguments": ["/bin/bash", "-c", f"cd {maison}/Desktop/cdc && ./x"]}))
    (la / "b.plist").write_bytes(plistlib.dumps({"Label": "b", "ProgramArguments": ["/bin/sh", str(a)]}))
    (la / "c.plist").write_bytes(plistlib.dumps({"Label": "c", "ProgramArguments": ["/bin/sh", str(maison / "Desktop/sansdiese/run.sh")]}))
    for x in ("Desktop/cdc", "Desktop/guille", "Desktop/sansdiese", "Desktop/niveau2"):
        assert "launchd" in (missions.refus_ecriture(maison / x, maison) or ""), x
    assert missions.refus_ecriture(maison / "Desktop" / "projet", maison) is None
    (la / "z.plist").write_text("pas un plist")
    assert "illisible" in (missions.refus_ecriture(maison / "Desktop" / "projet", maison) or "")
