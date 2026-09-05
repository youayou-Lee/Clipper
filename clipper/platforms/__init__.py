"""Platform clipboard backends."""

import sys

from .base import ClipboardBackend
from .linux import LinuxBackend
from .macos import MacOSBackend
from .windows import WindowsBackend

_BACKENDS = {
    "linux": (LinuxBackend,),
    "darwin": (MacOSBackend,),
    "win32": (WindowsBackend,),
}

__all__ = ["ClipboardBackend", "get_backend"]


def get_backend():
    """Return the first available backend for this platform, or None."""
    for cls in _BACKENDS.get(sys.platform, ()):
        backend = cls()
        if backend.available():
            return backend
    return None
