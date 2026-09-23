---
type: is
id: is-01m2nz8q666pwqcbxbn7d5jr6x
title: "Repository source boundary: subjects, attached filesystem, and lifecycle"
kind: feature
status: in_progress
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2p1pszq015wyj1b3admbt8r
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T20:41:53.605Z
updated_at: 2026-09-23T01:38:16.626Z
started_at: 2026-09-16T21:24:53.260Z
---
Introduce RepositorySubject, SourceSession, ContentSource, SourceCapabilities, and AttachedFilesystemSubject with exactly one active subject per server/browser session. SourceSession owns subject identity, generation, content reader, navigation/index capability, and lease. Generalize coordinator, file/raw/tree/container/event routes, cache keys, and plugin dispatch without behavior change for filesystem roots. Add additive content-reader plugin APIs; keep resolve_path and served_root filesystem-only, capability-gate legacy hooks on non-filesystem sources, and define typed unsupported behavior for recency, ignore, watcher, activity, and mutation capabilities. Preserve exact-root containment, update every built-in consumer and parity row, and publish through mb-tsdc. GitRevisionSubject, GitPath, tree/blob reads, batch readers, and revision leases remain mb-z335.

## Notes

2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. Source sessions, bounded content ports and binary/structured/agent-log/diff/image/Markdown consumers are implemented. The broad hook-migration checkbox was split from remaining golden/integration acceptance in the repository spec. Review/publication remains mb-tsdc.

Earlier history:
#156 was folded into draft #216 https://github.com/jlevy/metabrowser/pull/216. There is no separate source-boundary PR. Review is mb-tsdc. Do not reopen #156.
