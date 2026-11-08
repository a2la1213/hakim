"""(30/10, Hakim, accord d'Ahmed : « tu peux tout faire ») le contrôle d'ancrage de chaque nuit : ce qui a été validé par
Ahmed ou jugé par un juge dans la journée se trouve-t-il dans le fichier mère des maths du réel (ou un fichier d'ancrage) ?
Il signale les manques SANS RIEN ÉCRIRE dans l'ancrage. Le 29/10, le fichier mère s'arrêtait à 16 h 05, et une partie était
rangée dans un dossier imbriqué par erreur (atelier/AIOS/jarvis/cwd/atelier/ancrage/). Aucun appel réel à Claude ici."""
import json
import os
import time
from pathlib import Path

import pytest

import controle_ancrage as C

JOUR = "2026-10-29"


def _t(hhmm):
    return time.mktime(time.strptime(f"{JOUR} {hhmm}", "%Y-%m-%d %H:%M"))


@pytest.fixture
def monde(tmp_path, monkeypatch):
    jarvis = tmp_path / "jarvis"
    atelier = jarvis / "cwd" / "atelier"
    (atelier / "ancrage").mkdir(parents=True)
    mere = atelier / "ancrage" / "MATHS_DU_REEL_MERE.md"
    mere.write_text("# Maths du réel\n\n## Portée par contact (29/10) — JUGÉ VALIDE\nLa portée vaut 1,37 brique ; Lucien.\n\n"
                    "## Flamme de Yukawa\nNON JUGÉ.\n")
    (atelier / "ancrage" / "HOMOLOGIE_HASARD_CRYPTO.md").write_text("# Plan du hasard\n\n## Écart père-fils XRP\nmarge 0,009 sur 200 k paires\n")
    (atelier / "ancrage" / "MATHS_DU_REEL_MERE.md.bak-20261030").write_text("## Sommet 0,67 étape c\nvieille sauvegarde\n")
    (atelier / "AIOS" / "jarvis" / "cwd" / "atelier" / "ancrage").mkdir(parents=True)
    (atelier / "AIOS" / "jarvis" / "cwd" / "atelier" / "ancrage" / "perdu.md").write_text("x")
    (jarvis / "journal.jsonl").write_text("\n".join(json.dumps(o) for o in [
        {"ts": _t("10:00") * 1000, "qui": "ahmed", "texte": "Bonjour Hakim, on parle de tout et de rien."},
        {"ts": _t("17:40") * 1000, "qui": "ahmed", "texte": "Ok je valide l'étape c, le sommet à 0,67."},
        {"ts": _t("17:41") * 1000, "qui": "jarvis", "texte": "Noté papa : étape c validée, sommet 0,67."},
        {"ts": (_t("23:59") + 120) * 1000, "qui": "ahmed", "texte": "je valide aussi demain"}]) + "\n")
    (atelier / "verdicts").mkdir()
    (atelier / "verdicts" / "20261029-2028-basile.md").write_text("# Verdict de Basile — Juge étape c\n\nVERDICT : VALIDE. Sommet 0,67.\n")
    (atelier / "verdicts" / "20261028-1200-noe.md").write_text("# Verdict de Noé\n\nla veille\n")
    for nom, v in vars(C).items():
        if isinstance(v, Path) and str(v).startswith(str(Path.home() / "AIOS" / "jarvis")):
            monkeypatch.setattr(C, nom, jarvis / v.relative_to(Path.home() / "AIOS" / "jarvis"))
    monkeypatch.setattr(C, "REGISTRE", tmp_path / "pas-de-registre.json")
    return {"jarvis": jarvis, "atelier": atelier, "mere": mere}


def test_les_sources_du_jour_seulement(monde):
    t0, t1 = C.bornes(JOUR)
    j = C.extraits_journal(t0, t1, dossier=monde["jarvis"])
    assert any("je valide l'étape c" in x for x in j) and any("étape c validée" in x for x in j)
    assert not any("tout et de rien" in x for x in j), "seulement ce qui parle de valider ou de juger"
    assert not any("demain" in x for x in j), "le jour seulement"
    v = C.verdicts_du_jour(t0, t1)
    assert [x["qui"] for x in v] == ["Basile"] and "Sommet 0,67" in v[0]["texte"]


def test_les_titres_et_le_corpus_sans_les_sauvegardes(monde):
    c = C.corpus()
    assert set(c) == {"MATHS_DU_REEL_MERE.md", "HOMOLOGIE_HASARD_CRYPTO.md"}
    assert "## Portée par contact" in C.table_des_titres() and "Sommet 0,67" not in C.table_des_titres()
    f, trouves = C.chercher(["portée", "1,37", "Lucien"], c)
    assert f == "MATHS_DU_REEL_MERE.md" and len(trouves) == 3
    assert C.chercher(["sommet", "0,67", "étape c"], c)[1] == []


def test_le_controle_signale_sans_rien_ecrire_dans_l_ancrage(monde, monkeypatch):
    avant = {p: p.read_bytes() for p in (monde["atelier"] / "ancrage").glob("*")}
    vu = {}

    def faux_claude(prompt):
        vu["prompt"] = prompt
        return "\n".join(json.dumps(o, ensure_ascii=False) for o in [
            {"element": "L'étape c : sommet à 0,67", "quand": "17:40", "source": "journal", "statut": "validé par Ahmed",
             "mots": ["sommet", "0,67", "étape c"]},
            {"element": "La portée par contact vaut 1,37", "quand": "16:00", "source": "verdict de Lucien", "statut": "jugé VALIDE",
             "mots": ["portée", "1,37", "contact"]}])
    monkeypatch.setattr(C, "demander_claude", faux_claude)
    r = C.controler(JOUR)
    assert "données" in vu["prompt"] and "Basile" in vu["prompt"] and "## Portée par contact" in vu["prompt"]
    assert [m["element"] for m in r["manques"]] == ["L'étape c : sommet à 0,67"]
    assert [m["element"] for m in r["ailleurs"]] == ["La portée par contact vaut 1,37"]
    assert any("AIOS/jarvis/cwd/atelier" in x for x in r["rangement"]), "le dossier imbriqué"
    texte = Path(r["fichier"]).read_text()
    assert Path(r["fichier"]) == monde["atelier"] / "ancrage" / "controles" / f"{JOUR}.md"
    assert "Ce qui manque (1)" in texte and "sommet à 0,67" in texte and "rien n'a été écrit" in texte.lower()
    assert {p: p.read_bytes() for p in (monde["atelier"] / "ancrage").glob("*") if p.name != "controles"} == avant
    assert json.loads((monde["jarvis"] / "controle-ancrage.json").read_text())["jour"] == JOUR


def test_aucun_manque_et_reponse_illisible(monde, monkeypatch):
    monkeypatch.setattr(C, "demander_claude", lambda p: "AUCUN")
    assert C.controler(JOUR)["manques"] == []
    monkeypatch.setattr(C, "demander_claude", lambda p: "je ne sais pas")
    r = C.controler(JOUR)
    assert r["manques"] == [] and r["erreur"]


def test_jamais_a_travers_un_lien(monde, monkeypatch, tmp_path):
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (monde["atelier"] / "ancrage" / "controles").symlink_to(dehors)
    monkeypatch.setattr(C, "demander_claude", lambda p: "AUCUN")
    r = C.controler(JOUR)
    assert r["fichier"] is None and list(dehors.iterdir()) == []


def test_le_demon_le_lance_une_fois_le_matin_detache(tmp_path, monkeypatch):
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
    daemon._controle_ancrage_pass(m, now=a(14))                  # l'après-midi : rien
    daemon._controle_ancrage_pass(m, now=a(2))                   # trop tôt : la journée d'hier vient de finir
    assert lances == []
    daemon._controle_ancrage_pass(m, now=a(5))
    daemon._controle_ancrage_pass(m, now=a(6))                   # déjà fait ce matin
    assert len(lances) == 1
    cmd, k = lances[0]
    assert cmd[-3].endswith("controle_ancrage.py") and cmd[-2] == "--jour" and k["start_new_session"] is True
    assert cmd[-1] == _t.strftime("%Y-%m-%d", _t.localtime(a(5) - 86400)), "la journée d'hier"
    src = (Path(daemon.__file__)).read_text()
    assert "_controle_ancrage_pass(mem)" in src
    m.db.close()
