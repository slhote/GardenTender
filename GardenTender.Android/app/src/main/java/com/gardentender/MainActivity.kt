package com.gardentender

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.viewmodel.compose.viewModel
import org.koin.androidx.compose.koinViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.gardentender.auth.AuthState
import com.gardentender.auth.AuthViewModel
import com.gardentender.ui.GenerateScreen
import com.gardentender.ui.HomeScreen
import com.gardentender.ui.LoginScreen
import com.gardentender.ui.ResultScreen
import com.gardentender.ui.ScanScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    val nav = rememberNavController()
                    val vm: DemoViewModel = viewModel()
                    val auth: AuthViewModel = koinViewModel()
                    val authState = auth.state

                    // Route to login/home as auth state changes (login, logout, restored session).
                    LaunchedEffect(authState) {
                        when (authState) {
                            is AuthState.LoggedIn -> nav.navigate("home") { popUpTo(0) }
                            AuthState.LoggedOut -> nav.navigate("login") { popUpTo(0) }
                            AuthState.Loading -> Unit
                        }
                    }

                    NavHost(nav, startDestination = "loading") {
                        composable("loading") { }
                        composable("login") {
                            LoginScreen(auth.error) { auth.login(this@MainActivity) }
                        }
                        composable("home") {
                            val user = (authState as? AuthState.LoggedIn)?.user
                            HomeScreen(
                                userLabel = user?.email ?: user?.name,
                                log = vm.activityLog,
                                onScan = { nav.navigate("scan") },
                                onGenerate = { nav.navigate("generate") },
                                onLogout = { auth.logout() },
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
            }
        }
    }
}
