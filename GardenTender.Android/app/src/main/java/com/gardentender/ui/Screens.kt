package com.gardentender.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.gardentender.qr.PlantAction
import com.gardentender.qr.QrGenerator
import com.gardentender.qr.QrPayload
import com.gardentender.qr.QrScanner
import com.gardentender.qr.ScanResult

@Composable
fun LoginScreen(error: String?, onLogin: () -> Unit, onBiometricLogin: (() -> Unit)? = null) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("GardenTender", style = MaterialTheme.typography.headlineMedium)
        if (onBiometricLogin != null) {
            Button(onBiometricLogin, Modifier.fillMaxWidth()) { Text("Log in with fingerprint") }
            OutlinedButton(onLogin, Modifier.fillMaxWidth()) { Text("Log in with password") }
        } else {
            Button(onLogin, Modifier.fillMaxWidth()) { Text("Log in") }
        }
        if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
    }
}

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

@Composable
fun SettingsScreen(
    darkTheme: Boolean,
    onDarkThemeChange: (Boolean) -> Unit,
    biometricAvailable: Boolean,
    biometricEnabled: Boolean,
    onBiometricChange: (Boolean) -> Unit,
    error: String?,
) {
    Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("Theme", style = MaterialTheme.typography.bodyLarge)
            ThemeToggle(darkTheme, onDarkThemeChange)
        }
        if (biometricAvailable) {
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Biometric login", style = MaterialTheme.typography.bodyLarge)
                    Text("Log in with your fingerprint", style = MaterialTheme.typography.bodySmall)
                }
                Switch(biometricEnabled, onBiometricChange)
            }
        }
        if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
    }
}

/** Pill toggle showing a sun/"LIGHT MODE" or moon/"DARK MODE" state. */
@Composable
fun ThemeToggle(dark: Boolean, onChange: (Boolean) -> Unit) {
    val trackColor by animateColorAsState(if (dark) Color(0xFF2E3138) else Color(0xFFEDEDED), label = "track")
    val thumbOffset by animateDpAsState(if (dark) 64.dp else 0.dp, label = "thumb")
    val textColor = if (dark) Color(0xFF6B6F78) else Color(0xFFB0B3BA)
    val iconColor = Color(0xFFA9AEB8)
    Box(
        Modifier
            .size(104.dp, 40.dp)
            .clip(CircleShape)
            .background(trackColor)
            .toggleable(dark, role = Role.Switch, onValueChange = onChange)
            .padding(4.dp),
    ) {
        Text(
            if (dark) "DARK" else "LIGHT",
            modifier = Modifier.align(if (dark) Alignment.CenterStart else Alignment.CenterEnd).padding(horizontal = 8.dp),
            color = textColor,
            fontWeight = FontWeight.ExtraBold,
            fontSize = 9.sp,
            lineHeight = 10.sp,
            textAlign = TextAlign.Center,
        )
        Box(
            Modifier.offset(x = thumbOffset).size(32.dp).clip(CircleShape).background(Color.White),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (dark) Icons.Filled.DarkMode else Icons.Filled.LightMode,
                contentDescription = null,
                tint = iconColor,
                modifier = Modifier.size(20.dp),
            )
        }
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
