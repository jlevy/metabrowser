---
type: is
id: is-01m7jec6ngeg29ame32pmhrpbe
title: "PR header: 'Fetched just now via GitHub CLI' sits in the metadata lines' rhythm; no empty labels row above it"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:07:27.779Z
updated_at: 2026-11-17T05:58:00.879Z
closed_at: 2026-11-16T20:03:34.844Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: "and on a PR view th text below, the \"Fetched just now...\" line has a lot o vertical space above it" then "it should just be part of the same metadata lines". Measured on /pull/474 (no labels): .github-pull-labels is empty but 20 px tall (top 165), header row-gap 6 px, then .github-pull-status 26 px (the Refresh button) at top 191; the opened line is 18 px at 141.
