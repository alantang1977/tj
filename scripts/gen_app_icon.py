#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 gen_app_icon.py —— WebHTV 单一入口自定义脚本（IMAGE 图标 + 全部非图标配置）
================================================================================
在【本地克隆下来的项目根目录】运行：

    python scripts/gen_app_icon.py                 # 默认：执行全部自定义
    python scripts/gen_app_icon.py --force          # 强制重写
    python scripts/gen_app_icon.py --verify         # 仅校验图标
    python scripts/gen_app_icon.py --preview        # 导出预览
    python scripts/gen_app_icon.py --export         # 导出图标资源
    python scripts/gen_app_icon.py --icons-only     # 仅安装图标

脚本会直接修改你本地项目文件，自动完成以下全部自定义：

  [1] applicationId 安装包名 + 自动补全 buildFeatures { viewBinding true }
      （注意：namespace 保持上游 com.fongmi.android.tv，绝不修改）
  [2] app 显示名称（英文 / 简体 / 繁体 多语言 strings.xml + AndroidManifest 硬编码 label）
  [3] app 图标（固定 ICON_STYLE=image）：使用 scripts/assets/icon-style-image 中唯一母版和预制资源，
      - 手机 Launcher / 圆形 Launcher / Adaptive / Monochrome
      - Android TV 五档密度 Banner / App Logo / Play Store / 通知图标 / favicon
      - 所有彩色图标只使用附件原图；TV Banner 不添加任何中文、英文或应用名称文字
      - Banner 等比完整容纳原图于黑色 16:9 画布，不裁切、不叠加标识
      - 仅复制预制资源并校验 SHA-256、格式、尺寸、XML 与 Manifest 接线；不执行运行时绘图
  [4] 开机启动图 startup_logo.png、手机端启动图 mobile_startup.png
  [5] AndroidManifest 接线：
      - android:label 若为硬编码则改成 @string
      - TV Banner 保持 WebHTV 原生 @mipmap/ic_banner 引用（leanback 五档密度 PNG）
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
    from PIL import Image  # 可选：仅用于原有壁纸裁剪辅助功能，不参与图标安装
except ImportError:
    Image = None
try:
    import yaml as _yaml  # 可选：用于校验 workflow YAML 改完后仍可解析
    _YAML_OK = True
except Exception:
    _yaml = None
    _YAML_OK = False
import shutil
import sys
import subprocess
import xml.etree.ElementTree as ET

EXPECTED_RELEASE_CERT_SHA256 = ""  # 必须填入旧 TANG TV APK 的 signer SHA-256；CI 留空时阻断发布

# Windows 控制台即时刷新输出，避免日志"卡住不动"的假象（每行 print 立即显示）
try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
except Exception:
    pass

# ==============================================================================
# 失败登记表：把「无需修改（SKIP）」和「真的处理失败」区分开
# ------------------------------------------------------------------------------
# 原实现里各步骤的返回值含义偏窄：False 既可能是「本来就是目标状态、无需改动」，
# 也可能是「处理失败」。于是 main() 里除了图标那一步，其它步骤的失败
#（Java 写回校验不过、YAML 被破坏、XML 解析失败…）都只是打印一行 [ERROR]
# 就继续往下走，最终仍以 0 退出 —— 一份坏文件照样会被提交、被 CI 拿去打包。
# 这里用一张全局登记表把真失败收上来，main() 结尾据此以非零码退出。
FAILURES = []


def _fail(msg):
    """登记一条真实失败（main() 结尾汇总并以非零码退出）。返回 False 便于 return _fail(...)。"""
    FAILURES.append(str(msg))
    return False


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
    # 旧仓库当前 versionCode=560；本次升级至少递增到 561，避免商店/设备拒绝旧版本更新。
    "VERSION_CODE": "561",
    # 从旧版已安装 APK 提取 signer SHA-256 后填入；这是公开证书指纹，不是私钥/密码。
    "EXPECTED_RELEASE_CERT_SHA256": "",
    # CNB 仓库地址（真实存在的仓库，格式：用户名/仓库名）
    "CNB_REPO_SLUG": "tangtang.com.cn.kul/juntv",
    # custom/ 目录下的开机启动图文件名
    "STARTUP_LOGO": "startup_logo.png",
    # custom/ 目录下的手机端启动图文件名
    "MOBILE_STARTUP": "mobile_startup.png",
    # 图标模式固定为 image；旧 cat / 3d / iphone17 绘图模式已移除。
    "ICON_STYLE": "image",
    "ICON_ASSET_DIR": "scripts/assets/icon-style-image",
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
# 用法：python gen_app_icon.py --force
# 适用场景：上游同步后文件形态变化、怀疑脚本假阳性 SKIP、或需要确保所有修改落地
FORCE_MODE = False
# --auto-rollback：写盘后若读盘校验失败，自动把文件还原成修改前内容，
# 绝不把"自己都验证不过"的文件留在工作区（宁可保持上游原样，也不让 CI 报错）
AUTO_ROLLBACK = False

import argparse
import hashlib
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "icon-style-image"
MANIFEST = ASSET_ROOT / "manifest.json"
PAYLOAD = ASSET_ROOT / "payload"
PREVIEW = ASSET_ROOT / "preview"
ICON_STYLE = "image"
# Immutable project/master pins: updating the manifest alone cannot authorize a different master.
EXPECTED_MANIFEST_SHA256 = "b462baf6a31369ca8900389f44be2c88997a72ee68a84eb67caf0ef0b7bd02d0"
EXPECTED_MASTER_SHA256 = "8f255887ff08ee59449a7fddf01ac55e4ab59715b92d2c4a8ac8da691cab9541"
EXPECTED_MASTER_FOREGROUND_SHA256 = "b4e505d14945db74743edb53f8b913138869c90e1caca17eac996876dd6bfb1d"
EXPECTED_APPLICATION_ID = "com.silent.android.tangtv"
EXPECTED_NAMESPACE = "com.fongmi.android.tv"
EXPECTED_PROJECT_REF = "v5.6.0-beta-202611191140"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
# Compatibility alias used by the migrated non-icon customization functions.
_ANDROID_NS = ANDROID_NS


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        raise RuntimeError(f"Missing icon manifest: {MANIFEST}")
    manifest_hash = sha256(MANIFEST)
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(f"Pinned manifest hash mismatch: {manifest_hash}")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("icon_style") != ICON_STYLE:
        raise RuntimeError("Only ICON_STYLE=image is supported")
    if data.get("project") != "Silent1566/webhtv":
        raise RuntimeError("Icon manifest project identity mismatch")
    if data.get("ref") != EXPECTED_PROJECT_REF:
        raise RuntimeError("Icon manifest ref mismatch; review project upgrade before reuse")
    if data.get("namespace") != EXPECTED_NAMESPACE:
        raise RuntimeError("Pinned namespace mismatch; project namespace must remain com.fongmi.android.tv")
    if data.get("master", {}).get("sha256") != EXPECTED_MASTER_SHA256:
        raise RuntimeError("Only the originally supplied color master is permitted")
    if data.get("master_foreground", {}).get("sha256") != EXPECTED_MASTER_FOREGROUND_SHA256:
        raise RuntimeError("Alpha-extracted foreground no longer matches the fixed master")
    return data


def validate_asset_sources(data: dict) -> list[str]:
    errors = []
    for key in ("master", "master_foreground"):
        item = data[key]
        p = ASSET_ROOT / item["path"]
        if not p.is_file():
            errors.append(f"missing master source: {p}")
        elif sha256(p) != item["sha256"]:
            errors.append(f"master hash mismatch: {p}")
    for item in data["installs"]:
        src = ASSET_ROOT / item["source"]
        if not src.is_file():
            errors.append(f"missing payload: {src}")
        elif sha256(src) != item["sha256"]:
            errors.append(f"payload hash mismatch: {src}")
    return errors


def validate_project_contract(data: dict) -> list[str]:
    errors = []
    gradle = ROOT / "app/build.gradle"
    if not gradle.is_file():
        errors.append("required project file missing: app/build.gradle")
    else:
        txt = gradle.read_text(encoding="utf-8")
        for token in (
            f"namespace = '{EXPECTED_NAMESPACE}'",
            'leanback {', 'mobile {', 'arm64_v8a {', 'armeabi_v7a {'
        ):
            if token not in txt:
                errors.append(f"Gradle contract missing: {token}")

    def parse_manifest(rel: str):
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"required project file missing: {rel}")
            return None
        try:
            return ET.parse(path).getroot()
        except ET.ParseError as exc:
            errors.append(f"Manifest XML parse error {rel}: {exc}")
            return None

    def alias_for(root, alias_short: str, rel: str):
        if root is None:
            return None
        app = root.find("application")
        if app is None:
            errors.append(f"Manifest has no application element: {rel}")
            return None
        for alias in app.findall("activity-alias"):
            name = alias.get(ANDROID_NS + "name", "")
            if name.rsplit(".", 1)[-1] == alias_short:
                return alias
        errors.append(f"Manifest missing activity-alias {alias_short}: {rel}")
        return None

    main_rel = "app/src/main/AndroidManifest.xml"
    main = parse_manifest(main_rel)
    if main is not None:
        app = main.find("application")
        if app is None:
            errors.append("main Manifest has no application element")
        else:
            expected = {"icon": "@mipmap/ic_launcher", "roundIcon": "@mipmap/ic_launcher_round"}
            for attr, value in expected.items():
                actual = app.get(ANDROID_NS + attr)
                if actual != value:
                    errors.append(f"main Manifest android:{attr} is {actual!r}, expected {value!r}")

    mobile_rel = "app/src/mobile/AndroidManifest.xml"
    mobile = parse_manifest(mobile_rel)
    mobile_current = alias_for(mobile, "HomeActivityCurrent", mobile_rel)
    if mobile_current is not None:
        for attr, value in (("icon", "@mipmap/ic_launcher"), ("roundIcon", "@mipmap/ic_launcher_round")):
            if mobile_current.get(ANDROID_NS + attr) != value:
                errors.append(f"mobile HomeActivityCurrent android:{attr} must be {value}")
    mobile_history = alias_for(mobile, "HomeActivityHistory", mobile_rel)
    if mobile_history is not None:
        if mobile_history.get(ANDROID_NS + "icon") != "@drawable/ic_launcher_history":
            errors.append("mobile Original icon alias was changed")
        if mobile_history.get(ANDROID_NS + "roundIcon") != "@drawable/ic_launcher_history":
            errors.append("mobile Original round icon alias was changed")

    tv_rel = "app/src/leanback/AndroidManifest.xml"
    tv = parse_manifest(tv_rel)
    if tv is not None:
        app = tv.find("application")
        if app is None or app.get(ANDROID_NS + "banner") != "@mipmap/ic_banner":
            errors.append('TV application must keep android:banner="@mipmap/ic_banner"')
    tv_current = alias_for(tv, "HomeActivityCurrent", tv_rel)
    if tv_current is not None:
        for attr, value in (("icon", "@mipmap/ic_launcher"), ("roundIcon", "@mipmap/ic_launcher_round"), ("banner", "@mipmap/ic_banner")):
            if tv_current.get(ANDROID_NS + attr) != value:
                errors.append(f"TV HomeActivityCurrent android:{attr} must be {value}")
    tv_history = alias_for(tv, "HomeActivityHistory", tv_rel)
    if tv_history is not None:
        if tv_history.get(ANDROID_NS + "icon") != "@drawable/ic_launcher_history":
            errors.append("TV Original icon alias was changed")
        if tv_history.get(ANDROID_NS + "roundIcon") != "@drawable/ic_launcher_history":
            errors.append("TV Original round icon alias was changed")
        if tv_history.get(ANDROID_NS + "banner") != "@drawable/ic_banner_history":
            errors.append("TV Original banner alias was changed")

    # app_name is owned by the non-icon customizer; banner artwork remains the pinned image asset.

    # Preserve both history-option resources; only the enabled default/current icon is replaced.
    if not list(ROOT.glob("app/src/main/res/drawable*/ic_launcher_history.*")):
        errors.append("Original launcher icon resource ic_launcher_history is missing")
    if not list(ROOT.glob("app/src/main/res/drawable*/ic_banner_history.*")):
        errors.append("Original TV banner resource ic_banner_history is missing")
    return errors


def validate_install_targets(data: dict) -> list[str]:
    errors = []
    for item in data["installs"]:
        target = ROOT / item["target"]
        if not target.is_file():
            errors.append(f"missing installed resource: {target.relative_to(ROOT)}")
            continue
        if sha256(target) != item["sha256"]:
            errors.append(f"installed resource hash mismatch: {target.relative_to(ROOT)}")
        if item.get("format") == "XML" or target.suffix.lower() == ".xml":
            try:
                ET.parse(target)
            except ET.ParseError as e:
                errors.append(f"invalid XML {target.relative_to(ROOT)}: {e}")
    for rel in data.get("cleanup", []):
        if (ROOT / rel).exists():
            errors.append(f"obsolete conflicting resource remains: {rel}")
    # Adaptive XML should retain the exact Android drawable references.
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        p = ROOT / "app/src/main/res/mipmap-anydpi-v26" / name
        if p.is_file():
            try:
                r = ET.parse(p).getroot()
                refs = [child.attrib.get(ANDROID_NS + "drawable", "") for child in list(r)]
                if refs != ["@drawable/ic_launcher_background", "@drawable/ic_launcher_foreground", "@drawable/ic_launcher_monochrome"]:
                    errors.append(f"adaptive icon layer order/reference mismatch: {p.relative_to(ROOT)}")
            except ET.ParseError as e:
                errors.append(f"invalid adaptive XML {p.relative_to(ROOT)}: {e}")
    return errors


def ensure_webhtv_tv_banner_manifest(verbose: bool = True) -> bool:
    """恢复 WebHTV 的 TV Banner 契约：application/current alias 必须引用 @mipmap/ic_banner。

    本函数特意不改 main Manifest，也不触碰 Original icon 的历史 Banner；
    TV PNG 由五档 mipmap-* 密度资源提供，不使用附件旧脚本的 @drawable 方案。
    返回是否发生了文件修改；解析失败会抛出异常，阻断后续安装/构建。
    """
    manifest = ROOT / "app/src/leanback/AndroidManifest.xml"
    if not manifest.is_file():
        raise FileNotFoundError(f"Required TV Manifest missing: {manifest.relative_to(ROOT)}")

    android_uri = "http://schemas.android.com/apk/res/android"
    tools_uri = "http://schemas.android.com/tools"
    ET.register_namespace("android", android_uri)
    ET.register_namespace("tools", tools_uri)
    try:
        tree = ET.parse(manifest)
    except ET.ParseError as exc:
        raise RuntimeError(f"TV Manifest XML parse error: {exc}") from exc

    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise RuntimeError("TV Manifest has no application element")

    banner_attr = "{" + android_uri + "}banner"
    changed = False
    current = app.get(banner_attr)
    if current != "@mipmap/ic_banner":
        app.set(banner_attr, "@mipmap/ic_banner")
        changed = True
        if verbose:
            print(f"[FIX] leanback application android:banner {current!r} -> '@mipmap/ic_banner'")

    found_current = False
    for alias in app.findall("activity-alias"):
        name = alias.get("{" + android_uri + "}name", "")
        if name.rsplit(".", 1)[-1] == "HomeActivityCurrent":
            found_current = True
            alias_banner = alias.get(banner_attr)
            if alias_banner != "@mipmap/ic_banner":
                alias.set(banner_attr, "@mipmap/ic_banner")
                changed = True
                if verbose:
                    print(f"[FIX] HomeActivityCurrent android:banner {alias_banner!r} -> '@mipmap/ic_banner'")
            break
    if not found_current:
        raise RuntimeError("TV Manifest missing activity-alias HomeActivityCurrent")

    if changed:
        tree.write(manifest, encoding="utf-8", xml_declaration=True)
    elif verbose:
        print("[OK] leanback application / current alias banner 已使用 @mipmap/ic_banner，无需重复修改")
    return changed


def install(data: dict) -> None:
    errors = validate_asset_sources(data)
    if errors:
        raise RuntimeError("Asset preflight failed:\n  - " + "\n  - ".join(errors))
    # Repair the known legacy @drawable mismatch before the installer's contract check.
    ensure_webhtv_tv_banner_manifest(verbose=True)
    for item in data["installs"]:
        src = ASSET_ROOT / item["source"]
        dst = ROOT / item["target"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if sha256(dst) != item["sha256"]:
            raise RuntimeError(f"Post-copy hash mismatch: {dst.relative_to(ROOT)}")
        print(f"[OK] {item['target']}")
    for rel in data.get("cleanup", []):
        path = ROOT / rel
        if path.exists():
            path.unlink()
            print(f"[CLEAN] {rel}")
    errors = validate_install_targets(data)
    errors += validate_project_contract(data)
    if errors:
        raise RuntimeError("Post-install verification failed:\n  - " + "\n  - ".join(errors))
    print(f"[DONE] ICON_STYLE={ICON_STYLE}; {len(data['installs'])} resources installed and verified")
    print("[KEEP] ic_launcher_history / ic_banner_history are preserved as the app's explicit Original icon option.")


def verify(data: dict) -> None:
    errors = validate_asset_sources(data)
    errors += validate_install_targets(data)
    errors += validate_project_contract(data)
    if errors:
        raise RuntimeError("Icon verification failed:\n  - " + "\n  - ".join(errors))
    print(f"[OK] ICON_STYLE={ICON_STYLE}; {len(data['installs'])} resources match SHA-256 and project wiring")


def export_preview() -> None:
    if not PREVIEW.is_dir():
        raise RuntimeError(f"Preview directory missing: {PREVIEW}")
    out = ROOT / "build/icon-preview"
    out.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p in sorted(PREVIEW.iterdir()):
        if p.is_file():
            shutil.copyfile(p, out / p.name)
            copied += 1
    print(f"[OK] {copied} preview files exported to {out.relative_to(ROOT)}")



# Adapter API retained for the attachment's full customization workflow.
def install_icon_assets(config=None, verbose=True):
    data = load_manifest(); install(data); return True

def verify_icons(style="image", verbose=True, config=None):
    try:
        if str(style).lower() != "image": raise RuntimeError("Only ICON_STYLE=image is supported")
        verify(load_manifest()); return True, []
    except Exception as exc:
        if verbose: print(f"[ICON ERROR] {exc}")
        return False, [("icon verification", False, str(exc))]

def do_write(style="image"):
    if str(style).lower() != "image": raise ValueError("Only ICON_STYLE=image is supported")
    install(load_manifest())

def do_preview(style="image"):
    if str(style).lower() != "image": raise ValueError("Only ICON_STYLE=image is supported")
    export_preview()

def do_export(style="image"):
    if str(style).lower() != "image": raise ValueError("Only ICON_STYLE=image is supported")
    load_manifest(); out = ROOT / "build/icon-export"
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for rel in ("master.png", "master-foreground.png", "manifest.json"):
        p = ASSET_ROOT / rel
        if p.is_file(): shutil.copy2(p, out / p.name)
    for folder in ("payload", "preview"):
        p = ASSET_ROOT / folder
        if p.is_dir(): shutil.copytree(p, out / folder)
    print(f"[OK] Full IMAGE icon set exported to {out.relative_to(ROOT)}")


def get_release_keystore_fingerprint():
    """读取 local.properties 指向的 release.jks，用 keytool 提取证书 SHA-256 指纹（大写无冒号）。

    返回 (fingerprint_str, store_path, alias, error_msg)。失败时 fingerprint_str 为 None。
    CI 里 Configure release signing 之后 local.properties 才存在；本地开发时可能不存在。
    """
    lp = os.path.join(REPO_ROOT, "local.properties")
    if not os.path.exists(lp):
        return None, "", "", "local.properties 不存在（CI 签名步骤之前或本地未配置）"
    props = {}
    with open(lp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()
    store = props.get("storeFile", "")
    store_pass = props.get("storePassword", "")
    alias = props.get("keyAlias", "")
    if not store or not os.path.exists(store):
        return None, store, alias, f"storeFile 不存在: {store}"
    if not store_pass:
        return None, store, alias, "local.properties 缺 storePassword"
    # keytool -list -v 输出里找 "SHA256: AA:BB:..."
    try:
        import subprocess
        cmd = ["keytool", "-list", "-v", "-keystore", store,
               "-storepass", store_pass, "-alias", alias] if alias else \
              ["keytool", "-list", "-v", "-keystore", store, "-storepass", store_pass]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return None, store, alias, f"keytool 执行失败: {e}"
    import re as _re
    m = _re.search(r"SHA256:\s*([0-9A-Fa-f:]+)", out)
    if not m:
        return None, store, alias, "keytool 输出中未找到 SHA256 指纹（keystore 路径或密码错误？）"
    fp = m.group(1).replace(":", "").upper()
    return fp, store, alias, ""


def verify_signing_keystore(verbose=True):
    """校验 release keystore 证书指纹是否与 EXPECTED_RELEASE_CERT_SHA256 一致。

    · EXPECTED 为空：本地无 keystore 时允许仅处理源码；一旦 local.properties 存在则阻断。
    · CI 注入了 local.properties 后必须配置 EXPECTED，否则阻断构建。
    · EXPECTED 非空：指纹不一致返回 False。
    · local.properties 不存在：本地仅提示信息并放行；GitHub Actions 应在 Secrets 注入后执行指纹校验。
    · local.properties 存在但密钥/路径/keytool 无效：返回 False，阻断本地流程。
    """
    fp, store, alias, err = get_release_keystore_fingerprint()
    if fp is None:
        local_props = os.path.join(REPO_ROOT, "local.properties")
        if not os.path.exists(local_props):
            if verbose:
                print("[INFO] 本地未配置 local.properties，未读取本地 Release keystore。")
                print("[INFO] 这是正常情况：GitHub Actions 会在注入 RELEASE_KEYSTORE_BASE64 等 Secrets 后生成签名配置并执行发布签名检查。")
            return True
        if verbose:
            print(f"[ERROR] local.properties 已存在，但无法读取 Release 证书指纹：{err}")
            print("        请检查 storeFile、storePassword、keyAlias 和本机 keytool/JDK 配置。")
        return False
    expected = str(CONFIG.get("EXPECTED_RELEASE_CERT_SHA256", EXPECTED_RELEASE_CERT_SHA256)).strip().replace(":", "").upper()
    if verbose:
        print(f"[INFO] 当前 release keystore: {os.path.basename(store)} alias={alias}")
        print(f"[INFO] 证书 SHA256 指纹: {fp}")
    if not expected:
        if verbose:
            print("[ERROR] 未配置 EXPECTED_RELEASE_CERT_SHA256，无法证明签名与旧版 TANG TV 一致。")
            print("        请从旧版已安装 APK 提取 signer SHA-256，写入 custom/config.env 后再构建。")
        return False
    if fp == expected:
        if verbose:
            print("[OK] 发布签名证书指纹与预期一致（老用户可正常覆盖安装）")
        return True
    if verbose:
        print(f"[ERROR] 发布签名证书指纹不匹配！")
        print(f"        预期: {expected}")
        print(f"        实际: {fp}")
        print(f"        → 这把 keystore 与老用户已安装的 APK 不同，覆盖安装会失败。")
        print(f"        → 请检查 GitHub Secret RELEASE_KEYSTORE_BASE64 是否被换过。")
    return False



def _find_android_build_tool(tool_name):
    """在 PATH / ANDROID_HOME / ANDROID_SDK_ROOT 的 build-tools 中查找工具。"""
    from shutil import which
    found = which(tool_name) or which(tool_name + ".bat")
    if found:
        return found
    roots = [os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", "")]
    candidates = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        bt_root = os.path.join(root, "build-tools")
        if os.path.isdir(bt_root):
            for version in sorted(os.listdir(bt_root), reverse=True):
                for name in (tool_name, tool_name + ".bat", tool_name + ".exe"):
                    candidate = os.path.join(bt_root, version, name)
                    if os.path.isfile(candidate):
                        candidates.append(candidate)
    return candidates[0] if candidates else None


def verify_signed_apk(apk_path, verbose=True):
    """校验 Release APK 的签名证书、applicationId 和 versionCode。CI 构建后必须调用。"""
    apk_path = os.path.abspath(apk_path)
    if not os.path.isfile(apk_path):
        print(f"[ERROR] APK 文件不存在：{apk_path}")
        return False
    expected = str(CONFIG.get("EXPECTED_RELEASE_CERT_SHA256", EXPECTED_RELEASE_CERT_SHA256)).strip().replace(":", "").upper()
    if not expected:
        print("[ERROR] EXPECTED_RELEASE_CERT_SHA256 未配置；拒绝接受未锁定签名的 APK。")
        return False
    apksigner = _find_android_build_tool("apksigner")
    if not apksigner:
        print("[ERROR] 找不到 Android SDK build-tools/apksigner，无法验证 APK 签名。")
        return False
    try:
        result = subprocess.run([apksigner, "verify", "--print-certs", apk_path],
                                capture_output=True, text=True, timeout=90)
    except Exception as exc:
        print(f"[ERROR] apksigner 执行失败：{exc}")
        return False
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        print(f"[ERROR] APK 签名验证失败：\n{output[-4000:]}")
        return False
    match = re.search(r"certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)", output, re.IGNORECASE)
    if not match:
        print(f"[ERROR] apksigner 输出中找不到 SHA-256 signer digest：\n{output[-2000:]}")
        return False
    actual = match.group(1).replace(":", "").upper()
    if actual != expected:
        print("[ERROR] 新 APK 的签名证书与旧版 TANG TV 不一致，禁止发布/安装覆盖。")
        print(f"        expected: {expected}")
        print(f"        actual:   {actual}")
        return False

    aapt = _find_android_build_tool("aapt")
    if not aapt:
        print("[ERROR] 找不到 Android SDK build-tools/aapt，无法验证 APK package/versionCode。")
        return False
    try:
        badging = subprocess.run([aapt, "dump", "badging", apk_path],
                                 capture_output=True, text=True, timeout=60)
    except Exception as exc:
        print(f"[ERROR] aapt 执行失败：{exc}")
        return False
    if badging.returncode != 0:
        print(f"[ERROR] aapt 无法读取 APK manifest：{badging.stderr[-2000:]}")
        return False
    package_match = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'", badging.stdout, re.MULTILINE)
    if not package_match:
        print("[ERROR] aapt 输出中无法解析 package/versionCode/versionName。")
        return False
    package_name, version_code, version_name = package_match.groups()
    expected_package = EXPECTED_APPLICATION_ID
    configured_package = str(CONFIG.get("PACKAGE_NAME", "")).strip()
    expected_version_code = str(CONFIG.get("VERSION_CODE", "")).strip()
    if configured_package != EXPECTED_APPLICATION_ID:
        print(f"[ERROR] config.env PACKAGE_NAME 已偏离旧 TANG TV applicationId：{configured_package!r}")
        return False
    if package_name != expected_package:
        print(f"[ERROR] APK applicationId 不匹配：expected={expected_package}, actual={package_name}")
        return False
    if expected_version_code and version_code != expected_version_code:
        print(f"[ERROR] APK versionCode 不匹配：expected={expected_version_code}, actual={version_code}")
        return False
    if verbose:
        print(f"[OK] APK 签名证书 SHA-256 匹配旧版：{actual}")
        print(f"[OK] APK applicationId={package_name}, versionCode={version_code}, versionName={version_name}")
        print(f"[OK] APK 签名、包名和版本号检查通过：{os.path.basename(apk_path)}")
    return True

def load_config_env():
    """如果存在 custom/config.env，则用它的值覆盖 CONFIG。"""
    global EXPECTED_RELEASE_CERT_SHA256
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
                if key == "ICON_STYLE":
                    if value.strip().lower() != "image":
                        print(f"[WARN] 忽略 config.env 中的旧图标模式 {value!r}；ICON_STYLE 固定为 image")
                    CONFIG["ICON_STYLE"] = "image"
                    continue
                if key in CONFIG:
                    CONFIG[key] = value
                    if key == "EXPECTED_RELEASE_CERT_SHA256":
                        EXPECTED_RELEASE_CERT_SHA256 = value.strip().replace(":", "").upper()
                    # 不在终端回显证书指纹配置值，避免把它误当成密码复制/泄露。
                    if key == "EXPECTED_RELEASE_CERT_SHA256":
                        print("[INFO] config.env: EXPECTED_RELEASE_CERT_SHA256 = 已配置" if value.strip() else "[WARN] config.env: EXPECTED_RELEASE_CERT_SHA256 尚未配置")
                    else:
                        print(f"[INFO] config.env: {key} = {value}")


# ---------------------------------------------------------------- 1. build.gradle
def modify_build_gradle(config):
    """
    修改 app/build.gradle：
      - 仅替换 applicationId（namespace 不碰！）
      - versionName 加后缀（可选）
      - 自动补全 buildFeatures { viewBinding true }
    """
    package_name = str(config.get("PACKAGE_NAME", "")).strip()
    version_suffix = config.get("VERSION_NAME_SUFFIX", "")
    version_code = str(config.get("VERSION_CODE", "")).strip()
    changed_any = False

    # This single-entry profile is specifically for upgrading the legacy TANG TV app.
    # Do not silently turn it into the upstream WebHTV package or another application.
    if package_name != EXPECTED_APPLICATION_ID:
        return _fail(
            f"PACKAGE_NAME 必须保持旧 TANG TV applicationId={EXPECTED_APPLICATION_ID}，"
            f"当前配置为 {package_name!r}；拒绝生成不同应用包。"
        )

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

        if version_code:
            if not version_code.isdigit() or int(version_code) <= 0:
                return _fail(f"VERSION_CODE 非法：{version_code!r}")
            current_vc_match = re.search(r'\bversionCode\s*=?\s*([0-9]+)', content)
            if current_vc_match and int(version_code) < int(current_vc_match.group(1)):
                return _fail(
                    f"拒绝降低 versionCode：项目当前为 {current_vc_match.group(1)}，"
                    f"配置目标为 {version_code}。Android 更新必须使用更高版本号。"
                )
            before_vc = content
            content, n_vc = re.subn(
                r'(\bversionCode\s*=?\s*)[0-9]+',
                lambda m: m.group(1) + version_code,
                content, count=1,
            )
            if n_vc and content != before_vc:
                changed_any = True
                print(f"[OK] {filename}: versionCode 已更新为 {version_code}")
            elif n_vc:
                print(f"[OK] {filename}: versionCode 已是 {version_code}")

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

        # 自动补全 viewBinding（groovy .gradle）。同时识别 `viewBinding true`
        # 和 `viewBinding = true`，避免把上游已有配置误判为缺失并重复插入块。
        if filename.endswith(".gradle"):
            vb_enabled = re.search(r'\bviewBinding\s*(?:=\s*)?true\b', content)
            vb_disabled = re.search(r'\bviewBinding\s*(?:=\s*)?false\b', content)
            if vb_disabled:
                before_vb = content
                content = re.sub(
                    r'\bviewBinding\s*(?:=\s*)?false\b',
                    'viewBinding = true', content, count=1,
                )
            elif not vb_enabled:
                before_vb = content
                if re.search(r'\bbuildFeatures\s*\{', content):
                    content = re.sub(
                        r'(\bbuildFeatures\s*\{)',
                        r'\g<1>\n        viewBinding = true',
                        content, count=1,
                    )
                else:
                    content = re.sub(
                        r'(android\s*\{)',
                        r'\g<1>\n    buildFeatures {\n        viewBinding = true\n    }',
                        content, count=1,
                    )
            else:
                before_vb = content
            if content != before_vb:
                changed_any = True
                print("[OK] app/build.gradle: 已补全/启用 buildFeatures { viewBinding = true }")
            elif not vb_enabled and not vb_disabled:
                print("[WARN] app/build.gradle: 未找到 android{} 或 buildFeatures{} 块，viewBinding 补全失败，请人工检查")

        if content != original:
            # 写回前花括号平衡校验：viewBinding 插入若错位会破坏 android{} 块
            if not _brace_balance(filename, content):
                print(f"[FATAL] {filename}: 因花括号不平衡，放弃写回（保留原文件，避免 Gradle 解析失败）")
                _fail(f"{filename}: 花括号不平衡，已放弃写回")
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] app/{filename}: applicationId -> {package_name}"
                  + (f"，versionName 加后缀 {version_suffix}" if version_suffix else ""))
        else:
            print(f"[OK] app/{filename}: 已符合目标配置，无需重复修改")
    return changed_any


# ---------------------------------------------------------------- 2. 多语言名称
def modify_strings_xml(rel_path, app_name):
    """修改指定 strings.xml 中的 app_name 系列字段。"""
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[INFO] 可选资源文件不存在，保持项目现状: {rel_path}")
        return False
    ET.register_namespace("android", _ANDROID_NS.lstrip("{").rstrip("}"))
    ET.register_namespace("tools", "http://schemas.android.com/tools")
    try:
        tree = ET.parse(full_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"[ERROR] 解析 XML 失败 {rel_path}: {e}")
        return _fail(f"XML 解析失败 {rel_path}: {e}")

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
    checked_count = 0
    changed_count = 0
    for rel, name in files:
        full_path = os.path.join(REPO_ROOT, rel)
        if os.path.isfile(full_path):
            checked_count += 1
        if modify_strings_xml(rel, name):
            changed_any = True
            changed_count += 1
    if checked_count:
        if changed_count:
            print(f"[OK] 多语言 app_name：检查 {checked_count} 个 strings.xml，更新 {changed_count} 个文件")
        else:
            print(f"[OK] 多语言 app_name：检查 {checked_count} 个 strings.xml，全部已符合 config.env，无需修改")
    else:
        print("[WARN] 未找到可检查的 strings.xml，请确认项目资源目录")
    return changed_any


# ---------------------------------------------------------------- 3. 应用图标
def generate_app_icons(config):
    """只安装固定 IMAGE 母版资源；不再包含 cat/3d/iphone17 绘图分支。"""
    style = str(config.get("ICON_STYLE", "image")).strip().lower()
    if style != "image":
        return _fail(f"仅支持 ICON_STYLE=image，收到 {style!r}")
    try:
        print("[INFO] 安装 WebHTV 固定 IMAGE 图标资源（无 Pillow/NumPy 图标绘制）...")
        return install_icon_assets(config, verbose=True)
    except Exception as e:
        print(f"[ERROR] 图标安装/校验失败: {e}")
        return _fail(f"图标安装/校验失败: {e}")


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
            print(f"[INFO] 未提供可选启动图 custom/{source_file}，保留项目现有启动图")
            continue
        for target_rel in targets:
            target = os.path.join(REPO_ROOT, target_rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target) and os.path.getsize(target) == os.path.getsize(source):
                with open(source, "rb") as f1, open(target, "rb") as f2:
                    if f1.read() == f2.read():
                        print(f"[OK] {target_rel} 与 custom 源图完全一致，无需重复复制")
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
    except ET.ParseError as e:
        print(f"[ERROR] 解析 AndroidManifest.xml 失败: {e}")
        return _fail(f"AndroidManifest.xml 解析失败: {e}")
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
    except ET.ParseError as e:
        print(f"[ERROR] {os.path.relpath(manifest_path, REPO_ROOT)} 解析失败: {e}")
        return _fail(f"{os.path.relpath(manifest_path, REPO_ROOT)} 解析失败")

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
    """按 WebHTV 原生资源布局校验/修复 TV Banner，不再写入通用 @drawable 引用。

    TV application 与 HomeActivityCurrent 使用 @mipmap/ic_banner；
    图标安装阶段已在 leanback/res/mipmap-{density}/ 写入五档 PNG。
    HomeActivityHistory 的 @drawable/ic_banner_history 保持不变。
    """
    try:
        ensure_webhtv_tv_banner_manifest(verbose=True)
        missing = []
        for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
            rel = f"app/src/leanback/res/mipmap-{density}/ic_banner.png"
            if not os.path.isfile(os.path.join(REPO_ROOT, rel)):
                missing.append(rel)
        if missing:
            return _fail("TV Banner mipmap resources missing: " + ", ".join(missing))
        print("[OK] TV Banner：Manifest 引用 @mipmap/ic_banner，五档密度资源齐全")
        return True
    except Exception as exc:
        print(f"[ERROR] TV Banner Manifest 接线失败: {exc}")
        return _fail(f"TV Banner Manifest 接线失败: {exc}")


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
            print(f"[INFO] 可选文件不存在，未处理: {os.path.relpath(full_path, REPO_ROOT)}")
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
            print(f"[OK] {rel_path}: 已符合目标配置，无需修改")
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
            print(f"[INFO] 可选文件不存在，未处理: {os.path.relpath(full_path, REPO_ROOT)}")
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        rel_path = os.path.relpath(full_path, REPO_ROOT)
        if github_repo:
            # 替换所有已知旧仓库指向 → 目标仓库（Silent1566/webhtv + xinyonghuu/Mooyingshi 等）
            for _old_owner_repo in ["Silent1566/webhtv", "xinyonghuu/Mooyingshi"]:
                content = re.sub(rf'api\.github\.com/repos/{re.escape(_old_owner_repo)}',
                                 f'api.github.com/repos/{github_repo}', content)
                content = re.sub(rf'github\.com/{re.escape(_old_owner_repo)}',
                                 f'github.com/{github_repo}', content)
        if cnb_slug:
            content = re.sub(r'cnb\.cool/fish2035/webhtv-release',
                             f'cnb.cool/{cnb_slug}', content)
        # 残留检查：URL 字符串里不得再有旧仓库（注释里的 "adapted for Mooyingshi" 不影响）
        _residual = re.findall(r'github\.com/(?:xinyonghuu/Mooyingshi|Silent1566/webhtv)', content)
        if _residual:
            _java_sanity_check(content, rel_path,
                                forbid_patterns=[r'github\.com/xinyonghuu/Mooyingshi',
                                                 r'github\.com/Silent1566/webhtv'])
        if content != original:
            # 写回前健全性校验（这些是 .java 文件，防止替换逻辑破坏语法）
            _java_sanity_check(content, rel_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            changed_any = True
            print(f"[OK] {rel_path}: 更新链接已替换（GitHub={github_repo or '未改'} / CNB={cnb_slug or '未改'}）")
        else:
            print(f"[OK] {rel_path}: 已符合目标配置，无需修改")
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
            + "\n  请检查 gen_app_icon.py 中的字符串拼接逻辑，修复后重新运行。"
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
            return _fail(f"{label}: YAML 改完后无法解析 —— {e}")
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


def _java_block_end(lines, start):
    """返回 Java 方法/代码块的末行；兼容声明与主体在同一行的情况。"""
    depth = 0
    seen_open = False
    for i in range(start, len(lines)):
        opens = lines[i].count('{')
        closes = lines[i].count('}')
        seen_open = seen_open or opens > 0
        depth += opens - closes
        if seen_open and depth == 0:
            return i
        if depth < 0:
            return None
    return None


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
        print(f"[INFO] {rel_path} 不存在，继续处理其余更新地址文件")
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
            gu_end = _java_block_end(lines, gu_start)
            if gu_end is not None:
                gu_body = '\n'.join(lines[gu_start:gu_end+1])
                # 幂等判断：只有当 getCnbMirrorAsset 在方法中排在 getChannelAsset 之前
                # （即 CNB 是第一个被检查的源）才认为是 CNB 优先。
                # 旧代码 beta 分支里也有 getCnbMirrorAsset，但排在 GitHub 之后，必须替换。
                pos_cnb = gu_body.find('getCnbMirrorAsset')
                pos_gh  = gu_body.find('getChannelAsset')
                already_cnb_first = (pos_cnb >= 0 and (pos_gh < 0 or pos_cnb < pos_gh))
                if already_cnb_first and not FORCE_MODE:
                    print(f"[OK] {rel_path}: getUpdate() 已符合 CNB 优先逻辑")
                else:
                    _before = content
                    indent = lines[gu_start][:len(lines[gu_start]) - len(lines[gu_start].lstrip())]
                    new_method = [
                        f'{indent}private Update getUpdate(String channel) {{',
                        f'{indent}    String manifestName = getManifestName(channel);',
                        f'{indent}    // 第一优先：CNB 国内直连，成功直接返回，不回退 GitHub',
                        f'{indent}    Update cnb = readUpdate(channel, Github.getCnbMirrorAsset(manifestName), SOURCE_CNB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (cnb.hasManifest()) {{',
                        f'{indent}        Log.i(TAG, "update_source=CNB channel=" + channel + " manifest=" + manifestName);',
                        f'{indent}        return cnb;',
                        f'{indent}    }}',
                        f'{indent}    Log.w(TAG, "CNB manifest unavailable, falling back to GitHub channel=" + channel);',
                        f'{indent}    // 第二优先：GitHub update-channel tag',
                        f'{indent}    Update update = readUpdate(channel, Github.getChannelAsset(manifestName), SOURCE_GITHUB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (update.hasManifest()) {{',
                        f'{indent}        Log.i(TAG, "update_source=GitHub-channel channel=" + channel);',
                        f'{indent}        return update;',
                        f'{indent}    }}',
                        f'{indent}    if (Update.CHANNEL_BETA.equals(channel)) return getGithubBetaUpdate(channel);',
                        f'{indent}    // 第三优先：GitHub latest release',
                        f'{indent}    update = readUpdate(channel, Github.getGithubLatestAsset(manifestName), SOURCE_GITHUB, GITHUB_API_HEADERS, null);',
                        f'{indent}    if (update.hasManifest()) {{',
                        f'{indent}        Log.i(TAG, "update_source=GitHub-latest channel=" + channel);',
                        f'{indent}        return update;',
                        f'{indent}    }}',
                        f'{indent}    // 兜底：GitHub Releases API 遍历',
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
                                     'getGithubStableUpdate(channel)',
                                     'update_source=CNB',
                                     'update_source=GitHub-channel']
                                    if p not in content]
                        if _missing:
                            raise RuntimeError(
                                f"[FATAL] {rel_path}: getUpdate() 注入后模式校验失败，缺失：{_missing}。")
                        print(f"[OK] {rel_path}: getUpdate() 强化为 CNB 第一优先（带日志）→ GitHub update-channel → GitHub API 兜底")
                        changed_any = True
                    else:
                        print(f"[OK] {rel_path}: getUpdate() 已符合 CNB 优先逻辑（--force 下形态不变）")
            else:
                print(f"[WARN] {rel_path}: getUpdate() 方法未找到闭合大括号，请人工检查")
        else:
            print(f"[WARN] {rel_path}: 未找到 getUpdate() 方法，请人工检查 Updater.java 结构")

        # A2. parseDownloads()：逐行扫描定位 update.apkUrl 行，在其后插入 apkField 判断
        already_apkfield = "String apkField = update.apk;" in content
        if already_apkfield:
            # 已生成块在 --force 下同样保留；旧实现只删到 if 的右括号，
            # 会遗留 else，连续执行两次后产生重复 else 并破坏 Java 编译。
            print(f"[OK] {rel_path}: parseDownloads() 已符合 CNB 直链优先逻辑")
        else:
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
                    f'{indent}// CNB manifest 里的 apk 字段是 CNB Release 直链，优先用它下载',
                    f'{indent}if (apkField != null && apkField.startsWith("https://cnb.cool/")) {{',
                    f'{indent}    update.apkUrl = apkField;',
                    f'{indent}    Log.i(TAG, "apk_download_source=CNB-direct url=" + apkField);',
                    f'{indent}}}',
                    f'{indent}// 否则回退 GitHub Release 直链',
                    f'{indent}else {{',
                    f'{indent}    Log.i(TAG, "apk_download_source=GitHub url=" + update.apkUrl);',
                    f'{indent}}}',
                ]
                lines = lines[:pd_idx+1] + insertion + lines[pd_idx+1:]
                content = '\n'.join(lines)
                if content != _before:
                    # 注入后模式校验：apkField 声明 + CNB 直链判断必须成对出现
                    _missing = [p for p in
                                ['String apkField = update.apk;',
                                 'apkField != null && apkField.startsWith("https://cnb.cool/")',
                                 'update.apkUrl = apkField;',
                                 'apk_download_source=CNB-direct']
                                if p not in content]
                    if _missing:
                        raise RuntimeError(
                            f"[FATAL] {rel_path}: parseDownloads() 注入后模式校验失败，缺失：{_missing}。"
                            f"请检查 Updater.java 上游结构或本脚本 A2 逻辑。")
                    print(f"[OK] {rel_path}: parseDownloads() 强化为 CNB Release 直链优先（带日志）→ GitHub 兜底")
                    changed_any = True
                else:
                    print(f"[OK] {rel_path}: parseDownloads() 已符合 CNB 直链优先逻辑（--force 下形态不变）")
            else:
                print(f"[WARN] {rel_path}: 未找到 update.apkUrl = update.githubUrl; 行，请人工检查")

        # A3. getRoutes()：逐行扫描定位，自动注入 CNB 第一路由判断
        already_cnb_route = 'cnbUrl.startsWith("https://cnb.cool/")' in content
        if already_cnb_route and not FORCE_MODE:
            print(f"[OK] {rel_path}: 已具备 CNB 首选及 GitHub/OCI 兜底路由")
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
                    print(f"[OK] {rel_path}: 已具备 CNB 首选及 GitHub/OCI 兜底路由（强制模式下无需改写）")
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
                _fail(f"{rel_path}: 写回验证失败（CNB 优先 / CNB 直链未落地）")
                if AUTO_ROLLBACK:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    print(f"[ROLLBACK] {rel_path}: 已自动还原为修改前内容（不影响构建）")
                changed_any = False
        elif changed_any:
            # 内部状态不一致：标记了修改但内容未变（不应该发生）
            print(f"[WARN] {rel_path}: 内部状态不一致（标记修改但内容未变），请检查")
            changed_any = False

    # ---------- B. Github.java：CNB_MANIFEST 常量自愈 + CNB_RELEASE_DOWNLOAD + getCnbReleaseAsset ----------
    github_rel = os.path.join("app", "src", "main", "java", "com", "fongmi", "android", "tv", "utils", "Github.java")
    github_path = os.path.join(REPO_ROOT, github_rel)
    if not os.path.exists(github_path):
        print(f"[INFO] {github_rel} 不存在，跳过该可选更新入口")
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
            print(f"[OK] {github_rel}: CNB_MANIFEST 常量已存在")

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
                    rel_end = _java_block_end(g_lines, rel_start)
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
                mirror_end = _java_block_end(g_lines, mirror_start)
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
                        print(f"[OK] {github_rel}: getCnbReleaseAsset 方法已存在")
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
                _fail(f"{github_rel}: 写回验证失败（CNB_MANIFEST / CNB_RELEASE_DOWNLOAD 未落地）")
                if AUTO_ROLLBACK:
                    with open(github_path, "w", encoding="utf-8") as f:
                        f.write(g_original)
                    print(f"[ROLLBACK] {github_rel}: 已自动还原为修改前内容（不影响构建）")

    # ---------- D. UpdateChannelTest.java 适配新逻辑 ----------
    test_rel = os.path.join("app", "src", "test", "java", "com", "fongmi", "android", "tv", "UpdateChannelTest.java")
    test_path = os.path.join(REPO_ROOT, test_rel)
    if os.path.isfile(test_path):
        with open(test_path, "r", encoding="utf-8") as f:
            t_original = f.read()
        t_content = t_original

        # 测试1：updaterShortCircuitsOnStaticChannelManifestBeforeGithubApi
        # 旧断言：Github.getChannelAsset 第一优先
        # 新断言：CNB manifest 第一优先，然后是 GitHub channel
        old_test1_body = '''        int channelAsset = method.indexOf("Github.getChannelAsset");
        int shortCircuit = method.indexOf("hasManifest()) return", channelAsset);
        int betaApi = method.indexOf("getGithubBetaUpdate", shortCircuit);

        assertTrue("The fixed GitHub channel manifest must be tried first", channelAsset >= 0);
        assertTrue("A valid static manifest must prevent an unnecessary GitHub API request", shortCircuit > channelAsset);
        assertTrue("The GitHub Releases API must be fallback-only", betaApi > shortCircuit);'''

        new_test1_body = '''        int cnbManifest = method.indexOf("Github.getCnbMirrorAsset");
        int cnbHasManifest = method.indexOf("cnb.hasManifest()", cnbManifest);
        int channelAsset = method.indexOf("Github.getChannelAsset", cnbHasManifest);
        int githubApi = method.indexOf("getGithubBetaUpdate", channelAsset);

        assertTrue("CNB manifest must be tried first", cnbManifest >= 0);
        assertTrue("A valid CNB manifest must short-circuit before any GitHub channel request", cnbHasManifest > cnbManifest);
        assertTrue("GitHub channel manifest must be fallback after CNB", channelAsset > cnbHasManifest);
        assertTrue("The GitHub Releases API must be last-resort", githubApi > channelAsset);'''

        if old_test1_body in t_content:
            t_content = t_content.replace(old_test1_body, new_test1_body)
            print(f"[OK] {test_rel}: 测试1 已适配 CNB 优先逻辑")

        # 测试2：betaKeepsCnbManifestAsMigrationFallbackBeforeGithubApi
        # 旧断言：CNB 是 migration fallback（第二选择）
        # 新断言：CNB 是第一优先，然后才是 GitHub
        old_test2_body = '''        int cnbFallback = method.indexOf("Github.getCnbMirrorAsset");
        int cnbShortCircuit = method.indexOf("hasManifest()) return", cnbFallback);
        int betaApi = method.indexOf("getGithubBetaUpdate", cnbShortCircuit);

        assertTrue("Beta should retain the currently published CNB manifest as a migration fallback", cnbFallback >= 0);
        assertTrue("A valid CNB beta manifest must prevent a direct GitHub API request", cnbShortCircuit > cnbFallback);
        assertTrue("The direct GitHub API must remain the last resort", betaApi > cnbShortCircuit);'''

        new_test2_body = '''        int cnbFirst = method.indexOf("Github.getCnbMirrorAsset");
        int cnbHasManifest = method.indexOf("cnb.hasManifest()", cnbFirst);
        int channelFallback = method.indexOf("Github.getChannelAsset", cnbHasManifest);
        int githubApi = method.indexOf("getGithubBetaUpdate", channelFallback);

        assertTrue("CNB manifest must be the first choice", cnbFirst >= 0);
        assertTrue("A valid CNB manifest must short-circuit immediately", cnbHasManifest > cnbFirst);
        assertTrue("GitHub channel must be fallback after CNB failure", channelFallback > cnbHasManifest);
        assertTrue("The direct GitHub API must remain last resort", githubApi > channelFallback);'''

        if old_test2_body in t_content:
            t_content = t_content.replace(old_test2_body, new_test2_body)
            print(f"[OK] {test_rel}: 测试2 已适配 CNB 优先逻辑")

        if t_content != t_original:
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(t_content)
            changed_any = True
            print(f"[OK] {test_rel}: 单元测试已适配 CNB 优先更新逻辑")
        elif new_test1_body in t_content and new_test2_body in t_content:
            print(f"[OK] {test_rel}: 单元测试已覆盖 CNB 优先顺序，无需重复修改")
        else:
            print(f"[WARN] {test_rel}: 未匹配到可自动替换的旧测试断言；请人工确认现有测试是否覆盖 CNB 优先顺序")

    if changed_any:
        return True
    print("[OK] 更新机制已符合目标状态（CNB 优先 + CNB 直连下载 + 路由兜底）")
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
        print("[WARN] CNB_REPO_SLUG 未配置，相关 CNB 发布文件不会更新")
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
        print("[WARN] 未找到 sync-cnb-release.sh，无法自动更新 CNB 发布脚本")
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

    # 2.5) 删除 update.json 汇总生成代码（App 端不查这个文件，且 cp 多文件会报错）
    _update_json_block = (
        '# 生成 App 端查的汇总 update.json（取 mobile arm64 主包）\n'
        'if ls cnb-mirror/apk/mobile-arm64-v8a-*.json 1>/dev/null 2>&1; then\n'
        '  cp cnb-mirror/apk/mobile-arm64-v8a-*.json cnb-mirror/apk/update.json\n'
        'else\n'
        '  cp cnb-mirror/apk/*.json cnb-mirror/apk/update.json\n'
        'fi\n'
    )
    if _update_json_block in content:
        content = content.replace(_update_json_block, '', 1)
        print("[OK] sync-cnb-release.sh: 已删除 update.json 汇总生成代码")

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
    print(f"[OK] sync-cnb-release.sh: CNB slug 已符合目标值，且已确保 chmod +x")
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
        print(f"[WARN] {gp_rel} 不存在，无法固化 Gradle/R8 内存参数")
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

    # 只接管内存/编码参数，保留上游或用户已有的其它 JVM 参数。
    # 例如指定上游使用 AGP 9.x，原有 --add-exports 不能在内存调优时被误删。
    import shlex
    existing_jvm = found.get('org.gradle.jvmargs', (0, ''))[1]
    try:
        jvm_tokens = shlex.split(existing_jvm)
    except ValueError:
        jvm_tokens = existing_jvm.split()
    extra_jvm = [
        token for token in jvm_tokens
        if not token.startswith('-Xmx')
        and not token.startswith('-XX:MaxMetaspaceSize=')
        and not token.startswith('-Dfile.encoding=')
    ]
    expected['org.gradle.jvmargs'] = (
        '-Xmx5g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8'
        + ((' ' + ' '.join(extra_jvm)) if extra_jvm else '')
    )

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
            print(f"[OK] {gp_rel}: {_key} 已符合目标值")

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
            _fail(f"{gp_rel}: 写回验证失败（内存参数未落地）")
            if AUTO_ROLLBACK:
                with open(gp_path, "w", encoding="utf-8") as f:
                    f.write(original)
                print(f"[ROLLBACK] {gp_rel}: 已自动还原为修改前内容（不影响构建）")
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
        print("[WARN] CNB_REPO_SLUG 未配置，相关 CNB 发布文件不会更新，跳过工作流修改")
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
            print(f"[WARN] 必需的工作流文件不存在: {rel_path}")
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

        # 只有 Android Release 构建工作流需要 Android SDK；CNB-only 同步工作流不需要 setup-android。
        is_android_release = rel_path.replace("\\", "/").endswith("/android-release.yml")
        has_sa = False
        crlf = "\r\n" in content
        if crlf:
            content = content.replace("\r\n", "\n")

        if is_android_release:
            wf_lines = content.split("\n")
            sa_idx = None
            for i, line in enumerate(wf_lines):
                if "android-actions/setup-android@" in line and "uses:" in line:
                    sa_idx = i
                    break
            has_sa = sa_idx is not None
            if sa_idx is not None:
                sa_line = wf_lines[sa_idx]
                sa_indent = sa_line[:len(sa_line) - len(sa_line.lstrip())]
                sa_dash = "- " if sa_line.lstrip().startswith("- ") else ""
                sa_key = sa_indent + ("  " if sa_dash else "")
                already_with = False
                for j in range(sa_idx + 1, min(sa_idx + 6, len(wf_lines))):
                    if wf_lines[j].strip().startswith("with:"):
                        for k in range(j + 1, min(j + 4, len(wf_lines))):
                            if "packages" in wf_lines[k] and "platform-tools" in wf_lines[k]:
                                already_with = True
                                break
                        break
                if already_with and not FORCE_MODE:
                    print(f"[OK] {rel_path}: setup-android 已显式配置 packages=platform-tools")
                else:
                    before_setup = "\n".join(wf_lines)
                    j = sa_idx + 1
                    if j < len(wf_lines) and wf_lines[j].strip().startswith("with:"):
                        j += 1
                        while j < len(wf_lines) and wf_lines[j].strip() and \
                                len(wf_lines[j]) - len(wf_lines[j].lstrip()) > len(sa_key):
                            j += 1
                    new_sa_lines = [
                        f"{sa_indent}{sa_dash}uses: android-actions/setup-android@v3",
                        f"{sa_key}with:",
                        f"{sa_key}  packages: 'platform-tools'",
                    ]
                    wf_lines = wf_lines[:sa_idx] + new_sa_lines + wf_lines[j:]
                    content = "\n".join(wf_lines)
                    if content != before_setup:
                        print(f"[OK] {rel_path}: setup-android 显式 packages=platform-tools（排除已废弃 tools 包）")
                        if "Install Android packages" not in content:
                            install_step = (
                                f"{sa_indent}- name: Install Android packages\n"
                                f"{sa_indent}  run: |\n"
                                f"{sa_indent}    sdkmanager \"platform-tools\" "
                                f"\"platforms;android-{compile_sdk}\" "
                                f"\"build-tools;{compile_sdk}.0.0\"\n"
                            )
                            anchor = (
                                f"{sa_indent}{sa_dash}uses: android-actions/setup-android@v3\n"
                                f"{sa_key}with:\n"
                                f"{sa_key}  packages: 'platform-tools'\n"
                            )
                            content = content.replace(anchor, anchor + install_step, 1)
                            print(f"[OK] {rel_path}: 已加入 Android SDK platform/build-tools 安装步骤（compileSdk={compile_sdk}）")
                    else:
                        print(f"[OK] {rel_path}: setup-android 已符合目标，无需重复改写")
            else:
                print(f"[WARN] {rel_path}: Android Release 工作流未找到 android-actions/setup-android 步骤，请检查 SDK 安装步骤")

        if crlf:
            content = content.replace("\n", "\r\n")
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

        # android-release.yml 必须完全退出旧 local_customize/Pillow 绘图链路。
        if rel_path.endswith("android-release.yml"):
            wf_lines = content.splitlines(keepends=True)
            replacement = (
                "      - name: Verify committed IMAGE icon assets\\n"
                "        run: python3 scripts/gen_app_icon.py --verify\\n"
            ).replace("\\n", "\n")
            old_step_names = {"Regenerate icons from custom script", "Install image-master icon assets"}
            out_lines = []
            i = 0
            replaced = False
            while i < len(wf_lines):
                line = wf_lines[i]
                stripped = line.strip()
                is_old = any(stripped == f"- name: {name}" for name in old_step_names)
                if is_old:
                    indent = line[:len(line) - len(line.lstrip())]
                    # Consume the entire step until the next sibling step or end of this job's step list.
                    i += 1
                    while i < len(wf_lines):
                        nxt = wf_lines[i]
                        if nxt.strip() and len(nxt) - len(nxt.lstrip()) == len(indent) and nxt.lstrip().startswith("- "):
                            break
                        if nxt.strip() and len(nxt) - len(nxt.lstrip()) < len(indent):
                            break
                        i += 1
                    if not replaced:
                        out_lines.append(indent + "- name: Verify committed IMAGE icon assets\n")
                        out_lines.append(indent + "  run: python3 scripts/gen_app_icon.py --verify\n")
                        replaced = True
                    continue
                # If a new verify step already exists, preserve only one.
                if stripped == "- name: Verify committed IMAGE icon assets":
                    if replaced:
                        i += 1
                        while i < len(wf_lines):
                            nxt = wf_lines[i]
                            if nxt.strip() and len(nxt) - len(nxt.lstrip()) == len(line) - len(line.lstrip()) and nxt.lstrip().startswith("- "):
                                break
                            if nxt.strip() and len(nxt) - len(nxt.lstrip()) < len(line) - len(line.lstrip()):
                                break
                            i += 1
                        continue
                    replaced = True
                out_lines.append(line)
                i += 1
            content = "".join(out_lines)

            # Replace old workflow signer verifier; local_customize.py is intentionally retired.
            content = content.replace(
                "python3 custom/local_customize.py --verify-signing",
                "python3 scripts/gen_app_icon.py --verify-signing",
            )
            # Ensure the IMAGE files are checked in each matrix build job too (not only the test job).
            if "Verify IMAGE assets before APK build" not in content:
                build_match = re.search(r"(?m)^  build:\s*$", content)
                if build_match:
                    tail = content[build_match.end():]
                    py_start = tail.find("      - name: Set up Python 3.10\n")
                    py_end = -1
                    if py_start >= 0:
                        version_pos = tail.find("python-version:", py_start)
                        next_step = tail.find("      - name:", py_start + 1)
                        if version_pos >= 0 and (next_step < 0 or version_pos < next_step):
                            py_end = tail.find("\n", version_pos)
                    if py_end >= 0:
                        at = build_match.end() + py_end + 1
                        step = (
                            "\\n      - name: Verify IMAGE assets before APK build\\n"
                            "        run: python3 scripts/gen_app_icon.py --verify\\n"
                        ).replace("\\n", "\n")
                        content = content[:at] + step + content[at:]
                    else:
                        print("[ERROR] android-release.yml: build job 未找到 Python 3.10 步骤，无法插入 IMAGE 校验")
                        _fail("android-release.yml: build job 缺少 IMAGE 资源校验步骤")
                else:
                    print("[ERROR] android-release.yml: 未找到 build job，无法插入 IMAGE 校验")
                    _fail("android-release.yml: 缺少 build job")

            # Every APK must be signer/package/version checked before artifact upload.
            if "--verify-apk-signature" not in content:
                collect_line = '          cp "${apks[0]}" dist/\n'
                if collect_line in content:
                    content = content.replace(
                        collect_line,
                        collect_line + '          python3 scripts/gen_app_icon.py --verify-apk-signature "${apks[0]}"\n',
                        1,
                    )
                else:
                    print("[ERROR] android-release.yml: 未找到 Collect APK 复制步骤，无法插入 APK 签名检查")
                    _fail("android-release.yml: 未插入 APK 签名检查")

            # No CI workflow may keep a retired single-entry predecessor reference.
            if "custom/local_customize.py" in content:
                print("[ERROR] android-release.yml 仍引用已退役的 custom/local_customize.py")
                _fail("android-release.yml: 仍引用 custom/local_customize.py")
            if "Regenerate icons from custom script" in content or "Pillow numpy" in content:
                print("[ERROR] android-release.yml 仍残留旧图标绘制步骤")
                _fail("android-release.yml: 仍残留 Pillow/NumPy 旧图标生成步骤")

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
                    print("[ERROR] android-release.yml: 检测到 GRADLE_OPTS，但未能按行移除")
                    _fail("android-release.yml: GRADLE_OPTS 未能清理，内存配置存在双重来源")
            else:
                print("[OK] android-release.yml: 未设置 GRADLE_OPTS，Gradle 内存统一由 gradle.properties 控制")

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
                    print("[OK] android-release.yml: publish_oci 默认值已经是 false")
                else:
                    print("[WARN] android-release.yml: 未找到 publish_oci 输入项，跳过")


        # —— CNB 推送默认开启：sync_cnb 默认 true，避免每次打 release 都要手动勾选 ——
        if "android-release" in rel_path:
            # 把 sync_cnb 的 default: false 改成 default: true
            content = content.replace(
                'description: "Optionally mirror APKs to CNB Release and sync CNB manifests"\n        required: false\n        default: false',
                'description: "Mirror APKs to CNB Release and sync CNB manifests (default on)"\n        required: false\n        default: true'
            )

        # —— 发布签名：去掉 KEYSTORE_BASE64 回退

        # —— CNB_TOKEN 预检：sync_cnb 为 true 但 CNB_TOKEN 为空时提前报错 
        if "android-release" in rel_path:
            _CHECK_TOKEN_MARKER = "Check CNB_TOKEN before sync"
            if _CHECK_TOKEN_MARKER not in content:
                _check_step = (
                    "\n"
                    '      - name: Check CNB_TOKEN before sync\n'
                    '        if: ${{ inputs.sync_cnb }}\n'
                    '        env:\n'
                    '          CNB_TOKEN: ${{ secrets.CNB_TOKEN }}\n'
                    '        run: |\n'
                    '          if [ -z "$CNB_TOKEN" ]; then\n'
                    '            echo "::error title=CNB_TOKEN missing::sync_cnb is on but CNB_TOKEN secret is not configured."\n'
                    '            exit 1\n'
                    '          fi\n'
                    '          echo "CNB_TOKEN is configured."\n'
                )
                _sync_anchor = '      - name: Sync to CNB\n'
                if _sync_anchor in content:
                    content = content.replace(_sync_anchor, _check_step + _sync_anchor, 1)
                    print("[OK] android-release.yml: 已注入 CNB_TOKEN 预检步骤")
                else:
                    print("[WARN] android-release.yml: 未找到 Sync to CNB 步骤")

        # —— 删除 update.json 汇总生成代码（App 端不查这个文件，且 cp 多文件会报错）——
        if "android-release" in rel_path:
            _before_update_json = content
            # 匹配 update.json 生成代码块（注释 + if/else + fi）
            _update_json_block = (
                '          # 生成 App 端查的汇总 update.json（取当前 channel 的 mobile arm64 主包）\n'
                '          if ls channel-manifests/mobile-arm64-v8a-*.json 1>/dev/null 2>&1; then\n'
                '            cp channel-manifests/mobile-arm64-v8a-*.json channel-manifests/update.json\n'
                '          else\n'
                '            cp channel-manifests/*.json channel-manifests/update.json\n'
                '          fi\n'
            )
            if _update_json_block in content:
                content = content.replace(_update_json_block, '', 1)
                print("[OK] android-release.yml: 已删除 update.json 汇总生成代码（App 端按 ABI 分 manifest 查，不需要汇总）")

        # —— 发布签名：去掉 KEYSTORE_BASE64 回退，强制只用 RELEASE_*，并加指纹校验步骤 ——
        if "android-release" in rel_path:
            _before_sign = content
            # 1) 删除旧 KEYSTORE_* env（回退源）
            for _old_env in [
                "          KEYSTORE_BASE64: ${{ secrets.KEYSTORE_BASE64 }}\n",
                "          KEY_ALIAS: ${{ secrets.KEY_ALIAS }}\n",
                "          KEY_PASSWORD: ${{ secrets.KEY_PASSWORD }}\n",
            ]:
                content = content.replace(_old_env, "")
            # 2) 回退逻辑改为直接赋值（不再 :-$KEYSTORE_*）
            content = content.replace(
                'KS_BASE64="${RELEASE_KEYSTORE_BASE64:-$KEYSTORE_BASE64}"',
                'KS_BASE64="$RELEASE_KEYSTORE_BASE64"')
            content = content.replace(
                'STORE_PASSWORD="${RELEASE_STORE_PASSWORD:-$KEY_PASSWORD}"',
                'STORE_PASSWORD="$RELEASE_STORE_PASSWORD"')
            content = content.replace(
                'ALIAS="${RELEASE_KEY_ALIAS:-$KEY_ALIAS}"',
                'ALIAS="$RELEASE_KEY_ALIAS"')
            content = content.replace(
                'KEY_PASS="${RELEASE_KEY_PASSWORD:-$STORE_PASSWORD}"',
                'KEY_PASS="$RELEASE_KEY_PASSWORD"')
            # 3) 在 Configure release signing 的 echo 之后、Build 之前插入指纹校验步骤
            if "--verify-signing" not in content:
                _verify_step = (
                    "\n      - name: Verify signing keystore fingerprint\n"
                    "        run: python3 scripts/gen_app_icon.py --verify-signing\n"
                )
                # 锚点：echo "Release signing configured" 行尾
                content = content.replace(
                    '          echo "Release signing configured"\n',
                    '          echo "Release signing configured"\n' + _verify_step,
                    1)
            if content != _before_sign:
                print("[OK] android-release.yml: 签名配置已收紧（去掉 KEYSTORE_* 回退 + 加指纹校验步骤）")

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
            # 仅 Android Release 工作流检查 SDK/Gradle 配置；CNB-only 工作流不需要这些步骤。
            v_sa = (not is_android_release) or (not has_sa) or ("packages:" in wf_verify and "platform-tools" in wf_verify)
            v_chmod = ("bash .github/scripts/sync-cnb-release.sh" in wf_verify
                       or "sync-cnb-release.sh" not in wf_verify)
            v_grace = (not is_android_release) or ("GRADLE_OPTS" not in wf_verify)
            v_cnb = old_slug not in wf_verify  # 确保旧 slug 已被替换
            if v_sa and v_chmod and v_grace and v_cnb:
                checks = "CNB slug/chmod"
                if is_android_release:
                    checks += "/Android SDK/Gradle 内存配置"
                print(f"[VERIFY] {rel_path}: 写回验证通过（{checks}）")
            else:
                print(f"[ERROR] {rel_path}: 写回验证失败！CNB已替换={v_cnb}, chmod={v_chmod}, GRADLE_OPTS={v_grace}")
                _fail(f"{rel_path}: 写回验证失败（CNB/chmod/GRADLE_OPTS 未全部落地）")
                if AUTO_ROLLBACK:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    print(f"[ROLLBACK] {rel_path}: 校验失败，已自动还原为修改前内容（不影响构建）")
                    changed_any = True
                    continue
            changed_any = True
            print(f"[OK] {rel_path}: CNB 配置已更新（GRADLE_OPTS 已清理/保持无）")
        else:
            print(f"[OK] {rel_path}: 已符合目标配置，无需修改")
    return changed_any


# ------------------------------------------------------------ 5c-1. 手机壁纸由TV壁纸转换
def sync_mobile_wallpaper_from_tv(config,
                                  tv_rel="app/src/leanback/res/drawable-nodpi/wallpaper_1.webp",
                                  mob_rel="app/src/mobile/res/drawable-nodpi/wallpaper_1.webp",
                                  tw=1080, th=1920,
                                  bird_x=600, bird_y=292):
    """把 TV(leanback) 横版 wallpaper_1（翠绿晨光，蜂鸟栖枝）100%原汁原味移植为手机竖版壁纸，
    写入 mobile 同名文件，使其成为手机版首装第一张默认壁纸（与 TV 首装一致）。

    纯裁剪移植（不增加任何元素、不合成、不模糊填充、不变形）：
      · 以蜂鸟中心 (bird_x,bird_y) 为正中心，从横版原图中裁出一个 9:16 竖幅；
      · 裁剪框取「以蜂鸟为中心且能完整放进源图」的最大尺寸，确保蜂鸟（含喙/尾/脚）完整；
      · 等比 LANCZOS 放大到 1080x1920，蜂鸟精确落在画布正中心。
    注：bird_x/bird_y 为该 leanback 壁纸中蜂鸟整体（含胸腹尾）的像素中心。
    每次运行重新生成，幂等；源文件缺失时仅告警不报错（不阻断其它定制）。
    """
    tv_path = os.path.join(REPO_ROOT, tv_rel)
    mob_path = os.path.join(REPO_ROOT, mob_rel)
    if not os.path.exists(tv_path):
        print(f"[WARN] 未找到 TV 壁纸源 {tv_rel}，跳过手机壁纸转换")
        return False
    try:
        src = Image.open(tv_path).convert("RGB")
        sw, sh = src.size
        r = tw / th

        # 以蜂鸟为中心、能完整放进源图的最大 9:16 裁剪框
        h_max = min(2 * min(bird_y, sh - bird_y),
                    2 * min(bird_x, sw - bird_x) / r,
                    sh)
        w_max = h_max * r
        # 以蜂鸟整数中心对称取整（保证蜂鸟像素中心==裁剪框中心，且结果可精确复现）
        half_w = int(round(w_max / 2))
        half_h = int(round(h_max / 2))
        x0i = int(bird_x) - half_w; x1i = int(bird_x) + half_w
        y0i = int(bird_y) - half_h; y1i = int(bird_y) + half_h
        crop = src.crop((x0i, y0i, x1i, y1i))
        out = crop.resize((tw, th), Image.LANCZOS)

        # 校验蜂鸟中心是否精确落在画布正中心
        cx = (bird_x - x0i) / (x1i - x0i) * tw
        cy = (bird_y - y0i) / (y1i - y0i) * th
        centered = abs(cx - tw / 2) <= 1.5 and abs(cy - th / 2) <= 1.5

        os.makedirs(os.path.dirname(mob_path), exist_ok=True)
        out.save(mob_path, "WEBP", quality=95, method=6)
        flag = "蜂鸟精确居中" if centered else "蜂鸟居中存在偏差"
        print(f"[OK] 手机壁纸 {mob_rel} 已由 TV {tv_rel} 纯裁剪移植（{tw}x{th}，裁剪{x1i-x0i}x{y1i-y0i}，{flag}，首装第一张默认）")
        return True
    except Exception as e:
        print(f"[WARN] 手机壁纸转换失败（不阻断）：{e}")
        return False


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
            print(f"[INFO] 可选文件不存在，未处理: {rel}")
            return False
        with open(full, "r", encoding="utf-8") as f:
            original = f.read()
        content = original
        applied = 0
        for marker, old, new, ok_desc in edits:
            if marker in content:
                print(f"[OK] {os.path.basename(rel)}: 已包含所需内容（{ok_desc}）")
                continue
            if old not in content:
                print(f"[FATAL] {rel}: 未找到锚点，跳过该文件修改以避免破坏构建：{ok_desc}")
                if AUTO_ROLLBACK:
                    with open(full, "w", encoding="utf-8", newline="\n") as f:
                        f.write(original)
                    print(f"[ROLLBACK] 已还原 {rel}")
                return _fail(f"{rel}: 未找到锚点（{ok_desc}）")
            content = content.replace(old, new, 1)
            applied += 1
            print(f"[OK] {os.path.basename(rel)}: {ok_desc}")
        if content != original:
            if not _brace_ok(content):
                print(f"[FATAL] {rel}: 花括号不平衡，放弃写回" + ("（自动回滚）" if AUTO_ROLLBACK else ""))
                if AUTO_ROLLBACK:
                    with open(full, "w", encoding="utf-8", newline="\n") as f:
                        f.write(original)
                return _fail(f"{rel}: 花括号不平衡，已放弃写回")
            with open(full, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            # 读盘回验
            with open(full, "r", encoding="utf-8") as f:
                reread = f.read()
            for marker, _old, _new, _desc in edits:
                if marker not in reread:
                    print(f"[FATAL] {rel}: 写盘后回验缺少 {marker.strip()}")
                    return _fail(f"{rel}: 写盘后回验缺少 {marker.strip()}")
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
                print(f"[OK] {flavor}/WallFlavor.java 已存在且顺序正确")
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
                _fail(f"缺少内置壁纸资源: {os.path.relpath(p, REPO_ROOT)}")
                changed_any = False
    return changed_any


# ------------------------------------------------------------ 清理重复脚本
def cleanup_duplicate_scripts():
    """确保 custom/ 目录下只有【当前这一个】Python 脚本 gen_app_icon.py。

    自动删除：
      · 历史遗留的备份脚本，如「local_customize - 副本.py」及其它多余的 *.py；
      · custom/__pycache__ 缓存目录。
    保留：当前正在运行的脚本本身、config.env（配置文件，非脚本）、diy.yml、图片素材。
    """
    try:
        self_name = os.path.basename(os.path.abspath(__file__))
    except Exception:
        self_name = "gen_app_icon.py"
    keep = {self_name, "gen_app_icon.py"}
    # 只做「移走备份」而不是 os.remove：万一 custom/ 里放着自己写的辅助脚本，直接删不可恢复；
    # 移进备份目录既能保持「custom/ 下只有一个脚本」的初衷，又能随时取回。
    backup_dir = os.path.join(CUSTOM_DIR, ".removed-backup", time.strftime("%Y%m%d-%H%M%S"))
    moved = []
    removed = []
    if os.path.isdir(CUSTOM_DIR):
        for name in os.listdir(CUSTOM_DIR):
            full = os.path.join(CUSTOM_DIR, name)
            if name.endswith(".py") and os.path.isfile(full) and name not in keep:
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                    shutil.move(full, os.path.join(backup_dir, name))
                    moved.append(name)
                except Exception as e:
                    print(f"[WARN] 无法移走多余脚本 {name}: {e}")
        pycache = os.path.join(CUSTOM_DIR, "__pycache__")
        if os.path.isdir(pycache):
            try:
                shutil.rmtree(pycache, ignore_errors=True); removed.append("__pycache__")
            except Exception:
                pass
    # Legacy scripts are retained locally but their backup must not be committed to GitHub.
    gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
    ignore_rule = "custom/.removed-backup/"
    try:
        existing = ""
        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        if ignore_rule not in existing.splitlines():
            with open(gitignore_path, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write("\n# Local backups of retired customization scripts (never commit)\n")
                fh.write(ignore_rule + "\n")
            print("[OK] .gitignore: 已忽略 custom/.removed-backup/，避免把旧 local_customize.py 备份推送到仓库")
    except OSError as exc:
        _fail(f"无法更新 .gitignore 忽略本地旧脚本备份：{exc}")
    if moved:
        print("[OK] 已把多余脚本移入备份目录（未删除）：%s" % "、".join(moved))
        print(f"     备份位置：{os.path.relpath(backup_dir, CUSTOM_DIR)}（需要时可直接取回）")
    if removed:
        print("[OK] 已清理缓存目录：%s" % "、".join(removed))
    if not moved and not removed:
        print("[OK] custom/ 下只有 gen_app_icon.py，无重复脚本需要备份")


# ---------------------------------------------------------------- 清理上游半成品代码
def remove_broken_upstream_code():
    """删除上游新增的、导致 CI 编译失败的半成品 Origin / Crash 代码。

    背景：上游仓库合入了「origin isolation」隔离播放功能和「crash recovery」崩溃恢复功能，
    但只合入了调用方文件，没有合入对应的实现类方法（PlaybackService.originLease、
    NodeRuntime.openOrigin、CrashReport.isMainProcess 等都不存在），导致 19 个
    cannot find symbol 编译错误。本函数把这些半成品文件全部删掉，让编译能通过。

    策略：
    1. 删除所有 Origin / Crash 实现文件和目录（playback/origin/、PreviousProcessCrashRecovery 等）
    2. 把所有被污染的业务文件（PlaybackService.java、TmdbDetailActivity.java、App.java 等）
       整体恢复成上游 v5.6.0 正式版的干净版本，彻底清除所有残留引用

    注意：如果仓库已经是完整的 beta 版（CrashReport.isMainProcess 存在），
    说明 Origin/Crash 代码是完整的，不需要清理，直接跳过。
    """
    import urllib.request

    # === 前置检查：如果 beta 版方法完整，直接跳过 ===
    crash_report_path = os.path.join(REPO_ROOT, "app/src/main/java/com/fongmi/android/tv/utils/CrashReport.java")
    if os.path.exists(crash_report_path):
        with open(crash_report_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "isMainProcess" in content:
            print("[OK] 检测到完整的 beta 版代码，无需清理上游半成品文件")
            return

    UPSTREAM_RAW_BASE = "https://raw.githubusercontent.com/Silent1566/webhtv/v5.6.0-beta-202611191140"

    # === 第一步：删除所有半成品实现文件 / 目录 ===
    broken_paths = [
        # --- Origin 隔离播放功能（半成品，全套删掉）---
        "app/src/main/java/com/fongmi/android/tv/playback/origin",
        "app/src/main/java/com/fongmi/android/tv/node/OriginNodeService.java",
        "app/src/main/java/com/fongmi/android/tv/server/proxy/ProxyClientOriginPolicy.java",
        # --- Crash 崩溃恢复（调用了不存在的 CrashReport.isMainProcess）---
        "app/src/main/java/com/fongmi/android/tv/utils/PreviousProcessCrashRecovery.java",
        # --- 测试文件（test 源集）---
        "app/src/test/java/com/fongmi/android/tv/playback/origin",
        "app/src/test/java/com/fongmi/android/tv/server/proxy/ProxyClientOriginPolicyTest.java",
        "app/src/test/java/com/fongmi/android/tv/utils/PreviousProcessCrashRecoveryTest.java",
        "app/src/test/java/com/fongmi/android/tv/utils/CrashActivityIsolationTest.java",
        "app/src/test/java/com/fongmi/android/tv/utils/CrashHandlerTest.java",
        "app/src/test/java/com/fongmi/android/tv/utils/CrashLogWiringTest.java",
        "app/src/test/java/com/fongmi/android/tv/utils/CrashRecoveryGateTest.java",
        # --- androidTest 文件 ---
        "app/src/androidTest/java/com/fongmi/android/tv/playback/origin",
        "app/src/androidTest/assets/origin-isolation",
        # --- testLeanback 文件 ---
        "app/src/testLeanback/java/com/fongmi/android/tv/playback/origin",
        # --- testMobile 文件 ---
        "app/src/testMobile/java/com/fongmi/android/tv/ui/activity/CrashActivityDetailsTest.java",
        # --- 文档 ---
        "docs/H-ORIGIN-RESUME-isolated-history-playback.md",
    ]

    removed = []
    for rel in broken_paths:
        full = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(full):
            continue
        try:
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
            removed.append(rel)
        except Exception as e:
            print(f"[WARN] 无法删除 {rel}: {e}")
            _fail(f"无法删除上游半成品文件 {rel}: {e}")

    if removed:
        print(f"[OK] 已删除半成品实现文件 {len(removed)} 项：")
        for r in removed:
            print(f"     - {r}")

    # === 第二步：把所有被污染的业务文件恢复成上游 v5.6.0 干净版本 ===
    # 这些文件里残留了对 OriginSessionClient / OriginHistoryPlayback / PreviousProcessCrashRecovery
    # 的 import、字段、方法调用，不清理会导致 13 个 "package does not exist" 编译错误。
    # 整体恢复成上游正式版是最彻底、最可靠的清理方式。
    polluted_business_files = [
        # main 源码
        "app/src/main/java/com/fongmi/android/tv/App.java",
        "app/src/main/java/com/fongmi/android/tv/Startup.java",
        "app/src/main/java/com/fongmi/android/tv/api/CatSource.java",
        "app/src/main/java/com/fongmi/android/tv/api/config/VodConfig.java",
        "app/src/main/java/com/fongmi/android/tv/db/AppDatabase.java",
        "app/src/main/java/com/fongmi/android/tv/node/NodeBundle.java",
        "app/src/main/java/com/fongmi/android/tv/node/NodeRuntime.java",
        "app/src/main/java/com/fongmi/android/tv/service/PlaybackService.java",
        "app/src/main/java/com/fongmi/android/tv/ui/activity/CrashActivity.java",
        "app/src/main/java/com/fongmi/android/tv/ui/activity/TmdbDetailActivity.java",
        "app/src/main/java/com/fongmi/android/tv/utils/CrashLogSession.java",
        "app/src/main/java/com/fongmi/android/tv/utils/CrashReport.java",
        # leanback 源集
        "app/src/leanback/java/com/fongmi/android/tv/ui/activity/HomeActivity.java",
        "app/src/leanback/java/com/fongmi/android/tv/ui/activity/VideoActivity.java",
        # mobile 源集
        "app/src/mobile/java/com/fongmi/android/tv/ui/activity/HomeActivity.java",
        "app/src/mobile/java/com/fongmi/android/tv/ui/activity/VideoActivity.java",
    ]

    restored = []
    failed = []
    for rel in polluted_business_files:
        local_path = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(local_path):
            continue  # 本地不存在，跳过
        url = f"{UPSTREAM_RAW_BASE}/{rel}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "local-customize/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            with open(local_path, "wb") as f:
                f.write(content)
            restored.append(rel)
        except Exception as e:
            failed.append((rel, str(e)))

    if restored:
        print(f"[OK] 已恢复 {len(restored)} 个被污染业务文件为上游 v5.6.0 干净版本：")
        for r in restored:
            print(f"     - {r}")

    if failed:
        print(f"[WARN] {len(failed)} 个文件恢复失败（可能导致残留引用）：")
        for rel, err in failed:
            print(f"     - {rel}: {err}")
        _fail(f"{len(failed)} 个上游业务文件恢复失败；已阻断流程，请检查网络或上游源码后重试")

    if not removed and not restored:
        print("[OK] 未发现需要清理的上游半成品代码")


# ---------------------------------------------------------------- 主流程
def main():
    global FORCE_MODE, AUTO_ROLLBACK
    FORCE_MODE = "--force" in sys.argv
    AUTO_ROLLBACK = "--auto-rollback" in sys.argv
    print("=" * 72)
    print("  gen_app_icon.py —— 本地一键自定义（名称 / 图标 / 包名 / CNB / 内存）")
    print(f"  项目根目录: {REPO_ROOT}")
    if FORCE_MODE:
        print("  [模式] 强制模式 --force：跳过幂等判断，强制重写所有可修改文件")
    if AUTO_ROLLBACK:
        print("  [模式] --auto-rollback：写盘校验失败时自动还原文件，宁可不改也不破坏构建")
    print("=" * 72)

    if not os.path.isdir(REPO_ROOT):
        print(f"[ERROR] 找不到项目根目录: {REPO_ROOT}")
        sys.exit(1)

    gradle_files = [
        os.path.join(REPO_ROOT, "app", "build.gradle"),
        os.path.join(REPO_ROOT, "app", "build.gradle.kts"),
    ]
    if not any(os.path.isfile(path) for path in gradle_files) or Path(REPO_ROOT).resolve() != ROOT.resolve():
        print("[ERROR] 未检测到完整 Android 项目，或脚本资源目录与项目根目录不一致。")
        print("        请先把本包的 scripts/ 合并到项目根目录，再运行 python scripts/gen_app_icon.py。")
        print("        默认完整自定义已停止；--preview 和 --export 仍可在资源包中单独使用。")
        sys.exit(2)

    load_config_env()
    config = CONFIG

    if not os.path.isdir(CUSTOM_DIR):
        os.makedirs(CUSTOM_DIR, exist_ok=True)
        print(f"[INFO] 已创建 custom/ 目录：{CUSTOM_DIR}")

    cleanup_duplicate_scripts()

    print("\n--- [0/12] 清理上游半成品 Origin/Crash 代码（修复 CI 编译错误）---")
    remove_broken_upstream_code()

    results = []

    print("\n--- [1/12] app/build.gradle（applicationId + viewBinding）---")
    results.append(modify_build_gradle(config))

    print("\n--- [2/12] 多语言 app 名称（values / values-zh-rCN / values-zh-rTW）---")
    results.append(modify_all_strings(config))

    print("\n--- [3/12] 安装固定 IMAGE 母版整套应用图标（SHA-256 / 尺寸 / XML 校验）---")
    icon_ok = generate_app_icons(config)
    results.append(icon_ok)

    print("\n--- [4/12] 启动图（startup_logo / mobile_startup）---")
    results.append(replace_startup_images(config))

    print("\n--- [5/12] AndroidManifest.xml（android:label）---")
    results.append(modify_android_manifest(config))

    print("\n--- [5b/12] TV banner 接线（android:banner 指向 320x180 PNG，当贝桌面长方形）---")
    results.append(modify_manifest_banner(config))

    print("\n--- [5c/12] 默认内置壁纸（经典 wallpaper_1/2/3 置顶 + 中文名，TV:1-3-2 / 手机:1-2-3）---")
    results.append(customize_default_wallpapers(config))
    results.append(sync_mobile_wallpaper_from_tv(config))

    print("\n--- [6/12] 设置页作者链接（URL_GITHUB / URL_CNB）---")
    results.append(modify_author_links(config))

    print("\n--- [7/12] 检查更新链接（Github.java / GithubProxy.java / CI 测试）---")
    results.append(modify_update_urls(config))

    print("\n--- [8/12] 更新机制（CNB 优先 manifest + CNB 直连下载 APK + GitHub 兜底路由）---")
    results.append(modify_update_order(config))

    print("\n--- [9/12] sync-cnb-release.sh（CNB_REPO_SLUG）---")
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
    pkg_ok = (pkg == EXPECTED_APPLICATION_ID)
    if not pkg_ok:
        print(f"[ERROR] PACKAGE_NAME 必须是旧 TANG TV 的 {EXPECTED_APPLICATION_ID}，实际为 {pkg!r}")
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

    # —— 发布签名一致性：三重校验 ——
    #    (1) workflow 必须「无 release keystore 即失败」，杜绝 debug 签名混入
    #    (2) workflow 不得回退到旧 KEYSTORE_BASE64（否则两个 secret 可能是不同 key）
    #    (3) CI 里 local.properties 就绪后，用 keytool 硬校验证书指纹 == EXPECTED
    wf_rel = os.path.join(REPO_ROOT, ".github", "workflows", "android-release.yml")
    sign_ok = True
    if os.path.exists(wf_rel):
        with open(wf_rel, "r", encoding="utf-8") as f:
            wf_txt = f.read()
        if "RELEASE_KEYSTORE_BASE64" in wf_txt and "Release signing not configured" in wf_txt:
            print("[OK] android-release.yml 含发布签名硬校验：缺少 keystore secret 时构建直接失败")
        else:
            print("[ERROR] android-release.yml 缺发布签名硬校验")
            sign_ok = False
        # 不得回退到 KEYSTORE_BASE64（RELEASE 为空时回退会切到另一把 key）
        if "RELEASE_KEYSTORE_BASE64:-$KEYSTORE_BASE64" in wf_txt or \
           "RELEASE_KEYSTORE_BASE64:-" in wf_txt:
            print("[ERROR] android-release.yml 仍保留 KEYSTORE_BASE64 回退逻辑，"
                  "不同时间可能切到不同 keystore，导致签名不一致。请改为强制只用 RELEASE_KEYSTORE_BASE64。")
            sign_ok = False
        else:
            print("[OK] android-release.yml 已去掉 KEYSTORE_BASE64 回退，强制只用 RELEASE_KEYSTORE_BASE64")
    # CI 里 local.properties 就绪后才做指纹硬校验（本地开发时文件不存在则跳过）
    fp_ok = verify_signing_keystore(verbose=True)
    if not fp_ok:
        sign_ok = False
    results.append(sign_ok)

    # —— 应用名称一致性：所有 strings.xml 的 app_name 必须固定，防止上游覆盖回原名 ——
    name_ok = True
    expected_names = {
        "values": str(config.get("APP_NAME", "TANG TV")).strip(),
        "values-zh-rCN": str(config.get("APP_NAME_ZH_CN", config.get("APP_NAME", "TANG TV"))).strip(),
        "values-zh-rTW": str(config.get("APP_NAME_ZH_TW", config.get("APP_NAME", "TANG TV"))).strip(),
    }
    for res_dir, expected_name in expected_names.items():
        sp = os.path.join(REPO_ROOT, "app", "src", "main", "res", res_dir, "strings.xml")
        if not os.path.exists(sp):
            print(f"[WARN] {res_dir}/strings.xml 不存在，跳过 app_name 校验")
            continue
        with open(sp, "r", encoding="utf-8") as f:
            stxt = f.read()
        m = re.search(r'<string name="app_name">([^<]+)</string>', stxt)
        if not m:
            print(f"[ERROR] {res_dir}/strings.xml 未找到 app_name")
            name_ok = False
        elif m.group(1).strip() != expected_name:
            print(f"[ERROR] {res_dir}/strings.xml app_name='{m.group(1).strip()}'，应为 '{expected_name}'（会导致桌面图标名称错乱）")
            name_ok = False
        else:
            print(f"[OK] {res_dir}/strings.xml app_name = {expected_name}")
    results.append(name_ok)

    # —— productFlavors 不得覆盖 applicationId（否则不同 flavor 包名不同，无法统一升级）——
    flavors_ok = True
    gradle_path = os.path.join(REPO_ROOT, "app", "build.gradle")
    if os.path.exists(gradle_path):
        with open(gradle_path, "r", encoding="utf-8") as f:
            gtxt = f.read()
        # 提取 productFlavors { ... } 块
        m = re.search(r'productFlavors\s*\{(.*?)\n\s*\}', gtxt, re.DOTALL)
        if m and re.search(r'applicationId', m.group(1)):
            print("[ERROR] productFlavors 块内出现 applicationId 覆盖，不同 flavor 包名不同会导致无法统一升级！")
            flavors_ok = False
        else:
            print("[OK] productFlavors 未覆盖 applicationId（所有 flavor 共用同一包名）")
    results.append(flavors_ok)

    # —— release buildType 必须绑定 signingConfigs.release（不能静默回退 debug）——
    release_sign_ok = True
    if os.path.exists(gradle_path):
        with open(gradle_path, "r", encoding="utf-8") as f:
            gtxt = f.read()
        # 先定位 buildTypes { ... } 块，再在其内找 release { ... }
        bt = re.search(r'buildTypes\s*\{(.*?)\n    \}', gtxt, re.DOTALL)
        if bt:
            rb = re.search(r'release\s*\{(.*?)\n        \}', bt.group(1), re.DOTALL)
            if rb:
                rbody = rb.group(1)
                if 'signingConfigs.release' not in rbody:
                    print("[ERROR] release buildType 未绑定 signingConfigs.release，可能静默用 debug 签名！")
                    release_sign_ok = False
                else:
                    print("[OK] release buildType 绑定 signingConfigs.release")
                # 只有直接 signingConfig = signingConfigs.debug（无三元 release 判断）才报错
                if re.search(r'signingConfig\s*=\s*signingConfigs\.debug\s*$', rbody, re.MULTILINE):
                    print("[ERROR] release buildType 直接使用 signingConfigs.debug，会产出 debug 签名包！")
                    release_sign_ok = False
            else:
                print("[ERROR] buildTypes 内未找到 release 块，无法确认发布签名配置")
                release_sign_ok = False
        else:
            print("[ERROR] 未找到 buildTypes 块，无法确认发布签名配置")
            release_sign_ok = False
    results.append(release_sign_ok)

    # —— 单一入口 CI 接线硬校验：旧脚本不得再被 GitHub Actions 调用 ——
    wf_text = ""
    if os.path.isfile(wf_rel):
        with open(wf_rel, "r", encoding="utf-8") as fh:
            wf_text = fh.read()
    workflow_entry_ok = (
        "python3 scripts/gen_app_icon.py --verify-signing" in wf_text
        and "python3 scripts/gen_app_icon.py --verify-apk-signature" in wf_text
        and "python3 custom/local_customize.py" not in wf_text
        and "Regenerate icons from custom script" not in wf_text
    )
    if workflow_entry_ok:
        print("[OK] android-release.yml 全部使用 gen_app_icon.py；旧 local_customize/Pillow 入口已退出")
    else:
        print("[ERROR] android-release.yml 仍未完全切换到单一入口或缺少签名后验校验")
    results.append(workflow_entry_ok)

    version_code_ok = True
    if os.path.isfile(gradle_path):
        with open(gradle_path, "r", encoding="utf-8") as fh:
            gtxt_vc = fh.read()
        want_vc = str(config.get("VERSION_CODE", "")).strip()
        m_vc = re.search(r"\bversionCode\s*=?\s*([0-9]+)", gtxt_vc)
        version_code_ok = bool(m_vc and (not want_vc or m_vc.group(1) == want_vc))
        if version_code_ok:
            print(f"[OK] versionCode={m_vc.group(1)}，不低于本次配置的升级版本号")
        else:
            print(f"[ERROR] versionCode 不匹配：期望 {want_vc}，实际 {m_vc.group(1) if m_vc else '未找到'}")
    results.append(version_code_ok)

    # —— 旧版覆盖安装安全门禁：包名/版本号/签名必须分别核对 ——
    # 本地没有 local.properties 时允许完成源码配置，但不声称签名已验证；
    # CI 会在注入 RELEASE_KEYSTORE_BASE64 后执行 --verify-signing，且必须配置旧 APK 指纹。
    expected_cert_pin = str(config.get("EXPECTED_RELEASE_CERT_SHA256", EXPECTED_RELEASE_CERT_SHA256)).strip().replace(":", "").upper()
    signing_pin_ok = bool(re.fullmatch(r"[0-9A-F]{64}", expected_cert_pin))
    if signing_pin_ok:
        print("[OK] 已配置旧版 TANG TV 证书 SHA-256 锁定值；CI 将核对 Release keystore 与新 APK")
    else:
        print("[WARN] 尚未配置旧版 APK 的证书 SHA-256。当前不能证明新 APK 可覆盖旧安装；")
        print("       请从旧 APK 提取 Signer certificate SHA-256，写入 custom/config.env 的 EXPECTED_RELEASE_CERT_SHA256。")
        print("       为防止签名不一致的 APK 发布，CI 的 --verify-signing 将拒绝未配置指纹的 Release。")

    hard_checks = {
        "namespace": ns_ok,
        "applicationId": pkg_ok,
        "Release 工作流签名配置": sign_ok,
        "应用名称": name_ok,
        "productFlavors 包名": flavors_ok,
        "release buildType 签名": release_sign_ok,
        "CI 单一入口与 APK 验签": workflow_entry_ok,
        "versionCode": version_code_ok,
    }
    failed_checks = [label for label, ok in hard_checks.items() if not ok]

    # 所有硬性校验都必须阻断失败；EXPECTED_RELEASE_CERT_SHA256 在纯本地源码阶段
    # 仍只是警告，但 CI 的 --verify-signing / --verify-apk-signature 会强制要求它。
    if not icon_ok or FAILURES or failed_checks:
        print("\n" + "=" * 72)
        if not icon_ok:
            print("  [ERROR] 图标生成失败或一致性校验未通过（实际图标与预览不一致）。")
        if failed_checks:
            print("  [ERROR] 最终硬性校验未通过：" + "、".join(failed_checks))
        if FAILURES:
            print(f"  [ERROR] 共 {len(FAILURES)} 项处理失败：")
            for _msg in FAILURES:
                print(f"    · {_msg}")
        print("  本次运行以非零码退出，请勿提交；请按上方 [ERROR]/[verify] 的 FAIL 项排查后重跑。")
        print("=" * 72)
        sys.exit(1)

    print("\n" + "=" * 72)
    if not failed_checks and signing_pin_ok:
        print("  [DONE] 自定义修改完成；包名/名称/namespace/版本号/Release 工作流/签名指纹锁定均通过。")
    elif any(results):
        print("  [DONE] 本地自定义步骤已完成，但尚有 [WARN] 项；不得据此认定旧版覆盖签名已验证。")
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
    # --verify-signing：仅校验 release keystore 证书指纹是否与 EXPECTED 一致（CI 用）
    if "--verify-signing" in sys.argv:
        load_config_env()
        ok = verify_signing_keystore(verbose=True)
        sys.exit(0 if ok else 1)
    if "--verify-apk-signature" in sys.argv:
        load_config_env()
        try:
            apk_index = sys.argv.index("--verify-apk-signature")
            apk_file = sys.argv[apk_index + 1]
        except (ValueError, IndexError):
            print("[ERROR] 用法：python scripts/gen_app_icon.py --verify-apk-signature path/to/app.apk")
            sys.exit(2)
        sys.exit(0 if verify_signed_apk(apk_file, verbose=True) else 1)
    # --show-signing-fingerprint：打印当前 release.jks 的证书 SHA256 指纹（首次配置用）
    if "--show-signing-fingerprint" in sys.argv:
        load_config_env()
        fp, store, alias, err = get_release_keystore_fingerprint()
        if fp is None:
            print(f"[ERROR] 无法获取 keystore 指纹: {err}")
            print("        请先在 CI 里跑一次（local.properties 就绪后），或本地配置好 release.jks。")
            sys.exit(1)
        print(f"keystore: {store}")
        print(f"alias:    {alias}")
        print(f"SHA256:   {fp}")
        print()
        print("把上面这串指纹填到脚本常量 EXPECTED_RELEASE_CERT_SHA256 后提交，")
        print("以后 CI 每次构建都会硬校验此指纹，不匹配直接失败。")
        sys.exit(0)
    if "--help" in sys.argv or "-h" in sys.argv:
        print("WebHTV gen_app_icon.py 单一入口：默认执行完整自定义；--force 强制重写；--verify 仅校验图标；--preview 导出预览；--export 导出完整图标；--icons-only 仅安装图标；--verify-signing 校验证书；--verify-apk-signature 校验最终 APK；--show-signing-fingerprint 显示证书指纹。")
        sys.exit(0)
    if "--verify" in sys.argv:
        load_config_env(); _ok, _ = verify_icons("image", verbose=True)
        sys.exit(0 if _ok else 1)
    elif "--export" in sys.argv:
        load_config_env(); do_export("image")
    elif "--preview" in sys.argv:
        load_config_env(); do_preview("image")
    elif "--icons-only" in sys.argv:
        load_config_env(); do_write("image")
    else:
        main()
