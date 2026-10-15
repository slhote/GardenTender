package com.gardentender.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import org.json.JSONArray

data class ChatMessage(val text: String, val fromUser: Boolean)

/**
 * Holds the conversation. Scoped to the activity so it survives closing the sheet,
 * navigating between screens, and configuration changes; [ChatStore] carries it across restarts.
 */
class ChatViewModel(
    private val api: ChatApi,
    private val device: DeviceTools,
    private val store: ChatStore,
) : ViewModel() {
    val messages = mutableStateListOf<ChatMessage>()
    var open by mutableStateOf(false)
        private set
    var sending by mutableStateOf(false)
        private set

    /** Calls waiting for the user's approval (the card shown in the sheet). */
    var pending by mutableStateOf<List<PendingCall>>(emptyList())
        private set

    // Opaque server-side conversation state, echoed back on every request.
    private var history = JSONArray()

    // Every call the server is paused on: approval-needed ones plus device calls that run without asking.
    private var held = emptyList<PendingCall>()

    // Device calls already executed for the current pause, so a failed resume is never run twice.
    private val deviceDone = mutableMapOf<String, DeviceResult>()

    init {
        store.load()?.let {
            messages.addAll(it.messages)
            history = it.history
            held = it.held
            pending = held.filter { c -> c.confirm }
            if (held.isNotEmpty() && pending.isEmpty()) resume(approved = true)
        }
    }

    fun show() { open = true }
    fun hide() { open = false }

    fun reset() {
        open = false
        messages.clear()
        pending = emptyList()
        held = emptyList()
        deviceDone.clear()
        history = JSONArray()
        sending = false
        store.clear()
    }

    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || sending || held.isNotEmpty()) return
        messages.add(ChatMessage(trimmed, fromUser = true))
        sending = true
        viewModelScope.launch { call(trimmed, emptyMap(), emptyMap()) }
    }

    /** Approves or declines every call that asked for approval; runs the device calls that don't need it. */
    fun decide(approved: Boolean) = resume(approved)

    private fun resume(approved: Boolean) {
        if (sending || held.isEmpty()) return
        sending = true
        val calls = held
        viewModelScope.launch {
            val decisions = mutableMapOf<String, Boolean>()
            val results = mutableMapOf<String, DeviceResult>()
            for (c in calls) {
                if (c.runsOn == "device") {
                    results[c.id] = if (c.confirm && !approved) {
                        DeviceResult("The user declined this action.", isError = true)
                    } else {
                        deviceDone.getOrPut(c.id) { device.execute(c) }
                    }
                } else {
                    decisions[c.id] = approved
                }
            }
            call(null, decisions, results)
        }
    }

    private suspend fun call(message: String?, decisions: Map<String, Boolean>, deviceResults: Map<String, DeviceResult>) {
        var chainResume = false
        try {
            val reply = api.chat(history, message, decisions, deviceResults)
            history = reply.history
            held = reply.pending
            pending = held.filter { it.confirm }
            deviceDone.clear()
            if (reply.reply.isNotBlank()) messages.add(ChatMessage(reply.reply, fromUser = false))
            chainResume = held.isNotEmpty() && pending.isEmpty()
        } catch (e: ChatApiException) {
            messages.add(ChatMessage(e.message ?: "Something went wrong.", fromUser = false))
            if (held.none { it.confirm } && held.isNotEmpty()) {
                // Nothing for the user to retry from: drop the dangling tool request so the chat can continue.
                history = JSONArray((0 until history.length() - 1).map { history.get(it) })
                held = emptyList()
                deviceDone.clear()
            }
            pending = held.filter { it.confirm }
        } finally {
            sending = false
            store.save(messages, history, held)
        }
        if (chainResume) resume(approved = true)
    }
}
