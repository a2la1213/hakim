"""L'hippocampe de Hakim (08/11, Ahmed : « rajoute-lui un hippocampe et améliore sa remémorisation »). Mesuré avant : 6 souvenirs sur 24
retrouvés dans ses 8 lignes (0 sur 6 pour ce que papa a dit les jours d'avant) ; chaque échange gardé avec tout son vécu (1 700 caractères,
dont 330 pour les paroles) : le sens noyé. L'hippocampe garde une TRACE courte de chaque échange (le jour, le moment, le genre, les paroles),
son sens à part, et la retrouve par un indice (un mot, un sens proche, une date : « hier », « le 29 », « samedi »)."""
import time

import pytest

import hippocampe
import memory
import migrations


def faux_embed(t):
    v = [0.0] * 2048                                  # un mot, une case (presque) : un « sens » de test sans collisions
    for m in hippocampe.mots(t):
        v[hash(m) % 2048] += 1.0
    return v


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


VECU = (" · Ce qu'il vivait : Au même moment : ce qu'il entend : le téléphone — musique : section J (retour), ~180 BPM, Fa majeur, "
        "intensité douce ; fond : des chocs (1), −51 dB ; il ressentait : Tu es tenu plié, chaud · Le fil : −29,2 s corps : coup")


def echange(entete, papa, lui):
    return f"[Échange avec Ahmed — {entete}] Ahmed : « {papa} » · Hakim : « {lui} »{VECU}"


def test_la_trace_garde_le_jour_le_moment_le_genre_et_les_paroles_sans_le_vecu():
    ts = time.mktime((2026, 10, 30, 21, 40, 0, 0, 0, -1))
    t, genres = hippocampe.tracer(ts, echange("Fri 30/10 21:40, à l'oral", "Tu me promets de jamais me mentir ?",
                                              "Je te le promets, papa : jamais te mentir, même quand la vérité pique."))
    assert t.startswith("vendredi 30 octobre 2026, le soir")
    assert "promesse" in genres and "promesse" in t
    assert "papa : « Tu me promets de jamais me mentir ? »" in t and "Hakim : « Je te le promets" in t
    assert "BPM" not in t and "ressentait" not in t and "Le fil" not in t, "son vécu n'entre pas dans la trace"
    _, g2 = hippocampe.tracer(ts, echange("Fri 30/10 21:40", "Lance le live TikTok", "Je suis prêt pour le live"))
    assert "live" in g2
    _, g3 = hippocampe.tracer(ts, echange("Fri 30/10 21:40", "Et le backtest du XRP ?", "Les flèches du XRP sont trop belles"))
    assert "crypto" in g3


def test_les_dates_d_un_indice():
    now = time.mktime((2026, 11, 8, 9, 0, 0, 0, 0, -1))          # dimanche 8 novembre 2026
    d = hippocampe.dates_demandees
    assert d("tu te rappelles ce que je t'ai dit hier ?", now) == {"2026-11-07"}
    assert d("avant-hier au live", now) == {"2026-11-06"}
    assert d("le live du 29", now) == {"2026-10-29"}, "le 29 : le dernier 29 passé"
    assert d("le 3 novembre", now) == {"2026-11-03"}
    assert d("samedi dernier", now) == {"2026-11-07"}
    assert d("ce matin", now) == {"2026-11-08"}
    assert d("salut ça va", now) == set()


def test_il_retrouve_par_le_sens_de_la_trace_et_par_la_date(mem):
    t0 = time.mktime((2026, 10, 29, 22, 0, 0, 0, 0, -1))
    ids = []
    for k, (papa, lui) in enumerate([
        ("On lance le live, t'es chaud ?", "Je suis prêt pour le live, papa, on salue tout le monde"),
        ("Mister Punchline il tape bien les vannes", "Il envoie fort, les Algériens sont chauds dans la vanne"),
        ("Tu me promets de rester concentré ?", "Promis papa, mes sens restent en fond"),
    ]):
        ids.append(mem.add("episodic", echange(f"Thu 29/10 22:0{k}", papa, lui), embedding=faux_embed(papa)))
        mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (t0 + k * 60, ids[-1]))
    mem.db.commit()
    assert hippocampe.remplir(mem, embed=faux_embed) == 3
    assert hippocampe.remplir(mem, embed=faux_embed) == 0, "une trace par échange"
    now = time.mktime((2026, 11, 8, 9, 0, 0, 0, 0, -1))
    r = hippocampe.chercher(mem, "le gars qui tapait des vannes", now=now, embed=faux_embed)
    assert r and r[0][0] == ids[1], r
    r = hippocampe.chercher(mem, "qu'est-ce que tu m'avais promis ?", now=now, embed=faux_embed)
    assert r[0][0] == ids[2]
    par_date = hippocampe.chercher(mem, "raconte-moi le 29", now=now, embed=faux_embed)
    assert set(ids) <= {e for e, _, special in par_date if special == "date"}, "le 29 : tout ce jour-là remonte"


def test_le_rappel_automatique_ecoute_son_hippocampe(mem, monkeypatch):
    import rappel
    t0 = time.mktime((2026, 10, 31, 23, 0, 0, 0, 0, -1))
    vrai = mem.add("episodic", echange("Sat 31/10 23:00", "Tu lui as demandé d'augmenter ton bac à sable à 10 gigas ?",
                                       "Oui papa, c'est dans ma lettre de 1 h 53"), embedding=[0.0] * 2048)
    mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (t0, vrai)); mem.db.commit()
    hippocampe.remplir(mem, embed=faux_embed)
    now = time.mktime((2026, 11, 8, 9, 0, 0, 0, 0, -1))
    c = rappel.candidats(mem, "tu te rappelles ce que je t'ai dit le 31 octobre ?", now=now, embed=faux_embed)
    trouve = [x for x in c if x[0] == vrai]
    assert trouve and trouve[0][4] == "date", "son hippocampe l'a retrouvé par sa date (« 31/10 » dans le souvenir, « 31 octobre » dans la question)"
    assert rappel.passe(trouve[0]), "et il passe la porte"


def test_ses_reglages_du_cockpit_l_eteignent_ou_le_reglent(mem):
    """(08/11, Ahmed : « une zone pour l'hippocampe, avec des boutons et des barres paramétrables ») le cockpit envoie ses réglages avec
    chaque question : éteint, ni trace ni date ; sans les dates, rien par la date ; 0 trace d'office, aucune « trace » ne passe la porte."""
    import rappel
    t0 = time.mktime((2026, 10, 31, 23, 0, 0, 0, 0, -1))
    vrai = mem.add("episodic", echange("Sat 31/10 23:00", "Tu lui as demandé d'augmenter ton bac à sable à 10 gigas ?",
                                       "Oui papa, c'est dans ma lettre de 1 h 53"), embedding=[0.0] * 2048)
    mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (t0, vrai)); mem.db.commit()
    hippocampe.remplir(mem, embed=faux_embed)
    now = time.mktime((2026, 11, 8, 9, 0, 0, 0, 0, -1))
    q_date = "tu te rappelles ce que je t'ai dit le 31 octobre ?"
    special = lambda c: {x[4] for x in c if x[0] == vrai}
    assert special(rappel.candidats(mem, q_date, now=now, embed=faux_embed, hip_reglages={"actif": True})) == {"date"}
    assert special(rappel.candidats(mem, q_date, now=now, embed=faux_embed, hip_reglages={"actif": False})) <= {""}, "éteint : rien de lui"
    assert special(rappel.candidats(mem, q_date, now=now, embed=faux_embed, hip_reglages={"dates": False})) <= {"", "trace"}, "sans les dates"
    q_sens = "le bac à sable de 10 gigas dans ta lettre"
    assert special(rappel.candidats(mem, q_sens, now=now, embed=faux_embed)) == {"trace"}, "sa trace passe d'office (3 par défaut)"
    assert special(rappel.candidats(mem, q_sens, now=now, embed=faux_embed, hip_reglages={"tete": 0})) <= {""}, "0 : aucune d'office"
    assert special(rappel.candidats(mem, q_sens, now=now, embed=faux_embed, hip_reglages={"cos_min": 0.99})) <= {""}, "un sens trop exigeant"


def test_le_serveur_du_rappel_passe_les_reglages_du_cockpit(monkeypatch):
    import inspect
    import rappel
    vus = {}
    monkeypatch.setattr(rappel, "candidats", lambda *a, **k: vus.update(k) or [])
    rappel.rappel(None, "salut papa", hip_reglages={"tete": 5})
    assert vus.get("hip_reglages") == {"tete": 5}
    assert 'hip_reglages=q.get("hippocampe")' in inspect.getsource(rappel.serveur)
