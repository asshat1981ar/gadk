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
 * [NPC] represents a non-playable character. Can be an ally, vendor, or quest giver.
 * Uses a simple AI routine to either idle, patrol, or engage in combat.
 *
 * @param name The NPC's name.
 * @param maxHp Maximum Hit Points.
 * @param maxMp Maximum Magic Points.
 * @param str Strength stat.
 * @param agi Agility stat.
 * @param intel Intelligence stat.
 * @param aiBehavior The initial AI behavior mode.
 */
class NPC(
    name: String,
    maxHp: Int,
    maxMp: Int,
    str: Int,
    agi: Int,
    intel: Int,
    aiBehavior: AIBehavior = AIBehavior.IDLE
) : Entity(
    name = name,
    maxHp = maxHp,
    maxMp = maxMp,
    str = str,
    agi = agi,
    intel = intel,
    width = 85,
    height = 85
) {
    /** Current AI behavior mode. */
    var aiBehavior: AIBehavior = aiBehavior
        set(value) {
            field = value
            onBehaviorChanged?.invoke(value)
        }

    /** Optional callback when AI behavior changes. */
    var onBehaviorChanged: ((AIBehavior) -> Unit)? = null

    /** Target entity for combat engagement. */
    var target: Entity? = null
        set(value) {
            field = value
            if (value != null) {
                aiBehavior = AIBehavior.ENGAGED
            }
        }

    /**
     * Updates NPC AI state.
     * Called by the game loop.
     *
     * @param deltaTime Time since last update in seconds.
     */
    fun updateAI(deltaTime: Float) {
        when (aiBehavior) {
            AIBehavior.IDLE -> updateIdle(deltaTime)
            AIBehavior.PATROL -> updatePatrol(deltaTime)
            AIBehavior.ENGAGED -> updateEngaged(deltaTime)
            AIBehavior.FLEEING -> updateFleeing(deltaTime)
        }
    }

    private fun updateIdle(deltaTime: Float) {
        // Idle: possibly switch to patrol
        if (shouldStartPatrol()) {
            aiBehavior = AIBehavior.PATROL
        }
    }

    private fun updatePatrol(deltaTime: Float) {
        // Patrol: move along a path; if target appears, engage
        if (target != null && target!!.isAlive) {
            aiBehavior = AIBehavior.ENGAGED
        }
    }

    private fun updateEngaged(deltaTime: Float) {
        // Engage: attack the target if in range
        target?.takeDamage((str * 0.5f).toInt().coerceAtLeast(1))
        // If target dies, return to idle or patrol
        if (target?.isAlive == false) {
            target = null
            if (shouldStartPatrol()) {
                aiBehavior = AIBehavior.PATROL
            } else {
                aiBehavior = AIBehavior.IDLE
            }
        }
    }

    private fun updateFleeing(deltaTime: Float) {
        // Flee: move away from the nearest threat
        // Placeholder: logic would use position data
        if (!shouldFlee()) {
            aiBehavior = AIBehavior.IDLE
        }
    }

    private fun shouldStartPatrol(): Boolean = (0 until 5).any { (1..3).contains(it) }
    private fun shouldFlee(): Boolean = (0 until 10).any { it == 7 }

    /**
     * Renders the NPC with a distinct visual (e.g., a circle with a crown).
     */
    @Composable
    override fun RenderAvatar() {
        Box(
            modifier = Modifier
                .size(width.toDp(), height.toDp())
        ) {
            NPCCanvas(entity = this@NPC, size = IntSize(width, height))
        }
    }
}

/**
 * Canvas composable for drawing the NPC avatar.
 */
@Composable
internal fun NPCCanvas(
    entity: NPC,
    size: IntSize
) {
    Canvas(
        modifier = Modifier
            .size(size.width.toFloat(), size.height.toFloat())
    ) {
        // Draw a circle with a small crown-like triangle on top
        drawCircle(
            color = Color(0xFF8D6E63),
            radius = size.width / 2f - 5f,
            center = Offset(size.width / 2f, size.height / 2f)
        )
        // Crown indicator
        val crownPath = Path().apply {
            moveTo(size.width / 2f - 10f, size.height / 2f - 5f)
            lineTo(size.width / 2f, size.height / 2f - 20f)
            lineTo(size.width / 2f + 10f, size.height / 2f - 5f)
            close()
        }
        drawPath(crownPath, Color(0xFFFFD700))
    }
}

/**
 * Enumeration of possible AI behaviors for NPCs and enemies.
 */
enum class AIBehavior {
    IDLE,      // Doing nothing, waiting for a trigger.
    PATROL,    // Moving between waypoints.
    ENGAGED,   // Actively attacking a target.
    FLEEING    // Moving away from danger.
}