package com.gardentender.settings

import android.content.Context

/** The app's persisted preferences (the "settings" SharedPreferences file), shared by theme and auth. */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    /** null means "follow the system theme". */
    var darkTheme: Boolean?
        get() = if (prefs.contains(KEY_DARK)) prefs.getBoolean(KEY_DARK, false) else null
        set(value) {
            if (value == null) prefs.edit().remove(KEY_DARK).apply() else prefs.edit().putBoolean(KEY_DARK, value).apply()
        }

    var biometricEnabled: Boolean
        get() = prefs.getBoolean(KEY_BIOMETRIC, false)
        set(value) = prefs.edit().putBoolean(KEY_BIOMETRIC, value).apply()

    private companion object {
        const val KEY_DARK = "dark_theme"
        const val KEY_BIOMETRIC = "biometric_login"
    }
}
