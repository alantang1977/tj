package com.fongmi.android.tv.ui.dialog;

import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;

/**
 * Window sizing for the theme colour editor.
 *
 * <p>The editor previously inherited Material's default alert width, so the 13 colour
 * slots, the 3 opacity sliders and the live preview were squeezed into a narrow column
 * and the dialog covered only about 58% x 70% of a 1920x1080 screen - measured on
 * device at [405,160][1515,920]. It now follows the same contract as the ad-block
 * statistics dialog: fill the screen minus a constant safety margin.
 *
 * <p>The margin is a fixed dp value rather than a screen percentage. A percentage
 * silently changes the usable area with the panel resolution, while the editor's rows
 * have a fixed dp height and the preview needs a predictable amount of room; a fixed
 * margin keeps the same physical gutter on every device. It also keeps the dialog from
 * ever reaching the very edge of an overscanning TV panel.
 */
final class ThemeDialogLayout {

    /** Matches the ad-block statistics dialog's mobile gutter. */
    static final int MOBILE_MARGIN_DP = 16;

    /** Matches the ad-block statistics dialog's television gutter. */
    static final int LEANBACK_MARGIN_DP = 24;

    private ThemeDialogLayout() {
    }

    /** Screen edge gutter in dp for the running flavour. */
    static int marginDp(boolean leanback) {
        return leanback ? LEANBACK_MARGIN_DP : MOBILE_MARGIN_DP;
    }

    /** Window width that keeps {@code margin} on both sides, never below one pixel. */
    static int width(int screenWidth, int margin) {
        return Math.max(1, Math.max(1, screenWidth) - Math.max(0, margin) * 2);
    }

    /** Window height that keeps {@code margin} above and below, never below one pixel. */
    static int height(int screenHeight, int margin) {
        return Math.max(1, Math.max(1, screenHeight) - Math.max(0, margin) * 2);
    }

    /**
     * The panel drawable the editor must keep as its window background.
     *
     * <p>{@code WebHtvAlertDialogBuilder} paints this editor's panel through the window
     * background rather than through a view: the title row, the colour slots, the weighted
     * scroll area and the action buttons carry no background of their own. Material wraps
     * that panel in an {@link InsetDrawable} gutter, which is what kept the panel narrower
     * than the window, so the wrapper is dropped now that the window carries the margin
     * itself.
     *
     * <p>The panel itself has to be kept. Replacing the window background with a transparent
     * fill is only safe for a dialog whose layout supplies its own card - the ad-block
     * statistics dialog does - while here it erased the panel and left the settings page
     * visible through the whole editor.
     *
     * @return the inset-free panel, or {@code null} when the window carries no background.
     */
    static Drawable panelBackground(Drawable windowBackground) {
        Drawable panel = windowBackground;
        while (panel instanceof InsetDrawable inset) {
            panel = inset.getDrawable();
        }
        return panel;
    }
}
