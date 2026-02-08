from flask import Flask, render_template, request
from chatbot import Chatbot

app = Flask(__name__)
bot = Chatbot()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get")
def get_bot_response():
    user_text = request.args.get("msg")
    return bot.get_response(user_text)

if __name__ == "__main__":
    app.run(debug=True)