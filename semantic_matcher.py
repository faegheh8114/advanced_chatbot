"""
Optional semantic intent matcher using sentence embeddings.

Enabled only when SEMANTIC_MATCHING=1 and sentence-transformers is installed.
The model and intent embeddings are loaded once and reused across requests.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Multilingual model used for English and Persian intent matching.
DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class SemanticMatcher:
    """Wraps a sentence-transformers model to score user text against
    every known intent pattern using cosine similarity."""

    def __init__(self, intents, model_name=DEFAULT_MODEL_NAME):
        from sentence_transformers import SentenceTransformer, util

        self._util = util
        self._model = SentenceTransformer(model_name)
        self._intents_by_tag = {intent["tag"]: intent for intent in intents}

        self._tags = []
        patterns = []
        for intent in intents:
            for pattern in intent["patterns"]:
                self._tags.append(intent["tag"])
                patterns.append(pattern)

       # Precompute pattern embeddings once; they are reused for each request.
        self._pattern_embeddings = (
            self._model.encode(patterns, convert_to_tensor=True) if patterns else None
        )

    def best_match(self, text):
        """Return (intent, cosine_similarity) for the closest pattern, or
        (None, 0.0) if there is nothing to compare against."""
        if not text or self._pattern_embeddings is None:
            return None, 0.0

        query_embedding = self._model.encode(text, convert_to_tensor=True)
        similarities = self._util.cos_sim(query_embedding, self._pattern_embeddings)[0]
        best_index = int(similarities.argmax())
        best_score = max(float(similarities[best_index]), 0.0)
        best_tag = self._tags[best_index]
        return self._intents_by_tag[best_tag], best_score


def load_semantic_matcher(intents, model_name=DEFAULT_MODEL_NAME):
    """Build a SemanticMatcher when enabled and available."""
    if os.environ.get("SEMANTIC_MATCHING", "0") != "1":
        return None
    try:
        return SemanticMatcher(intents, model_name=model_name)
    except ImportError:
        logger.warning(
            "SEMANTIC_MATCHING=1 but the 'sentence-transformers' package "
            "is not installed. Falling back to rule-based matching only."
        )
        return None
    except Exception:
        logger.exception(
            "Failed to load the semantic matcher. Falling back to "
            "rule-based matching only."
        )
        return None
