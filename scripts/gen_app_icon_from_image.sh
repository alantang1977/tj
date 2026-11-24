#!/usr/bin/env bash
# Build all TANG TV Android brand icon assets from the approved cat artwork.
# Uses ImageMagick only for bitmap export; no Pillow drawing is used.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/other/image/tj_dream_cat_master.png"
PREVIEW=0
if [[ "${1:-}" == "--preview" ]]; then PREVIEW=1; fi

if command -v magick >/dev/null 2>&1; then
  im() { command magick "$@"; }
elif command -v convert >/dev/null 2>&1; then
  im() { command convert "$@"; }
else
  echo "ImageMagick (magick or convert) is required." >&2; exit 2
fi
[[ -f "$SRC" ]] || {
  echo "Missing approved source artwork: $SRC" >&2; exit 2;
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The supplied master is a rounded-square illustration on black corner fill.
# Flood only the corner-connected black area to transparency, then replace it
# with a sky-to-violet blend so Android launchers never show black corner wedges.
im "$SRC" -alpha on -fuzz 8% -fill none -draw 'color 0,0 floodfill' -draw 'color 1253,0 floodfill' -draw 'color 0,1253 floodfill' -draw 'color 1253,1253 floodfill' "$TMP/cutout.png"
im -size 1254x1254 gradient:'#41B9EC-#765BD1' "$TMP/gradient.png"
im "$TMP/gradient.png" "$TMP/cutout.png" -compose over -composite -strip "$TMP/art.png"

# Adaptive foreground uses the complete edge-to-edge artwork. The supplied
# composition already keeps the cat's ears and face within Android's adaptive
# mask; retaining the full art avoids an unwanted smaller square tile inside
# the launcher shape. The separate vector background remains the fallback layer.
im "$TMP/art.png" -filter Lanczos -resize '432x432!' -alpha off \
  -depth 8 -define png:bit-depth=8 -strip "$TMP/adaptive_foreground.png"

# A simple cat-head mark for Android 13 themed icons and monochrome notifications.
cat > "$TMP/cat-mark.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <path fill="#fff" d="M256 438c-39 0-76-9-106-26-40-22-66-59-75-104-7-38 5-75 30-103-13-36-17-79-13-125 28 9 61 29 84 54 23-11 50-17 80-17s57 6 80 17c23-25 56-45 84-54 4 46 0 89-13 125 25 28 37 65 30 103-9 45-35 82-75 104-30 17-67 26-106 26z"/>
</svg>
SVG
cat > "$TMP/cat-notification.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <path fill="#fff" d="M12 2.7c-1.55 0-3.02.34-4.33.97L3.5 2.1l.56 5.1C3.38 8.55 3 10.06 3 11.7c0 4.95 3.92 9.05 9 9.05s9-4.1 9-9.05c0-1.64-.38-3.15-1.06-4.5l.56-5.1-4.17 1.57C15.02 3.04 13.55 2.7 12 2.7z"/>
</svg>
SVG

write_vector_files() {
  cat > "$ROOT/app/src/main/res/drawable/ic_launcher_background.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<!-- TANG TV cat artwork adaptive-icon background. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="512"
    android:viewportHeight="512">
    <path android:pathData="M0,0h512v512h-512z">
        <aapt:attr xmlns:aapt="http://schemas.android.com/aapt" name="android:fillColor">
            <gradient android:startX="0" android:startY="0" android:endX="512" android:endY="512" android:type="linear" android:tileMode="clamp">
                <item android:offset="0" android:color="#41B9EC" />
                <item android:offset="0.42" android:color="#4A91E9" />
                <item android:offset="0.74" android:color="#7869D9" />
                <item android:offset="1" android:color="#E995D8" />
            </gradient>
        </aapt:attr>
    </path>
</vector>
XML

  cat > "$ROOT/app/src/main/res/drawable/ic_launcher_monochrome.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<!-- Simplified cat-head mark for Android 13+ themed icons. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="512"
    android:viewportHeight="512">
    <path android:fillColor="#FFFFFF"
        android:pathData="M256,438c-39,0-76-9-106-26-40-22-66-59-75-104-7-38,5-75,30-103-13-36-17-79-13-125 28,9 61,29 84,54 23-11 50-17 80-17s57,6 80,17c23-25 56-45 84-54 4,46 0,89-13,125 25,28 37,65 30,103-9,45-35,82-75,104-30,17-67,26-106,26z" />
</vector>
XML

  cat > "$ROOT/app/src/main/res/drawable-anydpi/ic_notification.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<!-- White cat-head status-bar/notification glyph. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF"
        android:pathData="M12,2.7 C10.45,2.7 8.98,3.04 7.67,3.67 L3.5,2.1 L4.06,7.2 C3.38,8.55 3,10.06 3,11.7 C3,16.65 6.92,20.75 12,20.75 C17.08,20.75 21,16.65 21,11.7 C21,10.06 20.62,8.55 19.94,7.2 L20.5,2.1 L16.33,3.67 C15.02,3.04 13.55,2.7 12,2.7 Z" />
</vector>
XML

  cat > "$ROOT/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
XML
  cat > "$ROOT/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
XML
}

# Make a high-resolution rounded-square or circular bitmap and then downsample.
make_masked() {
  local input="$1" out="$2" size="$3" shape="$4" format="$5"
  local big=$((size * 4))
  local radius=$((big * 22 / 100))
  local mask="$TMP/mask-${size}-${shape}.png"
  local mask_small="$TMP/mask-small-${size}-${shape}.png"
  local resized="$TMP/resized-${size}-${shape}.png"
  # Resize the artwork once at the target size; supersample only the mask to
  # preserve clean rounded/circular edges without a large 4x image pipeline.
  im "$input" -filter Lanczos -resize "${size}x${size}!" -depth 8 "$resized"
  im -size "${big}x${big}" xc:black -fill white \
    -draw "$([[ "$shape" == "circle" ]] && echo "circle $((big/2)),$((big/2)) $((big/2)),0" || echo "roundrectangle 0,0 $((big-1)),$((big-1)) $radius,$radius")" \
    -filter Lanczos -resize "${size}x${size}!" -colorspace gray -alpha copy "$mask_small"
  if [[ "$format" == "WEBP" ]]; then
    im "$resized" "$mask_small" -compose CopyOpacity -composite \
      -define webp:lossless=true -quality 100 -strip "$out"
  else
    im "$resized" "$mask_small" -compose CopyOpacity -composite \
      -depth 8 -define png:bit-depth=8 -define png:color-type=6 -strip "$out"
  fi
}

make_banner() {
  local w="$1" h="$2" out="$3"
  local tile=$((h * 78 / 100))
  local right=$((h * 7 / 100))
  local x=$((w - tile - right))
  local fs=$((h * 15 / 100))
  local tx=$((w * 7 / 100))
  local ty=$((h * 42 / 100))
  local radius=$((tile * 7 / 100))
  local bg="$TMP/banner-bg-${w}x${h}.png"
  local tilepng="$TMP/banner-tile-${w}x${h}.png"
  local mask="$TMP/banner-mask-${w}x${h}.png"
  local font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
  if [[ ! -f "$font" ]]; then font="DejaVu-Sans-Bold"; fi

  # Same artwork fills a blurred dark blue cinematic background; the crisp full
  # square master sits on the right, preserving the complete face and flowers.
  im "$TMP/art.png" -resize "${w}x${h}^" -gravity center -extent "${w}x${h}" \
    -blur "0x$((h / 16 + 2))" -modulate 68,92,100 \
    -fill 'rgba(7,20,48,0.55)' -draw "rectangle 0,0 $((w-1)),$((h-1))" "$bg"
  im "$TMP/art.png" -filter Lanczos -resize "${tile}x${tile}!" \
    -gravity center -extent "${tile}x${tile}" "$tilepng"
  im -size "${tile}x${tile}" xc:black -fill white \
    -draw "roundrectangle 0,0 $((tile-1)),$((tile-1)) $radius,$radius" "$mask"
  im "$tilepng" "$mask" -compose CopyOpacity -composite "$tilepng"
  im "$bg" "$tilepng" -geometry "+${x}+0" -compose over -composite \
    -font "$font" -pointsize "$fs" -fill '#FFFFFF' \
    -stroke 'rgba(7,18,43,0.62)' -strokewidth "$((h / 180 + 1))" \
    -gravity northwest -annotate "+${tx}+${ty}" 'TANG TV' \
    -stroke none -fill '#9DE8FF' -draw "roundrectangle ${tx},$((ty+fs+h/18)) $((tx+w*10/100)),$((ty+fs+h/18+h/90+1)) 2,2" \
    -depth 8 -strip "$out"
}

# Root asset master is part of the reproducible source set.
if [[ $PREVIEW -eq 0 ]]; then
  mkdir -p "$ROOT/other/image"
  write_vector_files
  mkdir -p "$ROOT/app/src/main/res/drawable-nodpi"
  cp "$TMP/adaptive_foreground.png" "$ROOT/app/src/main/res/drawable-nodpi/ic_launcher_foreground.png"

  # Legacy launcher bitmaps retain this repository's established px sizes.
  declare -A LAUNCHER=([mdpi]=128 [hdpi]=192 [xhdpi]=256 [xxhdpi]=384 [xxxhdpi]=512)
  for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
    px="${LAUNCHER[$density]}"
    mkdir -p "$ROOT/app/src/main/res/mipmap-$density"
    make_masked "$TMP/art.png" "$ROOT/app/src/main/res/mipmap-$density/ic_launcher.png" "$px" rounded PNG
  done

  # roundIcon follows the project's 48/72/96/144/192 px Android density mapping.
  declare -A ROUND=([mdpi]=48 [hdpi]=72 [xhdpi]=96 [xxhdpi]=144 [xxxhdpi]=192)
  for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
    px="${ROUND[$density]}"
    make_masked "$TMP/art.png" "$ROOT/app/src/main/res/mipmap-$density/ic_launcher_round.webp" "$px" circle WEBP
  done

  # Google Play listing art is an opaque square 512px image.
  mkdir -p "$ROOT/app/src/main"
  im "$TMP/art.png" -filter Lanczos -resize '512x512!' -alpha remove -alpha off -depth 8 -strip \
    "$ROOT/app/src/main/ic_launcher-playstore.png"

  # TV banner: 16:9, sized as 320x180dp across all five Android densities.
  declare -a BANNERS=("mdpi:320:180" "hdpi:480:270" "xhdpi:640:360" "xxhdpi:960:540" "xxxhdpi:1280:720")
  for spec in "${BANNERS[@]}"; do
    IFS=: read -r density w h <<< "$spec"
    mkdir -p "$ROOT/app/src/leanback/res/mipmap-$density" "$ROOT/app/src/main/res/drawable-$density"
    make_banner "$w" "$h" "$TMP/banner-${density}.png"
    cp "$TMP/banner-${density}.png" "$ROOT/app/src/leanback/res/mipmap-$density/ic_banner.png"
    cp "$TMP/banner-${density}.png" "$ROOT/app/src/main/res/drawable-$density/ic_banner.png"
  done

  # Remove the old adaptive-square banner and default-density duplicates. They
  # shadow proper 16:9 density bitmaps on Android 8+ and/or force upscaling.
  rm -f "$ROOT/app/src/leanback/res/mipmap-anydpi-v26/ic_banner.xml" \
        "$ROOT/app/src/leanback/res/drawable/ic_banner_foreground.xml" \
        "$ROOT/app/src/leanback/res/drawable/ic_banner.png" \
        "$ROOT/app/src/leanback/res/drawable-nodpi/ic_banner_foreground.png" \
        "$ROOT/app/src/main/res/drawable-nodpi/ic_banner.png"

  # In-app fallback logo: full source artwork, circle-cropped, original 600px contract.
  make_masked "$TMP/art.png" "$ROOT/app/src/main/res/drawable-nodpi/ic_logo.png" 600 circle PNG

  # Notifications: keep a monochrome, transparent white glyph (never a full-colour square).
  for spec in "mdpi:24" "hdpi:36" "xhdpi:48" "xxhdpi:72"; do
    IFS=: read -r density px <<< "$spec"
    mkdir -p "$ROOT/app/src/main/res/drawable-$density"
    im -background none "$TMP/cat-notification.svg" -resize "${px}x${px}!" -strip \
      "$ROOT/app/src/main/res/drawable-$density/ic_notification.png"
  done

  # Browser favicon uses a face-focused crop; individual ICO frames are exported natively.
  mkdir -p "$ROOT/app/src/main/assets"
  im "$TMP/art.png" -crop 1000x1000+127+70 +repage -resize '48x48!' \
    -gravity center -crop 48x48+0+0 +repage \
    \( -size 48x48 xc:black -fill white -draw 'circle 24,24 24,1' -colorspace gray -alpha copy \) \
    -compose CopyOpacity -composite -strip "$TMP/favicon48.png"
  im "$TMP/art.png" -crop 1000x1000+127+70 +repage -resize '32x32!' \
    \( -size 32x32 xc:black -fill white -draw 'circle 16,16 16,1' -colorspace gray -alpha copy \) \
    -compose CopyOpacity -composite -strip "$TMP/favicon32.png"
  im "$TMP/art.png" -crop 1000x1000+127+70 +repage -resize '16x16!' \
    \( -size 16x16 xc:black -fill white -draw 'circle 8,8 8,0' -colorspace gray -alpha copy \) \
    -compose CopyOpacity -composite -strip "$TMP/favicon16.png"
  im "$TMP/favicon48.png" "$TMP/favicon32.png" "$TMP/favicon16.png" \
    -define icon:auto-resize=48,32,16 "$ROOT/app/src/main/assets/favicon.ico"

else
  mkdir -p "$ROOT/build/icon-preview"
  make_masked "$TMP/art.png" "$ROOT/build/icon-preview/cat-launcher-rounded-512.png" 512 rounded PNG
  make_masked "$TMP/art.png" "$ROOT/build/icon-preview/cat-launcher-round-512.png" 512 circle PNG
  make_masked "$TMP/art.png" "$ROOT/build/icon-preview/cat-adaptive-mask-preview-432.png" 432 circle PNG
  cp "$TMP/adaptive_foreground.png" "$ROOT/build/icon-preview/cat-adaptive-foreground-432.png"
  make_banner 640 360 "$ROOT/build/icon-preview/cat-tv-banner-640x360.png"
fi

echo "TANG TV cat icon assets generated from: $SRC"
