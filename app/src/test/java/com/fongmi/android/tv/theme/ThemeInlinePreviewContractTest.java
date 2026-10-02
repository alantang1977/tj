package com.fongmi.android.tv.theme;

import org.junit.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.Assert.*;

/** Source-level boundaries complement the model tests and real view/device tests. */
public class ThemeInlinePreviewContractTest {

    @Test
    public void bothFlavoursOwnALocalSnapshotAndPutPresetsFirst() throws Exception {
        String mobile = read("mobile/java/com/fongmi/android/tv/ui/dialog/ThemeDialog.java");
        String tv = read("leanback/java/com/fongmi/android/tv/ui/dialog/ThemeDialog.java");
        assertEquals("the two flavours must not drift", mobile, tv);
        for (String source : new String[]{mobile, tv}) {
            assertTrue(source.contains("editor.preview(dark, wallpaperColor)"));
            assertTrue(source.contains("root.setTag(\"webhtv:ignore\")"));
            assertTrue(source.indexOf("content.addView(buildPresetRow()") < source.indexOf("content.addView(buildPaletteRow()"));
            assertFalse(source.contains("ThemeController.current()"));
            assertFalse(source.contains("ThemeController.apply("));
            assertFalse(source.contains("setDefaultNightMode("));
            assertFalse(source.contains("removeAllViews()"));
            assertTrue(source.contains("panel.render(editor, dark, tokens)"));
            assertTrue(source.contains("preview_draft"));
            assertTrue(source.contains("preview_dark"));
            assertTrue(source.contains("preview_scroll"));
            assertTrue(source.contains("previewTokens, hex ->"));
        }
    }

    @Test
    public void resetAndSelectionDoNotPublishAndSavingDoesNotDismissOnFailure() throws Exception {
        String editor = read("main/java/com/fongmi/android/tv/theme/ThemeEditor.java");
        assertTrue(editor.contains("return replace(ThemeProfile.defaultProfile())"));
        assertFalse(editor.contains("ThemeProfileStore.reset()"));
        String dialog = read("mobile/java/com/fongmi/android/tv/ui/dialog/ThemeDialog.java");
        assertTrue(dialog.contains("resetButton.setOnClickListener(view -> { editor.reset(); render(); })"));
        assertFalse(dialog.contains(".setPositiveButton("));
        int apply = dialog.indexOf("private void applyDraft()");
        int failed = dialog.indexOf("if (!result.success())", apply);
        int returnOnFailure = dialog.indexOf("return;", failed);
        int dismiss = dialog.indexOf("dismissAllowingStateLoss();", apply);
        assertTrue(apply >= 0 && failed > apply && returnOnFailure < dismiss);
        assertTrue(dialog.contains("else RefreshEvent.theme();"));
    }

    @Test
    public void realColorRowsReplaceTheBottomSampleAndShowResolvedValues() throws Exception {
        String source = read("main/java/com/fongmi/android/tv/theme/ThemePreviewView.java");
        assertFalse(source.contains("theme_editor_preview_title"));
        assertFalse(source.contains("theme_editor_preview_filled"));
        assertFalse(source.contains("theme_editor_preview_tonal"));
        assertFalse(source.contains("theme_editor_inherit"));
        assertTrue(source.contains("theme_editor_value_auto"));
        assertTrue(source.contains("theme_editor_value_adjusted"));
        assertFalse(source.contains("ThemeController.current()"));
        assertFalse(source.contains("removeAllViews()"));
        assertTrue(source.contains("if (!fromUser || binding) return;"));
        assertTrue(source.contains("screenWidthDp >= 700"));
        assertTrue(source.contains("tokens.colorSuccess()"));
        assertTrue(source.contains("tokens.colorWarning()"));
    }

    @Test
    public void localInteractiveControlsKeepExplicitFocusAndReadableText() throws Exception {
        String source = read("main/java/com/fongmi/android/tv/theme/ThemeEditorUi.java");
        assertTrue(source.contains("android.R.attr.state_focused"));
        assertTrue(source.contains("ThemeContrast.ratio"));
        assertTrue(source.contains("dp(context, 48)"));
        assertFalse(source.contains("ThemeController"));
    }

    private static String read(String path) throws Exception {
        Path root = Files.isDirectory(Path.of("src")) ? Path.of("src") : Path.of("app/src");
        return Files.readString(root.resolve(path));
    }
}
