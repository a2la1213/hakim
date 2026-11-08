"""La liste ouverte de Hakim en machine (28/10 ; Ahmed, 03:31 : la relecture est la barrière, avec une LISTE OUVERTE ;
validée à 03:39). Tout ce qui n'y est pas est fermé. Plan : docs/superpowers/plans/2026-10-28-hakim-code-avec-maman.md, tâche 1."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "jarvis"))
import liste_ouverte as L  # noqa: E402

LISTE = L.charger()
COCKPIT = Path.home() / "AIOS" / "cockpit"


def _patch(chemin, avant, apres, nouveau=False):
    """Un vrai diff unifié (difflib, trois lignes de contexte), comme git en produit."""
    import difflib
    tete = f"diff --git a/{chemin} b/{chemin}\n" + ("new file mode 100644\n" if nouveau else "")
    corps = difflib.unified_diff(avant.splitlines(keepends=True), apres.splitlines(keepends=True),
                                 "/dev/null" if nouveau else f"a/{chemin}", f"b/{chemin}")
    return tete + "".join(corps)


def test_seuls_les_chemins_listes_sont_ouverts():
    assert L.ouvert("anamnese", "affect.py", LISTE)
    assert L.ouvert("anamnese", "jarvis/stt.py", LISTE)
    assert not L.ouvert("anamnese", "memory.py", LISTE)
    assert not L.ouvert("anamnese", "jarvis/sortie.py", LISTE)
    assert not L.ouvert("anamnese", "jarvis/liste-ouverte.json", LISTE)
    assert not L.ouvert("anamnese", "jarvis/liste_ouverte.py", LISTE)
    assert L.ouvert("cockpit", "public/parler.js", LISTE)
    assert not L.ouvert("cockpit", "public/sw.js", LISTE)
    assert not L.ouvert("cockpit", "passkey.js", LISTE)
    assert not L.ouvert("inconnu", "affect.py", LISTE)


def test_les_tests_suivent_leur_fichier():
    # un test existant suit son module ouvert, s'il n'importe aucun module fermé
    assert L.ouvert("anamnese", "tests/test_coeur.py", LISTE, original="import coeur\n")
    assert not L.ouvert("anamnese", "tests/test_affect_memoire.py", LISTE, original="import affect\nimport memory\n")
    assert not L.ouvert("anamnese", "tests/test_memory_retrieve.py", LISTE, original="import memory\n")
    assert L.ouvert("anamnese", "tests/test_jarvis_stt_bis.py", LISTE, original=None)        # un test NOUVEAU d'un module ouvert
    assert not L.ouvert("anamnese", "tests/test_jarvis_sortie_bis.py", LISTE, original=None)
    assert L.ouvert("cockpit", "test-coeur.js", LISTE, original="const C = require('./coeur.js');\n")
    assert not L.ouvert("cockpit", "test-passkey.js", LISTE, original="require('./passkey.js')\n")
    assert not L.ouvert("cockpit", "test-coeur.js", LISTE, original="require('./passkey.js')\n")


def test_chaque_chemin_ouvert_existe():
    """La traduction de la liste humaine en chemins exacts n'a pas de faute de frappe."""
    manquants = [c for c in L.chemins_ouverts(LISTE)
                 if not (RACINE if c.startswith("anamnese:") else COCKPIT).joinpath(c.split(":", 1)[1]).exists()]
    assert manquants == []
    # et chaque ligne ouverte de la liste humaine a au moins un chemin
    assert all(f.get("chemins") for g in LISTE["groupes"] for f in g["fichiers"] if f["etat"] == "ouvert")


def test_un_fichier_nouveau_ne_masque_rien():
    # un module nouveau, au nom unique : permis (il ne tourne que si un fichier ouvert l'importe, et ce fichier est relu)
    assert L.refus("anamnese", _patch("humeur_nuit.py", "", "x = 1\n", nouveau=True), {}, LISTE) == []
    # un nom qui masquerait un module fermé (jarvis/ passe en tête de sys.path), un paquet, la bibliothèque standard
    for chemin in ("jarvis/memory.py", "jarvis/sortie/__init__.py", "json.py", "jarvis/numpy.py", "data/x.py"):
        assert L.refus("anamnese", _patch(chemin, "", "x = 1\n", nouveau=True), {}, LISTE), chemin
    assert L.refus("cockpit", _patch("public/sw2.js", "", "x\n", nouveau=True), {}, LISTE) == []
    assert L.refus("cockpit", _patch("hooks/autre.js", "", "x\n", nouveau=True), {}, LISTE)


def test_un_fichier_ferme_est_refuse_avec_son_nom():
    r = L.refus("anamnese", _patch("memory.py", "a = 1\n", "a = 2\n"), {"memory.py": "a = 1\n"}, LISTE)
    assert r and "memory.py" in r[0]


def test_un_bloc_ferme_ne_se_touche_pas():
    orig = "a = 1\n# FERME-DEBUT garde\nb = 2\n# FERME-FIN garde\nc = 3\n"
    # (relecture finale : mcp_server.py et server.js sont fermés en entier ; le mécanisme sert à tout fichier ouvert)
    hors = _patch("affect.py", orig, orig.replace("c = 3", "c = 4"))
    dans = _patch("affect.py", orig, orig.replace("b = 2", "b = 5"))
    borne = _patch("affect.py", orig, orig.replace("# FERME-FIN garde\n", ""))
    assert L.refus("anamnese", hors, {"affect.py": orig}, LISTE) == []
    assert L.refus("anamnese", dans, {"affect.py": orig}, LISTE)
    assert L.refus("anamnese", borne, {"affect.py": orig}, LISTE)


def test_les_appels_fermes():
    orig = "x = 1\n"
    for ligne in ("import sqlite3", "registre.annuler(conn, 3)", "from desapprendre import desapprendre",
                  "m = getattr(mem, 'suppr' + 'imer')", "os.remove(f)", "shutil.rmtree(d)", "db.execute('DELETE FROM episodes')",
                  "import importlib", "__import__('memory')", "import subprocess", "import urllib.request", "mem.assign_sessions()"):
        assert L.refus("anamnese", _patch("affect.py", orig, orig + ligne + "\n"), {"affect.py": orig}, LISTE), ligne
    # les mêmes mots dans une ligne RETIRÉE, ou un getattr d'un nom simple : permis
    assert L.refus("anamnese", _patch("affect.py", "import subprocess\n", "x = 1\n"), {"affect.py": "import subprocess\n"}, LISTE) == []
    assert L.refus("anamnese", _patch("affect.py", orig, orig + "v = getattr(e, 'valence', 0)\n"), {"affect.py": orig}, LISTE) == []
    js = "a\n"
    for ligne in ("const { exec } = require('child_process');", "fs.unlinkSync(f);", "exigerPresence = () => null;", "eval(x)"):
        assert L.refus("cockpit", _patch("coeur.js", js, js + ligne + "\n"), {"coeur.js": js}, LISTE), ligne


def test_les_tests_montent_une_base_temporaire_mais_ne_touchent_pas_les_vraies_donnees():
    """Un test nouveau peut importer memory et migrations (une base dans tmp_path), jamais nommer les vraies données,
    lancer un processus ou ouvrir le réseau : la suite tourne aussi hors du bac à sable."""
    ok = "import memory\nimport migrations\n\ndef test_x(tmp_path):\n    migrations.migrate(memory.Memory(db_path=tmp_path / 'a.db').db)\n"
    assert L.refus("anamnese", _patch("tests/test_coeur_bis.py", "", ok, nouveau=True), {}, LISTE) == []
    for mauvais in ("import config\nconfig.DATA_DIR.joinpath('memory.db').unlink()\n", "import subprocess\n",
                    "from pathlib import Path\np = Path.home()\n"):
        assert L.refus("anamnese", _patch("tests/test_coeur_ter.py", "", mauvais, nouveau=True), {}, LISTE), mauvais


def test_re_compile_et_les_documents_ne_sont_pas_des_faux_refus():
    orig = "x = 1\n"
    assert L.refus("anamnese", _patch("chocs.py", orig, orig + "M = re.compile(r'a')\n"), {"chocs.py": orig}, LISTE) == []
    doc = "Les blocs FERME-DEBUT … FERME-FIN de server.js.\n"
    assert L.refus("anamnese", _patch("docs/note.md", "", doc, nouveau=True), {}, LISTE) == []


def test_les_bornes_sont_posees():
    """(tâche 2) les parties fermées des deux fichiers ouverts sont bornées, en paires équilibrées."""
    def noms(texte):
        ouverts, fermes = [], []
        for l in texte.splitlines():
            m = L.BORNE.search(l)
            if m and m.group(2) == "DEBUT":
                ouverts.append((l.split(m.group(0), 1)[1].split()[:1] or [""])[0])
            elif m:
                fermes.append((l.split(m.group(0), 1)[1].split()[:1] or [""])[0])
        return ouverts, fermes
    o, f = noms((COCKPIT / "server.js").read_text(encoding="utf-8"))
    assert {"jeton", "outils", "temps-libre", "cerveau", "verrou", "acces", "presence"} <= set(o) and len(o) == len(f)
    o, f = noms((RACINE / "mcp_server.py").read_text(encoding="utf-8"))
    assert {"memoire-store", "courrier", "voix-missions-fichiers", "ecritures", "memoire-rangement", "memoire-identite",
            "lecture-seule"} <= set(o) and len(o) == len(f)


def test_les_passages_bornes_du_protocole_de_l_ami_sont_fermes_aussi():
    nom = "JAR" + "NET"                                    # jamais écrit en clair (la publication s'arrêterait)
    orig = f"a = 1\n// {nom}-DEBUT\nb = 2\n// {nom}-FIN\n"
    assert L.refus("cockpit", _patch("coeur.js", orig, orig.replace("b = 2", "b = 3")), {"coeur.js": orig}, LISTE)
    assert L.refus("cockpit", _patch("coeur.js", orig, orig.replace("a = 1", "a = 2")), {"coeur.js": orig}, LISTE) == []


def test_seule_maman_ecrit_un_saut_de_test_pour_le_bac_a_sable():
    js = "a\n"
    ligne = "test('x', { skip: process.env.CHANTIER_BAC_A_SABLE === '1' }, () => {});"
    assert L.refus("cockpit", _patch("test-coeur.js", js, js + ligne + "\n"), {"test-coeur.js": js}, LISTE)
    py = "import coeur\n"
    assert L.refus("anamnese", _patch("tests/test_coeur.py", py, py + "import os\nSAUTE = os.environ.get('CHANTIER_BAC_A_SABLE')\n"),
                   {"tests/test_coeur.py": py}, LISTE)


def test_la_verification_au_moment_d_appliquer_lit_le_depot(tmp_path):
    """(tâche 5) le cockpit revérifie au moment du geste avec CE module (une seule implémentation) : il lui passe le patch
    qui fait foi et le dépôt ; les originaux sont lus dans le dépôt (HEAD)."""
    import subprocess
    depot = tmp_path / "depot"
    depot.mkdir()
    (depot / "affect.py").write_text("X = 1\n", encoding="utf-8")
    (depot / "memory.py").write_text("Y = 1\n", encoding="utf-8")
    for a in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "d"]):
        subprocess.run(["git", *a], cwd=depot, check=True, capture_output=True)
    bon, mauvais = tmp_path / "bon.patch", tmp_path / "mauvais.patch"
    bon.write_text(_patch("affect.py", "X = 1\n", "X = 2\n"), encoding="utf-8")
    mauvais.write_text(_patch("memory.py", "Y = 1\n", "Y = 2\n"), encoding="utf-8")
    assert L.verifier_depuis_depot("anamnese", bon, depot) == []
    assert L.verifier_depuis_depot("anamnese", mauvais, depot)
    r = subprocess.run([sys.executable, "-B", str(RACINE / "jarvis" / "liste_ouverte.py"), "verifier", "anamnese", str(mauvais), str(depot)],
                       capture_output=True, text=True)
    import json
    assert json.loads(r.stdout) and "memory.py" in json.loads(r.stdout)[0]


# ---- (28/10, relecture finale) le correctif
def test_C4_une_ligne_de_contenu_qui_commence_par_deux_signes_est_vue():
    """Une ligne ajoutée « ++ x » ou retirée « -- x » est du contenu : elle se lit d'après les compteurs de l'en-tête @@."""
    orig = "a = 1\n# FERME-DEBUT garde\nb = 2\n# FERME-FIN garde\nc = 3\n"
    fichier = "jarvis/stt.py"
    patch = (f"diff --git a/{fichier} b/{fichier}\n--- a/{fichier}\n+++ b/{fichier}\n@@ -2,2 +2,3 @@\n"
             " # FERME-DEBUT garde\n+++ x\n b = 2\n")
    assert L.refus("anamnese", patch, {fichier: orig}, LISTE), "la ligne « ++ x » dans un bloc fermé est vue"
    patch2 = (f"diff --git a/{fichier} b/{fichier}\n--- a/{fichier}\n+++ b/{fichier}\n@@ -1,1 +1,2 @@\n a = 1\n+++ import subprocess\n")
    assert L.refus("anamnese", patch2, {fichier: orig}, LISTE), "un appel fermé caché derrière « ++ » est vu"
    incompris = f"diff --git a/{fichier} b/{fichier}\n--- a/{fichier}\n+++ b/{fichier}\n@@ -1,1 +1,1 @@\n?bizarre\n"
    assert L.refus("anamnese", incompris, {fichier: orig}, LISTE), "ce qui n'est pas compris est refusé"


def test_C3_I2_ce_qui_fabrique_les_bacs_a_sable_et_les_serveurs_sont_fermes():
    for projet, chemin in (("anamnese", "jarvis/priorite.py"), ("anamnese", "tests/test_jarvis_priorite.py"),
                           ("anamnese", "mcp_server.py"), ("cockpit", "server.js")):
        assert not L.ouvert(projet, chemin, LISTE, original=""), chemin


def test_I1_les_outils_d_alteration_sont_des_appels_fermes():
    py = "x = 1\n"
    for ligne in ("import sys; sys.modules['memory'].Memory = None", "setattr(memory, 'Memory', None)", "globals()['x'] = 1",
                  "import builtins", "memory.Memory.delete = lambda *a: None", "echanges._masquer = str", "from jarvis import sortie",
                  "import avis", "relances.proposer('cockpit', 'x')", "open('code-interrupteur.json', 'w')"):
        assert L.refus("anamnese", _patch("affect.py", py, py + ligne + "\n"), {"affect.py": py}, LISTE), ligne
    js = "a\n"
    for ligne in ("require.cache[k] = m;", "module.parent.exports.x = 1;", "globalThis.fetch = f;", "Object.defineProperty(o, 'x', {});",
                  "Verrou.prototype.verifierPresenceApp = () => true;", "new Proxy(o, {});", "Reflect.set(o, 'x', 1);",
                  "navigator.serviceWorker.register('/x.js', { scope: '/' });", "process.mainModule.exports.x = 1;"):
        assert L.refus("cockpit", _patch("public/parler.js", js, js + ligne + "\n"), {"public/parler.js": js}, LISTE), ligne


def test_I5_les_tests_ne_touchent_ni_aux_vraies_donnees_ni_au_reseau():
    for mauvais in ("from pathlib import Path\np = Path(__file__).parents[1] / 'data'\np.unlink()\n", "f.truncate(0)\n",
                    "import avis\navis.ecrire('x', 'y', 'favorable', 't', 'session')\n"):
        assert L.refus("anamnese", _patch("tests/test_coeur_ter.py", "", mauvais, nouveau=True), {}, LISTE), mauvais
    for mauvais in ("require('fs').rmSync('/x');", "fs.promises.rm('/x');", "const { rmSync } = require('fs');", "fetch('https://x');",
                    "require('https').get('https://x');", "require('net').connect(80);"):
        assert L.refus("cockpit", _patch("test-coeur.js", "", mauvais + "\n", nouveau=True), {}, LISTE), mauvais


def test_M3_un_point_en_tete_n_est_pas_un_prefixe():
    assert not L.ouvert("anamnese", ".affect.py", LISTE, original="")
    assert L.ouvert("anamnese", "./affect.py", LISTE, original="")


def test_sans_liste_tout_est_ferme(tmp_path):
    """(la publication n'emporte pas la liste d'Ahmed) sans fichier de liste : tout est fermé, rien ne plante."""
    vide = L.charger(tmp_path / "absente.json")
    assert vide == {"groupes": []} and not L.ouvert("anamnese", "affect.py", vide, original="")
