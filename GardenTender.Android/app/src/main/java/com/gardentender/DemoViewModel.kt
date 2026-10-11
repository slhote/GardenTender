package com.gardentender

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.gardentender.qr.QrPayload
import com.gardentender.qr.ScanResult
import java.text.DateFormat
import java.util.Date

class DemoViewModel : ViewModel() {
    var lastResult by mutableStateOf<ScanResult?>(null)
        private set
    val activityLog = mutableStateListOf<String>()

    /** Parses a scanned string, performs its action, and returns the result. */
    fun onScanned(raw: String): ScanResult {
        val result = QrPayload.parse(raw)
        if (result is ScanResult.PlantActionRequest) {
            val time = DateFormat.getTimeInstance().format(Date())
            activityLog.add(0, "$time - ${result.action.key} ${result.id}")
        }
        lastResult = result
        return result
    }
}
