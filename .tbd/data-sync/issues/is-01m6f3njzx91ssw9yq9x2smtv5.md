---
type: is
id: is-01m6f3njzx91ssw9yq9x2smtv5
title: Merge design and performance branches and open this branch's PR
kind: task
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6f3nkg482640stjteqx3fvw
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:55.867Z
updated_at: 2026-11-03T04:19:50.662Z
started_at: 2026-11-02T23:39:11.698Z
closed_at: 2026-11-03T04:19:50.661Z
close_reason: The design and performance branches are PRs 280 and 284, with the overlay as PR 283 on top, merged forward and linked in stack 278 as 272-277, 280, 284, 283.
resolution: null
duplicate_of: null
---
Forward-merge the design and performance branches into claude/v012-pr-review-workflows, open its PR, link it to stack 278 as a new layer with gh stack link, and run the required reviews on it. Notify the Pulls tab session, which merges forward from this branch.
