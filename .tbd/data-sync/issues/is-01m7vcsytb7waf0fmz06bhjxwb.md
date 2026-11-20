---
type: is
id: is-01m7vcsytb7waf0fmz06bhjxwb
title: "Event log reports: test the refresh waits' late paths and measure source:refresh's threshold"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
created_at: 2026-11-20T02:33:11.243Z
updated_at: 2026-11-20T02:33:11.243Z
---
Follow-up to PR 629 (mb-9zp5), review A finding A10 (Low). The late paths of the githubPull:refresh wait (pull-page.js noteRefreshWait) and the source:refresh wait (source-freshness.js noteRefresh) are not exercised by any session or Chrome test; only githubPull:diffSummary is. Add scenarios: the pull page mount session driving a stale_refreshing record past the late threshold, then refreshed (ok) or failed (failed); the source freshness session driving a refreshing row past it and ending ok or warning. source:refresh reuses WAIT_LATE_MS (10 s), which was measured for the Diff summary (checkout._pull_job, median 3.0 s, longest 3.8 s); measure a mirror refresh's duration from the event log and set its own threshold if it differs, recorded beside the constant.
