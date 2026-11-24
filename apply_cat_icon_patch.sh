#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Remove obsolete TV banner resources that can shadow the per-density 16:9 files.
rm -f \
  app/src/leanback/res/mipmap-anydpi-v26/ic_banner.xml \
  app/src/leanback/res/drawable/ic_banner_foreground.xml \
  app/src/leanback/res/drawable/ic_banner.png \
  app/src/leanback/res/drawable-nodpi/ic_banner_foreground.png \
  app/src/main/res/drawable-nodpi/ic_banner.png

python3 -m py_compile custom/local_customize.py scripts/gen_app_icon.py
bash scripts/verify_cat_icon_assets.sh

echo "TANG TV cat icon patch applied and resource validation passed."
