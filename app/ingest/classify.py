from urllib.parse import urlparse


def classify_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in {"youtube.com", "youtu.be", "m.youtube.com"}:
        return "youtube"
    if host in {"twitter.com", "x.com", "mobile.twitter.com"}:
        return "x"
    if host in {"reddit.com", "old.reddit.com"} or host.endswith(".reddit.com"):
        return "reddit"
    return "article"
