package com.gardentender.qr

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.dp

/** Only form-local state (plant id, action chip), so it has no ViewModel. */
@Composable
fun GenerateScreen() {
    var id by remember { mutableStateOf("tomato-1") }
    var water by remember { mutableStateOf(false) }
    val payload = QrPayload.build(id.ifBlank { "unnamed" }, if (water) PlantAction.Water else null)
    val bitmap = remember(payload) { QrGenerator.encode(payload) }
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        OutlinedTextField(id, { id = it }, label = { Text("Plant id") }, modifier = Modifier.fillMaxWidth())
        FilterChip(water, { water = !water }, label = { Text("Action: water") })
        Image(bitmap.asImageBitmap(), contentDescription = "QR code", modifier = Modifier.size(280.dp))
        Text(payload, style = MaterialTheme.typography.bodySmall)
    }
}
