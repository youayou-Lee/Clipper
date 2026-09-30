"""端到端:tesseract 真实 OCR → 检出(无 tesseract 时 skip)。

用 Pillow 把 BIP-39 官方测试助记词渲染成"截图",再走真实 OCR 链路——
等价于 SparkCat 面对的输入(用户把助记词截成图)。
"""

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from mnestic.detect.detector import find_mnemonics
from mnestic.ocr import ocr_image

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract 未安装(sudo apt-get install tesseract-ocr tesseract-ocr-eng)",
)

VALID_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


def _render_text_image(path: Path, text: str, *, width: int = 620) -> None:
    """把文本渲染成"截图":按像素宽度换行,模拟真实助记词截图的排版。"""
    font = None
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, 28)
            break
    if font is None:
        font = ImageFont.load_default()

    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate_line = f"{current} {word}".strip()
        if font.getlength(candidate_line) > width - 40 and current:
            lines.append(current)
            current = word
        else:
            current = candidate_line
    if current:
        lines.append(current)

    line_height = 44
    img = Image.new("RGB", (width, line_height * len(lines) + 40), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((20, 20 + i * line_height), line, fill=(20, 20, 20), font=font)
    img.save(path)


def test_ocr_detects_rendered_mnemonic(tmp_path: Path):
    image = tmp_path / "seed_screenshot.png"
    _render_text_image(image, VALID_12)
    text = ocr_image(image)
    hits = find_mnemonics(text)
    assert any(h.phrase == VALID_12 and h.checksum_valid for h in hits)


def test_ocr_clean_image_no_hits(tmp_path: Path):
    image = tmp_path / "clean.png"
    _render_text_image(image, "hello world, nothing to see here")
    assert find_mnemonics(ocr_image(image)) == []
