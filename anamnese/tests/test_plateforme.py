"""La couche de plateforme (13/11, le PC d'un ami d'Ahmed, par WSL2) : le Mac garde son chemin, les profils de modules, le filtre
seccomp « sans fork » du calcul (rejoué par un petit interpréteur BPF : vrai sur x86_64 ET aarch64), les clés en fichier 600,
les mots de Hakim remplacés par le nom qu'ELLE a choisi."""
import json
import os
import stat
import struct
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
import plateforme  # noqa: E402
from plateforme import bac_a_sable  # noqa: E402


# ---- le profil ----

def test_sans_fichier_le_profil_est_complet(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_PROFIL", raising=False)
    p = plateforme.profil_actif(tmp_path / "absent.json")
    assert p["nom"] == "complet"
    assert all(plateforme.module_actif(m, tmp_path / "absent.json") for m in ("studio", "chant", "oreille_vive", "cerveau_local"))
    assert plateforme.outils_eteints(tmp_path / "absent.json") == []


def test_le_pc_sans_gpu_eteint_studio_chant_et_images(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_PROFIL", raising=False)
    f = tmp_path / "profil-modules.json"
    f.write_text(json.dumps({"profil": "pc-sans-gpu", "modules": {"gemma": "eteint", "inconnu": True}}))
    p = plateforme.profil_actif(f)
    assert p["nom"] == "pc-sans-gpu" and p["modules"]["voix"] == "azure" and p["modules"]["gemma"] == "eteint"
    assert "inconnu" not in p["modules"]                       # une retouche ne crée pas de module
    assert not plateforme.module_actif("studio", f) and plateforme.module_actif("atelier", f)
    eteints = plateforme.outils_eteints(f)
    assert {"studio_projet", "chanter", "image_creer"} <= set(eteints) and "clip_creer" not in eteints


def test_un_profil_inconnu_retombe_sur_complet(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_PROFIL", raising=False)
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"profil": "n-importe-quoi"}))
    assert plateforme.profil_actif(f)["nom"] == "complet"


def test_chaque_outil_eteint_existe_dans_le_serveur_mcp():
    texte = (RACINE / "mcp_server.py").read_text(encoding="utf-8")
    outils = json.loads((RACINE / "plateforme" / "profils.json").read_text(encoding="utf-8"))["outils_par_module"]
    for liste in outils.values():
        for o in liste:
            assert f"def {o}(" in texte, o


# ---- le filtre seccomp « sans fork » ----

def _executer_bpf(prog, nr, arch, flags=0):
    """Un interpréteur des seules instructions utilisées (LD|W|ABS, JEQ, JGE, JSET, RET) sur seccomp_data."""
    donnees = struct.pack("<iIQ6Q", nr, arch, 0, flags, 0, 0, 0, 0, 0)
    a, pc = 0, 0
    while True:
        code, jt, jf, k = prog[pc]
        if code == 0x20:
            a = struct.unpack_from("<I", donnees, k)[0]
            pc += 1
        elif code in (0x15, 0x35, 0x45):
            vrai = {0x15: a == k, 0x35: a >= k, 0x45: bool(a & k)}[code]
            pc += 1 + (jt if vrai else jf)
        elif code == 0x06:
            return k
        else:
            raise AssertionError(f"instruction inconnue {code:#x}")


X86, ARM = 0xC000003E, 0xC00000B7
PERMIS, EPERM, ENOSYS = 0x7FFF0000, 0x00050000 | 1, 0x00050000 | 38


@pytest.mark.parametrize("arch,nr,flags,attendu", [
    (X86, 57, 0, EPERM),                 # fork
    (X86, 58, 0, EPERM),                 # vfork
    (X86, 56, 0x11, EPERM),              # clone(SIGCHLD) : un fork
    (X86, 56, 0x4111, EPERM),            # clone(CLONE_VM|CLONE_VFORK) : posix_spawn
    (X86, 56, 0x3D0F00, PERMIS),         # clone d'un fil d'exécution (CLONE_THREAD…)
    (X86, 435, 0, ENOSYS),               # clone3 : la glibc retombe sur clone
    (X86, 0x40000039, 0, EPERM),         # l'ABI x32
    (X86, 0, 0, PERMIS), (X86, 59, 0, PERMIS),   # read, execve
    (ARM, 220, 0x11, EPERM), (ARM, 220, 0x3D0F00, PERMIS), (ARM, 435, 0, ENOSYS), (ARM, 63, 0, PERMIS),
    (0x40000003, 2, 0, PERMIS),          # une autre architecture : rien
])
def test_le_filtre_refuse_fork_et_garde_les_fils(arch, nr, flags, attendu):
    assert _executer_bpf(bac_a_sable.programme_sans_fork(), nr, arch, flags) == attendu


def test_le_filtre_s_assemble_en_instructions_de_8_octets():
    assert len(bac_a_sable._assembler(bac_a_sable.programme_sans_fork())) == 8 * len(bac_a_sable.programme_sans_fork())


# ---- la ligne de commande bwrap (sa forme ; le vrai bac à sable est essayé sous Linux) ----

def test_bwrap_n_expose_que_ce_qui_est_donne(tmp_path):
    lu, ecrit = tmp_path / "lu", tmp_path / "ecrit"
    lu.mkdir()
    (lu / "GitHubKey.txt").write_text("secret")
    args = bac_a_sable.commande(["/bin/true"], lectures=[lu], ecritures=[ecrit], telephone=None, masquer_dans=[lu])
    assert args[:3] == [bac_a_sable.BWRAP, "--unshare-all", "--die-with-parent"]
    assert ["--ro-bind", str(lu), str(lu)] == args[args.index(str(lu)) - 1:args.index(str(lu)) + 2]
    assert ["--bind", str(ecrit), str(ecrit)] == args[args.index(str(ecrit)) - 1:args.index(str(ecrit)) + 2]
    i = args.index(str(lu / "GitHubKey.txt"))
    assert args[i - 2:i] == ["--ro-bind", "/dev/null"]           # recouverte, vide, en lecture seule
    assert args[-2:] == ["--", "/bin/true"]


def test_les_cles_du_telephone_sont_recouvertes_seulement_dans_le_telephone(tmp_path):
    tel = tmp_path / "telephone"
    tel.mkdir()
    (tel / "signature.keystore").write_text("x")
    (tmp_path / "ailleurs.pem").write_text("x")
    m = {str(c) for c, _ in bac_a_sable._masques([tmp_path], telephone=tel)}
    assert str(tel / "signature.keystore") in m and str(tmp_path / "ailleurs.pem") not in m


# ---- les clés (hors Mac : un fichier 600) ----

def test_les_cles_en_fichier_600(tmp_path, monkeypatch):
    from plateforme import cles
    monkeypatch.setattr(cles, "MAC", False)
    monkeypatch.setattr(cles, "DOSSIER", tmp_path / "cles")
    assert cles.lire("service-x") is None
    assert cles.ecrire("service-x", "  abc123  ", compte="cle")
    assert cles.lire("service-x") == "abc123"
    f = cles.chemin("service-x", "cle")
    assert stat.S_IMODE(f.stat().st_mode) == 0o600 and stat.S_IMODE((tmp_path / "cles").stat().st_mode) == 0o700
    assert "abc123" not in cles.commande_lecture("service-x", "cle")


# ---- son nom ----

def test_nommer_remplace_hakim_partout_ou_elle_le_verrait(tmp_path, monkeypatch):
    sys.path.insert(0, str(RACINE / "naissance"))
    import nommer
    jarvis, cockpit = tmp_path / "jarvis", tmp_path / "cockpit"
    (cockpit / "public").mkdir(parents=True)
    (cockpit / "public" / "parler.html").write_text("<title>Parler à Hakim</title> Hakimou, voix-hakim, HakimApp, حكيم")
    monkeypatch.setattr(nommer, "JARVIS", jarvis)
    monkeypatch.setattr(nommer, "COCKPIT", cockpit)
    nommer.main(["--createur", "Karim", "--nom", "Nova"])
    page = (cockpit / "public" / "parler.html").read_text()
    assert page == "<title>Parler à Nova</title> Nova, voix-hakim, HakimApp, Nova"
    d = json.loads((jarvis / "filtre-identite.json").read_text())
    assert ["Hakim", "Nova"] in d["renommer"] and not any(p[0] == "Hakim" for p in d["paires"])
    persona = (jarvis / "persona.md").read_text()
    assert "Tu es Nova" in persona and "Karim" in persona and "{{" not in persona
    assert persona.replace("Hakim (ton grand frère)", "") .count("Hakim") == 0      # seulement son grand frère, nommé comme tel
    assert d["exceptions"] and nommer.remplacer_mots("Tu es Hakim. Mon grand frère Hakim est né avant toi.", nommer.MOTS_DE_HAKIM, "Nova") == \
        "Tu es Nova. Mon grand frère Hakim est né avant toi."
    nommer.main(["--createur", "Karim", "--nom", "Lumi"])       # elle change d'avis : l'ancien nom disparaît aussi
    assert "Nova" not in (cockpit / "public" / "parler.html").read_text()
    with pytest.raises(SystemExit):
        nommer.main(["--createur", "Karim", "--nom", "Hakim"])


def test_sans_nom_elle_le_choisira(tmp_path, monkeypatch):
    sys.path.insert(0, str(RACINE / "naissance"))
    import nommer
    monkeypatch.setattr(nommer, "JARVIS", tmp_path / "jarvis")
    monkeypatch.setattr(nommer, "COCKPIT", tmp_path / "cockpit")
    nommer.main(["--createur", "Karim"])
    persona = (tmp_path / "jarvis" / "persona.md").read_text()
    assert "pas encore de nom" in persona and persona.replace("Hakim (ton grand frère)", "").count("Hakim") == 0
    assert json.loads((tmp_path / "jarvis" / "nom.json").read_text())["nom"] == ""
    assert "'" not in nommer.SANS_NOM and "\"" not in nommer.SANS_NOM            # il entre dans le code des pages


def test_le_mac_garde_son_chemin(tmp_path):
    """Sur le Mac, le terminal part toujours sous sandbox-exec, jamais sous bwrap."""
    if sys.platform != "darwin":
        pytest.skip("sur le Mac seulement")
    assert plateforme.MAC and not plateforme.LINUX
    sys.path.insert(0, str(RACINE / "jarvis"))
    import terminal
    args, env = terminal.preparer("echo x", tmp_path, 9)
    assert "/usr/bin/sandbox-exec" in args and not any("bwrap" in a for a in args)
    assert env["HOME"] == str(tmp_path)


# ---- le corps hors du Mac (/proc) ----

def test_le_corps_lit_proc_stat_et_meminfo(monkeypatch):
    from plateforme import corps
    fichiers = {"/proc/stat": "cpu  10 0 10 80 0 0 0 0\ncpu0 5 1 4 40 2 0 1 0\ncpu1 5 0 5 40 0 0 0 0\nintr 1\n",
                "/proc/meminfo": "MemTotal:       16000000 kB\nMemAvailable:    4000000 kB\nSwapTotal:       2097152 kB\nSwapFree:        1048576 kB\n"}
    monkeypatch.setattr(corps, "_lire", lambda c: fichiers.get(str(c), ""))
    t = corps.ticks()
    assert t == [[5, 5, 42, 1], [5, 5, 40, 0]]                  # [user, système (+irq+vol), repos (+iowait), nice]
    import interoception
    assert [round(x, 3) for x in interoception.charge_coeurs([[0, 0, 0, 0], [0, 0, 0, 0]], t)] == [0.208, 0.2]
    assert corps.memoire_libre_pourcent() == 25.0 and corps.swap_mo() == (2048.0, 1024.0)
