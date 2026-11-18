---
type: is
id: is-01m7nnxmbvvk8ctg8ckb0tzys7
title: Detect the app through LaunchServices and deliver by open -b
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxvge8wvp33zmj3nkpnvg
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:02.203Z
updated_at: 2026-11-17T21:17:17.151Z
---
Phase 1. ctypes LSCopyApplicationURLsForBundleIdentifier for the release bundle id; dev bundle only when chosen; test seam for goldens. Deliver with open -b <bundle> TARGET; map LaunchServices refusal to blocked. Browser path starts a detached server and opens the page once it answers.
