"""scripts/e2e_platform.py 的单元测试(mock subprocess,不碰真实剪贴板)。"""

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "e2e_platform.py"
spec = importlib.util.spec_from_file_location("e2e_platform", SCRIPT)
e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e2e)


class FakeProc:
    def __init__(self, returncode=0, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout


def test_backend_dispatch(monkeypatch):
    for platform, expected_reader in (("win32", e2e.win_read), ("darwin", e2e.mac_read), ("linux", e2e.linux_read)):
        monkeypatch.setattr(sys, "platform", platform)
        read, _ = e2e.backend()
        assert read is expected_reader


def test_win_write_uses_base64_not_raw_text(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProc(0)

    monkeypatch.setattr(e2e.subprocess, "run", fake_run)
    monkeypatch.setattr(e2e.shutil, "which", lambda name: "powershell")
    text = "桌面测试：泪水打湿猪脚饭"
    assert e2e.win_write(text) is True
    cmd_str = " ".join(captured["cmd"])
    assert text not in cmd_str  # 原文绝不进命令行(注入面为零)
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    assert b64 in cmd_str  # base64 载荷在命令中,接收端可无损还原


def test_win_write_failure(monkeypatch):
    monkeypatch.setattr(e2e.subprocess, "run", lambda cmd, **kw: FakeProc(1))
    monkeypatch.setattr(e2e.shutil, "which", lambda name: "powershell")
    assert e2e.win_write("x") is False


def test_win_read_strips_single_crlf(monkeypatch):
    monkeypatch.setattr(e2e.shutil, "which", lambda name: "powershell")
    monkeypatch.setattr(
        e2e.subprocess,
        "run",
        lambda cmd, **kw: FakeProc(0, "多行\n内容\r\n".encode("utf-8")),
    )
    assert e2e.win_read() == "多行\n内容"


def test_win_read_failure_returns_none(monkeypatch):
    monkeypatch.setattr(e2e.shutil, "which", lambda name: "powershell")
    monkeypatch.setattr(e2e.subprocess, "run", lambda cmd, **kw: FakeProc(1))
    assert e2e.win_read() is None


def test_no_mode_exits_2():
    with pytest.raises(SystemExit) as exc:
        e2e.main()
    assert exc.value.code == 2


def test_self_test_pass_exit_0(monkeypatch, capsys):
    token_holder = {}
    monkeypatch.setattr(e2e, "backend", lambda: (
        lambda: token_holder["text"],
        lambda t: token_holder.__setitem__("text", t) or True,
    ))
    monkeypatch.setattr(e2e.secrets, "token_hex", lambda n: "cafe")
    monkeypatch.setattr(sys, "argv", ["e2e_platform.py", "--self-test"])
    assert e2e.main() is None  # 成功路径正常返回(退出码 0)
    assert token_holder["text"] == "clipper-e2e-剪贴板验证-cafe"
    assert "PASS" in capsys.readouterr().out


def test_self_test_mismatch_exit_1(monkeypatch, capsys):
    monkeypatch.setattr(e2e, "backend", lambda: (lambda: "别的内容", lambda t: True))
    monkeypatch.setattr(sys, "argv", ["e2e_platform.py", "--self-test"])
    with pytest.raises(SystemExit) as exc:
        e2e.main()
    assert exc.value.code == 1
    assert "FAIL" in capsys.readouterr().out
