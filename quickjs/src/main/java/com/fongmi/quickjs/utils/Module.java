package com.fongmi.quickjs.utils;

import android.text.TextUtils;
import android.util.LruCache;

import com.github.catvod.net.OkHttp;
import com.github.catvod.utils.Asset;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public class Module {

    private static final int MAX_SIZE = 50;
    private final LruCache<String, String> cache;

    public Module() {
        cache = new LruCache<>(MAX_SIZE);
    }

    public static Module get() {
        return Loader.INSTANCE;
    }

    public String fetch(String name) {
        String content = cache.get(name);
        if (!TextUtils.isEmpty(content)) return content;
        if (name.startsWith("http")) {
            // 本机服务地址先直接读盘（回环下载不可靠，.py 已证实会失败），读不到再走 HTTP 下载。
            content = readLocalFile(name);
            if (content == null) content = OkHttp.string(name);
            cache.put(name, content);
        }
        else if (name.startsWith("assets")) cache.put(name, content = Asset.read(name));
        else if (name.startsWith("lib/")) cache.put(name, content = Asset.read("js/" + name));
        else if (name.startsWith("file://")) {
            content = readFile(name);
            if (content != null) cache.put(name, content);
        }
        return content;
    }

    /** 本机服务地址（http://127.0.0.1:端口/file/绝对路径）直接读盘，读不到返回 null 再走 HTTP。 */
    private String readLocalFile(String url) {
        try {
            if (!url.startsWith("http://127.0.0.1:") && !url.startsWith("http://localhost:")) return null;
            int i = url.indexOf("/file/");
            if (i < 0) return null;
            File file = new File(url.substring(i + 6));
            if (!file.exists()) return null;
            return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }

    /** file:// 地址直接读盘。 */
    private String readFile(String url) {
        try {
            String path = url.startsWith("file://") ? url.substring("file://".length()) : url.substring("file:/".length());
            File file = new File(path);
            if (!file.exists()) return null;
            return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }

    public void clear() {
        cache.evictAll();
    }

    private static class Loader {
        static volatile Module INSTANCE = new Module();
    }
}
