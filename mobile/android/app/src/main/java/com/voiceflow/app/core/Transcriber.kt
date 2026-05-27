package com.voiceflow.app.core

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

class TranscriptionException(message: String) : Exception(message)

/**
 * Single transcription call against the OpenAI endpoint. No retry logic here —
 * the caller owns retry policy (mirrors desktop transcriber.py / queue.py split).
 */
class Transcriber(
    private val apiKey: String,
    private val model: String,
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .callTimeout(60, TimeUnit.SECONDS)
        .build()

    fun transcribe(audio: File): String {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", audio.name, audio.asRequestBody("audio/m4a".toMediaType()))
            .addFormDataPart("model", model)
            .build()

        val request = Request.Builder()
            .url("https://api.openai.com/v1/audio/transcriptions")
            .header("Authorization", "Bearer $apiKey")
            .post(body)
            .build()

        client.newCall(request).execute().use { resp ->
            val payload = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                val detail = runCatching { JSONObject(payload).getJSONObject("error").getString("message") }
                    .getOrDefault(payload.take(200))
                throw TranscriptionException(
                    when (resp.code) {
                        401 -> "Auth failed — check your OpenAI key"
                        429 -> "Rate limited — try again shortly"
                        else -> "HTTP ${resp.code}: $detail"
                    }
                )
            }
            return runCatching { JSONObject(payload).getString("text").trim() }
                .getOrElse { throw TranscriptionException("Unexpected response: ${payload.take(200)}") }
        }
    }
}
