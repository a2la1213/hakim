"""Le cerveau local de Hakim sur MLX (lot D, accord d'Ahmed le 2026-10-20) : le dernier recours quand le forfait
Claude et l'API sont indisponibles. Avant : Gemma par Ollama, 204 s avant le premier mot (mesure du 18/10, le
Mac swappait). Mesures du 20/10 : voir MODELE ci-dessous.

Parlé par le cockpit sur stdin/stdout (aucun port réseau), une requête JSON par ligne :
  → {"id": 1, "messages": [{"role": "system"|"user"|"assistant", "content": "…"}], "max_tokens": 600}
  ← {"id": 1, "x": "morceau"} … puis {"id": 1, "fin": true, "jetons_s": 11.2}
  → {"stop": 1}  (Ahmed a coupé : la génération s'arrête au jeton suivant)
Il s'arrête seul après 10 min sans requête (il rend ses ~7 Go au Mac) ; le cockpit le relance au besoin.
"""
import json
import os
import queue
import sys
import threading
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
# Essais du 2026-10-20 (modèles déjà sur le disque, aucun téléchargement) : Gemma 4 12B « agentic » en MLX laissait
# passer ses jetons de pensée (« <|channel>thought », « <image|> ») ; Qwen3 8B en 4 bits, pensée coupée : prêt en 2 s,
# premier mot en 1,6 s, 20 jetons/s, un français propre. Réglable par JARVIS_MLX_MODELE.
MODELE = os.environ.get("JARVIS_MLX_MODELE", "mlx-community/Qwen3-8B-4bit")
REPOS_S = int(os.environ.get("JARVIS_MLX_REPOS_S", "600"))


def ecrire(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    from mlx_lm import load, stream_generate
    t = time.time()
    modele, tok = load(MODELE)
    ecrire({"pret": True, "charge_s": round(time.time() - t, 1), "modele": MODELE})
    demandes, arrets = queue.Queue(), set()

    def lire():
        for ligne in sys.stdin:
            try:
                o = json.loads(ligne)
            except ValueError:
                continue
            if "stop" in o:
                arrets.add(o["stop"])
            else:
                demandes.put(o)
        demandes.put(None)
    threading.Thread(target=lire, daemon=True).start()

    while True:
        try:
            d = demandes.get(timeout=REPOS_S)
        except queue.Empty:
            return                                          # au repos : il rend la mémoire
        if d is None:
            return
        i = d.get("id")
        try:
            try:
                prompt = tok.apply_chat_template(d["messages"], add_generation_prompt=True, enable_thinking=False)
            except TypeError:
                prompt = tok.apply_chat_template(d["messages"], add_generation_prompt=True)
            dernier = None
            for r in stream_generate(modele, tok, prompt=prompt, max_tokens=int(d.get("max_tokens") or 600)):
                if i in arrets:
                    break
                if r.text:
                    ecrire({"id": i, "x": r.text})
                dernier = r
            ecrire({"id": i, "fin": True, "jetons_s": round(getattr(dernier, "generation_tps", 0.0) or 0.0, 1)})
        except Exception as e:                              # noqa: BLE001 — l'erreur est dite au cockpit
            ecrire({"id": i, "erreur": f"{type(e).__name__}: {e}"[:300]})
        arrets.discard(i)


if __name__ == "__main__":
    main()
