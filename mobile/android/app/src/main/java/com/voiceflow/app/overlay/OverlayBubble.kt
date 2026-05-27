package com.voiceflow.app.overlay

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.ImageView
import com.voiceflow.app.R
import kotlin.math.abs

/**
 * Draggable, semi-transparent floating mic button drawn over other apps via
 * TYPE_APPLICATION_OVERLAY. FLAG_NOT_FOCUSABLE so the underlying app keeps input
 * focus (the user can still long-press-paste into the focused field). Bubble
 * colour reflects state, mirroring the desktop tray icon convention.
 */
class OverlayBubble(
    private val context: Context,
    private val onTap: () -> Unit,
) {
    enum class State { IDLE, RECORDING, TRANSCRIBING, SUCCESS, ERROR }

    private val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val view = ImageView(context)
    private val params = WindowManager.LayoutParams(
        dp(56), dp(56),
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
        PixelFormat.TRANSLUCENT,
    )
    private var added = false

    init {
        view.setImageResource(R.drawable.ic_mic)
        view.setPadding(dp(12), dp(12), dp(12), dp(12))
        setState(State.IDLE)
        params.gravity = Gravity.TOP or Gravity.START
        params.x = dp(16)
        params.y = dp(220)
        attachTouch()
    }

    fun show() {
        if (!added) {
            wm.addView(view, params)
            added = true
        }
    }

    fun hide() {
        if (added) {
            wm.removeView(view)
            added = false
        }
    }

    fun setState(state: State) {
        val color = when (state) {
            State.IDLE -> 0xFF607D8B.toInt()
            State.RECORDING -> 0xFFE53935.toInt()
            State.TRANSCRIBING -> 0xFFFBC02D.toInt()
            State.SUCCESS -> 0xFF43A047.toInt()
            State.ERROR -> 0xFFD32F2F.toInt()
        }
        view.background = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(color)
            alpha = 210
        }
    }

    private fun attachTouch() {
        var startX = 0
        var startY = 0
        var downX = 0f
        var downY = 0f
        var moved = false
        view.setOnTouchListener { _, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> {
                    startX = params.x
                    startY = params.y
                    downX = e.rawX
                    downY = e.rawY
                    moved = false
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (e.rawX - downX).toInt()
                    val dy = (e.rawY - downY).toInt()
                    if (abs(dx) > dp(8) || abs(dy) > dp(8)) moved = true
                    params.x = startX + dx
                    params.y = startY + dy
                    if (added) wm.updateViewLayout(view, params)
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!moved) onTap()
                    true
                }
                else -> false
            }
        }
    }

    private fun dp(value: Int): Int =
        (value * context.resources.displayMetrics.density).toInt()
}
