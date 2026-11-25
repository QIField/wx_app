"""SILK → mp3 转码唯一实现：媒体落盘后即时转码（media_fetch）与批量脚本共用。

浏览器解不了微信 SILK 编码（voiceformat=4），必须两步走：
SILK 解码成裸 PCM → ffmpeg 按 s16le/单声道/24kHz 编成 mp3。

依赖策略（优先级从高到低）：
  SILK 解码：pysilk(Python 库) > 外部 decoder.exe
  MP3 编码 ：ffmpeg(PATH/tools/scripts/env) > imageio_ffmpeg(Python 库)
任一环节缺失或转码失败都返回 None（不抛错）：调用方降级返回原始 silk，
保证「工具没装」只影响能不能播，不影响媒体链路本身。
"""
from __future__ import annotations

import io
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


def _run(cmd: list[str], timeout: int) -> bool:
    """跑外部命令，成功返回 True；抛异常或 returncode != 0 返回 False。

    统一 subprocess.run 调用模式：capture_output、error 忽略、超时兜底。
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="ignore", timeout=timeout,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_tool(name: str, explicit: str = "") -> str:
    """按「显式参数 → 环境变量 → PATH → tools/ → scripts/ → Python 库」找可执行文件。

    ffmpeg 的最后兜底是 imageio_ffmpeg.get_ffmpeg_exe()（pip 安装即得自带二进制），
    所以即使系统没装 ffmpeg 也能跑；decoder 无 Python 兜底，必须外部程序或用
    silk_to_pcm 的 pysilk 路径。
    """
    if not explicit:
        env_key = "SILK_DECODER" if name == "decoder" else "FFMPEG_BIN"
        explicit = os.getenv(env_key, "")
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
    # 最后兜底：ffmpeg 走 imageio-ffmpeg（pip 装就有）
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg  # type: ignore
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
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


def silk_to_pcm(silk: Path, rate: int = DEFAULT_RATE) -> bytes | None:
    """把 silk 文件解成裸 PCM（s16le，单声道，指定采样率）。

    优先用 pysilk(Python 库)，找不到再 fallback 外部 decoder.exe。
    成功返回 PCM 字节；失败返回 None。
    """
    # 路径 1：pysilk Python 库（silk-python 包）
    try:
        import pysilk  # type: ignore
        silk_data = silk.read_bytes()
        # 微信 silk 常在魔数前带 1~2 字节长度头，直接喂 pysilk 也能处理
        out = io.BytesIO()
        pysilk.decode(io.BytesIO(silk_data), out, rate)
        pcm = out.getvalue()
        if pcm:
            return pcm
    except Exception:
        pass

    # 路径 2：外部 decoder.exe（silk-v3-decoder）
    decoder = find_tool("decoder")
    if not decoder:
        return None
    try:
        with tempfile.TemporaryDirectory() as raw:
            tmpdir = Path(raw)
            src = _stripped(silk, tmpdir)
            pcm = tmpdir / "audio.pcm"
            if _run([decoder, str(src), str(pcm)], _DECODER_TIMEOUT) and pcm.is_file() and pcm.stat().st_size > 0:
                return pcm.read_bytes()
    except OSError:
        pass
    return None


def silk_to_mp3(silk: Path, out: Path, rate: int = DEFAULT_RATE) -> Path | None:
    """把 silk 文件转成 mp3。成功返回 mp3 路径；任何失败返回 None（调用方降级）。

    解码路径优先 pysilk(Python 库)，编码路径优先 ffmpeg(imageio_ffmpeg 兜底)。
    """
    if not looks_like_silk(silk):
        return None

    # 第一步：silk → PCM（pysilk 优先，decoder.exe fallback）
    pcm_bytes = silk_to_pcm(silk, rate)
    if pcm_bytes is None or len(pcm_bytes) == 0:
        return None

    # 第二步：PCM → mp3（ffmpeg 优先，imageio-ffmpeg 兜底已在 find_tool 内）
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return None

    try:
        with tempfile.TemporaryDirectory() as raw:
            tmpdir = Path(raw)
            pcm = tmpdir / "audio.pcm"
            pcm.write_bytes(pcm_bytes)

            out.parent.mkdir(parents=True, exist_ok=True)
            ok = _run(
                [
                    ffmpeg, "-y", "-loglevel", "error",
                    "-f", "s16le", "-ar", str(rate), "-ac", "1",
                    "-i", str(pcm), "-codec:a", "libmp3lame", "-b:a", "64k",
                    str(out),
                ],
                _FFMPEG_TIMEOUT,
            )
            if not ok or not out.is_file():
                return None
        return out
    except OSError:
        return None
