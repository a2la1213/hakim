"""La sagesse de Hakim (sagesse.py, accord d'Ahmed le 2026-10-22) : réflexe, contrôle noté, juge à l'aveugle la nuit."""
import json

import sagesse as S

T = 1_800_000_000.0


def _tour(tmp_path, **k):
    f = tmp_path / "tour.json"
    f.write_text(json.dumps({"ts": T * 1000, "tour_id": "1", "humeur": "tension", "polarite": -1, "intensite": 0.6,
                             "contexte": [], "suggestion": "atténuer", "sagesse": 0.2, "phrases": 3, **k}))
    return f


def test_decider_note_l_ecart_et_refuse_sans_reflexe(tmp_path):
    j = tmp_path / "s.jsonl"
    ok, t = S.decider("corriger", "il parlait de sa fille", 2, T + 60, _tour(tmp_path), j)
    assert ok and "écart" in t and "phrase 2" in t
    o = json.loads(j.read_text())
    assert o["decision"] == "corriger" and o["ecart"] is True and o["suggestion"] == "atténuer"
    assert S.decider("attenuer", "", 0, T + 60, _tour(tmp_path), j)[1].startswith("Noté : atténuer.")
    assert S.decider("hurler", "", 0, T + 60, _tour(tmp_path), j)[0] is False
    assert S.decider("garder", "", 0, T + 3600, _tour(tmp_path), j)[0] is False          # réflexe trop ancien


def test_le_juge_de_la_nuit_regle_la_sagesse(tmp_path):
    j, p, conv = tmp_path / "s.jsonl", tmp_path / "p.json", tmp_path / "c.json"
    conv.write_text(json.dumps({"messages": [{"id": T * 1000 - 100, "ts": T * 1000 - 100, "qui": "u", "texte": "Ma fille est là, dis bonjour"},
                                             {"id": T * 1000 + 200, "qui": "j", "texte": "Bonjour ma grande ! Je suis content de t'entendre."}]}))
    S.decider("contenir", "sa fille est là", 0, T + 30, _tour(tmp_path), j)
    vus = []

    def juge(prompt):
        vus.append(prompt)
        return '{"n": 1, "fait": "contenir", "juste": true, "pourquoi": "ton doux devant l\'enfant"}'
    b = S.juger_la_nuit(T + 3600, j, p, conv, juge)
    assert b == {"juges": 1, "lisibles": 1, "sagesse": round(S.DEPART + S.PAS, 3)}
    assert "contenir" not in vus[0].split("Réponse de Hakim")[0].split("### Cas 1")[1]   # à l'aveugle : pas sa décision
    assert S.juger_la_nuit(T + 7200, j, p, conv, juge)["juges"] == 0                      # déjà jugée
    assert "Ta sagesse : 0,23" in S.resume(T + 7200, j, p) and "1/1 décisions lisibles" in S.resume(T + 7200, j, p)
