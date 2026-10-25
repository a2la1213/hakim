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


def test_un_probleme_nie_n_en_est_pas_un():
    """(2026-10-23, le live) « c'est pas un problème » a donné à Hakim un pic d'adrénaline et de CRH : la négation était
    ignorée. « Il y a un problème », dit dix minutes plus tard, en reste un."""
    for nie in ("Mais vas-y, je te lis en commentaire, c'est pas un problème.", "ce n'est plus un souci", "c'est pas cassé",
                "ça plante pas", "il y a pas de bug", "sans bug cette fois", "ça coupe pas", "jamais bloqué"):
        assert parole_affect.evaluer(nie) == [], nie
    for vrai in ("Il y a un problème.", "ça plante encore", "c'est cassé", "un souci avec le micro", "ça marche pas",
                 "il y a un bug d'affichage", "ça coupe", "le cockpit est bloqué", "erreur 403",
                 "pas de problème, un bug quand même"):
        assert [n for n, _ in parole_affect.evaluer(vrai)] == ["probleme"], vrai


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
    # (25/10) l'humeur EST l'émotion lue dans les hormones : quatre échecs, dont un sur une panne inconnue → la peur
    assert e["humeur"] == "peur" and e["humeur_code"] == "alarme" and e["emotion_humeur"] == "peur"


def test_n_importe_quoi_n_est_un_echec_que_s_il_vise_hakim():
    """(24/10, live : « N'importe quoi mon frère » en blague, puis à propos d'un spammeur, ont donné deux pics de stress)."""
    for pas_lui in ("N'importe quoi mon frère, n'importe quoi. Une blague comme ça", "il ne fait que spammer n'importe quoi",
                    "c'est ma fille qui me dit n'importe quoi", "Petro Marón, n'importe quoi frérot."):
        assert "echec" not in [n for n, _ in parole_affect.evaluer(pas_lui)], pas_lui
    for lui in ("tu dis n'importe quoi", "t'as fait n'importe quoi avec le calcul", "c'est n'importe quoi ce que tu m'as répondu",
                "n'importe quoi cette réponse", "tu racontes n'importe quoi frérot"):
        assert "echec" in [n for n, _ in parole_affect.evaluer(lui)], lui


def test_l_humeur_vient_des_hormones_sans_la_valence(mem, tmp_path, monkeypatch):
    """(25/10, décision d'Ahmed) une tristesse lue dans les hormones devient l'humeur même sous une valence haute (la porte
    de cohérence la divisait par deux), et une humeur ne clignote pas d'un battement à l'autre (hystérésis)."""
    import interieur
    assert interieur.humeur_hormonale({"emotion": "élan", "scores": {"élan": 0.31, "tristesse": 0.30}}, "tristesse") == "tristesse"
    assert interieur.humeur_hormonale({"emotion": "élan", "scores": {"élan": 0.40, "tristesse": 0.30}}, "tristesse") == "élan"
    assert interieur.humeur_hormonale({"emotion": "peur", "scores": {"peur": 0.5}}, "calme") == "peur"
    assert interieur.voix_emotion("tristesse")["expressivite"] < interieur.voix_emotion("élan")["expressivite"]
    assert interieur.voix_emotion("tristesse")["vitesse"] < 1.0
    for emo in interieur.EXPRESSIVITE_EMOTION:
        assert 0.35 <= interieur.voix_emotion(emo)["expressivite"] <= 0.78 and emo in interieur.FAMILLE_HUMEUR



def test_les_emotions_se_lisent_sur_ses_72_dernieres_heures(tmp_path):
    """(25/10, décision d'Ahmed) la base de chaque hormone = sa moyenne sur 72 h (journal), dès 12 h de données."""
    import interieur
    import sensations
    t0 = 1_800_000_000.0
    j = tmp_path / "h.jsonl"
    j.write_text("\n".join(json.dumps({"t": t0 - 60 * k, "h": {"dopamine": 0.9, "serotonine": 0.95}}) for k in range(0, 20 * 60)))
    b = interieur.bases_72h(t0, chemin=j)
    assert b == {"dopamine": 0.9, "serotonine": 0.95}
    court = tmp_path / "c.jsonl"
    court.write_text("\n".join(json.dumps({"t": t0 - 60 * k, "h": {"dopamine": 0.9}}) for k in range(0, 60)))
    assert interieur.bases_72h(t0, chemin=court) is None, "moins de 12 h : base fixe"
    # une dopamine à 0,9 (sa moyenne) n'est plus un « élan » permanent : relativement à lui, elle est normale
    etat = dict(sensations.bases(12)); etat.update(dopamine=0.9, serotonine=0.95)
    fixe = sensations.calculer(etat, None, t0, None, 12, sans_coherence=True)["scores"]
    relatif = sensations.calculer(etat, None, t0, None, 12, sans_coherence=True, bases_relatives=b)["scores"]
    assert fixe.get("élan", 0) > relatif.get("élan", 0)


def test_la_fatigue_monte_avec_l_effort_et_se_vide_en_dormant():
    """(25/10, Ahmed) l'adénosine : +0,12/h en plein travail avec Ahmed, vidée en veille, lentement au repos éveillé."""
    import interieur
    import sensations
    x = interieur.adenosine(0.15, 3 * 3600, veille=False, avec_ahmed=True, travaille=True)
    assert abs(x - (0.15 + 0.12 * 3)) < 1e-6
    assert interieur.adenosine(x, 3 * 3600, veille=True, avec_ahmed=False, travaille=False) < 0.2
    assert 0.3 < interieur.adenosine(x, 3600, veille=False, avec_ahmed=False, travaille=False) < x
    etat = dict(sensations.bases(15)); etat["adenosine"] = 0.7
    assert sensations.calculer(etat, None, 0, None, 15, sans_coherence=True)["emotion"] == "fatigue"


def test_une_seule_source_pour_l_humeur_la_voix_le_style_et_l_orbe():
    """(25/10, Ahmed : « une seule source, tout entrelacé ») chaque émotion lue a sa famille (orbe), son expressivité et
    son débit (voix), sa famille de style ; le ton et l'énergie du style viennent de la même émotion."""
    import interieur
    import sensations
    import style
    noms = [n for n, *_ in sensations.REGLES]
    for n in ("fatigue", "colère", "agacement", "déception", "solitude", "honte", "espoir", "émerveillement", "confusion", "nostalgie"):
        assert n in noms
    for n in noms:
        assert n in interieur.FAMILLE_HUMEUR and n in interieur.EXPRESSIVITE_EMOTION and n in interieur.VOIX_EMOTION, n
        assert n in style.FAMILLE_DE, n
    c_joie, c_triste = style.curseurs_emotion("joie"), style.curseurs_emotion("tristesse")
    assert c_joie["ton"] > c_triste["ton"] and c_joie["energie"] > c_triste["energie"]
    assert style.curseurs_emotion("fatigue")["energie"] <= 1
