---
type: is
id: is-01m7gxa649tsf69zpw1hz2chk4
title: "GitHub labels: a cached per-repository label catalog colors every chip on first paint"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T00:50:01.480Z
updated_at: 2026-11-16T00:50:48.242Z
started_at: 2026-11-16T00:50:48.240Z
---
The user's report and request (2026-11-15), verbatim:

"Also, create another bead because I noticed that when I view PRs, the tags are loading the color of the labels very slowly. We should load all the labels and cache all of their colors properly. This should be done in a way that's quickly reusable, so we don't see missing colors ever"

Context: mb-9qob (label colors) carries each label's color on the PR record, the core preview and the catalog row. A record cached before that change has bare names, so its chips are neutral until the record's next refresh, and a chip drawn before its record arrives has no color yet.

Done when:
- Each repository's whole label set (name, color, description) is fetched once, through REST `repos/{owner}/{repo}/labels` (paged) or GraphQL `repository.labels`, and cached per repository in the existing GitHub cache store. It is persisted across restarts, refreshed on the plugin's existing freshness rules, and on a label name it does not know.
- Every label chip (PR page header, and anywhere else labels render) takes its color and description from that catalog by name whenever its own record lacks them, so a chip has its color on first paint whenever the catalog is cached. Old records need no refetch.
- The catalog is bounded, and reads and writes stay off the request path's critical section (AGENTS.md: bounded reads, bounded synchronous work).
- A `metab` route exposes the label catalog with a golden (AGENTS.md CLI parity).
- A Chrome check shows a chip from a bare-names record colored on first paint once the catalog is cached.
- The CHANGELOG and design-system Label Colors section say so.
