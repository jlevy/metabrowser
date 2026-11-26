---
type: is
id: is-01m8bmxkqx3ntea55p2vg2knzy
title: Profile and fix late rendered Markdown in Changes
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-26T10:02:50.490Z
updated_at: 2026-11-26T10:38:22.611Z
closed_at: 2026-11-26T10:38:22.602Z
close_reason: "Merged in #880; projection cost follows in mb-3dkn"
resolution: null
duplicate_of: null
---
A Markdown file's rendered view can arrive late in Changes; #878 capped the wait at RENDERED_WAIT_MS, which hides the cause. Measure where the time goes (projection slot queueing and 429 retries, the projection child's start, the projection itself, the git reads) on real pull requests, and fix the measured cause.
