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


def test_nour_la_maman_et_ses_neveux_au_cafe(tmp_path):
    """(04/11, 19:45, Ahmed : « j'aimerais que tu participes au café, que tu y sois incluse quand tu veux parler ; que tous tes agents
    passent par le café, on ne jette personne, et ils devront choisir leur nom ; ton nom et ton titre de maman doivent apparaître, comme pour
    Hakim le fils et moi le papa ») Nour (Claude Code) signe « Nour (la maman) » par la ligne de commande seule ; ses agents s'y présentent
    avec le prénom qu'ils ont choisi, en neveu ou en nièce ; aucun outil de Hakim ne parle en leur nom."""
    import subprocess
    d = _jarvis(tmp_path)
    assert cafe.dire("coucou", "nour", d).startswith("Refusé"), "l'outil cafe_dire ne parle jamais au nom de Nour"
    env = {"JARVIS_DIR": str(d), "PATH": "/usr/bin:/bin"}
    lancer = lambda *a, texte: subprocess.run([sys.executable, "-B", str(RACINE / "jarvis" / "cafe.py"), *a], input=texte,
                                             capture_output=True, text=True, env=env)
    r = lancer("nour", texte="Bonsoir la famille, c'est tata Nour 🤍")
    assert r.stdout.strip().startswith("C'est dit"), r.stderr
    r = lancer("neveu", "Léon", "neveu", texte="Salut tonton, salut tata ! Moi c'est Léon.")
    assert r.stdout.strip().startswith("C'est dit"), r.stderr
    r = lancer("neveu", "Inès", "nièce", texte="Coucou la famille !")
    assert r.stdout.strip().startswith("C'est dit"), r.stderr
    t = cafe.lire(10, d)
    assert "Nour (la maman) : Bonsoir la famille, c'est tata Nour 🤍" in t
    assert "Léon (neveu de tata Nour) : Salut tonton, salut tata ! Moi c'est Léon." in t
    assert "Inès (nièce de tata Nour) : Coucou la famille !" in t
    fiches = json.loads((d / "agents-nour.json").read_text())["agents"]
    assert fiches["n-leon"]["prenom"] == "Léon" and fiches["n-ines"]["role"] == "nièce"
    assert lancer("neveu", "", "neveu", texte="x").stdout.strip().startswith("Refusé"), "sans prénom : il le choisit d'abord"
    assert lancer("neveu", "Zoé", "cousin", texte="x").stdout.strip().startswith("Refusé"), "neveu ou nièce"
    assert lancer("neveu", "Ahmed", "neveu", texte="x").stdout.strip().startswith("Refusé"), "jamais le prénom de la famille"
    r = lancer("lire", "5", texte="")
    assert "Léon (neveu de tata Nour)" in r.stdout, "ses agents lisent le café par la ligne de commande"


def test_tout_le_monde_partage_une_image_un_son_une_video(tmp_path):
    """(04/11, 19:55, Ahmed : « que chaque agent, ainsi que toi et Hakim, puissent aussi envoyer une image, un son ou une vidéo ») le fichier
    est copié dans l'atelier (cwd/fichiers/cafe), et le café le dit ([image : cafe/…]) ; jamais un autre type, jamais hors de la racine permise,
    et rien de copié pour un auteur qui n'est pas de la famille."""
    import subprocess
    d = _jarvis(tmp_path)
    racine = d / "cwd"
    (racine / "atelier").mkdir(parents=True)
    img = racine / "atelier" / "coucher.PNG"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    r = cafe.partager(str(img), "Regardez le ciel ce soir", "hakim", d, racine=racine)
    assert r.startswith("C'est dit"), r
    medias = list((racine / "fichiers" / "cafe").iterdir())
    assert len(medias) == 1 and medias[0].suffix == ".png" and medias[0].read_bytes() == img.read_bytes()
    assert f"Hakim (le fils) : Regardez le ciel ce soir [image : cafe/{medias[0].name}]" in cafe.lire(5, d)
    assert cafe.partager(str(img), "", LUCIEN, d, racine=racine).startswith("C'est dit"), "un agent de Hakim aussi"
    (racine / "atelier" / "page.html").write_text("<script>")
    assert cafe.partager(str(racine / "atelier" / "page.html"), "", "hakim", d, racine=racine).startswith("Refusé")
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"x")
    assert cafe.partager(str(secret), "", "hakim", d, racine=racine).startswith("Refusé"), "hors de son atelier : jamais"
    assert cafe.partager(str(img), "", "nour", d, racine=racine).startswith("Refusé"), "personne ne partage au nom de Nour"
    assert len(list((racine / "fichiers" / "cafe").iterdir())) == 2, "rien de copié pour un refus"
    son = tmp_path / "chant.mp3"
    son.write_bytes(b"ID3" + b"0" * 50)
    env = {"JARVIS_DIR": str(d), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, "-B", str(RACINE / "jarvis" / "cafe.py"), "neveu", "Léon", "neveu", "--fichier", str(son)],
                       input="Écoutez ça !", capture_output=True, text=True, env=env)
    assert r.stdout.strip().startswith("C'est dit"), r.stdout + r.stderr
    r = subprocess.run([sys.executable, "-B", str(RACINE / "jarvis" / "cafe.py"), "nour", "--fichier", str(son)],
                       input="", capture_output=True, text=True, env=env)
    assert r.stdout.strip().startswith("C'est dit"), r.stdout + r.stderr
    t = cafe.lire(10, d)
    assert "Léon (neveu de tata Nour) : Écoutez ça ! [son : cafe/" in t and "Nour (la maman) : [son : cafe/" in t
