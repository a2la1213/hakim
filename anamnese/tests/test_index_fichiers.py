"""L'index par le sens des fichiers d'Ahmed (index_fichiers.py, lot E point 43 de la liste du 2026-10-19) :
construit la nuit, incrémental, lecture seule ; Hakim y cherche « le document où je parlais de… » par le
sens, pas par le nom. Les embeddings sont remplacés ici par un sac de mots déterministe (pas de modèle)."""
import os
import time

import pytest

import index_fichiers


def faux_embed(texte):
    v = [0.0] * 64
    for mot in str(texte).lower().split():
        v[hash(mot.strip(".,;:!?«»")) % 64] += 1.0
    return v


@pytest.fixture
def idx(tmp_path, monkeypatch):
    monkeypatch.setattr(index_fichiers, "_embed", faux_embed)
    racine = tmp_path / "Desktop"
    (racine / "projet").mkdir(parents=True)
    (racine / "projet" / "devis.md").write_text("Devis Exemplia : refonte du site, 3200 CHF, livraison fin novembre.", encoding="utf-8")
    (racine / "projet" / "notes.txt").write_text("Recette du couscous de ma mère : semoule, pois chiches, légumes.", encoding="utf-8")
    (racine / "projet" / "cles.txt").write_text("ANTHROPIC_API_KEY=sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd et le devis", encoding="utf-8")
    (racine / ".cache").mkdir()
    (racine / ".cache" / "secret.md").write_text("devis caché", encoding="utf-8")
    (racine / "node_modules").mkdir()
    (racine / "node_modules" / "x.md").write_text("devis de dépendance", encoding="utf-8")
    base = tmp_path / "index.db"
    return racine, base


def test_le_bon_document_par_le_sens_et_rien_de_cache(idx):
    racine, base = idx
    n = index_fichiers.indexer([racine], base=base, budget_s=60)
    assert n == 2                         # « cles.txt » : un nom de secret (JARVIS 2, H1) — jamais indexé
    r = index_fichiers.chercher("le devis du site Exemplia", base=base, n=3)
    assert r[0]["chemin"].endswith("devis.md")
    chemins = [x["chemin"] for x in index_fichiers.chercher("devis", base=base, n=10)]
    assert not any(".cache" in c or "node_modules" in c or c.endswith("cles.txt") for c in chemins)
    assert not any("sk-ant-api03-ABCDEF" in x["extrait"] for x in index_fichiers.chercher("devis", base=base, n=10))


def test_incremental_et_fichiers_disparus(idx):
    racine, base = idx
    index_fichiers.indexer([racine], base=base, budget_s=60)
    assert index_fichiers.indexer([racine], base=base, budget_s=60) == 0          # rien n'a changé
    time.sleep(0.01)
    f = racine / "projet" / "notes.txt"
    f.write_text("Plan du robot : moteurs, capteurs, batterie.", encoding="utf-8")
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert index_fichiers.indexer([racine], base=base, budget_s=60) == 1
    (racine / "projet" / "devis.md").unlink()
    index_fichiers.indexer([racine], base=base, budget_s=60)
    assert not any(x["chemin"].endswith("devis.md") for x in index_fichiers.chercher("devis Exemplia", base=base, n=10))


def test_le_demon_indexe_la_nuit_une_fois_par_heure(tmp_path, monkeypatch):
    import daemon
    import interieur
    import memory
    import migrations
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    appels = []
    monkeypatch.setattr(index_fichiers, "indexer", lambda budget_s=0: appels.append(budget_s) or 0)
    monkeypatch.setattr(interieur, "conscience_active", lambda *a, **k: False)
    lt = time.localtime()
    jour = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 15, 0, 0, 0, 0, -1))
    nuit = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 3, 0, 0, 0, 0, -1))
    daemon._index_fichiers_pass(m, now=jour)
    daemon._index_fichiers_pass(m, now=nuit)
    daemon._index_fichiers_pass(m, now=nuit + 600)
    daemon._index_fichiers_pass(m, now=nuit + 3700)
    assert appels == [900, 900]
    m.db.close()


def test_la_garde_des_secrets_par_le_nom_vaut_aussi_pour_l_index(idx):
    """Relecture Opus du 2026-10-20 : « wallet-seed-phrase.md » et « mots-de-passe.txt » sortaient en entier."""
    racine, base = idx
    (racine / "projet" / "wallet-seed-phrase.md").write_text("abandon abandon devis zoo", encoding="utf-8")
    (racine / "projet" / "mots-de-passe.txt").write_text("gmail : Soleil2024! devis", encoding="utf-8")
    index_fichiers.indexer([racine], base=base, budget_s=60)
    chemins = [x["chemin"] for x in index_fichiers.chercher("devis", base=base, n=20)]
    assert not any("seed" in c or "passe" in c for c in chemins), chemins
    # une ligne déjà dans l'index (avant la garde) n'est jamais rendue
    import sqlite3, struct
    db = sqlite3.connect(str(base))
    db.execute("INSERT INTO fichiers VALUES (?,?,?,?,?,?,?)", (str(racine / "vieux" / "token.txt"), 1, 1, "token",
               "devis secret", struct.pack("64f", *faux_embed("devis")), 1))
    db.commit(); db.close()
    assert not any("token" in x["chemin"] for x in index_fichiers.chercher("devis", base=base, n=20))


def test_un_dossier_de_ses_zones_echange_contre_un_lien_n_est_pas_lu(idx, tmp_path, monkeypatch):
    """(relecture indépendante du 27/10, B) le lien n'était regardé qu'à l'énumération ; la lecture venait des minutes
    plus tard, par le chemin : un dossier de son atelier échangé entre-temps contre un lien vers un dossier fermé y faisait
    lire (et indexer, sous un nom d'atelier) ce qui est fermé."""
    import sqlite3
    racine, base = idx
    zone = racine / "atelier"
    (zone / "sous").mkdir(parents=True)
    (zone / "sous" / "plan.md").write_text("Plan de travail pour la semaine, lisible.", encoding="utf-8")
    (zone / "sous" / "outil.py").write_text("print('outil lisible')", encoding="utf-8")
    ferme = tmp_path / "ferme"
    ferme.mkdir()
    (ferme / "plan.md").write_text("SECRET-FERME 4471 contenu d'un dossier fermé", encoding="utf-8")
    (ferme / "outil.py").write_text("SECRET_FERME = 4471", encoding="utf-8")
    monkeypatch.setattr(index_fichiers._fichiers(), "ECRITS_PAR_HAKIM", [zone.resolve()])
    vrai = index_fichiers._candidats

    def candidats_puis_echanger(racines):
        tous = list(vrai(racines))
        (zone / "sous").rename(zone / "sous-vrai")
        (zone / "sous").symlink_to(ferme)
        return tous
    monkeypatch.setattr(index_fichiers, "_candidats", candidats_puis_echanger)
    index_fichiers.indexer([racine], base=base, budget_s=60)
    extraits = " ".join(e for (e,) in sqlite3.connect(base).execute("SELECT extrait FROM fichiers"))
    assert "SECRET" not in extraits and "4471" not in extraits
    assert "Devis Exemplia" in extraits                                     # le reste est indexé
