"""Windows clipboard backend (ctypes, no dependencies)."""

import ctypes
import time

from .base import ClipboardBackend

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class WindowsBackend(ClipboardBackend):
    name = "windows"

    def available(self):
        return True

    def read(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        for _ in range(5):  # the clipboard can be briefly locked by other apps
            if user32.OpenClipboard(0):
                break
            time.sleep(0.05)
        else:
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.c_wchar_p(ptr).value
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def write(self, text) -> bool:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        for _ in range(5):
            if user32.OpenClipboard(0):
                break
            time.sleep(0.05)
        else:
            return False
        try:
            user32.EmptyClipboard()
            buf = ctypes.create_unicode_buffer(text)
            size = (len(text) + 1) * ctypes.sizeof(ctypes.c_wchar)
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return False
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                kernel32.GlobalFree(handle)
                return False
            try:
                ctypes.memmove(ptr, buf, size)
                if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                    kernel32.GlobalFree(handle)
                    return False
                return True
            finally:
                kernel32.GlobalUnlock(ptr)
        finally:
            user32.CloseClipboard()
