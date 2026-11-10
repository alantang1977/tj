package com.fongmi.android.tv.api.loader;

import com.fongmi.android.tv.App;
import com.fongmi.quickjs.crawler.Loader;
import com.fongmi.quickjs.utils.Module;
import com.github.catvod.crawler.Spider;
import com.github.catvod.crawler.SpiderDebug;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class JsLoader {

    private final ConcurrentHashMap<String, Spider> spiders;
    private final Loader loader;
    private volatile String recent;

    public JsLoader() {
        spiders = new ConcurrentHashMap<>();
        loader = new Loader();
    }

    public void clear() {
        try {
            SpiderCleanup.destroy("js-loader", spiders);
            Module.get().clear();
        } finally {
            spiders.clear();
            recent = null;
        }
    }

    public void setRecent(String recent) {
        setRecent("", recent);
    }

    /**
     * recent 必须与 {@link #getSpider(String, String, String, String, String)} 的槽位键同形：
     * spiders 按 {@link BaseLoader#slot(String, String)} 建键，而 {@link #proxy} 又拿 recent 去查
     * 同一张表。recent 若仍是裸 siteKey，桥接配置的 ?do=js 要么查不到自己（调用方拿到 500），
     * 要么命中激活配置里同名站源的实例。空命名空间等于改动前的裸 key。
     */
    public void setRecent(String namespace, String key) {
        this.recent = BaseLoader.slot(namespace, key);
    }

    /** 缓存键可能带命名空间前缀；对外的"活动插件"仍按脚本自己的 key 报告。 */
    public java.util.Set<String> activeKeys() {
        return com.fongmi.android.tv.api.loader.BaseLoader.baseKeys(spiders.keySet());
    }

    public Spider getSpider(String key, String api, String ext, String jar) {
        return getSpider("", key, api, ext, jar);
    }

    /**
     * 按 (命名空间, siteKey) 取 spider：桥接解析非激活配置时不能写进激活配置的槽位，
     * 否则 A、B 两个配置的同名站点会互相串源。空命名空间等于原来的行为。
     *
     * <p>初始化失败不缓存：SpiderInit.load 失败时返回 null，不建映射，下次访问会重试。
     * 改动前失败一次就把 SpiderNull 写进缓存，之后一直空页面，只有加载配置清掉
     * 全部 loader 缓存才能恢复——本地源 .js 没配 spider.jar 时一旦首次初始化失败
     * 就再也出不了数据，而填了带 spider 的配置反而能好（配置加载清了缓存）。
     * .py 不走这里，所以 .py 没这个问题。
     */
    public Spider getSpider(String namespace, String key, String api, String ext, String jar) {
        return SpiderInit.load(spiders, BaseLoader.slot(namespace, key),
                () -> loader.spider(api, BaseLoader.get().dex(jar)), spider -> {
                    spider.siteKey = key;
                    spider.init(App.get(), ext);
                }, e -> {
                    SpiderDebug.log("JsLoader", "JS spider init failed: key=%s api=%s", key, api);
                    SpiderDebug.log("JsLoader", e);
                    e.printStackTrace();
                });
    }

    public Object[] proxy(Map<String, String> params) throws Exception {
        if (recent == null) return null;
        Spider spider = spiders.get(recent);
        return spider != null ? spider.proxy(params) : null;
    }
}
