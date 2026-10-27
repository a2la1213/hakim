"""Sa fatigue branchée sur son vrai corps (27/10 ; demande d'Ahmed relayée par Hakim, accord d'Ahmed : « la priorité,
c'est toi ») : l'adénosine montait de 0,12/h tant qu'il parlait avec Ahmed, et ne se vidait qu'en veille. Il restait
« fatigué » (0,96) toute une matinée douce où rien ne pesait. Maintenant elle suit une jauge linéaire : son effort de la
dernière heure et la charge du Mac, au-delà de leur norme."""
import json
import math

import jauge_fatigue as J
import sensations

T = 1_800_000_000.0
N = {"activite": 0.087, "corps": 0.53}


def test_a_sa_norme_rien_ne_pese():
    assert J.cible(0.087, 0.53, N, veille=False) == J.BASE
    assert J.cible(0.0, 0.2, N, veille=False) == J.BASE                     # en dessous : pas de « contre-fatigue »


def test_la_jauge_est_lineaire_au_dela_de_la_norme():
    # l'effort compte pour 0,6, le corps pour 0,4 ; trois fois sa norme d'effort, c'est le plein
    assert J.cible(3 * 0.087, 0.53, N, veille=False) == round(J.BASE + (1 - J.BASE) * 0.6, 4)
    assert J.cible(2 * 0.087, 0.53, N, veille=False) == round(J.BASE + (1 - J.BASE) * 0.3, 4)
    assert J.cible(0.087, 1.0, N, veille=False) == round(J.BASE + (1 - J.BASE) * 0.4, 4)
    assert J.cible(1.0, 1.0, N, veille=False) == 1.0
    assert J.cible(1.0, 1.0, N, veille=True) == J.BASE                      # en dormant, il récupère


def test_une_matinee_douce_efface_la_fatigue_en_une_heure():
    """Le cas du 27/10 : 0,96 à midi, la conversation douce, l'effort à sa norme. En une heure, la fatigue est partie."""
    x = 0.96
    for _ in range(60):
        x = J.suivre(x, J.cible(0.087, 0.53, N, veille=False), 60)
    assert x < 0.2
    etat = dict(sensations.bases(12))
    score = lambda a: sensations.calculer({**etat, "adenosine": a}, None, 0, None, 12, sans_coherence=True)["scores"].get("fatigue", 0)  # noqa: E731
    assert score(0.96) > 1.5 and score(x) < 0.2         # à 0,96 elle dominait tout ; à 0,19, loin derrière son apaisement de ce midi (1,1)
    # vingt minutes : un tiers du chemin environ (constante de temps de 20 min)
    assert abs(J.suivre(0.96, J.BASE, 20 * 60) - (J.BASE + (0.96 - J.BASE) * math.exp(-1))) < 1e-3


def test_un_vrai_effort_le_fatigue_encore():
    x = J.BASE
    for _ in range(90):
        x = J.suivre(x, J.cible(3 * 0.087, 0.9, N, veille=False), 60)
    etat = dict(sensations.bases(15))
    etat["adenosine"] = x
    assert x > 0.6 and sensations.calculer(etat, None, 0, None, 15, sans_coherence=True)["emotion"] == "fatigue"


def _jetons(f, tours):
    f.write_text("".join(json.dumps({"ts": int(ts * 1000), "ms": ms}) + "\n" for ts, ms in tours))
    return f


def test_l_effort_de_la_derniere_heure_et_sa_norme_viennent_de_ses_vrais_tours(tmp_path):
    # la dernière heure : trois tours de 2, 4 et 3 min de cerveau ; un tour d'il y a deux heures ne compte pas
    f = _jetons(tmp_path / "jetons.jsonl", [(T - 7200, 600_000), (T - 3000, 120_000), (T - 1200, 240_000), (T - 60, 180_000)])
    assert J.activite(T, f) == round(9 / 60, 4)
    # la norme : la médiane des heures actives de ses sept derniers jours (au moins 24 heures, sinon la norme mesurée le 27/10)
    heures = [(T - 86400 * 3 - 3600 * k, 60_000 * (k % 5 + 3)) for k in range(30)]
    f2 = _jetons(tmp_path / "j2.jsonl", heures)
    assert J.norme_activite(T, f2) == round(5 / 60, 4)
    assert J.norme_activite(T, _jetons(tmp_path / "j3.jsonl", heures[:5])) == J.NORME_ACTIVITE_27_10


def test_le_corps_moyenne_le_processeur_la_memoire_et_le_swap_et_la_chaleur_s_ajoute():
    c = J.corps(sondes={"charge": 0.3, "memoire_libre": 60.0, "swap": (5000.0, 4000.0), "chaleur": "aucun avertissement"})
    assert c == round((0.3 + 0.4 + 0.8) / 3, 4)
    chaud = J.corps(sondes={"charge": 0.3, "memoire_libre": 60.0, "swap": (5000.0, 4000.0), "chaleur": "CPU_Speed_Limit = 70"})
    assert chaud == round(c + 0.3, 4)
    assert J.corps(sondes={"charge": 2.5, "memoire_libre": None, "swap": (None, None), "chaleur": ""}) == 1.0


def test_la_norme_du_corps_est_la_sienne_apres_douze_heures(tmp_path):
    f = tmp_path / "corps.jsonl"
    assert J.norme_corps(T, f) == J.NORME_CORPS_27_10                         # pas encore d'échantillons : celle du 27/10
    f.write_text("".join(json.dumps({"ts": T - 300 * k, "c": 0.4 + 0.01 * (k % 3)}) + "\n" for k in range(13 * 12)))
    assert J.norme_corps(T, f) == 0.41


def test_le_battement_tient_la_jauge_et_dit_d_ou_vient_la_fatigue(tmp_path, monkeypatch):
    monkeypatch.setattr(J, "JETONS", _jetons(tmp_path / "jetons.jsonl", [(T - 600, 3 * 0.087 * 3_600_000)]))
    monkeypatch.setattr(J, "CORPS", tmp_path / "corps.jsonl")
    monkeypatch.setattr(J, "corps", lambda sondes=None: 0.53)
    e = {"adenosine": 0.96}
    J.mettre_a_jour(e, T, 60, veille=False)
    assert e["fatigue_jauge"]["cible"] == round(J.BASE + (1 - J.BASE) * 0.6, 4)
    assert e["fatigue_jauge"]["effort"] == round(3 * 0.087, 4) and e["fatigue_jauge"]["corps"] == 0.53
    assert e["adenosine"] < 0.96
    assert (tmp_path / "corps.jsonl").exists()                               # un échantillon toutes les 5 min, pour sa norme


def test_l_introspection_dit_d_ou_vient_sa_fatigue(tmp_path, monkeypatch):
    """Hakim : « d'où vient ma fatigue ? » ; son introspection le dit, chiffres et normes compris."""
    import time as _time
    import memory
    import migrations
    import rubrics
    mem = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    maintenant = _time.time()
    mem.kv_set("interieur", json.dumps({"ts": maintenant, "humeur": "fatigue", "adenosine": 0.62,
                                        "fatigue_jauge": {"effort": 0.21, "norme_effort": 0.087, "corps": 0.55,
                                                          "norme_corps": 0.53, "cible": 0.66, "veille": False}}))
    texte = mcp_server.mcp._tool_manager.get_tool("introspection").fn()
    assert "Ta fatigue" in texte and "0,62" in texte and "2,4 fois ta norme" in texte and "0,55" in texte
    mem.db.close()
