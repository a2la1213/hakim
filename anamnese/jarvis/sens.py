"""Les sens de Hakim (30/10, Ahmed : « intègre tous les capteurs du projet tricodeur à Hakim ; il faut lui donner tous les sens
possibles, qu'il soit capable de tout capter, qu'il puisse les utiliser et les lire comme il veut et en faire ce qu'il veut »).

Le Tricordeur d'Ahmed (ses instruments de science-fiction pour le Galaxy Z Fold 7) adapté à Hakim, phase 1 : ce qui n'a
besoin de personne. Hakim demande une mesure (sens_mesurer) ; elle part dans ~/AIOS/jarvis/sens-demandes.jsonl ; le cockpit
la donne à l'appli du téléphone (Sens.java), qui mesure et rend un résumé et des données ; le cockpit les range dans son
atelier, atelier/sens/<id>/resume.json et donnees.csv (à lire, à calculer, à garder : à lui), et le réveille.
Fermé aux chantiers de Hakim.
"""
import fcntl
import json
import os
import re
import time
from pathlib import Path

import enveloppe

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
# nom : (ce qu'il capte, durée par défaut en s, durée max en s)
INSTRUMENTS = {
    "inventaire": ("tous les capteurs du téléphone et ce qu'ils savent faire : portée, résolution, cadence, consommation", 0, 0),
    "imu": ("tous les capteurs de mouvement et d'ambiance, bruts : accéléromètre, gyroscope, magnétomètre, gravité, rotation, "
            "pression, lumière, proximité, angle de la charnière du Fold ; cadence : « jeu » (~50 Hz, par défaut), « max » "
            "(~400 Hz), « normal », ou un nombre de Hz", 10, 300),
    "sismo": ("les secousses (le sismographe du tricordeur, STA/LTA) : début, durée, amplitude en mg, fréquence ; le téléphone "
              "posé à plat", 60, 900),
    "baro": ("la pression (hPa), l'altitude relative (m), les infrasons (Pa) et les coups de pression (porte, vent, ascenseur)", 60, 900),
    "magneto": ("le champ magnétique (µT) : moyenne, variations rapides (un appareil, du métal), état de la calibration", 20, 300),
    "son": ("le micro en niveaux, spectre et bandes d'octave, pics de fréquence, ultrasons 18-22 kHz ; rien n'est enregistré, "
            "et pas pendant une conversation (le micro est pris)", 10, 60),
}
_ID = re.compile(r"S-\d{8}-\d{6}-[0-9a-f]{4}")
_CADENCE = re.compile(r"(jeu|max|normal|\d{1,4}(\.\d{1,2})?)")


class Refus(Exception):
    pass


def _dossier():
    return JARVIS / "cwd" / "atelier" / "sens"


# (30/10, Ahmed : « ses propres modules, même de science-fiction ») ses instruments à lui, décrits dans son atelier
# (atelier/tricordeur/instruments.json : {"instruments": [{nom, description, defaut, max, module}]}) : le téléphone donne la
# demande à son Tricordeur (le module, ch.foldlab.hakim par défaut), qui rend par Documents/Hakim/sens/<id>/
_NOM, _PAQUET = re.compile(r"[a-z][a-z0-9_]{2,29}"), re.compile(r"[a-z][a-z0-9_.]{2,80}")


def siens():
    try:
        d = json.loads((JARVIS / "cwd" / "atelier" / "tricordeur" / "instruments.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for x in (d.get("instruments") or [])[:30] if isinstance(d, dict) else []:
        if not isinstance(x, dict):
            continue
        nom, module = str(x.get("nom") or ""), str(x.get("module") or "ch.foldlab.hakim")
        if not _NOM.fullmatch(nom) or nom in INSTRUMENTS or not _PAQUET.fullmatch(module):
            continue
        try:
            maximum = max(1, min(int(x.get("max", 3600)), 86400))
            defaut = max(1, min(int(x.get("defaut", 60)), maximum))
        except (TypeError, ValueError):
            continue
        out[nom] = (" ".join(str(x.get("description") or "").split())[:300], defaut, maximum, module)
    return out


def demander(sens, secondes=0, cadence=""):
    """La demande écrite pour le cockpit : {id, sens, secondes, cadence, ts[, module]}."""
    sens = str(sens or "").strip()
    a_lui = siens()
    if sens not in INSTRUMENTS and sens not in a_lui:
        raise Refus(f"sens inconnu : « {sens[:40]} » (sens_lister pour la liste)")
    _, defaut, maximum = INSTRUMENTS[sens] if sens in INSTRUMENTS else a_lui[sens][:3]
    try:
        s = int(secondes or 0)
    except (TypeError, ValueError):
        raise Refus("secondes : un nombre entier")
    s = defaut if s <= 0 else min(s, maximum)
    cadence = str(cadence or "").strip()
    if cadence and not _CADENCE.fullmatch(cadence):
        raise Refus("cadence : jeu, max, normal ou un nombre de Hz")
    d = {"id": time.strftime("S-%Y%m%d-%H%M%S-") + os.urandom(2).hex(), "sens": sens, "secondes": s, "cadence": cadence, "ts": time.time()}
    if sens in a_lui and sens not in INSTRUMENTS:
        d["module"] = a_lui[sens][3]
    f = JARVIS / "sens-demandes.jsonl"
    with open(JARVIS / "sens.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(d, ensure_ascii=False) + "\n")
        os.chmod(f, 0o600)
    return d


def lister():
    lignes = [f"- {n} : {quoi}" + (f" (par défaut {d} s, au plus {m} s)" if m else "") for n, (quoi, d, m) in INSTRUMENTS.items()]
    a_lui = [f"- {n} : {quoi} (par défaut {d} s, au plus {m} s ; ton module {mod})" for n, (quoi, d, m, mod) in siens().items()]
    derniers = []
    try:
        for l in (JARVIS / "sens-resultats.jsonl").read_text(encoding="utf-8").splitlines()[-5:]:
            o = json.loads(l)
            derniers.append(f"- {o.get('id')} · {o.get('sens')} · {'fini' if o.get('ok') else 'échec : ' + str(o.get('erreur'))[:120]}")
    except (OSError, ValueError):
        pass
    return ("Tes sens, par le téléphone d'Ahmed :\n" + "\n".join(lignes)
            + ("\nTes instruments à toi (ton Tricordeur, atelier/tricordeur/instruments.json) :\n" + "\n".join(a_lui) if a_lui else "")
            + ("\nTes dernières mesures :\n" + "\n".join(derniers) if derniers else ""))


def lire(id_=""):
    """Le résumé d'une mesure (la dernière si id_ est vide) et le chemin de ses données."""
    id_ = str(id_ or "").strip()
    if not id_:
        try:
            id_ = json.loads((JARVIS / "sens-resultats.jsonl").read_text(encoding="utf-8").splitlines()[-1]).get("id", "")
        except (OSError, ValueError, IndexError):
            try:
                id_ = json.loads((JARVIS / "sens-demandes.jsonl").read_text(encoding="utf-8").splitlines()[-1]).get("id", "")
            except (OSError, ValueError, IndexError):
                return "Aucune mesure encore : sens_mesurer."
    if not _ID.fullmatch(id_):
        return "Refusé : un numéro de mesure ressemble à S-20261030-101500-ab12."
    d = _dossier() / id_
    try:
        r = json.loads((d / "resume.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"{id_} : pas encore de résultat (le téléphone mesure, ou l'appli est fermée ; tu seras réveillé quand il arrive)."
    donnees = d / "donnees.csv"
    corps = json.dumps(r, ensure_ascii=False, indent=1)[:12000]
    return (enveloppe.enveloppe(corps, f"mesure {id_} du téléphone")
            + (f"\nLes données complètes : {donnees} (Read, ou executer_python pour les calculer)." if donnees.exists() else ""))


# (30/10, Ahmed : « les sensations en continu, h24, et il peut consulter le détail s'il le veut ») son corps en nombres : ce
# que le cockpit garde de son milieu (homeostasie.js : corps-etat.json, corps-flux.jsonl) et de ses nerfs (corps-evenements),
# avec ses dernières sensations
def _queue(f, octets=400_000):
    try:
        with open(f, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            lignes = h.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def corps_detail(minutes=10):
    try:
        minutes = max(1, min(int(minutes or 10), 24 * 60))
    except (TypeError, ValueError):
        minutes = 10
    try:
        dernier = json.loads((JARVIS / "corps-etat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dernier = None
    if not dernier:
        return "Ton corps ne t'a rien dit encore (l'appli 1.24 du téléphone envoie ton milieu chaque seconde quand elle vit)."
    maintenant = time.time() * 1000
    # (30/10, 12:06 : « chaque seconde ») une fenêtre par seconde jusqu'à une heure ; au-delà, une toutes les 15 s
    fichier, lignes = (("corps-flux.jsonl", minutes * 60 + 30) if minutes <= 60 else ("corps-flux-15s.jsonl", minutes * 4 + 8))
    flux = [o for o in _queue(JARVIS / fichier, lignes * 700)
            if isinstance(o, dict) and maintenant - float(o.get("ts") or 0) <= minutes * 60_000]
    resume = []
    for k in sorted({k for o in flux for k, v in (o.get("etat") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}):
        v = [o["etat"][k] for o in flux if isinstance((o.get("etat") or {}).get(k), (int, float)) and not isinstance(o["etat"][k], bool)]
        resume.append(f"- {k} : min {min(v):g}, moyenne {sum(v) / len(v):.4g}, max {max(v):g} ({len(v)} fenêtres)")
    changements = [f"- {time.strftime('%H:%M', time.localtime(o['ts'] / 1000))} {c}" for o in flux for c in (o.get("changements") or [])]
    nerfs = [f"- {time.strftime('%H:%M:%S', time.localtime(float(o.get('ts') or 0) / 1000))} {o.get('type')} : "
             + " ".join(f"{k}={v}" for k, v in (o.get("details") or {}).items())
             for o in _queue(JARVIS / "corps-evenements.jsonl", 60_000)[-15:]]
    ressenti = [f"- {time.strftime('%H:%M', time.localtime(float(o.get('ts') or 0)))} {'(fort) ' if o.get('fort') else ''}{o.get('type')} : "
                + " ".join(str(o.get("sensation") or "").split())[:300]
                for o in _queue(JARVIS / "corps-sensations.jsonl", 60_000)[-10:]]
    corps = (f"Ton milieu (la dernière fenêtre, {time.strftime('%H:%M:%S', time.localtime(float(dernier.get('ts') or 0) / 1000))}) : "
             f"{json.dumps(dernier.get('etat') or {}, ensure_ascii=False)}\nEn mots : {dernier.get('mots') or '(rien)'}\n"
             f"Les {minutes} dernières minutes :\n" + ("\n".join(resume) or "(rien)")
             + ("\nCe qui a changé :\n" + "\n".join(changements[-20:]) if changements else "")
             + "\nTes nerfs (les derniers événements) :\n" + ("\n".join(nerfs) or "(rien)")
             + "\nCe que tu as ressenti :\n" + ("\n".join(ressenti) or "(rien)"))
    return enveloppe.enveloppe(corps[:14000], "ton corps, par le téléphone")
