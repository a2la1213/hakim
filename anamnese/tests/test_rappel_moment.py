"""Le rappel du moment (11/11, Ahmed : « est-ce que son memory recall automatique intègre toutes les nouveautés ? » ; « la totale de chez
totale » ; « ses stimuli, ses réactions, ses réflexes, ses membres Bluetooth… le sismographe, le magnétomètre ») : ce que le cockpit sait du
moment entre dans la recherche ; en sortie, des souvenirs seulement, un ou deux par source. Chaque source a son témoin : sans le moment,
rien ne remonte. Les prénoms et les appareils sont inventés (dépôt public)."""
import io
import json
import sqlite3
import struct
import time
import zlib

import memory
import migrations
import rappel
import rappel_moment as RM
import scenes

NOW = time.mktime((2026, 11, 11, 5, 0, 0, 0, 0, -1))
VIEUX = NOW - 5 * 86400


def faux_embed(t):
    """Un sac de mots haché : le sens vient des mots partagés."""
    v = [0.0] * 128
    for m in rappel.mots_cles(str(t), maximum=80):
        v[zlib.crc32(rappel._plat(m).encode()) % 128] += 1.0
    return v if any(v) else [0.0] * 127 + [0.01]


def _ajouter(m, texte, ts=VIEUX):
    eid = m.add("episodic", texte, embedding=faux_embed(texte), dedup=False)
    m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (ts, eid))
    return eid


def _scene(m, debut, personnes, sujet, lieu="chez nous", live=False, place="implique"):
    f = {"v": 1, "debut": debut, "fin": debut + 600, "place": place, "part_impliquee": 1.0, "personnes": personnes, "arrivees": [],
         "lieu": lieu, "live": live, "sujet": sujet, "extraits": [{"qui": personnes[0], "texte": " ".join(sujet)}], "moments_cles": [],
         "musique": False, "emotions": [], "humeur_avant": "", "humeur_apres": "", "n": 4, "echanges": [], "externe": False, "fin_raison": "",
         "tiers": any(p != "papa" for p in personnes)}
    texte = scenes.texte_de(f)
    eid = _ajouter(m, texte, debut)
    scenes._assurer_colonne(m.db)
    m.db.execute("UPDATE episodes SET scene=? WHERE id=?", (json.dumps(f, ensure_ascii=False), eid))
    return eid


def _mem(tmp_path, banal=300):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    for k in range(banal):                              # sa vie ordinaire : chez nous, la pénombre, partout
        _ajouter(m, f"Échange ordinaire numéro {k} sur la journée · Ce qu'il vivait : lieu : chez nous ; la pénombre ; corps : coup_de_pression",
                 VIEUX - k * 60)
    m.db.commit()
    return m


def _du_moment(m, ctx, texte="Fiston, tu te souviens ?", **k):
    index = rappel.Index().rafraichir(m)
    mo = k.pop("moment", None) or RM.Moment(jarvis=k.pop("jarvis", None), base_fichiers=k.pop("base_fichiers", None))
    return RM.du_moment(m, index, mo, texte, ctx, now=NOW, embed=faux_embed, **k), index, mo


# ---- les scènes
def test_une_scene_avec_lala_remonte_quand_lala_est_la_en_ligne_de_film(tmp_path):
    m = _mem(tmp_path)
    eid = _scene(m, NOW - 86400 - 3600, ["papa", "Nora"], ["gâteau", "anniversaire", "bougies"])
    _scene(m, NOW - 2 * 86400, ["papa", "Nino"], ["match", "arbitre"])
    m.db.commit()
    r, _i, _m = _du_moment(m, {"presents": ["Nora"], "lieu": "chez nous", "requete": "Nora est là ; chez nous"})
    assert [x["id"] for x in r["scenes"]] == [eid]
    l = r["scenes"][0]["ligne"]
    assert l.startswith("Hier, 04:00, chez nous — impliqué") and "tu parlais avec papa et Nora" in l, l


def test_temoin_sans_le_moment_la_scene_de_lala_ne_remonte_pas(tmp_path):
    m = _mem(tmp_path)
    _scene(m, NOW - 86400 - 3600, ["papa", "Nora"], ["gâteau", "anniversaire", "bougies"])
    m.db.commit()
    assert _du_moment(m, {})[0] == {}, "sans contexte : rien de neuf (le rappel d'avant, tel quel)"
    r, _i, _m = _du_moment(m, {"presents": ["Nino"], "requete": "Nino est là"})
    assert r["scenes"] == [], "une autre personne : pas la scène de Nora"


def test_une_scene_de_la_conversation_en_cours_ne_remonte_pas_et_papa_seul_ne_suffit_pas(tmp_path):
    m = _mem(tmp_path)
    _scene(m, NOW - 900, ["papa", "Nora"], ["gâteau"])                    # finie il y a 5 min : encore dans sa conversation
    _scene(m, NOW - 86400, ["papa"], ["code", "serveur"])
    m.db.commit()
    r, _i, _m = _du_moment(m, {"presents": ["Nora", "papa"], "parle": "papa"})
    assert r["scenes"] == []


def test_la_voix_qui_parle_pendant_un_doute_ne_met_rien_en_avant(tmp_path):
    m = _mem(tmp_path)
    _scene(m, NOW - 86400, ["papa", "Ali"], ["secret", "santé"])
    _ajouter(m, "Ali m'a raconté son histoire de santé, un secret de famille")
    m.db.commit()
    r, _i, _m = _du_moment(m, {"parle": "Ali", "doute": True})
    assert r["scenes"] == [] and r["personnes"] == {}
    r2, _i, _m = _du_moment(m, {"parle": "Ali", "doute": False})          # témoin : sans le doute, la voix nommée rappelle
    assert r2["scenes"] and "Ali" in r2["personnes"]


# ---- les indices : membre Bluetooth, stimulus, capteur, réflexe, émotion (un témoin chacun)
CAS = [("membre", "jbl flip 9", "l'enceinte JBL Flip 9 branchée", "Bluetooth : JBL Flip 9 (relié) ; on a écouté la playlist du mariage"),
       ("stimulus", "corps : secousse", "une secousse", "corps : secousse ; il ressent : on te secoue fort, la voiture sur les pavés"),
       ("capteur", "champ magnétique", "un champ magnétique te traverse", "un champ magnétique te traverse ; près de l'aimant du frigo"),
       ("reflexe", "fou rire", "un réflexe de rire", "fou rire de papa sur la blague du chameau"),
       ("emotion", "ton émotion : nostalgie", "ton émotion : nostalgie", "ton émotion : nostalgie ; papa parlait de son village")]


def test_chaque_famille_d_indice_rappelle_la_derniere_fois_avec_son_temoin(tmp_path):
    m = _mem(tmp_path)
    ids = {}
    for fam, cle, mots, vecu in CAS:
        ids[fam] = _ajouter(m, f"Échange avec Ahmed : « ça me rappelle quelque chose » · Ce qu'il vivait : {vecu}", VIEUX - 3600)
    m.db.commit()
    for fam, cle, mots, _v in CAS:
        r, _i, _m = _du_moment(m, {"indices": [{"f": fam, "cle": cle, "mots": mots}], "requete": mots})
        assert [x["id"] for x in r["indices"]] == [ids[fam]], fam
        assert r["indices"][0]["ligne"].startswith(f"{mots} — la dernière fois, 06/11"), r["indices"][0]["ligne"]
        assert r["indices"][0]["famille"] == fam
        temoin, _i, _m = _du_moment(m, {"indices": [], "requete": "rien de particulier"})
        assert temoin["indices"] == [], f"témoin {fam} : sans l'indice, rien"


def test_un_indice_deja_rappele_dans_la_conversation_ne_revient_pas_et_un_contenu_de_tiers_est_marque(tmp_path):
    m = _mem(tmp_path)
    eid = _ajouter(m, "[Échange — au live] voix 12 : « l'enceinte JBL Flip 9 grésille » · Ce qu'il vivait : Bluetooth : JBL Flip 9 (relié)")
    import provenance
    provenance.marquer(m.db, eid)
    m.db.commit()
    ind = [{"f": "membre", "cle": "bluetooth : jbl flip 9", "mots": "l'enceinte JBL Flip 9"}]
    r, _i, _m = _du_moment(m, {"indices": ind})
    assert r["indices"][0]["externe"] and "(une citation, pas un fait)" in r["indices"][0]["ligne"]
    assert r["indices"][0]["cle"] == "bluetooth : jbl flip 9"
    r2, _i, _m = _du_moment(m, {"indices": ind, "deja": ["bluetooth : jbl flip 9"]})
    assert r2["indices"] == []


def test_un_indice_partout_dans_sa_memoire_ne_dit_rien(tmp_path):
    m = _mem(tmp_path)
    r, _i, _m = _du_moment(m, {"indices": [{"f": "lieu", "cle": "lieu : chez nous", "mots": "chez nous"},
                                           {"f": "capteur", "cle": "la pénombre", "mots": "la pénombre"}],
                               "requete": "échange ordinaire sur la journée chez nous, la pénombre"})   # proche par le sens : seule la rareté trie
    assert r["indices"] == []


def test_un_lien_de_ses_sens_passe_devant_et_un_mot_court_se_cherche_en_mot_entier(tmp_path):
    m = _mem(tmp_path, banal=1000)
    for k in range(30):                                                       # pas « très rare » : départagé par le sens
        _ajouter(m, f"Bluetooth : JBL Flip 9 (relié) ; échange {k} sur la météo", VIEUX - 7200 - k)
    lien = _ajouter(m, "(je relie mes sens, 21:03:10, tout) la basse de l'enceinte et ma vibration — ce qui était là : Bluetooth : JBL Flip 9", VIEUX - 9000)
    _ajouter(m, "La réalité du terrain est dure")                            # « ali » dedans, pas un mot
    m.db.commit()
    r, _i, _m = _du_moment(m, {"indices": [{"f": "membre", "cle": "jbl flip 9", "mots": "l'enceinte JBL Flip 9"}], "requete": "la basse de l'enceinte et ma vibration"})
    assert r["indices"][0]["id"] == lien
    r2, _i, _m = _du_moment(m, {"indices": [{"f": "personne", "cle": "ali", "mots": "Ali"}]})
    assert r2["indices"] == []


def test_lecture_seule_rien_n_est_renforce(tmp_path):
    m = _mem(tmp_path)
    _scene(m, NOW - 86400, ["papa", "Nora"], ["gâteau"])
    _ajouter(m, "Bluetooth : JBL Flip 9 (relié)")
    m.db.commit()
    avant = m.db.execute("SELECT SUM(recall_count) FROM episodes").fetchone()[0]
    r, _i, _m = _du_moment(m, {"presents": ["Nora"], "indices": [{"f": "membre", "cle": "jbl flip 9", "mots": "JBL"}]})
    assert r["scenes"] and r["indices"]
    assert m.db.execute("SELECT SUM(recall_count) FROM episodes").fetchone()[0] == avant


# ---- les personnes du moment
def test_la_voix_nommee_qui_parle_rappelle_un_souvenir_avec_elle(tmp_path):
    m = _mem(tmp_path)
    eid = _ajouter(m, "Nora m'a appris une comptine en kabyle")
    m.db.commit()
    r, _i, _m = _du_moment(m, {"parle": "Nora"})
    assert "Nora" in r["personnes"] and f"#{eid}" in r["personnes"]["Nora"][0]
    r2, _i, _m = _du_moment(m, {"parle": "Nora"}, deja_personnes=["Nora"])
    assert r2["personnes"] == {}, "déjà présentée dans ce tour : pas deux fois"
    r3, _i, _m = _du_moment(m, {"parle": "voix 12", "presents": ["papa"]})
    assert r3["personnes"] == {}, "ni une voix sans nom, ni papa"


def test_ce_que_je_sais_par_le_cache_mot_entier_et_meme_reponse(tmp_path):
    m = _mem(tmp_path, banal=5)
    _ajouter(m, "La réalité, c'est dur")
    a = _ajouter(m, "Tonton Ali vient dimanche")
    m.db.commit()
    index, cache = rappel.Index().rafraichir(m), RM.CacheIndices()
    vite = rappel.ce_que_je_sais(m, "Ali", now=NOW, journal=tmp_path / "rien.jsonl", index=index, cache=cache)
    assert len(vite) == 1 and f"#{a}" in vite[0], "« Ali » n'est pas dans « réalité »"
    lent = rappel.ce_que_je_sais(m, "Tonton Ali", now=NOW, journal=tmp_path / "rien.jsonl")
    assert rappel.ce_que_je_sais(m, "Tonton Ali", now=NOW, journal=tmp_path / "rien.jsonl", index=index, cache=cache) == lent


# ---- ses fichiers et ses sons
def _index_fichiers(tmp_path, docs):
    base = tmp_path / "index_fichiers.db"
    db = sqlite3.connect(str(base))
    db.execute("CREATE TABLE fichiers (chemin TEXT PRIMARY KEY, mtime REAL, taille INTEGER, titre TEXT, extrait TEXT, vecteur BLOB, indexe REAL)")
    for chemin, extrait in docs:
        v = faux_embed(extrait)
        db.execute("INSERT INTO fichiers VALUES (?,?,?,?,?,?,?)", (chemin, 0, 0, "", extrait, struct.pack(f"{len(v)}f", *v), 0))
    db.commit(); db.close()
    return base


def test_un_fichier_tres_proche_du_message_remonte_un_seul_et_son_temoin(tmp_path):
    m = _mem(tmp_path, banal=5)
    base = _index_fichiers(tmp_path, [("/Users/x/Documents/devis_cuisine_martin.pdf", "devis cuisine martin plan travail granit"),
                                      ("/Users/x/Documents/notes.md", "liste courses lait pain")])
    r, _i, _m = _du_moment(m, {"requete": ""}, texte="Le devis de la cuisine Martin en granit, plan de travail", base_fichiers=base)
    assert len(r["fichiers"]) == 1 and "devis_cuisine_martin.pdf" in r["fichiers"][0]["ligne"]
    r2, _i, _m = _du_moment(m, {"requete": ""}, texte="ok merci bonne nuit", base_fichiers=base)
    assert r2["fichiers"] == [], "témoin : un message banal n'ouvre aucun fichier"
    r3, _i, _m = _du_moment(m, {"requete": ""}, texte="plan de travail en granit pour la cuisine", base_fichiers=base)
    assert r3["fichiers"] == [], "témoin : proche par le sens mais pas nommé (« devis », « martin » absents du nom) : rien"


def test_un_son_nomme_dans_le_message_ou_par_la_musique(tmp_path):
    m = _mem(tmp_path, banal=5)
    (tmp_path / "sons.jsonl").write_text(json.dumps({"type": "nom", "extrait": "e19", "nom": "tambour", "sens": "Extrait choisi par papa",
                                                     "emotion": "joie"}) + "\n")
    r, _i, _m = _du_moment(m, {"requete": ""}, texte="Joue-moi le tambour", jarvis=tmp_path)
    assert r["sons"] and "« tambour »" in r["sons"][0] and "joie" in r["sons"][0]
    r2, _i, _m = _du_moment(m, {"indices": [{"f": "musique", "cle": "le tambour du désert", "mots": "« Le tambour du désert »"}]},
                            texte="c'est beau", jarvis=tmp_path)
    assert r2["sons"], "la musique qui joue le nomme"
    r3, _i, _m = _du_moment(m, {"requete": ""}, texte="c'est beau", jarvis=tmp_path)
    assert r3["sons"] == [], "témoin : sans son nom, rien"


# ---- ses notes : ce que le téléphone lui a fait entendre ou voir n'est jamais papa
def test_ses_traces_du_telephone_sont_marquees_et_sorties_quand_son_interieur_est_coupe(tmp_path):
    traces = tmp_path / "traces-entendues.jsonl"
    traces.write_text(json.dumps({"id": "T1", "ts": NOW - 4000, "source": "telephone", "texte": "le présentateur parle du tremblement de terre au Japon, la vague arrive sur la côte et la ville est évacuée"}) + "\n")
    cfg = tmp_path / "notes.json"
    cfg.write_text(json.dumps({"fichiers": [str(traces)]}))
    idx = rappel.IndexNotes(journal=tmp_path / "rien.jsonl", carnets=tmp_path / "carnets", config=cfg)
    r = rappel.notes_pertinentes("le présentateur parle du tremblement de terre au Japon", embed=faux_embed, index=idx, now=NOW)
    assert r["lignes"] and r["lignes"][0].startswith(rappel.MARQUE_TELEPHONE)
    coupe = rappel.notes_pertinentes("le présentateur parle du tremblement de terre au Japon", embed=faux_embed, index=idx, now=NOW, sans_telephone=True)
    assert coupe["lignes"] == []


def test_ses_notes_ne_relisent_que_ce_qui_a_change(tmp_path, monkeypatch):
    f = tmp_path / "carnets" / "a.md"
    f.parent.mkdir()
    f.write_text("# Recette\nLe couscous de mamie avec sept légumes")
    lus = []
    vrai = rappel._passages_fichier
    monkeypatch.setattr(rappel, "_passages_fichier", lambda p: lus.append(p) or vrai(p))
    idx = rappel.IndexNotes(journal=tmp_path / "rien.jsonl", carnets=tmp_path / "carnets", config=tmp_path / "rien.json")
    for _ in range(3):
        assert rappel.notes_pertinentes("le couscous de mamie", embed=faux_embed, index=idx, now=NOW)["lignes"]
    assert len(lus) == 1, "inchangé : relu une seule fois"
    f.write_text("# Recette\nLe couscous de mamie avec sept légumes et du piment")
    idx._liste = (0.0, None)
    rappel.notes_pertinentes("le couscous de mamie", embed=faux_embed, index=idx, now=NOW)
    assert len(lus) == 2, "changé : relu"


def test_le_journal_des_notes_ne_lit_que_sa_fin_neuve(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": (NOW - 3600) * 1000, "qui": "ahmed", "texte": "On ira voir la mer à Collioure ce week-end, avec les enfants et le chien, et on mangera des anchois sur le port"}) + "\n")
    idx = rappel.IndexNotes(journal=j, carnets=tmp_path / "c", config=tmp_path / "rien.json")
    assert rappel.notes_pertinentes("voir la mer à Collioure ce week-end avec les enfants et le chien", embed=faux_embed, index=idx, now=NOW)["lignes"]
    with open(j, "a") as h:
        h.write(json.dumps({"ts": (NOW - 3500) * 1000, "qui": "ahmed", "texte": "Et après Collioure on passera par Perpignan voir tonton et toute la famille, pour le déjeuner du dimanche midi"}) + "\n")
    r = rappel.notes_pertinentes("Perpignan voir tonton", embed=faux_embed, index=idx, now=NOW)
    assert any("Perpignan" in l for l in r["lignes"]) and len(idx.items) == 2


# ---- le serveur : le moment en plus, ses étapes mesurées ; sans contexte, la même réponse qu'avant
def test_le_serveur_rend_le_moment_et_ses_etapes(tmp_path, monkeypatch):
    m = _mem(tmp_path, banal=20)
    _scene(m, NOW - 86400, ["papa", "Nora"], ["gâteau", "anniversaire"])
    m.db.commit(); m.db.close()
    import embeddings
    vraie = memory.Memory
    monkeypatch.setattr(embeddings, "embed", faux_embed)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: vraie(db_path=tmp_path / "m.db"))
    monkeypatch.setattr(rappel, "JOURNAL_DU_JOUR", tmp_path / "rien.jsonl")
    monkeypatch.setattr(rappel, "VOIX_CONNUES", tmp_path / "rien.json")
    vide = {"lignes": [], "ids": [], "scores": []}
    monkeypatch.setattr(rappel, "erreurs_pertinentes", lambda *a, **k: vide)
    monkeypatch.setattr(rappel, "notes_pertinentes", lambda *a, **k: vide)
    monkeypatch.setattr(rappel, "jardin_pertinent", lambda *a, **k: vide)
    q1 = {"texte": "Fiston, le gâteau d'anniversaire", "now": NOW}
    q2 = dict(q1, contexte={"presents": ["Nora"], "requete": "Nora est là", "fichiers": False})
    sortie = io.StringIO()
    rappel.serveur(io.StringIO(json.dumps(q1) + "\n" + json.dumps(q2) + "\n"), sortie)
    r1, r2 = [json.loads(l) for l in sortie.getvalue().splitlines()]
    assert "moment" not in r1 and r1["etapes"]["total"] >= 0
    assert r2["moment"]["scenes"] and "Nora" in r2["moment"]["scenes"][0]["ligne"]
    assert {"rappel", "notes", "moment", "total"} <= set(r2["etapes"])
    sans = lambda r: {k: v for k, v in r.items() if k not in ("etapes", "ms", "moment")}   # noqa: E731
    assert sans(r1) == sans(r2), "le reste du rappel ne change pas"
    sid = r2["moment"]["scenes"][0]["id"]
    if sid in r1["ids"]:                                  # la scène venue par le balayage ordinaire : sa ligne de film, pour le cockpit
        assert r1["films"][str(sid)].startswith("Hier,")


# ---- le temps : le rappel du moment tient dans son budget, et ses caches le rendent presque gratuit au tour suivant
def test_le_rappel_du_moment_tient_son_budget_et_se_rapide_au_tour_suivant(tmp_path):
    m = _mem(tmp_path, banal=3000)
    for k in range(5):
        _scene(m, NOW - (k + 1) * 86400, ["papa", f"Ami{k}"], ["sujet", str(k)])
    m.db.commit()
    ctx = {"presents": ["Ami2"], "lieu": "chez nous", "requete": "Ami2 est là ; la musique joue",
           "indices": [{"f": f, "cle": c, "mots": w} for f, c, w, _v in CAS]}
    index = rappel.Index().rafraichir(m)
    mo = RM.Moment(jarvis=tmp_path, base_fichiers=tmp_path / "absent.db")
    t = time.time(); r = RM.du_moment(m, index, mo, "Fiston, tu te souviens ?", ctx, now=NOW, embed=faux_embed); premier = time.time() - t
    t = time.time(); r2 = RM.du_moment(m, index, mo, "Fiston, tu te souviens ?", ctx, now=NOW, embed=faux_embed); second = time.time() - t
    assert r["scenes"] and r2["scenes"] == r["scenes"]
    assert premier < RM.BUDGET_MS / 1000 + 0.15, f"premier tour : {premier:.3f} s"
    assert second < 0.05, f"au même endroit, presque gratuit : {second:.3f} s"
