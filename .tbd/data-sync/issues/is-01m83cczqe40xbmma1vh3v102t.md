---
type: is
id: is-01m83cczqe40xbmma1vh3v102t
title: "PR #722 A2: the heaviest-first test does not pin the order, and edge cases are untested"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836qya23kghgk2m3t9em8nc
created_at: 2026-11-23T05:00:01.637Z
updated_at: 2026-11-23T05:00:10.314Z
closed_at: 2026-11-23T05:00:10.187Z
close_reason: "fixed: in `feabdb162`: the deep branch is renamed `zdeep` so path order would pick wrong, and new tests cover ignored against unignored weight, bytes against files, and an exact tie broken by path (with reversed insertion); a mutation run failed every one of 10 mutations"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/722, finding A2 (Medium): the heaviest-first test does not pin the order, and edge cases are untested.
