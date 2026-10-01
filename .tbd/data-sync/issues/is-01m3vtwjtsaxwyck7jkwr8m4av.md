---
type: is
id: is-01m3vtwjtsaxwyck7jkwr8m4av
title: "Cache tests: remaining follow-ups after the suite review (test-only projections in production, three snapshot helpers, large files)"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T13:36:30.040Z
updated_at: 2026-10-01T13:36:30.040Z
---
From the PR #256 review (mb-sqlv), items already in the base and not fixed there: production carries test-only projections (classification_as_fixture, parsed_git_version_as_fixture, acquisition_gate_as_fixture in src/metabrowser/cache/) that exist so fixtures can be replayed; decide whether they belong in tests. Three snapshot helpers exist (the routes _snapshot records mode and size only; the recovery driver's; the permissions _tree); one shared helper would do. The case of LocalPath.value is unpinned (mutant U9, LocalPath(value.lower()), survives). Two fixture-only tests remain by design (test_url_grammar_reasons_are_closed_and_exercised, test_store_keys_are_distinct_across_sources_and_object_formats). Sizes worth a look: tests/test_cache_permissions.py 1,613 lines, test_cache_update.py 1,021, test_cache_layout.py 896, and the 325-line damaged block in cli-api-cache. Fifteen URL-grammar refusal reasons are now shown only by the fixture replay, not by a CLI golden (control_or_whitespace, non_ascii, backslash, fragment_not_allowed, invalid_user, missing_host, invalid_host, invalid_port, file_authority_not_local, missing_repository_path, empty_path_segment, dot_segment, encoded_delimiter, invalid_percent_encoding, invalid_path_character); the CLI rendering is one f-string, so this is accepted, but record it. Not labelled v0.12.
