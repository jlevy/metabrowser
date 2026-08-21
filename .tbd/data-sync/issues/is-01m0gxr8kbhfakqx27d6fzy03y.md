---
type: is
id: is-01m0gxr8kbhfakqx27d6fzy03y
title: Migrate every color token to oklch
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-21T01:07:49.993Z
updated_at: 2026-08-21T01:33:30.396Z
closed_at: 2026-08-21T01:33:30.395Z
close_reason: "Landed: all 298 literals are oklch (272+26 conversions), faithful by round-trip and verified as an identical colour multiset; a test rejects new hex/hsl/rgb."
---
Color definitions are a mix of hex, hsl, and oklch, so the vocabulary cannot be reasoned about consistently: lightness and chroma are only comparable within one notation, which is how a chip ground ended up four to seven times the chroma of its neighbours without anyone noticing. Migrate every literal in styles.css (and any plugin stylesheet) to oklch, preserving rendered color, and state the convention in design-system.md so new tokens arrive in oklch. Consider a check that rejects new hex/hsl literals in token definitions once the migration lands.
