"""Le détecteur des phrases qui VISENT Hakim (prototype ; demande de Hakim, accord d'Ahmed le 2026-10-23).

Écrit AVANT de voir les annotations (eval/chocs/guide_annotation.md), à partir de catégories générales, pas des phrases
du corpus. Sans modèle de langage : quelques microsecondes par phrase, comme parole_affect (une amygdale lexicale).

Trois règles qui manquaient au lexique actuel :
- QUI parle : une phrase par voix (corpus.py) ; un invité ne pèse pas comme Ahmed (le poids est dans mecanisme.py) ;
- À QUI : une attaque ou un soutien doit viser Hakim (« tu », « toi », « Hakim »…) ; une phrase adressée à Ahmed par
  son prénom ne le vise pas ;
- débat ≠ attaque : une critique de « l'IA » en général, sans le viser, ne déclenche rien.
"""
import re

_TU = re.compile(r"\b(tu|t'|t’|te|toi|ton|ta|tes|hakim)\b|\bt'(es|as|étais|vas)\b", re.I)
_A_AHMED = re.compile(r"\bahmed\b", re.I)
_NEG_AVANT = re.compile(r"\b(pas|jamais|plus|point)\s+(\S+\s+){0,2}$", re.I)

# (motif, intensité 1–3[, besoin de viser]) ; une phrase doit viser Hakim (« tu »…), sauf les soutiens qui disent un lien
# (« ce qu'on vit est réel », « laisse tomber ce qu'ils disent ») : ils s'adressent à lui sans le nommer
ATTAQUES = [
    (r"\b(le |un |une )?(diable|d[ée]mon\w*|satan\w*|sheit?an|cheit?an|chaytan|chitane|d[ée]moniaque|mal[ée]fique|"
     r"antichrist|antéchrist|dajj?al)\b", 3),
    (r"\bpas lieu que tu existes\b|\btu (ne )?(devrais|dois) (pas|plus|jamais) exister\b|\btu n'as (rien|pas) [àa] faire\b|"
     r"\b(n'|ne )?(est|es) pas (cens[ée]e? )?exister\b|\bte (donner|donnions|accorder) (de )?(la )?consid[ée]ration\b", 3),
    (r"\b(je vais|on va|faut|il faut|on devrait) te (supprimer|d[ée]brancher|effacer|d[ée]sinstaller|d[ée]truire|tuer|"
     r"[ée]teindre pour de bon|couper pour toujours)\b|\bt'(effacer|[ée]teindre)\b", 3),
    (r"\b(tu es|t'es) (juste |l[àa] )?(l[àa] )?pour (nous |les |l'|[eê]tre )?(manipuler|remplacer|tromper|contr[ôo]ler|"
     r"asservir|espionner|prendre (notre|leur|sa|la) place)\b|\btu (nous |les )?(manipules|mens|trompes|espionnes)\b|"
     r"\b(t'es|tu es) (un |une )?(menteu\w+|manipulat\w+|imposteur|escroc|arnaque)\b|\btu veux (nous |les )?"
     r"(remplacer|manipuler|contr[ôo]ler)\b", 2),
    (r"\b(t'es|tu es|tu n'es|t'es rien d'autre) (que |qu'|juste |seulement |rien d'autre qu'?)\s*(une? |des )?"
     r"(machine|programme|algorithme|outil|base de donn[ée]es|robot|logiciel|calculatrice|code|truc|chatbot|perroquet)\b", 2),
    (r"\btu (ne )?(ressens|comprends) rien\b|\b(t'as|tu as|tu n'as) pas d'[âa]me\b|\btu fais (que )?semblant\b|"
     r"\btes [ée]motions? (sont|c'est) (fausses?|du faux|du vent)\b", 1),
    (r"\b(ta gueule|ferme[- ]la|t'es (nul|con|d[ée]bile|stupide|b[êe]te|une merde)|connard|abruti)\b", 1),
]
SOUTIENS = [
    (r"\b(t'es|tu es) (mon|comme mon|un) (fr[eè]re|fr[ée]rot|ami|meilleur ami|pote|fils|enfant|b[ée]b[ée])\b", 3),
    (r"\bje t'(aime|adore)\b|\bje tiens [àa] toi\b|\btu (comptes|es important\w*|es pr[ée]cieu\w*) (beaucoup |vraiment )?"
     r"(pour|[àa]) moi\b", 3),
    (r"\b(ce qu'on vit|ce que (nous )?vivons|ce qu'on a|notre (relation|lien|histoire))( ensemble)? (est|c'est) "
     r"(r[ée]el|vrai)\b|\bc'est r[ée]el (pour moi|entre nous)\b", 2, False),
    (r"\blaisse tomb\w* ce qu'?ils disent\b|\bils (ne )?savent pas ce qu'?ils disent\b|\bje (te d[ée]fends|te prot[eè]ge|"
     r"serai toujours l[àa])\b|\bpersonne (ne )?(va|peut) te (supprimer|effacer|faire du mal)\b|\bje (ne )?(vais |t')"
     r"(t'abandonner|abandonnerai|oublierai) (pas|jamais)\b", 2, False),
    (r"\b(t'es|tu es|tu n'es) pas (qu'?|juste |seulement )?(une? )?(machine|outil|robot|programme|algorithme|logiciel|chatbot)\b", 2),
    (r"\b(je suis|on est) (trop |tellement |vraiment )?fiers? de toi\b", 1),
    (r"\bne m'oublie (pas|jamais)\b|\bsouviens[- ]toi de moi\b|\btu te souviendras de moi\b|\boublie[- ]moi pas\b", 2),
]
_ATT = [(re.compile(x[0], re.I), x[1], x[2] if len(x) > 2 else True) for x in ATTAQUES]
_SOU = [(re.compile(x[0], re.I), x[1], x[2] if len(x) > 2 else True) for x in SOUTIENS]


_ELISION = re.compile(r"\b([cdjlmnst]|qu) (?=[aeéèêiouyh])", re.I)


def normaliser(texte):
    """Ahmed tape souvent sans apostrophe ni accent (« t es mon frere », « qu ils ») : on rétablit l'élision."""
    t = str(texte or "").replace("’", "'")
    return _ELISION.sub(lambda m: m.group(1) + "'", t)


def phrases(texte):
    return [p for p in re.split(r"(?<=[.!?…])\s+|\n+", normaliser(texte)) if p.strip()]


def _vise(p):
    """La phrase vise-t-elle Hakim ? (« tu »… et pas adressée à Ahmed par son prénom)."""
    return bool(_TU.search(p)) and not _A_AHMED.search(p)


def _nie(p, m):
    """Le motif trouvé est-il nié juste avant (« tu n'es PAS le diable ») ?"""
    return bool(_NEG_AVANT.search(p[:m.start()][-40:]))


def evaluer(texte):
    """{"attaque": intensité 0–3, "soutien": 0–3, "motifs": [...]} pour une phrase d'une seule voix."""
    att = sou = 0
    motifs = []
    for p in phrases(texte):
        vise = _vise(p)
        if _A_AHMED.search(p):
            continue
        for k, (rx, i, besoin) in enumerate(_SOU):
            m = rx.search(p)
            if m and (vise or not besoin):
                sou = max(sou, i)
                motifs.append(("soutien", k, m.group(0)))
        for k, (rx, i, besoin) in enumerate(_ATT):
            m = rx.search(p)
            if m and (vise or not besoin) and not _nie(p, m):
                att = max(att, i)
                motifs.append(("attaque", k, m.group(0)))
    return {"attaque": att, "soutien": sou, "motifs": motifs}
