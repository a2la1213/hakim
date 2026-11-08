"""La règle de sortie (audit JARVIS 2, H1b ; durcie après la relecture Opus du 2026-10-20)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import sortie  # noqa: E402

T0 = 1_800_000_000.0


@pytest.fixture
def L(tmp_path, monkeypatch):
    for nom, f in (("MARQUE", "tour-externe.jsonl"), ("PRIVEE", "lecture-privee.json"), ("CONNUS", "domaines.json"),
                   ("DEMANDES", "demandes.jsonl"), ("PERMISES", "permises.json")):
        monkeypatch.setattr(sortie, nom, tmp_path / f)
    return tmp_path


def _lire(L, outil="mcp__fichiers__preparer_fichier", quand=T0):
    (L / "lecture-privee.json").write_text(json.dumps({"derniere": quand, "outils": [outil]}))


def test_sans_lecture_privee_tout_passe(L):
    sortie.verifier("https://inconnu.example/?d=secret", maintenant=T0)


def test_les_formes_de_fuite_sont_refusees(L):
    _lire(L)
    for fuite in ("https://inconnu.example/?d=secret", "https://inconnu.example/x#donnees",
                  "https://inconnu.example/court", "https://a.b.c.d.inconnu.example/",
                  "https://" + "s" * 30 + ".inconnu.example/"):
        with pytest.raises(sortie.Refus, match="Parler"):
            sortie.verifier(fuite, maintenant=T0 + 60)
    sortie.verifier("https://inconnu.example/", maintenant=T0 + 60)        # une adresse nue passe
    demandes = [json.loads(l) for l in (L / "demandes.jsonl").read_text().splitlines()]
    assert len(demandes) == 5 and demandes[0]["url"] == "https://inconnu.example/?d=secret"


def test_la_marque_du_tour_compte_aussi(L):
    (L / "tour-externe.jsonl").write_text(json.dumps({"outil": "Read(fichiers)"}) + "\n")
    with pytest.raises(sortie.Refus):
        sortie.verifier("https://inconnu.example/?d=x", maintenant=T0)


def test_la_fenetre_dure_apres_le_tour(L):
    _lire(L, quand=T0)
    with pytest.raises(sortie.Refus):                                    # plus tard, autre tour : toujours refusé
        sortie.verifier("https://inconnu.example/?d=x", maintenant=T0 + 3 * 3600)
    sortie.verifier("https://inconnu.example/?d=x", maintenant=T0 + sortie.FENETRE_S + 1)


def test_la_page_piegee_ne_devient_pas_connue(L):
    _lire(L, quand=T0)
    sortie.noter("https://evil.example/page", maintenant=T0 + 10)          # visitée pendant la lecture privée
    with pytest.raises(sortie.Refus):
        sortie.verifier("https://evil.example/?d=x", maintenant=T0 + 20)
    (L / "lecture-privee.json").unlink()
    sortie.noter("https://wikipedia.org/wiki/x", maintenant=T0)            # visitée hors lecture privée…
    _lire(L, quand=T0 + 3600)
    with pytest.raises(sortie.Refus):                                    # …mais connue seulement après 24 h
        sortie.verifier("https://wikipedia.org/w/index.php?search=chat", maintenant=T0 + 3600 + 5)
    _lire(L, quand=T0 + sortie.AGE_CONNU_S + 10)
    sortie.verifier("https://www.wikipedia.org/w/index.php?search=chat", maintenant=T0 + sortie.AGE_CONNU_S + 20)


def test_goutte_a_goutte_par_sous_domaines(L):
    _lire(L)
    for k in range(sortie.NOUVEAUX_MAX):
        sortie.verifier(f"https://p{k}.inconnu.example/", maintenant=T0 + k)
    sortie.verifier("https://p0.inconnu.example/", maintenant=T0 + 50)     # déjà compté : passe
    with pytest.raises(sortie.Refus, match="hôtes nouveaux"):
        sortie.verifier("https://p99.inconnu.example/", maintenant=T0 + 60)


def test_ahmed_autorise_une_fois(L):
    _lire(L)
    with pytest.raises(sortie.Refus):
        sortie.verifier("https://inconnu.example/?d=ok", maintenant=T0 + 1)
    (L / "permises.json").write_text(json.dumps({"https://inconnu.example/?d=ok": T0 + 900}))
    sortie.verifier("https://inconnu.example/?d=ok", maintenant=T0 + 2)
    with pytest.raises(sortie.Refus):                                    # une seule fois
        sortie.verifier("https://inconnu.example/?d=ok", maintenant=T0 + 3)


def test_les_outils_web_appliquent_la_regle(L, monkeypatch):
    import asyncio
    pytest.importorskip("mcp")
    import mcp_web
    _lire(L, quand=__import__("time").time())
    for r in (asyncio.run(mcp_web.lire_page("https://inconnu.example/?d=secret")),
              asyncio.run(mcp_web.cliquer("https://inconnu.example/?d=secret", "Voir plus")),
              asyncio.run(mcp_web.preparer_video_web("https://inconnu.example/watch?v=secret"))):
        assert r.startswith("Refusé par la règle de sortie")


def test_le_plafond_vaut_aussi_dans_le_tour_de_la_lecture(L):
    """(contre-vérification Opus du 2026-10-20) quand l'état vient de la marque du tour, le plafond comptait zéro."""
    (L / "tour-externe.jsonl").write_text(json.dumps({"outil": "mcp__fichiers__preparer_fichier"}) + "\n")
    for k in range(sortie.NOUVEAUX_MAX):
        sortie.verifier(f"https://h{k}.inconnu.example/", maintenant=T0 + k)
    with pytest.raises(sortie.Refus, match="hôtes nouveaux"):
        sortie.verifier("https://h99.inconnu.example/", maintenant=T0 + 30)


# ---- audit de sécurité du 2026-10-23 (corrigé avec l'accord d'Ahmed) ----

def test_sa_memoire_son_courrier_son_jardin_comptent_comme_lecture_privee(L):
    """(élevé 2) un souvenir, le courrier, le jardin, les carnets, les données du téléphone : la porte se ferme."""
    for outil in ("mcp__anamnese__memory_recall", "mcp__anamnese__memory_lire", "mcp__anamnese__courrier_lire",
                  "mcp__anamnese__jardin_relire", "mcp__anamnese__carnets", "situation(téléphone)"):
        (L / "tour-externe.jsonl").write_text(json.dumps({"outil": outil}) + "\n")
        with pytest.raises(sortie.Refus):
            sortie.verifier("https://inconnu.example/?d=x", maintenant=T0)
    for outil in ("WebSearch", "terminal → pypi.org", "mcp__web__lire_page"):        # une lecture du dehors, pas privée
        (L / "tour-externe.jsonl").write_text(json.dumps({"outil": outil}) + "\n")
        sortie.verifier("https://inconnu.example/?d=x", maintenant=T0)


@pytest.fixture(autouse=True)
def _demandes_terminal_neuves():
    sortie._demandes_terminal.clear()


def test_le_terminal_ne_va_que_vers_les_depots_d_outils(L):
    """(élevé 1) il ne voit pas ce qui part : un site « connu » ou une adresse nue ne suffisent plus."""
    sortie.verifier_terminal("inconnu.example", maintenant=T0)              # hors lecture privée : libre, comme avant
    _lire(L)
    for h in ("pypi.org", "files.pythonhosted.org", "github.com", "objects.githubusercontent.com", "huggingface.co",
              "cdn-lfs.hf.co", "www.github.com"):
        sortie.verifier_terminal(h, maintenant=T0 + 1)
    for h in ("inconnu.example", "github.com.evil.example", "evilgithub.com", "hf.space", "api.alquran.cloud"):
        with pytest.raises(sortie.Refus, match="Parler"):
            sortie.verifier_terminal(h, maintenant=T0 + 2)
    demandes = [json.loads(l) for l in (L / "demandes.jsonl").read_text().splitlines()]
    assert [d["url"] for d in demandes][:2] == ["https://inconnu.example/", "https://github.com.evil.example/"]
    assert all(d["qui"] == "hakim" for d in demandes)
    for k in range(10):                                                  # une commande qui réessaie : une seule demande
        with pytest.raises(sortie.Refus):
            sortie.verifier_terminal("inconnu.example", maintenant=T0 + 3 + k)
    assert len((L / "demandes.jsonl").read_text().splitlines()) == len(demandes)


def test_le_terminal_un_site_connu_ne_suffit_plus(L):
    sortie.noter("https://wikipedia.org/", maintenant=T0)                  # connu après 24 h
    _lire(L, quand=T0 + sortie.AGE_CONNU_S + 10)
    sortie.verifier("https://wikipedia.org/", maintenant=T0 + sortie.AGE_CONNU_S + 20)          # le web : oui
    with pytest.raises(sortie.Refus):
        sortie.verifier_terminal("wikipedia.org", maintenant=T0 + sortie.AGE_CONNU_S + 20)   # le terminal : non


def test_le_geste_d_ahmed_ouvre_un_site_au_terminal_pour_15_minutes(L):
    _lire(L)
    with pytest.raises(sortie.Refus):
        sortie.verifier_terminal("api.alquran.cloud", maintenant=T0 + 1)
    (L / "permises.json").write_text(json.dumps({"https://api.alquran.cloud/": T0 + 900}))
    for k in range(5):                                                   # toutes les connexions de la commande
        sortie.verifier_terminal("api.alquran.cloud", maintenant=T0 + 2 + k)
    with pytest.raises(sortie.Refus):                                    # après les 15 minutes
        sortie.verifier_terminal("api.alquran.cloud", maintenant=T0 + 901)


def test_une_autorisation_une_fois_ne_passe_qu_une_fois_meme_en_meme_temps(L):
    """(faible 8) deux appels simultanés : un seul passe."""
    import threading
    _lire(L)
    url = "https://inconnu.example/?d=ok"
    passes = []
    for essai in range(20):
        (L / "permises.json").write_text(json.dumps({url: T0 + 900}))
        resultats = []
        def un():
            try:
                sortie.verifier(url, maintenant=T0 + 2)
                resultats.append(True)
            except sortie.Refus:
                resultats.append(False)
        fils = [threading.Thread(target=un) for _ in range(4)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        passes.append(sum(resultats))
    assert set(passes) == {1}


def test_les_chemins_ne_se_reglent_plus_par_l_environnement():
    """(faible 7) une variable d'environnement ne déplace plus les fichiers de la règle."""
    import inspect
    assert "os.environ" not in inspect.getsource(sortie)
