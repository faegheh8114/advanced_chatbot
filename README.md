# Advanced Chatbot
**[Live Demo](https://advanced-chatbot-16cy.onrender.com)**,try it out (may take ~30s to wake up on first load)
A rule-based conversational chatbot built with **Flask**, featuring a clean chat-widget UI,
fuzzy intent matching (handles typos and rephrased questions), and a lightweight per-session
conversation state.

Built as a portfolio project to demonstrate backend (Python/Flask), frontend (vanilla JS/CSS),
and basic NLP techniques.

##  Features

- **Fuzzy intent matching** — combines substring matching, token overlap, and `difflib`
  similarity scoring, so the bot understands typos and reworded questions, not just exact phrases.
- **Per-session context** each visitor gets their own conversation state (no context bleeding
  between users), tracked via a Flask session cookie.
- **Human-like chat UI** message bubbles, avatar, timestamps, and a typing indicator with a
  short randomized delay before replies.
- **Easy to extend** add new topics by editing `intents.json`, no code changes required.
- **Graceful fallback** after repeated misunderstandings, the bot proactively suggests topics
  it can help with instead of repeating the same "I don't understand" message.
 - **Bilingual (English/Persian)**  detects whether a message is in Persian or English and replies in the same language.

##  Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python, Flask |
| Matching | `difflib` (standard library) |
| Frontend | HTML, CSS, vanilla JavaScript |
| Fonts | Sora (headings), Inter (body) |

##  Project Structure

```
advanced_chatbot/
├── app.py              # Flask routes & session handling
├── chatbot.py          # Intent matching engine
├── intents.json        # Conversation topics & responses
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

##  Getting Started

```bash
# 1. Clone the repo
git clone https://github.com/faegheh8114/advanced_chatbot.git
cd advanced_chatbot

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

You can also chat with the bot directly in the terminal without the web UI:

```bash
python chatbot.py
```

##  How the Matching Works

For each incoming message, `chatbot.py` scores it against every known pattern using three
signals, and picks the best match above a confidence threshold:

1. **Substring match** — exact phrase found in the message → highest confidence.
2. **Token overlap** — how many words the message shares with a pattern (handles reordering
   and extra words).
3. **Fuzzy similarity** (`difflib.SequenceMatcher`) — catches typos and near-matches.

If nothing scores high enough, the bot returns a fallback response, and after two fallbacks in
a row it proactively suggests what it *can* help with.

## Roadmap / Ideas for Future Improvement

- [ ] Persist conversation history to a database
- [x] Add multi-language support (Persian/English)
- [x] Deploy to Render with a live demo link
- [ ] Swap rule-based matching for an embeddings-based intent classifier


## Why I built this

I built this project to get hands-on with Flask and understand how a chatbot actually
decides what to say — not just calling an API, but writing the matching logic myself.
The first version only matched exact substrings, so I went back and added token-overlap
and fuzzy-string scoring to handle typos and reworded questions. I also learned the hard
way why templates/static folders matter in Flask (my first version silently failed to
find the HTML file), and picked up the basics of deploying a Python app to production
with Gunicorn on Render.

Next, I'd like to add multi-language support and swap the rule-based matching for a
small embeddings-based classifier.

## 📄 License

This project is open source and available for learning and portfolio purposes.
