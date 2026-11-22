---
type: is
id: is-01m82hx4dgadx9h9b789deab17
title: "A visible mirror page on a branch sees a push within seconds: probe the served branch between fetches"
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-22T21:16:59.182Z
updated_at: 2026-11-22T21:16:59.182Z
---
Since #632 (mb-pq8y), a mirror's pin on a branch follows the branch when a refresh moves it. But a refresh runs only when the mirror is stale: the page polls status every 30 s and asks when the last fetch is older than FRESHNESS_WINDOW_S (60 s). So a push shows up to about 90 s later, the same delay the pull request page had before the probes (mb-sjgl).

Apply the cadence plan's model to a mirror: while a page of the mirror is visible, probe the served branch's tip every few seconds and start the fetch at once when it moved. A full fetch otherwise stays on its window.

- The probe must stay provider-agnostic in core: `git ls-remote origin refs/heads/<branch>` with protocol v2's ref-prefix, so the server sends one ref. The GitHub plugin may offer a conditional REST read of the ref (`git/ref/heads/<branch>` with an ETag; a 304 spends no rate limit) if it measures cheaper.
- Measure both before choosing: process time, bytes, and latency on a large repository.
- One probe in flight per mirror, however many tabs ask, outside the store turn; hidden pages probe nothing.
- A commit pin and a tag never probe.

Relates to mb-2uut (branches follow the repository, OS-581): this sets how soon a followed branch follows.
