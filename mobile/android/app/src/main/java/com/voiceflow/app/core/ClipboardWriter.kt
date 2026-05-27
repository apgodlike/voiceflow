package com.voiceflow.app.core

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context

object ClipboardWriter {
    fun copy(context: Context, text: String) {
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("VoiceFlow", text))
    }
}
