package io.github.anilbeesetti.nextlib.media3ext.ffdecoder;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public class CompatFfmpegVideoRendererSourceTest {

    private static final String SOURCE_PATH = "app/src/main/java/io/github/anilbeesetti/nextlib/media3ext/ffdecoder/CompatFfmpegVideoRenderer.java";
    private static final String EXO_UTIL_PATH = "app/src/main/java/com/fongmi/android/tv/player/exo/ExoUtil.java";

    /**
     * The audio renderer may ask whether the platform supports the exact {@link
     * androidx.media3.common.Format}, but the video renderer must not: a 4K HEVC track that exceeds
     * the decoder's level reports unsupported, which would hand the track back to FFmpeg software
     * decoding and reintroduce the dropped-frame regression.
     */
    @Test
    public void platformOwnershipCheck_asksOnlyAboutMimeTypeNotExactFormat() throws Exception {
        String source = readSource();

        assertTrue(source.contains("getDecoderInfos(mimeType, false, false)"));
        assertFalse(source.contains("isFormatSupported("));
    }

    /**
     * The check must run through the selector the MediaCodec renderers were built with. Hardcoding
     * {@code MediaCodecSelector.DEFAULT} would make FFmpeg yield to a software platform decoder that
     * ExoUtil's hardware-only selector has already filtered out, leaving the track with no renderer
     * at all: a silent black screen with no PlaybackException to trigger any fallback.
     */
    @Test
    public void platformOwnershipCheck_usesTheInjectedSelectorNotTheDefaultOne() throws Exception {
        String source = readSource();

        assertTrue(source.contains("platformDecoderSelector == null ? MediaCodecSelector.DEFAULT : platformDecoderSelector"));
        assertTrue(source.contains("!selector.getDecoderInfos(mimeType, false, false).isEmpty()"));
    }

    /**
     * 硬解的优先级仍然是「系统 MediaCodec 先接管」，但 FFmpeg 必须保留为最后一级视频渲染器：
     * 平台根本没有该编码解码器时（AVS2/AVS3、部分 HEVC profile），旧行为会把整条视频轨判成
     * 不支持的子类型丢弃、只留声音。FFmpeg 只有在平台没有对应 mime 解码器时才接手，这一点由
     * 上面两个 ownership 断言锁定，所以保留注册不会让 4K HEVC 回退到软解。
     */
    @Test
    public void hardwareModeKeepsFfmpegAsTheLastVideoRenderer() throws Exception {
        String exoUtil = readSource(EXO_UTIL_PATH);
        int start = exoUtil.indexOf("private static int getVideoRenderMode(int decode)");
        assertTrue("getVideoRenderMode must exist", start >= 0);
        int end = exoUtil.indexOf("\n    }", start);
        String mode = exoUtil.substring(start, end > start ? end : exoUtil.length());

        // 兜底开启：硬解 = ON（MediaCodec 先接管、FFmpeg 排最后）；兜底关闭：仍为 OFF。
        assertTrue(mode, mode.contains("isDecoderFallbackEnabled()"));
        assertTrue(mode, mode.contains("EXTENSION_RENDERER_MODE_ON"));
        assertTrue(mode, mode.contains("EXTENSION_RENDERER_MODE_OFF"));
        assertTrue(exoUtil.contains("if (videoRenderMode == EXTENSION_RENDERER_MODE_OFF) return;"));
        assertTrue(exoUtil.contains("buildFfmpegVideoRenderer("));
        assertFalse(exoUtil.contains("new CompatFfmpegVideoRenderer("));
    }

    private static String readSource() throws Exception {
        return readSource(SOURCE_PATH);
    }

    private static String readSource(String relativePath) throws Exception {
        File root = new File(System.getProperty("user.dir"));
        while (root != null && !new File(root, relativePath).isFile()) root = root.getParentFile();
        assertNotNull("Unable to locate project root from " + System.getProperty("user.dir"), root);
        return Files.readString(new File(root, relativePath).toPath(), StandardCharsets.UTF_8);
    }
}
