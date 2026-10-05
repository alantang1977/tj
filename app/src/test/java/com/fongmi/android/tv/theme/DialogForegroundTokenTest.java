package com.fongmi.android.tv.theme;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Java-built dialogs must not pin their foreground to a fixed colour.
 *
 * <p>The dialogs below draw onto {@code shape_shell_proxy_dialog}, whose fill is
 * {@code ?attr/colorSurfaceContainerHigh} - light in the day table
 * ({@code #E7E8EF}) and dark in the night table ({@code #2A2F34}). A hard-coded
 * foreground can therefore only be right in one of the two modes.
 *
 * <p>This is the Java-side twin of the layout guard in
 * {@link ThemeBaseWiringTest#darkGlassSheetsUseAConstantLightForeground}. Layouts pin
 * their colour in XML and can be checked by reading the file; these dialogs build their
 * views in code and assign the colour at runtime, so the check is on the assignment
 * source instead. The two guards cover the two ways a fixed colour gets in.
 *
 * <p>Measured on the day/night panel pair, the pinned literals these classes used were:
 * {@code #5F6368} 4.95:1 day but 2.23:1 night, {@code #202124} 13.18:1 day but 1.19:1
 * night. The semantic replacements resolve to 5.23:1 or better in <em>both</em> tables.
 */
public class DialogForegroundTokenTest {

    /** Java-built dialogs that paint onto the palette-following dialog panel. */
    private static final String[] DIALOG_SOURCES = {
            "DebugLogDialog.java",
            "MpvConfigDialog.java",
            "PlaybackPerformanceDialog.java",
    };

    /**
     * Fixed foregrounds that must not appear: the legacy Material greys and blues these
     * dialogs used to pin, plus the plain white/black literals that would equally break
     * the other mode.
     */
    private static final String[] FORBIDDEN_LITERALS = {
            "#5F6368", "#202124", "#3C4043", "#174EA6", "#1A73E8",
            "#8AB4F8", "#E8F0FE", "#C4C7C5", "#C5221F",
    };

    @Test
    public void javaBuiltDialogsDoNotPinAFixedForeground() throws Exception {
        for (String name : DIALOG_SOURCES) {
            String source = stripComments(read("src/main/java/com/fongmi/android/tv/ui/dialog/" + name));
            for (String literal : FORBIDDEN_LITERALS) {
                assertFalse(name + " pins the fixed foreground " + literal
                                + ", which cannot be legible in both the day and night palettes",
                        source.contains("\"" + literal + "\""));
            }
            assertFalse(name + " must not pin a foreground through Color.parseColor",
                    source.contains("Color.parseColor(\"#"));
        }
    }

    /**
     * The dialogs must take their foreground from the active semantic snapshot.
     *
     * <p>{@code Color.TRANSPARENT} is deliberately still allowed: it is not a foreground
     * and carries no palette assumption (window backgrounds, tab ripples).
     */
    @Test
    public void javaBuiltDialogsReadTheActiveTokens() throws Exception {
        for (String name : DIALOG_SOURCES) {
            String source = stripComments(read("src/main/java/com/fongmi/android/tv/ui/dialog/" + name));
            assertTrue(name + " must resolve its foreground from ThemeController.current()",
                    source.contains("ThemeController.current()"));
            assertTrue(name + " must import ThemeController",
                    source.contains("import com.fongmi.android.tv.theme.ThemeController;"));
        }
    }

    /**
     * The MPV action popup must keep its fill and its foreground in the same palette.
     *
     * <p>{@code MpvConfigDialog.actionItem} now paints its label with
     * {@code colorOnSurface} / {@code colorError}. The popup background it sits on was a
     * fixed white shape, so it had to migrate in the same change - otherwise night mode
     * would render a near-black label on a still-white popup. Both halves are pinned so a
     * later edit cannot move one without the other.
     */
    @Test
    public void mpvActionPopupFollowsTheSamePaletteAsItsForeground() throws Exception {
        String popup = stripComments(read("src/main/res/drawable/shape_mpv_action_menu.xml"));
        assertTrue("the popup fill must follow the palette",
                popup.contains("?attr/colorSurfaceContainerLowest"));
        assertTrue("the popup stroke must follow the palette",
                popup.contains("?attr/colorOutlineVariant"));
        assertFalse("the popup must not keep a fixed fill", popup.contains("#FFFFFF"));
        assertFalse("the popup must not keep a fixed stroke", popup.contains("#E1E5EA"));
    }

    private static String stripComments(String source) {
        String withoutXml = source.replaceAll("(?s)<!--.*?-->", "");
        return withoutXml
                .replaceAll("(?s)/\\*.*?\\*/", "")
                .replaceAll("(?m)//.*$", "");
    }

    private static String read(String path) throws Exception {
        Path root = Files.exists(Path.of("src")) ? Path.of("") : Path.of("app");
        return Files.readString(root.resolve(path), StandardCharsets.UTF_8);
    }
}
