"""Module exemple — montre le chargement dynamique. Sert aussi de gabarit."""
import time

from modules.registry import Module


class Clock(Module):
    name = "clock"
    description = "Donne la date et l'heure actuelles."

    def run(self, arg, context):
        return "🕒 " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
