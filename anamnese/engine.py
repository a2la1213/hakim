"""Moteur GELÉ — chat via Claude Code CLI (abonnement) ou Ollama local ;
embeddings via Ollama (nomic-embed-text).

Gelé = on ne ré-entraîne jamais ses poids en continu (sinon : oubli
catastrophique). Tout l'apprentissage continu va dans la mémoire externe.
Depuis 2026-08-18 : CHAT_MODEL "claude:<alias>" route vers `claude -p`
(même pont éprouvé que dream_sonnet.py) ; tout autre nom reste Ollama.
"""
import re
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests

import config

# (27/10, Ahmed : « on remplace Gemma par Sonnet, même les rêves ») la voie Claude est ISOLÉE : --restricted (ni réglages
# ni hooks de l'utilisateur : le SessionStart ferait décroître sa mémoire de travail), aucun outil, aucun serveur MCP,
# un dossier vide, le forfait (jamais la clé API). Chaque appel est journalisé ; au-delà de CLAUDE_MAX_JOUR appels par
# jour (un emballement, un bug), le modèle de secours (Gemma) prend la main.
CLAUDE = os.environ.get("ANAMNESE_CLAUDE_BIN") or str(Path.home() / ".npm-global" / "bin" / "claude")
JOURNAL_APPELS = config.DATA_DIR / "llm-appels.jsonl"
CLAUDE_MAX_JOUR = int(os.environ.get("ANAMNESE_CLAUDE_MAX_JOUR", "400"))
_appels_du_jour = {"jour": "", "n": 0}


def _journaliser_appel(o):
    try:
        fd = os.open(JOURNAL_APPELS, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as h:
            h.write(json.dumps({"ts": time.time(), **o}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _compter_aujourdhui(jour):
    """Les appels à Claude du jour, relus dans le journal (relecture du 27/10 : un redémarrage du démon remettait le
    compte à zéro)."""
    n = 0
    try:
        with open(JOURNAL_APPELS, encoding="utf-8") as h:
            for l in h:
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if time.strftime("%Y-%m-%d", time.localtime(o.get("ts", 0))) == jour and not str(o.get("modele", "")).startswith("gemma"):
                    n += 1
    except OSError:
        pass
    return n


def _plafond_atteint():
    jour = time.strftime("%Y-%m-%d")
    if _appels_du_jour["jour"] != jour:
        _appels_du_jour.update(jour=jour, n=_compter_aujourdhui(jour))
    return _appels_du_jour["n"] >= CLAUDE_MAX_JOUR


class Engine:
    def __init__(self, host=config.OLLAMA_HOST,
                 chat_model=config.CHAT_MODEL,
                 embed_model=config.EMBED_MODEL,
                 secours_model=None):
        self.host = host.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.secours_model = secours_model      # Ollama, quand la voie Claude échoue ou a atteint son plafond
        self.dernier = None                     # « sonnet », « gemma »… : qui a répondu au dernier appel

    def health(self):
        if self.chat_model.startswith("claude"):
            return True                         # la voie Claude ne dépend pas d'Ollama (l'échec retombe sur le secours)
        try:
            return requests.get(f"{self.host}/api/tags", timeout=3).ok
        except requests.RequestException:
            return False

    def chat(self, messages, stream=True, think=False):
        """messages : [{'role', 'content'}]. Retourne le texte complet.

        think=False : désactive le mode « thinking » des modèles type Qwen3.5
        (sinon ils crachent un long raisonnement <think>… qui pollue la sortie
        et explose le temps de génération). Mettre think=None pour laisser le
        défaut du modèle.
        """
        if self.chat_model.startswith("claude"):
            if not (self.secours_model and _plafond_atteint()):
                try:
                    return self._chat_claude(messages, stream=stream)
                except requests.RequestException:
                    if not self.secours_model:
                        raise
            texte = self._chat_ollama(messages, stream, think, self.secours_model)
            _journaliser_appel({"modele": "gemma (secours)", "entree_car": sum(len(m["content"]) for m in messages),
                                "sortie_car": len(texte or ""), "erreur": None})
            return texte
        return self._chat_ollama(messages, stream, think, self.chat_model)

    def _chat_ollama(self, messages, stream, think, modele):
        self.dernier = "gemma" if "gemma" in str(modele).lower() else str(modele)
        url = f"{self.host}/api/chat"
        payload = {"model": modele, "messages": messages, "stream": stream}
        if think is not None:
            payload["think"] = think
        if not stream:
            r = requests.post(url, json=payload, timeout=config.LLM_TIMEOUT)
            r.raise_for_status()
            return r.json()["message"]["content"]
        text = ""
        with requests.post(url, json=payload, stream=True, timeout=config.LLM_TIMEOUT) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("message", {}).get("content", "")
                print(piece, end="", flush=True)
                text += piece
                if chunk.get("done"):
                    break
        print()
        return text

    def _chat_claude(self, messages, stream=True):
        """Voie Claude Code CLI (abonnement, sans clé API), pont de dream_sonnet.

        chat_model "claude:<alias>" → `claude -p --model <alias>`. Aucun outil
        (--allowedTools "") : génération pure, comme la voie Ollama. En échec,
        lève requests.RequestException pour conserver le contrat d'erreur des
        appelants (rate_importance, daemon, loop).
        """
        alias = self.chat_model.split(":", 1)[1] if ":" in self.chat_model else "sonnet"
        parts = [m["content"] if m.get("role") == "system"
                 else f"[{m.get('role', 'user')}] {m['content']}" for m in messages]
        prompt = "\n\n".join(parts)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}   # le forfait, jamais l'API payante
        env["ANAMNESE_HEADLESS"] = "1"
        debut, trace = time.monotonic(), {"modele": alias, "entree_car": len(prompt)}
        _appels_du_jour["n"] += 1
        try:
            with tempfile.TemporaryDirectory(prefix="tete-de-fond-") as vide:
                r = subprocess.run(
                    [CLAUDE, "-p", prompt, "--model", alias, "--restricted", "--tools", "", "--strict-mcp-config",
                     "--no-session-persistence", "--max-turns", "1", "--output-format", "json"],
                    capture_output=True, text=True, timeout=config.LLM_TIMEOUT, cwd=vide, env=env,
                    stdin=subprocess.DEVNULL)
            o = json.loads(r.stdout or "{}")
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            _journaliser_appel({**trace, "erreur": type(e).__name__, "duree_s": round(time.monotonic() - debut, 1)})
            raise requests.RequestException(f"claude CLI : {e}")
        text = str(o.get("result") or "").strip()
        erreur = r.returncode != 0 or bool(o.get("is_error")) or not text or text.startswith("API Error")
        _journaliser_appel({**trace, "sortie_car": len(text), "cout_usd": o.get("total_cost_usd"),
                            "duree_s": round(time.monotonic() - debut, 1), "erreur": text[:120] if erreur else None})
        if erreur:
            raise requests.RequestException(f"claude CLI rc={r.returncode} : {text[:200] or (r.stderr or '')[:200]}")
        self.dernier = alias
        if stream:
            print(text)
        return text

    def embed(self, text):
        """Vecteur d'embedding (list[float])."""
        r = requests.post(f"{self.host}/api/embeddings",
                          json={"model": self.embed_model, "prompt": text},
                          timeout=60)
        r.raise_for_status()
        return r.json()["embedding"]

    def rate_importance(self, text):
        """Note 0..1 la mémorabilité (à la Generative Agents, Stanford)."""
        prompt = ("Sur une échelle de 0 à 10, évalue l'importance de cet énoncé "
                  "pour une mémoire à long terme (0 = trivial, 10 = crucial). "
                  "Réponds UNIQUEMENT par un nombre.\n\nÉnoncé : " + text)
        try:
            out = self.chat([{"role": "user", "content": prompt}], stream=False)
            m = re.search(r"\d+", out)
            val = int(m.group()) if m else 5
            return max(0.0, min(1.0, val / 10.0))
        except (requests.RequestException, ValueError, KeyError):
            return 0.5
