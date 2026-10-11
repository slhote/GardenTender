package com.gardentender.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.gardentender.qr.PlantAction
import com.gardentender.qr.QrGenerator
import com.gardentender.qr.QrPayload
import com.gardentender.qr.QrScanner
import com.gardentender.qr.ScanResult

@Composable
fun HomeScreen(log: List<String>, onScan: () -> Unit, onGenerate: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("GardenTender QR demo", style = MaterialTheme.typography.headlineSmall)
        Button(onScan, Modifier.fillMaxWidth()) { Text("Scan a code") }
        Button(onGenerate, Modifier.fillMaxWidth()) { Text("Generate a test code") }
        Text("Activity log", style = MaterialTheme.typography.titleMedium)
        if (log.isEmpty()) Text("Nothing yet. Scan a ?action=water code.")
        log.forEach { Text(it) }
    }
}

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

@Composable
fun ScanScreen(onScanned: (String) -> Unit) {
    val context = LocalContext.current
    var granted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(Unit) { if (!granted) launcher.launch(Manifest.permission.CAMERA) }

    if (granted) {
        QrScanner(Modifier.fillMaxSize(), onScanned)
    } else {
        Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
            Text("Camera permission is needed to scan.")
            Button({ launcher.launch(Manifest.permission.CAMERA) }) { Text("Grant") }
        }
    }
}

@Composable
fun ResultScreen(result: ScanResult?, onDone: () -> Unit) {
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
