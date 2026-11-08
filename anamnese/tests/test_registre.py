"""Registre avec retour arrière (Phase A, étape 1 — idée centrale de Prime Agent, 2026-10-16).

- Le registre n'enregistre QUE dans un processus où ANAMNESE_REGISTRE désigne une entrée ouverte
  (la passe de nuit le transmet à `claude -p`, qui le transmet au serveur MCP — vérifié par une
  sonde) : le démon et les sessions ne sont jamais mêlés à une nuit.
- Sont notés avant/après : identité (cœur, évolution), compétences, souvenirs créés, rubriques
  créées, mutations de taxonomie.
- annuler() défait en sens inverse, refuse d'écraser ce qui a changé depuis (conflit noté),
  supprime proprement un souvenir créé (facettes, co-activation, cerveau 3D, liens, rubrique),
  et s'enregistre lui-même : une annulation est annulable.
- Les compétences gardent leur historique, registre ouvert ou non.

Prédiction écrite avant le code : tout échoue (module registre absent).
"""

import json

import pytest

import identity
import memory
import migrations
import registre
import rubrics
import taxonomy


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    m.kv_set("self_model", "Je suis Anamnèse, cœur d'origine validé par Ahmed.")
    yield m
    m.db.close()


def _ouvrir(mem, monkeypatch):
    rid = registre.ouvrir(mem.db, "nuit", "passe de test")
    monkeypatch.setenv(registre.ENV, rid)
    return rid


def test_rien_n_est_note_sans_registre_ouvert(mem, monkeypatch):
    monkeypatch.delenv(registre.ENV, raising=False)
    mem.add("semantic", "Fait hors registre", embedding=[0.1] * 8)
    assert registre.entrees(mem.db) == []


def test_note_et_annule_une_passe_complete(mem, monkeypatch):
    rid = _ouvrir(mem, monkeypatch)
    eid = mem.add("semantic", "Fait distillé cette nuit", embedding=[0.1] * 8)
    mem.db.execute("INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (?, 1, 0.5, 1)", (eid,))
    mem.db.commit()
    mem.save_skill("deployer", "Déployer", "v2")
    assert identity.append(mem, "Je contemple lumierex rivagex silencex horizonx.", now=5000.0)[0]
    rubrics.rubric_create(mem.db, "projets/nouveau", now=5000.0)
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)

    e = registre.entrees(mem.db)[0]
    assert e["id"] == rid and e["changements"] >= 5 and e["ferme"]

    rapport = registre.annuler(mem.db, rid)
    assert rapport["conflits"] == [] and rapport["annules"] == rapport["total"]
    assert mem.db.execute("SELECT 1 FROM episodes WHERE id=?", (eid,)).fetchone() is None
    assert mem.db.execute("SELECT 1 FROM coactivation WHERE a_id=? OR b_id=?", (eid, eid)).fetchone() is None
    assert mem.get_skill("deployer") is None
    assert identity.evolution(mem) == []
    assert rubrics.get_rubric_id(mem.db, "projets/nouveau") is None
    assert registre.entrees(mem.db)[0]["annule"] == rid           # l'annulation est enregistrée


def test_annulation_refuse_d_ecraser_un_changement_posterieur(mem, monkeypatch):
    rid = _ouvrir(mem, monkeypatch)
    mem.save_skill("deployer", "Déployer", "v2")
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)
    mem.save_skill("deployer", "Déployer", "v3 écrite par Ahmed après la nuit")
    rapport = registre.annuler(mem.db, rid)
    assert len(rapport["conflits"]) == 1
    assert mem.get_skill("deployer")[2] == "v3 écrite par Ahmed après la nuit"


def test_simulation_n_ecrit_rien(mem, monkeypatch):
    rid = _ouvrir(mem, monkeypatch)
    eid = mem.add("semantic", "Fait à annuler", embedding=[0.1] * 8)
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)
    rapport = registre.annuler(mem.db, rid, simulation=True)
    assert rapport["annules"] == 1
    assert mem.db.execute("SELECT 1 FROM episodes WHERE id=?", (eid,)).fetchone() is not None


def test_une_annulation_est_annulable(mem, monkeypatch):
    rid = _ouvrir(mem, monkeypatch)
    eid = mem.add("semantic", "Fait précieux", embedding=[0.1] * 8)
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)
    annulation = registre.annuler(mem.db, rid)["registre"]
    assert mem.db.execute("SELECT 1 FROM episodes WHERE id=?", (eid,)).fetchone() is None
    registre.annuler(mem.db, annulation)
    row = mem.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()
    assert row is not None and row[0] == "Fait précieux"


def test_mutation_de_taxonomie_annulee(mem, monkeypatch):
    rubrics.rubric_create(mem.db, "projets/a", now=1000.0)
    rubrics.rubric_create(mem.db, "projets/b", now=1000.0)
    eid = mem.add("semantic", "Fait rangé", embedding=[0.1] * 8)
    rubrics.attach_episode(mem.db, eid, "projets/a", 0.8, 1000.0)
    rid = _ouvrir(mem, monkeypatch)
    taxonomy.reclassify(mem.db, eid, "projets/b", now=2000.0)
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)
    registre.annuler(mem.db, rid)
    path = mem.db.execute("SELECT r.path FROM episodes e JOIN rubrics r ON r.id=e.rubric_id WHERE e.id=?",
                          (eid,)).fetchone()[0]
    assert path == "projets/a"


def test_historique_des_competences_toujours_garde(mem, monkeypatch):
    monkeypatch.delenv(registre.ENV, raising=False)
    mem.save_skill("deployer", "Déployer", "v1")
    mem.save_skill("deployer", "Déployer", "v2")
    mem.save_skill("deployer", "Déployer", "v3")
    assert [v["content"] for v in registre.versions_competence(mem.db, "deployer")] == ["v1", "v2"]


# --- relecture indépendante (Opus 5.5, CORRIGER), scénarios prouvés s1 à s10 -----------------

def _nuit(mem, monkeypatch, action):
    rid = _ouvrir(mem, monkeypatch)
    resultat = action()
    monkeypatch.delenv(registre.ENV)
    registre.fermer(mem.db, rid)
    return rid, resultat


def _rubrique_de(mem, eid):
    row = mem.db.execute("SELECT r.path FROM episodes e LEFT JOIN rubrics r ON r.id=e.rubric_id WHERE e.id=?",
                         (eid,)).fetchone()
    return row[0] if row else "(supprimé)"


def test_taxonomie_modifiee_apres_la_nuit_est_un_conflit(mem, monkeypatch):
    for p in ("projets/a", "projets/b", "projets/c"):
        rubrics.rubric_create(mem.db, p, now=1000.0)
    eid = mem.add("semantic", "Fait", embedding=[0.1] * 8)
    rubrics.attach_episode(mem.db, eid, "projets/a", 0.8, 1000.0)
    rid, _ = _nuit(mem, monkeypatch, lambda: taxonomy.reclassify(mem.db, eid, "projets/b", now=2000.0))
    taxonomy.reclassify(mem.db, eid, "projets/c", now=3000.0)          # Ahmed, après la nuit
    r = registre.annuler(mem.db, rid)
    assert len(r["conflits"]) == 1 and _rubrique_de(mem, eid) == "projets/c"


def test_double_annulation_et_entree_ouverte_refusees(mem, monkeypatch):
    rid, _ = _nuit(mem, monkeypatch, lambda: mem.add("semantic", "Fait", embedding=[0.1] * 8))
    registre.annuler(mem.db, rid)
    with pytest.raises(ValueError, match="déjà annulée"):
        registre.annuler(mem.db, rid)
    ouverte = registre.ouvrir(mem.db, "nuit", "jamais fermée")
    with pytest.raises(ValueError, match="ouverte"):
        registre.annuler(mem.db, ouverte)


def test_erreur_imprevue_ne_bloque_pas_le_reste(mem, monkeypatch):
    for p in ("projets/a", "projets/b", "projets/d"):
        rubrics.rubric_create(mem.db, p, now=1000.0)
    ancien = mem.add("semantic", "Fait ancien", embedding=[0.1] * 8)
    rubrics.attach_episode(mem.db, ancien, "projets/a", 0.8, 1000.0)

    def passe():
        cree = mem.add("semantic", "Fait inventé par la nuit", embedding=[0.2] * 8)
        rubrics.attach_episode(mem.db, cree, "projets/b", 0.8, 1500.0)   # hors de la fusion à venir
        taxonomy.reclassify(mem.db, ancien, "projets/b", now=2000.0)
        return cree
    rid, cree = _nuit(mem, monkeypatch, passe)
    taxonomy.merge(mem.db, "projets/a", "projets/d", now=3000.0)        # Ahmed fusionne a dans d
    r = registre.annuler(mem.db, rid)
    assert len(r["conflits"]) == 1                                       # le reclassement : rubrique disparue
    assert _rubrique_de(mem, cree) == "(supprimé)"                       # le reste est bien défait
    assert all(e["ferme"] for e in registre.entrees(mem.db))            # aucune entrée fantôme ouverte


def test_identite_annulee_en_bloc(mem, monkeypatch):
    rid, _ = _nuit(mem, monkeypatch,
                   lambda: identity.append(mem, "Je contemple lumierex rivagex silencex horizonx.", now=5000.0))
    identity.set_core(mem, "Je suis Anamnèse, cœur réécrit par Ahmed après la nuit, plus long.", force=True)
    r = registre.annuler(mem.db, rid)
    assert r["annules"] == 0 and len(r["conflits"]) == r["total"]
    assert mem.kv_get("self_model") == identity.assemble(identity.core(mem), identity.evolution(mem))


def test_nuit_a_plusieurs_passes_annulees_dans_le_desordre(mem, monkeypatch):
    for p in ("projets/a", "projets/b"):
        rubrics.rubric_create(mem.db, p, now=1000.0)

    def passe1():
        eid = mem.add("semantic", "Fait de la passe 1", embedding=[0.1] * 8)
        rubrics.attach_episode(mem.db, eid, "projets/a", 0.8, 1500.0)
        return eid
    p1, eid = _nuit(mem, monkeypatch, passe1)
    p2, _ = _nuit(mem, monkeypatch, lambda: taxonomy.reclassify(mem.db, eid, "projets/b", now=2000.0))
    r1 = registre.annuler(mem.db, p1)                    # le souvenir a été retouché par la passe 2
    assert len(r1["conflits"]) == 1 and _rubrique_de(mem, eid) == "projets/b"
    registre.annuler(mem.db, p2)
    assert _rubrique_de(mem, eid) == "projets/a"


def test_simulation_identique_au_reel_et_sans_trace(mem, monkeypatch):
    def passe():
        rubrics.rubric_create(mem.db, "projets/nouveau", now=5000.0)
        eid = mem.add("semantic", "Fait", embedding=[0.1] * 8)
        rubrics.attach_episode(mem.db, eid, "projets/nouveau", 0.8, 5000.0)
        mem.save_skill("deployer", "Déployer", "v1")
        mem.save_skill("deployer", "Déployer", "v2")
    rid, _ = _nuit(mem, monkeypatch, passe)
    avant = len(registre.entrees(mem.db))
    sim = registre.annuler(mem.db, rid, simulation=True)
    assert len(registre.entrees(mem.db)) == avant and rubrics.get_rubric_id(mem.db, "projets/nouveau")
    reel = registre.annuler(mem.db, rid)
    assert (sim["annules"], len(sim["conflits"])) == (reel["annules"], len(reel["conflits"])) == (reel["total"], 0)


def test_suppression_purge_le_journal_de_taxonomie(mem, monkeypatch):
    for p in ("projets/a", "projets/b"):
        rubrics.rubric_create(mem.db, p, now=1000.0)

    def passe():
        eid = mem.add("semantic", "Fait", embedding=[0.1] * 8)
        rubrics.attach_episode(mem.db, eid, "projets/a", 0.8, 1500.0)
        taxonomy.reclassify(mem.db, eid, "projets/b", now=2000.0)
    rid, _ = _nuit(mem, monkeypatch, passe)
    registre.annuler(mem.db, rid)
    assert taxonomy.undo_last(mem.db) == "(rien à annuler)"


def test_reannulation_restaure_etiquette_et_kind_hint(mem, monkeypatch):
    rid, _ = _nuit(mem, monkeypatch, lambda: rubrics.rubric_create(mem.db, "projets/x", now=5000.0,
                                                                     label="Projet X", kind_hint="semantic"))
    annulation = registre.annuler(mem.db, rid)["registre"]
    registre.annuler(mem.db, annulation)
    assert mem.db.execute("SELECT label, kind_hint FROM rubrics WHERE path='projets/x'").fetchone() == ("Projet X", "semantic")


def test_version_defaite_gardee_dans_l_historique(mem, monkeypatch):
    mem.save_skill("deployer", "Déployer", "v1")
    rid, _ = _nuit(mem, monkeypatch, lambda: mem.save_skill("deployer", "Déployer", "v2 de la nuit"))
    registre.annuler(mem.db, rid)
    assert mem.get_skill("deployer")[2] == "v1"
    assert "v2 de la nuit" in [v["content"] for v in registre.versions_competence(mem.db, "deployer")]


def test_rien_n_est_note_dans_une_entree_fermee(mem, monkeypatch):
    rid, _ = _nuit(mem, monkeypatch, lambda: None)
    monkeypatch.setenv(registre.ENV, rid)                 # processus qui survit à la fermeture
    mem.add("semantic", "Écrit trop tard", embedding=[0.1] * 8)
    assert registre.changements(mem.db, rid) == []


def test_curseur_de_consolidation_restaure(tmp_path):
    import sqlite3
    import consolidate
    db = tmp_path / "c.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
    con.execute("INSERT INTO kv VALUES ('consolidation_curseur', '500.0', 0)")
    con.commit()
    rid = registre.ouvrir(con, "nuit", "passe")
    consolidate.avancer_curseur(800.0, fenetre=(900.0, 950.0), db_path=db, registre_id=rid)
    registre.fermer(con, rid)
    registre.annuler(con, rid)
    assert consolidate.curseur(db_path=db) == 500.0      # la passe annulée sera refaite
    con.close()


def test_provenance_restauree_a_la_reannulation(mem, monkeypatch):
    source = mem.add("episodic", "Souvenir source ancien", embedding=[0.3] * 8)

    def passe():
        fait = mem.add("semantic", "Fait distillé de la nuit", embedding=[0.1] * 8)
        mem.db.execute("INSERT INTO insight_edges (insight_id, source_id) VALUES (?,?)", (fait, source))
        mem.db.commit()
        return fait
    rid, fait = _nuit(mem, monkeypatch, passe)
    annulation = registre.annuler(mem.db, rid)["registre"]
    registre.annuler(mem.db, annulation)
    assert mem.db.execute("SELECT 1 FROM insight_edges WHERE insight_id=? AND source_id=?", (fait, source)).fetchone()


def test_souvenir_source_d_un_fait_posterieur_est_un_conflit(mem, monkeypatch):
    rid, cree = _nuit(mem, monkeypatch, lambda: mem.add("semantic", "Fait de la nuit", embedding=[0.1] * 8))
    plus_tard = mem.add("semantic", "Fait plus récent qui en dépend", embedding=[0.2] * 8)
    mem.db.execute("INSERT INTO insight_edges (insight_id, source_id) VALUES (?,?)", (plus_tard, cree))
    mem.db.commit()
    r = registre.annuler(mem.db, rid)
    assert len(r["conflits"]) == 1 and _rubrique_de(mem, cree) != "(supprimé)"
