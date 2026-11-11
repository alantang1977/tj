package com.fongmi.android.tv.ui.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.fongmi.android.tv.bean.Vod;
import com.fongmi.android.tv.databinding.AdapterBannerBinding;
import com.fongmi.android.tv.utils.ImgUtil;

import java.util.ArrayList;
import java.util.List;

/**
 * 首页轮播横幅适配器（B1）：给 VodFragment 的 ViewPager2 用。
 * 数据来自当前站首页推荐（SiteApi.homeContent 的 homeVideoContent）。
 */
public class BannerAdapter extends RecyclerView.Adapter<BannerAdapter.Holder> {

    private final OnClickListener listener;
    private final List<Vod> items = new ArrayList<>();

    public BannerAdapter(OnClickListener listener) {
        this.listener = listener;
    }

    public interface OnClickListener {
        void onItemClick(Vod item);
    }

    public void submit(List<Vod> list) {
        items.clear();
        if (list != null) items.addAll(list);
        notifyDataSetChanged();
    }

    public int getItemCount() {
        return items.size();
    }

    public Vod getItem(int position) {
        return items.get(position);
    }

    @NonNull
    @Override
    public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        return new Holder(AdapterBannerBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false));
    }

    @Override
    public void onBindViewHolder(@NonNull Holder holder, int position) {
        holder.bind(items.get(position));
    }

    class Holder extends RecyclerView.ViewHolder {

        private final AdapterBannerBinding binding;

        Holder(@NonNull AdapterBannerBinding binding) {
            super(binding.getRoot());
            this.binding = binding;
        }

        void bind(Vod item) {
            binding.name.setText(item.getName());
            if (item.getRemarks() == null || item.getRemarks().isEmpty()) {
                binding.remark.setVisibility(View.GONE);
            } else {
                binding.remark.setVisibility(View.VISIBLE);
                binding.remark.setText(item.getRemarks());
            }
            ImgUtil.load(item.getName(), item.getPic(), binding.image);
            binding.getRoot().setOnClickListener(v -> {
                if (listener != null) listener.onItemClick(item);
            });
        }
    }
}
