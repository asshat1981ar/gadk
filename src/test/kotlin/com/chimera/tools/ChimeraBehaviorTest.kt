package com.chimera.tools

import io.mockk.every
import io.mockk.mockk
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.TestInstance

/**
 * Unit test suite for ChimeraBehavior class.
 * Tests deterministic NPC behavioral patterns and decision-making logic.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class ChimeraBehaviorTest {

    private lateinit var behavior: ChimeraBehavior

    @BeforeEach
    fun setUp() {
        behavior = ChimeraBehavior()
    }

    @Test
    fun `test initial state is neutral`() {
        val state = behavior.getCurrentState()
        assertEquals(ChimeraBehavior.State.NEUTRAL, state)
    }

    @Test
    fun `test state transition to aggressive`() {
        behavior.transitionTo(ChimeraBehavior.State.AGGRESSIVE)
        assertEquals(ChimeraBehavior.State.AGGRESSIVE, behavior.getCurrentState())
    }

    @Test
    fun `test state transition to defensive`() {
        behavior.transitionTo(ChimeraBehavior.State.DEFENSIVE)
        assertEquals(ChimeraBehavior.State.DEFENSIVE, behavior.getCurrentState())
    }

    @Test
    fun `test state transition to neutral`() {
        behavior.transitionTo(ChimeraBehavior.State.NEUTRAL)
        assertEquals(ChimeraBehaviour.State.NEUTRAL, behavior.getCurrentState())
    }

    @Test
    fun `test decision making with high threat level`() {
        val decision = behavior.makeDecision(threatLevel = 0.9f)
        assertTrue(decision.isAggressive || decision.isDefensive)
    }

    @Test
    fun `test decision making with low threat level`() {
        val decision = behavior.makeDecision(threatLevel = 0.1f)
        assertEquals(ChimeraBehavior.State.NEUTRAL, decision.nextState)
    }

    @Test
    fun `test calculate response time returns positive value`() {
        val responseTime = behavior.calculateResponseTime()
        assertTrue(responseTime > 0)
    }

    @Test
    fun `test calculate response time with mocked environment`() {
        val mockEnvironment: Environment = mockk()
        every { mockEnvironment.getDifficulty() } returns 2
        
        val responseTime = behavior.calculateResponseTime(environment = mockEnvironment)
        assertEquals(500L, responseTime)
    }

    @Test
    fun `test invalid state transition throws exception`() {
        assertThrows<IllegalArgumentException> {
            behavior.transitionTo(null as ChimeraBehavior.State?)
        }
    }

    @Test
    fun test multiple rapid transitions maintain consistency() {
        behavior.transitionTo(ChimeraBehavior.State.AGGRESSIVE)
        behavior.transitionTo(ChimeraBehavior.State.DEFENSIVE)
        behavior.transitionTo(ChimeraBehavior.State.NEUTRAL)
        
        assertEquals(ChimeraBehavior.State.NEUTRAL, behavior.getCurrentState())
    }

    @Test
    fun test behavior reset returns to initial state() {
        behavior.transitionTo(ChimeraBehavior.State.AGGRESSIVE)
        behavior.reset()
        assertEquals(ChimeraBehavior.State.NEUTRAL, behavior.getCurrentState())
    }
}

/**
 * Mock Environment interface for testing.
 */
private interface Environment {
    fun getDifficulty(): Int
}