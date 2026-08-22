from chatbot import Chatbot


def test_lowercases_and_trims():
    assert Chatbot.clean_input("  Hello There  ") == "hello there"


def test_strips_punctuation():
    assert Chatbot.clean_input("Hi!! How are you??") == "hi how are you"


def test_collapses_whitespace():
    assert Chatbot.clean_input("hi    there\t\tfriend") == "hi there friend"


def test_keeps_persian_letters():
    assert Chatbot.clean_input("سلام، خوبی؟") == "سلام خوبی"


def test_strips_emoji_and_symbols():
    assert Chatbot.clean_input("hello 😊 #great!") == "hello great"


def test_empty_input_stays_empty():
    assert Chatbot.clean_input("") == ""
    assert Chatbot.clean_input("   ") == ""


def test_digits_are_kept():
    assert Chatbot.clean_input("call me at 123") == "call me at 123"
