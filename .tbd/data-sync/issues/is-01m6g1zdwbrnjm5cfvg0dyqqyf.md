---
type: is
id: is-01m6g1zdwbrnjm5cfvg0dyqqyf
title: "PR #284 E4: a pull request's record refresh takes 3.7-4.7 s against a 1.5 s budget"
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m6g1yw7yj073zja4jqvz0g8b
created_at: 2026-11-03T06:36:35.594Z
updated_at: 2026-11-03T06:37:53.907Z
---
Low, from review E of https://github.com/jlevy/metabrowser/pull/284 (https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5747841588), deferred out of that PR.

What review E measured: `builtin_plugins/github/pulls.py:668` now gathers the record's five parts. `metab <pull URL> --no-serve` on a cached record, 3 adjacent pairs at load 2.9 to 6.7: head 5.55, 4.55, 5.29 s against the base layer's 7.84, 7.19, 6.70 s, where `metab --version` alone is 0.84-0.89 s. So the refresh itself is about 3.7-4.7 s: 1.2x to 1.7x faster than the base layer, and 2.5x to 3x over the 1.5 s budget in exp-040. It is Low because serve mode refreshes in the background and paints the cached record at about 0.3 s, so a reader of a cached pull request does not wait for it; a first open and the freshness of what is shown do.

Work: measure where the 3.7 s goes now. The study's split (exp-040, one `--no-serve` of an uncached pull request, 5.5-6.6 s) was Python start and record read 0.4-0.7 s, two `gh auth status` spawns 0.8-1.0 s, six sequential `gh api` spawns 3.0-4.0 s whose cost is the spawn and TLS handshake and not the payload, and the Git fetch with `merge-base` 0.9-1.4 s. PR #284 put the five parts in flight together; what is left is the one-request refresh, the second half of the study's fix 6 ("or one GraphQL query"), which needs design because `gh.py` names every page and reads every ETag, and one query changes how a rate-limit refusal is reported.

Waits on: the measurement above on a quiet machine (mb-jwfx), and nothing in PR #284.
