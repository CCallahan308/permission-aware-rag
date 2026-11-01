import threading
from typing import TYPE_CHECKING, List
from app.config import settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

_model_instance = None
_model_lock = threading.Lock()

def get_embedding_model() -> "TextEmbedding":
    global _model_instance
    with _model_lock:
        if _model_instance is None:
            # Tests replace embeddings without loading ONNX or downloading a model.
            from fastembed import TextEmbedding
            _model_instance = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
    return _model_instance

def embed_text(text: str) -> List[float]:
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    vec = embeddings[0]
    # Ensure float list
    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    return [float(x) for x in vec]

def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    output = []
    for vec in embeddings:
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        output.append([float(x) for x in vec])
    return output
