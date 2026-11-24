---
type: is
id: is-01m85cqzk2aa0xjsg7j6jzqrms
title: Rendered diff drops KPress's stylesheets when KPress's version has a local segment, so documents read in sans under the serif reading font
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/777
    at: 2026-11-24T01:07:43.218Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-23T23:44:30.781Z
updated_at: 2026-11-24T01:07:43.828Z
started_at: 2026-11-23T23:51:23.610Z
closed_at: 2026-11-24T01:07:43.826Z
close_reason: "Fixed in #777: the rendered diff keeps same-origin KPress stylesheets under /kpress-static/ by resolved origin and normalized path, whatever KPress's version holds (a PEP 440 local segment's + was refused), and warns of any it leaves out or that fails to load. Browserless test with release and local-version stamps; Chrome test of a stand-in pull request's Docs and Changes under a local-version address. Audit of the serif rule found no other violation."
resolution: null
duplicate_of: null
---
