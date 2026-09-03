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
he chatbot receives the text, then compares it with the intents that were introduced before, and chooses the closest one. The first step was simple matching, but it was not enough because users would ask different types of questions for the same thing. For example:
```
"What is the price?"
"How much does it cost?"
```

Both questions should lead to the same intent.

To handle this, I improved the matching system by combining multiple techniques such as substring matching, token overlap, and fuzzy similarity.
## Features

### Custom Intent Matching

The chatbot uses a custom matching system written in Python.

I mixed three ways: exact match, token overlap, and fuzzy matching with difflib. The main reason was typos — many people would ask different types of questions but mean one thing. How these three methods work together is explained in the "How the Matching Works" section below.
### Conversation Context

The application keeps a small amount of conversation state using Flask sessions.

Flask's default session mechanism stores signed session data on the client side, rather than maintaining a server-side session store. For this project I only store a small amount of non-sensitive conversation context, so that was acceptable. If the application needed sensitive data, large conversation histories, or more complex multi-instance state management, I would move the state to a server-side store such as Redis.

Each user has a separate session, so conversations do not interfere with each other.
### Bilingual Support

The chatbot supports both English and Persian messages and responds in the same language.

I used a lightweight Unicode-based language detection approach rather than an external language-detection library. The chatbot checks whether the input contains characters from the Arabic-script Unicode range, which is sufficient for distinguishing Persian from English in this project. Then, after identifying the intent, it selects the corresponding Persian or English response. I chose this approach because the project only needed to distinguish between two supported languages, so using a full language-detection model would have added unnecessary complexity.

### Web Chat Interface

The project includes a simple chat interface with message bubbles, avatars, timestamps, and a typing indicator, so it feels responsive rather than just displaying a sequence of messages.

The main challenge was coordinating the message bubbles, timestamps, avatars, and typing indicator with the JavaScript request/response flow. I kept the interface relatively simple because the main focus of the project was the chatbot and intent-matching system, not frontend design. I refined the UI until the interaction felt clear and natural, while keeping the frontend separate from the matching logic.

## How the Matching Works

I don't use a weighted average of the three methods. They work as a decision hierarchy.

First, I check for a phrase-level substring match. If a known pattern appears as a complete phrase in the user's message, I treat it as a high-confidence match with a score of 1.0. If there is no substring match, I calculate both token-overlap and fuzzy-similarity scores, and use the stronger of the two. The final score then has to pass a confidence threshold of 0.78 before the intent is accepted.

I chose this approach because the three methods measure different things. A substring match is strong evidence of an exact phrase, while token overlap and fuzzy similarity are more useful for reordered words and small spelling differences.

If two intents get similar scores, I use deterministic tie-breaking rules instead of choosing randomly. The chatbot first compares the matching score, and when the scores are equal, it uses the matched pattern length and then the intent tag to make the result deterministic. This means the same input produces the same result every time.

The 0.78 threshold was chosen empirically rather than from a specific mathematical formula. I used it as a confidence cutoff and then evaluated the classifier on a labeled test set. I also added regression tests for cases where lower-confidence matching could produce false positives.

A simple example is the input "helo" instead of "hello". Substring matching would not find the exact pattern because one character is missing. Fuzzy matching can still recognize the high character-level similarity and classify it as a greeting. On the other hand, substring matching is stronger when the user includes the exact phrase inside a longer message. For example, "hi there, quick question for you" can be recognized directly because "hi" is an exact pattern.

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

First, I would try to develop the matching so it's clear and understandable when it's texting to users.

A good next step would be to improve the intent dataset and add a proper semantic matching layer using sentence embeddings. This would help the chatbot handle more complex paraphrases that rule-based matching may miss.

I would also move the conversation state from the current in-memory store to something like Redis if I wanted to deploy it with multiple workers or keep conversations persistent.

So I wouldn't replace the whole system with an LLM right away. I would start by making the parts of the current architecture that are causing problems more reliable and able to handle more work.
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

There are some things that this doesn't cover.

This chatbot is designed to follow rules. It doesn't come up with new answers like large language models do. Instead, it chooses responses based on predefined intentions and the matching logic used in the project.

For this version, I chose not to use an LLM or external API because the main goal was to understand and build the intent-matching process myself. Using embedding-based semantic matching would be a good next step for dealing with more complex paraphrases. This would let us keep the current rule-based layer for matches that are easy to predict and test.
## License

This project is open source and available for learning and portfolio purposes.
