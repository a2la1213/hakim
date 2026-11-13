"""L'HÉRITAGE DE HAKIM : ses savoir-faire et ses procédures, JAMAIS la vie privée d'Ahmed (Ahmed, 13/11).

Ce qui part : ses COMPÉTENCES (table skills) et ses TRACES DE RAISONNEMENT techniques (souvenirs « reasoning ») rangées
dans une rubrique de la LISTE BLANCHE (son propre système, l'apprentissage) — rien d'autre : ni souvenirs, ni identité,
ni conversations.
Comment :
1. la vraie mémoire de Hakim est lue en LECTURE SEULE : une copie par l'API de sauvegarde de SQLite depuis une connexion
   « mode=ro » ; on ne travaille que sur la copie (data/memory.db n'est jamais ouvert en écriture) ;
2. chaque élément est NEUTRALISÉ : l'en-tête (qui, quand, pour qui) retiré, « papa » → « son créateur », « maman » →
   « Claude Code », les noms du dictionnaire privé du filtre d'identité de Hakim et les noms de projets et de clients
   d'Ahmed (ceux que retire la publication publique, et chaque projet de son arbre de rubriques) remplacés, les longues
   citations de conversation retirées, les chemins personnels raccourcis ;
3. chaque élément neutralisé passe la VÉRIFICATION, qui le refuse (sans le réparer) s'il reste un nom de personne, un lieu,
   un chiffre d'argent ou un mot de finance, une clé, la santé, la religion, la famille, un réseau social : on préfère
   perdre une trace que laisser passer un morceau de sa vie ;
4. le fichier d'export (heritage-hakim.json) part chez Ahmed, qui le relit et l'APPROUVE (son empreinte est scellée) ;
   l'import chez la nouvelle IA refuse un fichier non approuvé, ou modifié après l'approbation.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
for _p in (str(ICI), str(RACINE_DEPOT), str(RACINE_DEPOT / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

import prenoms   # noqa: E402

LISTE_BLANCHE = ("projets/anamnese", "meta-apprentissage")
# Les noms privés ne sont JAMAIS écrits dans ce code (il est publié) : ils sont lus, à l'exécution, dans les fichiers privés
# du Mac d'Ahmed — le dictionnaire du filtre d'identité de Hakim, et les règles de la publication publique (les noms de
# projets, de clients et de proches qu'elle retire, et le prénom qui l'ARRÊTE).
SOURCES_PRIVEES = {
    "dictionnaire": Path.home() / "AIOS" / "jarvis" / "filtre-identite.json",
    "neutraliser": Path.home() / "AIOS" / "publication" / "neutraliser.pl",
    "publier": Path.home() / "AIOS" / "publication" / "publier.sh",
}
DICTIONNAIRE_PRIVE = SOURCES_PRIVEES["dictionnaire"]
VERSION = 1
COMMUNS = {"cite", "robot", "genesis", "benchmark", "supra", "study", "app", "web", "bio", "distillation", "independant",
           "inspiration", "metal", "audio", "eval", "design", "frontend", "seo", "qa", "devops", "local", "fullstack"}

# --------------------------------------------------------------------------- lecture seule
def copie_lecture_seule(db_reel, dest):
    """Copie la base par l'API de sauvegarde depuis une connexion en lecture seule (mode=ro) : la vraie base n'est jamais
    ouverte en écriture."""
    src = sqlite3.connect(f"file:{Path(db_reel).resolve()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return Path(dest)


def candidats(conn):
    """Les compétences et les traces de raisonnement des rubriques de la liste blanche : [{genre, cle, titre, texte, rubrique}]."""
    out = []
    for nom, desc, contenu in conn.execute("SELECT name, description, content FROM skills ORDER BY id"):
        out.append({"genre": "competence", "cle": f"skill:{nom}", "titre": nom, "description": desc or "", "texte": contenu or "",
                    "rubrique": None})
    cols = {r[1] for r in conn.execute("PRAGMA table_info(episodes)")}
    if "rubric_id" in cols:
        rows = conn.execute("SELECT e.id, e.ts, e.content, r.path FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id "
                            "WHERE e.role = 'reasoning' ORDER BY e.id").fetchall()
    else:
        rows = [(i, ts, c, None) for i, ts, c in conn.execute("SELECT id, ts, content FROM episodes WHERE role='reasoning'")]
    for eid, ts, contenu, chemin in rows:
        out.append({"genre": "raisonnement", "cle": f"reasoning:{eid}", "titre": "", "description": "", "texte": contenu or "",
                    "rubrique": chemin, "date": time.strftime("%Y-%m", time.localtime(ts or 0))})   # au mois : jamais son horaire
    return out


def dans_liste_blanche(c, liste=LISTE_BLANCHE):
    if c["genre"] == "competence":
        return True
    r = c.get("rubrique") or ""
    return any(r == x or r.startswith(x + "/") for x in liste)


def codes_des_agents(dossiers=None):
    """Les codes de projets d'Ahmed tirés des NOMS de ses équipes d'agents (« dev-tarifs-xyzt », « qa-xyzt » → « xyzt ») :
    un dernier segment partagé par au moins deux agents est un code de projet (relecture indépendante du 13/11)."""
    from collections import Counter
    if dossiers is None:
        dossiers = [Path.home() / ".claude" / "agents"] + list((Path.home() / "Desktop").glob("*/.claude/agents"))
    c = Counter()
    for d in dossiers:
        try:
            for f in Path(d).glob("*.md"):
                seg = f.stem.split("-")[-1].lower()
                if len(seg) >= 3 and seg not in COMMUNS:
                    c[seg] += 1
        except OSError:
            continue
    return sorted(k for k, n in c.items() if n >= 2)


def initiales(regles):
    """Les initiales des noms de produits retirés par la publication (« MaBelleBoutique » → « mbb ») : un identifiant de
    code comme « mbb_active_business » trahit le client."""
    out = set()
    for gauche in regles.interdits if regles else []:
        for nom in re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+){2,}", gauche):
            out.add("".join(x[0] for x in re.findall(r"[A-Z][a-z]+", nom)).lower())
    return sorted(x for x in out if len(x) >= 3)


def projets_de_l_arbre(conn):
    """Les noms de projets d'Ahmed (rubriques « projets/<nom> ») hors liste blanche : à retirer des textes."""
    try:
        chemins = [p for (p,) in conn.execute("SELECT path FROM rubrics")]
    except sqlite3.Error:
        return []
    noms = set()
    for p in chemins:
        parties = p.split("/")
        if len(parties) >= 2 and parties[0] == "projets" and parties[1] != "anamnese":
            noms.add(parties[1])
    return sorted(noms)


# --------------------------------------------------------------------------- neutralisation
_PUBLICATION = [(r"(?i)a2la1213|\ba2la\b", "le créateur")]       # son nom public d'artiste et de dépôt


class Regles:
    """Les règles privées lues sur le Mac : remplacements (regex, texte) et noms interdits (regex) pour la vérification."""

    def __init__(self, remplacements=(), interdits=(), dico_noms=()):
        self.remplacements = list(remplacements)
        self.interdits = list(interdits)
        self.dico_noms = list(dico_noms)


def regles_privees(sources=None):
    sources = {**SOURCES_PRIVEES, **(sources or {})}
    remplacements, interdits = [], []
    dico = _dico_prive(sources.get("dictionnaire"))
    try:
        pl = Path(sources["publier"]).read_text(encoding="utf-8")
        for gauche, droite in re.findall(r"-e 's/((?:[^/\\']|\\.)+)/((?:[^/\\']|\\.)*)/g'", pl):
            remplacements.append((gauche, droite.replace("\\.", ".")))
            interdits.append(gauche)                       # ce que la publication réécrit ne doit plus se lire après nous
        for motif in re.findall(r'if grep -rli -E "([^"]+)"[^\n]*ARRÊT : le prénom', pl):
            interdits.append(f"(?i){motif}")
    except (OSError, KeyError):
        pass
    try:
        npl = Path(sources["neutraliser"]).read_text(encoding="utf-8")
        for gauche, droite in re.findall(r"s/((?:[^/\\]|\\.)+)/((?:[^/\\]|\\.)*)/g", npl):
            try:
                re.compile(gauche)
            except re.error:
                continue
            remplacements.append((gauche, droite))
            interdits.append(gauche)
    except (OSError, KeyError):
        pass
    return Regles(remplacements, interdits, dico)
CREATEUR = "le créateur de Hakim"          # jamais « son créateur » : chez la nouvelle IA, ce serait son papa à elle
_ROLES = [
    (r"(?i)\bde papa\b", "du créateur de Hakim"), (r"(?i)\bà papa\b", "au créateur de Hakim"),
    (r"\bpapa\b", CREATEUR), (r"\bPapa\b", "Le créateur de Hakim"), (r"\bPAPA\b", "LE CRÉATEUR DE HAKIM"),
    # dans un identifiant de code (« transcriptionsPapa », « voix_papa_azure ») : bordé de lettres, ou en camelCase
    (r"(?<=[a-z])Papa(?![a-z])", "Createur"), (r"(?<![A-Za-z])papa(?![a-z])", "createur"),
    (r"\b(?:maman|Maman|Nour)\b", "Claude Code"), (r"\bfrérot\b", "Hakim"), (r"\bfiston\b", "Hakim"),
    (r"\b(?:tonton|tata)\b", "la famille d'agents"),
    (r"\b(?:Z ?Fold ?7|Galaxy Z Fold\s?\d*|Fold 7|Galaxy Watch\s?\d*|S21 Ultra)\b", "le téléphone"),
    (r"(?:/Users|/home)/[^/\s]+", "~"), (r"(?:-Users|-home)-[A-Za-z0-9_.]+-", "-~-"),
    # les heures d'horloge (« 21:45-22:10 », « à 08:50 », « avant 22 h », « après 22 h 30 ») : ensemble, elles dessinent ses
    # nuits et ses journées ; une DURÉE (« blocs de 6 h », « toutes les 3 h ») et un format d'écran (« 16:10 ») restent
    (r"(?<![\w:])(?!(?:16:9|16:10|4:3|21:9|9:16|3:2)\b)\d{1,2}:\d{2}(?::\d{2})?\b", "[heure]"),
    (r"\b\d{1,2}\s?h\s?\d{2}\b", "[heure]"),
    (r"(?i)\b(à|vers|dès|depuis|jusqu'à|avant|après)\s\d{1,2}\s?h\b", r"\1 [heure]"),
]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
# un jour précis (« le 03/11 », « du 19-20/10 », « 08/11 [heure] ») devient son mois : la date au mois, comme le champ « date »
_JOUR = re.compile(r"\b(?:(?:le|du|au|depuis le|jusqu'au|dès le|et le|entre le)\s+)?(?:[0-3]\d)(?:-[0-3]\d)?/(0[1-9]|1[0-2])"
                   r"(?:/\d{2,4})?\b(?=\s*(?:\[heure\]|[,;:).]|\s|$))")


def _au_mois(t):
    def mois(m):
        avant = m.group(0)
        if not re.match(r"(?:le|du|au|depuis|jusqu|dès|et|entre)\b", avant) and not re.search(r"\[heure\]", t[m.end():m.end() + 12]):
            return avant                                   # « 10/10 » sans mot de date : un score de tests, pas un jour
        return "en " + _MOIS[int(m.group(1)) - 1]
    return _JOUR.sub(mois, t)


def _retirer_entete(t):
    """L'en-tête « [Raisonnement, agent X pour Y, 13/11, « … [[son: genou]] … »] » : retiré en entier, crochets imbriqués
    compris (relecture indépendante du 13/11 : le premier « ] » laissait un reste)."""
    t = str(t or "").lstrip()
    if not t.startswith("["):
        return t
    prof = 0
    for i, ch in enumerate(t[:800]):
        prof += ch == "["
        prof -= ch == "]"
        if prof == 0:
            return t[i + 1:].lstrip()
    return t
# une citation de conversation (« … » attribuée à quelqu'un, ou longue) : retirée
_CITATION_ATTRIBUEE = re.compile(r"(?P<att>\b(?:du créateur de Hakim|au créateur de Hakim|le créateur de Hakim|son créateur|"
                                 r"Ahmed|Hakim|Claude Code|il|elle)\b\s*(?:\d{1,2}[:h/]\d{2}\s*)?"
                                 r"(?:dit|disait|a dit|demande|demandait|écrit)?\s*:\s*)«[^»]{0,800}»")
_CITATION_LONGUE = re.compile(r"«[^»]{90,1500}»")
# une citation courte qui PARLE (« je veux tout », « T'étais bloqué dans le passé ») : une parole, pas un terme technique
_CITATION_PAROLE = re.compile(r"«[^»]{0,89}\b(?:je|j'|tu|t'|moi|toi|t'es|t'étais|ton|ta|tes|c'est pas|t'as|ouais|wallah|mdr|wesh|frérot|fiston|papa)\b[^»]{0,89}»",
                              re.I)


def _retirer_paroles(t):
    """Une parole (« je… », « tu… ») part ; une docstring, une consigne ou un message d'erreur cités restent."""
    def f(m):
        if re.search(r"(?i)(docstring|consigne|commentaire|message d'erreur|erreur|log|affiche)\W{0,4}$", t[max(0, m.start() - 30):m.start()]):
            return m.group(0)
        return "«…»"
    return _CITATION_PAROLE.sub(f, t)


def _est_hakim(vrai):
    return prenoms._sans_accents(vrai).startswith("hakim") or vrai == "حكيم"


def formes_projets(projets):
    """Les façons d'écrire les noms de projets d'Ahmed (« appli-x », « appli x », « applix »…)."""
    out = set()
    for p in projets:
        for f in {p, p.replace("-", " "), p.replace("-", ""), p.replace("-", "_")}:
            if len(f) >= 3 and f.lower() not in COMMUNS:
                out.add(f)
        tete = p.split("-")[0]
        if len(tete) >= 6 and tete.lower() not in COMMUNS:
            out.add(tete)
    return sorted(out, key=len, reverse=True)


def _neutre_noms(texte, dico_noms, projets):
    t = texte
    for vrai in sorted(dico_noms, key=len, reverse=True):
        if not vrai:
            continue
        if _est_hakim(vrai):
            t = re.sub(rf"(?<![\w]){re.escape(vrai)}(?![\w])", "Hakim", t, flags=re.I)
            continue
        v = re.escape(vrai)
        t = re.sub(rf"(?<![\w])[dD]['’]\s?{v}(?![\w])", "du créateur de Hakim", t, flags=re.I)
        t = re.sub(rf"(?<![\w])de {v}(?![\w])", "du créateur de Hakim", t, flags=re.I)
        t = re.sub(rf"(?<![\w])à {v}(?![\w])", "au créateur de Hakim", t, flags=re.I)
        t = re.sub(rf"(?<![\w]){v}(?![\w])", CREATEUR, t, flags=re.I)
        # dans un identifiant de code (« voix_ahmed ») : le nom aussi, bordé de lettres seulement
        t = re.sub(rf"(?<![a-zà-ÿ]){v}(?![a-zà-ÿ])", "createur", t, flags=re.I)
    for forme in formes_projets(projets):
        t = re.sub(rf"(?<![\w]){re.escape(forme)}(?![\w])", "un projet", t, flags=re.I)
    return t


def neutraliser(texte, dico_noms=(), projets=(), regles=None):
    """L'ordre compte : les noms de projets d'abord (« clientx-app » avant que « clientx » ne soit réécrit), puis les
    règles privées de la publication (« un ami d'Ahmed »…), puis les noms du dictionnaire (« Ahmed » → « le créateur »)."""
    t = _retirer_entete(texte)
    t = _neutre_noms(t, (), projets)
    for rx, r in _PUBLICATION + (regles.remplacements if regles else []):
        try:
            t = re.sub(rx, r, t)
        except re.error:
            continue
    t = _neutre_noms(t, dico_noms, ())
    for rx, r in _ROLES:
        t = re.sub(rx, r, t)
    t = _CITATION_ATTRIBUEE.sub(r"\g<att>«…»", t)                        # qui a parlé reste, ce qu'il a dit part
    t = _CITATION_LONGUE.sub("«…»", t)
    t = _retirer_paroles(t)
    t = _au_mois(t)
    t = t.replace("du le créateur de Hakim", "du créateur de Hakim").replace("de le créateur de Hakim", "du créateur de Hakim")
    return re.sub(r"[ \t]{2,}", " ", t).strip()


# --------------------------------------------------------------------------- vérification (fail-closed)
# (calibré le 13/11 sur les 132 candidats de la liste blanche : « marge thermique », « diagnostic de la voix », « enceinte »
# du téléphone, « plus proche voisin », « processus enfants », « dette technique », la « police » d'écriture sont des mots
# techniques, pas sa vie)
_LIEUX = re.compile(r"(?i)\b(Gen[eè]ve|Toulouse|Vaud|Valais|Alger|Oran|Constantine|"
                    r"Paris|Lyon|Marseille|Bruxelles|Zurich|Z[uü]rich|Berne|Fribourg|Neuch[aâ]tel|Montreux|Vevey|Nyon|"
                    r"Yverdon|Casablanca|Tunis|Rabat|Marrakech|chez nous|chez lui|à la maison|Sunrise_\w+|"
                    r"\w+\.ts\.net|tail[0-9a-f]{4,})\b"
                    r"|\b\d{1,4},?\s(?:rue|avenue|chemin|boulevard|route|place|impasse)\s(?:de |du |des |d')?\w+"
                    r"|\b(?:\d{1,3}\.){3}\d{1,3}\b")
_ARGENT = re.compile(r"\d[\d\s'’.,]*\s?(?:€|CHF|EUR|USD|USDT|k€)(?![A-Za-z])|(?<![A-Za-z])(?:€|CHF|USD|EUR)\s?\d"
                     r"|\$\s?\d|(?i:\b\d[\d\s'’.,]*\s?(?:francs?|euros?|dollars?|centimes?)\b)"
                     r"|(?i:\b(?:XRP|BTC|ETH|USDT|bitcoin|crypto\w*|Bit[g]et|Binance|trading|trader|traders|bourse|backtest\w*|"
                     r"TJM|salaires?|chiffre d'affaires|bougies?|chandeliers?|minage|mineurs?|PoUW|blockchain|wallet)\b)")
_SANTE = re.compile(r"(?i)\b(sant[ée]|maladies?|malade|m[ée]decin\w*|m[ée]dical\w*|h[ôo]pital|m[ée]dicament\w*|ordonnance|"
                    r"douleur\w*|bless[ée]\w*|blessure\w*|grossesse|psychiatr\w*|psychologue|th[ée]rapie|d[ée]pression|"
                    r"anxi[ée]t[ée]|cancer|diab[èe]te|handicap\w*|fatigue chronique)\b")
_PRIVE = re.compile(r"(?i)\b((?:ma|sa|ta|notre|leur|la) famille|familial\w*|m[èe]re|p[èe]re|s[œo]eur|fr[èe]re|[ée]pouse|mari|"
                    r"(?:ses|mes|tes|leurs|son|mon) enfants?|b[ée]b[ée]|mariage|divorce|anniversaire|amoureu\w*|copine|copain|"
                    r"religion|religieu\w*|Allah|islam\w*|musulman\w*|coran\w*|quran|sourate\w*|versets?|pri[èe]res?|"
                    r"ramadan|hadith\w*|mosqu[ée]e|dieu|baraka\w*|inch'?allah|machallah|hamdoulah|salam|TikTok|Instagram|"
                    r"Facebook|Snapchat|abonn[ée]s|viewers?|empreinte vocale|signature vocale|ami d'enfance|ex-?femme|"
                    r"nationalit[ée]|passeport|faillite|dettes? (?!technique)|avocat\w*|tribunal|plainte|prison)\b")
_CLE_LONGUE = re.compile(r"(?<![\w/+=.-])[A-Za-z0-9_\-+/=]{24,}(?![\w/+=-])")
# des IDENTIFIANTS de comptes (relecture indépendante du 13/11 : un projet Vercel, une équipe, une base Supabase, un IBAN
# d'exemple, un numéro d'entreprise, l'endroit où dort une clé)
_IDENTIFIANTS = re.compile(r"\b(?:prj|team|org|proj|acct|cus|sub|pi|price|prod|ws|wrkspc)_[A-Za-z0-9]{8,}\b"
                           r"|\b(?=[a-z0-9]*[g-z])(?=[a-z0-9]*\d)[a-z0-9]{20}\b|\b[a-z0-9]{20}\.supabase\.co\b"
                           r"|(?i:project.?ref\s*[:=]?\s*[a-z0-9]{12,})|\bCHE-?\d{3}\.?\d{3}\.?\d{3}\b"
                           r"|\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b"
                           r"|\.env(?:\.[a-z]+)?\b[^\n]{0,80}\b[A-Z0-9_]*(?:KEY|SECRET|TOKEN)\b"
                           r"|\b[A-Z0-9_]*(?:KEY|SECRET|TOKEN)\b[^\n]{0,80}\.env(?:\.[a-z]+)?\b")
# sa vie quotidienne, ses lives, ses appareils, son origine (relecture indépendante du 13/11)
_HABITUDES = re.compile(r"(?i)\b(?:boxe|muay|sieste|entra[îi]nement|salle de sport|se couche|s'endort|au lit|réveil de|"
                        r"(?:sommeil|repas|dîner|douche) du créateur|le créateur (?:dort|mange|sort))\b")
_LIVES = re.compile(r"\b(?i:le|un|du|des|son|ses|en|au|ce|d'un|pendant le|pendant son) lives?\b(?!\s*(?:route|scoring))"
                    r"|\blive\s*(?:\(|du |de )?\s*(?:\[heure\]|en (?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|"
                    r"octobre|novembre|décembre)|\d{2}/\d{2})"
                    r"|\bses (?:amis|potes)\b|\bWhatsApp\b|\bMessenger\b")
_APPAREILS = re.compile(r"(?i)\b\w+['’]s (?:buds|iphone|ipad|macbook|galaxy|airpods|watch|phone|tab)\b|\bbuds\b|airpods|"
                        r"ULT Field|ICONIC Sound|Galaxy (?:Buds|Watch|Z|S\d+)|\bZ ?Fold|\bZ ?Flip|\[prénom\]")
_ORIGINE = re.compile(r"(?i)\bar-DZ\b|\bdarija\b|alg[ée]rie\w*|kabyle|maghr[ée]bin\w*|\barabes?\b")
_MAJ = re.compile(r"(?<![\w'’-])([A-ZÀ-Ý][a-zà-ÿ]{2,})(?![\w'’-])")
NOMS_PERMIS = {"hakim", "claude"}      # son grand frère, et Claude (Claude Code) : la nouvelle IA les connaît


def _ressemble_cle(tok):
    """Un identifiant ou une clé : long, mêlant majuscules, minuscules et chiffres, sans vrai mot (un nom de modèle comme
    « potion-multilingual-128M » ou un chemin n'en est pas un)."""
    if "/" in tok.strip("/") and tok.count("/") >= 1 and re.search(r"[a-z]{5,}", tok):
        return False
    lettres = max((len(x) for x in re.findall(r"[A-Za-z]+", tok)), default=0)
    classes = sum(bool(re.search(rx, tok)) for rx in (r"[A-Z]", r"[a-z]", r"\d"))
    return classes == 3 and lettres <= 10 and len(set(tok)) >= 12


def verifier(texte, dico_noms=(), autres_noms=(), regles=None):
    """Les raisons de refuser un texte neutralisé ([] = il passe). Ne rend jamais la valeur trouvée."""
    import fichiers
    t = str(texte or "")
    raisons = []
    interdits = {prenoms._sans_accents(n) for n in list(dico_noms) + list(autres_noms) if n and not _est_hakim(n)} - NOMS_PERMIS
    for m in _MAJ.findall(t):
        k = prenoms._sans_accents(m)
        if k in NOMS_PERMIS:
            continue
        if prenoms.est_prenom(m) and not prenoms.est_ambigu(m) or k in interdits:
            raisons.append("nom")
            break
    # bordé de LETTRES (pas de mots) : un nom dans un identifiant (« voix_ahmed ») compte aussi
    if "nom" not in raisons and any(re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", prenoms._sans_accents(t)) for n in interdits):
        raisons.append("nom")
    if "nom" not in raisons and regles is not None:
        for rx in regles.interdits:
            try:
                if re.search(rx, t):
                    raisons.append("nom")
                    break
            except re.error:
                continue
    if _LIEUX.search(t):
        raisons.append("lieu")
    if _ARGENT.search(t):
        raisons.append("argent")
    if fichiers.masquer(t) != t or any(_ressemble_cle(m) for m in _CLE_LONGUE.findall(t)) or "PRIVATE KEY" in t:
        raisons.append("clé")
    if _IDENTIFIANTS.search(t) and "clé" not in raisons:
        raisons.append("clé")
    if _SANTE.search(t):
        raisons.append("santé")
    if _PRIVE.search(t) or _HABITUDES.search(t) or _LIVES.search(t):
        raisons.append("vie privée")
    if _APPAREILS.search(t):
        raisons.append("appareil")
    if _ORIGINE.search(t):
        raisons.append("origine")
    # « papa », « maman », « fiston » qui resteraient (même dans un identifiant)
    if re.search(r"(?<![A-Za-z])(?:papa|maman|fiston|fr[ée]rot)(?![a-z])|(?<=[a-z])(?:Papa|Maman)(?![a-z])", t, re.I) \
            and "nom" not in raisons:
        raisons.append("nom")
    return raisons


def marque_client(texte, regles=None, genre="raisonnement"):
    """Une procédure d'un projet client d'Ahmed (même sous pseudonyme de publication) n'est pas un savoir-faire de Hakim :
    une compétence qui nomme un projet (ou porte l'étiquette d'un agent de projet, « [dev-tarifs-x] »), une trace qui nomme
    un pseudonyme de client."""
    t = str(texte or "")
    pseudos = set()
    for _g, d in (regles.remplacements if regles else []):
        if re.fullmatch(r"[A-Z][A-Za-z0-9]{4,}", d or ""):
            pseudos.add(d)
    if any(re.search(rf"(?<![A-Za-z]){re.escape(x)}(?![a-z])", t, re.I) for x in pseudos):
        return True
    if genre == "competence" and (re.search(r"\bun projet\b", t) or re.match(r"\s*\[[a-z0-9-]+\]", t)):
        return True
    return False


# --------------------------------------------------------------------------- export, approbation, import
def _dico_prive(chemin=None):
    try:
        d = json.loads(Path(chemin or DICTIONNAIRE_PRIVE).read_text(encoding="utf-8"))
        return [v for v, _a in d.get("paires") or [] if v]
    except (OSError, ValueError):
        return []


def empreinte(elements):
    return hashlib.sha256(json.dumps(elements, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def exporter(db_reel, sortie, sources=None, autres_noms=(), liste=LISTE_BLANCHE):
    """Construit heritage-hakim.json (à relire et approuver par Ahmed). sources : les fichiers privés (défaut : ceux du
    Mac d'Ahmed). Rend (bilan, chemin)."""
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    regles = regles_privees(sources)
    dico = regles.dico_noms
    codes = codes_des_agents(None if sources is None else sources.get("agents", []))
    inits = initiales(regles)
    with tempfile.TemporaryDirectory(prefix="heritage-") as d:
        copie = copie_lecture_seule(db_reel, Path(d) / "copie.db")
        conn = sqlite3.connect(str(copie))
        try:
            tous = candidats(conn)
            projets = projets_de_l_arbre(conn)
        finally:
            conn.close()
    bilan = {"candidats": len(tous), "hors_liste_blanche": 0, "refuses": {}, "gardes": 0,
             "par_genre": {"competence": 0, "raisonnement": 0}}
    elements, refus_exemples = [], []
    for c in tous:
        if not dans_liste_blanche(c, liste):
            bilan["hors_liste_blanche"] += 1
            continue
        texte = neutraliser(c["texte"], dico, projets + codes, regles)
        titre = neutraliser(c.get("titre") or "", dico, projets + codes, regles)
        desc = neutraliser(c.get("description") or "", dico, projets + codes, regles)
        tout = "\n".join([titre, desc, texte])
        raisons = verifier(tout, dico, list(autres_noms) + formes_projets(projets) + codes + inits, regles)
        if marque_client("\n".join([titre, desc, texte, c.get("description") or ""]), regles, c["genre"]):
            raisons.append("client")
        if raisons:
            for r in raisons:
                bilan["refuses"][r] = bilan["refuses"].get(r, 0) + 1
            refus_exemples.append({"cle": c["cle"], "raisons": raisons})
            continue
        e = {"genre": c["genre"], "titre": titre, "description": desc, "texte": texte, "rubrique": c.get("rubrique") or "",
             "date": c.get("date") or ""}
        elements.append(e)
        bilan["par_genre"][c["genre"]] += 1
    bilan["gardes"] = len(elements)
    bilan["refuses_total"] = len(refus_exemples)
    export = {"version": VERSION, "de": "Hakim", "cree": time.strftime("%Y-%m-%dT%H:%M:%S"), "liste_blanche": list(liste),
              "bilan": bilan, "elements": elements, "empreinte": empreinte(elements),
              "approbation": None,
              "a_relire": "À relire élément par élément avant de le transmettre. Pour approuver : python -m naissance.cerveau "
                          "heritage-approuver <ce fichier>. Toute modification après l'approbation fait refuser l'import."}
    chemin = sortie / "heritage-hakim.json"
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(export, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, chemin)
    # les refus ne gardent que leur clé et leurs raisons (jamais le texte) : pour qu'Ahmed sache ce qui n'est pas parti
    (sortie / "heritage-refus.json").write_text(json.dumps(refus_exemples, ensure_ascii=False, indent=1), encoding="utf-8")
    # la même chose, lisible d'un œil : un élément par bloc, numéroté
    import textwrap
    blocs = [f"HÉRITAGE DE HAKIM — {len(elements)} éléments ({bilan['par_genre']['competence']} compétences, "
             f"{bilan['par_genre']['raisonnement']} traces). À relire avant de transmettre.\n"]
    for i, x in enumerate(elements, 1):
        tete = (f"[{i}] {'COMPÉTENCE ' + x['titre'] if x['genre'] == 'competence' else 'TRACE ' + (x['rubrique'] or '')}"
                + (f" — {x['date']}" if x.get("date") else ""))
        corps = "\n".join(textwrap.fill(l, 110) for l in (x["description"] + "\n" + x["texte"]).strip().splitlines())
        blocs.append(f"{tete}\n{corps}\n")
    lisible = sortie / "heritage-hakim-a-relire.txt"
    lisible.write_text("\n".join(blocs), encoding="utf-8")
    os.chmod(lisible, 0o600)
    os.chmod(sortie / "heritage-refus.json", 0o600)
    return bilan, chemin


def approuver(chemin, par="Ahmed"):
    """Ahmed a relu : l'empreinte du contenu est scellée dans l'approbation."""
    chemin = Path(chemin)
    e = json.loads(chemin.read_text(encoding="utf-8"))
    e["approbation"] = {"par": par, "quand": time.strftime("%Y-%m-%dT%H:%M:%S"), "empreinte": empreinte(e["elements"])}
    chemin.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    return e["approbation"]


class NonApprouve(Exception):
    pass


def importer(chemin, db_path, embed=None):
    """Chez la nouvelle IA : ses compétences et ses traces héritées de son grand frère. Refuse un export non approuvé, ou
    modifié après l'approbation."""
    import memory
    e = json.loads(Path(chemin).read_text(encoding="utf-8"))
    a = e.get("approbation") or {}
    if not a:
        raise NonApprouve("l'héritage n'a pas été approuvé par Ahmed")
    if a.get("empreinte") != empreinte(e.get("elements") or []):
        raise NonApprouve("l'héritage a changé depuis l'approbation d'Ahmed")
    if embed is None:
        import embeddings
        embed = embeddings.embed
    import grand_frere
    mem = memory.Memory(db_path)
    n = {"competence": 0, "raisonnement": 0}
    for x in e["elements"]:
        # chez elle, chaque « Hakim » d'une trace héritée est son grand frère (le relais de son nom ne le réécrit pas)
        x = {**x, "texte": grand_frere.au_grand_frere(x["texte"]), "description": grand_frere.au_grand_frere(x["description"])}
        if x["genre"] == "competence":
            mem.save_skill(x["titre"], x["description"] or x["titre"],
                           f"(héritée de mon grand frère Hakim)\n{x['texte']}")
        else:
            mem.add("reasoning", f"[Héritage de mon grand frère Hakim — trace de {x.get('date') or '?'}] {x['texte']}",
                    importance=0.6, embedding=list(embed(x["texte"])))
        n[x["genre"]] += 1
    mem.kv_set("heritage_hakim", json.dumps({"importe": time.time(), "empreinte": a["empreinte"], **n}))
    mem.db.close()
    return n
