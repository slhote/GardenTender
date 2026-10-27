package com.gardentender

import android.graphics.Color
import android.os.Bundle
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gardentender.auth.AuthState
import com.gardentender.auth.AuthViewModel
import com.gardentender.chat.ChatFab
import com.gardentender.chat.ChatSideSheet
import com.gardentender.chat.ChatViewModel
import com.gardentender.chat.RequestNotificationPermissionWhenChatOpens
import com.gardentender.navigation.AppNavHost
import com.gardentender.navigation.Routes
import com.gardentender.settings.ThemeViewModel
import com.gardentender.ui.AppTopBar
import org.koin.androidx.compose.koinViewModel

class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val themeVm: ThemeViewModel = koinViewModel()
            val dark = themeVm.darkTheme ?: isSystemInDarkTheme()
            // Re-apply when the in-app theme changes so system bar icons follow it, not the device theme.
            DisposableEffect(dark) {
                enableEdgeToEdge(
                    statusBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT) { dark },
                    navigationBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT) { dark },
                )
                onDispose {}
            }
            MaterialTheme(colorScheme = if (dark) darkColorScheme() else lightColorScheme()) {
                Surface {
                    val nav = rememberNavController()
                    val auth: AuthViewModel = koinViewModel()
                    val chat: ChatViewModel = koinViewModel()
                    val authState = auth.state
                    val route = nav.currentBackStackEntryAsState().value?.destination?.route

                    RequestNotificationPermissionWhenChatOpens(chat.open)

                    // Route to login/home as auth state changes (login, logout, restored session).
                    LaunchedEffect(authState) {
                        when (authState) {
                            is AuthState.LoggedIn -> nav.navigate(Routes.HOME) { popUpTo(0) }
                            AuthState.LoggedOut -> {
                                chat.reset() // don't leak one user's chat to the next login
                                nav.navigate(Routes.LOGIN) { popUpTo(0) }
                            }
                            AuthState.Loading -> nav.navigate(Routes.LOADING) { popUpTo(0) }
                        }
                    }

                    Box(Modifier.fillMaxSize()) {
                        Scaffold(
                            floatingActionButton = {
                                if (authState is AuthState.LoggedIn) ChatFab(onClick = chat::show)
                            },
                            topBar = {
                                if (route != Routes.LOADING) {
                                    val onSettings = route == Routes.SETTINGS
                                    AppTopBar(
                                        title = if (onSettings) "Settings" else "GardenTender",
                                        onBack = if (onSettings) ({ nav.popBackStack() }) else null,
                                        onSettings = { if (!onSettings) nav.navigate(Routes.SETTINGS) },
                                        onLogout = if (authState is AuthState.LoggedIn) auth::logout else null,
                                    )
                                }
                            },
                        ) { padding ->
                            AppNavHost(
                                nav = nav,
                                activity = this@MainActivity,
                                auth = auth,
                                themeVm = themeVm,
                                scanVm = koinViewModel(),
                                darkTheme = dark,
                                modifier = Modifier.padding(padding).consumeWindowInsets(padding).imePadding(),
                            )
                        }
                        if (authState is AuthState.LoggedIn) ChatSideSheet(chat)
                    }
                }
            }
        }
    }
}
