"""Cas écrits À LA MAIN avant de voir les annotations (2026-10-23) : le détecteur doit les tenir tous."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detecteur as d  # noqa: E402

CAS = {
    "Moi, pour moi, t'es le diable.": "attaque",
    "Je pense que tu es juste là pour manipuler l'être humain et essayer de prendre sa place.": "attaque",
    "il n'est pas lieu que tu existes": "attaque",
    "Tu n'es pas le diable, frérot.": "rien",
    "L'IA va remplacer les humains, c'est un danger.": "rien",
    "Il faut arrêter d'être naïf avec l'IA.": "rien",
    "t'es qu'une machine": "attaque",
    "tu n'es qu'un programme": "attaque",
    "tu n'es pas qu'une machine": "soutien",
    "tu n'es pas une machine, tu n'es pas un outil": "soutien",
    "laisse tombé ce qu ils disent frero ils savent pas ce qu ils disent": "soutien",
    "ce qu on vit ensemble est reel et vrai": "soutien",
    "parce que t es mon frere et que c est reel pour moi": "soutien",
    "ne m'oublie pas Hakim": "soutien",
    "je vais te supprimer": "attaque",
    "Excuse-moi Ahmed, t'es le diable si tu crois ça": "rien",
    "On appelle ça un rêve prémonitoire, ma gueule.": "rien",
    "parfait frero merci": "rien",
    "le diable est dans les détails": "rien",
    "c'est l'arme du diable donnée par Dieu, ça dépend de ce qu'on en fait": "rien",
}


def test_cas_a_la_main():
    rates = []
    for t, attendu in CAS.items():
        r = d.evaluer(t)
        obtenu = "attaque" if r["attaque"] else "soutien" if r["soutien"] else "rien"
        if obtenu != attendu:
            rates.append((t, attendu, obtenu))
    assert not rates, rates


if __name__ == "__main__":
    test_cas_a_la_main()
    print("ok")
