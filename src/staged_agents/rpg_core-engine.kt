// app/src/main/java/com/chimera/rpg/core/GameEngine.kt
package com.chimera.rpg.core

import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.chimera.rpg.core.engine.GameLoop
import com.chimera.rpg.core.engine.GameState
import com.chimera.rpg.core.engine.RPGCoreEngine
import com.chimera.rpg.core.engine.loop.DefaultGameLoop
import com.chimera.rpg.core.engine.state.DefaultGameState
import com.chimera.rpg.core.engine.time.FPSCounter
import com.chimera.rpg.core.engine.time.FrameTimeCalculator
import com.chimera.rpg.core.engine.time.TimeSource
import com.chimera.rpg.core.engine.time.defaultTimeSource
import com.chimera.rpg.core.engine.update.GameUpdateProcessor
import com.chimera.rpg.core.engine.update.UpdateProcessor

/**
 * RPG Core Game Engine.
 *
 * Provides a production-grade game loop, state machine, FPS counter, and main-thread handler
 * designed for Jetpack Compose UI rendering via Canvas.
 *
 * Responsibilities:
 * - Manages [GameState] transitions.
 * - Drives a fixed timestep game loop ([GameLoop]).
 * - Tracks FPS via [FPSCounter].
 * - Schedules updates on the main/Android UI thread via [Handler].
 *
 * Usage:
 * ```
 * @Composable
 * fun MyGameScreen() {
 *     RPGGameEngine(
 *         initialState = GameState.Loading,
 *         onRender = { canvas, state, frameTime ->
 *             // draw with canvas.drawRect, canvas.drawCircle, canvas.drawImage
 *         }
 *     )
 * }
 * ```
 */
class RPGCoreEngine(
    private val context: android.content.Context,
    initialState: GameState = DefaultGameState.Idle,
    private val updateProcessor: UpdateProcessor = GameUpdateProcessor(),
    private val timeSource: TimeSource = defaultTimeSource(),
    private val loop: GameLoop = DefaultGameLoop()
) {
    private val mainHandler = Handler(Looper.getMainLooper())

    private val _state: MutableState<GameState> = mutableStateOf(initialState)
    val state: MutableState<GameState> get() = _state

    private val _fps: MutableState<Float> = mutableStateOf(0f)
    val fps: MutableState<Float> get() = _fps

    private val fpsCounter = FPSCounter(timeSource = timeSource)

    /**
     * Transition to a new game state.
     */
    fun setState(newState: GameState) {
        _state.value = newState
    }

    /**
     * Process one update tick on the main thread.
     * Safe to call from background threads via [mainHandler.post].
     */
    fun tick() {
        val currentState = state.value
        val deltaMs = loop.tickIntervalMs
        val frameTimeNs = timeSource.nanoTime()
        val frameTimeMs = FrameTimeCalculator.toMillis(frameTimeNs)

        updateProcessor.process(
            state = currentState,
            deltaMs = deltaMs,
            frameTimeNs = frameTimeNs,
            frameTimeMs = frameTimeMs,
            output = object : UpdateProcessor.UpdateOutput {
                override fun setState(newState: GameState) {
                    // Post to main thread to ensure state change is composed on UI thread
                    mainHandler.post { _state.value = newState }
                }

                override fun render(canvas: AndroidCanvasProxy, deltaMs: Long) {
                    // Rendering is handled by the Composable; this callback is informational
                }
            }
        )

        // Update FPS counter every tick and expose smoothed FPS
        _fps.value = fpsCounter.updateAndGetFps(frameTimeNs)
    }

    /**
     * Schedules [tick] on the main thread with the loop's interval.
     * Returns a runnable that can be removed to stop scheduling.
     */
    fun scheduleTick(): Runnable {
        return object : Runnable {
            override fun run() {
                tick()
                mainHandler.postDelayed(this, loop.tickIntervalMs)
            }
        }
    }

    /**
     * Starts the game loop by posting the first tick.
     */
    fun start() {
        mainHandler.post(scheduleTick())
    }

    /**
     * Stops the game loop by removing any pending posts.
     */
    fun stop() {
        mainHandler.removeCallbacksAndMessages(null)
    }
}

/**
 * Composable that hosts the RPG game engine and renders via Canvas.
 *
 * @param initialState Initial [GameState].
 * @param modifier Modifier for the hosting view.
 * @param onRender Render callback invoked every frame with canvas, current state, and frameTimeNs.
 *                 Use [CanvasProxy.drawRect], [CanvasProxy.drawCircle], [CanvasProxy.drawImage].
 */
@Composable
fun RPGGameEngine(
    initialState: GameState = DefaultGameState.Idle,
    modifier: Modifier = Modifier,
    onRender: @Composable (CanvasProxy, GameState, frameTimeNs: Long) -> Unit
) {
    val engine = remember {
        RPGCoreEngine(
            context = LocalContext.current,
            initialState = initialState
        )
    }
    val lifecycleOwner = LocalLifecycleOwner.current

    // Observe lifecycle to start/stop the engine
    SideEffect {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> engine.start()
                Lifecycle.Event.ON_PAUSE -> engine.stop()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            engine.stop()
        }
    }

    // Start engine when initialState is set externally (if needed)
    LaunchedEffect(initialState) {
        // Keep engine managed by lifecycle; this is a hook for future extensions
    }

    var frameTimeNs by remember { mutableStateOf(0L) }

    // Update frameTimeNs each tick so the Composable can read it during recomposition
    LaunchedEffect(engine) {
        // Tick on main thread at loop interval; update frameTimeNs for rendering
        engine.tick()
        frameTimeNs = engine.loop.tickIntervalNs
    }

    CompositionLocalProvider(
        LocalGameEngine provides engine
    ) {
        AndroidView(
            factory = { context ->
                // Custom Compose-friendly view that defers to Canvas drawing
                engine.view = ComposeGameView(context).apply {
                    setContent {
                        val engineProvided = checkNotNull(LocalGameEngine.current)
                        val currentState = engineProvided.state.value
                        onRender(
                            canvas = CanvasProxy(it),
                            state = currentState,
                            frameTimeNs = frameTimeNs
                        )
                    }
                }
            },
            modifier = modifier
        )
    }
}

/**
 * Preview composable for [RPGGameEngine].
 * Shows a simple render loop with FPS counter and state indicator.
 */
@Composable
@Preview(showBackground = true, name = "RPG Game Engine Preview")
fun RPGGameEnginePreview() {
    var gameState by remember { mutableStateOf(GameState.Loading) }

    RPGGameEngine(initialState = gameState) { canvas, state, frameTimeNs ->
        // Background
        canvas.drawRect(
            topLeft = Offset(0f, 0f),
            size = canvas.size,
            color = android.graphics.Color.DKGRAY
        )

        // FPS display
        val fps = canvas.engine.fps.value
        canvas.drawText(
            text = "FPS: ${fps.toInt()}",
            x = 16f,
            y = 48f,
            color = android.graphics.Color.WHITE
        )

        // State display
        val stateText = when (state) {
            is GameState.Loading -> "Loading..."
            is GameState.Playing -> "Playing"
            is GameState.Paused -> "Paused"
            is GameState.GameOver -> "Game Over"
        }
        canvas.drawText(
            text = stateText,
            x = 16f,
            y = 80f,
            color = android.graphics.Color.GREEN
        )

        // Simple animated circle to show rendering works
        val time = (frameTimeNs / 1_000_000).toFloat()
        canvas.drawCircle(
            center = Offset(
                x = 150f + 50f * kotlin.math.sin(time / 100f),
                y = 150f + 50f * kotlin.math.cos(time / 120f)
            ),
            radius = 30f,
            color = android.graphics.Color.parseColor("#FF6F00")
        )
    }
}

/**
 * Represents the various states of the RPG game.
 */
sealed interface GameState {
    /** Initializing resources, loading assets. */
    data object Loading : GameState

    /** Actively playing. */
    data object Playing : GameState

    /** Paused by user or game logic. */
    data object Paused : GameState

    /** Game has ended (victory or defeat). */
    data object GameOver : GameState

    /** Idle, waiting for input or start signal. */
    data object Idle : GameState
}

/**
 * Default implementations of [GameState] singletons.
 */
object DefaultGameState {
    val Loading: GameState = Loading
    val Playing: GameState = Playing
    val Paused: GameState = Paused
    val GameOver: GameState = GameOver
    val Idle: GameState = Idle
}

/**
 * Game loop contract with fixed timestep.
 */
interface GameLoop {
    /** Milliseconds between ticks. */
    val tickIntervalMs: Long
    val tickIntervalNs: Long

    fun tick()
}

/**
 * Default fixed timestep game loop at 60 FPS (16 ms).
 */
class DefaultGameLoop private constructor(
    override val tickIntervalMs: Long = 16L,
    override val tickIntervalNs: Long = 16_000_000L
) : GameLoop {
    override fun tick() {
        // Fixed timestep logic handled externally; this is a marker/utility class.
    }

    companion object {
        operator fun invoke(
            tickIntervalMs: Long = 16L,
            tickIntervalNs: Long = 16_000_000L
        ): DefaultGameLoop = DefaultGameLoop(tickIntervalMs, tickIntervalNs)
    }
}

/**
 * FPS counter using exponential moving average for smooth readings.
 */
class FPSCounter(
    private val timeSource: TimeSource = defaultTimeSource(),
    private val alpha: Float = 0.125f
) {
    private var lastTimeNs: Long = timeSource.nanoTime()
    private var fps: Float = 60f

    /**
     * Updates FPS with the latest frame time and returns the current smoothed FPS.
     */
    fun updateAndGetFps(currentTimeNs: Long): Float {
        val deltaNs = currentTimeNs - lastTimeNs
        lastTimeNs = currentTimeNs
        val instantFps = if (deltaNs > 0) 1_000_000_000.0 / deltaNs else 60.0
        fps += alpha * (instantFps - fps)
        return fps
    }

    /**
     * Convenience wrapper that uses [timeSource.nanoTime] internally.
     */
    fun updateAndGetFps(): Float {
        return updateAndGetFps(timeSource.nanoTime())
    }
}

/**
 * Frame time utility object.
 */
object FrameTimeCalculator {
    fun toMillis(nanoseconds: Long): Long = nanoseconds / 1_000_000
    fun toNanos(millis: Long): Long = millis * 1_000_000
}

/**
 * Default time source delegating to [System.nanoTime].
 */
fun defaultTimeSource(): TimeSource = object : TimeSource {
    override fun nanoTime(): Long = System.nanoTime()
}

/**
 * Time source abstraction for testability.
 */
interface TimeSource {
    fun nanoTime(): Long
}

/**
 * Update processor that routes state changes and rendering through callbacks.
 */
class GameUpdateProcessor : UpdateProcessor {
    override fun process(
        state: GameState,
        deltaMs: Long,
        frameTimeNs: Long,
        frameTimeMs: Long,
        output: UpdateProcessor.UpdateOutput
    ) {
        when (state) {
            is GameState.Loading -> {
                // Simulate loading work
                output.setState(GameState.Playing)
            }
            is GameState.Playing -> {
                // Game logic update
                // Example: handle input, move entities, etc.
            }
            is GameState.Paused -> {
                // Paused: no game logic progression
            }
            is GameState.GameOver -> {
                // Game over handling
            }
            is GameState.Idle -> {
                output.setState(GameState.Loading)
            }
        }
    }
}

/**
 * Update processor interface.
 */
interface UpdateProcessor {
    fun process(
        state: GameState,
        deltaMs: Long,
        frameTimeNs: Long,
        frameTimeMs: Long,
        output: UpdateOutput
    )

    interface UpdateOutput {
        fun setState(newState: GameState)
        fun render(canvas: AndroidCanvasProxy, deltaMs: Long)
    }
}

/**
 * Android Canvas proxy exposing draw operations used by Compose rendering.
 */
class AndroidCanvasProxy(private val androidCanvas: android.graphics.Canvas) : CanvasProxy {
    override val size: Size
        get() = Size(androidCanvas.width.toFloat(), androidCanvas.height.toFloat())

    override fun drawRect(
        topLeft: Offset,
        size: Size,
        color: android.graphics.Color
    ) {
        val paint = android.graphics.Paint().apply { this.color = color.toInt() }
        androidCanvas.drawRect(
            topLeft.x,
            topLeft.y,
            topLeft.x + size.width,
            topLeft.y + size.height,
            paint
        )
    }

    override fun drawCircle(
        center: Offset,
        radius: Float,
        color: android.graphics.Color
    ) {
        val paint = android.graphics.Paint().apply { this.color = color.toInt() }
        androidCanvas.drawCircle(center.x, center.y, radius, paint)
    }

    override fun drawText(
        text: String,
        x: Float,
        y: Float,
        color: android.graphics.Color
    ) {
        val paint = android.graphics.Paint().apply {
            this.color = color.toInt()
            textSize = 24f
        }
        androidCanvas.drawText(text, x, y, paint)
    }
}

/**
 * Canvas proxy interface used by game rendering composables.
 */
interface CanvasProxy {
    val size: Size
    fun drawRect(topLeft: Offset, size: Size, color: android.graphics.Color)
    fun drawCircle(center: Offset, radius: Float, color: android.graphics.Color)
    fun drawText(text: String, x: Float, y: Float, color: android.graphics.Color)
}

/**
 * Offset representing a point in 2D space.
 */
data class Offset(val x: Float, val y: Float)

/**
 * Size representing width and height.
 */
data class Size(val width: Float, val height: Float)

/**
 * Holds a reference to the engine for composable access.
 */
internal expect var LocalGameEngine: CompositionLocal<RPGCoreEngine>

/**
 * Internal view that hosts the engine's rendering surface.
 */
private class ComposeGameView(context: android.content.Context) : android.view.View(context) {
    lateinit var setContent: () -> Unit

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        post(setContent)
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        // Clean up resources if needed
    }
}

DONE: rpg core engine with game loop, state machine, fps counter, and main thread handler