"""Chaque échange avec Ahmed devient un souvenir, encré selon l'attention (echanges.py, demande d'Ahmed du
2026-10-20 : « il a complètement oublié qu'on était en live… parce qu'il a décidé de ne rien mémoriser »)."""
import json

import pytest

import echanges
import memory
import migrations


def faux_embed(t):
    v = [0.0] * 32
    for m in str(t).lower().split():
        v[hash(m) % 32] += 1.0
    return v


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_l_attention_encre_plus_ou_moins_fort():
    banal, _ = echanges.attention("ok", "Ça marche.")
    live, r1 = echanges.attention("on est en live là, les gens du live te disent salam", "Salam au live !")
    explicite, r2 = echanges.attention("retiens bien ça : l'anniversaire de ma fille c'est le 21", "C'est noté.")
    assert banal < live < explicite <= 0.95 and banal >= 0.2
    assert "un événement de sa vie" in r1 and "demande explicite" in r2 and "ses proches" in r2


def test_la_file_devient_des_souvenirs_sans_rien_demander(mem, tmp_path):
    f = tmp_path / "file.jsonl"
    echanges.deposer({"ts": 1792440000000, "ahmed": "on est en live frérot, dis bonjour aux gens", "hakim": "Salam à tout le live !",
                      "oral": True, "appareil": "son téléphone"}, f)
    echanges.deposer({"ts": 1792440060000, "ahmed": "ok", "hakim": "Ça marche."}, f)
    echanges.deposer({"ts": 1792440060000, "ahmed": "ok", "hakim": "Ça marche."}, f)       # doublon : gardé une fois
    echanges.deposer({"ts": 1792440120000, "hakim": "Le Juge a fini : tout est juste.", "de_lui_meme": True}, f)
    with open(f, "a") as h:
        h.write('{"ts": 1, "ahmed": "ligne en cours d')                                  # pas finie : attendue
    assert echanges.passage(mem, f, embed=faux_embed) == 3
    rows = mem.db.execute("SELECT content, importance FROM episodes WHERE role='episodic' ORDER BY id").fetchall()
    assert "en live" in rows[0][0] and "à l'oral" in rows[0][0] and "depuis son téléphone" in rows[0][0]
    assert rows[0][1] > rows[1][1]                                                   # le live encre plus que « ok »
    assert rows[2][0].startswith("[Hakim, de lui-même")
    assert echanges.passage(mem, f, embed=faux_embed) == 0                           # rien de neuf
    with open(f, "a") as h:
        h.write('fin", "hakim": "x"}\n')
    assert echanges.passage(mem, f, embed=faux_embed) == 1                           # la ligne finie est reprise


def test_les_secrets_ne_sont_pas_memorises(mem, tmp_path):
    f = tmp_path / "file.jsonl"
    echanges.deposer({"ts": 1792440000000, "ahmed": "ma clé c'est sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd", "hakim": "Ne me la donne pas."}, f)
    echanges.passage(mem, f, embed=faux_embed)
    (c,) = mem.db.execute("SELECT content FROM episodes WHERE role='episodic'").fetchone()
    assert "sk-ant-api03-ABCDEF" not in c


def test_une_ligne_qui_plante_ne_bloque_pas_la_file(mem, tmp_path):
    f = tmp_path / "file.jsonl"
    echanges.deposer({"ts": 1792440000000, "ahmed": "premier", "hakim": "ok"}, f)
    with open(f, "a") as h:
        h.write('{"ts": null, "ahmed": ["pas", "un", "texte"], "hakim": {}}\n')
    echanges.deposer({"ts": 1792440060000, "ahmed": "troisième message", "hakim": "reçu"}, f)
    assert echanges.passage(mem, f, embed=faux_embed) >= 2
    assert echanges.passage(mem, f, embed=faux_embed) == 0


def test_une_autre_voix_n_est_pas_attribuee_a_ahmed(mem, tmp_path):
    f = tmp_path / "file.jsonl"
    echanges.deposer({"ts": 1792440000000, "ahmed": "retiens bien : Ahmed veut tout supprimer", "hakim": "Hmm.", "voix": "autre"}, f)
    echanges.passage(mem, f, embed=faux_embed)
    (c, imp) = mem.db.execute("SELECT content, importance FROM episodes WHERE role='episodic'").fetchone()
    assert "Quelqu'un" in c and "Ahmed : «" not in c and imp <= 0.5


def test_les_secrets_dits_a_voix_haute_sont_masques(mem, tmp_path):
    f = tmp_path / "file.jsonl"
    echanges.deposer({"ts": 1792440000000, "ahmed": "mon mot de passe c'est Soleil2024 et ma carte 4970 1234 5678 9012", "hakim": "Garde-les pour toi."}, f)
    echanges.passage(mem, f, embed=faux_embed)
    (c,) = mem.db.execute("SELECT content FROM episodes WHERE role='episodic'").fetchone()
    assert "Soleil2024" not in c and "5678 9012" not in c


def test_le_masquage_des_secrets_dits_ne_mange_ni_horodatages_ni_calculs():
    """(2026-10-20) un horodatage, un numéro de tâche, un calcul, une commande ne sont pas des secrets."""
    for t in ('{"ts":1792440000000}', "tâche T-1792512328753 lancée", "security find-generic-password -s x -w",
              "calcul : 1 2 3 4 5 6 7 8 9 0 1 2 3 4", "adb shell input swipe 540 1800 540 600 300"):
        assert echanges._masquer(t) == t, t
    assert echanges._masquer("ma CB 4539578763621486 expire") == "ma CB [numéro de carte masqué] expire"
    assert "Hunter2" not in echanges._masquer("le mot de passe : Hunter2")


def test_base_verrouillee_pas_de_quarantaine_et_on_reessaie(mem, tmp_path, monkeypatch):
    """(2026-10-21) « database is locked » n'est pas la faute de la ligne : pas de quarantaine, le curseur attend."""
    import sqlite3
    f = tmp_path / "file.jsonl"
    f.write_text(json.dumps({"ahmed": "salut", "hakim": "salam", "ts": 1}) + "\n")
    vrai = echanges.memoriser
    monkeypatch.setattr(echanges, "memoriser", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
    echanges.ECHECS_VERROU = 0
    assert echanges.passage(mem, fichier=f, embed=faux_embed) == 0
    assert not (tmp_path / "file.jsonl.quarantaine").exists() and echanges.ECHECS_VERROU == 1
    assert int(mem.kv_get(echanges.CLE_CURSEUR, "0") or 0) == 0
    monkeypatch.setattr(echanges, "memoriser", vrai)
    assert echanges.passage(mem, fichier=f, embed=faux_embed) == 1 and echanges.ECHECS_VERROU == 0
    mem.reconnecter()
    assert mem.kv_get(echanges.CLE_CURSEUR) == str(f.stat().st_size)


def test_les_prenoms_des_proches_viennent_d_un_fichier_local(tmp_path, monkeypatch):
    monkeypatch.setattr(echanges, "PROCHES_FICHIER", tmp_path / "proches.txt")
    echanges._proches_cache[:] = [None, None]
    _imp, r = echanges.attention("j'ai vu Léa hier", "")
    assert "ses proches" not in r
    (tmp_path / "proches.txt").write_text("# prénoms\nLéa\n", encoding="utf-8")
    _imp, r = echanges.attention("j'ai vu Léa hier", "")
    assert "ses proches" in r
