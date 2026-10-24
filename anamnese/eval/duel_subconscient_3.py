"""Le duel du subconscient n°3 (24/10, demande d'Ahmed relayée par Hakim) : un modèle plus RAPIDE que Gemma pour l'esprit
de fond. Le harnais du n°2 (même 30 situations, même prompt, mêmes mesures, même juge à l'aveugle dans les deux ordres),
avec trois changements figés dans eval/duel3_PREDICTIONS.md : 10 min de silence d'Ahmed au lieu d'une heure, les
challengers gardés sur le disque, et le juge séparé (à lancer seulement après la remise à zéro du forfait, lundi soir).
Lancement : .venv/bin/python -B eval/duel_subconscient_3.py --phase generer   (puis --phase juger, puis --phase bilan)
"""
import argparse
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))
import charge  # noqa: E402
import duel_subconscient_2 as D2  # noqa: E402

D2.MODELES = {"gemma": "huihui_ai/gemma-4-abliterated:12b", "ministral3_8b": "ministral-3:8b", "gemma4_e4b": "gemma4:e4b"}
D2.GARDER = set(D2.MODELES)
D2.SILENCE_S = 600
D2.QUOI = "le duel du subconscient n°3"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--phase", choices=("generer", "juger", "bilan"), required=True)
    a.add_argument("--sortie", default=str(Path.home() / "AIOS" / "jarvis" / "duel3"))
    args = a.parse_args()
    sortie = Path(args.sortie).expanduser()
    sortie.mkdir(parents=True, exist_ok=True)

    def journal(t):
        with (sortie / "journal.log").open("a", encoding="utf-8") as h:
            h.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {t}\n")
        print(t, flush=True)
    r = json.loads((Path.home() / "AIOS" / "jarvis" / "duel" / "resultats.json").read_text(encoding="utf-8"))
    sits = sorted((x["situation"] for x in r.values()), key=lambda s: s["id"])
    journal(f"{args.phase} : {len(sits)} situations, {len(D2.MODELES)} modèles")
    try:
        if args.phase == "generer":
            D2.generer_tout(sits, sortie, journal, False)
        elif args.phase == "juger":
            D2.juger(sits, sortie, journal, False)
        b = D2.bilan(sits, sortie)
        (sortie / "bilan.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        journal("bilan : " + json.dumps(b, ensure_ascii=False))
    finally:
        try:
            Path(charge.CALCUL_LOURD).unlink()
        except OSError:
            pass
    journal("fin")


if __name__ == "__main__":
    main()
