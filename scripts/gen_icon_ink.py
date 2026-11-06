#!/usr/bin/env python3
"""墨影视图标生成（水墨播放键画作版）。

源图: ~/workspace/mooyingshi-icon/art_source.webp (1600x1600, AI 生成画作:
浅黑播放三角居中 + 墨晕扩散 + 宣纸底 #ECE6DD)。本脚本把画作铺到全部
品牌表面: 自适应图标前景/单色层、传统位图、圆图标、Play 商店图、TV 横幅、
应用内 logo、通知小图标 (改为白色播放三角剪影)、网站 favicon。

注意: 旧的 scripts/gen_app_icon.py (蓝底 MO 字标) 已不再对应当前图标,
不要再运行它, 否则品牌会被覆盖回去。

用法: python3 scripts/gen_icon_ink.py
"""
import os
from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.expanduser("~/workspace/mooyingshi-icon/art_source.webp")
PAPER = (0xEC, 0xE6, 0xDD, 255)
MAIN_RES = "app/src/main/res"

art = Image.open(ART).convert("RGB")
assert art.size[0] == art.size[1]


def save(img, rel, **kw):
    path = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, **kw)
    print(f"  {rel:58s} {img.size[0]}x{img.size[1]}")


def circle_crop(img):
    img = img.convert("RGBA")
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, img.size[0], img.size[1]], fill=255)
    img.putalpha(m)
    return img


def rounded(img, ratio=0.22):
    img = img.convert("RGBA")
    m = Image.new("L", img.size, 0)
    r = int(img.size[0] * ratio)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=r, fill=255)
    img.putalpha(m)
    return img


def art_at(px):
    return art.resize((px, px), Image.LANCZOS)


# --- 自适应图标前景: 108dp 画布 (864px), 纸色打底 + 画作内缩 90% ---
FG = 864
canvas = Image.new("RGBA", (FG, FG), PAPER)
inner = int(FG * 0.90)
off = (FG - inner) // 2
canvas.alpha_composite(art_at(inner).convert("RGBA"), (off, off))
save(canvas, f"{MAIN_RES}/drawable-nodpi/ic_launcher_art.png", format="PNG")

# --- 单色层: 以明度反相作 alpha 的黑色剪影 (系统自行重染) ---
gray = canvas.convert("L")
alpha = gray.point(lambda v: max(0, 235 - v) * 255 // 235)
mono = Image.new("RGBA", (FG, FG), (0, 0, 0, 0))
mono.putalpha(alpha)
save(mono, f"{MAIN_RES}/drawable-nodpi/ic_launcher_art_mono.png", format="PNG")

# --- 传统位图 (沿用仓库既有的偏大尺寸规格) ---
for name, px in [("mdpi", 128), ("hdpi", 192), ("xhdpi", 256), ("xxhdpi", 384), ("xxxhdpi", 512)]:
    save(rounded(art_at(px)), f"{MAIN_RES}/mipmap-{name}/ic_launcher.png", format="PNG")
for name, px in [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)]:
    save(circle_crop(art_at(px)), f"{MAIN_RES}/mipmap-{name}/ic_launcher_round.webp",
         format="WEBP", lossless=True, quality=100)

# --- Play 商店图 ---
save(art_at(512).convert("RGBA"), "app/src/main/ic_launcher-playstore.png", format="PNG")

# --- TV 横幅 320x180: 纸色底 + 画作等高居中 ---
banner = Image.new("RGBA", (320, 180), PAPER)
banner.alpha_composite(art_at(180).convert("RGBA"), (70, 0))
save(banner, "app/src/leanback/res/drawable/ic_banner.png", format="PNG")

# --- 应用内 logo (圆形, 与 ImgUtil circleCrop 一致) ---
save(circle_crop(art_at(600)), f"{MAIN_RES}/drawable-nodpi/ic_logo.png", format="PNG")

# --- 通知小图标: 白色播放三角剪影 (超采样绘制圆角) ---
def tri(px):
    ss = 4
    img = Image.new("RGBA", (px * ss, px * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = px * ss
    d.polygon([(0.32 * s, 0.24 * s), (0.76 * s, 0.50 * s), (0.32 * s, 0.76 * s)],
              fill=(255, 255, 255, 255))
    return img.resize((px, px), Image.LANCZOS)

for name, px in [("mdpi", 24), ("hdpi", 36), ("xhdpi", 48), ("xxhdpi", 72)]:
    save(tri(px), f"{MAIN_RES}/drawable-{name}/ic_notification.png", format="PNG")

# --- favicon: 16/32/48 三帧逐帧渲染, 升序, 最大帧为正图 ---
frames = [circle_crop(art_at(px)) for px in (16, 32, 48)]
save(frames[-1], "app/src/main/assets/favicon.ico", format="ICO",
     sizes=[(16, 16), (32, 32), (48, 48)], append_images=frames[:-1])
print("done")
