---
type: is
id: is-01m0vdp2yad9t1vnc9cfhw7fsb
title: "PR #74 review R1: implement semantic scope configuration"
kind: bug
status: in_progress
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:40.193Z
updated_at: 2026-08-25T03:05:51.201Z
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R1 Blocker. contract.py:36-61 declares hidden_allowlist and stay_on_filesystem, while providers/python.py:337-345 fingerprints them without applying them. Thread supported scope through discovery/watch, reject unsupported scope explicitly, define portable fingerprinting, and add provider harness coverage.
