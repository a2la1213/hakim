"""La trace émotionnelle des souvenirs et la parole → hormones (affect v2, cinquième passage, 2026-10-21 ; prédictions
figées dans eval/affect_v2_predictions.md, mesure : eval/affect_v2_memoire.py)."""
import json
import sqlite3
import time

import pytest

import affect
import consolidate
import echanges
import memory
import migrations
import parole_affect


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


def _v2(m):
    m.kv_set("affect_v2", "1")
    affect.get_state(m)
    affect._save_v2(m, affect.bases(v2=True), {}, {}, time.time())


def test_la_parole_evaluee():
    assert parole_affect.evaluer("ça marche pas, ça plante") == [("probleme", 0.6)]
    assert parole_affect.evaluer("pas parfait") == []
    assert parole_affect.evaluer("ça marche, on fait comme ça") == []
    assert {n for n, _ in parole_affect.evaluer("parfait frero merci beaucoup")} == {"succes", "chaleur_user"}
    assert len(parole_affect.evaluer("génial merci et si on ajoutait une idée, ça bug")) <= 2


def test_la_parole_v2_seulement_et_sans_double_compte(mem, tmp_path):
    assert parole_affect.appliquer(mem, "merci frero", "projets/anamnese", time.time()) == []      # v1 : rien
    _v2(mem)
    journal = tmp_path / "j.jsonl"
    t = time.time()
    journal.write_text(json.dumps({"ts": t - 60, "nom": "chaleur_user", "source": "hakim"}) + "\n")
    assert parole_affect.appliquer(mem, "merci frero, parfait", "projets/anamnese", t, journal) == [("succes", 0.4)]


def test_chaque_souvenir_porte_sa_trace(mem):
    _v2(mem)
    affect.event(mem, "echec", 1.0, sujet="une panne jamais vue")
    eid = mem.add("episodic", "la panne du cockpit", importance=0.5, embedding=faux_embed("panne"), dedup=False)
    ev, ja = mem.db.execute("SELECT enc_valence, enc_affect FROM episodes WHERE id=?", (eid,)).fetchone()
    t = json.loads(ja)
    assert ev is not None and "adrenaline" in t["h"] and t["e"] == "alarme" and t["c"] >= 0.5


def test_un_echange_vecu_avec_emotion_est_encre_plus_fort(tmp_path):
    imps = []
    for alarme in (False, True):
        m = memory.Memory(db_path=tmp_path / f"m{alarme}.db")
        migrations.migrate(m.db)
        _v2(m)
        if alarme:
            affect.event(m, "echec", 1.0, sujet="une panne jamais vue")
        echanges.memoriser(m, {"ahmed": "on regarde le planning de la semaine", "hakim": "D'accord.",
                               "ts": time.time() * 1000}, embed=faux_embed)
        imps.append(m.db.execute("SELECT importance FROM episodes WHERE role='episodic'").fetchone()[0])
        m.db.close()
    assert 0.05 <= round(imps[1] - imps[0], 3) <= 0.15


def test_rappel_dependant_de_l_etat_et_garde_fou(mem):
    _v2(mem)
    v0, a0 = affect.valence_arousal(affect.bases(v2=True))
    # même contenu, même âge : l'un encodé sombre, l'autre encodé gai
    ids = {}
    for nom, ev in (("sombre", v0 - 0.3), ("gai", v0 + 0.3)):
        ids[nom] = mem.add("episodic", f"le déploiement du cockpit ({nom})", importance=0.5,
                           embedding=faux_embed("le déploiement du cockpit"), dedup=False)
        mem.db.execute("UPDATE episodes SET enc_valence=?, enc_arousal=?, enc_affect=NULL, ts=? WHERE id=?",
                       (ev, a0, time.time() - 3600, ids[nom]))
    mem.db.commit()
    for k in range(4):                                       # une humeur sombre
        affect.event(mem, "echec", 1.0)
    f_sombre = affect.modulation_rappel(mem)
    v, a = affect.valence_arousal(affect.get_state(mem))
    assert v - v0 < -affect.MEM_GARDE
    assert f_sombre(v0 - 0.3, a0, 0.0, 0.5)[1] == 0.0       # le garde-fou : pas de bonus au sombre
    # l'émotionnel résiste à l'oubli, le neutre s'efface plus vite, le non estampillé ne bouge pas
    f = affect.modulation_rappel(mem, charge_moyenne=0.4)
    assert abs(f(v0, a0, 1.0, 0.2)[0] - (0.2 + 0.8 * affect.MEM_RESISTE * 0.6)) < 1e-9
    assert f(v0, a0, 0.0, 0.2)[0] < 0.2 and f(None, None, None, 0.2) == (0.2, 0.0)
    assert f(v0, a0, 0.4, 0.2)[1] == 0.0                     # encodé à la base : jamais d'avantage


def test_neutre_aucun_bonus_d_etat(mem):
    _v2(mem)
    v0, a0 = affect.valence_arousal(affect.bases(v2=True))
    f = affect.modulation_rappel(mem)
    assert f(v0 + 0.2, a0 + 0.1, 0.0, 0.5)[1] < 1e-6 and f(v0, a0, 0.0, 0.5)[1] < 1e-6


def test_v1_rappel_inchange(mem):
    assert affect.modulation_rappel(mem) is None


def _base(tmp_path, v2):
    db = tmp_path / f"c{v2}.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, rubric_id INTEGER, "
                "enc_valence REAL, enc_arousal REAL, enc_affect TEXT)")
    con.execute("CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT)")
    con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
    con.execute("INSERT INTO episodes (ts, role, content, rubric_id, enc_affect) VALUES (100, 'episodic', 'la panne', NULL, ?)",
                (json.dumps({"c": 0.8}),))
    con.execute("INSERT INTO episodes (ts, role, content, rubric_id, enc_affect) VALUES (101, 'episodic', 'le café', NULL, ?)",
                (json.dumps({"c": 0.1}),))
    if v2:
        con.execute("INSERT INTO kv VALUES ('affect_v2', '1', 0)")
    con.commit()
    con.close()
    return db


def test_la_nuit_garde_d_abord_l_emotionnel(tmp_path):
    lot = consolidate.lot_a_consolider(0, db_path=_base(tmp_path, True))
    assert [s["emotion"] for s in lot] == [True, False]
    p = consolidate.construire_prompt("BASE", lot)
    assert "VÉCU AVEC ÉMOTION] la panne" in p and consolidate.CONSIGNE_EMOTION in p
    lot1 = consolidate.lot_a_consolider(0, db_path=_base(tmp_path, False))
    assert not any(s["emotion"] for s in lot1) and consolidate.CONSIGNE_EMOTION not in consolidate.construire_prompt("BASE", lot1)


def test_gemma_recoit_l_emotion_et_le_fond(mem, tmp_path, monkeypatch):
    import interieur
    _v2(mem)
    for k in range(3):
        affect.event(mem, "echec", 1.0)
    affect.event(mem, "echec", 1.0, sujet="une panne jamais vue")
    monkeypatch.setattr(interieur, "JOURNAL_TEMPS", tmp_path / "temps.jsonl")
    e = interieur.tick(mem, penser=lambda *a, **k: None, interrupteur_={"actif": True})
    assert e["humeur"].startswith(interieur.LIBELLES["alarme"]) and "(fond : " in e["humeur"]
