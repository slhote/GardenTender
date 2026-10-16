package com.gardentender.chat

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.withStarted
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import org.json.JSONArray

data class ChatMessage(val text: String, val fromUser: Boolean)

/**
 * Holds the conversation. Scoped to the activity so it survives closing the sheet,
 * navigating between screens, and configuration changes. It is memory-only on purpose: closing the app clears it.
 */
class ChatViewModel(
    private val api: ChatApi,
    private val device: DeviceTools,
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

    // Set when the whole app leaves the foreground (e.g. the calendar app opens) while a request is running.
    private var backgrounded = false
    private val processObserver = object : DefaultLifecycleObserver {
        override fun onStop(owner: LifecycleOwner) { backgrounded = true }
    }

    init {
        ProcessLifecycleOwner.get().lifecycle.addObserver(processObserver)
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
    }

    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || sending || held.isNotEmpty()) return
        messages.add(ChatMessage(trimmed, fromUser = true))
        sending = true
        viewModelScope.launch { call(trimmed, emptyMap(), emptyMap()) }
    }

    /** Approving runs the calls and tells the server. Declining is handled locally so it works offline. */
    fun decide(approved: Boolean) {
        if (approved) resume(approved = true) else declineLocally()
    }

    /**
     * Drops the paused tool request and keeps the chat usable. The assistant turn that asked for the action is
     * removed from the server history, so no network request is needed and the card can never get stuck.
     */
    private fun declineLocally() {
        if (sending || held.isEmpty()) return
        val last = history.length() - 1
        if (last >= 0 && history.getJSONObject(last).optString("role") == "assistant") {
            history = JSONArray((0 until last).map { history.get(it) })
        }
        held = emptyList()
        pending = emptyList()
        deviceDone.clear()
        messages.add(ChatMessage("Okay, I won't do that.", fromUser = false))
    }

    private fun resume(approved: Boolean) {
        if (sending || held.isEmpty()) return
        sending = true
        val calls = held
        pending = emptyList() // hide the card right away; it comes back only if the request fails
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
            backgrounded = false
            val reply = try {
                api.chat(history, message, decisions, deviceResults)
            } catch (e: ChatApiException) {
                // Android can cut the connection while the app is in the background. If that's what happened,
                // wait for the user to come back and try once more (device results are cached, so nothing re-runs).
                if (!e.isNetwork || !backgrounded) throw e
                ProcessLifecycleOwner.get().lifecycle.withStarted { }
                backgrounded = false
                api.chat(history, message, decisions, deviceResults)
            }
            history = reply.history
            held = reply.pending
            pending = held.filter { it.confirm }
            deviceDone.clear()
            if (reply.reply.isNotBlank()) messages.add(ChatMessage(reply.reply, fromUser = false))
            chainResume = held.isNotEmpty() && pending.isEmpty()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            // Anything unexpected (bad JSON, etc.) should show up in the chat, not crash the app.
            messages.add(ChatMessage((e as? ChatApiException)?.message ?: "Something went wrong talking to the chat server.", fromUser = false))
            if (held.none { it.confirm } && held.isNotEmpty()) {
                // Nothing for the user to retry from: drop the dangling tool request so the chat can continue.
                history = JSONArray((0 until history.length() - 1).map { history.get(it) })
                held = emptyList()
                deviceDone.clear()
            }
            pending = held.filter { it.confirm }
        } finally {
            sending = false
        }
        if (chainResume) resume(approved = true)
    }

    override fun onCleared() {
        ProcessLifecycleOwner.get().lifecycle.removeObserver(processObserver)
    }
}
