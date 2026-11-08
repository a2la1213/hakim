"""(03/11, Ahmed : « micro ouvert ; on le laisse apprendre à détecter les sons, les bruits, les voix qui se mélangent, une
seule voix… il faut qu'il apprenne de lui-même à écouter ») ses familles de sons : apprises seules, nommées par lui.
La forme d'un son vient de l'encodeur du petit Whisper (stt_vif.py) ; ici, des vecteurs faits à la main."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import sons_familles as F  # noqa: E402

R = np.random.default_rng(7)
COMMUN = R.normal(0, 1, 64) * 5                     # ce que tous les sons partagent (la « couleur » de l'encodeur)
GENRES = {g: R.normal(0, 1, 64) for g in ("voix", "musique", "frigo")}


def son(genre):
    return COMMUN + GENRES[genre] + R.normal(0, 0.25, 64)


def ecouter_d_abord(fi, t=0.0):
    for k in range(F.ECOUTE_MIN):
        assert F.entendre(son(("voix", "musique", "frigo")[k % 3]), fichier=fi, maintenant=t + k) is None, "il écoute d'abord"


def test_il_ecoute_d_abord_puis_range_seul_en_familles(tmp_path):
    fi = tmp_path / "familles.json"
    ecouter_d_abord(fi)
    a = F.entendre(son("voix"), fichier=fi, maintenant=100.0)
    assert a["nouvelle"] and a["famille"] == "son 1"
    assert F.entendre(son("voix"), fichier=fi, maintenant=101.0)["famille"] == "son 1", "une voix encore : la même famille"
    b = F.entendre(son("musique"), fichier=fi, maintenant=102.0)
    assert b["nouvelle"] and b["famille"] == "son 2", "de la musique : autre chose, malgré tout ce qu'elles partagent"
    assert F.entendre(son("frigo"), fichier=fi, maintenant=103.0)["famille"] == "son 3"
    assert F.entendre(son("musique"), fichier=fi, maintenant=104.0)["famille"] == "son 2"
    assert oct(fi.stat().st_mode & 0o777) == "0o600"


def test_il_nomme_ses_familles_et_retient_ce_qu_elles_portent(tmp_path):
    fi = tmp_path / "familles.json"
    ecouter_d_abord(fi)
    F.entendre(son("voix"), fichier=fi, maintenant=100.0, parole=True)
    F.entendre(son("voix"), fichier=fi, maintenant=101.0, parole=True, voix=2)
    F.nommer("son 1", "papa et ses potes", fichier=fi)
    assert F.entendre(son("voix"), fichier=fi, maintenant=102.0)["famille"] == "papa et ses potes"
    l = F.lister(fichier=fi)
    assert l[0]["nom"] == "papa et ses potes" and l[0]["fois"] == 3 and l[0]["avec_parole"] == 2 and l[0]["plusieurs_voix"] == 1
    with pytest.raises(ValueError):
        F.nommer("son 9", "rien", fichier=fi)
    with pytest.raises(ValueError):
        F.nommer("son 1", "[voix 2] piège", fichier=fi)
