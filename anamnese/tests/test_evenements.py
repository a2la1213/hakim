"""Le journal d'événements en ajout seul (evenements.py, lot E point 7 de la liste du 2026-10-19 ; loi L10
« chaque brique est témoin »). Chaque changement d'identité y laisse un témoin chaîné (empreinte du
précédent) : on peut vérifier que rien n'a été réécrit, et reconstruire l'identité. Précédent : le cœur
d'identité rongé par le chemin du démon (diagnostic du 15/10)."""
import json

import pytest

import evenements
import identity
import memory
import migrations


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


@pytest.fixture
def journal(tmp_path, monkeypatch):
    j = tmp_path / "evenements.jsonl"
    monkeypatch.setattr(evenements, "FICHIER", j)
    return j


def test_chaine_verifiee_et_reecriture_detectee(journal):
    for i in range(3):
        evenements.ajouter("essai", {"i": i}, source="test")
    ok, n, casse = evenements.verifier()
    assert ok and n == 3 and casse is None
    lignes = journal.read_text().splitlines()
    falsifie = json.loads(lignes[1]); falsifie["donnees"]["i"] = 99
    lignes[1] = json.dumps(falsifie)
    journal.write_text("\n".join(lignes) + "\n")
    ok, n, casse = evenements.verifier()
    assert not ok and casse == 2                     # la 2e entrée ne correspond plus à son empreinte


def test_une_ligne_supprimee_casse_la_chaine(journal):
    for i in range(3):
        evenements.ajouter("essai", {"i": i})
    lignes = journal.read_text().splitlines()
    journal.write_text("\n".join([lignes[0], lignes[2]]) + "\n")
    assert evenements.verifier()[0] is False


def test_chaque_changement_d_identite_laisse_un_temoin(mem, journal):
    assert identity.set_core(mem, "Je suis Anamnèse, la mémoire qui dure, et ma voix s'appelle Hakim.")[0]
    assert identity.append(mem, "J'ai appris à me taire quand Ahmed parle.", now=1e9)[0]
    assert not identity.append(mem, "J'ai appris autre chose.", now=1e9 + 60)[0]      # refusée : rien d'écrit
    ev = evenements.lire()
    types = [e["type"] for e in ev]
    assert types.count("identite") == 2 and types[0] == "genese"
    coeur, evo = evenements.reconstruire_identite()
    assert coeur == identity.core(mem) and evo == identity.evolution(mem)
    assert evenements.verifier()[0]


def test_l_identite_divergente_est_signalee(mem, journal):
    identity.set_core(mem, "Je suis Anamnèse, la mémoire qui dure, et ma voix s'appelle Hakim.")
    mem.kv_set("self_core", "Je suis un autre.")                 # écriture qui contourne identity.py
    assert evenements.ecart_identite(mem) is not None


def test_chaque_souvenir_garde_son_auteur(tmp_path, monkeypatch, journal):
    """Lot E, point 17 : la provenance. Le serveur MCP de Hakim porte ANAMNESE_SOURCE=hakim ; une session
    Claude Code n'a rien → « claude-code ». memory_store rend aussi l'#id du souvenir."""
    import rubrics
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    r1 = mcp_server.memory_store("[Hakim, essai, 2026-10-19] La qibla depuis Exempleville est à 121,6°.", kind="semantic")
    monkeypatch.delenv("ANAMNESE_SOURCE")
    r2 = mcp_server.memory_store("[Anamnèse, essai, 2026-10-19] Le journal d'événements est né ce soir.", kind="semantic")
    import re
    id1, id2 = (int(re.search(r"#(\d+)", r).group(1)) for r in (r1, r2))
    assert evenements.auteurs() == {id1: "hakim", id2: "claude-code"}
    assert evenements.verifier()[0]
    mem.db.close()


def test_souvenirs_courts_avec_detail_dans_un_fichier(tmp_path, monkeypatch, journal):
    """Lot E, point 4 (proposé par Hakim) : ses souvenirs restent courts (< 150 mots) ; le détail va dans un
    fichier, que memory_detail rend en entier. Le rappel ne sert que l'extrait."""
    import rubrics
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    monkeypatch.setattr(mcp_server, "DETAILS", tmp_path / "details")
    monkeypatch.setenv("ANAMNESE_COURT_MOTS", "150")
    long = "[Hakim, maths du réel, 2026-10-19] " + " ".join(f"mot{i}" for i in range(400)) + " fin."
    r = mcp_server.memory_store(long, kind="semantic")
    import re
    eid = int(re.search(r"#(\d+)", r).group(1))
    (contenu,) = mem.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()
    ref = re.search(r"memory_detail\('(D-[0-9a-f]+)'\)", contenu).group(1)
    assert len(contenu.split()) < 160 and contenu.startswith("[Hakim, maths du réel")
    assert mcp_server.memory_detail(ref).count("mot399") == 1 and "fin." in mcp_server.memory_detail(ref)
    assert "inconnu" in mcp_server.memory_detail("D-../../etc/passwd")
    court = mcp_server.memory_store("[Hakim, essai, 2026-10-19] Une note brève.", kind="semantic")
    assert "memory_detail" not in mem.db.execute("SELECT content FROM episodes ORDER BY id DESC LIMIT 1").fetchone()[0]
    # relecture du 2026-10-20 : une note RÉVISÉE (mêmes 140 premiers mots, fin différente) n'est pas un doublon ;
    # le même texte entier, si
    revise = long.replace(" fin.", " fin corrigée : le résultat change.")
    assert mcp_server.memory_store(revise, kind="semantic").startswith("Mémorisé #")
    assert "déjà mémorisé" in mcp_server.memory_store(revise, kind="semantic")
    mem.db.close()


def test_ecrivains_concurrents_et_fin_coupee(tmp_path):
    """Relecture Opus du 2026-10-20 : 4 écrivains à 300 événements cassaient la chaîne ; retirer les derniers
    événements passait inaperçu."""
    import multiprocessing as mp
    f = tmp_path / "ev.jsonl"
    ps = [mp.get_context("fork").Process(target=_ecrire_beaucoup, args=(f, 150)) for _ in range(4)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    assert evenements.verifier(f) == (True, 600, None)
    lignes = f.read_text().splitlines()
    f.write_text("\n".join(lignes[:-3]) + "\n")                      # la fin coupée
    ok, n, casse = evenements.verifier(f)
    assert not ok and n == 597 and casse == 598


def _ecrire_beaucoup(f, n):
    for i in range(n):
        evenements.ajouter("memoire", {"id": i}, chemin=f)
