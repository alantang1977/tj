package com.fongmi.android.tv.ui.dialog;

import android.content.Intent;
import android.text.TextUtils;
import android.view.View;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentActivity;
import androidx.viewbinding.ViewBinding;

import com.fongmi.android.tv.App;
import com.fongmi.android.tv.R;
import com.fongmi.android.tv.api.config.VodConfig;
import com.fongmi.android.tv.bean.Config;
import com.fongmi.android.tv.bean.Site;
import com.fongmi.android.tv.databinding.DialogLocalSourceBinding;
import com.fongmi.android.tv.event.ConfigEvent;
import com.fongmi.android.tv.impl.Callback;
import com.fongmi.android.tv.theme.WebHtvAlertDialogBuilder;
import com.fongmi.android.tv.ui.adapter.LocalSourceAdapter;
import com.fongmi.android.tv.ui.custom.CustomTextListener;
import com.fongmi.android.tv.utils.FileChooser;
import com.fongmi.android.tv.utils.LocalSource;
import com.fongmi.android.tv.utils.Notify;
import com.fongmi.android.tv.utils.ResUtil;
import com.github.catvod.utils.Path;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * 本地源弹窗（魔影式）：选文件夹/文件扫描成本地源，列表里可搜索、按分类过滤、
 * 全选/反选/删除/清空，点一个源切过去，密源开关控制 [密] 的源显不显示。
 */
public class LocalSourceDialog extends BaseAlertDialog implements LocalSourceAdapter.OnClickListener {

    private DialogLocalSourceBinding binding;
    private LocalSourceAdapter adapter;
    private List<Site> all = new ArrayList<>();
    private String category = "全部";
    private String keyword = "";
    private boolean scanning;
    private int pickMode;

    private static final int PICK_DIR = 0;
    private static final int PICK_FILE = 1;
    private static final int PICK_PHP_ROOT = 2;
    private static final int PICK_DIR_REPLACE = 3;

    public static LocalSourceDialog create() {
        return new LocalSourceDialog();
    }

    public void show(FragmentActivity activity) {
        show(activity.getSupportFragmentManager(), "LocalSourceDialog");
    }

    public void show(Fragment fragment) {
        show(fragment.getChildFragmentManager(), "LocalSourceDialog");
    }

    private boolean moreExpanded;

    private final ActivityResultLauncher<Intent> launcher = registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
        if (result.getData() == null || result.getData().getData() == null) return;
        String path = FileChooser.getPersistentPathFromUri(result.getData().getData());
        if (TextUtils.isEmpty(path)) return;
        if (pickMode == PICK_DIR) {
            LocalSource.setScanDir(path);
            refreshScanDir();
            scanDir(new File(path));
        } else if (pickMode == PICK_DIR_REPLACE) {
            // 更换文件夹：旧文件夹扫出来的源不再适用，先清空再扫新文件夹，免得旧源一直留在列表里。
            LocalSource.setScanDir(path);
            LocalSource.clear();
            refreshScanDir();
            scanDir(new File(path));
        } else if (pickMode == PICK_FILE) {
            File file = new File(path);
            if (!LocalSource.isSupported(file.getName())) {
                Notify.show(R.string.local_source_bad_ext);
                return;
            }
            scanFiles(List.of(file));
        } else if (pickMode == PICK_PHP_ROOT) {
            LocalSource.setPhpRoot(path);
            refreshPhpRoot();
            Notify.show(R.string.local_source_php_hint);
        }
    });

    @Override
    protected ViewBinding getBinding() {
        return binding = DialogLocalSourceBinding.inflate(getLayoutInflater());
    }

    @Override
    protected MaterialAlertDialogBuilder getBuilder() {
        return new WebHtvAlertDialogBuilder(requireActivity(), R.style.ThemeOverlay_WebHTV_Dialog).setTitle(R.string.local_source).setView(getBinding().getRoot());
    }

    @Override
    protected void initView() {
        adapter = new LocalSourceAdapter(this);
        binding.sites.setAdapter(adapter);
        binding.search.addTextChangedListener(new CustomTextListener() {
            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                keyword = s == null ? "" : s.toString();
                refreshList();
            }
        });
        binding.pick.setOnClickListener(v -> {
            pickMode = PICK_DIR;
            FileChooser.from(launcher).showDirectory();
        });
        binding.changeDir.setOnClickListener(v -> {
            pickMode = PICK_DIR_REPLACE;
            FileChooser.from(launcher).showDirectory();
        });
        binding.pickFile.setOnClickListener(v -> {
            pickMode = PICK_FILE;
            FileChooser.from(launcher).show();
        });
        binding.scanAll.setOnClickListener(v -> scanAll());
        binding.selectAll.setOnClickListener(v -> adapter.selectAll());
        binding.invert.setOnClickListener(v -> adapter.invert());
        binding.remove.setOnClickListener(v -> removeSelected());
        binding.clear.setOnClickListener(v -> clearAll());
        binding.pickPhpRoot.setOnClickListener(v -> {
            pickMode = PICK_PHP_ROOT;
            FileChooser.from(launcher).showDirectory();
        });
        binding.secret.setOnClickListener(v -> toggleSecret());
        binding.scrollTop.setOnClickListener(v -> binding.sites.scrollToPosition(0));
        binding.scrollBottom.setOnClickListener(v -> {
            int count = adapter.getItemCount();
            if (count > 0) binding.sites.scrollToPosition(count - 1);
        });
        binding.moreToggle.setOnClickListener(v -> setMoreExpanded(!moreExpanded));
        setMoreExpanded(false);
        refreshSecret();
        refreshPhpRoot();
        refreshScanDir();
        refreshList();
    }

    private void refreshScanDir() {
        String dir = LocalSource.getScanDir();
        binding.scanDir.setText(TextUtils.isEmpty(dir) ? getString(R.string.local_source_scan_dir_empty) : dir);
    }

    /**
     * 下面 4 排按钮默认收起，列表独占空间；点“更多操作”展开按钮，列表相应收窄，
     * 让弹窗总高度不超屏，展开时底部按钮也能点到。
     */
    private void setMoreExpanded(boolean expanded) {
        moreExpanded = expanded;
        binding.moreActions.setVisibility(expanded ? View.VISIBLE : View.GONE);
        binding.moreToggle.setText(expanded ? R.string.local_source_collapse : R.string.local_source_more);
        // 列表高度：收起时 320dp（约 4 条），展开时 100dp（约 1 条），给按钮腾地方。
        // 上下限锁死同一值：只设最小高度时 weight 会把它撑大、把按钮顶出屏幕，
        // 加了最大高度才卡得住。“更多操作”已移到列表上方，不再被列表顶走。
        binding.sites.setMinHeight(ResUtil.dp2px(expanded ? 100 : 320));
        binding.sites.setMaxHeight(ResUtil.dp2px(expanded ? 100 : 320));
        binding.sites.requestLayout();
    }

    private void refreshList() {
        all = LocalSource.getSites();
        List<String> categories = LocalSource.categoriesOf(all);
        if (!categories.contains(category)) category = "全部";
        buildTabs(categories);
        List<Site> filtered = LocalSource.filter(all, category, keyword);
        adapter.setItems(filtered);
        binding.empty.setVisibility(filtered.isEmpty() ? View.VISIBLE : View.GONE);
        binding.status.setText(getString(R.string.local_source_count, all.size()));
    }

    private void buildTabs(List<String> categories) {
        binding.tabs.removeAllViews();
        for (String name : categories) {
            MaterialButton button = new MaterialButton(requireContext(), null, com.google.android.material.R.attr.materialButtonOutlinedStyle);
            button.setText(name);
            button.setSelected(name.equals(category));
            button.setOnClickListener(v -> {
                category = name;
                refreshList();
            });
            binding.tabs.addView(button);
        }
    }

    private void refreshSecret() {
        boolean show = LocalSource.isShowSecret();
        binding.secret.setText(getString(R.string.local_source_secret) + (show ? "：开" : "：关"));
    }

    private void refreshPhpRoot() {
        String root = LocalSource.getPhpRoot();
        binding.phpRoot.setText(getString(R.string.local_source_php_root_label, TextUtils.isEmpty(root) ? getString(R.string.local_source_php_root_empty) : root));
    }

    private void toggleSecret() {
        boolean show = !LocalSource.isShowSecret();
        LocalSource.setShowSecret(show);
        LocalSource.invalidate();
        refreshSecret();
        refreshList();
        reloadConfig();
    }

    private void scanAll() {
        if (scanning) return;
        String dir = LocalSource.getScanDir();
        File root = TextUtils.isEmpty(dir) ? Path.root() : new File(dir);
        scanDir(root);
    }

    private void scanDir(File dir) {
        if (scanning || dir == null) return;
        scanning = true;
        binding.status.setText(R.string.local_source_scanning);
        new Thread(() -> {
            int count = LocalSource.scan(dir);
            onScanDone(count);
        }).start();
    }

    private void scanFiles(List<File> files) {
        if (scanning) return;
        scanning = true;
        binding.status.setText(R.string.local_source_scanning);
        new Thread(() -> {
            int count = LocalSource.scanFiles(files);
            onScanDone(count);
        }).start();
    }

    private void onScanDone(int count) {
        App.post(() -> {
            scanning = false;
            LocalSource.invalidate();
            boolean skippedLarge = LocalSource.takeSkippedLargeDir();
            refreshList();
            // 有文件夹因文件过多被跳过：只提示这句，不再报导入数。
            if (skippedLarge) Notify.show(R.string.local_source_too_many_files);
            else Notify.show(getString(R.string.local_source_imported, count));
            if (count > 0) reloadConfig();
        });
    }

    /** 重新加载当前点播配置，让新扫到的本地源出现在首页站点列表里。 */
    private void reloadConfig() {
        VodConfig.load(Config.vod(), new Callback() {
            @Override
            public void success() {
                ConfigEvent.vod();
            }
        });
    }

    private void removeSelected() {
        List<String> keys = new ArrayList<>();
        for (Site site : adapter.getItems()) if (adapter.isSelected(site)) keys.add(site.getKey());
        if (keys.isEmpty()) return;
        int count = keys.size();
        // 直接删原始条目：拿已转换的 getSites() 再 saveSites() 会把 http://127.0.0.1:端口/file/... 写回盘里，端口一变就全空。
        LocalSource.removeByKeys(keys);
        adapter.clearSelection();
        refreshList();
        Notify.show(getString(R.string.local_source_deleted, count));
        reloadConfig();
    }

    private void clearAll() {
        if (LocalSource.getSites().isEmpty()) return;
        LocalSource.clear();
        refreshList();
        Notify.show(getString(R.string.local_source_deleted, 0));
        reloadConfig();
    }

    @Override
    public void onItemClick(Site item) {
        VodConfig.get().setHome(item);
        ConfigEvent.vod();
        dismiss();
    }

    @Override
    public void onSelectionChanged() {
    }
}
