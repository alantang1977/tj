package com.fongmi.android.tv.ui.activity;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.TextView;

import androidx.viewbinding.ViewBinding;

import com.fongmi.android.tv.R;
import com.fongmi.android.tv.api.config.ImportedAdRuleCandidateStore;
import com.fongmi.android.tv.api.config.RuleConfig;
import com.fongmi.android.tv.api.config.UserAdRuleStore;
import com.fongmi.android.tv.databinding.ActivitySettingAdBinding;
import com.fongmi.android.tv.player.IntroSkipKinds;
import com.fongmi.android.tv.setting.Setting;
import com.fongmi.android.tv.ui.base.BaseActivity;
import com.fongmi.android.tv.ui.dialog.AdBlockStatsDialog;
import com.fongmi.android.tv.ui.dialog.AdRuleManageDialog;
import com.github.catvod.crawler.SpiderDebug;

public class SettingAdActivity extends BaseActivity {

    private ActivitySettingAdBinding mBinding;
    private String[] introSkipMode;

    public static void start(Activity activity) {
        activity.startActivity(new Intent(activity, SettingAdActivity.class));
    }

    private String getSwitch(boolean value) {
        return getString(value ? R.string.setting_on : R.string.setting_off);
    }

    @Override
    protected ViewBinding getBinding() {
        return mBinding = ActivitySettingAdBinding.inflate(getLayoutInflater());
    }

    @Override
    protected void initView(Bundle savedInstanceState) {
        mBinding.adblock.requestFocus();
        introSkipMode = getResources().getStringArray(R.array.select_auto_skip_intro_outro);
        setText();
    }

    @Override
    protected void initEvent() {
        mBinding.adblock.setOnClickListener(this::setAdblock);
        mBinding.aiAdDetection.setOnClickListener(this::setAiAdDetection);
        mBinding.adRuleManage.setOnClickListener(view -> AdRuleManageDialog.create().show(this, this::setText));
        mBinding.adBlockStats.setOnClickListener(view -> AdBlockStatsDialog.create(this).show());
        mBinding.autoSkipIntroOutro.setOnClickListener(this::setAutoSkipIntroOutro);
        mBinding.introSkipKinds.setOnClickListener(view -> IntroSkipKinds.show(this, this::setText));
    }

    private void setText() {
        if (!canSetText()) return;
        safeSet("adblock", mBinding.adblockText, () -> getSwitch(Setting.isAdblock()));
        mBinding.aiAdDetection.setVisibility(Setting.isAiConfigReady() ? View.VISIBLE : View.GONE);
        safeSet("aiAdDetection", mBinding.aiAdDetectionText, () -> getSwitch(Setting.isAiAdDetection()));
        safeSet("adRuleManage", mBinding.adRuleManageText, () -> getString(R.string.ad_rule_count_with_pending,
                UserAdRuleStore.load().size() + RuleConfig.get().getDefaultRules().size(),
                ImportedAdRuleCandidateStore.pending().size()));
        safeSet("autoSkipIntroOutro", mBinding.autoSkipIntroOutroText, () -> introSkipMode[Setting.getIntroSkipMode()]);
        safeSet("introSkipKinds", mBinding.introSkipKindsText, IntroSkipKinds::summary);
    }

    private boolean canSetText() {
        return mBinding != null && !isFinishing() && !isDestroyed();
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
    protected void onResume() {
        super.onResume();
        setText();
    }
}
