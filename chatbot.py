import json
import random
import re

class Chatbot:
    def __init__(self, intents_file="intents.json"):
        with open(intents_file, "r", encoding="utf-8") as file:
            self.intents = json.load(file)["intents"]

    def clean_input(self, text):
        return re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())

    def get_response(self, user_input):
        user_input_clean = self.clean_input(user_input)
        for intent in self.intents:
            for pattern in intent["patterns"]:
                if pattern in user_input_clean:
                    return random.choice(intent["responses"])
        return "Sorry, I didn't understand that. Can you rephrase?"

if __name__ == "__main__":
    bot = Chatbot()
    print("🤖 Chatbot running! Type 'quit' to exit.")
    while True:
        msg = input("You: ")
        if msg.lower() == "quit":
            print("Bot: Goodbye! 👋")
            break
        print("Bot:", bot.get_response(msg))