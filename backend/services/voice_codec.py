"""SILK → mp3 转码唯一实现：媒体落盘后即时转码（media_fetch）与批量脚本共用。

浏览器解不了微信 SILK 编码（voiceformat=4），必须两步走：
decoder（silk-v3-decoder）把 silk 解成裸 PCM → ffmpeg 按 s16le/单声道/24kHz 编成 mp3。

依赖两个外部程序，按「显式参数 → 环境变量 → PATH → 项目 tools/ → scripts/」查找：
1. decoder —— https://github.com/kn007/silk-v3-decoder 的 silk_v3_decoder
2. ffmpeg —— winget install Gyan.FFmpeg 或直接放 tools/
任一缺失或转码失败都返回 None（不抛错）：调用方降级返回原始 silk，
保证「工具没装」只影响能不能播，不影响媒体链路本身。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# SILK 魔数：定位成功即视为 silk；微信语音常在魔数前多 1~2 字节长度头
SILK_MAGIC = b"#!SILK_V3"
# 只在文件头这一小段里找魔数，避免大文件整篇扫描
HEAD_SCAN = 64
# 微信 silk v3 默认 24000Hz 单声道 16bit；老语音可能是 16000Hz，调用方可覆盖
DEFAULT_RATE = 24000

ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根（backend/ 上一级）
# 工具查找位置：项目 tools/ 与 scripts/（不依赖 CWD，服务与脚本都能找到）
SEARCH_DIRS = (ROOT / "tools", ROOT / "scripts")

# 子进程超时（秒）：语音最长 60 秒，正常转码毫秒级，超时视为失败
_DECODER_TIMEOUT = 60
_FFMPEG_TIMEOUT = 120


def find_tool(name: str, explicit: str = "") -> str:
    """按「显式参数 → 环境变量 → PATH → tools/ → scripts/」找可执行文件。"""
    if not explicit:
        explicit = os.getenv("SILK_DECODER" if name == "decoder" else "FFMPEG_BIN", "")
    if explicit:
        return explicit
    for candidate in (name, f"{name}.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    for directory in SEARCH_DIRS:
        for suffix in ("", ".exe"):
            path = directory / f"{name}{suffix}"
            if path.is_file():
                return str(path)
    return ""


def looks_like_silk(path: Path) -> bool:
    """按魔数判断文件是否为 silk：扩展名不可信（.silk/.bin/无后缀都可能）。"""
    try:
        with path.open("rb") as fh:
            return SILK_MAGIC in fh.read(HEAD_SCAN)
    except OSError:
        return False


def _stripped(path: Path, tmpdir: Path) -> Path:
    """返回可直接喂给 decoder 的 silk：魔数前有字节时复制一份裁掉前置头。"""
    data = path.read_bytes()
    pos = data.find(SILK_MAGIC, 0, HEAD_SCAN)
    if pos <= 0:
        return path  # 魔数正好在开头（pos=0）或找不到（交给后续失败分支）
    fixed = tmpdir / f"{path.stem}.silk"
    fixed.write_bytes(data[pos:])
    return fixed


def silk_to_mp3(silk: Path, out: Path, rate: int = DEFAULT_RATE) -> Path | None:
    """把 silk 文件转成 mp3。成功返回 mp3 路径；任何失败返回 None（调用方降级）。"""
    if not looks_like_silk(silk):
        return None
    decoder = find_tool("decoder")
    ffmpeg = find_tool("ffmpeg")
    if not decoder or not ffmpeg:
        return None  # 工具未安装：静默降级，由调用方决定是否记日志
    try:
        with tempfile.TemporaryDirectory() as raw:
            tmpdir = Path(raw)
            src = _stripped(silk, tmpdir)
            pcm = tmpdir / "audio.pcm"

            # 第一步：SILK 解码成裸 PCM（decoder 输入 输出 两个位置参数）
            result = subprocess.run(
                [decoder, str(src), str(pcm)],
                capture_output=True, text=True, errors="ignore",
                timeout=_DECODER_TIMEOUT,
            )
            if result.returncode != 0 or not pcm.is_file() or pcm.stat().st_size == 0:
                return None

            # 第二步：PCM 按 s16le/单声道/指定采样率解释，编成 64k mp3
            out.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    ffmpeg, "-y", "-loglevel", "error",
                    "-f", "s16le", "-ar", str(rate), "-ac", "1",
                    "-i", str(pcm), "-codec:a", "libmp3lame", "-b:a", "64k",
                    str(out),
                ],
                capture_output=True, text=True, errors="ignore",
                timeout=_FFMPEG_TIMEOUT,
            )
            if result.returncode != 0 or not out.is_file():
                return None
        return out
    except (OSError, subprocess.TimeoutExpired):
        return None
