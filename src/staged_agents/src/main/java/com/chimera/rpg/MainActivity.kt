package com.chimera.rpg

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

/**
 * Main entry point for the RPG application.
 * Hosts the [RPGScene] composable which renders the game world using Canvas API.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            RPGApp {
                RPGScene()
            }
        }
    }
}

/**
 * Composable that sets up the application theme.
 *
 * @param content The composable content to display within the theme.
 */
@Composable
fun RPGApp(content: @Composable () -> Unit) {
    MaterialTheme {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background
        ) {
            content()
        }
    }
}

/**
 * RPG Game Scene rendered on a Canvas.
 * Demonstrates 2D rendering with drawRect, drawCircle, and drawImage patterns.
 */
@Composable
@Preview(showBackground = true, showSystemUi = true)
fun RPGScene() {
    Canvas(
        modifier = Modifier
            .fillMaxSize()
    ) {
        val canvasWidth = size.width
        val canvasHeight = size.height

        // Draw background - a gradient-like sky using layered rectangles
        drawRect(
            color = Color(0xFF1a1a2e),
            topLeft = Offset(0f, 0f),
            size = Size(canvasWidth, canvasHeight * 0.6f)
        )
        drawRect(
            color = Color(0xFF16213e),
            topLeft = Offset(0f, canvasHeight * 0.6f),
            size = Size(canvasWidth, canvasHeight * 0.4f)
        )

        // Draw a glowing "sun" in the sky
        drawCircle(
            color = Color(0xFFFFD700).copy(alpha = 0.8f),
            radius = 80f,
            center = Offset(canvasWidth * 0.7f, canvasHeight * 0.2f)
        )
        drawCircle(
            color = Color(0xFFFFD700).copy(alpha = 0.3f),
            radius = 150f,
            center = Offset(canvasWidth * 0.7f, canvasHeight * 0.2f)
        )

        // Draw a simple ground/platform
        drawRect(
            color = Color(0xFF5d4037),
            topLeft = Offset(0f, canvasHeight * 0.75f),
            size = Size(canvasWidth, canvasHeight * 0.25f)
        )

        // Draw a hero character (stylized figure)
        drawCircle(
            color = Color(0xFF4fc3f7),
            radius = 25f,
            center = Offset(canvasWidth * 0.5f, canvasHeight * 0.55f)
        )
        // Head
        drawCircle(
            color = Color(0xFFFFAB91),
            radius = 15f,
            center = Offset(canvasWidth * 0.5f, canvasHeight * 0.45f)
        )
        // Body
        drawRect(
            color = Color(0xFF1e88e5),
            topLeft = Offset(canvasWidth * 0.45f, canvasHeight * 0.60f),
            size = Size(30f, 40f)
        )
        // Legs
        drawRect(
            color = Color(0xFFd32f2f),
            topLeft = Offset(canvasWidth * 0.45f, canvasHeight * 0.90f),
            size = Size(15f, 30f)
        )
        drawRect(
            color = Color(0xFFd32f2f),
            topLeft = Offset(canvasWidth * 0.55f, canvasHeight * 0.90f),
            size = Size(15f, 30f)
        )

        // Draw some collectible items (gold coins)
        drawCircle(
            color = Color(0xFFFFD700),
            radius = 12f,
            center = Offset(canvasWidth * 0.3f, canvasHeight * 0.3f)
        )
        drawCircle(
            color = Color(0xFF66bb6a),
            radius = 8f,
            center = Offset(canvasWidth * 0.8f, canvasHeight * 0.4f)
        )

        // Draw an enemy
        drawCircle(
            color = Color(0xFFf44336),
            radius = 20f,
            center = Offset(canvasWidth * 0.5f, canvasHeight * 0.8f)
        )
        // Enemy eyes
        drawCircle(
            color = Color.White,
            radius = 5f,
            center = Offset(canvasWidth * 0.47f, canvasHeight * 0.78f)
        )
        drawCircle(
            color = Color.White,
            radius = 5f,
            center = Offset(canvasWidth * 0.53f, canvasHeight * 0.78f)
        )
        drawCircle(
            color = Color.Black,
            radius = 2f,
            center = Offset(canvasWidth * 0.47f, canvasHeight * 0.78f)
        )
        drawCircle(
            color = Color.Black,
            radius = 2f,
            center = Offset(canvasWidth * 0.53f, canvasHeight * 0.78f)
        )

        // Draw decorative trees
        drawRect(
            color = Color(0xFF3e2723),
            topLeft = Offset(canvasWidth * 0.1f, canvasHeight * 0.55f),
            size = Size(20f, 60f)
        )
        drawCircle(
            color = Color(0xFF2e7d32),
            radius = 35f,
            center = Offset(canvasWidth * 0.1f, canvasHeight * 0.45f)
        )

        // UI elements layer - health bar
        drawRect(
            color = Color(0x44000000),
            topLeft = Offset(20.dp.toPx(), 20.dp.toPx()),
            size = Size(200.dp.toPx(), 25.dp.toPx())
        )
        drawRect(
            color = Color(0xFFe53935),
            topLeft = Offset(20.dp.toPx(), 20.dp.toPx()),
            size = Size(140.dp.toPx(), 25.dp.toPx()) // 70% health
        )
    }
}

/**
 * Preview showing the RPG scene in light and dark themes.
 */
@Preview(showBackground = true)
@Composable
fun RPGScenePreview() {
    RPGApp {
        RPGScene()
    }
}