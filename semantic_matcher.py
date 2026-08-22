"""
Optional semantic (embedding-based) intent matcher.

This is a *second opinion* layered on top of the rule-based matching in
chatbot.py. It is only loaded when both are true:

  1. the SEMANTIC_MATCHING environment variable is set to "1", and
  2. the `sentence-transformers` package is installed.

Both gates exist on purpose: `sentence-transformers` pulls in PyTorch,
which is a large dependency (several hundred MB) and noticeably slower
to import/load than the rest of this project. On a memory-constrained
host (e.g. Render's free tier) that can be the difference between a
service that starts and one that gets OOM-killed. Keeping it opt-in
means the app is small and fast by default, while still supporting the
semantic layer for anyone who deploys somewhere with more headroom.

The embedding model is loaded once (at process/app startup) and reused
for every request - never re-loaded or re-downloaded per request. Intent
pattern embeddings are likewise computed once, at load time, not on
every call to best_match().
"""
import logging
import os

logger = logging.getLogger(__name__)

# A small multilingual sentence-embedding model that covers both English
# and Persian, which is what this chatbot needs. "MiniLM" variants trade
# some accuracy for a much smaller footprint than larger multilingual
# models (e.g. LaBSE), which matters for deployment size.
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

        # Precompute once: this is the "cache precomputed intent
        # embeddings" step from the design - encoding is comparatively
        # expensive, so we never want to do it per-request for the
        # (fixed) set of intent patterns.
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
    """Build a SemanticMatcher if enabled and available, else return None.

    Returning None (rather than raising) is deliberate: the semantic layer
    is an enhancement, not a requirement, so any problem loading it should
    degrade to rule-based-only matching instead of taking the app down.
    """
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
