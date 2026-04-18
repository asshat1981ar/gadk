package com.chimera.rpg

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.chimera.rpg.ui.theme.ChimeraRPGTheme

/**
 * Main entry point for the Chimera RPG Android application.
 * Hosts the [GameScreen] composable as the primary content view.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ChimeraRPGTheme {
                // A surface container using the 'background' color from the theme
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    GameScreen()
                }
            }
        }
    }
}

/**
 * Top-level composable that hosts the game viewport.
 */
@Composable
fun GameScreen(modifier: Modifier = Modifier) {
    GameViewport(modifier = modifier)
}

/**
 * Viewport composable responsible for rendering the 2D game world using the Canvas API.
 * Demonstrates [drawRect] and [drawCircle] primitives as foundational building blocks
 * for in-game rendering.
 */
@Composable
fun GameViewport(modifier: Modifier = Modifier) {
    GameViewportContent(modifier = modifier)
}

/**
 * Internal viewport content rendered via Canvas API.
 */
@Composable
internal fun GameViewportContent(modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier
            .fillMaxSize()
    ) {
        val canvasWidth = size.width
        val canvasHeight = size.height

        // Layered background using drawRect
        drawRect(
            color = Color(0xFF1a1a2e),
            topLeft = Offset(0f, 0f),
            size = Size(canvasWidth, canvasHeight)
        )
        drawRect(
            color = Color(0xFF16213e),
            topLeft = Offset(0f, canvasHeight * 0.6f),
            size = Size(canvasWidth, canvasHeight * 0.4f)
        )

        // Player entity via drawCircle
        drawCircle(
            color = Color(0xFFe94560),
            radius = 32.dp.toPx(),
            center = Offset(canvasWidth / 2, canvasHeight / 2)
        )

        // Demonstrate native canvas access via drawIntoCanvas
        drawIntoCanvas {
            val nativeCanvas = it.nativeCanvas
            nativeCanvas.drawARGB(68, 255, 255, 255)
        }
    }
}

/**
 * Preview provider for Android Studio design-time rendering.
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
fun GameViewportPreview() {
    ChimeraRPGTheme {
        GameViewportContent()
    }
}

/**
 * Application-wide theme configuration.
 */
@Composable
fun ChimeraRPGTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = androidx.compose.material3.lightColorScheme(
            primary = Color(0xFFe94560),
            onPrimary = Color.White,
            background = Color(0xFF0f0f1a),
            surface = Color(0xFF1a1a2e)
        ),
        content = content
    )
}