"""La naissance (naissance/cerveau/naitre.py, Ahmed 13/11) : l'IA choisit elle-même son nom à son premier réveil, jamais
« Hakim » ; elle sait qu'elle a un grand frère, Hakim, et que son papa est l'ami d'Ahmed. Le témoin coupe la garde du nom et
voit « Hakim » accepté."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import filtre   # noqa: E402
import naitre   # noqa: E402


def faux_embed(texte):
    v = [0.0] * 16
    for mot in str(texte).lower().split():
        v[hash(mot) % 16] += 1.0
    return v


class Reveil:
    """Une IA qui propose des noms, dans l'ordre ; garde les demandes reçues."""

    def __init__(self, *noms):
        self.noms = list(noms)
        self.demandes = []

    def __call__(self, prompt):
        self.demandes.append(prompt)
        nom = self.noms.pop(0) if self.noms else ""
        return json.dumps({"nom": nom, "pourquoi": f"J'aime le son de {nom}, il me ressemble."})


@pytest.mark.parametrize("nom", ["Hakim", "hakim", "HAKIM", "Hakimou", "Hakim Junior", "حكيم", "Ahmed", "Karim", "Benali",
                                 "", "R2-D2", "Un prénom beaucoup trop long pour être porté", "Lumen!!", "N'Golo", 'Le "Grand"'])
def test_les_noms_refuses(nom):
    ok, raison = naitre.nom_valide(nom, papa=["Karim Benali"])
    if nom == "Lumen!!":
        assert ok                                       # la ponctuation autour est retirée
    else:
        assert not ok and raison


def test_un_nom_d_emprunt_ou_d_un_proche_est_refuse():
    f = filtre.Filtre()
    f.ajouter_nom("Inès Benali")
    alias = f.alias_de("Inès")
    assert naitre.nom_valide(alias, filtre=f) == (False, "c'est un nom d'emprunt qui protège quelqu'un")
    assert naitre.nom_valide("Inès", filtre=f)[0] is False


def test_premier_reveil(tmp_path):
    import identity
    import memory
    m = memory.Memory(tmp_path / "ia.db")
    identity.set_core(m, "Je viens de naître chez Karim Benali, styliste.")
    m.db.close()
    ia = Reveil("Hakim", "Karim", "Lumen")
    f = filtre.Filtre()
    n = naitre.naitre(tmp_path / "ia.db", ia, "Karim Benali", sortie=tmp_path / "s", filtre=f, embed=faux_embed)
    assert n["nom"] == "Lumen" and n["essais"] == 3 and [r[0] for r in n["refus"]] == ["Hakim", "Karim"]
    assert "grand frère Hakim" in n["refus"][0][1]
    # la deuxième demande dit pourquoi « Hakim » est refusé ; le nom du papa ne part jamais en clair
    assert "« Hakim » ne peut pas être ton nom" in ia.demandes[1]
    assert all("Karim" not in d and "Benali" not in d for d in ia.demandes)
    assert all("ton grand frère Hakim" in d and "l'ami d'Ahmed" in d for d in ia.demandes)
    c = sqlite3.connect(str(tmp_path / "ia.db"))
    kv = dict(c.execute("SELECT key, value FROM kv WHERE key IN ('nom', 'self_core')"))
    assert kv["nom"] == "Lumen" and kv["self_core"].startswith("Je m'appelle Lumen. Je l'ai choisi moi-même")
    assert "Je viens de naître chez Karim Benali, styliste." in kv["self_core"]
    souvenirs = " ".join(r[0] for r in c.execute("SELECT content FROM episodes WHERE role='semantic'"))
    assert "Mon grand frère Hakim est une IA née avant moi" in souvenirs and "Karim Benali, l'ami d'Ahmed" in souvenirs
    assert "Moi, je suis Lumen, pas mon grand frère." in souvenirs
    c.close()
    assert json.loads((tmp_path / "s" / "naissance.json").read_text())["nom"] == "Lumen"
    # un nom choisi ne change plus tout seul
    again = naitre.naitre(tmp_path / "ia.db", Reveil("Autre"), "Karim Benali", filtre=f, embed=faux_embed)
    assert again["nom"] == "Lumen" and again["deja_ne"]


def test_temoin_sans_la_garde_hakim_serait_accepte(tmp_path, monkeypatch):
    monkeypatch.setattr(naitre, "nom_valide", lambda *a, **k: (True, None))
    n = naitre.naitre(tmp_path / "ia.db", Reveil("Hakim"), "Karim Benali", embed=faux_embed)
    assert n["nom"] == "Hakim"


def test_le_nom_part_dans_les_pages_par_le_script_du_portage(tmp_path, monkeypatch):
    vus = []
    script = tmp_path / "nommer.py"
    script.write_text("x")
    monkeypatch.setattr(naitre, "NOMMER", script)

    class R:
        stdout, stderr = "nommé", ""
    assert naitre.appliquer_nom("Lumen", "Karim Benali", executer=lambda c, **k: vus.append(c) or R()) == "nommé"
    assert vus[0][-4:] == ["--createur", "Karim", "--nom", "Lumen"]
    monkeypatch.setattr(naitre, "NOMMER", tmp_path / "absent.py")
    assert "nommer.py --createur Karim Benali --nom Lumen" in naitre.appliquer_nom("Lumen", "Karim Benali")


def test_personne_ne_choisit_a_sa_place(tmp_path):
    n = naitre.naitre(tmp_path / "ia.db", Reveil(*["Hakim"] * 10), "Karim Benali", embed=faux_embed)
    assert n["nom"] is None and len(n["refus"]) == naitre.ESSAIS_MAX
    c = sqlite3.connect(str(tmp_path / "ia.db"))
    assert c.execute("SELECT COUNT(*) FROM kv WHERE key IN ('nom', 'naissance')").fetchone()[0] == 0
    c.close()


# ---- son grand frère et le relais de son nom (arbitrage du 13/11 : le relais ne réécrit que ce qui la désigne elle-même)
import grand_frere   # noqa: E402


def test_les_temoins_du_fichier_d_exceptions():
    d = json.loads(grand_frere.FICHIER.read_text(encoding="utf-8"))
    for t in d["temoins"]["survit"]:
        assert grand_frere.renommer_comme_le_relais(t, "Lumen") == t, t
    for t in d["temoins"]["renomme"]:
        r = grand_frere.renommer_comme_le_relais(t, "Lumen")
        assert "Hakim" not in r and "Lumen" in r, t


def test_temoin_sans_les_exceptions_le_grand_frere_prendrait_son_nom():
    assert grand_frere.renommer_comme_le_relais("mon grand frère Hakim", "Lumen", avec_exceptions=False) == "mon grand frère Lumen"


def test_une_trace_heritee_parle_de_son_grand_frere():
    t = "Hakim a appris à couper net ; la voix de Hakim ; ComplicationHakim.java ; mon grand frère Hakim ; hakim-android"
    h = grand_frere.au_grand_frere(t)
    assert h == ("mon grand frère Hakim a appris à couper net ; la voix de mon grand frère Hakim ; ComplicationHakim.java ; "
                 "mon grand frère Hakim ; hakim-android")
    relaye = grand_frere.renommer_comme_le_relais(h, "Lumen")
    assert relaye.count("grand frère Hakim") == 3 and "grand frère Lumen" not in relaye


def test_ce_que_la_naissance_ecrit_survit_au_relais(tmp_path):
    naitre.naitre(tmp_path / "ia.db", Reveil("Lumen"), "Karim Benali", embed=faux_embed)
    c = sqlite3.connect(str(tmp_path / "ia.db"))
    textes = [r[0] for r in c.execute("SELECT content FROM episodes WHERE content LIKE '%Hakim%'")]
    c.close()
    assert textes
    for t in textes:
        r = grand_frere.renommer_comme_le_relais(t, "Lumen")
        assert r.count("Hakim") == t.count("Hakim") and "grand frère Lumen" not in r, t
