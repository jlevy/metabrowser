# Feature: Directory File-Type Summary

**Date:** 2026-08-12

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser should give a directory the compact composition summary that makes GitHub’s
repository language panel useful, but should describe the files Metabrowser actually
indexes rather than infer programming languages.

The directory Overview view adds a collapsible **File types** panel above the
directory’s README. It renders two thin stacked bars over one shared set of logical file
types:

- **Files** shows each type’s share of the indexed file count
- **Size** shows each type’s share of indexed bytes

One structured list below the bars reports both absolute values and both percentages:

```text
.py     150 files (12%)      10 MB (30%)
.md      63 files (5%)        1 MB (3%)
```

The bars, legend marks, and rows use the same category order and colors, so the user can
compare how a type’s prevalence changes between count and size without learning two
encodings. The panel consumes the folder rollup’s extension tallies and live refresh
path. It starts no second filesystem crawl.

The feature generalizes the WIP folder-view design into an **Overview** view rather than
attaching directory chrome to a selected README file.
Selecting a directory opens its Overview, which contains the summary and then its
direct-child README when present.
Opening `README.md` itself continues to show only that file.
The Treemap remains a separate folder view.

## Goals

- Make count-heavy and byte-heavy file types visible at the same time
- Use Metabrowser’s indexed logical file types, including documents, data, images,
  source, archives, and extensionless files
- Preserve GitHub’s useful visual grammar: a compact stacked bar, stable category
  colors, a neutral Other segment, and a nearby text legend
- Fit the summary into Metabrowser’s panel, typography, color-token, filter, lifecycle,
  light-theme, dark-theme, and print contracts
- Make the served root and every selected nested directory follow the same Overview
  contract
- Reuse `/api/rollup`, `ext_tallies`, `watchRollup`, and the existing inventory event
  stream, with a bounded tally-only response
- Keep partial, truncated, empty, zero-byte, and failed states honest
- Keep the panel optional without adding another Settings-menu preference: it is an
  expanded-by-default disclosure whose state persists through `mb.prefs`

## Non-Goals

- Programming-language detection, GitHub Linguist compatibility, MIME sniffing, or
  content inspection
- Linguist-style generated, vendored, documentation, or language-detectability rules;
  Metabrowser uses its existing inventory and ignored-path semantics
- Allocated disk blocks or decompressed content size; Size uses the inventory’s existing
  `st_size` value
- Replacing the Treemap or duplicating its hierarchy, age, and spatial controls
- Making an explicitly opened README file depend on its parent directory’s rollup
- Clicking a type row to search, navigate, or mutate the global type filter in the first
  release
- A user-selectable sort control, arbitrary metrics, or one bar per filter dimension
- A root-only shell special case while directory views are unavailable

## Background

### What GitHub Gets Right

Reviewed against GitHub’s repository UI on 2026-08-12. GitHub’s current repository
sidebar uses an 8-pixel stacked bar with a 2-pixel gap, clipped ends, stable language
colors, and a compact wrapped legend.
Each segment carries an accessible language-and-percentage label.
The visible percentages are based on bytes, not file count; GitHub’s language API
likewise reports the number of bytes attributed to each language.

The useful pattern is the correspondence among bar segment, color mark, label, and
percentage. The language classifier and its exclusions are not the pattern Metabrowser
needs. Metabrowser browses arbitrary local trees, so `.md`, `.jsonl`, `.png`, and an
unknown extension belong in the same summary as `.py`.

GitHub can place the summary in a repository sidebar because its page already reserves
that rail. Metabrowser already combines a 300-pixel navigator with KPress’s optional
document TOC, so copying the placement would create a cramped third column.
The familiar grammar belongs in the preview’s document measure instead.

Two changes make the pattern more useful for a file browser:

1. Count and byte share get separate bars because they answer different questions.
2. The rows retain absolute counts and sizes, so the visualization never hides the
   underlying quantities.

### Existing Metabrowser Seams

The folder-view work in the draft pull request already defines the needed data and live
lifecycle:

- `InventoryIndex.rollup` computes subtree totals plus `ext_tallies` rows containing
  all-file and unignored file counts and byte totals
- `/api/rollup` bounds depth, children, total emitted nodes, and extension rows while
  reporting scanning and truncation state
- `mb.watchRollup` fetches once, refreshes after relevant inventory events, supports an
  active-view gate, and provides disposal
- the folder plugin owns directory views and already composes a direct-child README
  through the built-in Markdown renderer
- `mb.filters` owns the shared **Show ignored** state

The current main branch still opens a root README as a file because the folder-view pull
request has not merged.
This plan targets the folder-view contract and does not add a temporary root-only
implementation to the shell.

The existing rollup chooses extension rows by byte rank.
That is sufficient for one size-based chart but not for two metrics: a type represented
by thousands of tiny files can be important in the Files bar and absent from a
byte-ranked top set.
The data selection must account for both dimensions before the UI is trustworthy.

## Design

### Resolved Decisions

1. **The feature is a folder Overview, not README decoration.** The folder plugin
   exposes `Overview` and `Treemap`. Overview is the default and renders the file-type
   summary followed by a direct-child README when one exists.
   An explicitly selected README remains an ordinary Markdown file view with no
   directory summary.
2. **Overview exists without a README.** A README-less folder still has useful
   composition data, so its Overview contains the summary without a redundant “No
   README” panel. An empty indexed directory gets one explicit empty state.
3. **File type means the canonical indexed extension in version one.** The summary uses
   the same `FsEntry.ext` key as the type filter: lower-case leading-dot extensions such
   as `.py` and `.md`, including canonical compound tails such as `.tar.gz`. It does not
   unwrap compressed files or infer from contents.
   Dotfiles and other extensionless names join **No extension**. Directories and
   symlinks do not contribute to file or byte totals.
4. **Both bars use one category set, order, and color map.** A type never moves to a
   different horizontal position merely because the metric changes.
   Rows use that same order.
   `Other` is always last and neutral.
5. **Category selection protects both metrics and both ignored-file scopes.** The server
   scores each type by its greatest share across all-file count, all-file bytes,
   unignored count, and unignored bytes.
   It keeps the top ten scores and aggregates the remainder into Other.
   A type that matters in any rendered state therefore cannot be hidden merely because
   another metric selected the rows.
   The browser omits a named row only when both of its active-scope values are zero; its
   palette slot remains reserved if the ignored-file scope later makes it visible.
6. **There is no sort toggle.** Rows retain the server’s deterministic maximum-share
   order defined below.
   A control that reorders one bar independently would break cross-bar comparison; a
   control that reorders both adds work without adding a new answer.
7. **Show ignored is the one shared filter that changes the summary.** When it is on,
   the panel uses all-file columns; when it is off, it uses unignored columns.
   The scope text says **Including ignored** or **Ignored excluded** when ignored files
   exist. Recency, type, and size filters do not change the directory composition
   summary: applying `.py` and making the panel report 100% `.py` would destroy its
   purpose.
8. **The panel is expanded by default and collapsible.** Its disclosure state persists
   across roots under the versioned preference `folder.fileTypeSummary.open`. A
   collapsed panel keeps a one-line header with total files and bytes, so hiding the
   detail does not create an unexplained blank above the README.
9. **Category colors belong to aggregate visualizations.** The tree’s existing `ft-*`
   colors identify broad rendering subtypes; several exact extensions intentionally
   share one tree color.
   Adjacent stacked-bar segments need distinct categorical colors, so the design system
   gains a bounded distribution palette.
   A folder-view session assigns displayed logical types to distinct slots and retains
   those assignments across live updates.
   The file-type-grouped Treemap uses the same map when both views are mounted.
   Labels remain plain text, and Other uses a neutral token.
10. **The bars are visual summaries; the table is authoritative.** Bars do not become
    tab stops or carry tooltips that duplicate the rows.
    Each bar has one accessible text alternative, and the semantic table supplies every
    exact value. Color is never the only path to the data.
11. **The summary is a sibling panel in the document measure.** When a README exists,
    the Markdown bridge gives folder Overview a host-chrome lead slot in KPress’s
    document column. The summary and README card have the same outer width and a small
    vertical gap; one is not boxed inside the other.
    At the wide document band, the TOC starts beside the README row below the summary
    rather than beside unrelated file statistics.
    The panel uses the host sans face and panel tokens, not KPress prose typography.
12. **Directory chrome does not print.** The panel carries the same no-print contract as
    other host controls.
    Printing Overview prints the README when present; the directory summary does not
    become part of the document.
13. **Known partial data is useful but labelled.** During scanning, the panel renders
    percentages over indexed-so-far data and shows a quiet progressive status.
    On terminal truncation it retains a persistent scope warning.
    It never turns a pending rollup into an empty directory.
14. **One watch belongs to each mounted summary.** It uses `watchRollup` with the view’s
    active gate, aborts in-flight work on disposal, and updates keyed rows in place.
    Hidden lazy views do not keep polling, and updates do not replace the focused
    disclosure control.

### Information Architecture

The folder tabs become:

```text
OVERVIEW   TREEMAP
```

Overview is a composite directory view:

```text
┌ FILE TYPES     1,250 files · 33.3 MB                    ▴ ┐
│ Files  ████████████████████████▉▉▉▉▉░░░░                 │
│ Size   ███████████████▉▉▉▉▉▉▉▉▉▉▉▉▉▉░░░                 │
│                                                            │
│ Type                 Files                     Size         │
│ ● .py          150 files (12%)            10 MB (30%)      │
│ ● .md           63 files (5%)               1 MB (3%)      │
│ ● Other         23 files (1.8%)          400 KB (1.2%)     │
└────────────────────────────────────────────────────────────┘

# Directory README title
README content…
```

The drawing shows structure, not exact color or dimensions.
The implementation uses two 8-pixel tracks, a 2-pixel track-colored separation between
segments, the app’s panel border, and existing type-scale and spacing tokens.
The track height and segment gap become named Aggregate distributions component tokens
rather than use-site literals.

The header contains four roles and no repeated sentence:

- the small-caps label **File types**
- optional muted scope text when ignored files exist
- total file count and byte size in tabular numerals
- the disclosure mark and accessible expanded state

### Tallies and Percentages

The rollup wire row remains compatible with the folder-view work:

```text
[extension_key, all_files, all_bytes, unignored_files, unignored_bytes]
```

The browser normalizes it immediately into a typed object.
It never indexes array positions throughout rendering code.
The server retains `(none)` as the no-extension key and the empty string as the Other
sentinel. The normalization boundary maps those distinct wire values to **No extension**
and **Other**; presentation code never guesses from falsiness.

For the active ignored-file scope:

```text
file_percent = type_files / total_files
byte_percent = type_bytes / total_bytes
```

Percentages are calculated from integer totals before display rounding.
Formatting uses the user’s locale with at most one decimal place:

- exact zero is `0%`
- a positive value below `0.1%` is `<0.1%`
- values at or above `0.1%` use up to one decimal place

Displayed percentages do not need to sum to exactly 100% after rounding.
The Other row ensures the underlying integer totals do sum to the directory totals.

Segments use their unrounded integer count or byte value as a flex weight after the
fixed gaps are subtracted from the track.
They do not use rounded percentage widths or a minimum width that would exaggerate small
categories. Subpixel categories remain available through their row.

The SDK’s existing `formatSize` and an additive SDK count formatter own absolute
formatting and singular/plural copy.
Before reuse here, the shared byte formatter gains GB, TB, and PB bands while preserving
its existing B, KB, and MB output; a directory total must not degrade into thousands of
MB. The Size column keeps the existing byte-count color treatment; percentages use muted
text.

### Category Selection and Other

For each type, calculate four comparable shares using their respective population
totals:

```text
score = max(
  all_file_share,
  all_byte_share,
  unignored_file_share,
  unignored_byte_share,
)
```

A share with a zero population total is zero.
For deterministic tie-breaking, define `byte_score` as the greater all/unignored byte
share and `file_score` as the greater all/unignored file share.

The top ten types by descending `score`, `byte_score`, `file_score`, then normalized key
become named rows. Every omitted type contributes to one Other row in all four integer
columns. **No extension** is a normal named type and can enter the top ten; it is not
Other. The browser omits an all-zero Other row in the active scope.

This selection happens before serialization so the response stays bounded.
The selection must be covered with a fixture where one extension dominates bytes and a
different extension dominates count.
Byte-only ranking is not an acceptable approximation.

### Distribution Color Contract

Add twelve light/dark categorical tokens plus a neutral Other token under a documented
**Aggregate distributions** section in the design system.
Consumers address palette slots through classes, never literal colors or inline color
custom properties. Inline unitless flex weights remain permitted because they encode
data, not theme.

The folder summary maintains an `extension_key -> palette_slot` map:

- existing displayed types keep their slot across live updates
- a new type takes the next unused slot from a deterministic key-derived starting point
- a removed type’s slot stays reserved for the mounted view so its return does not
  recolor the panel
- navigating to a different directory starts a new mapping
- Other always uses the neutral token

The palette assignment is scoped to one directory comparison.
This guarantees distinct visible segments without pretending an open-ended extension
vocabulary has a universal color standard.
When the type-grouped Treemap and Overview coexist for a directory, they share the map.

Every segment is separated by the track color, every row repeats a small color mark, and
the adjacent text names the type.
Similar colors or color-vision differences do not remove information.

The Aggregate distributions contract documents this mark as a deliberate alternative to
the broad file-type icon used in navigation and filters.
Here the mark’s job is to join one exact-extension row to its bar segments; a broad icon
shared by several extensions cannot provide that link.
Labels, counts, and status copy remain in the host sans face.

### Responsive Layout

The panel follows the README prose measure and uses container queries against the
preview pane, not window media queries.

- At ordinary widths, the semantic table has `Type`, `Files`, and `Size` columns;
  numeric columns align right.
- At narrow widths, each type becomes a two-line grid row: the type spans the row and
  Files and Size sit below it.
  The bars keep their labels and full remaining width.
- Long or synthetic type labels wrap within the first column; they never widen the
  preview or create a nested scroll owner.
- The collapsed header may wrap its totals, but the disclosure remains a full-size
  target.

### Loading, Empty, Partial, and Failure States

The panel supports these states explicitly:

| State | Presentation |
| --- | --- |
| Initial request | Header and two neutral skeleton tracks; delayed text says “Loading file types…” only when the request remains visible |
| Scanning with rows | Render current rows and say “Scanning… percentages cover files indexed so far.” |
| Complete | Remove progress copy; bars and rows are final for the current inventory snapshot |
| Truncated | Keep rows and a persistent warning with indexed and configured-cap counts |
| Empty complete directory | “No files in this directory.” with no empty bars or table |
| All files are zero bytes | Render the Files bar normally; Size shows a neutral zero track and `0 B` values |
| Request failure | “Could not load file types.” plus one Retry action; the live watch remains able to recover |

Progress and completion copy use the design system’s state language.
Routine live count changes are not announced.
The transition from loading or scanning to a terminal state uses one polite status
announcement.

### Overview and Markdown Composition

The folder plugin changes its `readme` view to `overview` and labels it **Overview**. It
always advertises Overview because the summary does not depend on README presence.
Overview is the default folder view; Treemap remains lazily mounted.

The Markdown built-in gains one narrow composition helper that can mount host-owned DOM
in a lead slot above, and aligned with, the KPress prose card after rendering and
document-meta hoisting.
The lead slot and prose card occupy successive rows of the document column.
At KPress’s wide band, the TOC occupies the prose row; at narrower bands the panel and
document stack in the existing single-column flow.

The lead slot is not `.metabrowser-doc-meta`: frontmatter and diagnostics remain inside
the README card under their existing contract, while the File types panel keeps its own
border as directory chrome.
The helper owns this KPress DOM and grid knowledge; the folder plugin does not copy
selectors or reach into private shell globals.
It returns a disposal function for mounted host content.

When `readme_path` is absent, the folder plugin renders the summary in a centered
overview measure using the same content padding.
It does not instantiate an empty KPress document merely to borrow layout.

Changing folders disposes the summary watch, filter subscription, Retry handler, and any
Markdown TOC state.
Switching between Overview and Treemap follows the existing lazy view
lifecycle.

### Accessibility and Interaction

- The disclosure uses a native `<details>` and `<summary>` contract or an equivalent
  button with `aria-expanded`; its full header is keyboard operable.
- Each bar is a labelled figure whose concise accessible description identifies the
  metric and points to the exact values in the following File types table.
  Individual visual segments are hidden from the accessibility tree to avoid repeating
  that table.
- The table has real headers and no interactive rows in version one.
- Category marks are decorative because the type text names every row.
- Counts use locale formatting, correct singular/plural copy, and tabular numerals.
- Focus is not moved during scan or live updates.
- `prefers-reduced-motion` disables segment-width interpolation; all data updates
  immediately.
- Light and dark palette tokens are reviewed as marks on their actual track and panel
  surfaces. No text is placed on a category color.

## API Changes

No new endpoint or filesystem pass is required.

Extend the folder rollup contract as follows:

- allow `depth=0` and `top=0` on `/api/rollup`; the response retains the root totals and
  `ext_tallies` but emits no child nodes
- accept `ext_rank=dual` and select named extension tallies by the four-share score
  rather than bytes alone; the existing default remains byte-ranked until every in-tree
  consumer adopts the dual ranking
- retain the current compact row shape and explicit Other sentinel
- retain both all-file and unignored columns in one response so **Show ignored** changes
  presentation without a refetch
- retain `index_status`, `indexed_files`, `max_files`, and `truncated`
- expose the shell’s count formatter through the SDK alongside `formatSize`, and make
  the shell and SDK share one byte formatter with bounded GB, TB, and PB output, so
  folder plugins do not duplicate locale, unit, or pluralization rules

`mb.fetchRollup` and `mb.watchRollup` accept the zero-depth options without replacing
their existing defaults.
The summary requests ten named types.
The browser module gives that product limit and the palette size named constants rather
than repeating numeric literals.
Treemap callers may keep their current depth and node budgets while adopting the same
dual-metric tally ranking.

The browser adds a strict module responsible for:

- validating and normalizing tally rows
- choosing active all/unignored values
- calculating shares and display strings
- maintaining category slots across updates
- rendering and updating the summary markup
- mounting, retrying, subscribing, and disposing through explicit methods

The module uses supported SDK helpers for rollups, filters, preferences, formatting, and
folder-view lifecycle.
It does not access private `app.js` state.

## Backward Compatibility

- **Internal code types, methods, and function signatures: DO NOT MAINTAIN.** Do not
  retain deprecated internal wrappers while refactoring the WIP folder plugin.
  Keep the rollup row normalization boundary explicit.
- **Plugin SDK: KEEP DEPRECATED.** Preserve existing `fetchRollup` and `watchRollup`
  options and response fields.
  Zero-depth support and the document-composition helper are additive; this plan
  deprecates no existing SDK member.
- **Server API: KEEP DEPRECATED.** Preserve `/api/rollup` field names and compact tally
  rows. The dual-metric ranking is opt-in until every in-tree consumer adopts it; then it
  may become the documented default in the same release.
- **File formats: N/A.**
- **Database schemas: N/A.**

## Implementation Plan

### Phase 1: Dual-Metric Rollup and Summary Primitive

- [ ] Rebase or land the folder envelope, rollup route, SDK watcher, and folder plugin
  prerequisites from the folder-view work
- [ ] Extend rollup bounds to allow a root-and-tallies response with no emitted children
- [ ] Implement four-share type selection, stable Other totals, and all/unignored parity
- [ ] Add typed wire validation and fixtures for byte-heavy, count-heavy, ignored-heavy,
  extensionless, compound-extension, zero-byte, scanning, and truncated cases
- [ ] Add aggregate-distribution tokens and the exact-type category resolver, and route
  type-grouped folder visualizations through it
- [ ] Implement the strict summary module with percentage formatting, keyed updates,
  collapse persistence, Retry, active gating, and disposal
- [ ] Add the Aggregate Distributions component contract to the design system

### Phase 2: Folder Overview Integration and Browser Validation

- [ ] Replace the conditional folder README view with an always-present Overview view
  and make Overview the default
- [ ] Add the Markdown composition helper and mount the summary as a document-column
  sibling above the README card without changing an explicitly opened Markdown file
- [ ] Render the measured standalone Overview layout when no README exists
- [ ] Synchronize **Show ignored**, retain directory-wide behavior for the other filter
  dimensions, and expose scope copy only when it carries information
- [ ] Validate live addition, removal, type change, scan completion, truncation, folder
  navigation, lazy tab activation, and view replacement
- [ ] Validate wide and narrow panes, light and dark themes, reduced motion, keyboard
  and screen-reader structure, and print output in a real browser
- [ ] Run `make verify` and review the built wheel for the new folder assets

## Testing Strategy

### Server and Inventory

- One fixture makes `.bin` dominate bytes and `.txt` dominate count; both must survive
  the named-row cap.
- Separate fixtures make a type significant only in the all-file population and only in
  the unignored population; toggling scope must not turn either into an unreported type.
- Other’s four integer columns must equal the omitted rows exactly.
- Logical extension tests cover case normalization, canonical compound names, dotfiles,
  extensionless files, and no symlink contribution.
- Route tests pin zero-depth bounds, safe-path rejection, pending index behavior,
  terminal truncation metadata, and bounded response size.

### Browser Module and DOM

- Pure tests cover percent formatting boundaries, zero denominators, count
  pluralization, byte-unit boundaries, maximum-share ordering, stable color slots,
  Other-last behavior, and malformed rows.
- DOM tests assert identical category order and slot classes across both bars and the
  table, real table headers, accessible bar alternatives, disclosure persistence, and
  escaped labels.
- Lifecycle tests assert one active watch, no hidden-view refresh, abort and listener
  cleanup on disposal, Retry recovery, and focus preservation during keyed updates.
- Filter tests assert that **Show ignored** changes the selected integer columns while
  recency, type, and size filters leave the composition unchanged.
- Composition tests assert that folder Overview gets the panel as a sibling above the
  README card, the wide-band TOC starts on the README row, directly opened Markdown does
  not get the panel, README-less Overview avoids a fake empty document, and print hides
  the panel.

### Real-Browser Review

Use directories representing one type, ten types, more than ten types, thousands of tiny
files, one dominant binary, ignored dependency trees, no README, a long README TOC, and
an empty directory. Review ordinary and narrow preview widths in both themes.
Confirm that the panel reads as directory chrome, the README remains visually primary,
the two bars can be compared without consulting color alone, and ignored-state changes
do not trigger a new rollup request.

## Risks and Mitigations

- **The panel competes with the README.** It stays compact, collapsible, inside the
  document measure, and remembers collapse state.
  It has no shadow or oversized heading.
- **Byte ranking hides count-heavy types.** The server selects categories using the
  maximum of both metrics and both ignored-file populations.
- **Ignored dependencies dominate.** The panel follows the existing Show ignored state,
  makes its scope explicit, and already has both populations on the wire.
- **Colors drift during live updates.** The mounted view reserves slots for its lifetime
  and updates keyed rows rather than rebuilding rank-colored markup.
- **Arbitrary extensions exhaust the palette.** The visible named set is capped at ten
  against twelve slots; the unbounded tail is one neutral Other row.
- **The summary duplicates the Treemap.** Overview answers composition with exact
  totals; Treemap answers spatial hierarchy and navigation.
  They share data and type colors but not controls or layout.
- **KPress DOM changes break injection.** One Markdown-owned composition helper contains
  the selector knowledge and has contract tests.
  The folder plugin calls the helper rather than querying KPress internals.
- **Partial scans look final.** Scanning and truncation remain visible beside the data,
  and pending never renders as empty.

## Rollout Plan

Land this with the folder-view work or immediately after its rebase onto current main.
Do not ship a root-only README decorator as an intermediate state.

The rollout is additive to the rollup endpoint and folder plugin.
Existing file views, explicit README deep links, and print behavior remain unchanged.
The first visit opens the panel; a user who collapses it keeps that preference across
served roots. No data migration is required.

The Overview-default decision supersedes the WIP folder plan’s Treemap-default and
conditional-README-tab decisions.
Record that change in the folder plan when the two branches are reconciled so there is
one final folder-view contract.

## Open Questions

No product decision blocks implementation.
Real-browser review should still test one judgment call: whether the expanded-by-default
panel remains appropriately quiet in a README-less directory.
If it does not, change the default only for that case; do not add a Settings-menu toggle
or make the served root behave differently from nested folders.

## Acceptance Criteria

- A selected directory opens Overview with a collapsible File types panel and its
  direct-child README below it when present
- An explicitly opened README has no directory summary
- The panel shows Files and Size bars with the same named types, order, colors, and
  neutral Other segment
- Each row shows logical type, absolute file count, file percentage, formatted bytes,
  and byte percentage
- A count-heavy type and a byte-heavy type both survive the top-ten bound
- No extension is a named group, and compound extensions use their canonical indexed
  type
- Show ignored switches the panel between the two rollup populations without refetching;
  other filters do not collapse the composition
- Scanning, truncation, empty, zero-byte, and failure states are distinguishable and
  truthful
- The panel updates from inventory changes, retains category colors and disclosure
  focus, and disposes every watcher and listener on view replacement
- The layout works at narrow and wide preview widths in light and dark themes, remains
  usable without color or motion, and does not print with the README
- The implementation performs no second filesystem crawl and stays within the existing
  rollup response and node budgets
- `make verify` passes

## References

- [GitHub repository language panel](https://github.com/jlevy/metabrowser)
- [GitHub Linguist](https://github.com/github-linguist/linguist)
- [GitHub GraphQL language-byte contract](https://docs.github.com/en/graphql/reference/objects#languageedge)
- [Design system](../../../design-system.md)
- [Architecture](../../../architecture.md)
- [Filter controls and fine-grained navigation filtering](../done/plan-2026-08-09-nav-filter-controls.md)
- [Folder views, Treemap, and unified filtering](https://github.com/jlevy/metabrowser/pull/23)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
