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


def test_eteint_rien():
    assert style.consigne(Mem(actif=False), now=T) is None


def test_chaque_famille_a_sa_forme_et_le_fond_passe_avant():
    vus = {}
    for emo in ("élan", "gratitude", "calme", "curiosité", "peur", "tristesse"):
        s = style.consigne(Mem(emotion=emo), now=T)
        vus[s["famille"]] = s["texte"]
        assert "jamais le fond" in s["texte"] and "honnêteté" in s["texte"]
    assert set(vus) == {"élan", "lien", "calme", "curiosité", "alerte", "bas"}
    assert "pas de blague" in vus["alerte"] and "PRIORITAIRE" in vus["alerte"] and "au plus 60 %" in vus["alerte"]
    assert "aucune exclamation" in vus["calme"] and "PRIORITAIRE" not in vus["calme"]
    assert "humour" in vus["élan"] and "affection" in vus["lien"]


def test_les_gestes_sont_notes_et_l_energie_les_ajuste():
    s = style.depuis_etat("joie", 0.60, 0.40)
    assert s["cibles"]["mots_par_phrase"] == 15 and "rythme rapide" in s["texte"] and not s["prioritaire"]
    b = style.depuis_etat("calme", 0.20, 0.40)
    assert b["cibles"]["longueur"] == 0.8 and "plus brève" in b["texte"]
    assert style.depuis_etat("tristesse", 0.4, 0.4)["prioritaire"]


def test_un_choc_change_le_style_du_meme_tour():
    m = Mem()
    affect.event(m, "attaque", 1.0, now=T - 5, hour=12)        # l'émotion se recalcule (pas de battement frais)
    s = style.consigne(m, now=T)
    assert s["famille"] == "alerte"


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
