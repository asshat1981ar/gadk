package com.chimera.rpg.core.engine

/**
 * Represents the current state of the game.
 */
sealed interface GameState {
    /** The game is actively running and updating. */
    data object Playing : GameState

    /** The game is paused; updates are suspended. */
    data object Paused : GameState

    /** The game has ended; no further updates should be processed. */
    data object GameOver : GameState
}

/**
 * Returns a user-facing label for the given state.
 */
fun GameState.label(): String = when (this) {
    is GameState.Playing -> "Playing"
    is GameState.Paused -> "Paused"
    is GameState.GameOver -> "Game Over"
}