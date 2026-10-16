package com.gardentender.chat

import org.json.JSONObject
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

private val DATE_TIME = DateTimeFormatter.ofPattern("EEE, MMM d 'at' h:mm a", Locale.getDefault())
private val TIME_ONLY = DateTimeFormatter.ofPattern("h:mm a", Locale.getDefault())

/** Plain-language description of a pending call for the approval card. */
fun describeCall(call: PendingCall): String {
    val input = call.input
    return when (call.name) {
        "add_calendar_event" -> {
            val start = parse(input.optString("start"))
            val end = if (input.isNull("end")) null else parse(input.optString("end"))
            buildString {
                append("Add \"${input.optString("title")}\" to your calendar")
                if (start != null) {
                    append(" on ${start.format(DATE_TIME)}")
                    if (end != null) {
                        append(if (end.toLocalDate() == start.toLocalDate()) " until ${end.format(TIME_ONLY)}" else " until ${end.format(DATE_TIME)}")
                    }
                }
            }
        }
        "set_reminder" -> {
            val at = parse(input.optString("time"))
            "Remind you: \"${input.optString("text")}\"" + (at?.let { " on ${it.format(DATE_TIME)}" } ?: "")
        }
        "update_plant" -> "Change plant #${input.optString("plant_id")}'s ${fieldLabel(input)} to \"${input.optString("value")}\""
        else -> fallback(call)
    }
}

private fun fieldLabel(input: JSONObject): String = when (val field = input.optString("field")) {
    "water_every_days" -> "watering interval (days)"
    else -> field
}

private fun parse(value: String): LocalDateTime? = try {
    LocalDateTime.parse(value)
} catch (e: DateTimeParseException) {
    try {
        OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
    } catch (e: DateTimeParseException) {
        null
    }
}

private fun fallback(call: PendingCall): String {
    val args = call.input.keys().asSequence().joinToString(", ") { "$it=${call.input.get(it)}" }
    return "${call.name}($args)"
}
