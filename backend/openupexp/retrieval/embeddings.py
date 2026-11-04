"""Provedores de embedding.

O modelo e a versão ficam registrados em corpus_version: trocar de modelo gera
um novo corpus_version, sem sobrescrever o anterior.
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from openupexp.config import get_settings


class Embedder(Protocol):
    provider: str
    model: str
    dim: int

    def encode_passages(self, texts: list[str]) -> list[list[float]]: ...

    def encode_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Embedding determinístico por *hashing trick* — só para testes e modo simulado."""

    provider = "hash"

    def __init__(self, dim: int = 256):
        self.dim = dim
        self.model = f"hash-{dim}"

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def encode_query(self, text: str) -> list[float]:
        return self._vec(text)


class SentenceTransformerEmbedder:
    provider = "sentence-transformers"

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model = model
        self._st = SentenceTransformer(model)
        self.dim = self._st.get_sentence_embedding_dimension()
        # modelos E5 exigem prefixos de consulta/passagem
        self._e5 = "e5" in model.lower()

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        if self._e5:
            texts = [f"passage: {t}" for t in texts]
        return self._st.encode(texts, normalize_embeddings=True, batch_size=32).tolist()

    def encode_query(self, text: str) -> list[float]:
        if self._e5:
            text = f"query: {text}"
        return self._st.encode(text, normalize_embeddings=True).tolist()


@lru_cache
def get_embedder(provider: str | None = None, model: str | None = None) -> Embedder:
    s = get_settings()
    provider = provider or s.embedding_provider
    if provider == "hash":
        return HashEmbedder()
    if provider == "sentence-transformers":
        return SentenceTransformerEmbedder(model or s.embedding_model)
    raise ValueError(f"provedor de embedding desconhecido: {provider}")
