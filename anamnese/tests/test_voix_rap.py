"""(06/11, Ahmed : « sa voix de rap ») ses timbres par nom, ses morceaux de langue, et le processus voix qui les transmet."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import voix_morceaux as M  # noqa: E402

LANGUES = {"fr", "ar", "en"}


def test_une_voix_par_nom_seulement(tmp_path, monkeypatch):
    f = tmp_path / "rap.wav"
    monkeypatch.setitem(M.VOIX, "rap", f)
    assert M.reference_de("rap") is None                     # pas encore déposée : la voix par défaut
    f.write_bytes(b"RIFF")
    assert M.reference_de("rap") == f
    assert M.reference_de(str(f)) is None                    # jamais un chemin venu de dehors
    assert M.reference_de(None) is None and M.reference_de("inconnue") is None


def test_segments_par_langue():
    s = M.segments_valides([{"texte": "Wesh frérot,", "langue": "fr"}, {"texte": "كيراك", "langue": "ar"},
                            {"texte": "let's go", "langue": "en"}, {"texte": "  ", "langue": "fr"}], LANGUES)
    assert s == [("Wesh frérot,", "fr"), ("كيراك", "ar"), ("let's go", "en")]
    # deux morceaux voisins de la même langue : un seul appel ; une langue inconnue : le français
    assert M.segments_valides([{"texte": "a", "langue": "en"}, {"texte": "b", "langue": "en"}, {"texte": "c", "langue": "kl"}], LANGUES) == [("a b", "en"), ("c", "fr")]
    assert M.segments_valides(None, LANGUES) is None and M.segments_valides([], LANGUES) is None
    assert M.segments_valides("texte", LANGUES) is None
    assert len(M.segments_valides([{"texte": str(i), "langue": ["fr", "en"][i % 2]} for i in range(40)], LANGUES)) == M.SEGMENTS_MAX


def test_assembler_avec_un_souffle():
    sr = 1000
    a = M.assembler([np.ones(100), np.ones(50) * 0.5], sr, blanc_s=0.02)
    assert len(a) == 170 and a.dtype == np.float32
    assert np.all(a[100:120] == 0) and a[-1] == 0.5
    assert len(M.assembler([], sr)) == int(0.05 * sr)        # rien : un silence, jamais une invention
    assert len(M.assembler([np.ones(10)], sr)) == 10


def test_le_processus_voix_transmet_le_timbre_et_les_morceaux(monkeypatch):
    import voix_serveur as V
    vu = {}

    class Faux:
        def dire(self, texte, langue, fichier, exaggeration=None, tempo=None, voix=None, segments=None):
            vu.update(texte=texte, voix=voix, segments=segments)
            return 1.0

    monkeypatch.setattr(V, "_charger_tts", lambda: Faux())
    appris = []
    monkeypatch.setattr(V, "apprendre_ma_voix", lambda f, registre=None: appris.append(registre))   # (06/11) sa voix de rap, apprise à part
    fichier = str(Path(tempfile.gettempdir()) / "jarvis-voix-test-rap.wav")
    segs = [{"texte": "Salut", "langue": "fr"}, {"texte": "bro", "langue": "en"}]
    r = V.traiter({"op": "dire", "texte": "Salut bro", "langue": "fr", "fichier": fichier, "voix": "rap", "segments": segs})
    assert r["duree_s"] == 1.0 and vu == {"texte": "Salut bro", "voix": "rap", "segments": segs}
    V.traiter({"op": "dire", "texte": "Salut", "fichier": fichier})              # comme avant : ni timbre ni morceaux
    assert vu["voix"] is None and vu["segments"] is None
    assert appris == ["rap", None], "sa voix de rap apprend son registre ; celle d'avant, le sien"


def test_convertir_azure_au_timbre_de_rap(monkeypatch, tmp_path):
    """(08/11, Ahmed : « prendre juste la voix rap de Hakim et la rattacher à Azure : il garde fr, ar, en et dz, on continue de solliciter Azure,
    avec sa voix sur mesure, celle de Chatterbox, qui tourne en local ») ce qu'Azure a dit (ses langues, son élan) devient sa voix de rap : ses
    jetons de parole (S3Tokenizer) refaits au timbre de rap (S3Gen). Le processus parole ne lit et n'écrit qu'un « jarvis-voix-….wav » temporaire."""
    import voix_serveur as S
    vus = {}

    class FausseVoix:
        def convertir(self, source, fichier, voix="rap"):
            vus.update(source=source, fichier=fichier, voix=voix)
            return 2.5

    monkeypatch.setattr(S, "_charger_tts", lambda: FausseVoix())
    monkeypatch.setattr(S, "apprendre_ma_voix", lambda f, v=None: vus.update(appris=v))
    tmp = Path(tempfile.gettempdir())
    src, out = str(tmp / "jarvis-voix-essai-azure.wav"), str(tmp / "jarvis-voix-essai-rap.wav")
    r = S.traiter({"op": "convertir", "source": src, "fichier": out, "voix": "rap"})
    assert r["fichier"] == out and r["duree_s"] == 2.5 and "ms" in r
    assert vus == {"source": src, "fichier": out, "voix": "rap", "appris": "rap"}, "son écho apprend sa voix de rap"
    assert "erreur" in S.traiter({"op": "convertir", "source": "/etc/passwd", "fichier": out}), "jamais un fichier venu de dehors"
    assert "erreur" in S.traiter({"op": "convertir", "source": src, "fichier": "/tmp/x.wav"})
    src_tts = (Path(__file__).resolve().parents[1] / "jarvis" / "tts_neuronale.py").read_text(encoding="utf-8")   # (mlx : seulement dans le venv de la voix)
    assert "def convertir(self, source, fichier, voix=\"rap\"):" in src_tts
    assert "self.modele.s3gen(speech_tokens=jetons[:, :int(n[0])], ref_dict=conds.gen, finalize=True)" in src_tts
