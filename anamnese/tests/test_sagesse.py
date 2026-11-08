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
    assert b == {"juges": 1, "lisibles": 1, "sagesse": round(S.DEPART + S.PAS * 0.6 * (1 - S.DEPART), 3)}   # 0,205
    assert "contenir" not in vus[0].split("Réponse de Hakim")[0].split("### Cas 1")[1]   # à l'aveugle : pas sa décision
    assert S.juger_la_nuit(T + 7200, j, p, conv, juge)["juges"] == 0                      # déjà jugée
    assert "Ta sagesse : 0,20" in S.resume(T + 7200, j, p) and "1/1 décisions lisibles" in S.resume(T + 7200, j, p)


def _nuit(tmp_path, cas):
    """cas : [(décision, polarité, intensité, ce que le juge lit, juste)] → la sagesse après une nuit."""
    j, p, conv = tmp_path / "s.jsonl", tmp_path / "p.json", tmp_path / "c.json"
    msgs, lignes = [], []
    for k, (d, pol, i, lu, juste) in enumerate(cas):
        t = T + 100 * k
        msgs += [{"id": t * 1000 - 50, "ts": t * 1000 - 50, "qui": "u", "texte": f"message {k}"},
                 {"id": t * 1000 + 50, "qui": "j", "texte": f"réponse {k}"}]
        tour = _tour(tmp_path, ts=t * 1000, polarite=pol, intensite=i)
        S.decider(d, "", 0, t + 10, tour, j)
        lignes.append(json.dumps({"n": k + 1, "fait": lu, "juste": juste, "pourquoi": "x"}))
    conv.write_text(json.dumps({"messages": msgs}))
    return S.juger_la_nuit(T + 3600, j, p, conv, lambda prompt: "\n".join(lignes))["sagesse"]


def test_une_decision_que_le_juge_ne_lit_pas_ne_compte_pas(tmp_path):
    assert _nuit(tmp_path, [("atténuer", -1, 0.8, "garder", True)]) == S.DEPART


def test_tempérer_un_elan_apprend_moins_qu_un_moment_difficile(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    dur = _nuit(tmp_path / "a", [("atténuer", -1, 0.8, "atténuer", True)])
    doux = _nuit(tmp_path / "b", [("atténuer", 1, 0.8, "atténuer", True)])
    assert S.DEPART < doux < dur


def test_au_plus_deux_centiemes_par_nuit_et_on_peut_perdre(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    beaucoup = _nuit(tmp_path / "a", [("contenir", -1, 1.0, "contenir", True)] * 30)
    assert beaucoup == round(S.DEPART + S.PLAFOND_NUIT, 3)
    assert _nuit(tmp_path / "b", [("contenir", -1, 1.0, "contenir", False)]) < S.DEPART
