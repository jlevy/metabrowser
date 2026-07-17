---
type: is
id: is-01kxhq8bm6fbstcagw3f99agrx
title: "PR #1 review A1: escape agent-log event kinds"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.309Z
updated_at: 2026-07-15T01:47:16.394Z
---
Review A1 (High). src/metabrowser/builtin_plugins/agent_log/index.js and logutil/parsing.py: prevent file-content DOM XSS from attacker-controlled event kind values; replace inline JS interpolation with safe delegated events.
