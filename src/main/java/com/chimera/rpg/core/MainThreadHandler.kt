package com.chimera.rpg.core

import android.os.Handler
import android.os.Looper

/**
 * Provides access to the main-thread [Handler] for posting UI updates.
 * This is a thin wrapper around [Handler(Looper.getMainLooper())].
 */
object MainThreadHandler {
    private val handler = Handler(Looper.getMainLooper())

    /** Posts a runnable to the main thread. */
    fun post(runnable: () -> Unit) {
        handler.post(runnable)
    }

    /** Posts a runnable to the main thread with a delay in milliseconds. */
    fun postDelayed(runnable: () -> Unit, delayMs: Long) {
        handler.postDelayed(runnable, delayMs)
    }

    /** Removes all pending callbacks. */
    fun removeCallbacks() {
        handler.removeCallbacksAndMessages(null)
    }
}