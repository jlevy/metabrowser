---
type: is
id: is-01m7vpe4zwhef2vz5br01ykr3a
title: Check that every pin literal in a source-freshness golden appears in its recorded fixture
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T05:21:30.096Z
updated_at: 2026-11-20T05:21:30.096Z
---
PR 629 added a golden line with the then-current page pin; PR 632 re-recorded tests/fixtures/source-freshness-responses.json and re-blessed every pin. Neither branch had the other, the edits sat on adjacent lines, and git merged them cleanly, leaving main red (fixed in PR 638, mb-3hsq). A cheap guard: a test that every pin literal in tests/golden/cli-ui-source-freshness.tryscript.md appears in the fixture, so a stale line fails as a clear message on the PR that drifts.
