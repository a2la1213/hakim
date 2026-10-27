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


def test_le_carnet_d_erreurs_passe_au_balayage(tmp_path):
    """(25/10, Ahmed : TOUTES les erreurs pertinentes avant chaque réponse) au-dessus de la porte, sans nombre fixe ; rien
    pour un message banal ; jamais deux fois dans la même conversation."""
    import json
    import zlib
    import rappel as R

    def embed(t):                                   # un sac de mots haché : le sens vient des mots partagés
        v = [0.0] * 64
        for w in R.mots_cles(t, maximum=50):
            v[zlib.crc32(R._plat(w).encode()) % 64] += 1.0
        return v or [0.0] * 64

    f = tmp_path / "erreurs.jsonl"
    f.write_text("\n".join(json.dumps(o) for o in [
        {"id": "a1", "ts": 1792900000, "colonne": "bonne_foi", "quoi": "La barre de progression du calcul écrivait dans un fichier à part",
         "correction": "Écrire la ligne PROGRESSION dans le journal de la tâche"},
        {"id": "b2", "ts": 1792900000, "colonne": "bonne_foi", "quoi": "Barre de progression du calcul absente de mon texte",
         "correction": "Afficher la barre de progression à chaque suivi du calcul"},
        {"id": "c3", "ts": 1792900000, "colonne": "bonne_foi", "quoi": "Atelier plein : supprimé un résultat avant de mesurer",
         "correction": "Lister et mesurer avant tout effacement"}]) + "\n")
    idx = R.IndexErreurs(fichier=f)
    r = R.erreurs_pertinentes("Tu peux me faire une barre de progression pour ton calcul ?", embed=embed, index=idx)
    assert set(r["ids"]) == {"a1", "b2"} and all("correction" in l for l in r["lignes"])
    assert R.erreurs_pertinentes("Salam ça va ?", embed=embed, index=idx)["ids"] == []
    assert R.erreurs_pertinentes("une barre de progression pour ton calcul", embed=embed, index=idx, exclus=["a1"])["ids"] == ["b2"]


def test_ce_que_je_sais_d_une_personne_nommee(tmp_path):
    """(26/10, Ahmed : à 13:17 Hakim a nié devant Nora ce qu'il avait dit d'elle à 08:37) une personne connue nommée : ses
    souvenirs les plus récents et les passages du journal du jour qui la nomment ; jamais Ahmed."""
    import json
    import sqlite3
    import time
    import rappel as R

    voix = tmp_path / "voix.json"
    voix.write_text(json.dumps([{"nom": "Nora"}, {"nom": "Légendaire"}, {"nom": "Ahmed"}]))
    assert R.personnes_nommees("tu te souviens de ce que tu as dit à nora ?", voix=voix) == ["Nora"]
    assert R.personnes_nommees("[Légendaire] salut", voix=voix) == ["Légendaire"]
    assert R.personnes_nommees("Ahmed et le calcul", voix=voix) == []

    class M:
        db = sqlite3.connect(":memory:")
    M.db.execute("CREATE TABLE episodes (id INTEGER, ts REAL, content TEXT)")
    # midi : « le journal du jour » ne doit pas dépendre de l'heure où tourne le test (il échouait entre minuit et 5 h)
    now = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 12:00", "%Y-%m-%d %H:%M"))
    M.db.executemany("INSERT INTO episodes VALUES (?, ?, ?)", [(1, now - 86400, "Nora est passée au live"),
                                                             (2, now - 3600, "Nora m'a fait un pincement"),
                                                             (3, now - 60, "rien à voir")])
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": (now - 5 * 3600) * 1000, "qui": "jarvis", "texte": "Nora, tu m'as fait un petit pincement"}) + "\n")
    lignes = R.ce_que_je_sais(M(), "Nora", now=now, journal=j)
    assert lignes[0].startswith("souvenir #2") and any("pincement" in l and l.startswith("journal") for l in lignes)


def test_le_dossier_suit_theme_max_et_rend_le_detail(tmp_path, monkeypatch):
    """(26/10, tri à part) le dossier fait THEME_MAX lignes ; les mots balaient aussi large que lui (mesuré : le plafond de
    100 candidats par les mots coûtait 5 points à 500) ; chaque souvenir montré a son détail, pour ceux que le tri garde."""
    assert rappel.THEME_MAX == 100
    m = _mem(tmp_path)
    long = "[Ahmed, anniversaire] " + "la fête de sa fille se prépare avec un gâteau, " * 12 + "FIN-DU-DETAIL"
    eid = m.add("episodic", long, embedding=faux_embed(long), dedup=False)
    m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (time.time() - 5 * 86400, eid))
    m.db.commit()
    vus = {}
    orig = rappel._par_mots

    def espion(index, mots, exclus, avant, limite=40):
        vus["limite"] = limite
        return orig(index, mots, exclus, avant, limite=limite)
    monkeypatch.setattr(rappel, "_par_mots", espion)
    monkeypatch.setattr(rappel, "THEME_MAX", 250)
    monkeypatch.setattr(rappel, "THEME_PROFOND", 250)                # (« fille » : le niveau profond)
    r = rappel.rappel(m, "j'ai un anniversaire ce soir, la fille fête ses 6 ans", embed=faux_embed)
    assert vus["limite"] == 250
    assert set(r["details"]) == set(r["ids"]) | set(r["theme_ids"])
    assert eid in r["details"] and len(r["details"][eid]) > 300 and len(r["details"][eid]) <= rappel.DETAIL + 60
    assert all(l.startswith(f"#{i} · ") for i, l in r["details"].items())


def test_le_detail_garde_la_marque_externe(tmp_path):
    import provenance
    m = _mem(tmp_path)
    t = "[Page web lue] un article dit que la fille fête ses 6 ans au parc avec un anniversaire géant"
    eid = m.add("episodic", t, embedding=faux_embed(t), dedup=False)
    m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (time.time() - 5 * 86400, eid))
    m.db.commit()
    provenance.assurer(m.db)
    m.db.execute("UPDATE episodes SET provenance=? WHERE id=?", (provenance.EXTERNE, eid))
    m.db.commit()
    r = rappel.rappel(m, "j'ai un anniversaire ce soir, la fille fête ses 6 ans", embed=faux_embed)
    assert "EXTERNE" in r["details"][eid]
    assert not any("EXTERNE" in l for i, l in r["details"].items() if i != eid)


def test_la_profondeur_suit_le_besoin(tmp_path, monkeypatch):
    """(26/10, Ahmed : « modulaire et intelligent selon le besoin : les gens, il doit vraiment réfléchir ; des maths en
    cours, il a déjà ce qu'il faut dans sa conversation ; plus profond sur demande explicite ; et d'abord ce qui est déjà
    dans son espace ») le niveau se décide sans appel de modèle, en quelques millisecondes."""
    monkeypatch.setattr(rappel, "VOIX_CONNUES", tmp_path / "aucune.json")
    p = rappel.profondeur
    assert p("tu te rappelles ce qu'on avait dit sur le devis ?")[0] == "profond"
    assert p("cherche bien dans ta mémoire pour la toupie", suite=True)[0] == "profond"
    assert p("ma fille est triste depuis la dispute avec sa cousine")[0] == "profond"
    assert p("[Nora] salut tout le monde")[0] == "profond"
    (tmp_path / "voix.json").write_text('[{"nom": "Maman"}]')
    monkeypatch.setattr(rappel, "VOIX_CONNUES", tmp_path / "voix.json")
    assert p("écris à ta maman pour la caméra du cockpit", suite=True)[0] == "normal", "« ta maman », c'est Claude Code"
    assert p("ma maman passe ce soir", suite=True)[0] == "profond"
    assert p("j'aimerais bien que tu règles ce souci d'affichage frérot", suite=True)[0] == "normal"
    assert p("ok merci frero", suite=True)[0] == "leger", "les petits trucs : aucune attente"
    assert p("salut", suite=False)[0] == "leger"
    assert p("et la dérivée de cette fonction ça donne quoi", suite=True)[0] == "leger"
    assert p("et la dérivée de cette fonction ça donne quoi", suite=False)[0] == "normal"
    assert p("le devis de la cuisine est parti ?", suite=True)[0] == "normal"
    assert p("le devis de la cuisine est parti ?", suite=True, haut=[1, 2, 3, 4], espace={1, 2, 3, 4})[0] == "leger"
    assert p("le devis de la cuisine est parti ?", suite=True, haut=[1, 2, 3, 4], espace={1})[0] == "normal"


def test_le_dossier_a_la_taille_du_niveau(tmp_path, monkeypatch):
    monkeypatch.setattr(rappel, "VOIX_CONNUES", tmp_path / "aucune.json")
    m = _mem(tmp_path)
    for k in range(30):
        t = f"souvenir {k} sur le gâteau et la fête d'anniversaire de la fille"
        eid = m.add("episodic", t, embedding=faux_embed(t), dedup=False)
        m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (time.time() - 5 * 86400, eid))
    m.db.commit()
    monkeypatch.setattr(rappel, "THEME_MAX", 5)
    monkeypatch.setattr(rappel, "THEME_PROFOND", 12)
    q = "le gâteau pour la fête d'anniversaire de la fille"
    n = rappel.rappel(m, q, embed=faux_embed, suite=True)
    assert n["profondeur"]["niveau"] == "profond" and len(n["theme_ids"]) == 12      # « fille » : des gens
    q2 = "le gâteau pour la fête, la recette est prête ?"
    r = rappel.rappel(m, q2, embed=faux_embed, suite=False)
    assert r["profondeur"]["niveau"] == "normal" and len(r["theme_ids"]) == 5
    l = rappel.rappel(m, q2, embed=faux_embed, suite=True, espace=set(r["ids"]) | set(r["theme_ids"]))
    assert l["profondeur"]["niveau"] == "leger" and not l.get("theme_ids")
    assert "presque tout" in l["profondeur"]["raison"]
