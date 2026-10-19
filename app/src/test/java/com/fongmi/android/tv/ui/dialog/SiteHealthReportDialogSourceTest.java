package com.fongmi.android.tv.ui.dialog;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.file.Files;
import java.nio.file.Path;

/** Keeps the ad-rule ranking user-facing by resolving stored rule IDs to display names. */
public class SiteHealthReportDialogSourceTest {

    @Test
    public void ruleRankingUsesResolvedDisplayNames() throws Exception {
        String source = Files.readString(Path.of(
                "src/main/java/com/fongmi/android/tv/ui/dialog/SiteHealthReportDialog.java"));

        assertTrue(source.contains("ruleDimensionSummary(report.adBlockedByRule)"));
        assertTrue(source.contains("AdBlockStatsStore.getRuleDisplayName(entry.getKey())"));
        assertFalse(source.contains("dimensionSummary(report.adBlockedByRule)"));
    }

    /**
     * The report body is built in code, so it cannot inherit a theme attribute the way the dialog
     * XML does. A hard-coded translucent black looked fine on the light panel but made every
     * generated row unreadable on the dark one (the XML title, which uses {@code ?attr/colorOnSurface},
     * stayed legible) - so generated text must use resolved semantic roles instead.
     */
    @Test
    public void generatedRowsUseResolvedThemeRolesInsteadOfFixedBlack() throws Exception {
        String source = Files.readString(Path.of(
                "src/main/java/com/fongmi/android/tv/ui/dialog/SiteHealthReportDialog.java"));

        assertFalse("generated report text must not use a fixed translucent black",
                source.contains("R.color.black"));
        assertTrue("generated text must resolve its colour from the active theme",
                source.contains("ThemeController.current().colorOnSurface"));
        // Status accents are tuned for a light panel; on a dark panel they must be
        // contrast-corrected against the actual panel fill rather than used raw.
        // Match the call site, not the declaration: "readableOnPanel(" also occurs in
        // the method signature, so that spelling stayed true after the call was removed.
        assertTrue("status accents must be contrast-corrected against the panel",
                source.contains("readableOnPanel(color)"));
        assertTrue(source.contains("ThemeController.current().colorSurfaceContainerHigh()"));
    }
}
