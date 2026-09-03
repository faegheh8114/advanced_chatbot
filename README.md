# Advanced Chatbot

A lightweight, bilingual chatbot built with Flask.

It is a rule-based conversational chatbot with a custom intent matching system. It can understand different ways of asking the same question, handle minor typos, and maintain short-term conversation context for each user.

The goal of this project was to understand how chatbot systems work by building the matching logic instead of relying on external APIs.


## Live Demo

You can try the chatbot here:

https://advanced-chatbot-16cy.onrender.com

The first request may take around 30 seconds because the free Render instance needs to wake up after inactivity.

## Screenshots

### Chat interface

![Chat interface](screenshots/screen1.png)

### Example conversation:

![Example conversation](screenshots/screen2.png)

### Intent matching example:

![Intent matching example](screenshots/screen3.png)

## Project Overview

The chatbot receives a user message, compares it with predefined intents, selects the closest match, and returns an appropriate response.

The first version of this project used simple matching, but it quickly became clear that users do not always ask questions in exactly the same way.

For example:
```
"What is the price?"
"How much does it cost?"
```

Both questions should elicit the same response.

To achieve this, I enhanced the matching system by incorporating various techniques, including substring matching, token overlap, and fuzzy similarity.

## Features

### Custom Intent Matching

The chatbot uses a custom matching system written in Python.

It combines:

- Exact phrase matching
- Token overlap scoring
- Fuzzy similarity matching using Python's difflib.

This allows the chatbot to recognize different versions of similar questions.

### Conversation Context

The application uses Flask sessions to keep a small amount of conversation state.

Each user has a separate session, so conversations do not interfere with each other.

### Bilingual Support

The chatbot supports English and Persian messages and responds in the same language.

### Web Chat Interface

The project includes a simple chat interface with message bubbles.

- Message bubbles
- User and bot avatars
- Timestamps
- A typing indicator
- Responsive layout

## How the Matching Works

The chatbot calculates a score for every incoming message based on available patterns.

The scoring process includes:

1. Substring matching verifies if a known phrase is present in the user's message.

2. Token Overlap: The system compares shared words between the user's message and known patterns.

3. Fuzzy Similarity: Use the difflib.SequenceMatcher class to detect similar phrases and minor typos.

The chatbot selects the intent with the highest score. If no intent receives a reliable score, the chatbot returns a fallback response.

## Challenges and Solutions

### False Matches with Short or Common Words

After adding fuzzy matching, it became clear that very short inputs such as "hi," "ok," or "no" could sometimes match the wrong intent. Short words can produce misleading similarity scores when compared with longer patterns.

I fixed this by making the matching rules stricter for short inputs. This prevents fuzzy similarity alone from selecting an intent.

### Getting deployment right

The app ran correctly locally, but deployment required adjustments to the Flask configuration, dependencies, and production run command. After testing and fixing the configuration, the app deployed successfully on Render.



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

- Store conversation history in a database
- Experiment with semantic matching using embeddings
- Add more complex conversation flows
- Expand the intent dataset




## What I Learned

The intent-matching logic was the hardest part of this project. I initially assumed simple text comparison would be enough, but different ways of phrasing the same question made matching more challenging than expected.

I also learned that improving recall can easily introduce false matches, so the matching system needs a balance between flexibility and reliability.

If I started the project again, I would:

* Plan the project structure earlier
* Add tests from the beginning
* Keep the matching logic separate from response generation
* Structure the intent data more deliberately

This project gave me a better understanding of how rule-based chatbots work and highlighted the limitations of simple text matching.


## Why I Built This

I built this project to understand how chatbots work rather than relying on an external API.

Building the intent-matching system myself helped me understand the challenges of handling different phrasings and balancing flexible matching with reliable results.

The project started as a simple rule-based chatbot and gradually evolved into an exploration of matching strategies, testing, and reliability.

## Limitations

This chatbot is intentionally designed as a rule-based system.

Unlike large language models, it does not generate new answers. Instead, it selects responses based on predefined intents and the matching logic implemented in the project.

### License

This open-source project is available for learning and portfolio purposes.
