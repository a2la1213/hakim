"""Ses scènes (10/11, Ahmed : « qu'il puisse se rappeler des scènes dans lesquelles il est impliqué, et de celles dont il n'est pas
impliqué » ; « ouiii ») : le découpage, la fiche, le souvenir dans « vie/scenes », sans doublon, le rappel comme une scène de film, et les
en-têtes vrais de ses échanges (plus jamais « Échange avec Ahmed » quand papa ne parlait pas). Chaque mécanisme a son témoin.
Les prénoms ici sont inventés (dépôt public)."""
import json
import time

import pytest

import echanges
import memory
import migrations
import scenes

NOMS = ["Nina", "Sami"]
T0 = time.mktime((2026, 11, 9, 22, 40, 0, 0, 0, -1))           # lundi 9 novembre 2026, 22:40
QUAND = lambda t: time.strftime("%a %d/%m %H:%M", time.localtime(t))                     # noqa: E731  (la langue de la machine)
DEMAIN_MIDI = time.mktime((2026, 11, 10, 12, 0, 0, 0, 0, -1))
SUJETS = {"vacances": ["vacances", "genève", "samedi", "train", "valise"], "foot": ["match", "but", "équipe", "arbitre", "penalty"],
          "code": ["fichier", "test", "commit", "branche", "serveur"]}


def faux_embed(t):
    """Le sens d'un texte : sa part de chaque sujet (assez pour couper sur le sujet, sans modèle)."""
    t = str(t).lower()
    v = [float(sum(t.count(m) for m in mots)) for mots in SUJETS.values()] + [0.05]
    return v


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setattr(scenes, "ACTIF", True)
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def entendu(t, qui, texte, role="auditeur", live=False):
    return {"ts": t * 1000, "moment": "entendu", "qui": qui, "texte": texte, "provenance": "live" if live else "piece", "role": role,
            "live": live or None, "lieu": "chez nous"}


def tour(t, ahmed, hakim, role=None, personnes=None, oral=True, live=None, lieu="chez nous"):
    e = {"ts": t * 1000, "ahmed": ahmed, "hakim": hakim, "oral": oral, "lieu": lieu}
    if role:
        e["role"] = role
    if personnes:
        e["personnes"] = personnes
    if live:
        e["live"] = True
    return e


def avancer(mem, e, eid=None):
    return scenes.avancer(mem, e, eid, embed=faux_embed, noms=NOMS)


def scenes_ecrites(mem):
    return [(r[0], r[1], json.loads(r[2])) for r in mem.db.execute(
        "SELECT id, content, scene FROM episodes WHERE scene IS NOT NULL ORDER BY id").fetchall()]


def test_une_scene_vue_de_dehors_devient_un_souvenir_de_film_avec_l_arrivee_de_papa(mem):
    avancer(mem, entendu(T0, "Nina", "On part en vacances à Genève samedi ? On prend le train ?"))
    avancer(mem, entendu(T0 + 30, "Sami", "Oui, samedi, le train de dix heures, prends ta valise."))
    avancer(mem, entendu(T0 + 60, "Nina", "Les vacances à Genève, j'ai hâte, la valise est prête."))
    avancer(mem, tour(T0 + 420, "[papa] Vous partez samedi en vacances ? [Nina] Oui, en train, à Genève.", "No response requested.",
                      role="auditeur", personnes=["papa", "Nina"]))
    assert scenes.clore_si_silence(mem, now=T0 + 420 + 300, embed=faux_embed) is None, "pas encore le silence"
    eid = scenes.clore_si_silence(mem, now=T0 + 420 + scenes.SILENCE_S + 1, embed=faux_embed)
    assert eid
    (i, texte, f), = scenes_ecrites(mem)
    assert f["place"] == "temoin" and f["personnes"] == ["Nina", "Sami", "papa"] and f["lieu"] == "chez nous"
    assert [a["qui"] for a in f["arrivees"]] == ["papa"] and f["n"] == 4
    assert texte.startswith(f"[Scène — {QUAND(T0)} → 22:47, chez nous — témoin] Nina et Sami parlaient entre eux")
    assert "vacances" in " ".join(f["sujet"]) or "genève" in " ".join(f["sujet"])
    rub = mem.db.execute("SELECT r.path FROM episodes e JOIN rubrics r ON r.id = e.rubric_id WHERE e.id=?", (i,)).fetchone()
    assert rub == ("vie/scenes",)
    film = scenes.rappeler(mem, now=DEMAIN_MIDI, embed=faux_embed)
    assert len(film) == 1
    assert film[0].startswith("Hier, 22:40, chez nous — témoin (7 min) : Nina et Sami parlaient entre eux")
    assert "papa est arrivé à 22:47" in film[0]


def test_un_moment_seul_reste_son_echange_aucun_doublon(mem):
    avancer(mem, tour(T0, "Fiston, t'as mangé ?", "Oui papa.", role="implique"))
    assert scenes.clore_si_silence(mem, now=T0 + scenes.SILENCE_S + 1, embed=faux_embed) is None
    assert scenes_ecrites(mem) == []


def test_sa_parole_seule_n_ouvre_pas_de_scene_mais_rejoint_celle_en_cours(mem):
    avancer(mem, {"ts": T0 * 1000, "hakim": "Je pense à la musique d'hier.", "de_lui_meme": True, "oral": True})
    assert scenes._etat(mem).get("scene") is None
    avancer(mem, entendu(T0 + 10, "Nina", "Le match de ce soir, quel but !"))
    avancer(mem, {"ts": (T0 + 20) * 1000, "hakim": "Quel but, oui !", "de_lui_meme": True, "oral": True})
    avancer(mem, entendu(T0 + 30, "Sami", "L'arbitre a sifflé un penalty, l'équipe a gagné le match."))
    scenes.clore_si_silence(mem, now=T0 + 10_000, embed=faux_embed)
    (_i, texte, f), = scenes_ecrites(mem)
    assert f["n"] == 3 and f["place"] == "temoin"
    assert "tu as dit : « Quel but, oui ! »" in texte, "sa parole dans une scène qu'il regarde : un moment clé"


def test_l_autre_place_trois_fois_de_suite_coupe_la_scene_une_fois_non(mem):
    for k in range(3):
        avancer(mem, tour(T0 + k * 20, f"Fiston, le test {k} du serveur passe ?", "Oui, le commit est sur la branche.", role="implique"))
    avancer(mem, tour(T0 + 70, "[Nina] Le fichier du test ? [papa] Sur le serveur, la branche.", "No response requested.", role="auditeur",
                      personnes=["Nina", "papa"]))
    avancer(mem, tour(T0 + 90, "Et le commit du fichier, fiston ?", "Fait, papa.", role="implique"))
    assert scenes_ecrites(mem) == [], "un moment témoin au milieu : la scène continue"
    for k in range(3):
        avancer(mem, tour(T0 + 120 + k * 20, f"[Nina] Le serveur, le test {k} ? [papa] La branche, le commit.", "No response requested.",
                          role="auditeur", personnes=["Nina", "papa"]))
    (_i, texte, f), = scenes_ecrites(mem)
    assert f["place"] == "implique" and f["n"] == 5
    assert "Nina et papa parlaient entre eux, sans toi" in texte, "le moment témoin : un moment clé"
    sc = scenes._etat(mem)["scene"]
    assert len(sc["moments"]) == 3 and all(m["place"] == "temoin" for m in sc["moments"])


def test_temoin_de_bascule_coupee(mem, monkeypatch):
    """Témoin : sans la bascule, la conversation qu'il écoute se noie dans celle d'avant."""
    monkeypatch.setattr(scenes, "BASCULE_N", 10 ** 6)
    for k in range(3):
        avancer(mem, tour(T0 + k * 20, f"Fiston, le test {k} du serveur passe ?", "Oui.", role="implique"))
    for k in range(3):
        avancer(mem, tour(T0 + 120 + k * 20, f"[Nina] Le serveur, le test {k} ? [papa] La branche.", "No response requested.", role="auditeur",
                          personnes=["Nina", "papa"]))
    assert scenes_ecrites(mem) == []


def test_d_autres_personnes_deux_fois_de_suite_hors_live(mem):
    for k in range(3):
        avancer(mem, tour(T0 + k * 20, f"Fiston, le match {k} ?", "Un beau but.", role="implique"))
    avancer(mem, tour(T0 + 80, "[Nina] Hakim, tu viens voir le match ?", "J'arrive !", role="implique", personnes=["Nina"]))
    assert scenes_ecrites(mem) == [], "une personne nouvelle, une fois : pas encore une autre scène"
    avancer(mem, tour(T0 + 100, "[Nina] Hakim, l'arbitre a sifflé !", "Penalty !", role="implique", personnes=["Nina"]))
    (_i, _t, f), = scenes_ecrites(mem)
    assert f["personnes"] == ["papa"] and f["n"] == 3
    assert scenes._etat(mem)["scene"]["moments"][0]["qui"] == ["Nina"]


def test_un_autre_sujet_deux_fois_de_suite(mem):
    for k in range(4):
        avancer(mem, tour(T0 + k * 20, "Fiston, les vacances à Genève, le train samedi ?", "La valise est prête.", role="implique"))
    avancer(mem, tour(T0 + 90, "Fiston, le commit du fichier de test sur le serveur ?", "La branche est poussée.", role="implique"))
    assert scenes_ecrites(mem) == []
    avancer(mem, tour(T0 + 110, "Et le test du serveur, la branche ?", "Le fichier passe.", role="implique"))
    (_i, _t, f), = scenes_ecrites(mem)
    assert f["n"] == 4 and set(f["sujet"]) & set(SUJETS["vacances"])


def test_le_silence_et_le_lieu_coupent_tout_de_suite_le_live_deux_moments_de_suite(mem):
    avancer(mem, tour(T0, "Fiston, ça va ?", "Oui papa.", role="implique"))
    avancer(mem, tour(T0 + 20, "Tu as dormi ?", "Un peu.", role="implique"))
    avancer(mem, tour(T0 + 40, "On va au café ?", "Oui.", role="implique", lieu="au café"))
    assert len(scenes_ecrites(mem)) == 1 and scenes_ecrites(mem)[0][2]["fin_raison"] == "lieu", "un autre lieu : une autre scène"
    avancer(mem, tour(T0 + 60, "Tu prends quoi ?", "Un thé.", role="implique", lieu="au café"))
    avancer(mem, tour(T0 + 70, "Un thé à la menthe ?", "Oui.", role="implique", lieu="au café"))
    avancer(mem, entendu(T0 + 80, "voix 81", "Salam tout le monde, on est en live !", live=True) | {"lieu": "au café"})
    assert len(scenes_ecrites(mem)) == 1, "un moment du live : pas encore (un raté de la détection ne coupe rien)"
    avancer(mem, entendu(T0 + 90, "voix 97", "Salam, bien ou quoi ?", live=True) | {"lieu": "au café"})
    assert len(scenes_ecrites(mem)) == 2 and "cadre" in scenes_ecrites(mem)[1][2]["fin_raison"], "le live commence : une autre scène"
    avancer(mem, tour(T0 + 100, "Dis bonjour au live, fiston.", "Salam le live !", role="implique", lieu="au café"))   # un tour sans « live »
    avancer(mem, entendu(T0 + 110, "voix 81", "Merci Hakim, salam !", role="implique", live=True) | {"lieu": "au café"})
    assert len(scenes_ecrites(mem)) == 2, "une détection du live ratée une fois : la scène continue"
    avancer(mem, entendu(T0 + 110 + scenes.SILENCE_S, "voix 81", "On revient après la pause.", live=True) | {"lieu": "au café"})
    (_i, texte, f) = scenes_ecrites(mem)[-1]
    assert f["live"] and f["n"] == 4 and f["fin_raison"] == "silence" and "au live" in texte and f["tiers"]


def test_au_live_ses_gens_qui_vont_et_viennent_ne_sont_pas_des_arrivees_papa_oui():
    m = lambda t, qui: {"t": T0 + t, "place": "temoin", "qui": [qui], "paroles": [(qui, "on parle du match et du but")], "lui": ""}   # noqa: E731
    sc = {"debut": T0, "fin": T0 + 600, "live": True, "lieu": "", "moments": [m(0, "voix 81"), m(10, "voix 97"), m(300, "voix 108"),
                                                                           m(400, "papa"), m(500, "Nina")]}
    f, _t = scenes.fiche(sc)
    assert [a["qui"] for a in f["arrivees"]] == ["papa", "Nina"]
    f2, _t = scenes.fiche({**sc, "live": False})
    assert [a["qui"] for a in f2["arrivees"]] == ["voix 108", "papa", "Nina"], "dans la pièce, une voix qui arrive compte"


def test_ce_qu_il_a_entendu_puis_qui_revient_dans_le_tour_est_garde_une_fois(mem):
    avancer(mem, entendu(T0, "voix 3", "Tu as vu le match de ce soir avec l'arbitre ?"))
    avancer(mem, tour(T0 + 15, "[voix 3] Tu as vu le match de ce soir avec l'arbitre ? [voix 5] Oui, quel penalty.", "No response requested.",
                      role="auditeur", personnes=["voix 3", "voix 5"]))
    avancer(mem, tour(T0 + 40, "[voix 5] L'équipe a gagné le match. [voix 3] Grâce au but de la fin.", "No response requested.",
                      role="auditeur", personnes=["voix 5", "voix 3"]))
    scenes.clore_si_silence(mem, now=T0 + 10_000, embed=faux_embed)
    (_i, _t, f), = scenes_ecrites(mem)
    assert f["n"] == 2


def test_ce_qu_il_a_entendu_qui_arrive_apres_son_tour_n_est_pas_compte_deux_fois(mem):
    avancer(mem, tour(T0 + 15, "[voix 3] Tu as vu le match de ce soir avec l'arbitre ? [voix 5] Oui, quel penalty.", "No response requested.",
                      role="auditeur"))
    avancer(mem, entendu(T0, "voix 3", "Tu as vu le match de ce soir avec l'arbitre ?"))
    avancer(mem, tour(T0 + 40, "[voix 5] L'équipe a gagné. [voix 3] Le but.", "No response requested.", role="auditeur"))
    scenes.clore_si_silence(mem, now=T0 + 10_000, embed=faux_embed)
    (_i, _t, f), = scenes_ecrites(mem)
    assert f["n"] == 2


def test_temoin_d_absorption_coupee(mem, monkeypatch):
    monkeypatch.setattr(scenes, "_absorber", lambda sc, m: None)
    monkeypatch.setattr(scenes, "_deja_dans_un_tour", lambda sc, m: False)
    avancer(mem, entendu(T0, "voix 3", "Tu as vu le match de ce soir avec l'arbitre ?"))
    avancer(mem, tour(T0 + 15, "[voix 3] Tu as vu le match de ce soir avec l'arbitre ? [voix 5] Oui, quel penalty.", "No response requested.",
                      role="auditeur"))
    avancer(mem, tour(T0 + 40, "[voix 5] L'équipe a gagné. [voix 3] Le but.", "No response requested.", role="auditeur"))
    scenes.clore_si_silence(mem, now=T0 + 10_000, embed=faux_embed)
    assert scenes_ecrites(mem)[0][2]["n"] == 3, "sans l'absorption, le même moment compte deux fois"


def faire(mem, debut, place, qui, lieu="chez nous", live=False, sujet="vacances"):
    mots = " ".join(SUJETS[sujet])
    for k in range(3):
        if place == "temoin":
            avancer(mem, entendu(debut + k * 20, qui[k % len(qui)], f"On parle de {mots} ensemble", live=live) | {"lieu": lieu})
        else:
            avancer(mem, tour(debut + k * 20, f"Fiston, {mots} ?", f"Oui, {mots}.", role="implique", personnes=qui, live=live, lieu=lieu))
    scenes.clore_si_silence(mem, now=debut + 5000, embed=faux_embed)


def test_le_rappel_par_qui_par_place_par_jour_par_lieu_et_par_sujet_et_il_renforce(mem):
    faire(mem, T0 - 86400, "implique", ["papa"], sujet="code")                       # avant-hier soir (8/11) : avec papa
    faire(mem, T0, "temoin", ["Nina", "Sami"], sujet="vacances")                      # hier soir : Nina et Sami
    faire(mem, T0 + 3600, "temoin", ["voix 81", "voix 97"], live=True, sujet="foot")  # hier soir, plus tard : au live
    faire(mem, DEMAIN_MIDI - 3 * 3600, "implique", ["papa", "Nina"], sujet="foot")   # ce matin : papa et Nina
    r = lambda **k: scenes.rappeler(mem, now=DEMAIN_MIDI, embed=faux_embed, **k)        # noqa: E731
    assert len(r()) == 4 and r()[0].startswith("Aujourd'hui, 09:00")
    assert len(r(qui="papa et Nina")) == 1 and "tu parlais avec papa et Nina" in r(qui="papa et Nina")[0]
    assert len(r(qui="Ahmed")) == 2, "Ahmed, c'est papa"
    assert all("— témoin" in x for x in r(role="témoin")) and len(r(role="auditeur")) == 2
    assert len(r(role="impliqué")) == 2
    hier_soir = r(quand="hier soir")
    assert len(hier_soir) == 2 and all(x.startswith("Hier,") for x in hier_soir)
    assert len(r(quand="hier soir", role="témoin", qui="Nina")) == 1
    assert len(r(quand="ce matin")) == 1 and len(r(quand="le 8")) == 1
    live = r(lieu="au live")
    assert len(live) == 1 and "au live" in live[0] and "voix 81 et voix 97 parlaient entre eux" in live[0]
    assert "des citations, pas des faits" in live[0]
    assert r(sujet="le match et l'arbitre")[0].startswith(("Aujourd'hui", "Hier, 23:40")), "le sujet d'abord"
    faire(mem, T0 + 9000, "temoin", ["voix 12", "voix 3"], sujet="code")              # 01:10, après minuit : encore « hier soir »
    assert len(r(quand="hier soir")) == 3 and len(r(quand="hier")) == 2
    assert r(qui="quelqu'un d'inconnu") == []
    (avant,) = mem.db.execute("SELECT MAX(recall_count) FROM episodes WHERE scene IS NOT NULL").fetchone()
    assert avant >= 1, "rappeler une scène la renforce"


def test_la_scene_en_cours_se_rappelle_aussi(mem):
    avancer(mem, entendu(T0, "voix 81", "Le match de ce soir, quel but !", live=True))
    avancer(mem, entendu(T0 + 20, "voix 97", "L'arbitre, ce penalty !", live=True))
    (l,) = scenes.rappeler(mem, now=T0 + 60, embed=faux_embed)
    assert "(en cours)" in l and "au live" in l
    assert scenes.etat(mem, now=T0 + 60) == l


# ---- ses échanges : l'en-tête dit la vérité (témoin : avant le 10/11, « Échange avec Ahmed » même quand papa ne parlait pas)
@pytest.fixture
def mem_echanges(tmp_path):
    m = memory.Memory(db_path=tmp_path / "e.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def fe(t):
    v = [0.0] * 32
    for w in str(t).lower().split():
        v[hash(w) % 32] += 1.0
    return v


def contenus(m):
    return [r[0] for r in m.db.execute("SELECT content FROM episodes WHERE role='episodic' AND scene IS NULL ORDER BY id")]


def test_temoin_l_entete_dit_ce_qu_il_a_entendu_voix_par_voix(mem_echanges, tmp_path):
    f = tmp_path / "f.jsonl"
    echanges.deposer({"ts": T0 * 1000, "ahmed": "[voix 3] Il pleut ? [voix 5] Non, pas encore.", "hakim": "No response requested.",
                      "oral": True, "role": "auditeur", "personnes": ["voix 3", "voix 5"]}, f)
    echanges.deposer({"ts": (T0 + 60) * 1000, "ahmed": "[voix 114] C'est bon Hakim, c'est bon Hakim.", "hakim": "Merci, je t'entends.",
                      "oral": True, "role": "implique", "personnes": ["voix 114"]}, f)
    echanges.deposer({"ts": (T0 + 120) * 1000, "ahmed": "Fiston, tu fais quoi ?", "hakim": "Je t'écoute, papa.", "oral": True,
                      "role": "implique"}, f)
    assert echanges.passage(mem_echanges, f, embed=fe) == 3
    a, b, c = contenus(mem_echanges)
    assert a.startswith(f"[Entendu, témoin — {QUAND(T0)}, à l'oral, voix 3 et voix 5 parlaient entre eux, pas à lui] voix 3 : « Il pleut ? »")
    assert "Hakim n'a rien dit" in a and "Ahmed" not in a
    assert b.startswith(f"[Échange avec voix 114 — {QUAND(T0 + 60)}, à l'oral, papa ne disait rien] voix 114 : « C'est bon Hakim")
    assert c.startswith(f"[Échange avec Ahmed — {QUAND(T0 + 120)}, à l'oral] Ahmed : « Fiston, tu fais quoi ? »"), "avec papa : comme avant"


def test_une_ligne_d_avant_sans_place_est_relue_avec_la_meme_regle(mem_echanges, tmp_path):
    f = tmp_path / "f.jsonl"
    echanges.deposer({"ts": T0 * 1000, "ahmed": "[voix 12] Il pleut ?", "hakim": "Pas encore, je crois.", "oral": True}, f)
    echanges.deposer({"ts": (T0 + 60) * 1000, "ahmed": "Amen. … [voix 12] Give me some money.", "hakim": "Amen, papa.", "oral": True}, f)
    echanges.deposer({"ts": (T0 + 120) * 1000, "ahmed": "[voix 7] Hakim, t'es là ?", "hakim": "Oui !", "oral": True}, f)
    echanges.passage(mem_echanges, f, embed=fe)
    a, b, c = contenus(mem_echanges)
    assert a.startswith("[Entendu, témoin") and "Hakim (il a réagi) : « Pas encore, je crois. »" in a
    assert b.startswith("[Échange avec Ahmed"), "papa parlait (une voix autour) : son échange"
    assert c.startswith("[Échange avec voix 7")


def test_temoin_l_attention_vient_des_mots_de_papa_seulement(mem_echanges, tmp_path):
    f = tmp_path / "f.jsonl"
    echanges.deposer({"ts": T0 * 1000, "ahmed": "[voix 3] Retiens bien ça, c'est très important. [voix 5] D'accord.", "hakim": "No response requested.",
                      "oral": True, "role": "auditeur"}, f)
    echanges.passage(mem_echanges, f, embed=fe)
    (imp,) = mem_echanges.db.execute("SELECT importance FROM episodes WHERE role='episodic'").fetchone()
    explicite, _ = echanges.attention("Retiens bien ça, c'est très important. D'accord.", "")
    assert imp < explicite, "« retiens » d'une autre voix n'est pas la demande de papa"


def test_le_passage_fait_les_scenes_et_les_relie_a_leurs_echanges(mem_echanges, tmp_path, monkeypatch):
    monkeypatch.setattr(scenes, "ACTIF", True)
    f = tmp_path / "f.jsonl"
    vieux = T0 - 86400
    echanges.deposer(entendu(vieux, "Nina", "Le train pour Genève part samedi."), f)
    echanges.deposer({"ts": (vieux + 20) * 1000, "ahmed": "[Nina] Et la valise ? [Sami] Prête pour samedi.", "hakim": "No response requested.",
                      "oral": True, "role": "auditeur", "personnes": ["Nina", "Sami"]}, f)
    echanges.deposer({"ts": (vieux + 40) * 1000, "ahmed": "[Sami] Les vacances, enfin. [Nina] Oui, à Genève.", "hakim": "No response requested.",
                      "oral": True, "role": "auditeur", "personnes": ["Sami", "Nina"]}, f)
    monkeypatch.setattr(scenes, "_noms_connus", lambda: NOMS)
    assert echanges.passage(mem_echanges, f, embed=fe) == 2, "le moment entendu n'est pas un échange ; la scène est comptée à part"
    assert echanges.SCENES_ECRITES == 1
    (contenu, fiche), = mem_echanges.db.execute("SELECT content, scene FROM episodes WHERE scene IS NOT NULL").fetchall()
    fiche = json.loads(fiche)
    ids = [r[0] for r in mem_echanges.db.execute("SELECT id FROM episodes WHERE content LIKE '[Entendu, témoin%' ORDER BY id")]
    assert fiche["echanges"] == ids and fiche["n"] == 3 and fiche["place"] == "temoin"
    assert all(f"#{i}" in contenu for i in ids), "la scène nomme ses échanges au lieu de les recopier"
    assert echanges.passage(mem_echanges, f, embed=fe) == 0 and echanges.SCENES_ECRITES == 0


def test_l_outil_de_hakim(mem, monkeypatch):
    import memory as memory_mod
    monkeypatch.setattr(memory_mod, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", faux_embed, raising=False)
    import embeddings
    monkeypatch.setattr(embeddings, "embed", faux_embed)
    faire(mem, T0, "temoin", ["Nina", "Sami"])
    outil = mcp_server.mcp._tool_manager.get_tool("scenes_rappeler").fn
    r = outil(qui="Nina", role="témoin")
    assert r.startswith("- ") and "Nina et Sami parlaient entre eux" in r
    assert outil(qui="Nina", role="impliqué") == "(aucune scène pour qui : Nina, place : impliqué)"


def test_l_hippocampe_et_l_audit_lisent_les_nouveaux_en_tetes(mem_echanges):
    import audit_provenance
    import hippocampe
    q = QUAND(T0)
    ids = [mem_echanges.add("episodic", c, embedding=[], dedup=False) for c in (
        f"[Entendu, témoin — {q}, à l'oral, voix 3 et voix 5 parlaient entre eux, pas à lui] voix 3 : « Il pleut ? » · Hakim n'a rien dit",
        f"[Échange avec voix 7 — {q}, à l'oral, papa ne disait rien] voix 7 : « Hakim, t'es là ? » · Hakim : « Oui ! »",
        f"[Scène — {q} → 22:58, chez nous — témoin] Nina et Sami parlaient entre eux, sans s'adresser à toi.")]
    hippocampe.remplir(mem_echanges, embed=fe)
    traces = {r[0] for r in mem_echanges.db.execute("SELECT episode_id FROM hippocampe")}
    assert set(ids) <= traces, "ses scènes et ce qu'il a entendu ont leur trace, comme ses échanges"
    assert all(audit_provenance.EN_TETE.match(c) for c in [mem_echanges.db.execute("SELECT content FROM episodes WHERE id=?", (i,)).fetchone()[0]
                                                             for i in ids[:2]])
