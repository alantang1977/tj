# E-SP11 电视端 EXO 掉帧：默认调度/丢帧阈值归因

- **任务 ID**：`E-SP11`（Exo 性能专项，`E-SP*` 家族）
- **开始时间**：2026-10-21 11:05 (+08:00, Asia/Shanghai)
- **lane**：诊断 + 默认值治理（非上游合并、非 ABI/原生改动）
- **当前状态**：**阶段 A（只读归因）完成；阶段 C 已实施两处「对齐上游」改动（未编译、未装机、未实测）；阶段 B（设备 bisect）待做**
- **阻塞**：本机 shell 无法启动（`bash` 与 `pwsh` 均报 `DSH workspace preparation failed (not a user permission denial)`），因此 `task_guard.sh`、Gradle 编译/单测、`git` 校验、AAR 反编译在本轮均无法执行；电视盒真机不在本会话可达范围。

---

## 0. 用户问题与复现口径

**现象**：同一个视频，当前应用（WebHTV）播放掉帧；`FongMi/TV`、`OK影视 5.1.6`、本仓 `Silent1566` 分支能稳定播放。历史上怀疑与「音频去广告」有关，该功能已删除（`docs/C45-remove-ad-audio-fingerprint-speech.md`）后仍有反馈。

**已排除**：去广告链路本身（代码已移除）。残留的 `ExoStartupAudioRenderer` 只是把 `MediaCodecAudioRenderer` 外层包裹一次（`app/src/main/java/com/fongmi/android/tv/player/exo/ExoUtil.java:937-942`），不解释「与内容相关的掉帧」，可在阶段 B 顺带确认其为透传。

**代码结构前提**：电视端与手机端共用同一套 `app/src/main` EXO 实现（`src/leanback` 无独立播放器代码，仅 `testLeanback` 为测试源集）。因此「电视版才掉帧」的差异只能来自**运行时配置 + 设备时序**，不存在「电视版另一套播放器」。

---

## 1. 结论（可判定部分）

本仓库默认开启了一条**成链的 media3 省电/低唤醒调度路径**，并把「解码输入丢帧阈值」压到上游默认值的 **1/3**：

| 环节 | WebHTV 默认 | 上游（media3 / FongMi / OK影视 基线） | 位置 |
|---|---|---|---|
| 动态调度 `experimentalSetDynamicSchedulingEnabled` | **开**（`perf_dynamic_scheduling=true`） | 未启用（opt-in 实验 API） | `ExoUtil.java:305-306`；开关 `PlaybackPerformanceSetting.java:314-321`、`PlaybackPerformanceSetting.java:580` |
| `setEnableDurationToProgressUs`（按解码耗时推迟唤醒） | **开** | **false** | `ExoFrameSchedulingRendererSettings.java:33-46`、`ExoUtil.java:952-953`；开关 `PlaybackPerformanceSetting.java:332-339`、`:581` |
| 强制异步 `MediaCodec` 队列 | **开**（`forceEnableMediaCodecAsynchronousQueueing`） | 不强制 | `ExoUtil.java:945-951`；开关 `PlaybackPerformanceSetting.java:323-330`、`:579` |
| 解码输入丢帧阈值 | **5 000 µs** | **15 000 µs**（1.9.0-rc01 起） | `ExoUtil.java:103`（`ENHANCED_LATE_THRESHOLD_TO_DROP_INPUT_US`）、`:954`、`ExoRuntimeAwareVideoRenderer.java:109-112` |
| Surface 固定尺寸 | 开 | 上游无此行为（`PlayerView` 用布局尺寸） | `PlaybackActivity.java:716-738` |

**上游口径证据**
- `MediaCodecVideoRenderer.DEFAULT_LATE_THRESHOLD_TO_DROP_DECODER_INPUT_US = 15000`，且上游**默认就会丢**迟到帧：[MediaCodecVideoRenderer 参考](https://developer.android.com/reference/androidx/media3/exoplayer/video/MediaCodecVideoRenderer)、[release 分支源码](https://github.com/androidx/media/blob/release/libraries/exoplayer/src/main/java/androidx/media3/exoplayer/DefaultRenderersFactory.java)
- 1.9.0-rc01 才把该默认值调到 15 ms：[release notes](https://github.com/androidx/media/releases/tag/1.9.0-rc01)
- `setEnableDurationToProgressUs` 上游默认 **false**：[Builder 参考](https://developer.android.com/reference/androidx/media3/exoplayer/video/MediaCodecVideoRenderer.Builder)
- `VideoFrameReleaseControl` 的早释放上限本身写死 50 ms：[androidx/media issue #2990](https://github.com/androidx/media/issues/2990)

**机制（为什么这三条会掉帧）**
`durationToProgress` 的语义是「播放器按解码器预计可出帧时间推迟唤醒」，它只在「动态调度开 + 解码器异步 + 注册了 Callback」三者同时成立时生效 —— 本仓库默认恰好三条全开。收益是 CPU 空转减少；代价是**唤醒预算更紧**。电视盒 SoC/内核定时器精度差、且常被其他后台（预加载、站源请求、WebHome 页面）抢占时，按「预计可出帧时间」算出的唤醒点会落到帧截止之后：输出帧错过 vsync → `onDroppedVideoFrames`；同时 5 ms 阈值让解码输入在「预测将迟到」时就被丢弃（上游给 15 ms 余量）。两者叠加表现为**内容相关、设备相关、与音频链路无关**的掉帧，与用户反馈的三个特征完全吻合。

---

## 2. 为什么其他播放器不卡

同为 media3 内核（`FongMi/TV`、`OK影视`）时，上述四项都取上游默认：不启用动态调度、不算 durationToProgress、不强制异步队列、丢帧阈值 15 ms。本仓库为了「省 CPU / 4K 掉帧缓解」把它们全打开并把阈值收紧，等于**用画面连续性换唤醒次数**。这解释了「同一个视频、别的播放器稳、本应用掉帧」。

`Silent1566` 分支若不含这组默认值，则它不掉帧也是同一解释。

---

## 3. 需一并更正的既有说法（防止继续误导排查）

`PlaybackPerformanceCatalog.java:113` 的选项说明写着「动态调度…保持开启（默认）通常更省 CPU、**掉帧更少**」。本轮证据只能支持「更省 CPU」，**不支持「掉帧更少」**，且方向可能相反。该文案在定案前不应作为结论引用；定案后需按实测结论改写。

---

## 4. 阶段 B：零改动 bisect（不需要重新打包，可直接在已发布包上做）

四个开关都是运行时设置，且设置页已有对应项（`PlaybackPerformanceCatalog.java:112-116`）。因此**可以先用发布包定位，再决定是否改代码**。

1. 设置 → 播放性能 → 切「自定义」（避免预设回写覆盖单项开关）。
2. 固定同一片源、同一电视盒、同一网络，每组连续播放 10 分钟：

| 组 | 改动 | 目的 |
|---|---|---|
| A | 全默认 | 基线（复现掉帧） |
| B | 只关「输入丢帧阈值」 | 判定 5 ms 阈值贡献 |
| C | B + 关「Media3 动态调度」 | 判定动态调度贡献 |
| D | C + 关「解码耗时推进」 | 判定 durationToProgress 贡献 |
| E | D + 「MediaCodec 队列」改自动 | 判定强制异步贡献 |
| F | E + 关「Surface 固定尺寸」 | 判定 Surface 尺寸贡献 |
| G | F + 「帧率匹配」改关闭 | 判定刷新率节拍贡献 |

3. 判读：优先看设置页/诊断导出的 `droppedFrames` 增量与 `onVideoFrameProcessingOffset` 分位（已有实现：`PlaybackAnalyticsListener.java:501-516`、`AV-DIAG-01-playback-diagnostics.md`）；用 `logcat` 的 `droppedFrames=` 行看是否成串。
4. 对照：同片同盒跑 `FongMi/TV` 与 `G:\下载\OK影视-5.1.6`，取同量级指标（二者无同款诊断，退化为 `dumpsys SurfaceFlinger --latency` + 肉眼卡顿点对齐）。

**判定规则**：某一组相对上一组丢帧率降幅 > 70% 即锁定该环节为主线；若 F、G 才有明显收益，则 Surface/帧率方向为主，动态调度链降为次要。

**注意**：23.976/24p 内容在 60/50 Hz 面板上本身就是 3:2 pulldown 抖动，属「节拍抖动」而非「丢帧」，G 组用于把两者分开，避免误判修好。

---

## 5. 阶段 C：候选修复（按阶段 B 结果择一，均不删除开关）

### C-1 对齐上游默认（推荐作为起点）
- `PlaybackPerformanceSetting.putRecommendedFlags()`（`:578-587`）与四个 getter 兜底（`:314-348`）：`perf_dynamic_scheduling`、`perf_video_duration_progress` 默认改 `false`；`perf_codec_async_queueing` 改由 `ExoPerformanceSetting` 的 `CODEC_QUEUE_AUTO` 决定，不再在预设里写死 `true`。
- 新增迁移键（沿用本文件既有 `migrateXxx()` 模式，见 `:69-89`），只对「未自定义」的老用户生效。

### C-2 只收阈值（最小改动）
- `ExoUtil.ENHANCED_LATE_THRESHOLD_TO_DROP_INPUT_US`：`5_000L` → 上游 `15_000L`（或直接不再覆盖，交给依赖默认值）。
- 优点：不动调度链，回归面最小；缺点：若主线是动态调度则无效。

### C-3 按设备/profile 分级
- 动态调度链只在「推荐/自动」之外的低端兼容预设里开启；电视端默认走 `false`。
- 需要 `PlaybackPerformanceSetting` 增加「电视端」维度的默认值分叉，改动面比 C-1 大，仅当 C-1 在手机端造成明显功耗/温度回退时才采用。

**共同约束**：三个开关必须成组思考 —— 关 `dynamic_scheduling` 后 `duration_progress` 自动失效（其文档明确仅在动态调度下生效），单独关后者可能只是「看起来改了」。

---

## 6. 验证矩阵（阶段 C 之后）

- **单测**：`PlaybackPerformanceSetting` 预设写值、迁移幂等、缺键兜底；`ExoFrameSchedulingRendererSettingsTest`、`ExoFrameSchedulingExperimentPolicyTest` 保持通过。现有测试是否断言了旧默认值需先检索（本轮无法运行 Gradle，未确认）。
- **设备**：用户回报片源 + 4K HEVC 23.976 + 1080p AVC 25 + DV5（Vulkan 路径）；无外挂字幕 / ASS / 双字幕；硬解 / 软解；seek 后 60 s 稳态。
- **指标**：10 分钟丢帧率、`processingOffset` p95、首帧时间、seek 完成时间、音画偏移。
- **验收**：A 组现象消失，且与 FongMi 对照差距落在噪声内；手机端不出现功耗/温度回退。

---

## 7. 回滚

不删除任何开关与代码路径，只改默认值与阈值；回滚 = 恢复原默认值 + 让迁移键失效重新初始化。任何单台设备都可现场切回。

---

## 8. 未决与如实记录

1. **未实测**：本会话无电视盒，§1 的机制是**代码与上游默认值对比推出的可证伪假设**，不是实测结论。阶段 B 是唯一的判定手段。
2. **依赖源码未终审**：`media3 = "1.11.0-alpha01-fongmi"`（`gradle/libs.versions.toml:50`）是 FongMi fork，其内建默认值理论上应与 1.9+ 一致；本轮因 shell 不可用无法反编译 `libs/` 内 AAR 交叉确认。若 fork 已改过默认值，§1 表格的「上游」列需以 fork 源码复核。
3. **A/B 实验未定位是否生效**：`ExoFrameSchedulingExperimentPolicy` 需要设备 `deviceDigest` 被分配才应用（否则 `Reason.DEVICE_NOT_ENROLLED` 回落 `stable`）；阶段 B 前需确认无有效分配，否则会污染测量。
4. **`isAuto` 与预设关系**：新装默认 `PROFILE_AUTO`，`putRecommendedFlags()` 会在首次初始化写入上述 `true`；因此「关掉」必须走自定义或新预设，单纯改代码里的 `Prefers.getBoolean(..., true)` 兜底对老用户无效 —— 迁移键是必需品。

---

## 9. 实施记录（2026-10-21，本会话）

按「只消除本仓相对上游的偏差、不动省电主干」的原则落地两处改动，两者互相独立、可单独回滚：

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| 1 | `ENHANCED_LATE_THRESHOLD_TO_DROP_INPUT_US` `5_000L` → `15_000L` | `app/src/main/java/com/fongmi/android/tv/player/exo/ExoUtil.java:105` | 与 media3 1.9.0-rc01+ 默认一致。纯放宽：原先被提前丢弃的迟到帧现在会照常呈现。两处使用点（`DefaultRenderersFactory` 路径与 `ExoRuntimeAwareVideoRenderer` builder）共用该常量，自动一并生效。 |
| 2 | `perf_video_duration_progress` 默认 `true` → `false` | `PlaybackPerformanceSetting.java:337`（getter 兜底）、`:584`（`putRecommendedFlags`） | 与上游默认一致。仍保留开关：动态调度开着时不再按「预计出帧时间」推迟唤醒，从而保留动态调度的 CPU 收益、去掉最激进的唤醒预算。 |
| 3 | 既有用户迁移 | `PlaybackPerformanceSetting.java:734-746`、`:84`、`:35-37` | 新增 `KEY_EXO_FRAME_SCHEDULING_PARITY_MIGRATED`（`..._parity_v1`）+ `migrateExoFrameSchedulingParity()`，沿用既有 `migrateXxx` 惯用法：只对非 `PROFILE_CUSTOM` 且该项未被显式覆盖的用户写回 `false`，幂等。 |
| 4 | 选项说明更正 | `PlaybackPerformanceCatalog.java:113-114` | 「动态调度…掉帧更少」改为条件表述（本轮证据不支持该结论）；「解码耗时推进」改为默认关闭并说明代价。 |

**未改动**（留给阶段 B 判定）：`perf_dynamic_scheduling`（仍默认开）、`perf_codec_async_queueing`（仍默认开）、`perf_surface_fixed_size`（仍默认开）、`FRAME_RATE_SEAMLESS`。

**验证状态：未编译、未装机、未实测。** 本会话 `bash` 与 `pwsh` 均报 `DSH workspace preparation failed`，REA 的 Windows 进程通道也不可用（`capability_unavailable`），因此 Gradle 编译、单测、`task_guard.sh`、`git` 提交/打 tag 全部无法执行；`emulator-5558`（adb 端口 5559，已装 `com.silent.android.webhtv` 5.6.0 debuggable）无法接收新包。
**恢复后的验证顺序**：`bash .codex/scripts/task_guard.sh start --id E-SP11 --mode quick-fix --scope app/src/main/java/com/fongmi/android/tv/player/exo app/src/main/java/com/fongmi/android/tv/setting docs/E-SP11-exo-tv-frame-drop-defaults.md` → 双 flavor Java 编译 → `./gradlew :app:testLeanbackDebugUnitTest --tests '*player.exo.*'`（该目录 600+ 例，无测试断言这两个默认值，预期零改动失败）→ 装机 `adb -s emulator-5558 install -r` → 用 §4 的 A/B 两组对比。

## 10. 首轮模拟器观测（2026-10-21 11:21 装机，11:23–11:24 采样）

**环境**：`emulator-5558`（x86，`app_process32`），`com.silent.android.webhtv` 5.6.0，`last_update_time=2026-10-21 11:21:36`（含本次改动）；片源 730 902 ms / `video/mp4` / 4 073 199 bps / 372 MB，路由 `EXTERNAL_LOOPBACK_PROXY`，`audioOutput=PCM`、`tunnel=false`。

**观测**（`TV-playback-telemetry` 逐样本）：

| 指标 | 值 | 判读 |
|---|---|---|
| `firstFrameMs` | 3 491 | 正常 |
| `rebufferCount` / `rebufferTotalMs` | 0 / 0 | 无重缓冲 |
| `bufferedMs` | 21 000–31 000 | 缓冲健康 |
| `dropped` | ≥100 累计（回调按 50 递增） | 掉帧仍在 |
| `renderedFps` | 12.500 | 渲染帧率异常偏低 |
| `bandwidthBps` vs `mediaBps` | 2 400 000 vs 4 073 199 | 带宽低于码率 |
| 解码器 | `FfmpegVideoDecoder` + `VIDEO_DECODER_ERROR_READ_FRAME` 反复 | **FFmpeg 软解** |

**结论：本轮不能用于判定改动效果。** 可见瓶颈是模拟器侧的软件解码（x86 无真实硬件解码器，`/dev/fastpipe` ioctl 被 SELinux 拒绝）叠加回环代理带宽低于码率；这与电视盒的硬件解码路径不是同一种负载。可作为「无崩溃、无重缓冲、缓冲健康」的健全性证据，但不能作为「掉帧已修复」的证据。模拟器仍有一个有效用法：**环境恒定**，在同一模拟器上做 A/B 两组对照，差值仍有参考价值。

**顺带发现（与本任务无关，仅记录不修）**
1. `DefaultTrackSelector: Audio channel count constraints cannot be applied without reference to Context` —— TrackSelector 用了不带 `Context` 的已废弃构造，音频声道数约束被**静默忽略**；每次 prepare/seek 都出现。
2. `System: A resource failed to call release` 反复出现 —— 有资源未释放（Surface/Codec 类），属泄漏迹象。
3. `TV-SpiderDebug: Executor did not terminate in time for range ...` —— 预加载线程池关闭超时（1 s 未退出），低端机上是潜在卡顿源。
4. `AudioActivity`/`)` 无关；`TV-ai-rec` 推荐接口超时不涉及播放。

## 10.1 设置状态核对（11:28，`run-as` 读取 SharedPreferences）

改动**已真实生效**，且迁移按设计执行：

```
perf_video_duration_progress = false                                  ← 默认值改动
playback_performance_exo_frame_scheduling_parity_v1 = true            ← 迁移键已落盘
perf_dynamic_scheduling = true                                        ← 按计划未动
perf_late_drop_input = true                                           ← 开关仍在，阈值已放宽到 15 ms
perf_codec_async_queueing = true                                      ← 按计划未动
perf_exo_profile = 4 (AUTO) / perf_exo_frame_rate_mode = 1 (仅无缝) / tunnel=false
```

解码运行时存档显示正在播放的内容为 **`video/hevc` 3840×1606**（另有多条 `video/hevc` 3840×1608/1920、`video/avc` 1080p 记录），帧率字段为 `25000`/`60000` → **4K HEVC、25 fps**。

## 10.2 第二轮观测：切「硬解」后仍走 FFmpeg 软解

用户切换硬解后，会话 `p-24rf8a-5`（位置 649–679 s）指标：

| 指标 | 值 |
|---|---|
| 解码器 | **仍为 `FfmpegVideoDecoder`**（`VIDEO_DECODER_ERROR_READ_FRAME` 持续每 ~1–10 s 出现） |
| `dropped` | **5 920**（会话累计） |
| `firstFrameMs` | **9 995**（软解会话为 3 491） |
| `rebufferCount` | 1（142 ms） |
| `bufferedMs` | 27 000–33 000 |
| `renderedFps` | unknown |

**判读**：x86 模拟器没有 4K HEVC 硬件解码器，硬解请求必然失败并按 `E-SP9` 的「解码器兜底」自动回落软解——日志里没有 `MediaCodecVideoRenderer`，只有 FFmpeg。因此：
1. 本环境**无法**用来验证掉帧修复；掉帧由解码吞吐决定（~10 fps 丢弃对应 25 fps 内容）。
2. 首帧从 3.5 s 恶化到 10 s，是「先试硬解失败再回落」的代价，属可优化项（不在本任务范围，记录待评估）。
3. 两个会话的 `dropped` 不能直接对比：会话内容/位置不同，且第二会话多了硬解尝试与回落过程。

**结论**：模拟器这条线到此为止，除「改动已生效、应用未回归」外无法提供掉帧判据。真正的验收必须在硬解可用的设备（电视盒）上做。

## 10.3 第三轮观测：1080p + 硬解（健康基线）

会话 `p-25aj5m-b`：47:21 片源（2 841 680 ms）、`mediaBps=2 707 721`、`bandwidthBps=45 443 801`（**16.8× 余量**）。

| 指标 | 值 | 判读 |
|---|---|---|
| 解码器 | **MediaCodec 硬解**（整个会话 `FfmpegVideoDecoder` 计数 = 0） | 硬解真正生效 |
| `renderedFps` | **25.000** | 与片源一致 |
| `dropped` | **0**（0 次 `droppedFrames` 回调、0 个非零 rebuffer 采样） | 无掉帧 |
| `firstFrameMs` | 1 028 | 起播快 |
| `bufferedMs` | 42 575 | 缓冲充足 |
| `rebuffer` | 0 | 无重缓冲 |

**三会话对比（同一构建、同一进程，仅换片源与解码路径）**

| | 4K HEVC 软解 | 4K HEVC 切硬解后（仍软解） | 1080p 硬解 |
|---|---|---|---|
| 解码器 | FFmpeg | FFmpeg | MediaCodec |
| `renderedFps` | 12.5 | unknown | 25.000 |
| `dropped` | 100 / 73 s | 5 920 | **0** |
| `firstFrameMs` | 3 491 | 9 995 | 1 028 |
| `rebuffer` | 0 | 1（142 ms） | 0 |

**结论**：掉帧与**解码路径**强相关，与帧调度/丢帧参数无关。本轮同时证明改动后的构建在硬解路径上**无回归**（0 掉帧、25 fps、1 s 首帧）。

## 10.4 由本次对照得出的新假设（优先级高于调度参数）

模拟器的表现说明：**只要落到软解，4K 就会大面积掉帧；其他播放器不卡，很可能是因为它们仍在硬解。**

本仓有一个上游 media3 没有的机制：**按设备持久化排除解码器**。

- `ExoDecoderRuntimeSession.shouldExclude()`（`:154-167`）在每次选解码器时按 `(环境, 解码器名, 格式签名, secure, output)` 判黑名单，命中即从候选中剔除：`profiles.isBlacklisted(key, nowEpochMs)`。
- `ExoDecoderRuntimeProfileStore.ENTRY_TTL_MS = 30 天`（`:17`、`:241`）：黑名单条目 30 天未刷新才过期。
- 结果是：**某台设备只要历史上记录过一次该解码器+该格式的失败，之后 30 天内都会静默改用软解**；用户只感知到「同一个视频掉帧、别的播放器不卡」，且该状态跨版本升级保留——与「删掉音频去广告后仍然掉帧」的现象一致。
- stock media3 / FongMi / OK影视 没有这个机制，因此不存在这种静默降级。

**现场判定方法**（可让用户执行，或从应用诊断导出读取）：

```bash
adb shell run-as <包名> cat shared_prefs/<包名>_preferences.xml | grep perf_exo_decoder_runtime_v1
```

若条目中出现该片源的 `video/hevc` + 对应分辨率组合，即说明硬解被本机黑名单排除。当前模拟器会话**没有**出现排除日志，1080p 走的是硬解，符合预期。

**待验证**：用户设备上该 store 的实际内容。这是把「掉帧」从调度问题改判为解码路径问题的关键证据。

## 12. 实施记录（2026-10-21，解码器排除显性化）

按 §10.4 的假设补充可观测性，使「静默降级到软解」在设置页可见：

| 改动 | 文件 | 内容 |
|---|---|---|
| 存储层读取接口 | `ExoDecoderRuntimeProfileStore.java` | 新增 `activeBlacklist(long)`：返回当前生效的排除条目，按 `updatedAtEpochMs` 倒序；只读，会顺带执行既有 `prune` |
| 门面层摘要 | `ExoDecoderRuntimeProfiles.java` | 新增 `blacklistedCount()`、`blacklistSummary()`（无命中返回 `""`）、`mimeLabel()`；摘要形如 `硬解已排除 1 条（HEVC 3840×2160）` |
| 设置页展示 | `PlaybackPerformanceSetting.java` | `getSummary()` 在存在排除时追加 `"，" + 摘要`，否则保持原样 |
| 回归锁 | `ExoDecoderRuntimeProfilesSummaryTest.java`（新增） | 4 例：无排除为空、两次连续失败后摘要含格式与分辨率、单次失败不产生摘要、`activeBlacklist` 倒序且跳过健康条目 |

**验证（本会话实测）**
- `bash ./gradlew :app:assembleLeanbackArmeabi_v7aDebug --offline` → **BUILD SUCCESSFUL（2m30s）**
- `:app:testLeanbackArmeabi_v7aDebugUnitTest --tests '*ExoDecoderRuntime*'` → **34 例 / 0 失败**（Store 13、Session 13、Key 4、新 Summary 4）
- `adb -s emulator-5558 install -r` → Success；启动无 `FATAL`/`AndroidRuntime`

**边界**：设置页那一行的**实际渲染未做屏幕走查**；目前证据是「摘要逻辑单测通过 + 编译通过 + 装机可启动」。若需要，可在构造一条黑名单条目后截图确认。

## 13. C91 复评修复（2026-10-21，`7faf6cea93` 与本轮改动）

`docs/C91-beta-merge-review-dev3-20261021.md` 对提交 `7faf6cea93` 的复评结论：4 项必修，已全部落地并各有可证伪锁。

| # | 级别 | 问题 | 修复 | 锁 |
|---|---|---|---|---|
| 1 | **high** | 「输入丢帧阈值」关闭时不调用 setter，而 media3 fork（`1.11.0-alpha01-fongmi`）的 `lateThresholdToDropDecoderInputUs` 默认就是 15 ms。E-SP11 把开启值也改成 15 ms 后，**开/关完全等价**，开关变 no-op（关掉仍丢输入帧）。fork 源码 `MediaCodecVideoRenderer.java:700-707` 明确只有 `C.TIME_UNSET` 才不丢。 | `ExoUtil.java`、`ExoRuntimeAwareVideoRenderer.java` 两条构建路径：开 → `15_000L`；关 → `C.TIME_UNSET`（后者补 `else` 分支与 `import androidx.media3.common.C`）。 | `PlaybackPerformanceSettingSourceTest.lateDropThresholdSwitchCanActuallyDisableDropping` |
| 2 | medium | `blacklistedCount()/blacklistSummary()` 统计 store 内**所有**黑名单条目，但键含 `environmentDigest`（fingerprint + app 版本 + media3 版本）且条目 30 天 TTL 跨升级保留 ⇒ 升级后旧条目仍被显示成「当前生效的硬解排除」。 | 新增 `ExoDecoderRuntimeProfiles.activeBlacklist()`，按当前 `environment.digest()` 过滤后再计数/取最新。 | `ExoDecoderRuntimeProfilesSummaryTest.summaryIgnoresExclusionsRecordedUnderAnotherEnvironment` |
| 3 | low | `PlaybackPerformanceSetting.getSummary()` 无条件追加 EXO 摘要，而该行同时服务 EXO/MPV/IJK；后两者会显示该内核不可能发生的降级。 | 仅 `PlayerSetting.getPlayer() == PlayerSetting.EXO` 时追加。 | 复核（无单测，行为受内核选择控制） |
| 4 | low | 两项设置说明与实现不符（把掉帧风险写死成「电视盒」；「输入丢帧阈值」未说明 15 ms 与关闭代价）。 | `PlaybackPerformanceCatalog` 改为条件表述，补 15 ms 与「关闭后不丢输入帧、可能累积音画延迟」。 | 复核 |

**验证**：双 flavor arm64 Debug Java 编译 `BUILD SUCCESSFUL in 3m 19s`；`--tests '*ExoDecoderRuntime*' --tests '*PlaybackPerformance*'` **50 例 0 失败**；exo 全包 **617 例 / 1 skipped / 0 失败**；`check_ui_tokens.sh` PASS。

**仍未解决（与本任务原有边界一致）**：阶段 B 设备 bisect 与电视盒实测未执行。本轮 `adb devices` 只有 `127.0.0.1:5557` 与 `emulator-5556`，均为 x86_64 / SDK 28 镜像，且未构建 x86_64 产物 ⇒「阈值关闭后的丢帧行为」与「摘要那一行的实际渲染」都没有设备端证据。

## 11. 下一步（唯一动作）

装上新包后先只做 §4 的 A（全默认）与 B（关「输入丢帧阈值」）两组对照：若新默认下 A 组已明显好于旧版，说明「5 ms 阈值 + durationToProgress」就是主线，收工；若 A 仍掉帧而 B 好转，再单独评估把 `perf_late_drop_input` 默认关掉（此时阈值已放宽，需重新取值）。
