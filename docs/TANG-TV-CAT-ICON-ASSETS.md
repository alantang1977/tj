# TANG TV 猫咪图标资源说明（v5.6.0）

## 资源母版

- `other/image/tj_dream_cat_master.png`
- 来自本次确认的梦幻云间灰猫图片，尺寸 1254 × 1254，PNG/RGB。
- 图片四角原有黑色圆角底在导出时仅对角落连通的黑色区域做透明化，再以蓝紫渐变补底；猫咪、天空、云朵、花卉及项圈播放按钮不重新绘制。

## 生成方式

```bash
python scripts/gen_app_icon.py
```

只生成预览：

```bash
python scripts/gen_app_icon.py --preview
```

位图处理使用 ImageMagick（`magick` 或 `convert` 命令）；该流程不使用 Pillow。要求 ImageMagick 和 Bash 可执行。

## 手机端图标

| 资源 | 路径 | 尺寸 |
|---|---|---:|
| 传统启动图标 | `app/src/main/res/mipmap-mdpi..xxxhdpi/ic_launcher.png` | 128、192、256、384、512 px |
| 圆形图标 | `app/src/main/res/mipmap-mdpi..xxxhdpi/ic_launcher_round.webp` | 48、72、96、144、192 px |
| 自适应前景 | `app/src/main/res/drawable-nodpi/ic_launcher_foreground.png` | 432 × 432 px，全幅 artwork |
| 自适应背景 | `app/src/main/res/drawable/ic_launcher_background.xml` | 108 dp 矢量渐变 |
| 单色主题层 | `app/src/main/res/drawable/ic_launcher_monochrome.xml` | 108 dp 白色猫头标记 |
| Play 商店图 | `app/src/main/ic_launcher-playstore.png` | 512 × 512 px |

自适应图标 XML 保留在 `mipmap-anydpi-v26/`，并引用前景、背景和单色层。

## Android TV / Leanback

Leanback 启动横幅使用 5 档密度位图，资源名为 `@mipmap/ic_banner`：

| 密度 | 尺寸 |
|---|---:|
| mdpi | 320 × 180 |
| hdpi | 480 × 270 |
| xhdpi | 640 × 360 |
| xxhdpi | 960 × 540 |
| xxxhdpi | 1280 × 720 |

横幅同时输出到 `app/src/main/res/drawable-{density}/ic_banner.png`，供主 Manifest 的 `@drawable/ic_banner` 使用；并输出到 `app/src/leanback/res/mipmap-{density}/ic_banner.png`。Leanback Manifest 的 application 与当前启动 alias 均改为 `@mipmap/ic_banner`，两处都按 TV 专用密度位图解析。

已删除会遮蔽密度位图的旧版 `app/src/leanback/res/mipmap-anydpi-v26/ic_banner.xml`、`drawable/ic_banner.png` 和 `drawable/ic_banner_foreground.xml` 等残留资源。TV 历史启动入口为禁用状态，相关 `*_history` 图标没有改动。

## 其他品牌资源

- 应用内圆形兜底 Logo：`app/src/main/res/drawable-nodpi/ic_logo.png`，600 × 600 px。
- 通知栏图标：`drawable-anydpi/ic_notification.xml`，以及 mdpi 24、hdpi 36、xhdpi 48、xxhdpi 72 px 位图。
- Web 管理端 favicon：`app/src/main/assets/favicon.ico`，包含 16、32、48 px 三帧。

`splash` 启动画面资源 `startup_logo.png` 不属于 Launcher/TV banner 图标资源，本次保持原样。

## 资源校验

执行：

```bash
bash scripts/verify_cat_icon_assets.sh
```

脚本会校验手机端各密度资源、TV 两套横幅规格、关键透明图层、favicon 帧、Manifest 引用和旧 TV 横幅遮蔽资源是否清理。
