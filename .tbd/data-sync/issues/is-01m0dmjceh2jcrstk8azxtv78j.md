---
type: is
id: is-01m0dmjceh2jcrstk8azxtv78j
title: "Research: file patch formats — compatibility surface and gaps"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:29:36.847Z
updated_at: 2026-08-19T18:29:36.847Z
---
Background research (running via subagent) into docs/project/research/research-2026-08-19-file-patch-formats.md: survey POSIX/GNU unified+context, git's extended format (renames, modes, binary literal/delta, combined diffs, quoting, apply rules), GitHub PR .diff/.patch + files-endpoint truncation, JSON Patch RFCs, and agent edit formats (LSP TextEdit, apply_patch/V4A, aider SEARCH-REPLACE). Deliverable: ingest vs emit compatibility surfaces, parser gaps vs the survey, agent-workflow needs beyond classic patches. Feeds a 'Relation to existing formats' section in file-diff-format.md. Requirement from review: backward compatibility with existing patch formats as much as possible, full compatibility with our features, GitHub PRs, and agent workflows.
