"""La boucle de retour, niveau 1 minimal (boucle_retour.py, accord d'Ahmed le 2026-10-22) : elle note, ne modifie rien."""
import json

import boucle_retour as B
import memory
import migrations

T = 1_800_000_000.0


def _mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    return m


def test_propose_utilise_par_lecture_ou_recouvrement_puis_correction(tmp_path):
    m = _mem(tmp_path)
    cafe = m.add("episodic", "Ahmed boit son café serré chaque matin vers sept heures à Exempleville", embedding=[])
    robot = m.add("episodic", "Le robot ressent ses hormones par équations différentielles", embedding=[])
    rien = m.add("episodic", "Un devis de cuisine envoyé au client", embedding=[])
    avant = (m.db.execute("SELECT COUNT(*), SUM(importance) FROM episodes").fetchone())
    conv = {"messages": [
        {"id": T * 1000, "ts": T * 1000, "qui": "u", "texte": "Tu te souviens de mes habitudes ?"},
        {"id": T * 1000 + 300, "qui": "j", "texte": "Oui : ton café serré chaque matin, vers sept heures."},
        {"id": (T + 60) * 1000, "ts": (T + 60) * 1000, "qui": "u", "texte": "Non, c'est pas ça, je bois du thé maintenant."}]}
    bal = [{"ts": (T + 0.4) * 1000, "ids": [cafe, robot, rien]}]
    lec = [{"ts": T + 5, "ids": [robot]}]
    ev = B.evenements(m, T - 10, T + 3600, conversation=conv, balayages=bal, lectures=lec, rates=[], importants=[])
    types = [(e["type"], e["souvenir"], e["source"]) for e in ev]
    assert ("propose", rien, "balayage") in types and ("indice", rien, "recouvrement") not in types
    assert ("indice", cafe, "recouvrement") in types and ("utilise", cafe, "recouvrement") not in types   # un indice, pas un usage
    assert ("utilise", robot, "lecture") in types
    assert ("correction", robot, "ahmed") in types and ("correction", cafe, "ahmed") not in types
    assert m.db.execute("SELECT COUNT(*), SUM(importance) FROM episodes").fetchone() == avant      # rien de modifié


def test_la_nuit_ecrit_ses_evenements_et_compte_les_nuits(tmp_path):
    m = _mem(tmp_path)
    s = m.add("episodic", "Sa fille fête ses six ans le vingt et un octobre", embedding=[])
    sources = dict(conversation={"messages": [{"id": T * 1000, "ts": T * 1000, "qui": "u", "texte": "c'est quand déjà ?"},
                                              {"id": T * 1000 + 100, "qui": "j", "texte": "Ta fille fête ses six ans le vingt et un octobre."}]},
                   balayages=[{"ts": T * 1000, "ids": [s]}], lectures=[{"ts": T + 2, "ids": [s]}], importants=[],
                   rates=[{"ts": T + 30, "type": "rate", "ids": [s]}, {"ts": T + 40, "type": "recherche", "hors_balayage": [99]}])
    b = B.nuit(m, T + 3600, tmp_path / "boucle", **sources)
    assert b["nuit"] == 1 and b["proposes"] == 1 and b["utilises"] == 1 and b["rates_hakim"] == 1 and b["rates_indices"] == 1
    assert b["regles"] == B.empreinte_regles()
    b2 = B.nuit(m, T + 90000, tmp_path / "boucle", **sources)
    assert b2["nuit"] == 2 and b2["proposes"] == 0                     # la période suivante : rien de neuf
    assert "2 nuit(s)" in B.resume(tmp_path / "boucle")


def test_les_tours_viennent_du_journal_brut_et_de_ses_archives(tmp_path):
    (tmp_path / "archives").mkdir()
    ligne = lambda t, qui, texte: json.dumps({"ts": t * 1000, "qui": qui, "texte": texte}) + "\n"   # noqa: E731
    (tmp_path / "archives" / "journal-2027-01.jsonl").write_text(ligne(T, "ahmed", "le matin") + ligne(T + 5, "jarvis", "réponse du matin"))
    (tmp_path / "journal.jsonl").write_text(ligne(T + 5, "jarvis", "réponse du matin")                     # en double : gardé une fois
                                            + ligne(T + 50, "jarvis", "(tour de lui-même, sans texte)")
                                            + ligne(T + 60, "ahmed", "le soir") + ligne(T + 61, "jarvis", "Voilà. [de lui-même : courrier]")
                                            + ligne(T + 62, "jarvis", "réponse du soir"))
    c = B.journal_brut(T - 10, T + 100, tmp_path)
    assert [(m["qui"], m["texte"]) for m in c["messages"]] == [("u", "le matin"), ("j", "réponse du matin"), ("u", "le soir"),
                                                               ("j", "réponse du soir")]
    assert [(m["texte"], r["texte"]) for m, r, *_ in B.tours(c)] == [("le matin", "réponse du matin"), ("le soir", "réponse du soir")]


def test_la_balise_souvenirs_compte_comme_usage(tmp_path):
    m = _mem(tmp_path)
    a = m.add("episodic", "Ahmed prépare un live le vendredi matin", embedding=[])
    b = m.add("episodic", "Le carnet bleu est rangé dans le tiroir du bureau", embedding=[])
    conv = {"messages": [{"id": T * 1000, "ts": T * 1000, "qui": "u", "texte": "on fait quoi demain ?"},
                         {"id": T * 1000 + 300, "qui": "j", "texte": "Ton live du vendredi."}]}
    ev = B.evenements(m, T - 10, T + 3600, conversation=conv, balayages=[{"ts": T * 1000, "ids": [a]}], lectures=[],
                      rates=[], importants=[], balises=[{"ts": T + 20, "ids": [a, b]}])
    types = {(e["type"], e["souvenir"], e["source"]) for e in ev}
    assert ("utilise", a, "balise") in types and ("utilise", b, "balise") in types   # b : proposé plus tôt dans la conversation


def test_une_nouvelle_serie_repart_de_zero(tmp_path):
    m = _mem(tmp_path)
    vide = dict(conversation={"messages": []}, balayages=[], lectures=[], rates=[], importants=[], balises=[])
    d = tmp_path / "boucle"
    d.mkdir()
    (d / "nuits.jsonl").write_text(json.dumps({"nuit": 1, "jusqua": T, "regles": "ancienne"}) + "\n")
    b = B.nuit(m, T + 86400, d, **vide)
    assert b["nuit"] == 2 and b["nuit_de_la_serie"] == 1 and b["utilises_balise"] == 0
    assert B.nuit(m, T + 2 * 86400, d, **vide)["nuit_de_la_serie"] == 2
