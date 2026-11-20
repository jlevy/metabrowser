---
type: is
id: is-01m7v6920aryngzfdaedc08hpk
title: "PR #617 A13: source protocol home, registration, and file handle unspecified or inverted"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:05.994Z
updated_at: 2026-11-20T00:58:48.419Z
started_at: 2026-11-20T00:39:19.734Z
closed_at: 2026-11-20T00:58:48.419Z
close_reason: "fixed in `d5ea44d`: protocol types and wire contract in a core module re-exported from `plugin_api`, SDK surface under `PLUGIN_SDK_VERSION`; sources declared as `[[table_source]] kind/adapter`, imported lazily and visible to `--doctor` and the parity check; only built-in or installed distributions can add one; the handle is a `ContentRef` plus an optional resolved-path capability, with the Git pin case stated"
resolution: null
duplicate_of: null
---
Severity: Medium. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 54-56, 219-236, 290. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A13).
