package com.chimera.rpg.graphics

import android.graphics.Color
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.by
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asAndroidImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.IntSize
import com.chimera.rpg.R

/**
 * Tile-based sprite renderer using Jetpack Compose Canvas with bitmap caching.
 *
 * This renderer efficiently draws tile-based game maps using sprite sheets with
 * bitmap caching for optimal performance. It supports camera translation, zoom,
 * and various tile rendering modes.
 *
 * @param modifier The modifier for layout and sizing
 * @param spriteSheet The sprite sheet containing all tiles
 * @param tileMap The 2D array of tile indices (row, col format)
 * @param cameraPosition The current camera position in world coordinates
 * @param cameraZoom The current zoom level (1.0 = 100%)
 * @param tileSize Override tile size; defaults to sprite sheet dimensions
 * @param renderMode How tiles are rendered
 * @param tileColors Optional color filters to apply to tiles
 * @param onTileClick Optional callback when a tile is clicked
 */
class TileRenderer(
    val modifier: Modifier = Modifier,
    val spriteSheet: SpriteSheet,
    val tileMap: Array<IntArray>,
    var cameraPosition: Offset = Offset.Zero,
    var cameraZoom: Float = 1f,
    val tileSize: IntSize? = null,
    val renderMode: RenderMode = RenderMode.Sprite,
    val tileColors: Map<Int, androidx.compose.ui.graphics.Color> = emptyMap(),
    val onTileClick: ((row: Int, col: Int) -> Unit)? = null
) {
    /**
     * The effective tile size considering override or sprite sheet dimensions.
     */
    val effectiveTileSize: IntSize = tileSize ?: run {
        val width = spriteSheet.spriteWidth
        val height = spriteSheet.spriteHeight
        IntSize(width, height)
    }

    /**
     * The visible tile region based on current camera position.
     */
    val visibleTileRegion: VisibleRegion
        get() {
            val canvasWidth = 1080 // Assume a reference canvas width for calculations
            val canvasHeight = 1920 // Assume a reference canvas height
            
            val viewWidth = (canvasWidth / cameraZoom).toInt()
            val viewHeight = (canvasHeight / cameraZoom).toInt()
            
            val startCol = (cameraPosition.x / effectiveTileSize.width).toInt().coerceAtLeast(0)
            val startRow = (cameraPosition.y / effectiveTileSize.height).toInt().coerceAtLeast(0)
            val endCol = ((cameraPosition.x + viewWidth) / effectiveTileSize.width).toInt().coerceAtMost(tileMap.getOrNull(0)?.size ?: 0)
            val endRow = ((cameraPosition.y + viewHeight) / effectiveTileSize.height).toInt().coerceAtMost(tileMap.size - 1)
            
            return VisibleRegion(
                startRow = startRow,
                endRow = endRow,
                startCol = startCol,
                endCol = endCol
            )
        }

    /**
     * Renders the complete tile map.
     *
     * @param onDraw Called with the DrawScope for custom drawing
     */
    @Composable
    fun render(onDraw: DrawScope.() -> Unit = {}) {
        val spriteCache = remember(spriteSheet) {
            mutableMapOf<Pair<Int, Int>, android.graphics.ImageBitmap?>()
        }

        Canvas(
            modifier = modifier
                .fillMaxSize()
                .onClick {
                    onTileClick?.let { callback ->
                        val pos = it
                        val col = ((pos.x + cameraPosition.x) / effectiveTileSize.width).toInt()
                        val row = ((pos.y + cameraPosition.y) / effectiveTileHeight).toInt()
                        if (row in tileMap.indices && col in tileMap[row].indices) {
                            callback(row, col)
                        }
                    }
                }
        ) {
            val canvasSize = size
            val scaledCameraPosition = cameraPosition.scale(cameraZoom)

            drawIntoCanvas { nativeCanvas ->
                nativeCanvas.nativeCanvas.save()
                nativeCanvas.nativeCanvas.translate(
                    -scaledCameraPosition.x,
                    -scaledCameraPosition.y
                )

                // Render tiles
                val region = visibleTileRegion
                for (row in region.startRow..region.endRow) {
                    for (col in region.startCol..region.endCol) {
                        if (row in tileMap.indices && col in tileMap[row].indices) {
                            val tileIndex = tileMap[row][col]
                            if (tileIndex != -1) { // -1 represents empty/walkable tile
                                renderTile(
                                    row = row,
                                    col = col,
                                    tileIndex = tileIndex,
                                    canvas = nativeCanvas,
                                    spriteCache = spriteCache
                                )
                            }
                        }
                    }
                }

                nativeCanvas.nativeCanvas.restore()
            }

            onDraw(this)
        }
    }

    /**
     * Renders a single tile at the specified position.
     */
    private fun DrawScope.renderTile(
        row: Int,
        col: Int,
        tileIndex: Int,
        canvas: android.graphics.Canvas,
        spriteCache: MutableMap<Pair<Int, Int>, android.graphics.ImageBitmap?>
    ) {
        val key = Pair(tileIndex, 0) // Using 0 as default frame for now
        val cachedBitmap = spriteCache.getOrPut(key) {
            spriteSheet.getSprite(
                row = tileIndex / spriteSheet.cols,
                col = tileIndex % spriteSheet.cols
            )?.asAndroidImageBitmap()
        }

        cachedBitmap?.let {
            val x = (col * effectiveTileSize.width).toFloat()
            val y = (row * effectiveTileSize.height).toFloat()
            val colorFilter = tileColors[tileIndex]

            if (colorFilter != null) {
                val paint = androidx.compose.ui.graphics.Paint().asFrameworkPaint()
                paint.colorFilter = android.graphics.PorterDuffColorFilter(
                    colorFilter.toArgb(),
                    android.graphics.PorterDuff.Mode.SRC_ATOP
                )
                canvas.drawImage(it, x, y, paint)
            } else {
                canvas.drawImage(it, x, y)
            }
        }
    }

    /**
     * Updates the camera position with bounds checking.
     *
     * @param newPosition The new camera position
     * @param mapWidth The total width of the map in pixels
     * @param mapHeight The total height of the map in pixels
     */
    fun updateCamera(newPosition: Offset, mapWidth: Int, mapHeight: Int) {
        val clampedX = newPosition.x.coerceIn(
            0f,
            (mapWidth - (1080 / cameraZoom)).coerceAtLeast(0f)
        )
        val clampedY = newPosition.y.coerceIn(
            0f,
            (mapHeight - (1920 / cameraZoom)).coerceAtLeast(0f)
        )
        cameraPosition = Offset(clampedX, clampedY)
    }

    /**
     * Scales the offset by a zoom factor.
     */
    private fun Offset.scale(factor: Float): Offset {
        return Offset(x / factor, y / factor)
    }
}

/**
 * Represents the visible region of the map based on camera position.
 */
data class VisibleRegion(
    val startRow: Int,
    val endRow: Int,
    val startCol: Int,
    val endCol: Int
)

/**
 * Rendering modes for tile visualization.
 */
enum class RenderMode {
    /**
     * Renders using sprite sheet images
     */
    Sprite,

    /**
     * Renders using colored rectangles for debugging
     */
    Debug,

    /**
     * Renders using procedural generated shapes
     */
    Procedural
}

/**
 * Composable preview of the TileRenderer.
 *
 * This shows a simple 10x10 tile map with various tile types.
 */
@Composable
@Preview(showBackground = true, showSystemUi = true)
fun TileRendererPreview() {
    // Create a simple 10x10 tile map with various tile types
    val testTileMap = arrayOf(
        intArrayOf(0, 1, 1, 1, 1, 1, 1, 1, 1, 0),
        intArrayOf(1, 2, 2, 2, 2, 2, 2, 2, 2, 1),
        intArrayOf(1, 2, 3, 3, 3, 3, 3, 3, 2, 1),
        intArrayOf(1, 2, 3, 4, 4, 4, 4, 3, 2, 1),
        intArrayOf(1, 2, 3, 4, 5, 5, 4, 3, 2, 1),
        intArrayOf(1, 2, 3, 4, 5, 5, 4, 3, 2, 1),
        intArrayOf(1, 2, 3, 4, 4, 4, 4, 3, 2, 1),
        intArrayOf(1, 2, 3, 3, 3, 3, 3, 3, 2, 1),
        intArrayOf(1, 2, 2, 2, 2, 2, 2, 2, 2, 1),
        intArrayOf(0, 1, 1, 1, 1, 1, 1, 1, 1, 0)
    )

    // Create dummy colors for different tile types
    val tileColors = mapOf(
        0 to androidx.compose.ui.graphics.Color.Green,
        1 to androidx.compose.ui.graphics.Color.Gray,
        2 to androidx.compose.ui.graphics.Color.DarkGray,
        3 to androidx.compose.ui.graphics.Color.Blue,
        4 to androidx.compose.ui.graphics.Color.Red,
        5 to androidx.compose.ui.graphics.Color.Yellow
    )

    // Create a dummy sprite sheet (in real usage, this would be loaded from resources)
    val dummyBitmap = android.graphics.Bitmap.createBitmap(
        64 * 5,  // width: 5 tiles
        64 * 2,  // height: 2 rows
        android.graphics.Bitmap.Config.ARGB_8888
    )
    
    val dummySpriteSheet = SpriteSheet.fromBitmap(
        bitmap = dummyBitmap,
        rows = 2,
        cols = 5,
        spriteWidth = 64,
        spriteHeight = 64
    ) ?: return Box(modifier = Modifier.fillMaxSize()) {}

    Box(modifier = Modifier.fillMaxSize()) {
        TileRenderer(
            modifier = Modifier.fillMaxSize(),
            spriteSheet = dummySpriteSheet,
            tileMap = testTileMap,
            cameraPosition = Offset(0f, 0f),
            cameraZoom = 1f,
            renderMode = RenderMode.Debug,
            tileColors = tileColors,
            onTileClick = { row, col ->
                // Handle tile click if needed
            }
        )
    }
}