---
type: is
id: is-01m7n8aqx25qnxzb6047h1ew59
title: "Diff summaries: diagnose why the existing cache does not make them fast"
kind: task
status: closed
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T17:19:31.745Z
updated_at: 2026-11-17T17:20:35.125Z
started_at: 2026-11-17T17:19:38.370Z
closed_at: 2026-11-17T17:20:35.124Z
close_reason: Diagnosis recorded; fixes tracked in mb-z8ea, mb-uqt4, mb-30dz
resolution: null
duplicate_of: null
---
Before any new layer: what is persisted today for the Pulls rows' change lines and the PR page's Diff summary, when it is read vs bypassed, invalidated, or missed, and why the PR page and the nav still wait. Findings go in the shared notes and this bead.

## Notes

Diagnosis 2026-11-17 in the side-session notes (diff-summary-measurements.md). Pulls: summary is read from per-PR list files on disk (1-6 ms) and a warm reopen paints cached rows at once (0.8 s); the wait is an empty cache filled slowly by a serial lane mostly via GitHub's API (no store in checkout mode) - fixed by PR B. PR page: never reads the cached list; draws from a per-request git comparison that needs the full record first (3.8-4.3 s cold); nothing in the row until 1.7-1.9 s - PR A and PR C. Gap left: persisting the comparison manifest per (base, head).
