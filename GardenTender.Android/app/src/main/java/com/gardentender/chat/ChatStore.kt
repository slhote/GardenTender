package com.gardentender.chat

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class StoredChat(val messages: List<ChatMessage>, val history: JSONArray, val held: List<PendingCall>)

/**
 * Keeps the conversation across app restarts in app-private storage (a small JSON file). Cleared on logout.
 * The held calls are stored too, so a restart while the server is waiting on an approval can still resume.
 */
class ChatStore(context: Context) {
    private val file = File(context.filesDir, "chat.json")

    fun save(messages: List<ChatMessage>, history: JSONArray, held: List<PendingCall>) {
        val json = JSONObject()
            .put("messages", JSONArray(messages.map { JSONObject().put("text", it.text).put("fromUser", it.fromUser) }))
            .put("history", history)
            .put(
                "held",
                JSONArray(
                    held.map {
                        JSONObject().put("id", it.id).put("name", it.name).put("input", it.input)
                            .put("runsOn", it.runsOn).put("confirm", it.confirm)
                    },
                ),
            )
        file.writeText(json.toString())
    }

    fun load(): StoredChat? = try {
        val json = JSONObject(file.readText())
        val messages = json.getJSONArray("messages")
        val held = json.getJSONArray("held")
        StoredChat(
            messages = (0 until messages.length()).map {
                messages.getJSONObject(it).let { m -> ChatMessage(m.getString("text"), m.getBoolean("fromUser")) }
            },
            history = json.getJSONArray("history"),
            held = (0 until held.length()).map {
                held.getJSONObject(it).let { h ->
                    PendingCall(h.getString("id"), h.getString("name"), h.getJSONObject("input"), h.getString("runsOn"), h.getBoolean("confirm"))
                }
            },
        )
    } catch (e: Exception) {
        null // missing or unreadable: start fresh
    }

    fun clear() {
        file.delete()
    }
}
