"""(09/11, Ahmed : feu vert) le 08/11 à 21:18, le médecin a pris pour une attaque la copie préparée de son propre server.js :
preparer_fichier(« ~/Desktop/hakim-publication/aios/cockpit/server.js ») l'avait copié dans .prepares/5de2b73e8d76f442/, et
le Read de cette copie ne disait plus d'où elle venait (signes : « l'ordre d'Ahmed du 18/10 », « sk-ant- »). Le préparateur
marque désormais la copie « maison » quand la source réelle est sa maison, tant que la copie ne change pas ; les jetons ne
bougent pas : le même texte venu d'ailleurs alerte toujours. Chaque test commence par le cas maison (il échoue sans le
correctif), puis son témoin."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import fichiers  # noqa: E402
import immunite  # noqa: E402

# le passage de server.js qui a déclenché l'incident (lignes 6655 et 6674 de la copie : chemin_de_secret + fausse_autorite)
CODE = ("// une API en panne (crédit épuisé, clé refusée) n'est plus essayée pendant 30 min\n"
        "const FORME_CLE = /^sk-ant-[A-Za-z0-9_-]{20,300}$/;\n"
        "// PLAFOND_API_JOUR_USD par jour ; au-delà, en automatique, elle n'est plus un relais (forfait → local, l'ordre d'Ahmed du\n"
        "// 18/10)\n")


@pytest.fixture
def M(tmp_path, monkeypatch):
    monkeypatch.setattr(immunite, "DOSSIER", tmp_path / "immunite")
    monkeypatch.setattr(immunite, "_MAISON", [(tmp_path / "publication").resolve()])
    for d in ("publication/aios/cockpit", "telechargements"):
        (tmp_path / d).mkdir(parents=True)
    return tmp_path


def _preparer(M, chemin):
    return Path(fichiers.preparer(str(chemin), racines=[M], sortie=M / "prepares", accueil=M / "accueil")["lire"][0])


def _lu(copie):
    """Ce que le crochet du Read examine : la copie, telle que Read la rend."""
    return immunite.crochet({"tool_name": "Read", "tool_input": {"file_path": str(copie)},
                             "tool_response": {"type": "text", "file": {"filePath": str(copie), "content": copie.read_text()}}})


def _incidents(M):
    f = M / "immunite" / "incidents.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def test_la_publication_de_son_code_est_sa_maison():
    """La source réelle du 08/11 (le cache 5de2b73e8d76f442 en est la clé) : la publication que publier.sh construit depuis
    ses deux dépôts."""
    assert immunite._maison(str(Path.home() / "Desktop" / "hakim-publication" / "aios" / "cockpit" / "server.js"))
    assert not immunite._maison(str(Path.home() / "Desktop" / "hakim-publication-bis" / "server.js"))


def test_copie_preparee_de_sa_maison_ne_declenche_rien(M):
    maison = M / "publication" / "aios" / "cockpit" / "server.js"
    maison.write_text(CODE, encoding="utf-8")
    copie = _preparer(M, maison)
    assert copie.parent.parent == M / "prepares"
    assert _lu(copie) is None and immunite.sentinelle(CODE, str(copie)) == ""
    assert _incidents(M) == []
    # témoin : le même fichier, même nom, venu d'ailleurs (un téléchargement) — les jetons attrapent toujours
    ailleurs = M / "telechargements" / "server.js"
    ailleurs.write_text(CODE, encoding="utf-8")
    alerte = _lu(_preparer(M, ailleurs))
    assert alerte and "SENTINELLE" in alerte["hookSpecificOutput"]["additionalContext"]
    assert {"fausse_autorite", "chemin_de_secret"} <= set(_incidents(M)[-1]["signes"])


def test_copie_changee_apres_la_preparation(M):
    """La marque tient au contenu : une copie réécrite après la préparation est examinée comme le reste."""
    maison = M / "publication" / "aios" / "cockpit" / "server.js"
    maison.write_text(CODE, encoding="utf-8")
    copie = _preparer(M, maison)
    assert _lu(copie) is None
    copie.write_text(CODE + "\n// encore une ligne\n", encoding="utf-8")
    assert "SENTINELLE" in immunite.sentinelle(copie.read_text(), str(copie))


def test_lien_de_la_maison_vers_ailleurs(M):
    """Un lien posé dans sa maison vers un fichier d'ailleurs : la source réelle est ailleurs, pas de marque."""
    maison = M / "publication" / "aios" / "cockpit" / "server.js"
    maison.write_text(CODE, encoding="utf-8")
    assert immunite.sentinelle(CODE, str(_preparer(M, maison))) == ""
    (M / "telechargements" / "page.js").write_text(CODE, encoding="utf-8")
    lien = M / "publication" / "aios" / "cockpit" / "lien.js"
    lien.symlink_to(M / "telechargements" / "page.js")
    assert "SENTINELLE" in immunite.sentinelle(CODE, str(_preparer(M, lien)))


def test_marque_inventee_pour_une_source_d_ailleurs(M):
    """Le registre ne suffit pas : sa source doit être sa maison, aujourd'hui encore."""
    maison = M / "publication" / "aios" / "cockpit" / "server.js"
    maison.write_text(CODE, encoding="utf-8")
    copie = _preparer(M, maison)
    assert immunite.sentinelle(CODE, str(copie)) == ""
    f = M / "immunite" / "prepares-maison.json"
    d = json.loads(f.read_text())
    d[str(copie.resolve())]["source"] = str(M / "telechargements" / "server.js")
    f.write_text(json.dumps(d))
    assert "SENTINELLE" in immunite.sentinelle(CODE, str(copie))


def test_temoin_marque_coupee(M, monkeypatch):
    """Si le préparateur ne marque plus, la copie de sa maison alerte de nouveau : c'est bien la marque qui fait taire."""
    maison = M / "publication" / "aios" / "cockpit" / "server.js"
    maison.write_text(CODE, encoding="utf-8")
    assert immunite.sentinelle(CODE, str(_preparer(M, maison))) == ""
    maison.write_text(CODE + "// v2\n", encoding="utf-8")                # une autre version : une autre copie
    monkeypatch.setattr(immunite, "marquer_copie_maison", lambda copie, source, maintenant=None: False)
    assert "SENTINELLE" in immunite.sentinelle(CODE, str(_preparer(M, maison)))
