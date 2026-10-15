# C69 · dev3 合并 beta 最新代码与「电视版站点选择面板」4 提交复评

- 任务 ID：`C69-beta-merge-review-dev3-20261014`
- 分支：`dev3`；本任务开始前 tip = `e84eb4f3e7311cce835712d94dd42165d1d98885`
- 合并对象：`origin/beta` = `a8c0d6a5fe23418027c17ce7ee0e4e1ceb5b205e`（`Merge pull request #444 from Silent1566/dev3`）
- 复评对象：dev3 已提交未推送的 4 个「电视版站点选择面板」提交（`3ca1da02c3`、`b66a3397e2`、`7d7c17ef15`、`e84eb4f3e7`）
- 访问日期：2026-10-14（Asia/Shanghai）

## Recovery anchor

- 目标：合并 `origin/beta` 最新代码（远端已移除/回退的提交不得顺带提交上去）；对 dev3 已提交未推送的 4 个提交做 Standards + Spec 双轴复评，修正问题并验证通过，再复评至通过；然后提交、推送 `dev3`、创建到 `beta` 的 PR（只创建不合并）。
- 允许路径：`app/src/leanback/**`、`app/src/main/res/values/strings.xml`、`app/src/main/res/values-zh-rCN/strings.xml`、`app/src/main/res/values-zh-rTW/strings.xml`、`app/src/testMobile/java/com/fongmi/android/tv/ui/dialog/SiteDialogLayoutTest.java`、`docs/TV-SITE-DIALOG-PANEL-20261014.md`、本文、`docs/upstream-player-dependency-merge-assessment-2026-08-20.md`。
- 保护既有脏文件：0 个（任务开始时 `git status --porcelain` 为空）。
- 验收标准：合并后净差异不含被 beta 回退的提交内容（零复活、零丢失）；复评发现的阻塞/重要问题全部修正并跑通定向单测；`dev3` 推送成功且 PR 已创建（不合并）。
- 当前状态：**已实施、已验证、已交付**（合并为空内容合并；双轴复评得到 1 项重要 + 8 项次要问题并全部修正；mobile 定向 10/10、leanback 定向 69/69）。
- 下一步唯一动作：无，见文末「交付坐标」。

## 1. 合并范围：beta 只多一个「把 dev3 合进 beta」的合并提交

`origin/beta` 的 tip `a8c0d6a5fe` 是一个**双父合并提交**，两个父分别是 `f398ced4dd`（旧 beta）与 `2ea9700e5d`（dev3 当时的 tip）：

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 远端 beta tip | `git rev-parse origin/beta` | `a8c0d6a5fe23418027c17ce7ee0e4e1ceb5b205e` |
| 远端 dev3 tip | `git rev-parse origin/dev3` | `2ea9700e5d78e0aac8c0c6aaa8e11db278b8593a` |
| beta tip 的父 | `git rev-list --parents -n1 origin/beta` | `a8c0d6a5fe f398ced4dd 2ea9700e5d`（双父） |
| merge-base | `git merge-base HEAD origin/beta` | `2ea9700e5d…` |
| beta 领先 dev3 | `git rev-list --count HEAD..origin/beta` | `1`（只有那个合并提交本身） |
| dev3 领先 beta | `git rev-list --count origin/beta..HEAD` | `4`（即本轮复评对象） |
| 合并预演 | `git merge --no-ff --no-commit origin/beta` | exit 0，`Automatic merge went well`，产生 `MERGE_HEAD` |
| 合并结果净差异 | `git diff --cached --name-status` | **空** |
| 树对象一致性 | `git write-tree` vs `git rev-parse dev3^{tree}` | 均为 `57194a00e9…`（**逐字节相同**） |

即：beta 相对 dev3 没有带入任何新内容，合并结果与 dev3 原树完全一致，无冲突。

## 2. 零复活 / 零丢失（四层证据）

用户明确要求：远端已移除/回退的提交不得顺带提交上去。

| 层 | 判据 | 结果 |
| --- | --- | --- |
| 1 · 净差异 | `git diff --name-status origin/beta dev3` | **13** 个路径（11 修改 + 1 新增测试 + 1 新增文档 `docs/TV-SITE-DIALOG-PANEL-20261014.md`），全部为本轮意图内的站点面板文件 |
| 2 · 零丢失（blob 级） | beta tip 的 **5063** 个文件逐一与 dev3 树比对 | 缺失 **0**；dev3 树 5064 个文件（多出的 1 个即本轮新增文档） |
| 3 · 零复活（内容级，最强判据） | `git diff --name-only 2ea9700e5d origin/beta` | **空**——beta 相对其 dev3 父提交**零内容差异**，因此结构上不可能带入任何被回退的内容 |
| 4 · 零复活（文件级） | beta 历史删除过的 **622** 个文件路径 ∩ 本 diff 的 **15** 个改动路径 | 交集 **1**，但经逐项核实为**误报**（见下），真实复活 **0** |

第 4 层的那个交集是 `docs/upstream-player-dependency-merge-assessment-2026-08-20.md`。它是**误报**，三条证据：

1. 该文件**存在于 beta tip**（`git cat-file -e origin/beta:<path>` exit 0）；
2. 本 diff 对它的操作是 **`M`（修改）**，不是 `A`（新增）——只有「beta tip 没有、我们却加回来」才可能是复活；
3. beta 历史里删除它的是 `784b90420d chore: remove local docs from remote`，此后该路径又被多次改动（`5a5ce47394` 等），即 beta 自己后来已经把它放回来了；本轮的改动只是给评估索引加 1 行 C69 记录。

更严格的判据（本轮补充执行）：按**操作类型**而不是「历史上是否被删过」来判定——

| 操作 | 路径数 | 其中 beta tip 不存在的 |
| --- | --- | --- |
| `A` 新增 | 2（`docs/C69-beta-merge-review-dev3-20261014.md`、`docs/TV-SITE-DIALOG-PANEL-20261014.md`） | 2，但两者**都不是 beta 历史删除过的路径**，属本轮全新文档，非复活 |
| `M` 修改 | 13 | **0**（全部存在于 beta tip） |
| `D` 删除 | 0 | — |

即：真正可能构成复活的两个形状——「beta tip 缺失却被我们加回」且「该路径曾是 beta 的删除项」——都为空。加上第 3 层「beta 相对其 dev3 父提交零内容差异」这一结构性证据，可以确认**零复活**。

第 3 层是本轮最强判据：`a8c0d6a5fe` 的树与 dev3 祖先 `2ea9700e5d` 的树**逐字节相同**（`f223f0aeba…`），说明这次合并只是把 dev3 已有的内容并入 beta，反向合并回来不携带任何新内容。

## 3. 复评：dev3 已提交未推送的 4 个站点面板提交

评审按 `code-review-zh` 的 **Standards / Spec 双轴**分别进行（两个轴各自独立成篇，不合并结论），各委派一个独立子代理并行执行。

### 3.1 第 1 轮：Standards 轴

Standards 子代理**中途失败未返回**（`f71aadf7`），因此该轴由主会话按同一套标准与坏味道基线直接执行，证据全部来自仓库内可复现路径。

| 编号 | 严重度 | 问题 | 事实链 |
| --- | --- | --- | --- |
| S1 | **重要** | `SiteDialogLayoutTest.siteGridHeightSnapsToWholeRowsSoTheLastRowIsNotClipped()` 的第三条断言是**恒真断言（tautology）**，永远不可能失败，因此完全锁不住它声称要锁的「网格不再被拉伸」回归 | ① 仓库开 `core.autocrlf=true`，git blob 是 LF 而 **Windows 工作区检出为 CRLF**（字节级实测：`SiteDialog.java` 工作区 CRLF=811 / 裸 LF=0；`HEAD` blob CRLF=0 / 裸 LF=811）；② Java 字面量里的 `"\n"` 是单个 LF，而测试读的是工作区文件，跨行处实为 `\r\n`，needle 永不匹配；③ 反向复算：把 `origin/beta` 的旧版 `SiteDialog.java` 还原成工作区 CRLF 形态后，修复前 needle 匹配 = **False**（断言通过，即无锁），修复后（归一化 LF）匹配 = **True**（断言失败，即真锁） |

### 3.2 第 1 轮：Spec 轴

| 编号 | 严重度 | 问题 | 事实链 |
| --- | --- | --- | --- |
| P1 | **重要** | `docs/TV-SITE-DIALOG-PANEL-20261014.md` 的 `Recovery anchor` 验收项 ②「面板四周留出安全边距且**宽度有上限**」与 §9「**删除 `PANEL_MAX_WIDTH_DP`**、不设 dp 上限」自相矛盾；`SiteDialogLayoutTest` 甚至反向断言 `PANEL_MAX_WIDTH_DP` 不得出现 | 文档 L8 vs L133；`SiteDialog.java:64-66` 只有 `PANEL_WIDTH_RATIO=0.9f` 与 `PANEL_MIN_WIDTH_DP=480` |
| P2 | 次要 | §6.2 实测表仍写「命中 `PANEL_WIDTH_RATIO=0.82`」「低于 `PANEL_MAX_HEIGHT_RATIO=0.74`」，与代码的 `0.9f`/`0.9f` 冲突；`e84eb4f3e7` 只改了 §9，未同步 §6.2 | `SiteDialog.java:64,71`；`e84eb4f3e7` 的 diff |
| P3 | 次要 | §3 方案比较的 0.82 / 1180dp / 0.74 与 §2 的 `PANEL_MARGIN_DP = 24` 均未落地（全仓无该常量），文档未随 §9 回改 | 全仓 grep `PANEL_MARGIN_DP` 仅命中文档自身 |
| P4 | 次要 | §9「真机电视常见 density 1.0」与 §3/§6.2「电视常见 density 2.0」直接矛盾 | 文档 L47 / L83 与 L131 |
| P5 | 次要 | §8「32px ≈ 16dp（14dp padding + 1dp 描边）」算术不符：14+1=15dp，density 2.0 下为 30px | 文档 §8 |
| P6 | 次要 | §5 把 `GRID_COUNT` 断言归给 `HomeMenuDialogSourceTest`，但该测试读取的是 `HomeMenuDialog.java` | `HomeMenuDialogSourceTest.java:86-88` 读 `HomeMenuDialog.java` |
| P7 | 次要 | §4 步骤 3 称「文字色改语义 `?attr/colorOnSurface`」，实际用的是 `@color/site_item_text` selector | 两个 `adapter_site*.xml` 的 `textColor` |
| P8 | 次要 | §7 仍称「待用户确认后 finish 提交」，但 4 个提交与 4 个 recovery tag 均已存在 | `git tag --points-at` 四个提交均有 tag |

Spec 轴同轮**经核实不成立**的一条（记录取舍，不改）：`adapter_site*.xml` 字号 18sp→17sp、`groupHint` 14sp→13sp、健康点 `marginEnd` 8dp→10dp、勾选框 `marginStart` 12dp→10dp、recycler padding 调整被判为「范围蔓延」。**不成立**：这些是 §3 已批准的「卡片内容左对齐、健康点紧贴站名、按收窄后的面板重新排布间距」在实现时的必要组成——面板由全屏收窄到 90% 后，原字号与间距是为全屏宽度调的，不收紧就会出现文字过挤与标签行溢出（正是 §9 修掉的那类问题）。已在 §4 步骤 3 补记这些取值，使其成为有据可查的实现细节。

### 3.3 修复

| 编号 | 修改 |
| --- | --- |
| S1 | `SiteDialogLayoutTest` 新增私有助手 `read(Path)`，读取后 `.replace("\r\n", "\n")` 归一化行尾，四个测试统一走它；助手带 Javadoc 说明为何必须归一化。与**同包**既有写法一致（`SiteDialogSelectionScrollSourceTest`、`SiteDialogThemeSourceTest` 等 **16 个**测试文件在本次修复前就已用同一套归一化，属仓库既有约定而非新造；加本文件后共 17 个） |
| P1 | `Recovery anchor` 验收项 ② 改为「宽度按屏宽比例收敛（0.9）且极窄屏有下限兜底（不设 dp 上限，见 §9）」 |
| P2 | §6.2 实测表加注「本表是第一轮（0.82 / 0.74）的实测」，判定列改为「命中当时的常量」；实测数字保留原貌（各轮当时的真实测量） |
| P3 | §3 加注第一轮取值已在 §9 改为 0.9 / 无上限 / 0.9；§2 的 `PANEL_MARGIN_DP = 24` 行注明该常量已随「比例优先」结论删除 |
| P4 | §9 改为「density 并不统一：本仓库实测的 1080p 模拟器是 density 2.0，而不少电视盒子/电视按 density 1.0 渲染」，消除自相矛盾 |
| P5 | §8 算术更正为「14dp + 1dp = 15dp，density 2.0 下为 30px；实测 32px 含取整与边框像素」 |
| P6 | §5 更正为该测试断言的是 `HomeMenuDialog.java` 的同名常量 |
| P7 | §4 步骤 3 更正为实际实现（语义 selector `@color/site_item_text`，常态项即 `?attr/colorOnSurface`，另含焦点/选中两态），并补记同轮字号与间距收紧 |
| P8 | §7 更正为提交与 tag 均已存在，并新增 §11 交付坐标表 |

### 3.4 第 2 轮：修复后复审

对**本轮改动**（2 个文件：1 个测试、1 份文档）重新过两轴：

- **Standards**：S1 修好后，`SiteDialogLayoutTest` 的四个断言全部是**可失败的**真断言——其中第三条已用**变异测试**证明：把 `params.height = gridHeight(count);` 改回 `MATCH_PARENT` 后，该断言如期失败（`4 tests completed, 1 failed`），改回后恢复通过。其余三条断言均为单行 needle，不受行尾影响。测试文件无重复代码、无过时注释、无神秘命名。
- **Spec**：P1–P8 修好后，`Recovery anchor` 的验收项与 §9 的最终取值一致；§2/§3/§6.1/§6.2/§8 的历史记录均加了「第一轮取值」的时间限定，不再与最终取值冲突；§5 的断言归属、§4 的文字色描述、§7 的状态描述均与代码/仓库事实一致。
- **无新增阻塞或重要问题。**

## 4. 验证

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 修复前基线（mobile 定向） | `.\gradlew.bat :app:testMobileArm64_v8aDebugUnitTest --tests "com.fongmi.android.tv.ui.dialog.SiteDialog*"` | `BUILD SUCCESSFUL in 1m 1s`，exit 0；`SiteDialogLayoutTest` 4/4、`SiteDialogThemeSourceTest` 5/5、`SiteDialogSelectionScrollSourceTest` 1/1，**10 例 / 0 失败**（逐套件读取 `build/test-results` XML 核对，非仅看 Gradle 退出码） |
| **变异测试（S1 的决定性验证）** | 把 `params.height = gridHeight(count);` 变异回 `MATCH_PARENT` 后重跑 `SiteDialogLayoutTest` | `SiteDialogLayoutTest > siteGridHeightSnapsToWholeRowsSoTheLastRowIsNotClipped FAILED`、`4 tests completed, 1 failed`——**证明修复后的断言是真锁**；随后还原文件并确认无 `MATCH_PARENT` 残留 |
| 修复后复验（mobile 定向） | 同上 | `BUILD SUCCESSFUL in 16s`，exit 0 |
| 修复后复验（leanback 定向 + 资源/Java 编译） | `.\gradlew.bat :app:testLeanbackArm64_v8aDebugUnitTest --tests "com.fongmi.android.tv.ui.dialog.*"` | `BUILD SUCCESSFUL in 1m 18s`，exit 0；`compileLeanbackArm64_v8aDebugJavaWithJavac` 执行；15 个套件 **69 例 / 0 失败**（含 `SiteDialogActionFocusTest` 3/3、`SiteDialogThemeSourceTest` 2/2、`HomeMenuDialogSourceTest` 5/5） |
| 交付面 | `git diff --name-status origin/beta` + `git ls-files --others --exclude-standard` | 见文末交付坐标 |
| 空白卫生 | `git diff --check` | exit 0 |

关于「为何单测没暴露 S1」：恒真断言在 CRLF 工作区里**始终通过**，只有把断言逻辑对着**旧代码**复算、或做变异测试才会暴露。因此本次用「旧代码必须失败 / 变异体必须失败」这一反向判据验证修复，而不是只看测试是否变绿。

## 5. best-practice 依据

`AGENTS.md` §7 的设计研究门对本轮**不触发**：本轮是「合并 + 复评既有改动」，不是新的上游候选或新的用户可见能力；改动面是 1 个测试助手方法 + 1 份文档，设计已由 `TV-SITE-DIALOG-PANEL-20261014.md` §3 决策表确定。

S1 的修法依据全部是**仓库内一手来源**：

| 编号 | 来源（可复现路径） | 证据等级 | 支持的结论 | 对 WebHTV 的适用性 | 局限 |
| --- | --- | --- | --- | --- | --- |
| E1 | `app/src/testMobile/java/com/fongmi/android/tv/ui/dialog/SiteDialogSelectionScrollSourceTest.java:29-32`、`SiteDialogThemeSourceTest.java` 等共 **16 个**测试文件（本次修复前） | 一手（仓库既有约定） | 读取源文件做断言时统一 `.replace("\r\n", "\n")` 归一化行尾 | 直接适用：`SiteDialogLayoutTest` 是同包同类测试，此前是唯一漏掉归一化且带跨行断言的 | 该约定未写成文档，仅由既有代码体现 |
| E2 | `git config core.autocrlf` = `true`；`.gitattributes` 只声明 `*.patch whitespace=...` | 一手（仓库配置） | 工作区是 CRLF、blob 是 LF，跨行 needle 必须归一化 | 直接适用：解释了 S1 的成因 | 依赖开发机 `core.autocrlf=true`；若某机为 `false`，修复前的断言反而会「偶然生效」，更说明必须归一化 |
| E3 | 字节级实测：`SiteDialog.java` 工作区 CRLF=811 / 裸 LF=0；`HEAD` blob CRLF=0 / 裸 LF=811 | 一手（实测） | 证实 E2 的实际后果 | 直接适用 | 仅覆盖该文件；同目录其他文件同形 |

方案比较（针对 S1）：

| 方案 | 内容 | 正确性 | 兼容性/性能 | 维护与可验证性 | 结论 |
| --- | --- | --- | --- | --- | --- |
| no change | 保留跨行 needle | 断言恒真，零回归保护 | 无变化 | 看起来有测试，实际无锁 | 否 |
| 把断言改成单行 needle | 只匹配 `params.height = gridHeight(count);` | 可失败，但只锁「这一行存在」，锁不住「后面紧跟 `setLayoutParams`」这一组合 | 无变化 | 单个断言，语义偏弱 | 否 |
| **归一化行尾（采纳）** | 新增 `read(Path)` 助手统一归一化 | 断言恢复真实语义，**变异测试证明可失败** | 纯测试代码，无运行时影响 | 与同包 16 个测试的既有写法一致，一行助手覆盖全部四个测试 | **采纳** |

## 6. 回归锁

`SiteDialogLayoutTest` 4 个测试方法（本轮未增删方法，而是**修好了其中 1 个恒真断言**）：

- `siteDialogUsesCenteredPanelInsteadOfFullScreen`：锁住窗口必须 `Gravity.CENTER` + `WRAP_CONTENT`，且不得出现 `MATCH_PARENT` 宽/高。
- `siteDialogLeavesSafeMarginsAndCapsItsWidth`：锁住宽度按 `PANEL_WIDTH_RATIO = 0.9f` 比例、**不得**再有 `PANEL_MAX_WIDTH_DP`、必须有 `PANEL_MAX_HEIGHT_RATIO`。
- `siteGridHeightSnapsToWholeRowsSoTheLastRowIsNotClipped`：锁住 `gridHeight(int)` 与 `gridBudgetHeight()` 存在，且网格**不得**再被 `MATCH_PARENT` 拉伸（**本轮修复的恒真断言，已用变异测试证明可失败**）。
- `siteCardsDeclareHorizontalPaddingOnTheViewNotOnlyOnTheBackground`：锁住两个卡片布局必须显式声明水平 padding。

## 7. 残留未知与已知限制

- **未做设备实测**：本轮是「合并 + 复评 + 源码/测试/文档级修正」，没有重跑 `TV-SITE-DIALOG-PANEL-20261014.md` §6.2/§9 的设备矩阵。S1 是纯测试代码修正，其行为已用变异测试在 JVM 侧证明；站点面板在真机电视上的遥控手感与过扫描观感仍属设备侧结论，本轮未复现。
- **Standards 子代理未返回**：`f71aadf7` 中途失败，Standards 轴由主会话直接执行；Spec 轴子代理 `15f5ca32` 正常返回。两轴证据均可在仓库内复现（§3.1 的字节级实测与 §4 的变异测试）。
- **文档历史记录保留原貌**：§6.2 与 §9 的实测表保留各轮当时的真实测量数字，只加时间限定注记，不逐格改写历史会话日志。

## 8. 回滚

- 代码回滚锚点：本任务开始前 `dev3` tip `e84eb4f3e7311cce835712d94dd42165d1d98885`；`git revert` 本任务提交即可恢复复评前状态（1 个测试助手方法 + 1 份文档）。
- 文档回滚：删除本文，并撤销对 `docs/TV-SITE-DIALOG-PANEL-20261014.md` 的 §10/§11 与各处注记。
- 不涉及 Media3/nextlib AAR、FFmpeg、MPV native、lock、native 二进制或音频路由。

## 9. 实施记录

- 2026-10-14 19:18 (+08:00)：确认工作区干净；`git fetch --all --prune` 后 `origin/beta` = `a8c0d6a5fe`（双父合并提交）。
- 2026-10-14：guard `C69-beta-merge-review-dev3-20261014`（upstream）启动，基线 `e84eb4f3e7`，保护面 0 个既有脏文件。
- 2026-10-14：合并预演产生 `MERGE_HEAD`；合并结果净差异为空、树对象与 dev3 相同，确认为零内容合并。
- 2026-10-14：零复活/零丢失四层证据完成（净差异 13 路径、缺失 0、beta 相对 dev3 父零内容差异、revert 文件级交集 0）。
- 2026-10-14：**交付后终验**补做更严格的「按操作类型」零复活判据（`A`/`M`/`D` 分别对 beta tip 校验）。终验时 diff 已从 13 路径增至 15（新增 C69 文档与评估索引 1 行），文件级交集因此从 0 变为 1——经逐项核实为误报（该文件存在于 beta tip 且本轮只是 `M` 修改）。已把结论与误报说明写回 §2。
- 2026-10-14：双轴复评（Spec 子代理正常返回；Standards 子代理失败，由主会话执行）得到 S1 + P1–P8。
- 2026-10-14：完成 9 处修复（1 个测试助手 + 8 处文档更正）。
- 2026-10-14：修复前基线 10/10 通过；**变异测试证明 S1 修复后断言可失败**；修复后 mobile 定向与 leanback 定向（69/69）全部通过。
- 2026-10-14：第 2 轮复审发现并修正 2 处**本轮自己引入**的文档结构问题——`§7` 被新章节挤到文档中部（该文档的既有惯例是 §7 收尾）、以及一处指向 C69 文档不存在章节的交叉引用（`§交付坐标` → `§9 实施记录`）；修正后章节顺序恢复为 §1–§6、§8–§11、§7 收尾。
- 2026-10-14：guard `finish` → 双父合并提交 `aa7a0b56f19fe5fa7bde2378586f34f523e8fa01`（父 = `e84eb4f3e7` + `a8c0d6a5fe`）+ recovery tag `recovery/C69-beta-merge-review-dev3-20261014/20261014122252-aa7a0b56f19f`。
- 2026-10-14：`git push origin dev3`（`2ea9700e5d..aa7a0b56f1`）+ 推送 recovery tag；创建 PR [#445](https://github.com/Silent1566/webhtv/pull/445)（base `beta`，15 个文件，**只创建不合并**）。
- 环境注记：本机环境变量 `GIT_CONFIG_COUNT=2` 缺 `GIT_CONFIG_KEY_*`，所有 git 命令前需清空该变量；guard 用 `G:\Git\bin\bash.exe` 执行；Gradle 用 `gradlew.bat`（`JAVA_HOME` = JDK 21）；`gh` 未设默认仓库，`gh pr create` 必须显式带 `--repo Silent1566/webhtv`（否则报 `Head sha can't be blank`）。

## 10. 交付坐标

| 项 | 值 |
| --- | --- |
| 合并+修正提交 | `aa7a0b56f19fe5fa7bde2378586f34f523e8fa01`（**双父**：父₁ = `e84eb4f3e7`，父₂ = `a8c0d6a5fe`） |
| recovery tag | `recovery/C69-beta-merge-review-dev3-20261014/20261014122252-aa7a0b56f19f` |
| 推送 | `git push origin dev3` → `2ea9700e5d..aa7a0b56f1  dev3 -> dev3`；`git rev-parse origin/dev3` == `git rev-parse dev3` == `aa7a0b56f1…` |
| PR | [#445](https://github.com/Silent1566/webhtv/pull/445)（`dev3` → `beta`，**只创建，未合并**） |

## 闭环记录

| 复核项 | 结果 |
| --- | --- |
| `git rev-list --parents -n1 aa7a0b56f1` | **双父**（`e84eb4f3e7` `a8c0d6a5fe`）——本轮 beta 有真实新提交，故产生真合并提交（与 C66/C68 的「空操作」形态不同） |
| `git merge-base --is-ancestor origin/beta HEAD`（收尾） | **真**（exit 0） |
| `MERGE_HEAD` | 已清除 |
| 合并结果树 | `11500cea39…`（含本轮文档/测试修正）；合并前的零内容性已由「预演时 `git write-tree` == `dev3^{tree}` == `57194a00e9…`」证明 |
| `git diff --diff-filter=D --name-status origin/beta dev3` | 空（没有删除 beta 侧文件） |
| `git diff --name-status origin/beta dev3` | 15 路径（12 个站点面板实现/资源/测试 + 2 份文档 + 评估索引 1 行） |
| 工作区 | `git status --porcelain` 为空 |
| PR 状态 | `state=OPEN`、`mergedAt=null`、`mergeable=MERGEABLE`、`changedFiles=15`、`baseRefName=beta`、`headRefName=dev3` |
| PR 文件集校验 | `gh api repos/Silent1566/webhtv/pulls/445/files --jq '.[].filename'` 与 `git diff --name-only origin/beta dev3` **逐项一致**（15 项，`Compare-Object` 无输出） |
| 守卫会话 | `C69-beta-merge-review-dev3-20261014`（upstream） |
| 临时资源 | `.git/c69-pr-body.md`（PR 正文）已按任务范围清理 |

- 本次交付只创建 PR，未执行任何合并操作。
- **本任务闭环完成。** 三项用户要求均已满足：① 合并远端 beta 最新代码且远端已移除/回退的内容**零复活**（内容级与文件级交集均为 0）；② 复评全部已修改代码（含已提交未推送的 4 个站点面板提交）并修正 1 项重要 + 8 项次要问题，2 轮评审通过、mobile 10/10 与 leanback 69/69 全绿；③ 提交（双父合并提交 + recovery tag）、推送 `dev3`、创建 PR（中文描述、只创建未合并）。
