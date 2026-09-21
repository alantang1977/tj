package com.fongmi.android.tv.ui.dialog;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public class ConfigHistoryCurrentSourceGuardTest {

    private static final String MOBILE = "src/mobile/java/com/fongmi/android/tv/ui/adapter/ConfigAdapter.java";
    private static final String LEANBACK = "src/leanback/java/com/fongmi/android/tv/ui/adapter/ConfigAdapter.java";

    @Test
    public void editableHistoryAlwaysHidesCurrentConfig() throws Exception {
        assertCurrentConfigHidden(MOBILE);
        assertCurrentConfigHidden(LEANBACK);
    }

    @Test
    public void deletingAConfigRequiresConfirmation() throws Exception {
        assertDeleteConfirmation("src/mobile/java/com/fongmi/android/tv/ui/dialog/HistoryDialog.java");
        assertDeleteConfirmation("src/leanback/java/com/fongmi/android/tv/ui/dialog/HistoryDialog.java");
    }

    private static void assertCurrentConfigHidden(String file) throws Exception {
        String source = Files.readString(Path.of(file), StandardCharsets.UTF_8);
        assertTrue(source.contains("if (!readOnly && !TextUtils.isEmpty(currentUrl))"));
        assertTrue(source.contains("mItems.removeIf(item -> TextUtils.equals(item.getUrl(), currentUrl));"));
        assertFalse(source.contains("if (type != 0 && !readOnly && !TextUtils.isEmpty(currentUrl))"));
    }

    private static void assertDeleteConfirmation(String file) throws Exception {
        String source = Files.readString(Path.of(file), StandardCharsets.UTF_8);
        assertTrue(source.contains(".setTitle(R.string.config_delete_title)"));
        assertTrue(source.contains(".setMessage(getString(R.string.config_delete_message, item.getDesc()))"));
        assertFalse(source.contains(".setMessage(getString(R.string.config_delete_message, item.getName()))"));
        assertTrue(source.contains(".setNegativeButton(R.string.dialog_negative, null)"));
        assertTrue(source.contains(".setPositiveButton(R.string.dialog_positive"));
        if (file.contains("leanback")) {
            assertTrue(source.contains("dialog.setOnShowListener"));
            assertTrue(source.contains("BUTTON_NEGATIVE).requestFocus()"));
        }
    }
}
