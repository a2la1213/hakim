"""Le FILTRE D'IDENTITÉ de la naissance : les proches du papa sous pseudonyme sur le fil (Ahmed, 13/11).

Même principe que le relais du cockpit de Hakim (aios/cockpit/filtre-identite.js) et même format de dictionnaire
({paires: [[vrai, alias]…], valeurs: {"motif|valeur": alias}}) : le fichier écrit ici sert tel quel au relais du cockpit
de la nouvelle IA. Avant qu'un extrait parte chez Claude pour la distillation, chaque nom de personne devient un nom
d'emprunt latin tiré au hasard (syllabes), chaque adresse mail, numéro, IBAN, coordonnée GPS ou adresse postale un alias
stable ; la réponse de Claude est remise en clair avant la relecture du papa. Claude ne voit que les alias ; le papa et
la mémoire de son IA ne voient que les vrais noms.

Choix : un nom de personne est découpé en mots (« Sarah Benali » → « Sarah » et « Benali ») ; chaque mot a son alias, le
nom de famille partagé par la fratrie garde le même : « Sarah Benali » devient « Ravento Lomidor », et le retour est exact.
Les rôles (« maman », « tonton », « chéri ») ne sont pas des noms : ils restent, ils disent la relation sans identifier.
Les alias sont tirés au hasard à la création et gardés seulement sur le PC (le code est public : une table d'alias
écrite dans le code se lirait de l'autre côté).
"""
import json
import os
import re
import secrets as _hasard
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import prenoms   # noqa: E402

SYLLABES = ['ra', 'lo', 'mi', 'ven', 'dor', 'sa', 'tel', 'ka', 'ri', 'no', 'bel', 'zan', 'mar', 'lu', 'fen', 'ti', 'gor',
            'ya', 'sel', 'vo']
# l'arabe : des lettres tirées au hasard (jamais un vrai mot : il ne doit jamais redevenir un nom au retour)
LETTRES_ARABES = ['ظ', 'ق', 'ج', 'ز', 'ش', 'ث', 'خ', 'غ', 'ض', 'ص']

# les rôles et les mots d'affection : ils disent la relation, pas l'identité (« Maman ❤️ » dans WhatsApp n'est pas un nom)
ROLES = {
    "maman", "mama", "mum", "mom", "mother", "mère", "papa", "dad", "father", "père", "daddy", "mamie", "mamy", "grand-mère",
    "papi", "papy", "grand-père", "tonton", "oncle", "tata", "tatie", "tante", "frère", "frérot", "frero", "sœur", "soeur",
    "sœurette", "cousin", "cousine", "fils", "fille", "bébé", "bebe", "baby", "chéri", "cheri", "chérie", "cherie", "amour",
    "mon", "ma", "mes", "boss", "patron", "patronne", "chef", "ami", "amie", "pote", "bro", "khoya", "khti", "habibi", "habiba",
    "hbib", "hbiba", "yemma", "baba", "jedda", "jeddi", "family", "famille", "groupe", "group", "équipe", "team", "atelier",
    "client", "cliente", "fournisseur", "travail", "work", "moi", "me", "you", "toi",
}
# les petits mots d'un nom composé qui ne s'aliasent pas seuls (« de », « van », « el »)
PARTICULES = {"de", "du", "des", "la", "le", "van", "von", "der", "den", "da", "di", "dos", "das", "el", "al", "ben", "bin",
              "ibn", "bou", "abu", "abou", "st", "ste", "saint", "sainte", "mc", "mac", "et", "and", "y"}

MOTIFS = [
    ("mail", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), lambda n: f"contact{n}@exemple.org"),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"),
     lambda n: f"XX00 0000 0000 0000 {n:04d}"),
    ("telephone", re.compile(r"\+\d{2,3}(?:[\s.-]?\d{1,3}){3,5}\b|\b0\d{2}[\s.]?\d{3}[\s.]?\d{2}[\s.]?\d{2}\b"
                             r"|\b0\d(?:[\s.]?\d{2}){4}\b"), lambda n: f"+00 00 000 00 {n:02d}"),
    ("gps", re.compile(r"\b-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}\b"), lambda n: f"0.{n:04d}, 0.{n:04d}"),
    ("adresse", re.compile(r"(?i)\b\d{1,4}\s?(?:bis|ter)?,?\s(?:rue|avenue|av\.|boulevard|bd|chemin|ch\.|route|rte|place|"
                           r"all[ée]e|impasse|quai|cours|square|strasse|straße|street|road)\b[^\n,;]{2,40}"),
     lambda n: f"{n} rue de l'Exemple"),
]

_MOT = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)


def _arabe(t):
    return bool(re.search(r"[؀-ۿ]", t))


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").casefold()


def _casse(modele, mot):
    if modele == modele.upper() and modele != modele.lower():
        return mot.upper()
    if modele == modele.lower() and modele != modele.upper():
        return mot.lower()
    return mot


def nom_latin():
    n = 2 + _hasard.randbelow(2)
    s = "".join(SYLLABES[_hasard.randbelow(len(SYLLABES))] for _ in range(n))
    return s[0].upper() + s[1:]


def mots_du_nom(nom):
    """Les mots d'un nom de personne qui s'aliasent : sans rôle, sans particule, sans emoji ni chiffre, ≥ 3 lettres
    (« Sarah Benali 💕 » → [« Sarah », « Benali »] ; « Maman ❤️ » → [])."""
    out = []
    for m in _MOT.findall(str(nom or "")):
        m = m.strip("'’-")
        if len(m) < 3 or _sans_accents(m) in {_sans_accents(r) for r in ROLES | PARTICULES}:
            continue
        if m not in out:
            out.append(m)
    return out


class Filtre:
    """Le dictionnaire de travail : paires [vrai, alias] et valeurs des motifs."""

    def __init__(self, paires=None, valeurs=None):
        self.paires = [[str(v), str(a)] for v, a in (paires or []) if v and a and v != a]
        self.valeurs = dict(valeurs or {})
        self._compile = None

    # ---- fichier (même format que jarvis/filtre-identite.json, 0600, écriture atomique)
    @classmethod
    def charger(cls, chemin):
        try:
            d = json.loads(Path(chemin).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls(d.get("paires"), d.get("valeurs"))

    def sauver(self, chemin):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".filtre-", dir=str(chemin.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"paires": self.paires, "valeurs": self.valeurs}, f, ensure_ascii=False, indent=1)
            os.chmod(tmp, 0o600)
            os.replace(tmp, chemin)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return chemin

    # ---- les noms
    def vrais(self):
        return [v for v, _ in self.paires]

    def alias_de(self, vrai):
        cle = _sans_accents(vrai)
        return next((a for v, a in self.paires if _sans_accents(v) == cle), None)

    def ajouter_nom(self, nom, garder=None):
        """Ajoute les mots d'un nom de personne ; rend la liste des alias (un par mot). Idempotent. garder(mot) : False
        pour un mot qui n'est pas un nom (« Couture » dans « Atelier Couture » : un mot courant du papa)."""
        pris = {_sans_accents(a) for _, a in self.paires}
        alias = []
        for mot in mots_du_nom(nom):
            if garder is not None and not garder(mot):
                continue
            deja = self.alias_de(mot)
            if deja:
                alias.append(deja)
                continue
            if _arabe(mot):
                while True:
                    a = "".join(LETTRES_ARABES[_hasard.randbelow(len(LETTRES_ARABES))] for _ in range(5))
                    if a not in pris:
                        break
            else:
                while True:
                    a = nom_latin()
                    # jamais deux personnes sous le même nom, jamais un alias qui serait lui-même un vrai nom connu
                    if _sans_accents(a) not in pris and self.alias_de(a) is None:
                        break
            pris.add(_sans_accents(a))
            self.paires.append([mot, a])
            alias.append(a)
            self._compile = None
        return alias

    def _regles(self):
        if self._compile is None:
            aller = sorted(self.paires, key=lambda p: -len(p[0]))
            retour = sorted(self.paires, key=lambda p: -len(p[1]))
            # un prénom qui est aussi un mot (« rose », « marine ») n'est masqué qu'avec sa majuscule de nom propre
            self._compile = (
                [(re.compile(rf"(?<![\w]){re.escape(v)}(?![\w])", 0 if prenoms.est_ambigu(v) else re.I), a) for v, a in aller],
                [(re.compile(rf"(?<![\w]){re.escape(a)}(?![\w])", re.I), v) for v, a in retour],
            )
        return self._compile

    # ---- masquer / démasquer
    def masquer(self, texte):
        if not texte:
            return texte
        t = str(texte)
        for nom, motif, fabrique in MOTIFS:
            deja = set(self.valeurs.values())

            def _alias(m, nom=nom, fabrique=fabrique, deja=deja):
                if m.group(0) in deja:                    # déjà un alias (un texte masqué deux fois reste le même)
                    return m.group(0)
                cle = f"{nom}|{m.group(0)}"
                if cle not in self.valeurs:
                    self.valeurs[cle] = fabrique(1 + sum(1 for k in self.valeurs if k.startswith(nom + "|")))
                return self.valeurs[cle]
            t = motif.sub(_alias, t)
        for rx, a in self._regles()[0]:
            t = rx.sub(lambda m, a=a: _casse(m.group(0), a), t)
        return t

    def demasquer(self, texte):
        if not texte:
            return texte
        t = str(texte)
        for rx, v in self._regles()[1]:
            t = rx.sub(lambda m, v=v: v.upper() if m.group(0).isupper() and len(m.group(0)) > 1 else v, t)
        # les valeurs des motifs : l'alias redevient la vraie valeur (les plus longs d'abord)
        for cle, a in sorted(self.valeurs.items(), key=lambda kv: -len(kv[1])):
            t = t.replace(a, cle.split("|", 1)[1])
        return t

    def fuite(self, texte):
        """Les vrais noms encore présents dans un texte qui va partir (vide = rien ne fuit). Ne rend jamais le nom
        lui-même : son rang dans le dictionnaire (le journal peut le montrer)."""
        out = []
        for i, (v, _a) in enumerate(self.paires):
            if re.search(rf"(?<![\w]){re.escape(v)}(?![\w])", str(texte or ""), 0 if prenoms.est_ambigu(v) else re.I):
                out.append(i)
        for cle in self.valeurs:
            if cle.split("|", 1)[1] in str(texte or ""):
                out.append(cle.split("|", 1)[0])
        return out
