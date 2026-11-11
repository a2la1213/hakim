"""(11/11) Une écriture qui échoue sous la contention (« database is locked ») laissait la connexion du démon dans une
transaction ouverte. La lecture suivante y figeait un instantané, puis toutes les écritures échouaient, alors que la base
restait libre pour les autres connexions : plus d'échanges mémorisés du 10/11 23:04 au 11/11 06:20, WAL à 932 Mo.
Ici : la panne reproduite, puis kv_set et la boucle du démon qui la relâchent."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daemon  # noqa: E402
from memory import Memory  # noqa: E402


def _empoisonner(mem, chemin):
    """Un autre écrivain tient le verrou : l'écriture de mem échoue ; mem relit ; l'autre valide, un troisième écrit."""
    autre = sqlite3.connect(str(chemin), timeout=0.2)
    autre.execute("BEGIN IMMEDIATE")
    autre.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('x', '1', 0)")
    mem.db.execute("PRAGMA busy_timeout=200")
    with pytest.raises(sqlite3.OperationalError):
        mem.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('y', '1', 0)")   # écriture brute, sans kv_set
    mem.db.execute("SELECT count(*) FROM kv").fetchone()     # l'instantané se fige dans la transaction restée ouverte
    autre.commit()
    autre.close()
    tiers = sqlite3.connect(str(chemin))
    tiers.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('z', '1', 0)")
    tiers.commit()
    tiers.close()


def test_la_panne_reproduite_puis_relachee_par_la_boucle(tmp_path):
    chemin = tmp_path / "m.db"
    mem = Memory(chemin)
    _empoisonner(mem, chemin)
    assert mem.db.in_transaction
    with pytest.raises(sqlite3.OperationalError):            # la panne : la base est libre, mais pas pour cette connexion
        mem.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('w', '1', 0)")
    assert daemon._liberer_connexion(mem) is True
    assert not mem.db.in_transaction
    mem.kv_set("echanges_curseur", "42")                      # après le relâchement, ça écrit
    assert mem.kv_get("echanges_curseur") == "42"
    assert daemon._liberer_connexion(mem) is False            # rien d'ouvert : rien à faire


def test_kv_set_qui_echoue_ne_laisse_pas_de_transaction(tmp_path):
    chemin = tmp_path / "m.db"
    mem = Memory(chemin)
    mem.db.execute("PRAGMA busy_timeout=200")
    autre = sqlite3.connect(str(chemin), timeout=0.2)
    autre.execute("BEGIN IMMEDIATE")
    autre.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('x', '1', 0)")
    with pytest.raises(sqlite3.OperationalError):
        mem.kv_set("echanges_curseur", "1")
    assert not mem.db.in_transaction                          # relâchée avant de remonter l'erreur
    autre.commit()
    autre.close()
    mem.kv_set("echanges_curseur", "2")
    assert mem.kv_get("echanges_curseur") == "2"


def test_une_ecriture_en_attente_est_validee_pas_perdue(tmp_path):
    chemin = tmp_path / "m.db"
    mem = Memory(chemin)
    mem.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('attente', 'v', 0)")   # sans commit
    assert daemon._liberer_connexion(mem) is True
    autre = sqlite3.connect(str(chemin))
    assert autre.execute("SELECT value FROM kv WHERE key='attente'").fetchone() == ("v",)
    autre.close()


def test_temoin_sans_relachement_la_panne_reste(tmp_path, monkeypatch):
    """Témoin : sans _liberer_connexion, la connexion reste bloquée (le test d'au-dessus mesure bien le mécanisme)."""
    chemin = tmp_path / "m.db"
    mem = Memory(chemin)
    _empoisonner(mem, chemin)
    for _ in range(2):
        with pytest.raises(sqlite3.OperationalError):
            mem.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES ('w', '1', 0)")


def test_la_boucle_appelle_le_relachement():
    import inspect
    src = inspect.getsource(daemon.main)
    assert src.count("_liberer_connexion(mem)") >= 3
    assert src.index("_liberer_connexion(mem)") < src.index("_travaux_llm(")
    assert "line_buffering=True" in src
