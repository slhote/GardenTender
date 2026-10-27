package com.gardentender.qr

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ScanResultScreen(result: ScanResult?, onDone: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when (result) {
            is ScanResult.PlantView -> {
                Text("Plant: ${result.id}", style = MaterialTheme.typography.headlineSmall)
            }
            is ScanResult.PlantActionRequest -> {
                Text("Plant: ${result.id}", style = MaterialTheme.typography.headlineSmall)
                Text("Logged action: ${result.action.key}")
            }
            is ScanResult.Unknown -> {
                Text("Not a GardenTender code", style = MaterialTheme.typography.headlineSmall)
                Text(result.raw)
            }
            null -> Text("No scan yet")
        }
        Button(onDone) { Text("Done") }
    }
}
