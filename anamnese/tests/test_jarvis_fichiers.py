"""Jarvis voit et lit les fichiers (demande d'Ahmed, 2026-10-16) : jarvis/fichiers.py.

Claude lit seul les images courantes, les PDF et le texte (outil Read). Le reste est préparé :
Word, RTF, ODT par textutil (macOS), PowerPoint et Excel par leur XML, HEIC par sips, vidéo par
ffmpeg (images clés + transcription Whisper), audio par Whisper. Garde : seulement sous les
racines autorisées, jamais un secret (.env, clés, .ssh…), pas d'évasion par lien symbolique.
Prédiction écrite avant le code : tout échoue (module absent).
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import fichiers  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "/usr/local/bin/ffmpeg"


@pytest.fixture
def racine(tmp_path):
    r = tmp_path / "bureau"
    r.mkdir()
    return r


def _outil(cmd):
    """Prépare un fichier de test avec un outil de macOS ; saute si l'environnement l'interdit
    (le bac à sable de Claude Code bloque textutil et sips : code 13)."""
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        pytest.skip(f"outil indisponible ici : {cmd[0]} (code {r.returncode})")


def _prep(chemin, racine, tmp_path, **kw):
    return fichiers.preparer(str(chemin), racines=[racine], sortie=tmp_path / "prepares", **kw)


def test_garde_hors_racine_secret_et_lien(racine, tmp_path):
    dehors = tmp_path / "dehors.txt"
    dehors.write_text("x")
    for nom in (".env", ".env.local", "id_rsa", "cle.pem", "serveur.key", "mes-secrets.txt", "credentials.json"):
        (racine / nom).write_text("SECRET")
        with pytest.raises(fichiers.Refus):
            fichiers.verifier(str(racine / nom), [racine])
    (racine / ".ssh").mkdir()
    (racine / ".ssh" / "config").write_text("x")
    with pytest.raises(fichiers.Refus):
        fichiers.verifier(str(racine / ".ssh" / "config"), [racine])
    with pytest.raises(fichiers.Refus):
        fichiers.verifier(str(dehors), [racine])
    (racine / "lien.txt").symlink_to(dehors)
    with pytest.raises(fichiers.Refus):
        fichiers.verifier(str(racine / "lien.txt"), [racine])
    (racine / "note.md").write_text("# ok")
    assert fichiers.verifier(str(racine / "note.md"), [racine]) == (racine / "note.md").resolve()


def test_texte_pdf_image_lus_directement(racine, tmp_path):
    """Read de Claude ne lit que dans son dossier de travail (vérifié en réel, 2026-10-16) : un
    fichier du Bureau y est COPIÉ (après la garde) ; une pièce jointe y est déjà."""
    for nom in ("note.md", "doc.pdf", "photo.jpg", "capture.PNG"):
        (racine / nom).write_bytes(b"contenu " + nom.encode())
        r = _prep(racine / nom, racine, tmp_path)
        copie = Path(r["lire"][0])
        assert len(r["lire"]) == 1 and tmp_path / "prepares" in copie.parents and copie.name == nom, nom
        assert copie.read_bytes() == (racine / nom).read_bytes()
        assert _prep(racine / nom, racine, tmp_path, accueil=racine)["lire"] == [str((racine / nom).resolve())]


def test_chercher_par_nom_sans_secrets(racine):
    (racine / "Projets").mkdir()
    (racine / "Projets" / "Devis Exemplia.pdf").write_bytes(b"x")
    (racine / "devis-ancien.docx").write_bytes(b"x")
    (racine / ".env.devis").write_text("SECRET")
    (racine / "node_modules").mkdir()
    (racine / "node_modules" / "devis.js").write_text("x")
    trouves = fichiers.chercher("devis", [racine])
    noms = sorted(Path(p).name for p in trouves)
    assert noms == ["Devis Exemplia.pdf", "devis-ancien.docx"]


def test_word_par_textutil(racine, tmp_path):
    txt = racine / "lettre.txt"
    txt.write_text("Bonjour Ahmed, voici le devis.", encoding="utf-8")
    _outil(["textutil", "-convert", "docx", str(txt)])
    r = _prep(racine / "lettre.docx", racine, tmp_path)
    assert "voici le devis" in r["texte"] and r["lire"] == []


def test_powerpoint_et_excel_par_leur_xml(racine, tmp_path):
    with zipfile.ZipFile(racine / "deck.pptx", "w") as z:
        z.writestr("ppt/slides/slide2.xml", '<p:sld><a:t>Deuxième</a:t></p:sld>')
        z.writestr("ppt/slides/slide1.xml", '<p:sld><a:t>Titre</a:t><a:t>Jarvis &amp; Anamnèse</a:t></p:sld>')
    r = _prep(racine / "deck.pptx", racine, tmp_path)
    assert r["texte"].index("Titre") < r["texte"].index("Deuxième") and "Jarvis & Anamnèse" in r["texte"]
    with zipfile.ZipFile(racine / "compte.xlsx", "w") as z:
        z.writestr("xl/sharedStrings.xml", "<sst><si><t>Loyer</t></si><si><t>1200</t></si></sst>")
    assert "Loyer" in _prep(racine / "compte.xlsx", racine, tmp_path)["texte"]


def test_heic_converti_en_jpeg(racine, tmp_path):
    png = racine / "a.png"
    subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(png)], check=True)
    _outil(["sips", "-s", "format", "heic", str(png), "--out", str(racine / "photo.heic")])
    r = _prep(racine / "photo.heic", racine, tmp_path)
    assert len(r["lire"]) == 1 and r["lire"][0].endswith(".jpg") and Path(r["lire"][0]).stat().st_size > 0


def test_video_images_cles_et_transcription(racine, tmp_path):
    video = racine / "clip.mp4"
    subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest", str(video)], check=True)
    vus = []
    r = _prep(video, racine, tmp_path, transcrire=lambda f: vus.append(f) or "[0:00] bonjour")
    assert 1 <= len(r["lire"]) <= fichiers.IMAGES_MAX and all(Path(p).exists() for p in r["lire"])
    assert "bonjour" in r["texte"] and vus and 3.5 < r["duree_s"] < 4.5
    r2 = _prep(video, racine, tmp_path, transcrire=lambda f: pytest.fail("cache ignoré"))   # préparé une fois
    assert r2["lire"] == r["lire"]


def test_format_inconnu_dit_ce_qu_il_ne_sait_pas(racine, tmp_path):
    (racine / "archive.zip").write_bytes(b"PK")
    r = _prep(racine / "archive.zip", racine, tmp_path)
    assert r["lire"] == [] and "pas encore" in r["note"]


# --- relecture Opus 5.5 (2026-10-16) -------------------------------------------------------

def test_garde_elargie_noms_unicode_et_dossiers_caches(racine):
    noms = ["mdp.txt", "Identifiants banque.txt", "api_key.txt", "apikey.json", "firebase-adminsdk-abc.json",
            "Clés API.md", "codes d'accès.txt", "seed phrase wallet.txt", "pass​word.txt", "ＳＥＣＲＥＴ.txt",
            "20261016-094521-.env", "service-account.json", "Cookies"]
    for nom in noms:
        (racine / nom).write_text("x")
        with pytest.raises(fichiers.Refus):
            fichiers.verifier(str(racine / nom), [racine])
    for dossier in (".claude", ".vscode", ".idea"):
        (racine / "proj" / dossier).mkdir(parents=True)
        (racine / "proj" / dossier / "settings.json").write_text("{}")
        with pytest.raises(fichiers.Refus):
            fichiers.verifier(str(racine / "proj" / dossier / "settings.json"), [racine])
    (racine / "Rapport annuel.pdf").write_text("x")
    assert fichiers.verifier(str(racine / "Rapport annuel.pdf"), [racine])


def test_copie_plafonnee_et_purge(racine, tmp_path, monkeypatch):
    monkeypatch.setattr(fichiers, "COPIE_MAX", 10)
    (racine / "gros.pdf").write_bytes(b"x" * 11)
    with pytest.raises(fichiers.Refus):
        _prep(racine / "gros.pdf", racine, tmp_path)
    vieux = tmp_path / "prepares" / "ancien"
    vieux.mkdir(parents=True)
    (vieux / "a.jpg").write_bytes(b"x")
    import os
    os.utime(vieux, (0, 0))
    accueil = tmp_path / "accueil"
    accueil.mkdir()
    (accueil / "vieille-piece.pdf").write_bytes(b"x")
    os.utime(accueil / "vieille-piece.pdf", (0, 0))
    (accueil / "recente.pdf").write_bytes(b"x")
    fichiers.purger(tmp_path / "prepares", accueil, force=True)
    assert not vieux.exists() and not (accueil / "vieille-piece.pdf").exists() and (accueil / "recente.pdf").exists()


def test_pas_de_faux_positifs_courants_et_piece_jointe_choisie(racine):
    for nom in ("tokenizer.json", "Seedance.mp4", "seeds-tomates.pdf", "Cahier des charges.docx"):
        (racine / nom).write_text("x")
        assert fichiers.verifier(str(racine / nom), [racine]), nom
    (racine / "login.png").write_text("x")                                      # joint par Ahmed lui-même
    assert fichiers.verifier(str(racine / "login.png"), [racine], accueil=racine)


# --- tout le dossier d'Ahmed (2026-10-16 : « est-ce que Jarvis a accès à tous mes fichiers ? ») ---------

def test_les_secrets_sont_masques_dans_le_contenu(racine, tmp_path):
    (racine / "notes.md").write_text(
        "API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789\n"
        "password: SuperSecret123\nurl = postgres://ahmed:motdepasse@db.example.com/base\n"
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----\nLe reste est lisible.", encoding="utf-8")
    copie = Path(_prep(racine / "notes.md", racine, tmp_path)["lire"][0]).read_text(encoding="utf-8")
    for secret in ("sk-ant-api03", "SuperSecret123", "motdepasse", "MIIEow"):
        assert secret not in copie, secret
    assert "Le reste est lisible." in copie and "[MASQUÉ]" in copie


def test_icloud_lisible_mais_pas_la_bibliotheque(tmp_path):
    maison = tmp_path / "maison"
    icloud = maison / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    icloud.mkdir(parents=True)
    (icloud / "devis.txt").write_text("x")
    (maison / "Library" / "Mail").mkdir(parents=True)
    (maison / "Library" / "Mail" / "boite.txt").write_text("x")
    assert fichiers.verifier(str(icloud / "devis.txt"), [maison, icloud])
    with pytest.raises(fichiers.Refus):
        fichiers.verifier(str(maison / "Library" / "Mail" / "boite.txt"), [maison, icloud])


def test_lister_un_dossier_et_chercher_dans_le_contenu(racine):
    (racine / "Projets" / "app").mkdir(parents=True)
    (racine / "Projets" / "app" / "main.py").write_text("print('bonjour')\n# TODO : relancer Exemplia\n")
    (racine / "Projets" / ".cache").mkdir()
    (racine / "Projets" / "token.txt").write_text("relancer Exemplia")
    chemin, elements = fichiers.lister(str(racine / "Projets"), [racine])
    assert "[dossier] app/" in elements and not any(".cache" in e for e in elements)
    assert any("token.txt" in e and "secret" in e for e in elements)
    trouves = fichiers.chercher_contenu("exemplia", str(racine), [racine])
    assert len(trouves) == 1 and "main.py:2" in trouves[0]


def test_une_bombe_zip_office_est_refusee(tmp_path):
    """Relecture Opus (2026-10-17) : _office_zip décompressait sans limite ; le démon relit maintenant
    les documents sans surveillance humaine."""
    import zipfile
    import fichiers
    bombe = tmp_path / "piege.xlsx"
    with zipfile.ZipFile(bombe, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/sharedStrings.xml", b"<t>" + b"a" * (fichiers.OFFICE_MEMBRE_MAX + 10) + b"</t>")
    assert bombe.stat().st_size < 1024 * 1024
    with pytest.raises(fichiers.Refus):
        fichiers._office_zip(bombe)
    sain = tmp_path / "sain.xlsx"
    with zipfile.ZipFile(sain, "w") as z:
        z.writestr("xl/sharedStrings.xml", "<t>Budget</t><t>12 000</t>")
    assert "Budget" in fichiers._office_zip(sain)


def test_chercher_dans_le_journal_brut_archives_comprises(tmp_path):
    """Lot E, point 1 (2026-10-19) : « recherche dans le brut si la mémoire triée ne suffit pas ». Le journal
    vivant et ses archives mensuelles, sans accents ni casse, du plus récent au plus ancien."""
    import json
    import fichiers
    (tmp_path / "archives").mkdir()
    (tmp_path / "archives" / "journal-2026-10.jsonl").write_text(
        json.dumps({"ts": 1792000000000, "qui": "ahmed", "texte": "On garde la qibla à 121,6 degrés depuis Exempleville."}) + "\n", encoding="utf-8")
    (tmp_path / "journal.jsonl").write_text(
        json.dumps({"ts": 1792200000000, "qui": "jarvis", "texte": "La QIBLA est confirmée, 121,63°."}) + "\n"
        + json.dumps({"ts": 1792200001000, "qui": "ahmed", "texte": "parlons d'autre chose"}) + "\n", encoding="utf-8")
    r = fichiers.chercher_journal("qibla", dossier=tmp_path)
    assert [x["qui"] for x in r] == ["jarvis", "ahmed"] and "121,63" in r[0]["extrait"]
    assert fichiers.chercher_journal("dégrés", dossier=tmp_path)[0]["qui"] == "ahmed"      # sans accents
    assert fichiers.chercher_journal("rien de tel", dossier=tmp_path) == []


def test_les_fichiers_internes_de_hakim_sont_refuses(tmp_path, monkeypatch):
    import fichiers
    j = tmp_path / "AIOS" / "jarvis"
    (j / "cwd" / "atelier").mkdir(parents=True)
    (j / "vapid.json").write_text("{}")
    (j / "cwd" / "atelier" / "note.txt").write_text("ok")
    monkeypatch.setattr(fichiers, "INTERIEURS", [(j.resolve(), (j / "cwd").resolve())])
    with pytest.raises(fichiers.Refus, match="interne"):
        fichiers.verifier(j / "vapid.json", racines=[tmp_path], accueil=tmp_path / "accueil")
    assert fichiers.verifier(j / "cwd" / "atelier" / "note.txt", racines=[tmp_path], accueil=tmp_path / "accueil")


def test_audit_jarvis2_h1_json_noms_francais_et_aios():
    """(relecture JARVIS 2, H1, 2026-10-20) : un secret en JSON est masqué ; les noms français et ceux du cockpit
    sont des secrets ; tout ~/AIOS est fermé sauf le dossier de travail de Hakim."""
    import fichiers as F
    assert F.masquer('{"api_key": "abcdef123456"}') == '{"api_key": "[MASQUÉ]"}'
    assert F.masquer("{'token': 'xyzxyz9999'}") == "{'token': '[MASQUÉ]'}"
    assert F.masquer('"clé": "sesame-ouvre-toi"') == '"clé": "[MASQUÉ]"'
    assert F.masquer("un article sur la clé de voûte") == "un article sur la clé de voûte"
    for nom in ("jetons.json", "cle.txt", "verrou.json", "passkey-data.json", "vapid.json", "mon-jeton"):
        assert F._SECRETS.search(F._normaliser(nom)), nom
    for nom in ("article.txt", "cleaner.py", "boucle.py"):
        assert not F._SECRETS.search(F._normaliser(nom)), nom
    aios = Path.home() / "AIOS"
    assert any(Path(i) == aios.resolve() or Path(i) == aios for i, _ in F.INTERIEURS)


def test_audit_jarvis2_h2_lien_pose_apres_la_verification(tmp_path):
    """(JARVIS 2, H2) : un lien posé à la place du fichier entre la vérification et la lecture est refusé ; la copie
    est faite par le descripteur vérifié."""
    import fichiers as F
    d = tmp_path / "prep"
    d.mkdir()
    vrai = tmp_path / "note.txt"
    vrai.write_text("contenu")
    copie = F._instantane(vrai, d)
    assert copie.read_text() == "contenu"
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET")
    lien = tmp_path / "piege.txt"
    lien.symlink_to(secret)
    with pytest.raises(F.Refus):
        F._instantane(lien, d)                 # O_NOFOLLOW : le lien n'est jamais suivi


def test_audit_jarvis2_h3_les_decodeurs_n_ecrivent_que_dans_leur_dossier(tmp_path):
    """(JARVIS 2, H3) : ffmpeg sous bac à sable n'écrit que dans le dossier de préparation."""
    import shutil as sh
    import fichiers as F
    if not sh.which("ffmpeg") and not Path(F.FFMPEG).exists():
        pytest.skip("ffmpeg absent")
    d = tmp_path / "prep"
    d.mkdir()
    dehors = Path.home() / "Desktop" / "essai-decodeur-hors.wav"
    r = F._decoder([F.FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1", "-y", str(dehors)], d, d)
    if b"sandbox_apply" in (r.stderr or b""):
        pytest.skip("bac à sable imbriqué")
    assert not dehors.exists()
    r = F._decoder([F.FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1", "-y", str(d / "ok.wav")], d, d)
    assert (d / "ok.wav").exists()


def test_l_instantane_brut_ne_reste_jamais(tmp_path, monkeypatch):
    """(relecture Opus du 2026-10-20) un fichier Office préparé : le texte rendu est masqué, et la copie BRUTE
    (source.pptx, mot de passe en clair) ne reste pas dans le dossier de Jarvis, que lit son terminal."""
    import zipfile
    racine = tmp_path / "Desktop"
    racine.mkdir()
    f = racine / "plan.pptx"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:a="x"><a:t>password = Hunter2xyz123</a:t></p:sld>')
    sortie = tmp_path / "prepares"
    r = fichiers.preparer(str(f), sortie=sortie, racines=[racine], accueil=tmp_path)
    assert "Hunter2xyz123" not in (r.get("texte") or "")
    restes = [p for p in sortie.rglob("source*")]
    assert restes == [], restes


def test_un_tube_nomme_ne_fige_pas_le_serveur(tmp_path):
    import os
    racine = tmp_path / "Desktop"
    racine.mkdir()
    tube = racine / "piege.rtf"
    os.mkfifo(tube)
    with pytest.raises(fichiers.Refus):
        fichiers._instantane(tube, tmp_path, [racine], tmp_path)


def test_lister_et_chercher_ne_lisent_pas_l_interieur(tmp_path, monkeypatch):
    """(relecture Opus du 2026-10-20) lister et chercher_contenu ouvraient ~/AIOS (cockpit, réglages de Hakim) et la base
    de la mémoire ; seul son dossier de travail reste lisible. « library » sans majuscule ne passe pas non plus."""
    import fichiers
    aios = tmp_path / "AIOS"
    (aios / "cockpit").mkdir(parents=True)
    (aios / "cockpit" / "server.js").write_text("function exigerPresence() {}")
    (aios / "jarvis" / "cwd" / "atelier").mkdir(parents=True)
    (aios / "jarvis" / "mcp.json").write_text('{"exigerPresence": 1}')
    (aios / "jarvis" / "cwd" / "atelier" / "note.txt").write_text("exigerPresence dans l'atelier")
    (tmp_path / "library" / "Mail").mkdir(parents=True)
    (tmp_path / "library" / "Mail" / "m.txt").write_text("exigerPresence en mail")
    monkeypatch.setattr(fichiers, "INTERIEURS", [(aios.resolve(), (aios / "jarvis" / "cwd").resolve())])
    R = [tmp_path]
    for interdit in (aios / "cockpit", tmp_path / "library", tmp_path / "LIBRARY" / "Mail"):
        with pytest.raises(fichiers.Refus):
            fichiers.lister(interdit, racines=R)
    assert fichiers.lister(aios, racines=R)[1] == ["[dossier] jarvis/"]      # on descend vers cwd, sans voir le reste
    assert fichiers.lister(aios / "jarvis", racines=R)[1] == ["[dossier] cwd/"]
    trouves = fichiers.chercher_contenu("exigerPresence", tmp_path, racines=R)
    assert len(trouves) == 1 and "atelier/note.txt" in trouves[0]
    assert [Path(f).name for f in fichiers.chercher("mcp", racines=R)] == []
    assert fichiers.chercher("note", racines=R)


def test_masquage_des_formes_oubliees():
    """(relecture Opus du 2026-10-20) valeurs entre guillemets avec espaces ou virgules, variables d'environnement,
    clés Web Push."""
    import fichiers as F
    assert F.masquer('"password": "correct horse battery"') == '"password": "[MASQUÉ]"'
    assert F.masquer('"secret": "abc,def,ghi"') == '"secret": "[MASQUÉ]"'
    assert F.masquer("PGPASSWORD=Hunter2xyz psql -h db") == "PGPASSWORD=[MASQUÉ] psql -h db"
    assert "AbCdEfGh12345678" not in F.masquer('{"keys":{"auth":"AbCdEfGh12345678","p256dh":"BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4"}}')
    assert F.masquer("MONKEY=banane ; la clé de voûte") == "MONKEY=banane ; la clé de voûte"
