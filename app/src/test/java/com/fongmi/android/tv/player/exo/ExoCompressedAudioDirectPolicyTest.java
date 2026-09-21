package com.fongmi.android.tv.player.exo;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.Format;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.util.Clock;
import androidx.media3.common.util.StuckPlayerException;
import androidx.media3.common.util.Util;
import androidx.media3.exoplayer.audio.AudioOffloadSupport;
import androidx.media3.exoplayer.audio.AudioOutput;
import androidx.media3.exoplayer.audio.AudioOutputProvider;

import org.junit.Test;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;

public class ExoCompressedAudioDirectPolicyTest {

    @Test
    public void standardOffload_isPreservedWithoutDirectProbe() {
        AtomicInteger directQueries = new AtomicInteger();
        AudioOffloadSupport standard = supported(true, true);
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> standard,
                (format, attributes) -> {
                    directQueries.incrementAndGet();
                    return true;
                });

        AudioOffloadSupport actual = policy.getAudioOffloadSupport(
                aacStereo(), AudioAttributes.DEFAULT);

        assertSame(standard, actual);
        assertTrue(actual.isFormatSupported);
        assertTrue(actual.isGaplessSupported);
        assertTrue(actual.isSpeedChangeSupported);
        assertTrue(directQueries.get() == 0);
    }

    @Test
    public void directBitstream_enablesEncodedBypassWithoutFakeOffload() {
        Format format = aacStereo();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> true);

        AudioOutputProvider.FormatSupport actual = wrapped(policy)
                .getFormatSupport(formatConfig(format));

        assertTrue(actual.supportLevel
                == AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY);
        assertFalse(actual.isFormatSupportedForOffload);
        assertTrue(policy.usesVendorDirect(C.ENCODING_AAC_LC, 48_000,
                Util.getAudioTrackChannelConfig(format)));
    }

    @Test
    public void passthroughWithoutOffload_isOverriddenByVendorDirect() {
        Format format = aacStereo();
        AudioOutputProvider.FormatSupport passthrough =
                new AudioOutputProvider.FormatSupport.Builder()
                        .setFormatSupportLevel(
                                AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY)
                        .setIsFormatSupportedForOffload(false)
                        .build();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> true);

        AudioOutputProvider.FormatSupport actual = policy.wrapOutputProvider(
                new FixedFormatSupportAudioOutputProvider(passthrough))
                .getFormatSupport(formatConfig(format));

        assertTrue(actual.supportLevel
                == AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY);
        assertFalse(actual.isFormatSupportedForOffload);
        assertTrue(policy.usesVendorDirect(C.ENCODING_AAC_LC, 48_000,
                Util.getAudioTrackChannelConfig(format)));
    }

    @Test
    public void directBitstream_buildsNonOffloadEncodedOutput() throws Exception {
        Format format = aacStereo();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> true);
        AudioOutputProvider provider = wrapped(policy);
        AudioOutputProvider.FormatConfig config = formatConfig(format);
        provider.getFormatSupport(config);

        AudioOutputProvider.OutputConfig output = provider.getOutputConfig(config);

        assertTrue(output.encoding == C.ENCODING_AAC_LC);
        assertTrue(output.sampleRate == 48_000);
        assertTrue(output.channelMask == Util.getAudioTrackChannelConfig(format));
        assertTrue(output.bufferSize == 256 * 1024);
        assertFalse(output.isOffload);
        assertFalse(output.isTunneling);
        assertTrue(output.audioSessionId == 0);
        assertTrue(output.virtualDeviceId == C.INDEX_UNSET);
    }

    @Test
    public void tunneling_doesNotAdvertiseVendorOnlyBypass() {
        AtomicInteger queries = new AtomicInteger();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (format, attributes) -> { queries.incrementAndGet(); return true; });

        assertSame(AudioOutputProvider.FormatSupport.UNSUPPORTED,
                wrapped(policy).getFormatSupport(tunnelingConfig()));
        assertEquals(0, queries.get());
        assertFalse(policy.usesVendorDirect(C.ENCODING_AAC_LC, 48_000,
                Util.getAudioTrackChannelConfig(aacStereo())));
    }

    @Test
    public void tunneling_afterCachedDirectProbe_preservesStandardConfiguration() throws Exception {
        Format format = aacStereo();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> true);
        wrapped(policy).getFormatSupport(formatConfig(format));
        AudioOutputProvider.OutputConfig standard = encodedOutput(true, false);
        StandardAudioOutputProvider delegate = new StandardAudioOutputProvider(standard);
        AudioOutputProvider provider = policy.wrapOutputProvider(delegate);

        // Even without a new capability query, the final request must not use the stale direct key.
        assertSame(standard, provider.getOutputConfig(tunnelingConfig()));
        assertTrue(standard.isTunneling);
        assertEquals(1234, standard.audioSessionId);
        assertSame(delegate.support, provider.getFormatSupport(tunnelingConfig()));
    }

    @Test
    public void finalStandardMode_ignoresDirectCacheAndPublishesItsActualOutput() throws Exception {
        for (boolean offload : new boolean[]{false, true}) {
            ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                    (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                    (format, attributes) -> true);
            wrapped(policy).getFormatSupport(formatConfig(aacStereo()));
            AudioOutputProvider.OutputConfig standard = encodedOutput(!offload, offload);
            StandardAudioOutputProvider delegate = new StandardAudioOutputProvider(standard);
            AudioOutput output = policy.wrapOutputProvider(delegate).getAudioOutput(standard);

            assertEquals(1, delegate.creations);
            assertEquals(!offload, policy.getAudioOutputSnapshot().tunneling());
            assertEquals(offload, policy.getAudioOutputSnapshot().offload());
            // A standard mode must not apply any vendor builder overrides, even with a cached key.
            policy.modifyAudioTrackBuilder(null, standard);
            output.release();
            assertFalse(policy.getAudioOutputSnapshot().initialized());
        }
    }

    @Test
    public void failedInitialization_doesNotPublishOutputState() {
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (format, attributes) -> false);
        assertThrows(AudioOutputProvider.InitializationException.class,
                () -> wrapped(policy).getAudioOutput(encodedOutput(false, false)));
        assertFalse(policy.getAudioOutputSnapshot().initialized());
    }

    @Test
    public void missingDirectSupport_keepsPcmFallback() {
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (format, attributes) -> false);

        AudioOutputProvider.FormatSupport actual = wrapped(policy)
                .getFormatSupport(formatConfig(aacStereo()));

        assertTrue(actual.supportLevel
                == AudioOutputProvider.FORMAT_UNSUPPORTED);
    }

    @Test
    public void failedDirectConfig_isNotRetriedInSamePlayerSession() {
        AtomicInteger directQueries = new AtomicInteger();
        Format format = aacStereo();
        int channelMask = Util.getAudioTrackChannelConfig(format);
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> {
                    directQueries.incrementAndGet();
                    return true;
                });
        assertTrue(wrapped(policy).getFormatSupport(formatConfig(format))
                .supportLevel == AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY);

        policy.disableVendorDirect(C.ENCODING_AAC_LC, 48_000, channelMask);
        AudioOutputProvider.FormatSupport fallback = wrapped(policy)
                .getFormatSupport(formatConfig(format));

        assertTrue(fallback.supportLevel
                == AudioOutputProvider.FORMAT_UNSUPPORTED);
        assertFalse(policy.usesVendorDirect(
                C.ENCODING_AAC_LC, 48_000, channelMask));
        assertTrue(directQueries.get() == 1);
    }

    @Test
    public void failedDirectConfig_masksDelegatePassthroughForPcmFallback() {
        Format format = aacStereo();
        int channelMask = Util.getAudioTrackChannelConfig(format);
        AudioOutputProvider.FormatSupport passthrough =
                new AudioOutputProvider.FormatSupport.Builder()
                        .setFormatSupportLevel(
                                AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY)
                        .setIsFormatSupportedForOffload(false)
                        .build();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (ignoredFormat, ignoredAttributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (ignoredFormat, ignoredAttributes) -> true);
        AudioOutputProvider provider = policy.wrapOutputProvider(
                new FixedFormatSupportAudioOutputProvider(passthrough));
        assertTrue(provider.getFormatSupport(formatConfig(format)).supportLevel
                == AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY);

        policy.disableVendorDirect(C.ENCODING_AAC_LC, 48_000, channelMask);

        AudioOutputProvider.FormatSupport fallback =
                provider.getFormatSupport(formatConfig(format));
        assertTrue(fallback.supportLevel == AudioOutputProvider.FORMAT_UNSUPPORTED);
        assertTrue(policy.consumePcmFallbackRequest());
        assertFalse(policy.consumePcmFallbackRequest());
    }

    @Test
    public void unsupportedEncodedFrameType_doesNotProbeDirectPlayback() {
        AtomicInteger directQueries = new AtomicInteger();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (format, attributes) -> {
                    directQueries.incrementAndGet();
                    return true;
                });
        Format flac = new Format.Builder()
                .setSampleMimeType(MimeTypes.AUDIO_FLAC)
                .setSampleRate(48_000)
                .setChannelCount(2)
                .build();

        AudioOutputProvider.FormatSupport actual = wrapped(policy)
                .getFormatSupport(formatConfig(flac));

        assertTrue(actual.supportLevel
                == AudioOutputProvider.FORMAT_UNSUPPORTED);
        assertTrue(directQueries.get() == 0);
    }

    @Test
    public void incompleteFormat_doesNotProbeDirectPlayback() {
        AtomicInteger directQueries = new AtomicInteger();
        ExoCompressedAudioDirectPolicy policy = new ExoCompressedAudioDirectPolicy(
                (format, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                (format, attributes) -> {
                    directQueries.incrementAndGet();
                    return true;
                });
        Format incomplete = new Format.Builder()
                .setSampleMimeType(MimeTypes.AUDIO_AAC)
                .setCodecs("mp4a.40.2")
                .build();

        AudioOutputProvider.FormatSupport actual = wrapped(policy)
                .getFormatSupport(formatConfig(incomplete));

        assertTrue(actual.supportLevel
                == AudioOutputProvider.FORMAT_UNSUPPORTED);
        assertTrue(directQueries.get() == 0);
    }

    @Test
    public void acceptedDirectAudio_stuckPlaying_requestsOnePcmRetry() throws Exception {
        for (int sampleRate : new int[]{44_100, 48_000}) {
            DirectOutputFixture fixture = new DirectOutputFixture(sampleRate);
            fixture.stall();

            assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
            assertTrue(fixture.policy.consumePcmFallbackRequest());
            assertFalse(fixture.policy.consumePcmFallbackRequest());
            assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
            // Even a delegate advertising generic passthrough must now force decoder + PCM.
            assertEquals(AudioOutputProvider.FORMAT_UNSUPPORTED,
                    fixture.provider.getFormatSupport(formatConfig(fixture.format)).supportLevel);
            assertFalse(fixture.policy.usesVendorDirect(C.ENCODING_AAC_LC, sampleRate,
                    Util.getAudioTrackChannelConfig(fixture.format)));
        }
    }

    @Test
    public void otherTimeoutsAndErrors_doNotDisableStalledDirectOutput() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        for (int type : new int[]{StuckPlayerException.STUCK_BUFFERING_NOT_LOADING,
                StuckPlayerException.STUCK_BUFFERING_NO_PROGRESS,
                StuckPlayerException.STUCK_PLAYING_NOT_ENDING,
                StuckPlayerException.STUCK_SUPPRESSED}) {
            assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuck(type)));
        }
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(
                playbackError(PlaybackException.ERROR_CODE_TIMEOUT,
                        new IllegalStateException())));
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(
                playbackError(PlaybackException.ERROR_CODE_IO_UNSPECIFIED,
                        new StuckPlayerException(
                                StuckPlayerException.STUCK_PLAYING_NO_PROGRESS, 10_000))));
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(null));
        assertFalse(fixture.policy.consumePcmFallbackRequest());
        assertEquals(AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY,
                fixture.provider.getFormatSupport(formatConfig(fixture.format)).supportLevel);
    }

    @Test
    public void recentAudioProgress_doesNotBlameDirectOutput() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        fixture.raw.positionUs = 4_000_000;
        assertEquals(4_000_000, fixture.output.getPositionUs());

        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
        assertFalse(fixture.policy.consumePcmFallbackRequest());
    }

    @Test
    public void outputStallsAfterProgress_canRecoverAtNonzeroPosition() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.writeAndPlay();
        fixture.output.getPositionUs();
        fixture.nowMs.addAndGet(5_000);
        fixture.raw.positionUs = 5_000_000;
        fixture.output.getPositionUs();
        fixture.nowMs.addAndGet(10_000);
        fixture.output.getPositionUs();

        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void zeroWritesOrUnknownPosition_doNotProveOutputStall() throws Exception {
        DirectOutputFixture noData = new DirectOutputFixture(44_100);
        noData.raw.acceptWrites = false;
        noData.stall();
        assertFalse(noData.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        DirectOutputFixture unknown = new DirectOutputFixture(44_100);
        unknown.raw.positionUs = C.TIME_UNSET;
        unknown.stall();
        assertFalse(unknown.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void pauseAndResume_restartObservationWindow() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.writeAndPlay();
        fixture.output.getPositionUs();
        fixture.output.pause();
        fixture.nowMs.addAndGet(20_000);
        fixture.output.getPositionUs();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        fixture.output.play();
        fixture.output.getPositionUs();
        fixture.nowMs.addAndGet(1_000);
        fixture.output.getPositionUs();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
        fixture.nowMs.addAndGet(1_000);
        fixture.output.getPositionUs();
        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void flush_requiresFreshInputAndProgressEvidence() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        fixture.output.flush();
        fixture.nowMs.addAndGet(10_000);
        fixture.output.getPositionUs();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        fixture.stall();
        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void naturalStop_discardsStallEvidence() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        fixture.output.stop();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void pauseAndReleaseBeforeError_preserveObservedEvidence() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        fixture.output.pause();
        fixture.output.release();

        assertFalse(fixture.policy.getAudioOutputSnapshot().initialized());
        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
        assertTrue(fixture.policy.consumePcmFallbackRequest());
    }

    @Test
    public void oldRelease_doesNotContaminateNewOutput() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        AudioOutput old = fixture.output;
        fixture.createOutput();
        old.release();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        fixture.stall();
        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void newPlaybackAttempt_rejectsOldAndLateInitializationEvidence() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.stall();
        fixture.policy.resetOutputProgress();
        fixture.output.getPositionUs();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        fixture.duringCreation = fixture.policy::resetOutputProgress;
        fixture.createOutput();
        fixture.stall();
        assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));

        fixture.duringCreation = null;
        fixture.createOutput();
        fixture.stall();
        assertTrue(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
    }

    @Test
    public void standardPcmOffloadAndTunneling_replaceVendorEvidence() throws Exception {
        AudioOutputProvider.OutputConfig pcm = new AudioOutputProvider.OutputConfig.Builder()
                .setEncoding(C.ENCODING_PCM_16BIT).setSampleRate(44_100)
                .setChannelMask(12).setBufferSize(4096).build();
        for (AudioOutputProvider.OutputConfig config : new AudioOutputProvider.OutputConfig[]{
                pcm, encodedOutput(false, true), encodedOutput(true, false)}) {
            DirectOutputFixture fixture = new DirectOutputFixture(44_100);
            fixture.stall();
            AudioOutput standard = fixture.policy.wrapOutputProvider(
                    new StandardAudioOutputProvider(config)).getAudioOutput(config);

            assertFalse(fixture.policy.requestPcmFallbackForStuckPlayback(stuckPlaying()));
            assertFalse(fixture.policy.consumePcmFallbackRequest());
            standard.release();
        }
    }

    @Test
    public void writeFailure_stillRequestsRecoverablePcmFallback() throws Exception {
        DirectOutputFixture fixture = new DirectOutputFixture(44_100);
        fixture.raw.writeFailure = new AudioOutput.WriteException(-6, false);
        AudioOutput.WriteException error = assertThrows(AudioOutput.WriteException.class,
                fixture::writeAndPlay);

        assertEquals(-6, error.errorCode);
        assertTrue(error.isRecoverable);
        assertTrue(fixture.policy.consumePcmFallbackRequest());
        assertEquals(AudioOutputProvider.FORMAT_UNSUPPORTED,
                fixture.provider.getFormatSupport(formatConfig(fixture.format)).supportLevel);
    }

    private static PlaybackException stuckPlaying() {
        return stuck(StuckPlayerException.STUCK_PLAYING_NO_PROGRESS);
    }

    private static PlaybackException stuck(int type) {
        return playbackError(PlaybackException.ERROR_CODE_TIMEOUT,
                new StuckPlayerException(type, 10_000));
    }

    private static PlaybackException playbackError(int errorCode, Throwable cause) {
        // Media3's public PlaybackException constructor reads android.os.SystemClock, which
        // the JVM unit-test android stub rejects as an unmocked native method. The
        // timestamped constructor keeps this fixture free of android.os framework calls.
        return new TestPlaybackException(errorCode, cause);
    }

    private static final class TestPlaybackException extends PlaybackException {

        TestPlaybackException(int errorCode, Throwable cause) {
            super("stuck", cause, errorCode, null, 0);
        }
    }

    private static final class DirectOutputFixture {
        final AtomicLong nowMs = new AtomicLong();
        final Format format;
        final ExoCompressedAudioDirectPolicy policy;
        final AudioOutputProvider provider;
        AudioOutput output;
        FakeAudioOutput raw;
        Runnable duringCreation;

        DirectOutputFixture(int sampleRate) throws Exception {
            format = aacStereo().buildUpon().setSampleRate(sampleRate).build();
            Clock clock = (Clock) Proxy.newProxyInstance(Clock.class.getClassLoader(),
                    new Class<?>[]{Clock.class}, (proxy, method, args) -> {
                        if (method.getName().equals("elapsedRealtime")) return nowMs.get();
                        throw new AssertionError("Unexpected Clock call: " + method.getName());
                    });
            policy = new ExoCompressedAudioDirectPolicy(
                    (ignoredFormat, attributes) -> AudioOffloadSupport.DEFAULT_UNSUPPORTED,
                    (ignoredFormat, attributes) -> true, clock, config -> {
                        if (duringCreation != null) duringCreation.run();
                        return raw.output;
                    });
            provider = policy.wrapOutputProvider(new FixedFormatSupportAudioOutputProvider(
                    new AudioOutputProvider.FormatSupport.Builder()
                            .setFormatSupportLevel(AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY)
                            .build()));
            provider.getFormatSupport(formatConfig(format));
            createOutput();
        }

        void createOutput() throws Exception {
            raw = new FakeAudioOutput();
            output = provider.getAudioOutput(provider.getOutputConfig(formatConfig(format)));
        }

        void writeAndPlay() throws AudioOutput.WriteException {
            ByteBuffer buffer = ByteBuffer.allocateDirect(32);
            output.write(buffer, 1, 1_027_599_000L);
            output.play();
        }

        void stall() throws AudioOutput.WriteException {
            writeAndPlay();
            output.getPositionUs();
            nowMs.addAndGet(10_000);
            output.getPositionUs();
        }
    }

    private static final class FakeAudioOutput {
        long positionUs;
        boolean acceptWrites = true;
        boolean released;
        AudioOutput.WriteException writeFailure;
        final AudioOutput output = (AudioOutput) Proxy.newProxyInstance(
                AudioOutput.class.getClassLoader(), new Class<?>[]{AudioOutput.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "getPositionUs":
                            if (released) throw new AssertionError("Queried released output");
                            return positionUs;
                        case "write":
                            if (writeFailure != null) throw writeFailure;
                            ByteBuffer buffer = (ByteBuffer) args[0];
                            if (acceptWrites) buffer.position(buffer.limit());
                            return !buffer.hasRemaining();
                        case "release":
                            released = true;
                            return null;
                        default:
                            return null;
                    }
                });
    }

    private static AudioOutputProvider wrapped(
            ExoCompressedAudioDirectPolicy policy) {
        return policy.wrapOutputProvider(new UnsupportedAudioOutputProvider());
    }

    private static AudioOutputProvider.FormatConfig formatConfig(Format format) {
        return new AudioOutputProvider.FormatConfig.Builder(format)
                .setAudioAttributes(AudioAttributes.DEFAULT)
                .build();
    }

    private static AudioOutputProvider.FormatConfig tunnelingConfig() {
        return new AudioOutputProvider.FormatConfig.Builder(aacStereo())
                .setAudioAttributes(AudioAttributes.DEFAULT)
                .setAudioSessionId(1234)
                .setVirtualDeviceId(0)
                .setEnableTunneling(true)
                .build();
    }

    private static AudioOutputProvider.OutputConfig encodedOutput(boolean tunneling, boolean offload) {
        return new AudioOutputProvider.OutputConfig.Builder()
                .setEncoding(C.ENCODING_AAC_LC)
                .setSampleRate(48_000)
                .setChannelMask(Util.getAudioTrackChannelConfig(aacStereo()))
                .setBufferSize(4096)
                .setAudioSessionId(1234)
                .setIsTunneling(tunneling)
                .setIsOffload(offload)
                .build();
    }

    private static Format aacStereo() {
        return new Format.Builder()
                .setSampleMimeType(MimeTypes.AUDIO_AAC)
                .setCodecs("mp4a.40.2")
                .setSampleRate(48_000)
                .setChannelCount(2)
                .build();
    }

    private static AudioOffloadSupport supported(
            boolean gapless, boolean speedChange) {
        return new AudioOffloadSupport.Builder()
                .setIsFormatSupported(true)
                .setIsGaplessSupported(gapless)
                .setIsSpeedChangeSupported(speedChange)
                .build();
    }

    private static class UnsupportedAudioOutputProvider
            implements AudioOutputProvider {

        @Override
        public FormatSupport getFormatSupport(FormatConfig config) {
            return FormatSupport.UNSUPPORTED;
        }

        @Override
        public OutputConfig getOutputConfig(FormatConfig config)
                throws ConfigurationException {
            throw new ConfigurationException("unsupported");
        }

        @Override
        public AudioOutput getAudioOutput(OutputConfig config)
                throws InitializationException {
            throw new InitializationException();
        }

        @Override
        public void addListener(Listener listener) {
        }

        @Override
        public void removeListener(Listener listener) {
        }

        @Override
        public void release() {
        }
    }

    private static final class FixedFormatSupportAudioOutputProvider
            extends UnsupportedAudioOutputProvider {

        private final FormatSupport formatSupport;

        FixedFormatSupportAudioOutputProvider(FormatSupport formatSupport) {
            this.formatSupport = formatSupport;
        }

        @Override
        public FormatSupport getFormatSupport(FormatConfig config) {
            return formatSupport;
        }
    }

    private static final class StandardAudioOutputProvider extends UnsupportedAudioOutputProvider {
        private final OutputConfig config;
        private final FormatSupport support = new FormatSupport.Builder()
                .setFormatSupportLevel(AudioOutputProvider.FORMAT_SUPPORTED_DIRECTLY).build();
        private int creations;

        StandardAudioOutputProvider(OutputConfig config) {
            this.config = config;
        }

        @Override public FormatSupport getFormatSupport(FormatConfig config) { return support; }

        @Override public OutputConfig getOutputConfig(FormatConfig config) { return this.config; }

        @Override public AudioOutput getAudioOutput(OutputConfig config) {
            assertSame(this.config, config);
            creations++;
            return (AudioOutput) Proxy.newProxyInstance(AudioOutput.class.getClassLoader(),
                    new Class<?>[]{AudioOutput.class}, (proxy, method, args) -> null);
        }
    }
}
