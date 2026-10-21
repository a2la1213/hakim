"""Moteur GELÉ — wrapper local Ollama (chat + embeddings). 100 % hors-ligne.

Gelé = on ne ré-entraîne jamais ses poids en continu (sinon : oubli
catastrophique). Tout l'apprentissage continu va dans la mémoire externe.
"""
import re
import json
import requests

import config


class Engine:
    def __init__(self, host=config.OLLAMA_HOST,
                 chat_model=config.CHAT_MODEL,
                 embed_model=config.EMBED_MODEL):
        self.host = host.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    def health(self):
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
        url = f"{self.host}/api/chat"
        payload = {"model": self.chat_model, "messages": messages, "stream": stream}
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
