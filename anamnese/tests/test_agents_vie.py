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
