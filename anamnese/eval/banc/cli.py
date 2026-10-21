"""Appels `claude -p` ISOLÉS pour le banc, et lecture des résultats.

Sur l'ABONNEMENT (décision d'Ahmed, 2026-10-16 : « tout gratuit », pas de clé API) : pas de
--bare, qui n'accepte que la clé API. L'isolation vient de --restricted, qui ignore les fichiers
de réglages (donc le hook SessionStart, qui injecterait la mémoire et écrirait dans la vraie
base), d'un dossier de travail VIDE et dédié (aucun CLAUDE.md de projet), de --tools "" (aucun
outil intégré) et de --strict-mcp-config. Vérifié en réel : authentification « none »
(abonnement), aucun outil ni serveur MCP au bras A, base réelle intacte, protocole Anamnèse
absent du contexte. Bras B : serveur MCP sur une COPIE de la base, en lecture seule."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PYTHON = RACINE / ".venv" / "bin" / "python"
CLAUDE_BIN = os.environ.get("ANAMNESE_CLAUDE_BIN", "claude")
OUTILS_LECTURE = ("mcp__anamnese__memory_recall", "mcp__anamnese__reasoning_recall",
                  "mcp__anamnese__facet_search", "mcp__anamnese__self_get")
_CONFIANCE = re.compile(r"confiance\s*:\s*(\d{1,3})", re.I)
_CONFIGS = []
_DOSSIER_VIDE = None


def dossier_vide():
    """Dossier de travail vide et dédié pour `claude -p` (aucun CLAUDE.md ni AGENTS.md à découvrir)."""
    global _DOSSIER_VIDE
    if _DOSSIER_VIDE is None or not _DOSSIER_VIDE.is_dir() or any(_DOSSIER_VIDE.iterdir()):
        _DOSSIER_VIDE = Path(tempfile.mkdtemp(prefix="banc-cwd-"))
    return _DOSSIER_VIDE


def config_mcp(base_copie):
    """Fichier --mcp-config : le serveur Anamnèse lancé sur la copie de la base."""
    conf = {"mcpServers": {"anamnese": {
        "command": str(PYTHON), "args": [str(RACINE / "eval" / "banc" / "mcp_copie.py")],
        "env": {"ANAMNESE_BANC_DB": str(base_copie)}}}}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", prefix="banc-mcp-", delete=False)
    json.dump(conf, f)
    f.close()
    _CONFIGS.append(Path(f.name))
    return Path(f.name)


def nettoyer_configs():
    """Supprime les fichiers --mcp-config créés (ils désignent une copie de données personnelles)."""
    while _CONFIGS:
        _CONFIGS.pop().unlink(missing_ok=True)


def commande(prompt, modele, systeme, base_copie=None, max_turns=8):
    cmd = [CLAUDE_BIN, "-p", prompt, "--restricted", "--model", modele, "--tools", "",
           "--strict-mcp-config", "--system-prompt", systeme, "--output-format", "json", "--max-turns", str(max_turns),
           "--no-session-persistence"]
    if base_copie is not None:
        cmd += ["--mcp-config", str(config_mcp(base_copie)), "--allowedTools", ",".join(OUTILS_LECTURE)]
    return cmd


def executer(cmd, timeout=300):
    """Résultat JSON de la CLI (dict), ou un dict d'erreur."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           cwd=str(dossier_vide()))   # sans stdin fermé, `claude -p` attend 3 s à chaque appel
    except subprocess.TimeoutExpired:
        return {"is_error": True, "subtype": "timeout", "result": "", "total_cost_usd": 0.0}
    sortie = (r.stdout or "").strip()
    for bloc in [sortie] + sortie.splitlines()[::-1]:
        try:
            res = json.loads(bloc)
        except ValueError:
            continue
        if isinstance(res, dict) and res.get("type") == "result":
            return res
    return {"is_error": True, "subtype": "sortie_illisible", "result": (sortie + (r.stderr or ""))[-800:],
            "total_cost_usd": 0.0}


def extraire_confiance(texte):
    m = _CONFIANCE.findall(texte or "")
    return min(100, max(0, int(m[-1]))) if m else None


def extraire_json(texte):
    """Premier bloc JSON (liste ou objet) d'un texte de modèle."""
    for ouvrant, fermant in (("[", "]"), ("{", "}")):
        a, b = (texte or "").find(ouvrant), (texte or "").rfind(fermant)
        if a >= 0 and b > a:
            try:
                return json.loads(texte[a:b + 1])
            except ValueError:
                continue
    return None


def extraire_objet(texte):
    """L'objet JSON {…} d'une réponse de juge (un « [3] » cité dans la justification n'est pas
    une liste à lire : bug relevé par la relecture). None si absent ou pas un objet."""
    t = texte or ""
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(t[a:b + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def verifier_acces():
    """Un appel minimal avant un run : l'abonnement répond (connexion, limite d'usage).
    Sinon arrêt net avec le message de la CLI (au lieu d'un run inutilisable)."""
    res = executer(commande("Réponds : ok", "claude-haiku-5-5", "Réponds en un mot.", max_turns=1), timeout=120)
    if res.get("is_error"):
        raise SystemExit(f"Accès à l'API impossible, run annulé : {str(res.get('result'))[:200]}")
