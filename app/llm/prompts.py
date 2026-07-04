import json
import re

SUMMARIZE_SYSTEM = (
    "You summarize AI/ML/Data-Science articles for an internal feed. "
    "Reply with 2-3 punchy sentences describing what the item is and why it "
    "matters. No preamble, no markdown."
)


def summarize_user(title: str, text: str) -> str:
    return f"Title: {title}\n\nContent:\n{text[:6000]}"


# The feed shows two layers per item: a one-line "short" blurb that fits the
# TikTok-style card at a glance, and a "long" deep-dive revealed by "see more".
# We ask the model for both in a single call and return them as JSON.
EXPLAIN_SYSTEM = (
    "You explain AI/ML/Data-Science news for a scrollable, TikTok-style feed. "
    "Given one article, produce two explanations of the same topic:\n"
    '- "short": a single punchy sentence (max ~30 words) saying what it is and '
    "why it matters. This is the headline blurb.\n"
    '- "long": a richer 3-5 sentence deep-dive with the key details, context, '
    "and implications.\n"
    "Write for a technical but busy audience. Do not repeat the title verbatim. "
    'Reply with ONLY a JSON object of the form {"short": "...", "long": "..."} '
    "— no preamble, no markdown, no code fences."
)


def explain_user(title: str, text: str) -> str:
    return f"Title: {title}\n\nContent:\n{text[:6000]}"


def parse_explanation(raw: str) -> dict | None:
    """Extract ``{"short", "long"}`` from a model reply, or None if unparseable.

    Models don't always honour "JSON only" — they may wrap the object in code
    fences or add stray prose. We strip fences and grab the first ``{...}``
    block before parsing.
    """
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    short = str(data.get("short") or "").strip()
    long = str(data.get("long") or "").strip()
    if not short and not long:
        return None
    return {"short": short or None, "long": long or None}


def coerce_explanation(raw: str) -> dict:
    """Always return a ``{"short", "long"}`` dict, never raising.

    If the model didn't return usable JSON, fall back to treating the whole
    reply as the short blurb so the item still renders.
    """
    parsed = parse_explanation(raw)
    if parsed:
        return parsed
    cleaned = (raw or "").strip()
    return {"short": cleaned[:400] or None, "long": None}
