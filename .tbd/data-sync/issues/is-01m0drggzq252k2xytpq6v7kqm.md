---
type: is
id: is-01m0drggzq252k2xytpq6v7kqm
title: "Agent-edit adapter: SEARCH/REPLACE and V4A blocks into v1 documents"
kind: feature
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T19:38:30.262Z
updated_at: 2026-11-14T18:45:15.189Z
---
From the patch-formats research: agent edit formats (aider SEARCH/REPLACE, OpenAI V4A apply_patch, str_replace tools) anchor by content, not line numbers — unanimously. Add an adapter that resolves content-anchored edits against a base tree into File Diff Format documents: locate each search block (uniqueness gate — ambiguous anchors are a refusal, not a guess), synthesize hunks with real line numbers, emit an anchored document. This gives agent workflows the same validated model, render path, and apply oracle as every other source, with no format change. Round-trip: the produced document applied to the base must reproduce the agent's intended result.
