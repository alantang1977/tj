package com.fongmi.android.tv.theme;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Layer 1 integration contract: both flavours inherit the WebHTV semantic theme and the
 * Activity theme maps every Material color role used by layouts onto a webhtv token, so no
 * screen silently falls back to the Material baseline palette.
 */
public class ThemeBaseWiringTest {

    private static final String[] ACTIVITY_ROLES = {
            "colorPrimary", "colorOnPrimary", "colorPrimaryContainer", "colorOnPrimaryContainer",
            "colorSecondary", "colorOnSecondary", "colorSecondaryContainer", "colorOnSecondaryContainer",
            "colorTertiary", "colorOnTertiary",
            "colorError", "colorOnError", "colorErrorContainer", "colorOnErrorContainer",
            "colorSurface", "colorSurfaceDim", "colorSurfaceBright",
            "colorSurfaceContainerLowest", "colorSurfaceContainerLow", "colorSurfaceContainer",
            "colorSurfaceContainerHigh", "colorSurfaceContainerHighest", "colorSurfaceVariant",
            "colorOnSurface", "colorOnSurfaceVariant", "colorOutline", "colorOutlineVariant",
            "colorSurfaceInverse", "colorOnSurfaceInverse", "colorPrimaryInverse",
            "colorControlNormal", "colorControlActivated",
    };

    private static final String[] DIALOG_ROLES = {
            "colorPrimary", "colorOnPrimary",
            "colorSecondaryContainer", "colorOnSecondaryContainer",
            "colorError", "colorOnError", "colorErrorContainer", "colorOnErrorContainer",
            "colorSurface", "colorSurfaceContainer", "colorSurfaceContainerHigh", "colorSurfaceContainerHighest",
            "colorOnSurface", "colorOnSurfaceVariant", "colorOutline", "colorOutlineVariant",
            "colorControlNormal", "colorControlActivated",
    };

    /** Layouts draw these over video, so they keep their own alpha instead of ?attr/colorOnSurface. */
    private static final String[] ON_SURFACE_ALPHA_ATTRS = {
            "colorOnSurface_20", "colorOnSurface_70", "colorOnSurface_80", "colorOnSurface_90",
    };

    /**
     * List/overlay layouts whose text is a flat colour over a fill that is dark in
     * every state.
     *
     * <p>Upstream painted these with a flat light colour ({@code @color/white},
     * {@code @color/white_60/80}); the unification to {@code ?attr/colorOnSurface}
     * resolved them to #1A1C1E in day mode and made them dark-on-dark over the
     * wallpaper, the video surface and the translucent white glass panels. Upstream
     * reused the very same item layouts inside {@code dialog_quick_search},
     * {@code dialog_episode_list} and {@code dialog_receive}, so a single always-light
     * role is correct in both the page and the dialog host.
     *
     * <p>The fill of each of these is {@code shape_live} (#47000000 / #5C000000),
     * {@code shape_vod_list} / {@code shape_vod_name} (#33000000),
     * {@code shape_video_episode_grid} (#99000000), {@code shape_quick_search_item} or a
     * {@code ?attr/colorSurfaceContainer*} panel - never a light one - so no state list
     * is needed. Their adapters were checked for {@code setSelected}: none of them call
     * it except through {@code shape_item}'s states, which this list excludes.
     */
    private static final String[] WALLPAPER_ITEMS = {
            "adapter_channel.xml", "adapter_epg_data.xml", "adapter_file.xml",
            "adapter_group.xml", "adapter_search.xml", "adapter_search_hot_word.xml",
            "adapter_search_record.xml", "adapter_search_word.xml", "adapter_vod.xml",
            "adapter_vod_list.xml", "adapter_vod_oval.xml", "view_empty.xml",
            "adapter_quick.xml", "view_progress.xml",
    };

    /**
     * Selectable items whose fill turns light when selected, so a flat colour cannot
     * serve both states.
     *
     * <p>{@code selector_item} is the shared fill of these items in the mobile flavour:
     * {@code state_selected} paints {@code colorSecondaryContainer} at 0.65 alpha - a
     * light grey in day mode (#DFE2E6 over the wallpaper measured #BAB9C5) - while the
     * default entry paints 15% black over the wallpaper, which is dark. Measured on the
     * home type chips: white text on the selected chip gave 1.94:1, dark text gave
     * 8.82:1; on an unselected chip white gave 6.32:1 and dark 2.71:1. Neither a flat
     * white nor a flat dark value can be right for both, which is why upstream shipped
     * these as state lists and why dev3 carried them until the unification replaced them.
     *
     * <p>This is the exact set dev3 used before that change; restoring it is the fix.
     */
    private static final String[][] WALLPAPER_STATE_ITEMS = {
            // chips over shape_item / shape_item_round -> selector_item
            {"adapter_type.xml", "@color/selector_text"},
            {"adapter_collect.xml", "@color/selector_text"},
            // episode / quality / flag rows over shape_video_item
            {"adapter_episode_grid.xml", "@color/selector_video_text"},
            {"adapter_episode_group.xml", "@color/selector_video_text"},
            {"adapter_episode_hori.xml", "@color/selector_video_text"},
            {"adapter_flag.xml", "@color/selector_video_text"},
            {"adapter_quality.xml", "@color/selector_video_text"},
    };

    /** Pages whose rows sit directly on the (dark) app wallpaper. */
    private static final String[] WALLPAPER_PAGES = {
            "fragment_setting.xml", "fragment_setting_ad.xml", "fragment_setting_ai.xml",
            "fragment_setting_danmaku.xml", "fragment_setting_enhance.xml",
            "fragment_setting_personal.xml", "fragment_setting_player.xml",
            "fragment_setting_subtitle.xml", "fragment_setting_tmdb.xml",
    };

    @Test
    public void flavourBaseThemesInheritTheWebhtvSemanticTheme() throws Exception {
        String mobile = read("src/mobile/res/values/styles.xml");
        assertTrue(mobile.contains("<style name=\"Theme.Base\" parent=\"Theme.WebHTV.Mobile\">"));
        assertFalse(mobile, mobile.contains("Theme.Material3.DynamicColors"));
        assertTrue(mobile.contains("<item name=\"materialAlertDialogTheme\">@style/ThemeOverlay.WebHTV.Dialog</item>"));
        assertTrue(mobile.contains("<item name=\"android:statusBarColor\">@color/transparent</item>"));

        String leanback = read("src/leanback/res/values/styles.xml");
        assertTrue(leanback.contains("<style name=\"Theme.Base\" parent=\"Theme.WebHTV.TV\">"));
        assertFalse(leanback, leanback.contains("<item name=\"colorPrimary\">@color/white</item>"));
    }

    @Test
    public void activityThemeMapsEveryMaterialColorRole() throws Exception {
        String theme = read("src/main/res/values/webhtv_styles.xml");
        assertFalse(theme, theme.contains("DynamicColors"));
        String body = styleBody(theme, "Theme.WebHTV");
        for (String role : ACTIVITY_ROLES) {
            assertTrue(role, body.contains("<item name=\"" + role + "\">@color/webhtv_"));
        }
        assertTrue(body.contains("<item name=\"android:colorBackground\">@color/webhtv_color_surface</item>"));
        assertTrue(body.contains("<item name=\"android:windowBackground\">?attr/colorSurface</item>"));
    }

    /**
     * Material points the framework text attributes at its own
     * {@code m3_sys_color_*} palette, so a widget built from the Activity context keeps
     * Material's colours and ThemeBinder cannot rewrite them (measured on device:
     * Material's {@code on_surface_variant} {@code #49454F} survived a custom theme).
     * The activity theme must therefore map the framework text roles onto our tokens.
     */
    @Test
    public void activityThemeMapsFrameworkTextRolesToWebhtvTokens() throws Exception {
        String theme = read("src/main/res/values/webhtv_styles.xml");
        String body = styleBody(theme, "Theme.WebHTV");
        for (String role : new String[]{
                "android:textColorPrimary", "android:textColorSecondary",
                "android:textColorTertiary", "android:textColorHint"}) {
            assertTrue(role + " must resolve through a webhtv selector",
                    body.contains("<item name=\"" + role + "\">@color/webhtv_text_"));
        }
        String primary = read("src/main/res/color/webhtv_text_primary.xml");
        String secondary = read("src/main/res/color/webhtv_text_secondary.xml");
        assertTrue(primary.contains("@color/webhtv_color_on_surface"));
        assertTrue(secondary.contains("@color/webhtv_color_on_surface_variant"));
        // Disabled emphasis must survive, otherwise disabled widgets no longer dim.
        assertTrue(primary.contains("android:state_enabled=\"false\""));
        assertTrue(secondary.contains("android:state_enabled=\"false\""));
    }

    @Test
    public void dialogsReuseTheSameSemanticRoles() throws Exception {
        String theme = read("src/main/res/values/webhtv_styles.xml");
        for (String style : new String[]{"Theme.WebHTV.Dialog", "ThemeOverlay.WebHTV.Dialog"}) {
            String body = styleBody(theme, style);
            for (String role : DIALOG_ROLES) {
                assertTrue(style + " is missing " + role, body.contains("<item name=\"" + role + "\">"));
            }
        }
    }

    @Test
    public void everyLayoutReferencedOnSurfaceAlphaAttrIsDeclaredAndThemed() throws Exception {
        StringBuilder layouts = new StringBuilder();
        for (String directory : new String[]{
                "src/main/res/layout", "src/mobile/res/layout", "src/leanback/res/layout"}) {
            Path root = Path.of(directory);
            if (!Files.isDirectory(root)) continue;
            try (var paths = Files.walk(root)) {
                for (Path path : paths.filter(Files::isRegularFile).toList()) {
                    layouts.append(Files.readString(path, StandardCharsets.UTF_8));
                }
            }
        }
        String attrs = read("src/main/res/values/webhtv_attrs.xml");
        String theme = styleBody(read("src/main/res/values/webhtv_styles.xml"), "Theme.WebHTV");
        for (String attr : ON_SURFACE_ALPHA_ATTRS) {
            if (!layouts.toString().contains("?attr/" + attr)) continue;
            assertTrue(attr + " is used by a layout but never declared", attrs.contains("name=\"" + attr + "\" format=\"color\""));
            assertTrue(attr + " is declared but never assigned by Theme.WebHTV", theme.contains("<item name=\"" + attr + "\">"));
        }
    }

    @Test
    public void onSurfaceAlphaResourcesTrackTheOnSurfaceToken() throws Exception {
        String[][] palettes = {
                {"src/main/res/values/webhtv_tokens.xml", "webhtv_color_on_surface", "src/main/res/values-night/webhtv_tokens.xml"},
        };
        for (String[] palette : palettes) {
            assertAlphaVariants(palette[0], palette[2]);
        }
        assertAlphaVariants("src/leanback/res/values/webhtv_tokens.xml", null);
    }

    /**
     * A page that sits on the wallpaper must not use {@code ?attr/colorOnSurface}.
     *
     * <p>{@code BaseActivity} paints a full-screen {@code CustomWallView} under every
     * mobile activity and every built-in wall is dark, while dialogs draw their text on a
     * light panel. A single {@code ?attr/colorOnSurface} therefore cannot serve both: the
     * light table made the settings rows near-black on the wallpaper (measured 1.27:1),
     * the dark table turned dialog text light on a light card (measured 1.24:1). The two
     * consumers are separated by {@code ?attr/webhtvColorOnWallpaper}, which is always
     * light.
     *
     * <p>Guard: this pins both halves so a future migration cannot quietly put a page back
     * on the dialog role, and cannot make the wallpaper role follow the surface at all.
     */
    @Test
    public void wallpaperPagesUseTheWallpaperForegroundRole() throws Exception {
        String[] all = new String[WALLPAPER_PAGES.length + WALLPAPER_ITEMS.length];
        System.arraycopy(WALLPAPER_PAGES, 0, all, 0, WALLPAPER_PAGES.length);
        System.arraycopy(WALLPAPER_ITEMS, 0, all, WALLPAPER_PAGES.length, WALLPAPER_ITEMS.length);
        for (String name : all) {
            String source = read("src/mobile/res/layout/" + name);
            assertFalse(name + " still paints wallpaper rows with the dialog on-surface role",
                    source.contains("android:textColor=\"?attr/colorOnSurface\""));
            assertTrue(name + " must use ?attr/webhtvColorOnWallpaper for its rows",
                    source.contains("android:textColor=\"?attr/webhtvColorOnWallpaper\""));
        }
    }

    /**
     * Selectable items must keep a state list, not a flat colour.
     *
     * <p>Their shared fill turns light when selected, so the text has to switch with it:
     * {@code selector_text} resolves to {@code colorOnSecondaryContainer}, and
     * {@code selector_video_text} resolves to the selected highlight, both falling back
     * to a light default. Collapsing either to one colour reintroduces an unreadable pair
     * on whichever state loses.
     */
    @Test
    public void selectableWallpaperItemsKeepAStateList() throws Exception {
        for (String[] entry : WALLPAPER_STATE_ITEMS) {
            String name = entry[0];
            String selector = entry[1];
            String source = read("src/mobile/res/layout/" + name);
            assertFalse(name + " must not fall back to the dialog on-surface role",
                    source.contains("android:textColor=\"?attr/colorOnSurface\""));
            assertTrue(name + " must paint its selectable text with " + selector,
                    source.contains("android:textColor=\"" + selector + "\""));
        }
    }

    /**
     * The state lists themselves must stay light by default and distinct when selected.
     *
     * <p>A flat list would silently defeat the guard above, so the semantics are pinned:
     * every entry resolves to a colour, the default entry is the light one used over the
     * dark wallpaper, and the selected entry is not the same as it.
     */
    @Test
    public void wallpaperStateListsAreLightByDefaultAndDistinctWhenSelected() throws Exception {
        String[][] selectors = {
                {"selector_text.xml", "@color/white"},
                {"selector_video_text.xml", "@color/white"},
        };
        for (String[] entry : selectors) {
            String name = entry[0];
            String source = read("src/mobile/res/color/" + name);
            assertTrue(name + " must declare a selected state",
                    source.contains("state_selected=\"true\""));
            assertTrue(name + " must fall back to the light wallpaper foreground",
                    source.contains("<item android:color=\"" + entry[1] + "\" />"));
            String selected = selectedColor(source);
            assertFalse(name + " selected colour must differ from its default",
                    entry[1].equals(selected));
            assertFalse(name + " must not reuse the dialog on-surface role",
                    selected.contains("colorOnSurface\""));
        }
    }

    /** Colour of the first entry guarded by {@code state_selected}. */
    private static String selectedColor(String selectorSource) {
        for (String line : selectorSource.split("\n")) {
            if (line.contains("state_selected=\"true\"")) {
                int start = line.indexOf("android:color=\"");
                assertTrue("selected entry has no colour: " + line, start >= 0);
                return line.substring(start + "android:color=\"".length(), line.indexOf('"', start + "android:color=\"".length()));
            }
        }
        throw new AssertionError("no state_selected entry found");
    }

    /**
     * The wallpaper foreground must stay light, identical in every palette, and out of
     * the binder's reach.
     *
     * <p>It is 0xFFFFFFFF in all three tables because the wallpaper is dark in both
     * system night modes. {@code ThemeBinder} only rewrites a view colour when
     * {@code ThemeColorIndex.replacementFor} yields a different value, so the guard is:
     * for every baseline palette and every active palette, 0xFFFFFFFF must resolve to
     * either no replacement or the value it already has.
     *
     * <p>The two palettes keep the colour out of reach for different reasons, and both
     * are fragile, so both are pinned. In the light palette 0xFFFFFFFF is shared by
     * {@code onPrimary}, {@code onError}, {@code onSuccess} and {@code onWarning}; those
     * roles only agree when they resolve to the identical colour, and the index reports
     * that as no change. In the dark palette no indexed role carries the value at all
     * ({@code colorPlayerControl} is 0xFFFFFFFF in both palettes but is not a
     * {@link ThemeRole}), so the lookup finds nothing to rewrite. A future palette edit
     * that made an indexed role resolve 0xFFFFFFFF to a different colour would start
     * repainting wallpaper text - this test fails first.
     */
    @Test
    public void wallpaperForegroundIsLightAndNotBinderRewritable() throws Exception {
        String light = read("src/main/res/values/webhtv_tokens.xml");
        String night = read("src/main/res/values-night/webhtv_tokens.xml");
        String tv = read("src/leanback/res/values/webhtv_tokens.xml");
        for (String source : new String[]{light, night, tv}) {
            assertTrue("every palette must declare webhtv_on_wallpaper",
                    source.contains("<color name=\"webhtv_on_wallpaper\">#FFFFFF</color>"));
        }

        String attrs = read("src/main/res/values/webhtv_attrs.xml");
        assertTrue("webhtvColorOnWallpaper must be declared",
                attrs.contains("name=\"webhtvColorOnWallpaper\" format=\"color\""));
        String theme = styleBody(read("src/main/res/values/webhtv_styles.xml"), "Theme.WebHTV");
        assertTrue("Theme.WebHTV must assign webhtvColorOnWallpaper",
                theme.contains("<item name=\"webhtvColorOnWallpaper\">@color/webhtv_on_wallpaper</item>"));

        // The binder only rewrites a colour when the index yields a different
        // replacement, so 0xFFFFFFFF must never resolve to one for any palette pair.
        ThemeTokens[] palettes = {ThemeTokens.light(), ThemeTokens.dark()};
        for (ThemeTokens baseline : palettes) {
            ThemeColorIndex index = ThemeColorIndex.of(baseline);
            for (ThemeTokens active : palettes) {
                assertNull("the wallpaper foreground must never be rewritten by the binder",
                        index.replacementFor(0xFFFFFFFF, active));
            }
        }
    }

    private static void assertAlphaVariants(String lightOrTvPath, String nightPath) throws Exception {
        for (String path : nightPath == null ? new String[]{lightOrTvPath} : new String[]{lightOrTvPath, nightPath}) {
            String source = read(path);
            String onSurface = hex(source, "webhtv_color_on_surface");
            assertEquals(path + " must declare the onSurface token", 6, onSurface.length());
            assertTrue(path + " webhtv_on_surface_20",
                    source.contains("<color name=\"webhtv_on_surface_20\">#33" + onSurface + "</color>"));
            assertTrue(path + " webhtv_on_surface_70",
                    source.contains("<color name=\"webhtv_on_surface_70\">#B3" + onSurface + "</color>"));
            assertTrue(path + " webhtv_on_surface_80",
                    source.contains("<color name=\"webhtv_on_surface_80\">#CC" + onSurface + "</color>"));
            assertTrue(path + " webhtv_on_surface_90",
                    source.contains("<color name=\"webhtv_on_surface_90\">#E6" + onSurface + "</color>"));
        }
    }

    private static String hex(String source, String colorName) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("<color name=\"" + colorName + "\">#([0-9A-Fa-f]{6})</color>")
                .matcher(source);
        assertTrue(colorName + " is missing", matcher.find());
        return matcher.group(1).toUpperCase(java.util.Locale.ROOT);
    }

    private static String styleBody(String source, String style) {
        int start = source.indexOf("<style name=\"" + style + "\"");
        assertTrue(style + " is missing", start >= 0);
        int end = source.indexOf("</style>", start);
        assertTrue(style + " is not closed", end > start);
        return source.substring(start, end);
    }

    private static String read(String path) throws Exception {
        Path root = Files.exists(Path.of("src")) ? Path.of("") : Path.of("app");
        return Files.readString(root.resolve(path), StandardCharsets.UTF_8);
    }
}
