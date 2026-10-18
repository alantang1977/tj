# MPV-BUFFERING-STALL-WATCHDOG-20261017

## Recovery anchor

- Objective: (1) 给 MPV 补上缓冲停滞看门狗，让卡在 BUFFERING 且无任何进展的会话有界退出；(2) 把内核/软硬解切换的原因补齐成统一、可机读的日志，使“为什么跳内核/切软硬解”能从导出日志直接回答。
- Lane: `standard`。
- Baseline: branch `dev2`, HEAD `3eee5e8c9d618c4f7845e6bd0100357f28ef82d0`。
- Protected dirty paths: `.wh_diag/**`（任务前已存在，未纳入 scope）。
- Status: 已实现，单测与四变体编译通过并已提交（`c2a09e7647dd`）；模拟器实测已完成（§7.1：MPV 布防通过、不误杀通过、停滞超时因测试环境限制未触发）。
- Next action: 无；停滞超时与 32 位/手机版布防待用限速方式补验（见 §7.2）。

## 1. 用户可见能力

1. **MPV 卡缓冲不再只能干等**：MPV 播放中若进入 BUFFERING 且位置与缓冲末端都不再前进，会在有界时间内结束该次尝试并走既有失败回退，而不是无限转圈。
2. **切换原因可追溯**：导出的播放日志里，每次换内核或换软硬解都会有一行 `switch-cause`，写明原因、是否用户显式选择、从哪个内核/软硬解换到哪个。

## 2. 现场证据与根因

### 2.1 15 秒启动看门狗对 MPV 实际不生效

`Constant.TIMEOUT_PLAY = 15s`（上游 fongmi 原值，鱼壳同样）。`PlayerManager` 的 `onPlaybackStateChanged`：

```java
if (state != Player.STATE_IDLE) App.removeCallbacks(runnable);
```

**任何非 IDLE 状态都取消定时器，包括 BUFFERING。** 而 `MpvPlayer.openCurrent()` 在 `handlePrepare()` 里第一步就 `playbackState = Player.STATE_BUFFERING; loading = true;`，因此 MPV 在真正开始解码之前就上报 BUFFERING，15 秒定时器随即被取消。

用户提供的导出日志印证：`setMediaItem timeout=15000`（22:09:38.016）→ `state=BUFFERING`（22:09:38.115，99ms 后）→ `state=READY`（22:09:49.204，11522ms）。虽然接近 15s，但**没有触发超时**，因为定时器在 99ms 时已被取消。

结论：对 MPV 起播路径，调大 15 秒没有意义；真正缺的是缓冲停滞兜底。

### 2.2 停滞看门狗只挂在 Exo 上

```java
private void armBufferingStallWatchdog() {
    if (!isExo() || player == null || spec == null) return;   // ← 只有 Exo
```

`checkBufferingStall()` 同样以 `!isExo()` 提前退出，seek 重臂点也是 `if (isExo()) armBufferingStallWatchdog();`。

后果：MPV 一旦卡在 BUFFERING，15 秒启动看门狗已被取消、停滞看门狗不存在，**没有任何兜底**。

### 2.3 看门狗本身是引擎无关的，MPV 已假设它存在

`ExoBufferingStallWatchdog` 只消费 position、buffered end、loading 三个量，全部引擎都能提供：

- `MpvPlayer` 的 `bufferedPositionMs()` 走 `MpvBufferedPositionPolicy`（日志 `playback-progress: action=buffer-read source=direct-engine` 证实会前进）；
- `isLoading()` 映射 mpv 的 `loading` 字段；
- 超时值无需调整：Exo 阈值 `MAX_STREAMING_REBUFFER_MS = 15s`，MPV 的 `MpvPerformanceSetting.getRebufferMs()` 最大映射到 8s（驱动 mpv 自身 `cache-pause-wait`），都远低于看门狗的 20s/60s 上限。

关键佐证：`MpvPlayer.timeOutSeekBuffering()` 的注释**已经假设存在这个看门狗**——

> Publishing READY would hide the progress indicator over a frozen frame … and would also cancel the stall watchdog, since checkBufferingStall() disarms on READY. Leave the state alone and let that watchdog own the stall.

对 MPV 来说，那个被引用的看门狗此前是空的。

### 2.4 切换原因日志此前无法回答“为什么换”

切换分散在多个路径，措辞与字段各异：

| 路径 | 原日志 |
| --- | --- |
| 失败回退内核 | `player: fallback player from=… to=…` |
| 失败回退软解 | `player: fallback decode player=… from=hard to=soft` |
| 手动换内核 | `player: switch player type=… chosen=…` |
| 自动软解 | `playback-stage: stage=switch-decode-auto`（无前后值） |
| 手动换软硬解 | `player: switch decode fresh decode=…`（无原因、无来源） |

没有统一字段，也没有“这次是用户选的还是自动回退的”这一维度，导致“设置 MPV 却跳到 EXO”这类问题无法从日志定性。

## 3. 方案比较

| 方案 | 收益 | 缺陷/风险 | 决定 |
| --- | --- | --- | --- |
| 只调大 `TIMEOUT_PLAY` | 改动最小 | 对 MPV 起播无效（定时器已被 BUFFERING 取消）；且与站点取址超时共用常量，等于放宽所有源站超时 | 否决 |
| 把看门狗复制一份 MPV 版 | 不动 Exo 路径 | 重复实现与重复维护，两套阈值会漂移 | 否决 |
| 看门狗上移为引擎无关，各引擎共用 | 单一实现、单一阈值；MPV 立即获得兜底 | 需确认 MPV 的 position/buffered/loading 语义与 Exo 一致（已确认）；需确认 20s/60s 高于两个引擎的 rebuffer 阈值（已确认） | **采用** |
| 给每个切换点加 `cause` 参数贯穿到 Activity | 原因最精确 | 需改 3 个 Activity、5 个调用点，破坏 4 个既有 source-text 测试的断言字符串；公开签名扩张 | 否决 |
| 在 `PlayerManager` 内部按入口推导原因 | 零公开签名变化、零 Activity 改动、既有测试断言全部保持有效 | 原因粒度取决于入口数量（当前每个入口语义唯一，足够） | **采用** |

## 4. 实现

### 4.1 看门狗引擎无关化

- `git mv` 把 `player/exo/ExoBufferingStallWatchdog.java` 移到 `player/BufferingStallWatchdog.java`，类名同步；测试同样移动。用 `git mv` 保留历史。
- 新增 `stalledDurationMs(now)`，在超时日志里报告**实测停滞时长**而不是只报配置上限。
- 类注释补上 MPV 维度：说明为何两个引擎共用、以及两个引擎各自的 rebuffer 阈值都必须低于它。

### 4.2 三个 Exo 专属门禁放开

- `armBufferingStallWatchdog()`：`!isExo() || player == null || spec == null` → `player == null || spec == null`。
- `checkBufferingStall()`：同上放开。
- seek 重臂点与 `STATE_BUFFERING` 分支：去掉 `if (isExo())`。

### 4.3 统一切换原因日志

新增 `switch-cause` 日志与两个 `logSwitchCause` 重载：

```text
switch-cause kind=kernel|decode|none cause=… chosen=true|false from=<内核>/<软硬解> to=<内核>/<软硬解> position=…
```

- `kind` **由实际变化推导**（内核变了→`kernel`，内核没变而软硬解变了→`decode`），不由调用方声明，避免“同内核只换软硬解”被误报成换内核。
- `chosen` 区分「用户显式选定」与「自动回退」。
- `from/to` 同时给出内核名与软硬解，避免只看到其中一个维度。

原因取值：

| cause | 触发点 |
| --- | --- |
| `user-choice` | 所有 `switchPlayer`/`switchDecode` 入口（均为 UI 用户操作） |
| `history-kernel-before-play` | `preparePlayer(force=false)`：按剧集记住的内核 |
| `history-kernel-retry-after-error` | `preparePlayer(force=true)`：onError 重试（`force` 本身就是归因信号） |
| `fallback-decode:<trigger>` | 失败后切软解 |
| `fallback-kernel:<trigger>` | 失败后换内核 |
| `kernel-unavailable` | 内核不可用（非播放失败） |
| `auto-no-hardware-decoder` | Exo 硬解无可用解码器时自动转软解 |
| `hard-decode-switch-retry` | 硬解初始化失败后重试硬解 |

`<trigger>` 由 `fallbackTrigger(PlaybackException)` 把 errorCode 归成短标签（`timeout`/`decoder-init`/`decoding`/`format-unsupported`/`network-timeout`/… 其余 `code-<n>`），保留数值以免丢失区分度。

**关键约束：未改动任何公开签名**（`preparePlayer`/`switchPlayer`/`switchDecode` 全部保持原样），因此 3 个 Activity 文件与 4 个既有 source-text 测试完全未动。这一点是设计选择的结果，不是巧合——见 §3 最后两行。

## 5. 影响与风险

- **兼容性**：无格式、ABI、Android API、包体积影响；纯 Java。
- **性能**：看门狗是 1s 轮询，此前只对 Exo 生效，现在对 MPV/IJK 同样生效。每 tick 只读 position/buffered/loading 三个已有属性，不新增 native 调用。MPV 的 `getBufferedPosition()` 读的是缓存属性而非同步 `mpv_get_property`，不会阻塞主线程。
- **主要回归风险**：误判正常慢速缓冲为停滞。已用三重保护约束：停滞判据要求 position 与 buffered **都不前进**；loading 时用 60s 上限；90s episode ceiling 额外要求段内净进展不足 15s 才触发。
- **次要风险**：MPV 的 buffered 读数在 seek 后会回退，可能被当成 discontinuity 而重锚（这是期望行为，`DISCONTINUITY_TOLERANCE_MS` 已覆盖）。
- **日志量**：`switch-cause` 每次切换一行、`buffering-stall` 每次布防/超时各一行，均为低频事件级日志，非每帧。

## 6. 验证

执行（2026-10-17 Asia/Shanghai）：

1. **定向用例**：`BufferingStallWatchdogTest` 23/23、`PlayerManagerSwitchCauseSourceTest` 8/8、`PlayerManagerLifecycleSourceTest` 3/3，失败/错误/跳过均为 0。
2. **全量单测**：`:app:testMobileArm64_v8aDebugUnitTest` → `5085 tests completed, 7 failed, 3 skipped`。
3. **基线对照**：同一命令在 `git stash` 后的 `3eee5e8c9d` 上跑出 `5076 tests completed, 7 failed, 3 skipped`；**失败集合逐条一致**（`MpvFontConfigTest`、`MpvHlsCacheCoordinatorTest`、`ReaderPlaybackRoutingSourceTest`×2、`TmdbSourceOnlyInteractionTest`、`TmdbUIAdapterTest`、`WebThemeTokenSourceTest`），即**零新增失败**，用例数 +9。
4. **四变体编译**：`compileMobileArm64_v8aDebugJavaWithJavac`、`compileLeanbackArm64_v8aDebugJavaWithJavac`、`compileLeanbackArmeabi_v7aDebugJavaWithJavac`、`compileMobileArmeabi_v7aDebugJavaWithJavac` 全部 `BUILD SUCCESSFUL`。
5. **变异测试**（证明断言可失败，非恒真）：
   - 把 `armBufferingStallWatchdog()` 重新用 `if (isExo())` 门禁 → `bufferingStateArmsTheStallWatchdogForEveryEngine` 如期 FAILED。
   - 把 `previousType/previousDecode` 的捕获移到 `playerType = type` **之后** → `everyKernelSwitchFlowsThroughTheSingleCauseLogger` 如期 FAILED。
   - 两次均从备份还原并复跑全量，回到 7 个预存失败。
   - 另有一次变异**未**失败（把捕获提前），已如实记录：那不是缺陷变异，因为捕获仍在覆盖之前，不构成对不变量的破坏。
6. `git diff --check` 通过。

### 6.1 设计过程中修正的一次错误

首版把 `cause` 作为参数贯穿到 3 个 Activity，导致 4 个既有 source-text 测试失败（`VideoActivityLayoutTest`×2、`TmdbUIAdapterTest`×1、`TmdbDetailDirectPlayTransitionSourceTest`×1）。经基线对照确认这 4 项确为本次引入后，改为在 `PlayerManager` 内部按入口推导原因，撤销全部 Activity 改动，4 项失败随之消失。这 4 项失败**不是**被放宽或删除的断言，而是改动被改回后自然恢复。

## 7. 设备验证记录

### 7.1 模拟器实测（2026-10-17，已执行）

**设备**：`192.168.50.3:5557`（本仓库约定的 2 号模拟器），Android 9 / x86_64 + houdini 翻译 / 应用 arm64-v8a。

**方式**：覆盖安装 `app/build/outputs/apk/leanbackArm64_v8a/debug/app-leanback-arm64_v8a-debug.apk`（200,391,926 字节，debug key SHA-1 `d92b568f…`，与设备已装包签名一致，数据保留）。**未打正式包**。

#### 通过：看门狗在 MPV 上布防

```text
buffering-stall: action=arm player=3 decode=1 position=11952 buffered=11952 loading=true
VO: [gpu] 1920x1080 => 1920x1080 yuv420p
```

- `player=3` 即 **MPV**。改动前 `armBufferingStallWatchdog()` 的 `if (!isExo()) return;` 会让这行日志根本不可能出现，因此这是门禁已放开的直接证据。
- `VO: [gpu] 1920x1080` 证明 MPV 确实加载并渲染了媒体，不是空转。
- 全程**没有** `action=timeout`，即正常播放未被误杀（§7 第 2 项“不误杀”在此场景下成立）。

#### 顺带复现并定性了「设置 MPV 却跳到 EXO」

```text
switch-cause: kind=kernel cause=history-kernel-before-play chosen=true from=MPV/hard to=EXO/hard position=0
```

全局默认内核已设为 MPV（`player=3`），但**该文件的历史记录里 `player=0`（EXO）**，于是起播前被切回 EXO。设备上历史分布为 `-1:12 / 0:170 / 3:4`，即绝大多数记录是 EXO。

这条正是本任务新增日志的价值所在：一行即可区分「历史记录覆盖了设置」与「失败自动回退」。**注意**：`chosen=true` 表示这是“用户显式选定过的内核”，此处来源是历史记录，不是本次失败回退（回退会带 `cause=fallback-kernel:<trigger>`），两者不会混淆。

#### 未通过：停滞超时（`action=timeout`）无法在模拟器上端到端触发

尝试了 7 种构造方式，全部退化为**源站取址的 30s 超时**（`TimeoutFutureException` + `player finish cost=30017ms`，`start-file`=0），MPV 没有机会加载媒体：

| # | 尝试 | 结果 |
| --- | --- | --- |
| 1 | 32KB 全零流 | 非有效 MP4，取址超时 |
| 2 | 真实 MP4 + 声明超大 Content-Length | 代理等待剩余字节，取址超时 |
| 3 | 无 Content-Length 的连续流 | 同上 |
| 4 | `moov` 在文件前部的 vt.mp4 | 同上 |
| 5 | 完整 HTTP 语义（HEAD / Range / 206） | 同上 |
| 6 | `adb reverse` 走 `127.0.0.1` | 同上 |
| 7 | 按请求序号区分 spider 探测与播放 + 手工 faststart 重排的 sintel | 同上 |

**根因（测试环境限制，非改动缺陷）**：`push_agent` 站点的 spider 会先探测 URL，探测阶段被停滞就自己挂到 30s 取址超时；而 `SiteApi.playerContent` 只有 `file:` 前缀或站点为空时才绕过 spider（`if (PUSH.equals(key) && (site.isEmpty() || isLocalFileUrl(requestId))) return pushPlayer(...)`），HTTP URL 必走 spider。

另注：`SIGSTOP` 冻结进程不可行——它会连同看门狗一起冻结，无法验证超时。

**因此停滞超时目前只有单测覆盖**（`BufferingStallWatchdogTest` 23 例，含 episode ceiling、seek 重锚、慢速填充不误杀、暂停不累积等边界），尚无设备端到端证据。

#### 建议的超时验证方式

真机/模拟器上改用**限速**而非服务端停滞：把设备带宽限到低于媒体码率，让 MPV 自然耗尽缓冲。这样取址能正常完成、媒体能加载，`position` 与 `buffered` 随后双双冻结，才是看门狗要捕获的状态。服务端停滞在 `push_agent` 路径上先天不可用。

### 7.2 仍需完成的设备验证

1. **停滞兜底**：按 §7.1 建议的限速方式，确认 `action=arm` 后出现 `action=timeout stalledMs=…`，且随后走既有失败回退而非无限转圈。
2. **不误杀（弱网场景）**：正常弱网缓冲（位置不动但 buffered 持续增长）必须**不**触发超时；暂停状态不得累积到 episode ceiling。
3. **切换归因**：分别做「用户手动换内核」「用户手动换软硬解」「播放失败自动回退」三类操作，确认导出日志各出现一行 `switch-cause`，且 `cause`/`chosen` 与实际操作一致。
4. **32 位与手机版**：leanback armeabi_v7a 与 mobile 各跑一次布防确认。
5. 回退判据：出现误杀或异常回退时，`git revert` 本任务提交即可完整恢复。

### 7.3 环境还原

验证后设备已恢复到任务前状态：prefs（移除临时写入的 `player=3`）、`tv` 数据库（历史分布回到 `-1:12 / 0:170 / 3:4`）、设备临时文件与 `adb reverse` 全部清理；宿主临时目录与测试服务进程已删除。仓库工作区无改动（仅任务前既有的 `.wh_diag/`）。

## 8. 回滚

纯 Java 改动（看门狗移动 + 三个门禁放开 + 原因日志），`git revert <本任务提交>` 即可完整回退；不涉及 native、依赖锁、补丁、产物或持久化 schema。恢复 tag 见提交记录。
