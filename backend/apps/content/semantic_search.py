import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    global _model
    try:
        from sentence_transformers import SentenceTransformer

        model_name = getattr(settings, "SEMANTIC_SEARCH_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(model_name)
        logger.info("Loaded semantic model: %s", model_name)
    except ImportError:
        logger.warning("sentence-transformers not installed; semantic search disabled")
    except Exception as exc:
        logger.error("Failed to load semantic model: %s", exc)


def get_model():
    if _model is None:
        _load_model()
    return _model


def is_available():
    return get_model() is not None


def encode(texts, normalize=True):
    import numpy as np

    model = get_model()
    if model is None:
        return None
    if isinstance(texts, str):
        texts = [texts]
    embeddings = model.encode(texts, show_progress_bar=False)
    if normalize:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = np.divide(embeddings, np.where(norms == 0, 1, norms))
    return embeddings


def compute_similarity(query_vec, doc_embeddings):
    import numpy as np

    if doc_embeddings is None or len(doc_embeddings) == 0:
        return []
    return np.dot(doc_embeddings, query_vec).tolist()


class SemanticSearchService:
    def __init__(self, lessons):
        self.lessons = lessons
        self._embeddings = None

    @property
    def _doc_embeddings(self):
        import numpy as np

        if self._embeddings is not None:
            return self._embeddings
        stored = [l.embedding for l in self.lessons if l.embedding]
        self._embeddings = np.array(stored) if stored else np.array([])
        return self._embeddings

    def search(self, query, top_k=10, min_score=0.0):
        query_vec = encode(query)
        if query_vec is None:
            return []

        embedding_scores = compute_similarity(
            query_vec[0],
            self._doc_embeddings,
        )

        combined_scores = []

        for idx, embedding_score in enumerate(embedding_scores):
            lesson = self.lessons[idx]

            trigram_score = getattr(
                lesson,
                "trigram_similarity",
                0.0,
            )

            # Blend semantic relevance with typo-tolerant lexical similarity.
            final_score = (
                embedding_score * 0.7
                + float(trigram_score) * 0.3
            )

            combined_scores.append((idx, final_score))

        indexed = sorted(
            combined_scores,
            key=lambda x: x[1],
            reverse=True,
        )

        results = []
        for idx, score in indexed:
            if score < min_score:
                continue
            results.append(
                {"lesson": self.lessons[idx], "score": round(float(score), 4)}
            )
            if len(results) >= top_k:
                break
        return results
