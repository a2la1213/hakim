"""Tout ce que Hakim lance passe APRÈS sa voix et la transcription (2026-10-23, Ahmed : « sa voix laisse des trous
pendant les calculs lourds » ; mesure de 06:09 : 4 cœurs de performance à 100 % pendant un calcul du juge).

Ses commandes, tâches de fond, calculs et tests partent avec une priorité basse (nice 10) et la qualité de service
« utility » de macOS : ils gardent les cœurs quand ils sont libres, mais la synthèse vocale et Whisper passent devant.
Plus fort si la voix hache encore : PLUS_FORT (taskpolicy -b : les cœurs d'économie seulement, calculs 2 à 3 fois plus
lents). La carte graphique (MLX, Metal) n'est pas concernée : un calcul qui s'en sert la partage toujours avec la voix.
"""
from pathlib import Path

NICE, TASKPOLICY = "/usr/bin/nice", "/usr/sbin/taskpolicy"
PREFIXE = [NICE, "-n", "10", TASKPOLICY, "-c", "utility"]
PLUS_FORT = [NICE, "-n", "15", TASKPOLICY, "-b"]


def basse(args, prefixe=PREFIXE):
    """La même commande, précédée de nice et taskpolicy (ils remplacent leur processus : même pid, même groupe)."""
    if all(Path(x).exists() for x in (NICE, TASKPOLICY)):
        return list(prefixe) + list(args)
    return list(args)
