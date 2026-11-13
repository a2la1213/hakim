"""La relecture obligatoire (naissance/cerveau/relecture.py, Ahmed 13/11 : « rien ne devient mémoire avant son oui ») : seuls
les souvenirs gardés ou corrigés par le papa entrent en mémoire ; le témoin coupe la porte et voit entrer l'effacé et le
non-décidé. La page est servie en local, protégée par son jeton."""
import http.client
import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import aspiration    # noqa: E402
import relecture     # noqa: E402


def faux_embed(texte):
    v = [0.0] * 16
    for mot in str(texte).lower().split():
        v[hash(mot) % 16] += 1.0
    return v


SRC = [{"affiche": "Documents/Collection.docx", "chemin": "/mnt/c/Users/k/Documents/Collection.docx"}]


@pytest.fixture
def sortie(tmp_path):
    s = tmp_path / "naissance"
    s.mkdir()
    props = {"papa": ["Karim Benali"], "fichiers_lus": 3, "inventaire": 9, "propositions": [
        {"id": "s1", "categorie": "metier", "texte": "Karim est styliste.", "sources": SRC, "importance": 0.9},
        {"id": "s2", "categorie": "proches", "texte": "Inès est sa cousine.", "sources": SRC, "importance": 0.7},
        {"id": "s3", "categorie": "gouts", "texte": "SOUVENIR-EFFACÉ : il déteste le lin.", "sources": SRC},
        {"id": "s4", "categorie": "habitudes", "texte": "SOUVENIR-NON-DÉCIDÉ : il se lève à 5 h.", "sources": SRC}],
        "soi": {"id": "soi", "categorie": "soi", "texte": "Je viens de naître chez Karim, styliste."}}
    (s / "propositions.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    db = aspiration._ouvrir(s / "inventaire.db")
    db.execute("INSERT INTO exclus VALUES ('/x/contrat.txt', 'Documents/Contrats/contrat.txt', 'papiers', 'doute', 'prudence', 0)")
    db.execute("INSERT INTO exclus VALUES ('/x/cle.txt', 'Documents/cle.txt', 'clé d''API', 'certain', 'contenu', 0)")
    db.commit()
    db.close()
    return s


def _contenus(db):
    c = sqlite3.connect(str(db))
    try:
        return [r[0] for r in c.execute("SELECT content FROM episodes WHERE role='semantic'")]
    finally:
        c.close()


def _decider_comme_le_papa(sortie):
    relecture.decider(sortie, "s1", "garder")
    relecture.decider(sortie, "s2", "corriger", "Inès est sa sœur, elle gère la boutique en ligne.")
    relecture.decider(sortie, "s3", "effacer")
    relecture.decider(sortie, "soi", "garder")


def test_rien_n_entre_sans_oui(sortie, tmp_path):
    _decider_comme_le_papa(sortie)
    bilan = relecture.importer(sortie, tmp_path / "ia.db", embed=faux_embed)
    assert bilan == {"importes": 2, "deja": 0, "soi": True, "sans_oui": 1, "effaces": 1}
    tout = " ".join(_contenus(tmp_path / "ia.db"))
    assert "Karim est styliste." in tout and "Inès est sa sœur, elle gère la boutique en ligne." in tout
    assert "Inès est sa cousine" not in tout                         # la correction remplace
    assert "SOUVENIR-EFFACÉ" not in tout and "SOUVENIR-NON-DÉCIDÉ" not in tout
    assert "d'après : Documents/Collection.docx" in tout and "relu et validé par papa" in tout
    c = sqlite3.connect(str(tmp_path / "ia.db"))
    assert c.execute("SELECT COUNT(*) FROM naissance_sources WHERE chemin LIKE '%Collection.docx'").fetchone()[0] == 2
    assert c.execute("SELECT value FROM kv WHERE key='self_core'").fetchone()[0] == "Je viens de naître chez Karim, styliste."
    c.close()


def test_temoin_sans_la_porte_l_efface_et_le_non_decide_entreraient(sortie, tmp_path, monkeypatch):
    _decider_comme_le_papa(sortie)
    monkeypatch.setattr(relecture, "retenues", lambda els, decs: [(e, e["texte"]) for e in els])
    relecture.importer(sortie, tmp_path / "temoin.db", embed=faux_embed)
    tout = " ".join(_contenus(tmp_path / "temoin.db"))
    assert "SOUVENIR-EFFACÉ" in tout and "SOUVENIR-NON-DÉCIDÉ" in tout


def test_sans_aucune_decision_rien_n_est_appris(sortie, tmp_path):
    bilan = relecture.importer(sortie, tmp_path / "ia.db", embed=faux_embed)
    assert bilan["importes"] == 0 and bilan["soi"] is False and bilan["sans_oui"] == 5
    assert not any("Appris du PC" in c for c in _contenus(tmp_path / "ia.db"))


def test_un_deuxieme_oui_n_ecrit_pas_deux_fois(sortie, tmp_path):
    _decider_comme_le_papa(sortie)
    relecture.importer(sortie, tmp_path / "ia.db", embed=faux_embed)
    relecture.decider(sortie, "s4", "garder")                      # il revient garder un souvenir oublié
    bilan = relecture.importer(sortie, tmp_path / "ia.db", embed=faux_embed)
    assert bilan["importes"] == 1 and bilan["deja"] == 3
    assert sum("Appris du PC" in c for c in _contenus(tmp_path / "ia.db")) == 3


def test_les_decisions_mal_formees(sortie):
    with pytest.raises(KeyError):
        relecture.decider(sortie, "inconnu", "garder")
    with pytest.raises(ValueError):
        relecture.decider(sortie, "s1", "corriger", "  ")
    with pytest.raises(ValueError):
        relecture.decider(sortie, "s1", "publier")
    relecture.decider(sortie, "s1", "garder")
    relecture.decider(sortie, "s1", None)                         # il change d'avis : plus de décision
    assert relecture.decisions(sortie) == {}


def test_reintegrer_un_doute_jamais_un_secret(sortie):
    assert relecture.reintegrer(sortie, "Documents/Contrats/contrat.txt") == ["Documents/Contrats/contrat.txt"]
    with pytest.raises(ValueError):
        relecture.reintegrer(sortie, "Documents/cle.txt")
    e = relecture.etat(sortie)
    assert e["secrets_exclus"] == 1 and e["prudence"] == [{"affiche": "Documents/Contrats/contrat.txt", "genre": "papiers",
                                                           "par": "prudence", "reintegre": True}]


def _requete(port, methode, chemin, corps=None, jeton=None, hote=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Content-Type": "application/json"}
    if jeton:
        h["X-Jeton"] = jeton
    if hote:
        h["Host"] = hote
    c.request(methode, chemin, body=json.dumps(corps) if corps is not None else None, headers=h)
    r = c.getresponse()
    b = r.read()
    c.close()
    return r.status, b


def test_la_page_locale(sortie, tmp_path):
    serveur, adresse = relecture.application(sortie, tmp_path / "ia.db", embed=faux_embed, port=0)
    t = threading.Thread(target=serveur.serve_forever, daemon=True)
    t.start()
    try:
        port = serveur.server_address[1]
        jeton = adresse.split("jeton=")[1]
        assert adresse.startswith(f"http://localhost:{port}/?jeton=")
        assert _requete(port, "GET", "/")[0] == 403                                   # sans jeton
        st, page = _requete(port, "GET", f"/?jeton={jeton}")
        assert st == 200 and "Ce que ton IA a appris de ton PC" in page.decode()
        st, e = _requete(port, "GET", "/api/etat", jeton=jeton)
        assert st == 200 and len(json.loads(e)["propositions"]) == 4
        assert _requete(port, "POST", "/api/decision", {"id": "s1", "decision": "garder"}, jeton="faux")[0] == 403
        assert _requete(port, "POST", "/api/decision", {"id": "s1", "decision": "garder"}, jeton=jeton,
                        hote="evil.example:80")[0] == 403                              # rebinding DNS : refusé
        assert _requete(port, "POST", "/api/decision", {"id": "s1", "decision": "garder"}, jeton=jeton)[0] == 200
        assert _requete(port, "POST", "/api/decision", {"id": "zz", "decision": "garder"}, jeton=jeton)[0] == 400
        st, b = _requete(port, "POST", "/api/valider", {}, jeton=jeton)
        assert st == 200 and json.loads(b)["bilan"]["importes"] == 1
    finally:
        serveur.shutdown()
        serveur.server_close()
    assert any("Karim est styliste." in c for c in _contenus(tmp_path / "ia.db"))
