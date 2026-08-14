# Feature: GitHub and Obsidian Markdown Navigation

**Date:** 2026-08-13 (last updated 2026-08-13)

**Author:** Metabrowser maintainers

**Status:** Approved

## Overview

Metabrowser should browse links among Markdown files in an ordinary GitHub repository or
Obsidian vault without configuration.
Standard Markdown links that resolve on GitHub must resolve the same way in Metabrowser.
Obsidian wiki-links must add their note, heading, block, label, and media conventions
without changing standard Markdown semantics.

Every selected repository path has one canonical URL:

```text
/view/<served-root-relative-path>#<document-fragment>
```

The pathname identifies the selected file or folder.
The fragment identifies a location inside that document.
This replaces the current hash-as-file router completely; there is no legacy hash
migration or compatibility mode.

Both syntax families use one typed resolution pipeline, one safe-resource policy, and
one public navigation boundary.
GitHub-compatible links are implemented first because they establish that foundation,
but the feature is not complete until the Obsidian scope also passes end-to-end
fixtures.
Static-site routing, GitHub remote-URL localization, backlinks, graph features,
and note transclusion remain explicitly mapped follow-ups.

## Goals

- Make same-repository links and resources that work in GitHub-rendered Markdown work
  automatically from nested files
- Support standard Obsidian wiki-links to notes, headings, and named blocks, including
  occurrence labels and deterministic ambiguity handling
- Support Obsidian image and media wiki-embeds through the existing bounded raw-resource
  boundary
- Give every selected file, folder, heading, and supported block a stable `/view/` URL
- Preserve native browser behavior through real `href` values: status previews,
  copy-link, keyboard use, modifier-click, middle-click, new tabs, reload, and history
- Keep generic route and history behavior in the browser shell and Markdown dialect
  behavior in the built-in Markdown plugin
- Reuse Metabrowser’s existing served-root containment, inventory, renderer-lifecycle,
  and plugin boundaries
- Make missing, ambiguous, unsafe, unsupported, and temporarily unresolved targets
  explicit instead of guessing

## Non-Goals

- Reading or migrating the old `/#<file-path>` route
- Reproducing a published MkDocs, Docusaurus, Jekyll, or GitHub Pages URL tree
- Localizing absolute GitHub `/blob/`, `/tree/`, branch, commit, or cross-repository
  URLs
- Appending `.md`, selecting `README.md` or `index.md`, changing case, or searching for
  a broken standard Markdown link by basename
- Emulating source-view line fragments such as `#L14-L20` in rendered Markdown
- Launching `file:`, `javascript:`, `data:`, `obsidian:`, or another custom scheme
  automatically
- Frontmatter-alias target lookup, complete note or section transclusion, backlinks,
  graph views, or cross-vault navigation
- Replacing the existing file-fetch, inventory, renderer, or bounded raw-file
  architecture

## Background

Metabrowser currently stores the selected file in `location.hash`. The same hash must
also identify a heading inside rendered Markdown, so route parsing relies on a
file-versus-heading heuristic.
Recent browser-history work pushes those hash routes, but the URL still cannot represent
both a file and a document location cleanly.

KPress already parses standard inline, reference-style, image, and sanitized raw-HTML
links. The built-in Markdown renderer mounts that HTML asynchronously and owns its
disposal lifecycle. KPress also produces GitHub-compatible heading IDs.
It leaves Obsidian wiki syntax as source text, so the Markdown plugin needs a
source-aware adapter before the final HTML loses code, escape, and embed context.

The completed
[research brief](../../research/research-2026-08-13-markdown-link-navigation.md)
compares CommonMark, GitHub, GitLab, VS Code, MkDocs, Docusaurus, Jekyll, and Obsidian.
Its decision addendum establishes exact GitHub repository semantics as the universal
standard-link baseline and parsed wiki syntax as the Obsidian adapter trigger.

## Design

### One Structured Navigation Model

Do not pass partially decoded strings through independent route, renderer, and click
heuristics. Use three explicit values:

```text
LinkIntent = {
  syntax, sourcePath, authoredTarget, label?, action
}

ResolvedTarget = {
  status, path?, query?, fragment?, mediaKind?, candidates?, reason?
}

NavigationTarget = {
  path, query?, fragment?
}

NavigationOpenOptions = {
  viewId?
}
```

`LinkIntent.action` distinguishes document navigation from a resource embed.
`ResolvedTarget.status` is one of `internal`, `external`, `missing`, `ambiguous`,
`unsafe`, `unsupported`, or `pending`. The original authored target remains available
for diagnostics.

`NavigationTarget.path` is a normalized, served-root-relative logical path with `/` as
its separator and no leading slash.
The empty string represents the served root.
Query and fragment omit their leading punctuation and remain separate from filesystem
lookup. Paths and fragments are decoded logical values.
Query metadata keeps its URL serialization so an escaped delimiter cannot be confused
with query structure.
The route formatter owns final path and fragment encoding and canonicalizes query
escapes.

The Markdown plugin owns intent creation and syntax-specific resolution.
The browser shell owns canonical URL formatting, file opening, history, and fragment
delivery. No Markdown module reaches private `app.js` globals.

### Canonical Route and History

The only selected-path route is:

```text
/view/<percent-encoded-served-root-relative-path>#<document-fragment>
```

Each path segment is encoded independently and `/` remains a separator.
`/view/` selects the served root.
Folders gain a trailing slash after the file API identifies their type.
A direct safe GET returns the application shell so refresh and new tabs work.
Malformed, multiply decoded, or escaping paths are rejected at the server boundary
before the shell is returned.

The `/view/` namespace avoids collisions with `/api`, `/raw`, `/static`, plugin routes,
and arbitrary repository root names.
Direct `/<path>` URLs belong only to a possible future published-site adapter.

A focused strict browser module owns route parsing, formatting, and canonicalization:

- User file or folder navigation uses `history.pushState`.
- Startup normalization and folder-slash canonicalization use `history.replaceState`.
- Back and forward use `popstate`.
- A fragment change for the selected file scrolls after rendering without fetching the
  file again.
- The CLI emits `/view/<path>` when started with a selected path.
- `/#<path>` is not parsed, rewritten, redirected, or treated as a file route.
- The old hash parser, file-route heuristic, `hashchange` file navigation, and their
  compatibility tests are removed.

This is an intentional clean break.
There is no feature flag, fallback reader, one-release migration, or dual-write period.

### Public Navigation Boundary

Replace the link-navigation surface with one cohesive SDK namespace:

```text
window.metabrowser.navigation.href(target) -> string
window.metabrowser.navigation.open(target, options?) -> Promise<void>
window.metabrowser.navigation.current() -> NavigationTarget | null
```

`href` is pure and returns the canonical URL. Public `open` represents a normal user
navigation and pushes history.
Initialization, canonical replacement, and popstate restoration use private shell
operations rather than public history flags.
The optional `viewId` is a presentation preference for in-app opening, not part of the
resource identity or canonical URL.

Move bundled callers, including folder views and Markdown, to this namespace in the same
change. Remove `openPath`, the `metabrowser:open-path` event, and link-specific SDK
compatibility shims; this pre-stable navigation redesign is not constrained by their
existing shape. Define the public target once in JSDoc and `types.d.ts`.

### Exact Standard Markdown Resolution

For a standard rendered Markdown or sanitized raw-HTML destination:

1. Split scheme or authority, path, query, and fragment before decoding.
2. Preserve explicitly allowed external URLs as external.
   A protocol-relative target such as `//example.com/file` is external, not a
   served-root path.
3. Keep an empty path on the current source file.
   Resolve one leading `/` from the served root; otherwise resolve from the source
   file’s directory.
4. Decode once, normalize `.` and `..`, and reject traversal above the served root,
   encoded separators, NUL bytes, and backslash traversal.
5. Preserve exact case.
   Do not add candidate extensions, choose index files, or search the inventory for
   ordinary Markdown.
6. Return a typed result rather than a guessed path.
7. Format document targets beneath `/view/` and embedded local resources through the
   existing safe raw-resource route.

Reference-style links need no special resolution branch after KPress produces their
final destination.
A folder target opens the folder; it does not choose a README. A query
is not part of filesystem lookup and remains navigation metadata.

Common mappings from `docs/current.md` are:

| Authored target | Result |
| --- | --- |
| `other.md` | `/view/docs/other.md` |
| `./other.md#setup` | `/view/docs/other.md#setup` |
| `../README.md` | `/view/README.md` |
| `/CONTRIBUTING.md` | `/view/CONTRIBUTING.md` |
| `#configuration` | `/view/docs/current.md#configuration`, without a refetch |
| `../images/map.svg` in an image | `/raw?path=images%2Fmap.svg` |
| `https://example.com/guide` | The unchanged external URL |

Exact document `href` values do not require a repository scan or a preflight request.
If the selected path is missing, the existing file-open flow shows the normal not-found
state. A future broken-link report may use the inventory without changing the resolver.

### Rendered Markdown Integration

A focused module enhances each completed KPress mount:

- classify anchors and embedded-resource elements relative to `ctx.path`;
- replace safe internal destinations with canonical URLs;
- preserve safe external destinations and native `target`, `download`, and modifier
  behavior;
- delegate only unmodified primary-button internal activation to
  `metabrowser.navigation.open`;
- keep missing, ambiguous, unsafe, and unsupported text keyboard-reachable with an
  accessible explanation;
- apply the active fragment only after the matching render completes; and
- return a disposer that removes listeners, subscriptions, and pending work when the
  renderer is replaced.

Do not use a dynamic `<base>` element; it would also retarget shell scripts, API calls,
and unrelated resources.
Resource rewriting uses the existing safe raw endpoint and its containment, compression,
and read-budget behavior.

### Obsidian Wiki-Link Adapter

The required Obsidian adapter recognizes at least:

- `[[Note]]`, `[[Folder/Note]]`, and `[[Note|Label]]`;
- `[[#Heading]]`, `[[Note#Heading]]`, `[[Note#Parent#Child]]`, and
  `[[Note#Heading|Label]]`;
- `[[#^block-id]]` and `[[Note#^block-id]]`; and
- attachment navigation such as `[[asset.pdf]]` and media embeds such as
  `![[asset.png|640x480]]`.

Parse wiki syntax with source context before rendering discards escape and code
information. A bounded Markdown-aware scanner or KPress extension may emit inert,
sanitizable metadata for later DOM enhancement.
A regular expression over final HTML is not sufficient.
Code spans, fenced blocks, existing Markdown links, and escaped literals remain
unchanged.

Resolution is deterministic and deliberately avoids Obsidian’s private tie-breakers:

1. Honor explicit relative paths and exact vault-root paths first.
2. Accept an omitted `.md` suffix for notes; require an extension for non-Markdown
   attachments.
3. Prefer an exact source-directory note for a bare note name.
4. Otherwise use the bounded inventory index for a unique basename or path-suffix
   result.
5. Return every viable candidate when multiple notes match; never choose by inventory
   order.
6. Leave lookup in a `pending` state while the required inventory view is incomplete,
   then re-enhance only the still-current mount.

Occurrence labels change display text, not target lookup.
Frontmatter aliases do not silently redirect plain links in this baseline.
Ordinary Markdown remains exact even inside a vault.

Heading links resolve against actual rendered IDs.
Named block syntax is parsed from source, mapped to explicit block metadata, and given a
real stable DOM target; block links are required, not an unsupported placeholder.
The parser must not invent block targets from paragraph text.

Image and media wiki-embeds reuse the safe resource resolver and apply bounded width and
height metadata without treating display values as part of target lookup.
Whole-note and note-section transclusion is a different rendering action and remains
future work; an unsupported note embed may expose a safe link to its target but must not
pretend it was transcluded.

### Security and Failure Behavior

- Every filesystem target remains beneath the configured served root after one decode
  and normalization pass.
- Route and resource handling reuse existing safe-path, symlink, inventory, gzip, and
  bounded-read helpers instead of creating a parallel containment policy.
- Repository-root links are formatted beneath `/view/`; they cannot address `/api`,
  `/static`, plugin assets, or another application namespace.
- Unsafe schemes and root escapes keep visible source text but gain no active local
  destination. External schemes follow the existing explicit trust policy.
- Missing and ambiguous targets are never redirected silently.
  Candidate paths and reasons remain available to keyboard and assistive-technology
  users.
- Wiki parsing and lookup are bounded by document bytes, target count, path length,
  inventory size, and response size.
  They never perform an unbounded synchronous tree walk on a request path.

## Components

| Component | Required adjustment |
| --- | --- |
| Focused server route helper, registered by `server.py` | Serve the shell for safe `/view/{path:path}` requests and reject malformed or escaping targets with existing safe-path helpers. |
| `src/metabrowser/cli/serve.py` | Emit a segment-encoded `/view/<path>` startup URL. |
| New strict module under `src/metabrowser/static/` | Define `NavigationTarget`, parse and format canonical routes, and own push, replace, pop, and fragment behavior. |
| `src/metabrowser/static/app.js` | Compose the navigation module with `selectFile`; delete hash file routing and its heuristic. |
| `plugin_sdk.js` and `types.d.ts` | Expose the `metabrowser.navigation` namespace, migrate bundled consumers, and remove the old path event surface. |
| New strict Markdown link modules | Resolve and enhance standard KPress links and resources, then parse and resolve Obsidian wiki syntax over the same result model. |
| Existing Markdown mount | Install enhancement after asynchronous render and dispose it with the TOC and render controller. |
| Inventory-derived note index | Provide bounded, completion-aware basename and path-suffix lookup for wiki targets only. |
| Tests and fixtures | Add a machine-readable resolution matrix plus route, DOM, SDK, lifecycle, accessibility, and integration coverage. |

All new browser modules enter the fully strict `tsconfig.json` project.
Do not add a file to the legacy allowlist.

## API and URL Changes

- Add the browser URL contract `/view/{path:path}`.
- Replace file identity in `location.hash`; fragments now identify only document
  locations.
- Replace `metabrowser.openPath` and `metabrowser:open-path` with
  `metabrowser.navigation`.
- Add the shared internal link-intent and resolved-target shapes in focused Markdown
  modules.
- Add no path-resolution HTTP endpoint in the baseline.

There is intentionally no compatibility promise for saved hash file URLs or the old
link-navigation SDK surface.
All bundled code and documentation change atomically.

## Implementation Plan

### Phase 1: Canonical Route and Navigation Boundary

- [x] Add the safe `/view/` shell route, strict route module, direct-load behavior, CLI
  URL, folder canonicalization, and push, replace, pop, and fragment behavior.
- [x] Delete hash file-route parsing, writing, listeners, and migration logic.
- [x] Introduce `metabrowser.navigation`, migrate bundled callers, remove the old SDK
  event surface, and cover the public types.

Exit condition: direct URLs, reload, new tabs, normal navigation, and back or forward
select exactly one path and fragment, with no hash-as-file fallback.

### Phase 2: GitHub-Compatible Standard Links

- [ ] Add exact standard-link and embedded-resource resolution to the built-in Markdown
  renderer.
- [ ] Produce canonical `href` and safe resource URLs while preserving native click
  variants, asynchronous fragment scrolling, and renderer disposal.
- [ ] Validate a GitHub-style fixture repository and the standard-link portion of the
  resolution matrix; update user-facing browsing documentation.

Exit condition: a repository whose same-repository Markdown links work on GitHub can be
browsed through Metabrowser without configuration.

### Phase 3: Obsidian Links and Embeds

- [ ] Parse wiki-links and media wiki-embeds with source context while leaving code,
  existing links, and escaped literals unchanged.
- [ ] Add exact-path precedence, optional note extensions, bounded unique-note lookup,
  pending and ambiguous results, and accessible candidate information.
- [ ] Map same-note and cross-note heading and named-block targets to real DOM anchors.
- [ ] Route image and media wiki-embeds safely and represent note transclusion as an
  explicit future action.
- [ ] Validate an Obsidian-style vault with duplicate basenames, spaces, Unicode,
  headings, blocks, labels, attachments, missing notes, and ambiguous notes.

Exit condition: supported `[[...]]` links select the deterministic note and location an
Obsidian user expects, all ambiguity is explicit, and standard Markdown behavior is
unchanged.

The implementation epic is complete only after all three phases pass `make verify` in
one end-to-end branch and PR. Phases are dependency order, not optional product slices.

## Work Tracking

Epic `mb-yq1f` owns the required baseline.
Its implementation chain is:

1. Feature `mb-ln8z` replaces routing and the public navigation boundary: `mb-b6bb`
   implements the URL codec, `mb-xt9v` adds direct server and CLI routes, `mb-ftti`
   integrates history and removes hash routing, and `mb-pi55` publishes the SDK and
   migrates bundled callers.
2. Feature `mb-zm16` implements exact standard Markdown links and resources: `mb-plxn`
   builds the typed resolver and `mb-ma28` integrates links, resources, fragments,
   activation, and renderer disposal.
3. Feature `mb-4pv4` proves the GitHub-compatible default: `mb-e0gk` builds the shared
   fixture matrix and `mb-9y9n` completes integration, accessibility, history, and
   browsing documentation.
4. Feature `mb-8qnd` implements Obsidian syntax and deterministic note lookup: `mb-7ve6`
   parses wiki syntax with source context and `mb-quiz` adds the bounded note index,
   pending state, and ambiguity handling.
5. Feature `mb-08is` completes Obsidian locations, media, and compatibility: `mb-lmub`
   implements heading and named-block targets, `mb-x2xp` implements attachment links and
   safe media embeds, and `mb-k1r7` completes vault fixtures, accessibility,
   documentation, and end-to-end validation.

Each bead includes focused tests and must pass `make verify`. The dependency chain keeps
one stable route and resolver contract underneath both syntax families.
Future extensions are tracked separately by `mb-fbm2` so they do not prevent closing the
baseline epic.

## Testing Strategy

Create `tests/fixtures/markdown_link_resolution.json` with source path, syntax, authored
target, action, inventory state, expected status, resolved path, query, fragment,
candidates, and canonical URL. Drive pure resolver tests and focused DOM behavior from
the same cases where practical.

Coverage includes:

- bare, dot, parent, root, folder, fragment-only, query, reference-style, raw-HTML,
  image, and external targets;
- spaces, Unicode, literal percent, `#`, and `?`, encoded separators, double-decode
  attempts, backslashes, traversal, symlinks, case mismatches, missing paths, and
  reserved route names;
- direct `/view/` GET, CLI startup, explicit absence of hash file routing, reload, new
  tabs, same-document fragments, asynchronous rendering, and back or forward;
- primary, modifier, middle, keyboard, `target`, and download activation behavior;
- KPress mount replacement, listener and inventory-subscription disposal, aborts, and no
  stale fragment scroll;
- unique, duplicate, relative, vault-root, label, heading, named-block, attachment, and
  media-embed wiki targets;
- code spans, fenced blocks, escaped wiki syntax, incomplete inventory, and bounded
  behavior when a document exceeds its wiki-target cap; and
- JSDoc and declaration parity for the new SDK with no old navigation surface.

Use the Node DOM harness and pytest wrappers for pure and rendered behavior, Starlette
tests for direct routes and containment, existing CLI golden tests for startup URLs, and
the project-wide `make verify` gate.

## Rollout Plan

Land the route, GitHub behavior, and Obsidian behavior as one coherent baseline with no
feature flag. Internal commits may follow the phase order, but the implementation PR is
not complete until both fixture repositories pass.

Wiki syntax is self-identifying and needs no global repository mode.
Exact standard links remain exact everywhere.
Future site adapters must be explicit or confidently configuration-detected and cannot
change baseline semantics silently.

## Acceptance Criteria

- Standard GitHub-style same-repository links and resources work automatically from
  nested Markdown files.
- Standard Obsidian note, heading, named-block, label, and media wiki-link behavior
  works automatically and deterministically.
- Every selected file, folder, heading, and supported named block has a canonical URL
  that survives direct load and normal browser navigation.
- Internal links expose final `href` values and preserve native non-primary activation.
- Exact failures, unsafe targets, incomplete lookup, and Obsidian ambiguity are visible
  and never hidden by fuzzy fallback.
- The old hash file route and old link-navigation SDK surface are absent rather than
  supported in parallel.
- The shell, SDK, and Markdown plugin retain their ownership boundaries, and every new
  listener, subscription, or pending operation has a tested disposal path.
- No route or resource read escapes the served root or aliases an application namespace.
- Route, resolver, DOM, server, CLI, accessibility, lifecycle, fixture, and project-wide
  verification tests pass.

## Future Extension Map

These are separate features after the baseline, not unresolved acceptance work:

| Extension | Bead | Preserved seam and trigger |
| --- | --- | --- |
| MkDocs, Docusaurus, Jekyll, and published root routes | `mb-d01n` | Translate source targets only after exact lookup and only from explicit or strong configuration; leave `/view/` canonical for repository browsing. |
| Same-repository absolute GitHub URL localization | `mb-v5cz` | Map `/blob/` or `/tree/` URLs only when repository and revision identity are proven; otherwise remain external. |
| Source-line locations | `mb-281d` | Add a source-view location type instead of overloading rendered heading fragments such as `#L14-L20`. |
| Broken-link reports, backlinks, and graphs | `mb-cl0b` | Consume the bounded inventory and resolver results asynchronously without changing click-time semantics. |
| Whole-note and section transclusion | `mb-55ll` | Add a rendering action with recursion, cycle, byte, time, and disposal budgets over the same resolved target. |
| Frontmatter alias lookup | `mb-vjes` | Add a separately tested metadata index and explicit ambiguity behavior if real vaults require target-by-alias resolution. |
| Multiple repositories or vaults | `mb-hvze` | Add explicit mounted-root identity to `NavigationTarget`; never infer a cross-root path from traversal. |

Feature bead `mb-fbm2` owns evaluation of this map after the required implementation is
measured.

## Open Questions

There are no blocking product questions.
Exact API names may receive mechanical refinement during `mb-ln8z`, but the single
target model, `/view/` route, clean break, ownership boundaries, and required GitHub and
Obsidian behaviors are fixed decisions.

## References

- [Markdown link navigation research](../../research/research-2026-08-13-markdown-link-navigation.md)
- [Development guide](../../../development.md)
- [Supply-chain security policy](../../../../SUPPLY-CHAIN-SECURITY.md)
- [GitHub basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
- [Obsidian internal links](https://obsidian.md/help/links)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
