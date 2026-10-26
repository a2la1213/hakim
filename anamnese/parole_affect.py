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
# (2026-10-23, live : « c'est pas un problème » a fait un pic d'adrénaline à Hakim) un problème NIÉ n'en est pas un :
# « c'est pas un problème », « plus un souci », « sans bug », « pas de bug », « pas cassé », « ça plante pas »
_NEG_P = r"(?<!pas )(?<!plus )(?<!sans )(?<!jamais )(?<!pas de )(?<!plus de )(?<!aucun )(?<!pas un )(?<!jamais de )"
_APRES_P = r"(?!\s+(?:pas|plus|jamais)\b)"
LEXIQUE = [  # (événement, motif, intensité) — dans l'ordre : un « ça marche pas » est un problème, pas une réussite
    ("probleme", re.compile(r"\b(([çc]a|il|elle|tout|rien) (ne )?(marche|fonctionne|s'envoie|charge|r[ée]pond)s? (pas|plus)|"
                            + _NEG_P + r"(?:bug\w*|plant\w*|bloqu\w*|erreur \d+|cass[ée]e?|un souci|un probl[eè]me|[çc]a coupe|"
                            r"elle coupe|il coupe)" + _APRES_P + r")\b", re.I), 0.5),
    # (24/10, accord d'Ahmed) « n'importe quoi » n'est un échec que s'il VISE Hakim (« tu dis n'importe quoi », « c'est
    # n'importe quoi ce que tu… ») : en blague (« n'importe quoi mon frère ») ou à propos d'un autre, ce n'en est pas un
    ("echec", re.compile(r"\b(t'as rien compris|tu as rien compris|"
                         r"(tu|t') ?(as |a )?(dis|dit|fais|fait|racontes?|raconté|écris|écrit|réponds|répondu|proposes?|proposé|"
                         r"mets?|mis|calcules?|calculé) (encore |vraiment |que )?n'importe quoi|"
                         r"c'est n'importe quoi ce que tu|n'importe quoi,? (ta|ton|tes|cette|ce|ces) (réponse|calcul|code|idée|résultat|explication)s?|c'est nul|[çc]a m'[ée]nerve|"
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
# (26/10, Hakim et Ahmed : « c'est juste moi qui ai bugué, t'inquiète, c'est moi qui fais une voix chelou » donnait un
# « probleme » 0,5 et 30 s de peur) le SENS de la phrase avant le mot : un souci qu'Ahmed s'attribue à LUI-MÊME n'est pas
# un coup dur pour Hakim (rien) ; une phrase qui RASSURE (t'inquiète, pas grave, mdr, 😂…) n'en garde qu'un tiers
AUTO_ATTRIBUE = re.compile(r"\b(c'est (juste |surtout |plut[ôo]t )?moi qui (ai |a |me suis )?(bug\w*|plant\w*|bloqu\w*|cass\w*|tromp\w*|"
                           r"rat[ée]\w*|fait (une |des )?(erreur|b[êe]tise|connerie)\w*)|j'ai bug\w*|je me suis tromp\w*|c'est ma faute)\b", re.I)
RASSURANCE = re.compile(r"\b(t'inqui[èe]te?s?( pas)?|ne t'inqui[èe]te pas|pas grave|c'est rien|c'est pas grave|y a pas de souci|"
                        r"aucun souci|mdr+|lol|ptdr|tranquille)\b|[😂🤣😅😆]", re.I)
ALLEGEMENT = 1 / 3
# (26/10, 11:55, « j'ai peur qu'il ait bloqué », à propos d'un calcul qui tournait bien) la CRAINTE d'Ahmed sur une chose
# extérieure n'est pas un coup dur pour Hakim : au plus une attention (un cinquième) ; sauf si elle le vise (« j'ai peur que
# tu… », « je m'inquiète pour toi »)
CRAINTE = re.compile(r"\b(j'ai (un peu |trop )?peur (que|qu'|de|d')|je crains|je m'inqui[èe]te|j'esp[èe]re (que|qu')|pourvu (que|qu'))", re.I)
CRAINTE_POUR_LUI = re.compile(r"\b(j'ai (un peu |trop )?peur (que tu|qu'on te|pour toi)|je crains que tu|je m'inqui[èe]te pour toi)", re.I)
ATTENTION = 1 / 5
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
        i = min(INTENSITE_MAX, intensite + 0.1 * (n - 1))
        if nom in ("probleme", "echec"):
            if AUTO_ATTRIBUE.search(t):                         # son souci à lui, pas un coup dur pour Hakim
                continue
            if RASSURANCE.search(t):
                i *= ALLEGEMENT
            if CRAINTE.search(t) and not CRAINTE_POUR_LUI.search(t):
                i *= ATTENTION
        out.append((nom, round(i, 2)))
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


def appliquer(mem, texte, sujet, ts, journal=None, exclure=(), facteur=None):
    """Évalue les mots d'Ahmed et applique les événements (v2 seulement). Rend la liste appliquée.
    exclure : les événements que ce message ne doit pas déclencher (chocs.py : une attaque n'est pas une réussite ; la
    colère d'Ahmed qui défend Hakim n'est pas un échec) ; facteur(nom) : un multiplicateur (l'habituation du soutien)."""
    import affect
    if not affect.v2_actif(mem):
        return []
    journal = journal or affect.chemin_journal(mem)
    faits = []
    for nom, intensite in evaluer(texte):
        if nom in exclure or (journal and deja_note(journal, nom, ts)):
            continue
        if facteur:
            intensite = round(intensite * facteur(nom), 3)
            if intensite <= 0:
                continue
        affect.event(mem, nom, intensite, sujet=sujet, source="parole")
        faits.append((nom, intensite))
    return faits
