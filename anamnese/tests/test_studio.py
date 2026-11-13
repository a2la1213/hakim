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
    monkeypatch.setattr(studio, "DOCUMENTS", tmp_path / "telephone" / "Hakim")              # (10/11) ses Documents, jamais les vrais
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", tmp_path / "telephone-ecritures.jsonl")
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
    assert reg["autotune"] is True and reg["autotune_niveau"] == "leger" and reg["tonalite"]
    assert reg["autotune_rapport"]["niveau"] == "leger"


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


# ---------------------------------------------------------------------------------------------- son instru, pour la voix de papa
# (09/11, Ahmed : « qu'il sache extraire SON instru d'une de ses chansons, “Deux livres” par exemple, pour que je pose ma voix dessus »)

def _chanson(dossier, nom, titre, fin, mp3=True, etat="prête", instrumental=False, depuis=None):
    dossier.mkdir(parents=True, exist_ok=True)
    f = dossier / f"{nom}.mp3"
    if mp3:
        if depuis:
            subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(depuis), "-c:a", "libmp3lame", str(f)], check=True)
        else:
            f.write_bytes(b"ID3 " + nom.encode())
    (dossier / f"{nom}.json").write_text(json.dumps({"nom": nom, "titre": titre, "etat": etat, "fin": fin, "instrumental": instrumental,
                                                     **({"mp3": str(f)} if mp3 else {})}))
    return f


@pytest.fixture
def separateur(tmp_path, monkeypatch):
    """Un faux Demucs (le vrai pèse trop pour la suite) : il reçoit « -B chant.py separer mélange voix reste », note le mélange
    reçu, rend la voix et le reste (une copie du mélange). Ce qu'on teste : la bonne chanson y entre, son reste devient l'instru."""
    vus = tmp_path / "separes.txt"
    s = tmp_path / "faux-demucs"
    # (13/11) deux façons de l'appeler : « -B chant.py separer mélange voix reste » (l'autotune) et « -B -W ignore studio_separation.py
    # separer mélange dossier --modeles … » (l'instru du studio) : le dossier reçoit instru.wav (le mélange) et vocals.wav
    s.write_text(f'''#!/bin/sh
if [ "$2" = "-W" ]; then
  echo "$5 $6 $*" >> "{vus}"; mkdir -p "$7"; cp "$6" "$7/instru.wav"; cp "$6" "$7/vocals.wav"
  echo "{{\\"pistes\\": {{\\"vocals\\": \\"$7/vocals.wav\\"}}, \\"instru\\": \\"$7/instru.wav\\", \\"modeles\\": [\\"htdemucs_ft\\", \\"htdemucs\\"]}}"
else
  echo "$3 $4" >> "{vus}"; cp "$4" "$5"; cp "$4" "$6"
fi
''')
    s.chmod(0o755)
    monkeypatch.setattr(studio, "PYTHON_SEPARATION", s)
    return vus


def test_trouver_sa_chanson_par_son_titre(tmp_path):
    c = studio.CHANSONS
    _chanson(c, "20261109-165302-deux-livres", "Deux livres", 100)
    _chanson(c, "20261109-171743-deux-livres", "Deux livres", 200)
    _chanson(c, "20261109-172807-deux-livres-voix-naturelle", "Deux livres (voix naturelle)", 300)
    _chanson(c, "20261109-180000-deux-livres", "Deux livres", 400, mp3=False, etat="ratée")
    (c / "20261109-171743-deux-livres-sans-correction.mp3").write_bytes(b"ID3 brut")
    d, autres = studio.trouver_chanson("  deux LIVRES ")
    assert d["nom"] == "20261109-171743-deux-livres"          # le titre exact, la plus récente finie (pas la ratée)
    assert [x["nom"] for x in autres] == ["20261109-165302-deux-livres", "20261109-172807-deux-livres-voix-naturelle"]
    assert studio.trouver_chanson("20261109-165302-deux-livres")[0]["nom"] == "20261109-165302-deux-livres"
    assert studio.trouver_chanson("Voix naturelle")[0]["nom"] == "20261109-172807-deux-livres-voix-naturelle"
    with pytest.raises(studio.Refus, match="Lanterne.*Deux livres"):
        studio.trouver_chanson("Lanterne")
    with pytest.raises(studio.Refus):
        studio.trouver_chanson("")


def test_son_instru_entre_dans_les_instrus_du_studio(sons, tmp_path, separateur):
    voix, instru = sons
    melange = tmp_path / "melange.wav"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(instru), "-i", str(voix), "-filter_complex",
                    "amix=inputs=2:normalize=0", str(melange)], check=True)
    mp3 = _chanson(studio.CHANSONS, "20261109-171743-deux-livres", "Deux livres", 200, depuis=melange)
    _chanson(studio.CHANSONS, "20261109-100000-beat", "Beat", 100, instrumental=True)
    avant = mp3.read_bytes()
    lances = []
    r = studio.instru_de_chanson("Deux livres", demarrer=lances.append)
    assert r["etat"] == "lancé" and len(lances) == 1 and r["travail"]["params"]["source"] == str(mp3.resolve())
    assert studio.instru_de_chanson("deux livres", demarrer=lances.append)["etat"] == "en file" and len(lances) == 1
    assert studio.travailleur(studio.STUDIO / "travaux") == 1
    assert separateur.read_text().split()[0] == "separer"     # Demucs a bien reçu sa chanson
    i = json.loads(next((studio.STUDIO / "instrus").glob("*.json")).read_text())
    assert i["origine"] == "demucs" and i["source"] == str(mp3.resolve()) and i["titre"] == "Deux livres (instru)"
    assert Path(i["mp3"]).is_file() and abs(i["duree_s"] - 10) < 0.5
    assert mp3.read_bytes() == avant                          # sa chanson n'est pas touchée
    d = studio.instru_de_chanson("Deux livres", demarrer=lances.append)
    assert d["etat"] == "déjà" and d["instru"]["id"] == i["id"] and len(lances) == 1       # pas deux fois le même calcul
    assert studio.instru_de_chanson("Deux livres", refaire=True, demarrer=lances.append)["etat"] == "lancé" and len(lances) == 2
    assert studio.instru_du_studio(i["id"]) == i["mp3"] and studio.instru_du_studio("deux livres (INSTRU)") == i["mp3"]
    assert studio.instru_du_studio("inconnue") == ""
    with pytest.raises(studio.Refus, match="déjà une instru"):
        studio.instru_de_chanson("Beat", demarrer=lances.append)


def test_outil_studio_instru_puis_la_prise_de_papa_mixee_dessus(monkeypatch, tmp_path, sons, separateur):
    """Le chemin entier de Hakim : studio_instru → l'instru dans le Studio → papa y pose sa prise → studio_mixer la mixe DESSUS."""
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = mcp_server.mcp._tool_manager.get_tool("studio_instru").fn
    mixer = mcp_server.mcp._tool_manager.get_tool("studio_mixer").fn
    avis = mcp_server.mcp._tool_manager.get_tool("studio_avis").fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert outil("Deux livres") == "Seul Hakim tire une instru de ses chansons."
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    voix, instru = sons
    mp3 = _chanson(studio.CHANSONS, "20261109-171743-deux-livres", "Deux livres", 200, depuis=instru)
    _chanson(studio.CHANSONS, "20261109-172807-deux-livres-voix-naturelle", "Deux livres (voix naturelle)", 300, depuis=instru)
    assert "« Deux livres (voix naturelle) » (20261109-172807" in outil()
    assert outil("Lanterne").startswith("Refusé : aucune de tes chansons")
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = outil("Deux livres")
    assert r.startswith("Instru lancée") and "20261109-171743-deux-livres" in r and "Autres versions" in r and len(vus) == 1
    assert "En cours : instru" in avis()
    studio.travailleur(studio.STUDIO / "travaux")
    i = json.loads(next((studio.STUDIO / "instrus").glob("*.json")).read_text())
    texte = avis()
    assert f"Instru prête" in texte and i["id"] in texte and "Instrus du Studio" in texte
    assert outil("Deux livres").startswith("Déjà dans le Studio") and len(vus) == 1
    # papa enregistre sa prise sur cette instru (la page du Studio écrit cette fiche)
    p = studio.STUDIO / "prises"
    p.mkdir(parents=True)
    (p / "P-1.json").write_text(json.dumps({"id": "P-1", "fichier": str(voix), "instru_chemin": i["mp3"], "ts": 1, "latence_ms": 150,
                                            "titre": "Papa sur Deux livres", "instru_titre": i["titre"]}))
    assert mixer(instru="inconnue").startswith("Refusé : instru inconnue")
    assert mixer(reverb=0.2).startswith("Mix lancé") and len(vus) == 2
    studio.travailleur(studio.STUDIO / "travaux")
    m = max(studio.STUDIO.glob("*.json"), key=lambda f: f.stat().st_mtime)
    fiche = json.loads(m.read_text())
    assert fiche["instru"] == i["mp3"] and fiche["prise"] == str(voix) and abs(fiche["mesure"]["lufs"] - studio.CIBLE_LUFS) <= 1.0
    assert mixer(instru=i["id"]).startswith("Mix lancé")       # ou son identifiant, donné par Hakim
    j = max((studio.STUDIO / "travaux").glob("J-*.json"), key=lambda f: f.stat().st_mtime)
    assert json.loads(j.read_text())["params"]["instru"] == i["mp3"]


def test_instru_gardee_par_papa_et_la_meilleure_separation(sons, tmp_path, separateur):
    """(13/11, Ahmed : « garder ce que je lui demande sur l'instru ») « garde la batterie et la basse » arrive à la séparation en noms de
    Demucs ; l'ensemble mesuré (ft + htdemucs) et la porte de la voix sont demandés ; le titre le dit."""
    voix, instru = sons
    f = studio.extraire_instru(instru, tmp_path / "instrus", titre="Moujahid 3.2", garder=["Batterie", "basse", "n'importe quoi"])
    ligne = separateur.read_text()
    assert "--modeles htdemucs_ft,htdemucs" in ligne and "--porte -25" in ligne and "--garder bass,drums" in ligne
    assert f["garder"] == ["bass", "drums"] and f["titre"] == "Moujahid 3.2 (instru : bass, drums)" and Path(f["mp3"]).is_file()
    g = studio.extraire_instru(instru, tmp_path / "instrus", titre="Tout")
    assert "--garder" not in separateur.read_text().splitlines()[-1] and g["titre"] == "Tout (instru)"


def test_instru_de_la_somme_et_la_soustraction():
    import numpy as np
    import studio_separation as S
    r = np.random.default_rng(1)
    p = {k: r.standard_normal((1000, 2)).astype(np.float32) for k in ("drums", "bass", "other", "vocals")}
    x = sum(p.values()) + 0.01                                # un reste qu'aucune piste n'a pris
    assert np.allclose(S.instru_de(x, p), x - p["vocals"])    # tout le non-vocal : le mélange moins la voix (le reste gardé)
    assert np.allclose(S.instru_de(x, p, ["drums", "bass"]), p["drums"] + p["bass"])
    assert np.allclose(S.instru_de(x, p, ["vocals"]), 0)      # la voix n'est jamais « gardée » dans une instru
