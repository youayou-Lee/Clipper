"""Watcher behaviour tests using a fake clipboard backend."""

import unittest

from clipper.platforms.base import ClipboardBackend
from clipper.watcher import ClipboardWatcher


class FakeBackend(ClipboardBackend):
    name = "fake"

    def __init__(self, items):
        self.items = list(items)
        self.i = 0

    def available(self):
        return True

    def read(self):
        return self.items[min(self.i, len(self.items) - 1)]

    def advance(self):
        self.i += 1


class WatcherTests(unittest.TestCase):
    def test_fires_on_change_only_once(self):
        seen = []
        backend = FakeBackend(["hello", "world"])
        watcher = ClipboardWatcher(backend, on_content=seen.append)
        watcher.poll_once()
        watcher.poll_once()  # same content -> no callback
        self.assertEqual(seen, ["hello"])
        backend.advance()
        watcher.poll_once()
        self.assertEqual(seen, ["hello", "world"])

    def test_none_read_ignored(self):
        seen = []
        backend = FakeBackend(["a"])
        backend.items[0] = None
        watcher = ClipboardWatcher(backend, on_content=seen.append)
        self.assertFalse(watcher.poll_once())
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
