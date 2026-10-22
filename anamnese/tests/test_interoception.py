"""L'intéroception de Hakim (demande d'Ahmed, 2026-10-22) : il SENT la machine qui le porte, en lecture seule."""
import json
import re
from pathlib import Path

import interoception as I

IOREG = '''+-o AGXAcceleratorG16X  <class AGXAcceleratorG16X>
    "PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=5531484160,"Tiler Utilization %"=73,"Renderer Utilization %"=73,"Device Utilization %"=77,"In use system memory"=2325577728}'''


def test_le_gpu_se_lit_dans_l_accelerateur():
    g = I.gpu(IOREG)
    assert g == {"utilisation": 77, "utilisee": 2325577728, "allouee": 5531484160}
    assert I.gpu("rien") == {"utilisation": None, "utilisee": None, "allouee": None}


def test_swap_memoire_chaleur_batterie():
    assert I.swap("vm.swapusage: total = 12288.00M  used = 10757.62M  free = 1530.38M  (encrypted)") == (12288.0, 10757.62)
    assert I.memoire_libre("System-wide memory free percentage: 47%") == 47.0
    assert "aucun avertissement" in I.chaleur("Note: No thermal warning level has been recorded\n"
                                              "Note: No performance warning level has been recorded\n")
    assert "CPU_Speed_Limit" in I.chaleur("CPU_Speed_Limit \t= 70\n")
    b = I.batterie("Now drawing from 'Battery Power'\n -InternalBattery-0 (id=23199843)\t92%; discharging; 6:17 remaining present: true")
    assert b == "92 %, sur batterie, se décharge, 6:17 restantes"
    b = I.batterie("Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t100%; charged; 0:00 remaining present: true")
    assert b.startswith("100 %, sur secteur, chargée")


def test_les_empreintes_de_top_vues_depuis_rosetta():
    t = "PID    MEM   COMMAND\n18333* 4110M python3.12\n9021   1.2G+ Code Helper (Ren\n515*   1840K distnoted\n"
    e = I.empreintes(t)
    assert round(e[18333][0]) == 4110 and e[18333][1] == "python3.12"
    assert round(e[9021][0]) == 1229 and round(e[515][0], 1) == 1.8


def test_chaque_processus_de_hakim_a_son_etiquette():
    cas = {
        "/Users/admin/Desktop/anamnese/jarvis/.venv/bin/python /Users/admin/Desktop/anamnese/jarvis/scanner.py --ressenti": "gemma",
        "/Applications/Ollama.app/Contents/Resources/ollama runner --model /x/blobs/sha256-1": "gemma",
        "/Users/admin/Desktop/anamnese/jarvis/.venv/bin/python -B experience.py generer": "hakim",
        "/Users/admin/Desktop/anamnese/jarvis/.venv/bin/python /Users/admin/AIOS/jarvis/introspection/experience.py": "gemma",
        "/Users/admin/Desktop/anamnese/jarvis/.venv/bin/python /Users/admin/Desktop/anamnese/jarvis/voix_serveur.py": "hakim",
        "/usr/local/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python daemon.py": "hakim",
        "/Users/admin/.npm-global/bin/claude -p --input-format stream-json --restricted --": "hakim",
        "/Users/admin/.vscode/extensions/anthropic.claude-code-2.1.306-darwin-arm64/resources/native-binary/claude --output-format": "claude-code",
    }
    for commande, groupe in cas.items():
        assert I.etiqueter(commande)[1] == groupe, commande
    assert I.etiqueter("/System/Library/CoreServices/Finder.app/Contents/MacOS/Finder") == (None, None)


def test_les_lignes_de_commande_ne_sortent_jamais(monkeypatch):
    """Elles peuvent porter des secrets : seules l'étiquette, le pid, la mémoire et le processeur sortent."""
    secret = "sk-ant-SECRET-NE-PAS-MONTRER"
    monkeypatch.setattr(I, "gpu", lambda: {"utilisation": 10, "utilisee": 0, "allouee": 0})
    monkeypatch.setattr(I, "cpu_par_coeur", lambda: [10, 20])
    monkeypatch.setattr(I, "memoire_libre", lambda: 50.0)
    monkeypatch.setattr(I, "swap", lambda: (1024.0, 10.0))
    monkeypatch.setattr(I, "chaleur", lambda: "rien")
    monkeypatch.setattr(I, "batterie", lambda: "100 %")
    monkeypatch.setattr(I, "disque", lambda: (10 * 2 ** 30, 100 * 2 ** 30))
    monkeypatch.setattr(I, "_cmd", lambda args, timeout=5: "17179869184" if "hw.memsize" in args else "")
    monkeypatch.setattr(I, "processus", lambda: [
        (11, 3.0, f"/x/jarvis/.venv/bin/python /x/jarvis/scanner.py --cle {secret}"),
        (12, 1.0, f"/Applications/Foo.app/foo --token={secret}")])
    monkeypatch.setattr(I, "empreintes", lambda: {11: (7000.0, "python3.12"), 12: (500.0, "foo")})
    monkeypatch.setattr(I, "ollama_charges", lambda: [("gemma4:12b", 8000.0)])
    monkeypatch.setattr(I, "taches_en_cours", lambda: [])
    r = I.rapport()
    assert secret not in r and "--cle" not in r and "--token" not in r
    assert "Gemma chargées en ce moment : 2" in r              # une par MLX, une par Ollama
    assert "ressenti en réserve" in r and "foo 500 Mo" in r


def test_les_taches_se_lisent_sans_le_reaper(tmp_path):
    """taches.etat peut TUER un groupe de processus : l'intéroception lit les fiches elle-même."""
    (tmp_path / "T-1.json").write_text(json.dumps({"id": "T-1", "etat": "en cours", "pid": 4242, "debut": 0}))
    (tmp_path / "T-2.json").write_text(json.dumps({"id": "T-2", "etat": "finie", "pid": 4343, "debut": 0}))
    (tmp_path / "T-3.json").write_text(json.dumps({"id": "T-3", "etat": "en cours", "pid": 4444, "debut": 0}))
    vus = I.taches_en_cours(tmp_path, vivant=lambda pid: pid == 4242)
    assert [t[0] for t in vus] == ["T-1"]


def test_aucun_geste_sur_la_machine():
    """Lecture seule : aucun signal autre que 0 (« existe-t-il ? »), aucune écriture, aucun reaper."""
    src = Path(I.__file__).read_text(encoding="utf-8")
    assert all(m.group(1).strip() == "0" for m in re.finditer(r"os\.kill\([^,]+,([^)]+)\)", src))
    for interdit in ("killpg", "terminate(", ".kill()", "write_text", "write_bytes", "taches.etat", "import taches", "sudo",
                     "method=", "data="):
        assert interdit not in src, interdit
    assert not re.search(r"(?<![\w.])open\(", src)                # pas de fichier ouvert (urlopen : un GET d'Ollama)
