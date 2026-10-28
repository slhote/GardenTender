package com.gardentender.di

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.work.WorkManager
import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationAPIClient
import com.auth0.android.authentication.storage.SecureCredentialsManager
import com.auth0.android.authentication.storage.SharedPreferencesStorage
import com.gardentender.auth.AuthRepository
import com.gardentender.auth.AuthViewModel
import com.gardentender.auth.BiometricAuthenticator
import com.gardentender.chat.ActivityTracker
import com.gardentender.chat.ChatApi
import com.gardentender.chat.ChatViewModel
import com.gardentender.chat.DeviceTools
import com.gardentender.config.AppConfig
import com.gardentender.qr.ScanViewModel
import com.gardentender.settings.SettingsStore
import com.gardentender.settings.ThemeViewModel
import org.koin.android.ext.koin.androidContext
import org.koin.core.module.dsl.viewModelOf
import org.koin.dsl.module

val appModule = module {
    single { AppConfig.fromBuildConfig() }
    single { SettingsStore(androidContext()) }
    single<Lifecycle> { ProcessLifecycleOwner.get().lifecycle }
    single { WorkManager.getInstance(androidContext()) }

    single { get<AppConfig>().let { Auth0.getInstance(it.auth0ClientId, it.auth0Domain) } }
    single { AuthenticationAPIClient(get<Auth0>()) }
    single { SecureCredentialsManager(get<AuthenticationAPIClient>(), get(), SharedPreferencesStorage(get())) }
    single { BiometricAuthenticator(androidContext()) }
    single { AuthRepository(get(), get(), get(), get(), get()) }

    single { ChatApi(get(), get()) }
    single { ActivityTracker() }
    single { DeviceTools(androidContext(), get(), get()) }

    viewModelOf(::AuthViewModel)
    viewModelOf(::ChatViewModel)
    viewModelOf(::ThemeViewModel)
    viewModelOf(::ScanViewModel)
}
