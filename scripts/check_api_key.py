"""Confirm the Anthropic API key in .env works. Costs a fraction of a cent.

Usage:
    python scripts/check_api_key.py
"""
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY is missing from .env")

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
message = client.messages.create(
    model="claude-haiku-5-5",
    max_tokens=20,
    messages=[{"role": "user", "content": "Reply with exactly: API key works"}],
)
print(message.content[0].text)
