from typing import Protocol


class ModelProvider(Protocol):
    def summarize(self, title: str, text: str) -> str: ...

    def explain(self, title: str, text: str) -> dict:
        """Return ``{"short": str | None, "long": str | None}`` for the item."""
        ...
