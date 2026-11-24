#!/usr/bin/env python3
"""Generate the TANG TV cat icon resource set from the approved master artwork.

This entry point intentionally uses ImageMagick (not Pillow) for all bitmap
processing. The actual pipeline is scripts/gen_app_icon_from_image.sh.

Usage:
  python scripts/gen_app_icon.py            # regenerate all Android/icon assets
  python scripts/gen_app_icon.py --preview  # write previews only
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "scripts" / "gen_app_icon_from_image.sh"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview", action="store_true",
        help="只输出预览图到 build/icon-preview/，不修改 Android res 资源",
    )
    args = parser.parse_args()

    if not PIPELINE.is_file():
        parser.error(f"找不到资源生成脚本：{PIPELINE}")
    if shutil.which("magick") is None and shutil.which("convert") is None:
        parser.error("需要安装 ImageMagick（magick 或 convert 命令）并加入 PATH。")
    bash = shutil.which("bash")
    if bash is None:
        parser.error("需要 Bash（Linux/macOS，或 Windows Git Bash）。")

    command = [bash, str(PIPELINE)]
    if args.preview:
        command.append("--preview")
    subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
