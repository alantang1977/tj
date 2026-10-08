package com.fongmi.android.tv.ui.activity;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.Assert.assertFalse;
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
                read(DIMENS).contains("<dimen name=\"webhtv_focus_ring_width\">3dp</dimen>"));
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
