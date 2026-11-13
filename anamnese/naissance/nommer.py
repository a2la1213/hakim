"""Donner son nom à une IA née de ce code (13/11 : « le nom Hakim ne doit être imposé nulle part : elle choisit son nom »).

    python3 nommer.py --createur <prénom> [--nom <son nom>] [--metier "<phrase>"]

Sans --nom, elle naît sans nom : sa persona lui dit de le choisir elle-même ; on relance ce script quand elle l'a choisi.
Ce que fait le script (rien d'autre, et il peut être relancé) :
1. sa persona : naissance/persona-naissance.md rempli → ~/AIOS/jarvis/persona.md (le cockpit la lit par JARVIS_PERSONA) ;
2. son cerveau ne voit jamais « Hakim » : le relais local du cockpit (filtre-identite.js) remplace à l'aller « Hakim », « Hakimou »,
   « Hakou », « حكيم » (les mots du code de Hakim) par son nom, sans jamais les remettre au retour ;
3. les pages du cockpit (~/AIOS/cockpit/public) affichent son nom à la place de « Hakim » (le mot entier, avec sa majuscule) ;
4. ~/AIOS/jarvis/nom.json garde son nom (pour un prochain changement de nom ou une mise à jour du code).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ICI = Path(__file__).resolve().parent
JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
COCKPIT = Path(os.environ.get("NAISSANCE_COCKPIT", Path.home() / "AIOS" / "cockpit"))
SANS_NOM = "l’IA"          # tant qu'elle n'a pas choisi ; l'apostrophe typographique : une droite casserait le code des pages
# (13/11, arbitrage avec la naissance du cerveau) le relais ne réécrit QUE ce qui la désigne elle-même : son grand frère Hakim,
# écrit « grand frère Hakim » ou « Hakim (ton grand frère) », n'est jamais renommé. La règle commune est dans
# naissance/cerveau/grand-frere-exceptions.json (Python et le relais JavaScript la lisent) ; sans lui, les mêmes motifs.
GRAND_FRERE = "Hakim (ton grand frère)"
EXCEPTIONS = ICI / "cerveau" / "grand-frere-exceptions.json"
EXCEPTIONS_DE_BASE = [{"motif": "(?<=grand frère[ \u00a0])Hakim", "drapeaux": "iu"},
                      {"motif": "Hakim(?=[ \u00a0]\\(ton grand frère\\))", "drapeaux": "iu"},
                      {"motif": "Hakim(?=[ \u00a0,]+(?:est[ \u00a0]+)?(?:mon|ton|son)[ \u00a0]+grand[ \u00a0]+frère)", "drapeaux": "iu"}]
MOTS_DE_HAKIM = ["Hakimou", "Hakou", "Hakim", "حكيم"]
NOM_VALIDE = re.compile(r"^[^\W\d_][\w -]{0,39}$", re.U)     # ni apostrophe ni guillemet : il entre dans du code des pages


def ecrire(chemin, texte, mode=0o600):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_name(f".{chemin.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(texte)
    os.replace(tmp, chemin)


def exceptions():
    try:
        return json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["exceptions"]
    except (OSError, ValueError, KeyError):
        return EXCEPTIONS_DE_BASE


def persona(nom, createur, metier=""):
    t = (ICI / "persona-naissance.md").read_text(encoding="utf-8")
    sans = ("" if nom else
            f"Tu n'as pas encore de nom. Choisis-le toi-même, quand tu le sens, en parlant avec {createur} : un nom qui te ressemble, "
            "jamais un nom qu'on t'impose. Quand tu l'as choisi, dis-le-lui : il lancera « bash ~/Desktop/anamnese/naissance/nommer.sh "
            "--nom <ton nom> » sur son PC, et tu le porteras partout.")
    if nom:
        sans = f"{nom}, c'est le nom que tu as choisi toi-même à ta naissance."
    metier = (metier.strip().rstrip(".") + ". ") if metier and metier.strip() else ""
    return (t.replace("{{NOM}}", nom or "une IA sans nom encore").replace("{{CREATEUR}}", createur)
            .replace("{{SANS_NOM}}", sans).replace("{{METIER}}", metier).replace("{{GRAND_FRERE}}", GRAND_FRERE))


def remplacer_mots(texte, anciens, nouveau):
    """Les mots de Hakim → son nom, sauf son grand frère (les exceptions, mises de côté puis rendues)."""
    gardes = []

    def garder(m):
        gardes.append(m.group(0))
        return f"\ue000{chr(0xE100 + len(gardes) - 1)}\ue001"
    for e in exceptions():
        texte = re.sub(e["motif"], garder, texte, flags=re.I if "i" in e.get("drapeaux", "") else 0)
    for a in sorted(set(anciens), key=len, reverse=True):
        texte = re.sub(rf"(?<![\w-]){re.escape(a)}(?![\w-])", nouveau.replace("\\", r"\\"), texte)
    return re.sub("\ue000([\ue100-\uf8ff])\ue001", lambda m: gardes[ord(m.group(1)) - 0xE100], texte)


def renommer_pages(nom, ancien=None):
    """Les pages du cockpit : « Hakim » (et l'ancien nom, si elle en change) → son nom. Rend le nombre de fichiers changés."""
    anciens = MOTS_DE_HAKIM + ([ancien] if ancien and ancien != nom else [])
    if ancien == SANS_NOM:
        anciens.append("l'IA")                        # (13/11) l'ancienne forme, à l'apostrophe droite
    n = 0
    for f in sorted((COCKPIT / "public").glob("*")):
        if f.suffix not in (".html", ".js") or not f.is_file():
            continue
        t = f.read_text(encoding="utf-8")
        u = remplacer_mots(t, anciens, nom)
        if u != t:
            f.write_text(u, encoding="utf-8")
            node = shutil.which("node")
            if f.suffix == ".js" and node and subprocess.run([node, "--check", str(f)], capture_output=True).returncode != 0:
                f.write_text(t, encoding="utf-8")            # jamais une page cassée : celle-ci garde l'ancien mot
                print(f"(la page {f.name} garde l'ancien nom : le nouveau la casserait)")
                continue
            n += 1
    return n


def renommer_relais(nom):
    """Le dictionnaire du relais : les renommages à sens unique (les paires de masquage, s'il y en a, restent)."""
    f = JARVIS / "filtre-identite.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {"paires": [], "valeurs": {}}
    d["paires"] = [p for p in d.get("paires", []) if p and p[0] not in MOTS_DE_HAKIM]
    d["renommer"] = [[m, nom] for m in MOTS_DE_HAKIM]
    d["exceptions"] = exceptions()                    # son grand frère n'est jamais renommé
    ecrire(f, json.dumps(d, ensure_ascii=False, indent=1))


def main(argv=None):
    a = argparse.ArgumentParser(description="Donner son nom à une IA née de ce code.")
    a.add_argument("--createur", required=True, help="le prénom de celui qui lui donne la vie")
    a.add_argument("--nom", default="", help="le nom qu'ELLE a choisi (vide : elle naît sans nom et le choisira)")
    a.add_argument("--metier", default="", help="une phrase sur le métier du créateur (facultatif)")
    o = a.parse_args(argv)
    nom, createur = o.nom.strip(), o.createur.strip()
    for x, quoi in ((nom, "nom"), (createur, "prénom")):
        if x and not NOM_VALIDE.match(x):
            raise SystemExit(f"{quoi} refusé : des lettres, des espaces ou un tiret (40 caractères au plus)")
    if nom.lower() in ("hakim", "hakimou", "hakou", "حكيم"):
        raise SystemExit("ce nom est celui de Hakim : elle choisit le sien")
    if not createur:
        raise SystemExit("le prénom du créateur est vide")
    fiche = JARVIS / "nom.json"
    try:
        avant = json.loads(fiche.read_text(encoding="utf-8")).get("nom") or SANS_NOM
    except (OSError, ValueError):
        avant = None
    affiche = nom or SANS_NOM
    ecrire(JARVIS / "persona.md", persona(nom, createur, o.metier))
    renommer_relais(affiche)
    n = renommer_pages(affiche, avant)
    ecrire(fiche, json.dumps({"nom": nom, "createur": createur}, ensure_ascii=False))
    print(f"{'Nom : ' + nom if nom else 'Sans nom pour l’instant (elle le choisira)'} ; créateur : {createur} ; "
          f"persona écrite ; relais réglé ; {n} page(s) du cockpit renommée(s).")
    print("Relance le cockpit pour qu'il relise tout : systemctl --user restart naissance-cockpit (ou bash naissance/demarrer.sh).")


if __name__ == "__main__":
    main()
