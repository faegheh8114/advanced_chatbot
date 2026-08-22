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


# --- Regression: short/common words must not "borrow" confidence from a
# longer pattern they merely happen to be a fragment of --------------------
#
# "you" is a fragment of "how are you" / "see you" / "you good"; "help" is
# a fragment of "help me". Neither says with any confidence which (if any)
# of those intents the user meant, so neither should classify at all - they
# should fall through to token-overlap/fuzzy scoring like any other partial
# match, which correctly keeps them below the confidence threshold.


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
    # Neither "yes" nor "no" appears in any pattern at all, but they're
    # exactly the kind of short, generic word this fix targets - included
    # per the regression request even though they were never the specific
    # bug (unlike "you"/"help", which used to score 1.0/0.8 respectively).
    tag, confidence = bot.classify(word)
    assert tag is None
    assert confidence < bot.confidence_threshold


def test_short_input_can_still_match_when_it_is_a_real_pattern(bot):
    # The fix must not simply reject all short input: "hi" is itself a
    # deliberate, standalone greeting pattern (not a fragment of a longer
    # one), so it should still classify immediately and with full
    # confidence via the exact/forward-substring path.
    tag, confidence = bot.classify("hi")
    assert tag == "greeting"
    assert confidence == 1.0


def test_short_pattern_typo_tolerance_is_preserved(bot):
    # "bye" is a 3-character pattern - long enough that fuzzy matching is
    # still trusted for it (unlike the 2-character "yo"/"hi" patterns), so
    # a typo like "byee" should still be recognized via fuzzy similarity.
    tag, confidence = bot.classify("byee")
    assert tag == "goodbye"
    assert confidence >= bot.confidence_threshold


def test_tie_breaking_does_not_depend_on_intents_json_order():
    # Two intents sharing the exact same pattern is a genuine tie: same
    # score, same matched-pattern length. "zzz_topic" is listed FIRST to
    # prove the winner isn't simply "whichever intent appears first" -
    # ties are resolved by alphabetically-first tag, deterministically.
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
