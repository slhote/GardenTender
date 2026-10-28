package com.gardentender.config

import com.gardentender.BuildConfig

/** Build-time settings from `local.properties`, injected so classes don't read [BuildConfig] directly. */
data class AppConfig(
    val auth0Domain: String,
    val auth0ClientId: String,
    val auth0Audience: String,
    val apiBaseUrl: String,
) {
    companion object {
        fun fromBuildConfig() = AppConfig(
            auth0Domain = BuildConfig.AUTH0_DOMAIN,
            auth0ClientId = BuildConfig.AUTH0_CLIENT_ID,
            auth0Audience = BuildConfig.AUTH0_AUDIENCE,
            apiBaseUrl = BuildConfig.API_BASE_URL,
        )
    }
}
