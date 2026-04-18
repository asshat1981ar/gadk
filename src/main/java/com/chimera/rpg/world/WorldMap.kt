package com.chimera.rpg.world

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gesture.waitForUpOrCancellation
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.graphicsLayer.Layer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.flow.collectLatest
import kotlin.math.roundToInt

/**
 * Represents the 2D procedural world map with tile-based rendering.
 *
 * @param width The width of the world map in tiles.
 * @param height The height of the world map in tiles.
 * @param tileSize The size of each tile in pixels.
 * @param initialCameraPosition The initial camera offset.
 */
class WorldMapGenerator(
    private val width: Int = 100,
    private val height: Int = 100,
    private val tileSize: Int = 64
) {
    private val tiles = Array(height) { y ->
        Array(width) { x ->
            // Procedural generation: create patterns
            val tile = when {
                x == 0 || y == 0 || x == width - 1 || y == height - 1 -> {
                    // Border with mountains
                    Tile(TileType.MOUNTAIN, false, 0xFF795548.toInt())
                }
                x % 10 == 0 && y % 10 == 0 -> {
                    // Villages at intersections
                    Tile(TileType.ROAD, true, 0xFF8D6E63.toInt())
                }
                x % 15 == 0 && y % 15 == 0 -> {
                    // Water features
                    Tile(TileType.WATER, false, 0xFF2196F3.toInt())
                }
                x % 7 == 0 || y % 7 == 0 -> {
                    // Forest lines
                    Tile(TileType.FOREST, true, 0xFF388E3C.toInt())
                }
                else -> {
                    // Default random terrain
                    generateRandomTile()
                }
            }
            tile
        }
    }

    /**
     * Gets the tile at world coordinates.
     */
    fun getTile(x: Int, y: Int): Tile? {
        if (x in 0 until width && y in 0 until height) {
            return tiles[y][x]
        }
        return null
    }

    /**
     * Gets the tile at world coordinates.
     */
    fun getTile(worldPos: Offset): Tile? {
        val tileX = (worldPos.x / tileSize).toInt()
        val tileY = (worldPos.y / tileSize).toInt()
        return getTile(tileX, tileY)
    }

    /**
     * Checks if a world position is walkable.
     */
    fun isWalkable(worldPos: Offset): Boolean {
        return getTile(worldPos)?.walkable ?: false
    }

    /**
     * Gets the world dimensions in pixels.
     */
    fun getWorldSize(): Offset {
        return Offset((width * tileSize).toFloat(), (height * tileSize).toFloat())
    }
}

/**
 * Composable that renders the world map with camera controls.
 *
 * @param worldMap The world map generator instance.
 * @param cameraPosition The current camera position (mutable state).
 * @param modifier The modifier for the canvas.
 */
@Composable
fun WorldMapView(
    worldMap: WorldMapGenerator,
    cameraPosition: MutableState<Offset>,
    modifier: Modifier = Modifier
) {
    val worldSize = remember(worldMap) { worldMap.getWorldSize() }
    
    // Camera animation for smooth transitions
    val animatedCameraX by animateFloatAsState(
        targetValue = cameraPosition.value.x,
        label = "Camera X Animation"
    )
    val animatedCameraY by animateFloatAsState(
        targetValue = cameraPosition.value.y,
        label = "Camera Y Animation"
    )

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(cameraPosition) {
                detectDragGestures(
                    onDrag = { change, dragAmount ->
                        cameraPosition.value = Offset(
                            cameraPosition.value.x + dragAmount.x,
                            cameraPosition.value.y + dragAmount.y
                        )
                    }
                )
            }
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = { pos ->
                        // Check what tile was tapped
                        val worldPos = Offset(pos.x + cameraPosition.value.x, pos.y + cameraPosition.value.y)
                        val tile = worldMap.getTile(worldPos)
                        tile?.let {
                            // Handle tile tap - could trigger events
                            println("Tapped tile: ${it.tileType} at world pos: $worldPos")
                        }
                    }
                )
            }
    ) {
        val density = LocalDensity.current
        drawWorld(worldMap, Offset(animatedCameraX, animatedCameraY), density)
    }
}

/**
 * Draws the world map tiles on the canvas.
 */
private fun DrawScope.drawWorld(
    worldMap: WorldMapGenerator,
    cameraPosition: Offset,
    density: Density
) {
    val worldSize = worldMap.getWorldSize()
    
    // Calculate visible tile range
    val viewWidth = size.width
    val viewHeight = size.height
    
    val startTileX = (cameraPosition.x / worldMap.tileSize).toInt().coerceAtLeast(0)
    val endTileX = ((cameraPosition.x + viewWidth) / worldMap.tileSize).toInt().coerceAtMost(worldMap.width - 1)
    val startTileY = (cameraPosition.y / worldMap.tileSize).toInt().coerceAtLeast(0)
    val endTileY = ((cameraPosition.y + viewHeight) / worldMap.tileSize).toInt().coerceAtMost(worldMap.height - 1)

    for (y in startTileY..endTileY) {
        for (x in startTileX..endTileX) {
            val tile = worldMap.getTile(x, y) ?: continue
            
            val drawX = x * worldMap.tileSize - cameraPosition.x
            val drawY = y * worldMap.tileSize - cameraPosition.y

            // Draw tile background
            drawRect(
                color = Color(tile.color),
                topLeft = Offset(drawX, drawY),
                size = androidx.compose.ui.geometry.Size(
                    worldMap.tileSize.toFloat(),
                    worldMap.tileSize.toFloat()
                )
            )

            // Draw tile border for better visibility
            drawRect(
                color = Color.Black.copy(alpha = 0.1f),
                topLeft = Offset(drawX, drawY),
                size = androidx.compose.ui.geometry.Size(
                    worldMap.tileSize.toFloat(),
                    worldMap.tileSize.toFloat()
                ),
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = 1f)
            )

            // Draw tile coordinates for debugging (optional)
            // Can be enabled for debugging purposes
        }
    }
}

/**
 * Composable that manages the world map state and camera.
 */
@Composable
fun rememberWorldMapState(
    worldMap: WorldMapGenerator = remember { WorldMapGenerator() },
    initialCamera: Offset = Offset.Zero
): MutableState<Offset> {
    return remember { mutableStateOf(initialCamera) }
}

/**
 * Preview showing a sample world map.
 */
@Composable
@Preview(showBackground = true)
fun WorldMapPreview() {
    val worldMap = remember { WorldMapGenerator(20, 15, 64) }
    var cameraPosition by rememberWorldMapState(worldMap)

    WorldMapView(
        worldMap = worldMap,
        cameraPosition = mutableStateOf(cameraPosition),
        modifier = Modifier.fillMaxSize()
    )
}