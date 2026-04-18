package com.chimera.rpg.ui.theme

import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.chimera.rpg.R

/**
 * Custom type definitions for the RPG application.
 * Contains font families and typographic scales.
 */
val RPGFontFamily = FontFamily(
    Font(R.font.noto_sans)
)

/**
 * Typography scale for RPG UI elements.
 * Defines text styles for headers, body text, and captions.
 */
object RPGTypography {
    val headingLarge = androidx.compose.material3.Typography.headlineLarge.copy(
        fontFamily = RPGFontFamily,
        fontWeight = FontWeight.Bold,
        fontSize = 32.sp
    )

    val headingMedium = androidx.compose.material3.Typography.headlineMedium.copy(
        fontFamily = RPGFontFamily,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp
    )

    val bodyLarge = androidx.compose.material3.Typography.bodyLarge.copy(
        fontFamily = RPGFontFamily,
        fontSize = 16.sp
    )

    val bodyMedium = androidx.compose.material3.Typography.bodyMedium.copy(
        fontFamily = RPGFontFamily,
        fontSize = 14.sp
    )

    val labelLarge = androidx.compose.material3.Typography.labelLarge.copy(
        fontFamily = RPGFontFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp
    )
}