package com.gardentender.chat

import com.gardentender.BuildConfig
import com.gardentender.auth.AuthRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
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

class ChatApiException(message: String) : Exception(message)

/**
 * Talks to GardenTender.Api `/chat`. [history] is opaque: it is echoed back from the previous response so the
 * server can stay stateless.
 */
class ChatApi(private val auth: AuthRepository) {
    suspend fun chat(
        history: JSONArray,
        message: String?,
        decisions: Map<String, Boolean>,
        deviceResults: Map<String, DeviceResult>,
    ): ChatReply =
        withContext(Dispatchers.IO) {
            val token = try {
                auth.accessToken()
            } catch (e: Exception) {
                throw ChatApiException("Couldn't get a login token. Try logging out and back in.")
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

            val url = try {
                URL("${BuildConfig.API_BASE_URL}/chat")
            } catch (e: java.net.MalformedURLException) {
                throw ChatApiException("api.baseUrl in local.properties isn't a valid URL (it needs http:// or https://).")
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
                if (code !in 200..299) {
                    throw ChatApiException(
                        when (code) {
                            401 -> "Not authorized. Try logging out and back in."
                            403 -> "Your account doesn't have chat access."
                            else -> "Chat server error ($code)."
                        },
                    )
                }
                val json = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
                val pending = json.getJSONArray("pending")
                ChatReply(
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
            } catch (e: ChatApiException) {
                throw e
            } catch (e: java.io.IOException) {
                android.util.Log.w("ChatApi", "chat request failed", e)
                throw ChatApiException("Couldn't reach the chat server (${e.javaClass.simpleName}).")
            } finally {
                conn.disconnect()
            }
        }
}
