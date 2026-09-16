package com.fongmi.android.tv.bean;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class AdBlockStatsTest {

    @Test
    public void incrementBlocksUpdatesAllDimensionsAtomically() {
        AdBlockStats stats = new AdBlockStats();

        stats.incrementBlocks("demo", "EXO", "rule-a", 3);
        stats.incrementBlocks("demo", "EXO", "hls.legacy-fallback", 2);

        assertEquals(5, stats.getTotalBlocked());
        assertEquals(5, stats.getSiteBlockedCount("demo"));
        assertEquals(3, stats.getRuleBlockedCount("rule-a"));
        assertEquals(2, stats.getRuleBlockedCount("hls.legacy-fallback"));
        assertEquals(5, stats.getPipelineBlockedCount("EXO"));
    }

    @Test
    public void nonPositiveCountsAreIgnoredAndResetClearsEveryDimension() {
        AdBlockStats stats = new AdBlockStats();

        stats.incrementBlocks("demo", "MPV", "rule-a", 4);
        stats.incrementBlocks("demo", "MPV", "rule-a", 0);
        stats.incrementBlocks("demo", "MPV", "rule-a", -2);
        stats.reset();

        assertEquals(0, stats.getTotalBlocked());
        assertEquals(0, stats.getSiteBlockedCount("demo"));
        assertEquals(0, stats.getRuleBlockedCount("rule-a"));
        assertEquals(0, stats.getPipelineBlockedCount("MPV"));
    }
}
