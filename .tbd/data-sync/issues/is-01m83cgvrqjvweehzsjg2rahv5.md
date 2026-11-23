---
type: is
id: is-01m83cgvrqjvweehzsjg2rahv5
title: "PR #724 A5: the map's region does not keep its box"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836s55277yzehg502zen0ra
created_at: 2026-11-23T05:02:08.662Z
updated_at: 2026-11-23T05:02:11.317Z
closed_at: 2026-11-23T05:02:11.314Z
close_reason: "fixed: in `1c4d0d59b`: the breakdown hands each answer to the map before its first paint settles (`onSnapshot`), so the box is decided from the section's first paint; a failure of the map's own request keeps the box and says the treemap is unavailable"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/724, finding A5 (Medium): the map's region does not keep its box.
