---
type: is
id: is-01kzwkxd4y4n9nmrjzv08etrpw
title: Contribute README to Folder Overview
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - frontend
dependencies:
  - type: blocks
    target: is-01kzwkyd569xvj3ak0edyfv8pm
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:51:04.093Z
updated_at: 2026-08-13T06:16:35.828Z
closed_at: 2026-08-13T06:16:35.828Z
close_reason: Implemented and validated on codex/folder-overview-implementation; focused coverage and make verify pass.
---
Implement folder/readme_panel.js and register folder.readme as the conditional content/document printable contribution. Resolve only from readme_path, key by path, and mount the exact ordinary Markdown primitive with the composer signal. Tests cover README presence/absence/add/remove, same-key non-remount, replacement disposal, no extra heading/frame, KPress/TOC parity, direct Markdown isolation, and dynamic Overview print eligibility.
