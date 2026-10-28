package com.gardentender.error

import android.util.Log
import com.gardentender.chat.ChatApiException

/**
 * The one place exceptions become text the user sees. Logic layers throw typed errors ([ChatApiException], Auth0's
 * exceptions); ViewModels pass them here instead of building messages themselves. Every mapped error is logged so
 * nothing is swallowed silently.
 */
object ErrorMessages {
    private const val TAG = "GardenTender"

    fun userMessage(e: Throwable, fallback: String): String {
        Log.w(TAG, fallback, e)
        return when (e) {
            is ChatApiException -> chat(e)
            else -> e.message ?: fallback
        }
    }

    /** For failures that are deliberately tolerated (best-effort work); logged, not shown. */
    fun logIgnored(what: String, e: Throwable) {
        Log.w(TAG, "$what failed (ignored)", e)
    }

    private fun chat(e: ChatApiException): String = when (e) {
        is ChatApiException.NoToken -> "Couldn't get a login token. Try logging out and back in."
        is ChatApiException.InvalidBaseUrl ->
            "api.baseUrl in local.properties isn't a valid URL (it needs http:// or https://)."
        is ChatApiException.Http -> when (e.code) {
            400 -> "The server doesn't offer that model. Pick another one."
            401 -> "Not authorized. Try logging out and back in."
            403 -> "Your account doesn't have chat access."
            else -> "Chat server error (${e.code})."
        }
        is ChatApiException.Network -> "Couldn't reach the chat server (${e.cause.javaClass.simpleName})."
        is ChatApiException.Unexpected -> "Something went wrong talking to the chat server."
    }
}
