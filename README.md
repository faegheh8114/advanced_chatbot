# Advanced Chatbot

A lightweight bilingual chatbot built with Flask.

This project is a rule-based conversational chatbot with a custom intent matching system. It can understand different ways of asking the same question, handle small typing mistakes, and keep a short conversation context for each user session.

The goal of this project was to understand how chatbot systems work internally by building the matching logic instead of relying on external chatbot APIs.

## Live Demo

Try it here: https://advanced-chatbot-16cy.onrender.com

The first request can take around 30 seconds since the free Render instance needs to wake up after being idle.

## Screenshots

### Chat interface

![Chat interface](screenshots/screen1.png)

### Example conversation:

![Example conversation](screenshots/screen2.png)

### Intent matching example:

![Intent matching example](screenshots/screen3.png)

## Project Overview
The chatbot receives the user's message, then compares it with the intents that were defined before, and picks the closest one. The first version just did simple matching, but that wasn't enough because users ask the same question in different ways. For example:
```
"What is the price?"
"How much does it cost?"
```

Both questions should lead to the same intent.

To handle this, I improved the matching system by combining multiple techniques such as substring matching, token overlap, and fuzzy similarity.
## Features

### Custom Intent Matching

The chatbot uses a custom matching system written in Python.

I combined three ways of matching: exact match, token overlap, and fuzzy matching using difflib. One method alone wasn't enough — the main reason was typos, and also that different people would phrase the same question in different ways but mean the same thing. How these three methods work together is explained in the "How the Matching Works" section below.
### Conversation Context

The application keeps a small amount of conversation state using Flask sessions.

Flask's default session mechanism stores signed session data on the client side rather than maintaining a server-side session store. Since this project only needs a small amount of non-sensitive conversation context, that was an acceptable tradeoff. If the app needed sensitive data, larger conversation histories, or multi-instance state management, I'd move this to a server-side store such as Redis.

Each user has a separate session, so conversations do not interfere with each other.
### Bilingual Support

The chatbot supports both English and Persian messages and responds in the same language.

Language detection uses a lightweight Unicode-based check rather than an external language-detection library: the input is checked for characters in the Arabic-script Unicode range, which is enough to distinguish Persian from English for this project. Once the intent is identified, the chatbot picks the corresponding Persian or English response. A full language-detection model would have been unnecessary complexity for a project that only needs to tell two languages apart.

### Web Chat Interface

The project includes a simple chat interface with message bubbles, avatars, timestamps, and a typing indicator, so the conversation feels responsive rather than just a sequence of plain messages.

The main challenge here was coordinating the bubbles, timestamps, avatars, and typing indicator with the JavaScript request/response flow. I kept the interface relatively simple since the main focus of the project was the chatbot and intent-matching logic, not frontend design — I refined the UI until the interaction felt clear and natural, while keeping the frontend separate from the matching logic.

## How the Matching Works

The three matching methods don't run as a weighted average — they work as a decision hierarchy, since each one measures something different.

First, the chatbot checks for a phrase-level substring match. If a known pattern appears as a complete phrase in the user's message, that's treated as a high-confidence match with a score of 1.0. A substring match is strong evidence of an exact phrase, so there's no need to check anything else once it's found.

If there's no substring match, the chatbot calculates both a token-overlap score and a fuzzy-similarity score (using difflib.SequenceMatcher) and takes the stronger of the two. These two are better suited for reordered words and small spelling differences than an exact substring ever could be. The final score then has to clear a confidence threshold of 0.78 before an intent is accepted; anything below that falls back to a default response.

The threshold itself came from testing rather than a formula — I evaluated the classifier against a labeled test set and landed on 0.78 as the cutoff, then added regression tests for the false-positive cases that showed up with lower-confidence matches.

A simple example: the input "helo" instead of "hello" has no substring match since a character is missing, but fuzzy matching still catches the high character-level similarity and classifies it correctly. On the other hand, substring matching wins when the exact phrase shows up inside a longer message — "hi there, quick question for you" is recognized directly because "hi" is an exact pattern, without needing fuzzy matching at all.
## Challenges and Solutions

### False Matches with Short or Common Words

Once I added fuzzy matching, I noticed something odd: very short inputs like "hi", "ok", or "no" (and similarly short Persian words) sometimes matched the wrong intent. Because of substring overlap and character-level similarity, short words picked up an unrealistically high score against patterns they had almost nothing to do with.

I fixed this by making the scoring stricter for short inputs, so fuzzy similarity alone could no longer be enough to select an intent on its own.

### Getting deployment right

The app ran fine locally, but getting it ready for production took some adjusting. I had to go through the Flask setup, requirements, and the run command to make sure everything matched what Render expected. Most of this was reading through configs carefully rather than one single bug — after a few rounds of fixing things, it deployed and ran correctly.

Most of the debugging along the way came from reading error messages and testing things directly in the code, with the occasional search when a Flask or deployment error needed more context.

### Managing user sessions
A chatbot should keep each user's conversation separate. Flask sessions were added to store short-term context and prevent different users from affecting each other's conversations.
## Evaluation
The chatbot was evaluated using the project's evaluation script.

Results:

| Metric | Score |
|--------|-------|
| Accuracy | 92.4% |
| Macro Precision | 97.4% |
| Macro Recall | 92.3% |
| Macro F1 | 94.2% |

## Tech Stack

| Area | Technology |
|------|------------|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Matching Logic | difflib and custom scoring |
| Data | JSON-based intents |
| Testing | pytest |
| Deployment | Render |

## Project Structure

```text
advanced_chatbot/
│
├── app.py
├── chatbot.py
├── evaluate.py
├── intents.json
│
├── templates/
│   └── index.html
│
├── static/
│   ├── style.css
│   └── script.js
│
└── tests/
    └── test_chatbot.py
```
##  Installation

Clone the repository:

```bash
git clone https://github.com/faegheh8114/advanced_chatbot.git
cd advanced_chatbot
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment.

**Windows:**

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Running Tests

Run the test suite with:

```bash
pytest
```

## Future Improvements

Possible improvements for future versions:

- Make the matching clearer and more understandable when the chatbot replies to users
- Improve the intent dataset and add a proper semantic matching layer using sentence embeddings, to handle more complex     paraphrases that rule-based matching may miss
- Move conversation state from the current in-memory store to something like Redis, if deploying with multiple workers or if conversations need to persist

I wouldn't replace the whole system with an LLM right away — I'd start by making the parts of the current architecture that cause problems more reliable and able to handle more load.

## What I Learned

The hardest part of this project was the intent-matching logic itself. I started out assuming simple text comparison would be enough, but quickly realized how much people vary their phrasing compared to what's actually stored in the intents file. I rewrote the matching logic several times trying to balance two things that pull in opposite directions: catching different phrasings of the same question, without opening the door to wrong matches.

Managing session state was its own smaller challenge — keeping each user's conversation isolated took more care than I expected going in.

If I started over, I'd plan the project structure a bit more before writing code:

- Add tests earlier instead of after the fact
- Keep the matching logic separate from response generation from the start
- Structure the intent data more deliberately

Even so, going through it this way is exactly what taught me how a chatbot actually works under the hood, and why some approaches that sound reasonable break down in practice.

## Why I Built This

I built this project because I wanted to understand what happens behind a chatbot instead of only using existing chatbot APIs.

Building the intent matching system myself helped me understand the challenges behind language processing, especially how small changes in wording can completely change the result.

This project started as a simple rule-based chatbot, but gradually became a deeper exploration of matching strategies, testing, and improving reliability.

## Limitations

There are some things this project doesn't cover.

This chatbot is intentionally designed as a rule-based system. It doesn't generate new answers like large language models do — instead, it selects responses based on predefined intents and the matching logic described above.

I chose not to use an LLM or an external API for this version because the main goal was to understand and build the intent-matching process myself, not to rely on an existing solution. Semantic matching using embeddings would be a good next step for handling more complex paraphrasing — that's covered in Future Improvements above.
## License

This project is open source and available for learning and portfolio purposes.
