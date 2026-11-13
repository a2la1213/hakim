"""Les commandes du cerveau de départ : python -m naissance.cerveau <commande> (depuis le dossier anamnese).

Dans l'ordre, sur le PC du papa (WSL2) :
  profils                                   les profils Windows vus depuis WSL (/mnt/c/Users)
  aspirer --profil /mnt/c/Users/<nom>       lecture seule des dossiers par défaut (ou --dossier Étiquette=chemin, répétable)
  distiller [--papa "Prénom Nom"]           Claude distille un échantillon (filtre d'identité sur le fil) → propositions.json
  relire                                    la page de relecture (http://localhost:4480/?jeton=…) ; rien n'est appris sans « oui »
  naitre --papa "Prénom"                    le premier réveil : l'IA choisit son nom
Sur le Mac d'Ahmed :
  heritage-exporter                         savoir-faire de Hakim → data/naissance/heritage-hakim.json (à relire)
  heritage-approuver <fichier>              Ahmed a relu : l'empreinte est scellée
Chez la nouvelle IA :
  heritage-importer <fichier>               ses compétences et traces héritées (refusé si non approuvé)
"""
import argparse
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
for _p in (str(ICI), str(RACINE_DEPOT), str(RACINE_DEPOT / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

SORTIE = RACINE_DEPOT / "data" / "naissance"


def _memoire(a):
    if a.memoire:
        return Path(a.memoire)
    import config
    return config.DB_PATH


def _juge(a):
    import garde_secrets
    if a.juge == "aucun":
        return None
    modele = a.juge.split(":", 1)[1] if a.juge.startswith("ollama:") else "qwen2.5:1.5b"
    j = garde_secrets.juge_ollama(modele=modele)
    try:                                                     # Ollama joignable ? Sinon : prudence (exclusion)
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).read()
        return j
    except Exception:
        print("(pas de modèle local joignable : les fichiers douteux seront mis de côté par prudence)", file=sys.stderr)
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m naissance.cerveau", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sortie", default=str(SORTIE), help="dossier de la naissance (inventaire, propositions…)")
    ap.add_argument("--memoire", default=None, help="la base de mémoire de la NOUVELLE IA (défaut : data/memory.db)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("profils")
    p = sp.add_parser("aspirer")
    p.add_argument("--profil")
    p.add_argument("--dossier", action="append", default=[], help="Étiquette=chemin (répétable)")
    p.add_argument("--juge", default="ollama", help="ollama[:modèle] ou aucun (doute → prudence)")
    p.add_argument("--budget", type=float, default=None, help="secondes au plus (reprenable)")
    p.add_argument("--decrire", action="store_true", help="décrire les photos (option coûteuse, envoie les images)")
    p = sp.add_parser("distiller")
    p.add_argument("--papa", action="append", default=[])
    p.add_argument("--proche", action="append", default=[])
    p.add_argument("--modele", default="opus")
    p.add_argument("--max-fichiers", type=int, default=60)
    p = sp.add_parser("relire")
    p.add_argument("--port", type=int, default=4480)
    sp.add_parser("importer")
    p = sp.add_parser("naitre")
    p.add_argument("--papa", required=True)
    p.add_argument("--modele", default="opus")
    p = sp.add_parser("chercher")
    p.add_argument("question")
    p = sp.add_parser("heritage-exporter")
    p.add_argument("--memoire-hakim", default=str(RACINE_DEPOT / "data" / "memory.db"))
    p = sp.add_parser("heritage-approuver")
    p.add_argument("fichier")
    p = sp.add_parser("heritage-importer")
    p.add_argument("fichier")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie)

    if a.cmd == "profils":
        import aspiration
        for pr in aspiration.profils_windows():
            print(pr, "→", ", ".join(f"{e} ({c})" for e, c in aspiration.dossiers_par_defaut(pr)))
    elif a.cmd == "aspirer":
        import aspiration
        racines = [tuple(d.split("=", 1)) for d in a.dossier if "=" in d]
        if a.profil:
            racines += aspiration.dossiers_par_defaut(a.profil)
        if not racines:
            ap.error("donner --profil ou --dossier")
        import relecture
        decrire = None
        if a.decrire:
            import distillation
            print("(option --decrire : chaque photo décrite part chez Anthropic ; 200 photos au plus)", file=sys.stderr)
            decrire = distillation.decrire_photo
        r = aspiration.aspirer(racines, sortie, juge=_juge(a), reintegres=relecture.reintegres(sortie), budget_s=a.budget,
                               decrire=decrire, journal=lambda m: print(m, flush=True))
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a.cmd == "distiller":
        import distillation
        r = distillation.distiller(sortie, papa_noms=a.papa, proches=a.proche, modele=a.modele, max_fichiers=a.max_fichiers,
                                   journal=lambda m: print(m, flush=True))
        print(f"{len(r['propositions'])} souvenirs proposés (+ son « soi ») à partir de {r['fichiers_lus']} fichiers lus. "
              f"Prochaine étape : python -m naissance.cerveau relire")
    elif a.cmd == "relire":
        import relecture
        relecture.servir(sortie, _memoire(a), port=a.port)
    elif a.cmd == "importer":
        import relecture
        print(json.dumps(relecture.importer(sortie, _memoire(a)), ensure_ascii=False))
    elif a.cmd == "naitre":
        import distillation
        import filtre
        import naitre
        f = filtre.Filtre.charger(sortie / "filtre-identite.json")
        r = naitre.naitre(_memoire(a), lambda p: distillation.appeler_claude(p, modele=a.modele), a.papa, sortie=sortie, filtre=f)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        if r.get("nom") and not r.get("deja_ne"):
            print(naitre.appliquer_nom(r["nom"], a.papa))
    elif a.cmd == "chercher":
        import aspiration
        for x in aspiration.chercher(sortie, a.question):
            print(f"{x['score']:.2f}  {x['affiche']}")
    elif a.cmd == "heritage-exporter":
        import heritage
        bilan, chemin = heritage.exporter(a.memoire_hakim, sortie)
        print(json.dumps(bilan, ensure_ascii=False, indent=1))
        print(f"À relire par Ahmed : {chemin}")
    elif a.cmd == "heritage-approuver":
        import heritage
        print(json.dumps(heritage.approuver(a.fichier), ensure_ascii=False))
    elif a.cmd == "heritage-importer":
        import heritage
        print(json.dumps(heritage.importer(a.fichier, _memoire(a)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
