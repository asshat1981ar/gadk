package com.chimera.rpg

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.dp

/**
 * Composable that hosts a full-screen [GameViewportCanvas].
 */
@Composable
fun GameViewport(modifier: Modifier = Modifier) {
    GameViewportCanvas(modifier = modifier)
}

/**
 * Canvas-backed viewport responsible for all 2D rendering using the Canvas API.
 *
 * Uses [drawRect] for background layers and [drawCircle] for a placeholder avatar.
 * Demonstrates procedural rendering via [DrawScope.drawIntoCanvas] for native interop.
 */
@Composable
internal fun GameViewportCanvas(modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier
            .fillMaxSize()
    ) {
        drawGameWorld()
    }
}

/**
 * Performs low-level 2D scene rendering on the canvas.
 *
 * This function is the core drawing routine invoked each compose recomposition/layout pass.
 * It demonstrates:
 *  - [drawRect] layered background rendering
 *  - [drawCircle] entity representation
 *  - [DrawScope.drawIntoCanvas] for native Canvas access
 */
private fun DrawScope.drawGameWorld() {
    val canvasWidth = size.width
    val canvasHeight = size.height

    // Background: deep space gradient via stacked rects
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

    // Player entity: a circle avatar centered in view
    drawCircle(
        color = Color(0xFFe94560),
        radius = 32.dp.toPx(),
        center = Offset(canvasWidth / 2, canvasHeight / 2)
    )

    // HUD backing using native canvas access for demonstration
    drawIntoCanvas {
        val nativeCanvas = it.nativeCanvas
        nativeCanvas.drawARGB(68, 255, 255, 255)
    }
}

/**
 * Preview provider showing the viewport in both light and dark themes.
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
fun GameViewportPreview() {
    ChimeraRPGTheme {
        GameViewportCanvas()
    }
}

@Preview(showBackground = false, showSystemUi = true)
@Composable
fun GameViewportDarkPreview() {
    ChimeraRPGTheme(darkTheme = true) {
        GameViewportCanvas()
    }
}