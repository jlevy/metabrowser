"""Event kinds, tool families, and each provider's mapping tables.

Every event has exactly one kind. A provider's table is an ordered tuple of
:class:`Rule`; the first rule whose raw type, subtype, and content-block type all match
wins, and an event no rule matches is ``unknown``. A rule field is an ``fnmatch``
pattern: ``*`` matches anything, including an absent subtype or block (passed as the
empty string), and a trailing ``*`` matches a prefix. The tables are values in code; the
golden ``tests/golden/agents-mapping-*.txt`` pins them and the classification of every
raw type the research brief lists.

Tools are grouped by family. A tool name maps to a family through the provider's table;
an MCP tool maps to ``mcp`` and is labelled ``mcp:<server>.<tool>``.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Final, NamedTuple

KINDS: Final = (
    "prompt",
    "text",
    "thinking",
    "tool-call",
    "tool-result",
    "metering",
    "control",
    "context",
    "error",
    "unknown",
)

TOOL_FAMILIES: Final = (
    "shell",
    "read",
    "edit",
    "search",
    "web",
    "mcp",
    "subagent",
    "other",
)


class Rule(NamedTuple):
    """One row of a mapping table: patterns over (raw type, subtype, block) and a kind."""

    raw_type: str
    subtype: str
    block: str
    kind: str


def classify(
    rules: tuple[Rule, ...], raw_type: str, subtype: str | None = None, block: str | None = None
) -> str:
    """The kind of the first rule matching, or ``unknown``."""

    sub = subtype or ""
    blk = block or ""
    for rule in rules:
        if (
            fnmatchcase(raw_type, rule.raw_type)
            and fnmatchcase(sub, rule.subtype)
            and fnmatchcase(blk, rule.block)
        ):
            return rule.kind
    return "unknown"


def _rules(*rows: tuple[str, str, str, str]) -> tuple[Rule, ...]:
    return tuple(Rule(*row) for row in rows)


# Claude Code. A transcript record's `type` is the raw type. For `attachment` the
# subtype is the attachment's own type, for `system` the record's `subtype`. The block is
# a content block's type; the provider also names three synthetic blocks, for facts that
# are not content blocks: `usage` (an assistant record's token usage), `api_error` (an
# assistant error stub), and `permission_decision` (a user record's decision).
CLAUDE_RULES: Final = _rules(
    ("assistant", "*", "api_error", "error"),
    ("assistant", "*", "usage", "metering"),
    ("assistant", "*", "text", "text"),
    ("assistant", "*", "thinking", "thinking"),
    ("assistant", "*", "redacted_thinking", "thinking"),
    ("assistant", "*", "tool_use", "tool-call"),
    ("assistant", "*", "server_tool_use", "tool-call"),
    ("assistant", "*", "*_tool_result", "tool-result"),
    ("user", "*", "permission_decision", "control"),
    ("user", "*", "text", "prompt"),
    ("user", "*", "image", "prompt"),
    ("user", "*", "document", "prompt"),
    ("user", "*", "tool_result", "tool-result"),
    ("queue-operation", "*", "*", "prompt"),
    ("attachment", "hook_*", "*", "control"),
    ("attachment", "queued_command", "*", "prompt"),
    ("attachment", "*", "*", "context"),
    ("system", "api_error", "*", "error"),
    ("system", "stop_hook_summary", "*", "control"),
    ("system", "*", "*", "context"),
    ("permission-mode", "*", "*", "control"),
    ("cost-state", "*", "*", "metering"),
    ("api-request*", "*", "*", "metering"),
    ("custom-title", "*", "*", "context"),
    ("agent-name", "*", "*", "context"),
    ("last-prompt", "*", "*", "context"),
    ("mode", "*", "*", "context"),
    ("pr-link", "*", "*", "context"),
    ("relocated", "*", "*", "context"),
    ("tools-used", "*", "*", "context"),
    ("atis-latch", "*", "*", "context"),
    ("file-history-*", "*", "*", "context"),
    ("summary", "*", "*", "context"),
    ("progress", "*", "*", "context"),
)

# Codex, rollout lines and thread-history items. A rollout line's `type` is the raw type
# and its payload's `type` the subtype; `response_item` messages carry their role as the
# block, and `item_completed` carries the item's type. A `thread_items` row has raw type
# `thread_item` and its `item_type` as the subtype; a `thread_turns` error is
# `thread_turn` with subtype `error`.
CODEX_RULES: Final = _rules(
    ("session_meta", "*", "*", "context"),
    ("turn_context", "*", "*", "context"),
    ("world_state", "*", "*", "context"),
    ("compacted", "*", "*", "context"),
    ("inter_agent_communication_metadata", "*", "*", "context"),
    ("token_usage_record", "*", "*", "metering"),
    ("response_item", "message", "user", "prompt"),
    ("response_item", "message", "assistant", "text"),
    ("response_item", "message", "*", "context"),
    ("response_item", "reasoning", "*", "thinking"),
    ("response_item", "*_call", "*", "tool-call"),
    ("response_item", "*_call_output", "*", "tool-result"),
    ("response_item", "compaction*", "*", "context"),
    ("response_item", "ghost_snapshot", "*", "context"),
    ("event_msg", "user_message", "*", "prompt"),
    ("event_msg", "agent_message*", "*", "text"),
    ("event_msg", "agent_reasoning*", "*", "thinking"),
    ("event_msg", "token_count", "*", "metering"),
    ("event_msg", "task_started", "*", "context"),
    ("event_msg", "task_complete", "*", "context"),
    ("event_msg", "thread_settings_applied", "*", "context"),
    ("event_msg", "context_compacted", "*", "context"),
    ("event_msg", "thread_rolled_back", "*", "context"),
    ("event_msg", "turn_aborted", "*", "error"),
    ("event_msg", "error", "*", "error"),
    ("event_msg", "stream_error", "*", "error"),
    ("event_msg", "*_approval_request", "*", "control"),
    ("event_msg", "exec_command_begin", "*", "tool-call"),
    ("event_msg", "exec_command_end", "*", "tool-result"),
    ("event_msg", "mcp_tool_call_begin", "*", "tool-call"),
    ("event_msg", "mcp_tool_call_end", "*", "tool-result"),
    ("event_msg", "patch_apply_begin", "*", "tool-call"),
    ("event_msg", "patch_apply_end", "*", "tool-result"),
    ("event_msg", "item_completed", "userMessage", "prompt"),
    ("event_msg", "item_completed", "agentMessage", "text"),
    ("event_msg", "item_completed", "reasoning", "thinking"),
    ("event_msg", "item_completed", "contextCompaction", "context"),
    ("event_msg", "item_completed", "commandExecution", "tool-result"),
    ("event_msg", "item_completed", "fileChange", "tool-result"),
    ("event_msg", "item_completed", "mcpToolCall", "tool-result"),
    ("event_msg", "item_completed", "webSearch", "tool-result"),
    ("event_msg", "item_completed", "collabAgentToolCall", "tool-result"),
    ("thread_item", "userMessage", "*", "prompt"),
    ("thread_item", "agentMessage", "*", "text"),
    ("thread_item", "reasoning", "*", "thinking"),
    ("thread_item", "commandExecution", "*", "tool-call"),
    ("thread_item", "fileChange", "*", "tool-call"),
    ("thread_item", "mcpToolCall", "*", "tool-call"),
    ("thread_item", "dynamicToolCall", "*", "tool-call"),
    ("thread_item", "webSearch", "*", "tool-call"),
    ("thread_item", "collabAgentToolCall", "*", "tool-call"),
    ("thread_item", "imageView", "*", "tool-call"),
    ("thread_item", "imageGeneration", "*", "tool-call"),
    ("thread_item", "contextCompaction", "*", "context"),
    ("thread_item", "enteredReviewMode", "*", "context"),
    ("thread_item", "exitedReviewMode", "*", "context"),
    ("thread_item", "plan", "*", "text"),
    ("thread_item", "error", "*", "error"),
    ("thread_turn", "error", "*", "error"),
)

# Every raw type the research brief lists, as (raw type, subtype, block), for the golden
# that classifies them. Claude Code first, then Codex.
CLAUDE_BRIEF_TYPES: Final[tuple[tuple[str, str, str], ...]] = (
    ("assistant", "", "text"),
    ("assistant", "", "thinking"),
    ("assistant", "", "tool_use"),
    ("assistant", "", "usage"),
    ("assistant", "", "api_error"),
    ("user", "", "text"),
    ("user", "", "tool_result"),
    ("user", "", "permission_decision"),
    ("api-request", "", ""),
    ("api-request-shape", "", ""),
    ("api-request-blob", "", ""),
    ("queue-operation", "", ""),
    ("attachment", "hook_success", ""),
    ("attachment", "hook_non_blocking_error", ""),
    ("attachment", "task_status", ""),
    ("attachment", "queued_command", ""),
    ("attachment", "remote_session_change", ""),
    ("attachment", "diagnostics", ""),
    ("system", "api_error", ""),
    ("system", "compact_boundary", ""),
    ("system", "stop_hook_summary", ""),
    ("system", "turn_duration", ""),
    ("system", "init", ""),
    ("custom-title", "", ""),
    ("agent-name", "", ""),
    ("last-prompt", "", ""),
    ("mode", "", ""),
    ("permission-mode", "", ""),
    ("pr-link", "", ""),
    ("relocated", "", ""),
    ("tools-used", "", ""),
    ("cost-state", "", ""),
    ("atis-latch", "", ""),
    ("file-history-snapshot", "", ""),
    ("file-history-delta", "", ""),
    ("summary", "", ""),
    ("progress", "", ""),
)

CODEX_BRIEF_TYPES: Final[tuple[tuple[str, str, str], ...]] = (
    ("session_meta", "", ""),
    ("turn_context", "", ""),
    ("world_state", "", ""),
    ("compacted", "", ""),
    ("inter_agent_communication_metadata", "", ""),
    ("token_usage_record", "", ""),
    ("response_item", "message", "user"),
    ("response_item", "message", "assistant"),
    ("response_item", "reasoning", ""),
    ("response_item", "function_call", ""),
    ("response_item", "function_call_output", ""),
    ("response_item", "custom_tool_call", ""),
    ("response_item", "custom_tool_call_output", ""),
    ("response_item", "compaction", ""),
    ("event_msg", "user_message", ""),
    ("event_msg", "agent_message", ""),
    ("event_msg", "token_count", ""),
    ("event_msg", "task_started", ""),
    ("event_msg", "task_complete", ""),
    ("event_msg", "turn_aborted", ""),
    ("event_msg", "item_completed", "commandExecution"),
    ("event_msg", "item_completed", "fileChange"),
    ("event_msg", "item_completed", "mcpToolCall"),
    ("event_msg", "item_completed", "webSearch"),
    ("event_msg", "item_completed", "collabAgentToolCall"),
    ("event_msg", "item_completed", "contextCompaction"),
    ("thread_item", "userMessage", ""),
    ("thread_item", "agentMessage", ""),
    ("thread_item", "reasoning", ""),
    ("thread_item", "commandExecution", ""),
    ("thread_item", "fileChange", ""),
    ("thread_item", "mcpToolCall", ""),
    ("thread_item", "webSearch", ""),
    ("thread_item", "collabAgentToolCall", ""),
    ("thread_item", "contextCompaction", ""),
    ("thread_turn", "error", ""),
)


class _ToolTable(NamedTuple):
    """Ordered (pattern, family) rows; the first matching pattern wins."""

    rows: tuple[tuple[str, str], ...]


CLAUDE_TOOL_FAMILIES: Final = _ToolTable(
    (
        ("Bash", "shell"),
        ("BashOutput", "shell"),
        ("KillShell", "shell"),
        ("KillBash", "shell"),
        ("Monitor", "shell"),
        ("Read", "read"),
        ("NotebookRead", "read"),
        ("Edit", "edit"),
        ("MultiEdit", "edit"),
        ("Write", "edit"),
        ("NotebookEdit", "edit"),
        ("Grep", "search"),
        ("Glob", "search"),
        ("ToolSearch", "search"),
        ("WebFetch", "web"),
        ("WebSearch", "web"),
        ("Task", "subagent"),
        ("Agent", "subagent"),
        ("Workflow", "subagent"),
    )
)

CODEX_TOOL_FAMILIES: Final = _ToolTable(
    (
        ("shell", "shell"),
        ("exec_command", "shell"),
        ("local_shell", "shell"),
        ("container.exec", "shell"),
        ("write_stdin", "shell"),
        ("unified_exec", "shell"),
        ("commandExecution", "shell"),
        ("read_file", "read"),
        ("view_image", "read"),
        ("imageView", "read"),
        ("apply_patch", "edit"),
        ("fileChange", "edit"),
        ("grep_files", "search"),
        ("list_dir", "search"),
        ("tool_search", "search"),
        ("web_search", "web"),
        ("web.run", "web"),
        ("webSearch", "web"),
        ("spawn_agent", "subagent"),
        ("send_input", "subagent"),
        ("wait_agent", "subagent"),
        ("close_agent", "subagent"),
        ("resume_agent", "subagent"),
        ("collabAgentToolCall", "subagent"),
    )
)

_TOOL_TABLES: Final = {"claude": CLAUDE_TOOL_FAMILIES, "codex": CODEX_TOOL_FAMILIES}


def mcp_label(server: str, tool: str) -> str:
    return f"mcp:{server}.{tool}"


def tool_family(agent: str, name: str) -> tuple[str, str]:
    """The (family, label) of a tool name: ``mcp__server__tool`` becomes an MCP label."""

    if name.startswith("mcp__"):
        server, _, tool = name[len("mcp__") :].partition("__")
        return "mcp", mcp_label(server, tool or "?")
    for pattern, family in _TOOL_TABLES[agent].rows:
        if pattern == name:
            return family, name
    return "other", name


def render_table(rules: tuple[Rule, ...]) -> str:
    """The table as text, one rule per line, for the mapping golden."""

    width = [max(len(rule[i]) for rule in rules) for i in range(3)]
    return "".join(
        f"{rule.raw_type:<{width[0]}}  {rule.subtype:<{width[1]}}  {rule.block:<{width[2]}}"
        f"  -> {rule.kind}\n"
        for rule in rules
    )


def render_classification(rules: tuple[Rule, ...], types: tuple[tuple[str, str, str], ...]) -> str:
    """Each brief type with the kind the table gives it, for the mapping golden."""

    return "".join(
        f"{raw or '-'} / {sub or '-'} / {blk or '-'} -> {classify(rules, raw, sub, blk)}\n"
        for raw, sub, blk in types
    )


def render_tool_table(table: _ToolTable) -> str:
    return "".join(f"{name} -> {family}\n" for name, family in table.rows)
