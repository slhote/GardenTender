package com.gardentender

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.gardentender.ui.GenerateScreen
import com.gardentender.ui.HomeScreen
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
                    NavHost(nav, startDestination = "home") {
                        composable("home") {
                            HomeScreen(vm.activityLog, { nav.navigate("scan") }, { nav.navigate("generate") })
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
