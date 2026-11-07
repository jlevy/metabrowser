---
type: is
id: is-01m6thmx3973vnsw532ya5nk4h
title: Navigate PR stacks with Shift J and Shift K
kind: feature
status: in_progress
priority: 2
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:22:52.251Z
updated_at: 2026-11-07T08:24:16.890Z
started_at: 2026-11-07T08:24:16.884Z
---
Match GitHub stack traversal from the active PR: Shift-J moves one layer toward the base, Shift-K one layer toward the top. Use the existing shortcut and Help/keycap system with the shift glyph followed by J or K. Operate only in an active PR with known stack membership, preserve text entry and dialog keyboard handling, handle first/last members without unexpected navigation, and dispose listeners on leaving the view. Include focused session tests, Help hints, and manual browser verification alongside the compact stack menu.
