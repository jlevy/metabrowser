---
type: is
id: is-01m0prnm7dpcrkdmr9b8bh30t7
title: "PR #72 review R10: emptyHeight cannot measure a stretch-sized region"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:27.309Z
updated_at: 2026-08-23T08:07:38.932Z
closed_at: 2026-08-23T08:07:38.931Z
close_reason: "Rebutted, not fixed. The finding assumed a container-sized region's shipped height is unmeasurable this way; in fact the in-flow stand-in is stretched exactly as the real element is, so #preview-pane reporting 0 missing is correct -- the pane fills its frame from first paint and only its contents are a placeholder. The proposed fix (measure out of flow) would have introduced a bug, reporting the whole 900px pane as missing. What was real was the missing explanation: 02c3105 adds a comment at heightOfStandIn saying why in-flow is deliberate and warning against the out-of-flow 'fix', and the README's region_heights row says the same."
---
probe.js:118-126 inserts a shallow clone as a sibling. .preview-pane (styles.css:2008) is flex:1 in a flex row, so the clone is flex:1 too and align-items:stretch gives it the full container height regardless of content — shipped_h ~= h, contributing a structural 0 to frame_missing_px. Fix: measure the stand-in out of flow at the element's own width, or exclude stretch-sized regions and say so.
