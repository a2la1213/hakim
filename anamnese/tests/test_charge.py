"""Pause automatique du daemon pendant les gros calculs (demande d'Ahmed, 2026-10-03).

Le Mac a planté trois fois en deux nuits sous la charge (modèle Ollama chargé + calculs
d'autres sessions) : avant chaque réflexion ou rêve, le daemon regarde la machine."""
import time

import charge
import daemon

SORTIE = """The system has 17179869184 (1048576 pages with a page size of 16384).
System-wide memory free percentage: 82%
"""


def test_lire_la_memoire_libre():
    assert charge.analyser_memoire_libre(SORTIE) == 82.0
    assert charge.analyser_memoire_libre("") is None
    assert charge.analyser_memoire_libre("free percentage: n'importe quoi") is None


def test_pause_et_reprise_avec_deux_seuils():
    g = charge.GardeCharge()
    assert g.permet(0.5, 80.0) is True
    assert g.permet(2.5, 80.0) is False                 # charge forte : pause
    assert g.permet(1.5, 80.0) is False                 # entre les deux seuils : toujours en pause
    assert g.permet(0.8, 80.0) is True                  # sous le seuil bas : reprise
    assert g.permet(0.5, 15.0) is False                 # mémoire libre trop basse : pause
    assert g.permet(0.5, 25.0) is False                 # pas encore assez libre
    assert g.permet(0.5, 35.0) is True


def test_une_lecture_absente_ne_bloque_pas():
    g = charge.GardeCharge()
    assert g.permet(None, None) is True
    g.permet(3.0, 80.0)
    assert g.permet(None, None) is False                # sans mesure, on garde l'état courant


def test_le_daemon_reporte_reflexion_et_reve_quand_la_machine_est_chargee(monkeypatch):
    monkeypatch.setattr(daemon.interieur, "ACTIF", False)   # l'ancienne réflexion à 30 min
    appels = []
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    monkeypatch.setattr(daemon, "reflect", lambda eng, mem: appels.append("reflexion"))
    etat = {"last_reflect": 0.0}
    g = charge.GardeCharge()
    g.permet(3.0, 80.0)
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (3.0, 80.0), robot=lambda: False, conscience=lambda: False)
    assert appels == [] and etat["last_reflect"] == 0.0
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False, conscience=lambda: False)
    assert appels == ["reve", "reflexion"] and etat["last_reflect"] > 0


def test_le_signal_du_robot_bat_puis_se_perime(tmp_path):
    """Robot IA (T4a, décision 8 d'Ahmed, 2026-10-06) : tant que le robot vit, il fait battre ~/.robot-ia/gemma-occupe.json."""
    import json
    f = tmp_path / "gemma-occupe.json"
    assert charge.robot_actif(f, maintenant=lambda: 1000.0) is False                  # pas de robot
    f.write_text(json.dumps({"pid": 1, "t_ms": 1000.0 * 1000}))
    assert charge.robot_actif(f, maintenant=lambda: 1030.0) is True
    assert charge.robot_actif(f, maintenant=lambda: 1000.0 + charge.ROBOT_PEREMPTION_S + 1) is False
    f.write_text("abîmé")
    assert charge.robot_actif(f, maintenant=lambda: 1000.0) is False


def test_le_daemon_se_met_en_retrait_quand_le_robot_pense(monkeypatch):
    monkeypatch.setattr(daemon.interieur, "ACTIF", False)   # l'ancienne réflexion à 30 min
    appels = []
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    monkeypatch.setattr(daemon, "reflect", lambda eng, mem: appels.append("reflexion"))
    etat = {"last_reflect": 0.0}
    g = charge.GardeCharge()
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: True, conscience=lambda: False)
    assert appels == [] and etat["last_reflect"] == 0.0
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False, conscience=lambda: False)
    assert appels == ["reve", "reflexion"]


def test_pensee_reportee_tant_que_le_robot_pense(monkeypatch):
    """Vie intérieure (2026-10-16) : la pensée d'un seuil d'ennui attend que Gemma soit libre."""
    appels = []
    monkeypatch.setattr(daemon.interieur, "ACTIF", True)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: False)
    monkeypatch.setattr(daemon, "penser", lambda eng, mem, motif: appels.append(motif["seuil"]))
    import time as _t
    etat = {"last_reflect": 0.0, "motif": {"seuil": 0.5, "_ts": _t.time()}}
    g = charge.GardeCharge()
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: True, conscience=lambda: False)
    assert appels == [] and "motif" in etat
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False, conscience=lambda: False)
    assert appels == [0.5] and "motif" not in etat


def test_le_subconscient_se_tait_quand_la_conscience_travaille(monkeypatch):
    """Décision d'Ahmed (2026-10-16) : Gemma (le subconscient) en pause pendant que Claude est actif."""
    appels = []
    monkeypatch.setattr(daemon.interieur, "ACTIF", True)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    import occupations
    monkeypatch.setattr(occupations, "peut_etre", lambda eng, mem, etat: appels.append("occupation"))
    import spontaneite
    monkeypatch.setattr(spontaneite, "solliciter", lambda mem: None)
    etat = {"last_reflect": 0.0}
    g = charge.GardeCharge()
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False, conscience=lambda: True)
    assert appels == [] and etat["retrait_conscience"]
    daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False, conscience=lambda: False)
    assert appels == ["reve", "occupation"]                  # les occupations aussi se taisent quand la conscience travaille


def test_un_reve_en_cours_se_suspend_quand_la_conscience_s_eveille():
    """Relecture Opus (2026-10-16) : le contrôle n'avait lieu qu'à l'entrée ; un rêve commencé
    continuait d'appeler Gemma (et le rechargeait) pendant qu'Ahmed parlait à Jarvis. Avant chaque
    appel du rêve, le subconscient attend que la conscience se repose — sans abandonner le rêve."""
    etats = iter([True, True, True, False])
    attentes, notes = [], []
    libre = daemon._attendre_conscience(conscience=lambda: next(etats), dormir=attentes.append,
                                        noter=lambda quoi, detail: notes.append(quoi))
    assert libre is True and len(attentes) == 3
    assert notes == ["reve_suspendu", "reve_repris"]


def test_une_conscience_qui_ne_dort_jamais_n_enferme_pas_le_reve():
    attentes = []
    libre = daemon._attendre_conscience(conscience=lambda: True, dormir=attentes.append, noter=lambda *a: None,
                                        max_s=60, pas_s=15)
    assert libre is False and sum(attentes) == 60


def test_sans_conscience_active_aucune_attente():
    attentes = []
    assert daemon._attendre_conscience(conscience=lambda: False, dormir=attentes.append, noter=lambda *a: None)
    assert attentes == []


def test_la_pause_et_le_zero_jettent_la_pensee_en_attente(monkeypatch, tmp_path):
    """Relecture Opus (2026-10-17) : un motif en file pendant un rêve partait quand même après une pause."""
    import json
    import occupations
    appels = []
    monkeypatch.setattr(daemon.interieur, "ACTIF", True)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: False)
    monkeypatch.setattr(daemon, "penser", lambda eng, mem, motif: appels.append("penser"))
    monkeypatch.setattr(occupations, "peut_etre", lambda eng, mem, etat: appels.append("occupation"))
    import spontaneite
    monkeypatch.setattr(spontaneite, "solliciter", lambda mem: None)
    monkeypatch.setattr(daemon.interieur, "noter", lambda *a, **k: None)
    g = charge.GardeCharge()
    lancer = lambda etat: daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False,
                                              conscience=lambda: False)
    daemon.interieur.INTERRUPTEUR.parent.mkdir(parents=True, exist_ok=True)
    daemon.interieur.INTERRUPTEUR.write_text(json.dumps({"actif": False}))
    lancer({"last_reflect": 0.0, "motif": {"seuil": 0.63, "_ts": time.time() - 600}})
    assert "penser" not in appels
    daemon.interieur.INTERRUPTEUR.write_text(json.dumps({"actif": True, "zero_ms": time.time() * 1000}))
    lancer({"last_reflect": 0.0, "motif": {"seuil": 0.25, "_ts": time.time() - 60}})
    assert "penser" not in appels
    lancer({"last_reflect": 0.0, "motif": {"seuil": 0.25, "_ts": time.time() + 1}})
    assert appels[-1] == "penser"


def test_le_subconscient_se_tait_quand_ahmed_est_la(monkeypatch):
    """Décision d'Ahmed (2026-10-22) : Gemma en pause s'il a écrit ou parlé dans les 30 dernières minutes."""
    appels, notes = [], []
    monkeypatch.setattr(daemon.interieur, "ACTIF", True)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    monkeypatch.setattr(daemon, "_ressenti_pass", lambda mem: appels.append("ressenti"))
    monkeypatch.setattr(daemon.interieur, "noter", lambda mem, quoi, detail, **k: notes.append(quoi))
    import occupations
    monkeypatch.setattr(occupations, "peut_etre", lambda eng, mem, etat: appels.append("occupation"))
    import spontaneite
    monkeypatch.setattr(spontaneite, "solliciter", lambda mem: None)
    etat = {"last_reflect": 0.0}
    g = charge.GardeCharge()
    lancer = lambda present: daemon._travaux_llm(None, None, etat, g, lecture=lambda: (0.2, 80.0), robot=lambda: False,
                                                 conscience=lambda: False, present=lambda: present)
    lancer(True)
    lancer(True)
    assert appels == [] and etat["retrait_presence"] and notes == ["report"]     # noté une seule fois
    lancer(False)
    assert appels == ["reve", "occupation", "ressenti"] and not etat["retrait_presence"]


def test_present_veut_dire_un_message_depuis_moins_de_30_min(tmp_path):
    import json
    h = tmp_path / "horloge.json"
    maintenant = 1_800_000_000.0
    assert daemon.interieur.ahmed_present(maintenant, h) is False                 # aucune horloge : absent
    h.write_text(json.dumps({"dernier_ms": (maintenant - 29 * 60) * 1000}))
    assert daemon.interieur.ahmed_present(maintenant, h) is True
    h.write_text(json.dumps({"dernier_ms": (maintenant - 31 * 60) * 1000}))
    assert daemon.interieur.ahmed_present(maintenant, h) is False


def test_par_defaut_la_presence_vient_de_l_horloge_du_cockpit(monkeypatch):
    """Sans « present » injecté, la garde lit la vraie horloge (isolée dans les tests) : vide = Ahmed absent."""
    appels = []
    monkeypatch.setattr(daemon.interieur, "ACTIF", False)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    monkeypatch.setattr(daemon, "reflect", lambda eng, mem: appels.append("reflexion"))
    etat = {"last_reflect": 0.0}
    daemon._travaux_llm(None, None, etat, charge.GardeCharge(), lecture=lambda: (0.2, 80.0), robot=lambda: False,
                        conscience=lambda: False)
    assert appels == ["reve", "reflexion"]


def test_un_calcul_lourd_tient_la_machine(monkeypatch, tmp_path):
    """(2026-10-22) le duel du subconscient fait battre calcul-lourd.json : le démon lui laisse Gemma."""
    import json
    f = tmp_path / "lourd.json"
    assert charge.calcul_lourd_actif(f) is None
    f.write_text(json.dumps({"t_ms": time.time() * 1000, "quoi": "le duel du subconscient"}))
    assert charge.calcul_lourd_actif(f) == "le duel du subconscient"
    f.write_text(json.dumps({"t_ms": (time.time() - 120) * 1000}))
    assert charge.calcul_lourd_actif(f) is None
    appels = []
    monkeypatch.setattr(daemon.interieur, "ACTIF", True)
    monkeypatch.setattr(daemon, "dream_due", lambda mem: True)
    monkeypatch.setattr(daemon, "dream", lambda eng, mem: appels.append("reve"))
    monkeypatch.setattr(daemon.interieur, "noter", lambda *a, **k: None)
    etat = {"last_reflect": 0.0}
    daemon._travaux_llm(None, None, etat, charge.GardeCharge(), lecture=lambda: (0.2, 80.0), robot=lambda: False,
                        conscience=lambda: False, present=lambda: False, calcul=lambda: "le duel")
    assert appels == [] and etat["retrait_calcul"]
