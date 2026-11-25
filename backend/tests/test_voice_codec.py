"""voice_codec 单测：silk 识别 / 工具缺失降级 / 真实工具链转码（本机装了才跑）。"""
from pathlib import Path

import pytest

from backend.services import voice_codec

ROOT = Path(__file__).resolve().parent.parent.parent

# 带长度头的 silk 文件头（微信语音真实形态：02 23 + #!SILK_V3）
SILK_WITH_HEADER = b"\x02\x23#!SILK_V3" + b"\x13\x00" + b"JUNK"


def test_looks_like_silk_with_header(tmp_path):
    """魔数前有长度头也识别为 silk；垃圾文件不误判。"""
    p = tmp_path / "a.silk"
    p.write_bytes(SILK_WITH_HEADER)
    assert voice_codec.looks_like_silk(p)

    junk = tmp_path / "b.silk"
    junk.write_bytes(b"PLAINTEXTNOTSILK")
    assert not voice_codec.looks_like_silk(junk)


def test_stripped_removes_leading_bytes(tmp_path):
    """裁头：魔数前的 02 23 被去掉；魔数在开头则原样返回。"""
    p = tmp_path / "a.silk"
    p.write_bytes(SILK_WITH_HEADER)
    stripped = voice_codec._stripped(p, tmp_path)
    assert stripped.read_bytes().startswith(b"#!SILK_V3")

    plain = tmp_path / "plain.silk"
    plain.write_bytes(b"#!SILK_V3DATA")
    assert voice_codec._stripped(plain, tmp_path) == plain


def test_silk_to_mp3_without_tools_returns_none(tmp_path, monkeypatch):
    """decoder/ffmpeg 缺失：返回 None 而不抛错（调用方降级返回原 silk）。"""
    p = tmp_path / "a.silk"
    p.write_bytes(SILK_WITH_HEADER)
    monkeypatch.setattr(voice_codec, "find_tool", lambda name, explicit="": "")
    assert voice_codec.silk_to_mp3(p, tmp_path / "a.mp3") is None


def test_silk_to_mp3_rejects_non_silk(tmp_path):
    """非 silk 文件直接拒绝，不空跑子进程。"""
    junk = tmp_path / "junk.silk"
    junk.write_bytes(b"NOTSILKDATA")
    assert voice_codec.silk_to_mp3(junk, tmp_path / "junk.mp3") is None


def _has_silk_decoder():
    """SILK 解码器可用：pysilk Python 库 or 外部 decoder.exe。"""
    try:
        import pysilk  # noqa: F401
        return True
    except Exception:
        pass
    return bool(voice_codec.find_tool("decoder"))


def _has_ffmpeg_encoder():
    """ffmpeg 可用：系统 ffmpeg or imageio_ffmpeg Python 库。"""
    return bool(voice_codec.find_tool("ffmpeg"))


def test_silk_to_mp3_with_real_tools(tmp_path):
    """端到端：本机装了解码器+ffmpeg（pysilk/imageio-ffmpeg 也算）时真转一条。"""
    # 优先用 media 目录里已下载的 silk 文件（.gitignore 忽略了 backend/media/，不能用 git ls-files）
    import glob as _glob
    candidates = [Path(p) for p in _glob.glob(str(ROOT / "backend" / "media" / "*" / "*.silk"))]
    if not candidates:
        # fallback：downloads/voice_samples/ 目录
        alt = ROOT / "downloads" / "voice_samples"
        if alt.exists():
            candidates = list(alt.glob("*.silk"))
    if not candidates:
        pytest.skip("本机没有真实 silk 样例")
    src = candidates[0]

    if not _has_silk_decoder() or not _has_ffmpeg_encoder():
        pytest.skip("本机未安装 SILK 解码器或 ffmpeg")

    out = tmp_path / "a.mp3"
    result = voice_codec.silk_to_mp3(src, out)

    assert result == out
    assert out.stat().st_size > 1000
    assert out.read_bytes()[:3] == b"ID3" or out.read_bytes()[:2] in (b"\xff\xfb", b"\xff\xf3")
