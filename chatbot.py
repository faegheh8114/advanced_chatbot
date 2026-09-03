import json
import logging
import random
import re
import difflib
from datetime import datetime

from semantic_matcher import load_semantic_matcher

logger = logging.getLogger(__name__)

# Confidence thresholds used by the matching pipeline.
SUBSTRING_MATCH_CONFIDENCE = 1.0
# Minimum confidence required to accept a matched intent.
# Validated against the current intent evaluation set.
INTENT_CONFIDENCE_THRESHOLD = 0.78

# Skip fuzzy matching for very short patterns, where character similarity
# is too noisy to be useful.
MIN_FUZZY_PATTERN_LENGTH = 3

# Limit input length to keep matching predictable and fast.
MAX_MESSAGE_LENGTH = 500

# Short replies that refer back to the previous intent
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
Hybrid rule-based and semantic intent-matching chatbot.
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
       # Reuse preloaded intents when provided.
        self.intents = intents if intents is not None else load_intents(intents_file)
        self._intents_by_tag = {intent["tag"]: intent for intent in self.intents}
        self.confidence_threshold = confidence_threshold

        # Load the semantic matcher once and reuse it when possible.
        if semantic_matcher is self._UNSET:
            semantic_matcher = load_semantic_matcher(self.intents)
        self.semantic_matcher = semantic_matcher

        # Conversation state for this chatbot instance.
        self.last_intent = None
        self.fallback_streak = 0
        self.pending_context = None  # tag of an intent awaiting clarification

    # Arabic/Persian punctuation removed during input normalization.
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
       """Check whether a pattern appears as a complete phrase."""
        if not needle:
            return False
        return re.search(rf"(?:^|\s){re.escape(needle)}(?:\s|$)", haystack) is not None

    def _rule_based_score(self, user_input_clean, user_tokens, pattern_clean):
       """Score a message against one pattern using phrase, token, and fuzzy matching."""
        if not pattern_clean:
            return 0.0
        if self._contains_as_phrase(pattern_clean, user_input_clean):
            return SUBSTRING_MATCH_CONFIDENCE

        overlap_score = self._token_overlap_score(user_tokens, set(pattern_clean.split()))
        fuzzy_score = 0.0
        if len(pattern_clean) >= MIN_FUZZY_PATTERN_LENGTH:
            fuzzy_score = difflib.SequenceMatcher(None, user_input_clean, pattern_clean).ratio()
        return max(overlap_score, fuzzy_score)

    @staticmethod
    def _is_better_candidate(candidate, current_best):
       """Compare candidates with deterministic tie-breaking."""
        score, pattern_len, tag = candidate
        best_score, best_len, best_tag = current_best
        if score != best_score:
            return score > best_score
        if pattern_len != best_len:
            return pattern_len > best_len
        return tag < best_tag

    def _best_rule_match(self, user_input_clean, user_tokens):
        """Return (intent, score) for the best rule-based candidate, using
        _is_better_candidate to resolve ties deterministically."""
        best_intent = None
        best_candidate = (0.0, 0, "")
        for intent in self.intents:
            for pattern in intent["patterns"]:
                pattern_clean = self.clean_input(pattern)
                score = self._rule_based_score(user_input_clean, user_tokens, pattern_clean)
                if score <= 0:
                    continue
                candidate = (score, len(pattern_clean), intent["tag"])
                if best_intent is None or self._is_better_candidate(candidate, best_candidate):
                    best_candidate = candidate
                    best_intent = intent
        return best_intent, best_candidate[0]

    def _best_match(self, user_input_clean):
       """Return the best matching intent and its confidence."""
        if not user_input_clean:
            return None, 0.0

        user_tokens = set(user_input_clean.split())
        best_intent, confidence = self._best_rule_match(user_input_clean, user_tokens)

       # Exact phrase matches do not need semantic scoring.
        if confidence >= SUBSTRING_MATCH_CONFIDENCE or self.semantic_matcher is None:
            return best_intent, confidence

        semantic_intent, semantic_score = self.semantic_matcher.best_match(user_input_clean)
        if semantic_intent is None:
            return best_intent, confidence

        if best_intent is not None and semantic_intent["tag"] == best_intent["tag"]:
           # Both matchers agree; keep the stronger score.
            confidence = max(confidence, semantic_score)
        elif semantic_score > confidence:
            # Prefer the semantic result when it has the stronger score.
            best_intent, confidence = semantic_intent, semantic_score

        return best_intent, confidence

    def classify(self, user_input):
       """Classify input without changing conversation state."""
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

      # Resolve short follow-ups using the pending intent context.
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
