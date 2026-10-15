package com.gardentender.chat

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.provider.CalendarContract
import androidx.core.app.NotificationManagerCompat
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import org.json.JSONObject
import java.time.Duration
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.concurrent.TimeUnit

data class DeviceResult(val content: String, val isError: Boolean = false)

/**
 * Executes the tool calls the server hands to the phone (`runs_on == "device"`). The server has already
 * validated the arguments; this still handles anything the device itself can reject (past times, disabled
 * notifications, no calendar app).
 */
class DeviceTools(private val context: Context) {
    fun execute(call: PendingCall): DeviceResult = try {
        when (call.name) {
            "set_reminder" -> setReminder(call.input)
            "add_calendar_event" -> addCalendarEvent(call.input)
            else -> DeviceResult("Unknown device tool ${call.name}.", isError = true)
        }
    } catch (e: DateTimeParseException) {
        DeviceResult("Couldn't read the date/time.", isError = true)
    }

    private fun setReminder(input: JSONObject): DeviceResult {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            return DeviceResult("Notifications are disabled for GardenTender, so the reminder can't be shown.", isError = true)
        }
        val at = parseLocal(input.getString("time"))
        val delay = Duration.between(LocalDateTime.now(), at)
        if (delay.isNegative) return DeviceResult("That time is in the past.", isError = true)

        // WorkManager survives reboots and needs no exact-alarm permission; delivery can be a few minutes late.
        val request = OneTimeWorkRequestBuilder<ReminderWorker>()
            .setInitialDelay(delay.toMillis(), TimeUnit.MILLISECONDS)
            .setInputData(workDataOf(ReminderWorker.KEY_TEXT to input.getString("text")))
            .build()
        WorkManager.getInstance(context).enqueue(request)
        return DeviceResult("Reminder set for ${at.format(DISPLAY)}.")
    }

    private fun addCalendarEvent(input: JSONObject): DeviceResult {
        val start = parseLocal(input.getString("start"))
        val end = if (input.has("end") && !input.isNull("end")) parseLocal(input.getString("end")) else start.plusHours(1)
        val intent = Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, input.getString("title"))
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, toMillis(start))
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, toMillis(end))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            DeviceResult("Opened the calendar app with the event prefilled. The user still has to save it there.")
        } catch (e: ActivityNotFoundException) {
            DeviceResult("No calendar app is installed.", isError = true)
        }
    }

    /** Local ISO 8601; if the model included an offset, convert it to the device's zone. */
    private fun parseLocal(value: String): LocalDateTime = try {
        LocalDateTime.parse(value)
    } catch (e: DateTimeParseException) {
        OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault()).toLocalDateTime()
    }

    private fun toMillis(t: LocalDateTime) = t.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()

    private companion object {
        val DISPLAY: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
    }
}
