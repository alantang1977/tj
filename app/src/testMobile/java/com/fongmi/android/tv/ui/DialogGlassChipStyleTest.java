package com.fongmi.android.tv.ui;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class DialogGlassChipStyleTest {

    /** The two video-frame extremes a translucent dialog stack can sit on. */
    private static final double[][] FRAME_EXTREMES = {{0, 0, 0}, {255, 255, 255}};

    @Test
    public void trackAndTitleSelectionsShareTheLightGlassFocusStyle() throws Exception {
        String selector = readMainResource("drawable", "selector_dialog_glass_chip.xml");
        String active = readMainResource("drawable", "shape_dialog_glass_chip_active.xml");
        String text = readMainResource("color", "selector_dialog_glass_chip_text.xml");
        String track = readLeanbackResource("layout", "adapter_track.xml");
        String title = readLeanbackResource("layout", "adapter_title.xml");
        String danmaku = readLeanbackResource("layout", "adapter_danmaku.xml");

        assertEquals("all focused/selected/checked/activated chip states must share one active drawable",
                5, occurrences(selector, "@drawable/shape_dialog_glass_chip_active"));
        assertTrue("active chips must use the light gray fill from the requested selected style",
                active.contains("android:color=\"#E6E6EA\""));
        assertTrue("active chips must keep a bright two-dp inner border",
                active.contains("android:width=\"2dp\"")
                        && active.contains("android:color=\"#F2FFFFFF\""));
        assertTrue("active chips must include the blue-gray lower focus edge",
                active.contains("android:color=\"#6B6F9F\""));
        // Every chip state the background selector can reach must keep a text entry of its own;
        // a dropped entry silently falls back to the palette-following default and re-ships the
        // reported defect for that state (state_activated is the TV persistent-selection state).
        String states = withoutComments(text);
        assertEquals("the chip text selector must keep exactly one entry per chip state",
                6, occurrences(states, "<item "));
        for (String state : new String[]{
                "android:state_enabled=\"false\"", "android:state_checked=\"true\"",
                "android:state_activated=\"true\"", "android:state_selected=\"true\"",
                "android:state_focused=\"true\""}) {
            assertTrue("the chip text selector must keep its " + state + " entry",
                    states.contains(state));
        }
        assertTrue("subtitle rows must use the shared chip background and text selectors",
                usesSharedSelectors(track));
        assertTrue("title rows must use the shared chip background and text selectors",
                usesSharedSelectors(title));
        assertTrue("danmaku rows must use the shared chip background and text selectors",
                usesSharedSelectors(danmaku));
    }

    /**
     * The chip text must not follow the palette.
     *
     * <p>The chip fill and its host panel are fixed in both tables, so a palette-following
     * foreground is unreadable in one of them. The reported defect was the night table:
     * {@code colorOnSurface} {@code #E2E2E9} on the selected fill {@code #E6E6EA} measured
     * <b>1.04:1</b>, which renders the selected track as a glowing white bar. The day table
     * has the mirror defect on the default chip: {@code #1A1C1E} on the translucent indigo
     * fill measured <b>1.68:1</b>.
     *
     * <p>The check is the resolved contrast rather than the literal spelling, so the colours
     * may be re-tuned as long as both states stay legible.
     */
    @Test
    public void chipTextStaysReadableOnItsFixedFillInBothPalettes() throws Exception {
        String text = withoutComments(readMainResource("color", "selector_dialog_glass_chip_text.xml"));
        String active = withoutComments(readMainResource("drawable", "shape_dialog_glass_chip_active.xml"));

        assertFalse("chip text must not follow the palette: its fill is fixed in both tables",
                text.contains("?attr/"));

        String selectedFill = resolve(lastSolidColor(active));
        assertNotNull("the selected chip face must resolve to a literal", selectedFill);
        String selectedForeground = resolve(lastColorForState(text, "android:state_checked=\"true\""));
        assertNotNull("the checked state must resolve to a literal", selectedForeground);
        double selected = contrast(selectedForeground, selectedFill);
        assertTrue("checked chip text " + selectedForeground + " on " + selectedFill + " measures "
                        + String.format(Locale.ROOT, "%.2f:1", selected) + ", below the 4.5:1 body-text floor",
                selected >= 4.5);

        String defaultFill = resolve(lastSolidColor(
                withoutComments(readMainResource("drawable", "selector_dialog_glass_chip.xml"))));
        assertNotNull("the default chip fill must resolve to a literal", defaultFill);
        String defaultForeground = resolve(lastColorForState(text, "<item "));
        assertNotNull("the default state must resolve to a literal", defaultForeground);
        // The chip is translucent (47%) and sits on the equally translucent glass panel
        // (80-90%), which sits on the video frame. Both layers let light through, so a bright
        // frame makes the composited face LIGHTER than the chip's raw colour: the raw value
        // measures 8.64:1, while the real stack bottoms out at 6.84:1 on a white frame. The
        // raw value is therefore an optimistic proxy, not the worst case - assert the real
        // composite so the guard enforces what the chip-text comment claims.
        double worst = Double.MAX_VALUE;
        int evaluated = 0;
        for (String[] panel : new String[][]{{"main", "drawable", "shape_dialog_glass_panel.xml"},
                {"leanback", "drawable", "shape_dialog_danmaku_sheet_glass_panel.xml"}}) {
            String[] stops = gradientStops(readPanel(panel[0], panel[1], panel[2]));
            // Pin the stop count: a gradient that lost its stops (or became a flat <solid>)
            // would leave `worst` at MAX_VALUE and make the floor below pass vacuously.
            assertEquals(panel[2] + " must stay a three-stop gradient so its worst case is computable",
                    3, stops.length);
            for (String stop : stops) {
                String glass = resolve(stop);
                assertNotNull("every glass gradient stop must resolve to a literal: " + stop, glass);
                for (double[] frame : FRAME_EXTREMES) {
                    double[] face = composite(defaultFill, composite(glass, frame));
                    worst = Math.min(worst, contrast(composite(defaultForeground, face), face));
                    evaluated++;
                }
            }
        }
        assertEquals("every glass stop must be checked against both frame extremes", 12, evaluated);
        assertTrue("default chip text " + defaultForeground + " on " + defaultFill + " over the glass"
                        + " measures " + String.format(Locale.ROOT, "%.2f:1", worst)
                        + " at worst, below the 4.5:1 body-text floor",
                worst >= 4.5);
    }

    private static String readPanel(String flavour, String type, String file) throws Exception {
        return withoutComments(read(findAppPath().resolve(Path.of("src", flavour, "res", type, file))));
    }

    /** The {@code startColor}/{@code centerColor}/{@code endColor} of a gradient, in declaration order. */
    private static String[] gradientStops(String drawable) {
        String[] found = new String[3];
        int count = 0;
        for (String attribute : new String[]{"startColor", "centerColor", "endColor"}) {
            String marker = "android:" + attribute + "=\"";
            int at = drawable.indexOf(marker);
            if (at < 0) continue;
            int start = at + marker.length();
            found[count++] = drawable.substring(start, drawable.indexOf('"', start));
        }
        String[] stops = new String[count];
        System.arraycopy(found, 0, stops, 0, count);
        return stops;
    }

    /** Composites an {@code #AARRGGBB}/{@code #RRGGBB} colour over an opaque backdrop. */
    private static double[] composite(String colour, double[] backdrop) {
        String digits = colour.startsWith("#") ? colour.substring(1) : colour;
        double alpha = digits.length() == 8 ? Integer.parseInt(digits.substring(0, 2), 16) / 255.0 : 1.0;
        String rgb = digits.length() == 8 ? digits.substring(2) : digits;
        double[] out = new double[3];
        for (int channel = 0; channel < 3; channel++) {
            double value = Integer.parseInt(rgb.substring(channel * 2, channel * 2 + 2), 16);
            out[channel] = alpha * value + (1 - alpha) * backdrop[channel];
        }
        return out;
    }

    private static double contrast(double[] first, double[] second) {
        double a = luminance(first);
        double b = luminance(second);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }

    private static double luminance(double[] rgb) {
        double[] channels = new double[3];
        for (int channel = 0; channel < 3; channel++) {
            double value = rgb[channel] / 255.0;
            channels[channel] = value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    }

    /**
     * Proves the contrast guard above is not vacuous.
     *
     * <p>Feeds the exact pair that shipped the reported defect - the night table's
     * {@code colorOnSurface} over the selected chip face - and requires it to be rejected,
     * so a future edit that restores a palette-following role cannot pass silently.
     */
    @Test
    public void theContrastGuardRejectsThePairThatShippedTheDefect() {
        double night = contrast("#E2E2E9", "#E6E6EA");
        assertTrue("the night onSurface/selected-chip pair must be rejected (measured "
                        + String.format(Locale.ROOT, "%.2f:1", night) + ")",
                night < 4.5);
        double day = contrast("#1A1C1E", "#383C73");
        assertTrue("the day onSurface/default-chip pair must be rejected (measured "
                        + String.format(Locale.ROOT, "%.2f:1", day) + ")",
                day < 4.5);
    }

    /**
     * The last {@code <solid>} fill of a chip drawable.
     *
     * <p>Both chip drawables declare their states in order, so the last fill is the one the
     * ordinary (unselected, enabled) chip paints: the raised face of
     * {@code shape_dialog_glass_chip_active} and the default item of
     * {@code selector_dialog_glass_chip}.
     */
    private static String lastSolidColor(String source) {
        String found = null;
        int at = 0;
        while ((at = source.indexOf("<solid android:color=\"", at)) >= 0) {
            int start = at + "<solid android:color=\"".length();
            int end = source.indexOf('"', start);
            if (end < 0) break;
            found = source.substring(start, end);
            at = end;
        }
        return found;
    }

    /** Drops XML comments so a documented colour name cannot satisfy a value assertion. */
    private static String withoutComments(String source) {
        return source.replaceAll("(?s)<!--.*?-->", "");
    }

    /**
     * The {@code android:color} of the last line carrying {@code marker}, or null.
     *
     * <p>The last rather than the first: a selector's final {@code <item>} is its default
     * state, which is the one an unselected chip resolves.
     */
    private static String lastColorForState(String source, String marker) {
        String found = null;
        for (String line : source.split("\n")) {
            if (!line.contains(marker)) continue;
            int at = line.indexOf("android:color=\"");
            if (at < 0) continue;
            int start = at + "android:color=\"".length();
            int end = line.indexOf('"', start);
            if (end > start) found = line.substring(start, end);
        }
        return found;
    }

    /** Resolves a {@code #RRGGBB} literal or a {@code @color/<name>} reference, or null. */
    private static String resolve(String value) throws Exception {
        if (value == null) return null;
        if (value.startsWith("#")) return value.matches("#[0-9A-Fa-f]{6,8}") ? value : null;
        if (!value.startsWith("@color/")) return null;
        String name = value.substring("@color/".length());
        String colors = readMainResource("values", "colors.xml");
        String marker = "<color name=\"" + name + "\">";
        int at = colors.indexOf(marker);
        if (at < 0) return null;
        int start = at + marker.length();
        int end = colors.indexOf('<', start);
        if (end < 0) return null;
        String resolved = colors.substring(start, end).trim();
        return resolved.startsWith("#") ? resolved : null;
    }

    /** WCAG 2.x relative-luminance contrast; alpha is dropped. */
    private static double contrast(String first, String second) {
        double a = luminance(first);
        double b = luminance(second);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }

    private static double luminance(String hex) {
        String digits = hex.startsWith("#") ? hex.substring(1) : hex;
        if (digits.length() == 8) digits = digits.substring(2);
        double[] channels = new double[3];
        for (int i = 0; i < 3; i++) {
            double value = Integer.parseInt(digits.substring(i * 2, i * 2 + 2), 16) / 255.0;
            channels[i] = value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    }

    @Test
    public void trackAdapterUsesActivatedStateForPersistentSelection() throws Exception {
        String adapter = read(findAppPath().resolve(Path.of("src", "main", "java", "com", "fongmi", "android", "tv", "ui", "adapter", "TrackAdapter.java")));

        assertTrue("track selection must use activated state so focus cannot erase the selected text color",
                adapter.contains("holder.binding.text.setActivated(item.isSelected());"));
        assertTrue("selected state is reserved for transient focus and must not represent the playing track",
                !adapter.contains("holder.binding.text.setSelected(item.isSelected());"));
    }

    @Test
    public void mobileTrackStyleSupportsPersistentActivatedState() throws Exception {
        String text = readMobileResource("color", "selector_control_sheet_text.xml");
        String background = readMobileResource("drawable", "selector_player_child_sheet_button.xml");

        assertTrue("mobile selected track text must react to the adapter activated state",
                text.contains("android:state_activated=\"true\""));
        assertTrue("mobile selected track background must react to the adapter activated state",
                background.contains("android:state_activated=\"true\""));
    }

    @Test
    public void mobileCategoryAndFilterDialogsShareTheControlSheetStyle() throws Exception {
        String category = readMobileResource("layout", "adapter_type_dialog.xml");
        String filter = readMobileResource("layout", "adapter_value.xml");

        assertTrue("category rows must use the mobile control-sheet selectors",
                usesControlSheetSelectors(category));
        assertTrue("filter rows must use the same mobile control-sheet selectors",
                usesControlSheetSelectors(filter));
        assertTrue("filter rows must preserve a stable 34dp touch target",
                filter.contains("android:layout_height=\"34dp\""));
    }

    private static boolean usesSharedSelectors(String layout) {
        return layout.contains("android:background=\"@drawable/selector_dialog_glass_chip\"")
                && layout.contains("android:textColor=\"@color/selector_dialog_glass_chip_text\"");
    }

    private static boolean usesControlSheetSelectors(String layout) {
        return layout.contains("android:background=\"@drawable/selector_control_sheet_button\"")
                && layout.contains("android:textColor=\"@color/selector_control_sheet_text\"");
    }

    private static int occurrences(String source, String value) {
        int count = 0;
        int index = 0;
        while ((index = source.indexOf(value, index)) >= 0) {
            count++;
            index += value.length();
        }
        return count;
    }

    private static String readMainResource(String type, String file) throws Exception {
        return read(findAppPath().resolve(Path.of("src", "main", "res", type, file)));
    }

    private static String readLeanbackResource(String type, String file) throws Exception {
        return read(findAppPath().resolve(Path.of("src", "leanback", "res", type, file)));
    }

    private static String readMobileResource(String type, String file) throws Exception {
        return read(findAppPath().resolve(Path.of("src", "mobile", "res", type, file)));
    }

    private static Path findAppPath() {
        return Files.exists(Path.of("src", "main")) ? Path.of(".") : Path.of("app");
    }

    private static String read(Path path) throws Exception {
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }
}
