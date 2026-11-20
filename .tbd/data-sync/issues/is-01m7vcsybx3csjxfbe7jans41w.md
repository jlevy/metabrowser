---
type: is
id: is-01m7vcsybx3csjxfbe7jans41w
title: "Event log reports: requests in flight before the reporter installs, and Resource Timing names without a method"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
parent_id: is-01m7wysap12x9d1xp4zz3m4sds
created_at: 2026-11-20T02:33:10.780Z
updated_at: 2026-11-20T17:11:44.093Z
---
Follow-up to PR 629 (mb-9zp5), review A finding A7 (Low, partly inferred). static/event-reports.js installs as an on-demand bundle after the first usable tree. A request sent before it installs carries no x-metabrowser-client header and is not timed while pending; if it is still pending when the reporter reads Resource Timing (once, at install), it is not seen at all, and a slow answer after install is missed. Resource Timing entries name only the URL, so the reports of earlier requests say no method (fetch /api/... rather than fetch GET /api/...). Options: observe resource entries with a PerformanceObserver (buffered) instead of one read, so requests that end after install are seen; record what the shell can of the method, or say plainly in the record that the method is unknown. Measure the cost on the startup path before moving anything eager (AGENTS.md: asset loading tiers).
