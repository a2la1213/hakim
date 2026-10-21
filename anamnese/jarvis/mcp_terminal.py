"""Serveur MCP « terminal » de Jarvis : un vrai shell (zsh) dans son atelier, avec internet (par une
passerelle qui refuse toute adresse locale ou privée) et le GPU, mais sans accès aux projets, aux clés
ni au reste du dossier d'Ahmed (jarvis/terminal.py). Les outils sont asynchrones : une commande longue
ne bloque pas le serveur."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP  # noqa: E402

import chantiers  # noqa: E402
import groupes  # noqa: E402
import recettes  # noqa: E402
import taches  # noqa: E402
import terminal  # noqa: E402

mcp = FastMCP("terminal")
# Relecture Opus du 2026-10-20 : les chantiers permettaient de sortir du bac à sable (configuration git écrite
# depuis l'atelier, profil des tests suivi par lien symbolique). Suspendus jusqu'à leur correction relue.
# Corrigés et relus ; réactivés par Ahmed le 2026-10-20 (« oui à tous »). Pour les suspendre à nouveau : y remettre une raison.
CHANTIERS_SUSPENDUS = ""


@mcp.tool()
async def executer(commande: str, delai_s: int = 120, arriere_plan: bool = False) -> str:
    """Exécute une commande dans TON terminal (zsh), dans ton atelier persistant
    (~/AIOS/jarvis/cwd/atelier, lisible ensuite avec Read). Tu as : internet (curl, git clone,
    pip/uv install, téléchargement de jeux de données ou de modèles), le GPU Apple (MLX / Metal),
    Python (numpy, scipy, sympy, mlx ; crée un venv dans l'atelier pour d'autres paquets), ffmpeg.
    Les fichiers qu'Ahmed t'a joints ou que tu as préparés sont lisibles dans ../fichiers.
    Interdit par le bac à sable : ses projets, ses clés et le reste de son dossier personnel,
    toute adresse locale ou privée (cockpit, Ollama, réseau de la maison), toute écriture hors de
    l'atelier. Chaque appel est un nouveau shell : enchaîne avec && ou utilise des chemins absolus.
    delai_s : de 1 à 1800 s (120 par défaut) ; mémoire 6 Go, atelier 5 Go au plus.
    arriere_plan=True pour TOUT ce qui peut durer plus de ~30 s (gros calcul, téléchargement,
    entraînement, compilation) : la commande devient une tâche de fond, tu reçois son numéro tout de suite
    et tu continues de parler avec Ahmed ; elle tourne jusqu'à 4 h (delai_s), survit à un Stop, et Ahmed
    est prévenu quand elle se termine. Suis-la avec suivre_tache, arrête-la avec arreter_tache."""
    try:
        if arriere_plan:
            tid = await asyncio.to_thread(taches.lancer, commande, delai_s if delai_s and delai_s != 120 else 3600)
            sortie = (f"Tâche de fond {tid} lancée (journal : {taches.DOSSIER / (tid + '.log')}). Elle tourne pendant "
                      f"que tu parles avec Ahmed ; suivre_tache('{tid}') pour voir où elle en est. Ahmed sera prévenu "
                      "quand elle finira, et tu verras son résultat dans le bloc [Tâches] de son prochain message.")
        else:
            sortie = await asyncio.to_thread(terminal.executer, commande, delai_s)
        alerte = await asyncio.to_thread(terminal.alerte_atelier)
        return f"{sortie}\n{alerte}" if alerte else sortie
    except taches.Refus as e:
        return f"Tâche refusée : {e}"
    except Exception as e:
        return f"Exécution impossible : {type(e).__name__}: {e}"[:400]


@mcp.tool()
def suivre_tache(tache: str, lignes: int = 30) -> str:
    """Où en est une tâche de fond (état, durée, code de retour, fin de son journal)."""
    e = taches.etat(tache)
    return taches.resume(e, lignes=max(1, min(int(lignes or 30), 300))) if e else f"Tâche inconnue : {tache}"


@mcp.tool()
def lister_taches() -> str:
    """Tes tâches de fond récentes (en cours, finies, arrêtées)."""
    t = taches.lister(n=12)
    return "\n".join(taches.resume(e, lignes=0).split("\n")[0] for e in t) if t else "Aucune tâche de fond."


@mcp.tool()
def arreter_tache(tache: str) -> str:
    """Arrête une tâche de fond (son groupe de processus entier)."""
    return f"Arrêt demandé pour {tache}." if taches.arreter(tache) else f"{tache} n'est pas en cours."


@mcp.tool()
def ouvrir_chantier(nom: str, projet: str = "anamnese") -> str:
    """Toucher à TON propre code sans danger : une COPIE du projet (anamnese) dans ton atelier, sur une branche
    hakim/<nom>. Tu la modifies avec ton terminal (chemins absolus) ; l'original n'est jamais touché, ta
    mémoire n'est pas copiée. Ensuite : tester_chantier, puis proposer_promotion. nom : minuscules et tirets."""
    if CHANTIERS_SUSPENDUS:
        return f"Suspendu : {CHANTIERS_SUSPENDUS}."
    try:
        c = chantiers.ouvrir(nom, projet)
        return f"Chantier prêt : {c} (branche hakim/{nom}). Modifie-le avec ton terminal, puis tester_chantier('{nom}')."
    except chantiers.Refus as e:
        return f"Refusé : {e}"


@mcp.tool()
def tester_chantier(nom: str) -> str:
    """Lance la suite de tests du projet dans ta copie, en arrière-plan (1 à 2 min), sous bac à sable : écriture
    seulement dans la copie, aucun réseau, ni la vraie mémoire ni les clés. Résultat : etat_chantier."""
    if CHANTIERS_SUSPENDUS:
        return f"Suspendu : {CHANTIERS_SUSPENDUS}."
    try:
        chantiers.lancer_tests(nom)
        return f"Tests lancés pour {nom} (1 à 2 min). Tu restes disponible ; etat_chantier('{nom}') pour le résultat."
    except chantiers.Refus as e:
        return f"Refusé : {e}"


@mcp.tool()
def etat_chantier(nom: str) -> str:
    """Les changements de ta copie et le résultat de ses derniers tests."""
    if CHANTIERS_SUSPENDUS:
        return f"Suspendu : {CHANTIERS_SUSPENDUS}."
    try:
        return chantiers.etat(nom)
    except chantiers.Refus as e:
        return f"Refusé : {e}"


@mcp.tool()
def proposer_promotion(nom: str, resume: str) -> str:
    """Propose à Ahmed d'intégrer ton chantier : le patch, le résultat des tests (à jour), les fichiers touchés,
    ceux du CŒUR signalés (identité, mémoire, gardes…). Rien n'est appliqué : Ahmed décide (ou Claude Code avec
    son accord), en commit à part, réversible. resume : ce que ça change et pourquoi, en quelques phrases."""
    if CHANTIERS_SUSPENDUS:
        return f"Suspendu : {CHANTIERS_SUSPENDUS}."
    try:
        f = chantiers.proposer(nom, resume)
        import json as _j
        d = _j.loads(f.read_text(encoding="utf-8"))
        return (f"Promotion {d['id']} proposée à Ahmed : {len(d['fichiers'])} fichier(s), tests "
                f"{'réussis' if d['tests_ok'] else 'EN ÉCHEC'}" + (f", touche au CŒUR ({', '.join(d['coeur'])})" if d['coeur'] else "")
                + ". Dis-lui en une phrase ce que tu proposes ; il décide.")
    except chantiers.Refus as e:
        return f"Refusé : {e}"


# ---- Les recettes de calcul (demande de Hakim, 2026-10-20, accord d'Ahmed) : jarvis/recettes.py ----
@mcp.tool()
async def recette_sauver(nom: str, commande: str, description: str = "", parametres: dict | None = None) -> str:
    """Sauver une chaîne de calcul qui a marché sous un NOM, pour la relancer en une phrase. `commande` : la chaîne
    entière (zsh, enchaînée par &&, exécutée dans ton atelier) avec des paramètres entre accolades, ex.
    "cd maths/qc && python cellules.py --n {n} && python lumiere.py --fenetre {fenetre}" ; `parametres` : leurs
    valeurs par défaut, ex. {"n": "24", "fenetre": "0.5"}. Rangée dans atelier/recettes/<nom>.json."""
    try:
        r, manquants = recettes.sauver(nom, commande, description, parametres)
    except recettes.Refus as e:
        return f"Refusé : {e}"
    return (f"Recette « {r['nom']} » sauvée." + (f" Sans valeur par défaut : {', '.join(manquants)} (à donner au lancement)." if manquants else "")
            + f" Relance-la avec recette_lancer('{r['nom']}', {{…}}).")


@mcp.tool()
async def recette_lancer(nom: str, params: dict | None = None, delai_s: int = 3600) -> str:
    """Relancer une recette en TÂCHE DE FOND avec d'autres paramètres (les autres gardent leur valeur par défaut).
    Ahmed est prévenu à la fin, et tu es réveillé pour lui en dire le résultat."""
    try:
        tid, commande = await asyncio.to_thread(recettes.lancer, nom, params or {}, max(60, min(int(delai_s or 3600), 4 * 3600)))
    except (recettes.Refus, taches.Refus) as e:
        return f"Refusé : {e}"
    alerte = await asyncio.to_thread(terminal.alerte_atelier)
    return f"Recette « {nom} » lancée en tâche de fond {tid} : {commande[:300]}" + (f"\n{alerte}" if alerte else "")


@mcp.tool()
async def recettes_liste() -> str:
    """Tes recettes de calcul : nom, description, paramètres par défaut, nombre de lancements."""
    return recettes.liste()


# (audit JARVIS 2, point B, 2026-10-20) TOUJOURS à la fin : mcp.run() ne rend pas la main — un outil déclaré après
# n'existait pas pour Hakim (les recettes étaient invisibles).
if __name__ == "__main__":
    groupes.installer_arret()            # le cockpit coupe Jarvis : ses commandes en cours meurent aussi
    mcp.run()
