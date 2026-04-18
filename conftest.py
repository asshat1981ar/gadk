"""Pytest bootstrap — sets env defaults needed by the swarm before imports.

Tests run without PyGithub and without a live OpenRouter key; the runtime
defaults to "fail loud" so production misconfiguration is caught, but the
test environment opts into the in-process mocks explicitly here.
"""

from __future__ import annotations

import os

# Phase 0 stabilization: allow MockGithub only under the explicit test env.
os.environ.setdefault("GITHUB_MOCK_ALLOWED", "true")
os.environ.setdefault("TEST_MODE", "true")
