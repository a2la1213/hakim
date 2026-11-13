"""L'aspiration du PC du papa (naissance/cerveau/aspiration.py) : lecture SEULE (le profil est identique, octet pour octet,
avant et après ; rien n'y est créé), les dossiers Windows par défaut et leurs doubles OneDrive, l'extraction (docx, pptx,
xlsx, pdf, WhatsApp, courriel, carnet, EXIF des photos, étiquettes des morceaux), l'index par le sens, la reprise."""
import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import aspiration      # noqa: E402
import extraction      # noqa: E402
import faux_profil     # noqa: E402


def faux_embed(texte):
    v = [0.0] * 128
    for mot in str(texte).lower().split():
        mot = mot.strip(".,;:!?«»[]")
        if len(mot) >= 4:
            v[hash(mot) % 128] += 1.0
    return v


@pytest.fixture
def profil(tmp_path):
    return faux_profil.creer(tmp_path / "c")


def _empreinte(racine):
    out = {}
    for d, dossiers, fichiers in os.walk(racine, followlinks=False):
        for n in dossiers + fichiers:
            p = Path(d) / n
            st = p.lstat()
            out[str(p)] = (st.st_mtime_ns, st.st_size,
                           hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink() else None)
    return out


def test_lecture_seule_le_profil_ne_change_pas_d_un_octet(profil, tmp_path):
    avant = _empreinte(profil["profil"])
    aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    assert _empreinte(profil["profil"]) == avant


def test_temoin_de_lecture_seule(profil, tmp_path):
    """Le témoin : un seul octet écrit dans le profil fait échouer la comparaison."""
    avant = _empreinte(profil["profil"])
    (profil["profil"] / "Documents" / "notes.txt").write_text("x", encoding="utf-8")
    assert _empreinte(profil["profil"]) != avant


def test_rien_n_est_ouvert_en_ecriture(profil, tmp_path, monkeypatch):
    import builtins
    vrai = builtins.open
    racine = str(profil["profil"])

    def garde(f, mode="r", *a, **k):
        if str(f).startswith(racine) and any(c in mode for c in "wax+"):
            raise AssertionError(f"écriture dans le profil : {f}")
        return vrai(f, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", garde)
    r = aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    assert r["indexes"] > 10


def test_les_dossiers_par_defaut_et_onedrive(profil):
    etiquettes = [e for e, _ in aspiration.dossiers_par_defaut(profil["profil"])]
    assert etiquettes == ["Documents", "Bureau", "OneDrive/Bureau", "Images", "Musique", "Vidéos"]
    assert aspiration.profils_windows(profil["profil"].parent) == [profil["profil"]]


def test_ce_que_l_inventaire_sait(profil, tmp_path):
    r = aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    par = {x["affiche"]: x for x in aspiration.lignes(tmp_path / "s")}
    col = par["Documents/Collection Printemps 2025.docx"]
    assert col["auteur"] == "Karim Benali" and col["date"] == "2024-02-10" and "Lin du Sud" in col["extrait"]
    assert col["vecteur"] is not None
    assert "Manteaux en laine bouillie" in par["Documents/Lookbook AH24.pptx"]["extrait"]
    assert "Robe Lin Sable" in par["Documents/Commandes boutique 2024.xlsx"]["extrait"]
    wa = par["Documents/Discussions/WhatsApp Chat with Inès Benali.txt"]
    assert wa["genre"] == "discussion" and wa["meta"]["participants"] == {"Karim Benali": 4, "Inès Benali": 2}
    assert par["Documents/Mails/Re tissus.eml"]["genre"] == "courriel"
    photo = par["Images/IMG_20230614_182205.jpg"]
    assert photo["date"] == "2023-06-14" and photo["meta"]["gps"] == [46.5197, 6.6323]
    assert photo["meta"]["appareil"] == "samsung SM-S938B"
    assert par["Musique/Aya Nakamura - Djadja.mp3"]["meta"]["artiste"] == "Aya Nakamura"
    assert "OneDrive/Bureau/rappel.txt" in par
    # ce que Windows met partout, les liens, AppData : jamais
    assert not any("desktop.ini" in a or "~$" in a or "AppData" in a or "Raccourci" in a for a in par)
    noms = {n for n, _s, _c in aspiration.noms_releves(tmp_path / "s")}
    assert {"Karim Benali", "Inès Benali", "Sarah Haddad"} <= noms
    assert r["complet"] and r["total_exclus"] == 6


@pytest.mark.skipif(not extraction.PDFTOTEXT, reason="pdftotext absent (le repli approximatif est testé à part)")
def test_le_pdf_par_pdftotext(profil, tmp_path):
    aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    par = {x["affiche"]: x for x in aspiration.lignes(tmp_path / "s")}
    assert "Coutures anglaises" in par["Documents/Atelier/Fiche technique robe.pdf"]["extrait"]


def test_le_pdf_sans_pdftotext(profil, monkeypatch):
    monkeypatch.setattr(extraction, "PDFTOTEXT", None)
    monkeypatch.setattr(extraction, "PDFINFO", None)
    ex = extraction.extraire(profil["profil"] / "Documents" / "Atelier" / "Fiche technique robe.pdf")
    assert "Coutures anglaises" in ex["texte"]


def test_l_index_par_le_sens(profil, tmp_path):
    aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    res = aspiration.chercher(tmp_path / "s", "manteaux en laine bouillie", embed=faux_embed, n=3)
    assert res[0]["affiche"] == "Documents/Lookbook AH24.pptx"


def test_reprenable_et_incremental(profil, tmp_path):
    rac = aspiration.dossiers_par_defaut(profil["profil"])
    r1 = aspiration.aspirer(rac, tmp_path / "s", embed=faux_embed, limite=5)
    assert not r1["complet"] and r1["indexes"] == 5
    r2 = aspiration.aspirer(rac, tmp_path / "s", embed=faux_embed)
    assert r2["complet"] and r2["inchanges"] == 5
    r3 = aspiration.aspirer(rac, tmp_path / "s", embed=faux_embed)
    assert r3["indexes"] == 0 and r3["total_inventaire"] == r2["total_inventaire"]
    # un fichier disparu (le papa l'a supprimé) sort de l'inventaire à la passe complète suivante
    os.remove(profil["profil"] / "Desktop" / "idées collection été.txt")
    aspiration.aspirer(rac, tmp_path / "s", embed=faux_embed)
    assert "Bureau/idées collection été.txt" not in {x["affiche"] for x in aspiration.lignes(tmp_path / "s")}


def test_whatsapp_android_et_iphone():
    android = "12/03/2024 14:22 - Karim: Salut !\nsuite du message\n12/03/2024 14:25 - Inès: Oui"
    iphone = "‎[12.03.24, 14:22:05] Karim: Salut !\n[12.03.24, 14:25:10] Inès: Oui"
    assert extraction.lire_whatsapp(android) == [("12/03/2024", "Karim", "Salut !\nsuite du message"), ("12/03/2024", "Inès", "Oui")]
    assert [a for _d, a, _m in extraction.lire_whatsapp(iphone)] == ["Karim", "Inès"]


def test_un_texte_windows_en_cp1252_et_en_utf16(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes("Défilé à l'atelier".encode("cp1252"))
    b = tmp_path / "b.txt"
    b.write_bytes("Défilé à l'atelier".encode("utf-16"))
    assert extraction.extraire(a)["texte"] == extraction.extraire(b)["texte"] == "Défilé à l'atelier"


def test_une_bombe_zip_ne_gonfle_rien(tmp_path, monkeypatch):
    import zipfile
    monkeypatch.setattr(extraction, "OFFICE_MEMBRE_MAX", 1000)
    f = tmp_path / "bombe.docx"
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:t>" + "a" * 50_000 + "</w:t>")
    assert extraction.extraire(f)["texte"] == ""


def test_son_outil_de_recherche_par_le_sens_lit_l_inventaire(profil, tmp_path, monkeypatch):
    """L'inventaire a les colonnes de l'index des fichiers de Hakim (index_fichiers.py) : chez elle, l'outil fichiers_par_sens
    peut chercher dans ce que l'aspiration a lu, sans autre index."""
    import index_fichiers
    aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed)
    monkeypatch.setattr(index_fichiers, "_embed", faux_embed)
    res = index_fichiers.chercher("manteaux en laine bouillie", base=tmp_path / "s" / "inventaire.db", n=3)
    assert res[0]["chemin"].endswith("Lookbook AH24.pptx")


def test_onedrive_en_ligne_seulement_n_est_jamais_lu(profil, tmp_path, monkeypatch):
    """Un fichier OneDrive « en ligne seulement » n'est pas sur le disque : le lire depuis WSL le téléchargerait. Windows le
    signale (une question à PowerShell, au début) ; il n'est jamais ouvert."""
    rappel = profil["profil"] / "OneDrive" / "Bureau" / "rappel.txt"
    vus = []

    class R:
        stdout = "C:\\Users\\kbenali\\OneDrive\\Bureau\\rappel.txt\r\n"
    def executer(cmd, **k):
        vus.append(cmd)
        return R()
    assert aspiration.windows_vers_wsl("C:\\Users\\k\\OneDrive\\a b.docx") == "/mnt/c/Users/k/OneDrive/a b.docx"
    assert aspiration.wsl_vers_windows("/mnt/c/Users/k/OneDrive") == "C:\\Users\\k\\OneDrive"
    nuage = aspiration.en_ligne_seulement([("OneDrive/Bureau", Path("/mnt/c/Users/kbenali/OneDrive/Bureau")),
                                           ("Documents", Path("/mnt/c/Users/kbenali/Documents"))], executer=executer)
    assert nuage == {"/mnt/c/Users/kbenali/OneDrive/Bureau/rappel.txt"} and len(vus) == 1      # Documents : pas OneDrive
    assert "RecallOnDataAccess" in vus[0][-1] or "0x400000" in vus[0][-1]
    lus = []
    vrai = aspiration.extraction.extraire
    monkeypatch.setattr(aspiration.extraction, "extraire", lambda p, genre=None: lus.append(Path(p)) or vrai(p, genre))
    r = aspiration.aspirer(aspiration.dossiers_par_defaut(profil["profil"]), tmp_path / "s", embed=faux_embed, nuage={str(rappel)})
    assert r["en_ligne_seulement"] == 1 and rappel not in lus
    assert "OneDrive/Bureau/rappel.txt" not in {x["affiche"] for x in aspiration.lignes(tmp_path / "s")}
