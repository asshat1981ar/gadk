import pytest

pytest.importorskip("google.adk")

from src.agents.builder import builder_agent
from src.agents.critic import critic_agent
from src.agents.finops import finops_agent
from src.agents.ideator import ideator_agent
from src.agents.orchestrator import orchestrator_agent
from src.agents.pulse import pulse_agent


def test_all_agents_are_adk_agents():
    for agent in [
        orchestrator_agent,
        ideator_agent,
        builder_agent,
        critic_agent,
        pulse_agent,
        finops_agent,
    ]:
        assert hasattr(agent, "name")
        assert hasattr(agent, "instruction")


def test_orchestrator_has_sub_agents():
    assert hasattr(orchestrator_agent, "sub_agents")
    assert len(orchestrator_agent.sub_agents) == 5


def test_orchestrator_sub_agent_names():
    names = [a.name for a in orchestrator_agent.sub_agents]
    assert "Ideator" in names
    assert "Builder" in names
    assert "Critic" in names
    assert "Pulse" in names
    assert "FinOps" in names


def test_ideator_has_description():
    assert hasattr(ideator_agent, "description")
    assert ideator_agent.description
