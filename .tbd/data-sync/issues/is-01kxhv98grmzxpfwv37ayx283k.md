---
type: is
id: is-01kxhv98grmzxpfwv37ayx283k
title: "PR #2 review R1: support and enforce nvm and fnm Node pins"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kxhv6wpfmr1b7m1dssdrkn48
created_at: 2026-07-15T02:56:50.199Z
updated_at: 2026-07-15T03:02:05.940Z
closed_at: 2026-07-15T03:02:05.939Z
close_reason: Implemented and regression-tested manager-specific Node pins plus NUL-safe git check-ignore handling; full make verify passed.
---
PR #2 R1 (Medium): .node-version:1, docs/development.md:22, devtools/npm_policy.py:12. Add exact .nvmrc for nvm, retain .node-version for fnm, enforce both against NODE_VERSION, and document the manager-specific files.
