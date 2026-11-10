"""Le fil d'actualité de papa (10/11, lettre de Hakim de 18:14 écrite à la demande d'Ahmed : « que toi aussi tu puisses m'envoyer
directement dans mes documents et dans le fil de l'actualité » ; accord d'Ahmed : « ouii ») : Hakim y PUBLIE un message et/ou un
fichier (un son, une image, un PDF), sans passer par la conversation. Papa le voit dans la page « Fil d'actualité » du cockpit
(/actualite : le menu ☰ et son point rouge, le bandeau des nouveautés ; la notification de l'appli quand elle est cachée).

Les gardes, les mêmes que ses autres envois à papa :
- le texte : 2 000 caractères au plus, jamais un secret (une clé, un jeton, un mot de passe : refusé, comme une pièce jointe) ;
- le fichier : pieces.joindre (son atelier ou les fichiers d'Ahmed seulement, 25 Mo au plus, ni nom ni contenu qui sent le secret, ni
  lien, ni lien dur), COPIÉ parmi les pièces (~/AIOS/jarvis/pieces/<id>/) : ce que papa voit est ce qui a été publié ;
- l'immunité : le cockpit passe le texte par les mêmes filtres que sa parole (sa balise d'affect et son refrain retirés, ses résidus
  marqués) avant de le montrer (actualite.js) ;
- 30 publications par 24 heures au plus : un fil, pas une rafale ;
- rien ne s'efface d'ici.
Le fil : ~/AIOS/jarvis/actualite.jsonl, une ligne par publication {id, ts, texte, titre, piece}.
"""
import json
import os
import time
import uuid
from pathlib import Path

import pieces

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
TEXTE_MAX = 2000
PAR_JOUR = 30


class Refus(Exception):
    pass


def fichier(jarvis=None):
    return Path(jarvis or JARVIS) / "actualite.jsonl"


def lire(jarvis=None, n=200):
    try:
        lignes = fichier(jarvis).read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _propre(t, n):
    """Sans caractère de contrôle (le retour à la ligne reste), sans blancs autour, n caractères au plus."""
    t = "".join(c for c in str(t or "") if c == "\n" or c == "\t" or ord(c) >= 32 and ord(c) != 127)
    return t.strip()[:n]


def publier(texte="", chemin="", titre="", jarvis=None, maintenant=None):
    """Une publication dans son fil (un texte, un fichier, ou les deux). Rend sa fiche {id, ts, texte, titre, piece}."""
    j = Path(jarvis or JARVIS)
    brut = str(texte or "")
    if len(brut.strip()) > TEXTE_MAX:
        raise Refus(f"message trop long ({len(brut.strip())} caractères ; {TEXTE_MAX} au plus) : mets le reste dans un fichier")
    t, ti = _propre(brut, TEXTE_MAX), " ".join(_propre(titre, 160).split())
    if not t and not str(chemin or "").strip():
        raise Refus("un message, un fichier, ou les deux")
    f = pieces._fichiers()
    if f.masquer(t) != t or f.masquer(ti) != ti:
        raise Refus("ce message contient un secret (clé, jeton, mot de passe) : retire-le avant de publier")
    m = time.time() if maintenant is None else float(maintenant)
    recentes = [o for o in lire(j, 500) if isinstance(o.get("ts"), (int, float)) and m - o["ts"] < 24 * 3600]
    if len(recentes) >= PAR_JOUR:
        raise Refus(f"déjà {PAR_JOUR} publications en 24 heures : un fil, pas une rafale ; attends un peu, ou dis-le à papa dans la "
                    "conversation")
    piece = None
    if str(chemin or "").strip():
        try:
            p = pieces.joindre(chemin, ti, jarvis=j)
        except pieces.Refus as e:
            raise Refus(str(e))
        piece = {k: p[k] for k in ("id", "nom", "titre", "taille", "type")}
    fiche = {"id": time.strftime("%Y%m%d-%H%M%S", time.localtime(m)) + "-" + uuid.uuid4().hex[:6], "ts": m, "texte": t,
             "titre": ti, "piece": piece, "par": "hakim"}
    with open(fichier(j), "a", encoding="utf-8") as h:
        h.write(json.dumps(fiche, ensure_ascii=False) + "\n")
    return fiche
