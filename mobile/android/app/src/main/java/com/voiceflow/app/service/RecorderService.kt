package com.voiceflow.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.voiceflow.app.MainActivity
import com.voiceflow.app.R
import com.voiceflow.app.core.AudioRecorder
import com.voiceflow.app.core.Cleaner
import com.voiceflow.app.core.ClipboardWriter
import com.voiceflow.app.core.Settings
import com.voiceflow.app.core.Transcriber
import com.voiceflow.app.overlay.OverlayBubble
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Foreground service (type microphone) that hosts the floating bubble and runs
 * the record -> transcribe -> clean -> clipboard pipeline. Mirrors the desktop
 * main.py orchestration. One in-flight job at a time; taps while transcribing
 * are ignored.
 */
class RecorderService : Service() {

    private enum class Phase { IDLE, RECORDING, TRANSCRIBING }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val main = Handler(Looper.getMainLooper())

    private lateinit var bubble: OverlayBubble
    private lateinit var recorder: AudioRecorder
    private lateinit var settings: Settings

    @Volatile private var phase = Phase.IDLE

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        settings = Settings(this)
        recorder = AudioRecorder(this)
        createChannel()
        startForegroundCompat()
        bubble = OverlayBubble(this) { onTap() }
        main.post { bubble.show() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    private fun onTap() {
        when (phase) {
            Phase.IDLE -> startRecording()
            Phase.RECORDING -> stopAndTranscribe()
            Phase.TRANSCRIBING -> Unit
        }
    }

    private fun startRecording() {
        if (settings.apiKey.isBlank()) {
            toast("Add your OpenAI key in the app first")
            return
        }
        try {
            recorder.start()
            phase = Phase.RECORDING
            bubble.setState(OverlayBubble.State.RECORDING)
        } catch (e: Exception) {
            toast("Mic error: ${e.message}")
            flashError()
        }
    }

    private fun stopAndTranscribe() {
        val file = recorder.stop()
        phase = Phase.TRANSCRIBING
        bubble.setState(OverlayBubble.State.TRANSCRIBING)

        if (file == null || !file.exists() || file.length() == 0L) {
            file?.delete()
            toast("Recording too short")
            flashError()
            return
        }

        scope.launch {
            try {
                val raw = Transcriber(settings.apiKey, settings.model).transcribe(file)
                val cleaned = Cleaner.clean(raw)
                main.post {
                    if (cleaned.isNotBlank()) {
                        ClipboardWriter.copy(this@RecorderService, cleaned)
                        bubble.setState(OverlayBubble.State.SUCCESS)
                        toast("Copied — long-press a field to paste")
                    } else {
                        bubble.setState(OverlayBubble.State.ERROR)
                        toast("Nothing transcribed")
                    }
                }
                delay(1200)
            } catch (e: Exception) {
                main.post {
                    bubble.setState(OverlayBubble.State.ERROR)
                    toast("Failed: ${e.message}")
                }
                delay(1200)
            } finally {
                file.delete()
                phase = Phase.IDLE
                main.post { bubble.setState(OverlayBubble.State.IDLE) }
            }
        }
    }

    private fun flashError() {
        phase = Phase.IDLE
        bubble.setState(OverlayBubble.State.ERROR)
        main.postDelayed({ bubble.setState(OverlayBubble.State.IDLE) }, 1200)
    }

    private fun toast(message: String) {
        main.post { Toast.makeText(this, message, Toast.LENGTH_SHORT).show() }
    }

    private fun createChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, getString(R.string.notif_channel), NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun startForegroundCompat() {
        val pending = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notif: Notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("VoiceFlow")
            .setContentText("Tap the floating mic to dictate")
            .setSmallIcon(R.drawable.ic_mic)
            .setContentIntent(pending)
            .setOngoing(true)
            .build()
        startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
        recorder.stop()
        main.post { bubble.hide() }
    }

    companion object {
        private const val CHANNEL_ID = "voiceflow_rec"
        private const val NOTIF_ID = 1

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, RecorderService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, RecorderService::class.java))
        }
    }
}
