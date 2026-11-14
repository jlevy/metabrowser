---
type: is
id: is-01m7b7q8ncbzx38srzymq9xp0e
title: "macOS title-bar mark: balance the light-mode tints' saturation (more gold, less purple)"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T19:56:29.227Z
updated_at: 2026-11-13T20:17:08.199Z
closed_at: 2026-11-13T20:17:08.197Z
close_reason: "Merged in #403: light title-bar M #9A7B00 (full chroma), B #9C62D5 (0.65), both about 4:1 on white; the B carries 1.4x the M's chroma, down from 2.5x."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "on light mode, the logo in the upper right corner should have a little more saturation on the yellow and a little less on the purple, can we check color saturation levels".

Measured: the light M #967B2C had OKLCH chroma 0.102 (0.84 of the sRGB maximum at its lightness); the light B #AD4AFF had 0.255 (all of it), 2.5 times the M. The user chose option B: M #9A7B00 (all of its chroma), B #9C62D5 (0.65), both about 4:1 on white, hues kept; the B now carries 1.4 times the M.
