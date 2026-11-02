---
type: is
id: is-01m6f1c18h9c7qpk1zswds5jh9
title: "PR #272 A1: compressed-patch 404 sentence is false for damage past the 8 MiB the route reads"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f1c0tknva4bd436kj524e0
hold: null
hold_until: null
created_at: 2026-11-02T21:06:45.648Z
updated_at: 2026-11-02T21:37:54.597Z
started_at: 2026-11-02T21:06:52.405Z
closed_at: 2026-11-02T21:37:54.595Z
close_reason: "fixed in 38447bdc: CHANGELOG.md and the addendum limit the 404 to the first 8 MiB of decoded content; test_damage_past_what_the_hooks_read_of_a_compressed_patch_is_not_reached holds both sides. Reply: https://github.com/jlevy/metabrowser/pull/272#issuecomment-6589082100"
resolution: null
duplicate_of: null
---
Low. CHANGELOG.md:975-976 and docs/project/reviews/review-2026-10-01-v012-changes-to-existing-behavior.md:68-69. Review: https://github.com/jlevy/metabrowser/pull/272#pullrequestreview-5743247737
