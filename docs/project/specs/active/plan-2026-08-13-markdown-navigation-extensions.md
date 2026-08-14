# Plan: Markdown Navigation Extensions

**Date:** 2026-08-13

**Author:** Metabrowser maintainers

**Status:** Active

## Context

The completed
[GitHub and Obsidian navigation baseline](../done/plan-2026-08-13-markdown-link-navigation.md)
provides one canonical `/view/<path>#<fragment>` route, exact standard Markdown
resolution, deterministic Obsidian wiki lookup, safe local resources, and a typed public
navigation boundary.
This phase adds adapters and knowledge features without weakening those defaults.

Ordinary Markdown links remain exact and repository-relative.
Every extension activates from explicit syntax, verified repository identity, or strong
project configuration.
Missing and ambiguous destinations remain visible rather than falling back to inventory
order, fuzzy matching, case folding, or traversal outside the active root.

## Public Contracts

### Project Context

Metabrowser derives read-only context from bounded local evidence:

- recognized static-site configuration filenames in the completed file catalog;
- GitHub repository identity, current commit, and current branch from local Git
  metadata;
- optional `.metabrowser/navigation.json` configuration beneath the served root.

The navigation configuration has a versioned shape:

```json
{
  "version": 1,
  "mounts": {
    "handbook": "docs/handbook",
    "service": "services/example"
  }
}
```

Mount names are URL-safe identifiers.
Mount paths are served-root-relative directories and must resolve inside the served
root. The file is data only: it cannot register code, plugins, or arbitrary routes.
Invalid configuration produces diagnostics and no mounts.

### Navigation Targets

`NavigationTarget` gains two explicit dimensions:

- `root`, an optional configured mounted-root identity;
- `sourceLines`, an optional `{start, end}` location for source views.

Primary-root links retain `/view/<path>`. Mounted targets use `/view/@/<root>/<path>`.
Source locations use canonical `view=source` and `line=<start>-<end>` query metadata,
not rendered heading fragments.
The URL codec, browser history, public SDK, raw resources, complete-source reads, and
renderers all use the same target type.

## Implementation Work

### Configured Static-Site Adapters (`mb-d01n`)

**Status:** Implemented with pure resolver and rendered-link lifecycle coverage.

The Markdown plugin recognizes MkDocs, Docusaurus, and Jekyll only when the completed
catalog contains their root configuration files.
For a root-relative, extensionless published route whose exact repository target does
not exist, the adapter generates a bounded ordered set of source candidates.

Acceptance criteria:

- an existing exact file or directory always wins;
- an adapter runs only for its recognized project configuration;
- one existing candidate becomes a canonical `/view/` source target;
- multiple existing candidates are reported as ambiguous;
- incomplete catalogs retain an explicit pending state;
- a route with no adapter result keeps ordinary exact Markdown behavior;
- mount-scoped documents use only the catalog for their active root.

### Verified GitHub URL Localization (`mb-v5cz`)

**Status:** Implemented with bounded Git metadata discovery, pure URL localization, and
rendered-link integration coverage.

Absolute `https://github.com/<owner>/<repo>/blob/...` and `/tree/...` links become local
only when their host and repository match the mounted Git context.

Acceptance criteria:

- a full commit permalink localizes only when it equals the mounted commit;
- a branch URL localizes only when it equals the mounted branch and is labelled as a
  working-tree view;
- a served subdirectory strips only its verified repository prefix;
- cross-repository, unknown-revision, tag-like, and malformed URLs remain external;
- query and fragment data preserve their ordinary meaning after localization;
- localized links retain native copy, new-tab, reload, and history behavior.

### Broken Links, Backlinks, and Graph Analysis (`mb-cl0b`)

**Status:** Implemented as a bounded, abortable Markdown-plugin analysis API over an
immutable catalog snapshot and the shared standard, wiki, adapter, and GitHub resolvers.

The Markdown plugin exposes a bounded asynchronous graph analyzer over immutable catalog
snapshots and the shared resolvers.
It returns nodes, resolved edges, unresolved edges, backlinks, diagnostics, and an
explicit completeness flag.

Acceptance criteria:

- standard Markdown and wiki edges use the same resolution rules as click-time links;
- analysis never changes click-time resolver state;
- file count, link count, aggregate source bytes, and per-file source reads are bounded;
- abort signals stop outstanding work and no live listener remains after disposal;
- incomplete catalogs or truncated scans remain explicit in the result;
- graph visualization remains a consumer concern outside the core resolver.

### Bounded Obsidian Transclusion (`mb-55ll`)

Whole-note, heading, and named-block wiki embeds render through the existing safe KPress
boundary after deterministic wiki resolution.

Acceptance criteria:

- whole-note, heading-section, and named-block embeds select source deterministically;
- nested embeds share limits for recursion depth, document count, aggregate source
  bytes, and elapsed time;
- a path-and-location cycle produces an accessible error instead of recursion;
- every fetch and nested renderer is aborted and disposed when its parent view leaves;
- missing, ambiguous, oversized, timed-out, and unsupported embeds remain visible;
- embedded links use the same canonical navigation and mounted-root identity as their
  source note.

### Source-View Line Locations (`mb-281d`)

GitHub-style `#L14` and `#L14-L20` locations on non-Markdown source files map to the
explicit `sourceLines` target.

Acceptance criteria:

- line ranges validate positive, ordered, bounded integers;
- canonical URLs use source-view query metadata and round-trip through the codec;
- source renderers expose stable line elements, scroll to the range, and visibly mark
  it;
- changing only the line range updates the active source view without refetching the
  file;
- Markdown heading IDs named `L14` remain rendered fragments rather than source lines.

### Frontmatter Alias Lookup (`mb-vjes`)

Alias lookup is a lazy, bounded metadata index used only after deterministic wiki path
resolution returns missing.
It recognizes scalar, flow-sequence, and block-sequence `alias` or `aliases` values in
leading YAML frontmatter.

Acceptance criteria:

- exact, relative, root, basename, and suffix wiki matches keep precedence;
- one alias target resolves, duplicate aliases are ambiguous, and missing aliases stay
  missing;
- standard Markdown links never consult aliases;
- malformed frontmatter is skipped with diagnostics;
- index size, source bytes, and concurrent reads are bounded and abortable;
- aliases never cross a mounted root unless the authored wiki target names that root.

### Explicit Mounted Roots (`mb-hvze`)

Configured mounts provide stable identity for browsing several repositories or vaults
inside one served root.
The primary served root continues to work without configuration.

Acceptance criteria:

- mounted targets round-trip through `/view/@/<root>/<path>`;
- every mounted path and resource is mapped through one validated contained prefix;
- file catalogs can return immutable root-scoped snapshots;
- ordinary relative links remain inside their current mounted root;
- `[[root::Note]]` is the only automatic cross-root wiki syntax;
- unknown roots, traversal, and ambiguous cross-root targets remain explicit;
- browser selection may omit a tree row for mounted aliases but still renders the file
  and maintains history correctly.

## Shared Limits and Safety

All new limits are named constants close to their owning implementation.
The implementation adds no dependency.
Reads use the existing bounded `/api/file` and KPress routes.
Repository and navigation configuration readers cap file size and never expose local
absolute paths to the browser.

The following invariants remain mandatory:

- ordinary Markdown links stay exact and GitHub-compatible;
- parsed wiki syntax remains the only automatic trigger for Obsidian lookup;
- every local route and resource remains served-root-contained;
- adapters do not guess by filename case, inventory order, or fuzzy similarity;
- new renderer state has a disposal path and preserves native browser link behavior.

## Validation

- [ ] Pure URL, adapter, GitHub localization, alias, transclusion-selection, and graph
  contracts
- [ ] DOM lifecycle, accessibility, source-location, and nested disposal coverage
- [ ] Server tests for bounded Git context and navigation configuration
- [ ] GitHub, Obsidian, static-site, and mounted-vault fixture matrices
- [ ] Documentation and public SDK contract checks
- [ ] `make verify`

## References

- [Markdown link navigation research](../../research/research-2026-08-13-markdown-link-navigation.md)
- [Completed baseline plan](../done/plan-2026-08-13-markdown-link-navigation.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
