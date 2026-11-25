---
type: is
id: is-01m88ccctmpetbjwn22w7s4cjx
title: "CI: a Chrome shard ran past its 7-minute limit when setup-node's tool-cache copy took 94 s"
kind: bug
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/823
    at: 2026-11-25T04:19:04.192Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-25T03:35:54.450Z
updated_at: 2026-11-25T04:19:04.200Z
started_at: 2026-11-25T03:45:05.372Z
---
main run 45537641286 (head de144e2fa, the #805 merge) was cancelled: chrome (3.13, 4/4) hit timeout-minutes 7 at 03:14:01 with 18 of its 19 tests done, and ci-ok failed. Every other job passed. The time went to actions/setup-node: 'Adding to the cache ...' (copying the downloaded Node 24.18.0 into /opt/hostedtoolcache) took 94 s, 03:07:25 to 03:08:59, where it normally takes about a second; the npm cache restore right after ran at 235 MB/s. Tests then started at 03:10:03 instead of about 03:08:30. The job's limit is about 1.5 times its measured 90th percentile and leaves no room for a setup step this slow. Fix: measure setup-node's step durations across recent runs (gh run data) to see whether 94 s is a tail or a one-off, then remove the per-job Node download and copy (for example a Node already in the runner's tool cache, if the supply-chain rules allow its pin) or give the setup steps their own measured budget so a slow copy fails fast and clearly.
