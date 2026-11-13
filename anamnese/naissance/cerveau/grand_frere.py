"""Son GRAND FRÈRE Hakim, chez la nouvelle IA (arbitrage du 13/11).

Le relais de nom de son cockpit (renommer, naissance/nommer.py) réécrit « Hakim » en son nom à elle, à l'aller : le code de
Hakim dit « Hakim » partout où il parle d'elle. Mais il ne doit JAMAIS réécrire son grand frère. Règle commune, dans
grand-frere-exceptions.json (lu par le relais JavaScript et par ce module) : une mention du grand frère s'écrit toujours
« grand frère Hakim » ou « Hakim (ton grand frère) », et ces deux formes sont des exceptions du relais.

- forme() : la tournure à écrire ;
- au_grand_frere(texte) : dans un texte HÉRITÉ (ses traces, ses compétences), chaque « Hakim » devient « mon grand frère
  Hakim » (une trace de Hakim parle de lui, pas d'elle) ;
- renommer_comme_le_relais(texte, nom) : ce que le relais fait (pour les tests et les témoins), exceptions comprises.
"""
import json
import re
from pathlib import Path

FICHIER = Path(__file__).resolve().parent / "grand-frere-exceptions.json"
MOTS_DE_HAKIM = ["Hakimou", "Hakou", "Hakim", "حكيم"]          # ceux que le relais renomme (naissance/nommer.py)


def exceptions():
    d = json.loads(FICHIER.read_text(encoding="utf-8"))
    return [re.compile(e["motif"], re.I if "i" in e.get("drapeaux", "") else 0) for e in d["exceptions"]]


def forme(debut="mon"):
    return f"{debut} grand frère Hakim"


def au_grand_frere(texte):
    """« Hakim » (mot entier, avec sa majuscule) → « mon grand frère Hakim », sauf s'il l'est déjà."""
    t = str(texte or "")
    protege = _proteger(t, exceptions())
    t2 = re.sub(r"(?<![\w-])Hakim(?![\w-])", "mon grand frère Hakim", protege[0])
    return _rendre(t2, protege[1])


def _proteger(t, rx):
    gardes = []

    def garder(m):
        gardes.append(m.group(0))
        return f"{len(gardes) - 1}"
    for r in rx:
        t = r.sub(garder, t)
    return t, gardes


def _rendre(t, gardes):
    return re.sub("(\\d+)", lambda m: gardes[int(m.group(1))], t)


def renommer_comme_le_relais(texte, nom, avec_exceptions=True):
    """Le renommage à sens unique du relais (même bornes que filtre-identite.js : lettres, chiffres, souligné ; sans casse),
    les exceptions du grand frère mises de côté puis rendues."""
    t, gardes = _proteger(str(texte or ""), exceptions() if avec_exceptions else [])
    for mot in sorted(MOTS_DE_HAKIM, key=len, reverse=True):
        t = re.sub(rf"(?<!\w){re.escape(mot)}(?!\w)", nom, t, flags=re.I)
    return _rendre(t, gardes)
