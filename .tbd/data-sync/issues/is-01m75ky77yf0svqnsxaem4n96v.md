---
type: is
id: is-01m75ky77yf0svqnsxaem4n96v
title: "PR #348 G3: whitespace between code tokens is not charged"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T15:34:33.469Z
updated_at: 2026-11-11T15:48:24.609Z
closed_at: 2026-11-11T15:48:24.608Z
close_reason: "Fixed in f959206b: code is charged as text, no tokens; spaced Ruby/C/JS render 8.6-8.9 ms at the cap. Same test."
resolution: null
duplicate_of: null
---
Review G3 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5860828559): Ruby 'a ' costs about twice 'a,' at the same estimate.
