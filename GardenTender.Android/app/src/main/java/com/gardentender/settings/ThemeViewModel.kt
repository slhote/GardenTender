package com.gardentender.settings

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel

class ThemeViewModel(private val settings: SettingsStore) : ViewModel() {
    var darkTheme by mutableStateOf(settings.darkTheme)
        private set

    fun setDarkTheme(enabled: Boolean) {
        darkTheme = enabled
        settings.darkTheme = enabled
    }
}
