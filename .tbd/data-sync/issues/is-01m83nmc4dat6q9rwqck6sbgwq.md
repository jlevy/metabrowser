---
type: is
id: is-01m83nmc4dat6q9rwqck6sbgwq
title: "Diff: Markdown files past a bound lose the Rendered | Source chooser"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T07:41:20.900Z
updated_at: 2026-11-23T10:18:16.995Z
started_at: 2026-11-23T07:44:30.012Z
closed_at: 2026-11-23T10:18:16.995Z
close_reason: Merged in https://github.com/jlevy/metabrowser/pull/749
resolution: null
duplicate_of: null
---
Seen on the installed desktop build, reviewing PR #1216 of the user's trading repository: on the Changes tab some changed Markdown files (for example docs/project/research/research-2026-11-19-agent-assisted-trading.md) show only Source with no Rendered | Source chooser, while others in the same PR (research-2026-11-19-algo-platforms-and-trading-stacks.md) have it. Lead: renderedFormat() in builtin_plugins/diff/diff-markdown.js admits only availability ready or deferred, so a change the server marks too_large (or timed_out etc.) gets no chooser. The user considers any such cutoff a misfeature: a renderable document should always offer Rendered, loading its sides on demand within measured bounds. Done: reproduce, name the mechanism, fix so every renderable file offers the chooser, golden plus session evidence.
