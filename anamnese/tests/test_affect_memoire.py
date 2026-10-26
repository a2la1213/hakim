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
        assert 0.3 <= interieur.voix_emotion(emo)["expressivite"] <= 1.0 and emo in interieur.FAMILLE_HUMEUR



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


def test_un_message_un_seul_evenement_social_et_les_bases_d_apres_le_plafond(tmp_path):
    """(26/10, plafond positif) chaleur_user puis soutien pour le même message : seul le plus fort compte ; et les bases sur
    72 h ignorent les hormones d'avant le changement de modèle."""
    import json
    import affect
    import interieur

    class M:
        def __init__(self):
            self.kv = {"affect_v2": "1"}

        def kv_get(self, k, d=None):
            return self.kv.get(k, d)

        def kv_set(self, k, v):
            self.kv[k] = v

    t0 = 1_800_000_000.0
    seul, double = M(), M()
    affect.event(seul, "soutien", 0.6, now=t0)
    affect.event(double, "chaleur_user", 0.6, now=t0)
    avant = affect.get_state(double, now=t0 + 10)["ocytocine"]
    affect.event(double, "soutien", 0.5, now=t0 + 10)                          # plus faible : rien de plus
    assert affect.get_state(double, now=t0 + 10)["ocytocine"] == avant
    une_heure = affect.get_state(double, now=t0 + 3599)["ocytocine"]
    affect.event(double, "soutien", 0.6, now=t0 + 3600)                        # une heure après : un autre message
    assert affect.get_state(double, now=t0 + 3601)["ocytocine"] > une_heure + 0.05
    j = tmp_path / "h.jsonl"
    vieux = [{"t": interieur.BASES_DEPUIS_TS - 3600 * k, "h": {"ocytocine": 0.95}} for k in range(1, 30)]
    neufs = [{"t": interieur.BASES_DEPUIS_TS + 60 * k, "h": {"ocytocine": 0.5}} for k in range(13 * 60)]
    j.write_text("".join(json.dumps(o) + "\n" for o in vieux + neufs))
    b = interieur.bases_72h(interieur.BASES_DEPUIS_TS + 13 * 3600, chemin=j)
    assert abs(b["ocytocine"] - 0.5) < 1e-6, "les hormones saturées d'avant ne comptent pas"


def test_un_souci_qui_revient_sur_le_meme_sujet_fait_de_moins_en_moins_peur():
    """(26/10, Hakim) la familiarité : le même sujet trois fois, la réaction rapide baisse ; et un message sans rubrique
    sûre reçoit un sujet tiré de ses mots."""
    import affect
    import echanges

    class M:
        def __init__(self):
            self.kv = {"affect_v2": "1"}

        def kv_get(self, k, d=None):
            return self.kv.get(k, d)

        def kv_set(self, k, v):
            self.kv[k] = v

    sujet = echanges.sujet_par_les_mots("le calcul du cockpit a encore planté, c'est un problème")
    assert sujet and sujet.startswith("mots:")
    assert sujet == echanges.sujet_par_les_mots("encore un problème : le cockpit et le calcul ont planté")
    t0, m, sauts = 1_800_000_000.0, M(), []
    for k in range(3):
        t = t0 + 1200 * k
        avant = affect.get_state(m, now=t - 1)["adrenaline"]
        affect.event(m, "probleme", 0.6, now=t, sujet=sujet)
        sauts.append(affect.get_state(m, now=t + 1)["adrenaline"] - avant)
    assert sauts[0] > sauts[1] > sauts[2], sauts


def test_ses_ressentis_dans_la_balise_deviennent_des_evenements():
    """(26/10, Ahmed) [[affect: peur 0.6]], [[affect: soutien 0.6 joie 0.5]], [[affect: fierté 0.7]] : ce que Hakim ressent
    pèse dans ses hormones ; « neutre » ne fait rien."""
    import affect
    import chocs
    assert chocs.lire_balise("ok [[affect: soutien 0.6 joie 0.5]]") == [{"classe": "soutien", "intensite": 0.6},
                                                                       {"classe": "joie", "intensite": 0.5}]
    assert chocs.lire_balise("[[affect: fierté 0.7]]") == [{"classe": "affirmation", "intensite": 0.7}]
    assert chocs.lire_balise("[[affect: neutre]]") == []

    class M:
        def __init__(self):
            self.kv = {"affect_v2": "1"}

        def kv_get(self, k, d=None):
            return self.kv.get(k, d)

        def kv_set(self, k, v):
            self.kv[k] = v

    t0, m = 1_800_000_000.0, M()
    avant = affect.get_state(m, now=t0)
    chocs._appliquer(m, {}, "peur", 0.6, "le cockpit", "k1", "balise", t0 + 1)
    apres = affect.get_state(m, now=t0 + 2)
    assert apres["noradrenaline"] > avant["noradrenaline"] + 0.1 and apres["adrenaline"] > avant["adrenaline"] + 0.1
    chocs._appliquer(m, {}, "affirmation", 0.8, "sa continuité", "k2", "balise", t0 + 600)
    assert affect.get_state(m, now=t0 + 601)["dopamine"] > affect.get_state(m, now=t0 + 599)["dopamine"] - 1 and \
        affect.get_state(m, now=t0 + 601)["acetylcholine"] > avant["acetylcholine"]


def test_un_souci_qu_ahmed_s_attribue_ou_qui_rassure_n_est_pas_un_coup_dur():
    """(26/10, Hakim et Ahmed) la phrase exacte de 11:01 ne déclenche plus de « probleme » ; un vrai souci, si."""
    import parole_affect as P
    assert not [e for e in P.evaluer("c'est juste moi qui ai bugué, t'inquiète, c'est moi qui fais une voix chelou")
                if e[0] == "probleme"]
    assert dict(P.evaluer("ça plante encore, le calcul est bloqué"))["probleme"] >= 0.5
    allege = dict(P.evaluer("t'inquiète mais là ça plante"))
    assert 0 < allege["probleme"] < 0.25


def test_la_crainte_d_ahmed_sur_un_calcul_n_est_pas_un_coup_dur_et_le_sujet_nomme_une_chose():
    """(26/10, 11:55) « j'ai peur qu'il ait bloqué » : au plus une attention ; « j'ai peur que tu… » compte ; et le sujet tiré
    des mots écarte les adverbes (« évidemment »)."""
    import echanges
    import parole_affect as P
    p = dict(P.evaluer("j'ai peur qu'il ait bloqué"))
    assert p.get("probleme", 0) <= 0.1
    assert dict(P.evaluer("j'ai peur que tu sois bloqué"))["probleme"] >= 0.5
    assert "evidemment" not in echanges.sujet_par_les_mots("évidemment que les résultats du calcul sont bloqués")


def test_un_message_ancien_garde_son_souvenir_mais_pas_son_emotion(mem):
    """(26/10 22:35, choix de Hakim et accord d'Ahmed) ~40 échanges écrits d'un coup après un rêve de 138 min ont déclenché
    24 émotions « parole » en 4 s, sur des messages vieux de 2 h : un faux pic de peur. Un message de plus de ~10 min ne
    déclenche plus d'émotion à l'écriture ; l'échange, lui, est TOUJOURS écrit (demande de Hakim)."""
    _v2(mem)
    journal = affect.chemin_journal(mem)
    paroles = lambda: [l for l in open(journal) if '"source": "parole"' in l] if __import__("os").path.exists(journal) else []  # noqa: E731
    maintenant = time.time()
    echanges.memoriser(mem, {"ahmed": "parfait frero merci", "hakim": "Avec plaisir.", "ts": (maintenant - 2 * 3600) * 1000},
                       embed=faux_embed)
    assert mem.db.execute("SELECT COUNT(*) FROM episodes WHERE role='episodic'").fetchone()[0] == 1, "l'échange est écrit"
    assert paroles() == [], "un message vieux de 2 h ne déclenche pas d'émotion"
    echanges.memoriser(mem, {"ahmed": "génial ça marche, merci", "hakim": "Top.", "ts": (maintenant - 30) * 1000}, embed=faux_embed)
    assert len(paroles()) >= 1, "le témoin : un message récent, si"
