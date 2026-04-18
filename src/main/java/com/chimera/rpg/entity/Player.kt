package com.chimera.rpg.entity

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.IntSize

/**
 * [Player] represents the controlled character in the RPG.
 * Extends [Entity] with player-specific attributes such as experience,
 * level, and equipment slots.
 *
 * @param name The player's chosen name.
 * @param maxHp Maximum Hit Points.
 * @param maxMp Maximum Magic Points.
 * @param str Strength stat.
 * @param agi Agility stat.
 * @param intel Intelligence stat.
 * @param level The player's current level.
 */
class Player(
    name: String,
    maxHp: Int,
    maxMp: Int,
    str: Int,
    agi: Int,
    intel: Int,
    level: Int = 1
) : Entity(
    name = name,
    maxHp = maxHp,
    maxMp = maxMp,
    str = str,
    agi = agi,
    intel = intel,
    width = 90,
    height = 90
) {
    /** Current level of the player. */
    var level: Int = level
        private set

    /** Experience points accumulated towards the next level. */
    var experience: Int = 0
        private set

    /** Experience points required for the next level. */
    val experienceToNextLevel: Int
        get() = level * 100

    /** Equipped weapon name. */
    var equippedWeapon: String? = null

    /** Equipped armor name. */
    var equippedArmor: String? = null

    /**
     * Adds [amount] experience. Triggers level up if threshold is reached.
     *
     * @return A list of level-ups that occurred (typically 0 or 1).
     */
    fun addExperience(amount: Int): List<Int> {
        if (amount <= 0) return emptyList()
        experience += amount
        val levelsGained = mutableListOf<Int>()
        while (experience >= experienceToNextLevel) {
            experience -= experienceToNextLevel
            levelUp()
            levelsGained.add(level)
        }
        return levelsGained
    }

    private fun levelUp() {
        level++
        // Stat scaling on level up
        val hpBoost = 10 + (level * 2)
        val mpBoost = 5 + (level * 1)
        val strBoost = 1
        val agiBoost = 1
        val intelBoost = 1

        maxHp += hpBoost
        currentHp = maxHp // Fully heal on level up
        maxMp += mpBoost
        currentMp = maxMp // Fully restore MP
        str += strBoost
        agi += agiBoost
        intel += intelBoost
    }

    /**
     * Equips an item, modifying relevant stats.
     *
     * @param item The item to equip.
     */
    fun equip(item: Item) {
        when (item.slot) {
            ItemSlot.WEAPON -> {
                equippedWeapon = item.name
                str += item.statBonus
            }
            ItemSlot.ARMOR -> {
                equippedArmor = item.name
                // Armor could add a defense stat; for simplicity, we just track it.
            }
        }
    }

    /**
     * Unequips an item, reversing its stat changes.
     *
     * @param item The item to unequip.
     */
    fun unequip(item: Item) {
        when (item.slot) {
            ItemSlot.WEAPON -> {
                if (equippedWeapon == item.name) {
                    equippedWeapon = null
                    str -= item.statBonus
                }
            }
            ItemSlot.ARMOR -> {
                if (equippedArmor == item.name) {
                    equippedArmor = null
                }
            }
        }
    }

    /**
     * Renders the player with a distinct visual (e.g., a triangle).
     */
    @Composable
    override fun RenderAvatar() {
        Box(
            modifier = Modifier
                .size(width.toDp(), height.toDp())
        ) {
            PlayerCanvas(entity = this@Player, size = IntSize(width, height))
        }
    }
}

/**
 * Canvas composable for drawing the player avatar.
 */
@Composable
internal fun PlayerCanvas(
    entity: Player,
    size: IntSize
) {
    Canvas(
        modifier = Modifier
            .size(size.width.toFloat(), size.height.toFloat())
    ) {
        // Draw a triangle pointing up to represent the player
        val path = Path().apply {
            moveTo(size.width / 2f, 10f)
            lineTo(size.width - 10f, size.height - 10f)
            lineTo(10f, size.height - 10f)
            close()
        }
        drawPath(
            path = path,
            color = Color(0xFF1565C0), // Blue
            style = Stroke(width = 2f)
        )
        // Fill
        drawPath(path, Color(0xFFE3F2FD))
    }
}

/**
 * Item slot enumeration.
 */
enum class ItemSlot {
    WEAPON, ARMOR
}

/**
 * Represents an equipable item.
 *
 * @param name Item display name.
 * @param slot Equipment slot.
 * @param statBonus Statistic bonus when equipped.
 */
data class Item(
    val name: String,
    val slot: ItemSlot,
    val statBonus: Int = 1
)