"""(04/11, Ahmed : « évalue le flux de chaque réponse et son parcours préférentiel, et analyse-le pour chacune de ses réponses »)
synapses_voir : ses chemins forts et élagués, et le parcours de ses dernières pensées jugées."""
import json
from pathlib import Path


def test_il_voit_ses_synapses_et_ses_parcours(tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    j = tmp_path / "AIOS" / "jarvis"
    j.mkdir(parents=True)
    assert mcp_server.synapses_voir().startswith("Pas encore de mesure")
    (j / "synapses.json").write_text(json.dumps({"familles": {
        "meuble": {"hum": {"poids": 0.12, "n": 22, "elaguee": True}, "voyons_voir": {"poids": 0.8, "n": 25}},
        "voie": {"non|suite": {"poids": 0.6, "n": 30}}},
        "historique": [{"t": 1_800_000_000_000, "famille": "meuble", "id": "hum", "evenement": "elaguee", "poids": 0.18}]}))
    (j / "parcours.jsonl").write_text(json.dumps({"extrait": "Ta mère va bien ?", "voix": "dite", "chemins": {"piste": "sonnet|courte", "meuble": "hum"},
                                                   "reaction": {"coupee": True}, "score": 0.1}) + "\n")
    r = mcp_server.synapses_voir()
    assert "tes meubles : forts « voyons_voir » 0,80 ; élagués « hum » (22 mesures, élaguée le " in r
    assert ": trop de coupures, de « non » ou de parasites)" in r
    assert "tes façons de parler : forts « non|suite » 0,60" in r
    assert "« Ta mère va bien ? » (dite) : piste sonnet|courte, meuble hum → coupée, score 0,1" in r
