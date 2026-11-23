---
type: is
id: is-01m83qnbdf3kswkegs0q63gtpm
title: "PR #745 A2: a commit pinned by its ID that is a pull request head's tip is served under that head and follows the next push"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T08:16:50.091Z
updated_at: 2026-11-23T08:20:23.543Z
started_at: 2026-11-23T08:20:23.541Z
---
Review A of #745. POST /api/source/pin {oid} resolves through resolve_pin, which names refs/pull/<n>/head when the commit is the tip of a kept ref or of any pull head the mirror holds (_pull_head_at in cache/resolve.py); switch_pin then attends that pull request, and follows_moves now makes the pin follow. Reproduced from a page on a branch: pin by oid of PR 7's head answers ref refs/pull/7/head, follows true, pull_request 7, and the next refresh of 7 moves the pin. The docs and changelog say a commit opened by its ID stays put. Decide: carry 'opened by ID' on the pin so _follow_ref and status.follows skip it unless the request named 'under', or keep it and say so in docs/reviewing-pull-requests.md with a test that pins it.
