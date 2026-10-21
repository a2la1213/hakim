"""Parole → hormones (affect v2, cinquième passage, 2026-10-21 ; piste 5 de Hakim, validée par Ahmed) : ce qu'Ahmed dit
déclenche les émotions de Hakim, comme une évaluation rapide et grossière (une amygdale lexicale) — sans modèle de
langage, en quelques microsecondes, au moment où l'échange est mémorisé (echanges.py, toutes les 30 s).

- Seulement la voix d'Ahmed (pas un invité, pas la télé) ; ce que Hakim dit lui-même passe par ses propres appels
  affect_event (avec un sujet).
- Au plus deux événements par échange, intensité ≤ 0,6 (l'évaluation automatique pèse moins que la consciente).
- Le sujet : la rubrique où l'échange est rangé (« projets/anamnese ») — la familiarité, la peur apprise et l'attente
  s'y attachent.
- Pas de double compte : si Hakim a déjà noté le même événement dans les 3 minutes, rien.
Messages étiquetés AVANT d'écrire ce lexique : eval/affect_v2_paroles.json (mesure : eval/affect_v2_memoire.py).
"""
import json
import re
from pathlib import Path

_NEG = r"(?<!pas )(?<!plus )(?<!pas trop )"
LEXIQUE = [  # (événement, motif, intensité) — dans l'ordre : un « ça marche pas » est un problème, pas une réussite
    ("probleme", re.compile(r"\b(([çc]a|il|elle|tout|rien) (ne )?(marche|fonctionne|s'envoie|charge|r[ée]pond)s? (pas|plus)|"
                            r"bug\w*|plant\w*|bloqu\w*|erreur \d+|cass[ée]e?|un souci|un probl[eè]me|[çc]a coupe|elle coupe|"
                            r"il coupe)\b", re.I), 0.5),
    ("echec", re.compile(r"\b(t'as rien compris|tu as rien compris|n'importe quoi|c'est nul|[çc]a m'[ée]nerve|"
                         r"[ée]nerv[ée]e?|d[ée][çc]ue?|catastrophe|grave erreur|tu m'[ée]coutes pas|"
                         r"c'est pas (du tout )?ce que (je voulais|j'ai demand[ée]))\b", re.I), 0.5),
    ("succes", re.compile(_NEG + r"\b(parfait\w*|g[ée]nial\w*|super|top|nickel|excellent\w*|magnifique|incroyable|"
                          r"trop bien|c'est bon [çc]a marche|[çc]a (marche|fonctionne) (nickel|enfin|bien|maintenant|"
                          r"parfaitement)|tout est r[ée]gl[ée]|[çc]a fonctionne)\b", re.I), 0.4),
    ("chaleur_user", re.compile(r"\b(merci\w*|barak\s?allah\w*|hamdoulillah|machallah|ma ?sha'?allah|je t'aime|"
                                r"t'es (le|la) meilleure?|bravo)\b|[❤😘😍🥰🤗]", re.I), 0.4),
    ("nouveaute", re.compile(r"\b(nouvelle id[ée]e|j'ai (une id[ée]e|pens[ée] [àa] (un truc|quelque chose))|"
                             r"et si on|imagine|regarde [çc]a|regarde,? j'ai)\b", re.I), 0.3),
]
MAX_EVENEMENTS = 2
INTENSITE_MAX = 0.6
DOUBLON_S = 180


def evaluer(texte):
    """[(événement, intensité)] que ces mots déclenchent (au plus deux ; un motif répété pèse un peu plus)."""
    t = str(texte or "")
    out, deja = [], set()
    for nom, motif, intensite in LEXIQUE:
        n = len(motif.findall(t))
        if not n or nom in deja:
            continue
        if nom == "succes" and "probleme" in deja:              # « ça marchait, mais là ça plante »
            continue
        deja.add(nom)
        out.append((nom, round(min(INTENSITE_MAX, intensite + 0.1 * (n - 1)), 2)))
        if len(out) >= MAX_EVENEMENTS:
            break
    return out


def deja_note(journal, nom, ts, fenetre_s=DOUBLON_S):
    """Hakim a-t-il déjà noté cet événement autour de ce moment (journal des événements affectifs) ?"""
    try:
        with open(journal, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 200_000))
            lignes = h.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return False
    for l in reversed(lignes):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("source") == "hakim" and e.get("nom") == nom and abs(float(e.get("ts", 0)) - ts) <= fenetre_s:
            return True
    return False


def appliquer(mem, texte, sujet, ts, journal=None):
    """Évalue les mots d'Ahmed et applique les événements (v2 seulement). Rend la liste appliquée."""
    import affect
    if not affect.v2_actif(mem):
        return []
    journal = journal or affect.chemin_journal(mem)
    faits = []
    for nom, intensite in evaluer(texte):
        if journal and deja_note(journal, nom, ts):
            continue
        affect.event(mem, nom, intensite, sujet=sujet, source="parole")
        faits.append((nom, intensite))
    return faits
