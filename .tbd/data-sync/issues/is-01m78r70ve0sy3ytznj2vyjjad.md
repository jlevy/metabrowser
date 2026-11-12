---
type: is
id: is-01m78r70ve0sy3ytznj2vyjjad
title: Transition recorder can place the input's own frame before the input
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T20:46:59.437Z
updated_at: 2026-11-12T20:46:59.437Z
---
Found while fixing mb-054f (jlevy/metabrowser#381). The recorder places frames in a transition's window by rAF timestamp, but Chrome can timestamp a frame up to a fraction of a millisecond before the input even when it draws that input in that frame. A probe page reproduced it in 1 of 8 runs: the ready frame began 0.2 ms before the press, and a valid transition read framesToReady 0 and could leave a blank frame out. Fixing it changes frame-window membership in accountFrames/regionMovement, which needs a scenario revision bump, so it is a decision for the performance campaign. exp-058's 462 transitions have no framesToReady 0; whether any blank frame was left out cannot be told from its samples. #381 documents the edge in explorations/performance-loop/README.md Limits.
