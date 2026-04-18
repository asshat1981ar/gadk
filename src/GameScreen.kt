package com.chimera.rpg

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.chimera.rpg.ui.theme.ChimeraRPGTheme

/**
 * Main gameplay screen composable.
 * Hosts the [GameViewport] and a minimal HUD overlay demonstrating Compose UI integration.
 */
@Composable
fun GameScreen() {
    Scaffold(
        containerColor = Color.Transparent
    ) {
        GameViewport(
            modifier = Modifier.padding(it)
        )
        // Minimal HUD overlay to confirm Compose UI layering works
        HUDOverlay()
    }
}

/**
 * Viewport wrapper that ensures the canvas fills available space.
 */
@Composable
private fun GameViewport(modifier: Modifier = Modifier) {
    GameViewportContent(modifier = modifier)
}

/**
 * Internal viewport content rendered via Canvas API.
 */
@Composable
internal fun GameViewportContent(modifier: Modifier = Modifier) {
    GameViewport(modifier = modifier)
}

/**
 * Simple HUD overlay displaying status text.
 */
@Composable
private fun HUDOverlay() {
    Text(
        text = "Chimera RPG — v1.0",
        color = Color.White,
        modifier = Modifier.padding(16.dp)
    )
}

/**
 * Preview provider for the GameScreen.
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
fun GameScreenPreview() {
    ChimeraRPGTheme {
        GameScreen()
    }
}