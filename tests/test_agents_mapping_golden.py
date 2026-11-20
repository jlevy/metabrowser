"""The two mapping tables, pinned as goldens, and the rules they must keep.

Each golden renders a provider's ordered rule table, the classification of every raw type
the research brief lists, and its tool-family table. A change to a table is a change to
every tally, so it shows up here as a diff to review.
"""

from __future__ import annotations

from metabrowser.builtin_plugins.agents import kinds
from tests.golden_harness import check_golden


def _render(
    title: str,
    rules: tuple[kinds.Rule, ...],
    brief: tuple[tuple[str, str, str], ...],
    tools: kinds._ToolTable,  # pyright: ignore[reportPrivateUsage]
) -> str:
    return (
        f"# {title}: ordered mapping table (raw type, subtype, block -> kind)\n"
        + kinds.render_table(rules)
        + f"\n# {title}: every raw type the research brief lists\n"
        + kinds.render_classification(rules, brief)
        + f"\n# {title}: tool name -> family (mcp__server__tool -> mcp:server.tool)\n"
        + kinds.render_tool_table(tools)
    )


def test_claude_mapping_golden() -> None:
    check_golden(
        "agents-mapping-claude.txt",
        _render(
            "Claude Code",
            kinds.CLAUDE_RULES,
            kinds.CLAUDE_BRIEF_TYPES,
            kinds.CLAUDE_TOOL_FAMILIES,
        ),
    )


def test_codex_mapping_golden() -> None:
    check_golden(
        "agents-mapping-codex.txt",
        _render(
            "Codex",
            kinds.CODEX_RULES,
            kinds.CODEX_BRIEF_TYPES,
            kinds.CODEX_TOOL_FAMILIES,
        ),
    )


def test_every_rule_names_a_real_kind_and_no_brief_type_is_unknown() -> None:
    for rules, brief in (
        (kinds.CLAUDE_RULES, kinds.CLAUDE_BRIEF_TYPES),
        (kinds.CODEX_RULES, kinds.CODEX_BRIEF_TYPES),
    ):
        assert {rule.kind for rule in rules} <= set(kinds.KINDS)
        assert "unknown" not in {rule.kind for rule in rules}
        for raw, sub, block in brief:
            assert kinds.classify(rules, raw, sub, block) != "unknown", (raw, sub, block)


def test_every_kind_is_reachable_from_some_table() -> None:
    reachable = {r.kind for r in kinds.CLAUDE_RULES} | {r.kind for r in kinds.CODEX_RULES}
    assert reachable | {"unknown"} == set(kinds.KINDS)


def test_first_match_wins_and_unmatched_is_unknown() -> None:
    rules = (kinds.Rule("a", "x", "*", "error"), kinds.Rule("a", "*", "*", "context"))
    assert kinds.classify(rules, "a", "x") == "error"
    assert kinds.classify(rules, "a", "y") == "context"
    assert kinds.classify(rules, "a") == "context"
    assert kinds.classify(rules, "b") == "unknown"
    assert kinds.classify(kinds.CLAUDE_RULES, "brand-new-record") == "unknown"
    # A rule that names a block never matches a record without one.
    assert kinds.classify(kinds.CLAUDE_RULES, "assistant") == "unknown"


def test_tool_families() -> None:
    assert kinds.tool_family("claude", "Bash") == ("shell", "Bash")
    assert kinds.tool_family("claude", "Agent") == ("subagent", "Agent")
    assert kinds.tool_family("claude", "mcp__github__create_issue") == (
        "mcp",
        "mcp:github.create_issue",
    )
    assert kinds.tool_family("codex", "apply_patch") == ("edit", "apply_patch")
    assert kinds.tool_family("codex", "mcp__srv__lookup") == ("mcp", "mcp:srv.lookup")
    assert kinds.tool_family("codex", "never_heard_of_it") == ("other", "never_heard_of_it")
    families = {family for _, family in kinds.CLAUDE_TOOL_FAMILIES.rows}
    families |= {family for _, family in kinds.CODEX_TOOL_FAMILIES.rows}
    assert families <= set(kinds.TOOL_FAMILIES)
