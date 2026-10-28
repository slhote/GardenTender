package com.gardentender.chat

import com.gardentender.auth.AuthRepository
import com.gardentender.config.AppConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.MalformedURLException
import java.net.URL

/** A tool call the server is paused on: awaiting approval and/or execution on the device. */
data class PendingCall(
    val id: String,
    val name: String,
    val input: JSONObject,
    val runsOn: String = "server",
    val confirm: Boolean = false,
)

data class ChatReply(val history: JSONArray, val reply: String, val pending: List<PendingCall>)

/** Typed `/chat` failures; `error/ErrorMessages` turns them into user-facing text. */
sealed class ChatApiException(cause: Throwable? = null) : Exception(cause) {
    class NoToken(cause: Throwable) : ChatApiException(cause)
    class InvalidBaseUrl(cause: Throwable) : ChatApiException(cause)
    class Http(val code: Int) : ChatApiException()

    /** Connection-level failure, worth retrying if the app was backgrounded. */
    class Network(override val cause: IOException) : ChatApiException(cause)

    /** Anything else (bad JSON, etc.). */
    class Unexpected(cause: Throwable) : ChatApiException(cause)
}

/**
 * Talks to GardenTender.Api `/chat`. [history] is opaque: it is echoed back from the previous response so the
 * server can stay stateless.
 */
class ChatApi(private val auth: AuthRepository, private val config: AppConfig) {
    suspend fun chat(
        history: JSONArray,
        message: String?,
        decisions: Map<String, Boolean>,
        deviceResults: Map<String, DeviceResult>,
        model: String? = null,
    ): ChatReply =
        withContext(Dispatchers.IO) {
            try {
                post(history, message, decisions, deviceResults, model)
            } catch (e: CancellationException) {
                throw e
            } catch (e: ChatApiException) {
                throw e
            } catch (e: Exception) {
                throw ChatApiException.Unexpected(e)
            }
        }

    private suspend fun post(
        history: JSONArray,
        message: String?,
        decisions: Map<String, Boolean>,
        deviceResults: Map<String, DeviceResult>,
        model: String?,
    ): ChatReply {
        val token = try {
            auth.accessToken()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            throw ChatApiException.NoToken(e)
        }
        val body = JSONObject()
            .put("history", history)
            .put("decisions", JSONObject(decisions))
            .put("timezone", java.util.TimeZone.getDefault().id)
            .put(
                "device_results",
                JSONObject().also { o ->
                    deviceResults.forEach { (id, r) -> o.put(id, JSONObject().put("content", r.content).put("is_error", r.isError)) }
                },
            )
        if (message != null) body.put("message", message)
        if (model != null) body.put("model", model)

        val url = try {
            URL("${config.apiBaseUrl}/chat")
        } catch (e: MalformedURLException) {
            throw ChatApiException.InvalidBaseUrl(e)
        }
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 10_000
            readTimeout = 120_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            conn.outputStream.use { it.write(body.toString().toByteArray()) }
            val code = conn.responseCode
            if (code !in 200..299) throw ChatApiException.Http(code)
            return parseReply(JSONObject(conn.inputStream.bufferedReader().use { it.readText() }))
        } catch (e: IOException) {
            throw ChatApiException.Network(e)
        } finally {
            conn.disconnect()
        }
    }

    private fun parseReply(json: JSONObject): ChatReply {
        val pending = json.getJSONArray("pending")
        return ChatReply(
            history = json.getJSONArray("history"),
            reply = json.getString("reply"),
            pending = (0 until pending.length()).map {
                pending.getJSONObject(it).let { p ->
                    PendingCall(
                        p.getString("id"),
                        p.getString("name"),
                        p.getJSONObject("input"),
                        p.getString("runs_on"),
                        p.getBoolean("confirm"),
                    )
                }
            },
        )
    }
}
