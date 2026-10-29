"""La liste ouverte de Hakim, en machine (28/10 ; Ahmed, 03:31 : « la relecture est la barrière », avec une LISTE OUVERTE
plutôt qu'une liste fermée ; il l'a validée à 03:39, telle que proposée, dans jarvis/liste-ouverte.json).

Une modification proposée par Hakim ne peut toucher QUE des fichiers de cette liste. Tout ce qui n'y est pas est fermé,
même ce qu'on aurait oublié. Ce module, la liste et leurs tests sont FERMÉS : sinon une modification pourrait ouvrir sa
propre porte.

Trois vérifications, au moment de proposer (chantiers.proposer) et de nouveau au moment d'appliquer (le cockpit) :
1. les fichiers : seulement les chemins exacts de la liste ; un test suit son module ouvert s'il n'importe aucun module
   fermé ; un fichier NOUVEAU est permis à quelques endroits, s'il ne masque rien (ni module du dépôt, ni bibliothèque) ;
2. les blocs FERME-DEBUT … FERME-FIN des fichiers ouverts (server.js, mcp_server.py) : rien ne s'y touche, et les
   bornes ne bougent pas ;
3. les appels fermés : une ligne AJOUTÉE qui efface, réécrit la base, lance un processus, ouvre le réseau ou contourne
   une garde est refusée. Ce sont des fils tendus, pas une preuve : la vraie barrière reste la relecture de maman, puis
   le geste d'Ahmed.
"""
import json
import re
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
LISTE = ICI / "liste-ouverte.json"
RACINES = {"anamnese": ICI.parent, "cockpit": Path.home() / "AIOS" / "cockpit"}

# --- 1. les fichiers
NOUVEAUX = {                                    # où un fichier NOUVEAU peut naître (jamais un paquet, jamais un sous-dossier)
    "anamnese": [re.compile(r"[a-z][a-z0-9_]*\.py"), re.compile(r"jarvis/[a-z][a-z0-9_]*\.py"),
                 re.compile(r"tests/test_[a-z0-9_]+\.py"), re.compile(r"eval/[a-z0-9_]+/[a-z0-9_]+\.(py|md|json)"),
                 re.compile(r"docs/[a-z0-9_/-]+\.md")],
    "cockpit": [re.compile(r"[a-z][a-z0-9-]*\.js"), re.compile(r"test-[a-z0-9-]+\.js"),
                re.compile(r"public/[a-z][a-z0-9-]*\.(js|html|css)")],
}
TOUJOURS_FERMES = {"anamnese": {"jarvis/liste_ouverte.py", "jarvis/liste-ouverte.json", "tests/test_liste_ouverte.py",
                                 # (29/10) le système immunitaire : jamais par un chantier de Hakim
                                 "jarvis/immunite.py", "jarvis/medecin.py", "jarvis/enveloppe.py"},
                   # (29/10) la garde de SendMessage : il n'écrit qu'à SES agents
                   "cockpit": {"sw.js", "public/sw.js", "garde-message.js"}}


def _sans_point(chemin):
    """(relecture finale, M3) retirer le préfixe « ./ », jamais des caractères : « .x.py » n'est pas « x.py »."""
    chemin = str(chemin)
    while chemin.startswith("./"):
        chemin = chemin[2:]
    return chemin


def charger(chemin=None):
    """La liste validée par Ahmed ; absente (une copie publiée du code, sans ses choix) : tout est fermé."""
    try:
        return json.loads(Path(chemin or LISTE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"groupes": []}


def chemins_ouverts(liste):
    return {c for g in liste.get("groupes", []) for f in g.get("fichiers", []) if f.get("etat") == "ouvert"
            for c in f.get("chemins", [])}


def _modules(projet, liste, etat):
    """Les noms de modules (sans extension) ouverts, ou tous ceux du dépôt pour etat='tous'."""
    if etat == "ouvert":
        return {Path(c.split(":", 1)[1]).stem for c in chemins_ouverts(liste) if c.startswith(projet + ":")}
    racine = RACINES[projet]
    motif = ("*.py", "jarvis/*.py") if projet == "anamnese" else ("*.js", "public/*.js")
    return {p.stem for m in motif for p in racine.glob(m)}


def _suit(projet, chemin, liste):
    """Le module que ce test suit, s'il est ouvert (tests/test_<module>[_…].py ; test-<nom>[-…].js)."""
    if projet == "anamnese":
        m = re.fullmatch(r"tests/test_([a-z0-9_]+)\.py", chemin)
        if not m:
            return None
        nom = m.group(1)
        for mod in _modules(projet, liste, "ouvert"):
            for cle in (mod, "jarvis_" + mod):
                if nom == cle or nom.startswith(cle + "_"):
                    return mod
        return None
    m = re.fullmatch(r"test-([a-z0-9-]+)\.js", chemin)
    if not m:
        return None
    nom = m.group(1)
    return next((mod for mod in _modules(projet, liste, "ouvert") if nom == mod or nom.startswith(mod + "-")), None)


# un test EXISTANT qui importe un module fermé reste fermé : il peut vérifier ce module (une garde, la mémoire) ; Hakim
# écrit alors ses tests dans un fichier nouveau, qui suit son module ouvert
def _importe_un_ferme(projet, texte, liste):
    ouverts = _modules(projet, liste, "ouvert")
    if projet == "anamnese":
        noms = set(re.findall(r"^\s*(?:from\s+([a-z_][a-z0-9_]*)|import\s+([a-z_][a-z0-9_]*))", texte or "", re.M))
        noms = {a or b for a, b in noms}
    else:
        noms = set(re.findall(r"require\(\s*['\"]\./(?:public/)?([a-z0-9-]+)\.js['\"]\s*\)", texte or ""))
    du_depot = _modules(projet, liste, "tous")
    return sorted(n for n in noms if n in du_depot and n not in ouverts)


def ouvert(projet, chemin, liste, original=None):
    """Hakim peut-il modifier ce fichier existant (original : son texte, ou None s'il est nouveau) ?"""
    chemin = _sans_point(chemin)
    if projet not in RACINES or chemin in TOUJOURS_FERMES.get(projet, set()):
        return False
    if f"{projet}:{chemin}" in chemins_ouverts(liste):
        return True
    if _suit(projet, chemin, liste):
        return original is None or not _importe_un_ferme(projet, original, liste)
    return False


def _masque(projet, chemin):
    """Un fichier nouveau masquerait-il un module existant (du dépôt, de la bibliothèque standard, des paquets installés) ?"""
    nom = Path(chemin).stem
    if projet == "anamnese":
        if nom in _modules(projet, {}, "tous") or nom in sys.stdlib_module_names:
            return True
        for site in (RACINES["anamnese"] / ".venv" / "lib").glob("python*/site-packages"):
            if (site / nom).exists() or any(site.glob(nom + ".*")):
                return True
        return False
    return nom in _modules(projet, {}, "tous")


def nouveau_permis(projet, chemin):
    chemin = _sans_point(chemin)
    if chemin in TOUJOURS_FERMES.get(projet, set()):
        return False
    if not any(m.fullmatch(chemin) for m in NOUVEAUX.get(projet, [])):
        return False
    if chemin.endswith((".py", ".js")) and not Path(chemin).name.startswith("test"):
        return not _masque(projet, chemin)
    return True


# --- le diff
ENTETES = ("index ", "--- ", "+++ ", "new file mode", "deleted file mode", "old mode", "new mode", "similarity index",
           "dissimilarity index", "rename from", "rename to", "copy from", "copy to", "Binary files", "GIT binary patch")


def _fichiers(patch):
    """[{chemin, nouveau, supprime, special, incompris, morceaux}] ; morceaux : [(debut_orig, [lignes])]. (relecture finale,
    C4) les lignes d'un morceau se lisent d'après les compteurs de l'en-tête @@, comme git : une ligne de contenu qui
    commence par « ++ » ou « -- » reste du contenu ; ce qui n'est pas compris est marqué, et refusé."""
    out, cur = [], None
    lignes = patch.splitlines()
    i = 0
    while i < len(lignes):
        l = lignes[i]
        if l.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+) b/(.+)$", l)
            cur = {"chemin": m.group(2) if m else "?", "nouveau": False, "supprime": False, "special": False,
                   "incompris": not m, "morceaux": []}
            out.append(cur)
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if l.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", l)
            if not m:
                cur["incompris"] = True
                i += 1
                continue
            a = int(m.group(2)) if m.group(2) is not None else 1
            b = int(m.group(4)) if m.group(4) is not None else 1
            morceau = []
            i += 1
            while (a > 0 or b > 0) and i < len(lignes):
                x = lignes[i]
                if x.startswith("\\"):                      # « \ No newline at end of file »
                    i += 1
                    continue
                c = x[:1] if x else " "
                if c == " ":
                    a, b = a - 1, b - 1
                elif c == "-":
                    a -= 1
                elif c == "+":
                    b -= 1
                else:
                    cur["incompris"] = True
                    break
                morceau.append(x if x else " ")
                i += 1
            if a != 0 or b != 0:
                cur["incompris"] = True
            cur["morceaux"].append([int(m.group(1)), morceau])
            continue
        if l.startswith("new file mode"):
            cur["nouveau"] = True
            cur["special"] = cur["special"] or not l.endswith("100644")
        elif l.startswith("deleted file mode"):
            cur["supprime"] = True
        elif l.startswith(("old mode", "new mode", "Binary files", "GIT binary patch", "similarity index", "dissimilarity index",
                           "rename from", "rename to", "copy from", "copy to")):
            cur["special"] = True
        elif not l.startswith(ENTETES):
            cur["incompris"] = True
        i += 1
    return out


BORNE = re.compile(r"(FERME|" + "JAR" + r"NET)-(DEBUT|FIN)\b")


def _blocs(texte):
    """Les blocs fermés d'un fichier : [(premiere_ligne, derniere_ligne)] (numérotées à partir de 1, bornes comprises)."""
    blocs, debut = [], None
    for i, l in enumerate((texte or "").splitlines(), 1):
        m = BORNE.search(l)
        if m and m.group(2) == "DEBUT":
            debut = i
        elif m and debut is not None:
            blocs.append((debut, i))
            debut = None
    return blocs


def _touche_un_bloc(morceaux, blocs):
    for debut, lignes in morceaux:
        n = debut                                      # la ligne d'origine courante
        for l in lignes:
            if l.startswith("-"):
                if any(a <= n <= b for a, b in blocs):
                    return True
                n += 1
            elif l.startswith("+"):
                if any(a < n <= b for a, b in blocs):  # une insertion entre deux lignes d'un bloc
                    return True
            else:
                n += 1
    return False


# --- 3. les appels fermés (dans les lignes AJOUTÉES)
APPELS_PY = [
    (r"\bimport\s+(sqlite3|importlib|subprocess|socket|urllib|requests|http|ctypes|shutil)\b|\bfrom\s+(sqlite3|importlib|subprocess|socket|urllib|requests|http|ctypes|shutil)\b",
     "un module qui touche la base, lance un processus ou ouvre le réseau"),
    (r"__import__\s*\(|(?<![\w.])(exec|eval|compile)\s*\(", "du code construit à l'exécution"),
    (r"\bgetattr\s*\(\s*[^,()]+,\s*(?!\s)(?!['\"][A-Za-z_][A-Za-z0-9_]*['\"]\s*[,)])", "un nom de fonction construit à l'exécution"),
    (r"\b(import|from)\s+(desapprendre|retractation|registre|migrations|run_migration|reclasser|ranger_nuit|rerouter_archives|taxonomy|nettoyer_journaux|liste_ouverte|chantiers|sortie|enveloppe|provenance|fichiers|terminal)\b",
     "un module fermé qui efface, déplace ou garde"),
    (r"\b(desapprendre|retracter|retablir|annuler|migrate|assign_sessions|decay_coactivation)\s*\(", "une fonction qui efface ou réécrit des souvenirs"),
    (r"\b(DELETE\s+FROM|DROP\s+(TABLE|INDEX)|ALTER\s+TABLE|UPDATE\s+\w+\s+SET|INSERT\s+(OR\s+\w+\s+)?INTO|VACUUM)\b|executescript",
     "une écriture directe dans la base"),
    (r"memory\.db|chantiers-prive|liste-ouverte|\.git/|code-interrupteur|journal-off|/avis/", "un fichier fermé nommé en clair"),
    # (relecture finale, I1) un module ouvert importé par un module fermé ne doit pas pouvoir le réécrire
    (r"\bsys\.modules\b|\b(setattr|delattr)\s*\(|\bglobals\s*\(\s*\)|\bvars\s*\(|\bbuiltins\b|__builtins__|__dict__|__class__|"
     r"__code__|__globals__|\bimport\s+inspect\b|\bimport\s+gc\b|\bctypes\b",
     "un outil qui réécrit un autre module"),
    (r"\bfrom\s+jarvis\s+import\b|\bimport\s+jarvis\.", "un module de jarvis importé par son chemin de paquet"),
    (r"\b(import|from)\s+(avis|relances|courrier|maman|daemon|config_prive)\b|\b(avis|relances|courrier|maman)\.\w+\s*\(",
     "un module du code avec maman"),
    (r"\bos\.(remove|unlink|rmdir|removedirs|system|popen|exec\w*|spawn\w*|kill|setuid|chmod)\b|\.unlink\s*\(|\brmtree\b|\.truncate\s*\(",
     "un effacement de fichier ou un processus"),
]
# les tests tournent aussi HORS du bac à sable (la suite d'Ahmed, la mienne) : ils peuvent monter une base temporaire
# (memory, migrations), jamais toucher les vraies données, lancer un processus ou ouvrir le réseau
APPELS_TESTS = [
    (r"\bimport\s+(sqlite3|importlib|subprocess|socket|urllib|requests|http|ctypes|shutil)\b|\bfrom\s+(sqlite3|importlib|subprocess|socket|urllib|requests|http|ctypes|shutil)\b",
     "un module qui lance un processus ou ouvre le réseau"),
    (r"__import__\s*\(|(?<![\w.])(exec|eval|compile)\s*\(", "du code construit à l'exécution"),
    (r"memory\.db|chantiers-prive|liste-ouverte|\.git/|DATA_DIR|Path\.home\(|expanduser|/Users/|AIOS", "un vrai fichier hors du dossier temporaire"),
    (r"CHANTIER_BAC_A_SABLE", "un test qui se comporte autrement dans le bac à sable"),
    # (relecture finale, I5) la suite tourne aussi hors du bac à sable : ni effacement, ni données réelles par __file__
    (r"\.unlink\s*\(|\.truncate\s*\(|__file__|\b(import|from)\s+(avis|relances|courrier|maman)\b|\bsys\.modules\b|\bbuiltins\b",
     "un effacement, un chemin vers le dépôt réel, ou un module du code avec maman"),
    (r"\bos\.(remove|unlink|rmdir|removedirs|system|popen|exec\w*|spawn\w*|kill|setuid|chmod)\b|\brmtree\b", "un effacement ou un processus"),
]
APPELS_JS = [
    (r"child_process|\bexecFile\b|\bexecSync\b|\bspawn\s*\(|\bexec\s*\(", "un processus lancé"),
    (r"\bfs\.(unlink|rm|rmdir|rmSync|unlinkSync|rmdirSync|truncate\w*|chmod\w*)\b", "un effacement de fichier"),
    (r"\beval\s*\(|new\s+Function\s*\(|\bimport\s*\(", "du code construit à l'exécution"),
    (r"\b(exigerPresence\w*|jetonValide|VERROU|auditer|verifierPresence\w*)\s*=(?!=)", "une garde réécrite"),
    (r"require\(\s*['\"]\./(passkey|missions|regles|ecritures|en-off|code)\.js['\"]", "un module fermé"),
    (r"memory\.db|chantiers-prive|liste-ouverte|\.git/", "un fichier fermé nommé en clair"),
    (r"CHANTIER_BAC_A_SABLE", "un code qui se comporte autrement dans le bac à sable"),
    # (relecture finale, I1 et I7) réécrire un autre module, ou installer un service worker qui intercepterait la page fermée
    (r"require\.cache|require\.main|module\.parent|process\.mainModule|process\.binding|process\.dlopen|\bglobalThis\b|"
     r"Object\.(defineProperty|setPrototypeOf)|\.prototype\.\w+\s*=(?!=)|\bnew\s+Proxy\b|\bReflect\.|serviceWorker|"
     r"require\(\s*['\"](vm|worker_threads|inspector|module)['\"]", "un outil qui réécrit un autre module ou intercepte une page"),
]
# les tests du cockpit tournent aussi hors du bac à sable : ni effacement, ni réseau
APPELS_JS_TESTS = [
    (r"\bfs\.promises\b|\brmSync\b|\brm\s*\(|\bunlink\w*\s*\(|require\(\s*['\"](fs/promises|https?|net|tls|dgram|dns)['\"]|"
     r"\bfetch\s*\(|http\.request|https\.request", "un effacement ou une sortie réseau dans un test"),
]


def _attributs_fermes(projet, liste):
    """(relecture finale, I1) « memory.Memory.x = … », « echanges._masquer = … » : réécrire un module fermé depuis un ouvert."""
    fermes = sorted(_modules(projet, liste, "tous") - _modules(projet, liste, "ouvert"))
    return re.compile(r"\b(" + "|".join(map(re.escape, fermes)) + r")(\.\w+)+\s*=(?!=)") if fermes else None


def _appels(projet, lignes, chemin="", liste=None):
    if not chemin.endswith((".py", ".js", ".html")):
        return []                                      # un document : rien ne s'exécute
    if projet == "anamnese":
        motifs = list(APPELS_TESTS if chemin.startswith("tests/") else APPELS_PY)
        attr = _attributs_fermes(projet, liste or {})
        if attr is not None and not chemin.startswith("tests/"):
            motifs.append((attr.pattern, "un module fermé réécrit"))
    else:
        motifs = APPELS_JS + (APPELS_JS_TESTS if Path(chemin).name.startswith("test-") else [])
    out = []
    for l in lignes:
        for m, pourquoi in motifs:
            if re.search(m, l):
                out.append(f"{pourquoi} : « {l.strip()[:100]} »")
                break
    return out


def refus(projet, patch, originaux, liste):
    """Les raisons de refuser ce patch (vide : il passe les trois portes). originaux : {chemin: texte d'origine}."""
    if projet not in RACINES:
        return [f"projet inconnu : {projet}"]
    out = []
    for f in _fichiers(patch):
        c = f["chemin"]
        if f.get("incompris"):
            out.append(f"{c} : une partie du diff n'est pas comprise : refusé")
            continue
        if f["special"]:
            out.append(f"{c} : un mode spécial (lien, exécutable, binaire) n'est jamais permis")
            continue
        if f["nouveau"]:
            if not nouveau_permis(projet, c):
                out.append(f"{c} : un fichier nouveau n'est pas permis ici (ou il masquerait un module existant)")
                continue
        elif not ouvert(projet, c, liste, original=originaux.get(c, "")):
            out.append(f"{c} : fermé (hors de la liste ouverte)")
            continue
        lignes = [l for _d, ls in f["morceaux"] for l in ls]
        code = c.endswith((".py", ".js"))
        if code and sorted(l[1:].strip() for l in lignes if l[:1] == "-" and BORNE.search(l)) != \
                sorted(l[1:].strip() for l in lignes if l[:1] == "+" and BORNE.search(l)):
            out.append(f"{c} : une borne FERME est ajoutée ou retirée")
            continue
        if _touche_un_bloc(f["morceaux"], _blocs(originaux.get(c, ""))):
            out.append(f"{c} : touche un bloc fermé")
            continue
        out += [f"{c} : {r}" for r in _appels(projet, [l[1:] for l in lignes if l.startswith("+")], c, liste)]
    return out


def verifier_depuis_depot(projet, patch_chemin, depot, liste=None):
    """(tâche 5) la même vérification, au moment d'appliquer : les originaux sont lus dans le dépôt (HEAD)."""
    import subprocess
    patch = Path(patch_chemin).read_text(encoding="utf-8")
    originaux = {}
    for f in _fichiers(patch):
        if not f["nouveau"]:
            r = subprocess.run(["git", "-C", str(depot), "show", f"HEAD:{f['chemin']}"], capture_output=True, text=True)
            originaux[f["chemin"]] = r.stdout if r.returncode == 0 else ""
    return refus(projet, patch, originaux, liste or charger())


if __name__ == "__main__":
    # python liste_ouverte.py verifier <projet> <patch> <dépôt> → la liste JSON des refus (le cockpit, au moment du geste)
    if len(sys.argv) == 5 and sys.argv[1] == "verifier":
        print(json.dumps(verifier_depuis_depot(sys.argv[2], sys.argv[3], sys.argv[4]), ensure_ascii=False))
    else:
        print("usage : liste_ouverte.py verifier <projet> <patch> <dépôt>", file=sys.stderr)
        sys.exit(2)
