package com.chimera.rpg.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.chimera.rpg.ui.theme.RPGTheme

/**
 * HUD (Heads-Up Display) overlay showing player health and mana.
 * Rendered with Jetpack Compose Canvas API using drawRect and drawCircle.
 */
@Composable
fun HUD(
    health: Float = 0.75f,
    maxHealth: Float = 1.0f,
    mana: Float = 0.5f,
    maxMana: Float = 1.0f,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.TopCenter
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val barHeight = 16.dp.toPx()
            val barWidth = size.width * 0.6f
            val barX = (size.width - barWidth) / 2f
            val barY = 24.dp.toPx()
            val barSpacing = 16.dp.toPx()

            // Health bar background
            drawRect(
                color = Color(0xFF333333),
                topLeft = Offset(barX, barY),
                size = Size(barWidth, barHeight),
                style = Stroke(width = 2f)
            )
            // Health bar fill
            drawRect(
                color = Color(0xFFE53935),
                topLeft = Offset(barX, barY),
                size = Size(barWidth * health, barHeight)
            )

            // Health bar label
            drawContext.canvas.nativeCanvas.apply {
                val paint = android.graphics.Paint().apply {
                    color = android.graphics.Color.WHITE
                    textSize = 14f
                    textAlign = android.graphics.Paint.Align.CENTER
                }
                drawText("HP", barX + barWidth / 2, barY - 6, paint)
            }

            // Mana bar background
            drawRect(
                color = Color(0xFF333333),
                topLeft = Offset(barX, barY + barSpacing + barHeight),
                size = Size(barWidth, barHeight),
                style = Stroke(width = 2f)
            )
            // Mana bar fill
            drawRect(
                color = Color(0xFF42A5F5),
                topLeft = Offset(barX, barY + barSpacing + barHeight),
                size = Size(barWidth * mana, barHeight)
            )

            // Mana bar label
            drawContext.canvas.nativeCanvas.apply {
                drawText("MP", barX + barWidth / 2, barY + barSpacing + barHeight - 6, paint)
            }

            // Player icon (circle with "P")
            val iconSize = 40.dp.toPx()
            drawCircle(
                color = Color(0xFF1E88E5),
                radius = iconSize / 2,
                center = Offset(size.width / 2f, barY + barSpacing * 2 + barHeight + iconSize)
            )
            drawContext.canvas.nativeCanvas.apply {
                drawText("P", size.width / 2, barY + barSpacing * 2 + barHeight + iconSize / 2 + 6, paint.apply {
                    textSize = 32f
                    textAlign = android.graphics.Paint.Align.CENTER
                    color = android.graphics.Color.WHITE
                })
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun HUDPreview() {
    RPGTheme {
        HUD(health = 0.75f, mana = 0.5f)
    }
}