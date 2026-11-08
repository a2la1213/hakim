"""(30/10, 16:01, Ahmed via Hakim : « que tout nouveau fichier écrit par l'appli Tricordeur, même lancé à la main par papa, me
réveille avec son résumé (voxels, champ min/max, anomalies, objets) et les chemins des images ») le résumé d'une mesure du
Tricordeur d'Ahmed, depuis ses fichiers."""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import tricordeur_papa as T  # noqa: E402


def _ply(f, n):
    f.write_bytes(f"ply\nformat binary_little_endian 1.0\nelement vertex {n}\nproperty float x\nend_header\n".encode() + struct.pack("<f", 0.0) * n)


def test_un_scan_3d_resume(tmp_path):
    b = "scan3d_20261030_155726_155833"
    (tmp_path / f"{b}.csv").write_text("x_m,y_m,z_m,B_mean_uT,n,B_min_uT,B_max_uT\n0,0,0,41.2,64,39.3,43.2\n1,0,0,55.0,10,50.1,60.5\n0,1,0,30.0,5,28,31\n")
    (tmp_path / f"{b}_anomalies.csv").write_text("x_m,y_m,z_m,delta_uT,t_s,B_uT\n0.5,0.5,0,12,3,70\n")
    _ply(tmp_path / f"{b}_scene.ply", 2000)
    _ply(tmp_path / f"{b}_objets.ply", 30)
    (tmp_path / f"{b}_carte.png").write_bytes(b"\x89PNG")
    r = T.resumer(tmp_path, b)
    assert r["instrument"] == "scan3d" and r["nom"] == "scan 3D (champ magnétique de la pièce)"
    assert r["resume"]["voxels"] == 3 and r["resume"]["anomalies"] == 1
    assert r["resume"]["B_mean_uT"] == {"min": 30.0, "max": 55.0, "moyenne": 42.07}
    assert r["resume"]["points"] == {"scene": 2000, "objets": 30}
    assert r["images"] == [str(tmp_path / f"{b}_carte.png")]
    assert T.groupe("scan3d_20261030_155726_155833_carte.png") == b and T.groupe("cosmos_20260925_081221.csv") == "cosmos_20260925_081221"


def test_un_autre_instrument_ses_colonnes(tmp_path):
    (tmp_path / "cosmos_20261030_220000.csv").write_text("t_s,x,y,energie\n1,2,3,40\n5,6,7,80\n")
    r = T.resumer(tmp_path, "cosmos_20261030_220000")
    assert r["instrument"] == "cosmos" and r["resume"]["lignes"] == 2
    assert r["resume"]["colonnes"]["energie"] == {"min": 40.0, "max": 80.0, "moyenne": 60.0}
    assert r["resume"]["duree_s"] == 4.0
    json.dumps(r)
