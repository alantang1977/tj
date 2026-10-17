package com.fongmi.android.tv.api.loader;

import android.text.TextUtils;

import com.fongmi.android.tv.App;
import com.fongmi.chaquo.Loader;
import com.github.catvod.crawler.Spider;
import com.github.catvod.crawler.SpiderDebug;
import com.github.catvod.crawler.SpiderNull;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class PyLoader {

    private static final String PY_TAG = "python-spider";

    private final ConcurrentHashMap<String, Spider> spiders;
    private final Loader loader;
    private volatile String recent;

    public PyLoader() {
        spiders = new ConcurrentHashMap<>();
        loader = new Loader();
    }

    public void clear() {
        try {
            SpiderCleanup.destroy("py-loader", spiders);
        } finally {
            spiders.clear();
            recent = null;
        }
    }

    public void setRecent(String recent) {
        this.recent = recent;
    }

    public java.util.Set<String> activeKeys() {
        return java.util.Set.copyOf(spiders.keySet());
    }

    public Spider getSpider(String key, String api, String ext) {
        return spiders.computeIfAbsent(key, k -> {
            try {
                Spider spider = loader.spider(api);
                spider.siteKey = key;
                spider.init(App.get(), normalizeExt(ext));
                return spider;
            } catch (Throwable e) {
                // A failed bridge init is otherwise hard to attribute: SpiderNull then
                // returns "" for every method, so home/category/search just render empty.
                // Record it under the python-spider tag (already routed to the NETWORK
                // category) and name the callable that failed, because the stack alone
                // does not tell whether it was init(), getDependence() or the import.
                SpiderDebug.log(PY_TAG, "init failed key=%s api=%s error=%s:%s", key, api, e.getClass().getName(), e.getMessage());
                SpiderDebug.log(PY_TAG, e);
                // SpiderDebug.log() is gated on DebugLogStore.acceptsTag(), which is false
                // whenever 调试日志 is off (the default).  Relying on it alone would make a
                // failed init invisible in Logcat even though this catch is the only place
                // that explains an all-empty site.  Keep the unconditional channel too, as
                // the sibling JsLoader does for its own init failure.
                e.printStackTrace();
                return new SpiderNull();
            }
        });
    }

    private String normalizeExt(String ext) {
        String value = TextUtils.isEmpty(ext) ? "" : ext.trim();
        // Many live Python spiders treat ext as an option object and call .get().
        // TV-style configs commonly express an empty extension as [], which would
        // otherwise deserialize to a list and crash those spiders during init.
        return "[]".equals(value) ? "{}" : ext;
    }

    public Object[] proxy(Map<String, String> params) throws Exception {
        if (recent == null) return null;
        Spider spider = spiders.get(recent);
        return spider != null ? spider.proxy(params) : null;
    }
}
