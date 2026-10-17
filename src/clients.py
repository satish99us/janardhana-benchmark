"""
Thin wrappers around the three providers, all exposing the same method:

    client.classify(image_bytes, media_type) -> dict

Each returns a parsed dict of finding -> label. All the provider-specific
mess (how you attach an image, how the response is shaped) is hidden here so
the rest of the code doesn't care which model it's talking to.

Keys are read from environment variables (loaded from .env by run_benchmark).
NEVER hardcode keys in this file.
"""

import os
import json
import time
import base64
from .config import MAX_RETRIES, RETRY_BACKOFF
from .prompts import (SYSTEM_PROMPT, build_user_prompt,
                      REPORT_SYSTEM_PROMPT, build_report_prompt)


def _extract_json(text: str) -> dict:
    """
    Models sometimes wrap JSON in ```json fences or add stray text despite
    instructions. Strip fences and grab the outermost {...} block.
    """
    if not text:
        raise ValueError("empty response")
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    # find outermost braces
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in response: {text[:200]}")
    return json.loads(t[start : end + 1])


def _with_retries(fn):
    """Call fn() with simple exponential backoff on any exception."""
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - we genuinely want to retry anything transient
            last = e
            wait = RETRY_BACKOFF ** attempt
            time.sleep(wait)
    raise last


# ---------------------------------------------------------------------------
# Anthropic / Claude
# ---------------------------------------------------------------------------
class ClaudeClient:
    def __init__(self, model_id: str):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model_id = model_id

    def classify(self, image_bytes: bytes, media_type: str) -> dict:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        def call():
            resp = self.client.messages.create(
                model=self.model_id,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": build_user_prompt()},
                        ],
                    }
                ],
            )
            text = "".join(block.text for block in resp.content if block.type == "text")
            return _extract_json(text)

        return _with_retries(call)

    def generate_report(self, image_bytes: bytes, media_type: str) -> dict:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        def call():
            resp = self.client.messages.create(
                model=self.model_id, max_tokens=1500, system=REPORT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": build_report_prompt()},
                ]}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            return _extract_json(text)

        return _with_retries(call)


# ---------------------------------------------------------------------------
# OpenAI / GPT
# ---------------------------------------------------------------------------
class OpenAIClient:
    def __init__(self, model_id: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model_id = model_id

    def classify(self, image_bytes: bytes, media_type: str) -> dict:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{media_type};base64,{b64}"

        def call():
            resp = self.client.chat.completions.create(
                model=self.model_id,
                max_completion_tokens=1024,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": build_user_prompt()},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            )
            text = resp.choices[0].message.content
            return _extract_json(text)

        return _with_retries(call)

    def generate_report(self, image_bytes: bytes, media_type: str) -> dict:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{media_type};base64,{b64}"

        def call():
            resp = self.client.chat.completions.create(
                model=self.model_id, max_completion_tokens=1500,
                messages=[
                    {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": build_report_prompt()},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]},
                ],
            )
            return _extract_json(resp.choices[0].message.content)

        return _with_retries(call)


# ---------------------------------------------------------------------------
# Google / Gemini
# ---------------------------------------------------------------------------
class GeminiClient:
    def __init__(self, model_id: str):
        from google import genai
        self.genai = genai
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model_id = model_id

    def classify(self, image_bytes: bytes, media_type: str) -> dict:
        from google.genai import types

        def call():
            resp = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                    SYSTEM_PROMPT + "\n\n" + build_user_prompt(),
                ],
            )
            return _extract_json(resp.text)

        return _with_retries(call)

    def generate_report(self, image_bytes: bytes, media_type: str) -> dict:
        from google.genai import types

        def call():
            resp = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                    REPORT_SYSTEM_PROMPT + "\n\n" + build_report_prompt(),
                ],
            )
            return _extract_json(resp.text)

        return _with_retries(call)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_client(provider: str, model_id: str):
    if provider == "anthropic":
        return ClaudeClient(model_id)
    if provider == "openai":
        return OpenAIClient(model_id)
    if provider == "google":
        return GeminiClient(model_id)
    raise ValueError(f"No automated client for provider '{provider}'. "
                     f"(Harrison/manual models are scored separately.)")
