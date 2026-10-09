package com.fongmi.android.tv.ui.fragment;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.viewbinding.ViewBinding;

import com.fongmi.android.tv.R;
import com.fongmi.android.tv.api.config.ImportedAdRuleCandidateStore;
import com.fongmi.android.tv.api.config.RuleConfig;
import com.fongmi.android.tv.api.config.UserAdRuleStore;
import com.fongmi.android.tv.databinding.FragmentSettingAdBinding;
import com.fongmi.android.tv.player.IntroSkipKinds;
import com.fongmi.android.tv.setting.Setting;
import com.fongmi.android.tv.ui.base.BaseFragment;
import com.fongmi.android.tv.ui.dialog.AdBlockStatsDialog;
import com.fongmi.android.tv.ui.dialog.AdRuleManageDialog;
import com.fongmi.android.tv.utils.ResUtil;
import com.github.catvod.crawler.SpiderDebug;

public class SettingAdFragment extends BaseFragment {

    private FragmentSettingAdBinding mBinding;
    private String[] introSkipMode;

    public static SettingAdFragment newInstance() {
        return new SettingAdFragment();
    }

    private String getSwitch(boolean value) {
        return getString(value ? R.string.setting_on : R.string.setting_off);
    }

    @Override
    protected ViewBinding getBinding(@NonNull LayoutInflater inflater, @Nullable ViewGroup container) {
        return mBinding = FragmentSettingAdBinding.inflate(inflater, container, false);
    }

    @Override
    protected void initView() {
        introSkipMode = ResUtil.getStringArray(R.array.select_auto_skip_intro_outro);
        setText();
    }

    @Override
    protected void initEvent() {
        mBinding.adblock.setOnClickListener(this::setAdblock);
        mBinding.aiAdDetection.setOnClickListener(this::setAiAdDetection);
        mBinding.adRuleManage.setOnClickListener(view -> AdRuleManageDialog.create().show(requireActivity(), this::setText));
        mBinding.adBlockStats.setOnClickListener(view -> AdBlockStatsDialog.create(requireActivity()).show());
        mBinding.autoSkipIntroOutro.setOnClickListener(this::setAutoSkipIntroOutro);
        mBinding.introSkipKinds.setOnClickListener(view -> IntroSkipKinds.show(requireActivity(), this::setText));
    }

    private void setText() {
        if (mBinding == null) return;
        if (!canSetText()) return;
        safeSet("adblock", mBinding.adblockText, () -> getSwitch(Setting.isAdblock()));
        safeRun("aiAdDetection", () -> {
            mBinding.aiAdDetection.setVisibility(Setting.isAiConfigReady() ? View.VISIBLE : View.GONE);
            mBinding.aiAdDetectionText.setText(getSwitch(Setting.isAiAdDetection()));
        }, () -> setError(mBinding.aiAdDetectionText));
        safeSet("adRuleManage", mBinding.adRuleManageText, () -> getString(R.string.ad_rule_count_with_pending,
                UserAdRuleStore.load().size() + RuleConfig.get().getDefaultRules().size(),
                ImportedAdRuleCandidateStore.pending().size()));
        safeSet("autoSkipIntroOutro", mBinding.autoSkipIntroOutroText, () -> introSkipMode[Setting.getIntroSkipMode()]);
        safeSet("introSkipKinds", mBinding.introSkipKindsText, IntroSkipKinds::summary);
    }

    private boolean canSetText() {
        return mBinding != null && isAdded() && getContext() != null;
    }

    private void safeSet(String name, TextView view, TextSupplier supplier) {
        safeRun(name, () -> view.setText(supplier.get()), () -> setError(view));
    }

    private void safeRun(String name, Runnable action, Runnable fallback) {
        try {
            action.run();
        } catch (Throwable e) {
            SpiderDebug.log("ad", "summary failed item=%s error=%s", name, e.toString());
            if (fallback == null) return;
            try {
                fallback.run();
            } catch (Throwable ignored) {
            }
        }
    }

    private void setError(TextView view) {
        if (view != null) view.setText(R.string.error_config_get);
    }

    private interface TextSupplier {
        CharSequence get();
    }

    private void setAdblock(View view) {
        Setting.putAdblock(!Setting.isAdblock());
        setText();
    }

    private void setAiAdDetection(View view) {
        Setting.putAiAdDetection(!Setting.isAiAdDetection());
        setText();
    }

    private void setAutoSkipIntroOutro(View view) {
        Setting.putIntroSkipMode((Setting.getIntroSkipMode() + 1) % introSkipMode.length);
        setText();
    }

    @Override
    public void onHiddenChanged(boolean hidden) {
        if (!hidden) setText();
    }

    @Override
    public void onResume() {
        super.onResume();
        setText();
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        mBinding = null;
    }
}
