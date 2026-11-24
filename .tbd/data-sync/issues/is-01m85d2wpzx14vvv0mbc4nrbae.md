---
type: is
id: is-01m85d2wpzx14vvv0mbc4nrbae
title: "PR #768 A4: nothing tests that the acquisition path reads the home's volume and passes it to providers"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m85d2hj4x5fmcx1vdke1637w
hold: null
hold_until: null
created_at: 2026-11-23T23:50:28.319Z
updated_at: 2026-11-24T00:16:48.735Z
started_at: 2026-11-23T23:50:50.122Z
closed_at: 2026-11-24T00:16:48.734Z
close_reason: "fixed in d8acc98f: test_first_clone_free_space.py::test_a_first_clone_is_checked_against_the_volume_that_will_hold_the_cache (fails when the aggregator passes None)"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/cache/providers.py:335-343. Add a test that check_first_clone(source, home=...) reads the free space of the volume holding home (or its nearest existing parent) and hands it to providers, None when unreadable. PR 768, review https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981
