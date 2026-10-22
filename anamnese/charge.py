"""La machine est-elle trop chargée pour réfléchir ? (demande d'Ahmed, 2026-10-03)

Le daemon charge un modèle d'environ 8 Go pour réfléchir et rêver. Le Mac a planté trois
fois en deux nuits quand ce modèle s'ajoutait aux gros calculs d'autres sessions. Avant
chaque réflexion ou rêve, on regarde la charge du processeur et la mémoire libre ; deux
seuils évitent d'hésiter sans arrêt (pause au-dessus du haut, reprise sous le bas).
Seuils : choix de Claude (les plantages sont venus à des charges de 60 à 200 sur 10 cœurs)."""
import os
import re
import subprocess

CHARGE_PAUSE = 2.0        # charge par cœur au-dessus de laquelle on se met en pause
CHARGE_REPRISE = 1.0      # charge par cœur sous laquelle on reprend
MEMOIRE_PAUSE = 20.0      # % de mémoire libre sous lequel on se met en pause
MEMOIRE_REPRISE = 30.0    # % de mémoire libre au-dessus duquel on reprend

# Robot IA (~/Desktop/robot-ia, T4a, décision 8 d'Ahmed, 2026-10-06) : tant que le robot vit, il fait battre ce
# fichier toutes les 10 s ; Anamnèse lui laisse Gemma. Un signal sans battement depuis une minute ne compte plus.
ROBOT_SIGNAL = os.path.expanduser("~/.robot-ia/gemma-occupe.json")
ROBOT_PEREMPTION_S = 60


def analyser_memoire_libre(texte):
    m = re.search(r"free percentage:\s*(\d+(?:\.\d+)?)%", texte or "")
    return float(m.group(1)) if m else None


def lire():
    """(charge par cœur, % de mémoire libre) ; None pour une mesure impossible."""
    try:
        charge = os.getloadavg()[0] / (os.cpu_count() or 1)
    except OSError:
        charge = None
    try:
        r = subprocess.run(["memory_pressure"], capture_output=True, text=True, errors="replace",
                           timeout=10, check=False)
        memoire = analyser_memoire_libre(r.stdout)
    except (OSError, subprocess.SubprocessError):
        memoire = None
    return charge, memoire


class GardeCharge:
    def __init__(self):
        self.en_pause = False

    def permet(self, charge, memoire_libre):
        """Vrai si l'on peut réfléchir ; une mesure absente garde l'état courant."""
        if self.en_pause:
            reprise = (charge is None or charge < CHARGE_REPRISE) and \
                      (memoire_libre is None or memoire_libre > MEMOIRE_REPRISE)
            if reprise and (charge is not None or memoire_libre is not None):
                self.en_pause = False
        else:
            if (charge is not None and charge > CHARGE_PAUSE) or \
                    (memoire_libre is not None and memoire_libre < MEMOIRE_PAUSE):
                self.en_pause = True
        return not self.en_pause


# (2026-10-22) un calcul lourd qui tient la machine (le duel du subconscient de la nuit) fait battre ce fichier ; le
# démon lui laisse alors Gemma et la mémoire, comme au robot. Un signal sans battement depuis une minute ne compte plus.
CALCUL_LOURD = os.path.expanduser("~/AIOS/jarvis/calcul-lourd.json")


def calcul_lourd_actif(chemin=None, maintenant=None):
    """(rend le libellé du calcul, ou None)"""
    import json
    import time
    try:
        with open(chemin or CALCUL_LOURD) as f:
            d = json.load(f)
        age = (maintenant or time.time)() - float(d["t_ms"]) / 1000
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return str(d.get("quoi") or "un calcul lourd") if 0 <= age <= ROBOT_PEREMPTION_S else None


def robot_actif(chemin=ROBOT_SIGNAL, maintenant=None):
    """Le robot pense-t-il en ce moment (son signal bat) ? Un signal absent, abîmé ou périmé : non."""
    import json
    import time
    try:
        with open(chemin) as f:
            d = json.load(f)
        t = float(d["t_ms"]) / 1000
    except (OSError, ValueError, KeyError, TypeError):
        return False
    age = (maintenant or time.time)() - t
    return 0 <= age <= ROBOT_PEREMPTION_S
