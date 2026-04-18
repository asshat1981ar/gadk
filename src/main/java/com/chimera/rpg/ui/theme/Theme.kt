package com.chimera.rpg.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * RPG Android application theme definition.
 * Handles light/dark theme switching and system UI integration.
 */
private val DarkColorScheme = darkColorScheme(
    primary = OnPrimary,
    secondary = OnSecondary,
    background = Background,
    surface = surface,
    onPrimary = Primary,
    onSecondary = Secondary,
    onBackground = OnSurface,
    onSurface = OnSurface
)

private val LightColorScheme = lightColorScheme(
    primary = OnPrimary,
    secondary = OnSecondary,
    background = Background,
    surface = surface,
    onPrimary = Primary,
    onSecondary = Secondary,
    onBackground = OnSurface,
    onSurface = OnSurface
)

/**
 * Main theme composable for the RPG application.
 * Applies the appropriate color scheme based on system settings.
 */
@Composable
fun RPG_AndroidTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}

/**
 * Sets up system UI integration for the RPG application.
 * Handles status bar and navigation bar styling.
 */
@Composable
fun RPGAndroidSetupContent() {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            val controller = WindowInsetsControllerCompat(window, view)
            controller.isAppearanceLightStatusBars = darkTheme
        }
    }
}