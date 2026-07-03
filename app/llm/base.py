from typing import Protocol


class ModelProvider(Protocol):
    def summarize(self, title: str, text: str) -> str: ...
