// Ported from AVBox (github.com/XiaochangXu/AVBox), AGPL-3.0, adapted for Mooyingshi.
package com.fongmi.android.tv.glass

const val GLASS_BACKDROP_BAND_MARGIN_DP = 64

data class LiquidGlassConfig(
    val navbarEnabled: Boolean,
    val controlsEnabled: Boolean,
    val blurDp: Float,
    val distortionDp: Float,
    val translucency: Float,
    val dispersion: Boolean,
) {
    val containerAlphaScale: Float get() = 2f - translucency * 2f

    val contentBrightness: Float get() = (0.5f - translucency).coerceAtLeast(0f) * 0.12f

    val contentContrast: Float get() = 1f - (0.5f - translucency).coerceAtLeast(0f) * 0.25f

    val contentSaturation: Float get() = 1.5f - (translucency - 0.5f).coerceAtLeast(0f)
}
