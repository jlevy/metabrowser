---
type: is
id: is-01m7zktgz6zp5s6ny6dkmxm5m7
title: Keep provider-specific agent behavior inside the Agents plugin
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-agent-operations-views.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/683
    at: 2026-11-21T19:01:26.451Z
labels: []
dependencies: []
parent_id: is-01m7wysc4mfcdyek4vgsexz8y9
created_at: 2026-11-21T17:52:47.588Z
updated_at: 2026-11-21T19:01:26.453Z
---
Finish moving Claude Code and Codex-specific behavior behind the built-in Agents manifest and provider modules. Keep the generic JSONL SDK and existing callers compatible. Document the runtime boundary and plugin diagnostics.

## Notes

The Agent Session Browser manifest owns provider recognition and chart implementation. Existing SDK and import compatibility remain available. Plugin sources and required plugin IDs are shown through CLI and native Settings.
