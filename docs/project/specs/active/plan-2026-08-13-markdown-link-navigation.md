# Feature: Default Cross-File Markdown Navigation

**Date:** 2026-08-13 (last updated 2026-08-13)

**Author:** Metabrowser maintainers

**Status:** Approved

## Overview

Metabrowser should open links among files in an ordinary GitHub repository with no
configuration. A document at `docs/current.md` should make `other.md`,
`../README.md#install`, `/CONTRIBUTING.md`, local images, and fragment-only links behave
as their authors expect on GitHub.
The resulting URLs must also survive refresh, copy-link, new tabs, and browser back and
forward.

The implementation gives every selected repository path a canonical
`/view/<path>#<fragment>` URL and adds one exact, safe resolution pipeline for rendered
Markdown links and resources.
The existing hash route remains an accepted legacy input, not the public route written
by new navigation.

Obsidian wiki-links are a second phase over the same pipeline.
They add syntax parsing and deterministic note lookup, but they do not change standard
Markdown resolution.
Static-site generators, remote-repository URL localization, backlinks, and recursive
transclusion remain later adapters.

## Goals

- Make same-repository links that work in GitHub-rendered Markdown work in Metabrowser
  by default, with no mode selection or project configuration
- Give files, folders, and in-document locations stable URLs under `/view/`
- Preserve native browser behavior for real `href`s, including status previews,
  copy-link, keyboard use, modifier-click, middle-click, new tabs, reload, and history
- Resolve standard paths exactly, distinguish links from embedded resources, and keep
  unsafe or missing targets honest
- Keep route and history policy in the browser shell while keeping Markdown and Obsidian
  syntax in the built-in Markdown plugin
- Reuse the served-root containment, raw-resource, inventory, renderer-lifecycle, and
  public SDK boundaries already enforced by Metabrowser
- Add Obsidian `[[...]]` navigation later without creating a second routing or resource
  system

## Non-Goals

- Reproducing a published MkDocs, Docusaurus, Jekyll, or GitHub Pages route tree without
  an explicit future site adapter
- Treating absolute GitHub `/blob/`, `/tree/`, branch, commit, or cross-repository URLs
  as local files in the first release
- Appending `.md`, choosing `README.md` or `index.md`, searching by basename, changing
  case, or fuzzy-matching a broken standard Markdown link
- Emulating GitHub source-view line fragments such as `#L14-L20` in rendered Markdown
- Launching `file:`, `javascript:`, `data:`, `obsidian:`, or other custom schemes
  automatically
- Full Obsidian note transclusion, recursive embeds, backlinks, graph views, alias
  redirects, or cross-vault navigation
- Replacing the existing file-fetch, renderer, or inventory architecture

## Background

Metabrowser currently stores a selected file in `location.hash`. The same hash must also
identify a heading inside rendered Markdown, so route parsing relies on a heuristic:
fragments containing a slash or file-like extension are treated as files and other
fragments are left as document anchors.
Recent browser-history work correctly pushes hash entries, but it cannot remove this
collision.

KPress already parses standard inline, reference-style, image, and sanitized raw-HTML
links. The built-in Markdown renderer mounts that HTML asynchronously and owns its
disposal lifecycle. This means the first phase does not need another Markdown parser: it
can classify and enhance the rendered anchors and resources after each mount.

The completed
[research brief](../../research/research-2026-08-13-markdown-link-navigation.md)
compares CommonMark, GitHub, GitLab, VS Code, MkDocs, Docusaurus, Jekyll, and Obsidian.
Its decision addendum establishes GitHub-compatible exact resolution as the automatic
baseline and wiki-link parsing as a later adapter.

## Design

### Compatibility Contract

For standard rendered Markdown, the authored destination is interpreted in this order:

1. Split the destination into scheme or authority, path, query, and fragment without
   decoding it more than once.
2. Preserve safe explicit external URLs as external.
   Treat a protocol-relative target such as `//example.com/file` as external, not as a
   served-root path.
3. Keep an empty path on the current file.
   Resolve a leading single `/` from the served root; otherwise resolve from the source
   file’s directory.
4. Normalize `.` and `..`, rejecting traversal above the served root, encoded
   separators, NUL bytes, and backslash traversal.
5. Preserve exact case and do not add candidates for ordinary Markdown.
6. Produce a typed result: internal, external, missing, unsafe, or unsupported.
7. Give an internal navigation target a segment-encoded `/view/...` `href`. Give an
   embedded local resource a safe `/raw?path=...` URL.

Reference-style links require no special branch after KPress has produced their final
`href`. A link to a folder opens the folder; it does not choose a README. A query is not
part of the filesystem lookup and is preserved for URL compatibility even when
Metabrowser does not interpret it.

The common mappings from `docs/current.md` are:

| Authored target | Result |
| --- | --- |
| `other.md` | `/view/docs/other.md` |
| `./other.md#setup` | `/view/docs/other.md#setup` |
| `../README.md` | `/view/README.md` |
| `/CONTRIBUTING.md` | `/view/CONTRIBUTING.md` |
| `#configuration` | `/view/docs/current.md#configuration` without a refetch |
| `../images/map.svg` in an image | `/raw?path=images%2Fmap.svg` |
| `https://example.com/guide` | unchanged external URL |

### Canonical Route and History

The public route is:

```text
/view/<percent-encoded-served-root-relative-path>#<document-fragment>
```

Each path segment is encoded independently and `/` remains a separator.
`/view/` selects the served root.
Folders use a trailing slash after their type is known.
A direct safe GET returns the application shell so refresh and new tabs work; malformed
or escaping paths are rejected at the server boundary before the shell is returned.

The `/view/` namespace is intentional.
A direct `/<path>` route would collide with `/api`, `/raw`, `/static`, plugin routes,
and arbitrary future application routes.
It would also make leading `/` destinations ambiguous between repository-root content
and the application origin.
Published-site routing belongs to a future adapter.

One focused strict browser module owns parsing, formatting, canonicalization, and legacy
migration. `app.js` remains the composition shell: it asks that module for the initial
path, calls the existing file-opening flow, and commits the route after the response
identifies a file or folder.

- User file or folder navigation uses `history.pushState`.
- Startup normalization, folder slash canonicalization, and legacy migration use
  `history.replaceState`.
- Back and forward use `popstate`; file selection no longer depends on `hashchange`.
- A fragment change within the current file does not fetch the file again.
- An old `/#<encoded-path>` URL is accepted and replaced with `/view/<path>` once.
  A hash that is only an in-document anchor is not reclassified as a file.
- The CLI emits `/view/<path>` when started with a selected path.

### Structured Navigation Boundary

The shell owns generic path navigation and exposes it through the public SDK. Existing
`mb.openPath(path, {viewId})` behavior remains source-compatible.
Its options gain optional `query` and `fragment` fields, and a new
`mb.hrefForPath(path, options)` helper formats the corresponding canonical `href`
without reaching into private `app.js` state.
History-driven restoration remains an internal shell concern; plugin-initiated
`openPath` calls push normal user-navigation entries.

Conceptually, the boundary carries these values:

```text
LinkIntent     = {syntax, sourcePath, authoredTarget, action}
ResolvedTarget = {status, path?, query?, fragment?, candidates?, reason?}
Navigation     = {path, query?, fragment?, viewId?, history?}
```

The Markdown plugin owns `LinkIntent` creation and dialect fallbacks.
Generic route formatting, file opening, history, and fragment delivery remain
consumer-agnostic shell capabilities.
The final DOM element always receives the canonical `href`; the plugin’s delegated
handler intercepts only an unmodified primary-button activation that the shell can open
in place.

### Rendered Markdown Integration

A focused module in the built-in Markdown plugin enhances each completed KPress mount:

- classify anchors and embedded-resource elements relative to `ctx.path`;
- replace resolvable local destinations with their canonical URLs;
- preserve safe external destinations and native `target`, `download`, and modifier
  behavior;
- delegate ordinary internal clicks to the public navigation method;
- mark unsafe targets accessibly and preserve the normal not-found state after an exact
  target is opened;
- map the active fragment to KPress’s GitHub-compatible heading IDs after asynchronous
  rendering; and
- return a disposer that removes listeners and pending work when the renderer is
  replaced.

The enhancement does not use a dynamic `<base>` element because that would also retarget
shell scripts, API calls, and unrelated resources.
It does not reach private shell globals.
Resource rewriting uses the existing safe raw endpoint and its compression and
containment behavior.

Exact local `href`s can be produced without scanning the repository.
Phase 1 does not preflight every link or add a batch endpoint: the existing file-open
request determines whether a selected target exists and presents the normal not-found
state.
This keeps documents with many links cheap to mount and keeps navigation available
while inventory coverage is incomplete.
Proactive broken-link reporting can later consume a bounded index without changing
resolution semantics.

### Obsidian Adapter

Phase 2 adds a Markdown-plugin parser for self-identifying wiki syntax.
It recognizes at least:

- `[[Note]]` and `[[Folder/Note]]`;
- `[[Note#Heading|Label]]`;
- heading and block subpaths represented in the structured fragment field; and
- `![[asset.png]]` as an embedded-resource intent.

The adapter parses with access to source syntax, before rendering discards escape and
code-context information.
A bounded Markdown-aware scanner or KPress syntax extension may emit inert link metadata
for the browser to decorate after sanitization; a regular expression over final HTML is
not sufficient. Code spans, fenced blocks, existing links, and escaped literals remain
unchanged. The resulting intents call the same resolver and navigation boundary as
standard anchors.

An explicit relative or vault-root path wins.
An optional `.md` suffix is allowed for notes.
A bare note name may use a bounded inventory-derived basename or path-suffix index, but
only a unique result navigates.
Multiple candidates produce an accessible ambiguous state that retains the candidate
paths; arbitrary inventory order never chooses a note.
Standard Markdown links continue to use exact resolution even in a vault.

Heading targets map to actual rendered IDs.
Block references require explicit block metadata and may land as unsupported until that
metadata exists; they must not scroll to a guessed paragraph.
Image and media wiki-embeds reuse the safe resource route.
Note transclusion and recursive embeds remain outside this plan.

### Components

| Component | Adjustment |
| --- | --- |
| Focused server route helper, registered by `server.py` | Serve the shell for safe `/view/{path:path}` requests and reject malformed or escaping targets with existing safe-path helpers. |
| `src/metabrowser/cli/serve.py` | Emit a segment-encoded `/view/<path>` startup URL instead of a file path in the hash. |
| New strict module under `src/metabrowser/static/` | Parse and format canonical routes, migrate legacy hashes, and define push, replace, and pop behavior. |
| `src/metabrowser/static/app.js` | Compose the route module with existing `selectFile` and remove file identity from the hash-routing heuristic. |
| `src/metabrowser/static/plugin_sdk.js` and `types.d.ts` | Extend `openPath` with query and fragment options and add `hrefForPath` while retaining existing calls. |
| New link modules under `src/metabrowser/builtin_plugins/markdown/` | Enhance standard KPress links and resources in Phase 1; preserve source context while parsing and resolving wiki-links in Phase 2. |
| Existing Markdown mount | Install link enhancement after async render and dispose it with the TOC and render controller. |
| Tests and fixtures | Add a machine-readable resolution matrix plus route, DOM, SDK, renderer-lifecycle, and integration coverage. |

All new browser modules enter the fully strict `tsconfig.json` project.
No file is added to the legacy allowlist.

### Security and Failure Behavior

- Every filesystem path remains beneath the configured served root after one decoding
  and normalization pass.
- The implementation reuses existing safe-path and raw-resource helpers rather than
  creating a parallel containment policy.
- Repository-root links cannot address `/api`, `/static`, plugin assets, or other
  application namespaces; they are interpreted as repository paths and then formatted
  beneath `/view/`.
- Unsafe schemes and root escapes retain visible text but have no active local
  destination. External `http`, `https`, `mailto`, and other explicitly allowed schemes
  follow the existing trust policy.
- Missing and ambiguous targets are not silently redirected.
  Their source target and reason remain available to keyboard and assistive-technology
  users.
- Obsidian lookup work is bounded by target count, path length, inventory size, and
  response size. It never performs an unbounded synchronous tree walk on a request path.

## API Changes

The browser URL contract gains `/view/{path:path}`. The public SDK extends
`openPath(path, options)` with optional query and fragment fields and adds
`hrefForPath(path, options)`. JSDoc and `types.d.ts` define the options once.
Existing `openPath(path)` and `openPath(path, {viewId})` calls remain unchanged.
Phase 1 adds no path-resolution endpoint.

No Markdown authoring syntax changes.
Standard links require no settings.
The Obsidian adapter activates only for parsed wiki syntax; `.obsidian/` detection may
provide vault context but cannot alter exact standard-link behavior.

## Implementation Plan

### Phase 1: GitHub-Compatible Navigation by Default

- [ ] Add the canonical `/view/` server route, strict route module, CLI URL, legacy-hash
  migration, folder canonicalization, and push, replace, pop, and fragment behavior.
- [ ] Extend `openPath` with query and fragment options, add `hrefForPath`, and preserve
  existing SDK calls.
- [ ] Add exact standard-link and embedded-resource enhancement to the built-in Markdown
  renderer, including canonical `href`s, safe raw-resource URLs, native click variants,
  asynchronous fragment scrolling, and disposal.
- [ ] Validate the default against a GitHub-style fixture repository and the full
  resolution matrix, then update user-facing browsing documentation.

Phase 1 is complete when a repository whose same-repository Markdown links work on
GitHub can be browsed through Metabrowser without configuration, and direct URLs,
reload, new tabs, and history produce the same selected file and fragment.

### Phase 2: Obsidian Wiki-Link Navigation

- [ ] Parse wiki-links and media wiki-embeds with source syntax context, leaving code,
  existing links, and escaped literals unchanged, then produce the shared structured
  intent.
- [ ] Add bounded unique-note lookup with exact-path precedence, optional `.md`,
  ambiguity results, and incomplete-index behavior.
- [ ] Map wiki heading targets to rendered anchors and represent unsupported block
  targets honestly.
- [ ] Reuse canonical navigation and safe-resource URLs for links and media, with
  renderer disposal and accessibility coverage.
- [ ] Validate against an Obsidian-style vault containing duplicate basenames, spaces,
  Unicode, headings, blocks, attachments, missing notes, and ambiguous notes.

Phase 2 is complete when supported `[[...]]` links select the same unique note and
heading an Obsidian user would expect, while ambiguous or unsupported cases remain
explicit and standard Markdown behavior is unchanged.

## Work Tracking

Epic `mb-yq1f` owns the plan.
Its implementation chain is:

1. `mb-ln8z` establishes canonical routes and the navigation SDK.
2. `mb-zm16` adds exact standard Markdown links and resources after `mb-ln8z`.
3. `mb-4pv4` proves the GitHub-compatible default after `mb-zm16`.
4. `mb-8qnd` adds wiki-link parsing and unique-note lookup after `mb-4pv4`.
5. `mb-08is` completes Obsidian anchors, media, and fixtures after `mb-8qnd`.

Each bead includes focused tests and must pass `make verify`; the dependencies protect
the stable route and standard-link baseline before dialect fallback is introduced.

## Testing Strategy

Create `tests/fixtures/markdown_link_resolution.json` with source path, syntax, authored
target, action, inventory, dialect, expected status, resolved path, query, fragment, and
canonical URL. The same cases should drive pure resolver tests and focused DOM behavior
tests where possible.

Coverage includes:

- bare, dot, parent, root, folder, fragment-only, query, reference-style, raw-HTML,
  image, and external targets;
- spaces, Unicode, literal percent, `#`, and `?`, encoded separators, double-decode
  attempts, backslashes, traversal, symlinks, case mismatches, missing paths, and
  reserved route names;
- direct `/view/` GET, CLI startup URL, legacy hash migration, reload, new tab,
  same-document fragments, asynchronous render completion, and back and forward;
- primary, modifier, middle, keyboard, `target`, and download activation behavior;
- KPress mount replacement, listener disposal, aborts, and no stale fragment scroll;
- unique, duplicate, relative, vault-root, heading, block, attachment, and embed wiki
  targets in Phase 2; and
- bounded behavior with incomplete inventory and a document exceeding the Phase 2
  per-render wiki-link cap.

Use the repository’s Node DOM harness and pytest wrappers for pure and rendered
behavior, Starlette tests for direct routes and containment, and existing CLI golden
tests for startup URLs.
`make verify` is the required handoff gate for every bead.

## Rollout Plan

Ship Phase 1 as the default with no feature flag.
Exact standard resolution is narrower than guessing and legacy hash URLs remain
readable, so a user can move between versions without losing saved paths.
New navigation writes only `/view/` URLs.

Ship Phase 2 only after its unique-versus-ambiguous contract and bounded index behavior
pass. Wiki syntax is self-identifying, so it needs no global mode switch.
Site adapters remain opt-in or configuration-detected follow-ups and cannot change Phase
1 semantics.

## Acceptance Criteria

- Standard GitHub-style same-repository links and resources work automatically from
  nested Markdown files.
- Every selected file, folder, and heading has a canonical URL that survives direct load
  and normal browser navigation.
- Internal links expose final `href`s and preserve native non-primary click behavior.
- Exact failures, unsafe targets, and later Obsidian ambiguities are never hidden by a
  fuzzy fallback.
- The shell, SDK, and Markdown plugin retain their ownership boundaries, and every new
  renderer listener or pending operation has a tested disposal path.
- No route or resource read escapes the served root or aliases an application namespace.
- Phase-specific fixture, DOM, server, CLI, compatibility, and project-wide verification
  tests pass.

## Open Questions

There are no blocking product questions.
Proactive repository-wide broken-link reports, published-site route adapters, and
recursive Obsidian note embeds are separate future features rather than unresolved parts
of this plan.

## References

- [Markdown link navigation research](../../research/research-2026-08-13-markdown-link-navigation.md)
- [Development guide](../../../development.md)
- [Supply-chain security policy](../../../../SUPPLY-CHAIN-SECURITY.md)
- [GitHub basic writing and formatting syntax](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)
- [Obsidian internal links](https://obsidian.md/help/links)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
