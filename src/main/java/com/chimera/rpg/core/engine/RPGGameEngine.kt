package com.chimera.rpg.core.engine

/**
 * Core game engine interface responsible for the fixed-timestep update loop
 * and state management. Implementations should be thread-safe for calls
 * from the update thread, and UI state changes should be posted to the
 * main thread via [postToMainThread].
 */
interface RPGGameEngine {

    /** Current game state. */
    val state: GameState

    /** Starts the engine. Safe to call multiple times; no-op if already running. */
    fun start()

    /** Stops the engine. Safe to call when not running. */
    fun stop()

    /**
     * Performs a single game update. Called by the game loop at a fixed
     * timestep (in milliseconds).
     */
    fun update(deltaTimeMs: Double)

    /** Registers a listener for state changes. */
    fun registerListener(listener: GameUpdateListener)

    /** Removes a previously registered listener. */
    fun unregisterListener(listener: GameUpdateListener)

    /** Posts a runnable to the main thread for UI updates. */
    fun postToMainThread(runnable: () -> Unit)
}

/**
 * Listener for game state changes.
 */
interface GameUpdateListener {
    /** Called when the game state changes. */
    fun onGameStateChanged(newState: GameState)
}