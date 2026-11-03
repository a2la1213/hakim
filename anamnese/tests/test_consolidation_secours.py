"""Consolidation de nuit (2026-10-15) : verdict honnête, secours API, porte d'entrée.

- La CLI sort du JSON (--output-format json) : on lit subtype / is_error / api_error_status.
  Seul subtype == "success" marque la nuit ; max-turns atteint = INCOMPLÈTE, non marquée.
- Abonnement indisponible (limite, auth, CLI absente) → relance par Claude Code avec
  --settings apiKeyHelper (la CLI lit elle-même la clé dans le trousseau ; la clé n'entre jamais
  dans ce processus) et le modèle de secours (Opus 5.5). Sans clé : on le dit, rien n'est marqué.
  Vérifié en réel le 2026-10-15 : ANTHROPIC_API_KEY dans l'environnement est IGNORÉ par
  `claude -p` (apiKeySource=none) ; apiKeyHelper est utilisé (apiKeySource=apiKeyHelper).
- Les rêves ne sont instrumentés dreamer='sonnet' que si Sonnet a vraiment fait le run.
- Porte : moins de MIN_NOUVEAUX vrais souvenirs depuis la dernière nuit → nuit sautée.
- La clé n'apparaît jamais dans le journal.

Prédiction écrite avant le code : tout échoue (verdict, cle_api, nouveaux_souvenirs absents).
Prédiction pour la bascule apiKeyHelper : les tests de commande et de secours échouent sur la
version qui passait la clé par l'environnement.
"""

import pytest

import consolidate



def _res(subtype="success", is_error=False, status=None, result="Consolidé.", turns=8):
    return {"type": "result", "subtype": subtype, "is_error": is_error,
            "api_error_status": status, "result": result, "num_turns": turns,
            "total_cost_usd": 0.42}


@pytest.mark.parametrize("res, attendu", [
    (_res(), "ok"),
    (_res("error_max_turns", True, turns=40), "incomplete"),
    (_res("error_during_execution", True, 429, "rate limited", 1), "limite"),
    (_res("success", True, None, "Claude AI usage limit reached|1760000000", 1), "limite"),
    (_res("success", True, None, "5-hour limit reached ∙ resets 3am", 1), "limite"),
    (_res("error_during_execution", True, 401, "Invalid API key · Please run /login", 0), "limite"),
    ({"is_error": True, "subtype": "cli_absente", "num_turns": 0, "result": ""}, "limite"),
    ({"is_error": True, "subtype": "timeout", "num_turns": None, "result": ""}, "echec"),
    (_res("error_during_execution", True, 500, "boom", 3), "echec"),
])
def test_verdict(res, attendu):
    assert consolidate.verdict(res) == attendu


def _lot(n):
    return [{"id": i, "ts": float(i), "role": "semantic", "rubrique": None, "content": f"s{i}"} for i in range(n)]


@pytest.fixture
def nuit(monkeypatch):
    """main() isolé : aucun subprocess, aucune DB, journal en mémoire."""
    journal, appels, marques, reves = [], [], [], []
    monkeypatch.setattr(consolidate, "log", lambda m: journal.append(str(m)))
    monkeypatch.setattr(consolidate, "curseur", lambda *a, **k: 0.0)
    monkeypatch.setattr(consolidate, "avancer_curseur", lambda *a, **k: True)
    fermes = []
    monkeypatch.setattr(consolidate, "_ouvrir_registre", lambda lot: "reg_test")
    monkeypatch.setattr(consolidate, "_fermer_registre", lambda rid, resume: fermes.append(rid))
    monkeypatch.setattr(consolidate, "lot_a_consolider", lambda *a, **k: _lot(10))
    monkeypatch.setattr(consolidate, "mark_consolidated", lambda *a, **k: marques.append(1) or True)
    monkeypatch.setattr(consolidate, "log_sonnet_dreams", lambda *a, **k: reves.append(1) or 0)
    monkeypatch.setattr(consolidate, "_refresh_dataset", lambda: None)
    monkeypatch.setattr(consolidate, "secours_disponible", lambda: True)
    monkeypatch.setattr(consolidate, "version_cli", lambda: "2.1.300")
    monkeypatch.setattr(consolidate, "trace_depuis", lambda *a, **k: True)
    sauts = []
    monkeypatch.setattr(consolidate, "marquer_saut", lambda *a, **k: sauts.append(1))
    reponses, prompts, registres = [], [], []

    def faux_run(prompt, modele, secours=False, registre_id=None):
        appels.append((modele, secours))
        registres.append(registre_id)
        prompts.append(prompt)
        return reponses.pop(0)

    monkeypatch.setattr(consolidate, "_run", faux_run)
    return {"journal": journal, "appels": appels, "marques": marques, "reves": reves,
            "reponses": reponses, "mp": monkeypatch, "sauts": sauts, "registres": registres, "fermes": fermes,
            "prompts": prompts}


def _sequence_trace(nuit, *valeurs):
    """trace_depuis renvoie ces valeurs dans l'ordre (avant le secours, puis preuve finale)."""
    it = iter(valeurs)
    nuit["mp"].setattr(consolidate, "trace_depuis", lambda *a, **k: next(it))


def test_abonnement_ok(nuit):
    nuit["reponses"].append(_res())
    consolidate.main()
    assert nuit["appels"] == [(consolidate.MODELE, False)]
    assert nuit["marques"] == [1] and nuit["reves"] == [1]


def test_limite_bascule_sur_api_opus(nuit):
    _sequence_trace(nuit, False, True)
    nuit["reponses"] += [_res("success", True, 429, "usage limit reached", 1), _res()]
    consolidate.main()
    assert nuit["appels"] == [(consolidate.MODELE, False), ("claude-opus-5-5", True)]
    assert nuit["marques"] == [1]
    assert nuit["reves"] == []                       # pas un run Sonnet : pas d'instrumentation


def test_limite_sans_cle_rien_n_est_marque(nuit):
    nuit["mp"].setattr(consolidate, "secours_disponible", lambda: False)
    _sequence_trace(nuit, False)
    nuit["reponses"].append(_res("success", True, 429, "usage limit reached", 1))
    consolidate.main()
    assert len(nuit["appels"]) == 1 and nuit["marques"] == []
    assert any("trousseau" in ligne for ligne in nuit["journal"])


def test_max_turns_incomplete_non_marquee(nuit):
    nuit["reponses"].append(_res("error_max_turns", True, turns=40))
    consolidate.main()
    assert len(nuit["appels"]) == 1 and nuit["marques"] == []
    assert any("INCOMPLÈTE" in ligne for ligne in nuit["journal"])


def test_porte_nuit_sautee(nuit):
    nuit["mp"].setattr(consolidate, "lot_a_consolider", lambda *a, **k: _lot(1))
    consolidate.main()
    assert nuit["appels"] == [] and nuit["marques"] == []
    assert any("sautée" in ligne for ligne in nuit["journal"])


def test_nouveaux_souvenirs_compte_la_vraie_matiere(tmp_path):
    import sqlite3
    db = tmp_path / "m.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT)")
    con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
    con.execute("INSERT INTO kv VALUES ('last_consolidation', '100', 100)")
    lignes = [(50, "semantic"), (150, "semantic"), (160, "episodic"), (170, "reflection"),
              (180, "insight"), (190, "dream"), (200, "outreach"), (210, "reasoning")]
    con.executemany("INSERT INTO episodes (ts, role, content) VALUES (?, ?, 'x')", lignes)
    con.commit()
    con.close()
    assert consolidate.nouveaux_souvenirs(db) == 3       # semantic 150, episodic 160, reasoning 210


def test_allowlist_de_nuit_sans_self_update():
    outils = consolidate.TOOLS.split(",")
    assert "mcp__anamnese__self_append" in outils
    assert "mcp__anamnese__self_update" not in outils


def _commande(monkeypatch, **kw):
    vu = {}

    class _R:
        stdout = '{"type": "result", "subtype": "success", "is_error": false}'
        stderr = ""

    def faux(cmd, **opts):
        vu["cmd"], vu["env"] = cmd, opts.get("env", {})
        return _R()

    monkeypatch.setattr(consolidate.subprocess, "run", faux)
    consolidate._run("prompt", **kw)
    return vu


def test_commande_secours_par_apikeyhelper(monkeypatch):
    import json
    vu = _commande(monkeypatch, modele="claude-opus-5-5", secours=True)
    cmd = vu["cmd"]
    assert cmd[0] == consolidate.CLAUDE_BIN
    reglages = json.loads(cmd[cmd.index("--settings") + 1])
    assert consolidate.SERVICE_CLE in reglages["apiKeyHelper"]
    assert "ANTHROPIC_API_KEY" not in vu["env"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"


def test_commande_abonnement_sans_settings(monkeypatch):
    vu = _commande(monkeypatch, modele="sonnet")
    assert "--settings" not in vu["cmd"] and "ANTHROPIC_API_KEY" not in vu["env"]


# --- relecture indépendante du 2026-10-15 (constats 3, 4, 7, 10, 11, 12) ---

def _trace(nuit, valeur):
    nuit["mp"].setattr(consolidate, "trace_depuis", lambda *a, **k: valeur)


def test_succes_sans_trace_est_suspect(nuit):
    _trace(nuit, False)
    nuit["reponses"].append(_res())
    consolidate.main()
    assert nuit["marques"] == []
    assert any("SUSPECT" in ligne for ligne in nuit["journal"])


def test_succes_en_un_tour_est_suspect(nuit):
    nuit["reponses"].append(_res(turns=1))
    consolidate.main()
    assert nuit["marques"] == []


def test_limite_apres_la_trace_pas_de_secours(nuit):
    _trace(nuit, True)
    nuit["reponses"].append(_res("success", True, None, "usage limit reached", 30))
    consolidate.main()
    assert len(nuit["appels"]) == 1 and nuit["marques"] == [1]


def test_secours_apres_passage_interrompu_reprend(nuit):
    _sequence_trace(nuit, False, True)
    nuit["reponses"] += [_res("success", True, None, "usage limit reached", 20), _res()]
    consolidate.main()
    assert nuit["appels"][1] == ("claude-opus-5-5", True)
    assert nuit["prompts"][1].startswith(consolidate.NOTE_REPRISE.split("{")[0])
    assert nuit["prompts"][0] == nuit["prompts"][1].split("\n\n", 1)[1]


def test_route_login_d_un_projet_n_est_pas_une_limite():
    res = _res("error_during_execution", True, None,
               "Échec : la route /login de botgarage renvoie 500 (authentication middleware)", 12)
    assert consolidate.verdict(res) == "echec"


def test_json_indente_est_lu(monkeypatch):
    class _R:
        stdout = '{\n  "type": "result",\n  "subtype": "success",\n  "is_error": false\n}'
        stderr = ""
    monkeypatch.setattr(consolidate.subprocess, "run", lambda *a, **k: _R())
    assert consolidate._run("p", "sonnet")["subtype"] == "success"


def test_nuit_sautee_laisse_un_signe_de_vie(nuit):
    nuit["mp"].setattr(consolidate, "lot_a_consolider", lambda *a, **k: [])
    consolidate.main()
    assert nuit["sauts"] == [1]


def test_reves_instrumentes_pour_un_id_sonnet_complet(nuit):
    nuit["mp"].setattr(consolidate, "MODELE", "claude-sonnet-5-5")
    nuit["reponses"].append(_res())
    consolidate.main()
    assert nuit["reves"] == [1]



def test_secours_payant_desactive_par_defaut(monkeypatch):
    """Décision d'Ahmed (2026-10-16) : tout gratuit. Le secours par clé API ne s'active
    qu'avec ANAMNESE_SECOURS_API=1, même si une clé est rangée dans le trousseau."""
    monkeypatch.delenv("ANAMNESE_SECOURS_API", raising=False)
    assert consolidate.secours_disponible() is False



def test_chaque_passe_a_son_entree_de_registre(nuit):
    """Phase A : l'identifiant d'entrée est transmis au run (puis au serveur MCP) et l'entrée est
    fermée après la passe, même en cas de secours."""
    _sequence_trace(nuit, False, True)
    nuit["reponses"] += [_res("success", True, 429, "usage limit reached", 1), _res()]
    nuit["mp"].setattr(consolidate, "secours_disponible", lambda: True)
    consolidate.main()
    assert nuit["registres"] == ["reg_test", "reg_test"] and nuit["fermes"] == ["reg_test"]


def test_run_transmet_l_entree_de_registre(monkeypatch):
    vu = {}

    class _R:
        stdout = '{"type": "result", "subtype": "success", "is_error": false}'
        stderr = ""

    monkeypatch.setattr(consolidate.subprocess, "run", lambda cmd, **kw: vu.update(kw) or _R())
    consolidate._run("prompt", "sonnet", registre_id="reg_x")
    assert vu["env"]["ANAMNESE_REGISTRE"] == "reg_x"
    consolidate._run("prompt", "sonnet")
    assert "ANAMNESE_REGISTRE" not in vu["env"]


def test_entree_fermee_meme_si_la_passe_plante(nuit):
    def plante(*a, **k):
        raise RuntimeError("panne au milieu de la passe")

    nuit["mp"].setattr(consolidate, "_une_passe", plante)
    with pytest.raises(RuntimeError):
        consolidate.main()
    assert nuit["fermes"] == ["reg_test"]
