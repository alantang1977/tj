// Ported from AVBox (github.com/XiaochangXu/AVBox), AGPL-3.0, adapted for Mooyingshi.
package com.fongmi.android.tv.glass

object NavMetrics {

    const val SLOT_MAIN_DP = 56

    fun actionSlotFor(tabCount: Int): Int = tabCount / 2

    fun slotIndexOfTab(tab: Int, actionSlot: Int?): Int =
        if (actionSlot != null && tab >= actionSlot) tab + 1 else tab

    fun tabIndexOfSlot(slot: Int, actionSlot: Int?): Int =
        if (actionSlot != null && slot > actionSlot) slot - 1 else slot
}
