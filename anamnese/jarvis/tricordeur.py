"""Le Tricordeur de Hakim (30/10, accord d'Ahmed : « qu'il puisse coder son Tricordeur lui-même », « ses propres modules »).

Sa copie de travail est dans son atelier (atelier/tricordeur, git ; la version d'Ahmed étiquetée « origine », une autre
copie intouchable hors de l'atelier). Il compile depuis son terminal (./construire.sh, APK non signé). Ici, hors de son
bac à sable :
  - signer(apk) : avec SA clé à lui (une clé neuve, jamais celle d'Ahmed), rangée hors de l'atelier, son mot de passe dans le
    trousseau ; Hakim ne la voit jamais (il l'a demandé). Aucun programme de son atelier ne tourne ici : les outils d'Android
    viennent du SDK du Mac (son atelier pourrait les avoir changés, et ce code tient le mot de passe) ;
  - livrer(apk, note) : un APK signé posé dans Documents/Hakim/Tricordeur du téléphone, avec sa note ; Ahmed installe.
Chaque geste est noté (tricordeur-journal.jsonl), qu'Ahmed suit dans le cockpit. Fermé aux chantiers de Hakim.
"""
import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import fichiers

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
SERVICE = "hakim-tricordeur-signature"
SDK_BT = Path.home() / "Library" / "Android" / "sdk" / "build-tools" / "35.0.0"
JDK = Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home")
APK_MAX = 300 * 1024 * 1024


class Refus(Exception):
    pass


def _atelier():
    return JARVIS / "cwd" / "atelier"


def _noter(o):
    f = JARVIS / "tricordeur-journal.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), **o}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)


def _apk(rel):
    """Un .apk de son atelier, sans lien, au plus APK_MAX."""
    a = _atelier()
    p = a / str(rel or "").strip().lstrip("/")
    reel = Path(os.path.realpath(p))
    if p.suffix != ".apk" or os.path.islink(p) or a.resolve() not in reel.parents or not reel.is_file():
        raise Refus("un fichier .apk de ton atelier (ex. « tricordeur/build/tricordeur-hakim.apk »), pas un lien")
    if reel.stat().st_size > APK_MAX:
        raise Refus("APK trop lourd")
    return reel


def _mot_de_passe(creer=False):
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", SERVICE, "-a", "hakim", "-w"],
                       capture_output=True, text=True, timeout=10)
    k = r.stdout.strip() if r.returncode == 0 else ""
    if not k and creer:
        k = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        r = subprocess.run(["/usr/bin/security", "-i"], capture_output=True, text=True, timeout=10,
                           input=f'add-generic-password -s {SERVICE} -a hakim -l "Clé du Tricordeur de Hakim" -w {k}\n')
        if r.returncode != 0:
            raise Refus("trousseau indisponible")
    if not k:
        raise Refus("pas encore de clé")
    return k


def _cle(env):
    d = JARVIS / "tricordeur-signature"
    d.mkdir(mode=0o700, exist_ok=True)
    ks = d / "hakim-tricordeur.keystore"
    if not ks.exists():
        r = subprocess.run([str(JDK / "bin" / "keytool"), "-genkeypair", "-keystore", str(ks), "-alias", "hakim", "-keyalg", "RSA",
                            "-keysize", "3072", "-validity", "10000", "-storepass:env", "MDP", "-keypass:env", "MDP",
                            "-dname", "CN=Tricordeur de Hakim"], capture_output=True, text=True, timeout=60, env=env)
        if r.returncode != 0:
            raise Refus("la clé n'a pas pu être créée")
        os.chmod(ks, 0o600)
    return ks


def signer(rel, executer=subprocess.run):
    src = _apk(rel)
    env = {**os.environ, "MDP": _mot_de_passe(creer=True), "JAVA_HOME": str(JDK), "PATH": f"{JDK / 'bin'}:/usr/bin:/bin"}
    ks = _cle(env)
    sortie = src.with_name(src.stem + "-signe.apk")
    (JARVIS / "tricordeur-signature").mkdir(mode=0o700, exist_ok=True)
    tmp = Path(JARVIS / "tricordeur-signature" / f"{os.getpid()}-{int(time.time())}.apk")
    try:
        r = executer([str(SDK_BT / "apksigner"), "sign", "--v4-signing-enabled", "false", "--ks", str(ks), "--ks-pass", "env:MDP", "--key-pass", "env:MDP",
                      "--out", str(tmp), str(src)], capture_output=True, text=True, timeout=300, env=env)
        if r.returncode != 0:
            raise Refus("signature refusée : " + (r.stderr or r.stdout or "?").strip().splitlines()[-1][:200])
        fichiers.ecrire_sans_lien(sortie, tmp.read_bytes(), _atelier())
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    _noter({"action": "signature", "apk": str(sortie.relative_to(_atelier().resolve())) if _atelier().resolve() in sortie.parents else str(sortie),
            "taille": sortie.stat().st_size})
    return sortie


def livrer(rel, note=""):
    import telephone
    src = _apk(rel)
    v = subprocess.run([str(SDK_BT / "apksigner"), "verify", "--print-certs", str(src)], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "JAVA_HOME": str(JDK), "PATH": f"{JDK / 'bin'}:/usr/bin:/bin"})
    if v.returncode != 0 or "Tricordeur de Hakim" not in v.stdout:
        raise Refus("cet APK n'est pas signé de ta clé : tricordeur_signer d'abord")
    nom = f"Tricordeur/{time.strftime('%Y%m%d-%H%M')}-{src.stem}.apk"
    telephone.ecrire(f"Hakim/{nom}", depuis_atelier=str(src.relative_to(_atelier().resolve())), note="APK de son Tricordeur")
    if str(note or "").strip():
        telephone.ecrire(f"Hakim/{nom[:-4]}.txt", texte=f"Ce qui change (Hakim) :\n{str(note).strip()}\n", note="note de l'APK")
    _noter({"action": "livraison", "apk": str(src.name), "vers": f"Documents/Hakim/{nom}", "note": str(note or "")[:500]})
    return f"Documents/Hakim/{nom}"


def journal(n=40):
    try:
        lignes = (JARVIS / "tricordeur-journal.jsonl").read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    return [json.loads(l) for l in lignes if l.strip()]
