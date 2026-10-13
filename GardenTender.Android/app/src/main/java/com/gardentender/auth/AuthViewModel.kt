package com.gardentender.auth

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

sealed interface AuthState {
    data object Loading : AuthState
    data object LoggedOut : AuthState
    data class LoggedIn(val user: UserProfile?) : AuthState
}

class AuthViewModel(private val repo: AuthRepository) : ViewModel() {
    var state by mutableStateOf<AuthState>(AuthState.Loading)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    init {
        if (repo.isConfigured && repo.hasValidCredentials()) {
            viewModelScope.launch {
                state = AuthState.LoggedIn(runCatching { repo.currentUser() }.getOrNull())
            }
        } else {
            state = AuthState.LoggedOut
            if (!repo.isConfigured) error = "Auth0 is not configured. Set auth0.domain and auth0.clientId in local.properties."
        }
    }

    fun login(activityContext: Context) {
        if (!repo.isConfigured) return
        error = null
        viewModelScope.launch {
            try {
                state = AuthState.LoggedIn(repo.login(activityContext))
            } catch (e: Exception) {
                error = e.message ?: "Login failed"
            }
        }
    }

    fun logout(activityContext: Context) {
        viewModelScope.launch {
            try {
                repo.logout(activityContext)
                state = AuthState.LoggedOut
            } catch (e: Exception) {
                error = e.message ?: "Logout failed"
            }
        }
    }
}
