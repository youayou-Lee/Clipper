"""L2 组件测试:扫描链路(目录 → OCR 注入点 → 检出 → sqlite 审计)。

OCR 用注入的 mock 替代,不依赖 tesseract;图片文件用 Pillow 生成。
"""

import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from mnestic.scan import Finding, list_images, record_findings, scan_directory

VALID_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


def _make_png(path: Path) -> None:
    Image.new("RGB", (8, 8), color=(240, 240, 240)).save(path)


@pytest.fixture
def image_dir(tmp_path: Path) -> Path:
    _make_png(tmp_path / "screenshot_001.png")
    _make_png(tmp_path / "vacation.jpg")
    (tmp_path / "notes.txt").write_text(VALID_12)  # 非图片,不应被扫
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_png(sub / "nested.webp")
    return tmp_path


class TestListImages:
    def test_recursive_and_extension_filter(self, image_dir: Path):
        images = list_images(image_dir)
        names = [p.name for p in images]
        # rglob 按路径全序排序:子目录 sub/ 排在顶层 vacation.jpg 之前
        assert names == ["screenshot_001.png", "nested.webp", "vacation.jpg"]

    def test_missing_directory_raises(self, tmp_path: Path):
        with pytest.raises(NotADirectoryError):
            list_images(tmp_path / "nope")


class TestScanDirectory:
    def test_finds_mnemonic_via_injected_ocr(self, image_dir: Path, tmp_path: Path):
        def fake_ocr(path):
            # 前后缀用非词表词包住,保证 run 不被 "keep/safe" 这类词表词污染
            return (
                f"xyzzy {VALID_12} qqqqq"
                if path.name == "screenshot_001.png"
                else "hello world"
            )

        db = tmp_path / "findings.db"
        findings = scan_directory(image_dir, ocr_fn=fake_ocr, db_path=db)
        assert [f.phrase for f in findings] == [VALID_12]
        assert findings[0].image.endswith("screenshot_001.png")
        assert findings[0].checksum_valid is True

    def test_audit_written_to_sqlite(self, image_dir: Path, tmp_path: Path):
        def fake_ocr(path):
            return VALID_12 if path.name == "screenshot_001.png" else "nothing here"

        db = tmp_path / "findings.db"
        scan_directory(image_dir, ocr_fn=fake_ocr, db_path=db)
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT image, phrase, word_count, checksum_valid FROM findings"
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        assert rows[0][1] == VALID_12 and rows[0][2] == 12 and rows[0][3] == 1

    def test_db_none_skips_audit(self, image_dir: Path, tmp_path: Path):
        findings = scan_directory(image_dir, ocr_fn=lambda p: "", db_path=None)
        assert findings == []

    def test_ocr_error_is_skipped_not_fatal(self, image_dir: Path, tmp_path: Path):
        def bad_ocr(path):
            raise RuntimeError("ocr boom")

        findings = scan_directory(image_dir, ocr_fn=bad_ocr, db_path=None)
        assert findings == []


class TestRecordFindings:
    def test_appends_across_calls(self, tmp_path: Path):
        db = tmp_path / "findings.db"
        f1 = Finding(image="a.png", phrase=VALID_12, word_count=12, checksum_valid=True)
        record_findings([f1], db)
        record_findings([], db)
        record_findings([f1], db)
        conn = sqlite3.connect(db)
        try:
            assert conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 2
        finally:
            conn.close()
