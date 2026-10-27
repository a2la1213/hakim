"""Les pièces jointes de Hakim : d'où elles peuvent venir, et ce qui est copié."""
import json

import pytest

import pieces


@pytest.fixture
def jarvis(tmp_path):
    for d in ("cwd/atelier/pour_ahmed", "cwd/fichiers", "cwd/calculs", "journal"):
        (tmp_path / d).mkdir(parents=True)
    return tmp_path


def test_joindre_copie_et_indexe(jarvis):
    (jarvis / "cwd/atelier/pour_ahmed/test.txt").write_text("bonjour Ahmed")
    f = pieces.joindre("atelier/pour_ahmed/test.txt", "un test", jarvis=jarvis)
    copie = jarvis / "pieces" / f["id"] / "test.txt"
    assert copie.read_text() == "bonjour Ahmed" and f["taille"] == 13 and f["type"] == "txt"
    (jarvis / "cwd/atelier/pour_ahmed/test.txt").write_text("changé après coup")
    assert copie.read_text() == "bonjour Ahmed"                      # ce qui a été joint ne bouge plus
    idx = [json.loads(l) for l in (jarvis / "pieces/index.jsonl").read_text().splitlines()]
    assert idx[0]["id"] == f["id"] and idx[0]["origine"] == "atelier/pour_ahmed/test.txt"


def test_refus(jarvis, tmp_path):
    (jarvis / "cwd/calculs/r.txt").write_text("x")
    (jarvis / "journal/j.txt").write_text("x")
    (jarvis / "cwd/atelier/.env").write_text("x")
    (jarvis / "cwd/atelier/cle.txt").write_text("ma clé : sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789")
    (jarvis / "cwd/atelier/gros.bin").write_bytes(b"0" * (pieces.TAILLE_MAX + 1))
    (jarvis / "cwd/atelier/lien.txt").symlink_to(jarvis / "journal/j.txt")
    for c in ("calculs/r.txt", str(jarvis / "journal/j.txt"), "atelier/.env", "atelier/cle.txt", "atelier/gros.bin",
              "atelier/lien.txt", "atelier/absent.txt", "atelier"):
        with pytest.raises(pieces.Refus):
            pieces.joindre(c, jarvis=jarvis)


def test_fichier_d_ahmed_et_image(jarvis):
    (jarvis / "cwd/fichiers/photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 20)
    f = pieces.joindre(str(jarvis / "cwd/fichiers/photo.png"), jarvis=jarvis)
    assert f["type"] == "png" and (jarvis / "pieces" / f["id"] / "photo.png").exists()


def test_un_lien_dur_dans_l_atelier_n_est_pas_joint(jarvis):
    """(27/10, Ahmed : « boucher toutes les failles ») un lien dur ne se voit pas au chemin : il est refusé."""
    import os
    (jarvis / "journal/j.txt").write_text("le journal brut")
    os.link(jarvis / "journal/j.txt", jarvis / "cwd/atelier/pour_ahmed/dur.txt")
    with pytest.raises(pieces.Refus, match="lien dur"):
        pieces.joindre("atelier/pour_ahmed/dur.txt", jarvis=jarvis)


def test_un_tube_glisse_apres_la_verification_ne_fige_pas_le_serveur(jarvis, monkeypatch):
    """(relecture indépendante du 27/10, E) is_file() puis os.open sans O_NONBLOCK : un tube nommé substitué entre les
    deux figeait le serveur anamnese à l'ouverture (personne n'écrit dedans)."""
    import os
    import signal
    os.mkfifo(jarvis / "cwd/atelier/pour_ahmed/t.txt")
    monkeypatch.setattr(pieces.Path, "is_file", lambda self: True)          # la course gagnée : on a vu un fichier

    class Fige(Exception):                                                  # pas un OSError : rien ne le rattrape
        pass

    def fige(*_):
        raise Fige("l'ouverture du tube a figé le serveur")
    ancien = signal.signal(signal.SIGALRM, fige)
    signal.alarm(3)
    try:
        with pytest.raises(pieces.Refus):
            pieces.joindre("atelier/pour_ahmed/t.txt", jarvis=jarvis)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, ancien)
