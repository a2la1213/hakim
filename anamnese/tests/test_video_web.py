"""Les vidéos en ligne (jarvis/video_web.py) : les sous-titres d'abord, la vidéo seulement sans eux ; sans réseau ici."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import video_web as V  # noqa: E402

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>bonjour</c> à tous

00:00:02.500 --> 00:00:04.000
bonjour à tous
aujourd'hui on parle de maths

00:00:20.000 --> 00:00:22.000
et voilà la fin
"""


def test_vtt_sans_repetitions():
    t = V.lire_vtt(VTT)
    assert t == "[0:01] bonjour à tous aujourd'hui on parle de maths\n[0:20] et voilà la fin"


def faux_lancer(meta, sous_titres=True, video=True):
    def lancer(commande, delai, atelier):
        d = Path(atelier)
        if "--dump-single-json" in commande:
            return 0, "[info] …\n" + json.dumps(meta)
        if "--skip-download" in commande and sous_titres:
            dossier = d / commande.split(" -o ")[1].split()[0].strip("'")
            (dossier.parent).mkdir(parents=True, exist_ok=True)
            Path(str(dossier) + ".fr.vtt").write_text(VTT)
            return 0, ""
        if "-f " in commande and video:
            dossier = d / commande.split(" -o ")[1].split()[0].strip("'").replace("video.%(ext)s", "")
            (dossier / "video.mp4").write_bytes(b"\0" * 10)
            return 0, ""
        return 1, "ERROR: rien"
    return lancer


def test_sous_titres_seuls(tmp_path, monkeypatch):
    meta = {"title": "Cours", "channel": "Chaîne", "duration": 125, "upload_date": "20261020",
            "webpage_url": "https://www.youtube.com/watch?v=x", "subtitles": {"fr": []}}
    monkeypatch.setattr(V, "_lancer", faux_lancer(meta))
    monkeypatch.setattr(V, "YTDLP", tmp_path / "yt-dlp"); (tmp_path / "yt-dlp").write_text("")
    appels = []
    r = V.preparer("https://www.youtube.com/watch?v=x", atelier=tmp_path / "atelier", verifier=lambda h, p: None,
                   preparer_fichier=lambda *a, **k: appels.append(a) or {})
    assert r["source"] == "sous-titres manuels (fr)" and "aujourd'hui on parle de maths" in r["texte"] and not appels
    assert "Cours" in V.resume(r) and "20/10/2026" in V.resume(r) and "2:05" in V.resume(r)
    assert not any((tmp_path / "atelier" / "videos-web").iterdir())          # rien ne reste


def test_sans_sous_titres_la_video_est_transcrite(tmp_path, monkeypatch):
    meta = {"title": "Vlog", "duration": 300, "webpage_url": "https://www.youtube.com/watch?v=y"}
    monkeypatch.setattr(V, "_lancer", faux_lancer(meta, sous_titres=False))
    monkeypatch.setattr(V, "YTDLP", tmp_path / "yt-dlp"); (tmp_path / "yt-dlp").write_text("")
    r = V.preparer("https://www.youtube.com/watch?v=y", atelier=tmp_path / "atelier", verifier=lambda h, p: None,
                   preparer_fichier=lambda chemin, transcrire=None: {"lire": ["/x/image-01.jpg"], "texte": "salut tout le monde",
                                                                       "note": "9 images clés, transcription de la bande son"})
    assert r["source"].startswith("transcription locale") and r["texte"] == "salut tout le monde" and r["lire"] == ["/x/image-01.jpg"]


def test_refus(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "YTDLP", tmp_path / "yt-dlp"); (tmp_path / "yt-dlp").write_text("")
    with pytest.raises(V.Refus):
        V.preparer("http://127.0.0.1:4317/parler", atelier=tmp_path / "atelier")
    monkeypatch.setattr(V, "_lancer", faux_lancer({"title": "Direct", "is_live": True}))
    with pytest.raises(V.Refus):
        V.preparer("https://www.youtube.com/watch?v=z", atelier=tmp_path / "atelier", verifier=lambda h, p: None)
