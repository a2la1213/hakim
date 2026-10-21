"""boot_brief = source de vérité unique du briefing de démarrage (santé + MDT), bornée, best-effort.
DB temp migrée, jamais data/memory.db."""
import time
import pytest
import config, memory, migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    for i in range(5):
        m.add("user", f"souvenir saillant numéro {i}", importance=0.7, embedding=[0.0] * 8)
    m.db.commit()
    yield m
    m.db.close()


def test_boot_brief_amorce_et_borne(mem):
    out = mem.boot_brief(time.time(), cap=1200)
    assert "MDT amorcée" in out                 # tête MDT présente
    assert len(out) <= 1200                       # borné (anti-bloat)


def test_boot_brief_best_effort_db_legacy(tmp_path, monkeypatch):
    # DB sans working_memory/kv santé : ne lève pas, renvoie qqch de propre
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "leg.db")
    migrations.migrate(m.db)
    out = m.boot_brief(time.time())
    assert isinstance(out, str)                    # jamais d'exception
    m.db.close()


def test_boot_brief_injecte_skills_et_reasoning(tmp_path, monkeypatch):
    import embeddings, migrations
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "s.db")
    migrations.migrate(m.db)
    m.add("user", "je travaille sur le routage TVA batiment", importance=0.9, embedding=[0.1] * 8)
    m.save_skill("tva-batiment", "calcul TVA chantier", "procédure : ...")
    m.add("reasoning", "problème TVA → étapes → décision : appliquer 10%", importance=0.8, embedding=[0.1] * 8)
    m.db.commit()
    out = m.boot_brief(__import__("time").time(), cap=2000)
    assert "tva-batiment" in out or "compétence" in out.lower()   # au moins une skill remonte
    assert len(out) <= 2000                                        # toujours borné
    m.db.close()


def test_boot_brief_cap_tronque_par_lignes_et_garde_hints(tmp_path, monkeypatch):
    import embeddings, migrations, time as _t
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "big.db")
    migrations.migrate(m.db)
    for i in range(40):                                  # focus énorme → force le cap
        m.add("user", f"souvenir de continuité tres long numero {i} " * 4, importance=0.9, embedding=[0.1] * 8)
    m.save_skill("proc-cle", "procédure clé à ne pas perdre", "…")
    m.db.commit()
    out = m.boot_brief(_t.time(), cap=800)
    assert len(out) <= 800                                # borné
    assert "\n" in out and not out.endswith(" ")          # tronqué par lignes, pas un mot coupé net
    assert "proc-cle" in out or "réutiliser" in out.lower()  # les hints survivent au cap (placés avant le focus)
    m.db.close()


def test_boot_brief_degrade_sans_exception(tmp_path, monkeypatch):
    import embeddings, migrations, time as _t
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.1] * 8)
    m = Memory(db_path=tmp_path / "deg.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(Memory, "wm_boot", lambda self, now: (_ for _ in ()).throw(RuntimeError("boom")))
    out = m.boot_brief(_t.time())                          # wm_boot KO → dégradé, jamais d'exception
    assert isinstance(out, str) and "dégradé" in out.lower()
    m.db.close()


def test_cli_wm_boot_and_outreach(tmp_path, monkeypatch, capsys):
    import sys, cli
    import memory as memory_mod, embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)

    class TmpMemory(Memory):
        def __init__(self):
            super().__init__(db_path=tmp_path / "c.db")
            migrations.migrate(self.db)
            self.add("user", "contexte de reprise batiment", importance=0.8, embedding=[0.0] * 8)
            self.db.commit()
    monkeypatch.setattr(memory_mod, "Memory", TmpMemory)
    monkeypatch.setattr(sys, "argv", ["anamnese", "wm-boot"])
    cli.main()
    assert "MDT amorcée" in capsys.readouterr().out
    # outreach porte MAINTENANT le seed en tête
    monkeypatch.setattr(sys, "argv", ["anamnese", "outreach"])
    cli.main()
    assert "MDT amorcée" in capsys.readouterr().out
