"""把微信 SILK 语音转成 mp3（批量/单文件均可）。

转码核心在 backend/services/voice_codec.py（与服务端落盘后自动转码是同一份实现，
本脚本只做 CLI 编排：找文件、拼输出名、汇总结果）。

依赖 decoder.exe（silk-v3-decoder）与 ffmpeg.exe，查找顺序见 voice_codec.find_tool
（PATH → 项目 tools/ → scripts/，或环境变量 SILK_DECODER / FFMPEG_BIN）。

用法示例：
    python scripts/silk_to_mp3.py                       # 转当前目录下所有 silk
    python scripts/silk_to_mp3.py downloads/voice_samples
    python scripts/silk_to_mp3.py voice.silk -o out.mp3
    python scripts/silk_to_mp3.py backend/media --rate 16000 --force
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services import voice_codec  # noqa: E402 转码唯一实现，勿在本脚本复制逻辑


def collect_inputs(target: Path) -> list[Path]:
    """单文件直接返回；目录则递归收集所有能识别出 silk 魔数的文件。"""
    if target.is_file():
        return [target]
    return sorted(
        p for p in target.rglob("*")
        if p.is_file() and p.suffix.lower() not in {".mp3", ".pcm"}
        and voice_codec.looks_like_silk(p)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="微信 SILK 语音转 mp3")
    parser.add_argument("target", nargs="?", default=".", help="silk 文件或目录（默认当前目录）")
    parser.add_argument("-o", "--output", help="输出 mp3 路径，仅单文件时可用")
    parser.add_argument("--rate", type=int, default=voice_codec.DEFAULT_RATE,
                        help=f"PCM 采样率，默认 {voice_codec.DEFAULT_RATE}")
    parser.add_argument("--force", action="store_true", help="已存在同名 mp3 时覆盖")
    args = parser.parse_args()

    if not voice_codec.find_tool("decoder") or not voice_codec.find_tool("ffmpeg"):
        print("缺少依赖：decoder（silk-v3-decoder）或 ffmpeg 未找到。")
        print(f"把可执行文件放到 {voice_codec.SEARCH_DIRS[0]} 或加入 PATH 后重试。")
        return 2

    target = Path(args.target)
    if not target.exists():
        print(f"路径不存在：{target}")
        return 2

    files = collect_inputs(target)
    if not files:
        print("没有找到 SILK 文件（按 #!SILK_V3 魔数识别）。")
        return 1
    if args.output and len(files) > 1:
        print("-o 只支持单文件输入，请去掉 -o 批量转换。")
        return 2

    ok = skipped = failed = 0
    for silk in files:
        out = Path(args.output) if args.output else silk.with_suffix(".mp3")
        if out.exists() and not args.force:
            print(f"跳过（已存在）：{out.name}")
            skipped += 1
            continue
        result = voice_codec.silk_to_mp3(silk, out, rate=args.rate)
        if result is None:
            print(f"失败：{silk.name}（decoder/ffmpeg 执行出错或文件损坏）")
            failed += 1
            continue
        print(f"成功：{silk.name} → {result.name}（{result.stat().st_size} 字节）")
        ok += 1

    print(f"\n完成：成功 {ok}，跳过 {skipped}，失败 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
