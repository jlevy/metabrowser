# Feature: Folder Overview Panels and File-Type Summary

**Date:** 2026-08-12

**Author:** Metabrowser maintainers

**Status:** Complete

## Overview

Metabrowser should make every folder a useful destination, not merely a container that
redirects to a README or one specialized visualization.
Selecting a folder opens an **Overview** tab composed from independent, ordered panels.
The built-in **Files** and **File Breakdown** panels are always present, a direct-child
README contributes a document panel when one exists, and future capabilities such as
License can contribute their own panels without rewriting Overview.

File Breakdown adopts the compact proportional grammar that makes GitHub’s repository
language panel useful, but describes the files Metabrowser actually indexes rather than
inferring programming languages.
One selected Files or Bytes metric drives every folder rollup view.
The structured table groups rows under the File Rollup Format groups and shows an
absolute value, a bar normalized to the selected population, and a percentage.

For example:

```text
FILES
Files      250 files  ████████████████████████████████████████
Ignored     18 files  ████████████████████████████████████████

FILE BREAKDOWN
CODE
Python     150 files  ████████████████████████                 60%

DOCUMENTATION
Markdown    63 files  ██████████                               25.2%
```

The Files and Ignored tracks are separately normalized compositions segmented by the
same stable file-type colors used below.
Files means unignored files; Ignored is the excluded population.
Group headings add scan structure but no new aggregation.
The panel consumes the folder rollup’s extension tallies and live refresh path.
It starts no second filesystem crawl.
An empty folder still has Overview and File types; the panel shows a concise empty state
instead of zero-length row fills or a blank surface.

Overview is one folder-level view, not a replacement for the view model.
Treemap remains a peer tab, and a future Files listing would also be a peer tab because
it changes the folder’s primary mode.
README, License, and similar summaries are Overview panels because they form one
scannable account of the selected folder.
Opening `README.md` itself continues to show only the ordinary Markdown file view.

## Goals

- Make count-heavy and byte-heavy file types easy to compare through one shared,
  immediately switchable metric
- Use Metabrowser’s indexed logical file types, including documents, data, images,
  source, archives, and extensionless files
- Preserve GitHub’s useful visual grammar of proportional bars and stable category
  colors while adapting it to a vertically scannable table for many file types
- Fit the summary into Metabrowser’s panel, typography, color-token, filter, lifecycle,
  light-theme, dark-theme, and print contracts
- Establish one supported, deterministic folder Overview panel registry so built-in and
  installed plugins can add independently available panels without coupling to sibling
  panels or private shell state
- Make the served root and every selected nested directory follow the same Overview
  contract
- Keep top-level folder modes distinct from Overview content: Overview and Treemap are
  peers now, and a future Files listing can join them without becoming an Overview panel
- Reuse `/api/rollup`, `ext_tallies`, `watchRollup`, and the existing inventory event
  stream, with a bounded tally-only response
- Keep partial, truncated, empty, zero-byte, and failed states honest
- Keep Files, File Breakdown, and README compact, document-aligned sections with the
  same visible heading hierarchy; Files and README begin expanded and File Breakdown
  begins collapsed

## Non-Goals

- Programming-language detection, GitHub Linguist compatibility, MIME sniffing, or
  content inspection
- Linguist-style generated, vendored, documentation, or language-detectability rules;
  Metabrowser uses its existing inventory and ignored-path semantics
- Allocated disk blocks or decompressed content size; Size uses the inventory’s existing
  `st_size` value
- Replacing the Treemap or duplicating its hierarchy, age, and spatial controls
- Implementing the future Files tab, a License panel, or a general-purpose dashboard
  layout in this release
- Making an explicitly opened README file depend on its parent directory’s rollup
- Clicking a type row to search, navigate, or mutate the global type filter in the first
  release
- A user-selectable sort control, arbitrary metrics, or additional filter dimensions
- A root-only shell special case while directory views are unavailable

## Background

### What GitHub Gets Right

Reviewed against GitHub’s repository UI on 2026-08-12. GitHub’s current repository
sidebar uses an 8-pixel stacked bar with a 2-pixel gap, clipped ends, stable language
colors, and a compact wrapped legend.
Each segment carries an accessible language-and-percentage label.
The visible percentages are based on bytes, not file count; GitHub’s language API
likewise reports the number of bytes attributed to each language.

The useful pattern is the correspondence among proportional bar, label, and percentage.
The language classifier and its exclusions are not the pattern Metabrowser needs.
Metabrowser browses arbitrary local trees, so `.md`, `.jsonl`, `.png`, and an unknown
extension belong in the same summary as `.py`.

GitHub can place the summary in a repository sidebar because its page already reserves
that rail. Metabrowser already combines a 300-pixel navigator with KPress’s optional
document TOC, so copying the placement would create a cramped third column.
The familiar grammar belongs in the preview’s document measure instead.

Three changes make the pattern more useful for a file browser:

1. Count and byte share get separate inline bars on every row because they answer
   different questions.
2. Documentation, Code, Data, and Other row groups reuse the navigation-preset
   vocabulary to make a longer list easier to scan without inventing group totals.
3. The rows retain absolute counts and sizes, so the visualization never hides the
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
- the folder plugin owns directory views and already delegates a direct-child README to
  the built-in Markdown renderer
- folder rollup controls own one shared Files / Bytes metric and **Show ignored** scope
  for Overview and Treemap

The WIP folder plugin currently hard-codes README as one folder view.
The current main branch still opens a root README as a file because that work has not
merged. This plan targets the folder-view contract, replaces the hard-coded composition
with an Overview panel registry, and does not add a temporary root-only implementation
to the shell.

The existing rollup chooses extension rows by byte rank.
That is sufficient for one size-based chart but not for two metrics: a type represented
by thousands of tiny files can be important in the Files column and absent from a
byte-ranked top set.
The data selection must account for both dimensions before the UI is trustworthy.

## Design

### Resolved Decisions

1. **Folder views and Overview panels solve different problems.** Overview and Treemap
   are peer folder tabs.
   A future Files listing is another peer tab because it is a primary mode, not a
   summary card. README, File types, and a future License summary are panels inside
   Overview.
2. **Every folder has Overview, and Overview is the default.** The served root and a
   selected nested folder follow the same rule.
   Overview does not depend on README, rollup completion, or nonempty contents.
3. **Overview is an ordered panel registry, not a hard-coded template.** Built-in and
   installed plugins register self-contained contributions through a supported SDK
   surface. The composer owns availability, ordering, layout, loading, failure isolation,
   and disposal; a panel does not query or position its siblings.
4. **Totals and the detailed file-type distribution are separate panels.** The required
   `folder.file-totals` panel is headed Files, starts expanded, and owns the shared
   Files / Bytes chooser plus immediate Files and Ignored rows.
   The required `folder.file-types` panel is headed File Breakdown, starts collapsed,
   and owns the full type distribution plus Show ignored.
   Both panels observe one folder-rollup state, so File Breakdown does not repeat the
   metric chooser. A complete folder with no indexed regular files renders “No files to
   summarize.” with no bars, percentages, table, or README-shaped placeholder.
   Pending inventory never masquerades as this empty state.
   A completed inventory that cannot serve an existing path renders “This folder is not
   in the current file index.”
   rather than leaving a loading skeleton visible.
5. **README is conditional and visually ordinary.** A direct-child README contributes a
   document-presentation panel only when it exists.
   Its content, metadata, diagnostics, TOC, responsive behavior, and print output come
   from the same built-in rendered Markdown mount used for an explicitly opened Markdown
   file. Overview adds its shared README section heading but no decorative wrapper around
   the document renderer.
   An explicitly selected README remains an ordinary Markdown file view with no
   directory summary.
6. **The population is the selected folder’s indexed subtree.** That matches GitHub’s
   repository-level usefulness and the existing rollup, rather than counting only direct
   children. Within that population, file type means the same `FsEntry.ext` key as the
   type filter: lower-case leading-dot extensions such as `.py` and `.md`, including
   bounded compound tails such as `.tar.gz`. It does not unwrap compressed files or
   infer from contents.
   Dotfiles and other extensionless names join **No extension**. Directories and
   symlinks do not contribute to file or byte totals.
7. **One selected metric controls every file rollup display.** The Files / Bytes chooser
   in Files switches the totals, File Breakdown, and Treemap together.
   Each File Breakdown row has one absolute value, normalized bar, and percentage.
   Files and Ignored each have one absolute value and a full-width composition track,
   because each row defines its own 100% population.
   A type keeps the same color when the selected metric changes, and the rollup-tail
   Other row remains neutral.
   The two composition tracks follow the breakdown’s registry group order and selected-
   metric rank within each group.
8. **The server preserves the complete semantic category population.** Known families
   retain their contributing extensions.
   No extension basenames and unknown exact extensions use independently bounded
   fallback lists with exact Others rows.
   The browser applies a consistent 10-row presentation bound with an expandable N more
   row rather than dropping data from the model.
9. **There is no separate sort toggle.** Rows sort descending by the active Files or
   Bytes metric. The other metric and stable row identity provide deterministic
   tie-breakers, so the ordering changes only when the selected comparison changes.
10. **Show ignored changes the detailed population, not its context.** The shared
    labelled checkbox starts checked when no preference exists.
    Unchecking it switches File Breakdown and Treemap to unignored data.
    It also sorts both top composition tracks against the same active breakdown
    population, while retaining one shared segment order across the Files and Ignored
    rows. The explicit Files and Ignored totals remain disjoint and visible in either
    scope. Recency, type, and size navigation filters do not change the directory
    composition summary.
11. **Overview sections declare their own initial disclosure state.** Files and README
    start expanded; File Breakdown starts collapsed.
    The composer renders each label with the same prominent uppercase section-heading
    treatment and one shared trailing-chevron disclosure control.
    Collapsing a section hides its mounted body without disposing its renderer, and the
    state is not persisted across Overview mounts.
12. **Category colors belong to aggregate visualizations.** The tree’s existing `ft-*`
    colors identify broad rendering subtypes; several exact extensions intentionally
    share one tree color.
    Adjacent row fills need distinct categorical colors, so the design system gains a
    bounded distribution palette.
    A folder-view session assigns displayed logical types to distinct slots and retains
    those assignments across live updates.
    The hierarchical Treemap colors files by exact extension and folders by dominant
    extension using the same map when both views are mounted.
    Exact extension rows lead with the shared broad-type file icon while their labels
    remain plain text. Family, No extension, Other types, Files, and Ignored parents stay
    iconless; unknown exact extension children use the generic blank-page icon, and
    Other uses a neutral token.
13. **File Breakdown is both visual summary and exact source.** Every selected-metric
    cell contains a right-aligned absolute value, a left-to-right proportional track,
    and a right-aligned percentage.
    Fills are decorative, do not become tab stops, and are hidden from the accessibility
    tree. Color is never the only path to the data.
    Type labels are bold scan anchors.
    Top composition segments add supplemental hover-only tooltips using the shared
    navigation primitive.
    Each tooltip puts the semantic family name in bold, then reports that segment’s
    exact file count and byte size for its disjoint Files or Ignored population.
    Files and Bytes tallies use the navigation panel’s shared count and byte emphasis
    classes, including the Files and Ignored rows; row roles do not override the
    magnitude-driven numeric weight.
14. **Overview supports surface and document presentations.** The composer supplies one
    shared section heading while preserving each presentation’s role.
    Surface panels are flat chrome rather than boxed; README retains the ordinary
    Markdown document card at regular and wide bands and follows KPress’s standard
    borderless narrow layout.
    Files, File Breakdown, and their section headings align to the card’s outer edges
    while it exists and to the README prose edge after the card collapses.
    At the wide document band, the TOC keeps its own rail.
15. **Printing is declared per panel.** File types carries the same no-print contract as
    other host controls.
    README is printable, so printing Overview prints the ordinary rendered document
    without the summary or empty panel slots.
16. **Partial rollups do not become partial visualizations.** During scanning, File
    Breakdown and Treemap retain their loading grammar rather than painting
    indexed-so-far rows or rectangles.
    On terminal truncation the completed view retains a persistent scope warning.
    Pending data never becomes an empty directory.
17. **One Overview watch supplies both file panels.** File Breakdown owns one
    `watchRollup` with the view’s active gate, aborts in-flight work on disposal, and
    updates keyed rows in place.
    It publishes validated terminal envelopes through a ref-counted, per-directory
    projection pool. Files subscribes to that projection, so its composition adds no
    request and never reaches into sibling DOM.
18. **Code, Documentation, Data, Logs, Archives, Media, and Other are presentation
    groups, not new rollups.** They reuse the shared recommended file-type definitions.
    Compound extensions inherit the longest recognized suffix.
    Extensionless files and unknown extensions use the disclosable No extension and
    Other types parents under Other.
    Empty groups are omitted and group headings carry no subtotal.
19. **Files presents stable population context.** Its Files row reports the unignored
    population and its Ignored row reports the excluded population.
    The rows are disjoint and remain visible for either scope.
    Each nonzero row is its own 100% denominator and receives a full-width track
    segmented by the same top-level type colors as File Breakdown.
    Segments are semantic families rather than individual extensions and use File
    Breakdown’s group-first, active-metric ordering.
    It shows only the selected-metric tally, with no redundant percentage.
    The whole Ignored row uses the shared dimmed-content token.
    A zero-byte population truthfully uses `0 B` and no fill.
20. **Treemap is the hierarchy view, with one metric and one scope choice.** It always
    lays out folders and files; the File types panel replaces the former type-grouping
    mode, and extension color replaces the former age-color mode.
    A Bytes/Files segmented control chooses area.
    A default-checked Show ignored checkbox includes and dims ignored cells; unchecking
    it removes them and uses unignored rollup totals.
    Names and values scale continuously from cell geometry within documented bounds,
    nested folder headers reserve that scaled height, and visible values use the shared
    byte and file-count formatters.
    File labels lead with the navigation tree’s shared file icon, and visible folder
    labels end in `/` without changing their path or accessible name.
    Hover brightens the composed type-derived surface and border together, with no local
    label patch, border-hue replacement, stacking change, or hidden descendants.
21. **Treemap folder navigation stays in Treemap.** Activating a directory cell, or
    moving to its parent with Backspace, opens the destination folder with Treemap
    selected. File cells retain ordinary file-view navigation.
    The public `openPath` option carries this preferred view through cached and fetched
    paths; the shell falls back to the destination’s declared default when the
    preference is unavailable.
    General tree, breadcrumb, and direct-link navigation still opens a folder’s default
    Overview, and the URL remains a path route rather than encoding transient tab state.

### Information Architecture

Folder tabs select the primary way of looking at the selected folder:

```text
OVERVIEW   TREEMAP   [FILES, future]
```

Overview composes a vertical stack of contributions:

```text
Overview
├── Files                              totals and metric choice, always
├── File Breakdown                     detailed type summary, always
├── README                             when a direct child exists
└── License and other plugin panels    future, when applicable
```

The future Files listing is intentionally not in this tree.
A listing changes the whole working mode and belongs beside Overview and Treemap.
A README or License explains the same folder and belongs inside Overview.

A populated Overview appears as two flat chrome sections followed by one document
section.
File Breakdown is collapsed initially and is expanded here to show its contents:

```text
FILES
──────────────────────────────────────────────────────────────
Files      1,175 files ████████████████████████████████████████
Ignored       75 files ████████████████████████████████████████

FILE BREAKDOWN
──────────────────────────────────────────────────────────────
Show ignored ☑
DOCUMENTATION
.md        23 files █                                          1.8%
CODE
.py       150 files ████                                        12%
.js        75 files ██                                           6%
DATA
.json      63 files ██                                           5%
OTHER
.bin        1 file  ▏                                         <0.1%
Other types …

README
──────────────────────────────────────────────────────────────
# Directory README title

README content…
```

The drawing shows structure, not exact color or dimensions.
The lower region is the ordinary KPress rendered-document content, not a new generic
README renderer or a nested File types panel.
Each metric column uses an 8-pixel track and existing type-scale and spacing tokens.
The track height is a named Aggregate distributions component token rather than a
use-site literal.

The shared uppercase section headings are the only content above their bodies.
Files owns the one Files / Bytes chooser and leads with disjoint Files and Ignored rows.
File Breakdown owns Show ignored and the full detail table.
No visible Type or metric header repeats what the aligned columns already communicate.
Screen-reader-only column headers preserve the semantic table relationships.

An empty folder keeps the same first panel and no synthetic document panel:

```text
FILES
──────────────────────────────────────────────────────────────
No files to summarize.
```

It does not render zero-width colored fills, a header-only table, `NaN%`, or “No README”
copy. The empty state remains inside the stable section so an empty folder does not look
like a failed or unfinished preview.

### Folder Overview Panel Contract

The built-in folder plugin adds `mb.folderOverview.registerPanel(panelId, spec)`
alongside the core `registerView(kindId, viewId, spec)` registry.
It is a documented `window.metabrowser` capability, but its implementation and schema
remain in the folder plugin rather than making core understand folder panels.
The two registries are not interchangeable: the view registry owns tabs and lazy tab
mounting, while the Overview registry owns regions inside the one
`("folder", "overview")` view.

Each panel descriptor supplies:

- a stable, plugin-qualified `panelId` and accessible `label`
- `placement` as `summary`, `content`, or `supplemental`; the composer sorts by that
  fixed band and then by `panelId`, never by script-load timing
- `presentation` as `surface` for a flat host-rendered body or `document` when the
  mounted renderer already owns its content surface
- `required`, defaulting to false; a required panel keeps its slot and treats a null
  resolution as a contract error, while an optional null result removes its slot
- `resolve(ctx, { signal })`, which may return `{ key, data }`, a promise of that
  result, or `null` when the panel does not apply; `key` identifies equivalent mounted
  content across context refreshes, and all asynchronous work must be bounded and
  abortable
- `mount(container, ctx, data, { signal })`, which returns an instance-specific handle
  with `dispose()` and may provide `update(ctx, data)`
- `printable`, which defaults to false

Registration validates unknown placement and presentation values and rejects duplicate
IDs. The composer resolves contributions independently, reserves their deterministic
order while pending, and mounts each result into its own labelled `<section>`. A null
result removes only an optional slot.
A result with the same key keeps its mounted handle and calls `update` when one exists;
a changed key disposes the old handle before mounting the replacement.
A failed resolver or renderer receives a compact, panel-scoped error.
Transient failures offer Retry; invalid or permanent failures show an applicable
corrective action.
Network and server failures use the shell’s normal classification, and
plugin errors may declare whether they are retryable while preserving their cause.
The failure does not replace Overview or unmount a sibling.
Folder replacement aborts pending resolution and runs every mounted disposer exactly
once.

File types registers in the `summary` band, always resolves, uses `surface`, and is not
printable.
README registers in the `content` band, resolves only when the folder envelope
has `readme_path`, uses `document`, and is printable.
A future License panel can register in `supplemental` without either panel knowing it
exists. Folder inventory changes re-resolve availability through the same keyed
lifecycle, so adding or removing a README can add or remove that panel without
navigating away.

The composer reports aggregate print eligibility to the shell.
Overview offers Print only while at least one mounted panel is printable; an empty or
README-less folder does not offer an action that would produce a blank page.

The Markdown built-in gains an instance-safe rendered-document mount that returns its
own TOC disposer. Both the ordinary Markdown view and the README Overview contribution
call that mount.
This replaces the current singleton TOC cleanup seam and guarantees that
composed Markdown keeps the same content, diagnostics, breakpoints, theme, and print
behavior without the folder plugin copying KPress DOM selectors.

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
custom properties. Inline percentage widths remain permitted because they encode data,
not theme.

The folder summary maintains an `extension_key -> palette_slot` map:

- existing displayed types keep their slot across live updates
- a new type takes the next unused slot from a deterministic key-derived starting point
- a removed type’s slot stays reserved for the mounted view so its return does not
  recolor the panel
- navigating to a different directory starts a new mapping
- Other always uses the neutral token

The palette assignment is scoped to one directory comparison.
This guarantees distinct visible fills without pretending an open-ended extension
vocabulary has a universal color standard.
When Treemap and Overview coexist for a directory, their extension-colored marks share
the map.

Every row places its stable type color directly in the selected metric track, while
adjacent text names the type and gives the exact value and percentage.
No separate color mark or legend is needed.
Similar colors or color-vision differences do not remove information.
Labels, counts, and status copy remain in the host sans face.

### Responsive Layout

The panel follows the responsive README document geometry and uses container queries
against the preview pane, not window media queries.
At regular and wide bands, the section headings and File types body share the README
card’s left and right edges.
At the narrow band, KPress removes the card and those elements follow the Markdown text
edges instead.

- At ordinary widths, the fixed-layout semantic table keeps Type and the selected metric
  as aligned semantic columns without visible column labels.
  The metric keeps its tally and percentage right-aligned around a flexible track.
- At narrow widths, the same two columns remain so rows can still be compared.
  The metric track contracts before exact tallies or percentages disappear.
- Long or synthetic type labels wrap within the first column; they never widen the
  preview or create a nested scroll owner.
- Files and Ignored rows use the same selected-metric grammar as the breakdown.

### Loading, Empty, Partial, and Failure States

The panel supports these states explicitly:

| State | Presentation |
| --- | --- |
| Initial request | Header and two neutral skeleton tracks; delayed text says “Loading file types…” only when the request remains visible |
| Scanning with rows | Render current rows and say “Scanning… percentages cover files indexed so far.” |
| Complete | Remove progress copy; table rows and fills are final for the current inventory snapshot |
| Complete index miss | “This folder is not in the current file index.” rather than a persistent loading skeleton |
| Truncated | Keep rows and a persistent warning with indexed and configured-cap counts |
| Empty complete folder | “No files to summarize.” inside the File types panel, with no bars, percentages, or table |
| Active scope has only ignored files | “No included files. Show ignored to include N files.” rather than claiming the folder itself is empty |
| All files are zero bytes | Render the Files column normally; Size shows neutral zero tracks and `0 B` values |
| Request failure | “Could not load file types.” with Retry for a transient failure or the relevant corrective action for a permanent one; the live watch remains able to recover |

Progress and completion copy use the design system’s state language.
Routine live count changes are not announced.
The transition from loading or scanning to a terminal state uses one polite status
announcement. Empty is terminal data, not missing UI: Overview and the File types header
remain mounted, the explicit empty message replaces the table, and no README panel
appears unless a README actually exists.

### Overview Composition and Markdown Layout

The folder manifest advertises `overview` first and labels it **Overview**. The folder
plugin registers one Overview composer as that view, then registers File types and
README as ordinary panel contributions.
Treemap remains a lazily mounted top-level view.
A future Files listing would use the same manifest and `registerView` path as Treemap,
not the panel registry.

The Overview composer owns one responsive grid and vertical rhythm for all
contributions. Surface bodies and shared headings follow the document card’s outer
measure at regular and wide bands.
At KPress’s wide band, the README’s TOC occupies only the document row while summary
content aligns with the card above it.
At the narrow band, KPress removes the card and the panels align to the prose edge in
the existing single-column flow.

The README contribution mounts the shared Markdown document primitive directly into a
document-presentation region.
Frontmatter and diagnostics remain inside the normal KPress prose flow under their
existing contract, while File types keeps its host sans typography.
Overview preserves the prose card’s ordinary responsive presentation, including its
border, shadow, padding, and narrow-band collapse.
The Markdown primitive owns KPress DOM and grid knowledge; the Overview composer and
folder plugin do not copy selectors or reach into private shell globals.

When README is absent, its resolver returns null and the composer renders the remaining
panels in the same centered measure.
It does not instantiate an empty KPress document, show a “No README” card, or change the
selected tab.
An empty folder therefore has one deliberate File types section rather than
a blank preview.

The shell’s existing live folder-envelope refresh publishes updated context through one
supported SDK subscription.
Overview re-runs panel resolvers when direct-child facts can change, reusing that
refresh rather than starting one fetch per panel.
File Breakdown continues to use its rollup watch for aggregate updates and publishes
validated terminal envelopes to the shared Files projection.
Changing folders disposes the folder-context subscription, every panel resolver, summary
watch, filter subscription, Retry handler, and Markdown TOC instance.
Switching between Overview and Treemap follows the existing lazy view lifecycle.

### Accessibility and Interaction

- File types and README are labelled semantic sections with visible `h2` headings.
  Each heading contains one button with `aria-expanded`, `aria-controls`, and the shared
  trailing chevron; both start expanded.
- Collapsing an Overview panel hides its body without disposing or remounting it.
  Frontmatter and Diagnostics retain native `details` semantics, use the same trailing
  chevron, and start collapsed.
- File Breakdown has real column and row-group headers.
  Exact values and percentages remain ordinary readable text.
  Files retains screen-reader-only Population and active metric headers, and each
  population row exposes its exact tally.
- Individual visual fills are hidden from the accessibility tree because the adjacent
  text already contains the data.
- Counts use locale formatting, correct singular/plural copy, and tabular numerals.
- Focus is not moved during scan or live updates.
- `prefers-reduced-motion` disables fill-width interpolation; all data updates
  immediately.
- Light and dark palette tokens are reviewed as fills on their actual track and page
  surfaces. No text is placed on a category color.

## API Changes

No new endpoint or second file-type filesystem pass is required.
Extend the WIP `/api/rollup` route and folder envelope; File types reads the in-memory
inventory, while README availability retains one separately bounded direct-child lookup.

Add these browser SDK contracts:

- `mb.folderOverview.registerPanel(panelId, spec)` validates and registers the
  descriptor defined above; the folder plugin installs this namespace on the public SDK,
  and registration is additive to `registerView`, not a special view identifier
- `mb.folderOverview.listPanels()` returns frozen descriptors in deterministic placement
  and ID order for the built-in Overview composer
- `mb.folderContext.subscribe(path, onUpdate)` exposes the shell’s multiplexed live
  folder-envelope refresh and returns an unsubscribe function; it does not start a
  second refresh request per subscriber
- `setViewPrintState(container, state)` lets a composite renderer publish aggregate
  printability, profile, and runtime without editing private preview attributes
- the Markdown built-in exposes an instance-safe rendered-document mount returning a
  disposer, and the existing ordinary Markdown renderer delegates to it

The folder envelope retains `readme_path`. Overview treats that field as discovery data,
not an instruction to hard-code README into the composer.
Installed panels may use their own bounded data hooks from `resolve`; core does not gain
plugin-specific License or metadata fields merely to support the panel registry.

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

A separate strict Overview-composer module owns panel registration validation,
deterministic resolution and mounting, presentation classes, independent errors, print
eligibility, context refresh, and disposal.
The File types renderer does not contain README, KPress, or future-panel branches.

The module uses supported SDK helpers for rollups, filters, preferences, formatting, and
folder-view lifecycle.
It does not access private `app.js` state.

## Backward Compatibility

- **Internal code types, methods, and function signatures: DO NOT MAINTAIN.** Do not
  retain deprecated internal wrappers while refactoring the WIP folder plugin.
  Keep the rollup row normalization boundary explicit.
- **Plugin SDK: KEEP DEPRECATED.** Preserve existing `fetchRollup` and `watchRollup`
  options and response fields.
  The Overview panel registry, folder-context subscription, zero-depth support, and
  instance-safe Markdown mount are additive; this plan deprecates no existing SDK
  member. Existing `registerView` registrations remain top-level tabs and never become
  Overview panels implicitly.
- **Server API: KEEP DEPRECATED.** Preserve `/api/rollup` field names and compact tally
  rows. The dual-metric ranking is opt-in until every in-tree consumer adopts it; then it
  may become the documented default in the same release.
- **File formats: N/A.**
- **Database schemas: N/A.**

## Implementation Architecture

### Baseline Reconciliation

Implementation starts from current `main` plus the useful parts of the
`feat/folder-treemap` work, not from a wholesale copy of its final browser files.
Port the foundation in three reviewable slices:

1. Inventory rollup types, route, settings, and their tests.
2. Folder envelope, folder routing, lazy folder views, SDK rollup watch, and lifecycle
   tests.
3. Treemap layout, model, interaction, styles, and browser tests.

Preserve newer `main` behavior in `server.py` and `app.js`, including quick file
finding, current asset ordering, and recent-file behavior.
Do not port the WIP’s conditional README tab, root-README auto-navigation, singleton
Markdown TOC disposer, duplicate size formatter, direct folder-header refresher, or
1,100-line folder `index.js` as final architecture.
The slices may initially reproduce WIP behavior behind tests, but each slice is complete
only after it lands in the target modules below.

The implementation follows test-driven slices.
Write or port the focused failing tests for one contract, make that contract pass, then
refactor while the focused suite remains green.
Run the formatter and the affected Python and DOM wrappers after each slice;
`make verify` remains the final gate.

### Target Module Graph

```text
src/metabrowser/
├── inventory.py                         live index; thin rollup entry point
├── inventory_rollup.py                  pure aggregation and bounded emission
├── folder_discovery.py                  bounded direct-child README discovery
├── settings.py                          server limits and client-visible constants
├── server.py                            folder envelope, rollup route, asset wiring
├── wire_models.py                       rollup and tally wire types/validators
├── static/
│   ├── request_error.js                 generic request error classification
│   ├── formatters.js                    shared byte/count formatting
│   ├── inventory_scope.js               scoped event relevance and watch factory
│   ├── contribution_registry.js         generic deterministic registry primitive
│   ├── resource_context.js              multiplexed live resource-envelope store
│   ├── view_state.js                    active-view and dynamic print-state bridge
│   ├── plugin_sdk.js                    public SDK adapters only
│   ├── types.d.ts                       exact SDK and wire declarations
│   ├── app.js                           routing, folder chrome, generic view mounting
│   └── styles.css                       design tokens only for the new components
└── builtin_plugins/
    ├── markdown/
    │   ├── index.js                     thin view registration adapter
    │   ├── rendered.js                  instance-safe rendered Markdown mount
    │   └── source.js                    source rendering helpers
    └── folder/
        ├── manifest.toml                Overview default; Treemap peer
        ├── index.js                     imports and registrations only
        ├── overview_registry.js         folder-panel schema and registry facade
        ├── overview.js                  panel composer and lifecycle
        ├── readme_panel.js               conditional Markdown contribution
        ├── file_type_summary_model.js   pure tally-to-view-model transform
        ├── distribution_view.js         grouped inline-bar table
        ├── file_type_summary.js         live panel controller
        ├── category_palette.js          path-scoped stable palette pool
        ├── treemap_layout.js             pure geometry exports
        ├── treemap_model.js              pure rollup/filter/cell transforms
        ├── treemap.js                    Treemap DOM controller and view adapter
        ├── styles.css                    existing Treemap styles
        ├── overview.css                  composer and panel presentation styles
        └── file_type_summary.css         distribution-specific layout styles
```

Every new browser file except the existing legacy adapters `app.js`, `plugin_sdk.js`,
and Markdown `index.js` stays under the fully strict `tsconfig.json` include.
Do not add any new file to the legacy exclusion list.
Folder and Markdown `index.js` files are ES modules and use relative imports served by
the existing plugin-static route; the folder manifest no longer needs
`extra_scripts = ["treemap_layout.js"]`.

### Cross-Layer Data Flow

The one summary request is:

```text
FileTypeSummaryController
  -> mb.watchRollup(path, depth=0, top=0, ext_top=10, ext_rank=dual)
  -> GET /api/rollup
  -> InventoryIndex.rollup
  -> inventory_rollup.build_rollup
  -> root totals + bounded extension tallies
  -> normalizeRollupEnvelope
  -> buildFileTypeSummaryModel
  -> updateDistributionView
```

No layer walks the filesystem for file-type composition.
The rollup uses the process-wide inventory and calculates all/unignored totals together.
The browser holds both populations and changes columns locally when **Show ignored**
changes.

Folder context follows a separate, multiplexed path:

```text
/api/file folder envelope
  -> mb.folderContext.seed(path, envelope)
  -> one path-scoped inventory watch and debounced envelope refresh
  -> shell folder header subscriber
  -> Overview composer subscriber
  -> keyed panel re-resolution
```

The header and composer therefore never issue parallel `/api/file` refreshes for the
same selected folder.
README discovery is a bounded direct-child operation used only by the envelope; File
types continues to use inventory rollups.

### Server and Inventory Function Map

#### `src/metabrowser/inventory_rollup.py` — new

This module owns pure, synchronous transformation of a read-only inventory mapping.
It imports `FsEntry` only under `TYPE_CHECKING`, avoiding a runtime cycle with
`inventory.py`.

- `RollupOptions` is a frozen, slotted dataclass containing `depth`, `top`, `ext_top`,
  `ext_rank`, and `max_nodes`. Construction rejects negative limits and unknown ranking
  modes.
- `_SubtreeAggregate` is a private slotted accumulator for all/unignored file counts,
  bytes, newest modification time, and the four extension counters.
- `build_rollup(entries, root_path, options, ancestor_gitignored)` is the only public
  transformation entry point.
  It returns `None` for an absent or non-directory root and otherwise returns one
  `RollupResult` containing `node` and `ext_tallies`.
- `_group_children(entries)` creates the one parent-to-children map and skips the root’s
  self-parent link.
- `_aggregate_subtree(...)` performs the post-order aggregation once, propagates
  inherited ignore state, and never follows a symlink or opens a file.
- `_file_node(...)` and `_directory_node(...)` serialize the two node shapes without
  mixing traversal policy into aggregation.
- `_all_weight(...)`, `_unignored_weight(...)`, and `_ordered_children(...)` preserve
  the WIP’s interleaved all/unignored child selection and deterministic path tie-break.
- `_emit_bounded_tree(...)` performs breadth-first emission under both the per-directory
  and global node budgets.
  `depth=0` leaves the root’s `children` as the lazy `null` sentinel; `top=0` emits no
  child nodes and accounts for omitted content in `rest` when depth permits emission.
- `_share(value, total)` returns zero for a zero denominator and otherwise uses the
  unrounded integer ratio.
- `_extension_scores(aggregate, key)` returns `(score, byte_score, file_score)` from the
  four populations defined in Category Selection and Other.
- `_select_extension_keys(aggregate, limit, rank_mode)` returns deterministic named
  keys. `bytes` preserves the prior byte-first order; `dual` sorts descending by the
  three scores and ascending by normalized key.
- `_serialize_extension_tallies(aggregate, keys)` emits the compact five-cell rows and
  one exact Other row for every omitted key.
  It selects from the union of all four counters so a zero-byte or ignored-only type is
  not lost.

The algorithm remains one O(N) grouping/aggregation pass plus bounded sorts.
Its 100,000-entry performance fixture keeps the existing 150 ms development target and
records emitted-node and serialized-payload bounds.

#### `src/metabrowser/inventory.py`

- Remove `_SubtreeAgg` and the nested rollup helpers.
- Keep `ROLLUP_NO_EXT_KEY` and `ROLLUP_REST_EXT_KEY` in `inventory_rollup.py`; re-export
  them from `inventory.py` only if an existing import requires compatibility.
- `InventoryIndex.rollup(path, *, depth, top, ext_top, ext_rank="bytes", max_nodes=None)`
  validates its local preconditions, computes `_ancestor_gitignored(path)`, constructs
  `RollupOptions`, and delegates to `build_rollup`. It contains no serialization
  branches of its own.
- `_ancestor_gitignored(path)` remains on `InventoryIndex` because it reads index state,
  but it returns only the initial boolean passed into the pure builder.

The method is synchronous and contains no `await`, so the event loop cannot mutate the
index during one call.
Do not add an O(N) defensive copy merely to simulate concurrency that cannot interleave.

#### `src/metabrowser/watch_backends.py`

- `_emit_for_path(inventory, root, abs_path, change_type)` treats `lstat` at handling
  time as authoritative because watcher backends may coalesce or reorder rapid
  remove-and-recreate events.
- An absent current path removes any indexed entry regardless of the event label.
  A current directory is rewalked regardless of the label; when a stale delete names a
  recreated directory, the old indexed subtree is removed first so obsolete descendants
  cannot survive the rewalk.
- Every reconciliation continues to use `InventoryIndex.remove`, `rewalk_subtree`, and
  `apply_live_entry`, preserving aggregate updates and inventory-change events.

#### `src/metabrowser/folder_discovery.py` — new

- `FolderDiscovery` is a frozen, slotted result carrying `readme_name` and whether the
  unusual-casing fallback reached its entry limit.
- `discover_folder(target, *, max_entries)` first probes the three existing preferred
  spellings with regular-file, no-symlink checks, then performs at most `max_entries`
  `os.scandir` entries to find other case-insensitive `README.md` spellings.
- `_choose_readme(candidates)` applies the documented preferred-spelling order and then
  a stable case-sensitive name tie-break.

The caller has already resolved `target` through the safe-path helper.
The fallback never recurses, follows symlinks, or reads file content.
`_api_folder_envelope` calls it with `asyncio.to_thread`, so even the bounded directory
operation stays off the server event loop.

#### `src/metabrowser/settings.py`

Add named constants rather than literals at call sites:

- `ROLLUP_DEFAULT_EXT_RANK = "bytes"`
- `ROLLUP_FILE_TYPE_NAMED_LIMIT = 10`
- `DISTRIBUTION_PALETTE_SLOTS = 12`
- `FOLDER_DISCOVERY_MAX_ENTRIES = 4096`

Keep the WIP rollup depth, top, extension, node, and debounce bounds.
`client_settings_dict()` exports the rollup defaults, file-type named limit, palette
size, and watch debounce; it does not export the server-only discovery limit.

#### `src/metabrowser/wire_models.py`

- `ExtensionTallyRow` names the five-position tuple contract.
- `RollupResult` names the inventory result with `node` and `ext_tallies`.
- `RollupEnvelope` names the route response, including scan and truncation metadata.
- `validate_extension_tallies(rows)` checks row length, distinct string keys,
  nonnegative integer cells, at most one final Other sentinel, and all/unignored
  monotonicity.
- `validate_rollup_result(result)` calls `validate_rollup_node`, validates tallies, and
  asserts that tally columns sum to the root’s four totals.
- `validate_rollup_envelope(envelope)` additionally validates the nullable cold-index
  state and route metadata.

These validators remain test and assertion helpers; do not traverse a large response
again on every production request.

#### `src/metabrowser/server.py`

- `_query_bounded_int(request, name, default, *, minimum, maximum)` replaces repeated
  clamp expressions and treats malformed input as the default.
- `_query_choice(request, name, default, allowed)` parses `ext_rank`; an unsupported
  explicit value returns a 400 response rather than silently selecting a different
  semantic ranking.
- `api_rollup(request)` accepts zero for `depth` and `top`, passes `ext_rank` through to
  `InventoryIndex.rollup`, and preserves the current envelope and 404/cold-index
  behavior.
- `_api_folder_envelope(subpath, target)` always returns the folder manifest’s Overview
  and Treemap views without filtering a README tab.
  It calls `discover_folder` in a worker thread, retains `readme_path` as discovery
  data, and keeps the envelope `no-store`.
- `_api_file_impl(request)` continues to route directories before file classification.
- `index(request)` adds the strict helper assets before `plugin_sdk.js`, preserves all
  later dependency ordering, and no longer injects `METABROWSER_INITIAL_PATH`.
- Remove `_initial_file_path()`. With no hash route, the browser selects the served root
  folder; README becomes a panel inside its Overview rather than replacing the landing
  route.
- `_build_plugin_script_block()` needs no new loader feature.
  Relative ES-module imports resolve under the existing safe plugin-static route.

### Strict Browser-Core Function Map

These modules are small IIFEs that expose one frozen global factory for the legacy SDK
and shell adapters. They contain no folder panel IDs, README branches, or component CSS.

#### `src/metabrowser/static/request_error.js` — new

- `RequestError` stores a safe message, HTTP status, operation, and cause.
- `isAbortError(error)` recognizes browser aborts without depending on one realm’s
  `DOMException` constructor.
- `classifyRequestError(error)` returns `{ message, retryable }`; aborts are control
  flow, 408/425/429/5xx and network failures are retryable, and other 4xx failures are
  not.

Expose the helpers as `window.MetabrowserRequestErrors` and through `mb.errors`. Never
display raw response bodies or local paths.

#### `src/metabrowser/static/formatters.js` — new

- `formatBytes(value)` preserves existing B/KB/MB output and adds bounded GB/TB/PB
  bands.
- `formatInteger(value)` uses one cached `Intl.NumberFormat` instance.
- `formatFileCount(value)` applies localized integers and correct `file`/`files` copy.

Expose one frozen `window.MetabrowserFormatters` object.
Both `app.js` and `plugin_sdk.js` delegate to it; neither keeps a private
byte-formatting implementation.

#### `src/metabrowser/static/inventory_scope.js` — new

- `pathsIntersectScope(changedPaths, scopePath)` is the single relevance predicate used
  by rollups and live folder envelopes.
- `createInventoryWatch(scopePath, options, onUpdate)` owns the inventory event
  listener, trailing debounce, abort controller, stale bit, active gate, refresh, error
  callback, and idempotent disposal.
- The returned handle is `{ refresh, stale, dispose }`. `refresh()` never overlaps a
  prior request, and a completion after disposal is ignored.

`mb.watchRollup` becomes a typed wrapper that supplies `fetchRollup` to this generic
factory rather than duplicating listener code.

#### `src/metabrowser/static/contribution_registry.js` — new

- `createContributionRegistry({ validate, compare })` returns an isolated registry with
  `register(id, spec)` and `list()`.
- `register` validates before mutation, rejects duplicates, freezes the stored
  descriptor, and returns an unregister function for test isolation.
- `list` returns a frozen sorted snapshot and never exposes the mutable backing map.

The helper knows nothing about folder placements or panel presentation.
`overview_registry.js` supplies those rules.
Like `registerView`, panel registration happens during plugin module evaluation before
the DOM-ready mount; version one does not hot-add a newly registered descriptor to an
already mounted Overview.

#### `src/metabrowser/static/resource_context.js` — new

- `createResourceContextStore({ fetchEnvelope, pathsIntersect, debounceMs })` returns
  `seed`, `subscribe`, `refresh`, and `dispose` methods.
- A map entry holds the latest envelope, subscriber set, timer, abort controller, and
  monotonic request generation for one path.
- `seed(path, envelope)` publishes the already-fetched `/api/file` result without
  another request.
- `subscribe(path, listener)` immediately delivers a seed when present, adds no new
  inventory listener, and returns an idempotent unsubscribe.
- One global inventory listener schedules at most one trailing refresh for each path
  with subscribers.
- The last unsubscribe clears that path’s timer and request and releases the map entry.

`plugin_sdk.js` instantiates this generic store as `mb.folderContext`. Only folder
envelopes are seeded in version one, but the helper’s state model remains
resource-generic.

#### `src/metabrowser/static/view_state.js` — new

- `setActive(container, active)` is the shell-side state write and notifies subscribers
  only on a real transition.
- `isActive(container)` is the supported replacement for plugin checks of private tab
  attributes or `offsetParent` heuristics.
- `subscribeActive(container, listener)` delivers current state and returns an
  idempotent unsubscribe.
- `setPrintState(container, state)` validates `printable`, `profile`, and `runtime`,
  updates the view container, and dispatches one shell event when the active view’s
  print eligibility changes.

Expose plugin-safe methods as `mb.viewState.isActive`, `mb.viewState.subscribeActive`,
and `mb.setViewPrintState`. The shell-only active setter remains on
`window.MetabrowserViewState`.

#### `src/metabrowser/static/plugin_sdk.js`

Keep this legacy file an adapter:

- `fetchRollup(path, options)` serializes `depth`, `top`, `ext_top`, and `ext_rank`,
  forwards `signal`, parses the envelope, and throws `RequestError` for failures.
- `watchRollup(path, options, onUpdate)` delegates to `createInventoryWatch`.
- `fetchKpressRender(ctx, viewId, options)` forwards an additive `signal` option so a
  composed README mount can be aborted.
- `formatSize`, `formatInteger`, and `formatFileCount` delegate to the shared formatter.
- Install `mb.errors`, `mb.folderContext`, `mb.viewState`, and `mb.setViewPrintState`
  from the strict factories.
- Do not add the folder Overview registry here; the folder plugin attaches its own
  documented namespace.

Preserve all existing method names and defaults.
Do not move unrelated legacy SDK helpers during this feature.

#### `src/metabrowser/static/app.js`

Limit changes to shell integration seams:

- `selectFile(path, skipHistory)` keeps folder envelopes out of the file cache, commits
  directory routes only after a successful envelope, and aborts stale selections.
- `renderFolderHeader(data)` remains shared folder chrome and includes the same
  initially hidden print control as file views; dynamic Overview print state reveals it
  only when a printable panel is mounted.
- Replace `startFolderHeaderRefresh` and `stopFolderHeaderRefresh` with
  `startFolderHeaderSubscription(path)` and `stopFolderHeaderSubscription()`; the former
  subscribes to `mb.folderContext` and patches only the summary strip.
- `renderFile(data)` seeds `mb.folderContext` before it starts the header subscriber or
  mounts folder views.
- `mountPluginView(container, pluginView, ctx)` accepts either the existing spec-level
  `dispose` callback or a new instance handle returned by `render`. If an asynchronous
  mount finishes after replacement, dispose its handle immediately instead of retaining
  detached state.
- `disposeActivePluginViews()` invokes each normalized handle exactly once and then
  unsubscribes the folder header.
- `setActivePreviewView(tabId, preview)` calls `MetabrowserViewState.setActive` for
  every tab container and consumes dynamic print-state events.
- `printActiveView()` retains the existing print path; visibility now follows the active
  view’s published composite state.
- `parseHashRoute`, `splitHashRoute`, `commitRoute`, and `navigateToPath` preserve the
  WIP’s trailing-slash directory routes and history behavior.
- The DOM-ready entry point selects root Overview when there is no hash.
  Remove `serverInitialPath()` and `findRootReadme()`.

The shell does not import folder renderer modules, inspect panel IDs, or reach into
their DOM.

#### `src/metabrowser/static/types.d.ts`

Replace broad `Record<string, unknown>` declarations at the new boundaries with:

- `MetabrowserExtensionTallyRow` and normalized `MetabrowserExtensionTally`
- `MetabrowserRollupNode`, `MetabrowserRollupEnvelope`, options, and watch handle
- generic contribution-registry types
- `FolderOverviewPanelSpec<T>`, `FolderOverviewResolution<T>`,
  `FolderOverviewMountHandle<T>`, and panel error classification
- `FolderEnvelope`, folder-context subscription, and view-state APIs
- instance-safe Markdown mount options and handle
- category-palette lease and File types view-model types

The view renderer return type becomes additive:
`void | DisposableHandle | Promise<void | DisposableHandle>`. Existing `spec.dispose`
remains valid.

### Markdown Plugin Function Map

#### `src/metabrowser/builtin_plugins/markdown/rendered.js` — new

- `renderKpressDiagnosticsHtml(diagnostics, escapeHtml)` and `buildDiagnosticsNode(...)`
  retain the current diagnostic structure.
- `injectDiagnostics(container, diagnostics, mb)` inserts diagnostics in the existing
  KPress location.
- `renderKpressError(error, mb)` preserves the ordinary Markdown corrective states.
- `mountRenderedMarkdown(container, ctx, mb, options={})` paints loading state, fetches
  KPress with `options.signal`, ignores stale completions, injects diagnostics, starts
  one TOC instance, and returns `{ dispose }` for that instance.
- Its disposer aborts pending work and invokes only its own TOC disposer.
  It is safe to call more than once.

#### `src/metabrowser/builtin_plugins/markdown/source.js` — new

- `renderMarkdownSourceHtml(data, mb)` owns frontmatter splitting, truncation warning,
  escaping, and copy framing.
- `renderMarkdownSource(container, ctx, mb)` applies the source host class and measures
  the render.

#### `src/metabrowser/builtin_plugins/markdown/index.js`

Import the two modules, register the ordinary `rendered` and `source` views, and expose:

```text
mb.builtins.markdown.mountRendered
mb.builtins.markdown.renderSource
```

The ordinary rendered view returns the mount handle to the shell.
Remove `activeTocDispose`, `disposeToc`, and any module-wide rendered-document instance.
README and directly opened Markdown now exercise exactly the same mount function.

### Folder Plugin Function Map

#### `src/metabrowser/builtin_plugins/folder/overview_registry.js` — new

- `PLACEMENT_ORDER` maps `summary`, `content`, and `supplemental` to fixed ranks.
- `validatePanelId(id)` requires a stable plugin-qualified form such as
  `folder.file-types` or `example.license`.
- `validatePanelSpec(spec)` checks label, placement, presentation, resolver, mount,
  required status, printability, and optional error classifier without coercing invalid
  values.
- `comparePanels(a, b)` sorts placement rank and then panel ID.
- `createFolderOverviewRegistry(mb)` configures the generic contribution registry and
  returns `{ registerPanel, listPanels }`.

`index.js` publishes that frozen facade as `mb.folderOverview` before installed plugin
modules execute.

#### `src/metabrowser/builtin_plugins/folder/overview.js` — new

- `createOverviewView(mb, registry)` returns the `("folder", "overview")` view spec.
- `mountOverview(container, ctx, mb, registry)` creates the stack, subscribes once to
  `mb.folderContext` and active-view state, reconciles every registered descriptor, and
  returns one composite disposer.
- `handleContext(nextCtx)` retains the newest envelope and reconciles immediately only
  while Overview is active; otherwise it marks the composer stale.
- `handleActive(active)` performs one reconciliation when a stale Overview becomes
  visible.
- `createPanelSlot(descriptor)` creates a stable, labelled `<section>` in deterministic
  order and applies only composer-owned presentation classes.
- `resolvePanel(record, ctx)` increments the record generation, aborts the prior
  resolver, and calls `resolve(ctx, { signal })` inside the panel error boundary.
- `applyResolution(record, result, ctx)` removes an optional null slot, reports a
  required-null contract error, preserves an equal keyed mount, calls `update` when
  provided, or disposes before a changed-key mount.
- `mountPanel(record, result, ctx)` passes an abort signal, normalizes the returned
  handle, and discards late async completions safely.
- `renderPanelFailure(record, error)` uses the descriptor classifier and `mb.errors`;
  Retry reruns only that record’s resolver.
- `disposePanel(record)` aborts resolution/mount work, removes Retry listeners, and
  invokes the mount disposer exactly once.
- `publishPrintState(container, records, mb)` enables document printing only when one
  successfully mounted contribution is printable and derives the document profile and
  runtime from that contribution.
- The composite disposer ends the context subscription, disposes every record, and
  publishes non-printable state.
- Resolver cancellation and mounted-panel lifetime use separate abort controllers, so a
  same-key folder-envelope refresh can call `update` without silently disposing the
  mounted panel’s watchers and subscriptions.

The composer contains no `if panelId === ...` branches.
Tests must register a synthetic third panel and receive the same lifecycle as built-ins.

#### `src/metabrowser/builtin_plugins/folder/readme_panel.js` — new

- `createReadmePanel(mb)` returns the `folder.readme` descriptor in the `content` band
  with `document` presentation and `printable: true`.
- `resolveReadme(ctx)` returns `null` without `ctx.raw.readme_path`; otherwise it
  returns `{ key: readmePath, data: { path: readmePath } }`.
- `mountReadme(container, _ctx, data, options)` calls
  `mb.builtins.markdown.mountRendered` with a normal Markdown render context and the
  provided signal.

There is no README title, wrapper card, copied KPress selector, or README-specific TOC
cleanup in the folder plugin.

#### `src/metabrowser/builtin_plugins/folder/file_type_summary_model.js` — new

This file is pure and has no DOM, fetch, preference, or global access.

- `normalizeTallyRow(row)` converts the five-cell wire row into named integer fields,
  maps `(none)` and the Other sentinel explicitly, and throws on malformed data.
- `normalizeRollupEnvelope(raw)` normalizes every tally and root total while preserving
  scan/truncation metadata.
- `selectPopulation(envelope, showIgnored)` chooses all or unignored integer columns.
- `formatPercent(numerator, denominator, formatter)` implements zero, `<0.1%`, and
  at-most-one-decimal behavior from the design.
- `createFileTypeCategoryClassifier(rawPresets)` builds the
  Documentation/Code/Data/Other presentation classifier from the complete shared
  navigation-preset vocabulary, with suffix inheritance for compound extensions and
  Other as the safe fallback.
- `buildFileTypeSummaryModel(envelope, showIgnored, formatters, classifyCategory)`
  returns one discriminated model for `pending`, `populated`, `empty`, `ignored-only`,
  `zero-bytes`, `truncated`, `failed`, or `unavailable`. `unavailable` is a completed or
  truncated envelope with no root node, distinct from a cold pending index.
- Populated rows preserve server order, drop only active-scope double-zero named rows,
  keep Other last, and carry a presentation group, total-normalized percentage widths,
  and formatted counts, sizes, and shares.
- The model derives exact ignored file and byte deltas from the all and unignored root
  totals, formatted values, and all-population shares for the optional Ignored row.
- `_assertPopulationSums(model)` is a development/test assertion that named plus Other
  integers equal the selected root totals.

#### `src/metabrowser/builtin_plugins/folder/distribution_view.js` — new

- `mountDistributionView(container, model, palette)` builds the semantic Type/Metric
  table once, with screen-reader-only column headers.
- `updateDistributionView(handle, model)` keys DOM rows by extension key, updates text
  and fill widths in place, moves rows under Documentation/Code/Data/Other row-group
  bodies, and removes stale rows or empty groups without replacing retained elements.
- Empty, failed, and unavailable models replace the table with their terminal message.
- Each type row resolves a shared file-identity icon.
  Exact extensions use a synthetic filename; unknown exact children use the generic
  filename fallback. Family, No extension, and Other types headings stay iconless.
- The selected metric cell owns a right-aligned tally, an `aria-hidden` track and fill,
  and a right-aligned percentage.
  Its exact tally uses the public shared count or byte emphasis class on mount and every
  keyed update.
- `renderSummaryState(handle, model)` switches among loading, partial, empty,
  ignored-only, zero-byte, populated, and failure bodies without manufacturing a table
  for zero rows.

Color is applied through `mb-distribution-slot-N` or Other classes.
Only unitless data weights may be inline.

#### `src/metabrowser/builtin_plugins/folder/file_totals_panel.js`

- `createFileTotalsPanel(mb, palettePool, projectionPool, rollupControls)` returns the
  required `folder.file-totals` summary/surface descriptor, initially expanded.
- `mountFileTotalsPanel(container, ctx, mb, palettePool, projectionPool, rollupControls, options)`
  mounts the one Files / Bytes chooser and the inventory-backed Files and Ignored rows.
- The panel observes the shared metric and updates immediately from directory-total
  snapshots without waiting for the detailed rollup.
- It subscribes to the path’s latest validated rollup projection and rebuilds the two
  independently normalized composition tracks with the shared palette.
  A missing, stale, or incompatible projection leaves a nonzero row as one neutral
  full-width fill.

#### `src/metabrowser/builtin_plugins/folder/rollup_projection.js`

- `createFolderRollupProjectionPool()` owns ref-counted sessions keyed by folder path.
- `acquire(path)` returns a small publish, subscribe, and release lease.
  It replays the latest projection to late subscribers and discards it after the last
  release.
- The pool transports already-normalized data; it does not fetch, classify, or render.

#### `src/metabrowser/builtin_plugins/folder/file_type_summary.js`

- `createFileTypeSummaryPanel(mb, palettePool, projectionPool, rollupControls)` returns
  the required `folder.file-types` summary/surface descriptor headed File Breakdown and
  initially collapsed.
- Its resolver immediately returns `{ key: ctx.path, data: null }`; the panel is never
  absent, including for pending and empty folders.
- `mountFileTypeSummary(container, ctx, mb, palettePool, projectionPool, rollupControls, options)`
  acquires the path palette and projection leases, mounts the shared **Show ignored**
  checkbox, observes the shared metric and scope, subscribes to active-view state, and
  starts exactly one rollup watch.
- `applyEnvelope(raw)` normalizes once, rebuilds the pure model for current ignored
  scope, reserves palette slots for all named rows in the envelope, and patches the
  distribution view. Completed and truncated envelopes with totals are also published to
  the projection pool.
- The shared-control subscription rebuilds from the retained normalized envelope when
  metric or ignored scope changes; it does not refetch.
- `handleActive(active)` refreshes a stale watch when Overview becomes visible.
- `handleFailure(error)` retains a stale successful model when one exists; otherwise it
  renders the classified panel error and wires Retry to `watch.refresh()`.
- `dispose()` ends watch, filter and active subscriptions, Retry listeners, and palette
  lease exactly once.

The rollup options resolve to `depth=0`, `top=0`, `ext_top=0`, independently bounded
filename and remaining-type fallbacks, and `ext_rank="dual"`.

#### `src/metabrowser/builtin_plugins/folder/category_palette.js` — new

- `createCategoryPalettePool(slotCount)` owns a path-to-session map.
- `acquire(path)` increments a reference count and returns a lease with `sync(keys)`,
  `slotFor(key)`, `classFor(key)`, and `release()`.
- `hashKey(key)` gives a deterministic starting slot.
- `assignSlot(session, key)` probes unused slots so the capped summary has distinct
  colors; reserved slots survive rank and visibility changes for the session.
- Other always returns the neutral class and never consumes a numbered slot.
- The final release deletes the path session.

Overview and Treemap both acquire the same pool exported by folder `index.js`.

#### Treemap modules

The Treemap implementation stays split by responsibility:

- `treemap_layout.js` exports `squarify`, `packLevel`, `cellTypography`, `layoutTree`,
  and `worstAspect`; it has no global registration or DOM access.
  It owns hierarchy-only packing, remainder conservation, ignored-scope weight
  selection, bounded recursion, and fluid type geometry.
- `treemap_model.js` owns the two-field preference contract and legacy-state
  normalization as pure functions.
- `treemap.js` owns shared-control markup and binding, file-type palette classes,
  formatter-backed labels and status, resize handling, view-preserving folder
  navigation, keyboard and pointer behavior, tooltip lifecycle, rollup watch, view-state
  subscription, and one instance disposer.
- Replace `offsetParent` plus `IntersectionObserver` activity inference with
  `mb.viewState`.
- Hierarchical file and folder cells request the shared category-palette lease; existing
  broad `ft-*` icons remain appropriate for file identity while exact-type fills use the
  distribution palette.

Do not combine these modules back into folder `index.js`.

#### `src/metabrowser/builtin_plugins/folder/index.js`

This file only:

1. validates that `window.metabrowser` exists;
2. creates the category-palette pool and Overview registry;
3. publishes `mb.folderOverview`;
4. registers the File types and README descriptors;
5. registers the Overview and Treemap view adapters.

It contains no HTML templates, fetch loops, layout math, or retained view instance.

#### `src/metabrowser/builtin_plugins/folder/manifest.toml`

Declare exactly two folder views:

1. `overview`, label **Overview**, default, `content-body folder-overview-host`;
2. `treemap`, label **Treemap**, lazy peer, `content-body folder-treemap-host`.

Overview’s manifest printability starts false and is published dynamically by the
composer. Remove the README view and `extra_scripts` entry.
Do not declare the future Files tab.

### Styles and Asset Packaging

#### `src/metabrowser/static/styles.css`

Add only design tokens and palette utility classes:

- twelve light/dark `--mb-distribution-category-*` tokens;
- `--mb-distribution-other` and `--mb-distribution-track`;
- `--mb-distribution-track-height` and the existing general segment-gap contract;
- `.mb-distribution-slot-1` through `-12` and `.mb-distribution-other`, each assigning
  the component color variable from a token.

No folder layout selector belongs in core styles.

#### Folder plugin styles

- `overview.css` owns the shared visible headings, disclosure-button reset and focus
  treatment, responsive document-edge alignment, vertical panel stack, flat surface
  presentation, local error, loading slot, print exclusion, and wide/narrow bands.
  It does not override KPress document-card styling.
- `file_type_summary.css` owns the fixed table columns, row groups, repeated 8-pixel
  tracks, metric gutters, numeric alignment, narrow-width contraction, skeletons,
  status, and reduced-motion behavior.
- Existing `styles.css` remains Treemap-specific.
- Every value comes from an existing token or one of the new documented distribution
  tokens; no category color literal appears in plugin CSS.
- `manifest.toml` lists the two additional styles with `extra_styles` so wheel asset
  discovery and cache behavior stay manifest-driven.

### Test File Map

Keep tests beside the boundary they protect rather than accumulating one feature-wide
harness.

Python and route coverage:

- `tests/test_inventory_rollup.py` ports the WIP rollup unit and performance cases and
  adds dual selection, exact Other, zero limits, and zero-byte/ignored-only unions.
- `tests/test_rollup_route.py` owns query parsing, 400/404 behavior, clamping, cold
  envelopes, metadata, and the `depth=0&top=0&ext_rank=dual` summary request.
- `tests/test_rollup_wire_models.py` owns every node, tally, result, envelope, sentinel,
  nonnegative, monotonicity, and population-sum validator failure.
- `tests/test_api_folder_envelope.py` owns folder views, pending/complete aggregates,
  README discovery, unusual casing, scan cap, symlinks, empty folders, safe paths, and
  no-store headers.
- `tests/test_index_cdn_origins.py` replaces the root README seed assertion with root
  Overview startup and checks strict helper asset order.
- `tests/test_browser_lifespan_e2e.py` extends filesystem-to-inventory-to-envelope and
  rollup coverage for live file and README mutations.
- `tests/test_browser_assets.py`, `tests/test_plugin_extra_assets.py`, and
  `tests/test_distribution_policy.py` own SDK presence, relative ES-module/static style
  packaging, and built-wheel inclusion respectively.

Strict JavaScript and DOM coverage, each with a same-named `tests/test_*_js.py` Node
wrapper:

- `tests/dom/inventory_scope_behavior.js` tests path relevance, debounce, active/stale
  transitions, abort, retry callback, and disposal.
- `tests/dom/contribution_registry_behavior.js` tests schema rejection, duplicates,
  freezing, stable order, unregister, and independent registries.
- `tests/dom/resource_context_behavior.js` tests seeding, immediate delivery,
  multiplexing, generation races, last-subscriber cleanup, and one request per path.
- `tests/dom/view_state_behavior.js` tests active delivery, transition deduplication,
  print validation, active-view print events, and idempotent unsubscribe.
- `tests/dom/markdown_mount_behavior.js` tests direct/composed parity, two simultaneous
  TOCs, abort, late completion, diagnostics/error DOM, and exactly-once disposal.
- `tests/dom/folder_overview_behavior.js` tests placement/ID order, hidden optional
  slots, out-of-order resolution, keyed preserve/update/remount, local Retry, print
  aggregation, synthetic third panels, active gating, and teardown.
- `tests/dom/file_type_summary_model_behavior.js` tests tally normalization, active
  populations, sums, percent/size/count boundaries, row order, and every discriminated
  state without a DOM.
- `tests/dom/file_type_summary_behavior.js` tests the flat summary body, grouped table,
  inline metric fills, escaped labels, keyed patches, filters, Retry, hidden refresh,
  empty/ignored-only/zero-byte DOM, and teardown.
- `tests/dom/category_palette_behavior.js` tests deterministic probing, distinct capped
  slots, Other, reservation, cross-view leases, path isolation, and final release.
- `tests/dom/folder_treemap_behavior.js` receives the WIP interaction cases after the
  split and adds shared-palette and supported active-view assertions.

`tests/test_plugin_sdk_helpers.py` and TypeScript check-JS lock the public method and
declaration names.
Avoid source-text assertions for behavior that a DOM or route contract
test can execute.

### Lifecycle, Error, and Performance Invariants

One selected folder may have one mounted Overview and one lazily mounted Treemap.
Switching tabs does not dispose either, but `mb.viewState` prevents hidden views from
refreshing. Navigating to another path disposes every mounted view, context subscriber,
panel record, rollup watch, filter listener, active listener, request, timer, Retry
handler, TOC, resize observer, tooltip, and palette lease.

Disposal is idempotent at every level.
Late resolver, Markdown, rollup, or view-mount completions check their generation or
abort signal before touching DOM. A parent disposes children in reverse acquisition
order and catches only cleanup errors it can log without masking the original failure.

Panel resolver and mount failures are isolated by contribution.
Abort is never rendered as an error.
An invalid descriptor fails during registration; a permanent request error has no Retry;
a transient request error does.
A successful stale File types model stays visible while a refresh error is reported
quietly. No server error exposes an absolute root path.

Performance gates are:

- no new crawl and one O(N) in-memory rollup pass per request;
- no emitted child nodes for the summary request;
- at most ten named rows plus Other;
- one rollup watch per mounted File types panel;
- one multiplexed folder-envelope refresh per selected path;
- no panel-resolution or rollup refresh for hidden Overview or Treemap views; the one
  folder-envelope refresh remains active for the visible shell header;
- no full panel or table replacement during ordinary live updates;
- the existing 100,000-entry rollup budget and global node/payload caps remain tested.

## Implementation Plan

The top-level implementation epic is `mb-ilty`. Its children are independently
verifiable and carry their blockers in tbd:

| Bead | Scope | Blocked by |
| --- | --- | --- |
| `mb-qbmw` | Reconcile the folder-view foundation | — |
| `mb-lnfw` | Extract and extend the inventory rollup | `mb-qbmw` |
| `mb-qm04` | Stabilize folder envelopes and root routing | `mb-qbmw` |
| `mb-in4t` | Add strict browser lifecycle primitives | `mb-qbmw` |
| `mb-0c0e` | Make rendered Markdown mounts instance-safe | `mb-in4t` |
| `mb-0c9h` | Implement the Folder Overview registry and composer | `mb-qm04`, `mb-in4t` |
| `mb-o95v` | Contribute README to Folder Overview | `mb-0c0e`, `mb-0c9h` |
| `mb-6ol0` | Implement the dual-metric File types panel | `mb-lnfw`, `mb-in4t`, `mb-0c9h` |
| `mb-ds1s` | Share category colors and modularize Treemap | `mb-6ol0` |
| `mb-w0xh` | Complete integration and release validation | `mb-o95v`, `mb-ds1s` |

After `mb-qbmw`, the server rollup, folder envelope, and strict browser primitives can
proceed independently.
Markdown can proceed as soon as the browser lifecycle primitives exist; README and File
types meet only in the final composition, avoiding a long serial implementation branch.

### Phase 0: Reconcile the Folder-View Foundation

- [x] Port the three baseline slices from `feat/folder-treemap` onto current `main`
  while preserving newer shell behavior.
- [x] Move WIP code directly into the target modules; do not land the hard-coded README
  tab or monolithic folder plugin as an intermediate public contract.
- [x] Update root startup and folder route tests so no-hash startup opens root Overview.

### Phase 1: Stabilize the Server Data Plane

- [x] Extract `inventory_rollup.py` and make `InventoryIndex.rollup` a thin delegate.
- [x] Add zero-depth/top bounds, opt-in dual ranking, exact Other arithmetic, and full
  wire validators.
- [x] Add bounded README discovery and make the folder envelope always advertise
  Overview and Treemap.
- [x] Lock byte-heavy, count-heavy, ignored-only, extensionless, compound-extension,
  zero-byte, cold, scanning, truncated, and empty fixtures before browser work.

### Phase 2: Add Strict Reusable Browser Primitives

- [x] Add request errors, shared formatters, scoped inventory watch, generic
  contribution registry, resource-context store, and view-state bridge under strict
  check-JS.
- [x] Reduce `plugin_sdk.js` to adapters for those modules and extend exact public
  types.
- [x] Integrate context seeding, dynamic print state, per-instance view handles, and
  root folder startup into `app.js` with focused DOM tests.

### Phase 3: Build Overview and Instance-Safe Markdown

- [x] Split Markdown source/rendered modules and replace singleton TOC state with a
  returned mount handle.
- [x] Add the folder Overview registry facade and keyed composer with independent
  resolve, mount, Retry, print, and disposal boundaries.
- [x] Register README as a conditional document contribution and prove parity with the
  ordinary Markdown view.
- [x] Register a synthetic third panel in tests to prove that composer markup contains
  no built-in panel branching.

### Phase 4: Build File Totals, File Breakdown, and Treemap

- [x] Add the pure File types model, paired distribution view, controller, exact empty
  states, and Show ignored switching.
- [x] Add the path-scoped palette pool and route both File types and hierarchical
  Treemap marks through it.
- [x] Expose the navigation-owned file icon through the public SDK and use its shared
  alignment primitive in exact extension rows, Treemap file labels, and navigation.
- [x] Split the WIP Treemap into layout, model, and controller modules and adopt the
  supported active-view lifecycle.
- [x] Register Files as the required first summary panel and File Breakdown as the
  required collapsed detail panel; validate Overview with README, without README, and
  completely empty.

### Phase 5: Documentation, Packaging, and Validation

- [x] Document the shipped `mb.folderOverview`, folder-context, view-state, rollup, and
  Markdown mount contracts in `docs/plugins.md`.
- [x] Change the main architecture and design-system sections from planned to shipped,
  preserving this spec as the detailed authority.
- [x] Verify manifest-driven JS/CSS inclusion, strict type coverage, wheel contents, and
  installed-wheel smoke behavior.
- [x] Complete real-browser light/dark, wide/narrow, keyboard, reduced-motion, live
  update, and print review.
- [x] Run `make verify`, review the final diff, sync and close completed tbd children,
  push the branch, and watch CI to completion.

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

- Registry tests cover descriptor validation, duplicate IDs, fixed placement ordering,
  stable ID tie-breaking, a null optional resolver, asynchronous out-of-order
  resolution, transient Retry, permanent errors without Retry, abort, and exactly-once
  disposal.
- Composer tests use File types, README, and a synthetic third contribution to prove
  that adding a panel does not require an Overview template branch.
  They distinguish a future top-level Files view from an Overview contribution.
- Pure tests cover percent formatting boundaries, zero denominators, count
  pluralization, byte-unit boundaries, maximum-share ordering,
  Documentation/Code/Data/Other classification from shared presets, stable color slots,
  Other-last behavior, and malformed rows.
- DOM tests assert that Totals precedes Documentation/Code/Data/Other, Total precedes
  the conditional Ignored row, both metric fills share one slot class, semantic column
  headers are visually hidden, exact adjacent values remain, the zero-byte total stays
  truthful, decorative tracks are hidden, and labels are escaped.
- Lifecycle tests assert one active watch, no hidden-view refresh, abort and listener
  cleanup on disposal, Retry recovery, and focus preservation during keyed updates.
- Filter tests assert that **Show ignored** changes the selected integer columns while
  recency, type, and size filters leave the composition unchanged.
- Composition tests assert that folder Overview gets File types above the README
  document, the wide-band TOC starts on the README row, and directly opened Markdown
  does not get File types.
  README output must match the ordinary rendered Markdown mount, README-less Overview
  must avoid a fake document, and print must include only printable contributions.
- Empty-folder tests assert that Overview and File types remain present with “No files
  to summarize.”, no standalone tally, bars, table, arithmetic artifacts, fake README,
  or confusion with loading or failure.

### Real-Browser Review

Use directories representing one type, ten types, more than ten types, thousands of tiny
files, one dominant binary, ignored dependency trees, no README, a long README TOC, and
an empty directory. Review ordinary and narrow preview widths in both themes.
Confirm that the panel reads as directory chrome, the README remains visually primary,
Files and Bytes switch atomically, the two top composition tracks stay full width,
percentages read as File Breakdown track endpoints, and ignored-state changes do not
trigger a new rollup request.
At regular and wide widths, confirm that README retains the ordinary Markdown card and
that File types aligns to its outer edges.
Below the card breakpoint, confirm that the card disappears and both sections align to
the README prose edge.
Confirm that a completely empty folder still reads as a deliberate, finished Overview
rather than an unpainted preview.

## Risks and Mitigations

- **The panel competes with the README.** It stays compact and flat inside the
  responsive document boundary.
  The ordinary README card and common heading hierarchy separate the two sections
  without adding a File types card or interaction.
- **Byte ranking hides count-heavy types.** The server selects categories using the
  maximum of both metrics and both ignored-file populations.
- **Ignored dependencies dominate.** The panel follows the existing Show ignored state,
  makes its scope explicit through an exact leading row, and already has both
  populations on the wire.
- **Colors drift during live updates.** The mounted view reserves slots for its lifetime
  and updates keyed rows rather than rebuilding rank-colored markup.
- **Arbitrary extensions exhaust the palette.** The visible named set is capped at ten
  against twelve slots; the unbounded tail is one neutral Other row.
- **The summary duplicates the Treemap.** Overview answers composition with exact
  totals; Treemap answers spatial hierarchy and navigation.
  They share data and type colors but not controls or layout.
- **Panel timing produces layout jumps or accidental ordering.** Named placement bands
  and stable IDs determine slots before asynchronous resolution completes; script-load
  order never does.
- **One panel failure blanks the folder.** Resolver and renderer errors are caught at
  the panel boundary, recovery affects only that contribution, and sibling lifecycles
  continue.
- **KPress DOM changes break composition.** One instance-safe Markdown mount contains
  the selector and TOC knowledge and has parity tests.
  The folder plugin calls it rather than querying KPress internals.
- **Partial scans look final.** Scanning and truncation remain visible beside the data,
  and pending never renders as empty.

## Rollout Plan

Land this with the folder-view work or immediately after its rebase onto current main.
The panel platform, File types contribution, and README contribution ship as one folder
Overview contract. Do not ship a root-only README decorator or a hard-coded two-panel
template as an intermediate state.

The rollout is additive to the rollup endpoint and folder plugin.
Existing file views, explicit README deep links, and print behavior remain unchanged.
No disclosure preference or data migration is required.

The Overview-default and panel-registry decisions supersede the WIP folder plan’s
Treemap-default and conditional-README-tab decisions.
Record that change in the folder plan when the two branches are reconciled so there is
one final folder-view contract.

## Open Questions

No product decision blocks implementation.
Real-browser review should still tune spacing and density, but not the information
architecture: Overview remains the default, File types remains present, README remains
conditional, and future Files remains a peer view.
Files remains initially expanded and File Breakdown initially collapsed in sparse,
empty, root, and nested folders alike.

## Acceptance Criteria

- A folder selected through general navigation opens Overview; a folder selected inside
  Treemap keeps Treemap active.
  Treemap remains a peer tab, and the folder view contract can add a future Files peer
  without treating it as a panel
- Overview uses a public, deterministic, failure-isolated panel registry rather than a
  hard-coded File types and README template
- Files and File Breakdown are always present in the summary band; Files starts expanded
  and File Breakdown starts collapsed.
  A direct-child README is a conditional document panel below them and uses the ordinary
  rendered Markdown presentation
- README keeps the ordinary Markdown card at regular and wide widths and its standard
  borderless layout at narrow widths; both file sections stay flat and align to the card
  or prose edge for the active band
- An explicitly opened README has no directory summary
- Files owns the only Overview Files / Bytes chooser; changing it updates Files, File
  Breakdown, and Treemap through one shared state without refetching
- Files shows disjoint Files and Ignored rows whose selected-metric values conserve the
  complete directory population.
  Each nonzero row is a full-width composition segmented with File Breakdown’s colors,
  has no percentage label, and the Ignored row is dimmed.
  Both tracks share File Breakdown’s registry-group and selected-metric order, and each
  semantic-family segment exposes the bold type name plus exact count and byte size in
  the shared navigation tooltip
- File Breakdown shows a fixed Type/Metric table grouped under the recommended registry
  categories, omitting empty groups and adding no group subtotals
- Each breakdown row shows its logical type, selected-metric value,
  population-normalized fill, and percentage; changing the metric sorts rows by that
  metric
- A row keeps the same color across metrics; no separate circle, aggregate bar, or
  legend is needed
- Exact extension rows and Treemap file labels use the same shared file icon as
  navigation; family, No extension, Other types, Files, and Ignored headings stay
  iconless, while unknown exact children use the generic blank-page fallback
- Show ignored uses the same labelled checkbox primitive as navigation, starts checked
  without a saved preference, and scopes File Breakdown and Treemap without hiding the
  explicit Files and Ignored context
- Each subsection shows at most ten rows before an exact, reversible N more disclosure
- No extension is a named group, and compound extensions use their canonical indexed
  type
- Scanning, truncation, empty, completed-index-miss, zero-byte, and failure states are
  distinguishable and truthful
- A complete empty folder still renders Overview, Files, and File Breakdown truthfully,
  without a fake README panel
- The panel updates from inventory changes, retains category colors and keyed DOM, and
  disposes every watcher and listener on view replacement
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
- [Filter controls and fine-grained navigation filtering](plan-2026-08-09-nav-filter-controls.md)
- [Folder views, Treemap, and unified filtering](https://github.com/jlevy/metabrowser/pull/23)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
