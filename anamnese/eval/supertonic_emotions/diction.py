"""(04/11) la diction des essais de verifier.py relue par Whisper (venv de jarvis) : {"<nom>-<i>": CER} sur la dernière ligne.
Usage : jarvis/.venv/bin/python eval/supertonic_emotions/diction.py <dossier des wav>"""
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "jarvis"))
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))
import stt  # noqa: E402
from phrases import PHRASES  # noqa: E402
from voix_plage import cer  # noqa: E402

cers = {}
for f in sorted(Path(sys.argv[1]).glob("*.wav")):
    nom = f.stem
    lu = stt.transcrire(str(f), langue="fr")
    texte = lu.get("texte", "") if isinstance(lu, dict) else str(lu)
    cers[nom] = round(cer(PHRASES[int(nom.rsplit("-", 1)[1])], texte), 4)
print(json.dumps(cers))
