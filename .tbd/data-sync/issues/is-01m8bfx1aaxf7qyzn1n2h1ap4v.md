---
type: is
id: is-01m8bfx1aaxf7qyzn1n2h1ap4v
title: "Plugin authority: confined with declared needs as grants; no backend, no Python"
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx231spr2pvhzetq1j5as
  - type: blocks
    target: is-01m78gmwnk00rz776w8w8k7g9j
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:08.745Z
updated_at: 2026-11-26T09:20:37.483Z
started_at: 2026-11-26T09:20:28.190Z
---
Phase 4 (plan: Key Decision 11, What a Manifest Declares, Trust and Consent). A repository's worker requires confinement. The default grant: read the environment and its base interpreter, the editable roots its .pth files name, the clone, the served folder and scoped folders; write the plugin cache, a private temporary folder, and its own bytecode cache; no network; programs confined. [plugin.needs] in the manifest asks for more: read, write, network (none or internet), run, environment, and unconfined. Every need is a grant under confinement, the network and further writes included. The grant is the intersection of what is declared and what was approved (providers[].granted in the registry); a need that appears later is refused until approved, with a line in the bar; nothing asks on a version bump that declares nothing new. Workers are keyed by grant set, so no plugin runs with what only another was granted. Authority full is for a plugin that declares unconfined = true, or by --authority full; the bar never offers it. Where the machine has no backend (Linux before 5.13 or with Landlock off, an unknown architecture, a sandbox that cannot nest, Windows), a repository's plugin Python is refused with no_sandbox, its manifests, assets, and JavaScript still load, and --doctor names the missing piece. Sources the user adds prefer confinement and run without it where there is none, said plainly. The runtime turns a refused access into a message naming the need to declare; author mode logs what a hook asked for. The consent says that everything in the clone's environment runs, not only the listed providers, and that JavaScript runs in the page. Depends on the macOS spike's answer for the worker profile. Threat-model rows and the sentence in docs/working-with-agents.md.

## Notes

2026-11-26, third revision of the plan: folded in a second review of the isolation layer, threats, and protocol.
