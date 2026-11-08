"""Embeddings AUTONOMES via model2vec (statique, CPU, multilingue).

Remplace Ollama pour le MCP : aucun serveur externe, aucun onnxruntime.
Le modèle (potion-multilingual-128M, 256-dim) se charge à la 1re utilisation et
est mis en cache par HuggingFace.
"""
import config

_model = None


def _get():
    global _model
    if _model is None:
        from model2vec import StaticModel
        _model = StaticModel.from_pretrained(config.EMBED_MODEL_M2V)
    return _model


def embed(text):
    """Retourne un vecteur (list[float]) pour `text`."""
    vec = _get().encode([text])[0]
    return [float(x) for x in vec]
