"""
Unit tests for src.tools.content_guards.

Each test is named after the real failure mode it prevents from recurring.
References are to issues/PRs in asshat1981ar/project-chimera.
"""

from src.tools.content_guards import (
    LEAKED_REVIEW_PLACEHOLDER,
    is_duplicate_title,
    is_low_value_content,
    issue_signature,
    sanitize_review,
)

# ---------------------------------------------------------------------------
# sanitize_review
# ---------------------------------------------------------------------------


def test_sanitize_review_passes_through_real_prose():
    review = (
        "1) What's good\n"
        "- Clear separation of concerns.\n"
        "- Type hints throughout.\n"
        "\n2) What's missing\n"
        "- No unit tests for the scanner logic.\n"
    )
    assert sanitize_review(review) == review.strip()


def test_sanitize_review_rejects_raw_json_array_tool_call():
    # Exact shape seen in project-chimera issues #167, #165, #151, #149, #145.
    leakage = '[{"action": "list_repo_contents", "args": {"path": "src"}}]'
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_raw_json_object_tool_call():
    # Shape seen in #158, #141.
    leakage = '{"action": "list_directory", "args": {"path": "src/test"}}'
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_fenced_json_tool_call():
    # Shape seen in #139, #136 — same leakage wrapped in a markdown fence.
    leakage = '```json\n[{"action": "list_directory", "arguments": {"path": "src"}}]\n```'
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_tool_name_key_variant():
    # Some critic runs used "tool_name" instead of "action" — same failure class.
    leakage = '[{"tool_name": "list_directory", "arguments": {"path": "src"}}]'
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_thinking_fragment():
    # Shape seen in PR #159 body: the RPG engine generated an empty Kotlin
    # file and the "review" is the LLM thinking out loud.
    leakage = (
        "I'll review the Kotlin RPG Turn-Based Combat System component. "
        "However, I notice the code snippet is empty. Let me first check "
        "if there are any files in the repository that might contain this "
        "component."
    )
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_sidestep():
    # Shape seen in #147, #141: "Review saved to src/review.txt." — Critic
    # wrote the review to the target repo instead of returning it. That
    # leaked file write is itself a separate bug (tracked elsewhere), but
    # the empty-return needs to be caught here too.
    leakage = "Review completed and saved to src/review.txt."
    assert sanitize_review(leakage) == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_rejects_none_and_empty():
    assert sanitize_review(None) == LEAKED_REVIEW_PLACEHOLDER
    assert sanitize_review("") == LEAKED_REVIEW_PLACEHOLDER
    assert sanitize_review("    \n   \n\t") == LEAKED_REVIEW_PLACEHOLDER


def test_sanitize_review_keeps_prose_that_happens_to_contain_braces():
    # We must not over-match — real review prose can reference JSON inline.
    review = (
        "The config struct looks correct. {foo: bar} style literals are "
        "used consistently. No concerns."
    )
    assert sanitize_review(review) == review.strip()


# ---------------------------------------------------------------------------
# is_low_value_content
# ---------------------------------------------------------------------------


def test_is_low_value_content_rejects_empty_and_none():
    assert is_low_value_content(None) is True
    assert is_low_value_content("") is True
    assert is_low_value_content("   \n\n  ") is True


def test_is_low_value_content_rejects_kotlin_class_stub():
    # The shape of real stubs the RPG engine has been shipping.
    stub = "class TurnBasedCombatSystem {\n}\n"
    assert is_low_value_content(stub) is True


def test_is_low_value_content_rejects_python_pass_stub():
    stub = "class Foo:\n    pass\n"
    assert is_low_value_content(stub) is True


def test_is_low_value_content_rejects_comment_only():
    stub = "// TODO: implement\n// will do later\n"
    assert is_low_value_content(stub) is True


def test_is_low_value_content_accepts_real_implementation():
    # Long enough to clear the 80-byte floor and not a stub pattern.
    real = (
        "class CombatManager {\n"
        "  fun attack(target: Actor, weapon: Weapon): DamageResult {\n"
        "    val hitRoll = dice.roll(20) + weapon.toHit\n"
        "    if (hitRoll >= target.armorClass) {\n"
        "      return DamageResult.hit(weapon.damage.roll())\n"
        "    }\n"
        "    return DamageResult.miss()\n"
        "  }\n"
        "}\n"
    )
    assert is_low_value_content(real) is False


def test_is_low_value_content_respects_custom_min_bytes():
    # Explicit override for callers who want stricter/looser gates.
    short_but_real = "val x = computeCriticalHitMultiplier(actor, weapon)"
    assert is_low_value_content(short_but_real, min_bytes=100) is True
    assert is_low_value_content(short_but_real, min_bytes=10) is False


# ---------------------------------------------------------------------------
# issue_signature / is_duplicate_title
# ---------------------------------------------------------------------------


def test_issue_signature_is_stable():
    sig1 = issue_signature("[SWARM TASK] Implement Property-Based Testing")
    sig2 = issue_signature("[SWARM TASK] Implement Property-Based Testing")
    assert sig1 == sig2


def test_issue_signature_ignores_trivial_whitespace_drift():
    # Same title with extra spaces must normalize identically.
    sig1 = issue_signature("[SWARM TASK] Implement Property-Based Testing")
    sig2 = issue_signature("[SWARM TASK]   Implement  Property-Based Testing  ")
    assert sig1 == sig2


def test_issue_signature_distinguishes_different_titles():
    sig1 = issue_signature("[SWARM TASK] Implement Property-Based Testing")
    sig2 = issue_signature("[SWARM TASK] Implement Fuzz Testing")
    assert sig1 != sig2


def test_is_duplicate_title_catches_the_real_127_to_133_case():
    # The 7 duplicates in project-chimera #127-#133 all had this exact title.
    new = "[SWARM TASK] Implement Property-Based Testing"
    existing = [
        "[SWARM TASK] Implement Property-Based Testing",  # #127
        "[SDLCBot] Add unit test suite with JUnit5 and MockK",
    ]
    assert is_duplicate_title(new, existing) is True


def test_is_duplicate_title_is_case_insensitive():
    new = "[SWARM TASK] Implement Property-Based Testing"
    existing = ["[swarm task] implement property-based testing"]
    assert is_duplicate_title(new, existing) is True


def test_is_duplicate_title_no_false_positive():
    new = "[SDLCBot] Add Room database layer"
    existing = [
        "[SDLCBot] Add Jetpack Navigation component",
        "[SDLCBot] Add dependency injection with Koin",
    ]
    assert is_duplicate_title(new, existing) is False
