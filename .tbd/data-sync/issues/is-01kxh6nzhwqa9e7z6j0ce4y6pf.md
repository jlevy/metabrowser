---
type: is
id: is-01kxh6nzhwqa9e7z6j0ce4y6pf
title: "PR #1 review R3: retry failed KPress assets"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
parent_id: is-01kxh6nz7zzeerc5xgd3enrev2
created_at: 2026-07-14T20:56:46.908Z
updated_at: 2026-07-17T21:16:44.581Z
closed_at: 2026-07-14T21:14:03.893Z
close_reason: Fixed in 8c5d6b2 with retryable shared loads, bounded cached-stylesheet detection, regression coverage, and a passing 618-test verify gate.
---
Cursor review thread PRRT_kwDOTX174c6Q5J4N at src/metabrowser/static/plugin_sdk.js:320. Add a failing browser contract test showing failed stylesheet, script, and TOC-module loads are not marked complete, then keep in-flight deduplication while allowing later renders to retry.
