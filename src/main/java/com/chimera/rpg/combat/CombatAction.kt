package com.chimera.rpg.combat

import androidx.compose.runtime.Stable

/**
 * Represents a discrete combat action that an entity can perform.
 * Actions are processed in the turn queue by [CombatSystem].
 */
@Stable
data class CombatAction(
    /** Unique identifier for this action. */
    val id: String,
    /** The entity performing the action. */
    val actorId: String,
    /** The target entity of the action, if any. */
    val targetId: String?,
    /** The type of action being performed. */
    val type: ActionType,
    /** Optional payload for the action (e.g., spell ID, item ID, magnitude of damage). */
    val payload: Any? = null,
    /** Priority determines execution order when multiple actions are queued for the same tick. */
    val priority: Int = 0
) {
    /**
     * The type of combat action.
     */
    enum class ActionType {
        ATTACK,
        DEFEND,
        SPELL,
        ITEM
    }

    companion object {
        /** Creates an attack action. */
        fun attack(actorId: String, targetId: String, damage: Int): CombatAction {
            require(damage >= 0) { "Damage must be non-negative" }
            return CombatAction(
                id = "ACT_${actorId}_${System.currentTimeMillis()}",
                actorId = actorId,
                targetId = targetId,
                type = ActionType.ATTACK,
                payload = damage
            )
        }

        /** Creates a defend action. */
        fun defend(entityId: String): CombatAction {
            return CombatAction(
                id = "DEF_${entityId}_${System.currentTimeMillis()}",
                actorId = entityId,
                targetId = null,
                type = ActionType.DEFEND,
                payload = null
            )
        }

        /** Creates a spell action. */
        fun spell(
            actorId: String,
            targetId: String?,
            spellId: String,
            magnitude: Int = 1
        ): CombatAction {
            require(magnitude > 0) { "Spell magnitude must be positive" }
            return CombatAction(
                id = "SPE_${actorId}_${System.currentTimeMillis()}",
                actorId = actorId,
                targetId = targetId,
                type = ActionType.SPELL,
                payload = SpellPayload(spellId, magnitude)
            )
        }

        /** Creates an item action. */
        fun item(
            actorId: String,
            targetId: String?,
            itemId: String,
            magnitude: Int = 1
        ): CombatAction {
            require(magnitude > 0) { "Item magnitude must be positive" }
            return CombatAction(
                id = "ITM_${actorId}_${System.currentTimeMillis()}",
                actorId = actorId,
                targetId = targetId,
                type = ActionType.ITEM,
                payload = ItemPayload(itemId, magnitude)
            )
        }
    }
}

/** Payload for a spell action. */
@Stable
data class SpellPayload(
    val spellId: String,
    val magnitude: Int
)

/** Payload for an item action. */
@Stable
data class ItemPayload(
    val itemId: String,
    val magnitude: Int
)