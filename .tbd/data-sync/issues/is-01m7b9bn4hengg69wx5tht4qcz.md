---
type: is
id: is-01m7b9bn4hengg69wx5tht4qcz
title: "File-type palette: TypeScript a saturated yellow, departing from GitHub (Python unchanged)"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T20:25:05.936Z
updated_at: 2026-11-13T21:21:15.005Z
closed_at: 2026-11-13T21:21:15.004Z
close_reason: "Merged in #404: TypeScript hue 92, lightness_rank 1.5, chroma_ratio 1.0 (registry schema 5): light #cda600, dark #fecf00; Python unchanged; TS-Python dE 0.33. Follow-up: mb-uem0 (fdu reads schema 5)."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "the color for typescript and python are too close. let's deliberaely depart from github conventions and make typescript a color more like a yellow a bit like typescript but more yellow and saturated, keeping python same color."

Today TypeScript takes linguist #3178c6 (OKLCH hue 253.3) and Python #3572a5 (hue 246.5), 6.8 degrees apart, both blue. color_oklch.py states "no adjustment of GitHub's hues"; this is a deliberate, documented exception. JavaScript is yellow (hue 102.1), so the new TypeScript yellow must stay distinct from it and from every other family near that hue, in both themes.

Done when: TypeScript renders a saturated yellow in both themes, Python is unchanged, the nearest pairs are measured (Oklab delta-E) and stay distinguishable, the exception and its reason are recorded beside the family and in the palette docs, and a test pins it.

## Notes

2026-11-13: PR #404 (claude/ui-typescript-yellow, 3a1ca08a). TypeScript hue 92.0, lightness_rank 1.5, new chroma_ratio 1.0 field with deviation: light #cda600, dark #fecf00. TS-Python dE 0.032 -> 0.330; TS-JS 0.066 / 0.073. Alternates: h88 #d2a400/#ffcd44; h96 #cdae00/#fdd700. Review A running.
