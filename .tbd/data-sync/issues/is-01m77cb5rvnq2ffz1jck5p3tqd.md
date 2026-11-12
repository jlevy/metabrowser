---
type: is
id: is-01m77cb5rvnq2ffz1jck5p3tqd
title: A rejected choice resumes the first-run search it overtook, and Settings says what is running
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:00:18.202Z
updated_at: 2026-11-12T08:36:57.402Z
started_at: 2026-11-12T08:00:27.459Z
closed_at: 2026-11-12T08:36:57.400Z
close_reason: "Fixed in efe0cd42: a rejected choice resumes the search it overtook (RuntimeSelection.needsSearch, RuntimeOperations), and Settings shows what is running (RuntimeActivity), with RejectedChoiceDuringASearchTests for the review's sequence."
resolution: null
duplicate_of: null
---
Review C2 on #363 (mb-niod). With no saved setup, a Choose metab… made during the launch's discovery superseded it; a rejected choice then left no operation, the late search result was dropped, nothing rechecked, no guide was prepared, and Settings said it was still looking. Queued folders and the restore waited for Find Again. Fix: a rejected choice that overtook a search resumes it with a fresh ticket; Settings shows looking only while a search runs; superseded results still change nothing. Test initial discovery, rejected choice, late completion, the guide or adoption, and the release of queued folders.
