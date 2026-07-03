import hashlib


def dedup_hash(url: str | None, title: str | None) -> str:
    basis = f"{url or ''}|{(title or '').strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
