package com.fongmi.android.tv.ui.fragment;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/**
 * 手机端首页状态（空态 / 错误态）的契约。
 *
 * <p>手机端首页走的是与 {@code ProgressLayout} **并行**的第二套机制：状态由 Activity 通过
 * {@code StateEvent}（EventBus）广播、由 {@code VodFragment} 消费。改动前它只有
 * EMPTY/PROGRESS/CONTENT，而消费方对 EMPTY 的处理**只是隐藏转圈**——于是内容源加载失败后
 * 首页是**一片空白**，用户只看到一个会消失的吐司。
 *
 * <p>本契约钉住三件事：
 * <ol>
 *   <li><b>失败与"没有内容"必须分开表达</b>：失败发 {@code ERROR}（带原因），
 *       {@code EMPTY} 保持原义；</li>
 *   <li><b>错误态要有三要素</b>：错误色标题 + 原因 + 重试动作（§9.9）；</li>
 *   <li><b>不新写加载路径</b>：重试必须复用首次加载那条 {@code homeContent()}。</li>
 * </ol>
 */
public class MobileHomeStateContractTest {

    private static final String EVENT = "app/src/main/java/com/fongmi/android/tv/event/StateEvent.java";
    private static final String HOME = "app/src/mobile/java/com/fongmi/android/tv/ui/activity/HomeActivity.java";
    private static final String FRAGMENT = "app/src/mobile/java/com/fongmi/android/tv/ui/fragment/VodFragment.java";
    private static final String LAYOUT = "app/src/mobile/res/layout/fragment_vod.xml";
    private static final String STRINGS = "app/src/main/res/values/strings.xml";
    private static final String STRINGS_CN = "app/src/main/res/values-zh-rCN/strings.xml";

    @Test
    public void stateEventCarriesAFailureReasonAndAnErrorType() throws Exception {
        String source = read(EVENT);
        assertTrue("StateEvent 必须记录失败原因", source.contains("String message"));
        assertTrue("必须提供 error(message) 工厂", source.contains("public static void error(String message)"));
        assertTrue("必须有 ERROR 类型", source.contains("ERROR"));
        // 其余三个状态仍然不带原因。
        assertTrue("empty 仍应发不带原因的状态", source.contains("new StateEvent(Type.EMPTY, null)"));
        assertTrue("progress 仍应发不带原因的状态", source.contains("new StateEvent(Type.PROGRESS, null)"));
        assertTrue("content 仍应发不带原因的状态", source.contains("new StateEvent(Type.CONTENT, null)"));
    }

    /**
     * 失败必须发 ERROR 而不是 EMPTY：否则消费方只会隐藏转圈，首页留空白。
     */
    @Test
    public void homeConfigFailurePostsErrorNotEmpty() throws Exception {
        String body = methodBody(read(HOME), "public void error(String msg)");
        assertTrue("配置加载失败必须发 StateEvent.error(msg)", body.contains("StateEvent.error(msg)"));
        assertFalse("配置加载失败不得再发 StateEvent.empty()", body.contains("StateEvent.empty()"));
        // 崩溃重启那次是"本次跳过加载"，不是失败，应保持 EMPTY。
        String init = methodBody(read(HOME), "private void initConfig()");
        assertTrue("崩溃重启跳过加载仍应是 EMPTY（它不是失败）", init.contains("StateEvent.empty()"));
    }

    @Test
    public void homeFragmentRendersAnErrorStateWithReasonAndRetry() throws Exception {
        String source = read(FRAGMENT);
        String handler = methodBody(source, "public void onStateEvent(StateEvent event)");
        assertTrue("必须处理 ERROR 分支", handler.contains("case ERROR:"));
        assertTrue("ERROR 必须显示错误态而不是只隐藏转圈", handler.contains("showError(event.message())"));

        String showError = methodBody(source, "private void showError(String message)");
        assertTrue("错误态标题必须是 error_config_load", showError.contains("R.string.error_config_load"));
        assertTrue("错误态必须有重试按钮文案", showError.contains("R.string.error_retry"));
        assertTrue("错误态必须用 ProgressLayout 的 showError", showError.contains("mBinding.state.showError("));
        assertTrue("错误态的重试必须回到失败的那一步", showError.contains("retryConfig()"));
    }

    /**
     * 重试必须回到**失败的那一步**。
     *
     * <p>实机验证时发现：首页的错误来自承载它的 Activity 的内容源配置加载，最初把重试接成
     * {@code homeContent()}（重新加载首页内容）时，点了重试页面毫无变化——配置根本没被重新拉取。
     * 因此重试必须通过回调交回 Activity。
     */
    @Test
    public void retryGoesBackToTheStepThatActuallyFailed() throws Exception {
        String fragment = read(FRAGMENT);
        assertTrue("必须声明 ConfigRetry 回调接口", fragment.contains("interface ConfigRetry"));
        String retry = methodBody(fragment, "private void retryConfig()");
        assertTrue("重试必须优先交给实现了 ConfigRetry 的 Activity",
                retry.contains("activity instanceof ConfigRetry"));
        assertTrue("重试必须调用 Activity 的 retryConfig", retry.contains("retryConfig()"));

        String home = read(HOME);
        assertTrue("HomeActivity 必须实现该回调",
                home.contains("VodFragment.ConfigRetry"));
        String impl = methodBody(home, "public void retryConfig()");
        assertTrue("HomeActivity 的重试必须重新加载内容源配置", impl.contains("initConfig()"));
        assertTrue("重试期间应切回加载态，避免错误态一直停在屏幕上", impl.contains("StateEvent.progress()"));
    }

    @Test
    public void stateOverlayIsHiddenWhenContentOrProgressComesBack() throws Exception {
        String handler = methodBody(read(FRAGMENT), "public void onStateEvent(StateEvent event)");
        assertTrue("PROGRESS 时必须收起状态浮层", handler.contains("hideState();"));
        assertTrue("CONTENT 时必须收起状态浮层", handler.contains("case CONTENT:"));
        // EMPTY 保持原义：只是"没有内容"，不是失败，因此不得渲染错误态。
        String emptyCase = between(handler, "case EMPTY:", "case PROGRESS:");
        assertTrue("EMPTY 仍只是隐藏转圈", emptyCase.contains("hideProgress()"));
        assertFalse("EMPTY 不得显示错误态（它不是失败）", emptyCase.contains("showError("));
    }

    /**
     * "确实没有内容"也要给三件套，而不是留空白。
     *
     * <p>本批前半只修了失败路径（ERROR）；EMPTY 当时仍然只是隐藏转圈，同样会留空白，
     * 所以一并补上。空态与错误态的区别是**没有失败原因、标题不用错误色**。
     */
    @Test
    public void homeEmptyStateAlsoCarriesTheThreeParts() throws Exception {
        String showEmpty = methodBody(read(FRAGMENT), "private void showEmpty()");
        assertTrue("空态必须用 ProgressLayout 的内容注入",
                showEmpty.contains("mBinding.state.setEmptyContent("));
        assertTrue("空态必须切换到 EMPTY", showEmpty.contains("mBinding.state.showEmpty()"));
        for (String string : new String[]{
                "home_empty_title", "home_empty_description", "home_empty_action"}) {
            assertTrue("必须引用 " + string, showEmpty.contains(string));
            assertTrue("默认字符串表必须声明 " + string, read(STRINGS).contains("name=\"" + string + "\""));
            assertTrue("简中字符串表必须声明 " + string, read(STRINGS_CN).contains("name=\"" + string + "\""));
        }
        assertTrue("空态主动作必须复用同一条加载路径", showEmpty.contains("homeContent()"));
    }

    @Test
    public void layoutDeclaresTheStateOverlayAsAProgressLayout() throws Exception {
        String layout = read(LAYOUT);
        assertTrue("fragment_vod.xml 必须声明 @+id/state", layout.contains("@+id/state"));
        assertTrue("状态浮层必须是 ProgressLayout（复用其四态与内容注入，避免重复实现）",
                layout.contains("com.fongmi.android.tv.ui.custom.ProgressLayout"));
        // 它只负责画状态，不承载内容子视图。
        int at = layout.indexOf("@+id/state");
        assertTrue("状态浮层必须默认隐藏", layout.indexOf("android:visibility=\"gone\"", at) > 0);
    }

    // ------------------------------------------------------------------ helpers

    /** 取 {@code from} 与 {@code to} 之间的片段（用于按 case 切分 switch 体）。 */
    private static String between(String source, String from, String to) {
        int start = source.indexOf(from);
        assertTrue("必须能找到 " + from, start > 0);
        int end = source.indexOf(to, start);
        assertTrue("必须能找到 " + to, end > start);
        return source.substring(start, end);
    }

    private static String methodBody(String source, String signature) {
        String cleaned = withoutJavaComments(source);
        int start = cleaned.indexOf(signature);
        assertTrue("必须存在方法 " + signature, start > 0);
        int open = cleaned.indexOf('{', start);
        assertTrue("方法签名后必须有方法体", open > 0);
        int depth = 0;
        for (int i = open; i < cleaned.length(); i++) {
            char c = cleaned.charAt(i);
            if (c == '{') depth++;
            else if (c == '}' && --depth == 0) return cleaned.substring(start, i + 1);
        }
        return cleaned.substring(start);
    }

    private static String withoutJavaComments(String source) {
        return source.replaceAll("(?s)/\\*.*?\\*/", " ").replaceAll("(?m)//.*$", " ");
    }

    private static String read(String path) throws Exception {
        Path direct = Path.of(path);
        if (Files.exists(direct)) return Files.readString(direct, StandardCharsets.UTF_8);
        return Files.readString(Path.of("..").resolve(path), StandardCharsets.UTF_8);
    }
}
