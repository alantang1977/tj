package com.fongmi.android.tv.ui.dialog;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

/**
 * The theme colour editor used to inherit Material's default alert width and covered only
 * about 58% x 70% of a 1920x1080 panel (measured on device at [405,160][1515,920]), which
 * left the 13 colour slots, the 3 opacity sliders and the live preview squeezed into a
 * narrow column. It now follows the ad-block statistics dialog contract: fill the screen
 * minus a constant gutter.
 */
public class ThemeDialogLayoutTest {

    @Test
    public void guttersMatchTheAdBlockStatisticsReferenceDialog() {
        assertEquals("mobile gutter must match AdBlockStatsDialog", 16, ThemeDialogLayout.MOBILE_MARGIN_DP);
        assertEquals("television gutter must match AdBlockStatsDialog", 24, ThemeDialogLayout.LEANBACK_MARGIN_DP);
        assertEquals(16, ThemeDialogLayout.marginDp(false));
        assertEquals(24, ThemeDialogLayout.marginDp(true));
    }

    @Test
    public void dialogFillsTheScreenMinusTheGutter() {
        // 1920x1080 at 280dpi is the measured device; the gutter is already in pixels here.
        assertEquals(1920 - 32, ThemeDialogLayout.width(1920, 16));
        assertEquals(1080 - 32, ThemeDialogLayout.height(1080, 16));
        assertEquals(1920 - 48, ThemeDialogLayout.width(1920, 24));
        assertEquals(1080 - 48, ThemeDialogLayout.height(1080, 24));
    }

    @Test
    public void enlargedFootprintIsMateriallyLargerThanTheMeasuredBaseline() {
        int width = ThemeDialogLayout.width(1920, 16);
        int height = ThemeDialogLayout.height(1080, 16);
        // Measured before the change: [405,160][1515,920] => 1110 x 760.
        assertTrue("width must exceed the measured baseline of 1110px", width > 1110);
        assertTrue("height must exceed the measured baseline of 760px", height > 760);
        assertTrue("width must cover more than 90% of the panel", width > 1920 * 0.9);
        assertTrue("height must cover more than 90% of the panel", height > 1080 * 0.9);
    }

    @Test
    public void degenerateScreensNeverProduceANonPositiveWindow() {
        assertEquals(1, ThemeDialogLayout.width(0, 16));
        assertEquals(1, ThemeDialogLayout.height(0, 16));
        assertEquals(1, ThemeDialogLayout.width(10, 16));
        assertEquals(1, ThemeDialogLayout.height(10, 16));
        // A negative gutter is clamped to zero rather than widening past the panel.
        assertEquals(100, ThemeDialogLayout.width(100, -5));
        assertEquals(100, ThemeDialogLayout.height(100, -5));
        // A missing margin must not silently drop the whole measurement.
        assertNotEquals(0, ThemeDialogLayout.width(1080, 0));
        assertEquals(1080, ThemeDialogLayout.width(1080, 0));
    }

    @Test
    public void bothFlavoursApplyTheSharedSizingContract() throws Exception {
        for (String flavour : new String[]{"mobile", "leanback"}) {
            String dialog = read("src/" + flavour + "/java/com/fongmi/android/tv/ui/dialog/ThemeDialog.java");
            assertTrue(flavour + " must size the window from the shared helper",
                    dialog.contains("ThemeDialogLayout.marginDp("));
            assertTrue(flavour + " must size the width from the shared helper",
                    dialog.contains("ThemeDialogLayout.width("));
            assertTrue(flavour + " must size the height from the shared helper",
                    dialog.contains("ThemeDialogLayout.height("));
            assertTrue(flavour + " must apply the size to the window",
                    dialog.contains("window.setLayout(width, height)"));
            assertTrue(flavour + " must drop Material's background inset",
                    dialog.contains("decorView.setPadding(0, 0, 0, 0)"));
            assertTrue(flavour + " must let the scroll area absorb the freed height",
                    dialog.contains("ViewGroup.LayoutParams.MATCH_PARENT"));
            assertTrue(flavour + " must configure the window when the dialog starts",
                    dialog.contains("configureWindow(dialog)"));
            // Regression guard: the panel is painted by the window background, so replacing
            // it with a transparent fill (safe only for a dialog whose layout has its own
            // card) erased the whole editor and showed the settings page through it.
            assertTrue(flavour + " must keep the themed panel as the window background",
                    dialog.contains("ThemeDialogLayout.panelBackground(decorView.getBackground())"));
            assertFalse(flavour + " must not replace the panel with a transparent fill",
                    dialog.contains("new ColorDrawable(Color.TRANSPARENT)"));
        }
    }

    private static String read(String path) throws Exception {
        Path root = Files.exists(Path.of("src")) ? Path.of("") : Path.of("app");
        return Files.readString(root.resolve(path), StandardCharsets.UTF_8);
    }
}
