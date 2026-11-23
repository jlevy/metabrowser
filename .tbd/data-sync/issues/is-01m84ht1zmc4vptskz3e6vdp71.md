---
type: is
id: is-01m84ht1zmc4vptskz3e6vdp71
title: "PR #745 C1: the Docs tab keeps no memory of Changes, so a reload drops its followed note and the earlier diff the reader chose"
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T15:53:47.246Z
updated_at: 2026-11-23T16:02:22.526Z
started_at: 2026-11-23T16:02:22.525Z
---
Review C (follow-up, round 3) of #745, posted after the merge, at a5edbb9d2. Since the merge 6bd0e5031 brought main's Docs tab (#751), Docs mounts through mountDiff, follows a moved head through showChanges, and paints the followed note, but rememberChanges (pull-page.js:7370-7380 at a5edbb9d2) writes the entry's pullChanges only when onPageRoute(pathname, number, "files"). A Docs entry never gets it, so entryMemory and restoreChosen find nothing there. Main's own ownsChanges (:8346-8348) already takes files or docs.

Probe (attic, built on tests/dom/github-pull-changes-follow-behavior.js with pathname and tab from the environment): on files, pullChanges is written, the note survives the reload a followed pin makes, and an earlier diff the reader chose survives a reload with the newer offered. On docs, pullChanges stays null, the note after the reload is null, and after Show the earlier changes and a reload Docs shows the newer diff with no offer. The place survives on both (pane 1530).

On a repository URL every push reloads the page, so a reader on Docs loses the head-moved note at once, and the earlier diff they chose at the next push: review A's A5 and the note across a reload, on the second drawing of the comparison.

Fix: write and read the memory on both diff tabs (onPageRoute files or docs, or through diffTab), add a Docs pass to github-pull-changes-follow-behavior.js (reload says the note; a chosen earlier diff stays through a reload with the newer offered), and say in reviewing-pull-requests.md "Staying Current" and arch-github-pull-requests.md that Docs follows as Changes does, and that leaving both diff tabs ends the choice (C4).

## Notes

Review: https://github.com/jlevy/metabrowser/pull/745#pullrequestreview-6024808335
