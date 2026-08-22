import json

import pytest

from chatbot import Chatbot, IntentConfigError, load_intents


def test_loads_the_real_intents_file():
    intents = load_intents("intents.json")
    assert len(intents) > 0
    assert all("tag" in intent for intent in intents)


def test_missing_file_raises_clear_error():
    with pytest.raises(IntentConfigError, match="not found"):
        load_intents("does_not_exist.json")


def test_malformed_json_raises_clear_error(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(IntentConfigError, match="not valid JSON"):
        load_intents(str(bad_file))


def test_missing_intents_key_raises_clear_error(tmp_path):
    bad_file = tmp_path / "no_intents_key.json"
    bad_file.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    with pytest.raises(IntentConfigError, match="intents"):
        load_intents(str(bad_file))


def test_empty_intents_list_raises_clear_error(tmp_path):
    bad_file = tmp_path / "empty.json"
    bad_file.write_text(json.dumps({"intents": []}), encoding="utf-8")
    with pytest.raises(IntentConfigError):
        load_intents(str(bad_file))


def test_intent_missing_required_field_raises_clear_error(tmp_path):
    bad_file = tmp_path / "missing_field.json"
    bad_file.write_text(
        json.dumps({"intents": [{"tag": "greeting", "patterns": ["hi"]}]}),
        encoding="utf-8",
    )
    with pytest.raises(IntentConfigError, match="responses_en"):
        load_intents(str(bad_file))


def test_duplicate_tag_raises_clear_error(tmp_path):
    intent = {
        "tag": "greeting",
        "patterns": ["hi"],
        "responses_en": ["hi"],
        "responses_fa": ["سلام"],
    }
    bad_file = tmp_path / "duplicate.json"
    bad_file.write_text(json.dumps({"intents": [intent, intent]}), encoding="utf-8")
    with pytest.raises(IntentConfigError, match="Duplicate"):
        load_intents(str(bad_file))


def test_chatbot_construction_fails_fast_on_bad_config(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all", encoding="utf-8")
    with pytest.raises(IntentConfigError):
        Chatbot(intents_file=str(bad_file))
