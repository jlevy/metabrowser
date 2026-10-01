---
type: is
id: is-01m3tcz4v3nwkwh8peed9s8q00
title: Local folders whose names look like URLs (file:notes, a::b, me@host:dir, https:x) are refused instead of served
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T00:13:59.522Z
updated_at: 2026-10-01T00:14:02.533Z
---
Landing-risk review 2026-09-30: cli/main.py:278-296 classifies ROOT as a source string before treating it as a path, so an existing local folder named file:notes, a::b, me@host:dir or https:x is served on main but refused on the stack tip (verified); ./name works. Regression for standard features. Fix: an argument naming an existing local path is served as that path (classify only when it does not exist, or when it has an explicit scheme://); keep URL-shaped strings that are not existing paths classified as today. Acceptance: tryscript golden with such folder names served, and the existing URL goldens unchanged.
