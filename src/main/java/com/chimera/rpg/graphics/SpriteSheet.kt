package com.chimera.rpg.graphics

import android.graphics.Bitmap
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.asImageBitmap

/**
 * Represents a sprite sheet containing multiple sprites arranged in a grid.
 * 
 * A sprite sheet is a single bitmap containing multiple smaller images (sprites)
 * arranged in a regular grid pattern. This class provides efficient access to
 * individual sprites by their grid coordinates.
 *
 * @property bitmap The underlying bitmap containing all sprites
 * @property rows Number of rows in the sprite grid
 * @property cols Number of columns in the sprite grid
 * @property spriteWidth Width of each individual sprite in pixels
 * @property spriteHeight Height of each individual sprite in pixels
 */
@Stable
data class SpriteSheet(
    val bitmap: Bitmap,
    val rows: Int,
    val cols: Int,
    val spriteWidth: Int,
    val spriteHeight: Int
) {
    /**
     * Validates that the sprite sheet configuration is consistent.
     *
     * @return true if the sprite sheet dimensions are valid, false otherwise
     */
    fun isValid(): Boolean {
        if (rows <= 0 || cols <= 0) return false
        if (spriteWidth <= 0 || spriteHeight <= 0) return false
        if (bitmap.width != cols * spriteWidth) return false
        if (bitmap.height != rows * spriteHeight) return false
        return true
    }

    /**
     * Extracts a specific sprite from the sheet as an ImageBitmap.
     *
     * @param row Row index (0-based) of the sprite
     * @param col Column index (0-based) of the sprite
     * @return The extracted sprite as an ImageBitmap, or null if indices are invalid
     */
    @Composable
    fun getSprite(row: Int, col: Int): android.graphics.ImageBitmap? {
        require(row in 0 until rows) { "Row index $row out of bounds (0-$rows)" }
        require(col in 0 until cols) { "Column index $col out of bounds (0-$cols)" }
        
        // Cache the extracted sprite bitmap for performance
        return remember(bitmap, row, col) {
            val left = col * spriteWidth
            val top = row * spriteHeight
            val right = left + spriteWidth
            val bottom = top + spriteHeight
            
            Bitmap.createBitmap(bitmap, left, top, spriteWidth, spriteHeight)
                .asImageBitmap()
        }
    }

    companion object {
        /**
         * Creates a SpriteSheet from an existing bitmap with uniform sprite dimensions.
         *
         * @param bitmap The source bitmap containing sprites in a grid
         * @param rows Number of rows in the sprite grid
         * @param cols Number of columns in the sprite grid
         * @param spriteWidth Width of each individual sprite in pixels
         * @param spriteHeight Height of each individual sprite in pixels
         * @return A SpriteSheet instance if the configuration is valid, null otherwise
         */
        fun fromBitmap(
            bitmap: Bitmap,
            rows: Int,
            cols: Int,
            spriteWidth: Int,
            spriteHeight: Int
        ): SpriteSheet? {
            val sheet = SpriteSheet(
                bitmap = bitmap,
                rows = rows,
                cols = cols,
                spriteWidth = spriteWidth,
                spriteHeight = spriteHeight
            )
            return if (sheet.isValid()) sheet else null
        }
    }
}