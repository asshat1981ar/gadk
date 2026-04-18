package com.chimera.rpg.entity

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.IntSize

/**
 * Base [Entity] class representing any character in the RPG world.
 * Holds core stats, current HP/MP, and animation state.
 *
 * @param name The display name of the entity.
 * @param maxHp Maximum Hit Points.
 * @param maxMp Maximum Magic Points.
 * @param str Strength stat (affects physical damage).
 * @param agi Agility stat (affects evasion and turn order).
 * @param intel Intelligence stat (affects magic damage and MP).
 * @param width UI width in pixels for the visual representation.
 * @param height UI height in pixels for the visual representation.
 */
open class Entity(
    val name: String,
    maxHp: Int,
    maxMp: Int,
    val str: Int,
    val agi: Int,
    val intel: Int,
    private val width: Int = 80,
    private val height: Int = 80
) {
    /** Current Hit Points, clamped between 0 and [maxHp]. */
    var currentHp: Int = maxHp
        protected set

    /** Current Magic Points, clamped between 0 and [maxMp]. */
    var currentMp: Int = maxMp
        protected set

    /** Maximum Hit Points. */
    val maxHp get() = maxHp

    /** Maximum Magic Points. */
    val maxMp get() = maxMp

    /**
     * Returns the entity's health ratio in the range 0.0f to 1.0f.
     * Useful for animating health bars and color transitions.
     */
    val hpRatio: Float
        get() = if (maxHp > 0) currentHp.toFloat() / maxHp.toFloat() else 0f

    /**
     * Returns the entity's magic ratio in the range 0.0f to 1.0f.
     * Useful for animating MP bars and color transitions.
     */
    val mpRatio: Float
        get() = if (maxMp > 0) currentMp.toFloat() / maxMp.toFloat() else 0f

    /**
     * Returns true if the entity's HP is above 0.
     */
    val isAlive: Boolean
        get() = currentHp > 0

    /**
     * Inflicts [amount] damage to this entity.
     * HP will not drop below 0.
     *
     * @return The actual damage dealt.
     */
    open fun takeDamage(amount: Int): Int {
        val actualDamage = max(amount, 0)
        currentHp = (currentHp - actualDamage).coerceAtLeast(0)
        return actualDamage
    }

    /**
     * Restores [amount] HP to this entity.
     * HP will not exceed [maxHp].
     *
     * @return The actual HP restored.
     */
    fun heal(amount: Int): Int {
        val actualHeal = max(amount, 0)
        val before = currentHp
        currentHp = (currentHp + actualHeal).coerceAtMost(maxHp)
        return currentHp - before
    }

    /**
     * Attempts to spend [amount] MP. Returns true if successful.
     */
    fun spendMp(amount: Int): Boolean {
        if (currentMp < amount) return false
        currentMp -= amount
        return true
    }

    /**
     * Restores [amount] MP to this entity.
     * MP will not exceed [maxMp].
     *
     * @return The actual MP restored.
     */
    fun restoreMp(amount: Int): Int {
        val actualRestore = max(amount, 0)
        val before = currentMp
        currentMp = (currentMp + actualRestore).coerceAtMost(maxMp)
        return currentMp - before
    }

    /**
     * Renders a simple visual representation of the entity using Jetpack Compose Canvas.
     * Shows a color-coded avatar with HP/MP bars.
     */
    @Composable
    fun RenderAvatar() {
        Box(
            modifier = Modifier
                .size(width.toDp(), height.toDp())
        ) {
            EntityCanvas(
                entity = this@Entity,
                size = IntSize(width, height)
            )
        }
    }
}

/**
 * Canvas composable responsible for drawing the entity's visual representation.
 */
@Composable
internal fun EntityCanvas(
    entity: Entity,
    size: IntSize
) {
    val canvasSize = size
    val barHeight = 8
    val barY = canvasSize.height - barHeight - 4

    Canvas(
        modifier = Modifier
            .size(canvasSize.width.toFloat(), canvasSize.height.toFloat())
    ) {
        // Background circle
        drawCircle(
            color = when {
                entity.isAlive.not() -> Color(0xFF222222)
                entity.hpRatio > 0.5f -> Color(0xFF2E7D32) // green
                entity.hpRatio > 0.25f -> Color(0xFFFF9800) // orange
                else -> Color(0xFFD32F2F) // red
            },
            radius = (min(canvasSize.width, canvasSize.height) / 2f) - 4f,
            center = Offset(canvasSize.width / 2f, canvasSize.height / 2f)
        )

        // HP Bar background
        drawRect(
            color = Color(0xFF1E1E1E),
            topLeft = Offset(
                (canvasSize.width / 2f) - 36f,
                barY.toFloat()
            ),
            size = Size(72f, barHeight.toFloat())
        )
        // HP Bar fill
        drawRect(
            color = if (entity.hpRatio > 0.6f) Color(0xFF4CAF50) else Color(0xFFE53935),
            topLeft = Offset(
                (canvasSize.width / 2f) - 34f,
                (barY + 2).toFloat()
            ),
            size = Size(
                72f * entity.hpRatio,
                (barHeight - 4).toFloat()
            )
        )

        // MP Bar background
        drawRect(
            color = Color(0xFF1E1E1E),
            topLeft = Offset(
                (canvasSize.width / 2f) - 36f,
                (barY - 16).toFloat()
            ),
            size = Size(72f, barHeight.toFloat())
        )
        // MP Bar fill
        drawRect(
            color = Color(0xFF9C27B0),
            topLeft = Offset(
                (canvasSize.width / 2f) - 34f,
                (barY - 14).toFloat()
            ),
            size = Size(
                72f * entity.mpRatio,
                (barHeight - 4).toFloat()
            )
        )
    }
}

/**
 * Simple [AnimationState] tracking current frame and timer.
 */
class AnimationState {
    var currentFrame: Int = 0
        private set
    private var frameTimer: Float = 0f
    private val frameDuration: Float = 0.15f
    val spriteSize: IntSize = IntSize(32, 32)

    /**
     * Updates animation state. Call per frame with [deltaTime] in seconds.
     */
    fun update(deltaTime: Float) {
        frameTimer += deltaTime
        if (frameTimer >= frameDuration) {
            frameTimer = 0f
            currentFrame = (currentFrame + 1) % 4
        }
    }

    /**
     * Resets animation to the first frame.
     */
    fun reset() {
        currentFrame = 0
        frameTimer = 0f
    }
}

/**
 * Determines the priority in which entities should act.
 * Higher AGI generally acts first.
 */
fun sortByAgility(entities: List<Entity>): List<Entity> = entities.sortedByDescending { it.agi }