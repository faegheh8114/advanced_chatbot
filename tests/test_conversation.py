import pytest

from chatbot import Chatbot, load_intents


@pytest.fixture(scope="module")
def intents():
    return load_intents("intents.json")


@pytest.fixture
def bot(intents):
    return Chatbot(intents=intents, semantic_matcher=None)


def test_last_intent_is_tracked_after_a_match(bot):
    assert bot.last_intent is None
    bot.get_response("hello")
    assert bot.last_intent == "greeting"


def test_last_intent_unchanged_on_fallback(bot):
    bot.get_response("hello")
    bot.get_response("asdkjqwe nonsense text")
    assert bot.last_intent == "greeting"


def test_fallback_streak_resets_after_a_match(bot):
    bot.get_response("asdkjqwe nonsense text")
    assert bot.fallback_streak == 1
    bot.get_response("hi")
    assert bot.fallback_streak == 0


def test_repeated_fallbacks_offer_a_help_hint(bot):
    first = bot.get_response("asdkjqwe nonsense text")
    second = bot.get_response("zxjkqw more nonsense")
    assert first in Chatbot.FALLBACK_RESPONSES_EN
    assert second == Chatbot.FALLBACK_HELP_HINT_EN
    # The streak resets once the hint is shown, rather than repeating it
    # on every subsequent fallback.
    assert bot.fallback_streak == 0


def test_pricing_sets_pending_context(bot):
    bot.get_response("what is the price")
    assert bot.pending_context == "pricing"


def test_contextual_followup_resolves_using_pending_context(bot):
    bot.get_response("how much does it cost")
    assert bot.pending_context == "pricing"
    reply = bot.get_response("the second one")
    pricing_intent = next(i for i in bot.intents if i["tag"] == "pricing")
    assert reply in pricing_intent["context_followup_en"]
    # One-turn memory: it shouldn't still be "pending" after being used.
    assert bot.pending_context is None


def test_followup_phrase_without_pending_context_is_not_special_cased(bot):
    # "the second one" said out of the blue (no prior question asked)
    # should behave like any other unrecognized message.
    reply = bot.get_response("the second one")
    assert reply in Chatbot.FALLBACK_RESPONSES_EN


def test_pending_context_cleared_by_an_unrelated_new_topic(bot):
    bot.get_response("what is the price")
    assert bot.pending_context == "pricing"
    bot.get_response("hello")
    assert bot.pending_context is None


def test_reset_conversation_clears_all_state(bot):
    bot.get_response("what is the price")
    bot.get_response("asdkjqwe nonsense")
    bot.reset_conversation()
    assert bot.last_intent is None
    assert bot.fallback_streak == 0
    assert bot.pending_context is None


def test_persian_input_gets_persian_response(bot):
    reply = bot.get_response("سلام")
    greeting_intent = next(i for i in bot.intents if i["tag"] == "greeting")
    assert reply in greeting_intent["responses_fa"]


def test_english_input_gets_english_response(bot):
    reply = bot.get_response("hello")
    greeting_intent = next(i for i in bot.intents if i["tag"] == "greeting")
    assert reply in greeting_intent["responses_en"]
