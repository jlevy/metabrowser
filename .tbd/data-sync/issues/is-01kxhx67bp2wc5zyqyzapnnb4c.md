---
type: is
id: is-01kxhx67bp2wc5zyqyzapnnb4c
title: Pin tested runtime dependency floors
kind: chore
status: closed
priority: 1
version: 3
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T03:30:07.862Z
updated_at: 2026-07-15T03:36:44.139Z
closed_at: 2026-07-15T03:36:44.138Z
close_reason: Pinned every direct runtime dependency to its frozen tested version floor, preserved exact kpress==0.2.2, enforced the complete reviewed requirement list, updated maintainer and release-plan documentation, passed make verify, and pushed green PR checks.
---
Declare an explicit tested minimum version for every direct MetaBrowser runtime dependency, preserve the exact KPress compatibility pin, enforce the reviewed set in package policy, regenerate the lock without changing resolved artifacts, and run the complete release gate.
