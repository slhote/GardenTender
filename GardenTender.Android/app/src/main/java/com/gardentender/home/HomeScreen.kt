package com.gardentender.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun HomeScreen(
    userLabel: String?,
    log: List<String>,
    onScan: () -> Unit,
    onGenerate: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("GardenTender QR demo", style = MaterialTheme.typography.headlineSmall)
        if (userLabel != null) Text("Signed in as $userLabel")
        Button(onScan, Modifier.fillMaxWidth()) { Text("Scan a code") }
        Button(onGenerate, Modifier.fillMaxWidth()) { Text("Generate a test code") }
        Text("Activity log", style = MaterialTheme.typography.titleMedium)
        if (log.isEmpty()) Text("Nothing yet. Scan a ?action=water code.")
        log.forEach { Text(it) }
    }
}
