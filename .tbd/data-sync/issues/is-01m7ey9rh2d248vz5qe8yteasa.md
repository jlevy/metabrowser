---
type: is
id: is-01m7ey9rh2d248vz5qe8yteasa
title: Agent-log detection hard-codes agent names apart from the manifest
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7wysc4mfcdyek4vgsexz8y9
created_at: 2026-11-15T06:28:47.265Z
updated_at: 2026-11-20T17:12:06.029Z
---
file_kinds._detect_jsonl hard-codes claude, gemini, and pi separately from the agent_log manifest and _BUILTIN_ADAPTERS, so Codex logs open as unknown-jsonl without charts. Derive detection from one list.
