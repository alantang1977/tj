package com.fongmi.android.tv.ui.activity;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.Html;
import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.viewbinding.ViewBinding;
import androidx.viewpager2.widget.ViewPager2;

import com.fongmi.android.tv.App;
import com.fongmi.android.tv.R;
import com.fongmi.android.tv.api.SiteApi;
import com.fongmi.android.tv.api.config.VodConfig;
import com.fongmi.android.tv.bean.Episode;
import com.fongmi.android.tv.bean.Flag;
import com.fongmi.android.tv.bean.History;
import com.fongmi.android.tv.bean.Keep;
import com.fongmi.android.tv.bean.Result;
import com.fongmi.android.tv.bean.Site;
import com.fongmi.android.tv.bean.Vod;
import com.fongmi.android.tv.databinding.ActivityShortDramaBinding;
import com.fongmi.android.tv.databinding.ItemDramaGridBinding;
import com.fongmi.android.tv.databinding.ItemDramaHistoryBinding;
import com.fongmi.android.tv.databinding.ItemDramaPageBinding;
import com.fongmi.android.tv.db.AppDatabase;
import com.fongmi.android.tv.drama.DramaSites;
import com.fongmi.android.tv.ui.adapter.EpisodeAdapter;
import com.fongmi.android.tv.ui.base.BaseActivity;
import com.fongmi.android.tv.ui.dialog.EpisodeGridDialog;
import com.fongmi.android.tv.utils.ImgUtil;
import com.fongmi.android.tv.utils.Task;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Short-drama section modeled on the behaviour Cook verified in PeekPro:
 * when the imported config carries short-drama sites (see DramaSites), the
 * bottom bar gains a Drama tab leading here. The section is an immersive
 * vertical feed over the selected source's own list — swipe to change drama,
 * every drama starts at episode 1 — with a theater grid, a source switcher
 * and a history view. Playback of a single item that needs parsing, and all
 * detail/episode work, is handed to the existing VideoActivity, whose
 * short-drama mode already covers speed memory and auto-advance.
 */
public class ShortDramaActivity extends BaseActivity implements EpisodeAdapter.OnClickListener {

    private static final int COLOR_ACCENT = 0xFFFF7A29;
    private static final int COLOR_TAB = 0xFFFFFFFF;

    private enum Mode {FEED, THEATER, HISTORY}

    private ActivityShortDramaBinding mBinding;
    private List<Site> sites = new ArrayList<>();
    private Site current;
    private final List<Vod> feed = new ArrayList<>();
    private final Map<String, Vod> detailCache = new HashMap<>();
    private ExoPlayer player;
    private DefaultHttpDataSource.Factory httpFactory;
    private PageAdapter pageAdapter;
    private GridAdapter gridAdapter;
    private HistoryAdapter historyAdapter;
    private PageHolder activeHolder;
    private int currentPage = -1;
    private int playToken;
    private int loadRetry;
    private Mode mode = Mode.FEED;
    private int episodePosition = -1;
    private List<Episode> episodeList;
    private int playingEpisodeIndex;

    public static void start(Activity activity) {
        activity.startActivity(new Intent(activity, ShortDramaActivity.class));
    }

    @Override
    protected ViewBinding getBinding() {
        return mBinding = ActivityShortDramaBinding.inflate(getLayoutInflater());
    }

    @Override
    protected void initView(Bundle savedInstanceState) {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        sites = DramaSites.detect();
        current = DramaSites.current(sites);
        buildPlayer();
        pageAdapter = new PageAdapter();
        mBinding.pager.setOrientation(ViewPager2.ORIENTATION_VERTICAL);
        mBinding.pager.setOffscreenPageLimit(1);
        mBinding.pager.setAdapter(pageAdapter);
        mBinding.pager.registerOnPageChangeCallback(new ViewPager2.OnPageChangeCallback() {
            @Override
            public void onPageSelected(int position) {
                onPageChosen(position);
            }
        });
        gridAdapter = new GridAdapter();
        mBinding.grid.setLayoutManager(new GridLayoutManager(this, 3));
        mBinding.grid.setAdapter(gridAdapter);
        historyAdapter = new HistoryAdapter();
        mBinding.historyList.setLayoutManager(new LinearLayoutManager(this));
        mBinding.historyList.setAdapter(historyAdapter);
        setMode(Mode.FEED);
        if (current == null) showState(getString(R.string.drama_empty), false);
        else loadSource(current);
    }

    @Override
    protected void initEvent() {
        mBinding.tabRecommend.setOnClickListener(view -> setMode(Mode.FEED));
        mBinding.tabTheater.setOnClickListener(view -> setMode(Mode.THEATER));
        mBinding.tabHistory.setOnClickListener(view -> setMode(Mode.HISTORY));
        mBinding.tabHome.setOnClickListener(view -> finish());
        mBinding.btnSource.setOnClickListener(view -> showSourceDialog());
        mBinding.state.setOnClickListener(view -> {
            if (current != null) loadSource(current);
        });
    }

    private void buildPlayer() {
        httpFactory = new DefaultHttpDataSource.Factory()
                .setAllowCrossProtocolRedirects(true)
                .setConnectTimeoutMs(15000)
                .setReadTimeoutMs(15000);
        DefaultDataSource.Factory dataFactory = new DefaultDataSource.Factory(this, httpFactory);
        player = new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(dataFactory))
                .build();
        player.addListener(new Player.Listener() {
            @Override
            public void onPlaybackStateChanged(int state) {
                if (state == Player.STATE_READY && activeHolder != null) {
                    activeHolder.binding.pageLoading.setVisibility(View.GONE);
                    activeHolder.binding.poster.setVisibility(View.GONE);
                }
                if (state == Player.STATE_ENDED) {
                    onVideoEnded();
                }
            }

            @Override
            public void onPlayerError(@NonNull PlaybackException error) {
                if (activeHolder == null) return;
                // 播放地址本身没问题、只是网络抖了一下很常见：先自动重试一次，
                // 还不行再显示“加载失败，点击重试”，点提示文字也可以再试一次。
                if (loadRetry < 1 && currentPage >= 0 && currentPage < feed.size()) {
                    loadRetry++;
                    activeHolder.binding.pageLoading.setVisibility(View.VISIBLE);
                    activeHolder.binding.pageHint.setVisibility(View.GONE);
                    int position = currentPage;
                    PageHolder holder = activeHolder;
                    holder.binding.pageHint.postDelayed(() -> {
                        if (position == currentPage && activeHolder == holder) playEpisode(position, playingEpisodeIndex);
                    }, 800);
                    return;
                }
                activeHolder.binding.pageLoading.setVisibility(View.GONE);
                activeHolder.binding.pageHint.setText(R.string.drama_load_failed);
                activeHolder.binding.pageHint.setVisibility(View.VISIBLE);
            }
        });
    }

    // --- source loading -------------------------------------------------

    private void loadSource(Site site) {
        stopPlayer();
        showState(null, false);
        mBinding.progress.setVisibility(View.VISIBLE);
        feed.clear();
        pageAdapter.notifyDataSetChanged();
        gridAdapter.notifyDataSetChanged();
        Task.executor().submit(() -> {
            List<Vod> list = new ArrayList<>();
            try {
                Result result = SiteApi.homeContent(site);
                if (result != null) {
                    try {
                        result = SiteApi.fetchPic(site, result);
                    } catch (Exception ignored) {
                    }
                    if (result != null) list = result.getList();
                    if (list.isEmpty() && result != null && !result.getTypes().isEmpty()) {
                        Result category = SiteApi.categoryContent(site.getKey(), result.getTypes().get(0).getTypeId(), "1", false, new HashMap<>());
                        if (category != null) list = category.getList();
                    }
                }
            } catch (Exception ignored) {
            }
            List<Vod> loaded = list;
            App.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                mBinding.progress.setVisibility(View.GONE);
                feed.addAll(loaded);
                pageAdapter.notifyDataSetChanged();
                gridAdapter.notifyDataSetChanged();
                if (feed.isEmpty()) {
                    showState(getString(R.string.drama_no_content), false);
                } else {
                    currentPage = -1;
                    mBinding.pager.setCurrentItem(0, false);
                    onPageChosen(0);
                }
            });
        });
    }

    private void showSourceDialog() {
        if (sites.isEmpty()) return;
        String[] names = new String[sites.size()];
        for (int i = 0; i < sites.size(); i++) names[i] = sites.get(i).getDisplayName();
        int checked = Math.max(0, sites.indexOf(current));
        new AlertDialog.Builder(this)
                .setTitle(getString(R.string.drama_source_title) + " · " + getString(R.string.drama_source_count, sites.size()))
                .setSingleChoiceItems(names, checked, (dialog, which) -> {
                    dialog.dismiss();
                    Site target = sites.get(which);
                    if (current == null || !target.getKey().equals(current.getKey())) {
                        current = target;
                        DramaSites.saveCurrent(target.getKey());
                        detailCache.clear();
                        setMode(Mode.FEED);
                        loadSource(target);
                    }
                })
                .setNegativeButton(android.R.string.cancel, null)
                .show();
    }

    // --- feed playback --------------------------------------------------

    private void onPageChosen(int position) {
        if (position < 0 || position >= feed.size()) return;
        currentPage = position;
        playingEpisodeIndex = 0;
        mBinding.pager.post(() -> attachAndResolve(position, 0));
    }

    private PageHolder holderAt(int position) {
        if (mBinding.pager.getChildCount() == 0) return null;
        RecyclerView recycler = (RecyclerView) mBinding.pager.getChildAt(0);
        RecyclerView.ViewHolder holder = recycler.findViewHolderForAdapterPosition(position);
        return holder instanceof PageHolder ? (PageHolder) holder : null;
    }

    private void attachAndResolve(int position, int attempt) {
        if (position != currentPage) return;
        PageHolder holder = holderAt(position);
        if (holder == null) {
            if (attempt < 10) mBinding.pager.postDelayed(() -> attachAndResolve(position, attempt + 1), 50);
            return;
        }
        if (activeHolder != null && activeHolder != holder) {
            activeHolder.binding.player.setPlayer(null);
            activeHolder.binding.poster.setVisibility(View.VISIBLE);
        }
        activeHolder = holder;
        holder.binding.player.setPlayer(player);
        resolve(position, holder);
    }

    private void resolve(int position, PageHolder holder) {
        Vod vod = feed.get(position);
        Site site = current;
        if (site == null) return;
        int token = ++playToken;
        loadRetry = 0;
        holder.binding.pageLoading.setVisibility(View.VISIBLE);
        holder.binding.pageHint.setVisibility(View.GONE);
        holder.binding.name.setText(vod.getName());
        holder.binding.meta.setText(vod.getRemarks());
        holder.binding.content.setText("");
        Task.executor().submit(() -> {
            try {
                Vod detail = detailOf(site, vod);
                if (detail == null) {
                    failPage(token, holder, R.string.drama_load_failed);
                    return;
                }
                Flag flag = firstFlag(detail);
                if (flag == null || flag.getEpisodes().isEmpty()) {
                    failPage(token, holder, R.string.drama_load_failed);
                    return;
                }
                Episode episode = flag.getEpisodes().get(0);
                boolean kept = Keep.find(historyKey(site, detail)) != null;
                App.post(() -> {
                    if (token != playToken) return;
                    bindDetail(holder, detail, flag, kept);
                });
                Result playerResult = SiteApi.playerContent(site.getKey(), flag.getFlag(), episode.getUrl());
                if (playerResult != null && (Integer.valueOf(1).equals(playerResult.getParse()) || Integer.valueOf(1).equals(playerResult.getJx()))) {
                    App.post(() -> {
                        if (token != playToken) return;
                        holder.binding.pageLoading.setVisibility(View.GONE);
                        holder.binding.pageHint.setText(R.string.drama_need_parse);
                        holder.binding.pageHint.setVisibility(View.VISIBLE);
                    });
                    return;
                }
                String url = playerResult == null || playerResult.getUrl() == null ? "" : playerResult.getUrl().v();
                if (TextUtils.isEmpty(url)) {
                    failPage(token, holder, R.string.drama_load_failed);
                    return;
                }
                Map<String, String> headers = playerResult.getHeader();
                recordHistory(site, detail, flag, episode);
                App.post(() -> {
                    if (token != playToken) return;
                    playUrl(url, headers);
                });
            } catch (Exception e) {
                failPage(token, holder, R.string.drama_load_failed);
            }
        });
    }

    private void bindDetail(PageHolder holder, Vod detail, Flag flag, boolean kept) {
        holder.binding.meta.setText(getString(R.string.drama_episode_meta, 1, flag.getEpisodes().size()));
        holder.expanded = false;
        holder.binding.content.setMaxLines(2);
        String content = detail.getContent();
        if (!TextUtils.isEmpty(content)) {
            holder.binding.content.setText(Html.fromHtml(content, Html.FROM_HTML_MODE_LEGACY).toString().trim());
        }
        holder.binding.railKeep.setCompoundDrawablesWithIntrinsicBounds(0, kept ? R.drawable.ic_control_keep_on : R.drawable.ic_control_keep_off, 0, 0);
    }

    private void playUrl(String url, Map<String, String> headers) {
        httpFactory.setDefaultRequestProperties(headers == null ? new HashMap<>() : headers);
        MediaItem.Builder builder = new MediaItem.Builder().setUri(url);
        String lower = url.toLowerCase(Locale.ROOT);
        if (lower.contains(".m3u8")) builder.setMimeType(MimeTypes.APPLICATION_M3U8);
        else if (lower.contains(".mpd")) builder.setMimeType(MimeTypes.APPLICATION_MPD);
        player.setMediaItem(builder.build());
        player.prepare();
        player.play();
    }

    private void failPage(int token, PageHolder holder, int message) {
        App.post(() -> {
            if (token != playToken) return;
            holder.binding.pageLoading.setVisibility(View.GONE);
            holder.binding.pageHint.setText(message);
            holder.binding.pageHint.setVisibility(View.VISIBLE);
        });
    }

    private void stopPlayer() {
        playToken++;
        if (player != null) {
            player.stop();
            player.clearMediaItems();
        }
        if (activeHolder != null) {
            activeHolder.binding.player.setPlayer(null);
            activeHolder = null;
        }
    }

    private Vod detailOf(Site site, Vod vod) throws Exception {
        String cacheKey = site.getKey() + AppDatabase.SYMBOL + vod.getId();
        Vod cached = detailCache.get(cacheKey);
        if (cached != null) return cached;
        Result result = SiteApi.detailContent(site.getKey(), vod.getId());
        if (result == null || result.getList().isEmpty()) return null;
        Vod detail = result.getList().get(0);
        detailCache.put(cacheKey, detail);
        return detail;
    }

    private Flag firstFlag(Vod detail) {
        if (detail.getFlags() == null) return null;
        for (Flag flag : detail.getFlags()) if (flag != null && !flag.getEpisodes().isEmpty()) return flag;
        return null;
    }

    private String historyKey(Site site, Vod vod) {
        return site.getKey() + AppDatabase.SYMBOL + vod.getId() + AppDatabase.SYMBOL + VodConfig.getCid();
    }

    private void recordHistory(Site site, Vod detail, Flag flag, Episode episode) {
        try {
            String key = historyKey(site, detail);
            History history = History.find(key);
            if (history == null) {
                history = new History();
                history.setKey(key);
                history.setCid(VodConfig.getCid());
            }
            history.setVodName(detail.getName());
            history.setVodPic(detail.getPic());
            history.setVodFlag(flag.getFlag());
            history.setVodRemarks(episode.getName());
            history.setEpisodeUrl(episode.getUrl());
            history.setCreateTime(System.currentTimeMillis());
            history.save();
        } catch (Exception ignored) {
        }
    }

    // --- page actions ---------------------------------------------------

    private void toggleKeep(int position) {
        if (current == null || position < 0 || position >= feed.size()) return;
        Vod vod = feed.get(position);
        Site site = current;
        String key = historyKey(site, vod);
        Task.executor().submit(() -> {
            boolean kept;
            if (Keep.find(key) != null) {
                Keep.delete(key);
                kept = false;
            } else {
                Keep keep = new Keep();
                keep.setKey(key);
                keep.setCid(VodConfig.getCid());
                keep.setVodPic(vod.getPic());
                keep.setVodName(vod.getName());
                keep.setSiteName(site.getDisplayName());
                keep.setCreateTime(System.currentTimeMillis());
                keep.save();
                kept = true;
            }
            boolean result = kept;
            App.post(() -> {
                PageHolder holder = holderAt(position);
                if (holder != null) holder.binding.railKeep.setCompoundDrawablesWithIntrinsicBounds(0, result ? R.drawable.ic_control_keep_on : R.drawable.ic_control_keep_off, 0, 0);
            });
        });
    }

    private void openDetail(int position) {
        if (current == null || position < 0 || position >= feed.size()) return;
        Vod vod = feed.get(position);
        VideoActivity.start(this, current.getKey(), vod.getId(), vod.getName(), vod.getPic());
    }

    private void showEpisodes(int position) {
        if (current == null || position < 0 || position >= feed.size()) return;
        Vod vod = feed.get(position);
        Site site = current;
        Task.executor().submit(() -> {
            try {
                Vod detail = detailOf(site, vod);
                Flag flag = detail == null ? null : firstFlag(detail);
                if (flag == null) return;
                List<Episode> episodes = flag.getEpisodes();
                if (episodes.isEmpty()) return;
                // 高亮当前在播的那集，弹窗会自动定位到它那一页；新翻到的剧默认播第 1 集。
                int selected = position == currentPage ? Math.min(playingEpisodeIndex, episodes.size() - 1) : 0;
                for (Episode episode : episodes) episode.setSelected(false);
                episodes.get(selected).setSelected(true);
                episodePosition = position;
                episodeList = episodes;
                App.post(() -> EpisodeGridDialog.create().episodes(episodes).tmdbCard(false).show(this));
            } catch (Exception ignored) {
            }
        });
    }

    @Override
    public void onItemClick(Episode item) {
        if (item == null || episodeList == null || episodePosition < 0) return;
        int index = -1;
        for (int i = 0; i < episodeList.size(); i++) {
            Episode episode = episodeList.get(i);
            if (episode != null && episode.getUrl() != null && episode.getUrl().equals(item.getUrl())) {
                index = i;
                break;
            }
        }
        if (index < 0) return;
        loadRetry = 0;
        playEpisode(episodePosition, index);
    }

    /**
     * 当前集播完后自动播下一集：同部剧还有下一集就在视频流内换集播；
     * 已是最后一集就自动滑到下一部剧；已是最后一部则停住。
     */
    private void onVideoEnded() {
        if (mode != Mode.FEED || current == null || currentPage < 0 || currentPage >= feed.size()) return;
        if (activeHolder == null) return;
        int position = currentPage;
        Vod vod = feed.get(position);
        Site site = current;
        Task.executor().submit(() -> {
            try {
                Vod detail = detailOf(site, vod);
                Flag flag = detail == null ? null : firstFlag(detail);
                if (flag == null) return;
                int next = playingEpisodeIndex + 1;
                if (next < flag.getEpisodes().size()) {
                    loadRetry = 0;
                    App.post(() -> playEpisode(position, next));
                } else if (position + 1 < feed.size()) {
                    App.post(() -> {
                        if (position != currentPage) return;
                        mBinding.pager.setCurrentItem(position + 1, true);
                    });
                }
            } catch (Exception ignored) {
            }
        });
    }

    /**
     * 在短剧页当前页的视频流里换集播放，不跳本体播放器。
     * 与 resolve 共用同一套取播放地址逻辑，换集时用 playToken 顶掉未完成的旧请求。
     */
    private void playEpisode(int position, int episodeIndex) {
        if (current == null || position < 0 || position >= feed.size() || position != currentPage) return;
        PageHolder holder = holderAt(position);
        if (holder == null) return;
        Vod vod = feed.get(position);
        Site site = current;
        int token = ++playToken;
        holder.binding.pageLoading.setVisibility(View.VISIBLE);
        holder.binding.pageHint.setVisibility(View.GONE);
        Task.executor().submit(() -> {
            try {
                Vod detail = detailOf(site, vod);
                Flag flag = detail == null ? null : firstFlag(detail);
                if (flag == null || episodeIndex < 0 || episodeIndex >= flag.getEpisodes().size()) {
                    failPage(token, holder, R.string.drama_load_failed);
                    return;
                }
                Episode episode = flag.getEpisodes().get(episodeIndex);
                Result playerResult = SiteApi.playerContent(site.getKey(), flag.getFlag(), episode.getUrl());
                if (playerResult != null && (Integer.valueOf(1).equals(playerResult.getParse()) || Integer.valueOf(1).equals(playerResult.getJx()))) {
                    App.post(() -> {
                        if (token != playToken) return;
                        holder.binding.pageLoading.setVisibility(View.GONE);
                        holder.binding.pageHint.setText(R.string.drama_need_parse);
                        holder.binding.pageHint.setVisibility(View.VISIBLE);
                    });
                    return;
                }
                String url = playerResult == null || playerResult.getUrl() == null ? "" : playerResult.getUrl().v();
                if (TextUtils.isEmpty(url)) {
                    failPage(token, holder, R.string.drama_load_failed);
                    return;
                }
                Map<String, String> headers = playerResult.getHeader();
                recordHistory(site, detail, flag, episode);
                int index = episodeIndex;
                int total = flag.getEpisodes().size();
                App.post(() -> {
                    if (token != playToken) return;
                    playingEpisodeIndex = index;
                    holder.binding.meta.setText(getString(R.string.drama_episode_meta, index + 1, total));
                    playUrl(url, headers);
                });
            } catch (Exception e) {
                failPage(token, holder, R.string.drama_load_failed);
            }
        });
    }

    // --- modes ----------------------------------------------------------

    private void setMode(Mode target) {
        mode = target;
        mBinding.pager.setVisibility(target == Mode.FEED ? View.VISIBLE : View.GONE);
        mBinding.grid.setVisibility(target == Mode.THEATER ? View.VISIBLE : View.GONE);
        mBinding.historyList.setVisibility(target == Mode.HISTORY ? View.VISIBLE : View.GONE);
        mBinding.tabRecommend.setTextColor(target == Mode.FEED ? COLOR_ACCENT : COLOR_TAB);
        mBinding.tabTheater.setTextColor(target == Mode.THEATER ? COLOR_ACCENT : COLOR_TAB);
        mBinding.tabHistory.setTextColor(target == Mode.HISTORY ? COLOR_ACCENT : COLOR_TAB);
        if (target != Mode.FEED && player != null) player.pause();
        if (target == Mode.FEED && player != null && player.getMediaItemCount() > 0 && currentPage >= 0) player.play();
        if (target == Mode.HISTORY) reloadHistory();
    }

    private void reloadHistory() {
        Task.executor().submit(() -> {
            List<History> items = new ArrayList<>();
            try {
                for (History history : History.get()) {
                    String key = history.getKey();
                    if (key == null) continue;
                    for (Site site : sites) {
                        if (key.startsWith(site.getKey() + AppDatabase.SYMBOL)) {
                            items.add(history);
                            break;
                        }
                    }
                }
            } catch (Exception ignored) {
            }
            App.post(() -> historyAdapter.setItems(items));
        });
    }

    private void showState(String text, boolean retry) {
        mBinding.state.setText(text == null ? "" : text);
        mBinding.state.setVisibility(text == null ? View.GONE : View.VISIBLE);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (player != null) player.pause();
    }

    @Override
    protected void onDestroy() {
        if (player != null) player.release();
        super.onDestroy();
    }

    // --- adapters -------------------------------------------------------

    private class PageHolder extends RecyclerView.ViewHolder {
        final ItemDramaPageBinding binding;
        boolean expanded;

        PageHolder(@NonNull ItemDramaPageBinding binding) {
            super(binding.getRoot());
            this.binding = binding;
        }
    }

    private void toggleContent(PageHolder holder) {
        holder.expanded = !holder.expanded;
        holder.binding.content.setMaxLines(holder.expanded ? Integer.MAX_VALUE : 2);
    }

    private class PageAdapter extends RecyclerView.Adapter<PageHolder> {

        @NonNull
        @Override
        public PageHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            ItemDramaPageBinding binding = ItemDramaPageBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false);
            PageHolder holder = new PageHolder(binding);
            binding.railKeep.setOnClickListener(view -> toggleKeep(holder.getBindingAdapterPosition()));
            binding.railDetail.setOnClickListener(view -> toggleContent(holder));
            binding.railEpisodes.setOnClickListener(view -> showEpisodes(holder.getBindingAdapterPosition()));
            binding.pageHint.setOnClickListener(view -> {
                int pos = holder.getBindingAdapterPosition();
                if (pos < 0 || pos != currentPage) return;
                loadRetry = 0;
                playEpisode(pos, playingEpisodeIndex);
            });
            binding.content.setOnClickListener(view -> toggleContent(holder));
            binding.name.setOnClickListener(view -> openDetail(holder.getBindingAdapterPosition()));
            return holder;
        }

        @Override
        public void onBindViewHolder(@NonNull PageHolder holder, int position) {
            Vod vod = feed.get(position);
            holder.binding.player.setPlayer(null);
            holder.binding.poster.setVisibility(View.VISIBLE);
            holder.binding.pageLoading.setVisibility(View.GONE);
            holder.binding.pageHint.setVisibility(View.GONE);
            holder.binding.name.setText(vod.getName());
            holder.binding.meta.setText(vod.getRemarks());
            holder.expanded = false;
            holder.binding.content.setMaxLines(2);
            holder.binding.content.setText("");
            holder.binding.railKeep.setCompoundDrawablesWithIntrinsicBounds(0, R.drawable.ic_control_keep_off, 0, 0);
            ImgUtil.load(vod.getName(), vod.getPic(), holder.binding.poster);
        }

        @Override
        public int getItemCount() {
            return feed.size();
        }
    }

    private class GridAdapter extends RecyclerView.Adapter<GridAdapter.GridHolder> {

        class GridHolder extends RecyclerView.ViewHolder {
            final ItemDramaGridBinding binding;

            GridHolder(@NonNull ItemDramaGridBinding binding) {
                super(binding.getRoot());
                this.binding = binding;
            }
        }

        @NonNull
        @Override
        public GridHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            ItemDramaGridBinding binding = ItemDramaGridBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false);
            GridHolder holder = new GridHolder(binding);
            binding.getRoot().setOnClickListener(view -> {
                int position = holder.getBindingAdapterPosition();
                if (position >= 0) {
                    setMode(Mode.FEED);
                    mBinding.pager.setCurrentItem(position, false);
                }
            });
            return holder;
        }

        @Override
        public void onBindViewHolder(@NonNull GridHolder holder, int position) {
            Vod vod = feed.get(position);
            holder.binding.name.setText(vod.getName());
            holder.binding.remarks.setText(vod.getRemarks());
            ImgUtil.load(vod.getName(), vod.getPic(), holder.binding.poster);
        }

        @Override
        public int getItemCount() {
            return feed.size();
        }
    }

    private class HistoryAdapter extends RecyclerView.Adapter<HistoryAdapter.HistoryHolder> {

        private final List<History> items = new ArrayList<>();
        private final SimpleDateFormat format = new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault());

        class HistoryHolder extends RecyclerView.ViewHolder {
            final ItemDramaHistoryBinding binding;

            HistoryHolder(@NonNull ItemDramaHistoryBinding binding) {
                super(binding.getRoot());
                this.binding = binding;
            }
        }

        void setItems(List<History> list) {
            items.clear();
            items.addAll(list);
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public HistoryHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            ItemDramaHistoryBinding binding = ItemDramaHistoryBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false);
            HistoryHolder holder = new HistoryHolder(binding);
            binding.getRoot().setOnClickListener(view -> {
                int position = holder.getBindingAdapterPosition();
                if (position < 0) return;
                History history = items.get(position);
                String[] parts = history.getKey().split(AppDatabase.SYMBOL);
                if (parts.length >= 2) VideoActivity.start(ShortDramaActivity.this, parts[0], parts[1], history.getVodName(), history.getVodPic());
            });
            return holder;
        }

        @Override
        public void onBindViewHolder(@NonNull HistoryHolder holder, int position) {
            History history = items.get(position);
            holder.binding.name.setText(history.getVodName());
            String siteName = "";
            String[] parts = history.getKey() == null ? new String[0] : history.getKey().split(AppDatabase.SYMBOL);
            if (parts.length >= 1) {
                for (Site site : sites) if (site.getKey().equals(parts[0])) siteName = site.getDisplayName();
                if (TextUtils.isEmpty(siteName)) siteName = parts[0];
            }
            String remarks = history.getVodRemarks() == null ? "" : history.getVodRemarks();
            holder.binding.meta.setText(TextUtils.isEmpty(remarks) ? siteName : siteName + " · " + remarks);
            holder.binding.time.setText(history.getCreateTime() > 0 ? format.format(new Date(history.getCreateTime())) : "");
            ImgUtil.load(history.getVodName(), history.getVodPic(), holder.binding.poster);
        }

        @Override
        public int getItemCount() {
            return items.size();
        }
    }
}
