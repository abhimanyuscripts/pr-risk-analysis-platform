"""Gemini client for the LLM engine (Phase 11).

The model is chosen in backend/.env (GEMINI_MODEL), so switching models later,
or comparing two in the report, is a one-line change.
"""
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from backend/.env")
    # Explicit timeout in milliseconds: never call an external API without one.
    # The library retries 5 times silently by default; 2 attempts keeps failures visible.
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=120_000, retry_options=types.HttpRetryOptions(attempts=2)))
