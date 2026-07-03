SUMMARIZE_SYSTEM = (
    "You summarize AI/ML/Data-Science articles for an internal feed. "
    "Reply with 2-3 punchy sentences describing what the item is and why it "
    "matters. No preamble, no markdown."
)


def summarize_user(title: str, text: str) -> str:
    return f"Title: {title}\n\nContent:\n{text[:6000]}"
