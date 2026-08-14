# Future Plan: Markdown Navigation Extensions

**Date:** 2026-08-13

**Author:** Metabrowser maintainers

**Status:** Future

## Context

The completed
[GitHub and Obsidian navigation baseline](../done/plan-2026-08-13-markdown-link-navigation.md)
provides one canonical `/view/<path>#<fragment>` route, exact standard Markdown
resolution, deterministic Obsidian wiki lookup, safe local resources, and a typed public
navigation boundary.
Future adapters must preserve those defaults and activate only from explicit syntax,
configuration, or verified repository context.

## Work Map

| Extension | Bead | Required boundary |
| --- | --- | --- |
| MkDocs, Docusaurus, Jekyll, and published root routes | `mb-d01n` | Translate source targets only after exact lookup and only from explicit or strong configuration; keep `/view/` canonical for repository browsing. |
| Same-repository absolute GitHub URL localization | `mb-v5cz` | Map `/blob/` or `/tree/` URLs only when repository and revision identity are proven; otherwise leave them external. |
| Source-line locations | `mb-281d` | Add a source-view location type instead of overloading rendered heading fragments such as `#L14-L20`. |
| Broken-link reports, backlinks, and graphs | `mb-cl0b` | Consume bounded inventory and resolver results asynchronously without changing click-time semantics. |
| Whole-note and section transclusion | `mb-55ll` | Add a rendering action with recursion, cycle, byte, time, and disposal budgets over the same resolved target. |
| Frontmatter alias lookup | `mb-vjes` | Add a separately tested metadata index and explicit ambiguity behavior if real vaults require target-by-alias resolution. |
| Multiple repositories or vaults | `mb-hvze` | Add explicit mounted-root identity to `NavigationTarget`; never infer a cross-root path from traversal. |

Epic `mb-fbm2` owns evaluation and prioritization.
Each extension needs its own evidence, acceptance criteria, and implementation plan
before it moves into active work.

## Invariants

- Ordinary Markdown links remain exact and GitHub-compatible.
- Parsed wiki syntax remains the only automatic trigger for Obsidian lookup.
- Missing or ambiguous targets remain explicit; adapters do not guess by inventory
  order, filename case, or hidden project heuristics.
- Every local route and resource remains served-root-contained and bounded.
- New renderer state has a disposal path and preserves native browser link behavior.

## References

- [Markdown link navigation research](../../research/research-2026-08-13-markdown-link-navigation.md)
- [Completed baseline plan](../done/plan-2026-08-13-markdown-link-navigation.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
