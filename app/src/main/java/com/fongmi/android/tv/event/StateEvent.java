package com.fongmi.android.tv.event;

import org.greenrobot.eventbus.EventBus;

/**
 * 手机端首页（VodFragment）的状态广播。
 *
 * <p>这是与 {@code ProgressLayout}（视图内切换）并行的**第二套**状态机制：首页由 Fragment
 * 承载、状态由 Activity 触发，所以用 EventBus 广播而不是直接操作视图。
 *
 * <p><b>为什么加了 ERROR。</b>改动前只有 EMPTY/PROGRESS/CONTENT，而消费方对 EMPTY 的处理
 * 只是"隐藏转圈"——于是内容源加载失败时首页是**一片空白**（用户只看到一个会消失的吐司）。
 * 失败与"确实没有内容"是两件事，需要分开表达：EMPTY 表示没有内容，ERROR 表示加载失败
 * 并带上失败原因，由消费方渲染成「错误色 + 原因 + 重试动作」（设计文档 §9.9）。
 *
 * @param type    状态类型
 * @param message ERROR 时的失败原因；其余状态为 {@code null}
 */
public record StateEvent(Type type, String message) {

    public static void empty() {
        EventBus.getDefault().post(new StateEvent(Type.EMPTY, null));
    }

    public static void progress() {
        EventBus.getDefault().post(new StateEvent(Type.PROGRESS, null));
    }

    public static void content() {
        EventBus.getDefault().post(new StateEvent(Type.CONTENT, null));
    }

    /** 加载失败：带上原因，由消费方渲染错误态而不是留空白。 */
    public static void error(String message) {
        EventBus.getDefault().post(new StateEvent(Type.ERROR, message));
    }

    public enum Type {
        EMPTY, PROGRESS, CONTENT, ERROR
    }
}
