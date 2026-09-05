"""Platform e2e: real clipboard read/write verification (no third-party deps).

Usage (on the target machine, inside a real user session):
  python scripts/e2e_platform.py --self-test   # write known text, read back, compare
  python scripts/e2e_platform.py --read        # print current clipboard content
  python scripts/e2e_platform.py --write TEXT  # put TEXT on the clipboard

Windows uses PowerShell Set-Clipboard/Get-Clipboard; macOS uses pbcopy/pbpaste;
Linux uses xclip/wl-copy. Exit code 0 = success.
"""

import argparse
import secrets
import subprocess
import sys


def win_read():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        capture_output=True,
    )
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace").rstrip("\r\n") or None


def win_write(text):
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
        input=text.encode("utf-8"),
        capture_output=True,
    )
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
    parser.add_argument("--self-test", action="store_true", help="write known text, read back, compare")
    parser.add_argument("--read", action="store_true", help="print current clipboard content")
    parser.add_argument("--write", help="put the given text on the clipboard")
    args = parser.parse_args()

    read, write = backend()
    if args.read:
        content = read()
        print("--- clipboard content start ---")
        print(content if content is not None else "(unreadable/empty)")
        print("--- clipboard content end ---")
        return
    if args.write is not None:
        sys.exit(0 if write(args.write) else 1)
    if args.self_test:
        token = f"clipper-e2e-{secrets.token_hex(8)}"
        if not write(token):
            print("FAIL: write returned error")
            sys.exit(1)
        back = read()
        if back == token:
            print(f"PASS: roundtrip OK ({token})")
            return
        print(f"FAIL: wrote {token!r}, read back {back!r}")
        sys.exit(1)
    parser.error("choose one of --self-test / --read / --write")


if __name__ == "__main__":
    main()
