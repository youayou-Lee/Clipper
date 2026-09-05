"""Platform e2e: real clipboard read/write verification (no third-party deps).

Usage (on the target machine, inside a real user session):
  python scripts/e2e_platform.py --self-test   # write known text, read back, compare
  python scripts/e2e_platform.py --read        # print current clipboard content
  python scripts/e2e_platform.py --write TEXT  # put TEXT on the clipboard

Windows uses PowerShell Set-Clipboard/Get-Clipboard; macOS uses pbcopy/pbpaste;
Linux uses xclip/wl-copy. Exit code 0 = success.
"""

import argparse
import base64
import secrets
import shutil
import subprocess
import sys


PS_UTF8 = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"


def _ps():
    return shutil.which("powershell") or shutil.which("pwsh")


def win_read():
    ps = _ps()
    if not ps:
        print("FAIL: 未找到 powershell/pwsh", file=sys.stderr)
        return None
    out = subprocess.run(
        [ps, "-NoProfile", "-Command", PS_UTF8 + " Get-Clipboard -Raw"],
        capture_output=True,
    )
    if out.returncode != 0:
        return None
    text = out.stdout.decode("utf-8", errors="replace")
    if text.endswith("\r\n"):
        text = text[:-2]
    return text or None


def win_write(text):
    # 文本经 base64 进入命令(PowerShell 5.1 的管道 stdin 按控制台码页解码,
    # 非 ASCII 会乱码);base64 字符集本身注入安全。
    ps = _ps()
    if not ps:
        print("FAIL: 未找到 powershell/pwsh", file=sys.stderr)
        return False
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    cmd = (
        PS_UTF8
        + f" Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString("
        + f"[Convert]::FromBase64String('{b64}')))"
    )
    proc = subprocess.run([ps, "-NoProfile", "-Command", cmd], capture_output=True)
    return proc.returncode == 0


def mac_read():
    out = subprocess.run(["pbpaste"], capture_output=True)
    return out.stdout.decode("utf-8", errors="replace") or None


def mac_write(text):
    return subprocess.run(["pbcopy"], input=text.encode("utf-8")).returncode == 0


def linux_read():
    for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"]):
        try:
            out = subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            continue
        if out.returncode == 0:
            return out.stdout.decode("utf-8", errors="replace") or None
    return None


def linux_write(text):
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
        try:
            if subprocess.run(cmd, input=text.encode("utf-8")).returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def backend():
    if sys.platform == "win32":
        return win_read, win_write
    if sys.platform == "darwin":
        return mac_read, mac_write
    return linux_read, linux_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true", help="write known text, read back, compare")
    group.add_argument("--read", action="store_true", help="print current clipboard content")
    group.add_argument("--write", help="put the given text on the clipboard")
    args = parser.parse_args()

    read, write = backend()
    if args.read:
        content = read()
        print("--- clipboard content start ---")
        print(content if content is not None else "(unreadable/empty)")
        print("--- clipboard content end ---")
        sys.exit(0 if content is not None else 1)
    if args.write is not None:
        sys.exit(0 if write(args.write) else 1)
    if args.self_test:
        token = f"clipper-e2e-剪贴板验证-{secrets.token_hex(8)}"
        if not write(token):
            print("FAIL: write returned error")
            sys.exit(1)
        back = read()
        if back == token:
            print(f"PASS: roundtrip OK ({token})")
            return
        print(f"FAIL: wrote {token!r}, read back {back!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
