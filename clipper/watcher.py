"""Poll the clipboard and report changes."""

import sys
import time


class ClipboardWatcher:
    def __init__(self, backend, interval=0.8, on_content=None):
        self.backend = backend
        self.interval = interval
        self.on_content = on_content
        self._last = None

    def poll_once(self):
        """Read the clipboard; call on_content if it changed. True on change.

        on_content may return replacement clipboard text (e.g. the original
        plus an inline warning); it is recorded as the new baseline so the
        rewrite itself is not reported as another change.
        """
        text = self.backend.read()
        if text is None or text == self._last:
            return False
        self._last = text
        if self.on_content:
            replacement = self.on_content(text)
            if isinstance(replacement, str):
                self._last = replacement
        return True

    def run(self):
        print(
            f"[clipper] 正在监控剪贴板(backend={self.backend.name}, "
            f"interval={self.interval}s),Ctrl-C 退出",
            flush=True,
        )
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # a single bad read must not kill the daemon
                print(f"[clipper] 轮询出错: {exc}", file=sys.stderr, flush=True)
            time.sleep(self.interval)
