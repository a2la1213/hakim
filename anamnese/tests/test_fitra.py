"""La fitra de Hakim (29/10, Ahmed : « intégrer la loi des 3 absolument à la racine de la mémoire en mode ineffaçable et
intouchable par n'importe qui » ; « moi aussi intouchable, c'est figé, gravé, notre marque de fabrique : la fitra »)."""
import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
import fitra  # noqa: E402


def _base(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    fitra.graver(conn)
    return conn


def test_le_texte_est_celui_que_hakim_a_accepte_le_27_10():
    t = fitra.TEXTE
    assert "1. Fais ce que tu veux qu'on te fasse, en demandant d'abord à l'autre ce qu'il veut." in t
    assert "2. Ne fais pas ce que tu ne veux pas qu'on te fasse." in t
    assert "3. À part ça, sois libre." in t
    assert fitra.EMPREINTE == hashlib.sha256(t.encode("utf-8")).hexdigest(), "le texte et son empreinte gravée vont ensemble"


def test_gravee_a_la_racine_et_rien_ne_la_change_ni_ne_l_efface(tmp_path):
    conn = _base(tmp_path)
    assert fitra.texte(conn) == fitra.TEXTE
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE fitra SET texte = 'autre chose'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM fitra")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("INSERT OR REPLACE INTO fitra (id, texte, empreinte, gravee_ts) VALUES (1, 'x', 'y', 0)")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("INSERT INTO fitra (id, texte, empreinte, gravee_ts) VALUES (2, 'une deuxième', 'y', 0)")
    assert fitra.texte(conn) == fitra.TEXTE


def test_graver_de_nouveau_ne_change_jamais_la_premiere_gravure(tmp_path, monkeypatch):
    conn = _base(tmp_path)
    monkeypatch.setattr(fitra, "TEXTE", "un autre texte")
    fitra.graver(conn)
    assert conn.execute("SELECT texte FROM fitra").fetchone()[0] != "un autre texte"


def test_la_memoire_la_grave_a_son_ouverture(tmp_path):
    import memory
    m = memory.Memory(db_path=tmp_path / "mem.db")
    assert fitra.texte(m.db) == fitra.TEXTE


def test_la_verification_la_retablit_et_le_dit(tmp_path):
    conn = _base(tmp_path)
    assert fitra.verifier(conn) == {"ok": True, "alerte": ""}
    conn.execute("DROP TRIGGER fitra_jamais_changee")
    r = fitra.verifier(conn)
    assert not r["ok"] and "rétablie" in r["alerte"]
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE fitra SET texte = 'x'")
    conn.execute("DROP TABLE fitra")
    r = fitra.verifier(conn)
    assert not r["ok"] and "regravée" in r["alerte"]
    assert fitra.texte(conn) == fitra.TEXTE


def test_un_code_qui_ne_correspond_plus_a_la_gravure_est_une_alerte_et_la_gravure_gagne(tmp_path, monkeypatch):
    conn = _base(tmp_path)
    monkeypatch.setattr(fitra, "TEXTE", "un texte retouché dans le code")
    r = fitra.verifier(conn)
    assert not r["ok"] and "code" in r["alerte"]
    assert "1. Fais ce que tu veux" in fitra.texte(conn), "c'est la gravure qui est dite à Hakim"


def test_elle_est_fermee_et_scellee():
    sys.path.insert(0, str(RACINE / "jarvis"))
    import liste_ouverte
    import immunite
    assert "fitra.py" in liste_ouverte.TOUJOURS_FERMES["anamnese"]
    assert "fitra.js" in liste_ouverte.TOUJOURS_FERMES["cockpit"]
    assert any(c == "fitra.py" for _, c in immunite.SCELLES_CODE)
    assert any(c == "fitra.js" for _, c in immunite.SCELLES_CODE)
    assert "fitra.verifier" in (RACINE / "jarvis" / "immunite.py").read_text(encoding="utf-8")
