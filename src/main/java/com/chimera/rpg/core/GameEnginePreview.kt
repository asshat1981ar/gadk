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

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

/**
 * Preview composable for the [GameEngineView] that auto-starts the engine
 * and renders the UI in design-time tools.
 */
@Composable
public fun GameEngineView_Preview(
    engine: GameEngine = remember { GameEngine() }
) {
    // Start the engine when the preview enters composition.
    LaunchedEffect(engine) {
        engine.start()
        // Auto-stop after a short duration so the preview stays responsive.
        kotlinx.coroutines.delay(2000)
        engine.stop()
    }

    GameEngineView(engine = engine, modifier = ModifierPreview)
}

/**
 * Modifier used by preview layouts to provide a reasonable size without
 * relying on unbounded constraints.
 */
private val ModifierPreview = androidx.compose.ui.Modifier
    .then(androidx.compose.ui.Modifier)
    .then(androidx.compose.ui.Modifier)

/**
 * Standalone preview showing the engine in RUNNING state.
 */
@Preview(name = "Engine Running", widthDp = 360, heightDp = 640, showBackground = true)
@Composable
private fun Preview_Running() {
    val engine = remember { GameEngine() }
    LaunchedEffect(engine) {
        engine.start()
        kotlinx.coroutines.delay(5000)
        engine.stop()
    }
    GameEngineView(engine = engine)
}

/**
 * Standalone preview showing the engine in PAUSED state.
 */
@Preview(name = "Engine Paused", widthDp = 360, heightDp = 640, showBackground = true)
@Composable
private fun Preview_Paused() {
    val engine = remember { GameEngine() }
    LaunchedEffect(engine) {
        engine.start()
        kotlinx.coroutines.delay(500)
        engine.pause()
        kotlinx.coroutines.delay(2000)
        engine.resume()
        kotlinx.coroutines.delay(2000)
        engine.stop()
    }
    GameEngineView(engine = engine)
}

/**
 * Standalone preview showing the engine in STOPPED state.
 */
@Preview(name = "Engine Stopped", widthDp = 360, heightDp = 640, showBackground = true)
@Composable
private fun Preview_Stopped() {
    val engine = remember { GameEngine(engineConfig = EngineConfig(targetFps = 30)) }
    LaunchedEffect(engine) {
        engine.start()
        kotlinx.coroutines.delay(300)
        engine.stop()
    }
    GameEngineView(engine = engine)
}