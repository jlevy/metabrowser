---
type: is
id: is-01m0ndq4en94cfqm99tg6m0fyt
title: Declared deviation for swift/svelte, the one pair the derivation cannot separate
kind: task
status: open
priority: 3
version: 4
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:03:47.925Z
updated_at: 2026-08-22T21:14:56.850Z
---
Reported in QA: Python and TypeScript look like the same blue.

Measured. Python is linguist #3572a5 -> hue 246.50; TypeScript is #3178c6 -> hue 253.30. They are 6.80 degrees apart and share the theme's lightness and chroma, so light renders #0042bf vs #033dda. Distinguishable, but only just, and only if the two bars are adjacent.

TypeScript is in worse company than Python. Its nearest neighbour is xml at 1.86 degrees (#033dda vs #013ed9 -- the same colour), then powershell at 4.84. Seven families sit inside 243-264 degrees.

Decision from the review: move TypeScript purple-ward and stop taking GitHub's hue for it. That needs a declared-deviation concept, because check_file_type_colors.py currently requires a hue within 0.02 degrees of the linguist colour whenever linguist is set. Proposal: keep linguist and linguist_color for provenance, add a reason field recording why we left GitHub, and hold a deviated hue to the same 5 degree floor a house hue gets.

The constraint to settle first. Only three arcs on the whole circle clear 5 degrees on both sides: 308.37-309.22, 228.85-228.90, and 238.90-238.94. Only the first is purple. Putting TypeScript at 308.80 clears python by 62 degrees but lands 5.43 from css and 5.42 from julia, rendering #601fad against #5721b9 and #6a1da1 -- which trades one near-collision for two. A gentler move (268 or 276) reads as purple but sits about 4 degrees from lua or php, under the floor.

So this bead is blocked on the parent problem in its sibling: at one fixed lightness and chroma the circle has no room left. Worth deciding that first.

UPDATE after the palette measurement (mb-0ov6). Python/TypeScript was never the worst pair perceptually: at fixed tone they are dE 0.0275, already above the 0.02 mark, while html/svelte sat at 0.0020. Deriving from GitHub's full colour takes the pair to 0.0316 on its own.

So the deviation mechanism is probably NOT needed for TypeScript. Where it is still needed is swift/svelte, which stays at dE 0.0073 in the dark theme because #f05138 and #ff3e00 are near-identical upstream in all three dimensions.

Decide after mb-0ov6 lands and the new palette has been looked at in a browser: if TypeScript still reads as Python's blue, deviate it then, with the mechanism this bead describes.

## Notes

DECIDED AFTER mb-0ov6 LANDED AND WAS LOOKED AT.

TypeScript needs no deviation. The pair that started this bead now renders python #0385d6 against typescript #2586e9 in light and #5daef3 against #6db0ff in dark, at delta-E 0.0316 and 0.0240. Side by side in a browser they are two blues. The prediction recorded in the update above held: the derivation alone was enough, and moving TypeScript to a house hue would have cost a familiar colour to fix something that is no longer broken.

So the purple move is dropped. What remains is the mechanism, and it is still wanted -- for one pair rather than for TypeScript.

swift/svelte in the DARK theme is the one real collision left: #ff907b against #ff9279, delta-E 0.0073. On screen they are the same colour. Light is fine at 0.0191 (#ec4c33 against #f34519). #f05138 and #ff3e00 are near-identical upstream in hue, lightness and chroma together, so no derivation from GitHub's colour separates them -- which is exactly the case a declared deviation exists for.

Scope this bead now covers: add the declared-deviation concept (keep linguist and linguist_color for provenance, add a reason field recording why we left GitHub) and apply it to ONE of swift or svelte, in the dark theme's terms. check_file_type_colors.py already measures in delta-E and already holds house-placed families to a floor in both themes, so a deviated family should simply be held to that same floor rather than to the hue rules -- most of the mechanism this bead asked for is now in place.

Note the arcs recorded above (308.37-309.22 and the two near 228 and 238) were computed at the flat tone and against hue distance. --suggest still returns 308.80, but the constraint should be recomputed in delta-E before anything is placed, because the circle is no longer the only dimension in play.
