#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 local_customize.py —— 本地一键自定义脚本（webhtv / tangtv 项目）
================================================================================
在【本地克隆下来的项目根目录】运行：

    python3 local_customize.py        （或 python local_customize.py）

脚本会直接修改你本地项目文件，自动完成以下全部自定义：

  [1] app 显示名称（英文 / 简体 / 繁体 多语言 strings.xml）
  [2] app 启动图标（整合 gen_app_icon.py：程序化生成整套 launcher/adaptive/banner/通知/favicon）
  [3] 开机启动图 startup_logo.png、手机端启动图 mobile_startup.png
  [4] applicationId 安装包名（注意：namespace 绝对不修改！）
  [5] 自动补全 buildFeatures { viewBinding true }（解决 databinding 编译报错）
  [6] versionName 后缀（可选）
  [7] AndroidManifest.xml 硬编码 android:label
  [8] CNB 仓库地址（sync-cnb-release.sh + 工作流 yml 中的 CNB_REPO_SLUG/URL）
  [9] 工作流注入 GRADLE_OPTS 内存参数（解决 R8 OOM: Java heap space）

【重要警告】
  1. namespace 必须保持上游原值 com.fongmi.android.tv，本脚本绝不修改它。
     项目 Java 源码全部硬编码 import com.fongmi.android.tv.R / databinding.*，
     改 namespace 会导致上百个 cannot find symbol 编译错误。
  2. 修改完成后，用 git 提交并推送到你的构建仓库（如 tangtv），
     再触发 Android Release 工作流即可打包生成 APK。

【使用前准备】
  把自定义素材放进项目 custom/ 目录（没有就新建）：
    - startup_logo.png  开机启动图（可选）
    - mobile_startup.png 手机端启动图（可选）
================================================================================
"""

import glob
import os
import re
import time
try:
    from PIL import Image, ImageDraw, ImageFilter  # 图标生成/缩放需要
except ImportError:
    pass
import shutil
import sys
import xml.etree.ElementTree as ET

# Windows 控制台即时刷新输出，避免日志"卡住不动"的假象（每行 print 立即显示）
try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
except Exception:
    pass

# ==============================================================================
# ★★★ 配置区：按你的需要修改下面的值 ★★★
# （如果项目里存在 custom/config.env，脚本会优先读取 config.env 覆盖这里的值）
# ==============================================================================
CONFIG = {
    # APK 安装包名（只改安装标识，不影响源码编译；namespace 保持上游原样）
    "PACKAGE_NAME": "com.silent.android.tangtv",
    # 默认 / 英文 app 名称
    "APP_NAME": "TANG TV",
    # 简体中文 app 名称（与繁体一致，使用「湯影視」）
    "APP_NAME_ZH_CN": "湯影視",
    # 繁体中文 app 名称
    "APP_NAME_ZH_TW": "湯影視",
    # versionName 后缀，例如 "-beta1"，不需要就留空 ""
    "VERSION_NAME_SUFFIX": "",
    # CNB 仓库地址（真实存在的仓库，格式：用户名/仓库名）
    "CNB_REPO_SLUG": "tangtang.com.cn.kul/juntv",
    # custom/ 目录下的开机启动图文件名
    "STARTUP_LOGO": "startup_logo.png",
    # custom/ 目录下的手机端启动图文件名
    "MOBILE_STARTUP": "mobile_startup.png",
    # 程序化生成图标的风格：cat（默认，卡通蓝猫头）、3d（高级立体浮雕）或 iphone17（带光影）
    "ICON_STYLE": "cat",
    # 设置页「作者链接」：URL_GITHUB / URL_CNB（留空则不修改对应链接）
    "AUTHOR_GITHUB": "https://github.com/alantang1977/tj",
    "AUTHOR_CNB": "https://cnb.cool/tangtang.com.cn.kul/juntv",
    # 「检查更新」链接：GitHub 仓库（格式：用户名/仓库名）；CNB 部分自动用 CNB_REPO_SLUG
    "UPDATE_GITHUB_REPO": "alantang1977/tj",
}

# ---------------------------------------------------------------------------
# 下面代码一般不需要修改
# ---------------------------------------------------------------------------

# 脚本所在目录：兼容「放在项目根目录」和「放在 custom/ 目录」两种情况
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(_SCRIPT_DIR) == "custom":
    REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
else:
    REPO_ROOT = _SCRIPT_DIR

CUSTOM_DIR = os.path.join(REPO_ROOT, "custom")

# ==============================================================================
# 图标生成模块（整合自 custom/gen_app_icon.py）
# 用 Pillow 程序化生成整套应用图标：launcher / adaptive / banner / 通知栏 / favicon
# 风格由 CONFIG["ICON_STYLE"] 控制：3d（默认）或 iphone17
# ==============================================================================
GRAD_A = (0x8B, 0x5C, 0xF6)      # 左上 紫罗兰
GRAD_C = (0x5C, 0xBF, 0xF6)      # 新增：亮青 (流光过渡)
GRAD_MID = (0xF0, 0x9E, 0xE0)    # 中间 亮洋红
GRAD_B = (0xF4, 0x72, 0xB6)      # 右下 粉红
GRAD_A_HEX = "#8B5CF6"
GRAD_B_HEX = "#F472B6"
WHITE = (255, 255, 255, 255)
HOLE = (0, 0, 0, 0)
SS = 4          # 超采样倍率，先大图绘制再降采样得到干净边缘
VIEWPORT = 512  # VectorDrawable 视口边长
# 渐变内缩比例（沿用原逻辑）
GRAD_INSET_ADAPTIVE = 1.0 / 6.0
GRAD_INSET_CIRCLE = 0.1464
GRAD_INSET_ROUNDED = 0.0644
GRAD_INSET_SQUARE = 0.0
REPO = REPO_ROOT  # 指向项目根目录（由 local_customize.py 定义）
# --- 字标几何参数（重新调整以平衡视觉大小）---
R_STEM = 0.26          # 笔画宽度 / h
R_T_W = 0.85           # T 横条宽度 / h (从 1.0 缩小至 0.85，不再突出占位)
R_J_W = 0.6            # J 占位宽度 / h (微调了 J 的定位间距)
R_GAP = 0.1            # T 与 J 的间距 / h
R_TOTAL = R_T_W + R_GAP + R_J_W
# 字标占画面宽度的比例（沿用原值）
FILL_SAFE = 0.52
FILL_LEGACY = 0.70
FILL_CIRCLE = 0.64
FILL_NOTIFY = 0.88
# 小尺寸降级阈值
WORDMARK_MIN_PX = 32
FILL_BADGE = 0.68
# 3D 立体参数（已提高厚度强化立体感）
THICK_RATIO = 0.18      # 微小厚度 / h
OFFSET_RATIO = 0.35     # 偏移比例
def layout(size, fill):
    """按画面尺寸和填充比算出字标的基准几何。"""
    total_w = size * fill
    h = total_w / R_TOTAL
    x0 = (size - total_w) / 2
    y0 = (size - h) / 2
    return x0, y0, h
def draw_wordmark(size, fill, style="3d"):
    """绘制高级立体浮雕 T 和 J 字标（RGBA 图层）。

    支持风格：
    - 3d: 高级立体浮雕（含阴影、厚度、内侧高光、微渐变）
    - iphone17: 带OLED发光（兼具立体感）
    """
    layer = Image.new("RGBA", (size, size), HOLE)
    d = ImageDraw.Draw(layer)
    x0, y0, h = layout(size, fill)
    s = h * R_STEM
    thick = h * THICK_RATIO
    off = thick * OFFSET_RATIO
    # ----- T 的几何 -----
    t_bar_w = h * R_T_W
    t_bar_h = s
    t_stem_x = x0 + (t_bar_w - s) / 2
    t_stem_y = y0 + s
    t_stem_h = h - s
    # ----- J 的几何（缩短主体，顶部圆点与T平齐，底部严格对齐）-----
    j_x = x0 + h * (R_T_W + R_GAP)
    j_stem_w = h * 0.32          # 加宽 J 的竖干，使其与 T 的粗细匹配

    # 顶部圆点不能超过 T 顶边，圆心与 T 顶边平齐
    j_dot_r = j_stem_w * 0.57
    j_dot_cx = j_x + j_stem_w / 2
    j_dot_cy = y0 + j_dot_r      # 圆心位于 y0 线上，圆点顶边刚好平齐 T 顶边

    # J竖干缩短，底部对齐 y0+h，顶部让出圆点和间隙
    gap = s * 0.15
    j_stem_y = j_dot_cy + j_dot_r + gap  # 竖干顶部位置
    j_stem_h = (y0 + h) - j_stem_y       # 缩短后的竖干高度

    # 钩子（向左延伸，底部对齐）
    hook_w = j_stem_w * 0.9
    hook_h = j_stem_w * 0.55
    hook_x = j_x - hook_w
    hook_y = y0 + h - hook_h
    # === 精确视觉重心绝对居中修正（在原有物理居中基础上叠加） ===
    real_left = min(x0, hook_x)
    real_right = max(x0 + t_bar_w, j_x + j_stem_w)
    real_w = real_right - real_left
    # 计算 T 和 J 的视觉中心
    t_center = x0 + (t_bar_w / 2)
    j_center = (hook_x + (j_x + j_stem_w)) / 2
    visual_center = (t_center + j_center) / 2
    # 计算物理中心与视觉中心的偏移量
    physical_center = real_left + real_w / 2
    visual_offset = visual_center - physical_center
    # 在原计算基础上减去偏移量，达到视觉绝对居中
    shift_x = (size - real_w) / 2 - real_left - visual_offset
    x0 += shift_x
    t_stem_x += shift_x
    j_x += shift_x
    hook_x += shift_x
    j_dot_cx += shift_x
    # 定义所有区块（修改 J 竖干的区块坐标）
    blocks = [
        (x0, y0, t_bar_w, t_bar_h),
        (t_stem_x, t_stem_y, s, t_stem_h),
        (j_x, j_stem_y, j_stem_w, j_stem_h),
        (hook_x, hook_y, hook_w, hook_h),
    ]
    if fill == FILL_NOTIFY:
        # 系统强制要求：通知栏小图标必须为纯白透明，无任何阴影和渐变
        for x, y, w, bh in blocks:
            d.rectangle([x, y, x + w, y + bh], fill=WHITE)
        d.ellipse([j_dot_cx - j_dot_r, j_dot_cy - j_dot_r,
                   j_dot_cx + j_dot_r, j_dot_cy + j_dot_r], fill=WHITE)
        return layer
    # === 绘制高级立体浮雕挤出层（带环境阴影） ===
    # 1. 先在底层绘制极深的柔和阴影（模拟悬浮）
    shadow_layer = Image.new("RGBA", (size, size), HOLE)
    sd = ImageDraw.Draw(shadow_layer)
    for x, y, w, bh in blocks:
        sd.rectangle([x + off, y + thick, x + w + off, y + bh + thick], fill=(60, 20, 80, 150))
    # 圆圈的深阴影
    sd.ellipse([j_dot_cx - j_dot_r + off, j_dot_cy - j_dot_r + thick,
                j_dot_cx + j_dot_r + off, j_dot_cy + j_dot_r + thick], fill=(60, 20, 80, 150))

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=thick * 0.8))
    layer.alpha_composite(shadow_layer)
    # 2. 绘制主体的颜色挤出层（右面、底面偏暗色）
    for x, y, w, bh in blocks:
        d.rectangle([x + off, y + thick, x + w + off, y + bh + thick], fill=(120, 50, 140, 255)) # 深紫
    # 圆圈挤出层
    d.ellipse([j_dot_cx - j_dot_r + off, j_dot_cy - j_dot_r + thick,
               j_dot_cx + j_dot_r + off, j_dot_cy + j_dot_r + thick], fill=(120, 50, 140, 255))
    # === 绘制核心主体（含微渐变，模拟抛光表面）===
    # 绘制 T 和 J 表面（纯白渐变色，边缘带微蓝灰）
    for x, y, w, bh in blocks:
        d.rectangle([x, y, x + w, y + bh], fill=WHITE)

    # 绘制圆圈表面
    d.ellipse([j_dot_cx - j_dot_r, j_dot_cy - j_dot_r,
               j_dot_cx + j_dot_r, j_dot_cy + j_dot_r], fill=WHITE)
    # === 绘制高级液态玻璃立体三角形 ===
    tri_h = j_dot_r * 0.95
    tri_w = tri_h * 0.9

    # 完美居中修正：将质心（视觉重心）调整到圆心位置
    left_x = j_dot_cx - tri_w / 3
    right_x = j_dot_cx + 2 * tri_w / 3
    top_y = j_dot_cy - tri_h / 2
    bottom_y = j_dot_cy + tri_h / 2
    # 1. 极小投影（3D浮起感）
    proj_offset = int(s * 0.04)
    proj_layer = Image.new("RGBA", (size, size), HOLE)
    pd = ImageDraw.Draw(proj_layer)
    pd.polygon([(left_x + proj_offset, top_y + proj_offset),
                (left_x + proj_offset, bottom_y + proj_offset),
                (right_x + proj_offset, j_dot_cy + proj_offset)], fill=(0, 0, 0, 80))
    proj_layer = proj_layer.filter(ImageFilter.GaussianBlur(radius=thick * 0.2))
    layer.alpha_composite(proj_layer)
    # 2. 制作圆角蒙版（利用轻微高斯模糊实现液滴圆角）
    tri_mask = Image.new("L", (size, size), 0)
    td = ImageDraw.Draw(tri_mask)
    td.polygon([(left_x, top_y), (left_x, bottom_y), (right_x, j_dot_cy)], fill=255)
    tri_mask = tri_mask.filter(ImageFilter.GaussianBlur(radius=1.8))  # 超采样4倍，实际圆角很理想
    # 3. 内发光（边缘光晕 - 呼应流光背景）
    glow_layer = Image.new("RGBA", (size, size), HOLE)
    gd = ImageDraw.Draw(glow_layer)
    expand = int(s * 0.06)
    gd.polygon([(left_x - expand, top_y - expand),
                (left_x - expand, bottom_y + expand),
                (right_x + expand, j_dot_cy)], fill=(*GRAD_B, 100))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=thick * 0.3))
    layer.alpha_composite(glow_layer)
    # 4. 绘制受光渐变（模拟液滴/玻璃宝石质感，左上受光泛白，右下深紫）
    grad_layer = Image.new("RGBA", (size, size), HOLE)
    gd = ImageDraw.Draw(grad_layer)
    for i in range(size * 2):
        t = i / (size * 2)
        # 左上 -> 右下渐变
        if t < 0.5:
            t2 = t * 2
            r = int(255 + (GRAD_A[0] - 255) * t2)
            g = int(255 + (GRAD_A[1] - 255) * t2)
            b = int(255 + (GRAD_A[2] - 255) * t2)
        else:
            t2 = (t - 0.5) * 2
            r = int(GRAD_A[0] + (GRAD_MID[0] - GRAD_A[0]) * t2)
            g = int(GRAD_A[1] + (GRAD_MID[1] - GRAD_A[1]) * t2)
            b = int(GRAD_A[2] + (GRAD_MID[2] - GRAD_A[2]) * t2)
        gd.line([(i, 0), (0, i)], fill=(r, g, b, 255))
    # 利用蒙版将渐变抠入
    layer.paste(grad_layer, (0, 0), tri_mask)
    # 5. 边缘高光（锐利水晶切割感）
    hd = ImageDraw.Draw(layer)
    hd.line([(left_x + 2, top_y + 2), (left_x + 2, bottom_y - 2)], fill=(255, 255, 255, 200), width=int(s * 0.04))
    hd.line([(left_x + 2, top_y + 2), (right_x - 2, j_dot_cy)], fill=(255, 255, 255, 200), width=int(s * 0.04))
    # === 添加内侧高光与阴影（提升立体浮雕质感）===
    highlight = Image.new("RGBA", (size, size), HOLE)
    hd = ImageDraw.Draw(highlight)

    # T和J的立体高光（顶部和左侧亮线）
    for x, y, w, bh in blocks:
        hd.line([(x + 1, y + 1), (x + w - 1, y + 1)], fill=(255, 255, 255, 210), width=int(s * 0.08))
        hd.line([(x + 1, y + 1), (x + 1, y + bh - 1)], fill=(255, 255, 255, 210), width=int(s * 0.08))

    # 圆圈高光（顶部和左侧弧线）
    hd.arc([j_dot_cx - j_dot_r, j_dot_cy - j_dot_r, j_dot_cx + j_dot_r, j_dot_cy + j_dot_r], start=180, end=270, fill=(255, 255, 255, 210), width=int(s * 0.08))

    layer.alpha_composite(highlight)
    # 如果是 iPhone17 风格，增加发光效果（OLED光晕）
    if style == "iphone17":
        glow_layer = Image.new("RGBA", (size, size), HOLE)
        gd = ImageDraw.Draw(glow_layer)
        # 在字母下方增加光斑
        gd.ellipse([j_dot_cx - j_dot_r*1.5, j_dot_cy - j_dot_r*1.5,
                    j_dot_cx + j_dot_r*1.5, j_dot_cy + j_dot_r*1.5], fill=(*GRAD_B, 60))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=s * 0.3))
        layer.alpha_composite(glow_layer)
    return layer
def draw_badge(size):
    """只画 J 的立体浮雕轮廓（用于小尺寸降级），尺寸保持与主图一致。"""
    layer = Image.new("RGBA", (size, size), HOLE)
    d = ImageDraw.Draw(layer)
    s = size * 0.32
    h = size * 0.8
    x = (size - s) / 2
    y = (size - h) / 2

    # 计算圆点：顶部与整体顶边对齐
    j_dot_r = s * 0.57
    j_dot_cx = x + s / 2
    j_dot_cy = y + j_dot_r

    # 钩子（向左延伸，底部对齐）
    hook_w = s * 0.9
    hook_h = s * 0.55
    hook_x = x - hook_w
    hook_y = y + h - hook_h

    # === 视觉重心绝对居中修正 ===
    real_left = min(x, hook_x)
    real_right = x + s
    real_w = real_right - real_left
    # J的视觉中心（只有J，直接取J的中心）
    j_center = (hook_x + x + s) / 2
    visual_center = j_center
    physical_center = real_left + real_w / 2
    visual_offset = visual_center - physical_center
    shift_x = (size - real_w) / 2 - real_left - visual_offset
    x += shift_x
    hook_x += shift_x
    j_dot_cx += shift_x
    # 微厚度挤出
    d.rectangle([x + 2, y + 2, x + s + 2, y + h + 2], fill=(120, 50, 140, 120))
    d.ellipse([j_dot_cx - j_dot_r + 2, j_dot_cy - j_dot_r + 2,
               j_dot_cx + j_dot_r + 2, j_dot_cy + j_dot_r + 2], fill=(120, 50, 140, 120))
    d.rectangle([x, y, x + s, y + h], fill=WHITE)
    d.ellipse([j_dot_cx - j_dot_r, j_dot_cy - j_dot_r,
               j_dot_cx + j_dot_r, j_dot_cy + j_dot_r], fill=WHITE)

    # 钩子
    d.rectangle([hook_x, hook_y, hook_x + hook_w, hook_y + hook_h], fill=WHITE)
    return layer
# --- 位图绘制（流光溢彩渐变）---
def _smoothstep(t):
    """平滑插值函数，让渐变更加柔和灵动。"""
    return t * t * (3 - 2 * t)
def make_gradient(size, inset=0.0):
    """四重色彩平滑对角线性渐变，带有流光质感。"""
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    denom = 2.0 * (size - 1)
    span = max(1e-6, 1.0 - 2.0 * inset)

    for y in range(size):
        for x in range(size):
            t = (x + y) / denom
            t = min(1.0, max(0.0, (t - inset) / span))
            t = _smoothstep(t)

            # 四段色彩插值 (紫 -> 青 -> 洋红 -> 粉)
            if t < 0.33:
                t2 = t / 0.33
                r = round(GRAD_A[0] + (GRAD_C[0] - GRAD_A[0]) * t2)
                g = round(GRAD_A[1] + (GRAD_C[1] - GRAD_A[1]) * t2)
                b = round(GRAD_A[2] + (GRAD_C[2] - GRAD_A[2]) * t2)
            elif t < 0.66:
                t2 = (t - 0.33) / 0.33
                r = round(GRAD_C[0] + (GRAD_MID[0] - GRAD_C[0]) * t2)
                g = round(GRAD_C[1] + (GRAD_MID[1] - GRAD_C[1]) * t2)
                b = round(GRAD_C[2] + (GRAD_MID[2] - GRAD_C[2]) * t2)
            else:
                t2 = (t - 0.66) / 0.34
                r = round(GRAD_MID[0] + (GRAD_B[0] - GRAD_MID[0]) * t2)
                g = round(GRAD_MID[1] + (GRAD_B[1] - GRAD_MID[1]) * t2)
                b = round(GRAD_MID[2] + (GRAD_B[2] - GRAD_MID[2]) * t2)

            px[x, y] = (r, g, b)

    return grad.convert("RGBA")
def add_iphone17_background_flare(img):
    """在背景中心增加柔和的径向光斑。"""
    overlay = Image.new("RGBA", img.size, HOLE)
    d = ImageDraw.Draw(overlay)
    w, h = img.size
    center_x, center_y = w * 0.4, h * 0.4
    radius = w * 0.4
    d.ellipse([center_x - radius, center_y - radius,
               center_x + radius, center_y + radius], fill=(255, 255, 255, 35))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=w * 0.1))
    return Image.alpha_composite(img, overlay)
def _mask(size, shape, radius_ratio=0.0):
    m = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(m)
    if shape == "circle":
        md.ellipse([0, 0, size - 1, size - 1], fill=255)
    elif shape == "rounded":
        md.rounded_rectangle([0, 0, size - 1, size - 1],
                             radius=size * radius_ratio, fill=255)
    else:
        md.rectangle([0, 0, size - 1, size - 1], fill=255)
    return m

# ===== 卡通蓝猫头风格（V7：圆角耳 + 球体头 + 项圈铃铛 + 光晕）=====
import math as _math
CAT_BLUE_TOP = (155, 200, 255, 255)
CAT_BLUE_MID = (70, 140, 250, 255)
CAT_BLUE_BOT = (35, 88, 198, 255)
CAT_BLUE_SIDE = (22, 62, 155, 255)
CAT_PINK = (255, 150, 180, 255)
CAT_DARK = (35, 50, 85, 255)
CAT_NOSE = (244, 114, 142, 255)
CAT_COLLAR = (10, 110, 80, 255)
CAT_COLLAR_HL = (120, 230, 190, 255)
CAT_BELL = (255, 195, 40, 255)


def _rounded_poly(draw, pts, radius, fill, steps=12):
    """绘制圆角多边形（顶点用二次贝塞尔圆滑）。"""
    n = len(pts)
    out = []
    for i in range(n):
        V = pts[i]; A = pts[(i - 1) % n]; B = pts[(i + 1) % n]
        vlen = _math.hypot(V[0] - A[0], V[1] - A[1])
        alen = _math.hypot(V[0] - B[0], V[1] - B[1])
        ra = min(radius, vlen * 0.5); rb = min(radius, alen * 0.5)
        P1 = (V[0] + (A[0] - V[0]) * ra / vlen, V[1] + (A[1] - V[1]) * ra / vlen)
        P2 = (V[0] + (B[0] - V[0]) * rb / alen, V[1] + (B[1] - V[1]) * rb / alen)
        for s in range(steps + 1):
            t = s / steps
            x = (1 - t) * (1 - t) * P1[0] + 2 * (1 - t) * t * V[0] + t * t * P2[0]
            y = (1 - t) * (1 - t) * P1[1] + 2 * (1 - t) * t * V[1] + t * t * P2[1]
            out.append((x, y))
    draw.polygon(out, fill=fill)


def draw_cat(size):
    """绘制居中的卡通蓝猫头（广告级布光版，RGBA 透明底图层）。

    三点布光：主光左上、补光右侧、轮廓光右缘。
    元素：圆角三角耳（渐变白耳）、径向渐变球头、腮红、闭眼+睫毛、
    粉鼻水滴高光、ω嘴、胡须、项圈织物高光、金属铃铛、偏移双层光晕、接触投影。
    """
    layer = Image.new("RGBA", (size, size), HOLE)
    d = ImageDraw.Draw(layer)
    cx = size * 0.5
    r = size * 0.25
    head_cy = size * 0.5 + r * 0.08
    hx, hy = cx - r, head_cy - r
    ER = r * 0.10

    # ===== 头后光晕（偏移左上，紫蓝混色，双层）=====
    halo_cx, halo_cy = cx - r * 0.12, head_cy - r * 0.12
    halo_out = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(halo_out).ellipse([halo_cx - r * 1.25, halo_cy - r * 1.25,
                                       halo_cx + r * 1.25, halo_cy + r * 1.25],
                                      fill=(170, 190, 255, 40))
    halo_out = halo_out.filter(ImageFilter.GaussianBlur(radius=r * 0.35))
    layer.alpha_composite(halo_out)
    halo_in = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(halo_in).ellipse([halo_cx - r * 1.10, halo_cy - r * 1.10,
                                      halo_cx + r * 1.10, halo_cy + r * 1.10],
                                     fill=(200, 210, 255, 70))
    halo_in = halo_in.filter(ImageFilter.GaussianBlur(radius=r * 0.18))
    layer.alpha_composite(halo_in)

    # ===== 接触投影（整体向右下偏移）=====
    sh = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(sh).ellipse([hx + r * 0.12, hy + r * 0.15,
                                 hx + 2 * r + r * 0.12, hy + 2 * r + r * 0.15],
                                fill=(30, 10, 60, 100))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=size * 0.035))
    layer.alpha_composite(sh)

    # ===== 耳朵（圆角三角）=====
    def ear_pts(side):
        if side < 0:
            outer = (cx - r * 0.92, head_cy - r * 0.45)
            tip = (cx - r * 1.18, head_cy - r * 1.15)
            inner = (cx - r * 0.42, head_cy - r * 0.78)
        else:
            outer = (cx + r * 0.92, head_cy - r * 0.45)
            tip = (cx + r * 1.18, head_cy - r * 1.15)
            inner = (cx + r * 0.42, head_cy - r * 0.78)
        return outer, tip, inner

    def inner_pink(side):
        if side < 0:
            return [(cx - r * 0.80, head_cy - r * 0.55),
                    (cx - r * 1.02, head_cy - r * 0.98),
                    (cx - r * 0.52, head_cy - r * 0.74)]
        return [(cx + r * 0.80, head_cy - r * 0.55),
                (cx + r * 1.02, head_cy - r * 0.98),
                (cx + r * 0.52, head_cy - r * 0.74)]

    for side in (-1, 1):
        outer, tip, inner = ear_pts(side)
        mid = ((outer[0] + inner[0]) / 2, (outer[1] + inner[1]) / 2)
        _rounded_poly(d, [tip, inner, mid], ER, CAT_BLUE_MID)
        _rounded_poly(d, [tip, mid, outer], ER, CAT_BLUE_SIDE)
        # 耳朵与头交接处深色线
        d.line([outer[0], outer[1], inner[0], inner[1]],
               fill=CAT_BLUE_SIDE, width=max(1, int(r * 0.025)))

    # ===== 球体头：径向渐变（主光左上）=====
    head_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(head_mask).ellipse([hx, hy, hx + 2 * r, hy + 2 * r], fill=255)
    # 光源中心在左上
    lx, ly = cx - r * 0.35, head_cy - r * 0.45
    hgrad = Image.new("RGBA", (size, size), HOLE)
    hgd = ImageDraw.Draw(hgrad)
    # 用像素距离计算径向渐变
    import math
    for yy in range(int(hy), int(hy + 2 * r)):
        for xx in range(int(hx), int(hx + 2 * r)):
            dist = math.sqrt((xx - lx) ** 2 + (yy - ly) ** 2)
            max_d = r * 1.5
            k = min(1.0, dist / max_d)
            if k < 0.5:
                t = k * 2
                c = tuple(int(CAT_BLUE_TOP[i] + (CAT_BLUE_MID[i] - CAT_BLUE_TOP[i]) * t) for i in range(3))
            else:
                t = (k - 0.5) * 2
                # 暗部带一点暖紫（环境色反射）
                c_mid = CAT_BLUE_MID
                c_bot = (CAT_BLUE_BOT[0] + 15, CAT_BLUE_BOT[1], CAT_BLUE_BOT[2] - 10)
                c = tuple(int(c_mid[i] + (c_bot[i] - c_mid[i]) * t) for i in range(3))
            hgd.point((xx, yy), fill=c + (255,))
    layer.paste(hgrad, (0, 0), head_mask)

    # 轮廓光（右后缘细亮边）
    rim_light = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(rim_light).arc([hx, hy, hx + 2 * r, hy + 2 * r],
                                   start=280, end=80, fill=(180, 220, 255, 160),
                                   width=max(1, int(r * 0.045)))
    rim_light = rim_light.filter(ImageFilter.GaussianBlur(radius=r * 0.04))
    layer.alpha_composite(rim_light)

    # 白耳内（渐变：上浅冷灰白 -> 下纯白，保留极轻层次不显平）
    for side in (-1, 1):
        pts = inner_pink(side)
        ear_mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(ear_mask).polygon(pts, fill=255)
        ear_grad = Image.new("RGBA", (size, size), HOLE)
        egd = ImageDraw.Draw(ear_grad)
        for yy in range(int(size)):
            k = yy / size
            r_c = int(238 * (1 - k) + 255 * k)
            g_c = int(242 * (1 - k) + 255 * k)
            b_c = int(250 * (1 - k) + 255 * k)
            egd.line([(0, yy), (size, yy)], fill=(r_c, g_c, b_c, 255))
        layer.paste(ear_grad, (0, 0), ear_mask)

    # 主光高光（左上大面积柔光）
    spec = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(spec).ellipse([cx - r * 0.60, hy + r * 0.05,
                                   cx + r * 0.10, hy + r * 0.65], fill=(255, 255, 255, 100))
    spec = spec.filter(ImageFilter.GaussianBlur(radius=r * 0.20))
    layer.alpha_composite(spec)

    # 底部暗边
    rim = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(rim).arc([hx, hy, hx + 2 * r, hy + 2 * r],
                             start=20, end=160, fill=(15, 45, 120, 130), width=int(r * 0.10))
    rim = rim.filter(ImageFilter.GaussianBlur(radius=r * 0.06))
    layer.alpha_composite(rim)

    # ===== 奶白脸盘（纯白 + 极淡投影浮起感）=====
    face_cy = head_cy + r * 0.18
    face_box = [cx - r * 0.66, face_cy - r * 0.55,
                cx + r * 0.66, face_cy + r * 0.62]
    # 脸盘投影（淡灰偏移）
    face_sh = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(face_sh).ellipse([face_box[0] + r * 0.015, face_box[1] + r * 0.02,
                                      face_box[2] + r * 0.015, face_box[3] + r * 0.02],
                                     fill=(0, 20, 80, 40))
    face_sh = face_sh.filter(ImageFilter.GaussianBlur(radius=r * 0.04))
    layer.alpha_composite(face_sh)
    d.ellipse(face_box, fill=WHITE)

    # 闭眼 ^ ^（与鼻嘴比例协调）
    eye_y = face_cy - r * 0.10
    eye_dx, eye_w, eye_h = r * 0.40, r * 0.20, r * 0.16
    for ex in (cx - eye_dx, cx + eye_dx):
        d.arc([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
              start=200, end=340, fill=CAT_DARK, width=int(size * 0.012))

    # 粉鼻（圆润倒三角 + 底部阴影弧，与眼嘴等比例）
    nose_y = face_cy + r * 0.10
    nw = r * 0.11
    nose_pts = [(cx - nw, nose_y + nw * 0.15), (cx + nw, nose_y + nw * 0.15),
                (cx, nose_y + nw * 0.95)]
    d.polygon(nose_pts, fill=CAT_NOSE)
    # 鼻底阴影弧
    nose_sh = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(nose_sh).arc([cx - nw * 0.9, nose_y + nw * 0.5,
                                 cx + nw * 0.9, nose_y + nw * 1.3],
                                start=20, end=160, fill=(180, 60, 90, 80),
                                width=max(1, int(nw * 0.25)))
    nose_sh = nose_sh.filter(ImageFilter.GaussianBlur(radius=nw * 0.15))
    layer.alpha_composite(nose_sh)
    # 鼻尖水滴高光
    d.ellipse([cx - nw * 0.22, nose_y + nw * 0.25,
               cx + nw * 0.08, nose_y + nw * 0.55], fill=(255, 255, 255, 230))

    # ω 嘴（宽度与鼻子协调）
    mw = r * 0.14
    my = nose_y + nw * 0.9
    d.arc([cx - mw, my - nw * 0.3, cx, my + nw * 1.1], start=20, end=160,
          fill=CAT_DARK, width=int(size * 0.012))
    d.arc([cx, my - nw * 0.3, cx + mw, my + nw * 1.1], start=20, end=160,
          fill=CAT_DARK, width=int(size * 0.012))

    # 胡须（三长三短，更自然）
    whisker_rows = [
        (-0.10, 0.32),   # 上：最长
        (-0.02, 0.26),   # 中：中等
        (0.06, 0.20),    # 下：最短
    ]
    for dy, length in whisker_rows:
        yy = face_cy + r * dy
        ang = r * dy * 1.4
        d.line([(cx - r * 0.62, yy), (cx - r * 0.62 - r * length, yy + ang)],
               fill=(255, 255, 255, 235), width=int(size * 0.008))
        d.line([(cx + r * 0.62, yy), (cx + r * 0.62 + r * length, yy + ang)],
               fill=(255, 255, 255, 235), width=int(size * 0.008))

    # ===== 项圈（纯银金属反光）=====
    collar_cy = head_cy + r * 0.82
    collar_rx = r * 0.78
    collar_ry = r * 0.30
    # 横向渐变：中间高光白 -> 两侧暗银灰
    collar_grad = Image.new("RGBA", (size, size), HOLE)
    cgd = ImageDraw.Draw(collar_grad)
    for xx in range(int(size)):
        k = abs(xx - cx) / (collar_rx * 1.1)
        k = min(1.0, k)
        cr = int(60 * (1 - k) + 5 * k)
        cg_g = int(200 * (1 - k) + 90 * k)
        cb = int(150 * (1 - k) + 55 * k)
        cgd.line([(xx, 0), (xx, size)], fill=(cr, cg_g, cb, 255))
    collar_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(collar_mask).arc([cx - collar_rx, collar_cy - collar_ry,
                                      cx + collar_rx, collar_cy + collar_ry * 1.6],
                                     start=20, end=160, fill=255, width=int(r * 0.16))
    layer.paste(collar_grad, (0, 0), collar_mask)
    # 金属高光带
    band_hl = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(band_hl).arc([cx - collar_rx * 0.85, collar_cy - collar_ry * 0.7,
                                  cx + collar_rx * 0.85, collar_cy + collar_ry * 1.3],
                                 start=30, end=150, fill=(255, 255, 255, 160),
                                 width=max(1, int(r * 0.03)))
    band_hl = band_hl.filter(ImageFilter.GaussianBlur(radius=r * 0.02))
    layer.alpha_composite(band_hl)
    # 项圈两端金色铆钉
    for side in (-1, 1):
        rx = cx + side * collar_rx * 0.95
        ry = collar_cy + collar_ry * 0.3
        d.ellipse([rx - r * 0.04, ry - r * 0.04,
                   rx + r * 0.04, ry + r * 0.04], fill=(250, 204, 21, 255))
        d.ellipse([rx - r * 0.02, ry - r * 0.02,
                   rx + r * 0.02, ry + r * 0.02], fill=(255, 230, 120, 255))

    # ===== 金铃铛（金属质感：尖锐高光点 + 底部暗弧）=====
    bell_cx, bell_cy = cx, head_cy + r * 0.99
    bell_r = r * 0.13
    # 铃铛挂环（金色椭圆连接项圈）
    d.ellipse([bell_cx - bell_r * 0.20, bell_cy - bell_r * 1.15,
               bell_cx + bell_r * 0.20, bell_cy - bell_r * 0.78],
              fill=(200, 150, 20, 255))
    # 铃铛投影落在项圈上
    bell_sh = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(bell_sh).ellipse([bell_cx - bell_r * 0.9, bell_cy - bell_r * 0.9 + bell_r * 0.3,
                                      bell_cx + bell_r * 0.9, bell_cy + bell_r * 0.9 + bell_r * 0.3],
                                     fill=(120, 60, 0, 60))
    bell_sh = bell_sh.filter(ImageFilter.GaussianBlur(radius=bell_r * 0.3))
    layer.alpha_composite(bell_sh)
    # 铃铛本体
    d.ellipse([bell_cx - bell_r, bell_cy - bell_r,
               bell_cx + bell_r, bell_cy + bell_r], fill=CAT_BELL)
    # 底部暗弧
    bell_dark = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(bell_dark).arc([bell_cx - bell_r, bell_cy - bell_r,
                                   bell_cx + bell_r, bell_cy + bell_r],
                                  start=20, end=160, fill=(180, 120, 0, 100),
                                  width=max(1, int(bell_r * 0.25)))
    bell_dark = bell_dark.filter(ImageFilter.GaussianBlur(radius=bell_r * 0.15))
    layer.alpha_composite(bell_dark)
    # 尖锐高光点（偏橙金）
    d.ellipse([bell_cx - bell_r * 0.45, bell_cy - bell_r * 0.55,
               bell_cx - bell_r * 0.15, bell_cy - bell_r * 0.25],
              fill=(255, 220, 150, 220))
    # 中缝（随球体弧度微弯）和锤
    d.arc([bell_cx - bell_r * 0.7, bell_cy - bell_r * 0.35,
           bell_cx + bell_r * 0.7, bell_cy + bell_r * 0.35],
          start=0, end=180, fill=CAT_DARK, width=max(1, int(size * 0.005)))
    d.ellipse([bell_cx - bell_r * 0.15, bell_cy + bell_r * 0.05,
               bell_cx + bell_r * 0.15, bell_cy + bell_r * 0.35], fill=CAT_DARK)

    return layer


def draw_cat_silhouette(size):
    """猫头纯白剪影（通知栏 / monochrome 用，系统要求纯白透明）。"""
    layer = Image.new("RGBA", (size, size), HOLE)
    d = ImageDraw.Draw(layer)
    cx = size * 0.5
    r = size * 0.25
    head_cy = size * 0.5 + r * 0.08
    hx, hy = cx - r, head_cy - r
    for side in (-1, 1):
        if side < 0:
            pts = [(cx - r * 0.92, head_cy - r * 0.45),
                   (cx - r * 1.18, head_cy - r * 1.15),
                   (cx - r * 0.42, head_cy - r * 0.78)]
        else:
            pts = [(cx + r * 0.92, head_cy - r * 0.45),
                   (cx + r * 1.18, head_cy - r * 1.15),
                   (cx + r * 0.42, head_cy - r * 0.78)]
        _rounded_poly(d, pts, r * 0.10, WHITE)
    d.ellipse([hx, hy, hx + 2 * r, hy + 2 * r], fill=WHITE)
    return layer


def vector_cat(color="#FFFFFF", size_dp=108):
    """猫头剪影的 VectorDrawable（圆头 + 两耳），用于 adaptive 前景 / monochrome / 通知。"""
    vp = VIEWPORT
    cx, cy = vp * 0.5, vp * 0.5 + vp * 0.0224
    rr = vp * 0.25
    # 左耳
    le = (f"M{_p(cx - rr * 0.92)},{_p(cy - rr * 0.45)}"
          f"L{_p(cx - rr * 1.18)},{_p(cy - rr * 1.15)}"
          f"L{_p(cx - rr * 0.42)},{_p(cy - rr * 0.78)}z")
    # 右耳
    re_ = (f"M{_p(cx + rr * 0.92)},{_p(cy - rr * 0.45)}"
           f"L{_p(cx + rr * 1.18)},{_p(cy - rr * 1.15)}"
           f"L{_p(cx + rr * 0.42)},{_p(cy - rr * 0.78)}z")
    # 头圆
    head = (f"M{_p(cx)},{_p(cy - rr)}"
            f"A{_p(rr)},{_p(rr)} 0 1 1 {_p(cx)},{_p(cy + rr)}"
            f"A{_p(rr)},{_p(rr)} 0 1 1 {_p(cx)},{_p(cy - rr)}z")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- 由 local_customize.py 生成，请勿手工编辑 -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{size_dp}dp"
    android:height="{size_dp}dp"
    android:viewportWidth="{vp}"
    android:viewportHeight="{vp}">
    <path android:fillColor="{color}" android:pathData="{le}" />
    <path android:fillColor="{color}" android:pathData="{re_}" />
    <path android:fillColor="{color}" android:pathData="{head}" />
</vector>
"""


def _bokeh_and_vignette(img):
    """在渐变背景上叠加淡白色 bokeh 光斑和右下角暗角。"""
    w, h = img.size
    bokeh = Image.new("RGBA", (w, h), HOLE)
    bd = ImageDraw.Draw(bokeh)
    # 左上角大光斑
    bd.ellipse([-w * 0.1, -h * 0.15, w * 0.35, h * 0.25], fill=(255, 255, 255, 18))
    # 右下角小光斑
    bd.ellipse([w * 0.75, h * 0.7, w * 1.05, h * 0.95], fill=(255, 255, 255, 12))
    bokeh = bokeh.filter(ImageFilter.GaussianBlur(radius=w * 0.06))
    img.alpha_composite(bokeh)
    # 右下角暗角
    vig = Image.new("RGBA", (w, h), HOLE)
    vd = ImageDraw.Draw(vig)
    vd.pieslice([w * 0.5, h * 0.5, w * 1.6, h * 1.6], start=180, end=360,
                fill=(40, 0, 60, 35))
    vig = vig.filter(ImageFilter.GaussianBlur(radius=w * 0.15))
    img.alpha_composite(vig)


def render(size, shape="rounded", fill=FILL_LEGACY, radius_ratio=0.22,
           inset=None, badge=None, style="3d"):
    """渲染完整图标。

    style: cat（卡通蓝猫头）/ 3d（高级立体浮雕字标）/ iphone17（带光影字标）。
    """
    if inset is None:
        inset = {"circle": GRAD_INSET_CIRCLE,
                 "rounded": GRAD_INSET_ROUNDED}.get(shape, GRAD_INSET_SQUARE)
    if badge is None:
        badge = size < WORDMARK_MIN_PX
    big = size * SS

    # 绘制流光渐变背景
    img = make_gradient(big, inset)
    img = add_iphone17_background_flare(img)
    # 背景 bokeh + 右下角暗角
    _bokeh_and_vignette(img)

    # 绘制主体
    if style == "cat":
        img.alpha_composite(draw_cat(big))
    elif badge:
        img.alpha_composite(draw_badge(big))
    else:
        img.alpha_composite(draw_wordmark(big, fill, style=style))

    # 外形裁切
    if shape != "square":
        img.putalpha(_mask(big, shape, radius_ratio))
    return img.resize((size, size), Image.LANCZOS)
def render_banner(w, h, style="3d"):
    """Android TV banner 320x180。"""
    bw, bh = w * SS, h * SS
    img = make_gradient(max(bw, bh)).resize((bw, bh), Image.LANCZOS)
    img = add_iphone17_background_flare(img)

    if style == "cat":
        mark_box = int(bh * 0.95)
        mark = draw_cat(mark_box)
        img.alpha_composite(mark, (int(bw * 0.06), int((bh - mark_box) / 2)))
    else:
        mark_box = int(bh * 0.62)
        mark = draw_wordmark(mark_box, 0.92, style=style)
        img.alpha_composite(mark, (int(bw * 0.075), int((bh - mark_box) / 2)))

    return img.resize((w, h), Image.LANCZOS)
def render_notification(size, style="3d"):
    """通知栏小图标：纯白扁平轮廓（系统强制要求纯白透明，必须保持扁平）。"""
    if style == "cat":
        return draw_cat_silhouette(size * SS).resize((size, size), Image.LANCZOS)
    return draw_wordmark(size * SS, FILL_NOTIFY, style="3d").resize((size, size),
                          Image.LANCZOS)
def render_cat_foreground(size):
    """自适应图标前景：完整彩色猫（透明底），超采样后缩放至安全区内。

    自适应图标 108dp 中系统只显示中心 72dp 圆（半径 = size/3）。
    先用 SS=4 倍超采样绘制，再 LANCZOS 缩小，保证所有密度下边缘锐利无锯齿。
    """
    # 安全区系数：猫占画布 70%，确保耳尖/项圈/铃铛/光晕全在 72dp 圆内
    inner = int(size * 0.70)
    # 超采样绘制
    big = inner * SS
    cat = draw_cat(big)
    cat = cat.resize((inner, inner), Image.LANCZOS)
    # 居中放到 size x size 透明画布
    fg = Image.new("RGBA", (size, size), HOLE)
    offset = (size - inner) // 2
    fg.alpha_composite(cat, (offset, offset))
    return fg
def _remove_if_exists(rel):
    """删除可能残留的旧资源文件（避免同名 XML 与 PNG 冲突）。"""
    path = os.path.join(REPO, rel)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

def _purge_residual_foreground():
    """彻底清理所有可能残留的旧版白色剪影 XML（杜绝空白猫问题）。

    之前版本可能在 drawable/、drawable-anydpi/、drawable-v24/ 等目录写过
    ic_launcher_foreground.xml / ic_banner_foreground.xml。cat 风格改用 PNG 后，
    如果任何位置残留旧 XML，Android 资源解析可能优先选中它，导致空白白猫。
    """
    import glob as _glob
    patterns = [
        f"{MAIN_RES}/drawable*/ic_launcher_foreground.xml",
        "app/src/leanback/res/drawable*/ic_banner_foreground.xml",
    ]
    for pat in patterns:
        for f in _glob.glob(os.path.join(REPO, pat)):
            try:
                os.remove(f)
                print(f"  [clean] removed residual: {f}")
            except OSError:
                pass
# --- VectorDrawable 生成 ---
def _p(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")
def wordmark_paths(fill):
    """返回 (顶面路径, 空, 空, 三角形路径)，坐标基于 512 视口。"""
    x0, y0, h = layout(VIEWPORT, fill)
    s = h * R_STEM
    t_bar_w = h * R_T_W
    t_bar_h = s
    t_stem_x = x0 + (t_bar_w - s) / 2
    t_stem_y = y0 + s
    t_stem_h = h - s
    j_x = x0 + h * (R_T_W + R_GAP)
    j_stem_w = h * 0.32
    # 计算圆点：顶部与 T 平齐
    j_dot_r = j_stem_w * 0.57
    j_dot_cx = j_x + j_stem_w / 2
    j_dot_cy = y0 + j_dot_r
    # J 竖干缩短，底部对齐
    gap = s * 0.15
    j_stem_y = j_dot_cy + j_dot_r + gap
    j_stem_h = (y0 + h) - j_stem_y
    # 钩子
    hook_w = j_stem_w * 0.9
    hook_h = j_stem_w * 0.55
    hook_x = j_x - hook_w
    hook_y = y0 + h - hook_h
    # === 视觉重心绝对居中修正 ===
    real_left = min(x0, hook_x)
    real_right = max(x0 + t_bar_w, j_x + j_stem_w)
    real_w = real_right - real_left
    t_center = x0 + (t_bar_w / 2)
    j_center = (hook_x + (j_x + j_stem_w)) / 2
    visual_center = (t_center + j_center) / 2
    physical_center = real_left + real_w / 2
    visual_offset = visual_center - physical_center
    shift_x = (VIEWPORT - real_w) / 2 - real_left - visual_offset
    x0 += shift_x
    t_stem_x += shift_x
    j_x += shift_x
    hook_x += shift_x
    j_dot_cx += shift_x
    blocks = [
        (x0, y0, t_bar_w, t_bar_h),
        (t_stem_x, t_stem_y, s, t_stem_h),
        (j_x, j_stem_y, j_stem_w, j_stem_h),
        (hook_x, hook_y, hook_w, hook_h),
    ]
    def rect_to_path(x, y, w, bh):
        return f"M{_p(x)},{_p(y)}L{_p(x+w)},{_p(y)}L{_p(x+w)},{_p(y+bh)}L{_p(x)},{_p(y+bh)}z"
    if fill == FILL_NOTIFY:
        paths = [rect_to_path(*b) for b in blocks]
        return "".join(paths), "", "", ""
    top_paths = []
    for x, y, w, bh in blocks:
        top_paths.append(rect_to_path(x, y, w, bh))
    circle_path = (f"M{_p(j_dot_cx)},{_p(j_dot_cy - j_dot_r)}"
                   f"A{_p(j_dot_r)},{_p(j_dot_r)} 0 1 1 {_p(j_dot_cx)},{_p(j_dot_cy + j_dot_r)}"
                   f"A{_p(j_dot_r)},{_p(j_dot_r)} 0 1 1 {_p(j_dot_cx)},{_p(j_dot_cy - j_dot_r)}z")
    top_paths.append(circle_path)
    # 三角形（调整至质心完美居中，无偏移）
    tri_h = j_dot_r * 0.95
    tri_w = tri_h * 0.9
    tri_path = (f"M{_p(j_dot_cx - tri_w/3)},{_p(j_dot_cy - tri_h/2)}"
                f"L{_p(j_dot_cx - tri_w/3)},{_p(j_dot_cy + tri_h/2)}"
                f"L{_p(j_dot_cx + 2*tri_w/3)},{_p(j_dot_cy)}z")
    return "".join(top_paths), "", "", tri_path
def vector_wordmark(fill, color="#FFFFFF", size_dp=108):
    """生成字标的 VectorDrawable。由于 Android 矢量图限制，仅输出基础形状。"""
    top, _, _, tri = wordmark_paths(fill)
    if fill == FILL_NOTIFY:
        return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- 由 custom/gen_app_icon.py 生成，请勿手工编辑 -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{size_dp}dp"
    android:height="{size_dp}dp"
    android:viewportWidth="{VIEWPORT}"
    android:viewportHeight="{VIEWPORT}">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="{top}" />
</vector>
"""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- 由 custom/gen_app_icon.py 生成，请勿手工编辑 -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="{size_dp}dp"
    android:height="{size_dp}dp"
    android:viewportWidth="{VIEWPORT}"
    android:viewportHeight="{VIEWPORT}">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="{top}" />
    <!-- 紫色播放三角（向右） -->
    <path
        android:fillColor="{GRAD_A_HEX}"
        android:pathData="{tri}" />
</vector>
"""
def vector_background():
    """自适应图标背景：流光溢彩的对角渐变。"""
    lo = VIEWPORT * GRAD_INSET_ADAPTIVE
    hi = VIEWPORT - lo
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- 由 custom/gen_app_icon.py 生成，请勿手工编辑 -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="{VIEWPORT}"
    android:viewportHeight="{VIEWPORT}">
    <path android:pathData="M0,0h{VIEWPORT}v{VIEWPORT}h-{VIEWPORT}z">
        <aapt:attr xmlns:aapt="http://schemas.android.com/aapt"
            name="android:fillColor">
            <gradient
                android:startX="{_p(lo)}"
                android:startY="{_p(lo)}"
                android:endX="{_p(hi)}"
                android:endY="{_p(hi)}"
                android:type="linear"
                android:tileMode="clamp">
                <item android:offset="0" android:color="{GRAD_A_HEX}" />
                <item android:offset="0.33" android:color="#5CBFE0" />
                <item android:offset="0.66" android:color="#F09EE0" />
                <item android:offset="1" android:color="{GRAD_B_HEX}" />
            </gradient>
        </aapt:attr>
    </path>
</vector>
"""
ADAPTIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
"""
BANNER_XML = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_banner_foreground" />
</adaptive-icon>
"""
# --- 输出清单 ---
DENSITIES = [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96),
             ("xxhdpi", 144), ("xxxhdpi", 192)]
NOTIFY_DENSITIES = [("mdpi", 24), ("hdpi", 36), ("xhdpi", 48), ("xxhdpi", 72)]
LOGO_PX = 600
FAVICON_SIZES = [16, 32, 48]
MAIN_RES = "app/src/main/res"
def save_img(img, rel, **kw):
    path = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(8):
        try:
            img.save(path, **kw)
            break
        except OSError:
            if attempt == 7:
                raise
            time.sleep(0.25)
    print(f"  {rel:62s} {img.size[0]}x{img.size[1]}")
def save_text(text, rel):
    path = os.path.join(REPO, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"  {rel}")
def do_preview(style="3d"):
    out = "build/icon-preview"
    print(f"[preview] -> {out}/ (Style: {style})")
    save_img(render(512, "rounded", style=style), f"{out}/rounded_512.png")
    save_img(render(512, "circle", fill=FILL_CIRCLE, style=style), f"{out}/circle_512.png")
    save_img(render(512, "square", style=style), f"{out}/square_512.png")
    save_img(render(48, "rounded", style=style), f"{out}/rounded_48.png")
    save_img(render(72, "rounded", style=style), f"{out}/rounded_72.png")
    save_img(render(96, "rounded", style=style), f"{out}/rounded_96.png")
    save_img(render_banner(320, 180, style), f"{out}/banner.png")
    save_img(render(432, "circle", fill=FILL_SAFE, style=style), f"{out}/adaptive_circle.png")
    save_img(render(432, "rounded", fill=FILL_SAFE, radius_ratio=0.30, style=style),
              f"{out}/adaptive_squircle.png")
    mono = Image.new("RGBA", (432, 432), (0x1F, 0x1F, 0x1F, 255))
    if style == "cat":
        mono.alpha_composite(draw_cat_silhouette(432))
    else:
        mono.alpha_composite(draw_wordmark(432, FILL_SAFE, style="3d"))
    save_img(mono, f"{out}/monochrome.png")
    save_img(render(LOGO_PX, "circle", fill=FILL_CIRCLE, style=style), f"{out}/logo.png")
    for px in FAVICON_SIZES:
        save_img(render(px, "circle", fill=FILL_CIRCLE, style=style).resize(
            (px * 8, px * 8), Image.NEAREST), f"{out}/favicon_{px}.png")
    for px in (24, 36, 48, 72):
        bar = Image.new("RGBA", (px, px), (0x20, 0x21, 0x24, 255))
        bar.alpha_composite(render_notification(px, style=style))
        save_img(bar.resize((px * 8, px * 8), Image.NEAREST),
                  f"{out}/notification_{px}.png")
def do_write(style="3d"):
    print(f"[writing resources] (Style: {style})")
    if style == "cat":
        # cat 风格改用 PNG 前景，先彻底清理旧版白色剪影 XML（杜绝空白猫）
        _purge_residual_foreground()
    print("[vector drawables]")
    save_text(vector_background(), f"{MAIN_RES}/drawable/ic_launcher_background.xml")
    if style == "cat":
        # 自适应图标前景用完整彩色猫 PNG（透明底），而非白色矢量剪影
        _remove_if_exists(f"{MAIN_RES}/drawable/ic_launcher_foreground.xml")
        save_img(render_cat_foreground(432),
                 f"{MAIN_RES}/drawable-nodpi/ic_launcher_foreground.png", format="PNG")
        # monochrome 保持纯白矢量（Android 13 主题图标系统要求）
        save_text(vector_cat(), f"{MAIN_RES}/drawable/ic_launcher_monochrome.xml")
    else:
        _remove_if_exists(f"{MAIN_RES}/drawable-nodpi/ic_launcher_foreground.png")
        save_text(vector_wordmark(FILL_SAFE), f"{MAIN_RES}/drawable/ic_launcher_foreground.xml")
        save_text(vector_wordmark(FILL_SAFE),
                  f"{MAIN_RES}/drawable/ic_launcher_monochrome.xml")
    save_text(ADAPTIVE_XML, f"{MAIN_RES}/mipmap-anydpi-v26/ic_launcher.xml")
    save_text(ADAPTIVE_XML, f"{MAIN_RES}/mipmap-anydpi-v26/ic_launcher_round.xml")
    print("[legacy launcher bitmaps]")
    for name, base in DENSITIES:
        px = {"mdpi": 128, "hdpi": 192, "xhdpi": 256,
              "xxhdpi": 384, "xxxhdpi": 512}[name]
        save_img(render(px, "rounded", style=style), f"{MAIN_RES}/mipmap-{name}/ic_launcher.png",
                  format="PNG")
        save_img(render(base, "circle", fill=FILL_CIRCLE, style=style),
                  f"{MAIN_RES}/mipmap-{name}/ic_launcher_round.webp",
                  format="WEBP", lossless=True, quality=100)
    print("[play store]")
    save_img(render(512, "square", style=style), "app/src/main/ic_launcher-playstore.png",
              format="PNG")
    print("[tv banner]")
    if style == "cat":
        _remove_if_exists("app/src/leanback/res/drawable/ic_banner_foreground.xml")
        save_img(render_cat_foreground(432),
                 "app/src/leanback/res/drawable-nodpi/ic_banner_foreground.png", format="PNG")
    else:
        _remove_if_exists("app/src/leanback/res/drawable-nodpi/ic_banner_foreground.png")
        save_text(vector_wordmark(FILL_SAFE),
                  "app/src/leanback/res/drawable/ic_banner_foreground.xml")
    save_text(BANNER_XML, "app/src/leanback/res/mipmap-anydpi-v26/ic_banner.xml")
    save_img(render_banner(320, 180, style), "app/src/leanback/res/drawable/ic_banner.png",
              format="PNG")
    print("[in-app logo]")
    save_img(render(LOGO_PX, "circle", fill=FILL_CIRCLE, style=style),
              f"{MAIN_RES}/drawable-nodpi/ic_logo.png", format="PNG")
    print("[notification]")
    if style == "cat":
        save_text(vector_cat(size_dp=24),
                  f"{MAIN_RES}/drawable-anydpi/ic_notification.xml")
    else:
        save_text(vector_wordmark(FILL_NOTIFY, size_dp=24),
                  f"{MAIN_RES}/drawable-anydpi/ic_notification.xml")
    for name, px in NOTIFY_DENSITIES:
        save_img(render_notification(px, style=style),
                  f"{MAIN_RES}/drawable-{name}/ic_notification.png", format="PNG")
    print("[web favicon]")
    sizes = sorted(FAVICON_SIZES)
    frames = [render(px, "circle", fill=FILL_CIRCLE, style=style) for px in sizes]
    save_img(frames[-1], "app/src/main/assets/favicon.ico", format="ICO",
              sizes=[(px, px) for px in sizes],
              append_images=frames[:-1])
    print("\nDone.")


# 图标密度 -> 标准像素尺寸（Android 规范）
ICON_SIZES = {
    "mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192,
}
# Adaptive Icon 前景/背景 drawable 的标准尺寸（108dp）
ADAPTIVE_SIZES = {
    "mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432,
}

_ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def load_config_env():
    """如果存在 custom/config.env，则用它的值覆盖 CONFIG。"""
    env_path = os.path.join(CUSTOM_DIR, "config.env")
    if not os.path.exists(env_path):
        return
    print(f"[INFO] 发现 custom/config.env，优先使用其中的配置")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key in CONFIG:
                    CONFIG[key] = value
                    print(f"[INFO] config.env: {key} = {value}")


# ---------------------------------------------------------------- 1. build.gradle
def modify_build_gradle(config):
    """
    修改 app/build.gradle：
      - 仅替换 applicationId（namespace 不碰！）
      - versionName 加后缀（可选）
      - 自动补全 buildFeatures { viewBinding true }
    """
    package_name = config.get("PACKAGE_NAME", "")
    version_suffix = config.get("VERSION_NAME_SUFFIX", "")
    changed_any = False

    candidates = [
        os.path.join(REPO_ROOT, "app", "build.gradle"),
        os.path.join(REPO_ROOT, "app", "build.gradle.kts"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        filename = os.path.basename(path)

        if package_name:
            # groovy 格式 applicationId "xxx"
            content = re.sub(
                r'(applicationId\s+["\'])[^"\']+(["\'])',
                rf"\g<1>{package_name}\g<2>",
                content,
            )
            # kts 格式 applicationId = "xxx"
            content = re.sub(
                r'(applicationId\s*=\s*["\'])[^"\']+(["\'])',
                rf"\g<1>{package_name}\g<2>",
                content,
            )

        if version_suffix:
            def add_suffix(m):
                prefix, ver, quote = m.group(1), m.group(2), m.group(3)
                if not ver.endswith(version_suffix):
                    ver = ver + version_suffix
                return f"{prefix}{ver}{quote}"

            content = re.sub(
                r'(versionName\s*=?\s*["\'])([^"\']+)(["\'])',
                add_suffix,
                content,
            )

        # 自动补全 viewBinding（groovy .gradle）
        if filename.endswith(".gradle"):
            if "viewBinding true" not in content:
                if re.search(r'android\s*\{[^}]*buildFeatures', content):
                    content = re.sub(
                        r'(buildFeatures\s*\{)',
                        r'\g<1>\n        viewBinding true',
                        content,
                    )
                else:
                    content = re.sub(
                        r'(android\s*\{)',
                        r'\g<1>\n    buildFeatures {\n        viewBinding true\n    }',
                        content,
                    )
                changed_any = True
                print("[OK] app/build.gradle: 已补全 buildFeatures { viewBinding true }")

        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] app/{filename}: applicationId -> {package_name}"
                  + (f"，versionName 加后缀 {version_suffix}" if version_suffix else ""))
        else:
            print(f"[SKIP] app/{filename}: 已是目标值或无需修改")
    return changed_any


# ---------------------------------------------------------------- 2. 多语言名称
def modify_strings_xml(rel_path, app_name):
    """修改指定 strings.xml 中的 app_name 系列字段。"""
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[SKIP] 文件不存在: {rel_path}")
        return False
    ET.register_namespace("android", _ANDROID_NS.lstrip("{").rstrip("}"))
    ET.register_namespace("tools", "http://schemas.android.com/tools")
    try:
        tree = ET.parse(full_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"[ERROR] 解析 XML 失败 {rel_path}: {e}")
        return False

    changed = False
    targets = ["app_name", "app_name_tv", "app_name_short", "app_name_long"]
    for string_elem in root.findall("string"):
        if string_elem.get("name") in targets:
            old = string_elem.text or ""
            if old != app_name:
                string_elem.text = app_name
                changed = True
                print(f'[OK] {rel_path}: {string_elem.get("name")} "{old}" -> "{app_name}"')

    if changed:
        tree.write(full_path, encoding="utf-8", xml_declaration=True)
    return changed


def modify_all_strings(config):
    changed_any = False
    app_name = config.get("APP_NAME", "")
    zh_cn = config.get("APP_NAME_ZH_CN", app_name)
    zh_tw = config.get("APP_NAME_ZH_TW", app_name)

    files = [
        (os.path.join("app", "src", "main", "res", "values", "strings.xml"), app_name),
        (os.path.join("app", "src", "main", "res", "values-zh-rCN", "strings.xml"), zh_cn),
        (os.path.join("app", "src", "main", "res", "values-zh-rTW", "strings.xml"), zh_tw),
        (os.path.join("app", "src", "mobile", "res", "values", "strings.xml"), app_name),
        (os.path.join("app", "src", "mobile", "res", "values-zh-rCN", "strings.xml"), zh_cn),
        (os.path.join("app", "src", "mobile", "res", "values-zh-rTW", "strings.xml"), zh_tw),
        (os.path.join("app", "src", "leanback", "res", "values", "strings.xml"), app_name),
        (os.path.join("app", "src", "leanback", "res", "values-zh-rCN", "strings.xml"), zh_cn),
        (os.path.join("app", "src", "leanback", "res", "values-zh-rTW", "strings.xml"), zh_tw),
    ]
    for rel, name in files:
        if modify_strings_xml(rel, name):
            changed_any = True
    return changed_any


# ---------------------------------------------------------------- 3. 应用图标
def _save_icon(img_path, target, size=None):
    """把源图标写入 target，若安装了 Pillow 且给定 size 则缩放。返回 True/False。"""
    try:
        from PIL import Image
        have_pil = True
    except Exception:
        have_pil = False

    ext = os.path.splitext(target)[1].lower()
    if have_pil and size:
        try:
            img = Image.open(img_path).convert("RGBA")
        except Exception as e:
            print(f"      [WARN] 图标文件无法解析（{e}），按原文件复制")
            shutil.copy2(img_path, target)
            return True
        resample = getattr(Image, "Resampling", Image)
        img = img.resize((size, size), resample.LANCZOS)
        if ext == ".webp":
            img.save(target, "WEBP", quality=92)
        else:
            img.save(target, "PNG")
    else:
        if not have_pil and size:
            print("      [WARN] 未安装 Pillow（pip install pillow），图标按原尺寸复制")
        shutil.copy2(img_path, target)
    return True



def generate_app_icons(config):
    """程序化生成整套应用图标（整合自 custom/gen_app_icon.py 的 do_write 逻辑）。"""
    style = config.get("ICON_STYLE", "cat")
    if style not in ("cat", "3d", "iphone17"):
        print(f"[WARN] 未知风格 {style}，使用默认 cat")
        style = "cat"
    try:
        import PIL  # noqa: F401
    except Exception:
        print("[ERROR] 未安装 Pillow，无法生成图标。请先运行: pip install pillow")
        return False
    print(f"[INFO] 正在生成图标（风格: {style}）...")
    try:
        do_write(style)
        return True
    except Exception as e:
        print(f"[ERROR] 图标生成失败: {e}")
        return False


# ---------------------------------------------------------------- 4. 启动图
def replace_startup_images(config):
    """替换开机启动图与手机端启动图。"""
    custom_dir = CUSTOM_DIR
    mappings = [
        (config.get("STARTUP_LOGO", "startup_logo.png"), [
            os.path.join("app", "src", "leanback", "res", "drawable-nodpi", "startup_logo.png"),
            os.path.join("app", "src", "main", "res", "drawable-nodpi", "startup_logo.png"),
        ]),
        (config.get("MOBILE_STARTUP", "mobile_startup.png"), [
            os.path.join("app", "src", "mobile", "res", "drawable-nodpi", "mobile_startup.png"),
        ]),
    ]
    changed_any = False
    for source_file, targets in mappings:
        source = os.path.join(custom_dir, source_file)
        if not os.path.exists(source):
            print(f"[SKIP] custom/{source_file} 不存在，跳过")
            continue
        for target_rel in targets:
            target = os.path.join(REPO_ROOT, target_rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target) and os.path.getsize(target) == os.path.getsize(source):
                with open(source, "rb") as f1, open(target, "rb") as f2:
                    if f1.read() == f2.read():
                        print(f"[SKIP] {target_rel} 已是最新")
                        continue
            shutil.copy2(source, target)
            print(f"[OK] 复制 {source_file} -> {target_rel}")
            changed_any = True
    return changed_any


# ---------------------------------------------------------------- 5. AndroidManifest
def modify_android_manifest(config):
    """修改 AndroidManifest.xml 中硬编码的 android:label（如果没引用 @string）。"""
    app_name = config.get("APP_NAME", "")
    manifest_path = os.path.join(REPO_ROOT, "app", "src", "main", "AndroidManifest.xml")
    if not os.path.exists(manifest_path):
        return False
    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
    except ET.ParseError:
        return False
    changed = False
    application = root.find("application")
    if application is not None:
        label = application.get(_ANDROID_NS + "label")
        if label and not label.startswith("@"):
            application.set(_ANDROID_NS + "label", app_name)
            changed = True
            print(f'[OK] AndroidManifest.xml: android:label "{label}" -> "{app_name}"')
    if changed:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    return changed


# ---------------------------------------------------------------- 7. 作者链接
def modify_author_links(config):
    """修改「设置增强」页的作者链接 URL_GITHUB / URL_CNB（mobile 与 leanback 各一份）。"""
    github_url = str(config.get("AUTHOR_GITHUB", "")).strip()
    cnb_url = str(config.get("AUTHOR_CNB", "")).strip()
    changed_any = False
    candidates = [
        os.path.join(REPO_ROOT, "app", "src", "mobile", "java", "com", "fongmi",
                     "android", "tv", "ui", "fragment", "SettingEnhanceFragment.java"),
        os.path.join(REPO_ROOT, "app", "src", "leanback", "java", "com", "fongmi",
                     "android", "tv", "ui", "activity", "SettingEnhanceActivity.java"),
    ]
    for full_path in candidates:
        if not os.path.exists(full_path):
            print(f"[SKIP] 文件不存在: {os.path.relpath(full_path, REPO_ROOT)}")
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        rel_path = os.path.relpath(full_path, REPO_ROOT)
        if github_url:
            content = re.sub(
                r'(URL_GITHUB\s*=\s*")[^"]*(")',
                lambda m: m.group(1) + github_url + m.group(2),
                content,
            )
        if cnb_url:
            content = re.sub(
                r'(URL_CNB\s*=\s*")[^"]*(")',
                lambda m: m.group(1) + cnb_url + m.group(2),
                content,
            )
        if content != original:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] {rel_path}: 作者链接已更新（GitHub={github_url or '未改'} / CNB={cnb_url or '未改'}）")
        else:
            print(f"[SKIP] {rel_path}: 已是目标值")
    return changed_any


# ---------------------------------------------------------------- 8. 更新链接
def modify_update_urls(config):
    """把「检查更新」的上游地址（Silent1566 / fish2035）改成你自己的仓库。

    覆盖文件：
      - 主代码：Github.java（7 个 URL 常量）、GithubProxy.java（测速探针）
      - CI 测试：GithubTest.java、GithubProxyTest.java（release-critical 必跑，不同步会挂构建）
    """
    github_repo = str(config.get("UPDATE_GITHUB_REPO", "")).strip()
    cnb_slug = str(config.get("CNB_REPO_SLUG", "")).strip()
    changed_any = False
    candidates = [
        os.path.join(REPO_ROOT, "app", "src", "main", "java", "com", "fongmi", "android", "tv", "utils", "Github.java"),
        os.path.join(REPO_ROOT, "app", "src", "main", "java", "com", "fongmi", "android", "tv", "utils", "GithubProxy.java"),
        os.path.join(REPO_ROOT, "app", "src", "test", "java", "com", "fongmi", "android", "tv", "utils", "GithubTest.java"),
        os.path.join(REPO_ROOT, "app", "src", "test", "java", "com", "fongmi", "android", "tv", "utils", "GithubProxyTest.java"),
    ]
    for full_path in candidates:
        if not os.path.exists(full_path):
            print(f"[SKIP] 文件不存在: {os.path.relpath(full_path, REPO_ROOT)}")
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        rel_path = os.path.relpath(full_path, REPO_ROOT)
        if github_repo:
            content = re.sub(r'api\.github\.com/repos/Silent1566/webhtv',
                             f'api.github.com/repos/{github_repo}', content)
            content = re.sub(r'github\.com/Silent1566/webhtv',
                             f'github.com/{github_repo}', content)
        if cnb_slug:
            content = re.sub(r'cnb\.cool/fish2035/webhtv-release',
                             f'cnb.cool/{cnb_slug}', content)
        if content != original:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] {rel_path}: 更新链接已替换（GitHub={github_repo or '未改'} / CNB={cnb_slug or '未改'}）")
        else:
            print(f"[SKIP] {rel_path}: 已是目标值")
    return changed_any


# ---------------------------------------------------------------- 8. 更新顺序：CNB 优先
def modify_update_order(config):
    '''
    增强更新机制（Updater.java + Github.java），三处修改：
      1) getUpdate()：先读 CNB raw manifest（https://cnb.cool/<slug>/-/git/raw/main/apk/xx.json），
         失败才回退 GitHub（update-channel -> latest -> GitHub API 兜底）。
      2) getApkUrl()：CNB 源（SOURCE_CNB）命中后，APK 下载地址 = CNB Release 直链
         https://cnb.cool/<slug>/-/releases/download/<tag>/xx.apk（sync-cnb-release.sh 上传后
         manifest apk 字段即该地址），国内直连 CNB、绕开 GitHub。
      3) getRoutes()：把 CNB 下载地址作为第一路由，GitHub Release 原地址由
         UpdateRoutePlanner.plan() 追加为兜底（CNB 下载失败自动回退）。
    约束：UpdateRoutePlanner 本身不动（签名/逻辑不变），CI 测试均不受影响。
    '''
    changed_any = False
    cnb_slug = str(config.get("CNB_REPO_SLUG", "")).strip()

    # ---------- A. Updater.java ----------
    rel_path = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "Updater.java")
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[SKIP] {rel_path} 不存在")
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    # 清除历史污染的控制字符（如 \u0001），避免 Java 编译失败
    content = "".join(ch for ch in content if ch >= " " or ch in "\n\r\t")

    # A1. getUpdate()：CNB raw manifest 优先（先试 CNB，再 GitHub）
    old_block = '''        Update update = readUpdate(channel, Github.getChannelAsset(manifestName), SOURCE_GITHUB);
        if (update.hasManifest()) return update;
        if (Update.CHANNEL_BETA.equals(channel)) {
            update = readUpdate(channel, Github.getCnbMirrorAsset(manifestName), SOURCE_CNB);
            if (update.hasManifest()) return update;
            return getGithubBetaUpdate(channel);
        }'''
    new_block = '''        Update update = readUpdate(channel, Github.getCnbMirrorAsset(manifestName), SOURCE_CNB);
        if (update.hasManifest()) return update;
        if (Update.CHANNEL_BETA.equals(channel)) {
            update = readUpdate(channel, Github.getChannelAsset(manifestName), SOURCE_GITHUB);
            if (update.hasManifest()) return update;
            return getGithubBetaUpdate(channel);
        }'''
    if old_block in content:
        content = content.replace(old_block, new_block)
    elif "Update update = readUpdate(channel, Github.getCnbMirrorAsset(manifestName), SOURCE_CNB);" not in content:
        print(f"[WARN] {rel_path}: 未匹配到已知的 getUpdate 顺序代码，请人工检查 Updater.java")

    # A2. getApkUrl()：SOURCE_CNB 命中后直接拼 CNB Release 下载直链
    old_apkurl = '''        if (SOURCE_GITHUB.equals(source) && !TextUtils.isEmpty(update.name)) return Github.getGithubReleaseAsset(update.name, getFileName(apk, update.channel));
        if (apk.startsWith("http://") || apk.startsWith("https://")) return apk;'''
    new_apkurl = '''        if (SOURCE_GITHUB.equals(source) && !TextUtils.isEmpty(update.name)) return Github.getGithubReleaseAsset(update.name, getFileName(apk, update.channel));
        if (SOURCE_CNB.equals(source) && !TextUtils.isEmpty(update.name)) return Github.getCnbReleaseAsset(update.name, getFileName(apk, update.channel));
        if (apk.startsWith("http://") || apk.startsWith("https://")) return apk;'''
    if old_apkurl in content and "Github.getCnbReleaseAsset(update.name" not in content:
        content = content.replace(old_apkurl, new_apkurl)

    # A3. getRoutes()：CNB 下载地址第一路由，GitHub/OCI 由 plan() 追加为兜底
    if "import java.util.ArrayList;" not in content and "import java.util.Arrays;" in content:
        content = content.replace("import java.util.Arrays;", "import java.util.ArrayList;\nimport java.util.Arrays;")
    old_routes = "            return UpdateRoutePlanner.plan(Setting.getUpdateSource(), update.githubUrl, update.oci, github, endpoint);"
    new_routes = '''            List<UpdateTarget> routes = new ArrayList<>();
            String cnbUrl = update.apkUrl;
            if (cnbUrl != null && cnbUrl.startsWith("https://cnb.cool/")) {
                routes.add(UpdateTarget.github(cnbUrl));
            }
            routes.addAll(UpdateRoutePlanner.plan(Setting.getUpdateSource(), update.githubUrl, update.oci, github, endpoint));
            return routes;'''
    if old_routes in content and "String cnbUrl = update.apkUrl;" not in content:
        content = content.replace(old_routes, new_routes)

    if content != original:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        changed_any = True
        print(f"[OK] {rel_path}: CNB 优先 manifest + CNB 直连下载 + 路由兜底已生效")

    # ---------- B. Github.java：新增 CNB Release 下载常量与方法 ----------
    github_rel = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "utils", "Github.java")
    github_path = os.path.join(REPO_ROOT, github_rel)
    if not os.path.exists(github_path):
        print(f"[SKIP] {github_rel} 不存在")
    else:
        with open(github_path, "r", encoding="utf-8") as f:
            g_content = f.read()
        g_original = g_content
        # 清除历史污染的控制字符（如 \u0001），避免 Java 编译失败
        g_content = "".join(ch for ch in g_content if ch >= " " or ch in "\n\r\t")

        if "CNB_RELEASE_DOWNLOAD" not in g_content:
            release_base = f"https://cnb.cool/{cnb_slug}/-/releases/download" if cnb_slug else "https://cnb.cool/fish2035/webhtv-release/-/releases/download"
            g_content = re.sub(
                r'(private static final String CNB_MANIFEST = "[^"]*";)',
                '\\1\n    private static final String CNB_RELEASE_DOWNLOAD = "' + release_base + '";',
                g_content,
            )
            if not cnb_slug:
                print(f"[WARN] {github_rel}: CNB_REPO_SLUG 未配置，CNB_RELEASE_DOWNLOAD 暂用旧地址，请检查")
        if "public static String getCnbReleaseAsset" not in g_content:
            g_content = g_content.replace(
                '    public static String getCnbMirrorAsset(String name) {\n'
                '        return CNB_MANIFEST + "/" + name;\n'
                '    }',
                '    public static String getCnbMirrorAsset(String name) {\n'
                '        return CNB_MANIFEST + "/" + name;\n'
                '    }\n'
                '\n'
                '    public static String getCnbReleaseAsset(String tag, String name) {\n'
                '        return CNB_RELEASE_DOWNLOAD + "/" + tag + "/" + name;\n'
                '    }',
            )
        if g_content != g_original:
            with open(github_path, "w", encoding="utf-8") as f:
                f.write(g_content)
            changed_any = True
            print(f"[OK] {github_rel}: 新增 CNB_RELEASE_DOWNLOAD 常量 + getCnbReleaseAsset 方法")

    if changed_any:
        return True
    print("[SKIP] 更新机制已是目标状态（CNB 优先 + CNB 直连下载 + 路由兜底）")
    return False


# ---------------------------------------------------------------- 9. CNB 脚本
def modify_cnb_release_script(config):
    """修改 sync-cnb-release.sh 中的 CNB_REPO_SLUG。"""
    cnb_repo_slug = config.get("CNB_REPO_SLUG", "")
    if not cnb_repo_slug:
        print("[SKIP] CNB_REPO_SLUG 未配置")
        return False
    candidates = [
        os.path.join(REPO_ROOT, "github", "scripts", "sync-cnb-release.sh"),
        os.path.join(REPO_ROOT, ".github", "scripts", "sync-cnb-release.sh"),
        os.path.join(REPO_ROOT, "scripts", "sync-cnb-release.sh"),
        os.path.join(REPO_ROOT, "sync-cnb-release.sh"),
    ]
    script_path = next((p for p in candidates if os.path.exists(p)), None)
    if not script_path:
        print("[SKIP] 未找到 sync-cnb-release.sh")
        return False
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    content = re.sub(
        r'(CNB_REPO_SLUG\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{cnb_repo_slug}\g<2>",
        content,
    )
    content = re.sub(
        r'(CNB_REPO_SLUG\s*=\s*"\$\{CNB_REPO_SLUG:-)[^}]+(\}")',
        rf"\g<1>{cnb_repo_slug}\g<2>",
        content,
    )
    if content != original:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] sync-cnb-release.sh: CNB_REPO_SLUG -> {cnb_repo_slug}")
        return True
    print("[SKIP] sync-cnb-release.sh: 已是目标值")
    return False


# ---------------------------------------------------------------- 7. 工作流 yml
def modify_workflow_files(config):
    """
    修改 .github/workflows/android-release.yml 与 cnb-release-sync.yml：
      - 替换 CNB_REPO_SLUG / CNB_REPO_URL
      - 向 Build four release APKs 步骤注入 GRADLE_OPTS（R8 OOM 修复）
    注意：全部使用标准英文半角减号，杜绝 U+2011 非法字符。
    """
    cnb_repo_slug = config.get("CNB_REPO_SLUG", "")
    if not cnb_repo_slug:
        print("[SKIP] CNB_REPO_SLUG 未配置，跳过工作流修改")
        return False
    cnb_repo_url = f"https://cnb.cool/{cnb_repo_slug}.git"
    workflow_files = [
        os.path.join(".github", "workflows", "android-release.yml"),
        os.path.join(".github", "workflows", "cnb-release-sync.yml"),
    ]
    changed_any = False
    for rel_path in workflow_files:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(full_path):
            print(f"[SKIP] {rel_path} 不存在")
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content

        # 替换 CNB 变量
        content = re.sub(
            r'(CNB_REPO_SLUG:\s*)[^\s\'"\n]+',
            rf'\g<1>{cnb_repo_slug}',
            content,
        )
        content = re.sub(
            r"(\|\|\s*')[^']+('\s*\}\})",
            rf"\g<1>{cnb_repo_slug}\g<2>",
            content,
        )
        content = re.sub(
            r'(blank\s*=\s*)[^\s\'"\n,]+',
            rf'\g<1>{cnb_repo_slug}',
            content,
        )
        content = re.sub(
            r'(CNB_REPO_URL:\s*)https://[^\s\'"\n]+',
            rf'\g<1>{cnb_repo_url}',
            content,
        )
        content = re.sub(
            r"(\|\|\s*')https://[^']+('\s*\}\})",
            rf"\g<1>{cnb_repo_url}\g<2>",
            content,
        )

        # 修复脚本可执行权限：Windows 推送的文件常丢失 +x 位，直接 ./script.sh 会 Permission denied
        # 在每个脚本调用行前注入 chmod +x（幂等：已有 chmod 行则跳过）
        if "sync-cnb-release.sh" in content and "chmod +x .github/scripts/sync-cnb-release.sh" not in content:
            pat_chmod = re.compile(
                r'^([ \t]*)(\.github/scripts/sync-cnb-release\.sh)([ \t]*)$',
                re.MULTILINE,
            )
            content = pat_chmod.sub(
                lambda m: f"{m.group(1)}chmod +x .github/scripts/sync-cnb-release.sh\n"
                          f"{m.group(1)}{m.group(2)}{m.group(3)}",
                content,
            )
            print(f"[OK] {rel_path}: 注入 chmod +x（修复 Permission denied）")

        # 仅对 android-release.yml 注入 GRADLE_OPTS
        if rel_path.endswith("android-release.yml"):
            gradle_line = '          GRADLE_OPTS: "-Xmx4096m -XX:MaxMetaspaceSize=512m"'
            if "GRADLE_OPTS" in content:
                print("[SKIP] android-release.yml: GRADLE_OPTS 已存在")
            else:
                # 分支1：步骤已有 env 块 -> 在 env 块末尾追加 GRADLE_OPTS
                pat_has_env = re.compile(
                    r'(- name: Build four release APKs[ \t]*\r?\n( +)env:[ \t]*\r?\n(?:\2 +.+\r?\n)*)(\2)run:',
                    re.MULTILINE,
                )
                if pat_has_env.search(content):
                    content = pat_has_env.sub(
                        rf'\g<1>{gradle_line}\n\g<3>run:',
                        content,
                    )
                    print("[OK] android-release.yml: 已有 env 块，追加 GRADLE_OPTS")
                else:
                    # 分支2：步骤没有 env 块 -> 插入完整 env 块
                    pat_no_env = re.compile(
                        r'(- name: Build four release APKs[ \t]*\r?\n)( +)(run:)',
                        re.MULTILINE,
                    )
                    if pat_no_env.search(content):
                        insert_env = """        env:
          WEBHTV_RELEASE_TAG: ${{ steps.meta.outputs.tag }}
          WEBHTV_APK_SUFFIX: ${{ steps.meta.outputs.apk_suffix }}
          GRADLE_OPTS: "-Xmx4096m -XX:MaxMetaspaceSize=512m"
"""
                        content = pat_no_env.sub(
                            rf"\g<1>{insert_env}\g<2>\g<3>",
                            content,
                        )
                        print("[OK] android-release.yml: 注入 env 块 + GRADLE_OPTS")
                    else:
                        print("[WARN] android-release.yml: 未找到 Build four release APKs 步骤，跳过 GRADLE_OPTS 注入")

            # publish_oci 输入项默认改为 false（GitHub Actions 触发时默认不打勾，需要时再手动勾选）
            # 用逐行扫描实现，零正则回溯风险，保证不卡死
            oci_lines = content.splitlines(keepends=True)
            oci_patched = False
            oci_found = False
            for i, line in enumerate(oci_lines):
                if line.strip().startswith("publish_oci:"):
                    oci_found = True
                    for j in range(i + 1, min(i + 6, len(oci_lines))):
                        m_default = re.match(r'^(\s*default:\s*)(true|false)(\s*)$', oci_lines[j])
                        if m_default:
                            if m_default.group(2) == "true":
                                oci_lines[j] = m_default.group(1) + "false" + m_default.group(3)
                                oci_patched = True
                            break
            if oci_patched:
                content = "".join(oci_lines)
                print("[OK] android-release.yml: publish_oci 默认值已改为 false（默认不打勾）")
            else:
                if oci_found:
                    print("[SKIP] android-release.yml: publish_oci 默认值已是 false")
                else:
                    print("[WARN] android-release.yml: 未找到 publish_oci 输入项，跳过")

        if content != original:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] {rel_path}: CNB 配置 / GRADLE_OPTS 已更新")
        else:
            print(f"[SKIP] {rel_path}: 已是目标值")
    return changed_any


# ---------------------------------------------------------------- 主流程
def main():
    print("=" * 72)
    print("  local_customize.py —— 本地一键自定义（名称 / 图标 / 包名 / CNB / 内存）")
    print(f"  项目根目录: {REPO_ROOT}")
    print("=" * 72)

    if not os.path.isdir(REPO_ROOT):
        print(f"[ERROR] 找不到项目根目录: {REPO_ROOT}")
        sys.exit(1)

    load_config_env()
    config = CONFIG

    if not os.path.isdir(CUSTOM_DIR):
        os.makedirs(CUSTOM_DIR, exist_ok=True)
        print(f"[INFO] 已创建 custom/ 目录：{CUSTOM_DIR}")

    results = []

    print("\n--- [1/11] app/build.gradle（applicationId + viewBinding）---")
    results.append(modify_build_gradle(config))

    print("\n--- [2/11] 多语言 app 名称（values / values-zh-rCN / values-zh-rTW）---")
    results.append(modify_all_strings(config))

    print("\n--- [3/11] 程序化生成整套应用图标（gen_app_icon 逻辑，风格: %s）---" % config.get("ICON_STYLE", "3d"))
    results.append(generate_app_icons(config))

    print("\n--- [4/11] 启动图（startup_logo / mobile_startup）---")
    results.append(replace_startup_images(config))

    print("\n--- [5/11] AndroidManifest.xml（android:label）---")
    results.append(modify_android_manifest(config))

    print("\n--- [6/11] 设置页作者链接（URL_GITHUB / URL_CNB）---")
    results.append(modify_author_links(config))

    print("\n--- [7/11] 检查更新链接（Github.java / GithubProxy.java / CI 测试）---")
    results.append(modify_update_urls(config))

    print("\n--- [8/11] 更新机制（CNB 优先 manifest + CNB 直连下载 APK + GitHub 兜底路由）---")
    results.append(modify_update_order(config))

    print("\n--- [9/11] sync-cnb-release.sh（CNB_REPO_SLUG）---")
    results.append(modify_cnb_release_script(config))

    print("\n--- [10/11] 工作流 yml（CNB 地址 + chmod +x 权限 + GRADLE_OPTS 内存修复 + publish_oci 默认关闭）---")
    results.append(modify_workflow_files(config))

    print("\n--- [11/11] 最终校验：namespace 是否保持上游原值 ---")
    ns_ok = True
    ns_pattern = re.compile(r'namespace\s*=\s*[\'"]com\.fongmi\.android\.tv[\'"]')
    for path in [os.path.join(REPO_ROOT, "app", "build.gradle"),
                 os.path.join(REPO_ROOT, "app", "build.gradle.kts")]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                txt = f.read()
            if not ns_pattern.search(txt):
                print(f"[ERROR] {os.path.basename(path)} 中未发现 namespace com.fongmi.android.tv，请检查！")
                ns_ok = False
            else:
                print(f"[OK] {os.path.basename(path)} namespace 保持 com.fongmi.android.tv")
    results.append(ns_ok)

    print("\n" + "=" * 72)
    if any(results):
        print("  [DONE] 自定义修改完成！请检查上方日志。")
    else:
        print("  [DONE] 未发现需要修改的内容（或所有文件已是目标状态）。")
    print("=" * 72)
    print()
    print("【下一步】")
    print("  1. git add -A")
    print("  2. git commit -m \"local customize: app name/icon/package/cnb\"")
    print("  3. git push 到你的构建仓库（如 tangtv 的 main 分支）")
    print("  4. 在 GitHub Actions 手动触发 Android Release 工作流，即可打包生成 APK")
    print()
    print("  若推送的是 webhtv 仓库：触发 auto-sync / release-sync 会自动同步到 tangtv。")
    print("  提示：仓库 Secrets 中需配置 RELEASE_KEYSTORE_BASE64 / RELEASE_STORE_PASSWORD /")
    print("       RELEASE_KEY_ALIAS 等签名信息，release 构建才会成功。")


if __name__ == "__main__":
    main()
