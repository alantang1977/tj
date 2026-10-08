package com.fongmi.android.tv.theme;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * The unified theme entry point must resolve the persisted WebHTV appearance
 * preference into the shared semantic tokens so every module (following, lab,
 * dialogs, web pages) reads one source of truth.
 */
public class ThemeControllerContractTest {

    @Test
    public void controllerExposesPreferenceBackedResolution() throws Exception {
        String source = read("src/main/java/com/fongmi/android/tv/theme/ThemeController.java");
        assertTrue(source.contains("public static ThemeTokens resolveFromPreferences()"));
        assertTrue(source.contains("public static void applyFromPreferences(AppCompatActivity activity)"));
        assertTrue(source.contains("Setting.getThemeColor()"));
        assertTrue(source.contains("Setting.getWallColor()"));
        assertTrue(source.contains("ThemeSeed.WALLPAPER"));
        assertTrue(source.contains("ThemeSeed.EXPLICIT"));
    }

    @Test
    public void appearanceModeDrivesAppCompatNightMode() throws Exception {
        String controller = read("src/main/java/com/fongmi/android/tv/theme/ThemeController.java");
        assertTrue(controller.contains("public static void applyNightModeToApp()"));
        assertTrue(controller.contains("AppCompatDelegate.MODE_NIGHT_NO"));
        assertTrue(controller.contains("AppCompatDelegate.MODE_NIGHT_YES"));
        assertTrue(controller.contains("AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM"));
        assertTrue(controller.contains("ThemeMode themeMode = currentThemeMode();"));
        assertTrue(read("src/main/java/com/fongmi/android/tv/App.java").contains("ThemeController.applyNightModeToApp();"));
        for (String flavour : new String[]{"mobile", "leanback"}) {
            String dialog = read("src/" + flavour + "/java/com/fongmi/android/tv/ui/dialog/AppearanceDialog.java");
            assertTrue(dialog.contains("setting_theme_mode"));
            assertTrue(dialog.contains("Setting.putThemeMode(mode);"));
            assertTrue(dialog.contains("ThemeController.applyNightModeToApp();"));
        }
        assertTrue(read("src/main/java/com/fongmi/android/tv/setting/Setting.java").contains("public static int getThemeMode()"));
    }

    @Test
    public void everyActivityAppliesThePersistedThemeSnapshot() throws Exception {
        String mobile = read("src/mobile/java/com/fongmi/android/tv/ui/base/BaseActivity.java");
        String leanback = read("src/leanback/java/com/fongmi/android/tv/ui/base/BaseActivity.java");
        assertTrue(mobile.contains("ThemeController.applyFromPreferences(this);"));
        assertTrue(leanback.contains("ThemeController.applyFromPreferences(this);"));
    }

    @Test
    public void legacyPalettesDelegateToSemanticTokens() throws Exception {
        String colors = read("src/main/res/values/colors.xml");
        assertTrue(colors.contains("<color name=\"following_page_bg\">@color/webhtv_color_surface</color>"));
        assertTrue(colors.contains("<color name=\"following_accent\">@color/webhtv_color_primary</color>"));
        assertTrue(colors.contains("<color name=\"following_danger\">@color/webhtv_color_error</color>"));
        assertTrue(colors.contains("<color name=\"site_health_good\">@color/webhtv_color_health_good</color>"));
        assertTrue(colors.contains("<color name=\"site_health_bad\">@color/webhtv_color_health_bad</color>"));
        String lab = read("src/main/res/values/lab_colors.xml");
        assertTrue(lab.contains("<color name=\"lab_surface\">@color/webhtv_color_surface_container_high</color>"));
        assertTrue(lab.contains("<color name=\"lab_text_primary\">@color/webhtv_color_on_surface</color>"));
    }

    @Test
    public void followingAndDetailSurfacesUseSemanticAttributes() throws Exception {
        String following = read("src/main/res/layout/activity_following.xml");
        // 追更页改为壁纸背景：根布局必须透明，靠半透明面板承载文字。
        assertFalse(following.contains("android:background=\"?attr/colorSurface\""));
        assertTrue(following.contains("@drawable/shape_following_panel"));
        assertTrue(following.contains("app:backgroundTint=\"?attr/colorPrimary\""));
        assertTrue(following.contains("android:textColor=\"?attr/colorOnSurfaceVariant\""));
        String card = read("src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbCastPresenter.java");
        assertTrue(card.contains("ThemeController.current()"));
        assertTrue(card.contains("tokens.colorSurfaceContainerHigh()"));
        // 焦点环已由前景 selector（?attr/tvFocusRing，取值 tv_item_focus_ring）统一绘制，
        // presenter 只维护常态描边与卡面 token；不再自己画焦点描边以免双重描边。
        assertFalse(card.contains("tokens.colorFocus()"));
        assertTrue(card.contains("STROKE_NORMAL"));
        String video = read("src/leanback/java/com/fongmi/android/tv/ui/presenter/TmdbVideoPresenter.java");
        assertTrue(video.contains("selector_tmdb_media_focus"));
        String dialog = read("src/mobile/java/com/fongmi/android/tv/ui/dialog/AppearanceDialog.java");
        // 行的底色/描边与两个文字色必须来自同一个调色板：此前行底是固定浅色
        // selector_git_cloud_card，而文字已跟随 ThemeController.current()，在 TV 深色表上
        // 实测 1.16:1 / 1.36:1。现在两者都经由 AppearanceRowTheme 取当前 token。
        assertTrue(dialog.contains("AppearanceRowTheme.apply(row, title, summary, ThemeController.current())"));
        String rowTheme = read("src/main/java/com/fongmi/android/tv/theme/AppearanceRowTheme.java");
        assertTrue(rowTheme.contains("safe.colorOnSurface()"));
        assertTrue(rowTheme.contains("safe.colorOnSurfaceVariant()"));
    }

    @Test
    public void snapshotIsResolvedBeforeTheFirstContentView() throws Exception {
        for (String flavour : new String[]{"mobile", "leanback"}) {
            String source = read("src/" + flavour + "/java/com/fongmi/android/tv/ui/base/BaseActivity.java");
            int apply = source.indexOf("ThemeController.applyFromPreferences(this);");
            int content = source.indexOf("setContentView(");
            assertTrue(flavour + " must apply the persisted snapshot", apply > 0);
            assertTrue(flavour + " must set a content view", content > 0);
            assertTrue(flavour + " must resolve the theme snapshot before its first content view", apply < content);
        }
    }

    @Test
    public void controllerReadsTheV2ProfileAndKeepsABaselineSnapshot() throws Exception {
        String controller = read("src/main/java/com/fongmi/android/tv/theme/ThemeController.java");
        assertTrue(controller.contains("ThemeProfileStore.load()"));
        assertTrue(controller.contains("private static ThemeTokens resolveWith(ThemeProfile profile)"));
        assertTrue(controller.contains("baseline = frozenPalette();"));
        assertFalse("the binder baseline must never be seed-derived",
                controller.contains("baseline = resolveWith("));
        assertTrue(controller.contains("private static ThemeTokens frozenPalette()"));
        assertTrue(controller.contains("current = resolveWith(profile);"));
        assertTrue(controller.contains("ThemeBinder.bind(root, baseline, current);"));
        assertTrue(controller.contains("public static ThemeTokens baseline()"));
    }

    @Test
    public void ordinaryUiNightDecisionComesFromTheThemeController() throws Exception {
        String controller = read("src/main/java/com/fongmi/android/tv/theme/ThemeController.java");
        assertTrue(controller.contains("public static boolean isNight(Context context)"));
        String chrome = read("src/mobile/java/com/fongmi/android/tv/ui/activity/WebHomeChromeController.java");
        assertTrue(chrome.contains("ThemeController.isNight(activity)"));
        assertFalse(chrome.contains("UI_MODE_NIGHT_MASK"));
    }

    private static String read(String path) throws Exception {
        Path root = Files.exists(Path.of("src")) ? Path.of("") : Path.of("app");
        return Files.readString(root.resolve(path), StandardCharsets.UTF_8);
    }
}
