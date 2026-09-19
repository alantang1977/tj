# C16：T3/T4 详情内嵌 TMDB 元数据设计

> 状态：用户已批准按阶段实施。阶段 1-6 已完成；客户端需求已实现并通过模拟器验收，T4 服务端仍需在其独立仓库按本文合同实施。

## Recovery anchor

- 目标：扩展现有详情返回协议，使 T3 客户端爬虫和 T4 服务端接口可在 `detailContent` 结果中直接携带 TMDB 数据；APP 优先采用身份匹配的源数据，仅为缺失能力按需访问 TMDB。
- 基线：WebHTV `dev4@32a52698e5dab09fe18e49d18849a947057ca717`；OmniBox `main@d57b3e6672337febd46feca0d8ad59c6a2b507c3`；alist-tvbox `master@8a222f69a80291e836db702c34daf1ed5bdd5630`；atv-player `master@09feed1d5e5102f13bf91c9fbb76ea92808cb76d`。
- 范围：实现合同；阶段 1-6 已完成本仓库 APP 侧协议、解析、合并、详情接入、延迟能力和设备验收。
- 回滚：删除本文档并撤销总评估索引中的 C16 条目即可。
- 追加结论：alist-tvbox 适合作为 T4 的元数据持久化和图片访问参考，但当前 `/vod` 输出仍是平铺 `vod_*` 字段；atv-player 适合作为 APP 的字段级合并、季级身份、缓存和异步取消参考，不能直接作为 Android 协议实现。
- 当前进展：阶段 1-5 已完成客户端协议、纯逻辑、源缓存、source-first 详情接入和延迟能力；阶段 6 已在 `HD1910/Android 9` 模拟器完成 Mobile 与 Leanback 验收。
- 下一动作：如需实际接入，选择目标 T4 服务端仓库并按其现有持久化模型独立实现 C16 生产者合同；本仓库客户端侧无剩余实现项。

## 1. 设计结论

推荐在现有详情结果的 `Vod` 对象中增加可选 `tmdb` 字段，而不是照搬 OmniBox 的独立元数据请求接口。

核心规则：

1. 保持 `detailContent(ids)` 方法签名和顶层 JSON 不变，旧源和旧客户端继续兼容。
2. T3 与 T4 返回完全相同的数据合同，不在 APP 中按来源类型分叉。
3. `tmdb.id + tmdb.media_type` 是剧集级身份锚点；若详情处于选中季上下文，还必须包含 `season_number`。
4. APP 按能力组判断缺口。源数据完整时不得连接 TMDB；部分缺失时只补所需能力。
5. 合并采用 fill-only，源提供的合法非空字段优先，网络结果不得覆盖它们。
6. 空值默认表示未知。只有能力组列入 `complete` 时，空数组才表示明确为空。
7. 季、集、视频以及更多推荐等延迟能力只在用户实际访问时补齐。

## 2. 两项目现状分析

### 2.1 WebHTV 当前链路

`SiteViewModel.detailContent()` 最终进入 `SiteApi.detailContent()`：

- T3 调用爬虫的 `detailContent(List<String> ids)`，再由 `Result.fromJson()` 解析。
- T4 以 `ac=detail`、`ids=<id>` 等参数调用服务端，再由 `Result.fromType()` 解析。
- 两种来源随后统一进入 `Result.list<Vod>`、播放线路解析和 `VodDetailCache`。
- 当前 `Vod` 只有传统详情和播放字段，没有结构化 TMDB 数据。
- TMDB 详情模式当前通过 `TmdbService` 独立访问 TMDB，详情请求覆盖图片、演职员、翻译、外部 ID、视频、推荐和相似内容；电视内容另有季与单集请求。
- `TmdbDetailPrefetch` 使用 `tmdbId + mediaType` 标识请求并负责取消与身份隔离。

因此，扩展点应是 `Vod` 的结构化可选字段，并由统一仓库层消费，不能让 Activity 或 T3/T4 各自实现合并逻辑。

### 2.2 OmniBox 可借鉴逻辑

OmniBox 固定提交 `d57b3e6672337febd46feca0d8ad59c6a2b507c3` 使用 `TMDBMetadata` 容器保存资源身份、刮削类型、`scrapeData.tmdb`、更新时间和视频映射。`TMDBDetails` 包含 ID、电影/剧集名称、海报、背景、简介、评分、日期、类型、演职员和剧集信息。页面异步获取元数据，存在时显示增强内容，不存在时退回普通源详情。

可复用部分是结构化对象、媒体类型、资源映射及页面降级。不能直接照搬的部分是：

- 独立元数据接口会在详情之后增加一次请求，不符合源随详情直接返回的目标。
- OmniBox 字段不足以覆盖 WebHTV 的图片集、外部 ID、视频、推荐、相似内容和季集分层能力。
- 整体 `hasData()` 不能表达“已有核心信息但缺少演职员”这类局部缺口。

### 2.3 alist-tvbox：T4 服务端参考

固定版本 `8a222f69a80291e836db702c34daf1ed5bdd5630` 是 AList/TVBox 服务端。它的相关实现分成两条链：

- `src/main/java/cn/har01d/alist_tvbox/dto/TmdbDto.java:9-29` 和 `TmdbCredits.java:7-11` 将 TMDB 的 ID、电影/剧集标题、简介、类型、语言、国家、演职员、海报、评分和日期收敛为服务端 DTO。
- `src/main/java/cn/har01d/alist_tvbox/entity/Tmdb.java:20-38` 保存较窄的 TMDB 媒体快照；`TmdbMeta.java:23-40` 将本地路径、站点和 TMDB 记录关联起来。
- `src/main/java/cn/har01d/alist_tvbox/entity/MediaMetadata.java:15-53` 是更接近本需求的实现：以 `provider + metaId + season` 唯一索引保存 `status`、完整 JSON `payload` 和 `fetchTime`，用于完结剧长期零网络、在播剧按状态/TTL 刷新。
- `src/main/java/cn/har01d/alist_tvbox/dto/MetadataDetails.java:7-62` 已覆盖简介、季总数、集数、播出状态、别名、分集、评分、外部 ID、播放链接、导演、编剧、演员、背景图和背景图候选，比单纯 `TmdbDto` 更适合作为服务端快照字段清单。
- `src/main/java/cn/har01d/alist_tvbox/service/metadata/MetadataService.java:93-214` 实现“持久层 -> provider 内存/网络 -> 持久化”的读路径；旧快照或坏快照视为过期，失败的空对象不覆盖已有快照。
- `src/main/java/cn/har01d/alist_tvbox/service/TmdbEndpoint.java:18-32,126-174` 处理 TMDB API/图片镜像、Worker 池、URL 安全和 API key/Bearer token 隔离。
- `/vod` 详情入口位于 `web/TvBoxController.java:66-103`，最终由 `TvBoxService` 返回 `MovieDetail`；`tvbox/MovieDetail.java:11-35` 没有 `tmdb` 对象。`TvBoxService.java:2687-2768` 将 TMDB 记录映射回 `vod_pic`、`vod_year`、`vod_remarks`、`vod_actor`、`vod_director`、`vod_area`、`type_name`、`vod_lang` 和 `vod_content`。

因此，alist-tvbox 对 C16 的结论是“**服务端生产和快照设计有帮助，输出协议不能直接复用**”：它证明 T4 可以在服务端预抓取并持久化 TMDB，且季必须进入缓存键；但若只照搬其当前 `/vod` 平铺映射，APP 无法区分源字段和 TMDB 字段，也无法表达局部能力完整性。C16 应保留 `Vod.tmdb` 结构化对象，同时允许 T4 内部采用 `provider + tmdbId + season` 的持久化键。

### 2.4 atv-player：客户端参考

固定版本 `09feed1d5e5102f13bf91c9fbb76ea92808cb76d` 是桌面客户端，当前 HEAD 包含完整 metadata 子系统；TMDB Worker 轮询池提交 `e33fc859752f46547b992ecfffab7f5e48b902e1` 不是 HEAD 的祖先，因此本评估不把该提交的轮询实现当作冻结基线，只采纳 HEAD 中已存在的 provider、缓存和详情代码。

可借鉴证据：

- `src/atv_player/metadata/models.py:14-99` 将查询、匹配和详情记录分层；`MetadataRecord` 明确保存标题、原始标题、年份、海报、背景图候选、简介、评分、演员/导演、角色/演职员详情、类型、别名、季集、IMDb/TMDB ID 和详情字段。
- `src/atv_player/metadata/providers/tmdb.py:39-52,880-925` 将电视剧季号编码进 provider ID（`<tmdbId>:season:<n>`），并从 TMDB 原始响应保留 `external_ids`、`images`、cast/crew 角色、别名、季简介和背景图候选；`get_detail_full` 在 `:927-958` 进一步补充季/集和剧集级统计字段。
- `src/atv_player/metadata/merge.py:13-73,140-185` 采用按字段的 provider 优先级，而不是整条记录覆盖；简介还区分 `tmdb` 与 `tmdb_season`，说明剧集总简介和选中季简介不能混作一个无上下文字符串。
- `src/atv_player/metadata/cache.py:48-102` 对 provider/detail ID 做 TTL 缓存并使用 SHA-256 文件键；空结果支持更短 TTL。`cache_key.py:6-25` 在已有 TMDB 外部锚点时跳过标题搜索。
- `src/atv_player/metadata/async_runner.py:17-54` 将 provider 搜索/详情封装为可并行、可捕获单 provider 异常的任务；详情控制器在 `controllers/media_detail_controller.py:509-539,584-620,667-729` 以 TMDB 记录为基础再加载其他 provider，并按当前视图身份清理缓存。
- 测试 `tests/test_metadata_cache.py:26-101` 覆盖详情往返、空结果短 TTL 和通用 payload；`tests/test_metadata_cache_key.py:6-25` 覆盖 TMDB 外部锚点；`tests/test_media_detail_page_ui.py:25-67` 使用 `tv:1399:season:1` 和角色、评分、IMDb/TMDB ID、集列表验证详情展示。

因此，atv-player 对 C16 的结论是“**客户端消费机制有帮助，数据模型不直接移植**”：WebHTV 应引入字段级缺口规划、季级身份和缓存隔离，但仍以本项目已有 `TmdbService`、`TmdbDetailPrefetch`、Gson/Parcelable 和 Android 生命周期为实现边界。其 provider 优先级不能原样变成 WebHTV 的覆盖规则，因为用户要求源内嵌 TMDB 字段优先于 APP 网络补齐；在 C16 中它只作为“网络补齐内部不同 provider 的次级策略”参考。

## 3. 方案比较

### 3.1 保持现状

APP 继续自行匹配并请求 TMDB。兼容风险最低，但无法满足源数据直用，会继续产生重复请求、凭据依赖和匹配误差，不推荐。

### 3.2 复制 OmniBox 独立接口

模型清晰，但 T3 难以统一实现，而且页面仍需额外网络往返，不推荐。

### 3.3 在 Vod 中增加可选 tmdb 对象

T3/T4 现有响应、解析、缓存和页面入口不变；新客户端识别该字段，旧客户端忽略未知字段。APP 按能力组定向补齐，兼容性和可回滚性最佳，推荐。

## 4. 统一返回协议

在详情结果的第一个 `Vod` 中增加可选 `tmdb`：

```json
{
  "list": [{
    "vod_id": "source-item-id",
    "vod_name": "示例剧集",
    "vod_play_from": "线路一",
    "vod_play_url": "第1集$https://example/1.m3u8",
    "tmdb": {
      "schema": 1,
      "id": 1399,
      "media_type": "tv",
      "language": "zh-CN",
      "fetched_at": "2026-09-19T00:00:00Z",
      "complete": ["core", "credits", "images"],
      "detail": {}
    }
  }]
}
```

字段约束：

- `schema`：协议主版本，首版固定为整数 `1`。
- `id`：正整数 TMDB ID。
- `media_type`：仅允许 `movie` 或 `tv`。
- `season_number`：可选非负整数；仅 `tv` 使用，表示选中季上下文。电影固定为 0。
- `language`：可选，表示数据主要语言，例如 `zh-CN`。
- `fetched_at`：可选 ISO 8601 UTC 时间，只用于新鲜度判断。
- `complete`：可选能力组数组，表示生产者确认该组完整，即使内容为空。
- `detail`：保持 TMDB v3 的 snake_case JSON 形状，生产者只需返回实际拥有的字段。

### 4.1 detail 支持字段

首版支持当前 TMDB 详情模式使用的字段：

- 身份与标题：`id`、`title`、`name`、`original_title`、`original_name`。
- 摘要与状态：`overview`、`tagline`、`status`。
- 图片：`poster_path`、`backdrop_path`、`images`。
- 日期与评分：`release_date`、`first_air_date`、`vote_average`、`vote_count`。
- 分类与地区：`genres`、`origin_country`、`original_language`。
- 时长：电影 `runtime`，电视 `episode_run_time`。
- 电视：`number_of_seasons`、`number_of_episodes`、`seasons`。
- 扩展：`external_ids`、`credits`、`videos`、`recommendations`、`similar`。

图片字段可为 TMDB 相对路径或绝对 HTTPS URL。绝对 URL 原样使用；以 `/` 开头的路径由 APP 使用当前图片基址和尺寸策略拼接；其他形式无效。源不能通过该对象提供 TMDB API 地址、Authorization 或请求头。

### 4.2 季与集

`seasons` 可内嵌已知季；季对象可带 `episodes`。单集沿用 TMDB 字段，如 `id`、`season_number`、`episode_number`、`name`、`overview`、`air_date`、`still_path`、`runtime`、`guest_stars` 和 `crew`。

当详情对应“某一选中季”而不是整部剧时，`season_number` 参与缓存和合并身份；不能只用剧集级 `id + media_type`，否则不同季的简介、集列表或海报可能互相污染。等价身份为 `id + media_type + season_number(无则 0)`。

只有 `complete` 包含 `season:1` 时，该季空 `episodes` 才表示确认无数据；否则用户进入该季时仍可按需补齐。单集完整声明使用 `episode:1:1`。

### 4.3 能力组

首版定义：

- `core`
- `credits`
- `images`
- `external_ids`
- `videos`
- `recommendations`
- `similar`
- `season:N`
- `season_videos:N`
- `episode:N:E`
- `episode_videos:N:E`

推荐和相似内容的 `complete` 只表示首批结果完整，不表示所有分页已加载。

## 5. 缺失、空值与合并语义

- 字符串缺失、`null` 或空白均视为缺失。
- ID 必须大于 0。
- 分数必须有限且在合理范围内。未声明完整时零分视为未知；完整组中的零分可表示真实值。
- 对象类型错误时只丢弃该字段，不得使普通详情失败。
- 非空数组可直接采用；空数组只有在相应组包含于 `complete` 时才表示明确为空。
- 图片加载失败只尝试同组候选或普通 `Vod` 图片，不因此自动发起 TMDB 元数据请求。

同一字段优先级：

1. 身份匹配且合法的源内嵌字段。
2. 本地缓存中同 `id + media_type + season_number + language` 的有效字段。
3. 本次按需请求 TMDB 得到的字段。
4. 普通 `Vod` 的标题、封面和简介回退。
5. UI 默认值。

合并必须为 fill-only。用户刷新来源时重新执行详情函数；用户刷新 TMDB 时只更新非源字段。

身份最小校验：`schema == 1`、`id > 0`、媒体类型合法；若 `detail.id` 存在，必须与外层 ID 一致。强冲突时拒绝增强对象，继续显示普通详情并使用现有 TMDB 匹配流程。

## 6. APP 请求规划

### 6.1 首屏

1. 解析并验证 `tmdb`。
2. 在启动 `TmdbDetailPrefetch` 之前计算当前页面所需能力组。
3. 所需字段完整时直接渲染，TMDB 请求数必须为 0。
4. 部分缺失且用户 TMDB 配置可用时，复用现有详情请求，并只填缺口。
5. 只有合法 ID 时跳过标题搜索，直接按 ID 补齐。
6. ID 缺失或身份无效时维持现有匹配流程。
7. TMDB 未配置或补齐失败时，保留源增强数据与普通详情，不把增强失败升级为整页失败。

### 6.2 延迟能力

- 选择某季时检查 `season:N`。
- 打开单集扩展信息时检查 `episode:N:E`。
- 打开视频区时检查对应视频组。
- 推荐和相似内容先用内嵌首批结果，加载更多继续走现有分页。
- 页面关闭、切源或身份变化时继续使用现有取消与 identity 机制，旧请求不得覆盖新页面。

内嵌数据不依赖 APP 的 TMDB API Key。没有凭据时仍应完整显示已有源数据，只是不补缺口。

## 7. 数据模型与代码边界

批准实施后建议新增：

- `Vod.tmdb: TmdbSourcePayload`
- `TmdbSourcePayload`：版本、身份、语言、时间、完整组及详情对象
- `TmdbCapabilityPlanner`：纯函数计算缺口
- `TmdbSourceMerger`：校验、图片规范化和 fill-only 合并
- `TmdbDetailRepository`：统一源数据、本地缓存与网络补齐

同步覆盖 Gson、`Vod` Parcelable 或替代的大对象传递策略、`Result` 复制路径、`VodDetailCache`、页面生命周期和缓存键。Activity 不直接解析 JSON，源对象也不能未经校验写入 `TmdbService` 缓存。

## 8. 缓存、安全与负载

- 详情缓存继续保存整个 Result，旧缓存没有 `tmdb` 时按旧逻辑工作。
- TMDB 补齐缓存键必须包含 `id + media_type + season_number + language`，不能让同一剧不同季共享详情或简介。
- T4 内部持久化可采用 `provider + tmdbId + season_number` 唯一键，并保存状态、抓取时间和 JSON 快照；完结数据可长 TTL，在播数据按状态刷新。网络失败或空白快照不得覆盖已有有效快照。
- 合并后保留字段来源归属，防止缓存命中后误覆盖源字段。
- `fetched_at` 只影响刷新建议，不阻止旧数据先展示。
- APP 补齐只能使用用户当前 TMDB 配置，禁止源控制 API 地址、图片基址或凭据。
- 建议限制 `tmdb` 对象为 2 MiB、单数组 500 项、单字符串 64 KiB；超限时局部丢弃增强组，不影响播放线路。
- 日志只记录站点 key、Vod ID、TMDB ID、组命中和拒绝原因，不记录凭据或完整原始内容。

## 9. T3 与 T4 生产者指南

### 9.1 T3

继续返回原有 `detailContent(List<String> ids)` JSON，只在目标 Vod 内增加 `tmdb`。不新增回调，也不要求宿主向爬虫提供 TMDB 凭据。Java、JS 和 Python 桥接均将其作为普通 JSON 字段。

### 9.2 T4

继续响应现有 detail 请求。有合法 TMDB 数据时内嵌相同合同；没有时省略 `tmdb`，不得返回伪造 ID 或滥用 `complete`。

只有身份数据也有价值：

```json
"tmdb": {
  "schema": 1,
  "id": 1399,
  "media_type": "tv",
  "detail": {}
}
```

完整首屏对象应准确声明已有能力。若 `credits`、`images`、`videos`、`recommendations` 或 `similar` 已列入 `complete`，其中的空数组就是确认为空，APP 不再访问 TMDB。

T4 内部若有持久化元数据，建议按 `provider=tmdb、metaId=id、season=season_number` 保存，再在 `/vod` 的 `MovieDetail`/详情 `Vod` 序列化阶段组装为 `tmdb`。不能仅把 `Tmdb` 表的 `cover/score/actors` 平铺字段当作协议，因为这会丢失来源、季上下文、能力组和空值语义。

## 10. 收益、风险与取舍

收益：完整数据可实现零 TMDB 请求，降低延迟和凭据依赖；合法 ID 可避免标题误匹配；部分数据可增量补齐；旧源和普通详情兼容。

主要风险及控制：

- 错误 ID：严格身份校验，冲突时降级。
- 大型季集数据：能力组、延迟加载和大小上限。
- 空数组歧义：使用 `complete`。
- 文案或图片差异：源优先，fill-only。
- 数据陈旧：记录语言和抓取时间，时间敏感组按访问场景判断。
- T3/T4 分叉：两端只生产同一合同，APP 集中解析和消费。

## 11. 分阶段实施计划

### 阶段 1：协议和纯逻辑

新增模型、能力组、校验与合并器；给 `Vod` 增加可选字段；覆盖 Gson、Parcelable、复制和缓存合同测试。

### 阶段 2：详情模式接入

在预取前规划缺口；完整首屏直接渲染；部分缺失复用现有 `TmdbService.detail()`；保持取消和身份隔离。

### 阶段 3：季集与延迟组

接入季、集和各级视频组；推荐/相似首批内嵌，分页保持现状；补充诊断和生产者文档。

三个阶段独立可回滚。本轮不授权任何阶段实现。

## 12. 验收矩阵

1. 无 `tmdb` 的旧 T3/T4 响应与现状一致。
2. T3/T4 返回相同 JSON 时解析结果和请求计划一致。
3. 完整首屏打开详情时 TMDB 请求数为 0。
4. 只缺 `credits` 时最多发一次补齐请求，源字段不被覆盖。
5. 只有合法 ID 时跳过搜索并直接按 ID 补齐。
6. ID、媒体类型或 `detail.id` 冲突时拒绝增强对象，普通详情和播放仍可用。
7. 未声明完整的空数组触发按需补齐；已声明完整的空数组不联网。
8. 未配置 TMDB Key 时仍展示全部源增强数据。
9. 绝对图片 URL、相对路径和非法路径分别按合同处理。
10. 详情缓存往返后字段、来源归属和 `complete` 不丢失，旧缓存可读。
11. Parcelable 或复制后身份与组不丢失，且不产生超大 Binder 传输。
12. 切源、快速退出或切换条目时，旧请求不能覆盖新页面。
13. 电视内容只在打开缺失季或集时访问对应接口。
14. 超限或类型错误 payload 被局部拒绝，普通详情和播放线路不受影响。

最小实机验证：移动端和电视端各测试一条完整 T3、一条部分 T4 和一条无 TMDB 的旧源，记录首屏请求数、字段渲染、季集访问和切源隔离。

## 13. 证据与边界

- WebHTV 基线 `32a52698e5dab09fe18e49d18849a947057ca717`：`SiteViewModel`、`SiteApi`、`Vod`、`TmdbService`、`TmdbDetailPrefetch` 证明 T3/T4 已汇聚到 Result/Vod，并说明当前 TMDB 请求和生命周期边界。
- OmniBox 基线 `d57b3e6672337febd46feca0d8ad59c6a2b507c3`：`TMDBMetadata`、`TMDBDetails`、服务端元数据处理和页面消费证明结构化元数据及降级方式，也显示独立请求模型不满足本需求。
- alist-tvbox `8a222f69a80291e836db702c34daf1ed5bdd5630`：`dto/TmdbDto.java`、`dto/MetadataDetails.java`、`entity/MediaMetadata.java`、`service/metadata/MetadataService.java`、`service/metadata/TmdbMetadataProvider.java`、`service/TmdbEndpoint.java`、`web/TvBoxController.java` 和 `service/TvBoxService.java`。证据等级 A/B：实际源码和服务端测试；支持“服务端可按季持久化 TMDB 快照、失败不覆盖旧值、图片/凭据应隔离”，同时证明其当前 `/vod` 是平铺 `vod_*` 输出而非 C16 结构化合同。
- atv-player `09feed1d5e5102f13bf91c9fbb76ea92808cb76d`：`metadata/models.py`、`metadata/providers/tmdb.py`、`metadata/merge.py`、`metadata/cache.py`、`metadata/cache_key.py`、`metadata/async_runner.py`、`controllers/media_detail_controller.py` 及 `tests/test_metadata_cache.py`、`test_metadata_cache_key.py`、`test_media_detail_page_ui.py`。证据等级 A/B：实际源码和测试；支持“客户端应按字段合并、按季隔离身份、缓存外部锚点、异步任务隔离旧视图”。TMDB Worker 轮询提交 `e33fc859752f46547b992ecfffab7f5e48b902e1` 非该 HEAD 祖先，未纳入采用范围。
- 外部 PR、Issue、论文和性能基准不适用：本阶段只设计兼容 JSON 合同，不升级依赖、不改变运行行为，也不提出未经测量的性能结论。

## 14. 最终建议

**建议实施** `Vod.tmdb` 可选对象、TMDB 原生字段形状、能力组完整声明及 fill-only 合并；增加 `season_number` 上下文和 `id + media_type + season_number + language` 缓存键。吸收 alist-tvbox 的服务端按季快照、状态/TTL、失败不覆盖和图片/凭据隔离，吸收 atv-player 的字段级合并、外部 ID 直达、季级 provider ID、空结果短 TTL 和异步隔离。不要增加独立 T3/T4 元数据接口，不要在数据完整时连接 TMDB，也不要让源控制 APP 的 TMDB 地址或凭据。

## 15. 实现合同

本节是实现的唯一执行依据。若本节与前文概念描述冲突，以本节为准；未列入本节的 TMDB 字段不得成为首版的必需字段。

### 15.1 WebHTV 修改文件清单

首版客户端实现限定在以下路径：

| 文件 | 必须改动 |
| --- | --- |
| `app/src/main/java/com/fongmi/android/tv/bean/Vod.java` | 增加可选 `TmdbSourcePayload tmdb`，Gson 解析、getter/setter、Parcelable、`isSameContent` 参与内容比较 |
| `app/src/main/java/com/fongmi/android/tv/bean/TmdbSourcePayload.java` | 新增协议容器、校验、能力组、来源标记和深拷贝 |
| `app/src/main/java/com/fongmi/android/tv/bean/TmdbSourceDetail.java` | 新增 TMDB 原始详情包装；内部 `JsonObject` 以 JSON 字符串保存，不直接放进 Parcelable |
| `app/src/main/java/com/fongmi/android/tv/ui/helper/TmdbSourcePayloadParser.java` | 新增大小限制、身份校验、字段类型校验和图片 URL 规范化 |
| `app/src/main/java/com/fongmi/android/tv/ui/helper/TmdbSourceCapabilityPlanner.java` | 新增能力组判定和缺口计划，必须是无 Android UI 副作用的纯逻辑 |
| `app/src/main/java/com/fongmi/android/tv/ui/helper/TmdbSourceMerger.java` | 新增 source/cache/network 的字段级 fill-only 合并 |
| `app/src/main/java/com/fongmi/android/tv/api/SiteApi.java` | 不改变 T3/T4 请求；仅确保解析后的 `Vod.tmdb` 随 Result 缓存返回 |
| `app/src/main/java/com/fongmi/android/tv/ui/activity/TmdbDetailActivity.java` | 重排 `loadContent` 为先取源详情、再决定 TMDB 请求；增加 payload 到现有 `TmdbBundle` 的适配 |
| `app/src/main/java/com/fongmi/android/tv/service/TmdbService.java` | 仅补充缺口请求入口/缓存键；保留现有请求 URL 和认证策略 |
| `app/src/main/java/com/fongmi/android/tv/utils/VodDetailCache.java` | 不改变源详情键；如新增 TMDB 合并缓存，单独使用带季和语言的键，不把网络合并结果写回源内容缓存 |

不允许在首版修改 `catvod/`、`quickjs/`、`chaquo/` 的爬虫 ABI，也不允许新增 TMDB 独立 HTTP 接口。

### 15.2 Java 模型字段

`TmdbSourcePayload` 固定字段如下：

| 字段 | Java 类型 | JSON | 规则 |
| --- | --- | --- | --- |
| `schema` | `int` | `schema` | 仅接受 `1` |
| `tmdbId` | `int` | `id` | `> 0` |
| `mediaType` | `String` | `media_type` | 仅 `movie`/`tv`，统一小写 |
| `seasonNumber` | `int` | `season_number` | `tv` 可为 `0` 或正数；`movie` 必须为 `0` |
| `language` | `String` | `language` | 空值规范为 `""` |
| `fetchedAt` | `String` | `fetched_at` | 仅校验长度和 ISO-8601 形状，不参与身份 |
| `complete` | `Set<String>` | `complete` | 未知组丢弃；保留合法组并去重 |
| `detailJson` | `String` | `detail` | 保存 TMDB snake_case JSON；默认 `{}` |
| `sourceKind` | `String` | 不出现在协议 | `source_tmdb` / `cache_tmdb` / `remote_tmdb`，仅 APP 内部使用 |

`Vod` 中的字段声明为 `@SerializedName("tmdb") private TmdbSourcePayload tmdb;`，不添加 Simple XML `@Element`，因此 XML 详情自然忽略该扩展。旧 JSON、旧缓存和没有 `tmdb` 的源必须得到 `null`。

`TmdbSourceDetail` 不把所有 TMDB v3 字段复制成 Java 成员；保留 `JsonObject` 字符串并提供以下白名单读取器：`id`、标题、简介、海报、背景图、日期、评分、类型、地区、时长、`images`、`credits`、`aggregate_credits`、`external_ids`、`videos`、`recommendations`、`similar`、`seasons`、`episodes`、`translations`、`content_ratings`、`release_dates`。读取器遇到类型错误返回空值，不抛出到详情页。

### 15.3 JSON 规范与完整示例

T3/T4 只能在详情 `list[0]` 中返回 `tmdb`。搜索列表不返回该字段，播放接口也不返回该字段。`detail` 必须是 JSON object；不能是字符串、数组或 TMDB API 响应外层包装。

电影完整示例：

```json
{
  "list": [{
    "vod_id": "movie-1",
    "vod_name": "示例电影",
    "vod_pic": "https://source.example/poster.jpg",
    "vod_content": "源详情简介",
    "vod_play_from": "线路一",
    "vod_play_url": "正片$https://source.example/movie.m3u8",
    "tmdb": {
      "schema": 1,
      "id": 550,
      "media_type": "movie",
      "season_number": 0,
      "language": "zh-CN",
      "complete": ["core", "credits", "images", "external_ids", "videos", "recommendations", "similar"],
      "detail": {
        "id": 550,
        "title": "Fight Club",
        "original_title": "Fight Club",
        "overview": "...",
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
        "release_date": "1999-10-15",
        "vote_average": 8.4,
        "vote_count": 28000,
        "genres": [],
        "credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt0137523"},
        "videos": {"results": []},
        "recommendations": {"page": 1, "results": []},
        "similar": {"page": 1, "results": []}
      }
    }
  }]
}
```

电视剧选中季示例：

```json
{
  "list": [{
    "vod_id": "show-1",
    "vod_name": "示例剧集",
    "vod_play_url": "S01E01$https://source.example/1.m3u8",
    "tmdb": {
      "schema": 1,
      "id": 1399,
      "media_type": "tv",
      "season_number": 1,
      "language": "zh-CN",
      "complete": ["core", "credits", "images", "external_ids", "season:1"],
      "detail": {
        "id": 1399,
        "name": "Game of Thrones",
        "original_name": "Game of Thrones",
        "overview": "...",
        "first_air_date": "2011-04-17",
        "vote_average": 8.4,
        "number_of_seasons": 8,
        "number_of_episodes": 73,
        "seasons": [{"season_number": 1, "episode_count": 10, "episodes": []}],
        "aggregate_credits": {"cast": [], "crew": []},
        "external_ids": {"imdb_id": "tt0944947"}
      }
    }
  }]
}
```

`season:1` 的完整语义是 `seasons[]` 中第 1 季对象、`episodes` 数组和该季需要的 `images/credits` 均已由生产者确认；如果只返回季摘要而没有集列表，不能声明 `season:1`，只能返回 `core`。

### 15.4 能力组到字段和请求映射

| 能力组 | 最低字段/条件 | APP 现有请求 | 首屏还是延迟 |
| --- | --- | --- | --- |
| `core` | `id`、标题、简介、日期、`vote_average`、`genres`；TV 还需 `number_of_seasons`/`number_of_episodes`（若 TMDB 有值） | `TmdbService.detail(item, config, false)` | 首屏 |
| `credits` | `credits` 或 TV 的 `aggregate_credits`，cast/crew 均可为空但必须声明完整 | 同上 | 首屏 |
| `images` | `poster_path`、`backdrop_path` 和 `images` 已覆盖当前页面需要的语言候选 | 同上 | 首屏 |
| `external_ids` | `external_ids` object（无 ID 也必须能声明空） | 同上 | 首屏 |
| `videos` | 详情级 `videos.results` | `TmdbService.videos` 或现有相关视频入口 | 延迟 |
| `recommendations` | `recommendations.page=1` 和 `results` | `TmdbService.recommendations(item, config, 1)` | 首屏/延迟加载 |
| `similar` | `similar.page=1` 和 `results` | `TmdbService.similar(item, config, 1)` | 首屏/延迟加载 |
| `season:N` | 季摘要、`episodes`、季图和季演职员 | `TmdbService.season(item, N, config, detail)` | 选季时 |
| `season_videos:N` | 当前季视频 results | `TmdbService.seasonVideos(...)` | 打开视频时 |
| `episode:N:E` | 单集字段和当前集详情字段 | `TmdbService.episode(item, N, E, config, detail)` | 打开单集时 |
| `episode_videos:N:E` | 单集视频 results | `TmdbService.episodeVideos(...)` | 打开视频时 |

规划器规则：首屏只要求 `core`、`credits`、`images`；`external_ids` 只在当前 UI 显示 IMDb/外部 ID 或需要身份确认时要求。`recommendations`、`similar`、`videos` 不得因为缺少而阻塞首屏。TV 选季后才要求对应 `season:N`；不能用 `season:1` 满足 `season:2`。

### 15.5 详情页精确调用顺序

修改 `TmdbDetailActivity.loadContent()`（当前 `:2312`）为以下顺序，禁止在源详情完成前提交 `loadTmdbResult()`：

```text
generation = ++loadGeneration
detailTasks.cancelAll()
sourceResult = SiteApi.detailContent(key, id)
loadedVod = sourceResult.getVod()
payload = TmdbSourcePayloadParser.parse(loadedVod.getTmdb())
sourceBundle = TmdbSourceAdapter.toBundle(payload, loadedVod, config)
plan = TmdbSourceCapabilityPlanner.plan(sourceBundle, payload, currentUiState)
applyLoaded(loadedVod, sourceBundle, ...)

if plan.hasInitialNetworkGaps() and tmdbConfig.isReady() and siteAllowsTmdb:
    networkBundle = loadTmdbMissing(plan, payload.identity())
    mergedBundle = TmdbSourceMerger.fillOnly(sourceBundle, networkBundle)
    applyLoadedIfGenerationCurrent(loadedVod, mergedBundle)
```

具体分支：

1. payload 合法且首屏能力完整：不创建 `TmdbLoadResult`，不调用搜索、`loadTmdbBundle` 或 `TmdbService.detail`。
2. payload 合法但缺 `core`：用 payload 的 ID 构造 `TmdbItem`，直接调用详情接口；禁止标题搜索。
3. payload 合法但缺 `credits/images`：直接按 ID 请求完整详情并只合并缺口。
4. payload 只有 ID 且 `detail` 为空：直接按 ID 请求；只有 payload 无效或 ID 缺失时才进入原有 `searchResolvedTmdbMatch()`。
5. payload 冲突（外层 ID、`detail.id`、媒体类型不一致）：丢弃 payload，保留普通源详情，并执行现有匹配流程。
6. `reusableBundle` 非空时仍先合并合法 source payload；复用对象只作为低优先级网络缓存，不得覆盖源字段。
7. 每个后台结果回 UI 前检查 `generation`、`identity`、`season_number` 和 `mediaType`，任一不符直接丢弃。

`TmdbSourceAdapter.toBundle()` 必须填充现有内部 record：

| `TmdbBundle` 成员 | 来源 |
| --- | --- |
| `item` | payload 身份和 detail 标题/简介/图片/评分构造 `TmdbItem` |
| `detail` | `detailJson` 解析后的 `JsonObject` |
| `cast`/`creators` | `credits.cast/crew` 或 `aggregate_credits` 经现有转换器 |
| `photos` | `images.backdrops/posters` 与 detail 主图去重 |
| `related` | `recommendations.results` + `similar.results` 去重 |
| `seasons`/`seasonCounts` | `detail.seasons` |
| `seasonEpisodes` | 当前 `season_number` 对应季的 `episodes` |
| `seasonCast`/`seasonPhotos` | 对应季对象的 `credits`/`images` |

适配器不得调用网络；缺字段返回空集合，交给 planner 决定是否补齐。

### 15.6 合并、来源和缓存实现

`TmdbSourceMerger` 保存三层对象：`sourcePayload`、`networkPayload`、`effectiveBundle`，不把网络结果写回 `Vod.tmdb`。字段来源以能力组记录：`SOURCE`、`LOCAL_CACHE`、`REMOTE_TMDB`、`VOD_FALLBACK`。

缓存键固定为：

```text
tmdb-detail:{mediaType}:{tmdbId}:season={seasonNumber}:lang={language}:include={capabilityMask}
```

能力 mask 必须排序后生成，不能以 Java Set 的迭代顺序直接拼接。详情源缓存仍使用现有 `VodDetailCache` 的 `source + NUL + id` 键；不要改变其 TTL 或把合并结果存入该缓存。TMDB 网络缓存可沿用 `TmdbService` 现有 cache，但新季键必须追加 `seasonNumber`。

fill-only 的字段规则：字符串空白、数值未定义、对象缺失、未声明 complete 的空数组都允许由低优先级填充；源字段非空或其能力组明确声明空数组后，低优先级不得覆盖。`detail.id` 和身份字段永不由低优先级修改。

`Vod` Parcelable 只传 `tmdb` 的协议字段和 `detailJson` 字符串；传输前执行 256 KiB 单对象限制。超过限制不走 Parcelable，继续通过 `VodDetailCache.put()` 传递 key；绝不把 `JsonObject` 或完整图片/推荐对象直接写入 Binder。

### 15.7 T3/T4 服务端实现边界

T3 只需在现有 `detailContent(ids)` 返回的 `list[0]` 增加 `tmdb`，不新增函数、不改变 `ids` 语义；JS/Python/Java 爬虫桥接均把它当作普通 JSON。

T4 只需改造其 `ac=detail&ids=` 响应的 `MovieDetail`/Vod 序列化层；若使用 alist-tvbox 的实现，内部可将 `MediaMetadata(provider, metaId, season, status, payload, fetchTime)` 映射为 C16 对象，但不能把 `vod_*` 平铺字段当作替代合同。T4 必须：

- 没有合法快照时省略 `tmdb`，不能返回空 ID 对象。
- 读取快照失败时返回普通详情，不让整个 `ac=detail` 失败。
- 按 `provider=tmdb + metaId + season` 读写，网络失败不覆盖旧 payload。
- 图片只返回相对 TMDB path 或受信任的 HTTPS 图片 URL，不能返回 API key、Authorization、API base 或任意请求头。
- 服务端响应保持 JSON；XML 类型站点不承担 `tmdb` 合同，APP 仅从 JSON 读取该字段。

T4 的服务端测试必须验证旧客户端仍可读取 `vod_*`，新客户端读取 `tmdb`，同一 `ids` 在无快照、完整快照、部分快照和坏快照四种状态下均有确定响应。

### 15.8 测试文件和通过条件

首版必须新增或扩展以下测试：

| 测试 | 必须证明 |
| --- | --- |
| `TmdbSourcePayloadTest` | Gson 解析、schema/media/id/season 校验、未知组和坏类型处理 |
| `TmdbSourceCapabilityPlannerTest` | 每个能力组缺口、季/集隔离、完整空数组不联网 |
| `TmdbSourceMergerTest` | source > cache > network > Vod fallback，源值不被覆盖 |
| `TmdbSourceAdapterTest` | payload 无网络转成现有 `TmdbBundle` 所需的所有集合 |
| `VodTmdbParcelableTest` | Parcelable 往返、旧对象兼容、256 KiB 超限走 cache key |
| `SiteApiT3TmdbDetailTest` | type 3 JSON 详情保留 tmdb 且缓存往返不丢失 |
| `SiteApiT4TmdbDetailTest` | type 4 JSON 详情保留 tmdb，普通字段不变 |
| `TmdbDetailSourcePayloadTest` | 完整 payload 不调用 TMDB；部分 payload 只按 ID 补齐 |
| `TmdbDetailGenerationTest` | 切源、切季、退出后旧任务不能更新页面 |
| `TmdbServiceCacheKeyTest` | media/id/season/language/capability 不串缓存 |

“零 TMDB 请求”必须通过可注入的 fake `TmdbService` 或请求计数器断言，不能仅通过 UI 截图推断。每个测试失败都必须保留实际请求 URL/能力组，便于确认没有误触发标题搜索或整包详情请求。

## 16. 实施顺序与提交边界

实施必须按以下顺序，每阶段独立编译/测试并保持可回滚：

1. **协议模型**：新增 payload/detail/parser，扩展 `Vod` Gson、Parcelable、copy/diff；运行模型和解析测试。
2. **纯逻辑**：实现 adapter/planner/merger，运行字段、能力、季集、来源优先级测试。
3. **源接入**：确认 T3/T4 JSON 详情和 `VodDetailCache` 往返，运行 SiteApi 测试。
4. **详情页接入**：重排 `loadContent` 的先源后网状态机，接入 `TmdbBundle`，运行零请求、缺口补齐和 generation 测试。
5. **延迟能力**：接入季、集、视频、推荐分页，运行季集和视频回归。
6. **设备验收**：移动端、Leanback 各验证完整 T3、部分 T4、无扩展旧源；记录网络请求计数和页面结果。

每阶段只允许修改对应任务文档声明的客户端文件；T4 服务端应使用独立任务文档和独立提交，不与 APP 提交混合。任何新增字段、接口、依赖或跨仓库变更都必须先更新本实现合同并重新评审。

## 17. 实施记录

### 阶段 1：协议模型

- 提交：`4865bd7ad08cfd1dd12fba60a202b346e71336a0`；恢复标签 `recovery/C16-stage1/20260919104302-4865bd7ad08c`。
- 已实现 `TmdbSourcePayload` 的固定协议字段、内部来源标记、深拷贝、身份合法性判断、确定性能力组集合和 Binder 大小判断。
- 已实现 `TmdbSourceDetail` 的 `JsonObject` 字符串保存及白名单读取器；读取器遇到缺失或类型错误返回空值，不向详情页抛出异常。
- 已实现 `TmdbSourcePayloadParser`：校验 `schema/id/media_type/season_number/detail.id/detail.season_number`，清理未知能力组和坏类型字段，规范化图片 URL，并执行 2 MiB、500 项、64 KiB 限制。
- 已扩展 `Vod`：`tmdb` 参与 Gson、Parcelable 和 `isSameContent`；超过 256 KiB 时不把 `detailJson` 放入 Binder，而是通过现有 `VodDetailCache.put()` 生成 key。
- 定向验证：`TmdbSourcePayloadTest`、`VodTmdbParcelableTest` 共 7 项通过；同一 Gradle 调用完成 Mobile Arm64 单测和 Leanback Arm64 Debug Java 编译，结果 `BUILD SUCCESSFUL`。
- 未验证项：真实 Android Binder 往返、设备详情页消费和 T3/T4 源接入，按第 16 节后续阶段继续处理。

### 阶段 2：纯逻辑

- 提交：`bbd0a4de5fbbbe497cc4f5935a6c17ed46d50708`；恢复标签 `recovery/C16-stage2/20260919105729-bbd0a4de5fbb`。
- 将原活动内私有 `TmdbBundle` 提升为 `ui.helper.TmdbBundle`，保持现有字段和详情页调用不变，供纯逻辑和后续源接入共用。
- 新增 `TmdbSourceAdapter`：从已校验 payload 无网络构造 `TmdbItem`、详情 JSON、演职员、图片、相关推荐、季集、季演职员和季图片；绝对 HTTPS 图片保持原样，相对路径使用当前 APP 图片基址。
- 新增 `TmdbSourceCapabilityPlanner`：按首屏、季、集和视频场景计算 required/available/missing，完整空组视为已满足，季与集严格隔离。
- 新增 `TmdbSourceMerger`：按 source > local cache > remote TMDB 的 fill-only 规则合并 item、detail、集合和季映射，并记录字段来源；源声明完整的空值不会被覆盖。
- 修复 `TmdbSourcePayloadParser` 对数组元素递归校验时误用父数组字段类型、导致 cast/images/seasons 等数组被清空的问题；新增 adapter/planner/merger 测试覆盖。
- 定向验证：`TmdbSourceAdapterTest`、`TmdbSourceCapabilityPlannerTest`、`TmdbSourceMergerTest` 共 10 项通过；同一 Gradle 调用完成 Leanback Arm64 Debug Java 编译，结果 `BUILD SUCCESSFUL`。
- 未验证项：真实网络补齐请求、Activity 状态机接线、真实设备 UI 和源详情缓存往返，按阶段 3-6 继续处理。

### 阶段 3：源接入

- 提交：`070efd6f4ec818a840f4b2bccb384389d116b368`；恢复标签 `recovery/C16-stage3/20260919105928-070efd6f4ec8`。
- 新增 `SiteApiT3TmdbDetailTest`：使用 T3 `detailContent` 的 JSON 形状验证 `Vod.tmdb`、身份、能力组和详情读取器保留，并通过 `VodDetailCache` 内容往返后仍保留完整协议。
- 新增 `SiteApiT4TmdbDetailTest`：使用 T4 `ac=detail` 的 JSON 形状验证电视剧季上下文、`season:1`、季数组和缓存往返，普通详情字段未被改变。
- 本阶段确认 Gson、`Result` 列表复制和现有详情缓存无需生产代码改动；`SiteApi` 的 T3/T4 请求与分派保持不变。
- 定向验证：两个测试类共 4 项通过，Mobile Arm64 Debug 单测任务返回 `BUILD SUCCESSFUL`。
- 未验证项：Activity 尚未在调用 `TmdbDetailPrefetch` 前消费 payload，真实 T3/T4 网络请求和页面请求数留待阶段 4/6。

### 阶段 4：详情页接入

- 提交：`7de6bed8886ab34e429f4e66295d12e946815393`；恢复标签 `recovery/C16-stage4/20260919111304-7de6bed8886a`。
- `TmdbDetailActivity.loadContent` 已改为先完成 `SiteApi.detailContent`、解析并应用 `Vod.tmdb`，再决定是否创建旧 TMDB 匹配任务；旧源路径仍在源详情完成后串行执行。
- 合法 payload 先按 identity 构造 `TmdbBundle`，再计算 `TmdbSourceCapabilityPlanner` 首屏缺口；`core/credits/images` 完整时直接返回，不调用来源详情 TMDB 请求。
- 部分 payload 使用 `TmdbService.detailForSource()` 按 TMDB ID 请求，合并后通过 `TmdbSourceMerger.fillOnly()` 仅填缺口；不再为有效身份执行标题搜索。
- `TmdbService` 新增 source detail 缓存键，包含媒体类型、TMDB ID、季上下文、语言和排序后的能力 mask；请求 URL、认证和磁盘缓存实现保持现有策略。
- `TmdbSourceAdapter.fromNetwork()` 复用与服务端 payload 相同的字段解析、图片规范化和季集映射，确保 source 与 network bundle 形状一致。
- 后台合并回 UI 前继续检查 generation、当前 `Vod` 和 TMDB identity；旧页面、切源或退出不会应用迟到结果。
- 同步调整旧 standalone 源码测试：仍保留单次首屏绑定和季预加载，但断言顺序改为 source detail -> payload plan -> TMDB wait。
- 定向验证：`TmdbDetailSourcePayloadTest`、`TmdbDetailGenerationTest`、`TmdbServiceCacheKeyTest`、`TmdbSourceAdapterTest`、`TmdbDetailActivityLayoutTest`、`TmdbUIAdapterTest` 共 75 项通过；Leanback Arm64 Debug Java 编译通过，Gradle 返回 `BUILD SUCCESSFUL`。
- 未验证项：真实网站 T3/T4 网络请求计数、移动端/电视端字段渲染和真实退出/切源竞态，留待阶段 6 设备验收。

### 阶段 5：延迟能力

- 新增活动级 source payload 身份状态；仅当当前 TMDB 身份仍与源 payload 一致时，季、集和视频的完整组短路生效。
- `fetchSeasonIfNeeded` 对已由 `season:N` 完整声明的季直接返回；内部 stale split 探针也跳过已完整声明的季。用户显式 refresh 仍保留原刷新语义。
- 长按单集时，`episode:N:E` 完整声明直接使用已绑定的 TMDB 分集元数据打开详情，不再请求单集接口；缺失该组时继续走原补齐路径。
- 新增 `TmdbSourceAdapter.videos()`：无网络从 detail、season 和 episode 对象解析 `TmdbVideo`，保持 title/season/episode scope，并按现有规则去重排序。
- 视频区仅在当前上下文需要的 `videos`、`season_videos:N`、`episode_videos:N:E` 全部声明完整时使用内嵌视频；否则保持现有网络聚合，避免只补一部分造成上下文缺口。
- 推荐和相似内容继续使用阶段 2 的内嵌首批 `related`；加载更多和个性化推荐仍走现有分页/服务流程。
- 定向验证：`TmdbSourceAdapterTest` 新增三 scope 视频解析；`TmdbDetailSourcePayloadTest` 新增季、集、视频短路断言；连同 generation、缓存键、布局和 UI 接线测试共 203 项通过；Leanback Arm64 Debug Java 编译通过。
- 未验证项：真实设备上选择缺失季、长按缺失集、打开视频区的请求数与 UI 结果，留待阶段 6。

### 阶段 6：设备验收

- 测试入口：新增 `app/src/androidTest/java/com/fongmi/android/tv/ui/activity/C16TmdbSourceDetailDeviceTest.java`。测试通过 `ActivityScenario` 启动未导出的 `TmdbDetailActivity`，等待真实 View 文本后断言字段渲染；夹具使用 `adb reverse` 暴露本机 T4/T3 源。测试仅在 `Config.vod()` 指向 C16 夹具时执行，普通设备保持 JUnit skip，不影响既有 AndroidTest。
- 设备：`192.168.50.3:5561`，`HD1910`，Android 9，`x86_64 + arm64` 兼容层，1920×1080/280 dpi。所有数据改动在测试前备份，验收后已恢复 `com.silent.android.webhtv_preferences.xml` 和 `databases/tv`；测试 APK 已卸载，reverse 已移除。
- Mobile APK：SHA-256 `17e0ec2c403a9185134cbc609fb80867a65a54094b5ccc1f6166ba2c79256dbe`。Leanback APK：SHA-256 `563a222b1773ad8df7beeddb765d49cf6e6e39701a2fbe1622c63785ce873887`。AndroidTest APK：SHA-256 `4a659334f8c617b45e5bcb53c5867a52b5c7250c74b15684864e266a86367ed8`。
- Mobile 结果：完整 T4、部分 T4、无扩展旧源、完整 T3 各 1 项仪器测试通过。
- Leanback 结果：完整 T4、部分 T4、无扩展旧源、完整 T3 各 1 项仪器测试通过；另通过完整 TV 季集场景 1 项。
- 完整 T4 请求证据：夹具仅收到 `/config.json` 与 `/t4_complete?ac=detail&ids=c16-t4-complete-1`；日志为 `source payload plan required=[core, credits, images] missing=[]`，没有 TMDB detail/search 请求。UI 显示 `C16 Complete T4`、`Embedded complete overview`、`Embedded Actor`。
- 完整 T3 请求证据：夹具仅收到 `/config.json` 与 `/t3_complete.js`；Mobile 和 Leanback 均为 `required=[core, credits, images] missing=[]`，没有 TMDB detail/search 请求。JS Spider 返回普通 `detailContent` JSON，证明 T3 JSON 字段无需 ABI 改动即可透传。
- 部分 T4 请求证据：夹具收到 `/t4_partial?ac=detail&ids=c16-t4-partial-1`；Mobile 日志为 `missing=[credits, images]`，Leanback 同组，随后只出现按 TMDB ID 的 `requestJson type=detail`，没有标题搜索。UI 保留 `C16 Partial T4` 和 `Source partial overview must win`。
- 旧源证据：夹具收到 `/legacy?ac=detail&ids=c16-legacy-1`；Mobile/Leanback 继续走原有 `load tasks ... singlePass=true`、`tmdb wait` 与单次首屏绑定，UI 显示普通标题、`line-a` 线路和 `正片` 选集，无崩溃。
- 季集证据：Leanback 完整 TV 夹具仅收到 `/t4_tv_complete?ac=detail&ids=c16-t4-tv-1`；`season:1`、`episode:1:1` 与视频组均已内嵌，UI 显示 `Embedded Episode 1`，日志没有 `season`、`episode` 或 TMDB detail/search 请求。
- 切源/退出隔离：设备场景不制造真实竞态；阶段 4 的 `TmdbDetailGenerationTest` 已验证迟到的 source-fill 结果在 generation、当前 Vod 或 TMDB identity 变化后不会更新页面。真实弱网快速切源仍需发布前抽样关注，但不阻塞本期合同完成。
