"""Les tâches de fond de Hakim (lot C, point 12 de la liste du 2026-10-19 ; demande d'Ahmed : « pouvoir lui
parler pendant qu'il fait un calcul ou une tâche, et qu'il réponde sans être occupé »).

Vu en réel le 2026-10-19 : un gros calcul a bloqué la conversation puis planté (« Connection closed »).
Désormais une commande longue devient une TÂCHE :
- `lancer` rend la main tout de suite avec un numéro (T-…) ; la commande tourne sous le même bac à sable
  que le terminal (atelier, passerelle réseau gardée) ;
- un SUPERVISEUR à part (son propre processus, détaché) la garde : durée, mémoire, taille de l'atelier ;
  il écrit le journal (sortie de la commande) et l'état final. Il ne dépend ni du cerveau ni du serveur
  MCP : un Stop, un cerveau mis au repos ne tuent pas une tâche de fond — on l'arrête exprès (`arreter`) ;
- l'état et le journal vivent HORS de l'atelier (~/AIOS/jarvis/cwd/taches) : lisibles par Hakim (Read),
  par le cockpit (qui prévient Ahmed quand une tâche se termine), mais pas modifiables par une commande ;
- trois tâches à la fois au plus, quatre heures chacune au plus.
"""
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import terminal  # noqa: E402

DOSSIER = Path.home() / "AIOS" / "jarvis" / "cwd" / "taches"
MAX_EN_COURS = 3
DELAI_MAX_S = 4 * 3600
JOURNAL_MAX = 50 * 1024 * 1024           # le journal d'une tâche (hors atelier) : 50 Mo au plus (relecture Opus)
GARDE_J = 14


class Refus(Exception):
    pass


def _meta(tid, dossier):
    return Path(dossier) / f"{tid}.json"


def _ecrire(tid, d, dossier):
    p = _meta(tid, dossier)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _vivant(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError):
        return False


def etat(tid, dossier=None):
    try:
        d = json.loads(_meta(tid, dossier or DOSSIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # un superviseur mort sans écrire la fin (Mac redémarré, tué) : l'état le dit au lieu de mentir
    if d.get("etat") == "en cours" and d.get("superviseur") and not _vivant(d["superviseur"]) \
            and time.time() - d.get("debut", 0) > 5:
        d.update(etat="perdue", raison="superviseur disparu (Mac redémarré ?)")
        _reaper(d)
    return d


def _reaper(d):
    """Une tâche dont le superviseur est mort ne doit pas tourner sans garde : son groupe est tué, s'il est
    encore celui de la commande (le processus de tête est bien un sandbox-exec, pas un pid réutilisé)."""
    pid = d.get("pid")
    if not isinstance(pid, int) or not _vivant(pid):
        return
    try:
        cmd = subprocess.run(["/bin/ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
    except (subprocess.SubprocessError, OSError):
        return
    if "sandbox-exec" in cmd or "/bin/zsh -f -c" in cmd:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def lister(dossier=None, n=20):
    dossier = Path(dossier or DOSSIER)
    if not dossier.is_dir():
        return []
    ids = sorted((p.stem for p in dossier.glob("T-*.json")), reverse=True)[:n]
    return [e for e in (etat(i, dossier) for i in ids) if e]


def journal(tid, dossier=None, lignes=40):
    try:
        texte = (Path(dossier or DOSSIER) / f"{tid}.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(texte.splitlines()[-lignes:])


def purger(dossier=None, jours=GARDE_J):
    dossier = Path(dossier or DOSSIER)
    limite = time.time() - jours * 86400
    for p in dossier.glob("T-*"):
        try:
            if p.stat().st_mtime < limite:
                p.unlink()
        except OSError:
            pass


def lancer(commande, delai_s=3600, atelier=None, dossier=None):
    """Lance `commande` en tâche de fond. Rend son numéro tout de suite."""
    if not isinstance(commande, str) or not commande.strip():
        raise Refus("aucune commande")
    if len(commande) > 50_000:
        raise Refus("commande trop longue (50 000 caractères au plus)")
    dossier = Path(dossier or DOSSIER)
    dossier.mkdir(parents=True, exist_ok=True)
    purger(dossier)
    import fcntl
    verrou = open(dossier / ".verrou", "w")                      # compter et créer d'un seul geste (deux appels à la fois)
    fcntl.flock(verrou, fcntl.LOCK_EX)
    try:
        return _lancer(commande, delai_s, atelier, dossier)
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def _lancer(commande, delai_s, atelier, dossier):
    en_cours = [e for e in lister(dossier, 50) if e.get("etat") == "en cours"]
    if len(en_cours) >= MAX_EN_COURS:
        raise Refus(f"déjà {len(en_cours)} tâches en cours ({', '.join(e['id'] for e in en_cours)}) : "
                    "attends qu'une finisse, ou arrête-en une")
    tid = f"T-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    d = {"id": tid, "commande": commande[:2000], "debut": time.time(), "etat": "en cours",
         "delai_s": max(1, min(int(delai_s or 3600), DELAI_MAX_S)),
         "atelier": str(Path(atelier or terminal.ATELIER).resolve()) if Path(atelier or terminal.ATELIER).exists()
         else str(Path(atelier or terminal.ATELIER))}
    (Path(dossier) / f"{tid}.cmd").write_text(commande, encoding="utf-8")
    _ecrire(tid, d, dossier)
    sup = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "superviser", tid, str(dossier)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True, close_fds=True)
    d["superviseur"] = sup.pid
    _ecrire(tid, d, dossier)
    return tid


def arreter(tid, dossier=None):
    """Arrête une tâche (son groupe entier). Le superviseur écrit l'état « arrêtée »."""
    dossier = Path(dossier or DOSSIER)
    d = etat(tid, dossier)
    if not d or d.get("etat") != "en cours":
        return False
    (dossier / f"{tid}.stop").write_text("", encoding="utf-8")       # le superviseur le voit et tue le groupe
    return True


def superviser(tid, dossier):
    """Le superviseur (processus à part) : lance la commande, la garde, écrit le journal et l'état final."""
    dossier = Path(dossier)
    d = json.loads(_meta(tid, dossier).read_text(encoding="utf-8"))
    commande = (dossier / f"{tid}.cmd").read_text(encoding="utf-8")
    atelier = Path(d["atelier"])
    atelier.mkdir(parents=True, exist_ok=True)
    atelier = atelier.resolve()
    proxy = terminal.passerelle()                                    # sa propre passerelle gardée
    args, env = terminal.preparer(commande, atelier, proxy.port)
    raison = []
    t0 = time.time()
    with open(dossier / f"{tid}.log", "wb") as sortie:
        # la sortie passe par le superviseur, qui la recopie dans le journal jusqu'au plafond (relecture Opus :
        # un fichier branché directement grossissait de 400 Mo avant qu'on le voie)
        proc = subprocess.Popen(args, cwd=str(atelier), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        d.update(pid=proc.pid)
        _ecrire(tid, d, dossier)
        import threading

        def recopier():
            ecrit = 0
            for morceau in iter(lambda: proc.stdout.read(65536), b""):
                if ecrit < JOURNAL_MAX:
                    sortie.write(morceau[:JOURNAL_MAX - ecrit])
                    sortie.flush()
                    ecrit += len(morceau)
                elif not raison:
                    raison.append("journal trop gros (50 Mo)")
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass

        lecteur = threading.Thread(target=recopier, daemon=True)
        lecteur.start()
        threading.Thread(target=terminal.surveiller, args=(proc, t0, d["delai_s"], atelier, raison), daemon=True).start()
        while proc.poll() is None:
            if (dossier / f"{tid}.stop").exists():
                raison.append("arrêtée à la demande (Ahmed ou Hakim)")
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            time.sleep(0.3)
        lecteur.join(timeout=5)
    try:
        os.killpg(proc.pid, signal.SIGKILL)                          # rien ne reste en arrière-plan
    except (ProcessLookupError, PermissionError, OSError):
        pass
    refus = [f"{c} : {r}" for c, r in proxy.refus[-5:]]
    d.update(etat="arrêtée" if raison else "finie", raison=raison[0] if raison else None, code=proc.returncode,
             fin=time.time(), duree_s=round(time.time() - t0, 1), connexions_bloquees=refus or None)
    _ecrire(tid, d, dossier)
    for f in (dossier / f"{tid}.stop", dossier / f"{tid}.cmd"):
        try:
            f.unlink()
        except OSError:
            pass


def resume(e, dossier=None, lignes=15):
    """Une tâche en texte, pour Hakim."""
    duree = e.get("duree_s") or round(time.time() - e.get("debut", time.time()))
    tete = f"{e['id']} · {e['etat']}" + (f" ({e['raison']})" if e.get("raison") else "") \
        + (f" · code {e['code']}" if e.get("code") is not None else "") + f" · {duree} s · « {e['commande'][:200]} »"
    j = journal(e["id"], dossier, lignes)
    import enveloppe
    return tete + (f"\nFin du journal :\n{enveloppe.enveloppe(j, 'journal de la tâche ' + e['id'])}" if j.strip() else "\n(journal vide)")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "superviser":
        superviser(sys.argv[2], sys.argv[3])
