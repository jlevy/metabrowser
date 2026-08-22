---
type: is
id: is-01m0nvja2tjy1gyw0397p0wf1b
title: Hover a bar segment by styling it, not by dimming its neighbours
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T23:05:49.913Z
updated_at: 2026-08-22T23:05:49.913Z
---
Hovering a segment of a file-decomposition bar currently dims every OTHER segment. The hovered segment is identified by what happens to everything around it.

That is the wrong metaphor, and the rule it breaks is general: a hover is a statement about the thing under the pointer, so it belongs ON that thing. Changing fifty other segments to say something about one is both a bigger visual event than the interaction deserves and a claim about the others -- dimmed reads as "excluded" or "inactive", which is not what is being said.

REQUIRED BEHAVIOUR, for the hovered segment only:

- A subtle border: darker than the segment in light mode, lighter than it in dark mode.
- A slight shift in the segment's own brightness -- brighter or darker as suits the theme.
- Every other segment left exactly as it was.

AND IT IS A DESIGN-SYSTEM RULE, not a fix to one component. It should be written into docs/design-system.md as the model for hover on ANY bar or chart -- stacked bars, the treemap, distribution rows, anything added later. State the principle (hover styles the hovered thing, never its neighbours) alongside the specific treatment, so the next chart does not have to re-derive it.

Note the history: the current behaviour was deliberate, from "hover picks out one tally segment instead of fading the whole bar" (9bd46ba) -- which was itself a fix for fading the ENTIRE bar. So this is the third position, and the reason it is the right one should be recorded, or the next change will move it again.

Note also the palette interaction: segments now vary in lightness (mb-0ov6), and markdown deliberately sits outside the band, so a fixed brightness delta will land differently on a light segment than on a dark one. The treatment needs to be relative to the segment's own colour rather than an absolute overlay, and it has to be checked against both the lightest and the darkest families in both themes.

Tokens, not literals, for the border and the shift, so the treatment is reusable by the next chart that needs it.
