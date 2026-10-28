package com.gardentender.auth

import android.content.Context
import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationAPIClient
import com.auth0.android.authentication.storage.SecureCredentialsManager
import com.auth0.android.provider.WebAuthProvider
import com.gardentender.config.AppConfig
import com.gardentender.error.ErrorMessages
import com.gardentender.settings.SettingsStore
import kotlinx.coroutines.CancellationException

data class UserProfile(val name: String?, val email: String?)

class AuthRepository(
    private val account: Auth0,
    private val apiClient: AuthenticationAPIClient,
    private val credMgr: SecureCredentialsManager,
    private val settings: SettingsStore,
    private val config: AppConfig,
) {
    var biometricEnabled: Boolean
        get() = settings.biometricEnabled
        set(value) { settings.biometricEnabled = value }

    val isConfigured: Boolean get() = config.auth0ClientId.isNotBlank()

    fun hasValidCredentials(): Boolean = credMgr.hasValidCredentials()

    /** Launches Universal Login in the browser; [activityContext] must be an Activity. */
    suspend fun login(activityContext: Context): UserProfile {
        val result = WebAuthProvider.login(account)
            .withScheme(SCHEME)
            .withScope("openid profile email offline_access")
            .withAudience(config.auth0Audience)
            .withParameters(mapOf("prompt" to "login"))
            .await(activityContext)
        credMgr.saveCredentials(result)
        return result.user.let { UserProfile(it.name, it.email) }
    }

    /** Access token for the GardenTender API (refreshed automatically when expired). */
    suspend fun accessToken(): String = credMgr.awaitCredentials().accessToken

    suspend fun currentUser(): UserProfile {
        val creds = credMgr.awaitCredentials()
        val info = apiClient
            .userInfo(creds.accessToken)
            .await()

        return UserProfile(info.name, info.email)
    }

    /**
     * Local-only logout: revokes the refresh token (best effort) and clears stored credentials.
     * The Auth0 browser session is left alone, so [login] forces `prompt=login` to re-ask for credentials.
     * With biometric login enabled the credentials are kept so the user can log back in with a scan.
     */
    suspend fun logout() {
        if (biometricEnabled) return
        try {
            credMgr.awaitCredentials().refreshToken?.let { apiClient.revokeToken(it).await() }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            ErrorMessages.logIgnored("Refresh token revocation", e)
        }
        credMgr.clearCredentials()
    }

    private companion object {
        const val SCHEME = "gardentender-auth"
    }
}
