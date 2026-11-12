---
type: is
id: is-01m77cb5rvnq2ffz1jck5p3tqd
title: A rejected choice resumes the first-run search it overtook, and Settings says what is running
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:00:18.202Z
updated_at: 2026-11-12T08:00:27.462Z
started_at: 2026-11-12T08:00:27.459Z
---
Review C2 on #363 (mb-niod). With no saved setup, a Choose metab… made during the launch's discovery superseded it; a rejected choice then left no operation, the late search result was dropped, nothing rechecked, no guide was prepared, and Settings said it was still looking. Queued folders and the restore waited for Find Again. Fix: a rejected choice that overtook a search resumes it with a fresh ticket; Settings shows looking only while a search runs; superseded results still change nothing. Test initial discovery, rejected choice, late completion, the guide or adoption, and the release of queued folders.
