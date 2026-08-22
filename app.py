import collections
import logging
import os
import secrets

from flask import Flask, render_template, request, jsonify, session

from chatbot import Chatbot, IntentConfigError, load_intents
from semantic_matcher import load_semantic_matcher

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# --- Secret key -------------------------------------------------------------
# A hard-coded secret key would let anyone who can read this repository
# forge session cookies for any deployment that didn't override it. Render
# sets the RENDER environment variable on every service it runs, so we use
# that (together with an explicit FLASK_ENV=production) to require a real
# SECRET_KEY in anything that looks like production, while still letting
# local development work out of the box with a key that's random per
# process (so it's never checked into source, but you don't have to set
# anything to run `python app.py` locally).
_looks_like_production = (
    os.environ.get("RENDER") is not None
    or os.environ.get("FLASK_ENV") == "production"
)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if _looks_like_production:
        raise RuntimeError(
            "SECRET_KEY environment variable must be set in production. "
            "Set it in your Render service's environment variables."
        )
    app.secret_key = secrets.token_hex(32)
    app.logger.warning(
        "SECRET_KEY not set — using a random key for this process only. "
        "Sessions will not persist across restarts. Set SECRET_KEY for "
        "production."
    )

# Debug mode must never be on in production: it exposes an interactive
# debugger/stack traces to anyone who can trigger an error. Default to off;
# opt in explicitly for local development only.
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1" and not _looks_like_production

# Requests with a message longer than this are rejected outright rather
# than silently truncated, so the client knows why nothing sensible came
# back. Matches chatbot.MAX_MESSAGE_LENGTH.
MAX_MESSAGE_LENGTH = 500

# Loaded and validated once at startup (not per-request/per-session): a
# broken intents.json should fail fast and loudly in the logs rather than
# surfacing as a confusing error on someone's first message. The intents
# list and (if enabled) the semantic matcher are then shared read-only by
# every per-session Chatbot instance below.
try:
    _intents = load_intents()
except IntentConfigError as exc:
    app.logger.critical("Failed to load chatbot configuration: %s", exc)
    raise

# The semantic matcher (if SEMANTIC_MATCHING=1 and sentence-transformers is
# installed) wraps a large embedding model. It is loaded exactly once here,
# at process startup, and shared by every per-session Chatbot below -
# never re-loaded per request or per session.
_semantic_matcher = load_semantic_matcher(_intents)

# One Chatbot instance per user session, so conversation context
# (fallback streak, last intent) doesn't leak between different visitors.
# Bounded and LRU-evicted so long-running deployments don't accumulate an
# unbounded number of abandoned sessions in memory.
_MAX_SESSIONS = 500
_bot_sessions = collections.OrderedDict()


def get_bot_for_session():
    if "session_id" not in session:
        session["session_id"] = secrets.token_hex(16)
    session_id = session["session_id"]

    if session_id in _bot_sessions:
        _bot_sessions.move_to_end(session_id)
        return _bot_sessions[session_id]

    bot = Chatbot(intents=_intents, semantic_matcher=_semantic_matcher)
    _bot_sessions[session_id] = bot
    if len(_bot_sessions) > _MAX_SESSIONS:
        _bot_sessions.popitem(last=False)
    return bot


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/get")
def get_bot_response():
    user_text = request.args.get("msg", "")
    if len(user_text) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Message is too long."}), 400

    try:
        bot = get_bot_for_session()
        response = bot.get_response(user_text)
    except Exception:
        # Full detail always goes to the logs; the client only ever gets a
        # generic message so internal errors/stack traces are never exposed.
        app.logger.exception("Error while generating chatbot response")
        return jsonify({"error": "Something went wrong on our end. Please try again."}), 500

    return jsonify({"response": response})


@app.route("/reset", methods=["POST"])
def reset_conversation():
    try:
        bot = get_bot_for_session()
        bot.reset_conversation()
    except Exception:
        app.logger.exception("Error while resetting conversation")
        return jsonify({"error": "Something went wrong on our end. Please try again."}), 500
    return jsonify({"status": "ok"})


@app.errorhandler(404)
def handle_not_found(_error):
    return jsonify({"error": "Not found."}), 404


@app.errorhandler(500)
def handle_server_error(_error):
    app.logger.exception("Unhandled server error")
    return jsonify({"error": "Something went wrong on our end. Please try again."}), 500


if __name__ == "__main__":
    app.run(debug=DEBUG)
