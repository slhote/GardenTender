package com.gardentender.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.gardentender.ui.ErrorText

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
        ErrorText(error)
    }
}
