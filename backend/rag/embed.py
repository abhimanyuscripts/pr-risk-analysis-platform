"""Phase 13: turn text into meaning vectors, locally and for free.

all-MiniLM-L6-v2 is a small open-source sentence-embedding model (about 90 MB,
384 numbers per text). It runs on the laptop's CPU, so RAG never calls an
outside service. Vectors are normalised to length 1, so cosine distance is a
fair "how different in meaning" measure.
"""
import os
from functools import lru_cache

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # silences a harmless library warning

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer  # slow import, so only when needed
    return SentenceTransformer(EMBEDDING_MODEL)


def embed(texts: list[str]):
    """Return one 384-number vector per text (a numpy array, rows normalised)."""
    return get_model().encode(texts, batch_size=32, normalize_embeddings=True,
                              show_progress_bar=len(texts) > 32)
