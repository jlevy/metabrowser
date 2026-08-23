---
type: is
id: is-01m0r9bs70w5fzc2th0cjpbnzc
title: Enforce kebab-case JavaScript and TypeScript filenames
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-23T21:45:24.959Z
updated_at: 2026-08-23T21:45:31.507Z
---
First-party browser modules, plugin modules, DOM tests, and performance tooling contain snake_case filenames despite the project convention. Rename them to descriptive kebab-case names, update all references, document the reason, and add a lint/CI invariant so regressions fail immediately.
