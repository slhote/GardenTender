package com.gardentender

import android.os.Bundle
import androidx.fragment.app.FragmentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import android.graphics.Color
import androidx.compose.runtime.DisposableEffect
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gardentender.auth.AuthState
import com.gardentender.auth.AuthViewModel
import com.gardentender.chat.ChatFab
import com.gardentender.chat.ChatSideSheet
import com.gardentender.chat.ChatViewModel
import com.gardentender.settings.ThemeViewModel
import com.gardentender.ui.GenerateScreen
import com.gardentender.ui.HomeScreen
import com.gardentender.ui.LoginScreen
import com.gardentender.ui.ResultScreen
import com.gardentender.ui.ScanScreen
import com.gardentender.ui.SettingsScreen
import org.koin.androidx.compose.koinViewModel

class MainActivity : FragmentActivity() {
    @OptIn(ExperimentalMaterial3Api::class)
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
                    val vm: DemoViewModel = viewModel()
                    val auth: AuthViewModel = koinViewModel()
                    val chat: ChatViewModel = koinViewModel()
                    val authState = auth.state
                    val route = nav.currentBackStackEntryAsState().value?.destination?.route
                    var menuOpen by remember { mutableStateOf(false) }

                    // Reminders are shown as notifications, so ask for the permission the first time chat opens.
                    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
                    LaunchedEffect(chat.open) {
                        if (chat.open && android.os.Build.VERSION.SDK_INT >= 33) {
                            notifPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                        }
                    }

                    // Route to login/home as auth state changes (login, logout, restored session).
                    LaunchedEffect(authState) {
                        when (authState) {
                            is AuthState.LoggedIn -> nav.navigate("home") { popUpTo(0) }
                            AuthState.LoggedOut -> {
                                chat.reset() // don't leak one user's chat to the next login
                                nav.navigate("login") { popUpTo(0) }
                            }
                            AuthState.Loading -> nav.navigate("loading") { popUpTo(0) }
                        }
                    }

                    Box(Modifier.fillMaxSize()) {
                    Scaffold(
                        floatingActionButton = {
                            if (authState is AuthState.LoggedIn) ChatFab(onClick = chat::show)
                        },
                        topBar = {
                            if (route != "loading") {
                                // Plain Surface instead of TopAppBar: TopAppBar animates its container
                                // color, which lags behind the rest of the screen on theme change.
                                Surface(color = MaterialTheme.colorScheme.surface) {
                                    Row(
                                        Modifier.fillMaxWidth().statusBarsPadding().height(64.dp).padding(horizontal = 4.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        if (route == "settings") {
                                            IconButton({ nav.popBackStack() }) {
                                                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                                            }
                                        }
                                        Text(
                                            if (route == "settings") "Settings" else "GardenTender",
                                            style = MaterialTheme.typography.titleLarge,
                                            modifier = Modifier.weight(1f).padding(start = if (route == "settings") 4.dp else 12.dp),
                                        )
                                        Box {
                                            IconButton({ menuOpen = true }) {
                                                Icon(Icons.Default.AccountCircle, "Profile menu")
                                            }
                                            DropdownMenu(menuOpen, { menuOpen = false }) {
                                                DropdownMenuItem(
                                                    text = { Text("Settings") },
                                                    onClick = {
                                                        menuOpen = false
                                                        if (route != "settings") nav.navigate("settings")
                                                    },
                                                )
                                                if (authState is AuthState.LoggedIn) {
                                                    DropdownMenuItem(
                                                        text = { Text("Log out") },
                                                        onClick = {
                                                            menuOpen = false
                                                            auth.logout()
                                                        },
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    ) { padding ->
                        NavHost(nav, startDestination = "loading", modifier = Modifier.padding(padding).consumeWindowInsets(padding).imePadding()) {
                            composable("loading") {
                                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                    CircularProgressIndicator()
                                }
                            }
                            composable("login") {
                                LoginScreen(
                                    error = auth.error,
                                    onLogin = { auth.login(this@MainActivity) },
                                    onBiometricLogin = if (auth.canBiometricLogin) {
                                        { auth.loginWithBiometric(this@MainActivity) }
                                    } else null,
                                )
                            }
                            composable("home") {
                                val user = (authState as? AuthState.LoggedIn)?.user
                                HomeScreen(
                                    userLabel = user?.email ?: user?.name,
                                    log = vm.activityLog,
                                    onScan = { nav.navigate("scan") },
                                    onGenerate = { nav.navigate("generate") },
                                )
                            }
                            composable("settings") {
                                SettingsScreen(
                                    darkTheme = dark,
                                    onDarkThemeChange = themeVm::setDarkTheme,
                                    biometricAvailable = auth.biometricAvailable,
                                    biometricEnabled = auth.biometricEnabled,
                                    onBiometricChange = { auth.setBiometricEnabled(this@MainActivity, it) },
                                    error = auth.error,
                                )
                            }
                            composable("generate") { GenerateScreen() }
                            composable("scan") {
                                ScanScreen { raw ->
                                    vm.onScanned(raw)
                                    nav.navigate("result") { popUpTo("home") }
                                }
                            }
                            composable("result") {
                                ResultScreen(vm.lastResult) { nav.popBackStack("home", false) }
                            }
                        }
                    }
                    if (authState is AuthState.LoggedIn) ChatSideSheet(chat)
                    }
                }
            }
        }
    }
}
