"""Le juge de nuit (27/10 ; idée d'Ahmed : « la nuit porte conseil, chez les IA encore plus » ; relayée par Hakim) : chaque
nuit, un juge indépendant (Opus, qui n'a rien fait de ce qu'il relit) reprend les résultats non jugés du fichier mère des
maths du réel et les résultats marqués importants sans verdict, refait les calculs dans un bac à sable qui LIT l'atelier
sans l'écrire, et AJOUTE ses verdicts (sauvegarde avant, jamais de réécriture du fond). Aucun appel réel ici."""
import json
import os

import pytest

import juge_nuit as J

MERE = """# Maths du réel

## Lien : compression et stockage
Voir COMPRESSION_MERE.md.

## 2026-10-25 21:45 — Anneaux de MÊME taille (CALCULÉ, NON JUGÉ)
Les anneaux s'assemblent. atelier/anneaux/a.py

## Vitesse limite (26/10) — calculé ET jugé (À CORRIGER puis corrigé)
R = 0,9885.

## 27/10/2026 (suite) — TOUT ce qui a été fait (ajout seul)
Rien n'est jugé : aucun juge n'est passé.

### D0. DÉCISION D'AHMED (27/10, 18:20) — le jet maison
Ahmed veut une formule maison. NON JUGÉ n'a pas de sens ici.

### D1. Tourbillon SEUL (13:27) — CALCULÉ, NON JUGÉ (atelier/tourbillon_seul_27oct/)
- chiffres : 0,42.

### D2. Patineur, compléments
- Quatre cases : cohérence oui. NON JUGÉ.

### D10. Récapitulatif honnête de l'après-midi
Tout est NON JUGÉ.

### 25/10 23h1x, VERDICT DU JUGE sur l'échelle : À CORRIGER
Rien.
"""


@pytest.fixture
def lieux(tmp_path, monkeypatch):
    atelier = tmp_path / "atelier"
    (atelier / "ancrage" / "sauvegardes").mkdir(parents=True)
    mere = atelier / "ancrage" / "MATHS_DU_REEL_MERE.md"
    mere.write_text(MERE, encoding="utf-8")
    monkeypatch.setattr(J, "ATELIER", atelier)
    monkeypatch.setattr(J, "MERE", mere)
    monkeypatch.setattr(J, "SAUVEGARDES", atelier / "ancrage" / "sauvegardes")
    monkeypatch.setattr(J, "IMPORTANTS", tmp_path / "importants.jsonl")
    monkeypatch.setattr(J, "ETAT", tmp_path / "juge-nuit-etat.json")
    monkeypatch.setattr(J, "RAPPORT", tmp_path / "juge-nuit.json")
    monkeypatch.setattr(J, "JOURNAL", tmp_path / "juge-nuit.jsonl")
    return {"atelier": atelier, "mere": mere, "tmp": tmp_path}


def test_les_resultats_a_juger_sont_les_blocs_non_juges_qui_sont_des_resultats(lieux):
    titres = [b["titre"] for b in J.candidats(J.etat_lu())]
    # les plus récents d'abord (la fin du fichier) ; ni décision, ni récapitulatif, ni verdict, ni lien, ni conteneur
    assert titres == ["D2. Patineur, compléments", "D1. Tourbillon SEUL (13:27) — CALCULÉ, NON JUGÉ (atelier/tourbillon_seul_27oct/)",
                      "2026-10-25 21:45 — Anneaux de MÊME taille (CALCULÉ, NON JUGÉ)"]
    d1 = [b for b in J.candidats(J.etat_lu()) if b["titre"].startswith("D1.")][0]
    assert d1["corps"] == "- chiffres : 0,42."


def test_les_importants_sans_verdict_passent_aussi_et_les_nouveaux_blocs_d_abord(lieux):
    lieux["tmp"].joinpath("importants.jsonl").write_text(
        json.dumps({"id": "I-aaaaaa", "ts": 1, "enonce": "Le patineur tourne plus vite.", "preuves": "atelier/p.py"}) + "\n"
        + json.dumps({"id": "I-236daf", "ts": 2, "enonce": "Isotropie.", "preuves": "x"}) + "\n", encoding="utf-8")
    lieux["mere"].write_text(MERE + "\n## 2026-10-27 09:50 — VERDICT DU JUGE sur l'isotropie (I-236daf) : À CORRIGER\n", encoding="utf-8")
    e = J.etat_lu()
    e["vus"] = [J.cle("2026-10-25 21:45 — Anneaux de MÊME taille (CALCULÉ, NON JUGÉ)")]
    c = J.candidats(e)
    assert [x.get("id") or x["titre"][:3] for x in c] == ["D2.", "D1.", "I-aaaaaa", "202"]
    # déjà jugé une nuit précédente : il ne revient pas
    e["juges"] = {J.cle("D2. Patineur, compléments"): {"verdict": "VALIDE"}}
    assert "D2." not in [x["titre"][:3] for x in J.candidats(e)]
    assert len(J.candidats(e, maximum=1)) == 1


def test_lire_le_verdict_du_juge():
    v = J.lire_verdict("J'ai refait.\nVERDICT : À CORRIGER\nRAISON : le bord fait tout.\nREFAIT : a.py sur 2 graines, 0,41 au lieu de 0,42.")
    assert v == {"verdict": "À CORRIGER", "raison": "le bord fait tout.", "refait": "a.py sur 2 graines, 0,41 au lieu de 0,42."}
    assert J.lire_verdict("VERDICT: non verifiable\nRAISON: script introuvable")["verdict"] == "NON VÉRIFIABLE"
    assert J.lire_verdict("blabla")["verdict"] is None


def test_les_verdicts_s_ajoutent_a_la_fin_le_statut_se_met_a_jour_et_la_sauvegarde_est_faite_avant(lieux):
    blocs = {b["titre"][:3]: b for b in J.candidats(J.etat_lu())}
    v = [{**blocs["D1."], "verdict": "VALIDE", "raison": "chiffres retrouvés", "refait": "seul.py : 0,42"},
         {**blocs["D2."], "verdict": "NON VÉRIFIABLE", "raison": "raisonnement", "refait": "rien"},
         {"source": "important", "id": "I-aaaaaa", "titre": "I-aaaaaa : Le patineur tourne plus vite.", "verdict": "À CORRIGER",
          "raison": "témoin absent", "refait": "p.py"}]
    J.ecrire_verdicts(v, "28/10")
    t = lieux["mere"].read_text(encoding="utf-8")
    assert t.startswith(MERE.rstrip("\n").split("### D1.")[0].rstrip("\n")[:40])
    assert "### D1. Tourbillon SEUL (13:27) — CALCULÉ, JUGÉ LA NUIT DU 28/10 : VALIDE (atelier/tourbillon_seul_27oct/)" in t
    assert "### D2. Patineur, compléments — JUGÉ LA NUIT DU 28/10 : NON VÉRIFIABLE (voir la fin)" in t
    fin = t.split("## Juge de nuit du 28/10")[1]
    assert "VALIDE" in fin and "chiffres retrouvés" in fin and "I-aaaaaa" in fin and "témoin absent" in fin
    # le reste du fichier n'a pas bougé
    assert "- chiffres : 0,42." in t and "Tout est NON JUGÉ." in t
    sauvegardes = list((lieux["atelier"] / "ancrage" / "sauvegardes").iterdir())
    assert len(sauvegardes) == 1 and sauvegardes[0].read_text(encoding="utf-8") == MERE


def test_jamais_un_lien_pour_le_fichier_mere(lieux, tmp_path):
    dehors = tmp_path / "dehors.md"
    dehors.write_text("à ne pas toucher", encoding="utf-8")
    lieux["mere"].unlink()
    os.symlink(dehors, lieux["mere"])
    with pytest.raises(J.Refus):
        J.ecrire_verdicts([{"source": "important", "id": "I-x", "titre": "x", "verdict": "VALIDE", "raison": "r", "refait": "r"}], "28/10")
    assert dehors.read_text(encoding="utf-8") == "à ne pas toucher"
    assert J.lire_mere() == ""


def test_le_juge_est_opus_isole_avec_un_seul_outil_le_terminal_qui_lit_sans_ecrire(lieux, monkeypatch):
    vu = {}

    class R:
        returncode = 0
        stdout = json.dumps({"result": "VERDICT : VALIDE\nRAISON : ok\nREFAIT : a.py", "is_error": False, "total_cost_usd": 0.3})
        stderr = ""

    def faux(c, **k):
        vu["c"], vu["k"] = c, k
        return R()

    monkeypatch.setattr(J.subprocess, "run", faux)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-pas-pour-lui")
    b = J.candidats(J.etat_lu())[0]
    v = J.juger(b, lieux["atelier"] / "juge-nuit" / "2026-10-28")
    assert v["verdict"] == "VALIDE"
    c = vu["c"]
    assert c[c.index("--model") + 1] == "opus" and c[c.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in c and "--restricted" in c and c[c.index("--allowedTools") + 1] == "mcp__juge__executer"
    mcp = json.loads(c[c.index("--mcp-config") + 1])
    assert list(mcp["mcpServers"]) == ["juge"] and mcp["mcpServers"]["juge"]["args"][0].endswith("mcp_juge.py")
    assert mcp["mcpServers"]["juge"]["env"]["JUGE_DOSSIER"].endswith("juge-nuit/2026-10-28")
    assert "ANTHROPIC_API_KEY" not in vu["k"]["env"]
    assert "Patineur" in vu["k"]["input"] and "données" in vu["k"]["input"]


def test_la_nuit_attend_le_calme_et_les_tests_et_s_arrete_a_l_heure(lieux, monkeypatch):
    monkeypatch.setattr(J, "_tests_en_cours", lambda: False)
    monkeypatch.setattr(J, "_dernier_echange", lambda: 0)
    assert J.pret(now=10_000) is True
    monkeypatch.setattr(J, "_dernier_echange", lambda: 10_000 - 1800)
    assert J.pret(now=10_000) is False                       # Ahmed et Hakim se sont parlé il y a 30 min
    monkeypatch.setattr(J, "_dernier_echange", lambda: 0)
    monkeypatch.setattr(J, "_tests_en_cours", lambda: True)
    assert J.pret(now=10_000) is False                       # un test de nuit tourne encore


def test_une_nuit_complete_avec_un_faux_juge(lieux, monkeypatch):
    monkeypatch.setattr(J, "pret", lambda now=None: True)
    monkeypatch.setattr(J, "juger", lambda b, d: {**b, "verdict": "VALIDE", "raison": "ok", "refait": "x", "brut": "VERDICT : VALIDE"})
    n = J.nuit(attendre=False)
    assert n == 3
    r = json.loads(lieux["tmp"].joinpath("juge-nuit.json").read_text(encoding="utf-8"))
    assert r["etat"] == "fini" and len(r["verdicts"]) == 3 and r["verdicts"][0]["verdict"] == "VALIDE"
    assert J.candidats(J.etat_lu()) == []                    # tout est jugé : la nuit suivante n'a rien à refaire
    assert lieux["mere"].read_text(encoding="utf-8").count("## Juge de nuit du") == 1


def test_le_demon_le_lance_une_fois_par_nuit_detache(tmp_path, monkeypatch):
    import time as _t
    import daemon
    import memory
    import migrations
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(daemon.config, "DATA_DIR", tmp_path)
    lances = []

    class P:
        def __init__(self, cmd, **k):
            lances.append((cmd, k))
    monkeypatch.setattr(daemon.subprocess, "Popen", P)
    lt = _t.localtime()
    a = lambda h: _t.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 30, 0, 0, 0, -1))   # noqa: E731
    daemon._juge_nuit_pass(m, now=a(14))                         # l'après-midi : rien
    assert lances == []
    daemon._juge_nuit_pass(m, now=a(1))
    daemon._juge_nuit_pass(m, now=a(2))                          # déjà lancé cette nuit
    assert len(lances) == 1
    cmd, k = lances[0]
    assert cmd[-2].endswith("juge_nuit.py") and cmd[-1] == "nuit" and k["start_new_session"] is True
    m.db.close()
