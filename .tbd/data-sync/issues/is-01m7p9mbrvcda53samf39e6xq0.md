---
type: is
id: is-01m7p9mbrvcda53samf39e6xq0
title: "Config format discipline: every Metabrowser config file carries one short self-describing format string (mf01, mf02, ...) like tbd's, and human-edited configs are YAML; apply it across existing configs"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T03:01:30.010Z
updated_at: 2026-11-18T03:02:31.814Z
---
Owner, 2026-11-18 in chat: 'We should have a very simple format string for the configs in the metabrowser configs, e.g. "mf01", "mf02" etc that is self-describing but simple, a bit like what tbd does. We might already have this, but it's good to have the discipline and then apply it across our configs.' and 'for readability, I would be inclined to make it YAML, like we do for soft schemas or for tbd configs.' Today versions are ad hoc: integers (FILE_DIFF_SCHEMA_VERSION = 1, FILE_TYPE_REGISTRY_SCHEMA_VERSION = 5), 'schema' strings (LEGEND_SCHEMA), cache layout 'format' (cache/projection.py), MARKDOWN_DIFF_VERSION. Scope: decide the scheme (one sequence per file kind vs one shared mfNN; how a reader refuses a newer format; where the registry of formats lives with a check), write it in docs/development.md or an arch doc with a test that every config file and writer declares it, and migrate the user-facing config files (settings, recents) to YAML with the string. Caches and wire payloads: decide whether they adopt it (likely a separate concern; say so). The recents store (mb-40k4) is the first consumer.

## Notes

2026-11-18 owner (chat): 'It's best if it's a string, but it can be incrementally updated, and it's self-descriptive. Check if we already have a convention, in which case we might want to use that'; 'when a new format comes along, it's easy to migrate it forward when a new incompatible format arises. For compatible formats, we don't update the version. Check how tbd has done this'.
Finding: Metabrowser already has the tbd-style convention for the application home: src/metabrowser/cache/layout.py writes layout.yml and config.yml (YAML) with a format string 'f01' (LAYOUT_FORMAT, CONFIG_FORMAT), keeps an append-only FORMAT_HISTORY / CONFIG_FORMAT_HISTORY (every format a release wrote, oldest first), a MIGRATIONS map from each format to the next, refuses a newer format with FutureLayoutFormatError and upgrade guidance (cache/projection.py 'future_format'), and bumps only on an incompatible change. tbd does the same with 'tbd_format: f08' in .tbd/config.yml.
Plan: adopt that convention as the rule (one fNN string per file kind, own history and migrations, bump only on incompatible change, refuse newer), state it once in docs/development.md with a check, apply it to the recents store first (recent-targets.yml, format f01) and audit the other persisted config files; leave wire payloads and per-entry cache schemas (FILE_DIFF_SCHEMA_VERSION etc.) as a separate decision.
