package com.chimera.rpg.core.engine

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * Fixed-timestep game loop implementation. Runs on a background coroutine
 * and calls [RPGGameEngine.update] at a consistent rate.
 *
 * This class is thread-safe for listener registration.
 */
internal class GameLoop(private val engine: RPGGameEngine) {

    private val scope = CoroutineScope(engine.asContextElement())
    private val mutex = Mutex()
    private var listeners = emptyList<GameUpdateListener>()
    private var job: Job? = null
    private var running = false

    /** Registers a listener. Thread-safe. */
    fun registerListener(listener: GameUpdateListener) {
        mutex.withLock {
            listeners = listeners + listener
        }
    }

    /** Removes a listener. Thread-safe. */
    fun unregisterListener(listener: GameUpdateListener) {
        mutex.withLock {
            listeners = listeners - listener
        }
    }

    /** Starts the loop if not already running. */
    fun start() {
        mutex.withLock {
            if (running) return
            running = true
            job = scope.launch {
                while (isActive) {
                    try {
                        // Fixed timestep of 16ms (approximately 60 FPS)
                        engine.update(16.0)
                    } catch (e: Exception) {
                        // TODO: proper error handling / reporting
                        e.printStackTrace()
                    }
                    kotlinx.coroutines.delay(16) // ~60 FPS fixed timestep
                }
            }
        }
    }

    /** Stops the loop and clears listeners. */
    fun stop() {
        mutex.withLock {
            running = false
            job?.cancel()
            job = null
            listeners = emptyList()
        }
    }

    /** Performs a single update cycle, notifying listeners. */
    suspend fun update(deltaTimeMs: Double) = withContext(scope.coroutineContext) {
        mutex.withLock {
            // In a real implementation, the engine would perform game logic here
            // For this template, we rely on the engine's own update implementation
            listeners.forEach { it.onGameStateChanged(engine.state) }
        }
    }

    /**
     * Helper to provide a [CoroutineContext] that can be used as a [java.lang.AutoCloseable].
     */
    private fun RPGGameEngine.asContextElement() = kotlin.coroutines.CoroutineContext {}
}