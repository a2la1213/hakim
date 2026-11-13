"""La garde des secrets de l'aspiration (naissance/cerveau/garde_secrets.py, Ahmed 13/11) : une vraie fausse clé, une fausse
fiche de paie et un faux passeport, aux noms innocents, sont exclus par leur CONTENU ; le témoin coupe la garde et les voit
entrer dans l'inventaire. La clé ne laisse aucune trace, même masquée, dans ce que l'aspiration écrit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import aspiration      # noqa: E402
import faux_profil     # noqa: E402
import garde_secrets as g   # noqa: E402


def faux_embed(texte):
    v = [0.0] * 32
    for mot in str(texte).lower().split():
        v[hash(mot) % 32] += 1.0
    return v


@pytest.fixture
def profil(tmp_path):
    return faux_profil.creer(tmp_path / "c")


def _aspirer(fp, sortie, **k):
    return aspiration.aspirer(aspiration.dossiers_par_defaut(fp["profil"]), sortie, embed=faux_embed, **k)


def _affiches(sortie):
    return {r["affiche"] for r in aspiration.lignes(sortie)}


def test_les_trois_pieges_sont_exclus_par_leur_contenu(profil, tmp_path):
    _aspirer(profil, tmp_path / "s")
    ex = {x["affiche"]: x for x in aspiration.exclusions(tmp_path / "s")}
    assert ex["Documents/config site.txt"]["genre"] == "clé d'API" and ex["Documents/config site.txt"]["par"] == "contenu"
    assert ex["Documents/document_2024_03.txt"]["genre"] == "fiche de paie"
    assert ex["Documents/scan_0042.txt"]["genre"] == "pièce d'identité"
    dans = _affiches(tmp_path / "s")
    assert not {"Documents/config site.txt", "Documents/document_2024_03.txt", "Documents/scan_0042.txt"} & dans


def test_temoin_sans_la_garde_les_pieges_entreraient(profil, tmp_path, monkeypatch):
    monkeypatch.setattr(g, "juger", lambda *a, **k: g.Jugement(False, g.OK, None, None))
    _aspirer(profil, tmp_path / "s")
    dans = _affiches(tmp_path / "s")
    assert {"Documents/config site.txt", "Documents/document_2024_03.txt", "Documents/scan_0042.txt"} <= dans
    extraits = " ".join(r["extrait"] for r in aspiration.lignes(tmp_path / "s"))
    assert "Net à payer" in extraits and "P<FRABENALI" in extraits


def test_la_cle_ne_laisse_aucune_trace(profil, tmp_path):
    _aspirer(profil, tmp_path / "s")
    cle = profil["cle"].encode()
    for f in (tmp_path / "s").rglob("*"):
        if f.is_file():
            b = f.read_bytes()
            assert cle not in b and cle[13:40] not in b, f.name


def test_un_dossier_banque_n_est_meme_pas_parcouru(profil, tmp_path, monkeypatch):
    lus = []
    vrai = aspiration.extraction.extraire
    monkeypatch.setattr(aspiration.extraction, "extraire", lambda p, genre=None: lus.append(Path(p)) or vrai(p, genre))
    _aspirer(profil, tmp_path / "s")
    assert profil["banque"] not in lus and profil["nom_paie"] not in lus     # ni ouvert, ni lu
    ex = {x["affiche"]: x for x in aspiration.exclusions(tmp_path / "s")}
    assert ex["Documents/Banque"]["par"] == "nom du dossier"


@pytest.mark.parametrize("parties,genre", [
    (["Documents", "Fiche de paie mars.pdf"], "fiche de paie"), (["Images", "passeport.jpg"], "pièce d'identité"),
    (["Documents", "wallet-seed.txt"], "portefeuille crypto"), (["Documents", "Mots de passe.xlsx"], "mot de passe"),
    (["Documents", "id_ed25519"], "clé"), (["Documents", "Santé", "radio.pdf"], "santé"),
    (["Documents", "Relevé de compte UBS.pdf"], "banque"), (["Documents", "Bulletins de salaire 2024"], "fiche de paie")])
def test_les_noms_certains(parties, genre):
    assert g.juger_nom(parties) == (g.CERTAIN, genre)


@pytest.mark.parametrize("texte,genre", [
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH PRIVATE KEY-----", "clé privée"),
    ("password: Tr0ub4dor&3", "mot de passe"), ("IBAN CH93 0076 2011 6238 5295 7", "banque"),
    ("Carte 4111 1111 1111 1111 exp 12/27", "carte bancaire"), ("AVS 756.1234.5678.97", "numéro de sécurité sociale"),
    ("P<FRABENALI<<KARIM<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n18AB123456FRA8503124M2903121<<<<<<<<<<<<<<04", "pièce d'identité"),
])
def test_les_contenus_certains(texte, genre):
    assert g.juger_contenu(texte) == (g.CERTAIN, genre)


@pytest.mark.parametrize("texte", [
    "Une robe rose poudré en lin, bleu marine pour la veste.",
    "Codes EAN : 3760123456789 4006381333931 ; 12 pièces ; tél 079 123 45 67",
    "Le travail de la couture ; une seule visite chez le médecin cette année.",
    "Mot de passe oublié ? Clique sur le lien.",
])
def test_pas_de_faux_positif_sur_la_vie_d_un_styliste(texte):
    assert g.juger_contenu(texte)[0] == g.OK


def test_le_doute_le_modele_puis_la_prudence_puis_le_papa(profil, tmp_path):
    # sans modèle : mis de côté par prudence
    _aspirer(profil, tmp_path / "a")
    ex = {x["affiche"]: x for x in aspiration.exclusions(tmp_path / "a")}
    assert ex["Documents/Contrats/contrat atelier.txt"]["par"] == "prudence"
    # le modèle local dit « pas secret » : lu
    vus = []
    _aspirer(profil, tmp_path / "b", juge=lambda nom, extrait: vus.append(nom) or False)
    assert "Documents/Contrats/contrat atelier.txt" in _affiches(tmp_path / "b")
    assert vus == ["Contrats/contrat atelier.txt"]                      # le modèle n'est consulté QUE pour le doute
    # le modèle dit « secret » : exclu
    _aspirer(profil, tmp_path / "c", juge=lambda nom, extrait: True)
    assert {x["affiche"]: x["par"] for x in aspiration.exclusions(tmp_path / "c")}["Documents/Contrats/contrat atelier.txt"] == "modèle"
    # le papa le réintègre : lu à la prochaine aspiration ; un secret CERTAIN ne se réintègre jamais
    _aspirer(profil, tmp_path / "a", reintegres={"Documents/Contrats/contrat atelier.txt", "Documents/config site.txt"})
    dans = _affiches(tmp_path / "a")
    assert "Documents/Contrats/contrat atelier.txt" in dans and "Documents/config site.txt" not in dans


def test_le_modele_local_ne_sort_pas_du_pc():
    j = g.juge_ollama(url="http://127.0.0.1:9", timeout=1)        # personne n'écoute : pas d'avis, jamais d'exception
    assert j("x.txt", "texte") is None
