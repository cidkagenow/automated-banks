"""Vision layer — two narrow capabilities only:

  1. classify(screenshot, candidates) -> state name
     Given a list of (state_name, description), pick the matching one.
     The vision model only CLASSIFIES; it never picks coordinates.

  2. extract(screenshot, schema_hint) -> dict
     Pull structured data (balances, transactions) out of the final screen.

This split is the architectural lesson from v1: when we asked the model to
both identify the screen AND choose the next action AND pick exact pixel
coordinates, it picked wrong coordinates. Splitting it means each call has
one job.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-pro"
MAX_TOKENS = 4096


class VisionError(RuntimeError):
    pass


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise VisionError(
                "GEMINI_API_KEY not set. Get one at https://aistudio.google.com/apikey "
                "and add it to .env."
            )
        _client = genai.Client(api_key=key)
    return _client


def _model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def _thinking() -> types.ThinkingConfig:
    # Pro requires thinking_budget>=128; Flash supports 0.
    return types.ThinkingConfig(thinking_budget=128 if "pro" in _model() else 0)


def _generate(prompt: str, screenshot: Path, system: str | None = None) -> str:
    client = _get_client()
    image = types.Part.from_bytes(data=screenshot.read_bytes(), mime_type="image/png")
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        max_output_tokens=MAX_TOKENS,
        temperature=0.0,
        thinking_config=_thinking(),
    )
    if system:
        cfg.system_instruction = system
    try:
        resp = client.models.generate_content(
            model=_model(), contents=[image, prompt], config=cfg,
        )
    except Exception as e:  # noqa: BLE001
        raise VisionError(f"Gemini request failed: {e}") from e
    text = (resp.text or "").strip()
    if not text:
        raise VisionError("Gemini returned an empty response.")
    return text


def _parse_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise VisionError(f"Model did not return valid JSON: {text[:300]}") from e


def classify(screenshot: Path, candidates: list[tuple[str, str]]) -> str:
    """Pick which of the candidate states matches the screenshot.

    `candidates` is a list of (state_name, description) tuples. The model
    must return one of the state_name values, or "unknown".
    """
    options = "\n".join(f"  - {name}: {desc}" for name, desc in candidates)
    valid = [name for name, _ in candidates] + ["unknown"]
    prompt = (
        "You are looking at an iPhone screenshot. Identify which of these "
        "states the screen is currently in:\n\n"
        f"{options}\n\n"
        f"Respond with JSON: {{\"state\": \"<one of: {', '.join(valid)}>\"}}. "
        "If nothing matches confidently, return \"unknown\". Do not include "
        "any other fields."
    )
    raw = _parse_json(_generate(prompt, screenshot))
    state = str(raw.get("state", "unknown"))
    if state not in valid:
        return "unknown"
    return state


def extract(screenshot: Path, instruction: str) -> dict[str, Any]:
    """Extract structured data from the screenshot per the instruction."""
    prompt = (
        f"{instruction}\n\n"
        "Respond with a single JSON object only — no surrounding text."
    )
    return _parse_json(_generate(prompt, screenshot))


def find_icon(screenshot: Path, app_name: str) -> tuple[float, float] | None:
    """Locate an app icon on the current iPhone screenshot.

    Returns normalized (x, y) of the icon center where x,y in [0,1], or
    None if the icon is not visible on this screen. Use this instead of
    Spotlight to launch apps — clicks on found icons are far more reliable
    than iPhone Mirroring's keyboard-shortcut-driven Spotlight path.
    """
    prompt = (
        f"Find the '{app_name}' app icon on this iPhone screenshot. "
        f"Look across the entire visible area including the dock. "
        f"If you can see it, respond with: "
        f'{{"found": true, "x": <number 0..1>, "y": <number 0..1>}} '
        f"giving the icon's CENTER in normalized image coordinates "
        f"(x: 0 = left edge, 1 = right edge; y: 0 = top, 1 = bottom). "
        f"If the icon is NOT visible on this screen, respond with: "
        f'{{"found": false}}. Respond with ONE JSON object, nothing else.'
    )
    raw = _parse_json(_generate(prompt, screenshot))
    if not raw.get("found"):
        return None
    try:
        x = float(raw["x"]); y = float(raw["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return (x, y)
