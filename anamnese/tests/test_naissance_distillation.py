"""Le filtre d'identité et la distillation du cerveau de départ (naissance/cerveau/filtre.py, distillation.py) : les noms
du papa et de ses proches ne partent jamais en clair chez Claude (témoin : sans le filtre, ils partiraient), la réponse
revient en clair, une proposition sans source est jetée, et RIEN n'entre en mémoire à cette étape."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import aspiration      # noqa: E402
import distillation    # noqa: E402
import faux_profil     # noqa: E402
import filtre          # noqa: E402

VRAIS = ["Karim", "Benali", "Inès", "Sarah", "Haddad"]


def faux_embed(texte):
    v = [0.0] * 32
    for mot in str(texte).lower().split():
        v[hash(mot) % 32] += 1.0
    return v


class FauxClaude:
    """Lit la demande MASQUÉE comme le ferait Claude et répond en JSON, en citant les fichiers et les noms d'emprunt vus."""

    def __init__(self):
        self.demandes = []

    def __call__(self, prompt):
        self.demandes.append(prompt)
        if "Voici les faits proposés" in prompt:
            pids = re.findall(r"^(P\d+) \[", prompt, re.M)
            return json.dumps({"souvenirs": [
                {"categorie": "metier", "texte": "Le papa est styliste et dirige sa propre marque.", "sources": pids[:2],
                 "confiance": 0.9, "importance": 0.9},
                {"categorie": "proches", "texte": self._proche(prompt) + " gère la boutique en ligne.", "sources": pids[1:3]},
                {"categorie": "gouts", "texte": "Il aime le lin.", "sources": ["P999"]},          # source inventée : jetée
                {"categorie": "banque", "texte": "Catégorie interdite.", "sources": pids[:1]}],
                "soi": f"Je viens de naître. Mon papa, {self._papa(prompt)}, est styliste. Hakim est mon grand frère."})
        fids = re.findall(r'<fichier id="(F\d+)"', prompt)
        return "```json\n" + json.dumps({"souvenirs": [
            {"categorie": "metier", "texte": f"{self._papa(prompt)} est styliste, fondateur de sa maison.", "sources": fids[:2]},
            {"categorie": "proches", "texte": f"{self._proche(prompt)} est sa sœur.", "sources": fids[:1] + ["A1"]},
            {"categorie": "ecriture", "texte": "Il écrit court, avec des emojis.", "sources": []}]}) + "\n```"

    @staticmethod
    def _papa(prompt):
        m = re.search(r"fondée en 2019 par (\w+ \w+)|(\w+ \w+) est styliste", prompt)
        return (m.group(1) or m.group(2)) if m else "le papa"

    @staticmethod
    def _proche(prompt):
        m = re.search(r"(\w+ \w+)(?:, ma sœur| est sa sœur)", prompt)
        return m.group(1) if m else "sa sœur"


@pytest.fixture
def inventaire(tmp_path):
    fp = faux_profil.creer(tmp_path / "c")
    aspiration.aspirer(aspiration.dossiers_par_defaut(fp["profil"]), tmp_path / "s", embed=faux_embed)
    return tmp_path / "s"


def test_filtre_aller_retour():
    f = filtre.Filtre()
    f.ajouter_nom("Sarah Benali 💕")
    f.ajouter_nom("Inès Benali")
    f.ajouter_nom("Maman ❤️")                                   # un rôle, pas un nom
    assert len(f.paires) == 3                                    # Sarah, Benali (partagé), Inès
    t = "Sarah Benali et Inès BENALI ; maman a dit oui ; sarah@x.ch, +41 79 123 45 67, IBAN CH93 0076 2011 6238 5295 7"
    m = f.masquer(t)
    assert not f.fuite(m)
    assert "maman" in m and "Sarah" not in m and "Benali" not in m and "BENALI" not in m and "sarah@x.ch" not in m
    assert f.masquer(m) == m                                     # masquer deux fois ne change rien
    assert f.demasquer(m) == t
    assert f.fuite(t)


def test_un_prenom_qui_est_aussi_une_couleur():
    f = filtre.Filtre()
    f.ajouter_nom("Rose Martin")
    m = f.masquer("Rose a choisi une robe rose et un col marine.")
    assert "robe rose" in m and not m.startswith("Rose")


def test_le_dictionnaire_au_format_du_cockpit(tmp_path):
    f = filtre.Filtre()
    f.ajouter_nom("Karim Benali")
    f.masquer("karim@maison-benali.ch")
    chemin = f.sauver(tmp_path / "filtre-identite.json")
    d = json.loads(chemin.read_text())
    assert set(d) == {"paires", "valeurs"} and oct(chemin.stat().st_mode)[-3:] == "600"
    assert filtre.Filtre.charger(chemin).paires == f.paires


def test_rien_ne_part_en_clair_et_tout_revient_en_clair(inventaire, tmp_path):
    claude = FauxClaude()
    out = distillation.distiller(inventaire, appeler=claude, papa_noms=["Karim Benali"])
    assert len(claude.demandes) == 2                              # un lot + la synthèse
    for d in claude.demandes:
        for n in VRAIS:
            assert not re.search(rf"\b{n}\b", d, re.I), n
        assert "079 123 45 67" not in d and "sarah.haddad@exemple-mode.ch" not in d
        assert "lieu 1" in d and "46.51" not in d                 # les lieux numérotés, jamais les coordonnées
    textes = [p["texte"] for p in out["propositions"]]
    assert "Inès Benali gère la boutique en ligne." in textes      # démasqué au retour
    assert "Karim Benali" in out["soi"]["texte"] and "Hakim" in out["soi"]["texte"]
    # sans source, source inventée, catégorie interdite : jetés
    assert out["refusees"] >= 3 and all(p["sources"] for p in out["propositions"])
    assert {p["categorie"] for p in out["propositions"]} <= set(distillation.CATEGORIES)
    s = out["propositions"][0]["sources"]
    assert s and all(Path(x["chemin"]).is_file() for x in s if x["chemin"])               # la provenance : le fichier
    assert json.loads((inventaire / "propositions.json").read_text())["propositions"] == out["propositions"]


def test_temoin_sans_filtre_les_noms_partiraient(inventaire, monkeypatch):
    """Le témoin : filtre coupé (masquer ne fait rien) → le contrôle avant envoi refuse ; contrôle coupé aussi → les vrais
    noms arrivent chez « Claude »."""
    monkeypatch.setattr(filtre.Filtre, "masquer", lambda self, t: t)
    with pytest.raises(distillation.Fuite):
        distillation.distiller(inventaire, appeler=FauxClaude(), papa_noms=["Karim Benali"])
    monkeypatch.setattr(filtre.Filtre, "fuite", lambda self, t: [])
    claude = FauxClaude()
    distillation.distiller(inventaire, appeler=claude, papa_noms=["Karim Benali"])
    assert "Karim Benali" in claude.demandes[0] and "Inès" in claude.demandes[0]


def test_la_distillation_n_ecrit_rien_en_memoire(inventaire, tmp_path, monkeypatch):
    import memory
    appels = []
    monkeypatch.setattr(memory.Memory, "add", lambda *a, **k: appels.append(a))
    monkeypatch.setattr(memory.Memory, "__init__", lambda *a, **k: appels.append("ouverte"))
    distillation.distiller(inventaire, appeler=FauxClaude(), papa_noms=["Karim Benali"])
    assert appels == []


def test_un_mot_courant_n_est_pas_masque(inventaire):
    """« Atelier Couture » comme nom de groupe : « couture » est un mot courant du papa, il reste lisible pour Claude."""
    f = distillation.preparer_filtre(inventaire, ["Karim Benali"], ["Atelier Couture"], textes=["la couture, la couture"])
    assert f.alias_de("Couture") is not None                     # déclaré par le papa : masqué
    (inventaire / "filtre-identite.json").unlink()
    g = distillation.preparer_filtre(inventaire.parent / "autre", [], [], textes=[])
    assert g.alias_de("Couture") is None
    import aspiration as a
    db = a._ouvrir(inventaire / "inventaire.db")
    db.execute("INSERT INTO noms VALUES ('Atelier Couture', 'whatsapp', 3)")
    db.commit()
    db.close()
    h = distillation.preparer_filtre(inventaire, [], [], textes=["la couture et la couture"])
    assert h.alias_de("Couture") is None and h.alias_de("Inès") is not None


def test_l_option_decrire_ne_montre_qu_une_photo(tmp_path):
    """L'option coûteuse : Claude ne voit qu'un dossier privé avec la seule photo (jamais le dossier du papa), et la copie
    disparaît après l'appel ; la description entre dans l'inventaire comme un texte (cherchable par le sens)."""
    fp = faux_profil.creer(tmp_path / "c")
    vus = []

    class R:
        stdout = json.dumps({"result": "Une robe longue en lin sable, sur une plage au coucher du soleil."})

    def executer(cmd, cwd=None, **k):
        vus.append((cmd, cwd, sorted(p.name for p in Path(cwd).iterdir()), oct(Path(cwd).stat().st_mode)[-3:]))
        return R()
    photo = fp["profil"] / "Pictures" / "IMG_20230614_182205.jpg"
    assert distillation.decrire_photo(photo, executer=executer).startswith("Une robe longue en lin")
    cmd, cwd, contenu, droits = vus[0]
    assert contenu == ["photo.jpg"] and droits == "700" and not Path(cwd).exists()
    assert cmd[cmd.index("--tools") + 1] == "Read" and "--strict-mcp-config" in cmd
    r = aspiration.aspirer(aspiration.dossiers_par_defaut(fp["profil"]), tmp_path / "s", embed=faux_embed,
                           decrire=lambda p: distillation.decrire_photo(p, executer=executer), decrire_max=2)
    assert r["decrites"] == 2
    photos = [x for x in aspiration.lignes(tmp_path / "s", genres=["photo"]) if x["extrait"]]
    assert len(photos) == 2 and photos[0]["vecteur"] is not None
