package com.gardentender.auth

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardentender.error.ErrorMessages
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

sealed interface AuthState {
    data object Loading : AuthState
    data object LoggedOut : AuthState
    data class LoggedIn(val user: UserProfile?) : AuthState
}

class AuthViewModel(
    private val repo: AuthRepository,
    private val biometric: BiometricAuthenticator,
) : ViewModel() {
    var state by mutableStateOf<AuthState>(AuthState.Loading)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    var biometricEnabled by mutableStateOf(repo.biometricEnabled && biometric.isAvailable())
        private set
    val biometricAvailable: Boolean get() = biometric.isAvailable()

    /** True when the login screen should offer a fingerprint login (credentials are kept while logged out). */
    val canBiometricLogin: Boolean get() = biometricEnabled && repo.hasValidCredentials()

    init {
        if (biometricEnabled && repo.hasValidCredentials()) {
            // Stay locked on the login screen until the user authenticates.
            state = AuthState.LoggedOut
        } else if (repo.isConfigured && repo.hasValidCredentials()) {
            viewModelScope.launch {
                // A failed profile fetch still leaves the user logged in; the home screen just omits the name.
                val user = try {
                    repo.currentUser()
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    ErrorMessages.logIgnored("Profile fetch", e)
                    null
                }
                state = AuthState.LoggedIn(user)
            }
        } else {
            state = AuthState.LoggedOut
            if (!repo.isConfigured) error = "Auth0 is not configured. Set auth0.domain and auth0.clientId in local.properties."
        }
    }

    fun login(activityContext: Context) {
        if (!repo.isConfigured) return
        error = null
        state = AuthState.Loading
        viewModelScope.launch {
            try {
                state = AuthState.LoggedIn(repo.login(activityContext))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                error = ErrorMessages.userMessage(e, "Login failed")
                state = AuthState.LoggedOut
            }
        }
    }

    fun loginWithBiometric(activity: FragmentActivity) {
        if (!canBiometricLogin) return
        error = null
        viewModelScope.launch {
            when (val r = biometric.authenticate(activity, "Log in to GardenTender")) {
                BiometricResult.Success -> {
                    state = AuthState.Loading
                    state = try {
                        AuthState.LoggedIn(repo.currentUser())
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        error = ErrorMessages.userMessage(e, "Login failed")
                        AuthState.LoggedOut
                    }
                }
                is BiometricResult.Failed -> error = r.message
            }
        }
    }

    /** Turns biometric login on or off; the change only applies after a successful scan. */
    fun setBiometricEnabled(activity: FragmentActivity, enabled: Boolean) {
        if (enabled == biometricEnabled) return
        if (enabled && !biometric.isAvailable()) {
            error = "Biometric authentication is not available on this device."
            return
        }
        error = null
        viewModelScope.launch {
            val title = if (enabled) "Enable biometric login" else "Disable biometric login"
            when (val r = biometric.authenticate(activity, title, "Confirm with your fingerprint")) {
                BiometricResult.Success -> {
                    repo.biometricEnabled = enabled
                    biometricEnabled = enabled
                }
                is BiometricResult.Failed -> error = r.message
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            try {
                repo.logout()
                state = AuthState.LoggedOut
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                error = ErrorMessages.userMessage(e, "Logout failed")
            }
        }
    }
}
