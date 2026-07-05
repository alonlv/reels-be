from html import unescape
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


def clean_text(value: str | None) -> str | None:
    """Reduce a possibly-HTML snippet to plain, display-ready text.

    Decodes entities (``&quot;``, ``&#x2013;``, …), strips tags (``<p>``,
    ``<blockquote>``, …) and collapses whitespace, so raw RSS/OG HTML never
    reaches the feed UI. Returns None when nothing readable is left.
    """
    if not value:
        return None
    # Unescape first so escaped markup ("&lt;p&gt;") turns into real tags we can
    # then strip; BeautifulSoup drops the tags and decodes any remaining entities.
    text = BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)
    text = " ".join(text.split())
    return text or None


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _best_image(soup: BeautifulSoup, base_url: str) -> str | None:
    """Find the most representative image for a page.

    Prefer social-card images (og/twitter), then an explicit image_src link,
    then the first inline <img>. Relative URLs are resolved against the page.
    """
    candidate = (
        _meta(soup, "og:image")
        or _meta(soup, "og:image:url")
        or _meta(soup, "twitter:image")
        or _meta(soup, "twitter:image:src")
    )
    if not candidate:
        link = soup.find("link", rel="image_src")
        if link and link.get("href"):
            candidate = link["href"].strip()
    if not candidate:
        img = soup.find("img", src=True)
        if img:
            candidate = img["src"].strip()
    if not candidate:
        return None
    return urljoin(base_url, candidate)


# Cap the extracted body so a huge page can't bloat the payload we hand to the
# model; the explain prompt truncates to ~6k anyway.
MAX_TEXT_CHARS = 8000


def _visible_text(soup: BeautifulSoup) -> str | None:
    """Pull the readable body text out of a page for the model to summarise.

    Scripts, styles and other non-content tags are dropped; the remaining text
    is collapsed to single spaces and capped. Returns None when the page has no
    meaningful text (e.g. an SPA shell or a blank/blocked response).
    """
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    body = soup.body or soup
    text = " ".join(body.get_text(" ", strip=True).split())
    if not text:
        return None
    return text[:MAX_TEXT_CHARS]


def parse_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    summary = _meta(soup, "og:description") or _meta(soup, "description")
    image_url = _best_image(soup, url)
    # Extract the body text last: _visible_text strips tags in place.
    text = _visible_text(soup)
    # Strip any stray markup/entities so summaries are display-ready.
    return {
        "title": clean_text(title),
        "image_url": image_url,
        "summary": clean_text(summary),
        "text": text,
    }


def fetch_metadata(url: str, timeout: float = 8.0) -> dict:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"user-agent": "reels-bot/1.0"})
        resp.raise_for_status()
        return parse_metadata(resp.text, url)
    except Exception:
        return {"title": None, "image_url": None, "summary": None, "text": None}
