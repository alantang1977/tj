package com.fongmi.android.tv.cache;

import androidx.media3.mpvplayer.MpvHlsCacheCoordinator;

import com.bumptech.glide.Glide;
import com.fongmi.android.tv.App;
import com.fongmi.android.tv.Updater;
import com.fongmi.android.tv.api.loader.BaseLoader;
import com.fongmi.android.tv.api.parser.EpgParser;
import com.fongmi.android.tv.player.exo.MediaSourceFactory;
import com.fongmi.android.tv.player.karaoke.KaraokeTrackRepository;
import com.fongmi.android.tv.player.lyrics.LyricsRepository;
import com.fongmi.android.tv.server.process.ApkUrlPush;
import com.fongmi.android.tv.service.PlaybackService;
import com.fongmi.android.tv.web.WebHomeRawAdapter;
import com.fongmi.android.tv.web.ext.WebHomeExtensionRegistry;
import com.github.catvod.crawler.DebugLogStore;
import com.github.catvod.utils.Path;

import java.io.File;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

public final class CacheCleanupManager {

    private static final long TEMP_RETENTION_MS = 24L * 60L * 60L * 1000L;
    private static final long TEMP_MINIMUM_AGE_MS = 60L * 60L * 1000L;
    private static final long LEGACY_RETENTION_MS = 7L * 24L * 60L * 60L * 1000L;
    private static final Set<String> PROTECTED_NAMES = Set.of(
            "mpv-playback-recovery.lock",
            "mpv-playback-recovery.state",
            "mpv-playback-recovery.result"
    );
    private static final AtomicBoolean CANCELLED = new AtomicBoolean();
    private static final Object RUN_LOCK = new Object();
    private static volatile boolean running;

    private CacheCleanupManager() {
    }

    public static void execute(CacheCleanupPlan plan, Consumer<CacheCleanupResult> callback) {
        execute(plan, "manual", null, callback);
    }

    public static void execute(CacheCleanupPlan plan, String reason, Consumer<CacheCleanupResult> callback) {
        execute(plan, reason, null, callback);
    }

    public static void execute(CacheCleanupPlan plan, Consumer<CacheCleanupProgress> progress,
                               Consumer<CacheCleanupResult> callback) {
        execute(plan, "manual", progress, callback);
    }

    public static void execute(CacheCleanupPlan plan, String reason,
                               Consumer<CacheCleanupProgress> progress,
                               Consumer<CacheCleanupResult> callback) {
        if (plan == null || plan.modules().isEmpty()) {
            App.post(() -> callback.accept(new CacheCleanupResult(null, CacheCleanupStatus.NOT_ALLOWED,
                    0, 0, 0, 0, List.of("empty plan"))));
            return;
        }
        synchronized (RUN_LOCK) {
            if (running) {
                App.post(() -> callback.accept(new CacheCleanupResult(plan.modules().get(0),
                        CacheCleanupStatus.FAILED, 0, 0, 0, 0, List.of("cleanup already running"))));
                return;
            }
            running = true;
            CANCELLED.set(false);
        }
        new Thread(() -> run(plan, reason, progress, callback), "cache-cleanup").start();
    }

    public static boolean isRunning() {
        return running;
    }

    public static void cancel() {
        if (running) CANCELLED.set(true);
    }

    public static void applyConfiguredLimits() {
        File cache = App.get().getCacheDir();
        long retention = CachePolicyStore.getRetentionDays() * 24L * 60L * 60L * 1000L;
        long now = System.currentTimeMillis();
        CacheRetentionManager.applyLimit(new File(cache, "lyrics"),
                CachePolicyStore.getLimit(CacheModuleId.LYRICS), retention, () -> now, Set.of());
        CacheRetentionManager.applyLimit(new File(cache, "karaoke_tracks"),
                CachePolicyStore.getLimit(CacheModuleId.KARAOKE), retention, () -> now, Set.of());
        CacheRetentionManager.applyLimit(new File(cache, "webhome_ext"),
                CachePolicyStore.getLimit(CacheModuleId.WEBHOME_EXT), retention, () -> now, Set.of());
        CacheRetentionManager.applyLimit(new File(cache, "epg"),
                CachePolicyStore.getLimit(CacheModuleId.EPG), Math.min(retention, 6L * 60L * 60L * 1000L),
                () -> now, Set.of());
        CacheCenter.get().notifyChanged();
    }

    private static void run(CacheCleanupPlan plan, String reason,
                            Consumer<CacheCleanupProgress> progress,
                            Consumer<CacheCleanupResult> callback) {
        long startedAt = System.currentTimeMillis();
        ArrayList<CacheCleanupResult> results = new ArrayList<>();
        try {
            int total = plan.modules().size();
            for (int index = 0; index < total; index++) {
                CacheModuleId id = plan.modules().get(index);
                if (CANCELLED.get()) {
                    results.add(new CacheCleanupResult(id, CacheCleanupStatus.CANCELLED,
                            0, 0, 0, 0, List.of("cancelled")));
                    break;
                }
                if (progress != null) {
                    int completed = index;
                    App.post(() -> progress.accept(new CacheCleanupProgress(id, completed, total, 0, 0)));
                }
                results.add(cleanModule(id, plan.mode()));
            }
        } catch (Throwable error) {
            CacheModuleId id = plan.modules().get(0);
            results.add(new CacheCleanupResult(id, CacheCleanupStatus.FAILED,
                    0, 0, 0, 0, List.of(error.getClass().getSimpleName())));
        } finally {
            synchronized (RUN_LOCK) {
                running = false;
            }
        }
        long finishedAt = System.currentTimeMillis();
        CacheCleanupResult result = aggregate(results);
        CacheCleanupJournal.record(new CacheCleanupRecord(
                startedAt, Math.max(0, finishedAt - startedAt), reason == null ? "manual" : reason,
                plan.mode(), result.status(), result.bytesBefore(), result.bytesAfter(),
                result.deletedFiles(), result.skippedFiles(), result.warnings()));
        // Any cleanup mutates the disk, so the cached inventory is stale and every cache surface
        // (settings row, panel summary) must re-read it. Without this the settings row keeps the
        // pre-cleanup value until the user leaves and re-enters the page.
        App.post(CacheCenter.get()::invalidate);
        App.post(() -> callback.accept(result));
        App.post(CacheCenter.get()::publishChanged);
    }

    private static CacheCleanupResult cleanModule(CacheModuleId id, CacheCleanupMode mode) {
        CacheMeasurement before = measure(id);
        boolean playing = PlaybackService.isRunning();
        CacheCleanupStatus gate = CachePolicyEngine.directCleanupStatus(id, playing);
        if (gate != CacheCleanupStatus.COMPLETED) {
            return new CacheCleanupResult(id, gate, before.bytes(), before.bytes(), 0,
                    before.fileCount(), List.of(gate.name().toLowerCase()));
        }
        Outcome outcome;
        try {
            outcome = executeCleanup(id, mode);
        } catch (Throwable error) {
            return new CacheCleanupResult(id, CacheCleanupStatus.FAILED,
                    before.bytes(), before.bytes(), 0, before.fileCount(),
                    List.of(error.getClass().getSimpleName()));
        }
        CacheMeasurement after = measure(id);
        long deleted = Math.max(0, before.fileCount() - after.fileCount());
        long skipped = Math.max(0, after.fileCount());
        return new CacheCleanupResult(id,
                outcome.success ? CacheCleanupStatus.COMPLETED : CacheCleanupStatus.PARTIAL,
                before.bytes(), after.bytes(), deleted, skipped, outcome.warnings);
    }

    private static Outcome executeCleanup(CacheModuleId id, CacheCleanupMode mode) {
        File cache = App.get().getCacheDir();
        long limit = CachePolicyStore.getLimit(id);
        long retention = CachePolicyStore.getRetentionDays() * 24L * 60L * 60L * 1000L;
        return switch (id) {
            case EXO -> outcome(MediaSourceFactory.clearCacheIfIdle());
            case MPV_HLS -> outcome(MpvHlsCacheCoordinator.shared(Path.cache("mpv_hls")).clearIfIdle());
            case MPV_DEMUXER -> clearTree(new File(cache, "mpv-demuxer-cache"));
            case MPV_RUNTIME -> clearTrees(new File(cache, "mpv_lut_shaders"), new File(cache, "fontconfig"));
            case LYRICS -> mode == CacheCleanupMode.MODULE
                    ? outcome(LyricsRepository.clearCache() >= 0)
                    : outcome(CacheRetentionManager.applyLimit(new File(cache, "lyrics"), limit,
                    retention, System::currentTimeMillis, Set.of()));
            case KARAOKE -> mode == CacheCleanupMode.MODULE
                    ? outcome(KaraokeTrackRepository.clearCache())
                    : outcome(CacheRetentionManager.applyLimit(new File(cache, "karaoke_tracks"), limit,
                    retention, System::currentTimeMillis, Set.of()));
            case WEBHOME_EXT -> {
                WebHomeExtensionRegistry.get().clear();
                yield new Outcome(true, List.of());
            }
            case WEBHOME_RAW -> outcome(WebHomeRawAdapter.clearCache());
            case EPG -> mode == CacheCleanupMode.MODULE ? outcome(EpgParser.clearCache())
                    : outcome(CacheRetentionManager.applyLimit(new File(cache, "epg"), limit,
                    Math.min(retention, 6L * 60L * 60L * 1000L), System::currentTimeMillis, Set.of()));
            case GLIDE -> {
                Glide.get(App.get()).clearDiskCache();
                yield new Outcome(true, List.of());
            }
            case PLUGIN_SCRIPTS -> clearPluginCache(retention, Set.copyOf(BaseLoader.get().activePluginKeys()));
            case TEMP_FILES -> clearTemporaryFiles(TEMP_RETENTION_MS, limit);
            case DIAGNOSTIC_LOGS -> outcome(clearDiagnosticLogs());
            case LEGACY_FILES -> clearLegacyPaths(cache, mode);
            // Owner-managed and deliberately unreported: a cleanup must not guess at caches whose
            // owner is unknown, so this module is only ever measured.
            case UNCLASSIFIED -> new Outcome(true, List.of());
        };
    }

    /**
     * Clears exactly the paths the legacy rule table reports.
     *
     * <p>The previous implementation measured an inverted orphan tree and then deleted only
     * {@code restore-legacy}, so the module could report megabytes it would never remove. Both
     * sides now iterate the same rule table.</p>
     *
     * <p>A MODULE-level clean (the per-row button) means "remove this legacy path now" and ignores
     * the retention window; the tiered L1/L3 runs keep the 7-day age guard so an upgrade never
     * deletes a staging directory that the current process is still using.</p>
     */
    private static Outcome clearLegacyPaths(File cache, CacheCleanupMode mode) {
        long retentionMs = mode == CacheCleanupMode.MODULE ? 0 : LEGACY_RETENTION_MS;
        boolean success = true;
        ArrayList<String> warnings = new ArrayList<>();
        for (CacheLegacyRules.Rule rule : CacheLegacyRules.rules()) {
            Outcome result = clearTree(new File(cache, rule.name()), retentionMs);
            success &= result.success();
            warnings.addAll(result.warnings());
        }
        return new Outcome(success, warnings);
    }

    /**
     * Deletes the diagnostic log family through its owner.
     *
     * <p>{@code DebugLogStore.clear()} also drops the in-memory buffer and re-opens collection, so
     * the next log line recreates the file. Deleting the files directly would leave the writer
     * pointing at removed descriptors.</p>
     */
    private static boolean clearDiagnosticLogs() {
        try {
            DebugLogStore.clear();
            return true;
        } catch (Throwable error) {
            return false;
        }
    }

    private static Outcome clearTemporaryFiles(long retentionMs, long limitBytes) {
        File cache = App.get().getCacheDir();
        File[] files = cache.listFiles(File::isFile);
        if (files == null) return new Outcome(false, List.of("cache root unreadable"));
        long now = System.currentTimeMillis();
        boolean success = true;
        ArrayList<String> warnings = new ArrayList<>();
        ArrayList<File> remaining = new ArrayList<>();
        boolean updaterDownloading = Updater.isDownloading();
        boolean apkUrlPushing = ApkUrlPush.isActive();
        TemporaryFamily family = temporaryFamily(cache);
        for (File file : files) {
            String name = file.getName();
            if (!family.matches(name)) continue;
            if (!isExpired(file, now, retentionMs)
                    || CacheTempFilePolicy.isInUse(name, updaterDownloading, apkUrlPushing)) {
                remaining.add(file);
                continue;
            }
            if (!file.delete()) {
                success = false;
                warnings.add("delete failed: " + name);
            }
        }
        success &= CacheRetentionManager.enforceFileLimit(cache, remaining, limitBytes,
                TEMP_MINIMUM_AGE_MS, now);
        return new Outcome(success, warnings);
    }

    private static Outcome clearPluginCache(long retentionMs, Set<String> activeKeys) {
        File cache = App.get().getCacheDir();
        boolean success = true;
        ArrayList<String> warnings = new ArrayList<>();
        success &= deleteExpiredPluginFiles(new File(cache, "jar"), ".jar", activeKeys, retentionMs, warnings);
        success &= deleteExpiredPluginFiles(new File(cache, "py"), ".py", activeKeys, retentionMs, warnings);
        success &= deleteExpiredPluginFiles(new File(cache, "js"), ".js", activeKeys, retentionMs, warnings);
        return new Outcome(success, warnings);
    }

    private static boolean deleteExpiredPluginFiles(File root, String suffix, Set<String> activeKeys,
                                                    long retentionMs, List<String> warnings) {
        if (!root.isDirectory()) return true;
        File[] files = root.listFiles(File::isFile);
        if (files == null) return false;
        long now = System.currentTimeMillis();
        boolean success = true;
        for (File file : files) {
            String name = file.getName();
            if (!name.endsWith(suffix)) continue;
            String key = name.substring(0, name.length() - suffix.length());
            if (activeKeys.contains(key) || !isExpired(file, now, retentionMs)) continue;
            if (!file.delete()) {
                success = false;
                warnings.add("delete failed: " + name);
            }
        }
        return success;
    }

    /**
     * Clears a tree, optionally keeping entries newer than {@code retentionMs}.
     *
     * <p>{@code retentionMs <= 0} removes the whole tree; a positive value removes only entries
     * last modified before the cutoff.</p>
     */
    private static Outcome clearTree(File root, long retentionMs) {
        if (root == null || !root.exists()) return new Outcome(true, List.of());
        if (retentionMs <= 0) return clearTree(root);
        long cutoff = System.currentTimeMillis() - retentionMs;
        ArrayList<String> warnings = new ArrayList<>();
        boolean success = deleteAged(root, cutoff, warnings);
        return new Outcome(success, warnings);
    }

    private static boolean deleteAged(File file, long cutoff, List<String> warnings) {
        if (file == null || !file.exists()) return true;
        if (CachePathSafety.isSymbolicLink(file)) {
            warnings.add("symbolic link skipped: " + file.getName());
            return true;
        }
        boolean success = true;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children == null) {
                warnings.add("unreadable directory: " + file.getName());
                return false;
            }
            for (File child : children) success &= deleteAged(child, cutoff, warnings);
        }
        if (file.lastModified() >= cutoff) return success;
        if (!file.delete()) {
            warnings.add("delete failed: " + file.getName());
            return false;
        }
        return success;
    }

    private static Outcome clearTrees(File... roots) {
        boolean success = true;
        ArrayList<String> warnings = new ArrayList<>();
        for (File root : roots) {
            Outcome result = clearTree(root);
            success &= result.success;
            warnings.addAll(result.warnings);
        }
        return new Outcome(success, warnings);
    }

    private static Outcome clearTree(File root) {
        if (root == null || !root.exists()) return new Outcome(true, List.of());
        ArrayList<String> warnings = new ArrayList<>();
        boolean success = deleteTree(root, warnings);
        return new Outcome(success, warnings);
    }

    private static boolean deleteTree(File file, List<String> warnings) {
        if (file == null || !file.exists()) return true;
        if (CachePathSafety.isSymbolicLink(file)) {
            warnings.add("symbolic link skipped: " + file.getName());
            return true;
        }
        if (PROTECTED_NAMES.contains(file.getName())) {
            warnings.add("protected file skipped: " + file.getName());
            return true;
        }
        boolean success = true;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children == null) {
                warnings.add("unreadable directory: " + file.getName());
                return false;
            }
            for (File child : children) success &= deleteTree(child, warnings);
        }
        if (file.exists() && !file.delete()) {
            warnings.add("delete failed: " + file.getName());
            return false;
        }
        return success;
    }

    private static boolean isExpired(File file, long now, long retentionMs) {
        long modified = file.lastModified();
        return retentionMs <= 0 || modified > 0 && now - modified >= retentionMs;
    }

    /**
     * Builds the temporary-file candidate set from the registry definition of the
     * {@link CacheModuleId#TEMP_FILES} module, so cleanup can delete exactly the same family the
     * inventory reports ("reported is what gets deleted"). The previous hand-rolled prefix list
     * skipped {@code .zip}/{@code .log} siblings the registry counts and re-invented the naming
     * scheme in two places.
     */
    static TemporaryFamily temporaryFamily(File cache) {
        HashSet<String> suffixes = new HashSet<>();
        HashSet<String> excludeNames = new HashSet<>();
        for (CacheModule module : CacheModuleRegistry.modules(cache)) {
            if (module.id() != CacheModuleId.TEMP_FILES) continue;
            for (CacheRoot root : module.roots()) {
                suffixes.addAll(root.includeSuffixes());
                excludeNames.addAll(root.excludeNames());
            }
        }
        return new TemporaryFamily(suffixes, excludeNames);
    }

    /**
     * A candidate set over the cache-root temporary files, derived from the registry.
     */
    record TemporaryFamily(Set<String> suffixes, Set<String> excludeNames) {

        boolean matches(String name) {
            if (name == null || excludeNames.contains(name)) return false;
            for (String suffix : suffixes) if (name.endsWith(suffix)) return true;
            return false;
        }
    }

    private static CacheMeasurement measure(CacheModuleId id) {
        CacheModule module = CacheInventory.find(id);
        return module == null ? CacheMeasurement.unavailable(id, "unknown module")
                : CacheInventory.measure(module, Long.MAX_VALUE);
    }

    private static CacheCleanupResult aggregate(List<CacheCleanupResult> results) {
        if (results.isEmpty()) return new CacheCleanupResult(null, CacheCleanupStatus.NOT_ALLOWED,
                0, 0, 0, 0, List.of("empty results"));
        long before = 0, after = 0, deleted = 0, skipped = 0;
        ArrayList<String> warnings = new ArrayList<>();
        for (CacheCleanupResult result : results) {
            before += result.bytesBefore();
            after += result.bytesAfter();
            deleted += result.deletedFiles();
            skipped += result.skippedFiles();
            warnings.addAll(result.warnings());
        }
        CacheCleanupStatus status = results.stream().anyMatch(r -> r.status() == CacheCleanupStatus.CANCELLED)
                ? CacheCleanupStatus.CANCELLED
                : results.stream().anyMatch(r -> r.status() == CacheCleanupStatus.FAILED)
                ? CacheCleanupStatus.FAILED
                : results.stream().anyMatch(r -> r.status() == CacheCleanupStatus.DEFERRED
                || r.status() == CacheCleanupStatus.PARTIAL)
                ? CacheCleanupStatus.PARTIAL
                : results.stream().allMatch(r -> r.status() == CacheCleanupStatus.NOT_ALLOWED)
                ? CacheCleanupStatus.NOT_ALLOWED : CacheCleanupStatus.COMPLETED;
        return new CacheCleanupResult(results.get(0).id(), status, before, after, deleted, skipped, warnings);
    }

    private static Outcome outcome(boolean success) {
        return new Outcome(success, success ? List.of() : List.of("owner cleanup failed"));
    }

    private record Outcome(boolean success, List<String> warnings) {
    }
}
