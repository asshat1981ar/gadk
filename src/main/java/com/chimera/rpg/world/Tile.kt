package com.chimera.rpg.world

import androidx.compose.runtime.Stable

/**
 * Represents a single tile on the world map.
 *
 * @param tileType The type of tile (e.g., grass, water, mountain).
 * @param walkable Whether this tile can be traversed by entities.
 * @param color The visual color representation of the tile.
 */
@Stable
data class Tile(
    val tileType: TileType,
    val walkable: Boolean = true,
    val color: Int
)

/**
 * Enumeration of tile types that define terrain characteristics.
 */
enum class TileType {
    GRASS,      // Normal traversable terrain
    WATER,      // Impassable water
    MOUNTAIN,   // Impassable mountain
    ROAD,       // Path that connects areas
    FOREST      // Dense trees, slower traversal
}

/**
 * Generates a random tile based on weight probabilities.
 */
fun generateRandomTile(): Tile {
    val random = (0..100).random()
    return when {
        random < 50 -> Tile(TileType.GRASS, true, 0xFF4CAF50.toInt())
        random < 70 -> Tile(TileType.WATER, false, 0xFF2196F3.toInt())
        random < 80 -> Tile(TileType.MOUNTAIN, false, 0xFF795548.toInt())
        random < 90 -> Tile(TileType.ROAD, true, 0xFF8D6E63.toInt())
        else -> Tile(TileType.FOREST, true, 0xFF388E3C.toInt())
    }
}