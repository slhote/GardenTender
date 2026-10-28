package com.gardentender.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.gardentender.auth.AuthState
import com.gardentender.auth.AuthViewModel
import com.gardentender.auth.LoginScreen
import com.gardentender.home.HomeScreen
import com.gardentender.qr.GenerateScreen
import com.gardentender.qr.ScanResultScreen
import com.gardentender.qr.ScanScreen
import com.gardentender.qr.ScanViewModel
import com.gardentender.settings.SettingsScreen
import com.gardentender.settings.ThemeViewModel

/** All screens and the routes between them. ViewModels are activity-scoped and passed in by `MainActivity`. */
@Composable
fun AppNavHost(
    nav: NavHostController,
    activity: FragmentActivity,
    auth: AuthViewModel,
    themeVm: ThemeViewModel,
    scanVm: ScanViewModel,
    darkTheme: Boolean,
    modifier: Modifier = Modifier,
) {
    NavHost(nav, startDestination = Routes.LOADING, modifier = modifier) {
        composable(Routes.LOADING) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        composable(Routes.LOGIN) {
            LoginScreen(
                error = auth.error,
                onLogin = { auth.login(activity) },
                onBiometricLogin = if (auth.canBiometricLogin) {
                    { auth.loginWithBiometric(activity) }
                } else null,
            )
        }
        composable(Routes.HOME) {
            val user = (auth.state as? AuthState.LoggedIn)?.user
            HomeScreen(
                userLabel = user?.email ?: user?.name,
                log = scanVm.activityLog,
                onScan = { nav.navigate(Routes.SCAN) },
                onGenerate = { nav.navigate(Routes.GENERATE) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(
                darkTheme = darkTheme,
                onDarkThemeChange = themeVm::setDarkTheme,
                biometricAvailable = auth.biometricAvailable,
                biometricEnabled = auth.biometricEnabled,
                onBiometricChange = { auth.setBiometricEnabled(activity, it) },
                error = auth.error,
            )
        }
        composable(Routes.GENERATE) { GenerateScreen() }
        composable(Routes.SCAN) {
            ScanScreen { raw ->
                scanVm.onScanned(raw)
                nav.navigate(Routes.RESULT) { popUpTo(Routes.HOME) }
            }
        }
        composable(Routes.RESULT) {
            ScanResultScreen(scanVm.lastResult) { nav.popBackStack(Routes.HOME, false) }
        }
    }
}
