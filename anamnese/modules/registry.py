"""Système de modules — base de l'auto-extension (« ajout de module »).

Un module = une capacité chargée dynamiquement au démarrage. Les nouveaux
modules (y compris ceux générés par l'IA elle-même) sont déposés ici, versionnés
par git, et chargés au lancement.

GARDE-FOU : les modules générés par l'IA vont d'abord dans modules/proposed/
(inactifs). La promotion vers modules/ (actif) est une action humaine explicite.
"""
import inspect
import importlib.util
from pathlib import Path


class Module:
    """Interface minimale. Tout module doit sous-classer ceci."""
    name = "unnamed"
    description = "(pas de description)"

    def run(self, arg: str, context: dict) -> str:
        raise NotImplementedError


def load_modules(active_dir: Path):
    """Charge tous les `Module` trouvés dans active_dir (*.py)."""
    modules = {}
    active_dir = Path(active_dir)
    if not active_dir.exists():
        return modules
    for path in sorted(active_dir.glob("*.py")):
        if path.name.startswith("_") or path.stem == "registry":
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:  # un module cassé ne doit jamais faire tomber le système
            print(f"⚠️  Module '{path.name}' ignoré (erreur : {e})")
            continue
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Module) and obj is not Module:
                try:
                    inst = obj()
                    modules[inst.name] = inst
                except Exception as e:
                    print(f"⚠️  Module '{path.name}' non instancié ({e})")
    return modules
