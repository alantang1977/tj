package com.fongmi.android.tv.ui.activity;

import com.fongmi.android.tv.theme.ThemeTokens;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

/**
 * 电视版「焦点 = 主题色边框环」契约。
 *
 * 用户报告（两张实机截图）：
 * 1. 关于 WebHomeTV 弹窗的 `检查更新 / 加速源 / 我已知悉` 三个按钮和右下角齿轮图标，
 *    D-pad 焦点移上去基本看不出来；
 * 2. 追更页顶栏 `检查更新/全部已读/显示全部/导入订阅` 与卡片内
 *    `继续看/检查/标记已读/提醒开/换源/取消追更` 同样看不出焦点位置。
 *
 * 根因是"焦点态只改填充色，而填充色本身就是主题色"：
 * `ThemeTokens` 冻结色板里 `colorFocus == colorPrimary`（light `#0B57D0` / dark `#A8C7FA`），
 * 于是 `dialog_primary_button_bg.xml` 的 focused 与 default 解析结果字节相同，
 * `following_button_primary_bg.xml` 的 focused(`webhtv_color_focus`) 与
 * default(`following_accent` = `webhtv_color_primary`) 在 TV 上也字节相同。
 *
 * 本测试把三条要求固化成契约：
 * - R1 自带主题色填充的控件，聚焦时必须出现边框环（不能只靠填充变化）；
 * - R2 电视版只允许一套机制、一个宽度来源；
 * - R3 焦点环色必须受主题色板控制（FOCUS 用户槽 / 填充的配对 on-色），不得写死。
 */
public class TvFocusRingContractTest {

    private static final String COLORS = "app/src/main/res/values/colors.xml";
    private static final String DIMENS = "app/src/main/res/values/webhtv_dimens.xml";
    private static final String ABOUT_LAYOUT = "app/src/main/res/layout/dialog_about.xml";
    private static final String ABOUT_ICON = "app/src/main/res/drawable/about_primary_icon_button.xml";
    private static final String FOLLOWING_ITEM = "app/src/main/res/layout/item_following.xml";
    private static final String FOLLOWING_LEANBACK = "app/src/leanback/res/layout/activity_following.xml";

    private static final String RING_PRIMARY = "app/src/main/res/color/focus_ring_primary.xml";
    private static final String RING_SECONDARY = "app/src/main/res/color/focus_ring_secondary.xml";
    private static final String RING_ERROR = "app/src/main/res/color/focus_ring_error.xml";

    private static final String WIDTH = "@dimen/webhtv_focus_ring_width";

    private static final String TOKENS_LIGHT = "app/src/main/res/values/webhtv_tokens.xml";
    private static final String TOKENS_NIGHT = "app/src/main/res/values-night/webhtv_tokens.xml";

    private static final String LEANBACK_DRAWABLE = "app/src/leanback/res/drawable/";

    // ------------------------------------------------------------ R3 主题控制

    @Test
    public void focusRingColourIsThemeControlledNotHardCoded() throws Exception {
        String colors = read(COLORS);
        assertTrue("tvFocusRing 的取值必须接到主题 FOCUS 用户槽，不能再写死十六进制",
                colors.contains("<color name=\"tv_item_focus_ring\">@color/webhtv_color_focus</color>"));
        assertFalse("tv_item_focus_ring 不允许再出现硬编码黄色",
                colors.contains("<color name=\"tv_item_focus_ring\">#FFD166</color>"));

        // 自带主题色填充的控件，环色必须是该填充的配对 on-色：这些角色由主题解析器
        // 从用户 seed 重新生成并做过对比度校验，所以换任何主题环都仍然可见。
        assertTrue("primary 填充的环色必须取配对 on-色",
                colors.contains("<color name=\"focus_ring_on_primary\">@color/webhtv_color_on_primary</color>"));
        assertTrue("secondary container 填充的环色必须取配对 on-色",
                colors.contains("<color name=\"focus_ring_on_secondary_container\">@color/webhtv_color_on_secondary_container</color>"));
        assertTrue("error container 填充的环色必须取配对 on-色",
                colors.contains("<color name=\"focus_ring_on_error_container\">@color/webhtv_color_on_error_container</color>"));
        assertFalse("不得再用 on_error 去配 error container 填充（两者仅 1.40:1，环看不见）",
                colors.contains("<color name=\"focus_ring_on_error\">"));
    }

    /**
     * 环色只能配对**焦点态实际填充色**。这是实机验收暴露出的一类真缺陷：
     * `following_button_*_bg` 聚焦时填充会变成 FOCUS 色（冻结色板里 == primary），
     * 若环仍取 `on_secondary_container`，环与填充只有 1.33:1，焦点依旧看不见；
     * 同理 `?attr/colorErrorContainer` 填充配 `on_error` 只有 1.40:1。
     *
     * <p>逐对计算对比度，取 light / night / leanback 三套生效 token 各验一遍，
     * 避免以后换色板或换环色时静默退化到“环贴在近似色上”。门槛取 WCAG 2.2
     * SC 1.4.11 非文本对比度的 3:1。
     */
    @Test
    public void everyRingColourKeepsNonTextContrastAgainstItsFocusFill() throws Exception {
        // {说明, 焦点态填充 token, 环色别名}
        String[][] pairs = {
                {"primary / 焦点填充", "webhtv_color_primary", "focus_ring_on_primary"},
                {"FOCUS 填充", "webhtv_color_focus", "focus_ring_on_primary"},
                {"secondary container 填充", "webhtv_color_secondary_container", "focus_ring_on_secondary_container"},
                {"error container 填充", "webhtv_color_error_container", "focus_ring_on_error_container"},
        };
        String colors = read(COLORS);
        // TV 不再有独立的 leanback 色板，day/night 两张表就是全部生效表。
        for (String tokens : new String[]{TOKENS_LIGHT, TOKENS_NIGHT}) {
            for (String[] pair : pairs) {
                String fill = tokenHex(read(tokens), pair[1]);
                String alias = aliasTarget(colors, pair[2]);
                assertTrue(pair[2] + " 必须指向一个主题 token 而不是写死十六进制", alias.startsWith("@color/"));
                String ring = tokenHex(read(tokens), alias.substring("@color/".length()));
                double ratio = contrast(fill, ring);
                assertTrue(tokens + " 中 " + pair[0] + " 的环色 " + ring + " 与填充 " + fill
                                + " 只有 " + String.format("%.2f", ratio) + ":1，低于 3:1，焦点会看不见",
                        ratio >= 3.0);
            }
        }
    }

    @Test
    public void everyRingColourListResolvesThroughThemeTokens() throws Exception {
        String[][] cases = {
                {RING_PRIMARY, "focus_ring_on_primary"},
                {RING_SECONDARY, "focus_ring_on_secondary_container"},
                {RING_ERROR, "focus_ring_on_error_container"},
        };
        for (String[] item : cases) {
            String body = values(read(item[0]));
            // 属性顺序不属于语义差异，按状态+取值分别断言。
            assertTrue(item[0] + " 聚焦态必须使用主题环色 " + item[1],
                    body.contains("android:state_focused=\"true\"")
                            && body.contains("android:color=\"@color/" + item[1] + "\""));
            assertTrue(item[0] + " 按下态必须使用主题环色",
                    body.contains("android:state_pressed=\"true\"")
                            && body.contains("android:color=\"@color/" + item[1] + "\""));
            // 全透明擦除态：strokeWidth 是常量，只切换颜色值可避免任何布局变化。
            assertTrue(item[0] + " 非聚焦态必须是全透明而不是移除描边",
                    body.contains("android:color=\"@android:color/transparent\""));
            // 环色只允许来自主题 token，不允许写死十六进制。
            assertFalse(item[0] + " 不允许出现硬编码环色", body.matches(".*android:color=\"#.*"));
        }
    }

    // ------------------------------------------------------------ R2 应用表面唯一宽度

    /**
     * 用户报告（两张实机截图）：同一个电视首页上，「搜索/历史」两行功能按钮是**蓝色**边框，
     * 「最近观看」内容卡片是**白色**边框，且两边粗细不同。
     *
     * <p>根因是应用表面的焦点环分裂成两族：
     * <ul>
     *   <li>{@code shape_item_focused} / {@code shape_item_round_focused} 写
     *       {@code 1.5dp ?attr/colorPrimary}（蓝）；</li>
     *   <li>{@code shape_vod_focused} / {@code shape_vod_oval_focused} / {@code shape_keyboard_focused} /
     *       {@code shape_search_hot_word_focused} / {@code shape_chip_*_focused} 写
     *       {@code 1.5dp/2dp @color/white}（白，完全不随主题走）；</li>
     *   <li>{@code shape_config_history_item_focused} / {@code shape_site_item_*} /
     *       {@code shape_group_button_focused} 写 {@code 2dp}。</li>
     * </ul>
     *
     * <p>本测试把这些应用表面（宿主为调色板表面或对话框面板）的焦点环钉死到统一取值：
     * 宽度必须引用 {@code @dimen/webhtv_focus_ring_width}，环色必须走 {@code ?attr/tvFocusRing}
     * 或它配对的主题角色（{@code ?attr/colorOnPrimary} / {@code ?attr/colorPrimary} /
     * {@code ?attr/colorPrimaryContainer}），不得再写死 {@code @color/white} 或 {@code #FFFFFF}。
     *
     * <p><b>视频层刻意不在本约束内</b>：{@code shape_chip_focused}（播放页解析线路）、
     * {@code shape_chip_round_focused}（直播源弹窗）、{@code shape_video_focused}（画面框）、
     * {@code shape_subtitle_*_focused}（字幕工具栏）、{@code shape_live_focused}（直播抽屉）、
     * {@code selector_control_sheet_button} 与 {@code selector_exit_confirm_*}
     * 叠在视频画面或固定明暗的玻璃面板上，改走调色板会让浅色表的深蓝环贴在深底上（实测
     * 1.91:1）或在夜间表的浅底上消失。它们只统一宽度，环色保持与调色板无关。
     */
    @Test
    public void appSurfaceFocusRingsShareOneWidthTokenAndAThemeColour() throws Exception {
        // 应用表面焦点环：宿主是调色板表面/对话框面板，环色必须跟随主题。
        String[][] themed = {
                {"shape_item_focused.xml", "?attr/tvFocusRing"},
                {"shape_item_round_focused.xml", "?attr/tvFocusRing"},
                {"shape_item_selected.xml", "?attr/tvFocusRing"},
                {"shape_vod_focused.xml", "?attr/tvFocusRing"},
                {"shape_vod_oval_focused.xml", "?attr/tvFocusRing"},
                {"shape_keyboard_focused.xml", "?attr/tvFocusRing"},
                {"shape_search_hot_word_focused.xml", "?attr/tvFocusRing"},
                // 自带主题色填充的控件：环色取焦点态填充的配对角色，同样由主题解析器保证对比度。
                {"shape_config_history_item_focused.xml", "?attr/colorOnPrimary"},
                {"shape_site_item_focused.xml", "?attr/colorOnPrimary"},
                {"shape_site_item_selected.xml", "?attr/colorPrimary"},
                {"shape_group_button_focused.xml", "?attr/colorOnPrimary"},
        };
        for (String[] entry : themed) {
            String path = LEANBACK_DRAWABLE + entry[0];
            String body = values(read(path));
            assertTrue(path + " 的焦点环必须引用唯一宽度 token " + WIDTH,
                    body.contains("android:width=\"" + WIDTH + "\""));
            assertTrue(path + " 的环色必须取主题角色 " + entry[1] + "，不能写死",
                    body.contains("android:color=\"" + entry[1] + "\""));
            assertFalse(path + " 不允许再写死白色焦点环",
                    body.contains("android:color=\"@color/white\"") || body.contains("android:color=\"#FFFFFF\""));
            assertFalse(path + " 不允许再写死描边宽度（1.5dp/2dp/3dp）",
                    body.matches("(?s).*android:width=\"[0-9.]+dp\".*"));
        }

        // 视频层/固定明暗宿主：只统一宽度，环色保持与调色板无关。
        String[] paletteIndependent = {
                "shape_chip_focused.xml",
                "shape_chip_round_focused.xml",
                "shape_live_focused.xml",
                "shape_video_focused.xml",
                "shape_subtitle_focused.xml",
                "shape_subtitle_pressed.xml",
                "selector_control_sheet_button.xml",
                "selector_episode_dialog_item.xml",
                "selector_episode_dialog_page.xml",
                "selector_danmaku_result_item.xml",
                "selector_danmaku_search_action.xml",
                "shape_video_item_focused.xml",
        };
        for (String name : paletteIndependent) {
            String path = LEANBACK_DRAWABLE + name;
            String body = values(read(path));
            assertTrue(path + " 的焦点环必须引用唯一宽度 token " + WIDTH,
                    body.contains("android:width=\"" + WIDTH + "\""));
            // 只约束**焦点态**的描边宽度：这些文件里还带有 1dp 的常态轮廓，
            // 那是「未聚焦轮廓」而不是焦点环，套用 3dp 反而会模糊常态与焦点的区分。
            java.util.List<String> widths = focusStateStrokeWidths(body, name);
            assertFalse(path + " 的焦点态描边不允许写死宽度，实际为 " + widths,
                    widths.stream().anyMatch(w -> !WIDTH.equals(w)));
        }
    }

    /** 抽出 {@code body} 里焦点态描边的宽度（含单 shape 的 focused 文件）。 */
    private static java.util.List<String> focusStateStrokeWidths(String body, String name) {
        java.util.List<String> widths = new java.util.ArrayList<>();
        java.util.regex.Matcher item = java.util.regex.Pattern
                .compile("<item\\b[^>]*state_focused=\"true\"[^>]*>(.*?)</item>", java.util.regex.Pattern.DOTALL)
                .matcher(body);
        while (item.find()) {
            java.util.regex.Matcher stroke = java.util.regex.Pattern
                    .compile("<stroke\\b[^>]*android:width=\"([^\"]+)\"")
                    .matcher(item.group(1));
            while (stroke.find()) widths.add(stroke.group(1));
        }
        if (!body.contains("<item") && name.contains("focused")) {
            java.util.regex.Matcher stroke = java.util.regex.Pattern
                    .compile("<stroke\\b[^>]*android:width=\"([^\"]+)\"")
                    .matcher(body);
            while (stroke.find()) widths.add(stroke.group(1));
        }
        return widths;
    }

    /**
     * 全库不变量：leanback 里**任何**焦点态描边都不得写死宽度，必须引用唯一 token。
     *
     * <p>上一条测试是白名单式断言（只检查名单内的文件），新增文件不会被覆盖。本测试反过来
     * 扫描整个 {@code leanback/res/drawable}，所以以后新增一个焦点环、或把旧的 1.5dp/2dp
     * 写回来，都会直接转红——这正是用户报告「边框粗细也貌似不一样」需要被永久挡住的一类改动。
     *
     * <p>仅两个文件豁免，且各有明确理由（豁免列表本身就是契约）：
     * <ul>
     *   <li>{@code selector_video_item.xml} —— 它是电视版统一焦点环规范的**样板文件**
     *       （其他文件都在注释里指向它），其字面量 {@code 3dp} 与 token 取值完全相同，
     *       且 {@code NativeEnhancedPlaybackStyleFocusTest} 把它当作规范基准逐字断言；
     *       改它只会引入无视觉收益的跨任务测试改动。</li>
     *   <li>{@code shape_audio_action_icon_focused.xml} —— 它不是容器焦点环，而是播放页音频
     *       按钮上带 {@code inset=3dp} 的**图标内描边环**（40dp 图标 / 17dp 圆角），
     *       角色与尺寸均不同，套 3dp 会把图标糊成一团。</li>
     * </ul>
     */
    @Test
    public void noLeanbackFocusRingHardcodesItsWidth() throws Exception {
        java.util.Set<String> exempt = java.util.Set.of(
                "selector_video_item.xml",
                "shape_audio_action_icon_focused.xml");
        java.nio.file.Path dir = java.nio.file.Path.of("app/src/leanback/res/drawable");
        if (!java.nio.file.Files.isDirectory(dir)) dir = java.nio.file.Path.of("../app/src/leanback/res/drawable");
        assertTrue("leanback drawable 目录必须存在", java.nio.file.Files.isDirectory(dir));

        java.util.List<String> violations = new java.util.ArrayList<>();
        int checked = 0;
        try (java.util.stream.Stream<java.nio.file.Path> paths = java.nio.file.Files.list(dir)) {
            for (java.nio.file.Path path : paths.sorted().toList()) {
                String name = path.getFileName().toString();
                if (!name.endsWith(".xml") || exempt.contains(name)) continue;
                String body = values(read(path.toString().replace('\\', '/')));
                for (String width : focusStateStrokeWidths(body, name)) {
                    checked++;
                    if (!WIDTH.equals(width)) violations.add(name + " -> " + width);
                }
            }
        }
        assertTrue("扫描必须真的读到焦点环，否则本测试是空断言", checked >= 15);
        assertTrue("电视版焦点环宽度只允许有一个来源 " + WIDTH + "，以下仍写死：" + violations,
                violations.isEmpty());
    }

    /**
     * 回归门：同一个电视页面上的两族焦点环不得再分叉。
     *
     * <p>首页同时渲染功能按钮行（{@code adapter_func} → {@code selector_item}）与内容卡片行
     * （{@code adapter_vod} → {@code selector_vod}），两者就是用户截图里「上面蓝色、下面白色」
     * 的那一对。它们的焦点态环色必须来自同一个主题属性，宽度来自同一个 token。
     */
    @Test
    public void homeFunctionButtonsAndContentCardsShareTheSameRingSpec() throws Exception {
        String button = values(read(LEANBACK_DRAWABLE + "shape_item_focused.xml"));
        String card = values(read(LEANBACK_DRAWABLE + "shape_vod_focused.xml"));
        for (String body : new String[]{button, card}) {
            assertTrue("首页两族焦点环必须同宽", body.contains("android:width=\"" + WIDTH + "\""));
            assertTrue("首页两族焦点环必须同色（主题 FOCUS 槽）", body.contains("android:color=\"?attr/tvFocusRing\""));
        }
        // 消费方必须仍然分别指向这两个 selector，否则本断言就不再覆盖用户报告的控件。
        assertTrue(read("app/src/leanback/res/drawable/selector_item.xml").contains("@drawable/shape_item_focused"));
        assertTrue(read("app/src/leanback/res/drawable/selector_vod.xml").contains("@drawable/shape_vod_focused"));
    }

    // ------------------------------------------------------------ R2 卡片环圆角必须对齐宿主表面

    /**
     * 用户报告（2026-10-10 dev1 实机）：「边框在卡片上的圆角部分匹配不完美，感觉是圆角比卡片小，
     * 导致卡片的圆角还露出一节了」。
     *
     * <p>根因是几何而非颜色：{@code shape_vod_focused} 是卡片的 <b>foreground</b>，而卡片的可见
     * 表面另有自己的 8dp 圆角（图片走 {@code @style/Vod.Grid} 上圆角 8dp、标题块走
     * {@code shape_vod_name} 下圆角 8dp；列表型宿主走 {@code shape_vod_list} 四角 8dp）。
     * 描边型 {@code <shape>}（{@code GradientDrawable}）把描边中心线画在「内缩 w/2、圆角半径仍取
     * 声明值」的路径上，所以环的 <b>外边界</b>圆角半径 = 声明值 + w/2。声明 8dp 时外边界为
     * 8dp + w/2 &gt; 8dp，比卡片自身的弧更大，沿角落对角线卡片弧反而更靠外，露出 1–2px 月牙。
     *
     * <p>所以卡片环的声明圆角必须是 {@code 宿主圆角 - w/2}（理论值 8 - 0.75 = 7.25dp），再向下留
     * 一点像素取整余量：描边宽度按整数像素向上取整（1.5dp @ density 3 = 4.5px → 5px），
     * 若写满 7.25dp，在部分密度下环外边界会超出宿主弧 0.25–0.5px，仍会露出亚像素月牙；
     * 生产取值 7dp 在 density 1/1.75/2/2.353/3/4 下均为 0 溢出（见
     * {@code TvAppSurfaceFocusRingDeviceTest.cardRingOuterBoundaryContainsEveryCardSurfacePixel}）。
     * 由于全部 6 个 {@code selector_vod} 宿主的可见表面都是 8dp，单一环仍可覆盖全部宿主——
     * 这里的断言就是在钉死这条几何关系，并在宿主圆角分叉时立刻报警。
     */
    @Test
    public void cardRingCornerRadiusIsTheHostRadiusMinusHalfTheRingWidth() throws Exception {
        double width = dpValue(read(DIMENS), "webhtv_focus_ring_width");
        double ringRadius = dpValue(values(read(LEANBACK_DRAWABLE + "shape_vod_focused.xml")), "android:radius");

        // 宿主的可见表面圆角：图片型宿主的上圆角、标题块的下圆角、列表型宿主的四角。
        double imageTop = dpValue(values(read("app/src/main/res/values/styles.xml")), "cornerSizeTopLeft");
        double nameBottom = dpValue(values(read(LEANBACK_DRAWABLE + "shape_vod_name.xml")), "android:bottomLeftRadius");
        double listAll = dpValue(values(read(LEANBACK_DRAWABLE + "shape_vod_list.xml")), "android:radius");

        assertTrue("selector_vod 的 6 个宿主表面必须同圆角，否则一个环无法同时对齐（图片上圆角="
                        + imageTop + "dp，标题块下圆角=" + nameBottom + "dp，列表四角=" + listAll + "dp）",
                imageTop == nameBottom && nameBottom == listAll);
        double ideal = imageTop - width / 2;
        assertTrue("卡片环的声明圆角必须取 宿主圆角 - 环宽/2（" + ideal + "dp）再向下留像素取整余量，"
                        + "且不得超过理论值：实际 " + ringRadius + "dp（环宽 " + width + "dp）",
                ringRadius <= ideal + 0.01 && ringRadius >= ideal - 0.5);
    }

    /** 从 XML 文本里取出某个属性/dimen 的 dp 数值。 */
    private static double dpValue(String xml, String key) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile(java.util.regex.Pattern.quote(key) + "[^>]*?>?([0-9.]+)dp")
                .matcher(xml);
        assertTrue("必须能在 XML 里找到 " + key + " 的 dp 取值", matcher.find());
        return Double.parseDouble(matcher.group(1));
    }

    // ------------------------------------------------------------ R5 前景环圆角必须对齐宿主表面

    /**
     * 同一类缺陷在详情页/播放页的实例（2026-10-10 实机复核）：环作为卡片的 <b>foreground</b> 时，
     * 环外边界圆角半径 = 声明值 + w/2（见 §12.2 的几何推导）。若声明值直接写宿主圆角，
     * 外边界就会比宿主大 w/2，宿主圆角在环外露出一段；宿主是直角时更明显。
     *
     * <p>本测试把「声明值 = 宿主圆角 − w/2（下限 0）」钉死到四个宿主：
     * <ul>
     *   <li>{@code selector_episode_card}（焦点 3dp）→ 宿主 {@code adapter_episode_card} 的
     *       CardView {@code @dimen/webhtv_card_radius_default} = 8dp；</li>
     *   <li>{@code selector_tmdb_media_focus}（焦点 3dp）→ 宿主 {@code adapter_tmdb_video}/
     *       {@code adapter_tmdb_photo} 的 MaterialCardView 8dp；</li>
     *   <li>{@code selector_tmdb_cast_focus}（焦点 3dp）→ 宿主 {@code adapter_tmdb_cast} 的
     *       {@code @dimen/webhtv_card_radius_large} = 12dp；</li>
     *   <li>{@code shape_episode_photo_focused}（焦点 3dp）→ 宿主 {@code dialog_episode_detail}
     *       的 {@code @id/stillCard} CardView 8dp；</li>
     *   <li>{@code shape_video_focused}（宽度走 token）→ 宿主是普通 FrameLayout（直角），故为 0dp。</li>
     * </ul>
     *
     * <p>栅格化端到端断言（真实宿主 inflate + 环栅格化后数溢出像素）在
     * {@code TvAppSurfaceFocusRingDeviceTest.cardRingOuterBoundaryContainsItsHostSurface}。
     */
    @Test
    public void foregroundRingsDeclareTheirHostCornerMinusHalfTheRingWidth() throws Exception {
        // {环文件, 该状态的环宽 dp, 宿主圆角 dp, 宿主来源说明, 理想声明值 dp}
        // 理想值 = 宿主圆角 − 环宽/2；实测（Robolectric 栅格化，真实宿主 inflate）在各档密度下
        // 0 溢出的最小声明值就是该理想值（例如 8dp 宿主 + 3dp 环 = 6.5dp）。
        Object[][] rings = {
                {"app/src/main/res/drawable/selector_episode_card.xml", 3.0, 8.0, 6.0,
                        "adapter_episode_card CardView cardCornerRadius=webhtv_card_radius_default"},
                {"app/src/main/res/drawable/selector_tmdb_media_focus.xml", 3.0, 8.0, 6.0,
                        "adapter_tmdb_video/photo MaterialCardView cardCornerRadius=webhtv_card_radius_default"},
                {"app/src/main/res/drawable/selector_tmdb_cast_focus.xml", 3.0, 12.0, 9.5,
                        "adapter_tmdb_cast MaterialCardView cardCornerRadius=webhtv_card_radius_large"},
                {"app/src/main/res/drawable/shape_episode_photo_focused.xml", 3.0, 8.0, 6.0,
                        "dialog_episode_detail stillCard CardView cardCornerRadius=8dp"},
        };
        for (Object[] entry : rings) {
            String path = (String) entry[0];
            double width = (Double) entry[1];
            double host = (Double) entry[2];
            double expected = (Double) entry[3];
            double declared = firstCornerRadiusDp(values(read(path)));
            double ideal = Math.max(host - width / 2, 0);
            assertEquals(path + " 的焦点态声明圆角必须等于 宿主圆角 − 环宽/2 = " + ideal + "dp（宿主 "
                            + host + "dp 来自 " + entry[4] + "），实测 0 溢出的最小取值；实际 " + declared + "dp",
                    expected, declared, 0.01);
        }

        // 当前态（2dp）同样要减自己的 w/2：8dp 宿主 → 7dp 理论、实测 6dp 起 0 溢出（取 6dp）；
        // 12dp 宿主 → 11dp 理论、实测 10dp 起 0 溢出（取 10dp）。
        assertEquals("选集卡当前态声明圆角", 6.0,
                secondCurrentStateCornerRadiusDp(values(read("app/src/main/res/drawable/selector_episode_card.xml"))), 0.01);
        assertEquals("剧照/相关视频当前态声明圆角", 6.0,
                secondCurrentStateCornerRadiusDp(values(read("app/src/main/res/drawable/selector_tmdb_media_focus.xml"))), 0.01);
        assertEquals("演员卡当前态声明圆角", 9.5,
                secondCurrentStateCornerRadiusDp(values(read("app/src/main/res/drawable/selector_tmdb_cast_focus.xml"))), 0.01);

        // 直角宿主：播放页画面框是普通 FrameLayout（无圆角），环必须是 0dp，
        // 否则环外边界圆角（w/2 + 声明值）比黑底直角还大，黑角会露在环外。
        double videoRing = firstCornerRadiusDp(values(read(LEANBACK_DRAWABLE + "shape_video_focused.xml")));
        assertEquals("播放页画面框是直角宿主，环声明圆角必须是 0dp", 0.0, videoRing, 0.01);
    }

    /** 取 XML 里第一个 {@code android:radius} 的 dp 值（缺省视为 0，例如只写了 per-corner）。 */
    private static double firstCornerRadiusDp(String xml) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("android:radius=\"([0-9.]+)dp\"").matcher(xml);
        return matcher.find() ? Double.parseDouble(matcher.group(1)) : 0.0;
    }

    /** 取 XML 里第二个 {@code android:radius} 的 dp 值（这些 selector 的第二段就是当前态）。 */
    private static double secondCurrentStateCornerRadiusDp(String xml) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("android:radius=\"([0-9.]+)dp\"").matcher(xml);
        assertTrue("必须至少有两段带圆角的 shape", matcher.find() && matcher.find());
        return Double.parseDouble(matcher.group(1));
    }

    /**
     * 集数名可读性：TV 卡片下方那一行（{@code adapter_vod} 的 {@code @id/remark}）此前用
     * {@code ?attr/colorOnSurfaceVariant}（浅色表 #44474F）画在深色 {@code shape_vod_name}
     * 条带上，实机对比度只有 <b>1.35:1</b>（刷名 {@code @id/name} 用白色是 6.89:1），用户报告
     * 「集数名称一栏字体颜色不对看不清」。手机版同一行用的是 {@code ?attr/webhtvColorOnWallpaper}，
     * TV 对齐该取值。
     */
    @Test
    public void leanbackCardEpisodeLineUsesTheSameReadableColourAsItsTitle() throws Exception {
        String layout = read("app/src/leanback/res/layout/adapter_vod.xml");
        String nameColour = textColourOf(layout, "name");
        String remarkColour = textColourOf(layout, "remark");
        assertEquals("集数名必须与刷名同色（手机版同款可读取值）", nameColour, remarkColour);
        assertEquals("集数名必须走 webhtvColorOnWallpaper（深色条带上实测 6.89:1）",
                "?attr/webhtvColorOnWallpaper", remarkColour);
        assertFalse("集数名不允许再用 colorOnSurfaceVariant（深色条带上仅 1.35:1）",
                remarkColour.contains("colorOnSurfaceVariant"));
    }

    /** 取某个 {@code @+id/xxx} 控件上的 {@code android:textColor}。 */
    private static String textColourOf(String layout, String id) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("@\\+id/" + java.util.regex.Pattern.quote(id) + "\"(.*?)(?:/>|</)", java.util.regex.Pattern.DOTALL)
                .matcher(layout);
        assertTrue("布局里必须能找到 @+id/" + id, matcher.find());
        java.util.regex.Matcher colour = java.util.regex.Pattern
                .compile("android:textColor=\"([^\"]+)\"").matcher(matcher.group(1));
        assertTrue("@+id/" + id + " 必须显式声明 textColor", colour.find());
        return colour.group(1);
    }

    // ------------------------------------------------------------ R6 播放页环：统一宽度 + 主题派生色

    /**
     * 用户报告（2026-10-10 第三轮，dev1 实机）：
     * <blockquote>播放页按钮的边框太粗了，按钮和播放器选中后的边框颜色也不统一，
     * 请统一且都受到主题色彩控制</blockquote>
     *
     * <p>实机实测（1920×1080，2.35px/dp）：播放页同时存在两族环——
     * {@code selector_chip}（14+26 个 Control 按钮）走 1.5dp 写死白，
     * {@code selector_video_item}（11 个文本按钮）走 3dp {@code ?attr/tvFocusRing}，
     * 而「当前播放」走 2dp 写死绿 {@code #2CC56F}；同一屏上三种宽度、三种颜色。
     *
     * <p>本测试把播放页的两族环钉死（宿主分层：谁叠在视频/固定玻璃上，谁在页面背景上）：
     * <ol>
     *   <li>所有播放页焦点/当前态环的宽度都引用 {@code @dimen/webhtv_focus_ring_width}；</li>
     *   <li><b>视频层族</b>（控制条芯片、控制面板按钮、画面框、字幕/直播环）走
     *       {@code ?attr/tvPlayerRing} / {@code ?attr/tvPlayerCurrentRing}；</li>
     *   <li><b>应用表面族</b>（{@code selector_video_item}：简介/短显/搜索按钮行、集数表头、
     *       线路/清晰度/数组分段/分段/选集/快捷源芯片）走 {@code ?attr/tvFocusRing} /
     *       {@code ?attr/tvCurrentRing}，因为它们画在页面背景上而不是视频/玻璃上；</li>
     *   <li>复用这批芯片布局的两处固定玻璃对话框在子树内用
     *       {@code ThemeOverlay.WebHTV.GlassFocusRings} 把两项重绑回玻璃可读色。</li>
     * </ol>
     *
     * <p><b>为什么视频层族不能用 {@code ?attr/tvFocusRing}</b>：控制条/控制面板是固定深靛
     * 玻璃（{@code #E62F315E→#CC303463}，两张表里都是深色），浅色表 FOCUS 深蓝
     * {@code #0B57D0} 画在它上面只有 1.83:1（dev1 实机实测）。所以 {@code tvPlayerRing}
     * 在**浅色表**是 {@code ThemeResolver} 用 {@code readableAccent} 在三档玻璃上夹取到
     * ≥3:1（WCAG 2.2 SC 1.4.11 非文本门槛）后的派生色，保持用户 FOCUS / playerCurrent 槽
     * 的色相与彩度、只走明度；<b>深色表</b>两类宿主的底色都是深色，因此直接取与应用表面
     * 焦点环同值的近白——否则同一页会同时出现「应用表面近白 + 视频层灰蓝」两种高亮
     * （用户报告 2026-10-11「播放页存在多个不同颜色的高亮效果」）。
     */
    @Test
    public void playerFocusRingsShareOneWidthAndAThemeControlledColour() throws Exception {
        // {文件, 必须出现的环色属性}
        // 视频层族：宿主是叠在视频画面或固定深色玻璃上的控件。
        String[][] rings = {
                {"shape_chip_focused.xml", "?attr/tvPlayerRing"},
                {"shape_chip_round_focused.xml", "?attr/tvPlayerRing"},
                {"shape_video_focused.xml", "?attr/tvPlayerRing"},
                {"shape_subtitle_focused.xml", "?attr/tvPlayerRing"},
                {"shape_subtitle_pressed.xml", "?attr/tvPlayerRing"},
                {"shape_live_focused.xml", "?attr/tvPlayerRing"},
                {"selector_control_sheet_button.xml", "?attr/tvPlayerRing"},
        };
        for (String[] entry : rings) {
            String path = LEANBACK_DRAWABLE + entry[0];
            String body = values(read(path));
            assertTrue(path + " 的焦点环宽度必须引用唯一 token " + WIDTH,
                    body.contains("android:width=\"" + WIDTH + "\""));
            assertTrue(path + " 的焦点环色必须走视频层主题属性 " + entry[1], body.contains(entry[1]));
            assertFalse(path + " 不允许再写死白色焦点环",
                    body.contains("android:color=\"@color/white\"") || body.contains("android:color=\"#FFFFFF\""));
        }

        // 应用表面族：selector_video_item 的宿主是播放页内容区的按钮/芯片（简介/短显/搜索
        // 按钮行、集数表头、线路/清晰度/数组分段/分段/选集/快捷源行），它们画在页面背景上，
        // 不是叠在视频或固定玻璃上——2026-10-11 用户报告「播放页存在多个不同颜色的高亮效果」，
        // 这批芯片此前错用了视频层灰蓝环（#7695C5），现已归到调色板 FOCUS 槽。
        String chip = values(read(LEANBACK_DRAWABLE + "selector_video_item.xml"));
        assertTrue(LEANBACK_DRAWABLE + "selector_video_item.xml 的焦点环必须走应用表面属性 ?attr/tvFocusRing",
                chip.contains("?attr/tvFocusRing"));
        assertTrue(LEANBACK_DRAWABLE + "selector_video_item.xml 的当前态环必须走应用表面属性 ?attr/tvCurrentRing",
                chip.contains("?attr/tvCurrentRing"));
        assertFalse("播放页内容区芯片不允许再用视频层环色（会造成同页两种高亮色）",
                chip.contains("?attr/tvPlayerRing") || chip.contains("?attr/tvPlayerCurrentRing"));

        // 宿主是固定深色玻璃的两处对话框（复用同一批芯片布局）必须在子树内把两项重绑回玻璃可读色，
        // 否则浅色表（FOCUS = 深蓝 #0B57D0）的芯片环画在固定玻璃上只有 1.83:1。
        String overlay = "ThemeOverlay.WebHTV.GlassFocusRings";
        String leanbackStyles = read("app/src/leanback/res/values/styles.xml");
        assertTrue("leanback styles.xml 必须定义玻璃宿主覆盖层 " + overlay, leanbackStyles.contains("<style name=\"" + overlay + "\""));
        int overlayStart = leanbackStyles.indexOf("<style name=\"" + overlay + "\"");
        String overlayBody = leanbackStyles.substring(overlayStart, leanbackStyles.indexOf("</style>", overlayStart));
        assertTrue(overlay + " 必须把 tvFocusRing 重绑到 tv_player_focus_ring",
                overlayBody.contains("<item name=\"tvFocusRing\">@color/tv_player_focus_ring</item>"));
        assertTrue(overlay + " 必须把 tvCurrentRing 重绑到 tv_player_current_ring",
                overlayBody.contains("<item name=\"tvCurrentRing\">@color/tv_player_current_ring</item>"));
        for (String dialog : new String[]{"dialog_episode_list.xml", "dialog_quick_search.xml"}) {
            String layout = read("app/src/leanback/res/layout/" + dialog);
            assertTrue(dialog + " 是固定深色玻璃面（DARK_GLASS_SHEETS），必须在根上应用 " + overlay,
                    layout.contains("android:theme=\"@style/" + overlay + "\""));
        }

        // 「当前播放/当前生效」态：统一宽度 + 独立的当前态主题属性（不再是写死绿）。
        for (String name : new String[]{"selector_control_sheet_button.xml",
                "shape_chip_activated.xml", "shape_chip_round_activated.xml"}) {
            String path = LEANBACK_DRAWABLE + name;
            String body = values(read(path));
            assertTrue(path + " 的当前态环必须走 tvPlayerCurrentRing", body.contains("?attr/tvPlayerCurrentRing"));
            assertTrue(path + " 的当前态环宽度必须引用唯一 token", body.contains("android:width=\"" + WIDTH + "\""));
        }
        for (String name : new String[]{"selector_video_item.xml"}) {
            String path = LEANBACK_DRAWABLE + name;
            String body = values(read(path));
            assertTrue(path + " 的当前态环必须走 tvCurrentRing", body.contains("?attr/tvCurrentRing"));
            assertTrue(path + " 的当前态环宽度必须引用唯一 token", body.contains("android:width=\"" + WIDTH + "\""));
        }

        // 两个属性必须在 attrs 里声明、并在两个 flavor 的 Theme.Base 里绑定，否则解析不到会崩。
        String attrs = read("app/src/main/res/values/attrs.xml");
        for (String attr : new String[]{"tvPlayerRing", "tvPlayerCurrentRing"}) {
            assertTrue("attrs.xml 必须声明 " + attr, attrs.contains("<attr name=\"" + attr + "\" format=\"color\" />"));
        }
        for (String styles : new String[]{"app/src/leanback/res/values/styles.xml",
                "app/src/mobile/res/values/styles.xml"}) {
            String body = read(styles);
            assertTrue(styles + " 必须把 tvPlayerRing 绑到 tv_player_focus_ring",
                    body.contains("<item name=\"tvPlayerRing\">@color/tv_player_focus_ring</item>"));
            assertTrue(styles + " 必须把 tvPlayerCurrentRing 绑到 tv_player_current_ring",
                    body.contains("<item name=\"tvPlayerCurrentRing\">@color/tv_player_current_ring</item>"));
        }
    }

    /**
     * 视频层派生色必须真的在它的宿主背景上可读，且深色表不得再造出第二种高亮色。
     *
     * <p>核心风险：浅色表 FOCUS 深蓝 {@code #0B57D0} 在固定玻璃上只有 1.83:1。
     * 若以后有人把视频层环改回调色板原色或写死值，本条会直接报出实测比值。
     *
     * <p>2026-10-11：纯白视频不再是本层的约束背景（用户报告「播放页存在多个不同颜色的
     * 高亮效果」）——把它当作背景会把深色表的环压成灰蓝 {@code #7695C5}，于是同一页出现
     * 「应用表面近白 + 视频层灰蓝」两种高亮。深色表因此取与应用表面焦点环同值的近白，
     * 由 {@code playerRingColoursStayOneUnifiedHighlightInTheDarkTable} 钉住。
     * 代价：亮场景视频上的近白环对比度不足，仅在焦点落在画面框/播控条时出现。
     */
    @Test
    public void playerRingColoursClearNonTextContrastOnGlassBackdrops() throws Exception {
        // 与 ThemeResolver.PLAYER_RING_BACKDROPS 同一组：三档固定深色玻璃。
        int[] backdrops = {0xFF2F315E, 0xFF282955, 0xFF303463};
        double minimum = 3.0;
        // 与 ThemeTokens.light()/dark() 的 colorPlayerFocusRing/colorPlayerCurrentRing 同步。
        int[][] rings = {
                {0xFF447BF5, 0xFF00A95A},   // light
                {0xFFF5F7FF, 0xFF00A95A},   // dark（与应用表面焦点环同值）
        };
        for (int[] pair : rings) {
            for (int colour : pair) {
                for (int backdrop : backdrops) {
                    double ratio = contrast(colour, backdrop);
                    assertTrue(String.format(
                                    "播放页环色 #%06X 对背景 #%06X 实测 %.2f:1，必须 ≥%.1f:1（WCAG 2.2 SC 1.4.11）",
                                    colour & 0xFFFFFF, backdrop & 0xFFFFFF, ratio, minimum),
                            ratio + 0.001 >= minimum);
                }
            }
        }
        // 回归钉子：证明「直接用调色板原色」确实不可行，防止后人再试。
        assertTrue("浅色表 FOCUS #0B57D0 对固定玻璃本来就不可读（这条是浅色表派生的理由）",
                contrast(0xFF0B57D0, 0xFF303463) < 3.0);
    }

    /**
     * 播放页只允许一种高亮色：深色表的视频层环必须与应用表面焦点环同值。
     *
     * <p>用户报告（2026-10-11，实机截图）：播放页同时出现近白环（应用表面元素）与灰蓝环
     * （视频层元素：分段/排序芯片、控制条、画面框）。深色表下两类宿主的底色都是深色，
     * 没有任何可读性理由保留第二种高亮色，所以两者相等；浅色表则**必须不同**：
     * 深蓝 FOCUS 画在固定玻璃上只有 1.83:1，此时并存是为了可读性而不是配色随意。
     */
    @Test
    public void playerRingColoursStayOneUnifiedHighlightInTheDarkTable() throws Exception {
        String night = read(TOKENS_NIGHT);
        String day = read(TOKENS_LIGHT);
        assertEquals("深色表：视频层焦点环必须与应用表面焦点环同值（近白），否则同页会出现两种高亮色",
                colour(night, "webhtv_color_focus"), colour(night, "webhtv_color_player_focus_ring"));
        assertNotEquals("浅色表：视频层环必须仍是固定玻璃上的派生色，不能直接等于 FOCUS 槽",
                colour(day, "webhtv_color_focus"), colour(day, "webhtv_color_player_focus_ring"));
        // frozen 色板必须与 XML token 同步（ThemeContractTest 逐字段校验 51 个颜色，此处只钉这一项）。
        assertEquals("深色 frozen 色板的 video 层环必须与 night token 同步",
                colour(night, "webhtv_color_player_focus_ring"),
                ThemeTokens.dark().colorPlayerFocusRing());
        assertEquals("浅色 frozen 色板的 video 层环必须与 day token 同步",
                colour(day, "webhtv_color_player_focus_ring"),
                ThemeTokens.light().colorPlayerFocusRing());
    }

    /** 从 token 表里取一个颜色（十六进制文本 → ARGB）。 */
    private static int colour(String tokens, String name) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("<color name=\"" + name + "\">(#[0-9A-Fa-f]{6,8})</color>")
                .matcher(tokens);
        assertTrue(tokens + " 里找不到 " + name, matcher.find());
        String value = matcher.group(1);
        long parsed = Long.parseLong(value.substring(1), 16);
        return value.length() == 7 ? (int) (0xFF000000L | parsed) : (int) parsed;
    }

    /** WCAG 相对亮度对比度，用于上面的播放页环断言。 */
    private static double contrast(int first, int second) {
        double a = luminance(first);
        double b = luminance(second);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }

    private static double luminance(int colour) {
        double red = channel((colour >>> 16) & 0xFF);
        double green = channel((colour >>> 8) & 0xFF);
        double blue = channel(colour & 0xFF);
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    }

    private static double channel(int value) {
        double normalized = value / 255.0;
        return normalized <= 0.04045 ? normalized / 12.92 : Math.pow((normalized + 0.055) / 1.055, 2.4);
    }

    /**
     * 上一条只扫 drawable，抓不到**代码挂环**的控件（它们直接 setStrokeWidth/setStroke）。
     *
     * <p>用户报告（2026-10-10）：「还有个性推荐等卡片的边框粗细没有改小没有统一」。
     * 根因就是这类：{@code TmdbRecommendationPresenter} 写死 {@code FOCUS_WIDTH_DP = 3}、
     * {@code TmdbCardFocusHelper} / {@code TmdbEpisodeAdapter} / {@code TmdbDetailActivity} /
     * {@code TmdbVideoAdapter} / {@code InlineEpisodeAdapter} 各自写死 2~3dp，
     * 它们都不经过 drawable 层，所以前几轮统一 drawable 宽度时全部漏掉。
     *
     * <p>本测试扫描 Java 源码：凡是「焦点态下设置描边宽度」的表达式，宽度必须来自
     * {@code R.dimen.webhtv_focus_ring_width}（或经本类助手），不得出现 dp 字面量常量。
     */
    @Test
    public void noJavaCodeHardcodesAFocusRingWidth() throws Exception {
        // 扫描范围：所有可能挂焦点环的 Java 源。
        String[] sources = {
                "app/src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbRecommendationPresenter.java",
                "app/src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbCastPresenter.java",
                "app/src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbPhotoPresenter.java",
                "app/src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbVideoPresenter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbCardFocusHelper.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbEpisodeAdapter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbVideoAdapter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/InlineEpisodeAdapter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/activity/TmdbDetailActivity.java",
        };
        java.util.List<String> violations = new java.util.ArrayList<>();
        int sites = 0;
        for (String source : sources) {
            String body;
            try {
                body = read(source);
            } catch (Exception missing) {
                continue;
            }
            // 先找出所有「按焦点分支设描边宽度」的语句（这就是代码挂环点）。
            java.util.regex.Matcher site = java.util.regex.Pattern
                    .compile("setStroke(?:Width)?\\([^;]{0,240}?focused\\s*\\?[^;]{0,240}?\\)")
                    .matcher(body);
            while (site.find()) {
                sites++;
                String statement = site.group().replaceAll("\\s+", " ");
                // 取 focused ? 之后的「真分支」，直到冒号（三元）或结尾。
                int q = statement.indexOf("focused ?");
                String truthy = statement.substring(q + "focused ?".length());
                int colon = truthy.indexOf(':');
                if (colon >= 0) truthy = truthy.substring(0, colon);
                // 真分支里不允许出现 dp 字面量常量（数字或 *_DP 常量）。
                if (java.util.regex.Pattern.compile("\\b\\d+\\s*$").matcher(truthy.trim()).find()
                        || java.util.regex.Pattern.compile("\\b\\d+\\s*[,)]").matcher(truthy).find()
                        || truthy.contains("_DP")) {
                    violations.add(source + " -> " + statement);
                }
            }
        }
        assertTrue("必须真的扫到代码挂环的焦点宽度赋值，否则本测试是空断言（实扫到 " + sites + " 处）",
                sites >= 8);
        assertTrue("焦点态描边宽度不得在 Java 里写死 dp，必须引用 @dimen/webhtv_focus_ring_width；"
                + "以下仍是字面量：" + violations, violations.isEmpty());
    }

    /**
     * 同一类遗漏的另一面：环色也不得在 Java 里写死（应走 ThemeController.focusRingColor / 主题属性）。
     */
    @Test
    public void noJavaCodeHardcodesAFocusRingColour() throws Exception {
        String[] sources = {
                "app/src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbRecommendationPresenter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbCardFocusHelper.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbEpisodeAdapter.java",
        };
        for (String source : sources) {
            String body = read(source);
            assertFalse(source + " 不得写死焦点环色（旧的 #FFD166 家族）",
                    body.contains("0xFFD166") || body.contains("#FFD166") || body.contains("0xFFFFD166"));
            assertTrue(source + " 的焦点环色必须走 ThemeController.focusRingColor",
                    body.contains("ThemeController.focusRingColor"));
        }
    }

    // ------------------------------------------------------------ R2 统一机制与宽度

    /**
     * 焦点环色只允许有两个来源：XML 的 {@code ?attr/tvFocusRing} 和 Java 的
     * {@code ThemeController.focusRingColor(...)}。任何一处再写死字面量都会让同一个 TV
     * 应用里出现两种环色（详情页永远黄色、播放页/追更页跟主题），且写死的浅色环
     * 在浅色底板上只有 1.1–1.4:1。本测试把该不变量钉死。
     */
    @Test
    public void noTvFocusRingColourIsHardCodedOutsideTheThemeSlot() throws Exception {
        String[] sources = {
                "app/src/main/java/com/fongmi/android/tv/ui/activity/TmdbDetailActivity.java",
                "app/src/main/java/com/fongmi/android/tv/ui/activity/TmdbPersonActivity.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbCardFocusHelper.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbEpisodeAdapter.java",
                "app/src/main/java/com/fongmi/android/tv/ui/adapter/TmdbVideoAdapter.java",
                "app/src/main/res/drawable/shape_episode_photo_focused.xml",
        };
        for (String source : sources) {
            assertFalse(source + " 不允许再写死焦点环色，必须走主题 FOCUS 槽（?attr/tvFocusRing 或 ThemeController.focusRingColor）",
                    read(source).contains("FFD166"));
        }
        // 代码路径必须真的接到 ThemeController，而不是换一个写死的近似色。
        for (String source : new String[]{sources[0], sources[1], sources[2], sources[3], sources[4]}) {
            assertTrue(source + " 的焦点环必须取自 ThemeController.focusRingColor",
                    read(source).contains("ThemeController.focusRingColor"));
        }
        // 播放器视频层焦点与普通焦点隔离，不受本规范约束（见 docs 阶段 M 的非目标）。
        assertTrue("KaraokeStatusView 属于视频层，明确不在本规范范围内",
                read("app/src/main/java/com/fongmi/android/tv/ui/custom/KaraokeStatusView.java").contains("0xCCFFD166"));
    }

    @Test
    public void thereIsExactlyOneFocusRingWidthInTheTvUi() throws Exception {
        assertTrue("必须声明唯一的焦点环宽度 token",
                read(DIMENS).contains("<dimen name=\"webhtv_focus_ring_width\">"));
        assertTrue("焦点环宽度 token 只能声明一次",
                read(DIMENS).split("webhtv_focus_ring_width", -1).length == 2);
        // 报告涉及的两个页面必须引用同一个 token，且带焦点环的控件不允许写死描边宽度。
        // 注意：布局里可能有与焦点无关的描边（例如 item_following 的 MaterialCardView
        // 卡片外框 1dp），因此只约束真正带 focus_ring_ 环色的那个控件。
        for (String layout : new String[]{ABOUT_LAYOUT, FOLLOWING_ITEM, FOLLOWING_LEANBACK}) {
            String body = values(read(layout));
            assertTrue(layout + " 必须引用统一焦点环宽度 token", body.contains(WIDTH));
            int cursor = 0;
            int ringed = 0;
            while ((cursor = body.indexOf("app:strokeColor=\"@color/focus_ring_", cursor)) >= 0) {
                int open = body.lastIndexOf('<', cursor);
                int close = body.indexOf("/>");
                close = body.indexOf("/>", cursor);
                String control = body.substring(open, close);
                assertTrue(layout + " 的带环控件必须引用统一宽度 token", control.contains("app:strokeWidth=\"" + WIDTH + "\""));
                assertFalse(layout + " 的带环控件不允许写死描边宽度",
                        control.contains("app:strokeWidth=\"3dp\"") || control.contains("app:strokeWidth=\"1dp\""));
                ringed++;
                cursor += 1;
            }
            assertTrue(layout + " 至少应有一个带环控件", ringed > 0);
        }
        // 齿轮图标是普通 drawable，描边宽度同样只能引用 token。
        String gear = values(read(ABOUT_ICON));
        assertTrue("齿轮必须引用统一焦点环宽度 token", gear.contains(WIDTH));
        assertFalse("齿轮不允许写死描边宽度", gear.contains("android:width=\"3dp\""));
    }

    // ------------------------------------------------------------ R1 边框环真的加上去了

    @Test
    public void aboutDialogButtonsAndGearShowABorderRingWhenFocused() throws Exception {
        String layout = values(read(ABOUT_LAYOUT));

        // 三个按钮都必须有描边通道。它们此前只有 app:backgroundTint，填充即主题色，
        // 焦点态没有任何额外视觉线索。
        for (String id : new String[]{"checkUpdate", "githubProxy", "confirm"}) {
            int start = layout.indexOf("android:id=\"@+id/" + id + "\"");
            assertTrue(id + " 必须存在于关于弹窗布局", start >= 0);
            int end = layout.indexOf("/>", start);
            String button = layout.substring(start, end);
            assertTrue(id + " 必须带描边色通道", button.contains("app:strokeColor="));
            assertTrue(id + " 必须带统一宽度的描边", button.contains("app:strokeWidth=\"" + WIDTH + "\""));
            assertTrue(id + " 的环色必须取 primary 填充的配对 on-色",
                    button.contains("app:strokeColor=\"@color/focus_ring_primary\""));
        }

        // 齿轮图标按钮：焦点态 = 主题色填充 + 配对 on-色环，不再写死 #0B57D0。
        String gear = values(read(ABOUT_ICON));
        assertTrue("齿轮焦点态必须画主题色填充", gear.contains("android:color=\"?attr/colorPrimary\""));
        assertTrue("齿轮焦点态必须画配对 on-色边框环",
                gear.contains("android:color=\"?attr/colorOnPrimary\""));
        assertTrue("齿轮描边必须使用统一宽度 token", gear.contains(WIDTH));
        assertFalse("齿轮不允许再写死 #0B57D0", gear.contains("#0B57D0"));
        // 擦除态保留同宽透明描边，避免焦点切换改变尺寸。
        assertTrue("齿轮非聚焦态必须保留同宽透明描边",
                gear.contains("android:color=\"@color/transparent\""));
    }

    @Test
    public void followingActionButtonsShowABorderRingMatchingTheirFill() throws Exception {
        // 卡片内 action 按钮：填充家族决定环色。
        String item = values(read(FOLLOWING_ITEM));
        String[][] expected = {
                {"nextSeason", "@color/focus_ring_secondary"},
                {"continuePlay", "@color/focus_ring_primary"},
                {"check", "@color/focus_ring_secondary"},
                // read 的 backgroundTint 是 following_button_secondary_bg，它在聚焦时把填充
                // 换成 FOCUS 色，所以环必须按 primary 家族配对，不能按常态的 secondary 容器。
                {"read", "@color/focus_ring_primary"},
                {"notify", "@color/focus_ring_secondary"},
                {"sourceChange", "@color/focus_ring_secondary"},
                {"delete", "@color/focus_ring_error"},
        };
        for (String[] entry : expected) {
            int start = item.indexOf("android:id=\"@+id/" + entry[0] + "\"");
            assertTrue(entry[0] + " 必须存在于 item_following 布局", start >= 0);
            int end = item.indexOf("/>", start);
            String button = item.substring(start, end);
            assertTrue(entry[0] + " 必须带统一宽度的描边环",
                    button.contains("app:strokeWidth=\"" + WIDTH + "\""));
            assertTrue(entry[0] + " 的环色必须与它的填充配对",
                    button.contains("app:strokeColor=\"" + entry[1] + "\""));
        }

        // 顶栏 4 个按钮：check 与其余三个都用 following_button_*_bg，聚焦填充同为 FOCUS 色。
        String bar = values(read(FOLLOWING_LEANBACK));
        String[][] header = {
                {"check", "@color/focus_ring_primary"},
                {"readAll", "@color/focus_ring_primary"},
                {"filter", "@color/focus_ring_primary"},
                {"alistImport", "@color/focus_ring_primary"},
        };
        for (String[] entry : header) {
            int start = bar.indexOf("android:id=\"@+id/" + entry[0] + "\"");
            assertTrue(entry[0] + " 必须存在于 leanback activity_following 布局", start >= 0);
            int end = bar.indexOf("/>", start);
            String button = bar.substring(start, end);
            assertTrue(entry[0] + " 必须带统一宽度的描边环",
                    button.contains("app:strokeWidth=\"" + WIDTH + "\""));
            assertTrue(entry[0] + " 的环色必须与它的填充配对",
                    button.contains("app:strokeColor=\"" + entry[1] + "\""));
        }
    }

    /**
     * 不变量：带描边环的控件必须同时声明背景填充，否则"环色 = 填充的配对 on-色"
     * 这个前提就不成立，环会贴在面板背景上而失去对比度保证。
     */
    @Test
    public void everyRingedControlStillDeclaresItsFill() throws Exception {
        for (String layout : new String[]{ABOUT_LAYOUT, FOLLOWING_ITEM, FOLLOWING_LEANBACK}) {
            String body = values(read(layout));
            int cursor = 0;
            int checked = 0;
            while ((cursor = body.indexOf("app:strokeColor=\"@color/focus_ring_", cursor)) >= 0) {
                int open = body.lastIndexOf('<', cursor);
                assertTrue(layout + " 的带环控件必须声明填充",
                        body.substring(open, cursor).contains("app:backgroundTint="));
                checked++;
                cursor += 1;
            }
            assertTrue(layout + " 至少应有一个带环控件", checked > 0);
        }
    }

    // ------------------------------------------------------------ helpers

    /** Resolves a {@code <color name="alias">@color/target</color>} indirection. */
    private static String aliasTarget(String colors, String alias) {
        java.util.regex.Matcher m = java.util.regex.Pattern
                .compile("<color name=\"" + java.util.regex.Pattern.quote(alias) + "\">([^<]+)</color>")
                .matcher(colors);
        assertTrue("colors.xml 必须声明 " + alias, m.find());
        return m.group(1).trim();
    }

    /** Reads one {@code #RRGGBB} token value from a flavour token file. */
    private static String tokenHex(String tokens, String name) {
        java.util.regex.Matcher m = java.util.regex.Pattern
                .compile("<color name=\"" + java.util.regex.Pattern.quote(name) + "\">(#[0-9A-Fa-f]{6,8})</color>")
                .matcher(tokens);
        assertTrue("token 文件必须声明 " + name, m.find());
        String hex = m.group(1);
        return hex.length() == 9 ? "#" + hex.substring(3) : hex;
    }

    /** WCAG 2.x relative-luminance contrast ratio. */
    private static double contrast(String a, String b) {
        double la = luminance(a), lb = luminance(b);
        double hi = Math.max(la, lb), lo = Math.min(la, lb);
        return (hi + 0.05) / (lo + 0.05);
    }

    private static double luminance(String hex) {
        String h = hex.startsWith("#") ? hex.substring(1) : hex;
        double r = channel(h.substring(0, 2)), g = channel(h.substring(2, 4)), bl = channel(h.substring(4, 6));
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
    }

    private static double channel(String pair) {
        double v = Integer.parseInt(pair, 16) / 255.0;
        return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    }

    private static String values(String source) {
        return source.replaceAll("(?s)<!--.*?-->", " ").replaceAll("\\s+", " ");
    }

    private static String read(String path) throws Exception {
        Path direct = Path.of(path);
        if (Files.exists(direct)) return Files.readString(direct, StandardCharsets.UTF_8);
        return Files.readString(Path.of("..").resolve(path), StandardCharsets.UTF_8);
    }
}
