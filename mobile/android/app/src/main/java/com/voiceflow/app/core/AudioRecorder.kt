package com.voiceflow.app.core

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File

/**
 * Records mic to a compact AAC/m4a file (16 kHz mono) — small payload for the
 * OpenAI transcription endpoint, which accepts m4a. Audio is written to cacheDir
 * and deleted by the caller after transcription (privacy parity with desktop).
 */
class AudioRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var current: File? = null

    fun start(): File {
        val file = File(context.cacheDir, "rec_${System.currentTimeMillis()}.m4a")
        val r = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION") MediaRecorder()
        }
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioChannels(1)
        r.setAudioSamplingRate(16000)
        r.setAudioEncodingBitRate(64000)
        r.setOutputFile(file.absolutePath)
        r.prepare()
        r.start()
        recorder = r
        current = file
        return file
    }

    /** Stops and returns the file, or null if recording failed / was too short. */
    fun stop(): File? {
        val r = recorder ?: return null
        recorder = null
        return try {
            r.stop()
            current
        } catch (e: RuntimeException) {
            // stop() throws if no valid audio was captured (e.g. instant tap)
            current?.delete()
            null
        } finally {
            r.release()
            current = null
        }
    }
}
