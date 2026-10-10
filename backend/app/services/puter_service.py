import asyncio
import base64
import json
import logging
from typing import Optional, Dict, Any, List
import httpx

from backend.app.config import settings

logger = logging.getLogger("puter_service")

# Map of image_id -> asyncio.Event
_ai_waiters: Dict[str, asyncio.Event] = {}
# Map of image_id -> AI result payload
_ai_results: Dict[str, Dict[str, Any]] = {}


def register_waiter(image_id: str) -> asyncio.Event:
    """Registers an event waiter for an incoming image's Puter AI analysis."""
    ev = asyncio.Event()
    _ai_waiters[image_id] = ev
    return ev


def resolve_waiter(image_id: str, data: Dict[str, Any]):
    """Resolves any waiting request for an image's AI result."""
    _ai_results[image_id] = data
    if image_id in _ai_waiters:
        _ai_waiters[image_id].set()


def cleanup_waiter(image_id: str):
    """Clean up event and cached result."""
    _ai_waiters.pop(image_id, None)
    # We keep _ai_results briefly or let it be read


def get_cached_result(image_id: str) -> Optional[Dict[str, Any]]:
    return _ai_results.get(image_id)


async def wait_for_ai_result(image_id: str, timeout_seconds: float = 12.0) -> Optional[Dict[str, Any]]:
    """Awaits the AI result event up to timeout_seconds."""
    ev = _ai_waiters.get(image_id)
    if not ev:
        return _ai_results.get(image_id)

    try:
        await asyncio.wait_for(ev.wait(), timeout=timeout_seconds)
        return _ai_results.get(image_id)
    except asyncio.TimeoutError:
        return None
    finally:
        _ai_waiters.pop(image_id, None)


async def call_puter_ai_backend(
    image_bytes: bytes,
    mime_type: str,
    target_text: str,
    model: str = "gemini-2.5-flash"
) -> Optional[Dict[str, Any]]:
    """
    Directly invokes Puter AI Gateway if PUTER_AUTH_TOKEN is configured in backend settings.
    """
    token = settings.PUTER_AUTH_TOKEN
    if not token:
        return None

    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        prompt = (
            f"Inspect the provided image carefully. The image is a 3x3 grid containing 9 cells. The cells are numbered 1 to 9, reading left to right, top to bottom like this:\n"
            f"[1] [2] [3]\n[4] [5] [6]\n[7] [8] [9]\n\n"
            f'Your task is to find all cells that clearly contain ALL of the following objects: "{target_text}".\n'
            f'Return a comma-separated list of the cell numbers that match. If no cells match, return "None".\n'
            f'Do not include any other text, reasoning, or punctuation besides the numbers.'
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ]
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                "https://api.puter.com/puterai/openai/v1/chat/completions",
                headers=headers,
                json=payload
            )

        if resp.status_code == 200:
            res_json = resp.json()
            raw_text = res_json["choices"][0]["message"]["content"].strip()
            import re
            if re.match(r"^(none|null|no cells)\.?$", raw_text, flags=re.I) or ("none" in raw_text.lower() and not re.search(r"\d", raw_text)):
                digits = []
            else:
                comma_match = re.match(r"^([1-9](?:\s*,\s*[1-9])*)\.?$", raw_text)
                if comma_match:
                    digits = re.findall(r"[1-9]", comma_match.group(1))
                else:
                    bracket_match = re.search(r"\[\s*([0-9,\s]*)\s*\]", raw_text)
                    if bracket_match:
                        digits = re.findall(r"[1-9]", bracket_match.group(1))
                    else:
                        sanitized = re.sub(r"3\s*[xX*×by]\s*3", "", raw_text, flags=re.I)
                        sanitized = re.sub(r"9\s*(cells?|tiles?|squares?|grid)", "", sanitized, flags=re.I)
                        digits = re.findall(r"[1-9]", sanitized)

            unique_matches = sorted(list(set(int(d) for d in digits if 1 <= int(d) <= 9)))
            return {
                "matched_cells": unique_matches,
                "raw_output": raw_text,
                "model": model
            }
        else:
            logger.warning(f"Puter API error {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Error calling Puter AI backend: {e}")
        return None
