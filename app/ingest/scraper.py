from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


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


def parse_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    summary = _meta(soup, "og:description") or _meta(soup, "description")
    image_url = _best_image(soup, url)
    return {"title": title, "image_url": image_url, "summary": summary}


def fetch_metadata(url: str, timeout: float = 8.0) -> dict:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"user-agent": "reels-bot/1.0"})
        resp.raise_for_status()
        return parse_metadata(resp.text, url)
    except Exception:
        return {"title": None, "image_url": None, "summary": None}
