"""L'héritage de Hakim (naissance/cerveau/heritage.py, Ahmed 13/11) : ses savoir-faire passent, jamais la vie privée d'Ahmed.
Liste blanche des rubriques, neutralisation (filtre d'identité, règles privées de la publication), puis une vérification qui
refuse tout reste de nom, de lieu, d'argent, de clé, de santé ou de vie privée ; la vraie base n'est lue qu'en lecture seule ;
l'import exige l'approbation d'Ahmed, scellée par l'empreinte. Les témoins coupent chaque garde et voient passer sa vie."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import faux_profil   # noqa: E402
import heritage      # noqa: E402

CLE = faux_profil.cle_factice()
INTERDITS = ["Ahmed", "Yanis", "Nour", "Bourgville", "XRP", "Zébulon", "Myriam", "Clientix", "Jibou77", "voix_ahmed", "papa",
             CLE[:30], "450 CHF", "médecin", "prière", "mère"]


def faux_embed(texte):
    v = [0.0] * 16
    for mot in str(texte).lower().split():
        v[hash(mot) % 16] += 1.0
    return v


@pytest.fixture
def hakim(tmp_path):
    """Une fausse mémoire de Hakim, et les fichiers privés (dictionnaire, règles de publication) inventés."""
    db = tmp_path / "hakim.db"
    c = sqlite3.connect(str(db))
    c.executescript("""
        CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, importance REAL, embedding TEXT,
                               rubric_id INTEGER);
        CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);
        CREATE TABLE skills (id INTEGER PRIMARY KEY, ts REAL, name TEXT, description TEXT, content TEXT);
        INSERT INTO rubrics VALUES (1, 'projets/anamnese'), (2, 'projets/anamnese/hakim'), (3, 'vie/famille'),
                                   (4, 'projets/clientix-app'), (5, 'meta-apprentissage');
    """)
    c.execute("INSERT INTO skills VALUES (1, 0, 'debounce-ui', 'Champ de recherche réactif', "
              "'Attendre 300 ms après la dernière frappe avant de chercher.')")
    c.execute("INSERT INTO skills VALUES (2, 0, 'devis-client', 'Chiffrer', 'Facturer 450 CHF par jour pour Clientix.')")
    traces = [
        (2, "[Raisonnement, agent Yanis pour Nour, 13/11] PROBLÈME : papa n'entendait plus le son. ÉTAPES : mesurer "
            "voix_ahmed contre le journal ; Ahmed : « je veux que tu cherches partout ». DÉCISION : un témoin naturel."),
        (3, "Sa mère va mieux depuis lundi."),
        (1, "Le live à Bourgville a coupé la voix."),
        (1, "Backtest sur XRP : la fenêtre glissante ne gagne rien."),
        (1, "Le médecin a conseillé du repos."),
        (1, f"La clé du site : {CLE}"),
        (1, "Zébulon et Myriam ont testé l'appli."),
        (4, "Le site du client se déploie sur Vercel."),
        (1, "Comme pour clientix-app, on a mesuré avant de corriger."),
        (5, "Jibou77 a relu le code et trouvé deux failles."),
        (2, "Hakimou a appris à couper net quand on lui parle."),
        (5, "Un prix de 30 € pour l'abonnement."),
        (1, "La prière du soir l'apaise."),
    ]
    for i, (r, t) in enumerate(traces, 1):
        c.execute("INSERT INTO episodes (ts, role, content, importance, embedding, rubric_id) VALUES (?,?,?,?,?,?)",
                  (1_700_000_000 + i, "reasoning", t, 0.6, "[]", r))
    c.execute("INSERT INTO episodes (ts, role, content, importance, embedding, rubric_id) VALUES (0, 'episodic', "
              "'Un souvenir intime qui ne doit jamais partir.', 0.9, '[]', 1)")
    c.commit()
    c.close()
    (tmp_path / "dico.json").write_text(json.dumps({"paires": [["Ahmed", "Zorvan"], ["Hakim", "Kalo"], ["Hakimou", "Kalomou"],
                                                               ["Nour", "Velmi"]], "valeurs": {}}), encoding="utf-8")
    (tmp_path / "neutraliser.pl").write_text("s/Clientix/ExempleClient/g; s/clientix/exempleclient/g;\n"
                                             "s/\\bBourgville\\b/Exempleville/g;\n", encoding="utf-8")
    (tmp_path / "publier.sh").write_text(
        "grep -rl --null -E \"Jibou77|jibou77\" . | xargs -0 -r sed -i '' -e 's/Jibou77/un ami d’Ahmed/g' -e 's/jibou77/un_ami/g'\n"
        "if grep -rli -E \"zébulon|zebulon\" . >/dev/null 2>&1; then echo \"ARRÊT : le prénom d'un proche reste\" >&2; exit 1; fi\n",
        encoding="utf-8")
    sources = {"dictionnaire": tmp_path / "dico.json", "neutraliser": tmp_path / "neutraliser.pl", "publier": tmp_path / "publier.sh"}
    return db, sources


def _export(tmp_path, hakim, nom="export"):
    """(bilan, chemin, texte des ÉLÉMENTS exportés : ce qui partira chez la nouvelle IA)."""
    db, sources = hakim
    bilan, chemin = heritage.exporter(db, tmp_path / nom, sources=sources)
    e = json.loads(chemin.read_text(encoding="utf-8"))
    return bilan, chemin, json.dumps(e["elements"], ensure_ascii=False)


def test_le_savoir_faire_passe_la_vie_privee_jamais(tmp_path, hakim):
    bilan, chemin, texte = _export(tmp_path, hakim)
    assert bilan["candidats"] == 15 and bilan["hors_liste_blanche"] == 2
    assert bilan["gardes"] == 5 and bilan["par_genre"] == {"competence": 1, "raisonnement": 4}
    assert bilan["refuses_total"] == 8
    # « client » : le devis de Clientix, et le live dont la ville a été réécrite en pseudonyme (« Exempleville ») : prudence
    assert bilan["refuses"] == {"argent": 3, "client": 2, "santé": 1, "clé": 1, "nom": 1, "vie privée": 2}
    for x in INTERDITS:
        assert x.lower() not in texte.lower(), x
    assert "souvenir intime" not in chemin.read_text()                       # jamais un souvenir, seulement des traces
    assert "Exempleville" not in texte                                      # le lieu réécrit, puis le live refusé
    e = {"elements": json.loads(texte)}
    trace = next(x["texte"] for x in e["elements"] if "témoin naturel" in x["texte"])
    assert trace.startswith("PROBLÈME : le créateur de Hakim n'entendait plus le son")   # l'en-tête (qui, pour qui) retiré
    assert "voix_createur" in trace and "le créateur de Hakim : «…»" in trace and "cherches" not in trace
    assert any("un ami du créateur de Hakim a relu le code" in x["texte"] for x in e["elements"])
    assert any("Comme pour un projet, on a mesuré" in x["texte"] for x in e["elements"])
    assert any(x["texte"].startswith("Hakim a appris à couper net") for x in e["elements"])
    refus = json.loads((chemin.parent / "heritage-refus.json").read_text())
    assert all(set(r) == {"cle", "raisons"} for r in refus)                 # les refus ne gardent jamais leur texte


def test_la_vraie_base_n_est_lue_qu_en_lecture_seule(tmp_path, hakim):
    db, _ = hakim
    avant = (hashlib.sha256(db.read_bytes()).hexdigest(), db.stat().st_mtime_ns, sorted(p.name for p in db.parent.iterdir()))
    _export(tmp_path, hakim)
    assert (hashlib.sha256(db.read_bytes()).hexdigest(), db.stat().st_mtime_ns) == avant[:2]
    assert not (db.parent / "hakim.db-journal").exists() and not (db.parent / "hakim.db-wal").exists()
    with pytest.raises(sqlite3.OperationalError):                            # mode=ro : une écriture serait refusée
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        c.execute("INSERT INTO skills (ts, name, description, content) VALUES (0, 'x', 'x', 'x')")


def test_la_vraie_base_est_ouverte_en_mode_ro_et_seulement_ainsi(tmp_path, hakim, monkeypatch):
    db, sources = hakim
    vrai = sqlite3.connect
    ouvertures = []
    monkeypatch.setattr(heritage.sqlite3, "connect", lambda cible, *a, **k: ouvertures.append(str(cible)) or vrai(cible, *a, **k))
    heritage.exporter(db, tmp_path / "x", sources=sources)
    sur_la_vraie = [o for o in ouvertures if str(db.resolve()) in o or str(db) in o]
    assert sur_la_vraie == [f"file:{db.resolve()}?mode=ro"]


def test_temoin_sans_verification_sa_vie_passerait(tmp_path, hakim, monkeypatch):
    monkeypatch.setattr(heritage, "verifier", lambda *a, **k: [])
    monkeypatch.setattr(heritage, "marque_client", lambda *a, **k: False)
    bilan, _, texte = _export(tmp_path, hakim)
    assert bilan["gardes"] == 13
    for x in ("Bourgville", "XRP", "médecin", "prière", "450 CHF", CLE[:30]):
        assert x.lower() in texte.lower() or x == "Bourgville", x                 # Bourgville : déjà réécrit par les règles privées
    assert "exempleville" in texte.lower()


def test_temoin_sans_neutralisation_la_verification_refuse_quand_meme(tmp_path, hakim, monkeypatch):
    monkeypatch.setattr(heritage, "neutraliser", lambda t, *a, **k: str(t or ""))
    bilan, _, texte = _export(tmp_path, hakim)
    for x in ("Ahmed", "Yanis", "Jibou77", "Clientix"):
        assert x.lower() not in texte.lower(), x
    assert bilan["gardes"] < 5                                               # la deuxième garde a refusé ce que la première aurait réparé


def test_temoin_sans_liste_blanche_la_famille_passerait(tmp_path, hakim, monkeypatch):
    monkeypatch.setattr(heritage, "dans_liste_blanche", lambda c, liste=None: True)
    monkeypatch.setattr(heritage, "verifier", lambda *a, **k: [])
    _, _, texte = _export(tmp_path, hakim)
    assert "va mieux depuis lundi" in texte


def test_l_import_exige_l_approbation_d_ahmed(tmp_path, hakim):
    _, chemin, _ = _export(tmp_path, hakim)
    with pytest.raises(heritage.NonApprouve):
        heritage.importer(chemin, tmp_path / "ia.db", embed=faux_embed)
    a = heritage.approuver(chemin)
    assert a["par"] == "Ahmed" and len(a["empreinte"]) == 64
    n = heritage.importer(chemin, tmp_path / "ia.db", embed=faux_embed)
    assert n == {"competence": 1, "raisonnement": 4}
    c = sqlite3.connect(str(tmp_path / "ia.db"))
    assert c.execute("SELECT content FROM skills WHERE name='debounce-ui'").fetchone()[0].startswith("(héritée de mon grand frère Hakim")
    assert c.execute("SELECT COUNT(*) FROM episodes WHERE role='reasoning' AND content LIKE '[Héritage de mon grand frère Hakim%'"
                     ).fetchone()[0] == 4
    c.close()


def test_un_export_modifie_apres_l_approbation_est_refuse(tmp_path, hakim):
    _, chemin, _ = _export(tmp_path, hakim)
    heritage.approuver(chemin)
    e = json.loads(chemin.read_text())
    e["elements"][0]["texte"] += " Et le numéro d'Ahmed est le 079 000 00 00."
    chemin.write_text(json.dumps(e, ensure_ascii=False))
    with pytest.raises(heritage.NonApprouve):
        heritage.importer(chemin, tmp_path / "ia.db", embed=faux_embed)


@pytest.mark.parametrize("texte,raison", [
    ("Ravie : Inès a validé.", "nom"), ("Rendez-vous 12, rue de la Gare.", "lieu"), ("Payé 1 200 CHF.", "argent"),
    ("Le token ghp_abcdefghijklmnopqrstuvwxyz0123456789 fuit.", "clé"), ("Sa dépression revient.", "santé"),
    ("Son anniversaire tombe lundi.", "vie privée"),
    # ce que la relecture indépendante du 13/11 a trouvé (valeurs inventées)
    ("projectId prj_aB3dE5fG7hJ9kL1mN3pQ5rS7t, team_9xQ2wE4rT6yU8iO", "clé"), ("ref abcdefghij0123456789 côté base", "clé"),
    ("project ref : qwertyuiopasdfgh1234", "clé"), ("TVA CHE-123.456.789", "clé"), ("IBAN d'exemple CH93 0076 2011 6238 5295 7", "clé"),
    ("clé GEMINI_API_KEY dans ~/Desktop/site/.env.local", "clé"), ("sommeil_debut tôt (le créateur de Hakim à la boxe)", "vie privée"),
    ("sieste du créateur de Hakim, téléphone posé", "vie privée"), ("pendant la discussion tendue du live, ses amis riaient", "vie privée"),
    ("Le live du 10/11 a duré", "vie privée"), ("une réaction partie dans WhatsApp", "vie privée"),
    ("connecté à [prénom]'s buds puis à ULT Field 5", "appareil"), ("transcription_azure ar-DZ et darija chantée", "origine"),
    ("les identifiants transcriptionsPapa et voix_papa_azure", "nom"), ("un identifiant mbb_active_business", "nom"),
    ("MESURÉ (live [heure]-[heure]) : 39 s", "vie privée")])
def test_la_verification_par_genre(texte, raison):
    regles = heritage.Regles(interdits=["MaBelleBoutique"])
    assert raison in heritage.verifier(texte, autres_noms=heritage.initiales(regles), regles=regles)


@pytest.mark.parametrize("brut,propre", [
    ("[Raisonnement, agent X, 13/11, « balise [[son: genou]] muette »] PROBLÈME : la voix.", "PROBLÈME : la voix."),
    ("La lecture naturelle : « mot à mot » reste.", "La lecture naturelle : « mot à mot » reste."),
    ("papa : « je veux que tu cherches partout » ; puis rien.", "le créateur de Hakim : «…» ; puis rien."),
    ("la demande d'Ahmed : « tout » et la suite", "la demande du créateur de Hakim : «…» et la suite"),
    ("le faux « c'est pas un problème » vu", "le faux «…» vu"),
    ("mesuré de 21:45-22:10, validé à 08:50, puis vers 23 h", "mesuré de [heure]-[heure], validé à [heure], puis vers [heure]"),
    ("la voix de papa et azurePapa, voix_papa_azure", "la voix du créateur de Hakim et azureCreateur, voix_createur_azure"),
    ("~/.claude/projects/-Users-admin-AIOS/x.jsonl et /Users/admin/AIOS", "~/.claude/projects/-~-AIOS/x.jsonl et ~/AIOS"),
    # seconde relecture indépendante : les formes d'heures oubliées, les durées et un format d'écran qui doivent rester
    ("avant 22 h et après 22 h 30", "avant [heure] et après [heure]"),
    ("blocs de 6 h, toutes les 3 h, écran 16:10", "blocs de 6 h, toutes les 3 h, écran 16:10"),
    ("mesuré le 03/11, puis du 19-20/10 et (08/11 16:00), suite 10/10", "mesuré en novembre, puis en octobre et (en novembre [heure]), suite 10/10"),
    ("la docstring « on ne bouge pas les poteaux » reste", "la docstring « on ne bouge pas les poteaux » reste")])
def test_la_neutralisation(brut, propre):
    assert heritage.neutraliser(brut, dico_noms=["Ahmed"]) == propre


def test_les_codes_de_projets_des_equipes_d_agents(tmp_path):
    for n in ("dev-tarifs-xyzt", "qa-xyzt", "architecte-xyzt", "statisticien-eval", "expert-mlx-metal", "dev-x-metal"):
        (tmp_path / f"{n}.md").write_text("x")
    assert heritage.codes_des_agents([tmp_path]) == ["xyzt"]


@pytest.mark.parametrize("texte", [
    "La marge thermique du téléphone et le diagnostic de la voix.", "Le plus proche voisin vote, les processus enfants meurent.",
    "La police d'écriture Amiri ; la dette technique baisse.", "Le modèle minishlab/potion-multilingual-128M en 4,7 ms.",
    "Claude et Hakim se parlent ; le cache coûte 1,2 s.", "commit 4eb41a2, suite 1742/1742",
    "Vérifier le LIVE du routage ; scoring live des rubriques.", "embedding de 4eb41a2c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a"])
def test_pas_de_faux_refus_sur_un_texte_technique(texte):
    assert heritage.verifier(texte) == []
