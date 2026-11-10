package com.fongmi.android.tv.drama;

import android.text.TextUtils;

import com.fongmi.android.tv.api.config.VodConfig;
import com.fongmi.android.tv.bean.Site;
import com.fongmi.android.tv.setting.Setting;
import com.github.catvod.utils.Prefers;

import java.util.ArrayList;
import java.util.List;

/**
 * Detection for the short-drama section, modeled on the behaviour Cook
 * verified in PeekPro: when the imported config carries sites whose names
 * mark them as short-drama sources, the shell surfaces them in a dedicated
 * bottom-bar tab. A site counts when its name or key contains 短剧 / 漫短 /
 * 漫剧 / [短], or when the existing short-drama site policy already enables
 * it. This only organises the user's own config; it provides no content.
 */
public final class DramaSites {

    private static final String PREF_SITE = "drama_tab_site";
    private static final String[] KEYWORDS = {"短剧", "漫短", "漫剧", "[短]"};

    private DramaSites() {
    }

    public static boolean isDramaSite(Site site) {
        if (site == null || site.isEmpty()) return false;
        String name = site.getName();
        String key = site.getKey();
        for (String keyword : KEYWORDS) {
            if (!TextUtils.isEmpty(name) && name.contains(keyword)) return true;
            if (!TextUtils.isEmpty(key) && key.contains(keyword)) return true;
        }
        return Setting.isShortDramaSiteEnabled(key, name == null ? "" : name);
    }

    public static List<Site> detect() {
        List<Site> result = new ArrayList<>();
        for (Site site : VodConfig.get().getSites()) if (isDramaSite(site)) result.add(site);
        return result;
    }

    public static boolean hasDramaSites() {
        for (Site site : VodConfig.get().getSites()) if (isDramaSite(site)) return true;
        return false;
    }

    /** The site the section should open with: the remembered one, else the first detected. */
    public static Site current(List<Site> sites) {
        if (sites == null || sites.isEmpty()) return null;
        String saved = Prefers.getString(PREF_SITE, "");
        if (!TextUtils.isEmpty(saved)) {
            for (Site site : sites) if (saved.equals(site.getKey())) return site;
        }
        return sites.get(0);
    }

    public static void saveCurrent(String key) {
        Prefers.put(PREF_SITE, key == null ? "" : key);
    }
}
