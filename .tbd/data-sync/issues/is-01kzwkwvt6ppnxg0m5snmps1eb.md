---
type: is
id: is-01kzwkwvt6ppnxg0m5snmps1eb
title: Make rendered Markdown mounts instance-safe
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwkxd4y4n9nmrjzv08etrpw
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:46.340Z
updated_at: 2026-08-13T06:16:35.817Z
closed_at: 2026-08-13T06:16:35.817Z
close_reason: Implemented and validated on codex/folder-overview-implementation; focused coverage and make verify pass.
---
Split markdown/rendered.js and source.js from the legacy index adapter. Implement mountRenderedMarkdown with abort and one instance-owned TOC disposer, return its handle through the ordinary view, expose mb.builtins.markdown.mountRendered, and remove all singleton TOC state. Tests pin ordinary Markdown parity, diagnostics/errors, independent concurrent mounts, late completion suppression, and idempotent disposal.
