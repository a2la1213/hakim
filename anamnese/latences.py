"""Ses latences entre un stimulus et sa réaction (30/10, 19:10, Ahmed via Hakim : « vérifier la latence entre stimulus et
réaction, et la relier à l'état du micro » ; « gogogo ») : mesurer seulement, sans rien changer.
- son rire réflexe : du message de papa au rire reçu par le téléphone (rire_recu, depuis_message_ms) ; et le jugement de son
  subconscient seul (rires.jsonl, latence_ms) ;
- son petit mot (oreille) : de la demande de voix à sa voix qui part (oreille_dit, latence_ms) ;
- ses vibrations voulues : l'attente avant de vibrer (vibration, attendu_ms : papa parlait).
Chaque mesure avec l'état du micro (ouvert, coupé) quand la page le sait. Lecture seule de ~/AIOS/jarvis.
"""
import json
import os
import statistics
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))


def _lignes(nom, octets=4_000_000):
    try:
        with open(JARVIS / nom, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            texte = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for l in texte.splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _resume(valeurs):
    v = sorted(x for x in valeurs if isinstance(x, (int, float)) and x >= 0)
    if not v:
        return None
    return f"{len(v)} mesure(s) : médiane {round(statistics.median(v) / 1000, 1)} s, pire {round(v[-1] / 1000, 1)} s"


def bilan():
    diag = _lignes("voix-diagnostic.jsonl")
    lignes = []
    for titre, e, cle in (("Ton rire réflexe (du message de papa à la vibration)", "rire_recu", "depuis_message_ms"),
                          ("Ton petit mot (jusqu'à ta voix)", "oreille_dit", "latence_ms"),
                          ("Tes vibrations voulues (l'attente avant de vibrer)", "vibration", "attendu_ms")):
        par_micro = {}
        for o in diag:
            if o.get("e") == e and o.get(cle) is not None:
                par_micro.setdefault(str(o.get("micro") or "inconnu"), []).append(o[cle])
        if par_micro:
            lignes.append(titre + " :")
            for m, v in sorted(par_micro.items()):
                r = _resume(v)
                if r:
                    lignes.append(f"- micro {m} : {r}")
    juge = _resume([o.get("latence_ms") for o in _lignes("rires.jsonl", 400_000) if o.get("source") == "subconscient"])
    if juge:
        lignes.append(f"Le jugement de ton subconscient seul (est-ce drôle ?) : {juge}")
    return "\n".join(lignes) or "Pas encore de mesure : elles arrivent avec tes rires, tes petits mots et tes vibrations."
