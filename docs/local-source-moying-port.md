# 本地源（魔影式）复刻

## 完成句
把魔影底栏“本地源”复刻进墨影视：底栏常驻本地源入口，点开弹窗可扫描本地文件夹里的源文件，扫到的源直接追加到当前点播配置的站点列表末尾，不生成独立配置文件。

## Recovery anchor
- 目标：按魔影实现复刻本地源，替换已回退的 MuseTV“生成配置文件”那套（那套保存在分支 save/20261106-08660805）。
- 当前分支/HEAD：main / cad200df（2026-11-06 15:06 回退后状态，工作区干净）。
- 已完成：反编译分析魔影 APK（com.lanmo.android.lab v5.6.0），引擎 LocalSource.java 已新建（app/src/main/java/com/fongmi/android/tv/utils/LocalSource.java）。
- 待做：弹窗 UI + 适配器 + 布局、底栏 local 项、VodConfig 追加、字符串、图标；静态校验；本地提交（不推，等用户说推）。
- 已完成：反编译分析魔影 APK（com.lanmo.android.lab v5.6.0），引擎 LocalSource.java 已新建（app/src/main/java/com/fongmi/android/tv/utils/LocalSource.java）；弹窗 LocalSourceDialog + 适配器 + 两布局已建；底栏 local_source 项已加（menu_nav + HomeActivity 三处 + 玻璃栏）；VodConfig.initSite 已追加本地源；三语字符串已加；图标 ic_nav_local.png 已从恢复标签取回（用户发的 Files 图）；静态校验通过（6 个 XML 解析通过、绑定字段与布局 id 逐项对过、R.id.local_source 改名避开 dialog_apk_push_method 里已有的 R.id.local、Path.write 改成 byte[] 重载、补 App import、删未用的 NonNull import）。
- 验收：底栏出现本地源入口；扫文件夹能导入源；导入后首页站点列表出现本地源；密源默认不显示；删源后重载配置即消失。
- 回滚：本任务提交可整笔 revert；MuseTV 那套在 save/20261106-08660805 分支。
- 下一步：task_guard finish 提交（本地，不推），然后报给用户，等他说推再推、再编测试版。

## 研究（设计依据）
- 来源：魔影 APK（com.lanmo.android.lab，v5.6.0，webhtv 同源）反编译，见 ~/workspace/moying-analysis/。
- 关键类：ej2（LocalSourceDialog）、uf（引擎：sites.json 存取 + uf.B 解析）、gj2（递归收集 + 白名单 + 屏蔽目录）、fj2（分类映射 + 本机地址）、up5（配置加载时追加）、qd0（列表适配器）、zl4（本机 HTTP 服务 9978–9998）。
- 存储：filesDir/localSource/sites.json（sites 数组 + showSecret + scanDir + phpRoot），不用 SharedPreferences。
- 扫描白名单：wv.js、cat.js、xbpq.json、xyq.json、php、html、js、py、json；屏蔽约 50 个目录名（Android、DCIM、微信等）。
- 解析映射：.js→drpy type 3；.xbpq/.xyq→csp_XYQHiker type 0；.php→type 4（api 走本机服务）；.json/.txt→配置文件提 sites；[直播]跳过、[密]默认跳过；[...]标签变分类写成“名字┃[分类]”。
- 生效：配置加载时把 sites.json 的源追加到站点列表末尾（密源未开开关时过滤），api/ext 的 file:// 地址在读出时按当前本机服务端口换成本机地址。
- 方案比较：不做（保持回退后无本地源状态）/ 照搬魔影（本任务采用，改动最小且与墨影视现有 Local 服务、VodConfig、FileChooser 完全对得上）/ 继续用 MuseTV 生成配置文件那套（已回退，保留在分支，两套会打架故不用）。
- 风险：.php 源无 PHP 解释器，能否真播待实测；扫描全部默认扫外置存储根目录较慢，本任务默认只扫用户选的目录；.py/.html 用通用映射，属尽力而为。

## 范围
- 新建：app/src/main/java/com/fongmi/android/tv/utils/LocalSource.java
- 新建：app/src/mobile/java/com/fongmi/android/tv/ui/dialog/LocalSourceDialog.java
- 新建：app/src/mobile/java/com/fongmi/android/tv/ui/adapter/LocalSourceAdapter.java
- 新建：app/src/mobile/res/layout/dialog_local_source.xml、item_local_source.xml
- 新建：app/src/mobile/res/drawable-nodpi/ic_nav_local.png（从恢复标签取用户发的 Files 图）
- 修改：app/src/mobile/res/menu/menu_nav.xml、app/src/mobile/java/com/fongmi/android/tv/ui/activity/HomeActivity.java、app/src/main/java/com/fongmi/android/tv/api/config/VodConfig.java、app/src/main/res/values/strings.xml、app/src/main/res/values-zh-rCN/strings.xml、app/src/main/res/values-zh-rTW/strings.xml
- 本文档：docs/local-source-moying-port.md

## 时间与验证
- 开始：2026-11-06 15:36 CST。预计本地实现约 40–60 分钟，随后等用户确认再推、再编测试版（构建另计约 20 分钟）。
- 最便宜的决定性验证：本地无 SDK，编不了。静态验证：全部 XML 解析通过、Java 引用逐项核对（R.id、绑定类、FileChooser、VodConfig 追加点）、git diff 复查；真正编译与设备验证走 GitHub Actions 构建 + 用户手机实测。
