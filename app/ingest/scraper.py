import httpx
from bs4 import BeautifulSoup


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def parse_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    summary = _meta(soup, "og:description") or _meta(soup, "description")
    image_url = _meta(soup, "og:image")
    return {"title": title, "image_url": image_url, "summary": summary}


def fetch_metadata(url: str, timeout: float = 8.0) -> dict:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"user-agent": "reels-bot/1.0"})
        resp.raise_for_status()
        return parse_metadata(resp.text, url)
    except Exception:
        return {"title": None, "image_url": None, "summary": None}
