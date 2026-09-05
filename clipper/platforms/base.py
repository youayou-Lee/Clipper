"""Clipboard backend abstraction (one implementation per platform)."""

from abc import ABC, abstractmethod


class ClipboardBackend(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        """Whether this backend can work on the current machine."""

    @abstractmethod
    def read(self):
        """Return current clipboard text, or None if unavailable/empty."""

    def write(self, text) -> bool:
        """Replace clipboard content; return True on success. Optional."""
        return False
