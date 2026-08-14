---
type: is
id: is-01kzz4cn498dcvvbkxwt573zmw
title: "Route A: Implement the NavigationTarget URL codec"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dsnst5gw52s28a00czx8
  - type: blocks
    target: is-01kzz4dt2aa6059jzk41yszq49
parent_id: is-01kzz03fmd769zawq6gf5d1hd7
created_at: 2026-08-14T03:17:29.864Z
updated_at: 2026-08-14T03:30:44.643Z
closed_at: 2026-08-14T03:30:44.642Z
close_reason: Implemented and verified the canonical /view/ NavigationTarget codec in f58fd28.
---
Create a focused fully strict browser module for the canonical NavigationTarget {path, query?, fragment?}. Parse only /view/ pathname routes, encode each path segment exactly once, keep query and fragment out of filesystem identity, normalize folder and root forms, and reject malformed or unsafe encoded inputs. Add pure tests for spaces, Unicode, percent characters, empty root, queries, fragments, encoded separators, double decoding, backslashes, and traversal. Do not read or migrate hash-as-file routes.
