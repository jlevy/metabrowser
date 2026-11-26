---
type: is
id: is-01m8bfx0jk64cgj3sz7sm2nav4
title: View offers, table sources, and register modules in plugin workers
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T08:35:07.987Z
updated_at: 2026-11-26T08:36:54.131Z
---
Phase 3 (plan: The Plugin Runtime, extension points). Three Python extension points on main that the first revision of the plan never mentioned. [plugin] register modules are imported when a worker lists its plugins (Phase 1, with the worker). [[view]] offer predicates run in the server today for every folder page and every response that lists a text file's views (server.py _offered_folder_views, _offered_file_views), which a worker started on demand cannot answer without a wait: measure what an offer costs per page through a worker, then choose among a declarative predicate, a cached verdict by content fingerprint, and starting the worker with the first folder page. [[table_source]] adapters are an object protocol (table_source.py TableSource: generation, tables, schema, rows, record, card) whose TableHandle holds the server's event loop: proxy the five methods as calls under the request's Budget, and read_window as a host call. Until this lands, metab --doctor refuses a worker plugin that declares an offer or a table source, by name, and its other parts load. Goldens through --api for a fixture table source in a worker, equal to the same source in process.
