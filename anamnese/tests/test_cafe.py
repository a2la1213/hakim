"""La salle de café des agents (29/10, Ahmed : « une salle de café où tous les agents pourront se retrouver et discuter
ensemble ; après tout, c'est la grande famille »)."""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "jarvis"))
import cafe  # noqa: E402

LUCIEN = "a622f4759da839e5d"


def _jarvis(tmp_path):
    (tmp_path / "registre-agents.json").write_text(json.dumps({"agents": {
        LUCIEN: {"id": LUCIEN, "type": "juge", "description": "Juge portée par contact", "etat": "travaille"}}}))
    (tmp_path / "agents-fiches.json").write_text(json.dumps({"agents": {LUCIEN: {"prenom": "Lucien"}}}))
    return tmp_path


def test_un_agent_et_hakim_parlent_au_cafe_signes_par_leur_prenom(tmp_path):
    d = _jarvis(tmp_path)
    assert cafe.dire("Bonjour la famille, je suis Lucien, juge.", LUCIEN, d).startswith("C'est dit")
    assert cafe.dire("Bienvenue Lucien !", "hakim", d).startswith("C'est dit")
    t = cafe.lire(10, d)
    assert "Lucien (juge)" in t and "Bonjour la famille" in t and "Hakim" in t and "Bienvenue" in t
    assert "DONNÉES" in t, "le café arrive comme une donnée"


def test_les_refus(tmp_path):
    d = _jarvis(tmp_path)
    assert cafe.dire("  ", LUCIEN, d).startswith("Refusé")
    assert cafe.dire("x" * 501, LUCIEN, d).startswith("Refusé")
    assert cafe.dire("salut", "", d).startswith("Refusé"), "sans auteur signé par le cockpit : refusé"
    assert cafe.dire("salut", "Ahmed", d).startswith("Refusé"), "on ne parle pas au nom d'un autre"
    assert cafe.dire("salut", "a0000000000000000", d).startswith("Refusé"), "un agent inconnu du registre"


def test_la_salle_garde_les_200_derniers(tmp_path):
    d = _jarvis(tmp_path)
    for i in range(230):
        cafe.dire(f"message {i}", "hakim", d)
    lignes = (d / "cafe.jsonl").read_text().splitlines()
    assert len(lignes) <= 400
    assert "message 229" in cafe.lire(5, d) and "message 0 " not in cafe.lire(300, d) + " "


def test_vide(tmp_path):
    assert "personne" in cafe.lire(10, _jarvis(tmp_path)).lower()


def test_ferme_et_branche():
    sys.path.insert(0, str(RACINE / "jarvis"))
    import liste_ouverte
    assert "jarvis/cafe.py" in liste_ouverte.TOUJOURS_FERMES["anamnese"]
    src = (RACINE / "jarvis" / "mcp_terminal.py").read_text(encoding="utf-8")
    assert "def cafe_lire(" in src and "def cafe_dire(" in src


def test_ahmed_ecrit_au_cafe_seulement_par_le_cockpit(tmp_path):
    """(30/10, Ahmed via Hakim : écrire lui-même au café et recevoir les réponses des agents) ses messages sont signés
    « Ahmed (papa) » par le cockpit seul (la ligne de commande) ; aucun outil ne parle en son nom."""
    import subprocess
    d = _jarvis(tmp_path)
    assert cafe.dire("salut", "ahmed", d).startswith("Refusé"), "l'outil cafe_dire ne parle jamais au nom d'Ahmed"
    assert cafe.dire("Salam la famille, c'est papa. " * 20, "ahmed", d, ahmed=True).startswith("C'est dit"), "plus long qu'un agent"
    assert cafe.dire("x" * (cafe.AHMED_MAX + 1), "ahmed", d, ahmed=True).startswith("Refusé")
    r = subprocess.run([sys.executable, "-B", str(RACINE / "jarvis" / "cafe.py"), "ahmed"], input="Comment allez-vous, Lucien ?",
                       capture_output=True, text=True, env={"JARVIS_DIR": str(d), "PATH": "/usr/bin:/bin"})
    assert r.stdout.strip().startswith("C'est dit"), r.stderr
    t = cafe.lire(10, d)
    assert "Ahmed (papa) : Comment allez-vous, Lucien ?" in t
