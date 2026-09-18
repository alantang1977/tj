package com.fongmi.android.tv.api.config;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.fongmi.android.tv.bean.Rule;
import com.fongmi.android.tv.utils.HlsAdblockPipeline;
import com.fongmi.android.tv.utils.HlsManifestCleaner;

import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

public class HlsRuleConfigTest {

    @Test
    public void legacyHostsScopePlaylistAndRegexMatchesSegmentUrl() {
        List<HlsManifestCleaner.Rule> compiled = new ArrayList<>();
        HlsRuleConfig.compileLegacyRules(
                List.of(Rule.create("优质", List.of(".vvvip-plays33.cc"), List.of("16.4666"), List.of())),
                compiled);
        String manifest = "#EXTM3U\n"
                + "#EXTINF:7.0,\nhttps://cdn.example.com/16.4666-ad.ts\n"
                + "#EXTINF:8.0,\nhttps://cdn.example.com/main-1.ts\n"
                + "#EXTINF:8.0,\nhttps://cdn.example.com/main-2.ts\n"
                + "#EXT-X-ENDLIST\n";

        HlsAdblockPipeline.Outcome matched = HlsAdblockPipeline.apply(
                "https://foo.vvvip-plays33.cc/index.m3u8", manifest, compiled, false);
        HlsAdblockPipeline.Outcome outsideHost = HlsAdblockPipeline.apply(
                "https://video.example.com/index.m3u8", manifest, compiled, false);

        assertTrue(matched.structured());
        assertFalse(matched.manifest().contains("16.4666-ad.ts"));
        assertFalse(outsideHost.structured());
        assertTrue(outsideHost.manifest().contains("16.4666-ad.ts"));
    }
}
