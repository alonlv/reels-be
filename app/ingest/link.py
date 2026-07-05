"""Shared handling for user-submitted links.

Both the AI-news submit flow (``POST /api/feed``) and the CSI add flow
(``POST /api/csi``) accept a URL, and we want them to treat it the same way:
don't just store whatever string the user pasted. For a **public** URL we fetch
it, confirm it actually resolves to a real page, and pull out the title, image
and body text so the model can summarise what's genuinely there instead of
guessing from the bare link.

A **non-public** link (localhost, a private/loopback IP, an internal
``*.corp``/``*.internal`` host) can't be reached from the server, so there is
nothing to verify — we keep it exactly as given and skip the network round-trip.
"""

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse

from app.ingest.scraper import fetch_metadata

# Hostname suffixes that mark a host as internal-only — never reachable or
# verifiable from the public internet.
_PRIVATE_SUFFIXES = (
    ".local", ".localhost", ".internal", ".intranet",
    ".lan", ".corp", ".home", ".test",
)


def is_public_url(url: str) -> bool:
    """True when *url* points at a host we could fetch from the open internet.

    Loopback, private/link-local IPs and internal-only hostnames (localhost,
    ``*.corp``, a bare dotless intranet name, …) are treated as non-public.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host == "localhost" or host.endswith(_PRIVATE_SUFFIXES):
        return False
    try:
        ip = ip_address(host)
    except ValueError:
        # A named host — public unless it's a bare, dotless intranet name.
        return "." in host
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_unspecified
    )


@dataclass
class LinkInfo:
    """What we learned about a submitted link.

    ``public``    — the URL is on the open internet (worth verifying at all).
    ``reachable`` — the fetch returned describable content (title/summary/text).
    ``verified``  — public *and* reachable: the link checks out.
    The remaining fields carry whatever we extracted, for reuse by the caller.
    """

    url: str
    public: bool
    reachable: bool
    verified: bool
    title: str | None = None
    summary: str | None = None
    image_url: str | None = None
    text: str | None = None


def inspect_link(url: str | None) -> LinkInfo:
    """Verify + extract a public link, or pass a non-public one through untouched.

    Never raises: a public link that fails to load comes back with
    ``reachable=False`` (and ``verified=False``) so the caller can decide whether
    to reject it. An empty or non-public link comes back with ``public=False``.
    """
    url = (url or "").strip()
    if not url or not is_public_url(url):
        return LinkInfo(url=url, public=False, reachable=False, verified=False)

    meta = fetch_metadata(url)
    title = meta.get("title")
    summary = meta.get("summary")
    text = meta.get("text")
    # "Reachable" means the fetch actually yielded something describable — not a
    # dead link, a redirect to a login wall, or an empty SPA shell. A lone image
    # with no title/summary/text doesn't count as verified content.
    reachable = bool(title or summary or text)
    return LinkInfo(
        url=url,
        public=True,
        reachable=reachable,
        verified=reachable,
        title=title,
        summary=summary,
        image_url=meta.get("image_url"),
        text=text,
    )
