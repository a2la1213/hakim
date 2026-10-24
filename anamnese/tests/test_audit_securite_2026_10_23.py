"""Audit de sécurité du 2026-10-23 (mission de Hakim, corrigé avec l'accord d'Ahmed) : les points faibles 9 et 10, et
les permissions (point 6). Les points 1, 2, 5, 7 et 8 sont testés dans test_sortie.py et test_jarvis_fichiers.py."""
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


def test_la_voix_n_ecrit_que_dans_le_dossier_temporaire():
    """(faible 10) le chemin de sortie de la voix n'était pas validé."""
    voix_serveur = pytest.importorskip("voix_serveur")
    tmp = tempfile.gettempdir()
    assert voix_serveur.sortie_permise(os.path.join(tmp, "jarvis-voix-123-456-abcd.wav"))
    for mauvais in ("/Users/admin/.zshrc", os.path.join(tmp, "autre.wav"), os.path.join(tmp, "jarvis-voix-x.sh"),
                    os.path.join(tmp, "sous", "jarvis-voix-x.wav"), os.path.join(tmp, "..", "jarvis-voix-x.wav"), "", None):
        assert not voix_serveur.sortie_permise(mauvais), mauvais
    r = voix_serveur.traiter({"op": "dire", "texte": "bonjour", "fichier": "/tmp/../Users/admin/piege.wav"})
    assert "refusé" in r["erreur"]


def test_le_tableau_de_bord_sert_plusieurs_clients():
    """(faible 9) un client lent bloquait le tableau de bord."""
    import dashboard
    src = Path(dashboard.__file__).read_text(encoding="utf-8")
    assert "ThreadingHTTPServer((" in src and "    HTTPServer((" not in src
    assert 0 < dashboard.Handler.timeout <= 30


def test_le_courrier_est_lisible_par_ahmed_seul(tmp_path):
    """(moyen 6) le courrier était écrit avec les droits par défaut (lisible par les autres comptes du Mac)."""
    import courrier
    f = tmp_path / "courrier.jsonl"
    courrier.envoyer("hakim", "un test", sujet="droits", de="claude-code", fichier=f)
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_la_voix_borne_et_vide_son_cache_mlx():
    """(24/10, 17:43) la voix tenait 10 Go de tampons Metal gardés par MLX : cache borné au démarrage, vidé après chaque
    demande (sans dépendre de MLX ici : on vérifie que les appels sont faits)."""
    voix_serveur = pytest.importorskip("voix_serveur")
    appels = []
    import types
    faux = types.SimpleNamespace(set_cache_limit=lambda n: appels.append(("limite", n)), clear_cache=lambda: appels.append(("vide",)))
    sys.modules["mlx"] = types.SimpleNamespace(core=faux)
    sys.modules["mlx.core"] = faux
    try:
        voix_serveur.borner_cache(); voix_serveur.vider_cache()
    finally:
        del sys.modules["mlx.core"]; del sys.modules["mlx"]
    assert appels == [("limite", voix_serveur.CACHE_MAX_OCTETS), ("vide",)]
    assert voix_serveur.CACHE_MAX_OCTETS <= 1024 * 1024 * 1024
