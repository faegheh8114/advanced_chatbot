import os
import uuid
from flask import Flask, render_template, request, jsonify, session

from chatbot import Chatbot

app = Flask(__name__)
# In production, load this from an environment variable instead of hardcoding it.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# One Chatbot instance per user session, so conversation context
# (fallback streak, last intent) doesn't leak between different visitors.
_bot_sessions = {}


def get_bot_for_session():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    session_id = session["session_id"]

    if session_id not in _bot_sessions:
        _bot_sessions[session_id] = Chatbot()
    return _bot_sessions[session_id]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/get")
def get_bot_response():
    user_text = request.args.get("msg", "")
    bot = get_bot_for_session()
    response = bot.get_response(user_text)
    return jsonify({"response": response})


@app.route("/reset", methods=["POST"])
def reset_conversation():
    bot = get_bot_for_session()
    bot.reset_conversation()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
