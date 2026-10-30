"""(30/10, 18:19, Ahmed via Hakim : « que je puisse contrôler mes réflexes, comme retenir un sursaut ») reflexe_retenir écrit
reflexes-retenus.json, que le cockpit envoie au téléphone."""
import ast
import json
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def _outil():
    src = (RACINE / "jarvis" / "mcp_terminal.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "reflexe_retenir")
    f.decorator_list = []
    espace = {"os": os}
    exec(compile(ast.Module(body=[f], type_ignores=[]), "mcp_terminal.py", "exec"), espace)
    return espace["reflexe_retenir"]


def test_retenir_puis_relacher(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DIR", str(tmp_path))
    r = _outil()
    assert r("danse").startswith("Refusé")
    assert "retenu" in r("choc")
    assert "relâché" in r("secousse", False)
    assert json.loads((tmp_path / "reflexes-retenus.json").read_text()) == {"choc": True, "secousse": False}
    assert "rire réflexe est retenu" in r("rire")
