# Advanced Chatbot

A bilingual web-based FAQ chatbot built with Flask and Python.

This project focuses on designing an intent-based chatbot system that can understand user messages in English and Persian, classify them into predefined categories, and return appropriate responses through a simple web chat interface.

The main goal of this project was to explore chatbot architecture, text processing, intent classification, testing, and deployment practices without relying on external AI APIs.

## Overview

The chatbot receives a user's message, processes the text, identifies the relevant intent, and generates a response from a predefined knowledge base.

The system currently supports:

- English and Persian conversations
- Intent classification using rule-based matching
- Context-aware follow-up responses
- A browser-based chat interface
- Automated testing and evaluation

The project does not use a generative AI model. Instead, it uses a transparent classification pipeline where the decision process can be inspected and evaluated.

## Features

### Bilingual Support

The chatbot automatically detects English and Persian input and selects the appropriate response language.

### Intent Classification

The classification pipeline combines several matching approaches:

- Phrase matching
- Token overlap scoring
- Fuzzy matching for handling small typing mistakes
- Optional semantic similarity matching

A confidence threshold is used to decide whether a message should be assigned to an intent or handled as an unknown request.

### Conversation Context

The chatbot maintains limited conversation state during a user's session.

For example, after asking about a topic that requires clarification, a related short response can be interpreted using previous context.

### Testing and Evaluation

The project includes automated tests and an evaluation system to measure chatbot performance.

Current evaluation results:

- Accuracy: 92.4%
- Macro Precision: 97.4%
- Macro Recall: 92.3%
- Macro F1 Score: 94.2%

Test results:


50 passed


## Technologies

Backend:

- Python
- Flask
- Gunicorn

Frontend:

- HTML
- CSS
- JavaScript

Testing:

- pytest

Additional tools:

- difflib for fuzzy text matching
- sentence-transformers for optional semantic matching

## Project Structure


app.py Flask application and routes
chatbot.py Chatbot logic and intent classification
semantic_matcher.py Optional semantic matching module
intents.json Chatbot knowledge base
evaluate.py Evaluation script
data/ Evaluation dataset
tests/ Automated tests
templates/ HTML templates
static/ Frontend files


## How It Works

The chatbot follows these main steps:

1. Receive user input
2. Normalize and process the text
3. Compare the message with available intents
4. Calculate confidence scores
5. Select the most suitable intent
6. Return the corresponding response

If the confidence score is not high enough, the chatbot returns a fallback response instead of making an uncertain prediction.

## Installation

Clone the repository:


git clone https://github.com/faegheh8114/advanced_chatbot.git

Install dependencies:

pip install -r requirements.txt

For running tests:

pip install -r requirements-dev.txt
Running the Application

Start the Flask application:

python app.py

The chatbot will be available through the local web interface.

Running Tests

Run the test suite:

pytest -q

Run the evaluation script:

python evaluate.py
Deployment

The project supports deployment using Gunicorn.

Example:

gunicorn app:app --bind 0.0.0.0:$PORT
Limitations

The project was designed as a lightweight chatbot system. Current limitations include:

No database or permanent conversation storage
No user authentication system
Conversation state is stored in memory
No external LLM API integration

These choices were made to keep the architecture simple and focus on chatbot design, classification, and software engineering practices.

Future Improvements

Possible future improvements include:

Adding database support for conversation history
Expanding contextual responses to more intents
Adding CI/CD automation
Improving monitoring and logging
Creating an administration interface
Author

Faegheh Mashayekh

Computer Engineering Student
