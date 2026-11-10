"""Phase 11, Task 1: check that the Gemini key works.

Run from the backend/ folder:  python -m llm.smoke_test
Optionally test another model:  python -m llm.smoke_test gemini-3.1-flash-lite
"""
import sys
import time

from google.genai import errors

from llm.client import GEMINI_MODEL, get_client

model = sys.argv[1] if len(sys.argv) > 1 else GEMINI_MODEL
client = get_client()

flash = sorted(m.name for m in client.models.list() if "flash" in m.name)
print("Flash models this key can use:")
for name in flash:
    print("  ", name)

print(f"\nAsking {model} (up to 2 attempts, 120 s each)...", flush=True)
start = time.time()
try:
    response = client.models.generate_content(
        model=model, contents="Reply with exactly one word: ready")
except errors.APIError as e:
    print(f"FAILED after {time.time() - start:.0f} s: {e.code} {e.status}")
    print(e.message)
    sys.exit(1)

usage = response.usage_metadata
print(f"Answer: {response.text.strip()}  ({time.time() - start:.1f} s)")
print(f"Tokens: {usage.prompt_token_count} in, {usage.candidates_token_count} out, "
      f"{usage.thoughts_token_count or 0} thinking")
