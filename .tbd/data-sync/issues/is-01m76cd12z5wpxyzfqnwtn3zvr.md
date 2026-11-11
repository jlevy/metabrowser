---
type: is
id: is-01m76cd12z5wpxyzfqnwtn3zvr
title: Swift app code meets the tbd coding guidelines
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T22:42:04.510Z
updated_at: 2026-11-11T22:42:06.418Z
---
No Swift guideline exists in tbd, so apply the language-neutral ones to apps/macos: general-coding-rules, general-comment-rules, error-handling-rules (no swallowed errors; preserve causes; handle only what the layer can), general-testing-rules and general-tdd-guidelines (decision logic in ShellCore with tests; app-target code thin), filesystem-rules (atomic writes, safe paths), release-engineering-rules and supply-chain-hardening for scripts, backward-compatibility-rules (no speculative layers). Record anything deliberately left, with its reason, in apps/macos/README.md.
