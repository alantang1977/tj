package com.fongmi.android.tv.setting;

/**
 * 各 flavor 默认内置经典壁纸（wallpaper_1/2/3）的循环顺序。
 * TV(leanback)：wallpaper_1 -> wallpaper_3 -> wallpaper_2。
 * 由 Setting.buildDefaultWalls() 拼到默认壁纸列表最前，设计壁纸顺序与功能保持不变。
 * 该类按 flavor 各提供一份（main 共享代码按编译 flavor 取对应顺序）。
 */
final class WallFlavor {

    private WallFlavor() {
    }

    static int[] classicIds() {
        return new int[]{Setting.WALL_GREEN, Setting.WALL_CLASSIC_3, Setting.WALL_CLASSIC_2};
    }
}
