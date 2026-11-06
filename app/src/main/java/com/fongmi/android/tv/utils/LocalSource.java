package com.fongmi.android.tv.utils;

import android.text.TextUtils;

import com.fongmi.android.tv.App;
import com.fongmi.android.tv.bean.Site;
import com.github.catvod.utils.Json;
import com.github.catvod.utils.Path;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 本地源（魔影式）：扫描本地文件夹里的源文件，存进应用内部目录的 sites.json，
 * 配置加载时直接追加到当前点播配置的站点列表末尾，不生成独立配置文件。
 * <p>
 * 文件名 / 父目录名里的 [标签] 会变成站点分类，写进站点名：名字┃[分类]。
 * [直播] 的文件不收进站点；[密] 的文件默认不收，打开“显示密源”后才收。
 */
public class LocalSource {

    /** 扫描收录的文件后缀白名单（与魔影一致）。 */
    public static final List<String> EXTENSIONS = Arrays.asList("wv.js", "cat.js", "xbpq.json", "xyq.json", "php", "html", "js", "py", "json");
    /** 扫描时跳过的目录名（与魔影一致）。 */
    public static final Set<String> BLOCKED_DIRS = new HashSet<>(Arrays.asList("Android", ".thumbnails", "DCIM", "Pictures", "Movies", "Documents", "Music", "Ringtones", "Notifications", "Alarms", "PODCASTS", "Bluetooth", "WhatsApp", "tencent", "WeChat", "QQBrowser", "KuGou", "NetEaseCloudMusic", "Douyin", "Sina", "BaiduNetdisk", "Bilibili", "Logs", "Temp", "pids", "lxserver", "EnvFiles", "danmu_api", "examples", "migu_video", "musicfree", "musicSdk", "data", "controllers", "node_modules", "docs", "config", "lib", "libs", "libs_drpy", "apps", "public", "plugins", "utils", "scripts", "json", "jx", "webdav-files", "webdav", "install", ".github"));

    /** [标签] 到分类名的映射（与魔影一致）。 */
    public static final Map<String, String> CATEGORIES = new LinkedHashMap<>();

    static {
        CATEGORIES.put("[直播]", "直播");
        CATEGORIES.put("[书]", "小说");
        CATEGORIES.put("[画]", "漫画");
        CATEGORIES.put("[听]", "音乐");
        CATEGORIES.put("[短]", "短剧");
        CATEGORIES.put("[剧]", "影视");
        CATEGORIES.put("[密]", "密密");
    }

    private static List<Site> sites;

    private static File getDir() {
        return new File(Path.files(), "localSource");
    }

    private static File getFile() {
        return new File(getDir(), "sites.json");
    }

    /** 读 sites.json，读不到返回空对象。 */
    public static synchronized JsonObject getSettings() {
        try {
            File file = getFile();
            if (!file.exists()) return new JsonObject();
            JsonElement element = App.gson().fromJson(Path.read(file), JsonElement.class);
            return element != null && element.isJsonObject() ? element.getAsJsonObject() : new JsonObject();
        } catch (Exception e) {
            return new JsonObject();
        }
    }

    /** 写 sites.json。 */
    public static synchronized void saveSettings(JsonObject object) {
        try {
            File dir = getDir();
            if (dir.exists() || dir.mkdirs()) Path.write(getFile(), App.gson().toJson(object).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    public static boolean isShowSecret() {
        JsonObject object = getSettings();
        return object.has("showSecret") && object.get("showSecret").getAsBoolean();
    }

    public static void setShowSecret(boolean show) {
        JsonObject object = getSettings();
        object.addProperty("showSecret", show);
        saveSettings(object);
    }

    public static String getScanDir() {
        return Json.safeString(getSettings(), "scanDir");
    }

    public static void setScanDir(String dir) {
        JsonObject object = getSettings();
        object.addProperty("scanDir", dir == null ? "" : dir);
        saveSettings(object);
    }

    public static String getPhpRoot() {
        return Json.safeString(getSettings(), "phpRoot");
    }

    public static void setPhpRoot(String root) {
        JsonObject object = getSettings();
        object.addProperty("phpRoot", root == null ? "" : root);
        saveSettings(object);
    }

    /** 本地文件解析的根目录：优先用 PHP 根目录，否则用上次扫描目录。 */
    public static String getRoot() {
        String phpRoot = getPhpRoot();
        return !phpRoot.isEmpty() ? phpRoot : getScanDir();
    }

    /** 站点名里是不是密源（名字里带 ┃[密密]）。 */
    public static boolean isSecret(Site site) {
        if (site == null || site.getName() == null) return false;
        int start = site.getName().lastIndexOf("┃[");
        if (start < 0) return false;
        int end = site.getName().indexOf("]", start);
        return end > start && "密密".equals(site.getName().substring(start + 2, end));
    }

    /** 读出本地源站点列表（api/ext 按当前本机服务端口换成本机地址；密源未开开关时过滤掉）。 */
    public static synchronized List<Site> getSites() {
        if (sites != null) return new ArrayList<>(sites);
        // 旧版扫进来的 .py 条目 api 是 csp_<文件名>，走 JarLoader 读不出数据：
        // 首次加载时把它改回文件地址（老条目不用重扫也能好）。
        migrateStalePyApi();
        boolean showSecret = isShowSecret();
        List<Site> result = new ArrayList<>();
        List<JsonElement> array = Json.safeListElement(getSettings(), "sites");
        for (JsonElement element : array) {
            if (!element.isJsonObject()) continue;
            Site site = siteFrom(element.getAsJsonObject());
            if (site == null || site.getKey().isEmpty()) continue;
            if (!showSecret && isSecret(site)) continue;
            result.add(site);
        }
        sites = result;
        return new ArrayList<>(result);
    }

    /** 清掉内存缓存，下次 getSites() 重新读文件。 */
    public static synchronized void invalidate() {
        sites = null;
    }

    /** 把站点列表写回 sites.json 并更新缓存。 */
    public static synchronized void saveSites(List<Site> list) {
        JsonArray array = new JsonArray();
        for (Site site : list) array.add(siteToJson(site));
        JsonObject object = getSettings();
        object.add("sites", array);
        saveSettings(object);
        sites = new ArrayList<>(list);
    }

    /** 清空本地源（删掉全部站点）。 */
    public static synchronized void clear() {
        saveSites(new ArrayList<>());
    }

    private static Site siteFrom(JsonObject object) {
        try {
            Site site = new Site();
            site.setKey(Json.safeString(object, "key"));
            site.setName(Json.safeString(object, "name"));
            site.setApi(UrlUtil.convert(Json.safeString(object, "api")));
            site.setExt(UrlUtil.convert(Json.safeString(object, "ext")));
            site.setJar(Json.safeString(object, "jar"));
            site.setHomePage(UrlUtil.convert(Json.safeString(object, "homePage")));
            site.setType(object.has("type") ? object.get("type").getAsInt() : 3);
            site.setSearchable(object.has("searchable") ? object.get("searchable").getAsInt() : 1);
            if (object.has("quickSearch")) site.setQuickSearch(object.get("quickSearch").getAsInt());
            site.setChangeable(object.has("changeable") ? object.get("changeable").getAsInt() : 1);
            site.setHide(object.has("hide") ? object.get("hide").getAsInt() : 0);
            return site;
        } catch (Exception e) {
            return null;
        }
    }

    private static JsonObject siteToJson(Site site) {
        JsonObject object = new JsonObject();
        put(object, "key", site.getKey());
        put(object, "name", site.getName());
        put(object, "api", site.getApi());
        put(object, "ext", site.getExt());
        put(object, "jar", site.getJar());
        put(object, "homePage", site.getHomePage());
        if (site.getType() != null) object.addProperty("type", site.getType());
        if (site.getSearchable() != null) object.addProperty("searchable", site.getSearchable());
        if (site.getQuickSearch() != null) object.addProperty("quickSearch", site.getQuickSearch());
        if (site.getChangeable() != null) object.addProperty("changeable", site.getChangeable());
        if (site.getHide() != null) object.addProperty("hide", site.getHide());
        return object;
    }

    private static void put(JsonObject object, String key, String value) {
        if (value != null) object.addProperty(key, value);
    }

    /** 扫描一个目录（递归），返回新导入的站点数。 */
    public static int scan(File dir) {
        if (dir == null || !dir.isDirectory()) return 0;
        List<File> files = new ArrayList<>();
        collect(dir, files);
        return parse(files, isShowSecret());
    }

    /** 扫描指定的单个文件，返回新导入的站点数。 */
    public static int scanFiles(List<File> files) {
        return parse(files, isShowSecret());
    }

    /** 递归收集白名单后缀的文件，跳过屏蔽目录。 */
    private static void collect(File dir, List<File> out) {
        File[] children = dir.listFiles();
        if (children == null) return;
        for (File child : children) {
            if (child.isDirectory()) {
                if (!BLOCKED_DIRS.contains(child.getName())) collect(child, out);
            } else if (isSupported(child.getName())) {
                out.add(child);
            }
        }
    }

    /** 文件名后缀在不在白名单里（xbpq/xyq 按 .json 归一，wv.js 按 .js 归一）。 */
    public static boolean isSupported(String name) {
        if (name == null) return false;
        String lower = name.toLowerCase(Locale.ROOT);
        String ext = extension(lower);
        return EXTENSIONS.contains(ext) || EXTENSIONS.contains(normalizeExt(lower));
    }

    private static String extension(String lower) {
        int dot = lower.lastIndexOf('.');
        return dot < 0 ? "" : lower.substring(dot + 1);
    }

    /** xbpq.json/xyq.json 这类带两段后缀的，取倒数第二段 + 最后一 段拼起来比对。 */
    private static String normalizeExt(String lower) {
        String[] parts = lower.split("\\.");
        if (parts.length < 3) return extension(lower);
        return parts[parts.length - 2] + "." + parts[parts.length - 1];
    }

    /** 把文件解析成站点并合并进现有列表，返回新导入的站点数。 */
    private static synchronized int parse(List<File> files, boolean showSecret) {
        if (files == null || files.isEmpty()) return 0;
        List<Site> current = new ArrayList<>(getSitesRaw());
        Map<String, Site> byKey = new LinkedHashMap<>();
        for (Site site : current) byKey.put(site.getKey(), site);
        int added = 0;
        for (File file : files) {
            for (Site site : parseFile(file, showSecret)) {
                String key = site.getKey();
                Site old = byKey.get(key);
                if (old != null && old.getApi().equals(site.getApi())) continue;
                if (old != null && isStaleCspApi(old.getApi())) {
                    // 旧条目是坏的 csp_ 写法：直接刷新为新解析的结果，不产生 _1 副本。
                    site.setKey(key);
                    byKey.put(key, site);
                    added++;
                    continue;
                }
                int suffix = 1;
                while (byKey.containsKey(key)) key = site.getKey() + "_" + (suffix++);
                site.setKey(key);
                byKey.put(key, site);
                added++;
            }
        }
        if (added > 0) saveSites(new ArrayList<>(byKey.values()));
        return added;
    }

    /** 真的 Jar 蜘蛛类（xbpq/xyq/wv.js 用的），不是坏的 csp_ 写法，别动。 */
    private static boolean isKnownCspApi(String api) {
        return "csp_XYQHiker".equals(api) || "csp_WvSpider".equals(api) || "csp_XBPQ".equals(api) || "csp_FileSpider".equals(api);
    }

    /** 坏的 csp_ 写法：csp_ 开头又不是真的 Jar 蜘蛛类（旧版 .py 扫进来就是这个）。 */
    private static boolean isStaleCspApi(String api) {
        return api != null && api.startsWith("csp_") && !isKnownCspApi(api);
    }

    /** 修旧版扫进来的 .py 坏条目：api 是 csp_<文件名> 的改回文件地址，ext 清掉。 */
    private static void migrateStalePyApi() {
        List<Site> raw = getSitesRaw();
        if (raw.isEmpty()) return;
        boolean changed = false;
        for (Site site : raw) {
            if (!isStaleCspApi(site.getApi())) continue;
            String pyUrl = toFileUrl(site.getExt());
            // ext 必须是 .py 文件地址才算数，别把别的后缀文件当成蜘蛛。
            if (pyUrl != null && !pyUrl.toLowerCase(Locale.ROOT).endsWith(".py")) pyUrl = null;
            if (pyUrl == null) {
                String scanDir = getScanDir();
                File root = TextUtils.isEmpty(scanDir) ? null : new File(scanDir);
                File file = findPyFile(root, site.getKey() + ".py");
                if (file != null) pyUrl = fileUrl(file);
            }
            if (pyUrl == null) continue;
            site.setApi(pyUrl);
            site.setExt("");
            changed = true;
        }
        if (changed) {
            saveSites(raw);
            // saveSites 会把没换地址的原始列表写进缓存，这里必须清掉，
            // 后面 getSites() 才重新读盘换成本机地址。
            sites = null;
        }
    }

    /** file:// 地址原样用；本机地址 http://127.0.0.1:端口/file/路径 还原成 file:// 路径；其余返回 null。 */
    private static String toFileUrl(String url) {
        if (url == null) return null;
        if (url.startsWith("file://")) return url;
        int i = url.indexOf("/file/");
        if (url.startsWith("http://127.0.0.1:") && i > 0) return "file://" + url.substring(i + 6);
        return null;
    }

    /** 在扫描目录下递归找指定文件名的 .py（跳过屏蔽目录）。 */
    private static File findPyFile(File dir, String name) {
        if (dir == null || !dir.isDirectory()) return null;
        File[] children = dir.listFiles();
        if (children == null) return null;
        for (File child : children) {
            if (child.isDirectory()) {
                if (!BLOCKED_DIRS.contains(child.getName())) {
                    File found = findPyFile(child, name);
                    if (found != null) return found;
                }
            } else if (child.getName().equalsIgnoreCase(name)) {
                return child;
            }
        }
        return null;
    }

    /** 读 sites.json 里的原始站点（不过滤密源、不换地址），供合并时用。 */
    private static List<Site> getSitesRaw() {
        List<Site> result = new ArrayList<>();
        for (JsonElement element : Json.safeListElement(getSettings(), "sites")) {
            if (!element.isJsonObject()) continue;
            Site site = siteFromRaw(element.getAsJsonObject());
            if (site != null && !site.getKey().isEmpty()) result.add(site);
        }
        return result;
    }

    private static Site siteFromRaw(JsonObject object) {
        try {
            Site site = new Site();
            site.setKey(Json.safeString(object, "key"));
            site.setName(Json.safeString(object, "name"));
            site.setApi(Json.safeString(object, "api"));
            site.setExt(Json.safeString(object, "ext"));
            site.setJar(Json.safeString(object, "jar"));
            site.setHomePage(Json.safeString(object, "homePage"));
            site.setType(object.has("type") ? object.get("type").getAsInt() : 3);
            site.setSearchable(object.has("searchable") ? object.get("searchable").getAsInt() : 1);
            if (object.has("quickSearch")) site.setQuickSearch(object.get("quickSearch").getAsInt());
            site.setChangeable(object.has("changeable") ? object.get("changeable").getAsInt() : 1);
            site.setHide(object.has("hide") ? object.get("hide").getAsInt() : 0);
            return site;
        } catch (Exception e) {
            return null;
        }
    }

    /** 把一个文件解析成站点（一个配置文件可能解析出多个站点）。 */
    private static List<Site> parseFile(File file, boolean showSecret) {
        List<Site> result = new ArrayList<>();
        String name = file.getName();
        String parent = file.getParentFile() == null ? "" : file.getParentFile().getName();
        if (containsTag(name, "[直播]") || containsTag(parent, "[直播]")) return result;
        if (!showSecret && (containsTag(name, "[密]") || containsTag(parent, "[密]"))) return result;
        String lower = name.toLowerCase(Locale.ROOT);
        String base = stripExtension(name);
        String category = categoryOf(parent, base);
        String display = base + "┃[" + category + "]";
        boolean isXbpq = isInCategoryDir(file, "pq") || "xbpq.json".equals(normalizeExt(lower));
        boolean isXyq = isInCategoryDir(file, "yq") || "xyq.json".equals(normalizeExt(lower));
        boolean isCat = isInCategoryDir(file, "cat");
        if (isXbpq || isXyq) {
            result.add(newSite(base, display, 0, "csp_XYQHiker", fileUrl(file), ""));
        } else if ("cat.js".equals(lower) || ("js".equals(extension(lower)) && isCat)) {
            result.add(newSite(base, display, 3, fileUrl(file), "", ""));
        } else if ("js".equals(extension(lower)) || "wv.js".equals(normalizeExt(lower))) {
            if ("wv.js".equals(normalizeExt(lower))) result.add(newSite(base, display, 3, "csp_WvSpider", fileUrl(file), ""));
            else result.add(newSite(base, display, 3, fileUrl(file), "", ""));
        } else if ("php".equals(extension(lower))) {
            Site site = newSite(base, display, 4, fileUrl(file), file.getAbsolutePath(), "");
            site.setSearchable(0);
            site.setQuickSearch(0);
            result.add(site);
        } else if ("py".equals(extension(lower))) {
            // 魔影同款：api 必须是文件地址（含 .py），BaseLoader 才走 PyLoader；
            // 之前写成 csp_<文件名> 会被当成 Java 蜘蛛走 JarLoader，类不存在就全空。
            result.add(newSite(base, display, 3, fileUrl(file), "", ""));
        } else if ("html".equals(extension(lower))) {
            result.add(newSite(base, display, 3, fileUrl(file), fileUrl(file), ""));
        } else if ("json".equals(extension(lower)) || "txt".equals(extension(lower))) {
            result.addAll(parseConfigFile(file));
        }
        return result;
    }

    private static Site newSite(String key, String name, int type, String api, String ext, String jar) {
        Site site = new Site();
        site.setKey(key);
        site.setName(name);
        site.setType(type);
        site.setApi(api);
        site.setExt(ext);
        site.setJar(jar);
        site.setSearchable(1);
        site.setChangeable(1);
        site.setHide(0);
        return site;
    }

    /** .json/.txt 当配置文件解析：有 sites 数组就提站点，单个站点对象就直接收。 */
    private static List<Site> parseConfigFile(File file) {
        List<Site> result = new ArrayList<>();
        try {
            JsonElement element = App.gson().fromJson(Path.read(file), JsonElement.class);
            if (element == null) return result;
            if (element.isJsonObject() && element.getAsJsonObject().has("sites")) {
                for (JsonElement item : Json.safeListElement(element.getAsJsonObject(), "sites")) {
                    if (!item.isJsonObject()) continue;
                    Site site = siteFromRaw(item.getAsJsonObject());
                    if (site != null && !site.getKey().isEmpty()) result.add(site);
                }
            } else if (element.isJsonObject() && element.getAsJsonObject().has("key")) {
                Site site = siteFromRaw(element.getAsJsonObject());
                if (site != null && !site.getKey().isEmpty()) result.add(site);
            }
        } catch (Exception ignored) {
        }
        return result;
    }

    private static String fileUrl(File file) {
        return "file://" + file.getAbsolutePath();
    }

    private static String stripExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private static boolean containsTag(String text, String tag) {
        return text != null && text.contains(tag);
    }

    /** 从父目录名或文件名里找 [标签] 对应的分类，找不到默认“综合”。 */
    private static String categoryOf(String parent, String base) {
        for (Map.Entry<String, String> entry : CATEGORIES.entrySet()) {
            if (containsTag(parent, entry.getKey()) || containsTag(base, entry.getKey())) return entry.getValue();
        }
        return "综合";
    }

    /** 文件是不是在某类目录里（PQ类/YQ类/cat类，往上找父目录）。 */
    private static boolean isInCategoryDir(File file, String kind) {
        File parent = file.getParentFile();
        while (parent != null) {
            String lower = parent.getName().toLowerCase(Locale.ROOT);
            if ("pq".equals(kind) && (lower.equals("pq类") || lower.contains("pq类") || lower.equals("xbpq") || lower.equals("xbpq类"))) return true;
            if ("yq".equals(kind) && (lower.equals("yq类") || lower.contains("yq类") || lower.equals("xyq") || lower.equals("xyq类"))) return true;
            if ("cat".equals(kind) && (lower.equals("cat") || lower.contains("cat类") || lower.contains("cat源"))) return true;
            parent = parent.getParentFile();
        }
        return false;
    }

    /** 站点列表按分类分组后的分类名（“全部”在最前面）。 */
    public static List<String> categoriesOf(List<Site> list) {
        List<String> result = new ArrayList<>();
        result.add("全部");
        for (Site site : list) {
            String category = categoryOfName(site.getName());
            if (!result.contains(category)) result.add(category);
        }
        return result;
    }

    private static String categoryOfName(String name) {
        if (name == null) return "综合";
        int start = name.lastIndexOf("┃[");
        if (start < 0) return "综合";
        int end = name.indexOf("]", start);
        return end > start ? name.substring(start + 2, end) : "综合";
    }

    /** 按分类 + 搜索词过滤站点列表。 */
    public static List<Site> filter(List<Site> list, String category, String keyword) {
        List<Site> result = new ArrayList<>();
        for (Site site : list) {
            if (!TextUtils.isEmpty(category) && !"全部".equals(category) && !categoryOfName(site.getName()).equals(category)) continue;
            if (!TextUtils.isEmpty(keyword) && !site.getName().toLowerCase(Locale.ROOT).contains(keyword.toLowerCase(Locale.ROOT))) continue;
            result.add(site);
        }
        return result;
    }
}
