package com.fongmi.android.tv.ui.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.fongmi.android.tv.bean.History;
import com.fongmi.android.tv.databinding.AdapterContinueBinding;
import com.fongmi.android.tv.utils.ImgUtil;

import java.util.ArrayList;
import java.util.List;

/**
 * 首页“继续观看”适配器（B2）：横向滑动行，数据来自观看历史。
 * 只显示未看完的（duration > 0 且 position < duration），点进续播。
 */
public class ContinueAdapter extends RecyclerView.Adapter<ContinueAdapter.Holder> {

    private final OnClickListener listener;
    private final List<History> items = new ArrayList<>();

    public ContinueAdapter(OnClickListener listener) {
        this.listener = listener;
    }

    public interface OnClickListener {
        void onItemClick(History item);
    }

    public void submit(List<History> list) {
        items.clear();
        if (list != null) items.addAll(list);
        notifyDataSetChanged();
    }

    public int getItemCount() {
        return items.size();
    }

    @NonNull
    @Override
    public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        return new Holder(AdapterContinueBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false));
    }

    @Override
    public void onBindViewHolder(@NonNull Holder holder, int position) {
        holder.bind(items.get(position));
    }

    class Holder extends RecyclerView.ViewHolder {

        private final AdapterContinueBinding binding;

        Holder(@NonNull AdapterContinueBinding binding) {
            super(binding.getRoot());
            this.binding = binding;
        }

        void bind(History item) {
            binding.name.setText(item.getVodName());
            if (item.getVodRemarks() == null || item.getVodRemarks().isEmpty()) {
                binding.remark.setVisibility(View.GONE);
            } else {
                binding.remark.setVisibility(View.VISIBLE);
                binding.remark.setText(item.getVodRemarks());
            }
            long duration = item.getDuration();
            int progress = duration > 0 ? (int) (item.getPosition() * 100 / duration) : 0;
            binding.progress.setProgress(Math.max(0, Math.min(100, progress)));
            ImgUtil.load(item.getVodName(), item.getVodPic(), binding.image);
            binding.getRoot().setOnClickListener(v -> {
                if (listener != null) listener.onItemClick(item);
            });
        }
    }
}
