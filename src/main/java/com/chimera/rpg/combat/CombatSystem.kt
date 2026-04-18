package com.chimera.rpg.combat

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import kotlin.math.max

/**
 * Turn-based combat system managing entities, their states, and a queue of
 * [CombatAction]s.
 *
 * The system processes the queue each "tick", applying effects and resolving
 * turn order. Entities may act when their initiative timer reaches zero.
 */
class CombatSystem {

    /** Current entities participating in combat, keyed by entity id. */
    val entities = mutableMapOf<String, EntityState>()

    /** Queue of actions yet to be resolved. */
    private val _actionQueue = mutableStateListOf<CombatAction>()
    val actionQueue: List<CombatAction> get() = _actionQueue

    /** Ordered list of entity ids sorted by their next available turn time. */
    private val _turnOrder = mutableStateListOf<String>()
    val turnOrder: List<String> get() = _turnOrder

    /** The id of the entity currently selected to act. */
    var currentActorId: String? by mutableStateOf(null)

    /** Whether the system is processing an action (prevents queue mutations). */
    var isProcessing: Boolean by mutableStateOf(false)
        private set

    /** Mapping of entity id to initiative countdown (lower = sooner). */
    private val initiativeTimers = mutableMapOf<String, Int>()

    /**
     * Adds an entity to the combat system.
     *
     * @param id unique entity identifier
     * @param name display name
     * @param maxHp maximum hit points
     * @param initiative base initiative value (higher = acts sooner)
     * @param defense defense rating (reduces incoming damage)
     */
    fun addEntity(
        id: String,
        name: String,
        maxHp: Int,
        initiative: Int = 10,
        defense: Int = 1
    ) {
        require(maxHp > 0) { "maxHp must be positive" }
        require(initiative >= 0) { "initiative must be non-negative" }
        require(defense >= 0) { "defense must be non-negative" }
        entities[id] = EntityState(
            id = id,
            name = name,
            maxHp = maxHp,
            currentHp = maxHp,
            initiative = initiative,
            defense = defense,
            isDefending = false
        )
        initiativeTimers[id] = 0
        if (!_turnOrder.contains(id)) {
            _turnOrder.add(id)
        }
    }

    /**
     * Submits an action to the queue.
     * Actions are validated against known entities and queued for processing.
     */
    fun queueAction(action: CombatAction): Boolean {
        val actor = entities[action.actorId] ?: return false
        val target = if (action.targetId != null) entities[action.targetId] else null

        when (action.type) {
            CombatAction.ActionType.ATTACK -> {
                requireNotNull(target) { "Attack requires a valid targetId" }
            }
            CombatAction.ActionType.SPELL, CombatAction.ActionType.ITEM -> {
                requireNotNull(target) { "${action.type} requires a valid targetId" }
            }
            CombatAction.ActionType.DEFEND -> {
                // No target required
            }
        }

        _actionQueue.add(action)
        return true
    }

    /**
     * Advances combat by one tick.
     *
     * Processes all queued actions in priority order (higher priority first),
     * then advances initiative timers and refreshes turn order for entities
     * whose timer hits zero.
     */
    fun tick() {
        if (isProcessing || _actionQueue.isEmpty()) return
        isProcessing = true

        // 1) Sort actions: higher priority first, then FIFO for same priority
        val sortedActions = _actionQueue.sortedWith(
            compareByDescending<CombatAction> { it.priority }
        )
        _actionQueue.removeAll(_actionQueue)

        // 2) Execute actions
        for (action in sortedActions) {
            when (action.type) {
                CombatAction.ActionType.ATTACK -> executeAttack(action)
                CombatAction.ActionType.DEFEND -> executeDefend(action)
                CombatAction.ActionType.SPELL -> executeSpell(action)
                CombatAction.ActionType.ITEM -> executeItem(action)
            }
        }
        _actionQueue.clear()

        // 3) Advance timers and refresh turn order
        advanceTurns()

        isProcessing = false
    }

    private fun executeAttack(action: CombatAction) {
        val actor = entities[action.actorId] ?: return
        val target = entities[action.targetId!!] ?: return
        val payload = action.payload as? Int ?: return

        val dmgReduction = if (actor.isDefending) 2 else 1
        val damage = max(0, payload / dmgReduction)
        target.currentHp = max(0, target.currentHp - damage)

        actor.lastAction = "Attacked ${target.name} for $damage dmg"
        target.lastAction = "Took $damage dmg from ${actor.name}"
    }

    private fun executeDefend(action: CombatAction) {
        val actor = entities[action.actorId] ?: return
        actor.isDefending = true
        actor.lastAction = "Defending"
    }

    private fun executeSpell(action: CombatAction) {
        val actor = entities[action.actorId] ?: return
        val target = entities[action.targetId!!] ?: return
        val payload = action.payload as? SpellPayload ?: return

        val multiplier = when (payload.spellId) {
            "fireball" -> 3
            "frost" -> 2
            else -> 1
        }
        val dmgReduction = if (actor.isDefending) 2 else 1
        val damage = max(0, (payload.magnitude * multiplier) / dmgReduction)

        target.currentHp = max(0, target.currentHp - damage)
        actor.lastAction = "Cast ${payload.spellId} for $damage dmg"
        target.lastAction = "Took $damage dmg from spell"
    }

    private fun executeItem(action: CombatAction) {
        val actor = entities[entities.keys.firstOrNull { it == action.actorId } ?: return] ?: return
        val target = entities[action.targetId!!] ?: return
        val payload = action.payload as? ItemPayload ?: return

        // Heal items: "heal_potion"
        val healAmount = when (payload.itemId) {
            "heal_potion" -> payload.magnitude * 10
            else -> 0
        }
        if (healAmount > 0) {
            target.currentHp = minOf(target.maxHp, target.currentHp + healAmount)
            actor.lastAction = "Used ${payload.itemId} on ${target.name}"
            target.lastAction = "Healed ${healAmount} HP"
        } else {
            // Generic item usage
            actor.lastAction = "Used ${payload.itemId}"
            target.lastAction = "Item used by ${actor.name}"
        }
    }

    private fun advanceTurns() {
        // Decrement timers and find who is ready to act
        val ready = mutableListOf<String>()
        for (id in _turnOrder) {
            val timer = initiativeTimers.getOrDefault(id, 0) - entities[id]?.initiative ?: 0
            initiativeTimers[id] = max(0, timer)
            if (initiativeTimers[id] == 0) {
                ready.add(id)
            }
        }

        // Re-roll initiative for ready entities and re-sort turn order
        for (id in ready) {
            val entity = entities[id] ?: continue
            initiativeTimers[id] = entity.initiative
            // Move to back of turn order so they act after current cycle
            _turnOrder.remove(id)
            _turnOrder.add(id)
        }

        // Determine next actor: first entity whose timer is 0 in the turn order
        currentActorId = _turnOrder.firstOrNull { id -> initiativeTimers[id] == 0 }
    }

    /** Resets combat state for a new encounter. */
    fun reset() {
        entities.values.forEach { it.currentHp = it.maxHp; it.isDefending = false; it.lastAction = "" }
        initiativeTimers.keys.forEach { initiativeTimers[it] = 0 }
        _actionQueue.clear()
        _turnOrder.clear()
        entities.keys.forEach { if (!_turnOrder.contains(it)) _turnOrder.add(it) }
        currentActorId = _turnOrder.firstOrNull()
        isProcessing = false
    }

    /** Returns true if all enemies are defeated. */
    fun isCombatFinished(): Boolean {
        return entities.values.filter { it.maxHp > 0 }.all { it.currentHp <= 0 }
    }
}

/** State of an entity in combat. */
@Stable
data class EntityState(
    val id: String,
    val name: String,
    val maxHp: Int,
    var currentHp: Int,
    val initiative: Int,
    val defense: Int,
    var isDefending: Boolean,
    var lastAction: String = ""
)