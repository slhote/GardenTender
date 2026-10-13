package com.gardentender.auth

import android.content.Context
import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationAPIClient
import com.auth0.android.authentication.storage.SecureCredentialsManager
import com.auth0.android.provider.WebAuthProvider
import com.gardentender.BuildConfig

data class UserProfile(val name: String?, val email: String?)

class AuthRepository(
    private val account: Auth0,
    private val apiClient: AuthenticationAPIClient,
    private val credMgr: SecureCredentialsManager,
) {
    val isConfigured: Boolean get() = BuildConfig.AUTH0_CLIENT_ID.isNotBlank()

    fun hasValidCredentials(): Boolean = credMgr.hasValidCredentials()

    /** Launches Universal Login in the browser; [activityContext] must be an Activity. */
    suspend fun login(activityContext: Context): UserProfile {
        val result = WebAuthProvider.login(account)
            .withScheme(SCHEME)
            .withScope("openid profile email offline_access")
            .withParameters(mapOf("prompt" to "login"))
            .await(activityContext)
        credMgr.saveCredentials(result)
        return result.user.let { UserProfile(it.name, it.email) }
    }

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
     */
    suspend fun logout() {
        runCatching {
            credMgr.awaitCredentials().refreshToken?.let { apiClient.revokeToken(it).await() }
        }
        credMgr.clearCredentials()
    }

    private companion object {
        const val SCHEME = "gardentender-auth"
    }
}
