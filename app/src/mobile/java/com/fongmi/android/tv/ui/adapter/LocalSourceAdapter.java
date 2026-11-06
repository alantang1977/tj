package com.fongmi.android.tv.ui.adapter;

import android.view.LayoutInflater;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.fongmi.android.tv.bean.Site;
import com.fongmi.android.tv.databinding.ItemLocalSourceBinding;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class LocalSourceAdapter extends RecyclerView.Adapter<LocalSourceAdapter.ViewHolder> {

    private final OnClickListener listener;
    private List<Site> mItems = new ArrayList<>();
    private final Set<String> selected = new HashSet<>();

    public LocalSourceAdapter(OnClickListener listener) {
        this.listener = listener;
    }

    public interface OnClickListener {
        void onItemClick(Site item);
        void onSelectionChanged();
    }

    public LocalSourceAdapter setItems(List<Site> items) {
        mItems = items == null ? new ArrayList<>() : new ArrayList<>(items);
        selected.retainAll(keysOf(mItems));
        notifyDataSetChanged();
        return this;
    }

    private Set<String> keysOf(List<Site> items) {
        Set<String> keys = new HashSet<>();
        for (Site site : items) keys.add(site.getKey());
        return keys;
    }

    public List<Site> getItems() {
        return mItems;
    }

    public Set<String> getSelected() {
        return new HashSet<>(selected);
    }

    public void selectAll() {
        selected.clear();
        selected.addAll(keysOf(mItems));
        notifyDataSetChanged();
        listener.onSelectionChanged();
    }

    public void invert() {
        Set<String> next = new HashSet<>();
        for (Site site : mItems) if (!selected.contains(site.getKey())) next.add(site.getKey());
        selected.clear();
        selected.addAll(next);
        notifyDataSetChanged();
        listener.onSelectionChanged();
    }

    public void clearSelection() {
        selected.clear();
        notifyDataSetChanged();
        listener.onSelectionChanged();
    }

    public boolean isSelected(Site site) {
        return selected.contains(site.getKey());
    }

    public void removeSelected() {
        mItems.removeIf(site -> selected.contains(site.getKey()));
        selected.clear();
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        return new ViewHolder(ItemLocalSourceBinding.inflate(LayoutInflater.from(parent.getContext()), parent, false));
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        Site site = mItems.get(position);
        holder.binding.name.setText(site.getName());
        holder.binding.api.setText(site.getApi());
        holder.binding.check.setChecked(selected.contains(site.getKey()));
        holder.binding.check.setOnCheckedChangeListener((button, checked) -> {
            if (checked) selected.add(site.getKey());
            else selected.remove(site.getKey());
            listener.onSelectionChanged();
        });
        holder.binding.getRoot().setOnClickListener(v -> listener.onItemClick(site));
    }

    @Override
    public int getItemCount() {
        return mItems.size();
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        private final ItemLocalSourceBinding binding;

        ViewHolder(@NonNull ItemLocalSourceBinding binding) {
            super(binding.getRoot());
            this.binding = binding;
        }
    }
}
