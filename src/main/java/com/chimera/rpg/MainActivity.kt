package com.chimera.rpg

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.chimera.rpg.ui.theme.RPGTheme
import com.chimera.rpg.ui.theme.splashScreenBackground
import kotlinx.coroutines.delay

/**
 * Main entry point for the RPG application.
 * Hosts the navigation container and manages top-level UI state.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        installSplashScreen()

        setContent {
            RPGTheme {
                // Surface container using the 'background' color from the theme
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    RPGNavigation()
                }
            }
        }
    }
}

/**
 * Navigation entry point that shows a splash screen briefly then
 * transitions to the main menu.
 */
@Composable
fun RPGNavigation() {
    var showSplash by remember { mutableStateOf(true) }
    val context = LocalContext.current

    // Ensure splash screen is installed before we control visibility
    LaunchedEffect(Unit) {
        // Brief splash display (mimics real app initialization)
        delay(1500)
        showSplash = false
    }

    if (showSplash) {
        SplashScreenView()
    } else {
        MainMenu(onNavigateToSettings = {
            // In a full app you would use a Navigation Controller/NavHost here.
            // For this scaffold, we simply restart main menu with a different route.
            // The composable will be recomposed with the settings content.
        })
    }
}

/**
 * Splash screen composable using Canvas API for 2D rendering.
 */
@Composable
fun SplashScreenView() {
    val context = LocalContext.current
    SplashScreen()
}

/**
 * Preview provider for [SplashScreenView].
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
fun SplashScreenPreview() {
    RPGTheme { SplashScreen() }
}

/**
 * Preview provider for [RPGNavigation].
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
fun NavigationPreview() {
    RPGTheme { RPGNavigation() }
}