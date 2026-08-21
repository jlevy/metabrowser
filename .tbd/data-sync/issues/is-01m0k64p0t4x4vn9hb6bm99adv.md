---
type: is
id: is-01m0k64p0t4x4vn9hb6bm99adv
title: "check_file_type_colors: distinctness, and agreement with upstream"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
labels: []
dependencies: []
parent_id: is-01m0k63zme8wetezbbq59ys3k8
created_at: 2026-08-21T22:12:54.425Z
updated_at: 2026-08-21T22:28:13.582Z
---
The check that keeps the source honest, run by make lint beside public_hygiene and check_supply_chain.

Two rules:

Distinctness. No two families are within a stated perceptual distance of each other. The number is a claim about what a reader can tell apart in a bar segment a few pixels tall, so it is measured against real rendered segments and recorded beside the constant, as this repository requires of every bound.

Upstream agreement. For every family carrying a `linguist` name, the recorded `source` hex matches that language's color in a linguist clone. Skipped when no clone is present, so the check never needs the network; the failure message carries the clone command, and the clone belongs in attic/linguist.

Both rules need their own tests: a family too close to another, and a `source` that disagrees with a fixture, must each fail with the family named. A check nobody has seen fail is a check nobody should trust.

## Notes

Correction to the earlier framing: colours are declared as an oklch hue only, so this check is about hue separation and gamut, not about matching hex values.

Three rules, run by make lint beside public_hygiene and check_supply_chain:

Distinctness. No two families are within the stated floor of each other. The floor is a claim about telling two segments apart in a bar a few pixels tall, so it is measured against real rendered output and recorded beside the constant.

Upstream correspondence. Every family carrying a `linguist` name either declares that language's converted hue or records why it deviates. Deviations are expected — Python and TypeScript convert to 246.5 and 253.3 degrees, and one of them has to move — but an unexplained one is drift. Skipped when no linguist clone is present, so the check never needs the network; the failure message carries the clone command.

Gamut. Every colour the rule derives, on both themes, sits inside sRGB.

All three need tests that fail: two families too close, an unexplained deviation, and a colour out of gamut, each naming the family. A check nobody has seen fail is a check nobody should trust.
