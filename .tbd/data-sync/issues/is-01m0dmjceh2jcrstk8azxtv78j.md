---
type: is
id: is-01m0dmjceh2jcrstk8azxtv78j
title: "Research: file patch formats — compatibility surface and gaps"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-19T18:29:36.847Z
updated_at: 2026-08-19T19:38:31.282Z
closed_at: 2026-08-19T19:38:31.281Z
close_reason: "Research doc delivered: docs/project/research/research-2026-08-19-file-patch-formats.md (627 lines, comparison matrix, highlighting appendix, honest UNVERIFIED markers on the cut-off POSIX/GNU tail). Four probe-found parser defects fixed in dbe4a7e during the research; remaining gaps beaded: mb-a1as (ingest completion), mb-96ho (emitter), mb-s8pq (anchoring), new agent-edit adapter bead, mb-fc8l (highlighting, informed by the appendix)."
---
Background research (running via subagent) into docs/project/research/research-2026-08-19-file-patch-formats.md: survey POSIX/GNU unified+context, git's extended format (renames, modes, binary literal/delta, combined diffs, quoting, apply rules), GitHub PR .diff/.patch + files-endpoint truncation, JSON Patch RFCs, and agent edit formats (LSP TextEdit, apply_patch/V4A, aider SEARCH-REPLACE). Deliverable: ingest vs emit compatibility surfaces, parser gaps vs the survey, agent-workflow needs beyond classic patches. Feeds a 'Relation to existing formats' section in file-diff-format.md. Requirement from review: backward compatibility with existing patch formats as much as possible, full compatibility with our features, GitHub PRs, and agent workflows.
