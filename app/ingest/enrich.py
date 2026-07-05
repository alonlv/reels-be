import logging

from app.ingest.categorize import categorize, normalize_category

log = logging.getLogger("enrich")


def enrich(
    provider, title: str, text: str
) -> tuple[str | None, str | None, str | None, str]:
    """Return ``(short, long, technical, category)`` for an item, never raising.

    Asks the model for short/long/technical explanations and a category; on any
    failure falls back to the raw text (short) and the keyword categoriser.
    Category is validated against the taxonomy and falls back to keywords when
    off-list.
    """
    try:
        ex = provider.explain(title, text)
        short = ex.get("short")
        long = ex.get("long")
        technical = ex.get("technical")
        category = normalize_category(ex.get("category")) or categorize(title, text)
    except Exception as exc:  # noqa: BLE001 — enrichment must never crash a caller
        log.warning("explain failed for %r: %s", title, exc)
        short = (text or "")[:400] or None
        long = None
        technical = None
        category = categorize(title, text)
    return short, long, technical, category
