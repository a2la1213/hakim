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
