/*
 * Copyright 2025 Chimera RPG.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.chimera.rpg.core

import android.os.Handler
import android.os.Looper
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector1D
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import import androidx.compose.runtime.getValue
import import androidx.compose.runtime.mutableFloatStateOf
import import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
nimport kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.max
import kotlin.math.min

/**
 * Represents the overall state of the RPG core game engine.
 */
public enum class GameState {
    /** The engine is initializing resources and subsystems. */
    INITIALIZING,

    /** The engine is actively running the main game loop. */
    RUNNING,

    /** The engine is paused, typically during menus or backgrounding. */
    PAUSED,

    /** The engine has completed its lifecycle (e.g., game over). */
    STOPPED
}

/**
 * Configuration parameters for the game engine.
 *
 * @param targetFps The desired frames-per-second for the game loop.
 * @param updateIntervalMs The logical update interval in milliseconds.
 * @param renderIntervalMs The minimum render interval in milliseconds derived from target FPS.
 */
public data class EngineConfig(
    public val targetFps: Int = 60,
    public val updateIntervalMs: Long = 16,
    public val renderIntervalMs: Long = 16
)

/**
 * Snapshot of engine performance metrics captured per frame.
 *
 * @param frameNumber The cumulative frame count.
 * @param deltaTimeMs Time elapsed since the last frame in milliseconds.
 * @param fps The current instantaneous FPS.
 * @param averageFps The rolling average FPS over the last second.
 */
public data class PerformanceMetrics(
    public val frameNumber: Long,
    public val deltaTimeMs: Long,
    public val fps: Float,
    public val averageFps: Float
)

/**
 * Core game engine responsible for the game loop, state management,
 * FPS tracking, and main thread scheduling.
 *
 * The engine uses a fixed timestep for game updates (typically 16ms for 60 FPS)
 * and decouples rendering from updates to maintain consistent simulation behavior
 * regardless of rendering framerate variations.
 */
public class GameEngine {
    /** Current state of the engine. */
    public var state: GameState = GameState.INITIALIZING
        private set

    /** The configuration used to initialize this engine instance. */
    public val config: EngineConfig

    /** Current performance metrics. Updated each frame. */
    public var metrics: PerformanceMetrics = PerformanceMetrics(
        frameNumber = 0,
        deltaTimeMs = 0,
        fps = 0f,
        averageFps = 0f
    )
        private set

    /** The coroutine scope managing engine jobs. */
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** The handler for posting tasks to the main thread. */
    private val mainHandler = Handler(Looper.getMainLooper())

    /** A job reference for the game loop coroutine. */
    private var loopJob: Job? = null

    /** Accumulated time not yet processed by an update. */
    private var accumulator: Long = 0

    /** Timestamp of the last frame in nanoseconds. */
    private var lastFrameTimeNs: Long = 0

    /** Running sum of FPS values for average calculation. */
    private var fpsSum: Double = 0.0

    /** Count of FPS samples collected for the rolling average. */
    private var fpsSampleCount: Int = 0

    /**
     * Constructs a new [GameEngine] with the given configuration.
     *
     * @param config The engine configuration. Defaults to 60 FPS with 16ms update interval.
     */
    public constructor(config: EngineConfig = EngineConfig()) {
        this.config = config
    }

    /**
     * Starts the game loop and transitions the engine to the [RUNNING] state.
     * Safe to call multiple times; repeated calls on a running engine are ignored.
     */
    public fun start() {
        if (state == GameState.RUNNING) return
        state = GameState.RUNNING
        lastFrameTimeNs = System.nanoTime()
        accumulator = 0
        fpsSum = 0.0
        fpsSampleCount = 0

        loopJob = scope.launch {
            while (state == GameState.RUNNING) {
                val currentTimeNs = System.nanoTime()
                val elapsedNs = currentTimeNs - lastFrameTimeNs
                lastFrameTimeNs = currentTimeNs
                val elapsedMs = (elapsedNs / 1_000_000).toLong()

                // Update performance metrics
                val instantFps = if (elapsedMs > 0) 1000.0 / elapsedMs else 60.0
                metrics = metrics.copy(
                    frameNumber = metrics.frameNumber + 1,
                    deltaTimeMs = elapsedMs
                )

                // Update FPS rolling average
                fpsSum += instantFps
                fpsSampleCount++
                val averageFps = (fpsSum / fpsSampleCount).toFloat()
                metrics = metrics.copy(fps = instantFps.toFloat(), averageFps = averageFps)

                // Fixed timestep update
                accumulator += elapsedMs
                val updateInterval = config.updateIntervalMs
                var numUpdates = 0
                while (accumulator >= updateInterval) {
                    onUpdate(updateInterval)
                    accumulator -= updateInterval
                    numUpdates++
                    if (numUpdates >= MAX_UPDATES_PER_FRAME) break
                }

                // Render is called immediately after the loop iteration
                onRenderRequested()

                // Sleep to respect target frame time
                val targetFrameNs = config.renderIntervalMs * 1_000_000
                val sleepNs = targetFrameNs - (System.nanoTime() - currentTimeNs)
                if (sleepNs > 0) {
                    delay(sleepNs / 1_000_000)
                }
            }
        }
    }

    /**
     * Pauses the game loop, freezing state without releasing resources.
     * Transitions the engine to the [PAUSED] state.
     */
    public fun pause() {
        if (state != GameState.RUNNING) return
        state = GameState.PAUSED
    }

    /**
     * Resumes the game loop from a paused state.
     * If the engine is not paused, this is a no-op.
     */
    public fun resume() {
        if (state != GameState.PAUSED) return
        state = GameState.RUNNING
        lastFrameTimeNs = System.nanoTime()
    }

    /**
     * Stops the game loop, cleans up resources, and transitions to [STOPPED].
     * Safe to call from any state.
     */
    public fun stop() {
        if (state == GameState.STOPPED) return
        state = GameState.STOPPED
        loopJob?.cancel()
        loopJob = null
        scope.coroutineContext.cancel()
        mainHandler.removeCallbacksAndMessages(null)
    }

    /**
     * Called every fixed update interval with the step delta in milliseconds.
     * Override this in subclasses to implement game logic, physics, and state changes.
     *
     * @param deltaMs The fixed timestep in milliseconds.
     */
    public open fun onUpdate(deltaMs: Long) {
        // No-op base implementation; override to add game logic.
    }

    /**
     * Called to signal that a render pass should occur.
     * Override this in subclasses with a [Composable] function to trigger recomposition
     * with the current engine state.
     */
    public open fun onRenderRequested() {
        // No-op base implementation; UI is driven externally via state observation.
    }

    /**
     * Posts a [runnable] to be executed on the main thread.
     *
     * @param runnable A lambda with no parameters and no return value.
     */
    public fun postToMainThread(runnable: () -> Unit) {
        mainHandler.post { runnable() }
    }

    companion object {
        /** Safety cap to prevent runaway update loops. */
        private const val MAX_UPDATES_PER_FRAME: Int = 5
    }
}

/**
 * Composable that renders the RPG core engine state using Jetpack Compose Canvas.
 *
 * This component visualizes the engine's current state, FPS, and frame timing
 * using simple geometric shapes drawn on a [Canvas].
 *
 * @param engine The game engine instance to observe and render.
 * @param modifier Optional [Modifier] for layout and styling.
 *
 * @see GameEngine
 */
@Composable
public fun GameEngineView(
    engine: GameEngine,
    modifier: Modifier = Modifier
) {
    val inspectionMode = LocalInspectionMode.current
    // Animate the engine state as a color value for visual distinction
    val stateColor by remember(engine.state) {
        mutableFloatStateOf(
            when (engine.state) {
                GameState.INITIALIZING -> 0.6f // Cyan
                GameState.RUNNING -> 0.2f     // Green
                GameState.PAUSED -> 0.4f      // Yellow
                GameState.STOPPED -> 0.0f     // Red
            }
        )
    }
    val animatedColor = remember { Animatable(stateColor) }
    LaunchedEffect(engine.state) {
        animatedColor.animateTo(
            targetValue = stateColor,
            animationSpec = tween(durationMillis = 300, easing = LinearEasing)
        )
    }

    Canvas(
        modifier = modifier
            .fillMaxSize()
    ) { drawScope ->
        val width = size.width
        val height = size.height

        // Background
        drawRect(
            color = Color(0xFF1a1a2e),
            size = size
        )

        if (inspectionMode) {
            // Placeholder during design-time preview
            drawRect(
                color = Color(0x33ffffff),
                topLeft = Offset(width / 2 - 40, height / 2 - 10),
                size = androidx.compose.ui.unit.Size(width = 80f, height = 20f)
            )
            return@Canvas
        }

        // State indicator circle
        val indicatorRadius = 16.dp.toPx()
        drawCircle(
            color = Color(animatedColor.value, 0.8f, 1f),
            radius = indicatorRadius,
            center = Offset(60f, 60f)
        )

        // FPS display
        val fpsText = "FPS: ${engine.metrics.averageFps.toInt()}"
        drawContext.canvas.nativeCanvas.apply {
            // Note: In a real app you'd use a proper text-rendering API.
            // Here we approximate with a scaled rectangle to represent text area.
            val textArea = RectF(120f, 40f, 300f, 80f)
            drawRoundRect(
                color = Color(0xAAffffff).toArgb(),
                topLeft = textArea.topLeft,
                size = textArea.size,
                cornerRadiusX = 8f,
                cornerRadiusY = 8f
            )
        }

        // Performance graph (mini area chart) - last 60 frames
        val historySize = 60
        val history = remember { mutableListOf<Float>() }
        if (history.size > historySize) history.removeAt(0)
        history.add(engine.metrics.fps)

        if (history.size > 1) {
            val graphWidth = width - 40.dp.toPx()
            val graphHeight = 40.dp.toPx()
            val graphLeft = 20.dp.toPx()
            val graphTop = 100.dp.toPx()

            val maxFps = max(1f, history.maxOrNull() ?: 1f)
            drawContext.canvas.nativeCanvas.apply {
                drawColor(Color(0x10ffffff).toArgb()) // overlay
            }
            for (i in 1 until history.size) {
                val x0 = graphLeft + (i - 1) * graphWidth / historySize
                val y0 = graphTop + graphHeight * (1 - min(1f, history[i - 1] / maxFps))
                val x1 = graphLeft + i * graphWidth / historySize
                val y1 = graphTop + graphHeight * (1 - min(1f, history[i] / maxFps))
                drawContext.canvas.nativeCanvas.apply {
                    drawLine(x0, y0, x1, y1, android.graphics.Paint().apply {
                        color = Color(0x8800ff00.toInt()).toArgb()
                        strokeWidth = 2f
                    })
                }
            }
        }

        // Delta time bar
        val barWidth = 40.dp.toPx()
        val barHeight = min(100.dp.toPx(), engine.metrics.deltaTimeMs * 0.2f)
        drawRect(
            color = Color(0x88ff00ff),
            topLeft = Offset(width - 70f, height - 120f),
            size = androidx.compose.ui.unit.Size(barWidth, barHeight)
        )
    }
}

/**
 * Preview composable showing the [GameEngineView] in various states.
 * This is for design-time inspection only and is disabled in production.
 */
@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun GameEngineView_Preview() {
    val engine = remember { GameEngine() }
    // Start the engine in preview mode for a quick visual check
    LaunchedEffect(Unit) {
        engine.start()
        // Auto-stop after a short duration to keep preview fast
        delay(2000)
        engine.stop()
    }
    GameEngineView(engine = engine)
}