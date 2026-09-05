"""macOS clipboard backend via pbpaste."""

import shutil
import subprocess

from .base import ClipboardBackend


class MacOSBackend(ClipboardBackend):
    name = "macos"

    def available(self):
        return bool(shutil.which("pbpaste"))

    def read(self):
        try:
            proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout or None

    def write(self, text) -> bool:
        if not shutil.which("pbcopy"):
            return False
        try:
            proc = subprocess.run(
                ["pbcopy"], input=text, capture_output=True, text=True, timeout=2
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return proc.returncode == 0
