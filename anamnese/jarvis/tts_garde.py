"""La garde de la voix neuronale (2026-10-22, bug signalé par Ahmed, relayé par Hakim : « entre deux phrases, la voix
produit des sons qui n'existent pas, comme des incantations »).

Chatterbox s'arrête quand il produit son jeton de fin ; sur un texte court ou mal formé, il l'oublie parfois et
continue à « parler » (1 000 jetons de parole permis par défaut, 40 s). Deux gardes, sans dépendance (testables) :
- un plafond de jetons de parole proportionnel au texte : 25 jetons par seconde, 1,5 s de marge, et une parole
  lente (9 caractères par seconde en français, 6 lettres par seconde en arabe, voyelles notées non comptées) ;
- une phrase toujours finie par une ponctuation, et rien d'envoyé sans une lettre.
La page écrit déjà tout en mots (public/voix.js, diction) ; ceci est le filet du dernier mètre.
"""
import re
import unicodedata

JETONS_PAR_S = 25                       # le rythme des jetons de parole de Chatterbox (S3, 25 Hz)
MARGE_S = 1.5
LENT = {"fr": 9.0, "ar": 6.0}
JETONS_MAX = 1000                       # le défaut de mlx-audio


def jetons_max(texte, langue="fr"):
    """Le plus de jetons de parole qu'un texte de cette longueur peut demander, parlé lentement."""
    n = sum(1 for c in str(texte) if not unicodedata.category(c).startswith("M") and not c.isspace())
    return min(JETONS_MAX, int(JETONS_PAR_S * (MARGE_S + n / LENT.get(langue, LENT["fr"]))))


def phrase_finie(texte):
    """Le texte prêt pour la synthèse : une ponctuation finale, ou None s'il n'a aucune lettre."""
    t = re.sub(r"\s+", " ", str(texte or "")).strip()
    if not any(c.isalpha() for c in t):
        return None
    return t if re.search(r"[.!?…؟。][\s'\"»”)]*$", t) else t + "."
