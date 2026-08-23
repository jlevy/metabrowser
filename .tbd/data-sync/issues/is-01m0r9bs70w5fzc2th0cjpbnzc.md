---
type: is
id: is-01m0r9bs70w5fzc2th0cjpbnzc
title: Enforce kebab-case JavaScript and TypeScript filenames
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-23T21:45:24.959Z
updated_at: 2026-08-23T21:58:55.997Z
closed_at: 2026-08-23T21:58:55.996Z
close_reason: Migrated all 113 first-party JavaScript/TypeScript filename violations to kebab-case, added a tracked-and-untracked repository naming check, made Biome warnings fail lint-check, documented the convention, and passed make verify.
---
First-party browser modules, plugin modules, DOM tests, and performance tooling contain snake_case filenames despite the project convention. Rename them to descriptive kebab-case names, update all references, document the reason, and add a lint/CI invariant so regressions fail immediately.
