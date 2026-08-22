import json
import logging
import random
import re
import difflib
from datetime import datetime

from semantic_matcher import load_semantic_matcher

logger = logging.getLogger(__name__)

# --- Confidence thresholds --------------------------------------------------
# A substring match (the user's text contains a whole known pattern, or
# vice versa) is treated as certain - there's no ambiguity to weigh against
# other candidates, so it short-circuits the rest of the scoring pipeline.
SUBSTRING_MATCH_CONFIDENCE = 1.0

# Minimum combined confidence required to accept an intent instead of
# falling back. Chosen by running evaluate.py against data/intent_test.json
# and picking the lowest threshold that didn't introduce false positives
# on the "unknown"/out-of-scope examples in that set - see evaluate.py and
# the project report for the measured accuracy/precision/recall at this
# value. It was 0.78 before this refactor and is kept unchanged so existing
# behavior isn't disturbed without evidence a different number is better.
INTENT_CONFIDENCE_THRESHOLD = 0.78

# Requests longer than this are truncated before matching. difflib's
# similarity ratio is roughly O(n*m) in the length of the two strings, so
# without a cap a single very long message would be needlessly slow to
# score against every pattern.
MAX_MESSAGE_LENGTH = 500

# Short replies that only make sense as an answer to a question the bot
# just asked (e.g. "Which one?"), not as a new topic on their own. Used by
# the contextual follow-up mechanism below.
_CONTEXT_REFERENCE_PHRASES = {
    "yes", "yeah", "yep", "sure", "ok", "okay",
    "that one", "this one", "the first one", "first one",
    "the second one", "second one", "either one", "both",
    "بله", "آره", "باشه", "اوکی",
    "همین", "همون", "همینو", "همونو",
    "اولی", "دومی", "هردو",
}


class IntentConfigError(Exception):
    """Raised when intents.json is missing, unreadable, or malformed."""


def load_intents(intents_file="intents.json"):
    """Load and validate the intents file, raising IntentConfigError with a
    clear message if it's missing or doesn't have the shape the bot needs."""
    try:
        with open(intents_file, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise IntentConfigError(f"Intents file not found: {intents_file}")
    except json.JSONDecodeError as exc:
        raise IntentConfigError(f"Intents file is not valid JSON: {exc}")

    intents = data.get("intents") if isinstance(data, dict) else None
    if not isinstance(intents, list) or not intents:
        raise IntentConfigError(
            f"{intents_file} must contain a non-empty 'intents' list."
        )

    required_fields = ("tag", "patterns", "responses_en", "responses_fa")
    seen_tags = set()
    for index, intent in enumerate(intents):
        if not isinstance(intent, dict):
            raise IntentConfigError(f"Intent #{index} must be an object.")
        missing = [field for field in required_fields if not intent.get(field)]
        if missing:
            label = intent.get("tag", f"#{index}")
            raise IntentConfigError(
                f"Intent '{label}' is missing required field(s): {', '.join(missing)}"
            )
        if intent["tag"] in seen_tags:
            raise IntentConfigError(f"Duplicate intent tag: '{intent['tag']}'")
        seen_tags.add(intent["tag"])

    return intents


class Chatbot:
    """
    A hybrid rule-based / semantic intent-matching chatbot.

    Classification pipeline, per message:
      1. Normalization - lowercase, strip punctuation, collapse whitespace
         (keeping Persian/Arabic-script letters).
      2. Candidate matching - every intent's patterns are compared against
         the normalized text.
      3. Rule-based scoring - substring match, token overlap, and difflib
         fuzzy similarity (see _rule_based_score).
      4. Semantic scoring (only if the optional semantic layer is loaded) -
         cosine similarity between sentence embeddings.
      5. The two scores are combined into one confidence value.
      6. Confidence threshold - below INTENT_CONFIDENCE_THRESHOLD, the
         message is treated as unrecognized.
      7. Intent (with a random response for variety) or fallback.

    The bot also tracks light conversation state - the last recognized
    intent, how many times in a row it failed to understand the user, and
    (for intents that ask a clarifying question) a "pending context" tag
    so a short follow-up like "the second one" can be resolved using what
    was just being discussed instead of being treated as a fresh, unrelated
    message.
    """

    FALLBACK_RESPONSES_EN = [
        "Sorry, I didn't quite catch that. Could you rephrase?",
        "Hmm, I'm not sure I understand. Can you try saying that differently?",
        "I don't have an answer for that yet — could you ask in another way?",
    ]
    FALLBACK_RESPONSES_FA = [
        "ببخشید، متوجه نشدم. می‌شه یه‌جور دیگه بگی؟",
        "هوم، مطمئن نیستم درست فهمیدم. می‌تونی جور دیگه‌ای بپرسی؟",
        "هنوز جوابی برای این ندارم — می‌شه به شکل دیگه‌ای بپرسی؟",
    ]

    FALLBACK_HELP_HINT_EN = (
        "It looks like I'm struggling with that one. Try asking about "
        "our pricing, hours, or just say 'hi' to start over 🙂"
    )
    FALLBACK_HELP_HINT_FA = (
        "به نظر میاد این یکی رو متوجه نمی‌شم. می‌تونی درباره‌ی قیمت یا "
        "ساعت کاری بپرسی، یا فقط بنویس «سلام» تا از اول شروع کنیم 🙂"
    )

    # Unicode range for Persian/Arabic-script characters.
    _PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")

    # Sentinel so `semantic_matcher=None` (explicitly disable) can be told
    # apart from "not passed" (auto-detect from SEMANTIC_MATCHING env var).
    _UNSET = object()

    @classmethod
    def _is_persian(cls, text):
        return bool(cls._PERSIAN_RE.search(text))

    def __init__(
        self,
        intents_file="intents.json",
        intents=None,
        confidence_threshold=INTENT_CONFIDENCE_THRESHOLD,
        semantic_matcher=_UNSET,
    ):
        # `intents` lets callers (the Flask app, tests) share one already-
        # loaded/validated intents list across many Chatbot instances
        # instead of re-reading and re-validating the file every time.
        self.intents = intents if intents is not None else load_intents(intents_file)
        self._intents_by_tag = {intent["tag"]: intent for intent in self.intents}
        self.confidence_threshold = confidence_threshold

        # Likewise, the semantic matcher wraps a large embedding model that
        # must be loaded once and shared, not rebuilt per session. Passing
        # semantic_matcher=None explicitly opts out of it for this instance.
        if semantic_matcher is self._UNSET:
            semantic_matcher = load_semantic_matcher(self.intents)
        self.semantic_matcher = semantic_matcher

        # Per-instance conversation state. In the web app, app.py keeps one
        # Chatbot per browser session so this never leaks between visitors.
        self.last_intent = None
        self.fallback_streak = 0
        self.pending_context = None  # tag of an intent awaiting clarification

    # Arabic-script punctuation (comma, semicolon, question mark, percent,
    # decimal/thousands separators). These fall inside the same Unicode
    # block as Persian letters (U+0600-U+06FF), so a naive "keep everything
    # in that block" filter would leave them in the normalized text - e.g.
    # "khubi?" (Persian, with a trailing Arabic question mark) would stay one
    # token instead of becoming "khubi" (transliterated for this comment), silently
    # breaking token-overlap matching against clean patterns. Stripped
    # explicitly before the general keep-letters-and-digits pass below.
    _ARABIC_PUNCTUATION_RE = re.compile(r"[\u060C\u061B\u061F\u066A\u066B\u066C\u0640]")

    @staticmethod
    def clean_input(text):
        """Normalize text: lowercase, strip everything but Latin/Persian
        letters, digits and spaces, and collapse whitespace."""
        text = text.lower().strip()
        text = Chatbot._ARABIC_PUNCTUATION_RE.sub("", text)
        text = re.sub(r"[^a-z0-9\u0600-\u06FF\s]", "", text)
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _token_overlap_score(user_tokens, pattern_tokens):
        if not pattern_tokens:
            return 0.0
        overlap = user_tokens & pattern_tokens
        return len(overlap) / len(pattern_tokens)

    @staticmethod
    def _contains_as_phrase(needle, haystack):
        """Whether `needle` appears in `haystack` as a whole phrase - at the
        start/end of the string or surrounded by spaces - rather than as a
        raw substring. Without this, a short pattern like "yo" would count
        as a match inside unrelated words such as "you" or "your", since
        plain `in` checks don't respect word boundaries."""
        if not needle:
            return False
        return re.search(rf"(?:^|\s){re.escape(needle)}(?:\s|$)", haystack) is not None

    def _rule_based_score(self, user_input_clean, user_tokens, pattern_clean):
        """Score one (message, pattern) pair using substring / token-overlap
        / fuzzy matching. Returns a value in [0, 1]."""
        if not pattern_clean:
            return 0.0
        if self._contains_as_phrase(pattern_clean, user_input_clean) or self._contains_as_phrase(
            user_input_clean, pattern_clean
        ):
            return SUBSTRING_MATCH_CONFIDENCE

        overlap_score = self._token_overlap_score(user_tokens, set(pattern_clean.split()))
        fuzzy_score = difflib.SequenceMatcher(None, user_input_clean, pattern_clean).ratio()
        return max(overlap_score, fuzzy_score)

    def _best_rule_match(self, user_input_clean, user_tokens):
        """Return (intent, score) for the best rule-based candidate."""
        best_intent = None
        best_score = 0.0
        for intent in self.intents:
            for pattern in intent["patterns"]:
                pattern_clean = self.clean_input(pattern)
                score = self._rule_based_score(user_input_clean, user_tokens, pattern_clean)
                if score > best_score:
                    best_score = score
                    best_intent = intent
                    if best_score >= SUBSTRING_MATCH_CONFIDENCE:
                        return best_intent, best_score
        return best_intent, best_score

    def _best_match(self, user_input_clean):
        """Run the full candidate-matching + scoring pipeline and return
        (intent, confidence) for the best match, or (None, 0.0)."""
        if not user_input_clean:
            return None, 0.0

        user_tokens = set(user_input_clean.split())
        best_intent, confidence = self._best_rule_match(user_input_clean, user_tokens)

        # A substring hit is already maximally confident; the semantic
        # layer can't add anything, so skip it.
        if confidence >= SUBSTRING_MATCH_CONFIDENCE or self.semantic_matcher is None:
            return best_intent, confidence

        semantic_intent, semantic_score = self.semantic_matcher.best_match(user_input_clean)
        if semantic_intent is None:
            return best_intent, confidence

        if best_intent is not None and semantic_intent["tag"] == best_intent["tag"]:
            # Both layers agree - take the more confident of the two as the
            # combined score.
            confidence = max(confidence, semantic_score)
        elif semantic_score > confidence:
            # The layers disagree and the semantic layer is more confident -
            # trust it, since it can recognize paraphrases the rule-based
            # patterns don't literally contain.
            best_intent, confidence = semantic_intent, semantic_score

        return best_intent, confidence

    def classify(self, user_input):
        """Pure classification: return (intent_tag_or_None, confidence)
        without any randomness or conversation-state side effects. Used by
        evaluate.py and the test suite so results are reproducible."""
        if not isinstance(user_input, str) or not user_input.strip():
            return None, 0.0
        user_input_clean = self.clean_input(user_input[:MAX_MESSAGE_LENGTH])
        intent, confidence = self._best_match(user_input_clean)
        if intent and confidence >= self.confidence_threshold:
            return intent["tag"], confidence
        return None, confidence

    def get_response(self, user_input):
        if not isinstance(user_input, str) or not user_input.strip():
            return "I didn't receive any message — could you type something?"

        user_input = user_input[:MAX_MESSAGE_LENGTH]
        is_fa = self._is_persian(user_input)
        user_input_clean = self.clean_input(user_input)

        # Contextual follow-up: a short reference like "the second one"
        # can't be classified as a topic on its own, but if it directly
        # follows an intent that asked a clarifying question, resolve it
        # using that topic instead of treating it as unrecognized.
        if self.pending_context and user_input_clean in _CONTEXT_REFERENCE_PHRASES:
            intent = self._intents_by_tag.get(self.pending_context)
            self.pending_context = None
            if intent and intent.get("context_followup_en"):
                self.last_intent = intent["tag"]
                self.fallback_streak = 0
                responses = (
                    intent["context_followup_fa"] if is_fa else intent["context_followup_en"]
                )
                return random.choice(responses)

        intent, confidence = self._best_match(user_input_clean)

        if intent and confidence >= self.confidence_threshold:
            self.last_intent = intent["tag"]
            self.fallback_streak = 0
            self.pending_context = intent["tag"] if intent.get("awaits_clarification") else None
            responses = intent["responses_fa"] if is_fa else intent["responses_en"]
            return random.choice(responses)

        # Fallback path
        self.pending_context = None
        self.fallback_streak += 1
        if self.fallback_streak >= 2:
            self.fallback_streak = 0
            return self.FALLBACK_HELP_HINT_FA if is_fa else self.FALLBACK_HELP_HINT_EN
        return random.choice(self.FALLBACK_RESPONSES_FA if is_fa else self.FALLBACK_RESPONSES_EN)

    def reset_conversation(self):
        self.last_intent = None
        self.fallback_streak = 0
        self.pending_context = None


if __name__ == "__main__":
    bot = Chatbot()
    print("🤖 Chatbot running! Type 'quit' to exit.\n")
    while True:
        msg = input("You: ")
        if msg.lower() == "quit":
            print("Bot: Goodbye! 👋")
            break
        timestamp = datetime.now().strftime("%H:%M")
        print(f"Bot [{timestamp}]:", bot.get_response(msg))
