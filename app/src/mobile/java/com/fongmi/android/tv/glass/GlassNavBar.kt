package com.fongmi.android.tv.glass

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.ViewCompositionStrategy
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.fongmi.android.tv.setting.Setting
import com.kyant.backdrop.backdrops.rememberCanvasBackdrop

/**
 * Liquid-glass bottom navigation bar for the mobile home screen.
 *
 * The bar itself is FloatingNavBar, ported from AVBox (XiaochangXu/AVBox) and
 * adapted to this app: it renders with Kyant's backdrop library
 * (io.github.kyant0:backdrop). The app's content area is a classic Android
 * View hierarchy rather than Compose, so the backdrop source is a live
 * capture of the content's bottom strip, fed into a CanvasBackdrop each frame.
 */
class GlassNavItem(
    val id: Int,
    val iconRes: Int,
    val label: String,
    val liveItem: Boolean
)

class GlassNavState {

    interface Listener {
        fun onSelect(id: Int)
        fun onLiveLongPress()
    }

    var listener: Listener? = null

    var items: List<GlassNavItem> by mutableStateOf(emptyList())
    var selectedId: Int by mutableIntStateOf(0)
    var followingId: Int by mutableIntStateOf(-1)
    var followingBadge: Int by mutableIntStateOf(0)
    var darkMode: Boolean by mutableStateOf(true)
    var accentColor: Int by mutableIntStateOf(0xFFBB86FC.toInt())

    // Liquid glass effect parameters, synced from Setting by HomeActivity.
    var glassBlurDp: Float by mutableStateOf(5f)
    var glassDistortionDp: Float by mutableStateOf(30f)
    var glassTranslucency: Float by mutableStateOf(0.5f)
    var glassDispersion: Boolean by mutableStateOf(true)

    // Draw-phase state: read only inside the backdrop draw lambda so per-frame
    // captures invalidate drawing without triggering recomposition.
    var stripImage: ImageBitmap? by mutableStateOf(null)
    var stripOffset: IntOffset by mutableStateOf(IntOffset.Zero)
    var fallbackColor: Color by mutableStateOf(Color(0xFF121212))
}

/** Java-friendly entry points used by HomeActivity. */
object GlassNav {

    @JvmStatic
    fun createState(): GlassNavState = GlassNavState()

    @JvmStatic
    fun bind(view: ComposeView, state: GlassNavState) {
        view.setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed)
        view.setContent { GlassNavBarContent(state) }
    }

    @JvmStatic
    fun createCapture(source: ViewGroup, anchor: View, state: GlassNavState): GlassBackdropCapture {
        return GlassBackdropCapture(source, anchor, state)
    }
}

/**
 * Captures the bottom strip of [source] (the home root layout) before each draw
 * and publishes it as the backdrop image for the glass bar.
 *
 * The captured strip covers the glass slot plus an extra margin above it, so the
 * blur/lens effects have real content to sample at the bar's top edge.
 */
class GlassBackdropCapture(
    private val source: ViewGroup,
    private val anchor: View,
    private val state: GlassNavState
) {
    private var bitmap: Bitmap? = null
    private var canvas: Canvas? = null

    private val listener = ViewTreeObserver.OnPreDrawListener {
        capture()
        true
    }

    fun start() {
        source.viewTreeObserver.addOnPreDrawListener(listener)
    }

    fun stop() {
        if (source.viewTreeObserver.isAlive) {
            source.viewTreeObserver.removeOnPreDrawListener(listener)
        }
        bitmap = null
        canvas = null
    }

    private fun capture() {
        if (anchor.visibility != View.VISIBLE) return
        val width = source.width
        val sourceHeight = source.height
        if (width <= 0 || sourceHeight <= 0) return
        val stripHeight = minOf(sourceHeight, anchor.height + EXTRA_ABOVE_PX)
        if (stripHeight <= 0) return
        var bmp = bitmap
        if (bmp == null || bmp.width != width || bmp.height != stripHeight) {
            bmp = Bitmap.createBitmap(width, stripHeight, Bitmap.Config.ARGB_8888)
            bitmap = bmp
            canvas = Canvas(bmp)
        }
        val c = canvas ?: return
        try {
            bmp.eraseColor(android.graphics.Color.TRANSPARENT)
            c.save()
            c.translate(0f, -(sourceHeight - stripHeight).toFloat())
            // Draw every visible child except the glass bar itself (the anchor):
            // sampling the bar would feed the glass back into its own backdrop.
            source.background?.draw(c)
            for (i in 0 until source.childCount) {
                val child = source.getChildAt(i)
                if (child === anchor || child.visibility != View.VISIBLE) continue
                c.save()
                c.translate(child.left.toFloat(), child.top.toFloat())
                child.draw(c)
                c.restore()
            }
            c.restore()
        } catch (e: Exception) {
            return
        }
        val sourceLoc = IntArray(2)
        val anchorLoc = IntArray(2)
        source.getLocationInWindow(sourceLoc)
        anchor.getLocationInWindow(anchorLoc)
        // Strip origin in window: (sourceLoc.x, sourceLoc.y + sourceHeight - stripHeight).
        // The bar element spans the whole ComposeView, whose window origin is anchorLoc.
        state.stripOffset = IntOffset(
            sourceLoc[0] - anchorLoc[0],
            sourceLoc[1] + sourceHeight - stripHeight - anchorLoc[1]
        )
        state.stripImage = bmp.asImageBitmap()
    }

    companion object {
        private const val EXTRA_ABOVE_PX = 160
    }
}

// Geometry of the floating bar inside the 88dp glass slot (see activity_home.xml):
// 16dp side insets, 10dp above the slot's bottom edge, 64dp tall, so its top edge
// sits 14dp below the slot's top edge.
private val BarInsetX = 16.dp
private val BarTopInSlot = 14.dp

@Composable
fun GlassNavBarContent(state: GlassNavState) {
    // The backdrop is drawn in the bar element's own coordinate space, so the
    // captured strip (published relative to the whole slot) is shifted by the
    // bar's inset within the slot.
    val backdrop = rememberCanvasBackdrop {
        val image = state.stripImage
        if (image != null) {
            drawImage(
                image,
                dstOffset = IntOffset(
                    state.stripOffset.x - BarInsetX.toPx().toInt(),
                    state.stripOffset.y - BarTopInSlot.toPx().toInt()
                )
            )
        } else {
            drawRect(state.fallbackColor)
        }
    }

    val tabs = state.items.map { item ->
        GlassTabItem(
            iconRes = item.iconRes,
            label = item.label,
            badge = if (item.id == state.followingId) state.followingBadge else 0,
            liveItem = item.liveItem
        )
    }
    // Effect parameters come from the user's settings (synced into the state
    // by HomeActivity); defaults match AVBox's LiquidGlassState. The bar only
    // exists when the liquid glass toggle is on, so navbarEnabled is true.
    // controlsEnabled follows the liquid-glass switch: it gates the
    // tab controls' own glass treatment inside the bar.
    val config = LiquidGlassConfig(
        navbarEnabled = true,
        controlsEnabled = Setting.isLiquidGlass(),
        blurDp = state.glassBlurDp,
        distortionDp = state.glassDistortionDp,
        translucency = state.glassTranslucency,
        dispersion = state.glassDispersion
    )
    val selectedTabIndex = remember(state) {
        { state.items.indexOfFirst { it.id == state.selectedId }.coerceAtLeast(0) }
    }
    val accent = Color(state.accentColor)
    val surface = if (state.darkMode) Color(0xFF1E1E20) else Color(0xFFF4F4F6)
    val unselected = if (state.darkMode) Color.White.copy(alpha = 0.72f) else Color.Black.copy(alpha = 0.62f)

    Box(Modifier.fillMaxSize()) {
        FloatingNavBar(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(horizontal = BarInsetX)
                .padding(bottom = 10.dp)
                .fillMaxWidth(),
            backdrop = backdrop,
            axis = NavAxis.Horizontal,
            selectedTabIndex = selectedTabIndex,
            onTabSelected = { index ->
                state.items.getOrNull(index)?.let { state.listener?.onSelect(it.id) }
            },
            onReselected = { index ->
                state.items.getOrNull(index)?.let { state.listener?.onSelect(it.id) }
            },
            onTabLongPress = { index ->
                if (state.items.getOrNull(index)?.liveItem == true) state.listener?.onLiveLongPress()
            },
            tabs = tabs,
            config = config,
            accentColor = accent,
            surfaceColor = surface,
            selectedContentColor = accent,
            unselectedContentColor = unselected,
            isLightTheme = !state.darkMode
        )
    }
}
