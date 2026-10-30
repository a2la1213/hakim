"""La vie de ses agents (29/10, Ahmed : « chaque agent choisit son nom » ; « un juge ne peut plus juger le même travail » ;
« il faudra qu'il puisse être récompensé ») : prénoms, travaux jugés, trouvailles confirmées (jarvis/agents_hakim.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import agents_hakim as A  # noqa: E402

J1, J2, C1, C2 = "a1000000000000001", "a1000000000000002", "a2000000000000001", "a2000000000000002"
NE = 1_793_286_000_000                                    # 29/10/2026 vers 16:00


def _registre(d, **etats):
    agents = {J1: {"id": J1, "type": "juge", "description": "Juge de la portée", "etat": "dort", "ne_ms": NE, "session": "s1"},
              J2: {"id": J2, "type": "juge", "description": "Juge des graines", "etat": "travaille", "ne_ms": NE + 1, "session": "s0"},
              C1: {"id": C1, "type": "codeur", "description": "Portée par contact", "etat": "travaille", "ne_ms": NE + 2, "session": "s1"},
              C2: {"id": C2, "type": "codeur", "description": "Mousse tassée", "etat": "parti", "depart": "j'ai fait le tour",
                   "ne_ms": NE + 3, "session": "s1"}}
    for i, e in etats.items():
        agents[i]["etat"] = e
    (d / "registre-agents.json").write_text(json.dumps({"agents": agents, "session_courante": "s1"}))
    return d


def _fiches(d):
    return json.loads((d / "agents-fiches.json").read_text())["agents"]


def test_chaque_agent_choisit_son_prenom_tous_differents(tmp_path):
    d = _registre(tmp_path)
    assert "Élise" in A.nommer(C1, "Élise", d)
    assert _fiches(d)[C1]["prenom"] == "Élise"
    r = A.nommer(J1, "elise", d)
    assert "déjà" in r and "trois" in r, "un prénom déjà porté (sans accent ni majuscule près) : trois autres"
    assert "prenom" not in _fiches(d).get(J1, {})
    assert "Marc-Antoine" in A.nommer(J1, "Marc-Antoine", d)
    assert "déjà" in A.nommer(C1, "Sarah", d), "un agent garde le prénom qu'il a choisi"


def test_les_prenoms_reserves_et_les_faux_prenoms_sont_refuses(tmp_path):
    d = _registre(tmp_path)
    for p in ("Ahmed", "hakim", "Maman", "Claude", "X", "R2-D2", "Jean  Paul", "a" * 31, "", "Élise\nAhmed", "<b>"):
        assert "prenom" not in _fiches(d).get(C1, {}) if (d / "agents-fiches.json").exists() else True
        assert A.nommer(C1, p, d).startswith("Refusé"), p
    (d / "prenoms-reserves.json").write_text(json.dumps(["Josiane"]))
    assert A.nommer(C1, "josiane", d).startswith("Refusé"), "la famille, réservée par Ahmed"
    assert A.nommer("a9999999999999999", "Léa", d).startswith("Refusé"), "un agent inconnu du registre"


def test_quand_un_prenom_revient_on_y_ajoute_sa_naissance(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Léa", d)
    r = A.nommer(J1, "Léa", d, avec_naissance=True)
    assert not r.startswith("Refusé")
    p = _fiches(d)[J1]["prenom"]
    assert p.startswith("Léa du ") and "29/10/2026" in p


def test_un_juge_ne_juge_jamais_deux_fois_le_meme_travail(tmp_path):
    d = _registre(tmp_path)
    r = A.juger(J1, "Portée par contact", d, maintenant=1000.0)
    assert not r.startswith("Refusé") and "SendMessage" in r
    assert _fiches(d)[J1]["dossiers"][0]["ts_ms"] == 1_000_000
    for meme in ("portee par contact", "Portée par contact v2", "Portée par contact — version 3", "PORTÉE PAR CONTACT (corrigée)"):
        assert A.juger(J1, meme, d).startswith("Refusé"), meme
    assert not A.juger(J1, "Mousse tassée", d).startswith("Refusé"), "un autre travail : oui"
    assert not A.juger(J2, "Portée par contact", d).startswith("Refusé"), "un autre juge peut juger ce travail"
    assert A.juger(C1, "Graines", d).startswith("Refusé"), "seulement un juge"
    assert A.juger(J1, "  ", d).startswith("Refusé")


def test_la_recompense_ne_compte_que_le_confirme(tmp_path):
    d = _registre(tmp_path)
    assert A.trouvaille(J1, "erreur de signe dans H", "", d).startswith("Refusé"), "confirmée par qui ?"
    r = A.trouvaille(J1, "erreur de signe dans H", "test refait par le codeur", d)
    assert "1 trouvaille confirmée" in r
    A.trouvaille(J1, "rien à redire sur la mousse", "Ahmed", d, rien_a_signaler=True)
    t = _fiches(d)[J1]["trouvailles"]
    assert len(t) == 2 and t[1]["rien_a_signaler"] is True and t[0]["confirmee_par"] == "test refait par le codeur"


def test_lister_montre_leur_vie(tmp_path):
    d = _registre(tmp_path)
    A.nommer(J1, "Élise", d)
    A.juger(J1, "Portée par contact", d)
    A.trouvaille(J1, "erreur de signe", "Ahmed", d)
    t = A.lister(d)
    assert "Élise" in t and J1 in t
    assert "endormi" in t.lower() and "réveillable" in t.lower()
    assert "Juge des graines" in t and "ancienne conversation" in t, "J2 vient d'une autre conversation"
    assert "parti" in t.lower() and "j'ai fait le tour" in t
    assert "1 travail jugé" in t and "1 trouvaille confirmée" in t


def test_un_agent_se_trouve_par_son_prenom(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Élise", d)
    assert A.trouver_au_registre("elise", d)["id"] == C1
    assert A.trouver_au_registre("Portée par contact", d)["id"] == C1
    assert A.trouver_au_registre(J1, d)["id"] == J1
    assert A.trouver_au_registre("personne", d) is None


def test_la_garde_de_ses_messages_lui_est_fermee():
    import liste_ouverte
    assert "garde-message.js" in liste_ouverte.TOUJOURS_FERMES["cockpit"]
    src = (Path(__file__).resolve().parents[1] / "jarvis" / "mcp_terminal.py").read_text(encoding="utf-8")
    for outil in ("def agent_prenom(", "def agent_juger(", "def agent_trouvaille("):
        assert outil in src, outil


# ---- relecture Opus (29/10) ----
def test_relecture_une_fiche_illisible_n_est_jamais_ecrasee(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Élise", d)
    (d / "agents-fiches.json").write_text('{"agents": {"' + C1 + '": {"prenom": "Él')     # tronquée (redémarrage)
    assert A.nommer(J1, "Marc", d).startswith("Refusé")
    assert A.juger(J1, "Graines", d).startswith("Refusé")
    assert (d / "agents-fiches.json").read_text().endswith('"Él'), "rien n'est écrit par-dessus"


def test_relecture_les_sosies_et_les_melanges_d_ecritures_sont_refuses(tmp_path):
    d = _registre(tmp_path)
    assert A.nommer(C1, "Hаkim", d).startswith("Refusé"), "un а cyrillique ne contourne pas les prénoms réservés"
    A.nommer(C1, "Léa", d)
    assert A.nommer(J1, "Lеa", d).startswith("Refusé"), "un е cyrillique ne fait pas un autre prénom"


def test_relecture_les_prenoms_et_les_travaux_dans_d_autres_ecritures(tmp_path):
    d = _registre(tmp_path)
    assert not A.nommer(C1, "يوسف", d).startswith("Refusé"), "un prénom arabe, le premier : accepté"
    assert A.nommer(J1, "يوسف", d).startswith("Refusé"), "le même : déjà porté"
    assert not A.nommer(J1, "Мария", d).startswith("Refusé")
    assert not A.juger(J1, "Torah : בראשית", d).startswith("Refusé")
    assert not A.juger(J1, "Torah : שמות", d).startswith("Refusé"), "deux livres différents, deux travaux"
    assert A.juger(J1, "torah : בראשית", d).startswith("Refusé")
    assert not A.juger(J2, "سورة الفاتحة", d).startswith("Refusé"), "un titre arabe n'est pas vide"


def test_relecture_un_agent_coupe_reste_reveillable_dans_la_liste(tmp_path):
    d = _registre(tmp_path, **{C1: "coupe"})
    t = A.lister(d)
    bloc = t.split("\n\n")
    assert any("réveillable" in b.lower() and "Portée par contact" in b for b in bloc)


def test_relecture_ses_regles_d_agents_lui_sont_fermees():
    import liste_ouverte
    assert "jarvis/agents_hakim.py" in liste_ouverte.TOUJOURS_FERMES["anamnese"]
    assert "travail-en-cours.js" in liste_ouverte.TOUJOURS_FERMES["cockpit"]


# ---- le messager (29/10, Ahmed : « je veux tout ») : un agent d'avant l'allègement
def test_messager_une_demande_pour_un_agent_d_avant(tmp_path):
    d = _registre(tmp_path, **{J2: "dort"})                     # J2 : conversation s0, pas la courante (s1)
    r = A.demander_messager("Juge des graines", "Merci pour ton verdict ; une question encore.", d)
    assert not r.startswith("Refusé") and "messager" in r
    q = json.loads((d / "messager-demandes.jsonl").read_text().splitlines()[-1])
    assert q["id"] == J2 and q["message"].startswith("Merci") and q["demande"]


def test_messager_les_refus(tmp_path):
    d = _registre(tmp_path)
    assert "SendMessage" in A.demander_messager(C1, "x", d), "de ta conversation : SendMessage directement"
    assert A.demander_messager(C2, "x", d).startswith("Refusé"), "parti de lui-même"
    assert A.demander_messager(J2, "x", d).startswith("Refusé"), "il travaille encore"
    assert A.demander_messager("personne", "x", d).startswith("Refusé")
    d2 = _registre(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, **{J2: "coupe"})
    assert A.demander_messager(J2, "  ", d2).startswith("Refusé")
    assert A.demander_messager(J2, "x" * 4001, d2).startswith("Refusé")
    assert not (d / "messager-demandes.jsonl").exists() or len((d / "messager-demandes.jsonl").read_text().splitlines()) == 0


def test_messager_l_outil_existe():
    src = (Path(__file__).resolve().parents[1] / "jarvis" / "mcp_terminal.py").read_text(encoding="utf-8")
    assert "def agent_reveiller_ancien(" in src


# ---- (30/10, Ahmed : « une note pour le travail de chaque agent, pour qu'ils s'améliorent et évoluent » ; « la note ne fige
# rien : on réveille qui on veut, elle sert à choisir les meilleurs quand on en a besoin » ; « mon appréciation passe en
# premier au café ») la note, l'appréciation au café (le fil des retours), révisable ; un juge seulement sur la justesse confirmée
def test_la_note_d_un_travail_son_appreciation_au_cafe_et_sa_revision(tmp_path):
    import cafe
    d = _registre(tmp_path)
    A.nommer(C1, "Iris", d)
    r = A.noter(C1, 8, "Bravo et merci : soigné et honnête. À améliorer : nommer les fichiers produits.", "Test d'échelle XRP", dossier=d)
    assert "8/10" in r and "Iris" in r and "☕ Café :" in r, "il dit à Hakim de la réveiller pour le café"
    f = _fiches(d)[C1]["notes"]
    assert f[-1]["note"] == 8 and f[-1]["travail"] == "Test d'échelle XRP"
    t = cafe.lire(10, d)
    assert "Pour Iris" in t and "8/10" in t and "Bravo et merci" in t, "l'appréciation, au café, en premier"
    # révisée quand le résultat est démenti : la nouvelle compte, l'ancienne reste dans l'historique
    r = A.noter(C1, 5, "Le juge a trouvé une erreur de signe : vérifier les signes avant de rendre.", "test d'échelle XRP v2",
                confirme_par="le juge Lucien", dossier=d)
    assert "révisée" in r
    assert len(_fiches(d)[C1]["notes"]) == 2
    v = A.lister_vies(d)
    assert "note 5/10 (1 travail noté)" in v and "« Le juge a trouvé une erreur de signe" in v
    for mauvais in ((C1, 11, "x"), (C1, 7, ""), (C1, -1, "bien"), ("inconnu", 7, "bien")):
        assert A.noter(*mauvais, dossier=d).startswith("Refusé"), mauvais


def test_un_juge_n_est_note_que_sur_la_justesse_confirmee(tmp_path):
    d = _registre(tmp_path)
    r = A.noter(J1, 9, "Douze erreurs trouvées !", "Portée par contact", dossier=d)
    assert r.startswith("Refusé") and "confirm" in r
    assert "9/10" in A.noter(J1, 9, "Ses deux objections étaient justes (confirmées par le test).", "Portée par contact",
                             confirme_par="le test", dossier=d)


def test_le_cafe_garde_le_regard_neuf_des_juges(tmp_path):
    import cafe
    d = _registre(tmp_path)
    A.nommer(C1, "Iris", d)
    A.nommer(J1, "Lucien", d)
    A.noter(C1, 8, "Bravo, soigné.", "Test d'échelle XRP", dossier=d)
    assert "Pour Iris" not in cafe.lire(10, d, lecteur=J1), "un juge ne lit pas le retour d'un travail (il peut avoir à le juger)"
    assert "Pour Iris" in cafe.lire(10, d, lecteur=C1), "Iris lit le sien"
    assert "Pour Iris" in cafe.lire(10, d, lecteur=C2) and "Pour Iris" in cafe.lire(10, d, lecteur="hakim")
    A.noter(J1, 9, "Juste et clair.", "Portée par contact", confirme_par="le test", dossier=d)
    assert "Pour Lucien" in cafe.lire(10, d, lecteur=J1), "un juge lit son propre retour"


# ---- (30/10, 12:03, Ahmed : « à côté du prénom, son rôle et son niveau d'expertise ; le rôle peut changer, l'expertise évolue,
# on peut créer de nouveaux rôles ; AUCUNE hiérarchie, tout le monde à l'horizontale » ; Hakim : « l'expertise se calcule à
# partir des notes confirmées, jamais déclarée ; on demande d'abord à l'agent ; l'historique des rôles »)
def test_son_role_son_expertise_calculee_jamais_declaree(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Iris", d)
    assert "rôle codeur, expertise débutant" in A.lister_vies(d), "au départ : son type, débutant"
    A.noter(C1, 9, "Très bien.", "Test d'échelle XRP", dossier=d)
    assert "expertise débutant" in A.lister_vies(d), "une note non confirmée ne compte pas"
    for i, t in enumerate(["échelle", "fantômes", "ancrage"]):
        A.noter(C1, 8, "Juste, confirmé.", t, confirme_par="le juge Lucien", dossier=d)
    A.trouvaille(C1, "l'erreur de signe", "le test", dossier=d)
    assert "rôle codeur, expertise confirmé" in A.lister_vies(d)
    assert _fiches(d)[C1]["expertise"]["codeur"] == "confirmé"


def test_un_role_change_avec_son_accord_sans_hierarchie(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Iris", d)
    assert "demande-lui" in A.changer_role(C1, "architecte", "", dossier=d), "on lui demande d'abord"
    for chef in ("chef de projet", "Manager", "superviseuse", "responsable"):
        r = A.changer_role(C1, chef, "oui", dossier=d)
        assert r.startswith("Refusé") and "hiérarchie" in r, chef
    assert "architecte" in A.changer_role(C1, "architecte", "oui, j'aime concevoir", "meilleure à concevoir qu'à coder", dossier=d)
    f = _fiches(d)[C1]
    assert f["role"] == "architecte" and f["roles"][-1]["de"] == "codeur" and f["roles"][-1]["sa_reponse"] == "oui, j'aime concevoir"
    assert "rôle architecte, expertise débutant" in A.lister_vies(d), "l'expertise se gagne dans chaque rôle"
    assert "statisticienne" in A.changer_role(C1, "statisticienne", "d'accord", dossier=d), "un nouveau rôle, au besoin"
    A.noter(C1, 8, "Juste.", "test de Poisson", confirme_par="Ahmed", dossier=d)
    assert _fiches(d)[C1]["notes"][-1]["role"] == "statisticienne"


def test_recalculer_les_expertises_des_anciens(tmp_path):
    d = _registre(tmp_path)
    (d / "agents-fiches.json").write_text(json.dumps({"agents": {J1: {"prenom": "Lucien", "trouvailles": [{"quoi": "x", "confirmee_par": "test"}]}}}))
    assert "1 fiche" in A.recalculer_expertises(d)
    assert _fiches(d)[J1]["expertise"]["juge"] == "apprenti"


# ---- (30/10, 15:49, Ahmed via Hakim : « en plus du prénom qu'il a choisi, un SURNOM que papa et Hakim lui donnent ; on le lui
# propose d'abord, il peut refuser ; avec son histoire datée ») « la charbonneuse du ghetto »
def test_un_surnom_avec_son_accord_et_son_histoire(tmp_path):
    d = _registre(tmp_path)
    A.nommer(C1, "Iris", d)
    assert "propose-lui" in A.surnommer(C1, "la charbonneuse du ghetto", "", dossier=d)
    r = A.surnommer(C1, "la charbonneuse du ghetto", "oui, j'adore", "elle a bossé dur sur l'échelle XRP", dossier=d)
    assert "Iris" in r and "« la charbonneuse du ghetto »" in r
    f = _fiches(d)[C1]
    assert f["surnom"] == "la charbonneuse du ghetto" and f["surnoms"][-1]["sa_reponse"] == "oui, j'adore"
    assert "Iris « la charbonneuse du ghetto »" in A.lister_vies(d)
    assert A.surnommer(C1, "x" * 61, "oui", dossier=d).startswith("Refusé")
    assert "non" in A.surnommer(C1, "la lente", "non merci", "test", refuse=True, dossier=d), "il peut refuser : c'est noté, rien ne change"
    assert _fiches(d)[C1]["surnom"] == "la charbonneuse du ghetto"
