import pytest

from chatbot import Chatbot, load_intents


@pytest.fixture(scope="module")
def intents():
    return load_intents("intents.json")


@pytest.fixture
def bot(intents):
    # semantic_matcher=None: these tests exercise the rule-based pipeline
    # in isolation, regardless of whether the optional semantic layer is
    # installed in the environment running the tests.
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
    # Directly exercise the scoring function: pattern words present as a
    # set, but not contiguous, so the substring check can't fire.
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
    """Deterministic stand-in for SemanticMatcher so the hybrid-combination
    logic in Chatbot._best_match can be tested without the optional
    sentence-transformers dependency being installed."""

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
    # A paraphrase with no shared words/patterns at all, so the rule-based
    # layer alone would score close to 0 and this would otherwise fall back.
    tag, confidence = bot.classify("what would it set me back to sign up")
    assert tag == "pricing"
    assert confidence == 0.9


def test_semantic_layer_ignored_when_rules_already_confident(intents):
    greeting_intent = next(i for i in intents if i["tag"] == "greeting")
    pricing_intent = next(i for i in intents if i["tag"] == "pricing")
    bot = Chatbot(
        intents=intents,
        # Semantic layer disagrees, but the rule-based match is already a
        # certain substring hit, so it should win outright.
        semantic_matcher=_FakeSemanticMatcher(pricing_intent, 0.95),
    )
    tag, confidence = bot.classify("hello")
    assert tag == greeting_intent["tag"]
    assert confidence == 1.0


def test_semantic_layer_disabled_by_default(intents):
    bot = Chatbot(intents=intents)
    assert bot.semantic_matcher is None
