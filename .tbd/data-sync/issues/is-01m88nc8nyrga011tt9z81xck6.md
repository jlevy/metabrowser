---
type: is
id: is-01m88nc8nyrga011tt9z81xck6
title: "PR page: the stack chip is not right-aligned with the PR number"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:13:07.314Z
updated_at: 2026-11-25T06:13:58.960Z
started_at: 2026-11-25T06:13:58.959Z
---
Reported by the user after #815 merged: on the PR page, the stack chip on the Draft / Opened / updated row should end exactly under the PR number's right edge. Today the hidden Refresh slot at the row's right end keeps it about a Refresh-width in from that edge. Done when the chip's right edge matches the PR number's on every tab, with Refresh shown, waiting or absent, nothing moving as Refresh or the chip comes and goes, and the numbered controls' order unchanged, pinned by a Chrome check.
