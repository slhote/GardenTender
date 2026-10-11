package com.gardentender.qr

import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder

enum class PlantAction(val key: String) {
    Water("water");

    companion object {
        fun fromKey(key: String?) = entries.firstOrNull { it.key == key }
    }
}

sealed interface ScanResult {
    data class PlantView(val id: String) : ScanResult
    data class PlantActionRequest(val id: String, val action: PlantAction) : ScanResult
    data class Unknown(val raw: String) : ScanResult
}

object QrPayload {
    private const val SCHEME = "gardentender"
    private const val HOST = "plant"

    fun build(id: String, action: PlantAction? = null): String {
        val base = "$SCHEME://$HOST/${URLEncoder.encode(id, "UTF-8")}"
        return if (action == null) base else "$base?action=${action.key}"
    }

    fun parse(raw: String): ScanResult {
        val uri = try {
            URI(raw.trim())
        } catch (_: Exception) {
            return ScanResult.Unknown(raw)
        }
        if (uri.scheme != SCHEME || uri.host != HOST) return ScanResult.Unknown(raw)
        val id = uri.rawPath?.removePrefix("/")?.takeIf { it.isNotBlank() }
            ?.let { URLDecoder.decode(it, "UTF-8") }
            ?: return ScanResult.Unknown(raw)
        val actionKey = uri.rawQuery?.split("&")
            ?.map { it.split("=", limit = 2) }
            ?.firstOrNull { it[0] == "action" }
            ?.getOrNull(1)
        if (actionKey == null) return ScanResult.PlantView(id)
        val action = PlantAction.fromKey(actionKey) ?: return ScanResult.Unknown(raw)
        return ScanResult.PlantActionRequest(id, action)
    }
}
