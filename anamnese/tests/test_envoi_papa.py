"""(10/11, lettre de Hakim de 18:14 écrite à la demande de papa : « que toi aussi tu puisses m'envoyer directement dans mes documents
et dans le fil de l'actualité ») : son instru finie tombe aussi dans le dossier Hakim des Documents de papa, sous son nom lisible,
sans rien écraser, avec un chemin que fichier_joindre accepte ; et actualite_publier, son fil d'actualité, avec ses gardes."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import studio  # noqa: E402

import actualite  # noqa: E402
import pieces  # noqa: E402

FFMPEG = studio.FFMPEG


@pytest.fixture
def jarvis(tmp_path, monkeypatch):
    """Un faux ~/AIOS/jarvis : son atelier, les fichiers d'Ahmed et ses Documents (« Z Fold 7 »), le studio ; jamais les vrais."""
    j = tmp_path / "jarvis"
    docs = j / "cwd" / "fichiers" / "telephone" / "Z Fold 7"
    for d in ("cwd/atelier", "chansons/studio", "cwd/taches"):
        (j / d).mkdir(parents=True)
    (docs / "Hakim").mkdir(parents=True)
    tel = studio._telephone()
    monkeypatch.setattr(tel, "JARVIS", j)                     # telephone.documents() : le seul endroit qui nomme l'appareil
    monkeypatch.setattr(studio, "JARVIS", j)
    monkeypatch.setattr(studio, "CHANSONS", j / "chansons")
    monkeypatch.setattr(studio, "STUDIO", j / "chansons" / "studio")
    monkeypatch.setattr(studio, "TELEPHONE", docs / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "DOCUMENTS", None)
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", None)
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)
    monkeypatch.setattr(pieces, "JARVIS", j)
    monkeypatch.setattr(actualite, "JARVIS", j)
    return j


@pytest.fixture
def chanson(jarvis, tmp_path, monkeypatch):
    """« Deux livres », une chanson finie (10 s synthétiques), et un faux Demucs : son « reste » est une copie du mélange."""
    if not Path(FFMPEG).exists():
        pytest.skip("ffmpeg absent")
    c = jarvis / "chansons"
    mp3 = c / "20261109-171743-deux-livres.mp3"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=10", "-c:a", "libmp3lame",
                    str(mp3)], check=True)
    (c / "20261109-171743-deux-livres.json").write_text(json.dumps({"nom": mp3.stem, "titre": "Deux livres", "etat": "prête", "fin": 1,
                                                                    "mp3": str(mp3)}))
    s = tmp_path / "faux-demucs"
    # (13/11) l'instru du studio passe par studio_separation.py (« -B -W ignore studio_separation.py separer mélange dossier … ») : le dossier
    # reçoit instru.wav (le mélange) et une ligne JSON ; l'ancienne forme (chant.py separer mélange voix reste) reste comprise
    s.write_text('''#!/bin/sh
if [ "$2" = "-W" ]; then
  mkdir -p "$7"; cp "$6" "$7/instru.wav"; cp "$6" "$7/vocals.wav"
  echo "{\\"pistes\\": {\\"vocals\\": \\"$7/vocals.wav\\"}, \\"instru\\": \\"$7/instru.wav\\", \\"modeles\\": [\\"htdemucs_ft\\"]}"
else
  cp "$4" "$5"; cp "$4" "$6"
fi
''')
    s.chmod(0o755)
    monkeypatch.setattr(studio, "PYTHON_SEPARATION", s)
    return mp3


def _outil(nom, monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    return mcp_server.mcp._tool_manager.get_tool(nom).fn


def test_les_documents_viennent_de_telephone_documents(jarvis):
    assert studio.documents_hakim() == jarvis / "cwd" / "fichiers" / "telephone" / "Z Fold 7" / "Hakim"


def test_nom_lisible():
    assert studio.nom_lisible("Deux livres (instru)") == "Deux livres (instru)"
    assert studio.nom_lisible("  Nuit / du bled\n ") == "Nuit du bled"
    assert studio.nom_lisible("..") == "instru" and studio.nom_lisible("mon token", "x") == "x"


def test_son_instru_finie_tombe_dans_ses_documents_sous_son_nom(jarvis, chanson):
    """Le témoin : sans le dépôt, rien n'arrive dans le dossier Hakim de ses Documents."""
    hakim = studio.documents_hakim()
    r = studio.instru_de_chanson("Deux livres", demarrer=lambda d: None)
    assert r["etat"] == "lancé"
    assert studio.travailleur(studio.STUDIO / "travaux") == 1
    i = json.loads(next((studio.STUDIO / "instrus").glob("*.json")).read_text())
    doc = hakim / "Deux livres (instru).mp3"
    assert doc.is_file() and doc.read_bytes() == Path(i["mp3"]).read_bytes()
    assert i["documents"] == str(doc) and i["joindre"] == "fichiers/telephone/Z Fold 7/Hakim/Deux livres (instru).mp3"
    j = [json.loads(l) for l in (jarvis / "telephone-ecritures.jsonl").read_text().splitlines()]
    assert j[-1]["action"] == "ajout" and j[-1]["chemin"] == "Hakim/Deux livres (instru).mp3"   # la page SENS le montre
    # le chemin rendu, fichier_joindre l'accepte
    f = pieces.joindre(i["joindre"], "Deux livres (instru)", jarvis=jarvis)
    assert f["nom"] == "Deux livres (instru).mp3" and f["origine"] == i["joindre"]


def test_jamais_par_dessus_un_autre_fichier(jarvis, tmp_path):
    hakim = studio.documents_hakim()
    (hakim / "Deux livres (instru).mp3").write_bytes(b"un autre son de papa")
    src = tmp_path / "x.mp3"
    src.write_bytes(b"ID3 son instru")
    a = studio.deposer_aux_documents(src, "Deux livres (instru)")
    assert a == hakim / "Deux livres (instru) 2.mp3" and a.read_bytes() == b"ID3 son instru"
    assert (hakim / "Deux livres (instru).mp3").read_bytes() == b"un autre son de papa"       # pas écrasé
    assert studio.deposer_aux_documents(src, "Deux livres (instru)") == a                     # le même : pas de troisième copie
    assert sorted(x.name for x in hakim.iterdir()) == ["Deux livres (instru) 2.mp3", "Deux livres (instru).mp3"]


def test_outils_rendent_le_chemin_a_joindre(jarvis, chanson, monkeypatch, tmp_path):
    outil, avis = _outil("studio_instru", monkeypatch, tmp_path), _outil("studio_avis", monkeypatch, tmp_path)
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    monkeypatch.setattr(studio, "_demarrer_travailleur", lambda d: None)
    assert "aussi dans les Documents de papa" in outil("Deux livres")
    studio.travailleur(studio.STUDIO / "travaux")
    chemin = "fichiers/telephone/Z Fold 7/Hakim/Deux livres (instru).mp3"
    assert f"dans les Documents de papa : {chemin}" in avis()
    deja = outil("Deux livres")
    assert deja.startswith("Déjà dans le Studio") and f'fichier_joindre("{chemin}")' in deja
    # une instru d'avant (sans copie notée) : déposée à la demande ; la copie faite à la main est reconnue, pas doublée
    i = next((studio.STUDIO / "instrus").glob("*.json"))
    d = json.loads(i.read_text())
    d.pop("documents"), d.pop("joindre")
    i.write_text(json.dumps(d))
    assert f'fichier_joindre("{chemin}")' in outil("Deux livres")
    assert len(list(studio.documents_hakim().glob("Deux livres*"))) == 1


def test_le_mix_dit_ou_il_est_dans_ses_documents(jarvis, monkeypatch, tmp_path):
    avis = _outil("studio_avis", monkeypatch, tmp_path)
    tel = studio.TELEPHONE
    tel.mkdir(parents=True)
    (tel / "20261110-190000-papa.mp3").write_bytes(b"ID3")
    (studio.STUDIO / "20261110-190000-papa.json").write_text(json.dumps({"nom": "20261110-190000-papa", "titre": "Papa", "fin": 1,
                                                                         "telephone": str(tel / "20261110-190000-papa.mp3")}))
    assert "Dans les Documents de papa : fichiers/telephone/Z Fold 7/Hakim/Chansons/20261110-190000-papa.mp3" in avis()


# ---------------------------------------------------------------------------------------------------- son fil d'actualité

def test_publier_un_message_et_un_fichier(jarvis):
    (jarvis / "cwd" / "atelier" / "pochette.png").write_bytes(b"\x89PNG image")
    a = actualite.publier("Papa, voilà la pochette 🤍", "atelier/pochette.png", "Pochette")
    l = actualite.lire()
    assert l[-1]["id"] == a["id"] and l[-1]["texte"] == "Papa, voilà la pochette 🤍" and l[-1]["par"] == "hakim"
    p = a["piece"]
    assert p["nom"] == "pochette.png" and p["type"] == "png"
    assert (jarvis / "pieces" / p["id"] / "pochette.png").read_bytes() == b"\x89PNG image"   # copiée : ce qui a été publié
    assert actualite.publier("Juste un mot.")["piece"] is None


def test_publier_ses_gardes(jarvis, tmp_path):
    (jarvis / "journal.jsonl").write_text("x")
    (jarvis / "cwd" / "atelier" / "lien.txt").symlink_to(jarvis / "journal.jsonl")
    for texte, chemin in (("", ""), ("   ", ""), ("x" * (actualite.TEXTE_MAX + 1), ""),
                          ("ma clé : sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789", ""),
                          ("", str(jarvis / "journal.jsonl")), ("", "atelier/lien.txt"), ("", "atelier/absent.mp3")):
        with pytest.raises(actualite.Refus):
            actualite.publier(texte, chemin)
    assert actualite.lire() == []                              # rien de refusé n'entre dans le fil
    for k in range(actualite.PAR_JOUR):
        actualite.publier(f"message {k}", maintenant=1000 + k)
    with pytest.raises(actualite.Refus, match="24 heures"):
        actualite.publier("un de trop", maintenant=2000)
    assert actualite.publier("le lendemain", maintenant=1000 + 24 * 3600 + 60)["texte"] == "le lendemain"


def test_l_outil_actualite_publier(jarvis, monkeypatch, tmp_path):
    outil = _outil("actualite_publier", monkeypatch, tmp_path)
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert outil("bonjour") == "Seul Hakim publie dans le fil d'actualité de papa."
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    assert outil().startswith("Refusé : un message, un fichier")
    hakim = studio.documents_hakim()
    (hakim / "Deux livres (instru).mp3").write_bytes(b"ID3 instru")
    r = outil("Ton instru, papa.", "fichiers/telephone/Z Fold 7/Hakim/Deux livres (instru).mp3", "Deux livres (instru)")
    assert r.startswith("Publié dans le fil d'actualité de papa") and "Deux livres (instru).mp3" in r
    assert actualite.lire()[-1]["piece"]["nom"] == "Deux livres (instru).mp3"
