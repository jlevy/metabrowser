---
type: is
id: is-01kzcr8h2zz8xvdvspzn0aq7vk
title: Add a keyboard-key (KBD) design-system component
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzcr7qzp4j0x9h694b8evywa
created_at: 2026-08-06T23:59:11.966Z
updated_at: 2026-08-07T00:10:01.939Z
closed_at: 2026-08-07T00:10:01.939Z
close_reason: "Implemented on feat/quick-file-palette (PR #22): chrome typography rule documented in styles.css with an enforced exception list, .kbd component added and applied, T bound alongside /, palette rows restyled to the file-header weight hierarchy. make verify green."
---
One reusable component for every keyboard key rendered anywhere in the app.

Contract:
- key names always ALL CAPS (ENTER, ESC, T, and the arrow glyphs)
- bold weight
- a thin border, one consistent width, radius, and inset — defined as semantic tokens, not per-component literals
- sans UI face, per the chrome typography rule
- light and dark theme variants defined alongside the tokens

Deliverables:
- tokens plus a .kbd class (or equivalent) in src/metabrowser/static/styles.css
- a documented section in docs/design-system.md so future keys use it instead of ad-hoc text
- applied to the Quick File palette hint row, which currently prints the keys as a plain monospaced string in search_palette.js
- applied to every other key shown in chrome; sweep for them

This is the design system for keyboard shortcuts — it should be the only way keys are rendered.
