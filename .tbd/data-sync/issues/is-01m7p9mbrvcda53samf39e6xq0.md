---
type: is
id: is-01m7p9mbrvcda53samf39e6xq0
title: "Config format discipline: every Metabrowser config file carries one short self-describing format string (mf01, mf02, ...) like tbd's, and human-edited configs are YAML; apply it across existing configs"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T03:01:30.010Z
updated_at: 2026-11-18T03:01:30.010Z
---
Owner, 2026-11-18 in chat: 'We should have a very simple format string for the configs in the metabrowser configs, e.g. "mf01", "mf02" etc that is self-describing but simple, a bit like what tbd does. We might already have this, but it's good to have the discipline and then apply it across our configs.' and 'for readability, I would be inclined to make it YAML, like we do for soft schemas or for tbd configs.' Today versions are ad hoc: integers (FILE_DIFF_SCHEMA_VERSION = 1, FILE_TYPE_REGISTRY_SCHEMA_VERSION = 5), 'schema' strings (LEGEND_SCHEMA), cache layout 'format' (cache/projection.py), MARKDOWN_DIFF_VERSION. Scope: decide the scheme (one sequence per file kind vs one shared mfNN; how a reader refuses a newer format; where the registry of formats lives with a check), write it in docs/development.md or an arch doc with a test that every config file and writer declares it, and migrate the user-facing config files (settings, recents) to YAML with the string. Caches and wire payloads: decide whether they adopt it (likely a separate concern; say so). The recents store (mb-40k4) is the first consumer.
