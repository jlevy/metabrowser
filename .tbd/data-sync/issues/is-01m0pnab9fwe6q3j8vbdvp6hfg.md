---
type: is
id: is-01m0pnab9fwe6q3j8vbdvp6hfg
title: Illustrative hex values in colour beads were written by hand, not sampled
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:51.982Z
updated_at: 2026-08-23T06:35:51.982Z
---
WHAT HAPPENED. Beads mb-0ov6 and mb-6g81 quoted rendered colours -- `#b81608` among them -- as evidence in a palette argument. The real renders are `#dd5230` and `#dd5232`. The numbers were reconstructed from the maths rather than read off a render.

WHAT WAS AND WAS NOT AFFECTED. The perceptual distances were computed correctly and the conclusions held; only the illustrative hexes were wrong. That is the trap: the argument was sound, so nothing downstream failed, and the wrong values would have been quoted indefinitely by anyone reading the bead as a record of what the palette looks like.

THE FIX. A hex quoted as 'what this renders as' must come from a render -- sample the canvas in a real browser, which is how the correct values were eventually obtained. Where a value is derived rather than observed, say so in the same sentence. `devtools/check_file_type_colors.py` already computes and prints these, so the cheap habit is to paste its output rather than transcribe.
