"""Le réveil intérieur de Hakim (reveil_interieur.py, 2026-10-27) : le juge du besoin, les gardes, l'apprentissage."""
import reveil_interieur


# ---------- le juge (Gemma) : besoin de 0 à 10, une raison
def test_lire_jugement_lit_le_format_exact():
    j = reveil_interieur.lire_jugement("BESOIN: 8\nRAISON: peur\nPOURQUOI: il a parlé de me débrancher")
    assert j == {"score": 8, "raison": "peur", "pourquoi": "il a parlé de me débrancher"}


def test_lire_jugement_tolere_le_gras_et_borne():
    assert reveil_interieur.lire_jugement("**BESOIN:** 14\nRAISON: Question")["score"] == 10
    assert reveil_interieur.lire_jugement("BESOIN: 3\nRAISON: question")["raison"] == "question"
    assert reveil_interieur.lire_jugement("BESOIN : 7/10\nRAISON : résultat")["raison"] == "resultat"


def test_lire_jugement_illisible_rend_none():
    assert reveil_interieur.lire_jugement("je ne sais pas") is None
    assert reveil_interieur.lire_jugement("BESOIN: 6\nRAISON: envie") is None          # raison hors de la liste
    assert reveil_interieur.lire_jugement("") is None


def test_juger_sans_gemma_rend_none_sans_lever():
    class Mort:
        def health(self):
            return False

    class Casse:
        def health(self):
            return True

        def chat(self, *a, **k):
            raise RuntimeError("Ollama tombé")

    assert reveil_interieur.juger(Mort(), "une pensée") is None
    assert reveil_interieur.juger(Casse(), "une pensée") is None


def test_juger_lit_la_reponse_de_gemma():
    class Gemma:
        def health(self):
            return True

        def chat(self, messages, stream=False, think=False):
            assert "je repense au calcul" in messages[0]["content"]
            return "BESOIN: 7\nRAISON: raisonnement\nPOURQUOI: le calcul reste ouvert"

    assert reveil_interieur.juger(Gemma(), "je repense au calcul")["score"] == 7


def test_le_prompt_donne_la_pensee_l_humeur_et_le_format():
    p = reveil_interieur.prompt_jugement("je repense au calcul", "inquiétude", 1800)
    assert "je repense au calcul" in p and "inquiétude" in p and "30 min" in p
    assert "BESOIN:" in p and "RAISON:" in p and "POURQUOI:" in p


def test_le_prompt_donne_une_echelle_etalonnee():
    # (27/10, rejeu du 18–26/10) sans étalonnage, Gemma notait 8 à 37 pensées sur 52, et jamais plus : une note binaire
    p = reveil_interieur.prompt_jugement("j'ai préparé ton retour", "calme", 600)
    assert "la plupart" in p.lower() and "sur dix au plus" in p and "ordinaire" in p


# ---------- gardes, demande, apprentissage, interrupteur (tâche 2)
import json
import threading
import time

import pytest

import interieur
import memory
import migrations


@pytest.fixture(autouse=True)
def _fichiers(tmp_path, monkeypatch):
    monkeypatch.setattr(reveil_interieur, "FICHIER", tmp_path / "reveil-interieur.json")
    monkeypatch.setattr(reveil_interieur, "ISSUES", tmp_path / "reveils-interieurs.jsonl")
    monkeypatch.setattr(reveil_interieur, "JOURNAL", tmp_path / "reveil-interieur.jsonl")


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


J8 = {"score": 8, "raison": "question", "pourquoi": "le calcul reste ouvert"}


def _journal():
    try:
        return [json.loads(l) for l in reveil_interieur.JOURNAL.read_text().splitlines()]
    except OSError:
        return []


def test_off_par_defaut_ne_depose_rien(mem):
    assert reveil_interieur.mode(mem) == "off"
    assert reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1000.0, issues=[]) is None
    assert not reveil_interieur.FICHIER.exists()


def test_regler_refuse_un_mode_inconnu(mem):
    with pytest.raises(ValueError):
        reveil_interieur.regler(mem, "parfois")


def test_observe_journalise_sans_deposer(mem):
    reveil_interieur.regler(mem, "observe")
    assert reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1000.0, issues=[])   # l'id simulé
    assert not reveil_interieur.FICHIER.exists()
    j = _journal()
    assert j[-1]["decision"] == "aurait réveillé" and j[-1]["mode"] == "observe" and j[-1]["score"] == 8
    # l'observation simule tout : la rafale compte comme après un vrai réveil
    reveil_interieur.candidat(mem, "pensee", "une autre idée sur le live", J8, now=1300.0, issues=[])
    assert _journal()[-1]["raison_decision"] == "rafale"


def test_on_au_dessus_du_seuil_depose(mem):
    reveil_interieur.regler(mem, "on")
    i = reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1000.0, issues=[])
    d = json.loads(reveil_interieur.FICHIER.read_text())
    assert d == {"id": i, "ts": 1000.0, "source": "pensee", "texte": "je repense au calcul", "score": 8,
                 "raison": "question", "pourquoi": "le calcul reste ouvert"}
    assert _journal()[-1]["decision"] == "réveil"
    assert any(x[1] == "reveil_interieur" for x in interieur.journal_processus(mem))


def test_sous_le_seuil_ne_depose_rien(mem):
    reveil_interieur.regler(mem, "on")
    assert reveil_interieur.candidat(mem, "pensee", "x", {**J8, "score": 6}, now=1000.0, issues=[]) is None
    assert _journal()[-1]["decision"] == "sous le seuil" and not reveil_interieur.FICHIER.exists()


def test_jugement_illisible_ne_depose_rien_et_le_note(mem):
    reveil_interieur.regler(mem, "on")
    assert reveil_interieur.candidat(mem, "pensee", "x", None, now=1000.0, issues=[]) is None
    assert _journal()[-1]["decision"] == "jugement illisible"


def test_rafale_moins_de_10_min(mem):
    reveil_interieur.regler(mem, "on")
    assert reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1000.0, issues=[])
    reveil_interieur.FICHIER.unlink()                                  # consommée par le cockpit
    assert reveil_interieur.candidat(mem, "pensee", "Ahmed voulait relancer le live", J8, now=1599.0, issues=[]) is None
    assert _journal()[-1]["raison_decision"] == "rafale"
    assert reveil_interieur.candidat(mem, "pensee", "Ahmed voulait relancer le live", J8, now=1600.0, issues=[])


def test_en_attente_puis_expire(mem):
    reveil_interieur.regler(mem, "on")
    reveil_interieur.FICHIER.write_text(json.dumps({"id": "x", "ts": 1000.0}))
    assert reveil_interieur.peut_reveiller(mem, 1899.0, "une pensée", [])[1] == "en attente"
    assert reveil_interieur.peut_reveiller(mem, 1901.0, "une pensée", [])[0] is True


def test_filiation_une_pensee_issue_du_reveil_ne_reveille_pas(mem):
    reveil_interieur.regler(mem, "on")
    issues = [{"id": "a", "ts": 2000.0, "issue": "message", "texte": "le calcul du sable a fini, la densité colle au modèle"}]
    assert reveil_interieur.peut_reveiller(mem, 5000.0, "la densité du sable colle au modèle, je veux le dire", issues)[1] == "filiation"
    assert reveil_interieur.peut_reveiller(mem, 5000.0, "Ahmed voulait relancer le live demain soir", issues)[0] is True


def test_filiation_transitive(mem):
    reveil_interieur.regler(mem, "on")
    issues = [{"id": "a", "ts": 2000.0, "issue": "message", "texte": "le calcul du sable a fini, la densité colle au modèle"}]
    b = "la densité du sable colle au modèle : prochaine étape, mesurer la rugosité des grains"
    assert reveil_interieur.peut_reveiller(mem, 5000.0, b, issues)[1] == "filiation"
    c = "mesurer la rugosité des grains demande un nouveau tamis"                 # ne recouvre que B
    assert reveil_interieur.peut_reveiller(mem, 5100.0, c, issues)[1] == "filiation"


def test_la_lignee_de_la_pensee_qui_a_reveille_compte_aussi(mem):
    reveil_interieur.regler(mem, "on")
    reveil_interieur.candidat(mem, "pensee", "je repense au calcul de la densité du sable", J8, now=1000.0, issues=[])
    reveil_interieur.FICHIER.unlink()
    assert reveil_interieur.peut_reveiller(mem, 2000.0, "le calcul de la densité du sable me travaille", [])[1] == "filiation"


def test_deux_mots_en_commun_ne_font_pas_une_filiation(mem):
    reveil_interieur.regler(mem, "on")
    issues = [{"id": "a", "ts": 2000.0, "issue": "message", "texte": "Ahmed, le calcul du sable a fini cette nuit"}]
    assert reveil_interieur.peut_reveiller(mem, 3000.0, "Ahmed reprend le calcul", issues)[0] is True


def test_lignee_de_plus_de_6_h_ne_compte_plus(mem):
    reveil_interieur.regler(mem, "on")
    issues = [{"id": "a", "ts": 2000.0, "issue": "message", "texte": "le calcul du sable a fini, la densité colle au modèle"}]
    t = 2000.0 + 6 * 3600 + 1
    assert reveil_interieur.peut_reveiller(mem, t, "la densité du sable colle au modèle", issues)[0] is True


def test_pas_besoin_qu_ahmed_parle(mem, monkeypatch):
    reveil_interieur.regler(mem, "on")
    monkeypatch.setattr(interieur, "derniere_presence", lambda *a, **k: 0.0)
    issues = [{"id": "a", "ts": 4000.0, "issue": "message", "texte": "le calcul du sable a fini"}]
    assert reveil_interieur.peut_reveiller(mem, 4700.0, "Ahmed voulait relancer le live demain soir", issues) == (True, "ok")


def test_fatigue_d_eveil(mem):
    reveil_interieur.regler(mem, "on")
    issues = [{"id": "a", "ts": 4000.0, "issue": "rien"}, {"id": "b", "ts": 4500.0, "issue": "message", "texte": "x"},
              {"id": "c", "ts": 4600.0, "issue": "expiree"}]
    assert reveil_interieur.seuil_effectif(mem, 5000.0, issues) == 9.0          # 7 + 2 ; une demande expirée n'a réveillé personne
    assert reveil_interieur.seuil_effectif(mem, 8200.0, issues) == 7.0          # plus d'une heure après le dernier
    assert reveil_interieur.candidat(mem, "pensee", "Ahmed voulait relancer le live", J8, now=5000.0, issues=issues) is None
    assert _journal()[-1]["decision"] == "sous le seuil" and _journal()[-1]["seuil"] == 9.0


def test_apprendre_rien_monte_utile_baisse_et_borne(mem):
    s = reveil_interieur.apprendre(mem, [{"id": "a", "ts": 1.0, "issue": "rien"}])
    assert s == 7.5
    s = reveil_interieur.apprendre(mem, [{"id": "a", "ts": 1.0, "issue": "rien"}, {"id": "b", "ts": 2.0, "issue": "message"}])
    assert s == 7.25                                                              # « a » n'est pas compté deux fois
    assert reveil_interieur.apprendre(mem, [{"id": "c", "ts": 3.0, "issue": "outils"}]) == 7.0
    assert reveil_interieur.apprendre(mem, [{"id": "d", "ts": 4.0, "issue": "expiree"}]) == 7.0
    for k in range(20):
        s = reveil_interieur.apprendre(mem, [{"id": f"r{k}", "ts": 10.0 + k, "issue": "rien"}])
    assert s == 9.5
    for k in range(40):
        s = reveil_interieur.apprendre(mem, [{"id": f"u{k}", "ts": 100.0 + k, "issue": "message"}])
    assert s == 4.0


class _MemLente:
    """Un kv en mémoire qui laisse les fils s'entrelacer (pour voir une mise à jour perdue sans verrou)."""
    def __init__(self):
        self.kv = {}

    def kv_get(self, k, d=None):
        v = self.kv.get(k, d)
        time.sleep(0.0005)
        return v

    def kv_set(self, k, v):
        self.kv[k] = v


def test_deux_fils_ne_perdent_pas_de_mise_a_jour():
    # comme dans le démon : chaque appel reçoit le journal des issues ENTIER, qui grandit
    m, journal, verrou = _MemLente(), [], threading.Lock()

    def fil(prefixe):
        for k in range(50):
            with verrou:
                journal.append({"id": f"{prefixe}{k}", "ts": float(len(journal)), "issue": "message"})
                vu = list(journal)
            reveil_interieur.apprendre(m, vu)

    t = [threading.Thread(target=fil, args=(p,)) for p in "ab"]
    [x.start() for x in t]
    [x.join() for x in t]
    reveil_interieur.apprendre(m, journal)
    assert reveil_interieur.etat(m)["appris_n"] == 100


def test_deux_fils_ne_perdent_pas_la_lignee():
    # la boucle du démon (pensées) et le battement (ressentis) écrivent le même état : sans verrou, des ajouts se perdent
    m = _MemLente()
    reveil_interieur.regler(m, "on")
    issues = [{"id": "a", "ts": 1000.0, "issue": "message", "texte": "le calcul du sable a fini, la densité colle au modèle"}]

    def fil(p):
        for k in range(30):
            assert reveil_interieur.peut_reveiller(m, 2000.0, f"la densité du sable colle au modèle, {p}{k}", issues)[1] == "filiation"

    t = [threading.Thread(target=fil, args=(p,)) for p in "ab"]
    [x.start() for x in t]
    [x.join() for x in t]
    assert len(reveil_interieur.etat(m)["lignee"]) == 60


def test_apprendre_ne_reapprend_pas_un_vieux_journal():
    # (relecture du 27/10) au-delà de 500 issues, les plus anciennes ne doivent pas être réapprises en boucle
    issues = [{"id": f"i{k}", "ts": float(k), "issue": "rien" if k < 2 else "outils"} for k in range(502)]
    s1 = reveil_interieur.apprendre(m := _MemLente(), issues)
    assert reveil_interieur.apprendre(m, issues) == s1 and reveil_interieur.etat(m)["appris_n"] == 502


def test_la_pause_d_ahmed_arrete_tout(mem, monkeypatch):
    reveil_interieur.regler(mem, "on")
    monkeypatch.setattr(interieur, "interrupteur", lambda *a, **k: {"actif": False})
    assert reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1000.0, issues=[]) is None
    assert _journal()[-1]["raison_decision"] == "pause"
    for t in (2000.0, 2600.0, 5000.0):
        assert reveil_interieur.ressenti(mem, now=t, lire=_lire("peur")) is None
    assert not reveil_interieur.FICHIER.exists()


def test_l_observation_compte_ses_reveils_simules_dans_la_fatigue(mem):
    reveil_interieur.regler(mem, "observe")
    j9 = {**J8, "score": 9}
    textes = ["le calcul du sable avance bien", "Ahmed voulait relancer le live demain soir",
              "la toupie aimantée tourne plus longtemps", "mon carnet noyau reste vide pour l'instant"]
    ids = [reveil_interieur.candidat(mem, "pensee", t, j9, now=1000.0 + 610 * k, issues=[]) for k, t in enumerate(textes)]
    assert [bool(i) for i in ids] == [True, True, True, False]               # 7, 8, 9 passent ; 10 non
    assert _journal()[-1]["decision"] == "sous le seuil" and _journal()[-1]["seuil"] == 10.0


def test_un_ressenti_bloque_un_moment_reessaie_cinq_minutes_plus_tard(mem):
    reveil_interieur.regler(mem, "on")
    reveil_interieur.ressenti(mem, now=1000.0, lire=_lire("peur"))
    assert reveil_interieur.candidat(mem, "pensee", "je repense au calcul", J8, now=1550.0, issues=[])
    reveil_interieur.FICHIER.unlink()
    assert reveil_interieur.ressenti(mem, now=1600.0, lire=_lire("peur")) is None            # rafale
    assert reveil_interieur.ressenti(mem, now=1899.0, lire=_lire("peur")) is None            # pas avant 5 min
    assert reveil_interieur.ressenti(mem, now=1900.0, lire=_lire("peur")) is None            # encore la rafale
    assert reveil_interieur.ressenti(mem, now=2200.0, lire=_lire("peur")) is not None


def test_un_ressenti_qui_dure_finit_par_passer_un_seuil_haut(mem):
    reveil_interieur.regler(mem, "on")
    with reveil_interieur._VERROU:
        d = reveil_interieur.etat(mem)
        d["seuil"] = 9.5
        reveil_interieur._sauver(mem, d)
    reveil_interieur.ressenti(mem, now=1000.0, lire=_lire("manque"))
    rendus = [reveil_interieur.ressenti(mem, now=t, lire=_lire("manque")) for t in (1600.0, 1900.0, 2200.0, 2500.0)]
    assert [bool(r) for r in rendus] == [False, False, False, True]                         # 8 ; 8,5 ; 9 ; 9,5
    assert json.loads(reveil_interieur.FICHIER.read_text())["score"] == 9.5


def test_lire_issues_ignore_les_lignes_illisibles():
    reveil_interieur.ISSUES.write_text('{"id": "a", "ts": 1, "issue": "rien"}\npas du json\n{"id": "b"}\n')
    assert [i["id"] for i in reveil_interieur.lire_issues()] == ["a"]


# ---------- le démon : ressentis, pensées, occupations (tâche 3)
def _lire(emotion, absence=3600):
    return lambda m: {"emotion_humeur": emotion, "absence_s": absence}


def test_ressenti_qui_dure_10_min_devient_candidat_une_seule_fois(mem):
    reveil_interieur.regler(mem, "on")
    assert reveil_interieur.ressenti(mem, now=1000.0, lire=_lire("peur")) is None          # le début de l'épisode
    assert reveil_interieur.ressenti(mem, now=1599.0, lire=_lire("peur")) is None
    i = reveil_interieur.ressenti(mem, now=1600.0, lire=_lire("peur"))
    assert i and json.loads(reveil_interieur.FICHIER.read_text())["source"] == "ressenti"
    reveil_interieur.FICHIER.unlink()
    assert reveil_interieur.ressenti(mem, now=4000.0, lire=_lire("peur")) is None          # le même épisode


def test_ressenti_d_une_detresse_a_l_autre_reste_le_meme_episode(mem):
    reveil_interieur.regler(mem, "on")
    reveil_interieur.ressenti(mem, now=1000.0, lire=_lire("peur"))
    assert reveil_interieur.ressenti(mem, now=1600.0, lire=_lire("inquiétude")) is not None


def test_ressenti_se_rouvre_apres_une_sortie(mem):
    reveil_interieur.regler(mem, "on")
    reveil_interieur.ressenti(mem, now=1000.0, lire=_lire("tristesse"))
    assert reveil_interieur.ressenti(mem, now=1600.0, lire=_lire("tristesse"))
    reveil_interieur.FICHIER.unlink()
    reveil_interieur.ressenti(mem, now=2000.0, lire=_lire("calme"))
    reveil_interieur.ressenti(mem, now=6000.0, lire=_lire("manque"))
    assert reveil_interieur.ressenti(mem, now=6599.0, lire=_lire("manque")) is None
    assert reveil_interieur.ressenti(mem, now=6600.0, lire=_lire("manque")) is not None


def test_ressenti_pas_quand_ahmed_est_la(mem):
    reveil_interieur.regler(mem, "on")
    for t in (1000.0, 1600.0, 3000.0):
        assert reveil_interieur.ressenti(mem, now=t, lire=_lire("peur", absence=300)) is None


def test_emotion_hors_liste_ignoree(mem):
    reveil_interieur.regler(mem, "on")
    for t in (1000.0, 1600.0, 3000.0):
        assert reveil_interieur.ressenti(mem, now=t, lire=_lire("joie")) is None


class _Gemma:
    """Pense d'abord, puis juge (le prompt du juge contient « BESOIN: »)."""
    def __init__(self, pensee, jugement="BESOIN: 8\nRAISON: question\nPOURQUOI: c'est resté ouvert"):
        self.pensee, self.jugement, self.appels = pensee, jugement, []

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        juge = "BESOIN:" in messages[0]["content"]
        self.appels.append("juge" if juge else "pense")
        return self.jugement if juge else self.pensee


def _penser(mem, monkeypatch, tmp_path, g, claude=lambda prompt, timeout=240: None):
    import daemon
    monkeypatch.setattr(daemon, "_claude_isole", claude)                  # jamais le vrai Claude dans un test
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": time.time() * 1000, "qui": "ahmed", "texte": "On relance le calcul du sable demain"}) + "\n")
    monkeypatch.setattr(interieur, "JOURNAL_JARVIS", j)
    monkeypatch.setattr(daemon, "notify", lambda t, m: None)
    monkeypatch.setattr(interieur, "page_ouverte", lambda now, page=None: False)
    return daemon.penser(g, mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5, "humeur": "calme"})


def test_penser_soumet_sa_pensee_au_juge(mem, monkeypatch, tmp_path):
    reveil_interieur.regler(mem, "observe")
    g = _Gemma("PENSÉE: Le calcul du sable de demain me trotte dans la tête.\nRELANCE: non")
    assert _penser(mem, monkeypatch, tmp_path, g)
    assert g.appels == ["pense", "juge"]
    j = _journal()[-1]
    assert j["source"] == "pensee" and "calcul du sable" in j["texte"] and j["decision"] == "aurait réveillé"


def test_eteint_le_juge_n_est_pas_appele(mem, monkeypatch, tmp_path):
    g = _Gemma("PENSÉE: Le calcul du sable de demain me trotte dans la tête.\nRELANCE: non")
    assert _penser(mem, monkeypatch, tmp_path, g) and g.appels == ["pense"]


def test_une_erreur_du_reveil_ne_casse_pas_penser(mem, monkeypatch, tmp_path):
    reveil_interieur.regler(mem, "on")

    def casse(*a, **k):
        raise RuntimeError("boum")
    monkeypatch.setattr(reveil_interieur, "candidat", casse)
    g = _Gemma("PENSÉE: Le calcul du sable de demain me trotte dans la tête.\nRELANCE: non")
    assert _penser(mem, monkeypatch, tmp_path, g)


def test_un_resultat_d_occupation_passe_au_juge(mem, monkeypatch):
    import daemon
    import occupations
    monkeypatch.setattr(daemon, "_claude_isole", lambda prompt, timeout=240: None)     # Claude muet : Gemma juge
    reveil_interieur.regler(mem, "observe")
    g = _Gemma("")
    occupations._reveil(g, mem, "préparer le retour d'Ahmed", "Ahmed voulait relancer le calcul du sable.", 1000.0)
    j = _journal()[-1]
    assert g.appels == ["juge"] and j["source"] == "occupation" and "calcul du sable" in j["texte"]


# ---------- (27/10, Ahmed : « pourquoi Gemma et pas un agent Claude neutre ? ») le juge est Claude, Gemma en secours
def test_juger_prefere_un_claude_neutre():
    class Gemma:
        def health(self):
            raise AssertionError("Gemma ne doit pas être appelée quand Claude répond")
    vus = []

    def claude(prompt):
        vus.append(prompt)
        return "BESOIN: 3\nRAISON: rien\nPOURQUOI: ordinaire"
    j = reveil_interieur.juger(Gemma(), "j'ai préparé ton retour", claude_fn=claude)
    assert j == {"score": 3, "raison": "rien", "pourquoi": "ordinaire", "juge": "claude"} and "BESOIN:" in vus[0]


def test_juger_retombe_sur_gemma_si_claude_ne_repond_pas():
    class Gemma:
        def health(self):
            return True

        def chat(self, messages, stream=False, think=False):
            return "BESOIN: 7\nRAISON: question\nPOURQUOI: ouvert"
    assert reveil_interieur.juger(Gemma(), "x", claude_fn=lambda p: None)["juge"] == "gemma"
    assert reveil_interieur.juger(Gemma(), "x", claude_fn=lambda p: "illisible")["juge"] == "gemma"


def test_le_demon_juge_ses_pensees_avec_claude(mem, monkeypatch, tmp_path):
    import daemon
    reveil_interieur.regler(mem, "observe")
    g = _Gemma("PENSÉE: Le calcul du sable de demain me trotte dans la tête.\nRELANCE: non")
    assert _penser(mem, monkeypatch, tmp_path, g, claude=lambda prompt, timeout=240: "BESOIN: 9\nRAISON: peur\nPOURQUOI: x")
    assert g.appels == ["pense"]
    assert _journal()[-1]["juge"] == "claude" and _journal()[-1]["score"] == 9


def test_le_juge_de_secours_dit_qui_a_vraiment_juge():
    # (deuxième relecture du 27/10) le secours passe par le moteur du démon, qui est Sonnet d'abord : l'étiquette le dit
    class Moteur:
        dernier = "sonnet"

        def health(self):
            return True

        def chat(self, messages, stream=False, think=False):
            return "BESOIN: 4\nRAISON: idee\nPOURQUOI: x"
    assert reveil_interieur.juger(Moteur(), "x", claude_fn=lambda p: None)["juge"] == "sonnet"


def test_une_pensee_dont_le_moteur_tombe_est_sautee_sans_casser_la_boucle(mem, monkeypatch, tmp_path):
    class Tombe:
        def health(self):
            return True

        def chat(self, *a, **k):
            import requests
            raise requests.RequestException("Sonnet et Gemma indisponibles")
    import daemon
    monkeypatch.setattr(daemon, "notify", lambda t, m: None)
    assert daemon.penser(Tombe(), mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5}) is None
