package com.gardentender.settings

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel

class ThemeViewModel(context: Context) : ViewModel() {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var darkTheme by mutableStateOf<Boolean?>(
        if (prefs.contains(KEY_DARK)) prefs.getBoolean(KEY_DARK, false) else null,
    )
        private set

    fun setDarkTheme(enabled: Boolean) {
        darkTheme = enabled
        prefs.edit().putBoolean(KEY_DARK, enabled).apply()
    }

    private companion object {
        const val KEY_DARK = "dark_theme"
    }
}
