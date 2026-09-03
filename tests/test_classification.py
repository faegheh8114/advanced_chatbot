import pytest

from chatbot import Chatbot, load_intents


@pytest.fixture(scope="module")
def intents():
    return load_intents("intents.json")


@pytest.fixture
def bot(intents):
    # Keep these tests focused on rule-based matching.
    return Chatbot(intents=intents, semantic_matcher=None)


def test_exact_pattern_match(bot):
    tag, confidence = bot.classify("hello")
    assert tag == "greeting"
    assert confidence == 1.0


def test_substring_match_within_longer_message(bot):
    tag, confidence = bot.classify("hi there, quick question for you")
    assert tag == "greeting"
    assert confidence == 1.0


def test_token_overlap_scores_reordered_and_inserted_words():
    # Pattern words are present but not contiguous.
    pattern_tokens = set("what can you do".split())
    user_tokens = set("man what can you actually do these days".split())
    score = Chatbot._token_overlap_score(user_tokens, pattern_tokens)
    assert score == 1.0


def test_token_overlap_partial_match_scores_less_than_one():
    pattern_tokens = set("how can you help".split())
    user_tokens = set("how can you support".split())
    score = Chatbot._token_overlap_score(user_tokens, pattern_tokens)
    assert 0 < score < 1.0


def test_token_overlap_classifies_reordered_message(bot):
    tag, confidence = bot.classify("man what can you actually do these days")
    assert tag == "capabilities"
    assert confidence >= bot.confidence_threshold


def test_fuzzy_match_handles_typo(bot):
    tag, confidence = bot.classify("helo")
    assert tag == "greeting"
    assert confidence >= bot.confidence_threshold


def test_low_confidence_returns_no_intent(bot):
    tag, confidence = bot.classify("what is the capital of france")
    assert tag is None
    assert confidence < bot.confidence_threshold


class _FakeSemanticMatcher:
   """Simple stand-in for the semantic matcher used in tests."""

    def __init__(self, intent, score):
        self._intent = intent
        self._score = score

    def best_match(self, _text):
        return self._intent, self._score


def test_semantic_layer_used_when_rules_are_weak(intents):
    pricing_intent = next(i for i in intents if i["tag"] == "pricing")
    bot = Chatbot(
        intents=intents,
        semantic_matcher=_FakeSemanticMatcher(pricing_intent, 0.9),
    )
   # Rule-based matching should be too weak for this paraphrase.
    tag, confidence = bot.classify("what would it set me back to sign up")
    assert tag == "pricing"
    assert confidence == 0.9


def test_semantic_layer_ignored_when_rules_already_confident(intents):
    greeting_intent = next(i for i in intents if i["tag"] == "greeting")
    pricing_intent = next(i for i in intents if i["tag"] == "pricing")
    bot = Chatbot(
        intents=intents,
       # A confident rule-based match should take priority.
        semantic_matcher=_FakeSemanticMatcher(pricing_intent, 0.95),
    )
    tag, confidence = bot.classify("hello")
    assert tag == greeting_intent["tag"]
    assert confidence == 1.0


def test_semantic_layer_disabled_by_default(intents):
    bot = Chatbot(intents=intents)
    assert bot.semantic_matcher is None


# Regression: short fragments should not receive full-match confidence


def test_short_fragment_you_does_not_match_any_intent(bot):
    tag, confidence = bot.classify("you")
    assert tag is None
    assert confidence < bot.confidence_threshold


def test_short_fragment_help_does_not_match_any_intent(bot):
    tag, confidence = bot.classify("help")
    assert tag is None
    assert confidence < bot.confidence_threshold


@pytest.mark.parametrize("word", ["yes", "no"])
def test_other_short_common_words_do_not_match_any_intent(bot, word):
 # Short generic words should not match an intent by accident.
    tag, confidence = bot.classify(word)
    assert tag is None
    assert confidence < bot.confidence_threshold


def test_short_input_can_still_match_when_it_is_a_real_pattern(bot):
  # Short input should still match when it is a complete pattern.
    tag, confidence = bot.classify("hi")
    assert tag == "greeting"
    assert confidence == 1.0


def test_short_pattern_typo_tolerance_is_preserved(bot):
  # Fuzzy matching should still handle short patterns such as "bye".
    tag, confidence = bot.classify("byee")
    assert tag == "goodbye"
    assert confidence >= bot.confidence_threshold


def test_tie_breaking_does_not_depend_on_intents_json_order():
   # Identical matches should be resolved deterministically by tag.
    tied_intents = [
        {
            "tag": "zzz_topic",
            "patterns": ["book a flight"],
            "responses_en": ["z"],
            "responses_fa": ["z"],
        },
        {
            "tag": "aaa_topic",
            "patterns": ["book a flight"],
            "responses_en": ["a"],
            "responses_fa": ["a"],
        },
    ]
    bot = Chatbot(intents=tied_intents, semantic_matcher=None)
    tag, confidence = bot.classify("book a flight")
    assert tag == "aaa_topic"
    assert confidence == 1.0

    # Reversing the list order must not change the outcome.
    reordered_bot = Chatbot(intents=list(reversed(tied_intents)), semantic_matcher=None)
    tag, confidence = reordered_bot.classify("book a flight")
    assert tag == "aaa_topic"
