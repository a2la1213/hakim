"""La commande dreams : rapport imprimé, lecture seule."""
import sys

import migrations
from memory import Memory


def test_cmd_dreams(tmp_path, monkeypatch, capsys):
    import cli
    import memory as memory_mod

    class TmpMemory(Memory):
        def __init__(self):
            super().__init__(db_path=tmp_path / "t.db")
            migrations.migrate(self.db)

    monkeypatch.setattr(memory_mod, "Memory", TmpMemory)
    monkeypatch.setattr(sys, "argv", ["anamnese", "dreams"])
    cli.main()
    out = capsys.readouterr().out
    assert "VERDICT" in out and "INSUFFISANT" in out
