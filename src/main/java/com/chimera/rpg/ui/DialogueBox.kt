package com.chimera.rpg.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chimera.rpg.ui.theme.RPGTheme

/**
 * DialogueBox displays an NPC dialogue using Canvas API for the speech bubble.
 * Supports fade-in animation via animateFloatAsState.
 */
@Composable
fun DialogueBox(
    speaker: String = "Old Sage",
    dialogue: String = "Welcome, traveler. The ancient artifact lies within the crystal caverns.",
    isVisible: Boolean = true,
    modifier: Modifier = Modifier
) {
    val opacity by animateFloatAsState(
        targetValue = if (isVisible) 1f else 0f,
        label = "dialogueFade"
    )

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.3f)),
        contentAlignment = Alignment.BottomCenter
    ) {
        if (isVisible) {
            Canvas(
                modifier = Modifier
                    .padding(bottom = 48.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.DarkGray.copy(alpha = 0.95f))
            ) {
                val padding = 16.dp.toPx()
                val tailSize = 24.dp.toPx()
                val tailY = size.height
                val tailX = size.width / 2

                // Build speech bubble shape using Canvas primitives
                drawRoundRect(
                    color = Color.White.copy(alpha = 0.95f),
                    size = Size(
                        size.width - padding * 2,
                        size.height + tailSize - padding
                    ),
                    cornerRadiusX = 12.dp.toPx(),
                    cornerRadiusY = 12.dp.toPx()
                )

                // Draw tail (speech pointer)
                drawContext.canvas.nativeCanvas.apply {
                    val path = android.graphics.Path().apply {
                        moveTo(tailX - tailSize / 2, tailY)
                        lineTo(tailX, tailY - tailSize)
                        lineTo(tailX + tailSize / 2, tailY)
                        close()
                    }
                    drawPath(path, android.graphics.Color.DKGRAY)
                }

                // Text content - simple word wrap
                drawContext.canvas.nativeCanvas.apply {
                    val paint = android.graphics.Paint().apply {
                        color = android.graphics.Color.BLACK
                        textSize = 16.sp.toPx()
                        textAlign = android.graphics.Paint.Align.LEFT
                        isAntiAlias = true
                    }
                    var y = padding + 8
                    val lineHeight = paint.textSize * 1.4f
                    val maxLineWidth = size.width - padding * 2
                    // naive word wrap
                    val words = dialogue.split(" ")
                    var currentLine = ""
                    for (word in words) {
                        val test = if (currentLine.isEmpty()) word else "$currentLine $word"
                        if (paint.measureText(test) > maxLineWidth) {
                            drawText(currentLine, padding, y, paint)
                            y += lineHeight
                            currentLine = word
                        } else {
                            currentLine = test
                        }
                    }
                    if (currentLine.isNotEmpty()) {
                        drawText(currentLine, padding, y, paint)
                    }
                }
            }

            // Speaker name
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = speaker,
                    color = Color.White,
                    fontSize = 14.sp,
                    modifier = Modifier
                        .padding(bottom = 8.dp)
                        .background(
                            Color.Gray.copy(alpha = 0.3f),
                            shape = RoundedCornerShape(8.dp)
                        )
                        .padding(horizontal = 12.dp, vertical = 4.dp)
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun DialogueBoxPreview() {
    RPGTheme {
        DialogueBox(
            speaker = "King Eldrin",
            dialogue = "The shadows grow long, brave one. Seek the temple before the moon sets."
        )
    }
}