"""扫描层:目录递归 → OCR → 助记词检出 → sqlite 审计。

复刻 SparkCat 的扫描拓扑(遍历图片目录、逐图识别、记录结果),
但一切只发生在本机:结果进本地 sqlite,可选回传到 127.0.0.1 的 C2 模拟器。
不修改、不移动、不删除被扫描目录的任何文件。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path

from mnestic.detect.detector import MnemonicHit, find_mnemonics
from mnestic.ocr import OcrUnavailable, ocr_image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".tif"}

_DEFAULT_DB = Path.home() / ".local" / "share" / "mnestic" / "findings.db"


@dataclass(frozen=True)
class Finding:
    image: str
    phrase: str
    word_count: int
    checksum_valid: bool

    def masked(self) -> str:
        """脱敏显示:保首尾词,中间以 * 代替(与 clipper 保头尾思路一致)。"""
        words = self.phrase.split()
        if len(words) <= 2:
            return "*" * len(self.phrase)
        return " ".join([words[0], *["*" * len(w) for w in words[1:-1]], words[-1]])

    @classmethod
    def from_hit(cls, image: Path, hit: MnemonicHit) -> "Finding":
        return cls(
            image=str(image),
            phrase=hit.phrase,
            word_count=hit.word_count,
            checksum_valid=hit.checksum_valid,
        )

    def as_dict(self) -> dict:
        return asdict(self)


def list_images(directory: str | Path) -> list[Path]:
    """递归列出目录下的图片文件(按路径排序,保证结果可复现)。"""
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"扫描目录不存在或不是目录: {root}")
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file())


def scan_directory(
    directory: str | Path,
    *,
    ocr_fn=ocr_image,
    db_path: str | Path | None = _DEFAULT_DB,
) -> list[Finding]:
    """扫描目录:每张图 OCR → 助记词检出 → 写入审计库。

    ocr_fn 可注入(测试用 mock 替代真实 tesseract);db_path 传 None 跳过审计。
    """
    findings: list[Finding] = []
    for image in list_images(directory):
        try:
            text = ocr_fn(image)
        except OcrUnavailable:
            # OCR 环境缺失是全局性问题:一次性 fail loudly,而不是逐图告警后"静默零检出"
            raise
        except (RuntimeError, OSError) as exc:
            print(f"[mnestic] 跳过无法识别的图片 {image}: {exc}")
            continue
        for hit in find_mnemonics(text):
            findings.append(Finding.from_hit(image, hit))
    if db_path is not None:
        record_findings(findings, db_path)
    return findings


def record_findings(findings: list[Finding], db_path: str | Path) -> None:
    """把检出结果写入 sqlite 审计库(与 clipper 的历史库同风格)。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL,
                phrase TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                checksum_valid INTEGER NOT NULL,
                found_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.executemany(
            "INSERT INTO findings (image, phrase, word_count, checksum_valid) VALUES (?, ?, ?, ?)",
            [(f.image, f.phrase, f.word_count, int(f.checksum_valid)) for f in findings],
        )
        conn.commit()
    finally:
        conn.close()
