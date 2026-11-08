"""Le sous-agent Sonnet payé de consolidate est borné en tours (frein anti-runaway)."""
import inspect
import consolidate


def test_consolidate_command_has_max_turns():
    src = inspect.getsource(consolidate._run)  # le run vit dans _run depuis le 2026-10-15
    assert "--max-turns" in src and consolidate.MAX_TURNS.isdigit(), "le run claude sonnet doit être borné en tours"
    # le timeout wall-clock existant reste (double frein)
    assert "timeout=900" in src
