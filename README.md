# Advanced Chatbot

A bilingual (English/Persian) FAQ chatbot built with Flask. I built this to actually understand how intent classification works instead of just wiring up an API call to GPT and calling it done.

No LLM API is used anywhere in this project. It's a rule-based classification pipeline, so every response the bot gives can be traced back to an actual decision, not a black box.

## What it does

You send a message, in English or Persian, and the bot tries to figure out what you're asking and reply from a predefined knowledge base. If it isn't confident about the match it says so instead of guessing. I'd rather have it admit it doesn't know something than make up a confident wrong answer.

Main pieces:
- Detects English vs. Persian automatically
- Classifies intent using phrase matching, token overlap, and fuzzy matching for typos
- Optional semantic similarity matching (sentence-transformers) for cases the other methods miss
- Keeps a little conversation context so short follow-up messages still make sense
- Basic browser chat interface
- Test suite and an evaluation script

## Why not just use an LLM

Honestly, partly because the course required something rule-based, but also because I wanted to actually understand the mechanics instead of trusting a pretrained model to handle everything silently. It took longer to build and it's definitely less flashy than "connect to GPT-4," but I can point to exactly why the bot classified a message the way it did, which felt more useful for learning.

The part I'm actually proud of is the bilingual support. Persian isn't exactly a language most tutorials or examples cover, so getting the bot to reliably tell English and Persian apart and respond correctly in each took real effort, not just plugging in a library. As an Iranian this part mattered to me more than it probably would to most people building this.

## How classification works

The input text gets cleaned up first, then compared against the known intent phrases using a combination of token overlap and fuzzy matching (this is what catches typos). If semantic matching is enabled it also scores the message against intent examples using sentence embeddings. Whichever intent scores highest wins, as long as it clears a minimum confidence threshold. If nothing clears that bar, the bot falls back to a generic "not sure" response instead of picking the closest guess anyway.

The fuzzy matching part took way longer than I expected. It kept misfiring on short messages, matching things it shouldn't have and missing typos it should've caught, so I ended up rewriting it a few times before it actually behaved. Out of everything in this project, that's the piece I spent the most time debugging.

## Project structure

```
app.py                  Flask app + routes
chatbot.py              Core chatbot logic / intent classification
semantic_matcher.py     Optional semantic matching (sentence-transformers)
intents.json            Knowledge base
evaluate.py             Evaluation script
data/                   Evaluation dataset
tests/                  pytest test suite
templates/              HTML templates
static/                 CSS/JS
```

## Setup

```bash
git clone https://github.com/faegheh8114/advanced_chatbot.git
cd advanced_chatbot
pip install -r requirements.txt
```

Running tests also needs:
```bash
pip install -r requirements-dev.txt
```

## Running it

```bash
python app.py
```

Then just open the local URL it prints.

## Tests and evaluation

```bash
pytest -q
```

50 tests, all passing as of the last run. For the actual performance numbers:

```bash
python evaluate.py
```

Accuracy is sitting around 92% on the evaluation set. Precision is a bit higher than recall, so when the bot does commit to an intent it's usually right, it's just a little conservative and sometimes falls back to "not sure" on things it probably could have answered.

I didn't land on the confidence threshold with any real formula, it was mostly trial and error. I ran the evaluation script a bunch of times with different values, saw where it was misclassifying things or being too trigger-happy, adjusted, and reran it. After enough rounds of that I got a feel for where the tradeoff between "confident but sometimes wrong" and "safe but says I don't know too often" actually was, and picked the threshold from there.

## Deploying

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

Standard Gunicorn setup, nothing special.

## Limitations

Conversation management is the weakest part right now. It only keeps a little bit of context between messages, so it can't really carry a conversation or handle every follow-up question the way you'd want, it just handles a few specific cases well and struggles outside of that. Beyond that: no database, so nothing persists between restarts. No login system. No fallback to an actual LLM for questions completely outside the knowledge base, it just says it doesn't know. These are fine for a course project but would need addressing for anything closer to production.

## What's next

Conversation management is the first thing I'd fix, it needs to actually track context properly instead of the limited version it has now. Beyond that: hook up a real database for conversation history, add more intents, and set up basic CI so tests run automatically instead of me remembering to run them by hand. I'd also like to log the messages that hit the fallback response so I can see what the classifier is actually missing.

## Author

Faegheh Mashayekh, Computer Engineering student
