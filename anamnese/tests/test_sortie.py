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
