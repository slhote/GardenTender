package com.gardentender.di

import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationAPIClient
import com.auth0.android.authentication.storage.SecureCredentialsManager
import com.auth0.android.authentication.storage.SharedPreferencesStorage
import com.gardentender.BuildConfig
import com.gardentender.auth.AuthRepository
import com.gardentender.auth.AuthViewModel
import com.gardentender.auth.BiometricAuthenticator
import com.gardentender.chat.ActivityTracker
import com.gardentender.chat.ChatApi
import com.gardentender.chat.DeviceTools
import com.gardentender.chat.ChatViewModel
import com.gardentender.settings.ThemeViewModel
import org.koin.android.ext.koin.androidContext
import org.koin.core.module.dsl.viewModelOf
import org.koin.dsl.module

val appModule = module {
    single { Auth0.getInstance(BuildConfig.AUTH0_CLIENT_ID, BuildConfig.AUTH0_DOMAIN) }
    single { AuthenticationAPIClient(get<Auth0>()) }
    single { SecureCredentialsManager(get<AuthenticationAPIClient>(), get(), SharedPreferencesStorage(get())) }
    single { BiometricAuthenticator(androidContext()) }
    single { AuthRepository(get(), get(), get(), androidContext()) }
    single { ChatApi(get()) }
    single { ActivityTracker() }
    single { DeviceTools(androidContext(), get()) }
    viewModelOf(::AuthViewModel)
    viewModelOf(::ChatViewModel)
    viewModelOf(::ThemeViewModel)
}
