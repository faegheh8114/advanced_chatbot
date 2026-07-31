import json
import random
import re
import difflib
from datetime import datetime


class Chatbot:
    """
    A lightweight intent-matching chatbot.

    Matching strategy (in order):
      1. Exact / substring match against known patterns.
      2. Token overlap scoring — rewards messages that share whole words
         with a pattern, so word order and extra words don't break matching.
      3. Fuzzy string similarity (difflib) — catches typos and near-matches.

    The bot also tracks simple conversation state (last intent, how many
    times in a row it failed to understand the user) so it can respond a
    little more naturally, e.g. offering help after repeated fallbacks.
    """

    FALLBACK_RESPONSES = [
        "Sorry, I didn't quite catch that. Could you rephrase?",
        "Hmm, I'm not sure I understand. Can you try saying that differently?",
        "I don't have an answer for that yet — could you ask in another way?",
    ]

    FALLBACK_HELP_HINT = (
        "It looks like I'm struggling with that one. Try asking about "
        "our pricing, hours, or just say 'hi' to start over 🙂"
    )

    def __init__(self, intents_file="intents.json", fuzzy_threshold=0.78):
        with open(intents_file, "r", encoding="utf-8") as file:
            self.intents = json.load(file)["intents"]
        self.fuzzy_threshold = fuzzy_threshold

        # Simple per-instance conversation state.
        # In a multi-user web app you'd key this by session/user id instead.
        self.last_intent = None
        self.fallback_streak = 0

    @staticmethod
    def clean_input(text):
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return re.sub(r"\s+", " ", text)

    def _token_overlap_score(self, user_tokens, pattern):
        pattern_tokens = set(pattern.split())
        if not pattern_tokens:
            return 0.0
        overlap = user_tokens & pattern_tokens
        return len(overlap) / len(pattern_tokens)

    def _best_match(self, user_input_clean):
        """Return (intent, confidence) for the best matching intent, or (None, 0)."""
        if not user_input_clean:
            return None, 0.0

        user_tokens = set(user_input_clean.split())
        best_intent = None
        best_score = 0.0

        for intent in self.intents:
            for pattern in intent["patterns"]:
                pattern_clean = self.clean_input(pattern)

                # 1. Direct substring match -> high confidence immediately.
                if pattern_clean in user_input_clean or user_input_clean in pattern_clean:
                    return intent, 1.0

                # 2. Token overlap.
                overlap_score = self._token_overlap_score(user_tokens, pattern_clean)

                # 3. Fuzzy similarity as a fallback signal.
                fuzzy_score = difflib.SequenceMatcher(
                    None, user_input_clean, pattern_clean
                ).ratio()

                score = max(overlap_score, fuzzy_score)
                if score > best_score:
                    best_score = score
                    best_intent = intent

        return best_intent, best_score

    def get_response(self, user_input):
        if not user_input or not user_input.strip():
            return "I didn't receive any message — could you type something?"

        user_input_clean = self.clean_input(user_input)
        intent, confidence = self._best_match(user_input_clean)

        if intent and confidence >= self.fuzzy_threshold:
            self.last_intent = intent["tag"]
            self.fallback_streak = 0
            return random.choice(intent["responses"])

        # Fallback path
        self.fallback_streak += 1
        if self.fallback_streak >= 2:
            self.fallback_streak = 0
            return self.FALLBACK_HELP_HINT
        return random.choice(self.FALLBACK_RESPONSES)

    def reset_conversation(self):
        self.last_intent = None
        self.fallback_streak = 0


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
