"""Topic categorisation for feed items.

A small, dependency-free taxonomy shared by the LLM prompt (which is asked to
pick one) and a keyword fallback used when the model is unavailable or returns
something off-taxonomy.
"""

# Ordered most-specific first — the first rule that matches wins.
CATEGORIES = [
    "policy",
    "business",
    "open-source",
    "research",
    "tutorial",
    "product",
    "other",
]

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("policy", (
        "regulat", "lawsuit", "sued", "copyright", "privacy", "ethic", "safety",
        "governance", "banned", "ai act", "policy", "legislation",
        "misinformation", "election", "watermark", "guardrail",
    )),
    ("business", (
        "funding", "raises", "raised", "valuation", "acqui", " ipo", "revenue",
        "layoff", "partnership", "deal", "invest", "startup", "billion",
        "million", "ceo", "market", "stock", "earnings",
    )),
    ("open-source", (
        "open source", "open-source", "open-weight", "open weights", "weights",
        "github", "apache", "checkpoint", "released the model", "model release",
        "now available on hugging face",
    )),
    ("research", (
        "paper", "arxiv", "benchmark", "state-of-the-art", " sota", "study",
        "researchers", "neural", "algorithm", "dataset", "fine-tun",
        "pretrain", "architecture", "evaluation",
    )),
    ("tutorial", (
        "how to", "how-to", "tutorial", "guide", "walkthrough",
        "step-by-step", "build a", "getting started", "hands-on",
    )),
    ("product", (
        "launch", "announc", "introducing", "unveil", "now available",
        "new feature", "update", "app", "release", "ships", "rolls out", "api",
    )),
]


def categorize(title: str | None, text: str = "") -> str:
    """Best-effort keyword categorisation. Always returns a valid category."""
    hay = f"{title or ''} {text or ''}".lower()
    for category, keywords in _RULES:
        if any(k in hay for k in keywords):
            return category
    return "other"


def normalize_category(value: str | None) -> str | None:
    """Coerce a model-supplied label to the taxonomy, or None if it doesn't fit."""
    if not value:
        return None
    v = value.strip().lower().replace("_", "-").replace(" ", "-")
    return v if v in CATEGORIES else None
