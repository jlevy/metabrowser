---
type: is
id: is-01m84tyharp73rhm840rgmbrk5
title: "PR #761 A6: under a flood of one-shot askers, refusals that never ask again hold the probe cap's first places"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-23T18:33:31.199Z
updated_at: 2026-11-23T18:33:46.566Z
---
Review A6 (Low) of PR #761: https://github.com/jlevy/metabrowser/pull/761#pullrequestreview-6026703603 (review A, head 3f6e1a0c6). It is not a regression: main granted fewer probes in every case below.

Under a flood of new keys that each ask once (a script reading many cached numbers once), the 64 remembered refusals (MAX_KEPT_PULLS) each hold their place in _may_probe (served_pull.py) for PROBE_TURN_S and never ask again, so the free probes go unused. In review A's attic/sim_probe.py (production _may_probe, a visible page asking every ATTENDED_PROBE_S, 600 s, 1 s probes), 20 one-shot keys a second leave the page 14 probes of its 120 asks and 17 granted in all.

The review's suggested fix, counting as ahead only refusals renewed within their asker's interval (`now - since <= kept_s / 2`), was tried on #761 and reverted. It is not simple:

- Taken literally, it breaks tests/test_github_pull_list_probe.py::test_a_list_probe_the_cap_refused_keeps_its_place_until_its_next_ask (review A5 of #737). A list asks every LIST_PROBE_S and its turn is twice that, so a list ask a timer's 20 ms late is past kept_s / 2 and loses its place to a pull request refused after it. Any asker renewed on schedule sits just past its interval.
- A margin keeps that test but trades the page's place against the flood's arrival rate. One-shot flood, jitter 0, page probes / probes granted (scratch copies of served_pull.py, never the tree):

  | Rule | 10/s | 20/s | 40/s |
  | --- | --- | --- | --- |
  | head of #761 | 33 / 36 | 14 / 17 | 1 / 4 |
  | ahead within kept_s / 2 | 60 / 63 | 53 / 157 | 1 / 956 |
  | ahead within 0.55 kept_s | 33 / 36 | 18 / 463 | 10 / 867 |
  | ahead within 0.75 kept_s | 33 / 36 | 14 / 17 | 10 / 433 |

  0.55 and 0.75 pass the list-lateness test and every test in tests/test_github_pull_freshness.py; 0.5 fails it. At 0.5 and 40/s the flood takes 956 probes and the page 1. The repeating floods (13, 65, 100 and 200 askers, jitter 0 to 2 s) were unchanged at 0.75. At 0.5 they moved a few probes either way: at 200 askers with jitter 0.05, 0.5 and 2 s, 5, 2 and 3 askers were never probed, against the head's 6, 7 and 2. 0.55 was not run against them. most_kept stayed at 64 throughout.
- Mechanism (inferred from the model): refusals enter in waves of MAX_KEPT_PULLS / rate seconds and lapse together PROBE_TURN_S later. A refusal stops counting as ahead (1 - fraction) * kept_s before it lapses; only when that window is longer than the wave do enough stop counting for a newcomer to be admitted, and then the newcomers, not the page, take most of the free places. So the gain depends on the flood's rate, and a margin wide enough for timer lateness misses some rates.

A fix needs a rule that does not depend on the flood's rate, for example forgetting a one-shot refusal sooner than a renewed one, or admitting a newcomer only behind askers that renewed. Done when the 20/s one-shot flood leaves the page about its share without losing the list-lateness test, the repeating askers' fairness, or the MAX_KEPT_PULLS bound, measured with sim_probe.py.
