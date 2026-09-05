"""Linux clipboard backend: wl-paste (Wayland) or xclip/xsel (X11)."""

import os
import shutil
import subprocess

from .base import ClipboardBackend


class LinuxBackend(ClipboardBackend):
    name = "linux"

    def __init__(self):
        self._cmd = self._detect_command()

    @staticmethod
    def _detect_command():
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
            return ("wl-paste", "--no-newline")
        if shutil.which("xclip"):
            return ("xclip", "-selection", "clipboard", "-o")
        if shutil.which("xsel"):
            return ("xsel", "--clipboard", "--output")
        return None

    def available(self):
        return self._cmd is not None

    def read(self):
        if self._cmd is None:
            return None
        try:
            proc = subprocess.run(self._cmd, capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None  # empty selection / clipboard busy
        return proc.stdout or None

    def write(self, text) -> bool:
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
            cmd = ["wl-copy"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard"]
        elif shutil.which("xsel"):
            cmd = ["xsel", "--clipboard", "--input"]
        else:
            return False
        try:
            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return proc.returncode == 0
