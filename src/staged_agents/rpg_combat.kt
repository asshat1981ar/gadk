// app/src/main/java/com/chimera/rpg/combat/CombatAction.kt
package com.chimera.rpg.combat

/**
 * Represents a combat action that a combatant can take during a turn.
 * Each action has a name, type, power, and optional effect parameters.
 *
 * @property name The display name of the action
 * @property type The type of action being performed
 * @property power The base power/strength of the action
 * @property targetType Who this action targets (self, enemy, or all enemies)
 * @property isDefensive Whether this action is primarily defensive
 * @property element The elemental type of this action
 */
data class CombatAction(
    val name: String,
    val type: ActionType,
    val power: Int,
    val targetType: TargetType = TargetType.ENEMY,
    val isDefensive: Boolean = false,
    val element: ElementType = ElementType.PHYSICAL
)

/**
 * The type of combat action.
 */
enum class ActionType {
    ATTACK,      // Basic physical attack
    DEFEND,      // Defensive stance to reduce damage
    SPELL,       // Magical attack
    ITEM         // Using an item
}

/**
 * Who the action targets.
 */
enum class TargetType {
    SINGLE_ENEMY,  // Targets one specific enemy
    ALL_ENEMIES,   // Targets all enemies
    SELF,          // Affects the user (for healing/shields)
    ALL            // Affects everyone
}

/**
 * Elemental types for actions.
 */
enum class ElementType {
    PHYSICAL,
    FIRE,
    ICE,
    LIGHTNING,
    HOLY,
    DARK
}