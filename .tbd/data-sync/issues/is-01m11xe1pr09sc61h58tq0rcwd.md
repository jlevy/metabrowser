---
type: is
id: is-01m11xe1pr09sc61h58tq0rcwd
title: Split repository-library Phases 4-8 into their own plan once Phase 2 lands
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T15:29:20.599Z
updated_at: 2026-08-28T02:28:26.146Z
closed_at: 2026-08-28T02:28:26.145Z
close_reason: "Done in f46bc26, earlier than its Phase 2 trigger: the stated priority order schedules provider work independently of the cache, which is the condition the deferral was waiting on. Phases 4-7 are now plan-2026-08-27-github-provider-and-pull-requests.md with their beads retitled and respecified."
resolution: null
duplicate_of: null
---
PR #31 review S1 (deferred). The repository-library plan is ~1000 lines committing to the shape of Phases 4-8, whose inputs (measurements, real API responses) do not exist yet. Keeping the GitHub model in the same file means the 1A/1B contract is re-reviewed every time the provider model moves. Do this after Phase 2 lands, not on PR #31.
