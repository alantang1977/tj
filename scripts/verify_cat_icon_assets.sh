#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v magick >/dev/null 2>&1 && ! command -v convert >/dev/null 2>&1; then
  echo "ImageMagick (magick or convert) is required" >&2; exit 2
fi
command -v identify >/dev/null 2>&1 || { echo "ImageMagick identify is required" >&2; exit 2; }

fail() { echo "FAIL: $*" >&2; exit 1; }
check_size() {
  local file="$1" expected="$2" actual
  [[ -f "$file" ]] || fail "missing: $file"
  actual="$(identify -format '%wx%h' "$file")"
  [[ "$actual" == "$expected" ]] || fail "$file expected $expected, got $actual"
}
check_transparent_corner() {
  local file="$1" alpha
  if [[ "$file" != *'['* ]]; then [[ -f "$file" ]] || fail "missing: $file"; fi
  alpha="$(identify -format '%[pixel:p{0,0}]' "$file")"
  [[ "$alpha" == *",0)" || "$alpha" == *",0.0)" ]] || fail "$file top-left pixel is not transparent: $alpha"
}

# Legacy launcher icons and round icons (the project-specific px contract).
declare -A LAUNCHER=([mdpi]=128 [hdpi]=192 [xhdpi]=256 [xxhdpi]=384 [xxxhdpi]=512)
declare -A ROUND=([mdpi]=48 [hdpi]=72 [xhdpi]=96 [xxhdpi]=144 [xxxhdpi]=192)
for d in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  check_size "app/src/main/res/mipmap-$d/ic_launcher.png" "${LAUNCHER[$d]}x${LAUNCHER[$d]}"
  check_size "app/src/main/res/mipmap-$d/ic_launcher_round.webp" "${ROUND[$d]}x${ROUND[$d]}"
  check_size "app/src/leanback/res/mipmap-$d/ic_banner.png" "$(case "$d" in mdpi) echo 320x180;; hdpi) echo 480x270;; xhdpi) echo 640x360;; xxhdpi) echo 960x540;; xxxhdpi) echo 1280x720;; esac)"
  check_size "app/src/main/res/drawable-$d/ic_banner.png" "$(case "$d" in mdpi) echo 320x180;; hdpi) echo 480x270;; xhdpi) echo 640x360;; xxhdpi) echo 960x540;; xxxhdpi) echo 1280x720;; esac)"
  check_transparent_corner "app/src/main/res/mipmap-$d/ic_launcher.png"
  check_transparent_corner "app/src/main/res/mipmap-$d/ic_launcher_round.webp"
done

check_size app/src/main/res/drawable-nodpi/ic_launcher_foreground.png 432x432
check_size app/src/main/ic_launcher-playstore.png 512x512
check_size app/src/main/res/drawable-nodpi/ic_logo.png 600x600
check_transparent_corner app/src/main/res/drawable-nodpi/ic_logo.png
check_size app/src/main/res/drawable-mdpi/ic_notification.png 24x24
check_size app/src/main/res/drawable-hdpi/ic_notification.png 36x36
check_size app/src/main/res/drawable-xhdpi/ic_notification.png 48x48
check_size app/src/main/res/drawable-xxhdpi/ic_notification.png 72x72
for f in app/src/main/res/drawable-mdpi/ic_notification.png \
         app/src/main/res/drawable-hdpi/ic_notification.png \
         app/src/main/res/drawable-xhdpi/ic_notification.png \
         app/src/main/res/drawable-xxhdpi/ic_notification.png; do
  check_transparent_corner "$f"
done

# ICO must contain all three native frames, not only the smallest frame.
frames="$(identify -format '%wx%h ' app/src/main/assets/favicon.ico)"
[[ "$frames" == *"16x16"* && "$frames" == *"32x32"* && "$frames" == *"48x48"* ]] || fail "favicon frames missing: $frames"
for i in 0 1 2; do
  check_transparent_corner "app/src/main/assets/favicon.ico[$i]"
done

# Current mobile and Leanback launcher aliases must point to the generated assets.
grep -q 'android:icon="@mipmap/ic_launcher"' app/src/main/AndroidManifest.xml || fail "main manifest missing ic_launcher"
grep -q 'android:roundIcon="@mipmap/ic_launcher_round"' app/src/main/AndroidManifest.xml || fail "main manifest missing ic_launcher_round"
grep -q 'android:icon="@mipmap/ic_launcher"' app/src/mobile/AndroidManifest.xml || fail "mobile alias missing ic_launcher"
grep -q 'android:roundIcon="@mipmap/ic_launcher_round"' app/src/mobile/AndroidManifest.xml || fail "mobile alias missing ic_launcher_round"
[[ "$(grep -o 'android:banner="@mipmap/ic_banner"' app/src/leanback/AndroidManifest.xml | wc -l | tr -d ' ')" == 2 ]] || fail "Leanback application and current alias must point to @mipmap/ic_banner"
for obsolete in \
  app/src/leanback/res/mipmap-anydpi-v26/ic_banner.xml \
  app/src/leanback/res/drawable/ic_banner_foreground.xml \
  app/src/leanback/res/drawable/ic_banner.png; do
  [[ ! -e "$obsolete" ]] || fail "stale banner resource shadows density assets: $obsolete"
done

# Resource XML must be well-formed.
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path
files = [
    Path('app/src/main/res/drawable/ic_launcher_background.xml'),
    Path('app/src/main/res/drawable/ic_launcher_monochrome.xml'),
    Path('app/src/main/res/drawable-anydpi/ic_notification.xml'),
    Path('app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml'),
    Path('app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml'),
    Path('app/src/main/AndroidManifest.xml'),
    Path('app/src/mobile/AndroidManifest.xml'),
    Path('app/src/leanback/AndroidManifest.xml'),
]
for path in files:
    ET.parse(path)
print('PASS: resource XML parsed')
PY

echo "PASS: mobile launcher icons, adaptive layers, Play artwork, notification/favicons and all TV/main banners are present and match project dimensions."
