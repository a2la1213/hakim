"""Le rappel automatique (rappel.py, 2026-10-21) : mots rares + sens, porte contre le banal, voix connues."""
import time
import zlib

import memory
import migrations
import rappel


def faux_embed(t):
    v = [0.0] * 256
    for m in str(t).lower().split():
        v[zlib.crc32(m.encode()) % 256] += 1.0
    return v


def _mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    vieux = time.time() - 5 * 86400
    for texte in ["[Ahmed, sa fille, 2026-10-16] Sa fille fête ses 6 ans le 3 mars",
                  "[Échange avec Ahmed] Nora est sa cousine, elle vient au live samedi",
                  "Le devis de la cuisine est envoyé", "Réglage du routeur de mémoire",
                  "La voix 10 s'appelle Nora"] + [f"note banale numéro {k} sur rien du tout" for k in range(40)]:
        eid = m.add("episodic", texte, embedding=faux_embed(texte), dedup=False)
        m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (vieux, eid))
    m.db.commit()
    return m


def test_mots_rares_et_porte(tmp_path):
    m = _mem(tmp_path)
    r = rappel.rappel(m, "j'ai un anniversaire ce soir, la fille fête ses 6 ans", embed=faux_embed)
    assert r["lignes"] and "fête ses 6 ans" in r["lignes"][0]
    assert rappel.rappel(m, "ok merci frero", embed=faux_embed)["lignes"] == []


def test_une_voix_connue_rappelle_ce_qui_la_nomme(tmp_path):
    m = _mem(tmp_path)
    assert rappel.noms_entendus("[Nora] salut tout le monde [voix 3] coucou [Ahmed] ok") == ["nora"]
    r = rappel.rappel(m, "[Nora] salut, ça va ?", embed=faux_embed)
    assert any("Nora est sa cousine" in l for l in r["lignes"])
    assert rappel.rappel(m, "[Nora] salut", exclus=r["ids"], embed=faux_embed)["ids"] == [] or \
        not set(rappel.rappel(m, "[Nora] salut", exclus=r["ids"], embed=faux_embed)["ids"]) & set(r["ids"])


def test_ce_qui_tombe_aujourd_hui_remonte(tmp_path):
    m = _mem(tmp_path)
    mars = time.mktime((2027, 3, 3, 12, 0, 0, 0, 0, -1))
    r = rappel.rappel(m, "salut frero", now=mars, embed=faux_embed)
    assert any("fête ses 6 ans le 3 mars" in l and "porte la date du jour" in l for l in r["lignes"])
    assert rappel.rappel(m, "salut frero", now=mars, exclus=r["ids"], embed=faux_embed)["lignes"] == []


def test_des_mots_de_conversation_ne_suffisent_pas(tmp_path):
    m = _mem(tmp_path)
    for t in ["tu as capté ce qui change, je suis content", "attends, ça vient, je suis content"]:
        eid = m.add("episodic", t, embedding=faux_embed(t), dedup=False)
        m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (time.time() - 5 * 86400, eid))
    m.db.commit()
    r = rappel.rappel(m, "attends t'as capté ce qui vient de changer ? je suis trop content", embed=faux_embed)
    assert not any("capté ce qui change" in l for l in r["lignes"])
