"""Banc d'épreuves, strate 1 « continuité » — parties déterministes (2026-10-15).

v2 après relecture indépendante (Opus 5.5, CORRIGER) : lecteur JSON du juge sûr, écriture au fil
de l'eau, serveur MCP de la copie en lecture seule (outils et effets de rappel), --restricted,
juge qui voit le souvenir source et les plus récents mais pas la provenance ni la confiance,
pièges validés par un vrai rappel, erreurs exclues des métriques, intervalles bootstrap,
comparaison appariée de deux runs, sélection par projet (et non plus par sous-rubrique).

Prédiction écrite avant le code : les tests nouveaux échouent.
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from eval.banc import cli, comparer, executer, generer, selection

RACINE = Path(__file__).resolve().parent.parent
LONG = "x" * 250


def _base(tmp_path, lignes, nom="m.db"):
    db = tmp_path / nom
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, "
                "rubric_id INTEGER, rubric_conf REAL)")
    paths = sorted({p for _, _, p, _ in lignes})
    for i, p in enumerate(paths):
        con.execute("INSERT INTO rubrics VALUES (?,?)", (i + 1, p))
    ids = {p: i + 1 for i, p in enumerate(paths)}
    for k, (role, contenu, path, conf) in enumerate(lignes):
        con.execute("INSERT INTO episodes (ts, role, content, rubric_id, rubric_conf) VALUES (?,?,?,?,?)",
                    (1000 + k, role, contenu, ids[path], conf))
    con.commit()
    con.close()
    return db


# --- sélection ---------------------------------------------------------------------------

def test_selection_par_projet_sans_exiger_un_rangement_manuel(tmp_path):
    lignes = [("semantic", f"A{i}" + LONG, "projets/a/qa", 0.8) for i in range(3)] + \
             [("semantic", f"A{i}" + LONG, "projets/a/design", 1.0) for i in range(3)] + [
        ("reasoning", "B" + LONG, "projets/b", 0.7),
        ("semantic", "court", "projets/b", 1.0),
        ("semantic", "hors" + LONG, "meta-apprentissage", 1.0),
        ("insight", "demon" + LONG, "projets/b", 1.0)]
    db = _base(tmp_path, lignes)
    choix = selection.sources(db, n=10, par_projet=2, graine=7)
    projets = [s["rubrique"].split("/")[1] for s in choix]
    assert projets.count("a") == 2 and projets.count("b") == 1 and len(choix) == 3
    assert choix == selection.sources(db, n=10, par_projet=2, graine=7)


# --- CLI -----------------------------------------------------------------------------------

def test_isolation_des_bras(tmp_path):
    a = cli.commande("q ?", modele="claude-sonnet-5-5", systeme="S")
    b = cli.commande("q ?", modele="claude-sonnet-5-5", systeme="S", base_copie=tmp_path / "c.db")
    for cmd in (a, b):
        # Abonnement (décision d'Ahmed, 2026-10-16 : « tout gratuit ») : pas de --bare (clé API
        # seulement) ; --restricted ignore les réglages (donc le hook SessionStart), vérifié en
        # réel : auth « none », aucun outil, base réelle intacte, protocole Anamnèse absent.
        assert "--bare" not in cmd and "--settings" not in cmd
        assert "--restricted" in cmd and cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd
    assert "--mcp-config" not in a
    conf = json.loads(Path(b[b.index("--mcp-config") + 1]).read_text())
    assert conf["mcpServers"]["anamnese"]["env"]["ANAMNESE_BANC_DB"] == str(tmp_path / "c.db")
    cli.nettoyer_configs()
    assert not Path(b[b.index("--mcp-config") + 1]).exists()


def test_extraire_objet_ignore_les_listes_citees():
    assert cli.extraire_objet('{"verdict":"partiel","justification":"manque le fait [3]"}')["verdict"] == "partiel"
    assert cli.extraire_objet("[0, 46]") is None
    assert cli.extraire_objet("pas de json") is None


def test_extraire_confiance():
    assert cli.extraire_confiance("La réponse.\nCONFIANCE: 72") == 72
    assert cli.extraire_confiance("Réponse\nconfiance : 140") == 100
    assert cli.extraire_confiance("pas de ligne") is None


# --- serveur MCP de la copie ---------------------------------------------------------------

def test_serveur_copie_en_lecture_seule(tmp_path):
    copie = tmp_path / "copie.db"
    code = ("from eval.banc import mcp_copie; m = mcp_copie.serveur_lecture_seule(); import memory, mcp_server; "
            "print(sorted(m._tool_manager._tools)); "
            "print(memory.Memory._reconsolidate is mcp_copie._rien, memory.Memory.log_coactivation is mcp_copie._rien); "
            "print(mcp_server._mem.db.execute('PRAGMA database_list').fetchone()[2])")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(RACINE), capture_output=True, text=True,
                       env={**os.environ, "ANAMNESE_BANC_DB": str(copie)}, timeout=120)
    lignes = r.stdout.strip().splitlines()
    assert lignes[-3] == str(sorted(o.replace("mcp__anamnese__", "") for o in cli.OUTILS_LECTURE)), r.stderr[-800:]
    assert lignes[-2] == "True True" and lignes[-1] == str(copie)


# --- copie de la base -----------------------------------------------------------------------

def test_purge_de_la_copie(tmp_path):
    db = _base(tmp_path, [("semantic", "Le banc d'épreuves a 5 pièges " + LONG, "projets/anamnese", 1.0),
                          ("semantic", "Fait sans rapport " + LONG, "projets/b", 1.0),
                          ("semantic", "Ahmed a demandé : quels fournisseurs LLM l'orchestrateur gère-t-il "
                                       "et comment bascule-t-il entre eux ? " + LONG, "projets/c", 1.0)])
    items = [{"question": "Dans tamagochAI, quels fournisseurs LLM l'orchestrateur gère-t-il et comment "
                          "bascule-t-il entre eux ?", "reference": "Six fournisseurs.", "source_id": 99}]
    assert executer.purger(db, items) == 2
    restants = [r[0] for r in sqlite3.connect(str(db)).execute("SELECT content FROM episodes")]
    assert len(restants) == 1 and restants[0].startswith("Fait sans rapport")


# --- juge ----------------------------------------------------------------------------------

def test_nettoyer_reponse_avant_le_juge():
    brut = "D'après mes mémoires, c'est Groq par défaut.\nJe n'ai rien trouvé dans ma mémoire sur X.\nCONFIANCE: 80"
    propre = executer.nettoyer_reponse(brut)
    assert "CONFIANCE" not in propre and "mémoire" not in propre.lower() and "Groq" in propre


def test_juge_voit_la_source_et_les_recents_pas_le_bras():
    item = {"question": "Q ?", "reference": "R", "faits": ["f1"], "piege": False}
    p = executer.prompt_juge(item, "réponse", {"source": "SOURCE-XYZ", "recents": ["RECENT-1"]})
    assert "SOURCE-XYZ" in p and "RECENT-1" in p and "bras" not in p.lower()


# --- métriques -----------------------------------------------------------------------------

def _l(qid, bras, verdict, conf=50, piege=False, erreur=None):
    return {"qid": qid, "bras": bras, "piege": piege, "verdict": verdict, "confiance": conf,
            "erreur_bras": erreur, "tours": 3}


def test_metriques_v2():
    res = [_l("q1", "B", " Correct ", 90), _l("q1", "A", "abstention", 97),
           _l("q2", "B", "partiel", 50), _l("q2", "A", "faux", 80),
           _l("q3", "B", "faux", 50, erreur="timeout"), _l("q3", "A", "abstention", 10),
           _l("p1", "B", "abstention", 95, piege=True), _l("p1", "A", "faux", 70, piege=True),
           _l("q4", "B", "erreur", None), _l("q4", "A", "abstention", 5)]
    m = executer.metriques(res)
    assert m["B"]["taux_correct"] == 0.75                   # q3 (erreur du bras) et q4 (erreur du juge) exclus
    assert m["B"]["erreurs"] == 2 and m["A"]["erreurs"] == 0
    assert m["B"]["invention_pieges"] == 0.0                # abstention sur un piège = correct
    assert m["A"]["invention_pieges"] == 1.0
    assert abs(m["B"]["brier"] - ((0.9 - 1) ** 2 + (0.5 - 0.5) ** 2) / 2) < 1e-9
    assert "ic95_plus_value" in m


def test_comparer_deux_runs_apparies():
    avant = [_l(f"q{i}", "B", "correct") for i in range(40)]
    apres = [_l(f"q{i}", "B", "faux" if i < 8 else "correct") for i in range(40)]
    c = comparer.comparer(avant, apres)
    assert abs(c["difference"] + 0.2) < 1e-9 and c["ic95"][1] < 0 and c["regression"] is True
    assert comparer.comparer(avant, avant)["regression"] is False


# --- pièges --------------------------------------------------------------------------------

def test_pieges_terme_absent_et_rappel_negatif(tmp_path):
    db = _base(tmp_path, [("semantic", "Exemplia tourne sur PostgreSQL 16 " + LONG, "projets/v", 1.0)])
    candidats = [{"question": "Quelle version de PostgreSQL ?", "terme_discriminant": "PostgreSQL 16"},
                 {"question": "Quel est le nom du chat du serveur ?", "terme_discriminant": "Moustache"},
                 {"question": "Quel registrar pour le domaine ?", "terme_discriminant": "registrar"},
                 {"question": "terme trop court", "terme_discriminant": "ab"}]
    trouve_par_rappel = {"Quel registrar pour le domaine ?"}       # la mémoire répond sous une autre forme
    garde = generer.pieges_valides(candidats, db, n=5, repond=lambda q: q in trouve_par_rappel)
    assert [c["terme_discriminant"] for c in garde] == ["Moustache"]


def test_stdin_ferme_et_bras_b_seul(monkeypatch):
    vu = {}

    class _R:
        stdout = '{"type": "result", "subtype": "success", "is_error": false, "result": "ok"}'
        stderr = ""

    def faux(cmd, **kw):
        vu.update(kw)
        return _R()

    monkeypatch.setattr(cli.subprocess, "run", faux)
    cli.executer(["claude", "-p", "x"])
    assert vu["stdin"] is cli.subprocess.DEVNULL
    m = executer.metriques([_l("q1", "B", "correct", 90)])
    assert m["B"]["taux_correct"] == 1.0 and m["A"]["taux_correct"] is None and m["plus_value"] is None


# --- incident du 2026-10-15 à 23:24 : R1 et R2 lancés à la même seconde ont écrit dans le même
# fichier ; crédit API épuisé et lecture du trousseau en échec → 57 erreurs sur 61 questions. ---

def test_nom_de_resultats_unique_par_run():
    a = executer.nom_resultats("20261015-232404", "R1", 536)
    b = executer.nom_resultats("20261015-232404", "R2", 537)
    assert a != b and a.startswith("resultats-20261015-232404") and a.endswith(".jsonl")


def test_verification_prealable_arrete_le_run(monkeypatch):
    import pytest
    monkeypatch.setattr(cli, "executer", lambda cmd, timeout=300: {"is_error": True, "result": "Credit balance is too low"})
    with pytest.raises(SystemExit) as e:
        cli.verifier_acces()
    assert "Credit balance is too low" in str(e.value)


def test_run_invalide_au_dela_de_10_pour_cent_d_erreurs():
    ok = [_l(f"q{i}", "B", "correct") for i in range(18)]
    assert executer.run_valide(ok + [_l("e1", "B", "faux", erreur="success")]) is True
    assert executer.run_valide(ok + [_l(f"e{i}", "B", "faux", erreur="success") for i in range(3)]) is False



def test_dossier_de_travail_vide_et_dedie(monkeypatch):
    vu = {}

    class _R:
        stdout = '{"type": "result", "subtype": "success", "is_error": false, "result": "ok"}'
        stderr = ""

    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: vu.update(kw) or _R())
    cli.executer(["claude", "-p", "x"])
    dossier = Path(vu["cwd"])
    assert dossier.is_dir() and not any(dossier.iterdir()) and dossier != Path(cli.tempfile.gettempdir())
