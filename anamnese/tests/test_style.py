"""Le style du moment (style.py) et les nombres de la voix (jarvis/voix_nombres.py), 2026-10-23."""
import json
import math
import sys
from pathlib import Path

import affect
import interieur
import style

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import voix_nombres  # noqa: E402

T = 1_800_000_000.0


class Mem:
    def __init__(self, actif=True, emotion=None):
        self.kv = {"affect_v2": "1", "style_actif": "1" if actif else "0"}
        if emotion:
            self.kv["interieur"] = json.dumps({"sensation_code": {"emotion": emotion, "ts": T}})

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def _isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(style, "JOURNAL_TEMPS", str(tmp_path / "absent.jsonl"))   # jamais le vrai journal


def test_eteint_rien():
    assert style.consigne(Mem(actif=False), now=T) is None


def test_chaque_famille_a_sa_forme_le_fond_passe_avant_et_la_longueur_est_libre():
    vus = {}
    for emo, c in (("élan", {"ton": 9, "energie": 8, "affection": 5, "tension": 1}),
                   ("gratitude", {"ton": 7, "energie": 4, "affection": 9, "tension": 1}),
                   ("calme", {"ton": 6, "energie": 2, "affection": 5, "tension": 1}),
                   ("curiosité", {"ton": 6, "energie": 6, "affection": 4, "tension": 2}),
                   ("peur", {"ton": 3, "energie": 9, "affection": 4, "tension": 8}),
                   ("tristesse", {"ton": 2, "energie": 2, "affection": 3, "tension": 3})):
        s = style.depuis_curseurs(emo, c)
        vus[s["famille"]] = s
        assert "jamais le fond" in s["texte"] and "LONGUEUR reste celle que demande le sujet" in s["texte"]
        assert "longueur" not in s["cibles"]
    assert set(vus) == {"élan", "lien", "calme", "curiosité", "alerte", "bas"}
    assert vus["alerte"]["prioritaire"] and vus["alerte"]["cibles"]["humour"] == "aucun" and vus["alerte"]["cibles"]["exclamations"] == 0
    assert vus["élan"]["cibles"]["humour"] == "permis" and vus["élan"]["cibles"]["exclamations"] == 2
    assert vus["calme"]["cibles"]["mots_par_phrase"] > vus["élan"]["cibles"]["mots_par_phrase"]     # posé : des phrases plus longues


def test_une_alerte_doit_se_voir_dans_les_curseurs():
    s = style.depuis_curseurs("surprise", {"ton": 8, "energie": 7, "affection": 5, "tension": 1})
    assert s["famille"] == "élan" and not s["prioritaire"]


def test_les_curseurs_sont_relatifs_a_ses_trois_derniers_jours():
    b = affect.bases(v2=True)
    rv = sorted(0.40 + 0.01 * k for k in range(41))
    ra = sorted(0.30 + 0.01 * k for k in range(41))
    haut = style.curseurs(b, 0.79, 0.65, rv, ra)
    bas = style.curseurs(b, 0.45, 0.32, rv, ra)
    assert haut["ton"] > bas["ton"] and haut["energie"] > bas["energie"]
    assert style.curseurs({**b, "adrenaline": 0.4}, 0.6, 0.4, rv, ra)["tension"] == 10
    assert style.curseurs(b, 0.6, 0.4, rv, ra, choc=True)["tension"] >= 8


def test_les_reperes_sont_gardes_une_demi_heure(tmp_path, monkeypatch):
    f = tmp_path / "jt.jsonl"
    f.write_text("\n".join(json.dumps({"t": T - k * 60, "valence": 0.5 + 0.001 * k, "arousal": 0.4}) for k in range(400)))
    monkeypatch.setattr(style, "JOURNAL_TEMPS", str(f))
    m = Mem()
    v, _a = style.reperes(T, m)
    assert len(v) > 20 and json.loads(m.kv["style_reperes"])["ts"] == T
    f.write_text("")
    assert style.reperes(T + 60, m)[0] == v                    # depuis le cache


def test_un_choc_change_le_style_du_meme_tour(tmp_path, monkeypatch):
    _isoler(tmp_path, monkeypatch)
    m = Mem()
    affect.event(m, "attaque", 1.0, now=T - 5, hour=12)
    s = style.consigne(m, now=T)
    assert s["famille"] == "alerte" and s["prioritaire"] and s["curseurs"]["tension"] >= 8


def test_trois_nombres_par_morceau(tmp_path):
    sr = 24000
    t = [k / sr for k in range(int(1.5 * sr))]
    onde = [0.3 * math.sin(2 * math.pi * 140 * x) for x in t]
    m = voix_nombres.mesurer(onde, sr)
    assert m["duree_s"] == 1.5 and abs(m["hauteur_hz"] - 140) < 3 and -14 < m["energie_db"] < -12
    o = voix_nombres.noter(onde, sr, "Bonjour frérot.", "fr", {"exaggeration": 0.6, "cfg_weight": 0.42, "temperature": 0.8},
                           fichier=tmp_path / "v.jsonl")
    ligne = json.loads((tmp_path / "v.jsonl").read_text())
    assert ligne == o and ligne["mots"] == 2 and ligne["exaggeration"] == 0.6 and "temperature" not in ligne


def test_le_debit_suit_l_eveil_dans_ses_bornes():
    s = {"emotion": "calme"}
    base = interieur.voix(0.5, s)["vitesse"]
    assert interieur.voix(0.5, s, interieur._BASE_A + 0.14)["vitesse"] > base > interieur.voix(0.5, s, interieur._BASE_A - 0.14)["vitesse"]
    assert 0.92 <= interieur.voix(0.5, {"emotion": "élan"}, 1.0)["vitesse"] <= 1.06
