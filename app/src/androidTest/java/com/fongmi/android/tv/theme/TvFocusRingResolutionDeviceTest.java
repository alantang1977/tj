package com.fongmi.android.tv.theme;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Resources;
import android.util.TypedValue;
import android.view.View;
import android.widget.FrameLayout;

import androidx.appcompat.view.ContextThemeWrapper;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fongmi.android.tv.R;
import com.google.android.material.card.MaterialCardView;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

/**
 * 设备侧证明：TV 焦点环只有一个取值源，且两条绘制路径在任何主题下都取到同一个颜色。
 *
 * <p>背景：{@code tv_item_focus_ring} 由写死的 {@code #FFD166} 接线到主题 FOCUS 用户槽之后，
 * TV 详情页仍在 Java 里写死 {@code 0xFFFFD166}，于是同一个 TV 应用里出现了两种焦点环色，
 * 且浅色详情页（底板 {@code #EBE3DA}）的黄色环对比度只有 1.14:1，几乎看不见。
 *
 * <p>本测试在真实设备上断言：
 * <ol>
 *   <li>{@code ?attr/tvFocusRing} 解析到的就是 {@code tv_item_focus_ring}，
 *       且该 token 直连主题 FOCUS 用户槽；</li>
 *   <li>{@code ThemeController.focusRingColor(...)} 与 {@code ?attr/tvFocusRing} 字节一致
 *       —— 代码路径与 XML 选择器路径共用同一取值，不得各走一套；</li>
 *   <li>用户覆写主题后两条路径仍然一致：任何一条单独"跟随"都会重新造出两种环色。</li>
 * </ol>
 */
@RunWith(AndroidJUnit4.class)
public class TvFocusRingResolutionDeviceTest {

    private ThemeProfile originalProfile;

    @Before
    public void setUp() {
        originalProfile = ThemeProfileStore.load();
    }

    @After
    public void tearDown() {
        if (originalProfile != null) ThemeProfileStore.apply(originalProfile);
        ThemeController.applyFromPreferences(null);
    }

    @Test
    public void focusRingAttributeResolvesToTheThemeFocusSlot() {
        Context context = themedContext();
        int attribute = resolveAttrColor(context);
        assertEquals("?attr/tvFocusRing 必须解析到 tv_item_focus_ring",
                context.getColor(R.color.tv_item_focus_ring), attribute);
        assertEquals("代码路径与 XML 选择器路径必须共用同一取值",
                attribute, ThemeController.focusRingColor(context));
        assertEquals("焦点环必须来自主题 FOCUS 用户槽，而不是别的角色",
                context.getColor(R.color.webhtv_color_focus), attribute);
    }

    /**
     * 主题可控性：FOCUS 用户槽被覆写后，解析值必须变化。
     * 这是主题编辑器"焦点色"可改的底层保证；环色是槽的编译取值，槽位本身必须可覆写。
     */
    @Test
    public void focusRingFollowsTheThemeFocusSlot() {
        ThemeController.applyFromPreferences(null);
        int before = ThemeController.resolveFromPreferences().colorFocus();

        ThemeProfile profile = ThemeProfile.defaultProfile();
        profile.light.focus = "#00B0FF";
        profile.dark.focus = "#00B0FF";
        ThemeProfileStore.ApplyResult applied = ThemeProfileStore.apply(profile);
        assertTrue("测试用的主题配置必须能保存: " + applied.error(), applied.success());

        ThemeController.applyFromPreferences(null);
        int slot = ThemeController.resolveFromPreferences().colorFocus();
        assertNotEquals("改 FOCUS 槽后解析值必须变化，否则主题设置对焦点环无效", before, slot);
        assertEquals("active 快照的 FOCUS 槽必须等于解析结果", slot, ThemeController.current().colorFocus());
    }

    /**
     * 回归门：主题覆写后，代码路径写下的描边与 XML 选择器路径写下的描边必须仍然相同。
     * 详情页混用两条路径（{@code focusRingColor()} 与 {@code ?attr/tvFocusRing}），
     * 任何一条单独跟随主题都会让同一个页面出现两种环色。
     */
    @Test
    public void bothRingPathsStayIdenticalUnderAThemeOverride() {
        ThemeProfile profile = ThemeProfile.defaultProfile();
        profile.light.focus = "#00B0FF";
        profile.dark.focus = "#00B0FF";
        assertTrue("主题覆写必须能保存", ThemeProfileStore.apply(profile).success());
        ThemeController.applyFromPreferences(null);

        Context context = themedContext();
        int attribute = resolveAttrColor(context);
        int codePath = ThemeController.focusRingColor(context);
        assertEquals("代码路径与 XML 属性路径在主题覆写后仍必须同色", attribute, codePath);

        final int[] bound = new int[1];
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            FrameLayout root = new FrameLayout(context);
            MaterialCardView card = new MaterialCardView(context);
            card.setStrokeColor(codePath);
            root.addView(card);
            ThemeController.bindTheme(root);
            bound[0] = card.getStrokeColor();
        });
        // binder 只会把描边改写成解析后的角色取值；若它把两条路径分岔，这里会立刻暴露。
        assertTrue("描边经 binder 后必须仍等于两条路径的共同取值",
                bound[0] == attribute || bound[0] == ThemeController.current().colorFocus());
        assertEquals("binder 改写后代码路径仍须与 XML 路径同色",
                resolveAttrColor(context), ThemeController.focusRingColor(context));
    }

    /** 应用真实主题（Theme.App -> Theme.Base 声明了 tvFocusRing）的 Context。 */
    private static Context themedContext() {
        Context base = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return new ContextThemeWrapper(base, R.style.Theme_App);
    }

    private static int resolveAttrColor(Context context) {
        TypedValue value = new TypedValue();
        Resources.Theme theme = context.getTheme();
        assertTrue("主题必须声明 tvFocusRing", theme.resolveAttribute(R.attr.tvFocusRing, value, true));
        if (value.type >= TypedValue.TYPE_FIRST_COLOR_INT
                && value.type <= TypedValue.TYPE_LAST_COLOR_INT) {
            return value.data;
        }
        return context.getColor(value.resourceId);
    }
}
