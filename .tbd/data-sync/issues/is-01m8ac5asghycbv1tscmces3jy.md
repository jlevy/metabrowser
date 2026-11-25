---
type: is
id: is-01m8ac5asghycbv1tscmces3jy
title: Test sessions draw ages with the real builder, not the agesFrom copy
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T22:10:31.852Z
updated_at: 2026-11-25T22:10:31.852Z
---
Follow-up from review of #852 (mb-daxw). agesFrom in tests/dom/sdk-ref-fixture.js reimplements the age builder over a session's played formatAge, and already differs from it: it swaps the freshness class it last drew (a WeakMap) where metabrowser.retellAge swaps the age- namespace, and it does not escape tip in ageLabelHtml. 15 call sites in 11 sessions use it, Node sessions and Chrome .mjs pages that interpolate its source. Move them to the real builder: Node sessions through ageHelpers (the SDK in a sandbox with a fixed clock), Chrome pages through window.metabrowser's own ageLabel, ageLabelHtml and retellAge with {now} fixed, choosing now so each session's ages keep the lengths its layout checks need (B4 of review B on #506). Then delete agesFrom and update the transcripts whose labels change.
