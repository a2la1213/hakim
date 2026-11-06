"""Le studio (06/11, Ahmed : « m'enregistrer et me faire mixer et masteriser par Hakim ») : la chaîne de mixage sur un vrai
petit WAV synthétique (ffmpeg), le calage de la latence, la copie pour le téléphone, la file des calculs, les outils de Hakim."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import studio  # noqa: E402

FFMPEG = studio.FFMPEG
pytestmark = pytest.mark.skipif(not Path(FFMPEG).exists(), reason="ffmpeg absent")


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    """Jamais le vrai téléphone ni les vraies tâches."""
    monkeypatch.setattr(studio, "TELEPHONE", tmp_path / "telephone" / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "STUDIO", tmp_path / "chansons" / "studio")
    monkeypatch.setattr(studio, "CHANSONS", tmp_path / "chansons")
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)


def _wav(chemin, filtre, entrees, duree=10, canaux=1):
    args = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    for e in entrees:
        args += ["-f", "lavfi", "-i", f"{e}:d={duree}"]
    subprocess.run(args + ["-filter_complex", filtre, "-ac", str(canaux), "-ar", "48000", str(chemin)], check=True)
    return chemin


@pytest.fixture
def sons(tmp_path):
    """Une instru (une basse et un clic toutes les 0,5 s) et une voix qui attaque 150 ms APRÈS chaque clic (une prise en
    retard de 150 ms, comme une latence de casque), avec un léger souffle."""
    instru = _wav(tmp_path / "instru.wav", "[1]volume='0.6*lt(mod(t,0.5),0.03)':eval=frame[k];[0][k]amix=inputs=2:normalize=0",
                  ["sine=f=110", "sine=f=1000"], canaux=2)
    voix = _wav(tmp_path / "voix.wav",
                "[0]volume='0.4*between(mod(t-0.15,0.5),0,0.25)*gte(t,0.15)':eval=frame[v];[1]volume=0.5[n];[v][n]amix=inputs=2:normalize=0",
                ["sine=f=220", "anoisesrc=a=0.002"])
    return voix, instru


def test_les_chaines_contiennent_les_bons_filtres():
    assert studio.chaine_nettoyage() == ["highpass=f=80:poles=2", "afftdn=nr=10:nf=-45:tn=1"]
    assert studio.chaine_nettoyage(False) == ["highpass=f=80:poles=2"]
    v = ",".join(studio.chaine_voix(reverb=0.5, echo=0.5, bpm=100))
    for f in ("equalizer=f=250", "equalizer=f=3500", "deesser", "acompressor=threshold=-20dB:ratio=3", "aecho"):
        assert f in v
    assert "450|900" in v                                   # l'écho sur le temps : une croche pointée à 100 BPM
    assert "aecho" not in ",".join(studio.chaine_voix(reverb=0, echo=0))


def test_mixer_masterise_a_moins_14_lufs_et_copie_au_telephone(sons, tmp_path):
    voix, instru = sons
    etapes = []
    f = studio.mixer(voix, instru, tmp_path / "studio", titre="Essai", latence_ms=150, reverb=0.3,
                     progres=lambda n, t: etapes.append(n))
    assert Path(f["wav"]).is_file() and Path(f["mp3"]).is_file()
    assert abs(f["mesure"]["lufs"] - studio.CIBLE_LUFS) <= 1.0, f["mesure"]
    assert f["mesure"]["crete_db"] <= -0.9, f["mesure"]
    m = studio.mesurer(f["mp3"])                             # le MP3 aussi est au niveau
    assert abs(m["lufs"] - studio.CIBLE_LUFS) <= 1.0
    assert Path(f["telephone"]) == studio.TELEPHONE / Path(f["mp3"]).name and Path(f["telephone"]).is_file()
    assert etapes == [1, 2, 4, 5, 6, 7]                      # sans autotune, l'étape 3 est sautée
    fiche = json.loads((tmp_path / "studio" / f"{f['nom']}.json").read_text())
    assert fiche["reglages"]["latence_ms"] == 150 and fiche["avis"]["conseils"]
    assert not list((tmp_path / "studio").glob(".mix-*"))     # le dossier de travail effacé


def test_la_latence_retiree_recale_la_voix_sur_le_temps(sons, tmp_path):
    """Témoin : sans calage, l'écart mesuré est le retard de la prise (~ +150 ms) ; avec 150 ms retirés, il tombe près de 0."""
    voix, instru = sons
    x, sr = studio._pcm(voix)
    i, _ = studio._pcm(instru)
    brut, conf = studio.decalage_temps(x, i, sr)
    assert 120 <= brut <= 180 and conf >= 0.18, (brut, conf)
    f = studio.mixer(voix, instru, tmp_path / "s", latence_ms=150, reverb=0, debruitage=False)
    assert abs(f["avis"]["mesures"]["decalage_ms"]) <= 30, f["avis"]["mesures"]
    g = studio.mixer(voix, instru, tmp_path / "s", latence_ms=0, reverb=0, debruitage=False)
    assert g["avis"]["mesures"]["decalage_ms"] >= 120
    assert any("en retard" in c for c in g["avis"]["conseils"])


def test_avis_saturation_et_souffle(tmp_path):
    instru = _wav(tmp_path / "i.wav", "[0]volume=0.3", ["sine=f=110"], duree=5, canaux=2)
    sale = _wav(tmp_path / "v.wav", "[0]volume=12[v];[1]volume=1[n];[v][n]amix=inputs=2:normalize=0",
                ["sine=f=300", "anoisesrc=a=0.05"], duree=5)
    f = studio.mixer(sale, instru, tmp_path / "s", reverb=0)
    texte = " ".join(f["avis"]["conseils"])
    assert "sature" in texte and "souffle" in texte
    assert f["avis"]["mesures"]["decalage_confiance"] < 0.18 and "retard" not in texte and "avance" not in texte   # un son tenu : pas d'avis sur le temps


@pytest.mark.skipif(not studio.PYTHON_CHANT.exists(), reason="venv du chant absent")
def test_autotune_dans_le_venv_du_chant(sons, tmp_path):
    voix, instru = sons
    code = (f"import sys; sys.path.insert(0, {str(studio.ICI)!r}); import studio, json; "
            f"f = studio.mixer({str(voix)!r}, {str(instru)!r}, {str(tmp_path / 's')!r}, autotune=True, telephone={str(tmp_path / 't')!r}); "
            "print(json.dumps(f['reglages']))")
    r = subprocess.run([str(studio.PYTHON_CHANT), "-B", "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-500:]
    reg = json.loads(r.stdout.strip().splitlines()[-1])
    assert reg["autotune"] is True and reg["tonalite"]


def test_copie_au_telephone_et_synchronisation(tmp_path):
    c = tmp_path / "chansons"
    (c / "studio").mkdir(parents=True)
    (c / "a.mp3").write_bytes(b"ID3 a")
    (c / "a-sans-correction.mp3").write_bytes(b"ID3 brut")
    (c / "studio" / "mix.mp3").write_bytes(b"ID3 mix")
    tel = tmp_path / "tel"
    assert studio.synchroniser(c, tel) == ["a.mp3", "mix.mp3"]
    assert sorted(p.name for p in tel.iterdir()) == ["a.mp3", "mix.mp3"]
    assert studio.synchroniser(c, tel) == ["a.mp3", "mix.mp3"]       # une deuxième fois : rien ne change
    assert studio.copier_au_telephone(tmp_path / "absent.mp3", tel) is None


def test_la_file_un_travail_a_la_fois(sons, tmp_path):
    voix, instru = sons
    lancés = []
    j = studio.lancer("mixer", {"prise": str(voix), "instru": str(instru), "titre": "File", "reverb": 0},
                      demarrer=lancés.append)
    d = studio.STUDIO / "travaux"
    assert lancés == [d] and json.loads((d / f"{j['id']}.json").read_text())["etat"] == "en attente"
    with pytest.raises(studio.Refus, match="prise introuvable"):
        studio.lancer("mixer", {"prise": "/nulle/part.wav", "instru": str(instru)}, demarrer=lancés.append)
    with pytest.raises(studio.Refus, match="type"):
        studio.lancer("effacer-tout", {}, demarrer=lancés.append)
    assert studio.travailleur(d) == 1
    fin = json.loads((d / f"{j['id']}.json").read_text())
    assert fin["etat"] == "fini" and fin["resultat"]["mesure"]["lufs"] is not None and fin["etape"] == 7
    assert studio.occupe() is None


def test_occupe_et_chanson_qui_attend(tmp_path, monkeypatch):
    d = studio.STUDIO / "travaux"
    d.mkdir(parents=True)
    (d / "J-1.json").write_text(json.dumps({"id": "J-1", "etat": "en cours", "pid": os.getpid()}))
    assert studio.occupe()["id"] == "J-1"
    sys.path.insert(0, str(studio.ICI))
    import chant
    monkeypatch.setattr(chant, "PYTHON_CHANT", Path(sys.executable))
    monkeypatch.setattr(chant, "ACE", tmp_path)
    (tmp_path / "checkpoints").mkdir()
    with pytest.raises(chant.Refus, match="studio calcule"):
        chant.lancer("la", "rap", 30, dossier=tmp_path / "t", chansons=tmp_path / "c")
    (d / "J-1.json").write_text(json.dumps({"id": "J-1", "etat": "en cours", "pid": 999999}))
    assert studio.occupe() is None                          # un travailleur mort ne bloque rien


def test_outils_de_hakim(monkeypatch, tmp_path, sons):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    mixer = mcp_server.mcp._tool_manager.get_tool("studio_mixer").fn
    avis = mcp_server.mcp._tool_manager.get_tool("studio_avis").fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert mixer() == "Seul Hakim mixe dans le studio."
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    assert "Aucune prise" in mixer()
    voix, instru = sons
    p = studio.STUDIO / "prises"
    p.mkdir(parents=True)
    (p / "P-1.json").write_text(json.dumps({"id": "P-1", "fichier": str(voix), "instru_chemin": str(instru), "ts": 1,
                                            "latence_ms": 150, "choisie": True, "titre": "Ma prise", "instru_titre": "Basse"}))
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = mixer(voix_db=2, reverb=0.2)
    assert r.startswith("Mix lancé") and "prise P-1" in r and len(vus) == 1
    assert "En cours : mixer" in avis() and "P-1 (choisie)" in avis()
    studio.travailleur(studio.STUDIO / "travaux")
    texte = avis()
    assert "LUFS intégrés" in texte and "Ce que tu entends" in texte and "latence retirée 150" in texte
