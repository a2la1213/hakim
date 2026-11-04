"""(04/11, Ahmed : « entraîne Supertonic avec les émotions de Chatterbox, qu'on sente ses émotions dans sa voix ») ses styles
d'émotion : la voix M1 qu'Ahmed a choisie, poussée dans la direction qui sépare, chez Chatterbox, une émotion de sa voix neutre.
Chaque ligne d'un style reste sur la sphère unité, comme dans les styles publiés (vérifié sur M1-M5, F1-F5) ; le style de
durée reste celui de M1 (son débit par émotion est déjà réglé ailleurs : interieur.VOIX_EMOTION)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import styles_supertonic as S  # noqa: E402


def _style(graine):
    r = np.random.default_rng(graine)
    return {"ttl": S.sur_la_sphere(r.normal(size=(50, 256))), "dp": S.sur_la_sphere(r.normal(size=(8, 16)))}


def test_un_style_se_relit_tel_qu_il_a_ete_ecrit_au_format_des_styles_publies(tmp_path):
    s = _style(1)
    f = tmp_path / "M1-joie.json"
    S.ecrire(s, f, source="essai")
    brut = json.loads(f.read_text())
    assert brut["style_ttl"]["dims"] == [1, 50, 256] and brut["style_dp"]["dims"] == [1, 8, 16]
    assert brut["style_ttl"]["type"] == "float32" and np.array(brut["style_ttl"]["data"]).shape == (1, 50, 256)
    assert brut["metadata"]["source"] == "essai"
    lu = S.lire(f)
    assert np.allclose(lu["ttl"], s["ttl"], atol=1e-6) and np.allclose(lu["dp"], s["dp"], atol=1e-6)


def test_appliquer_garde_chaque_ligne_sur_la_sphere_et_la_duree_de_la_base():
    base, emo, neutre = _style(1), _style(2), _style(3)
    r = S.appliquer(base, emo, neutre, force=0.8)
    assert np.allclose(np.linalg.norm(r["ttl"], axis=1), 1.0)
    assert np.array_equal(r["dp"], base["dp"]), "son débit reste celui de M1"


def test_force_nulle_rend_la_base_et_la_force_eloigne_de_la_base_dans_le_sens_de_l_emotion():
    base, emo, neutre = _style(1), _style(2), _style(3)
    assert np.allclose(S.appliquer(base, emo, neutre, force=0.0)["ttl"], base["ttl"])
    d = emo["ttl"] - neutre["ttl"]
    proj = [float(np.sum((S.appliquer(base, emo, neutre, force=f)["ttl"] - base["ttl"]) * d)) for f in (0.25, 0.5, 1.0)]
    assert 0 < proj[0] < proj[1] < proj[2]


def test_une_emotion_identique_au_neutre_ne_change_rien():
    base, neutre = _style(1), _style(3)
    assert np.allclose(S.appliquer(base, neutre, neutre, force=1.0)["ttl"], base["ttl"])


def test_melanger_va_de_la_base_a_l_emotion_par_l_intensite_comme_le_fera_le_telephone():
    base, emo = _style(1), _style(2)
    assert np.allclose(S.melanger(base, emo, 0.0)["ttl"], base["ttl"])
    assert np.allclose(S.melanger(base, emo, 1.0)["ttl"], emo["ttl"])
    m = S.melanger(base, emo, 0.5)["ttl"]
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0)
    assert np.allclose(S.melanger(base, emo, 0.5)["dp"], base["dp"])


def test_un_style_mal_forme_est_refuse(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"style_ttl": {"data": [[[0.0] * 256] * 49], "dims": [1, 49, 256], "type": "float32"},
                             "style_dp": {"data": [[[0.0] * 16] * 8], "dims": [1, 8, 16], "type": "float32"}}))
    with pytest.raises(ValueError):
        S.lire(f)
