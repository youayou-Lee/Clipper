"""OCR 层:tesseract CLI 封装。

真实木马用 Google ML Kit 做本地 OCR(SparkCat),本复现在 Ubuntu 上用
tesseract 等价替代:同样的"图片进、文本出"接口,检出层不感知实现。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


class OcrUnavailable(RuntimeError):
    """tesseract 未安装时抛出,调用方不得静默吞掉。"""


def ensure_tesseract() -> str:
    """返回 tesseract 可执行路径;缺失时抛 OcrUnavailable。"""
    path = shutil.which("tesseract")
    if path is None:
        raise OcrUnavailable(
            "tesseract 未安装。Ubuntu 安装:sudo apt-get install -y tesseract-ocr tesseract-ocr-eng"
        )
    return path


def ocr_image(image_path: str | Path, *, scale: int = 3) -> str:
    """对单张图片做 OCR,返回文本。

    预处理:转灰度 + 等比放大(scale 倍)。截图类图片通常文字偏小,
    放大后 tesseract 对小字号英文的识别率显著提升——SparkCat 场景的
    典型输入正是手机截图。
    """
    tesseract = ensure_tesseract()
    with Image.open(image_path) as img:
        prepared = ImageOps.grayscale(img)
        width, height = prepared.size
        prepared = prepared.resize((width * scale, height * scale), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            prepared.save(tmp, format="PNG")
            tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [tesseract, str(tmp_path), "-", "--psm", "3", "-l", "eng"],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"tesseract 对 {image_path} 执行失败: {exc.stderr}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return result.stdout
