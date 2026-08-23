"""Entry point for Saipa Mashayekh 3299 — Internal Automation Platform.

The original portfolio chatbot has moved to legacy_chatbot/ and still runs
standalone (`python legacy_chatbot/app.py`); it isn't part of this platform.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
