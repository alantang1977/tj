#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 local_customize.py —— 本地一键自定义脚本（webhtv / tangtv 项目）
================================================================================
在【本地克隆下来的项目根目录】运行：

    python3 local_customize.py        （或 python local_customize.py）
    python3 local_customize.py --force  # 强制模式：跳过幂等判断，全部重写

脚本会直接修改你本地项目文件，自动完成以下全部自定义：

  [1] applicationId 安装包名 + 自动补全 buildFeatures { viewBinding true }
      （注意：namespace 保持上游 com.fongmi.android.tv，绝不修改）
  [2] app 显示名称（英文 / 简体 / 繁体 多语言 strings.xml + AndroidManifest 硬编码 label）
  [3] app 启动图标（程序化生成整套，cat 风格为卡通蓝猫头）：
      - 旧版 launcher：mipmap-mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi（ic_launcher.png + round.webp）
      - 自适应图标（API26+）：mipmap-anydpi-v26（背景矢量 + 彩色前景 PNG + monochrome 矢量）
      - TV banner 320x180（leanback drawable + adaptive xml）
      - Play Store 512x512、App 内 Logo 600px、通知栏图标（纯白扁平）、网页 favicon.ico
      - 耳朵根部沿头圆圆弧贴合；内白耳为收尖楔子，底边与外耳根同心
  [4] 开机启动图 startup_logo.png、手机端启动图 mobile_startup.png
  [5] AndroidManifest 接线：
      - android:label 若为硬编码则改成 @string
      - android:banner 强制指向 @drawable/ic_banner（320x180 长方形），
        banner PNG 同时写入 drawable-xhdpi 与 drawable-nodpi，适配当贝桌面等 TV 启动器
  [6] 设置页作者链接（URL_GITHUB / URL_CNB）
  [7] 「检查更新」链接替换（Github.java / GithubProxy.java / 对应单测）：
      上游 Silent1566 改为你配置的 GitHub 仓库 + CNB 仓库
  [8] 更新机制改为 CNB 优先：
      先拉 https://cnb.cool/<slug>/-/git/raw/main/apk/xx.json 版本清单，
      APK 走 CNB Release 直链下载；CNB 不可用时自动回退 GitHub
  [9] CNB 发布脚本 sync-cnb-release.sh 中的 CNB_REPO_SLUG / URL
 [10] Android Release 工作流 yml（CNB 地址 + 执行权限 + GRADLE_OPTS 清理 + OCI 开关）
 [11] 内存参数固化到 gradle.properties（org.gradle.jvmargs / workers.max / r8.maxWorkers，
      解决 R8 OOM: Java heap space；并清理 workflow 中残留的 GRADLE_OPTS，杜绝双源冲突）
 [12] 最终校验：namespace 必须仍为 com.fongmi.android.tv

【重要警告】
  1. namespace 必须保持上游原值 com.fongmi.android.tv，本脚本绝不修改它。
     项目 Java 源码全部硬编码 import com.fongmi.android.tv.R / databinding.*，
     改 namespace 会导致上百个 cannot find symbol 编译错误。
  2. 修改完成后，用 git 提交并推送到你的构建仓库（如 tangtv），
     再触发 Android Release 工作流即可打包生成 APK。
  3. 当贝桌面 v4.x 会强缓存旧图标：装新 APK 后需在当贝「设置-清除桌面缓存」
     （或卸载旧版 -> 清缓存 -> 重装 -> 重启），否则仍显示旧方形图标。

【配置】
  配置集中在下方 CONFIG 字典；若项目里存在 custom/config.env，
  会优先读取 config.env 覆盖 CONFIG（适合多人/多机不改脚本本体）。

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
try:
    import yaml as _yaml  # 可选：用于校验 workflow YAML 改完后仍可解析
    _YAML_OK = True
except Exception:
    _yaml = None
    _YAML_OK = False
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
    # 猫咪眼睛虹膜配色：
    #   amber 琥珀金（默认，暖色与青色头撞色、最醒目，呼应金铃铛）
    #   emerald 翡翠绿（与青色头部邻近色、柔和协调）
    #   sapphire 宝石蓝（冷色统一、通透）
    #   aqua 碧眼湖青（与头部同色系、整体感强）
    #   violet 紫罗兰（呼应紫粉背景、活泼）
    #   none 原版黑白眼（无彩色虹膜）
    "EYE_IRIS": "amber",
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
# 用 app/build.gradle 是否存在来判断项目根目录，比仅靠目录名更稳妥
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_SCRIPT_DIR, "app", "build.gradle")):
    REPO_ROOT = _SCRIPT_DIR
elif os.path.exists(os.path.join(os.path.dirname(_SCRIPT_DIR), "app", "build.gradle")):
    REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
else:
    # 回退：按目录名判断（兼容项目根目录本身叫 custom 的罕见情况）
    if os.path.basename(_SCRIPT_DIR) == "custom":
        REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
    else:
        REPO_ROOT = _SCRIPT_DIR

CUSTOM_DIR = os.path.join(REPO_ROOT, "custom")

# 强制模式：跳过所有幂等判断，强制重写所有可修改文件
# 用法：python local_customize.py --force
# 适用场景：上游同步后文件形态变化、怀疑脚本假阳性 SKIP、或需要确保所有修改落地
FORCE_MODE = False
# --auto-rollback：写盘后若读盘校验失败，自动把文件还原成修改前内容，
# 绝不把"自己都验证不过"的文件留在工作区（宁可保持上游原样，也不让 CI 报错）
AUTO_ROLLBACK = False

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
SS = 5          # 超采样倍率，先大图绘制再降采样得到干净边缘（5x 比 4x 边缘更锐利）
CAT_ZOOM = 1.15  # 实体猫放大倍数：圆形耳尖不触边的上限约 1.17(贴边)，1.15 留约1%安全间隙
CAT_KEEP_ALPHA = 80  # 视为“实体猫”的 alpha 下限（腮红115/暗边130保留，弱光晕26/60剔除）
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
CAT_BLUE_TOP = (200, 232, 255, 255)
CAT_BLUE_MID = (96, 168, 240, 255)
CAT_BLUE_BOT = (40, 110, 200, 255)
CAT_BLUE_SIDE = (24, 70, 150, 255)
CAT_PINK = (255, 150, 180, 255)
CAT_DARK = (15, 60, 60, 255)
CAT_NOSE = (247, 122, 152, 255)
CAT_COLLAR = (7, 193, 96, 255)
CAT_COLLAR_HL = (120, 230, 190, 255)
CAT_BELL = (252, 188, 48, 255)

# 彩色虹膜配色：outer=虹膜外缘主色, inner=靠瞳孔亮色, ring=最外圈深色描边
EYE_SCHEMES = {
    "amber":    {"outer": (240, 165, 45),  "inner": (255, 226, 150), "ring": (176, 104, 16)},
    "emerald":  {"outer": (74, 196, 132),  "inner": (190, 245, 205), "ring": (24, 128, 80)},
    "sapphire": {"outer": (86, 158, 240),  "inner": (190, 222, 255), "ring": (24, 84, 178)},
    "aqua":     {"outer": (60, 206, 196),  "inner": (185, 245, 240), "ring": (16, 128, 128)},
    "violet":   {"outer": (160, 122, 232), "inner": (222, 205, 255), "ring": (96, 60, 178)},
}
_IRIS_TILE_CACHE = {}


def _iris_tile(diameter, scheme):
    """生成径向渐变虹膜 RGBA 方块（带缓存）。中心亮 -> 外缘主色 -> 最外圈深色环。"""
    key = (int(diameter), scheme["outer"], scheme["inner"], scheme["ring"])
    if key in _IRIS_TILE_CACHE:
        return _IRIS_TILE_CACHE[key]
    s = max(2, int(diameter))
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = img.load()
    c = (s - 1) / 2.0
    outer, inner, ring = scheme["outer"], scheme["inner"], scheme["ring"]
    for y in range(s):
        for x in range(s):
            dist = _math.hypot(x - c, y - c) / (s / 2.0)
            if dist > 1.0:
                continue
            if dist > 0.90:
                col = ring
            elif dist > 0.55:
                t = (dist - 0.55) / 0.35
                col = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
            else:
                t = (dist / 0.55) ** 0.8
                col = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
            px[x, y] = (col[0], col[1], col[2], 255)
    _IRIS_TILE_CACHE[key] = img
    return img


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
                                      fill=(190, 225, 255, 26))
    halo_out = halo_out.filter(ImageFilter.GaussianBlur(radius=r * 0.35))
    layer.alpha_composite(halo_out)
    halo_in = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(halo_in).ellipse([halo_cx - r * 1.10, halo_cy - r * 1.10,
                                      halo_cx + r * 1.10, halo_cy + r * 1.10],
                                     fill=(205, 232, 255, 60))
    halo_in = halo_in.filter(ImageFilter.GaussianBlur(radius=r * 0.18))
    layer.alpha_composite(halo_in)

    # ===== 耳朵（圆角三角，耳根沿头圆圆弧贴合）=====
    # 把耳根两端投影到头圆（半径 r）上，耳底边不再是直线弦，
    # 而是沿头圆走的短弧；耳尖位置 / 里外分色 / 颜色保持不变。
    def _round_tip(pts, tip_idx, radius):
        """只把多边形第 tip_idx 个顶点用二次贝塞尔圆角（其余边保持原样）。"""
        V = pts[tip_idx]; A = pts[tip_idx - 1]; B = pts[tip_idx + 1]
        vlen = _math.hypot(V[0] - A[0], V[1] - A[1])
        alen = _math.hypot(V[0] - B[0], V[1] - B[1])
        ra = min(radius, vlen * 0.5); rb = min(radius, alen * 0.5)
        P1 = (V[0] + (A[0] - V[0]) * ra / vlen, V[1] + (A[1] - V[1]) * ra / vlen)
        P2 = (V[0] + (B[0] - V[0]) * rb / alen, V[1] + (B[1] - V[1]) * rb / alen)
        out = list(pts[:tip_idx])
        for s in range(13):
            t = s / 12
            x = (1 - t) * (1 - t) * P1[0] + 2 * (1 - t) * t * V[0] + t * t * P2[0]
            y = (1 - t) * (1 - t) * P1[1] + 2 * (1 - t) * t * V[1] + t * t * P2[1]
            out.append((x, y))
        out.extend(pts[tip_idx + 1:])
        return out

    def ear_geom(side):
        if side < 0:
            tip = (cx - r * 1.24, head_cy - r * 1.15)
            outer_raw = (cx - r * 0.96, head_cy - r * 0.45)
            inner_raw = (cx - r * 0.46, head_cy - r * 0.78)
        else:
            tip = (cx + r * 1.24, head_cy - r * 1.15)
            outer_raw = (cx + r * 0.96, head_cy - r * 0.45)
            inner_raw = (cx + r * 0.46, head_cy - r * 0.78)
        # 耳根两点投影到头圆上（方位角不变，半径统一为 r）
        def proj(pt):
            dx = pt[0] - cx; dy = pt[1] - head_cy
            dist = _math.hypot(dx, dy)
            return (cx + dx * r / dist, head_cy + dy * r / dist)
        outer = proj(outer_raw); inner = proj(inner_raw)
        a_outer = _math.atan2(outer[1] - head_cy, outer[0] - cx)
        a_inner = _math.atan2(inner[1] - head_cy, inner[0] - cx)
        da = a_inner - a_outer
        while da > _math.pi: da -= 2 * _math.pi
        while da < -_math.pi: da += 2 * _math.pi
        n_arc = 24
        arc_pts = [(cx + r * _math.cos(a_outer + da * (i / n_arc)),
                    head_cy + r * _math.sin(a_outer + da * (i / n_arc))) for i in range(n_arc + 1)]
        mid_idx = n_arc // 2
        return tip, inner, outer, arc_pts, mid_idx, a_outer, a_inner, da

    for side in (-1, 1):
        tip, inner, outer, arc_pts, mid_idx, a_outer, a_inner, da = ear_geom(side)
        # 外侧半（晴空藏蓝）：tip -> outer -> 沿弧 -> mid -> tip
        outer_half = _round_tip([tip] + arc_pts[:mid_idx + 1], 0, ER)
        d.polygon(outer_half, fill=CAT_BLUE_SIDE)
        # 内侧半（蜜桃珊瑚点缀）：tip -> mid -> 沿弧 -> inner -> tip
        inner_half = _round_tip([tip] + arc_pts[mid_idx:], 0, ER)
        d.polygon(inner_half, fill=(250, 150, 120, 255))
        # 耳根即头圆圆弧，不再画直线弦 / 深色缝线

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
                # 暗部带一点冷青（冰川环境色反射）
                c_mid = CAT_BLUE_MID
                c_bot = (CAT_BLUE_BOT[0] + 5, CAT_BLUE_BOT[1] + 10, CAT_BLUE_BOT[2] + 5)
                c = tuple(int(c_mid[i] + (c_bot[i] - c_mid[i]) * t) for i in range(3))
            hgd.point((xx, yy), fill=c + (255,))
    layer.paste(hgrad, (0, 0), head_mask)

    # 纯白亮光耳内（内嵌小楔子：白尖朝耳尖，底边沿头圆弧、与外耳根对齐）
    for side in (-1, 1):
        tip, inner, outer, arc_pts, mid_idx, a_outer, a_inner, da = ear_geom(side)
        r_white_base = r * 0.99            # 白底贴头圆，与外耳根对齐
        a_ws = a_outer + da * 0.12         # 两侧各内收 12%，白耳整体小一号
        a_we = a_inner - da * 0.12
        n_w = 12
        base_arc = [(cx + r_white_base * _math.cos(a_ws + (a_we - a_ws) * (i / n_w)),
                     head_cy + r_white_base * _math.sin(a_ws + (a_we - a_ws) * (i / n_w)))
                    for i in range(n_w + 1)]
        a_mid = a_ws + (a_we - a_ws) * 0.5
        r_wtip = r * 1.45                  # 白尖半径，收尖朝耳尖
        wtip = (cx + r_wtip * _math.cos(a_mid), head_cy + r_wtip * _math.sin(a_mid))
        pts = _round_tip([wtip] + base_arc, 0, r * 0.06)
        ear_mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(ear_mask).polygon(pts, fill=255)
        ear_grad = Image.new("RGBA", (size, size), HOLE)
        egd = ImageDraw.Draw(ear_grad)
        for yy in range(int(size)):
            k = yy / size
            r_c = int(255 * (1 - k) + 243 * k)
            g_c = int(255 * (1 - k) + 246 * k)
            b_c = int(255 * (1 - k) + 252 * k)
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
                             start=20, end=160, fill=(10, 60, 70, 130), width=int(r * 0.10))
    rim = rim.filter(ImageFilter.GaussianBlur(radius=r * 0.06))
    layer.alpha_composite(rim)

    # ===== 奶白脸盘（纯白 + 极淡投影浮起感）=====
    face_cy = head_cy + r * 0.18
    face_box = [cx - r * 0.70, face_cy - r * 0.55,
                cx + r * 0.70, face_cy + r * 0.62]
    # 脸盘投影（淡灰偏移）
    face_sh = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(face_sh).ellipse([face_box[0] + r * 0.015, face_box[1] + r * 0.02,
                                      face_box[2] + r * 0.015, face_box[3] + r * 0.02],
                                     fill=(0, 40, 50, 40))
    face_sh = face_sh.filter(ImageFilter.GaussianBlur(radius=r * 0.04))
    layer.alpha_composite(face_sh)
    d.ellipse(face_box, fill=(247, 240, 228, 255))
    # 脸瓷面柔光（上半部分微妙高光，瓷面质感，与猫头光泽统一）
    face_gloss = Image.new("RGBA", (size, size), HOLE)
    ImageDraw.Draw(face_gloss).ellipse([cx - r * 0.55, face_cy - r * 0.50,
                                          cx + r * 0.10, face_cy - r * 0.05],
                                         fill=(255, 255, 255, 35))
    face_gloss = face_gloss.filter(ImageFilter.GaussianBlur(radius=r * 0.10))
    layer.alpha_composite(face_gloss)

    # 大圆眼（low-poly 眼睛设计元素）：纯白大眼白 + 大黑瞳 + 左上单一高光点
    # 说明：去掉彩色虹膜 / 瞳孔月牙 / 副高光；眼白较原版略放大，浅奶白脸盘上保留一圈细灰描边。
    eye_y = face_cy - r * 0.10
    eye_dx, eye_R = r * 0.375, r * 0.205
    pupil_R = eye_R * 0.70
    for ex in (cx - eye_dx, cx + eye_dx):
        # 细灰描边（保证浅脸盘上眼白轮廓可读）
        d.ellipse([ex - eye_R - 1, eye_y - eye_R - 1,
                   ex + eye_R + 1, eye_y + eye_R + 1],
                  fill=(206, 212, 222, 255))
        # 纯白大眼白（无彩色虹膜）
        d.ellipse([ex - eye_R, eye_y - eye_R, ex + eye_R, eye_y + eye_R],
                  fill=(255, 255, 255, 255))
        # 大黑瞳
        d.ellipse([ex - pupil_R, eye_y - pupil_R, ex + pupil_R, eye_y + pupil_R],
                  fill=(13, 15, 32, 255))
        # 单一高光点（左上，加大更有神，完整落在瞳孔内）
        hl_r = eye_R * 0.25
        d.ellipse([ex - eye_R * 0.30 - hl_r, eye_y - eye_R * 0.30 - hl_r,
                   ex - eye_R * 0.30 + hl_r, eye_y - eye_R * 0.30 + hl_r],
                  fill=(255, 255, 255, 255))

    # 淡粉腮红（柔光，两颊）
    for _sg in (-1, 1):
        _bl = Image.new("RGBA", (size, size), HOLE)
        _bd = ImageDraw.Draw(_bl)
        _bx, _by, _br = cx + _sg * r * 0.56, face_cy + r * 0.14, r * 0.135
        _bd.ellipse([_bx - _br, _by - _br, _bx + _br, _by + _br], fill=(255, 150, 172, 115))
        _bl = _bl.filter(ImageFilter.GaussianBlur(r * 0.05))
        layer.alpha_composite(_bl)

    # 粉鼻（圆润水滴椭圆，日系Q版，与闭眼表情搭配）
    nose_y = face_cy + r * 0.10
    nw = r * 0.105
    d.ellipse([cx - nw, nose_y - nw * 0.25, cx + nw, nose_y + nw * 1.1], fill=CAT_NOSE)
    # 鼻尖水滴高光（两点+细线，湿润鼻头质感）
    d.ellipse([cx - nw * 0.52, nose_y + nw * 0.00,
               cx - nw * 0.14, nose_y + nw * 0.34], fill=(255, 255, 255, 240))
    d.ellipse([cx + nw * 0.04, nose_y + nw * 0.16,
               cx + nw * 0.30, nose_y + nw * 0.40], fill=(255, 255, 255, 180))
    d.line([(cx - nw * 0.40, nose_y + nw * 0.52), (cx + nw * 0.40, nose_y + nw * 0.52)],
           fill=(255, 255, 255, 120), width=max(1, int(nw * 0.12)))
    # 鼻头底部暗影弧（增强水滴鼻立体感）
    d.arc([cx - nw, nose_y + nw * 0.10, cx + nw, nose_y + nw * 1.30],
          start=20, end=160, fill=(205, 90, 110, 140),
          width=max(1, int(nw * 0.21)))

    # 三瓣嘴（中间竖线 + 左右圆润弧，日系Q版）
    mouth_cy = nose_y + nw * 1.3
    d.line([(cx, mouth_cy), (cx, mouth_cy + nw * 0.6)],
           fill=CAT_DARK, width=int(size * 0.010))
    mw = nw * 1.5
    d.arc([cx - mw, mouth_cy - nw * 0.1, cx, mouth_cy + nw * 1.0], start=10, end=170,
          fill=CAT_DARK, width=int(size * 0.012))
    d.arc([cx, mouth_cy - nw * 0.1, cx + mw, mouth_cy + nw * 1.0], start=10, end=170,
          fill=CAT_DARK, width=int(size * 0.012))
    # 嘴角微笑影（极淡粉弧，三瓣嘴更立体）
    smile_sh = Image.new("RGBA", (size, size), HOLE)
    ssd = ImageDraw.Draw(smile_sh)
    ssd.arc([cx - mw * 1.25, mouth_cy - nw * 0.2, cx - mw * 0.15, mouth_cy + nw * 1.15],
            start=20, end=160, fill=(232, 165, 175, 55), width=max(1, int(nw * 0.30)))
    ssd.arc([cx + mw * 0.15, mouth_cy - nw * 0.2, cx + mw * 1.25, mouth_cy + nw * 1.15],
            start=20, end=160, fill=(232, 165, 175, 55), width=max(1, int(nw * 0.30)))
    smile_sh = smile_sh.filter(ImageFilter.GaussianBlur(radius=nw * 0.25))
    layer.alpha_composite(smile_sh)
    # 三瓣嘴微笑收尾（两侧嘴角向外上方微翘，表情更温和）
    for sgn in (-1, 1):
        bx = cx + sgn * mw * 0.55
        by = mouth_cy + nw * 0.35
        d.line([(bx, by), (bx + sgn * max(2, int(nw * 0.36)), by - max(2, int(nw * 0.36)))],
               fill=CAT_DARK, width=max(1, int(nw * 0.21)))

    # 胡须（三长三短，白色光泽感：根部加粗 + 轻微上扬弧度 + 三层叠加）
    whisker_rows = [
        (-0.10, 0.32),   # 上：最长
        (-0.02, 0.26),   # 中：中等
        (0.06, 0.20),    # 下：最短
    ]
    whisker_w = int(size * 0.008)
    root_w = max(1, int(whisker_w * 1.4))  # 根部加粗
    for dy, length in whisker_rows:
        yy = face_cy + r * dy
        ang = r * dy * 1.4
        for side in (-1, 1):
            x_start = cx + side * r * 0.62
            x_end = x_start + side * r * length
            # 轻微上扬：终点 y 上移
            y_end = yy + ang - r * 0.03
            # 分段点（根部 35% 更粗，尖部 65% 正常）
            x_mid = x_start + (x_end - x_start) * 0.35
            y_mid = yy + (y_end - yy) * 0.35
            # 底层：淡灰阴影（右下偏移，增加立体感）
            d.line([(x_start + 1, yy + 1), (x_mid + 1, y_mid + 1)],
                   fill=(180, 190, 210, 100), width=root_w)
            d.line([(x_mid + 1, y_mid + 1), (x_end + 1, y_end + 1)],
                   fill=(180, 190, 210, 100), width=whisker_w)
            # 中层：白色主体
            d.line([(x_start, yy), (x_mid, y_mid)],
                   fill=(255, 255, 255, 235), width=root_w)
            d.line([(x_mid, y_mid), (x_end, y_end)],
                   fill=(255, 255, 255, 235), width=whisker_w)
            # 顶层：纯白高光（上方偏移，更细，增加光泽感）
            hl_w = max(1, whisker_w - 1)
            d.line([(x_start, yy - 1), (x_mid, y_mid - 1)],
                   fill=(255, 255, 255, 255), width=max(1, root_w - 1))
            d.line([(x_mid, y_mid - 1), (x_end, y_end - 1)],
                   fill=(255, 255, 255, 255), width=hl_w)

    # ===== 项圈（绿茶色渐变，明亮清新，与冰川蓝猫头形成冷暖对比）=====
    collar_cy = head_cy + r * 0.82
    collar_rx = r * 0.76
    collar_ry = r * 0.30
    # 横向渐变：中间绿茶高光 -> 两侧深绿茶
    collar_grad = Image.new("RGBA", (size, size), HOLE)
    cgd = ImageDraw.Draw(collar_grad)
    for xx in range(int(size)):
        k = abs(xx - cx) / (collar_rx * 1.1)
        k = min(1.0, k)
        cr = int(28 * (1 - k) + 6 * k)
        cg_g = int(200 * (1 - k) + 158 * k)
        cb = int(108 * (1 - k) + 80 * k)
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
                   rx + r * 0.04, ry + r * 0.04], fill=(252, 198, 38, 255))
        d.ellipse([rx - r * 0.02, ry - r * 0.02,
                   rx + r * 0.02, ry + r * 0.02], fill=(255, 230, 120, 255))

    # ===== 金铃铛（金属质感：尖锐高光点 + 底部暗弧）=====
    bell_cx, bell_cy = cx, head_cy + r * 0.99
    bell_r = r * 0.12
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
    # 尖锐高光点（两点式金属感）
    d.ellipse([bell_cx - bell_r * 0.48, bell_cy - bell_r * 0.55,
               bell_cx - bell_r * 0.16, bell_cy - bell_r * 0.23],
              fill=(255, 225, 150, 235))
    d.ellipse([bell_cx + bell_r * 0.08, bell_cy - bell_r * 0.45,
               bell_cx + bell_r * 0.28, bell_cy - bell_r * 0.27],
              fill=(255, 245, 200, 160))
    # 铃铛金属光泽弧（顶部受光弧，增强金属质感）
    d.arc([bell_cx - bell_r * 0.75, bell_cy - bell_r * 0.95,
           bell_cx + bell_r * 0.75, bell_cy + bell_r * 0.55],
          start=200, end=340, fill=(255, 240, 190, 190), width=max(1, int(bell_r * 0.09)))
    # 中缝（随球体弧度微弯）和锤
    d.arc([bell_cx - bell_r * 0.7, bell_cy - bell_r * 0.35,
           bell_cx + bell_r * 0.7, bell_cy + bell_r * 0.35],
          start=0, end=180, fill=CAT_DARK, width=max(1, int(size * 0.005)))
    d.ellipse([bell_cx - bell_r * 0.15, bell_cy + bell_r * 0.05,
               bell_cx + bell_r * 0.15, bell_cy + bell_r * 0.35], fill=CAT_DARK)

    # === 铃铛声波（两侧红色短弧，暗示「叮当响」）===
    for side in (-1, 1):
        for k, rr in enumerate((1.35, 1.70)):
            off = bell_r * rr
            arc = Image.new("RGBA", (size, size), HOLE)
            ImageDraw.Draw(arc).arc(
                [bell_cx - off, bell_cy - off, bell_cx + off, bell_cy + off],
                start=(-60 if side > 0 else 240),
                end=(-30 + k * 15 if side > 0 else 300 - k * 15),
                fill=(255, 185, 70, 160 - k * 70),
                width=max(1, int(bell_r * 0.14)))
            layer.alpha_composite(arc)

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
        # 与 draw_cat 一致：耳根投影到头圆、底边沿头圆弧，去掉外侧小凸角
        if side < 0:
            tip = (cx - r * 1.24, head_cy - r * 1.15)
            outer_raw = (cx - r * 0.96, head_cy - r * 0.45)
            inner_raw = (cx - r * 0.46, head_cy - r * 0.78)
        else:
            tip = (cx + r * 1.24, head_cy - r * 1.15)
            outer_raw = (cx + r * 0.96, head_cy - r * 0.45)
            inner_raw = (cx + r * 0.46, head_cy - r * 0.78)
        def _proj(pt):
            dx = pt[0] - cx; dy = pt[1] - head_cy
            dist = _math.hypot(dx, dy)
            return (cx + dx * r / dist, head_cy + dy * r / dist)
        outer = _proj(outer_raw); inner = _proj(inner_raw)
        a_outer = _math.atan2(outer[1] - head_cy, outer[0] - cx)
        a_inner = _math.atan2(inner[1] - head_cy, inner[0] - cx)
        da = a_inner - a_outer
        while da > _math.pi: da -= 2 * _math.pi
        while da < -_math.pi: da += 2 * _math.pi
        arc = [(cx + r * _math.cos(a_outer + da * (i / 16)),
                head_cy + r * _math.sin(a_outer + da * (i / 16))) for i in range(17)]
        pts = [tip] + arc
        # 只圆耳尖
        V = tip; A = arc[-1]; B = arc[0]
        vlen = _math.hypot(V[0] - A[0], V[1] - A[1]); alen = _math.hypot(V[0] - B[0], V[1] - B[1])
        rad = r * 0.10
        ra = min(rad, vlen * 0.5); rb = min(rad, alen * 0.5)
        P1 = (V[0] + (A[0] - V[0]) * ra / vlen, V[1] + (A[1] - V[1]) * ra / vlen)
        P2 = (V[0] + (B[0] - V[0]) * rb / alen, V[1] + (B[1] - V[1]) * rb / alen)
        rounded = []
        for s in range(13):
            t = s / 12
            rounded.append(((1 - t) * (1 - t) * P1[0] + 2 * (1 - t) * t * V[0] + t * t * P2[0],
                            (1 - t) * (1 - t) * P1[1] + 2 * (1 - t) * t * V[1] + t * t * P2[1]))
        d.polygon(rounded + arc[1:], fill=WHITE)
    d.ellipse([hx, hy, hx + 2 * r, hy + 2 * r], fill=WHITE)
    return layer


def vector_cat(color="#FFFFFF", size_dp=108):
    """猫头剪影的 VectorDrawable（圆头 + 两耳，耳根沿头圆弧），用于 adaptive 前景 / monochrome / 通知。"""
    vp = VIEWPORT
    cx, cy = vp * 0.5, vp * 0.5 + vp * 0.0224
    rr = vp * 0.25

    def _ear_path(side):
        if side < 0:
            tip = (cx - rr * 1.24, cy - rr * 1.15)
            outer_raw = (cx - rr * 0.96, cy - rr * 0.45)
            inner_raw = (cx - rr * 0.46, cy - rr * 0.78)
        else:
            tip = (cx + rr * 1.24, cy - rr * 1.15)
            outer_raw = (cx + rr * 0.96, cy - rr * 0.45)
            inner_raw = (cx + rr * 0.46, cy - rr * 0.78)
        def _proj(pt):
            dx = pt[0] - cx; dy = pt[1] - cy
            dist = _math.hypot(dx, dy)
            return (cx + dx * rr / dist, cy + dy * rr / dist)
        outer = _proj(outer_raw); inner = _proj(inner_raw)
        # tip -> outer -> 沿头圆弧 -> inner -> 回 tip
        return (f"M{_p(tip[0])},{_p(tip[1])}"
                f"L{_p(outer[0])},{_p(outer[1])}"
                f"A{_p(rr)},{_p(rr)} 0 0,1 {_p(inner[0])},{_p(inner[1])}z")

    le = _ear_path(-1)
    re_ = _ear_path(1)
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


def _fit_cat(canvas_size, zoom):
    """在 canvas_size 方画布上绘制猫，按实体轮廓(alpha>=CAT_KEEP_ALPHA)裁剪、剔除会形成
    硬边的弱光晕/弱投影，再整体放大 zoom（相对原始 draw_cat 同画布下的实体占比）。
    返回缩放后的实体猫 RGBA（透明底），由调用方居中贴入目标画布。"""
    mark = draw_cat(canvas_size)
    keep = mark.split()[3].point(lambda v: v if v >= CAT_KEEP_ALPHA else 0)
    bbox = keep.getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), HOLE)
    trim = mark.crop(bbox)
    trim.putalpha(trim.split()[3].point(lambda v: v if v >= CAT_KEEP_ALPHA else 0))
    tw, th = trim.size
    nw, nh = max(1, int(round(tw * zoom))), max(1, int(round(th * zoom)))
    return trim.resize((nw, nh), Image.LANCZOS)


def _exact_centered(tile, W, H, thr=CAT_KEEP_ALPHA):
    """把透明底 tile 的实体内容(alpha>=thr)严格居中到 W×H，返回新 RGBA。
    整数像素下若画布与实体宽/高奇偶不一致则无法均分，此时对 tile 做 1px 微缩放
    （视觉不可察）对齐奇偶，再贴入，使左右、上下边距完全相等、中心偏移为 0。"""
    def _bbox(im):
        return im.split()[3].point(lambda v: v if v >= thr else 0).getbbox()
    t = tile
    for _ in range(4):
        b = _bbox(t)
        if b is None:
            return Image.new("RGBA", (W, H), HOLE)
        bw, bh = b[2] - b[0], b[3] - b[1]
        if (W - bw) % 2 == 0 and (H - bh) % 2 == 0:
            break
        if (W - bw) % 2:
            t = t.resize((t.width + 1, t.height), Image.LANCZOS)
        if (H - bh) % 2:
            t = t.resize((t.width, t.height + 1), Image.LANCZOS)
    b = _bbox(t)
    bw, bh = b[2] - b[0], b[3] - b[1]
    out = Image.new("RGBA", (W, H), HOLE)
    out.alpha_composite(t, ((W - bw) // 2 - b[0], (H - bh) // 2 - b[1]))
    return out


def _cat_square_tile(size, zoom):
    """方图标用：超采样渲染实体猫并下采样到 size（透明底，尚未严格居中）。"""
    big = size * SS
    cat = _fit_cat(big, zoom)
    layer = Image.new("RGBA", (big, big), HOLE)
    layer.alpha_composite(cat, ((big - cat.width) // 2, (big - cat.height) // 2))
    return layer.resize((size, size), Image.LANCZOS)


# --- 形状边界的“内部间隙”解析函数（像素，内部为正）---
def _dist_circle(x, y, R):
    return R - (x * x + y * y) ** 0.5


def _dist_rect(x, y, a, b):
    return min(a - abs(x), b - abs(y))


def _dist_rounded(x, y, a, b, cr):
    ax = max(abs(x) - (a - cr), 0)
    ay = max(abs(y) - (b - cr), 0)
    return min(a - abs(x), b - abs(y), cr - (ax * ax + ay * ay) ** 0.5)


def _place_balanced(tile, W, H, distf, thr=CAT_KEEP_ALPHA):
    """把透明底实体猫(alpha>=thr)贴入 W×H 画布，并在垂直方向做“等间隙”平衡：
    猫的最上点是两只耳尖（同时最宽，落在斜上方位），最下点是铃铛（落在正下方）。
    纯 bbox 居中会让耳尖几乎贴到圆形边、而铃铛下方空一大片（视觉偏上）。这里搜索一个
    整数纵向位移，使上方(耳尖)与下方(铃铛)到形状边界的最小间隙相等且最大；水平仍居中。
    """
    b = tile.split()[3].point(lambda v: v if v >= thr else 0).getbbox()
    if b is None:
        return Image.new("RGBA", (W, H), HOLE)
    x0, y0, x1, y1 = b
    # 极值点（tile 局部，取像素中心 +0.5）：两个耳尖 + 底部铃铛
    pts_top = [(x0 + 0.5, y0 + 0.5), (x1 - 0.5, y0 + 0.5)]
    pts_bot = [((x0 + x1) / 2.0, y1 - 0.5)]
    cx_t, cy_t = tile.width / 2.0, tile.height / 2.0

    def clearances(oy):
        def cv(px, py):
            return distf(px - cx_t, py - cy_t + oy)
        dt = min(cv(*p) for p in pts_top)
        db = min(cv(*p) for p in pts_bot)
        return dt, db

    best = None
    for oy in range(-H // 4, H // 4 + 1):
        dt, db = clearances(oy)
        if dt <= 0 or db <= 0:
            continue
        score = min(dt, db)
        bal = abs(dt - db)
        cand = (score, -bal, -abs(oy))
        if best is None or cand > best[0]:
            best = (cand, oy)
    oy_use = best[1] if best else 0
    out = Image.new("RGBA", (W, H), HOLE)
    out.alpha_composite(tile, ((W - tile.width) // 2, (H - tile.height) // 2 + oy_use))
    return out


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

    if style == "cat":
        # 背景先在 big 处裁切（边缘最干净）再降到 size
        if shape != "square":
            img.putalpha(_mask(big, shape, radius_ratio))
        img = img.resize((size, size), Image.LANCZOS)
        # 猫：big 超采样渲染→降到 size→按形状边界做上下等间隙平衡（耳尖/铃铛到边距离一致）
        cat = _fit_cat(big, CAT_ZOOM)
        layer = Image.new("RGBA", (big, big), HOLE)
        layer.alpha_composite(cat, ((big - cat.width) // 2, (big - cat.height) // 2))
        catf = layer.resize((size, size), Image.LANCZOS)
        if shape == "circle":
            distf = lambda x, y: _dist_circle(x, y, size / 2.0)
        elif shape == "rounded":
            distf = lambda x, y: _dist_rounded(x, y, size / 2.0, size / 2.0,
                                               radius_ratio * size)
        else:
            distf = lambda x, y: _dist_rect(x, y, size / 2.0, size / 2.0)
        img.alpha_composite(_place_balanced(catf, size, size, distf))
        return img

    # 非 cat 风格：沿用原 big 合成→裁切→降采样路径
    if badge:
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
        # 背景降到最终尺寸；猫放大后在长方形 banner 内做上下等间隙平衡、水平居中（完整不裁切）
        img = img.resize((w, h), Image.LANCZOS)
        cat = _fit_cat(int(bh * 0.95), CAT_ZOOM)
        layer = Image.new("RGBA", (bw, bh), HOLE)
        layer.alpha_composite(cat, ((bw - cat.width) // 2, (bh - cat.height) // 2))
        catf = layer.resize((w, h), Image.LANCZOS)
        distf = lambda x, y: _dist_rect(x, y, w / 2.0, h / 2.0)
        img.alpha_composite(_place_balanced(catf, w, h, distf))
        return img

    mark_box = int(bh * 0.62)
    mark = draw_wordmark(mark_box, 0.92, style=style)
    img.alpha_composite(mark, (int(bw * 0.075), int((bh - mark_box) / 2)))

    return img.resize((w, h), Image.LANCZOS)
def render_notification(size, style="3d"):
    """通知栏小图标：纯白扁平轮廓（系统强制要求纯白透明，必须保持扁平）。"""
    if style == "cat":
        sil = draw_cat_silhouette(size * SS).resize((size, size), Image.LANCZOS)
        return _exact_centered(sil, size, size)
    # 注意：draw_wordmark 在 fill=FILL_NOTIFY 时会强制输出纯白无阴影，style 参数不影响结果
    return draw_wordmark(size * SS, FILL_NOTIFY, style=style).resize((size, size),
                          Image.LANCZOS)
def render_cat_foreground(size):
    """自适应图标前景：完整彩色猫（透明底），超采样后缩放至安全区内。

    自适应图标 108dp 中系统只保证中心约 72dp 可见（半径 ≈ size/3）。
    基准画布 inner=0.62*size 再随 CAT_ZOOM 放大（=0.719*size）：实体猫直径约 0.436*size，
    耳尖(实体 bbox 上角)到中心半径 ≈0.31*size < 0.333*size，圆形/水滴/方形 mask 都不裁切。
    弱光晕已剔除，SS=5 超采样再 LANCZOS 缩小，所有密度下边缘锐利无锯齿。
    """
    inner = int(size * 0.62 * CAT_ZOOM)
    big = inner * SS
    cat_big = _fit_cat(big, 1.0)
    cw = max(1, int(round(cat_big.width / SS)))
    ch = max(1, int(round(cat_big.height / SS)))
    cat = cat_big.resize((cw, ch), Image.LANCZOS)
    # 在 72dp 安全圆（R=size/3）内做上下等间隙平衡，耳尖/铃铛到安全圆边距离一致、不裁切
    distf = lambda x, y: _dist_circle(x, y, size / 3.0)
    return _place_balanced(cat, size, size, distf)
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
                before_vb = content
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
                if content != before_vb:
                    changed_any = True
                    print("[OK] app/build.gradle: 已补全 buildFeatures { viewBinding true }")
                else:
                    print("[WARN] app/build.gradle: 未找到 android{} 或 buildFeatures{} 块，viewBinding 补全失败，请人工检查")

        if content != original:
            # 写回前花括号平衡校验：viewBinding 插入若错位会破坏 android{} 块
            if not _brace_balance(filename, content):
                print(f"[FATAL] {filename}: 因花括号不平衡，放弃写回（保留原文件，避免 Gradle 解析失败）")
                continue
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
    # 必须在 parse 前注册命名空间，否则写回时 android: 前缀会变成 ns0:
    ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
    ET.register_namespace("tools", "http://schemas.android.com/tools")
    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
    except ET.ParseError:
        return False
    changed = False
    application = root.find("application")
    if application is not None:
        label = application.get(_ANDROID_NS + "label")
        if label and not label.startswith("@") and label != app_name:
            application.set(_ANDROID_NS + "label", app_name)
            changed = True
            print(f'[OK] AndroidManifest.xml: android:label "{label}" -> "{app_name}"')
    if changed:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    return changed


# ---------------------------------------------------------------- 5b. TV banner 接线（当贝桌面长方形）
def _patch_manifest_banner(manifest_path, banner_ref, TOOLS_NS, ANDROID_URI):
    """对单个 AndroidManifest.xml 做 banner 接线：改 banner + 加 tools:replace。"""
    if not os.path.exists(manifest_path):
        return False
    ET.register_namespace("android", ANDROID_URI)
    ET.register_namespace("tools", TOOLS_NS)
    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
    except ET.ParseError:
        print(f"[SKIP] {os.path.relpath(manifest_path, REPO_ROOT)} 解析失败")
        return False

    TOOLS_REPLACE_KEY = f"{{{TOOLS_NS}}}replace"
    changed = False
    application = root.find("application")
    if application is not None:
        cur = application.get(_ANDROID_NS + "banner")
        if cur != banner_ref:
            application.set(_ANDROID_NS + "banner", banner_ref)
            changed = True
            print(f"[OK] {os.path.relpath(manifest_path, REPO_ROOT)}: android:banner {cur or '未设置'} -> {banner_ref}")
        # tools:replace 只能列出本 manifest <application> 实际赋值的属性，
        # 否则 AGP 报 "tools:replace specified ... but no new value specified"。
        # 检查哪些 android:* 属性实际存在，只把它们加入 tools:replace。
        present = []
        for attr in ("banner", "icon", "roundIcon", "label"):
            if application.get(_ANDROID_NS + attr) is not None:
                present.append(f"android:{attr}")
        if present:
            replace_attr = application.get(TOOLS_REPLACE_KEY) or ""
            have = set(x.strip() for x in replace_attr.split(","))
            miss = [x for x in present if x not in have]
            if miss:
                new_val = ",".join([x for x in (replace_attr.split(",") if replace_attr else []) if x.strip()] + miss)
                application.set(TOOLS_REPLACE_KEY, new_val)
                changed = True
                print(f"[OK] {os.path.relpath(manifest_path, REPO_ROOT)}: tools:replace = {new_val}")
    if changed:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    return changed


def modify_manifest_banner(config):
    """强制 AndroidManifest 的 android:banner 指向 320x180 长方形 PNG drawable。

    同时处理 main 和 leanback flavor 两个 manifest（leanback flavor 自己也声明了
    @mipmap/ic_banner，不改会导致 leanback 变体合并冲突）。
    """
    banner_ref = "@drawable/ic_banner"
    TOOLS_NS = "http://schemas.android.com/tools"
    ANDROID_URI = "http://schemas.android.com/apk/res/android"

    # 需要处理的 manifest 列表：main + leanback flavor
    targets = [
        os.path.join(REPO_ROOT, "app", "src", "main", "AndroidManifest.xml"),
        os.path.join(REPO_ROOT, "app", "src", "leanback", "AndroidManifest.xml"),
    ]
    any_changed = False
    for mp in targets:
        if os.path.exists(mp):
            any_changed = _patch_manifest_banner(mp, banner_ref, TOOLS_NS, ANDROID_URI) or any_changed

    # 把 320x180 banner PNG 复制到主资源目录：
    #  - drawable-xhdpi（Android TV 官方推荐位置，320x180 对应 xhdpi）
    #  - drawable-nodpi（兜底）
    src = os.path.join(REPO_ROOT, "app", "src", "leanback", "res", "drawable", "ic_banner.png")
    copied_any = False
    if os.path.exists(src):
        for sub in ("drawable-xhdpi", "drawable-nodpi"):
            dst = os.path.join(REPO_ROOT, "app", "src", "main", "res", sub, "ic_banner.png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            copied_any = True
            print(f"[OK] banner PNG -> {os.path.relpath(dst, REPO_ROOT)}（320x180）")
    else:
        print(f"[WARN] 未找到 leanback banner 源文件: {os.path.relpath(src, REPO_ROOT)}，请先跑图标生成步骤")
    # 关键校验：manifest 已把 android:banner 指向 @drawable/ic_banner，
    # 必须保证至少有一个 ic_banner.png 资源存在，否则 AAPT 合并直接报 "resource not found"。
    banner_glob = glob.glob(os.path.join(REPO_ROOT, "app", "src", "main", "res",
                                        "drawable*", "ic_banner.png"))
    if not banner_glob:
        print("[FATAL] manifest 指向 @drawable/ic_banner，但 main 资源中找不到任何 ic_banner.png！"
              " 这会导致 AAPT resource-not-found 构建失败。请先让图标生成步骤产出 banner。")
        any_changed = False
    else:
        print(f"[SANITY] @drawable/ic_banner 资源存在：{os.path.relpath(banner_glob[0], REPO_ROOT)}")
    return any_changed


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
            # 写回前健全性校验（这些是 .java 文件，防止替换逻辑破坏语法）
            _java_sanity_check(content, rel_path)
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
            # 写回前健全性校验（这些是 .java 文件，防止替换逻辑破坏语法）
            _java_sanity_check(content, rel_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] {rel_path}: 更新链接已替换（GitHub={github_repo or '未改'} / CNB={cnb_slug or '未改'}）")
        else:
            print(f"[SKIP] {rel_path}: 已是目标值")
    return changed_any


# ---------------------------------------------------------------- 通用：Java 代码生成后健全性校验
def _java_sanity_check(content, label, require_patterns=None, forbid_patterns=None):
    '''
    在写回 .java 文件前调用，检查字符串拼接生成的 Java 代码是否存在明显语法问题。
    不通过则抛异常，使脚本以非零码退出，避免错误流入 Gradle 编译阶段（1~2 分钟后才报错）。
    检查项：
      1) 圆括号/花括号/方括号平衡（跳过字符串/字符字面量内的括号）
      2) 生成代码中使用的常见类型是否有对应 import（ArrayList, List, Map, HashMap 等）
      3) 含方法调用的非空行是否以 ; 或 { 或 } 结尾（排除注释和控制结构）
      4) require_patterns：每个正则必须能在代码中找到（生成代码块完整性校验）
      5) forbid_patterns：每个正则不得在代码中出现（残留/重复块校验）
    '''
    errors = []

    # 1) 括号平衡（忽略字符串字面量中的括号——简单处理：逐字符扫描，遇到 " 切换字符串状态）
    in_str = False
    in_char = False
    escape = False
    depth = {'()': 0, '{}': 0, '[]': 0}
    for ch in content:
        if escape:
            escape = False
            continue
        if ch == '\\' and (in_str or in_char):
            escape = True
            continue
        if ch == '"' and not in_char:
            in_str = not in_str
            continue
        if ch == "'" and not in_str:
            in_char = not in_char
            continue
        if in_str or in_char:
            continue
        if ch == '(':
            depth['()'] += 1
        elif ch == ')':
            depth['()'] -= 1
        elif ch == '{':
            depth['{}'] += 1
        elif ch == '}':
            depth['{}'] -= 1
        elif ch == '[':
            depth['[]'] += 1
        elif ch == ']':
            depth['[]'] -= 1
        for k, v in depth.items():
            if v < 0:
                errors.append(f"括号 {k} 出现未匹配的闭合（深度={v}）")
                depth[k] = 0  # 重置避免重复报错
    for k, v in depth.items():
        if v != 0:
            errors.append(f"括号 {k} 不平衡，剩余深度={v}")

    # 2) 常见类型 import 检查（仅当代码中确实使用了该类型时）
    _type_import_map = {
        'ArrayList': 'import java.util.ArrayList;',
        'List': 'import java.util.List;',
        'Map': 'import java.util.Map;',
        'HashMap': 'import java.util.HashMap;',
        'Set': 'import java.util.Set;',
        'HashSet': 'import java.util.HashSet;',
        'Collections': 'import java.util.Collections;',
        'Objects': 'import java.util.Objects;',
        'Optional': 'import java.util.Optional;',
    }
    # 去掉注释和字符串后再检查类型使用，避免误报
    _code_only = re.sub(r'//.*', '', content)
    _code_only = re.sub(r'/\*.*?\*/', '', _code_only, flags=re.DOTALL)
    for _type, _import in _type_import_map.items():
        # 匹配作为类型使用的情况（前面是非字母数字，后面是 < 或空格或 .）
        if re.search(r'(?<![A-Za-z0-9_])' + re.escape(_type) + r'[<\s.]', _code_only):
            if _import not in content:
                errors.append(f"使用了 {_type} 但缺少 {_import}")

    # 3) 语句结尾检查：含方法调用( 的非空行，若不是注释/控制结构/注解，应以 ; { } 结尾
    #    关键：用跨行括号深度追踪识别跨行表达式（assertEquals(\n  a,\n  b\n);）
    #    行末深度 > 0 说明在跨行方法调用/参数列表内，跳过收尾检查。
    _lines = content.split('\n')
    _line_end_depth = [0] * len(_lines)
    _d = 0
    _in_str = False
    _in_char = False
    _in_line_comment = False
    _in_block_comment = False
    _escape = False
    for _li, _raw_line in enumerate(_lines):
        _in_line_comment = False
        _i = 0
        while _i < len(_raw_line):
            _ch = _raw_line[_i]
            _nxt = _raw_line[_i + 1] if _i + 1 < len(_raw_line) else ''
            if _escape:
                _escape = False
                _i += 1
                continue
            if _in_line_comment:
                break
            if _in_block_comment:
                if _ch == '*' and _nxt == '/':
                    _in_block_comment = False
                    _i += 2
                    continue
                _i += 1
                continue
            if _ch == '\\' and (_in_str or _in_char):
                _escape = True
                _i += 1
                continue
            if _ch == '/' and _nxt == '/':
                _in_line_comment = True
                break
            if _ch == '/' and _nxt == '*':
                _in_block_comment = True
                _i += 2
                continue
            if _ch == '"' and not _in_char:
                _in_str = not _in_str
                _i += 1
                continue
            if _ch == "'" and not _in_str:
                _in_char = not _in_char
                _i += 1
                continue
            if _in_str or _in_char:
                _i += 1
                continue
            # 仅追踪圆括号 () 深度——用于识别跨行方法调用/参数列表
            # 花括号 {}（类/方法体）和方括号 [] 不参与，否则方法内所有行深度都 >0
            if _ch == '(':
                _d += 1
            elif _ch == ')':
                _d -= 1
            _i += 1
        _line_end_depth[_li] = _d

    for _lineno, _line in enumerate(_lines, 1):
        stripped = _line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
            continue
        if stripped.startswith('@'):  # 注解
            continue
        # 控制结构行（if/for/while/else/switch/case/try/catch/finally/do/synchronized）
        if re.match(r'^(if|for|while|else|switch|case|try|catch|finally|do|synchronized)\b', stripped):
            continue
        # 类/方法/接口声明行
        if re.match(r'^(public|private|protected|static|final|abstract|class|interface|enum|void|return)\b', stripped) and stripped.endswith('{'):
            continue
        # 跨行表达式：行末括号深度 > 0，说明在跨行方法调用/参数列表内（如 assertEquals(\n  a,\n  b\n);）
        if _line_end_depth[_lineno - 1] > 0:
            continue
        # 跨行表达式/链式调用续行：以运算符或 . 开头（如 || foo()、.bar()、+ baz）
        if re.match(r'^(\|\||&&|\+|-|\*|/|%|\?|:|==|!=|<=|>=|<|>|instanceof|\.)', stripped):
            continue
        # 待续行：以运算符结尾且无分号（如 foo() ||、bar() +）
        if re.search(r'(\|\||&&|\+|-|\*|/|%|\?|:)$', stripped) and not stripped.endswith(';'):
            continue
        # return 开头但不以 ; 结尾（跨行 return 第一行，如 return foo()）
        if stripped.startswith('return ') and not stripped.endswith(';'):
            continue
        # 以 ( 结尾：跨行方法调用/构造的开始（深度追踪已覆盖，此处为双重保险）
        if stripped.endswith('('):
            continue
        # 只检查含 '(' 且不含 '{' 开头的行（可能是方法调用语句）
        if '(' in stripped and not stripped.endswith(';') and not stripped.endswith('{') and not stripped.endswith('}') and not stripped.endswith(','):
            # 排除 package/import 行
            if not stripped.startswith('package ') and not stripped.startswith('import '):
                errors.append(f"第{_lineno}行语句可能未正确结尾（期望 ; 或 {{/}}）：{stripped[:80]}")

    # 4) 必现模式校验（生成代码块完整性）
    for _pat in (require_patterns or []):
        if not re.search(_pat, content):
            errors.append(f"必须包含的模式缺失：{_pat}")

    # 5) 禁止模式校验（残留/重复块）
    for _pat in (forbid_patterns or []):
        if re.search(_pat, content):
            errors.append(f"禁止出现的模式仍存在：{_pat}")

    if errors:
        raise RuntimeError(
            f"[FATAL] Java 健全性校验未通过 ({label})：\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n  请检查 local_customize.py 中的字符串拼接逻辑，修复后重新运行。"
        )
    print(f"[SANITY] {label}: Java 健全性校验通过（括号平衡 + import 完整 + 语句收尾 + 模式校验）")


def _yaml_looks_ok(label, content):
    """写回 workflow YAML 前做解析校验；pyyaml 不可用时降级为关键片段存在性检查。

    GitHub Actions 对 YAML 缩进极其敏感，行级手术一旦破坏缩进，
    CI 会在「开始执行」阶段直接报 "Invalid workflow file" 而不是编译错误。
    这里在本地提前挡住。
    """
    if not content:
        return False
    if _YAML_OK:
        try:
            _yaml.safe_load(content)
            print(f"[SANITY] {label}: YAML 解析通过（缩进/结构未破坏）")
            return True
        except Exception as e:
            print(f"[FATAL] {label}: YAML 改完后无法解析 —— {e}")
            print("        这会导致 GitHub Actions 直接报 Invalid workflow file，请检查行级手术逻辑。")
            return False
    # 降级：必须有 on/jobs 顶层键（未装 pyyaml 时的粗检）
    if not (("on:" in content or "name:" in content) and "jobs:" in content):
        print(f"[WARN] {label}: 未发现 on:/jobs: 结构，疑似 YAML 被破坏（未装 pyyaml，仅粗检）")
        return False
    return True


def _brace_balance(label, content):
    """Groovy build.gradle 花括号平衡粗检（写回前），防止行级插入破坏 android{} 块。"""
    depth = 0
    in_str = False
    esc = False
    min_d = 0
    for ch in content:
        if esc:
            esc = False; continue
        if ch == "\\" and in_str:
            esc = True; continue
        if ch == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            min_d = min(min_d, depth)
    if depth != 0 or min_d < 0:
        print(f"[FATAL] {label}: 花括号不平衡（depth={depth}, min={min_d}），写回会破坏 Gradle 脚本！")
        return False
    print(f"[SANITY] {label}: 花括号平衡（depth 最终为 0）")
    return True


# ---------------------------------------------------------------- 8. 更新顺序：CNB 优先
def modify_update_order(config):
    '''
    增强更新机制（Updater.java + Github.java），对齐线上真实代码结构，三处修改：
      1) getUpdate()：先读 CNB raw manifest（https://cnb.cool/<slug>/-/git/raw/main/apk/xx.json，
         由 sync-cnb-release.sh 在 sync_cnb 时推送），失败才回退 GitHub API。
      2) parseDownloads()：manifest 的 apk 字段为 CNB 直链（sync-cnb-release.sh 已改写）时，
         APK 下载地址优先用 CNB Release 直链 https://cnb.cool/<slug>/-/releases/download/<tag>/xx.apk，
         国内直连 CNB、绕开 GitHub。
      3) getRoutes()：线上已具备 CNB 第一路由 + GitHub/OCI 兜底形态，仅幂等校验。
    约束：UpdateRoutePlanner 本身不动（签名/逻辑不变），GitHub 兜底链路完整保留；
         未勾选 sync_cnb 发布时 CNB 无 manifest，自动回退 GitHub，不影响现有更新。
    健壮性：用方法体正则精确匹配（不依赖整文件子串），写回后重新读盘验证，
           --force 模式跳过幂等判断强制重写。
    '''
    changed_any = False
    cnb_slug = str(config.get("CNB_REPO_SLUG", "")).strip()

    # ---------- A. Updater.java ----------
    rel_path = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "Updater.java")
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[SKIP] {rel_path} 不存在（继续执行 Github.java 修改）")
    else:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        # 仅在检测到历史污染字符 \u0001 时才清洗，避免静默修改合法文件
        if "\u0001" in content:
            print(f"[WARN] {rel_path}: 检测到控制字符 \\u0001，执行清洗")
            content = "".join(ch for ch in content if ch >= " " or ch in "\n\r\t")

        # A1. getUpdate()：逐行扫描 + 大括号深度定位方法体（不依赖精确缩进/正则，兼容任意格式）
        lines = content.split('\n')
        gu_start = None
        for i, line in enumerate(lines):
            if 'private Update getUpdate(String channel)' in line:
                gu_start = i
                break
        if gu_start is not None:
            depth = 0
            gu_end = None
            for i in range(gu_start, len(lines)):
                depth += lines[i].count('{') - lines[i].count('}')
                if depth == 0 and i > gu_start:
                    gu_end = i
                    break
            if gu_end is not None:
                gu_body = '\n'.join(lines[gu_start:gu_end+1])
                # 幂等判断：只有当 getCnbMirrorAsset 在方法中排在 getChannelAsset 之前
                # （即 CNB 是第一个被检查的源）才认为是 CNB 优先。
                # 旧代码 beta 分支里也有 getCnbMirrorAsset，但排在 GitHub 之后，必须替换。
                pos_cnb = gu_body.find('getCnbMirrorAsset')
                pos_gh  = gu_body.find('getChannelAsset')
                already_cnb_first = (pos_cnb >= 0 and (pos_gh < 0 or pos_cnb < pos_gh))
                if already_cnb_first and not FORCE_MODE:
                    print(f"[SKIP] {rel_path}: getUpdate() 已是 CNB 优先")
                else:
                    _before = content
                    indent = lines[gu_start][:len(lines[gu_start]) - len(lines[gu_start].lstrip())]
                    new_method = [
                        f'{indent}private Update getUpdate(String channel) {{',
                        f'{indent}    String manifestName = getManifestName(channel);',
                        f'{indent}    Update cnb = readUpdate(channel, Github.getCnbMirrorAsset(manifestName), SOURCE_CNB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (cnb.hasManifest()) return cnb;',
                        f'{indent}    Update update = readUpdate(channel, Github.getChannelAsset(manifestName), SOURCE_GITHUB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (update.hasManifest()) return update;',
                        f'{indent}    if (Update.CHANNEL_BETA.equals(channel)) return getGithubBetaUpdate(channel);',
                        f'{indent}    update = readUpdate(channel, Github.getGithubLatestAsset(manifestName), SOURCE_GITHUB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (update.hasManifest()) return update;',
                        f'{indent}    return getGithubStableUpdate(channel);',
                        f'{indent}}}',
                    ]
                    lines = lines[:gu_start] + new_method + lines[gu_end+1:]
                    content = '\n'.join(lines)
                    if content != _before:
                        _missing = [p for p in
                                    ['private Update getUpdate(String channel)',
                                     'Github.getCnbMirrorAsset(manifestName)',
                                     'Github.getChannelAsset(manifestName)',
                                     'Github.getGithubLatestAsset(manifestName)',
                                     'getGithubBetaUpdate(channel)',
                                     'getGithubStableUpdate(channel)']
                                    if p not in content]
                        if _missing:
                            raise RuntimeError(
                                f"[FATAL] {rel_path}: getUpdate() 注入后模式校验失败，缺失：{_missing}。")
                        print(f"[OK] {rel_path}: getUpdate() 改为 CNB 优先 → GitHub update-channel → GitHub API 兜底")
                        changed_any = True
                    else:
                        print(f"[SKIP] {rel_path}: getUpdate() 已是 CNB 优先（--force 下形态不变）")
            else:
                print(f"[WARN] {rel_path}: getUpdate() 方法未找到闭合大括号，请人工检查")
        else:
            print(f"[WARN] {rel_path}: 未找到 getUpdate() 方法，请人工检查 Updater.java 结构")

        # A2. parseDownloads()：逐行扫描定位 update.apkUrl 行，在其后插入 apkField 判断
        already_apkfield = "String apkField = update.apk;" in content
        if already_apkfield and not FORCE_MODE:
            print(f"[SKIP] {rel_path}: parseDownloads() 已是 CNB 直链优先")
        else:
            # --force 且已有 apkField 时，先移除旧块（避免重复插入导致编译错误）
            if already_apkfield and FORCE_MODE:
                apf_start = None
                for i, line in enumerate(lines):
                    if 'String apkField = update.apk;' in line:
                        apf_start = i
                        break
                if apf_start is not None:
                    depth = 0
                    apf_end = apf_start
                    for i in range(apf_start, len(lines)):
                        if 'if (' in lines[i] or 'if(' in lines[i]:
                            depth += 1
                        if '}' in lines[i]:
                            depth -= 1
                            if depth <= 0:
                                apf_end = i
                                break
                    lines = lines[:apf_start] + lines[apf_end+1:]
                    content = '\n'.join(lines)
            pd_idx = None
            for i, line in enumerate(lines):
                if 'update.apkUrl = update.githubUrl;' in line:
                    pd_idx = i
                    break
            if pd_idx is not None:
                _before = content
                indent = lines[pd_idx][:len(lines[pd_idx]) - len(lines[pd_idx].lstrip())]
                insertion = [
                    f'{indent}String apkField = update.apk;',
                    f'{indent}if (apkField != null && apkField.startsWith("https://cnb.cool/")) {{',
                    f'{indent}    update.apkUrl = apkField;',
                    f'{indent}}}',
                ]
                lines = lines[:pd_idx+1] + insertion + lines[pd_idx+1:]
                content = '\n'.join(lines)
                if content != _before:
                    # 注入后模式校验：apkField 声明 + CNB 直链判断必须成对出现
                    _missing = [p for p in
                                ['String apkField = update.apk;',
                                 'apkField != null && apkField.startsWith("https://cnb.cool/")',
                                 'update.apkUrl = apkField;']
                                if p not in content]
                    if _missing:
                        raise RuntimeError(
                            f"[FATAL] {rel_path}: parseDownloads() 注入后模式校验失败，缺失：{_missing}。"
                            f"请检查 Updater.java 上游结构或本脚本 A2 逻辑。")
                    print(f"[OK] {rel_path}: parseDownloads() APK 下载改为 CNB Release 直链优先（GitHub 兜底）")
                    changed_any = True
                else:
                    print(f"[SKIP] {rel_path}: parseDownloads() 已是 CNB 直链优先（--force 下形态不变）")
            elif already_apkfield and FORCE_MODE:
                print(f"[SKIP] {rel_path}: parseDownloads() 已是 CNB 直链优先（--force 下形态不变）")
            else:
                print(f"[WARN] {rel_path}: 未找到 update.apkUrl = update.githubUrl; 行，请人工检查")

        # A3. getRoutes()：逐行扫描定位，自动注入 CNB 第一路由判断
        already_cnb_route = 'cnbUrl.startsWith("https://cnb.cool/")' in content
        if already_cnb_route and not FORCE_MODE:
            print(f"[SKIP] {rel_path}: getRoutes() 已具备 CNB 第一路由（GitHub/OCI 兜底）")
        else:
            gr_idx = None
            gr_mode = None  # 'addAll' 或 'return_plan'
            for i, line in enumerate(lines):
                if 'routes.addAll(UpdateRoutePlanner.plan' in line:
                    for j in range(max(0, i-30), i):
                        if 'getRoutes' in lines[j]:
                            gr_idx = i
                            gr_mode = 'addAll'
                            break
                    if gr_idx is not None:
                        break
            if gr_idx is None:
                for i, line in enumerate(lines):
                    if 'return UpdateRoutePlanner.plan' in line:
                        for j in range(max(0, i-30), i):
                            if 'getRoutes' in lines[j]:
                                gr_idx = i
                                gr_mode = 'return_plan'
                                break
                        if gr_idx is not None:
                            break
            if gr_idx is None:
                for i, line in enumerate(lines):
                    if 'return routes;' in line:
                        for j in range(max(0, i-30), i):
                            if 'getRoutes' in lines[j]:
                                gr_idx = i
                                gr_mode = 'return_routes'
                                break
                        if gr_idx is not None:
                            break
            if gr_idx is not None:
                # --force 且已有 cnbUrl 块时，先移除旧块（避免重复插入）
                if already_cnb_route and FORCE_MODE:
                    cnb_start = None
                    for i, line in enumerate(lines):
                        if 'String cnbUrl = update.apkUrl;' in line:
                            cnb_start = i
                            break
                    if cnb_start is not None:
                        depth = 0
                        cnb_end = cnb_start
                        for i in range(cnb_start, len(lines)):
                            if 'if (' in lines[i] or 'if(' in lines[i]:
                                depth += 1
                            if '}' in lines[i]:
                                depth -= 1
                                if depth <= 0:
                                    cnb_end = i
                                    break
                        lines = lines[:cnb_start] + lines[cnb_end+1:]
                        content = '\n'.join(lines)
                        # 移除后重新定位 gr_idx（行号可能变了）
                        gr_idx = None
                        for i, line in enumerate(lines):
                            if 'routes.addAll(UpdateRoutePlanner.plan' in line:
                                for j in range(max(0, i-30), i):
                                    if 'getRoutes' in lines[j]:
                                        gr_idx = i
                                        break
                                if gr_idx is not None:
                                    break
                        if gr_idx is None:
                            for i, line in enumerate(lines):
                                if 'return routes;' in line:
                                    for j in range(max(0, i-30), i):
                                        if 'getRoutes' in lines[j]:
                                            gr_idx = i
                                            break
                                    if gr_idx is not None:
                                        break
                _before = content
                indent = lines[gr_idx][:len(lines[gr_idx]) - len(lines[gr_idx].lstrip())]
                _skip_reason = None
                if gr_mode == 'return_plan':
                    # 格式：return UpdateRoutePlanner.plan(..., update.githubUrl, ...);
                    # 替换为：创建列表 + CNB 第一路由 + addAll(用 update.apkUrl) + return routes
                    # 注意：return 语句可能跨行（参数折行），先合并成完整语句再转换，
                    #       避免只取首行导致生成括号残缺/参数丢失的坏代码（历史教训）
                    stmt = lines[gr_idx]
                    stmt_end = gr_idx
                    while stmt_end < len(lines) - 1 and not stmt.rstrip().endswith(';'):
                        stmt_end += 1
                        stmt += ' ' + lines[stmt_end].strip()
                    if not stmt.rstrip().endswith(';'):
                        _skip_reason = (f"return UpdateRoutePlanner.plan 语句扫描到文件末尾仍未以分号闭合"
                                        f"（首行：{lines[gr_idx].strip()[:60]}）")
                    else:
                        new_line = stmt.replace('update.githubUrl', 'update.apkUrl')
                        new_line = new_line.replace('return UpdateRoutePlanner.plan',
                                                    'routes.addAll(UpdateRoutePlanner.plan')
                        # addAll( 比原 return 多一层左括号，需补右括号闭合 addAll，并保留语句分号
                        new_line = new_line.rstrip()[:-1] + ');'
                        replacement = [
                            f'{indent}List<UpdateTarget> routes = new ArrayList<>();',
                            f'{indent}String cnbUrl = update.apkUrl;',
                            f'{indent}if (cnbUrl != null && cnbUrl.startsWith("https://cnb.cool/")) {{',
                            f'{indent}    routes.add(UpdateTarget.github(cnbUrl));',
                            f'{indent}}}',
                            f'{indent}{new_line}',
                            f'{indent}return routes;',
                        ]
                        lines = lines[:gr_idx] + replacement + lines[stmt_end+1:]
                else:
                    # 格式：routes.addAll(...) 或 return routes;
                    # 把 update.githubUrl 改成 update.apkUrl（如果有）
                    if 'update.githubUrl' in lines[gr_idx]:
                        lines[gr_idx] = lines[gr_idx].replace('update.githubUrl', 'update.apkUrl')
                    cnb_route_code = [
                        f'{indent}String cnbUrl = update.apkUrl;',
                        f'{indent}if (cnbUrl != null && cnbUrl.startsWith("https://cnb.cool/")) {{',
                        f'{indent}    routes.add(UpdateTarget.github(cnbUrl));',
                        f'{indent}}}',
                    ]
                    lines = lines[:gr_idx] + cnb_route_code + lines[gr_idx:]
                content = '\n'.join(lines)
                if _skip_reason:
                    print(f"[WARN] {rel_path}: 跳过 getRoutes() CNB 注入——{_skip_reason}（请人工检查后处理）")
                elif content != _before:
                    # 注入后模式校验：routes 声明 + CNB 路由块 + 兜底 addAll/return 必须成对存在
                    _missing = [p for p in
                                ['List<UpdateTarget> routes',
                                 'String cnbUrl = update.apkUrl;',
                                 'cnbUrl.startsWith("https://cnb.cool/")',
                                 'routes.add(UpdateTarget.github(cnbUrl))']
                                if p not in content]
                    if _missing:
                        raise RuntimeError(
                            f"[FATAL] {rel_path}: getRoutes() 注入后模式校验失败，缺失：{_missing}。"
                            f"请检查 Updater.java 上游结构或本脚本 A3 逻辑。")
                    print(f"[OK] {rel_path}: getRoutes() 注入 CNB 第一路由（{gr_mode} 模式，apkUrl 优先）")
                    changed_any = True
                else:
                    print(f"[SKIP] {rel_path}: getRoutes() 已具备 CNB 第一路由（--force 下形态不变）")
            else:
                print(f"[WARN] {rel_path}: getRoutes() 未找到注入点（routes.addAll / return plan / return routes），请人工检查")

        # A4. 确保生成代码依赖的 import 存在（List / ArrayList）
        _needed_imports = []
        if 'import java.util.List;' not in content:
            _needed_imports.append('import java.util.List;')
        if 'import java.util.ArrayList;' not in content:
            _needed_imports.append('import java.util.ArrayList;')
        if _needed_imports:
            _lines = content.split('\n')
            _last_import_idx = -1
            for _i, _line in enumerate(_lines):
                if _line.strip().startswith('import '):
                    _last_import_idx = _i
            if _last_import_idx >= 0:
                _insert_at = _last_import_idx + 1
            else:
                # 无 import 时插到 package 声明之后
                _insert_at = 0
                for _i, _line in enumerate(_lines):
                    if _line.strip().startswith('package '):
                        _insert_at = _i + 1
                        break
            _lines = _lines[:_insert_at] + _needed_imports + _lines[_insert_at:]
            content = '\n'.join(_lines)
            print(f"[OK] {rel_path}: 补充 import {', '.join(_needed_imports)}")

        # 写回前健全性校验：括号平衡 / import 完整 / 语句收尾，不通过则脚本直接失败
        if content != original:
            _java_sanity_check(content, rel_path)

        # 写回 + 读盘验证（确保修改真正落盘，避免假阳性）
        if content != original:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 验证：重新读取文件，确认关键代码确实存在
            with open(full_path, "r", encoding="utf-8") as f:
                verify = f.read()
            v1 = "getCnbMirrorAsset(manifestName)" in verify
            v2 = "String apkField = update.apk;" in verify
            v3 = verify.find("getCnbMirrorAsset") < verify.find("getChannelAsset")
            if v1 and v2 and v3:
                print(f"[VERIFY] {rel_path}: 写回验证通过（CNB 优先在 GitHub 之前 + parseDownloads CNB 直链）")
            else:
                print(f"[ERROR] {rel_path}: 写回验证失败！cnbMirror={v1}, apkField={v2}, cnbFirst={v3}")
                changed_any = False
        elif changed_any:
            # 内部状态不一致：标记了修改但内容未变（不应该发生）
            print(f"[WARN] {rel_path}: 内部状态不一致（标记修改但内容未变），请检查")
            changed_any = False

    # ---------- B. Github.java：CNB_MANIFEST 常量自愈 + CNB_RELEASE_DOWNLOAD + getCnbReleaseAsset ----------
    github_rel = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "utils", "Github.java")
    github_path = os.path.join(REPO_ROOT, github_rel)
    if not os.path.exists(github_path):
        print(f"[SKIP] {github_rel} 不存在")
    else:
        with open(github_path, "r", encoding="utf-8") as f:
            g_content = f.read()
        g_original = g_content
        # 仅在检测到历史污染字符 \u0001 时才清洗
        if "\u0001" in g_content:
            print(f"[WARN] {github_rel}: 检测到控制字符 \\u0001，执行清洗")
            g_content = "".join(ch for ch in g_content if ch >= " " or ch in "\n\r\t")

        # B1+B2. CNB_MANIFEST + CNB_RELEASE_DOWNLOAD 常量：逐行扫描（不依赖缩进，兼容无缩进格式）
        g_lines = g_content.split('\n')
        has_manifest = any('private static final String CNB_MANIFEST' in line for line in g_lines)
        has_release = any('private static final String CNB_RELEASE_DOWNLOAD' in line for line in g_lines)
        _g_before = g_content

        if not has_manifest or FORCE_MODE:
            manifest_base = (
                f"https://cnb.cool/{cnb_slug}/-/git/raw/main/apk"
                if cnb_slug
                else "https://cnb.cool/fish2035/webhtv-release/-/git/raw/main/apk"
            )
            # --force 时先移除旧 CNB_MANIFEST 行
            if FORCE_MODE and has_manifest:
                g_lines = [line for line in g_lines if 'private static final String CNB_MANIFEST' not in line]
            # 找到 CNB_RELEASE_DOWNLOAD 行，在其前面插入 CNB_MANIFEST
            rd_idx = None
            for i, line in enumerate(g_lines):
                if 'private static final String CNB_RELEASE_DOWNLOAD' in line:
                    rd_idx = i
                    break
            if rd_idx is not None:
                indent = g_lines[rd_idx][:len(g_lines[rd_idx]) - len(g_lines[rd_idx].lstrip())]
                new_line = f'{indent}private static final String CNB_MANIFEST = "{manifest_base}";'
                g_lines = g_lines[:rd_idx] + [new_line] + g_lines[rd_idx:]
            else:
                # 找不到 CNB_RELEASE_DOWNLOAD，在 public class Github { 后面插入
                for i, line in enumerate(g_lines):
                    if 'public class Github' in line:
                        indent = line[:len(line) - len(line.lstrip())]
                        new_line = f'{indent}private static final String CNB_MANIFEST = "{manifest_base}";'
                        g_lines = g_lines[:i+1] + [new_line] + g_lines[i+1:]
                        break
            g_content = '\n'.join(g_lines)
            print(f"[OK] {github_rel}: CNB_MANIFEST 常量已{'重建' if not has_manifest else '强制更新'}（{manifest_base}）")
            if not cnb_slug:
                print(f"[WARN] {github_rel}: CNB_REPO_SLUG 未配置，CNB_MANIFEST 暂用旧地址，请检查")
        else:
            print(f"[SKIP] {github_rel}: CNB_MANIFEST 常量已存在")

        if not has_release or FORCE_MODE:
            release_base = f"https://cnb.cool/{cnb_slug}/-/releases/download" if cnb_slug else "https://cnb.cool/fish2035/webhtv-release/-/releases/download"
            g_lines = g_content.split('\n')
            # --force 时先移除旧 CNB_RELEASE_DOWNLOAD 行
            if FORCE_MODE and has_release:
                g_lines = [line for line in g_lines if 'private static final String CNB_RELEASE_DOWNLOAD' not in line]
            # 找到 CNB_MANIFEST 行，在其后面插入 CNB_RELEASE_DOWNLOAD
            mf_idx = None
            for i, line in enumerate(g_lines):
                if 'private static final String CNB_MANIFEST' in line:
                    mf_idx = i
                    break
            if mf_idx is not None:
                indent = g_lines[mf_idx][:len(g_lines[mf_idx]) - len(g_lines[mf_idx].lstrip())]
                new_line = f'{indent}private static final String CNB_RELEASE_DOWNLOAD = "{release_base}";'
                g_lines = g_lines[:mf_idx+1] + [new_line] + g_lines[mf_idx+1:]
            else:
                for i, line in enumerate(g_lines):
                    if 'public class Github' in line:
                        indent = line[:len(line) - len(line.lstrip())]
                        new_line = f'{indent}private static final String CNB_RELEASE_DOWNLOAD = "{release_base}";'
                        g_lines = g_lines[:i+1] + [new_line] + g_lines[i+1:]
                        break
            g_content = '\n'.join(g_lines)
            print(f"[OK] {github_rel}: CNB_RELEASE_DOWNLOAD 常量已设置")
            if not cnb_slug:
                print(f"[WARN] {github_rel}: CNB_REPO_SLUG 未配置，CNB_RELEASE_DOWNLOAD 暂用旧地址，请检查")

        if g_content != _g_before:
            changed_any = True

        # B3. getCnbReleaseAsset 方法：逐行扫描定位 getCnbMirrorAsset，在其后插入（不依赖缩进）
        if "public static String getCnbReleaseAsset" not in g_content or FORCE_MODE:
            g_lines = g_content.split('\n')
            # FORCE_MODE 时先移除已存在的 getCnbReleaseAsset 方法
            if FORCE_MODE:
                rel_start = None
                for i, line in enumerate(g_lines):
                    if 'public static String getCnbReleaseAsset(String tag, String name)' in line:
                        rel_start = i
                        break
                if rel_start is not None:
                    depth = 0
                    rel_end = None
                    for i in range(rel_start, len(g_lines)):
                        depth += g_lines[i].count('{') - g_lines[i].count('}')
                        if depth == 0 and i > rel_start:
                            rel_end = i
                            break
                    if rel_end is not None:
                        # 移除方法及其前的空行
                        while rel_start > 0 and not g_lines[rel_start-1].strip():
                            rel_start -= 1
                        g_lines = g_lines[:rel_start] + g_lines[rel_end+1:]
                        g_content = '\n'.join(g_lines)
            # 找到 getCnbMirrorAsset 方法的结束位置
            mirror_start = None
            for i, line in enumerate(g_lines):
                if 'public static String getCnbMirrorAsset(String name)' in line:
                    mirror_start = i
                    break
            if mirror_start is not None:
                depth = 0
                mirror_end = None
                for i in range(mirror_start, len(g_lines)):
                    depth += g_lines[i].count('{') - g_lines[i].count('}')
                    if depth == 0 and i > mirror_start:
                        mirror_end = i
                        break
                if mirror_end is not None:
                    _before_g = g_content
                    indent = g_lines[mirror_start][:len(g_lines[mirror_start]) - len(g_lines[mirror_start].lstrip())]
                    new_method = [
                        '',
                        f'{indent}public static String getCnbReleaseAsset(String tag, String name) {{',
                        f'{indent}    return CNB_RELEASE_DOWNLOAD + "/" + tag + "/" + name;',
                        f'{indent}}}',
                    ]
                    g_lines = g_lines[:mirror_end+1] + new_method + g_lines[mirror_end+1:]
                    g_content = '\n'.join(g_lines)
                    if g_content != _before_g:
                        print(f"[OK] {github_rel}: getCnbReleaseAsset 方法已添加")
                        changed_any = True
                    else:
                        print(f"[SKIP] {github_rel}: getCnbReleaseAsset 方法已存在（--force 下形态不变）")
                else:
                    print(f"[WARN] {github_rel}: getCnbMirrorAsset 方法未找到闭合大括号，跳过 getCnbReleaseAsset 注入")
            else:
                print(f"[WARN] {github_rel}: 未找到 getCnbMirrorAsset 方法，跳过 getCnbReleaseAsset 注入")

        # 写回前健全性校验
        if g_content != g_original:
            _java_sanity_check(g_content, github_rel)

        # 写回 + 读盘验证
        g_changed = (g_content != g_original)
        if g_changed:
            with open(github_path, "w", encoding="utf-8") as f:
                f.write(g_content)
            with open(github_path, "r", encoding="utf-8") as f:
                g_verify = f.read()
            v1 = "private static final String CNB_MANIFEST" in g_verify
            v2 = "CNB_RELEASE_DOWNLOAD" in g_verify
            v3 = "getCnbReleaseAsset" in g_verify
            if v1 and v2 and v3:
                print(f"[VERIFY] {github_rel}: 写回验证通过（CNB_MANIFEST + CNB_RELEASE_DOWNLOAD + getCnbReleaseAsset）")
            else:
                print(f"[ERROR] {github_rel}: 写回验证失败！CNB_MANIFEST={v1}, CNB_RELEASE_DOWNLOAD={v2}, getCnbReleaseAsset={v3}")

    if changed_any:
        return True
    print("[SKIP] 更新机制已是目标状态（CNB 优先 + CNB 直连下载 + 路由兜底）")
    return False


# ---------------------------------------------------------------- 9. CNB 脚本
def modify_cnb_release_script(config):
    """修改 sync-cnb-release.sh：

    1) CNB_REPO_SLUG 统一为「环境变量优先 + 正确默认值」形式：
         CNB_REPO_SLUG="${CNB_REPO_SLUG:-<你的slug>}"
       这样 workflow env 传入时用 env，未传时也默认指向你的 CNB 仓库，
       彻底消除 workflow 仍是旧 slug（fish2035/webhtv-release）时克隆错仓库的问题。
    2) 兜底替换脚本内任何残留的旧 slug / 旧 URL。
    3) 写盘后给脚本加可执行位（chmod +x），双保险避免 Permission denied。
    """
    cnb_repo_slug = config.get("CNB_REPO_SLUG", "")
    if not cnb_repo_slug:
        print("[SKIP] CNB_REPO_SLUG 未配置")
        return False
    old_slug = "fish2035/webhtv-release"
    cnb_repo_url = f"https://cnb.cool/{cnb_repo_slug}.git"
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

    # 1) 统一 slug 赋值为 env 优先 + 正确默认（兼容硬编码、单引号、${:-} 三种写法）
    desired_slug_line = f'CNB_REPO_SLUG="${{CNB_REPO_SLUG:-{cnb_repo_slug}}}"'
    content, n_slug = re.subn(
        r'''CNB_REPO_SLUG=(?:"\$\{CNB_REPO_SLUG:-[^}]*\}"|'[^']*'|"[^"]*"|'\'\$\{CNB_REPO_SLUG:-[^}]*\}\''|[^\s#]+)''',
        desired_slug_line,
        content,
        count=1,
    )
    # 2) 兜底：替换任何残留旧 slug / 旧 URL（注释、默认值等）
    content = content.replace(old_slug, cnb_repo_slug)
    content = content.replace(f"https://cnb.cool/{cnb_repo_slug}.git".replace(cnb_repo_slug, old_slug), cnb_repo_url)

    changed = content != original
    if changed or n_slug:
        with open(script_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    # 3) 无论内容是否变化，都确保可执行位存在（消除 exit 126 的根因之一）
    try:
        cur_mode = os.stat(script_path).st_mode
        os.chmod(script_path, cur_mode | 0o111)
    except OSError:
        pass

    # 校验：脚本里不能再残留旧 slug
    if old_slug in content:
        print(f"[WARN] sync-cnb-release.sh 仍残留旧 slug {old_slug}，请人工检查")
    if changed or n_slug:
        print(f"[OK] sync-cnb-release.sh: CNB_REPO_SLUG -> env 优先默认 {cnb_repo_slug}，并已 chmod +x")
        return True
    print(f"[SKIP] sync-cnb-release.sh: slug 已是目标值（已确保 chmod +x）")
    return False


# ---------------------------------------------------------------- 7. gradle.properties 内存参数固化
def ensure_gradle_properties(config=None):
    """
    将 R8 内存参数固化到 gradle.properties（幂等，已存在且值正确则不改动）。

    背景：R8 OOM（java.lang.OutOfMemoryError: Java heap space）曾因堆内存不足 +
          多 ABI 并行 worker 触发。内存配置只保留 gradle.properties 单一权威：
            org.gradle.jvmargs   = -Xmx5g（堆） / MaxMetaspaceSize=1g / UTF-8
            org.gradle.workers.max = 1（R8/javac 等大内存任务串行）
            android.r8.maxWorkers = 1（R8 内部线程上限）
          workflow 不再注入 GRADLE_OPTS（由 modify_workflow_files 清理），
          避免双源冲突导致 OOM 反复出现。
    策略：缺失的键自动补充；已存在但值与目标不一致的键更新为目标值（固化）。
    """
    gp_rel = os.path.join("gradle.properties")
    gp_path = os.path.join(REPO_ROOT, gp_rel)
    if not os.path.exists(gp_path):
        print(f"[SKIP] {gp_rel} 不存在，无法固化内存参数")
        return False

    expected = {
        'org.gradle.jvmargs': '-Xmx5g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8',
        'org.gradle.workers.max': '1',
        'android.r8.maxWorkers': '1',
    }
    with open(gp_path, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    lines = content.split('\n')

    # 解析现有键值（跳过注释/空行；值去掉行尾 # 注释）
    found = {}
    for _i, _line in enumerate(lines):
        _stripped = _line.strip()
        if not _stripped or _stripped.startswith('#') or '=' not in _stripped:
            continue
        _key, _, _value = _stripped.partition('=')
        _key = _key.strip()
        _value = _value.strip().split(' #')[0].strip()
        if _key in expected:
            found[_key] = (_i, _value)

    changed_any = False
    for _key, _want in expected.items():
        if _key not in found:
            lines.append(f'{_key}={_want}')
            print(f"[OK] {gp_rel}: 补充 {_key}={_want}")
            changed_any = True
        elif found[_key][1] != _want:
            lines[found[_key][0]] = f'{_key}={_want}'
            print(f"[OK] {gp_rel}: 更新 {_key}（{found[_key][1]} -> {_want}）")
            changed_any = True
        else:
            print(f"[SKIP] {gp_rel}: {_key} 已固化")

    if changed_any:
        new_content = '\n'.join(lines)
        # 确保有说明注释头（幂等）
        if 'Gradle daemon' not in new_content:
            new_content = (
                '# Gradle daemon 堆内存（R8 跑在 daemon 内，这是关键）\n'
                '# 5g 堆 + workers.max=1 使 R8/javac 串行，避免多 ABI 构建 OOM\n'
                '# 内存配置唯一权威：gradle.properties，workflow 不注入 GRADLE_OPTS\n'
                + new_content
            )
        if new_content != original:
            with open(gp_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            # 读盘验证
            with open(gp_path, "r", encoding="utf-8") as f:
                verify = f.read()
            _ok = all(f'{k}={v}' in verify for k, v in expected.items())
            if _ok:
                print(f"[VERIFY] {gp_rel}: 写回验证通过（内存参数已固化）")
                return True
            print(f"[ERROR] {gp_rel}: 写回验证失败！请检查文件内容")
            return False
    return False


# ---------------------------------------------------------------- 7b. 工作流 yml
def modify_workflow_files(config):
    """
    修改 .github/workflows/android-release.yml 与 cnb-release-sync.yml：
      - 替换 CNB_REPO_SLUG / CNB_REPO_URL
      - 清理 Build four release APKs 步骤中残留的 GRADLE_OPTS（内存统一由
        gradle.properties 控制，消除双源，防止 R8 OOM 反复出现）
      - setup-android 显式 packages / Install Android packages 步骤
      - 脚本调用前注入 chmod +x（修复 Permission denied）
      - publish_oci 输入项默认改为 false
    注意：全部使用标准英文半角减号，杜绝 U+2011 非法字符。
    """
    cnb_repo_slug = config.get("CNB_REPO_SLUG", "")
    if not cnb_repo_slug:
        print("[SKIP] CNB_REPO_SLUG 未配置，跳过工作流修改")
        return False
    cnb_repo_url = f"https://cnb.cool/{cnb_repo_slug}.git"
    # 读取项目 compileSdk，用于 setup-android 显式 packages（排除已废弃的 tools 包）
    compile_sdk = 34
    for _bp in [os.path.join(REPO_ROOT, "app", "build.gradle"),
                os.path.join(REPO_ROOT, "app", "build.gradle.kts")]:
        if os.path.exists(_bp):
            with open(_bp, "r", encoding="utf-8") as _f:
                _bt = _f.read()
            _m = re.search(r'compileSdk(?:Version)?\s*=?\s*["\']?(\d+)', _bt)
            if _m:
                compile_sdk = int(_m.group(1))
                break
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

        # 替换 CNB 变量：精确匹配旧值 fish2035/webhtv-release，不破坏 ${{ }} 模板表达式
        old_slug = "fish2035/webhtv-release"
        old_url = f"https://cnb.cool/{old_slug}.git"
        new_url = cnb_repo_url
        # 1) 简单赋值：CNB_REPO_SLUG: fish2035/webhtv-release
        content = re.sub(
            r'(CNB_REPO_SLUG:\s*)' + re.escape(old_slug) + r'(\s*$)',
            rf'\g<1>{cnb_repo_slug}\g<2>',
            content, flags=re.MULTILINE,
        )
        # 2) 简单赋值：CNB_REPO_URL: https://...
        content = re.sub(
            r'(CNB_REPO_URL:\s*)' + re.escape(old_url) + r'(\s*$)',
            rf'\g<1>{new_url}\g<2>',
            content, flags=re.MULTILINE,
        )
        # 3) cnb-release-sync.yml 中 || 'old-slug' }} 模板默认值
        content = re.sub(
            r"(\|\s*\|\s*')" + re.escape(old_slug) + r"('\s*\}\})",
            rf"\g<1>{cnb_repo_slug}\g<2>",
            content,
        )
        # 4) || 'https://old-url.git' }} 模板默认值
        content = re.sub(
            r"(\|\s*\|\s*')" + re.escape(old_url) + r"('\s*\}\})",
            rf"\g<1>{new_url}\g<2>",
            content,
        )
        # 5) description 文案中的 blank = old-slug / old-url
        content = re.sub(
            r'(blank\s*=\s*)' + re.escape(old_slug),
            rf'\g<1>{cnb_repo_slug}',
            content,
        )
        content = re.sub(
            r'(blank\s*=\s*)' + re.escape(old_url),
            rf'\g<1>{new_url}',
            content,
        )

        # setup-android：纯逐行扫描定位 uses 行（不依赖正则，兼容任意 YAML 格式/缩进）
        # 第一步：setup-android@v3 只设环境 + platform-tools（不含已废弃的 tools）
        # 第二步：单独步骤手动 sdkmanager 安装 platforms / build-tools
        crlf = '\r\n' in content
        if crlf:
            content = content.replace('\r\n', '\n')
        wf_lines = content.split('\n')
        sa_idx = None
        for i, line in enumerate(wf_lines):
            if 'android-actions/setup-android@' in line and 'uses:' in line:
                sa_idx = i
                break
        has_sa = sa_idx is not None
        if sa_idx is not None:
            sa_line = wf_lines[sa_idx]
            sa_indent = sa_line[:len(sa_line) - len(sa_line.lstrip())]
            sa_dash = '- ' if sa_line.lstrip().startswith('- ') else ''
            sa_key = sa_indent + ('  ' if sa_dash else '')
            # 幂等判断：逐行检查 uses 行后 5 行内是否已有 with: + packages: platform-tools
            already_with = False
            for j in range(sa_idx+1, min(sa_idx+6, len(wf_lines))):
                if wf_lines[j].strip().startswith('with:'):
                    for k in range(j+1, min(j+4, len(wf_lines))):
                        if 'packages' in wf_lines[k] and 'platform-tools' in wf_lines[k]:
                            already_with = True
                            break
                    break
            if already_with and not FORCE_MODE:
                print(f"[SKIP] {rel_path}: setup-android 已显式 packages=platform-tools")
            else:
                _before = content
                # 吞掉旧的 with 块（紧跟 uses 行的 with: 及其后缩进更深的行）
                j = sa_idx + 1
                if j < len(wf_lines) and wf_lines[j].strip().startswith('with:'):
                    j += 1
                    while j < len(wf_lines) and wf_lines[j].strip() and \
                            len(wf_lines[j]) - len(wf_lines[j].lstrip()) > len(sa_key):
                        j += 1
                new_sa_lines = [
                    f'{sa_indent}{sa_dash}uses: android-actions/setup-android@v3',
                    f'{sa_key}with:',
                    f'{sa_key}  packages: \'platform-tools\'',
                ]
                wf_lines = wf_lines[:sa_idx] + new_sa_lines + wf_lines[j:]
                content = '\n'.join(wf_lines)
                if content != _before:
                    print(f"[OK] {rel_path}: setup-android 显式 packages=platform-tools（排除 tools）")
                    # 第二步：检查是否已有 "Install Android packages" 步骤，没有则插入
                    if 'Install Android packages' not in content:
                        install_step = (
                            f'{sa_indent}- name: Install Android packages\n'
                            f'{sa_indent}  run: |\n'
                            f'{sa_indent}    sdkmanager "platform-tools" '
                            f'"platforms;android-{compile_sdk}" '
                            f'"build-tools;{compile_sdk}.0.0"\n'
                        )
                        anchor = (f'{sa_indent}{sa_dash}uses: android-actions/setup-android@v3\n'
                                  f'{sa_key}with:\n'
                                  f'{sa_key}  packages: \'platform-tools\'\n')
                        content = content.replace(anchor, anchor + install_step, 1)
                        print(f"[OK] {rel_path}: 插入 Install Android packages 步骤（compileSdk={compile_sdk}）")
                else:
                    print(f"[SKIP] {rel_path}: setup-android 已显式 packages=platform-tools（--force 下形态不变）")
        else:
            print(f"[WARN] {rel_path}: 未找到 android-actions/setup-android 步骤，"
                  f"请确认 workflow 中的 setup 步骤写法后手动修改")
        if crlf:
            content = content.replace('\n', '\r\n')
        # 修复脚本可执行权限：Windows 推送或 git 丢失 +x 位时，直接 ./script.sh 会
        # 报 "Permission denied"（exit 126）。最稳妥做法（与仓库 publish-oci 步骤一致）：
        # 用 `bash <script>` 显式调用，完全不依赖文件可执行位；同时补一行 chmod +x 双保险。
        if "sync-cnb-release.sh" in content and "bash .github/scripts/sync-cnb-release.sh" not in content:
            # 把「仅含缩进 + 裸路径」的调用行替换为 chmod + bash 显式调用。
            # 已带 bash 前缀的行因为 .github 前有 bash 字样，天然不匹配本正则。
            pat_call = re.compile(
                r'^([ \t]*)\.github/scripts/sync-cnb-release\.sh([ \t]*)$',
                re.MULTILINE,
            )
            content, n_call = pat_call.subn(
                lambda m: f"{m.group(1)}chmod +x .github/scripts/sync-cnb-release.sh 2>/dev/null || true\n"
                          f"{m.group(1)}bash .github/scripts/sync-cnb-release.sh{m.group(2)}",
                content,
            )
            if n_call:
                print(f"[OK] {rel_path}: sync 脚本改为 bash 显式调用 + chmod 双保险（修复 Permission denied exit 126）")
            else:
                print(f"[WARN] {rel_path}: 含 sync-cnb-release.sh 但未定位到裸调用行，请人工确认调用方式")

        # 仅对 android-release.yml 清理 GRADLE_OPTS：
        # 内存参数唯一权威是 gradle.properties（org.gradle.jvmargs / workers.max / r8.maxWorkers），
        # workflow 中残留的 GRADLE_OPTS 会造成双源冲突，是 R8 OOM 反复出现的根源之一。
        # 幂等清理：存在则整行移除，不存在则跳过。
        if rel_path.endswith("android-release.yml"):
            if "GRADLE_OPTS" in content:
                cleaned_lines = []
                removed = False
                for wline in content.split('\n'):
                    if wline.strip().startswith('GRADLE_OPTS:'):
                        removed = True
                        continue
                    cleaned_lines.append(wline)
                if removed:
                    content = '\n'.join(cleaned_lines)
                    print("[OK] android-release.yml: 已移除 GRADLE_OPTS（内存统一由 gradle.properties 控制，消除双源）")
                else:
                    print("[SKIP] android-release.yml: 检测到 GRADLE_OPTS 但未能按行移除，请人工检查")
            else:
                print("[SKIP] android-release.yml: 无 GRADLE_OPTS（内存由 gradle.properties 统一控制）")

            # 给 gradle 调用补 --stacktrace（幂等）：构建失败时打印完整堆栈，
            # 让 CI 日志直接定位出错 task/行，而不是只有 "Build failed"。
            # 仓库里 gradle 调用以「缩进 + --no-daemon」作为最后一个续行参数。
            if "--stacktrace" not in content:
                _st_lines = content.split("\n")
                _st_done = False
                for _i, _line in enumerate(_st_lines):
                    if _line.strip() == "--no-daemon":
                        _indent = _line[:len(_line) - len(_line.lstrip())]
                        _st_lines[_i] = f"{_indent}--no-daemon \\\n{_indent}--stacktrace"
                        _st_done = True
                if _st_done:
                    content = "\n".join(_st_lines)
                    print("[OK] android-release.yml: gradle 调用已补 --stacktrace（失败日志更清晰）")

            # publish_oci 输入项默认改为 false（GitHub Actions 触发时默认不打勾，需要时再手动勾选）
            # 用逐行扫描实现，零正则回溯风险，保证不卡死
            oci_lines = content.splitlines(keepends=True)
            oci_patched = False
            oci_found = False
            for i, line in enumerate(oci_lines):
                if line.strip().startswith("publish_oci:"):
                    oci_found = True
                    # 计算 publish_oci: 的缩进级别，扫描到下一个同级 key 为止
                    base_indent = len(line) - len(line.lstrip())
                    for j in range(i + 1, len(oci_lines)):
                        next_line = oci_lines[j]
                        # 空行跳过
                        if not next_line.strip():
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip())
                        # 遇到同级或更高级别的 key，停止扫描
                        if next_indent <= base_indent and next_line.strip():
                            break
                        m_default = re.match(r'^(\s*default:\s*)(true|false)(\s*)$', next_line)
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
            # 写回前 YAML 解析校验：一旦破坏缩进，GitHub Actions 会直接 Invalid workflow file
            if not _yaml_looks_ok(rel_path, content):
                print(f"[FATAL] {rel_path}: 因 YAML 校验未通过，放弃写回（保留原文件，避免 CI 直接失败）")
                continue
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 读盘验证：确认关键修改确实落盘
            with open(full_path, "r", encoding="utf-8") as f:
                wf_verify = f.read()
            # setup-android 验证：如果没有该步骤则跳过；如果已有配置（本次未改）则不报错
            v_sa = (not has_sa) or ("packages:" in wf_verify and "platform-tools" in wf_verify)
            v_chmod = ("bash .github/scripts/sync-cnb-release.sh" in wf_verify
                       or "sync-cnb-release.sh" not in wf_verify)
            v_grace = "GRADLE_OPTS" not in wf_verify
            v_cnb = old_slug not in wf_verify  # 确保旧 slug 已被替换
            if v_sa and v_chmod and v_grace and v_cnb:
                sa_note = "" if has_sa else "（无 setup-android 步骤，跳过该项验证）"
                print(f"[VERIFY] {rel_path}: 写回验证通过（CNB slug 已替换 + chmod + setup-android）{sa_note}")
            else:
                print(f"[ERROR] {rel_path}: 写回验证失败！CNB已替换={v_cnb}, chmod={v_chmod}, GRADLE_OPTS={v_grace}")
                if AUTO_ROLLBACK:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    print(f"[ROLLBACK] {rel_path}: 校验失败，已自动还原为修改前内容（不影响构建）")
                    changed_any = True
                    continue
            changed_any = True
            print(f"[OK] {rel_path}: CNB 配置已更新（GRADLE_OPTS 已清理/保持无）")
        else:
            print(f"[SKIP] {rel_path}: 已是目标值")
    return changed_any


# ------------------------------------------------------------ 5c. 默认内置壁纸
def customize_default_wallpapers(config):
    """把经典内置壁纸 wallpaper_1/2/3 置顶为初始默认壁纸，并补中文名/主题色（幂等，可重复执行）。

    需求：
      · 全新安装首次打开，首页背景默认显示 wallpaper_1（WALL_GREEN=1）。
      · 「默认壁纸」循环顺序：TV(leanback) 1→3→2；手机(mobile) 1→2→3；
        经典壁纸循环完后，仍保留原有 27 张设计壁纸（不删减任何既有功能）。
      · 给 wallpaper_1/2/3 增加与设计壁纸一致的中文名称与主题色。
    改动文件：
      · Setting.java：新增 WALL_CLASSIC_2/3；DESIGN_WALLS 维持原序，
        DEFAULT_WALLS = flavor 经典序列 + 设计壁纸；getWall() 默认改为 WALL_GREEN；
        补 getBuiltInWallColor/getBuiltInWallName 的 1/2/3 分支。
      · CustomWallView.getDesignResId()：补 1/2/3 -> wallpaper_1/2/3。
      · 各 flavor 新增同包 WallFlavor.java 提供经典壁纸顺序（main 共享代码按 flavor 取序）。
    """
    changed_any = False
    setting_rel = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "setting", "Setting.java")
    wallview_rel = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "ui", "custom", "CustomWallView.java")

    def _brace_ok(text):
        depth = 0
        in_str = False
        esc = False
        for ch in text:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        return depth == 0

    def _patch(label, rel, edits):
        """edits: [(marker, old, new, ok_desc)]。任一锚点失败则整文件回滚，绝不留半改状态。"""
        nonlocal changed_any
        full = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(full):
            print(f"[SKIP] 文件不存在: {rel}")
            return False
        with open(full, "r", encoding="utf-8") as f:
            original = f.read()
        content = original
        applied = 0
        for marker, old, new, ok_desc in edits:
            if marker in content:
                print(f"[SKIP] {os.path.basename(rel)}: 已包含 {marker.strip()}（{ok_desc}）")
                continue
            if old not in content:
                print(f"[FATAL] {rel}: 未找到锚点，跳过该文件修改以避免破坏构建：{ok_desc}")
                if AUTO_ROLLBACK:
                    with open(full, "w", encoding="utf-8", newline="\n") as f:
                        f.write(original)
                    print(f"[ROLLBACK] 已还原 {rel}")
                return False
            content = content.replace(old, new, 1)
            applied += 1
            print(f"[OK] {os.path.basename(rel)}: {ok_desc}")
        if content != original:
            if not _brace_ok(content):
                print(f"[FATAL] {rel}: 花括号不平衡，放弃写回" + ("（自动回滚）" if AUTO_ROLLBACK else ""))
                if AUTO_ROLLBACK:
                    with open(full, "w", encoding="utf-8", newline="\n") as f:
                        f.write(original)
                return False
            with open(full, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            # 读盘回验
            with open(full, "r", encoding="utf-8") as f:
                reread = f.read()
            for marker, _old, _new, _desc in edits:
                if marker not in reread:
                    print(f"[FATAL] {rel}: 写盘后回验缺少 {marker.strip()}")
                    return False
            changed_any = True
        return True

    # ---------- A. Setting.java ----------
    setting_edits = [
        (
            "WALL_CLASSIC_2 = 2",
            "    public static final int WALL_GREEN = 1;\n",
            "    public static final int WALL_GREEN = 1;\n"
            "    public static final int WALL_CLASSIC_2 = 2;   // 经典内置壁纸 wallpaper_2\n"
            "    public static final int WALL_CLASSIC_3 = 3;   // 经典内置壁纸 wallpaper_3\n",
            "新增 WALL_CLASSIC_2/3 常量",
        ),
        (
            "private static final int[] DESIGN_WALLS",
            "    private static final int[] DEFAULT_WALLS = {\n"
            "            WALL_DREAM_PURPLE, WALL_LAVENDER_CRYSTAL, WALL_PASTEL_PRISM, WALL_ROSE_VEIL, WALL_VIOLET_SMOKE,\n"
            "            WALL_NEON_BERRY, WALL_MIDNIGHT_MOON, WALL_NEON_CYBER, WALL_DEEP_SPACE_GLASS, WALL_GRAPHITE_SMOKE,\n"
            "            WALL_DAYLIGHT_MINIMAL, WALL_SKY_MINT, WALL_POLAR_LIGHT_GLASS, WALL_GLASS_GRADIENT, WALL_CRYSTAL_SKY,\n"
            "            WALL_BLUE_SILK, WALL_CYAN_CRYSTAL, WALL_MINT_GLACIER, WALL_AURORA_GLASS, WALL_DEEP_SEA,\n"
            "            WALL_LIQUID_CHROME, WALL_FOREST_MIST, WALL_EMERALD_AURORA, WALL_WARM_MOON_GLASS, WALL_PEACH_DAWN,\n"
            "            WALL_CHAMPAGNE_MIST, WALL_SUNSET_PRISM\n"
            "    };\n",
            "    // 设计壁纸（10..36）保持原有顺序与功能不变\n"
            "    private static final int[] DESIGN_WALLS = {\n"
            "            WALL_DREAM_PURPLE, WALL_LAVENDER_CRYSTAL, WALL_PASTEL_PRISM, WALL_ROSE_VEIL, WALL_VIOLET_SMOKE,\n"
            "            WALL_NEON_BERRY, WALL_MIDNIGHT_MOON, WALL_NEON_CYBER, WALL_DEEP_SPACE_GLASS, WALL_GRAPHITE_SMOKE,\n"
            "            WALL_DAYLIGHT_MINIMAL, WALL_SKY_MINT, WALL_POLAR_LIGHT_GLASS, WALL_GLASS_GRADIENT, WALL_CRYSTAL_SKY,\n"
            "            WALL_BLUE_SILK, WALL_CYAN_CRYSTAL, WALL_MINT_GLACIER, WALL_AURORA_GLASS, WALL_DEEP_SEA,\n"
            "            WALL_LIQUID_CHROME, WALL_FOREST_MIST, WALL_EMERALD_AURORA, WALL_WARM_MOON_GLASS, WALL_PEACH_DAWN,\n"
            "            WALL_CHAMPAGNE_MIST, WALL_SUNSET_PRISM\n"
            "    };\n\n"
            "    // 默认内置壁纸：经典 wallpaper_1/2/3 置顶（顺序按 TV/手机 flavor 由 WallFlavor 提供），其后保留全部设计壁纸\n"
            "    private static final int[] DEFAULT_WALLS = buildDefaultWalls();\n\n"
            "    private static int[] buildDefaultWalls() {\n"
            "        int[] classic = WallFlavor.classicIds();\n"
            "        int[] design = DESIGN_WALLS;\n"
            "        int[] all = new int[classic.length + design.length];\n"
            "        System.arraycopy(classic, 0, all, 0, classic.length);\n"
            "        System.arraycopy(design, 0, all, classic.length, design.length);\n"
            "        return all;\n"
            "    }\n",
            "DEFAULT_WALLS 改为 flavor 经典序列 + 设计壁纸",
        ),
        (
            'getInt("wall", WALL_GREEN)',
            "    public static int getWall() {\n"
            "        int wall = Prefers.getInt(\"wall\", WALL_DREAM_PURPLE);\n"
            "        return wall == WALL_GREEN || isLegacyColorWall(wall) ? WALL_DREAM_PURPLE : wall;\n"
            "    }\n",
            "    public static int getWall() {\n"
            "        // 初始安装默认显示经典壁纸 wallpaper_1（WALL_GREEN）；仅旧版纯色壁纸(5..9)回退到梦幻紫霞\n"
            "        int wall = Prefers.getInt(\"wall\", WALL_GREEN);\n"
            "        return isLegacyColorWall(wall) ? WALL_DREAM_PURPLE : wall;\n"
            "    }\n",
            "getWall() 初始默认改为 wallpaper_1",
        ),
        (
            "if (wall == WALL_CLASSIC_2) return 0xFF6A6BD8;",
            "    public static int getBuiltInWallColor(int wall) {\n"
            "        if (wall == WALL_AURORA_GLASS) return 0xFF2B8ECB;",
            "    public static int getBuiltInWallColor(int wall) {\n"
            "        if (wall == WALL_GREEN) return 0xFF40C090;\n"
            "        if (wall == WALL_CLASSIC_2) return 0xFF6A6BD8;\n"
            "        if (wall == WALL_CLASSIC_3) return 0xFF5E97B0;\n"
            "        if (wall == WALL_AURORA_GLASS) return 0xFF2B8ECB;",
            "补经典壁纸主题色 1/2/3",
        ),
        (
            'if (wall == WALL_CLASSIC_2) return "紫蓝渐变";',
            "    public static String getBuiltInWallName(int wall) {\n"
            '        if (wall == WALL_AURORA_GLASS) return "蓝紫流光";',
            "    public static String getBuiltInWallName(int wall) {\n"
            '        if (wall == WALL_GREEN) return "翠绿晨光";\n'
            '        if (wall == WALL_CLASSIC_2) return "紫蓝渐变";\n'
            '        if (wall == WALL_CLASSIC_3) return "梦幻光斑";\n'
            '        if (wall == WALL_AURORA_GLASS) return "蓝紫流光";',
            "补经典壁纸中文名称 1/2/3",
        ),
    ]
    _patch("Setting.java", setting_rel, setting_edits)

    # ---------- B. CustomWallView.java：getDesignResId 补 1/2/3 ----------
    wallview_edits = [
        (
            "case Setting.WALL_CLASSIC_2 -> R.drawable.wallpaper_2;",
            "        return switch (wall) {\n"
            "            case Setting.WALL_AURORA_GLASS -> R.drawable.wallpaper_design_10_aurora_glass;",
            "        return switch (wall) {\n"
            "            case Setting.WALL_GREEN -> R.drawable.wallpaper_1;\n"
            "            case Setting.WALL_CLASSIC_2 -> R.drawable.wallpaper_2;\n"
            "            case Setting.WALL_CLASSIC_3 -> R.drawable.wallpaper_3;\n"
            "            case Setting.WALL_AURORA_GLASS -> R.drawable.wallpaper_design_10_aurora_glass;",
            "getDesignResId() 补 wallpaper_1/2/3 映射",
        ),
    ]
    _patch("CustomWallView.java", wallview_rel, wallview_edits)

    # ---------- C. 各 flavor 的 WallFlavor.java（经典壁纸顺序）----------
    pkg_dir = os.path.join("app", "src", "{flavor}", "java", "com", "fongmi", "android", "tv", "setting")
    flavors = {
        "leanback": ("TV(leanback)：wallpaper_1 -> wallpaper_3 -> wallpaper_2",
                     "        return new int[]{Setting.WALL_GREEN, Setting.WALL_CLASSIC_3, Setting.WALL_CLASSIC_2};"),
        "mobile": ("手机(mobile)：wallpaper_1 -> wallpaper_2 -> wallpaper_3",
                   "        return new int[]{Setting.WALL_GREEN, Setting.WALL_CLASSIC_2, Setting.WALL_CLASSIC_3};"),
    }
    for flavor, (desc, order_line) in flavors.items():
        rel = os.path.join(pkg_dir.format(flavor=flavor), "WallFlavor.java")
        full = os.path.join(REPO_ROOT, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        body = (
            "package com.fongmi.android.tv.setting;\n\n"
            "/**\n"
            " * 各 flavor 默认内置经典壁纸（wallpaper_1/2/3）的循环顺序。\n"
            f" * {desc}。\n"
            " * 由 Setting.buildDefaultWalls() 拼到默认壁纸列表最前，设计壁纸顺序与功能保持不变。\n"
            " * 该类按 flavor 各提供一份（main 共享代码按编译 flavor 取对应顺序）。\n"
            " */\n"
            "final class WallFlavor {\n\n"
            "    private WallFlavor() {\n"
            "    }\n\n"
            "    static int[] classicIds() {\n"
            + order_line + "\n"
            "    }\n"
            "}\n"
        )
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                old_body = f.read()
            if "classicIds" in old_body and order_line.strip() in old_body:
                print(f"[SKIP] {flavor}/WallFlavor.java 已存在且顺序正确")
                continue
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(f"[OK] 写入 {rel}（{desc}）")
        changed_any = True

    # ---------- D. 资源存在性硬校验（缺图直接报错，避免编译失败）----------
    for flavor in ("leanback", "mobile"):
        res_dir = os.path.join(REPO_ROOT, "app", "src", flavor, "res", "drawable-nodpi")
        for n in (1, 2, 3):
            p = os.path.join(res_dir, f"wallpaper_{n}.webp")
            if not os.path.exists(p):
                print(f"[FATAL] 缺少内置壁纸资源: {os.path.relpath(p, REPO_ROOT)}")
                changed_any = False
    return changed_any


# ---------------------------------------------------------------- 主流程
def main():
    global FORCE_MODE, AUTO_ROLLBACK
    FORCE_MODE = "--force" in sys.argv
    AUTO_ROLLBACK = "--auto-rollback" in sys.argv
    print("=" * 72)
    print("  local_customize.py —— 本地一键自定义（名称 / 图标 / 包名 / CNB / 内存）")
    print(f"  项目根目录: {REPO_ROOT}")
    if FORCE_MODE:
        print("  [模式] 强制模式 --force：跳过幂等判断，强制重写所有可修改文件")
    if AUTO_ROLLBACK:
        print("  [模式] --auto-rollback：写盘校验失败时自动还原文件，宁可不改也不破坏构建")
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

    print("\n--- [5b/11] TV banner 接线（android:banner 指向 320x180 PNG，当贝桌面长方形）---")
    results.append(modify_manifest_banner(config))

    print("\n--- [5c/11] 默认内置壁纸（经典 wallpaper_1/2/3 置顶 + 中文名，TV:1-3-2 / 手机:1-2-3）---")
    results.append(customize_default_wallpapers(config))

    print("\n--- [6/11] 设置页作者链接（URL_GITHUB / URL_CNB）---")
    results.append(modify_author_links(config))

    print("\n--- [7/11] 检查更新链接（Github.java / GithubProxy.java / CI 测试）---")
    results.append(modify_update_urls(config))

    print("\n--- [8/11] 更新机制（CNB 优先 manifest + CNB 直连下载 APK + GitHub 兜底路由）---")
    results.append(modify_update_order(config))

    print("\n--- [9/11] sync-cnb-release.sh（CNB_REPO_SLUG）---")
    results.append(modify_cnb_release_script(config))

    print("\n--- [10/12] 工作流 yml（CNB 地址 + chmod +x 权限 + GRADLE_OPTS 清理 + publish_oci 默认关闭）---")
    results.append(modify_workflow_files(config))

    print("\n--- [11/12] gradle.properties 内存参数固化（R8 OOM 防护，单一权威）---")
    results.append(ensure_gradle_properties(config))

    print("\n--- [12/12] 最终校验：namespace / applicationId / 发布签名一致性 ---")
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

    # —— 应用标识一致性：applicationId 必须固定，跨版本不变才能覆盖安装 ——
    pkg = str(config.get("PACKAGE_NAME", "")).strip()
    pkg_ok = True
    if pkg:
        for path in [os.path.join(REPO_ROOT, "app", "build.gradle"),
                     os.path.join(REPO_ROOT, "app", "build.gradle.kts")]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    txt = f.read()
                if re.search(r'applicationId(?:\s*=)?\s*["\']' + re.escape(pkg) + r'["\']', txt):
                    print(f"[OK] {os.path.basename(path)} applicationId 固定为 {pkg}")
                else:
                    print(f"[ERROR] {os.path.basename(path)} applicationId 不是 {pkg}，会导致无法覆盖安装！")
                    pkg_ok = False
    results.append(pkg_ok)

    # —— 发布签名一致性：workflow 必须存在「无 keystore 即失败」的硬校验，
    #    确保所有 release APK 都用同一把 release 密钥签名，杜绝 debug 签名混入 ——
    wf_rel = os.path.join(REPO_ROOT, ".github", "workflows", "android-release.yml")
    sign_ok = True
    if os.path.exists(wf_rel):
        with open(wf_rel, "r", encoding="utf-8") as f:
            wf_txt = f.read()
        if "RELEASE_KEYSTORE_BASE64" in wf_txt and "Release signing not configured" in wf_txt:
            print("[OK] android-release.yml 含发布签名硬校验：缺少 keystore secret 时构建直接失败，"
                  "不会产出 debug 签名 APK")
        else:
            print("[WARN] android-release.yml 未发现完整的发布签名硬校验，请确认 release 始终用同一 keystore")
            sign_ok = False
    results.append(sign_ok)

    print("\n" + "=" * 72)
    if all([ns_ok, pkg_ok, sign_ok]):
        print("  [DONE] 自定义修改完成，且 包名 / namespace / 发布签名 一致性校验通过。")
    elif any(results):
        print("  [DONE] 自定义修改完成，但上方存在 [ERROR]/[WARN] 项，请按提示处理。")
    else:
        print("  [DONE] 未发现需要修改的内容（或所有文件已是目标状态）。")
    print("=" * 72)
    print()
    print("【签名 / 覆盖安装一致性要点（务必遵守）】")
    if pkg:
        print(f"  · 安装包名 applicationId 已固定为 {pkg}，以后每次都用本脚本生成，勿手改。")
    print("  · GitHub Secrets 里的 RELEASE_KEYSTORE_BASE64 / RELEASE_KEY_ALIAS /")
    print("    RELEASE_STORE_PASSWORD / RELEASE_KEY_PASSWORD 必须始终是【同一把】密钥，")
    print("    一旦更换 keystore，新 APK 签名变化，老用户将无法覆盖安装（需先卸载）。")
    print("  · 若设备上曾装过其它包名（如 com.silent.android.webhtv）或 debug 签名包，")
    print("    属于不同应用，需先卸载旧版再安装；之后同包名同签名即可正常增量升级。")
    print()
    print("【下一步】")
    print("  1. git add -A")
    print("  2. git commit -m \"local customize: app name/icon/package/cnb + release fix\"")
    print("  3. git push 到你的构建仓库（如 tj 的 main 分支）")
    print("  4. 在 GitHub Actions 手动触发 Android Release，勾选 sync_cnb，即可打包并同步 CNB。")


if __name__ == "__main__":
    main()
#（注：内容由AI生成）