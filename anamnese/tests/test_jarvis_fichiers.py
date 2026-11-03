"""Jarvis voit et lit les fichiers (demande d'Ahmed, 2026-10-16) : jarvis/fichiers.py.

Claude lit seul les images courantes, les PDF et le texte (outil Read). Le reste est préparé :
Word, RTF, ODT par textutil (macOS), PowerPoint et Excel par leur XML, HEIC par sips, vidéo par
ffmpeg (images clés + transcription Whisper), audio par Whisper. Garde : seulement sous les
racines autorisées, jamais un secret (.env, clés, .ssh…), pas d'évasion par lien symbolique.
Prédiction écrite avant le code : tout échoue (module absent).
"""
import json
import os
import time
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


def test_audio_les_secondes_de_chaque_mot_pour_son_creer(racine, tmp_path):
    """(31/10, 01:52, Hakim : « je coupe à l'aveugle avec son_creer ») un audio rend aussi ses passages et ses mots, avec
    leurs secondes, dans un fichier qu'il peut lire ; un audio préparé avant (sans les secondes) est repréparé une fois."""
    son = racine / "disquette.wav"
    subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(son)], check=True)
    seg = {"texte": "trop de disquettes", "segments": [{"debut": 12.4, "fin": 14.02, "texte": "Trop de disquettes,",
           "mots": [["Trop", 12.4, 12.7], ["de", 12.71, 12.89], ["disquettes,", 12.9, 13.79]]}]}
    d = fichiers._dossier_cache(son.resolve(), tmp_path / "prepares")
    (d / "preparation.json").write_text(json.dumps({"fichier": str(son), "lire": [], "texte": "trop de disquettes", "note": "audio"}))
    r = _prep(son, racine, tmp_path, transcrire=lambda f: seg)
    assert r["texte"] == "trop de disquettes" and r["temps"] in r["lire"]
    lu = Path(r["temps"]).read_text(encoding="utf-8")
    assert "0:12.40 → 0:14.02  [12.40 → 14.02]  Trop de disquettes," in lu
    assert "disquettes, 12.90-13.79" in lu and "son_creer" in r["note"]
    assert _prep(son, racine, tmp_path, transcrire=lambda f: pytest.fail("cache ignoré"))["temps"] == r["temps"]
    sans = racine / "sans.wav"                         # un transcripteur sans les secondes : rien ne casse
    subprocess.run([FFMPEG, "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=2", str(sans)], check=True)
    r2 = _prep(sans, racine, tmp_path, transcrire=lambda f: "bonjour")
    assert r2["texte"] == "bonjour" and r2["temps"] == "" and r2["lire"] == []


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


# ---- audit de sécurité du 2026-10-23 (corrigé avec l'accord d'Ahmed) ----

def _pdf(texte):
    """Un PDF minimal d'une page avec ce texte (ASCII)."""
    flux = f"BT /F1 12 Tf 20 100 Td ({texte}) Tj ET".encode()
    objets = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
              b"<< /Length " + str(len(flux)).encode() + b" >>\nstream\n" + flux + b"\nendstream",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, pos = b"%PDF-1.4\n", []
    for i, o in enumerate(objets, 1):
        pos.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{p:010d} 00000 n \n".encode() for p in pos)
    return out + f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def test_un_pdf_avec_un_secret_n_est_lu_qu_en_texte_masque(racine, tmp_path):
    """(audit du 2026-10-23, moyen 5) le PDF n'était jamais masqué."""
    (racine / "acces.pdf").write_bytes(_pdf("ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789 fin"))
    if not fichiers._pdf_texte(racine / "acces.pdf", tmp_path):
        pytest.skip("pdftotext indisponible ici")
    r = _prep(racine / "acces.pdf", racine, tmp_path)
    lu = Path(r["lire"][0])
    assert lu.name == "acces.pdf.texte-masque.txt" and "secrets" in r["note"]
    assert "sk-ant-api03" not in lu.read_text(encoding="utf-8") and "fin" in lu.read_text(encoding="utf-8")
    assert not list((tmp_path / "prepares").rglob("acces.pdf")), "le PDF brut ne reste pas dans le dossier de Hakim"
    assert _prep(racine / "acces.pdf", racine, tmp_path)["lire"] == r["lire"]          # la deuxième fois aussi
    (racine / "article.pdf").write_bytes(_pdf("Un article sans rien de secret."))
    assert Path(_prep(racine / "article.pdf", racine, tmp_path)["lire"][0]).name == "article.pdf"   # lu tel quel


def test_masquage_audit_2026_10_23():
    """(moyen 5) jetons Google et npm, clé secrète AWS sans libellé, mot de passe court sans chiffre."""
    import fichiers as F
    assert "ya29.a0AfH6SMBx" not in F.masquer("Authorization ya29.a0AfH6SMBxQwErTyUiOp_asdfghjkl1234")
    assert "npm_" not in F.masquer("//registry.npmjs.org/:_authToken=npm_abcdefghijklmnopqrstuvwxyz0123456789")
    aws = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert aws not in F.masquer(f"la clé : {aws} et la suite")
    assert F.masquer("pwd: soleilbleu") == "pwd: [MASQUÉ]"
    assert F.masquer("mot de passe = framboise") == "mot de passe = [MASQUÉ]"
    # ce qui n'est pas un secret reste lisible
    sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"
    assert F.masquer(f"commit {sha}") == f"commit {sha}"
    assert F.masquer("les jetons : beaucoup") == "les jetons : beaucoup"
    assert F.masquer("password: court") == "password: court"


def test_le_journal_par_plage_horaire(tmp_path):
    """(24/10, demande d'Ahmed relayée par Hakim) messages, état qui change, hormones qui bougent, événements, dans l'ordre."""
    import json as J
    import fichiers as F
    t0 = 1_800_000_000.0
    (tmp_path / "journal.jsonl").write_text("\n".join(J.dumps(x) for x in [
        {"ts": (t0 + 10) * 1000, "qui": "ahmed", "texte": "N'importe quoi mon frère, password: soleilbleu"},
        {"ts": (t0 + 20) * 1000, "qui": "jarvis", "texte": "Haha, d'accord."},
        {"ts": (t0 + 9000) * 1000, "qui": "ahmed", "texte": "hors plage"}]))
    temps = tmp_path / "t.jsonl"
    temps.write_text("\n".join(J.dumps({"t": t0 + k * 15, "etat": "eveil", "fait": "avec Ahmed", "humeur": "élan" if k < 3 else "surprise",
                                        "valence": 0.7, "arousal": 0.4}) for k in range(6)))
    hormones = tmp_path / "h.jsonl"
    hormones.write_text("\n".join(J.dumps({"t": t0 + 60 * k, "h": {"crh": 0.1 if k < 1 else 0.3, "dopamine": 0.6}, "v": 0.7, "a": 0.4}) for k in range(3)))
    evts = tmp_path / "e.jsonl"
    evts.write_text(J.dumps({"ts": t0 + 15, "nom": "echec", "intensite": 0.6, "source": "parole", "sujet": "profil"}))
    lignes, coupe = F.journal_plage(t0, t0 + 120, dossier=tmp_path, temps=temps, hormones=hormones, evenements=evts)
    texte = [x for _t, x in lignes]
    assert not coupe and len(texte) == 6
    assert all(any(c) for c in zip(*[[("ton état" in x and "élan" in x), ("N'importe quoi mon frère, password: [MASQUÉ]" in x),
                                        ("événement : echec 0.6 (source parole, sujet profil)" in x), ("toi : « Haha" in x)] for x in texte]))
    assert [i for i, x in enumerate(texte) if "N'importe quoi" in x] < [i for i, x in enumerate(texte) if "événement : echec" in x], "dans l'ordre du temps"
    assert any("humeur surprise" in x for x in texte) and any("crh 0.10→0.30" in x for x in texte)
    assert not any("hors plage" in x for x in texte)
    with pytest.raises(ValueError):
        F.journal_plage(t0, t0 + 7 * 3600, dossier=tmp_path)


def test_messages_entiers_sur_une_plage_courte_et_export_brut(tmp_path):
    """(26/10, Ahmed : réponses longues tronquées ; export pour les agents de contrôle) une plage de 30 min rend les messages
    entiers, une plage plus longue leur début (sauf entier=True) ; l'export écrit les messages entiers, positions masquées."""
    import json
    import fichiers as F
    t0 = 1_800_000_000.0
    long = "Point par point : " + "Einstein, Musk, la libraire. " * 40
    (tmp_path / "journal.jsonl").write_text("\n".join(json.dumps(o) for o in [
        {"ts": (t0 - 7200) * 1000, "qui": "ahmed", "texte": "avant, très avant"},
        {"ts": t0 * 1000, "qui": "ahmed", "texte": "je suis à 46.20441, 6.14321 frérot"},
        {"ts": (t0 + 60) * 1000, "qui": "jarvis", "texte": long}]) + "\n")
    vide = tmp_path / "vide.jsonl"
    court, _ = F.journal_plage(t0 - 60, t0 + 600, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide)
    assert long.strip() in court[-1][1] and "…" not in court[-1][1]
    assert "[POSITION MASQUÉE]" in court[0][1] and "46.20441" not in court[0][1]
    large, _ = F.journal_plage(t0 - 3600, t0 + 600, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide)
    assert large[-1][1].endswith("… »")
    entier, _ = F.journal_plage(t0 - 3600, t0 + 600, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide, entier=True)
    assert long.strip() in entier[-1][1]
    r = F.exporter_journal(debut=t0 - 10, fin=t0 + 100, dossier=tmp_path, sortie=tmp_path / "x.txt")
    texte = (tmp_path / "x.txt").read_text()
    assert r["messages"] == 2 and long.strip() in texte and "46.20441" not in texte
    r2 = F.exporter_journal(avant=t0 + 30, jetons=10, dossier=tmp_path, sortie=tmp_path / "y.txt")
    assert r2["messages"] == 1 and "46.20441" not in (tmp_path / "y.txt").read_text()     # le seul message qui tient


# ---------- (27/10, relecture du dépôt public par un Claude neuf ; Ahmed : « boucher toutes les failles ») son terminal
# écrit dans son atelier, il peut y poser des liens : rien ne doit lire ni écrire À TRAVERS eux
@pytest.fixture
def piege(tmp_path, monkeypatch):
    aios = tmp_path / "AIOS"
    cwd = aios / "jarvis" / "cwd"
    atelier = cwd / "atelier"
    atelier.mkdir(parents=True)
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "config").write_text("PIEGE-7731 dossier caché\n")
    (tmp_path / "Library" / "Mail").mkdir(parents=True)
    (tmp_path / "Library" / "Mail" / "m.txt").write_text("PIEGE-7731 bibliothèque\n")
    (aios / "cockpit").mkdir()
    (aios / "cockpit" / "reglages.json").write_text('{"x": "PIEGE-7731 intérieur"}\n')
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "credentials.md").write_text("PIEGE-7731 nom de secret\n")
    (tmp_path / "Documents" / "note.md").write_text("PIEGE-7731 note ouverte\n")
    (atelier / "propre.txt").write_text("PIEGE-7731 atelier\n")
    monkeypatch.setattr(fichiers, "INTERIEURS", [(aios.resolve(), cwd.resolve())])
    monkeypatch.setattr(fichiers, "ECRITS_PAR_HAKIM", [cwd.resolve()], raising=False)
    return tmp_path, atelier


def _lignes(trouves):
    return sorted(t.split(": ", 1)[1] for t in trouves)


def test_chercher_dans_fichiers_ne_suit_pas_un_lien_vers_ce_qui_est_ferme(piege):
    racine, atelier = piege
    for nom, cible in (("a.txt", ".ssh/config"), ("b.txt", "Library/Mail/m.txt"), ("c.json", "AIOS/cockpit/reglages.json"),
                       ("d.md", "Documents/credentials.md"), ("e.md", "Documents/note.md")):
        (atelier / nom).symlink_to(racine / cible)
    (atelier / "dossier-lie").symlink_to(racine / ".ssh")
    # un lien vers un fichier ouvert reste lisible (comme le fichier lui-même) ; rien de ce qui est fermé
    assert _lignes(fichiers.chercher_contenu("PIEGE-7731", atelier, racines=[racine])) == ["PIEGE-7731 atelier", "PIEGE-7731 note ouverte"]
    with pytest.raises(fichiers.Refus):
        fichiers.chercher_contenu("PIEGE-7731", atelier / "dossier-lie", racines=[racine])


def test_un_lien_dur_dans_ses_dossiers_est_refuse(piege):
    racine, atelier = piege
    os.link(racine / ".ssh" / "config", atelier / "dur.txt")
    with pytest.raises(fichiers.Refus, match="lien dur"):
        fichiers.verifier(str(atelier / "dur.txt"), [racine])
    assert _lignes(fichiers.chercher_contenu("PIEGE-7731", atelier, racines=[racine])) == ["PIEGE-7731 atelier"]
    # hors des dossiers où il écrit, un fichier à plusieurs liens reste lisible (Ahmed peut en avoir)
    os.link(racine / "Documents" / "note.md", racine / "Documents" / "note-bis.md")
    assert fichiers.verifier(str(racine / "Documents" / "note-bis.md"), [racine])


def test_l_export_du_journal_n_ecrit_jamais_a_travers_un_lien(tmp_path, monkeypatch):
    import json
    t0 = 1_800_000_000.0
    (tmp_path / "journal.jsonl").write_text(json.dumps({"ts": t0 * 1000, "qui": "jarvis", "texte": "echo PIEGE"}) + "\n")
    atelier, dehors = tmp_path / "atelier", tmp_path / "dehors"
    atelier.mkdir()
    dehors.mkdir()
    important = dehors / "important.txt"
    important.write_text("ORIGINAL")
    monkeypatch.setattr(fichiers, "EXPORTS", atelier / "journal-exports")
    n = time.strftime("%Y%m%d-%H%M%S", time.localtime(t0))
    (atelier / "journal-exports").mkdir()
    (atelier / "journal-exports" / f"journal-{n}-{n}.txt").symlink_to(important)        # le nom est prévisible
    with pytest.raises(fichiers.Refus):
        fichiers.exporter_journal(debut=t0 - 10, fin=t0 + 10, dossier=tmp_path)
    assert important.read_text() == "ORIGINAL"
    (atelier / "journal-exports" / f"journal-{n}-{n}.txt").unlink()
    (atelier / "journal-exports").rmdir()
    (atelier / "journal-exports").symlink_to(dehors)                                    # le dossier lui-même
    with pytest.raises(fichiers.Refus):
        fichiers.exporter_journal(debut=t0 - 10, fin=t0 + 10, dossier=tmp_path)
    assert sorted(p.name for p in dehors.iterdir()) == ["important.txt"]
    (atelier / "journal-exports").unlink()
    r = fichiers.exporter_journal(debut=t0 - 10, fin=t0 + 10, dossier=tmp_path)          # sans piège : écrit
    assert "echo PIEGE" in Path(r["fichier"]).read_text()


def test_ecrire_sans_lien_refuse_un_lien_dur(tmp_path):
    base = tmp_path / "atelier"
    base.mkdir()
    dehors = tmp_path / "dehors.txt"
    dehors.write_text("ORIGINAL")
    os.link(dehors, base / "dur.txt")
    with pytest.raises(fichiers.Refus):
        fichiers.ecrire_sans_lien(base / "dur.txt", "écrasé", base)
    assert dehors.read_text() == "ORIGINAL"
    assert fichiers.ecrire_sans_lien(base / "sous" / "neuf.txt", "ok", base).read_text() == "ok"
    assert fichiers.lire_sans_lien(base / "sous" / "neuf.txt", base) == "ok"
    with pytest.raises(fichiers.Refus):
        fichiers.lire_sans_lien(base / "dur.txt", base)


# ---------- (relecture indépendante du 27/10, points C et défauts des aides) la vérification regarde un chemin, puis le
# fichier était rouvert PAR CE CHEMIN : un dossier de l'atelier échangé entre les deux contre un lien faisait lire la cible
def _echanger(dossier, cible):
    dossier.rename(dossier.with_name(dossier.name + "-vrai"))
    dossier.symlink_to(cible)


def test_chercher_contenu_ne_lit_pas_un_dossier_echange_apres_la_verification(piege, monkeypatch):
    racine, atelier = piege
    (atelier / "sous").mkdir()
    (atelier / "sous" / "a.txt").write_text("PIEGE-7731 atelier sous\n")
    (racine / ".ssh" / "a.txt").write_text("PIEGE-7731 échangé\n")
    vrai = fichiers.verifier

    def verifier_puis_echanger(chemin, *a, **k):
        r = vrai(chemin, *a, **k)
        if Path(chemin).name == "a.txt" and not (atelier / "sous").is_symlink():
            _echanger(atelier / "sous", racine / ".ssh")
        return r
    monkeypatch.setattr(fichiers, "verifier", verifier_puis_echanger)
    trouves = fichiers.chercher_contenu("PIEGE-7731", atelier, racines=[racine])
    assert (atelier / "sous").is_symlink()                                    # la course a bien eu lieu
    assert "PIEGE-7731 échangé" not in _lignes(trouves) and "PIEGE-7731 atelier" in _lignes(trouves)


def test_lister_ne_liste_pas_un_dossier_echange_apres_la_verification(piege, monkeypatch):
    racine, atelier = piege
    (atelier / "sous").mkdir()
    (atelier / "sous" / "propre.txt").write_text("x")
    vrai, sous = fichiers._interieur, (atelier / "sous").resolve()

    def interieur_puis_echanger(p):
        r = vrai(p)
        if Path(p) == sous and not (atelier / "sous").is_symlink():
            _echanger(atelier / "sous", racine / ".ssh")
        return r
    monkeypatch.setattr(fichiers, "_interieur", interieur_puis_echanger)
    try:
        _, elements = fichiers.lister(atelier / "sous", racines=[racine])
    except fichiers.Refus:
        elements = []
    assert (atelier / "sous").is_symlink() and not any("config" in e for e in elements)


def test_les_aides_sans_lien_ont_un_plafond_et_rendent_un_refus_pas_une_erreur_brute(tmp_path, monkeypatch):
    base = tmp_path / "atelier"
    base.mkdir()
    (base / "gros.txt").write_bytes(b"x" * 100)
    with pytest.raises(fichiers.Refus, match="trop"):
        fichiers.lire_sans_lien(base / "gros.txt", base, maximum=50)
    assert fichiers.lire_sans_lien(base / "gros.txt", base, maximum=100) == "x" * 100
    # un dossier retiré par une tâche de fond entre sa création et son ouverture : un refus (recettes, export…)
    monkeypatch.setattr(fichiers.os, "mkdir", lambda *a, **k: None)
    with pytest.raises(fichiers.Refus):
        fichiers.ecrire_sans_lien(base / "neuf" / "x.txt", "x", base)
    with pytest.raises(fichiers.Refus):
        fichiers.creer_dossier_sans_lien(base / "neuf2", base)


def test_plage_coupee_le_dit_et_ecrit_le_fichier_complet(tmp_path, monkeypatch):
    """(30/10, Hakim, accord d'Ahmed : « surtout pour le journal ») le 30/10 à 0 h 51, Hakim a cru avoir lu toute la journée
    du 29 alors que le live du matin était coupé. Une plage dont des messages sont coupés le DIT en tête et en fin
    (« N messages tronqués ») et écrit elle-même le fichier complet, dont elle rend le chemin."""
    import json
    import fichiers as F
    monkeypatch.setattr(F, "EXPORTS", tmp_path / "atelier" / "journal-exports")
    (tmp_path / "atelier").mkdir()
    t0 = 1_800_000_000.0
    long = "Le live du matin : " + "l'aiguille partagée des deux sœurs. " * 30
    (tmp_path / "journal.jsonl").write_text("\n".join(json.dumps(o) for o in [
        {"ts": t0 * 1000, "qui": "ahmed", "texte": long},
        {"ts": (t0 + 60) * 1000, "qui": "jarvis", "texte": "court"},
        {"ts": (t0 + 120) * 1000, "qui": "jarvis", "texte": long + " fin du deuxième"}]) + "\n")
    vide = tmp_path / "vide.jsonl"
    o = F.plage_pour_outil(t0 - 3600, t0 + 600, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide)
    tete, fin = o.split("\n")[0], o.rstrip().split("\n")[-1]
    assert "2 messages tronqués" in tete and "2 messages tronqués" in fin
    chemin = Path(next(m for m in fin.split() if m.startswith(str(tmp_path))))
    texte = chemin.read_text()
    assert long.strip() in texte and "fin du deuxième" in texte and chemin.parent == tmp_path / "atelier" / "journal-exports"
    # une plage courte (messages entiers, rien de coupé) : ni avertissement ni fichier
    o2 = F.plage_pour_outil(t0 - 60, t0 + 600, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide)
    assert "tronqué" not in o2 and long.strip() in o2
    # trop de lignes : le dit aussi, et le fichier a tout
    (tmp_path / "journal.jsonl").write_text("\n".join(json.dumps({"ts": (t0 + k) * 1000, "qui": "ahmed", "texte": f"m{k}"})
                                                      for k in range(320)) + "\n")
    o3 = F.plage_pour_outil(t0 - 10, t0 + 400, dossier=tmp_path, temps=vide, hormones=vide, evenements=vide)
    assert "20 lignes non montrées" in o3.split("\n")[0] and "m319" not in o3.split("[")[-2]
    assert "m319" in Path(next(m for m in o3.rstrip().split("\n")[-1].split() if m.startswith(str(tmp_path)))).read_text()


def test_l_outil_du_journal_passe_par_la_plage_qui_le_dit(monkeypatch):
    import mcp_fichiers
    vu = {}
    monkeypatch.setattr(mcp_fichiers.fichiers, "plage_pour_outil", lambda t0, t1, entier=None: vu.setdefault("ok", "⚠ dit"))
    assert mcp_fichiers.chercher_dans_le_journal(debut="2026-10-29 06:00", fin="2026-10-29 12:00") == "⚠ dit"


def test_une_cle_privee_ne_se_lit_pas_meme_sans_nom_de_secret(tmp_path):
    """(30/10, Ahmed : « tu peux la masquer pour eux ») « GitHubKey » dans ses Documents, une vraie clé SSH privée, n'avait
    pas un nom de secret : refusée par son nom, et toute clé privée refusée par son contenu, quel que soit son nom."""
    racine = tmp_path / "Documents"
    racine.mkdir()
    (racine / "GitHubKey").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Bl\n")
    (racine / "GitHubKey.pub").write_text("ssh-ed25519 AAAA ahmed")
    (racine / "notes-du-jour.txt").write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIE\n")
    (racine / "courses.txt").write_text("du pain")
    for nom in ("GitHubKey", "GitHubKey.pub", "notes-du-jour.txt"):
        with pytest.raises(fichiers.Refus):
            fichiers.verifier(racine / nom, racines=[tmp_path], accueil=tmp_path / "accueil")
    assert fichiers.verifier(racine / "courses.txt", racines=[tmp_path], accueil=tmp_path / "accueil")


def test_son_terminal_ne_lit_ni_n_ecrit_une_cle_privee():
    import terminal
    args, _env = terminal.preparer("true", terminal.ATELIER, 9)
    profil = " ".join(str(a) for a in args)
    assert "[Gg]it[Hh]ub[Kk]ey" in profil and "deny file-read* file-write*" in profil
    assert profil.rindex("[Gg]it[Hh]ub[Kk]ey") > profil.rindex("(allow file-write*"), "la dernière règle l'emporte"


def test_chercher_voit_les_fichiers_du_telephone_meme_profonds(tmp_path, monkeypatch):
    """(30/10, 16:01, Hakim : « chercher_fichiers ne parcourt pas fichiers/telephone ; j'ai dit à papa « introuvable », à tort »)
    les fichiers du téléphone (le Tricordeur d'Ahmed y écrit ses scans) sont cherchés depuis leur propre racine."""
    import fichiers
    profond = tmp_path / "maison" / "a" / "b" / "c" / "d" / "e" / "f"
    profond.mkdir(parents=True)
    (profond / "scan3d_20261030_155726_155833_scene.ply").write_text("ply")
    monkeypatch.setattr(fichiers, "RACINES", [tmp_path / "maison"])
    monkeypatch.setattr(fichiers, "RACINES_PROFONDES", [tmp_path / "maison" / "a" / "b"])
    r = fichiers.chercher("scan3d_20261030")
    assert len(r) == 1 and r[0].endswith("_scene.ply"), r


def test_ses_hormones_a_chaque_seconde_et_sa_voix_a_l_heure_dite(tmp_path):
    """(30/10, 16:20, Ahmed via Hakim : « mes hormones notées dans le journal TOUTES LES SECONDES » ; « l'heure à laquelle chaque
    phrase de ma voix est réellement dite ») une plage courte : une ligne par seconde (ce qui a bougé, ou « stables ») ; sa voix
    à l'heure où elle a joué ; ses hormones de la plage écrites seconde par seconde dans un fichier."""
    import fichiers
    t0 = 1_800_000_000
    direct = tmp_path / "hormones-direct.jsonl"
    with open(direct, "w") as h:
        for i in range(10):
            h.write(json.dumps({"t": t0 + i, "h": {"crh": 0.15 + (0.05 if i >= 5 else 0), "dopamine": 0.8}}) + "\n")
    voix = tmp_path / "voix-dite.jsonl"
    voix.write_text(json.dumps({"t_ms": (t0 + 5) * 1000 + 200, "duree_ms": 1800, "texte": "je ne sais pas"}) + "\n")
    lignes, _coupe = fichiers.journal_plage(t0, t0 + 9, dossier=tmp_path, temps=tmp_path / "x", hormones=tmp_path / "x",
                                            evenements=tmp_path / "x", direct=direct, voix=voix)
    texte = "\n".join(x for _t, x in lignes)
    assert texte.count("tes hormones") == 10, texte
    assert "crh 0.15→0.20" in texte and "stables" in texte
    assert "ta voix dit : « je ne sais pas »" in texte
    i_voix, i_crh = texte.index("ta voix dit"), texte.index("crh 0.15→0.20")
    assert i_crh < i_voix, "le saut de 16:11:35 (seconde 5) vient avant sa phrase dite à 5,2 s"
    f = fichiers.exporter_hormones(t0, t0 + 9, direct=direct, sortie=tmp_path / "h.csv")
    assert Path(f).read_text().splitlines()[0].startswith("heure,t,") and len(Path(f).read_text().splitlines()) == 11
