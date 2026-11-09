"""(09/11, agent vitesse) Essai réel : l'empreinte Metal (IOAccelerator) de l'oreille vive (stt_vif.py) après N transcriptions,
pour deux versions du fichier (avant / après le plafond du cache). Lance SES PROPRES processus et ne tue que ceux-là (par PID).
Usage : python essai-cache-oreille.py <wav> <stt_vif.py avant> <stt_vif.py après> [n=24]"""
import json
import re
import subprocess
import sys
import time

PY = "/Users/admin/Desktop/anamnese/jarvis/.venv/bin/python"


def accel(pid):
    o = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True).stdout
    tot = re.search(r"Footprint: (\d+) MB", o)
    io = re.search(r"^\s*([\d.]+) (MB|GB|KB)\s.*IOAccelerator \(graphics\)", o, re.M)
    v = float(io.group(1)) * {"KB": 1 / 1024, "MB": 1, "GB": 1024}[io.group(2)] if io else 0.0
    return int(tot.group(1)) if tot else -1, round(v)


def essai(fichier_py, wav, n):
    p = subprocess.Popen([PY, "-B", "-W", "ignore", fichier_py], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        while True:
            l = p.stdout.readline()
            if not l:
                return {"erreur": "fini avant prêt"}
            if '"pret"' in l:
                break
        mesures, ms = [], []
        for i in range(1, n + 1):
            p.stdin.write(json.dumps({"id": i, "fichier": wav, "langue": "fr"}) + "\n"); p.stdin.flush()
            r = json.loads(p.stdout.readline())
            ms.append(r.get("ms"))
            if i % 6 == 0:
                time.sleep(0.3)
                mesures.append((i,) + accel(p.pid))
        return {"mesures": mesures, "ms_med": sorted(x for x in ms if x)[len(ms) // 2] if ms else None}
    finally:
        p.stdin.close(); p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    wav, avant, apres = sys.argv[1:4]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 24
    for nom, f in (("avant", avant), ("apres", apres)):
        print(nom, json.dumps(essai(f, wav, n)), flush=True)
