# Feature: Semantic File Type Families

**Date:** 2026-08-13 (last updated 2026-08-13)

**Author:** Metabrowser contributors

**Status:** Implemented and validated.

## Overview

Metabrowser treats the inventory’s bounded logical extension as the visible unit in the
folder Files summary and navigation type filter.
This is precise, but it fragments one recognizable language or format across rows such
as `.js`, `.mjs`, `.cjs`, and `.min.js`.

Add a small, declarative taxonomy of semantic file type families.
A family has a stable ID, a user-facing label, one broad category, and one or more
canonical extension suffixes.
The same taxonomy drives folder Overview aggregation, navigation filter groups,
categorical color identity, and server tallies.
Unknown or deliberately ungrouped extensions continue to appear as raw extensions, so
the catalog can stay curated rather than pretending to name every file type.

The first implementation should cover the common, high-confidence families that make the
UI materially easier to scan.
JavaScript, TypeScript, CSS, YAML, and Python are required examples.
The taxonomy remains intentionally open-ended, and unsupported or ambiguous extensions
retain their current raw-extension behavior.

This plan is a follow-up to the implemented
[folder Overview plan](plan-2026-08-12-directory-file-type-summary.md).
It defines and tracks the runtime implementation across the server, browser shell,
folder plugin, tests, and durable documentation.

## Goals

- Define file type categories, semantic families, canonical extension buckets, and raw
  fallbacks from one server-owned catalog.
- Group known extensions under readable labels such as **JavaScript**, **TypeScript**,
  **CSS**, **YAML**, and **Python** in the folder Files summary.
- Let a family row expand to the canonical extension buckets that contribute to its
  totals, while keeping family rows collapsed by default.
- Preserve exact count, byte, ignored-file, and percentage accounting at the family and
  child levels.
- Add semantic family parents to the navigation type chooser between the broad
  Docs/Code/Data presets and the longer canonical-extension list.
- Make broad category, family, and extension selections use the same matching rules and
  authoritative tallies.
- Preserve raw extensions, **No extension**, and **Remaining types** as honest
  fallbacks.
- Keep color identity aligned across Files and Treemap while leaving exact file icons
  tied to the displayed extension.
- Keep the API bounded, live-update safe, keyboard accessible, responsive, and
  compatible with existing plugin consumers.

## Non-Goals

- Building an exhaustive language database or promising a name for every extension.
- Detecting a language from file contents, shebangs, MIME types, parsers, or repository
  metadata.
- Resolving inherently ambiguous extensions such as `.m`, `.pl`, or `.r` when an
  extension-only decision would be misleading.
- Replacing file-kind classification, renderer selection, syntax highlighting, or the
  file-icon matcher. Those answer different questions.
- Adding family-specific icons.
  A family is an aggregate and remains text-only.
- Making **Remaining types** selectable in the navigation filter.
  It is a response budget tail, not a stable semantic identity.

## Background

Four related vocabularies currently overlap without representing the same concept:

1. `FsEntry.ext` is the bounded logical extension produced by `derive_ext`, such as
   `.min.js`, `.d.ts`, or `.tar.gz`.
2. `FILTER_TYPE_PRESETS` defines broad Docs, Code, and Data filters as extension and
   whole-filename tokens.
3. `FILE_TYPES` in the browser shell chooses a file icon and subtype class.
4. The folder rollup returns bounded exact-extension tallies for Files and Treemap.

The folder Files model currently infers broad category membership by checking whether an
exact rollup key ends in a preset extension.
That correctly puts `.min.js` under Code, but the navigation preset tally uses exact
membership and can disagree.
The rollup also caps exact extensions before the browser sees them, so client-only
family aggregation would produce incomplete parent totals and incomplete expansions.

The semantic family layer must therefore be defined once and applied before response
truncation on the server.
Browser helpers consume the serialized catalog rather than copying it.

### Relationship to GitHub Linguist

The preceding folder Overview research correctly separates GitHub’s useful visual
grammar from Linguist’s repository-language classifier.
The implementation also checks the current Linguist model rather than treating GitHub’s
visible bar as an extension lookup table.

Linguist owns a large `languages.yml` catalog and then refines classification through
repository overrides, modelines, filenames, shebangs, extensions, XML headers,
heuristics, and Bayesian classification.
Its repository language bar excludes binary, vendored, generated, documentation, data,
and prose files, then reports byte share for the remaining languages.
Metabrowser intentionally answers a different question: what files are present in this
selected folder, including documentation, data, unknown, and optionally ignored files,
by both file count and bytes.

The semantic family model is consistent with Linguist where the constraints align:

- use a declarative, reviewed catalog with stable semantic IDs;
- recognize common aliases such as `.yaml` and `.yml`, module variants such as `.js`,
  `.mjs`, and `.cjs`, and typed variants such as `.ts`, `.mts`, `.cts`, and `.tsx`;
- retain a family/category distinction instead of deriving display names from icons;
- keep ambiguous extensions conservative rather than claiming precision the available
  evidence cannot support; and
- use bytes as one first-class proportion, while adding file count because a file
  browser must also reveal many-small-file populations.

The deliberate differences are part of the product contract:

- classification is deterministic from indexed filenames and logical extensions; it does
  not read file contents or repository attributes on a request path;
- the catalog is a curated UI taxonomy, not a vendored or partial copy of Linguist;
- CSS includes common stylesheet variants such as SCSS and Less because users browse
  them as one practical family even though Linguist currently identifies those as
  distinct languages;
- C and C++ share one family because extension-only metadata cannot reliably
  disambiguate shared headers such as `.h`;
- SQL remains in Metabrowser’s existing Code filter for compatibility and task-oriented
  browsing, although Linguist declares SQL as data and excludes data languages from its
  repository language bar;
- Vue and Svelte remain readable standalone families rather than being folded into HTML;
  and
- unsupported types stay visible as raw extensions instead of disappearing from the
  summary.

These differences should remain explicit in catalog reviews.
A future content-aware classifier could add evidence without changing family IDs, but
exhaustive Linguist parity is neither required nor desirable for this metadata-only
rollup.

## Design Principles

1. **Retain exact identity beneath semantic identity.** Files still have their original
   logical extension for icons, tooltips, and plugin contracts.
   The taxonomy adds a semantic match; it does not rewrite `FsEntry.ext`.
2. **Use suffix rules only where declared.** A family member `.js` matches `.js` and a
   compound logical extension ending in `.js`, such as `.min.js`. An ungrouped raw
   extension remains exact.
3. **Prefer conservative incompleteness to incorrect names.** Unknown or ambiguous
   extensions remain visible as raw extensions.
4. **Aggregate before bounding.** Family totals and canonical child totals are computed
   from the complete subtree snapshot, then the ungrouped raw tail is capped.
5. **Do not duplicate populations.** Top-level family and raw rows partition the folder
   population. Expanded child rows explain a family parent and are not added again when
   checking root-total conservation.
6. **Keep one meaning for color.** Known-family extensions share the family’s palette
   key in Files and Treemap.
   Raw extensions keep an extension key.
   Icons remain exact file identities.
7. **Disclosures must reveal information.** A family with only one nonzero canonical
   child renders as a named row without a chevron.
   A disclosure appears only when at least two child buckets are present.

## Terminology

- **Logical extension:** The inventory’s final one or two eligible suffix components,
  such as `.min.js` or `.d.ts`.
- **Canonical extension:** The declared family suffix that matches a logical extension.
  For example, `.min.js` canonicalizes to `.js` inside JavaScript.
- **Family:** A stable named aggregate such as JavaScript or YAML.
- **Category:** One of Documentation, Code, Data, or Other.
- **Raw extension:** A logical extension that matches no declared family.
- **Family key:** A stable palette and model key of the form `family:<id>`.

## Taxonomy Model

### Authoritative Declaration

Extend `src/metabrowser/file_type_filters.py` so it owns a declarative catalog rather
than only three flat presets.
Keep the data separate from file icons and renderer kinds.
The conceptual schema is:

```python
class FileTypeFamily(TypedDict):
    id: str
    label: str
    category: Literal["docs", "code", "data"]
    extensions: tuple[str, ...]


class FileTypeCategory(TypedDict):
    id: Literal["docs", "code", "data"]
    label: str
    extra_values: tuple[str, ...]
```

`extensions` contains normalized lowercase suffix rules with a leading dot.
`extra_values` retains category members that are not represented by a family, including
exact filenames such as `README`, `LICENSE`, `Makefile`, and `Dockerfile`.

Generate the existing `FILTER_TYPE_PRESETS` compatibility value from the category extras
plus family members.
There must not be a second hand-maintained copy of family extensions in Python,
JavaScript, the folder plugin, or documentation.

### Initial Catalog Policy

The initial catalog is curated by usefulness and confidence, not completeness:

- It must include JavaScript (`.js`, `.mjs`, `.cjs`, and `.jsx`), TypeScript (`.ts`,
  `.mts`, `.cts`, and `.tsx`), CSS and its commonly co-located stylesheet variants, YAML
  (`.yaml` and `.yml`), and Python with at least `.py`.
- It should include other existing preset members when several extensions routinely
  describe one recognizable language or format and the grouping is not ambiguous.
- It may include a small number of high-frequency singleton families when the readable
  name materially improves scanning.
- It must not group an ambiguous extension merely to reduce row count.
- Adding a family later is a data change with taxonomy, parity, and UI contract tests;
  it does not require a new rendering path.

The implementation PR should list the final seed catalog explicitly for review.
This plan does not claim to enumerate every language or extension.

The implemented seed catalog is:

- Documentation: Markdown, Plain text, reStructuredText, AsciiDoc, Org, PDF, Word, Rich
  Text, OpenDocument, and EPUB
- Code: Python, JavaScript, TypeScript, CSS, HTML, Rust, Go, Java, Kotlin, Swift, C/C++,
  C#, Ruby, PHP, Scala, Clojure, Elixir, Erlang, Haskell, Lua, Julia, Dart, Vue, Svelte,
  Shell, PowerShell, and SQL
- Data: JSON, YAML, TOML, INI, Delimited text, XML, Parquet, Arrow, Avro, ORC, Protocol
  Buffers, GraphQL, and SQLite

Ambiguous `.m`, `.mm`, `.ml`, `.pl`, `.r`, and `.db` tails remain raw rows inside their
broad category.
Category-only filenames such as README, LICENSE, Makefile, and Dockerfile
also remain outside semantic families.

### Matching and Canonicalization

`derive_ext` bounds the input vocabulary before taxonomy matching.
It retains at most the final two short, lowercase, alphanumeric suffix components.
`bundle.js.map` remains `.js.map`, while `bundle.umd.min.js.map` and `types.d.ts.map`
normalize to `.js.map` and `.ts.map`. A single `.map` remains `.map`. This cap preserves
common compound formats without allowing descriptive filename segments to multiply raw
tally rows. The indexed value is authoritative on every browser path; clients do not
re-derive it from the filename when `ext` is present.

Add pure Python helpers with equivalent browser behavior:

- `family_for_extension(extension)` returns the family and matched canonical suffix.
- `canonical_extension(extension)` returns the matched suffix or the normalized raw
  extension.
- `category_for_file(name, extension)` returns the family’s category first, then checks
  category extras, then returns Other.
- `distribution_key_for_extension(extension)` returns `family:<id>` for a known family,
  the normalized raw extension for an unknown type, and the neutral key for aggregate
  tails.
- `serialize_file_type_taxonomy()` returns a frozen, JSON-safe settings value for the
  browser.

Matching rules are deterministic:

1. Normalize case and leading-dot form.
2. Match a declared member when the logical extension equals the member or ends with it.
3. Prefer the longest matching declared member.
4. Reject duplicate family IDs, duplicate members, invalid category references, empty
   labels, and ambiguous equal-length matches during module initialization or a focused
   validation test.
5. Match dotted category extras with the same declared suffix semantics, and match
   whole-filename category extras case-insensitively and exactly.
6. Leave unknown extensions raw and classify them through broad category extras when
   possible, otherwise Other.

The `.js` member therefore covers `.min.js`, and `.ts` covers `.d.ts`, without listing
each compound form. The original logical extension remains available to consumers that
need it.

### Browser Contract

Expose the serialized catalog in `METABROWSER_SETTINGS.FILE_TYPE_TAXONOMY` and add a
strict browser module at `src/metabrowser/static/file_type_taxonomy.js`. It validates
and freezes the injected data, provides the matching helpers above, and publishes the
read-only runtime used by the shell.

Extend the public SDK with a `fileTypes` facade so the built-in folder plugin and future
plugins do not reach into private `app.js` state.
The facade should expose immutable category/family descriptors plus `matchExtension`,
`canonicalExtension`, and `distributionKeyForExtension`. Keep `fileTypeIcon(path)`
unchanged.

Update `src/metabrowser/static/types.d.ts`, `docs/plugins.md`, the asset loading order,
and plugin SDK contract tests.
The Python catalog remains the only declaration of membership; JavaScript implements
only the matching algorithm over injected data.

## Server Aggregation and Wire Contracts

### Navigation Tallies

Refactor `InventoryIndex.navigation_tallies` to classify each file once during its
existing complete-index pass and return a typed result rather than an expanding
positional tuple. The result contains:

- root tracked/ignored count and byte totals;
- existing raw logical-extension tallies for compatibility;
- canonical-extension tallies for the navigation child list;
- family tallies keyed by stable family ID;
- broad category preset tallies;
- recency tallies.

Every tally retains separate tracked and ignored counts.
`/api/tree` adds `canonical_extensions` and `type_families` fields while retaining
`extensions` and `type_presets` for compatibility.
The browser switches to the new fields when present and can fall back to the old fields
during a mixed-version transition.

Family and category counts use the same classifier as filtering.
A `.min.js` file must contribute to canonical `.js`, JavaScript, and Code exactly once
in each corresponding population.

### Folder Rollup Tallies

Extend the subtree aggregation in `src/metabrowser/inventory_rollup.py` with a bounded
semantic breakdown computed from the complete extension counters.
Preserve the existing `ext_tallies` response for Treemap and plugin compatibility, and
add `type_tallies`:

```json
{
  "type_tallies": {
    "families": [
      {
        "id": "javascript",
        "all_files": 150,
        "all_bytes": 10485760,
        "unignored_files": 145,
        "unignored_bytes": 9437184,
        "extensions": [
          [".js", 120, 7340032, 116, 6815744],
          [".mjs", 20, 2097152, 20, 2097152],
          [".cjs", 10, 1048576, 9, 524288]
        ]
      }
    ],
    "extensions": [
      [".rs", 12, 2097152, 12, 2097152],
      ["(none)", 3, 256, 3, 256],
      ["", 8, 65536, 7, 61440]
    ]
  }
}
```

Family child rows are canonical buckets, so a `.min.js` file is represented in the `.js`
child. Family members make the child count inherently bounded by the fixed catalog.
The ungrouped raw-extension list uses dual count/byte ranking and a dedicated `type_top`
request bound. **No extension** is emitted explicitly when present and does not consume
the raw-extension budget.
Omitted ungrouped types are combined into the final empty-key **Remaining types** row.

Add wire validation with these invariants:

- every metric is a nonnegative integer;
- unignored values do not exceed all-file values;
- canonical children sum exactly to their family parent;
- top-level family parents plus ungrouped extension rows sum exactly to the root;
- family IDs are unique and known to the response catalog;
- no extension appears in more than one top-level population;
- No extension appears at most once and Remaining types is final;
- the response remains bounded independently of inventory size.

Extend `RollupOptions`, `/api/rollup`, `fetchRollup`, `watchRollup`, settings defaults,
JSDoc, and TypeScript declarations with `type_top`. Existing callers that omit it keep
their current `ext_tallies` behavior.

## Folder Files Overview

### Presentation Hierarchy

Keep the existing Totals, Documentation, Code, Data, and Other rowgroups.
Within each category, display a single ordered stream of:

- semantic family parent rows;
- ungrouped raw extension rows;
- No extension and Remaining types fallbacks where applicable.

Family and raw rows use the same dual count/byte score and deterministic key tie-breaker
for ordering. Remaining types stays last in Other.

A family parent row:

- uses the readable family label, such as **JavaScript**;
- has no file icon because it represents an aggregate;
- reports exact file and byte values, percentages, and independently normalized bars;
- uses `family:<id>` as its palette key;
- places a gray proportional chevron immediately after the label when at least two
  nonzero child buckets exist;
- begins collapsed on every newly mounted folder Overview.

Expanding the parent reveals indented canonical extension rows directly beneath it.
Each child:

- shows its canonical extension label and the shared icon for a synthetic filename;
- uses the same family palette color as its parent;
- reports percentages against the folder’s selected population, not against the family,
  so parent and child values retain one denominator and the children visibly sum to the
  parent;
- follows the catalog’s deterministic member order, with zero rows omitted.

A singleton family still uses the readable parent label but has no disclosure.
Showing an expandable `.py` child under a Python row would add no information.

### Interaction and State

Use a table-compatible disclosure button inside the row header rather than placing
`details` around table rows.
The button carries `aria-expanded`, `aria-controls`, Enter and Space activation, visible
keyboard focus, and the same trailing-chevron geometry as other section disclosures.
The label and chevron are the hit target; metric cells remain noninteractive.

Store expanded family IDs on the mounted distribution view handle.
Keyed live updates preserve expansion and focus for families that remain present, remove
stale state when a family disappears, and do not remount the whole table.
Folder replacement creates a new collapsed state.

Update `file_type_summary_model.js` to normalize the hierarchical response and build
family parent/child rows.
Update `distribution_view.js` and `file_type_summary.css` for keyed parent rows,
accessible disclosures, child indentation, responsive metrics, reduced motion, print
behavior, and live updates.
The empty, ignored-only, zero-byte, truncated, failed, and unavailable states remain
unchanged.

## Navigation Type Chooser

The type menu becomes a three-tier hierarchy separated by the existing menu dividers:

1. broad **Docs**, **Code**, and **Data** presets;
2. present semantic families such as **JavaScript**, **TypeScript**, **CSS**, **YAML**,
   and **Python**;
3. the existing bounded list of canonical extensions.

Category and family rows are text-only aggregate choices with tracked/ignored tallies.
Canonical extension rows retain their exact extension icons.
Only families with a nonzero count in the selected ignored-file population appear.
The curated catalog keeps this middle tier bounded; raw extensions retain the existing
menu cap.

Selecting a category adds its category extras and every family member token.
Selecting a family adds all of its canonical member tokens.
Turning a parent off removes only its own values, matching the existing additive
Docs/Code/Data behavior.
An aggregate row is checked only when all of its member values are selected.
Removing a child makes its parents unchecked; no third visual state is introduced in
this phase.

`filter_state.js` canonicalizes each row’s logical extension before matching selected
extension tokens.
A selected `.js` therefore includes `.min.js`; an unknown raw extension
remains exact. Exact whole-filename tokens continue to reach extensionless files such as
README and LICENSE.

Generalize `filter_controls.menuGroupHtml` from one undifferentiated preset list to
ordered preset sections without embedding file-type semantics in the control primitive.
The trigger summarizes an exact family selection by family label before falling back to
the existing `.ext +N` form.
Filtering remains transient and stays out of the URL.

The Recent source, live overlays, lazy tree rows, and normal tree rows all pass the same
logical extension through the shared predicate.
No source may re-derive a last-dot extension and bypass canonicalization.

## Color and Icon Identity

Known-family extensions use `family:<id>` as their distribution palette key.
Apply that mapping in both the Files summary and Treemap:

- family parents and children share one color;
- Treemap files in the family use that family color;
- Treemap folders whose dominant extension belongs to the family use the same color;
- unknown raw extensions retain their raw-extension palette keys;
- aggregate tails retain the neutral Other color.

This changes categorical grouping, not file identity.
Exact extension children, Treemap files, and navigation rows still resolve icons from
the original filename or a synthetic canonical extension.
Family parents, Total, and Ignored remain text-only.

## Accessibility and Responsive Behavior

- Family disclosures are native buttons with `aria-expanded` and stable controlled-row
  IDs.
- Hidden child rows leave both the visual and accessibility trees.
- Parent metrics remain readable when collapsed, so disclosure is never required to
  understand the folder totals.
- Color is supplementary; labels, values, and hierarchy communicate all information.
- Child indentation must not consume the minimum metric widths at compact and narrow
  container bands.
- The family chevron scales with the inherited label size, uses the shared muted color,
  and follows reduced-motion preferences.
- Focus remains on the family button across live updates and returns to a valid element
  if its family disappears.
- Screen-reader-only Type, Files, and Size column headings remain present.

## Backward Compatibility

- **Code types, methods, and function signatures:** Do not retain obsolete internal
  tuple signatures after callers migrate.
  Keep focused compatibility aliases only where a public import has been documented.
- **Library APIs:** Keep `fileTypeIcon`, existing plugin SDK helpers, and documented
  rollup options. Add the file-type taxonomy facade without changing existing behavior.
- **Server APIs:** Keep `extensions`, `type_presets`, and `ext_tallies`; add
  `canonical_extensions`, `type_families`, and `type_tallies` additively.
- **File formats:** Not applicable.
- **Database schemas:** Not applicable.

The browser may use new fields immediately because server and static assets ship
together, but additive wire compatibility protects plugins and tests that consume the
documented rollup contract.

## File and Function Plan

### Taxonomy Foundation

- `src/metabrowser/file_type_filters.py`
  - add validated category and family declarations;
  - generate `FILTER_TYPE_PRESETS`;
  - add normalization, matching, category, canonical-extension, palette-key, and
    serialization helpers.
- `src/metabrowser/settings.py`
  - inject `FILE_TYPE_TAXONOMY` and a `ROLLUP_FILE_TYPE_RAW_LIMIT` default.
- `src/metabrowser/static/file_type_taxonomy.js`
  - validate/freeze injected descriptors and expose pure matching helpers.
- `src/metabrowser/static/plugin_sdk.js`
  - publish the read-only `mb.fileTypes` facade.
- `src/metabrowser/static/types.d.ts`
  - type settings, taxonomy descriptors, matches, and SDK methods.
- browser asset registration and distribution checks
  - load and package the strict module before shell and plugin consumers.

### Server Tallies

- `src/metabrowser/inventory.py::navigation_tallies`
  - classify once per file and return typed raw, canonical, family, category, and
    recency tallies.
- `src/metabrowser/inventory_rollup.py`
  - retain complete logical-extension counters;
  - aggregate family parents and canonical children before bounding;
  - dual-rank only ungrouped raw rows and emit a conserved tail.
- `src/metabrowser/wire_models.py`
  - define and validate the hierarchical type tally contract and conservation rules.
- `src/metabrowser/server.py::api_tree` and `api_rollup`
  - serialize additive fields, parse `type_top`, and keep aggregation off the event
    loop.
- `src/metabrowser/static/plugin_sdk.js::fetchRollup` and `watchRollup`
  - forward `type_top` while retaining disposal and refresh behavior.

### Navigation Filter

- `src/metabrowser/static/filter_state.js::typeMatches`
  - canonicalize logical extensions through the shared runtime before membership tests.
- `src/metabrowser/static/filter_controls.js::menuGroupHtml`
  - accept ordered generic preset sections and preserve menu keyboard semantics.
- `src/metabrowser/static/app.js`
  - store canonical/family tallies;
  - build category, present-family, and canonical-extension menu tiers;
  - preserve additive parent selection and group-aware trigger summaries;
  - pass logical extensions consistently from tree, Recent, and live-update sources.
- `src/metabrowser/static/styles.css`
  - style generic section dividers and aggregate rows with existing menu tokens.

### Folder Overview and Treemap

- `src/metabrowser/builtin_plugins/folder/file_type_summary.js`
  - request semantic tallies and pass the SDK taxonomy runtime to the model/view.
- `src/metabrowser/builtin_plugins/folder/file_type_summary_model.js`
  - normalize family parents, canonical children, raw rows, and fallbacks;
  - calculate folder-relative metrics and deterministic category ordering.
- `src/metabrowser/builtin_plugins/folder/distribution_view.js`
  - reconcile keyed family rows and child rows;
  - own expanded-family state and accessible disclosure events.
- `src/metabrowser/builtin_plugins/folder/file_type_summary.css`
  - add family disclosure and child indentation without changing metric alignment.
- `src/metabrowser/builtin_plugins/folder/category_palette.js`
  - lease family keys for recognized extensions.
- `src/metabrowser/builtin_plugins/folder/treemap.js` and `treemap_model.js`
  - map file and dominant extensions through the shared distribution key.

### Durable Documentation

- `docs/design-system.md`
  - document semantic families, nested table disclosures, aggregate icon rules, and
    family color identity.
- `docs/architecture.md`
  - document taxonomy ownership, one-pass aggregation, wire compatibility, and palette
    mapping.
- `docs/plugins.md`
  - document `mb.fileTypes`, additive rollup fields, and `type_top`.
- `docs/project/specs/done/plan-2026-08-09-nav-filter-controls.md`
  - add an implementation addendum for the hierarchical type chooser.

## Implementation Plan

Use one implementation phase with red-green changes at each boundary:

- [x] Add and validate the server-owned taxonomy plus the strict browser/SDK runtime.
- [x] Extend navigation and rollup aggregation with conserved semantic tallies and
  additive wire fields.
- [x] Upgrade the navigation chooser to category, family, and canonical-extension tiers.
- [x] Upgrade the folder Files model and table with collapsed family disclosures.
- [x] Align Files and Treemap palette keys for known families.
- [x] Update durable design, architecture, plugin, and navigation-filter documentation.
- [x] Run targeted Python and Node tests, live browser validation, and `make verify`.

## Testing Strategy

### Taxonomy and Parity

- Pin the logical-extension boundary: one- and two-component suffixes remain exact,
  while longer eligible tails retain only their final two components.
- Validate unique IDs, normalized members, category references, and deterministic
  longest-suffix matching.
- Pin required examples: `.min.js` to JavaScript/`.js`, `.d.ts` to TypeScript/`.ts`,
  `.yaml` and `.yml` to YAML, `.py` to Python, and unknown extensions to raw fallback.
- Feed one serialized Python catalog fixture to the browser helper and assert equivalent
  family, canonical extension, category, and palette keys.
- Verify ambiguous and extensionless cases remain conservative.

### Aggregation and Wire Contracts

- Prove tracked/ignored and count/byte totals for mixed family, raw, compound,
  extensionless, and zero-byte inputs.
- Prove canonical children sum to each family and top-level rows sum to the rollup root.
- Prove a family below the raw ranking cutoff still has a complete parent total.
- Prove raw truncation creates one final Remaining types row without absorbing family or
  No extension totals.
- Prove payload size is bounded by the catalog plus `type_top`, not inventory
  cardinality.
- Keep existing `extensions`, `type_presets`, and `ext_tallies` contract tests green.

### Navigation

- Verify three ordered menu tiers, current-population counts, separators, and no icons
  on aggregate category/family rows.
- Verify selecting JavaScript selects its canonical children, `.js` matches `.min.js`,
  removing a child clears the parent check, and Code composes with other selections.
- Verify ignored-file toggles re-rank and hide zero-count families without another scan.
- Verify tree, lazy subtree, Recent, and live-overlay sources produce identical matches.
- Verify menu focus, arrow keys, Space/Enter, Escape, outside click, and trigger
  summary.

### Folder Overview and Treemap

- Verify family parents render in the correct category without icons and start
  collapsed.
- Verify multi-child families disclose canonical rows with icons; singleton families
  have no redundant chevron.
- Verify parent and child bars share a denominator and the family color.
- Verify raw, No extension, Remaining types, Total, and Ignored icon rules remain
  intact.
- Verify disclosure state, focus, palette leases, and DOM identity survive live updates.
- Verify Treemap files and dominant folders use the same family palette key as Files.
- Verify empty, ignored-only, zero-byte, truncated, failed, and unavailable states.

### Visual and Release Validation

- Check representative mixed-language folders at wide, compact, and narrow widths in
  light and dark themes.
- Confirm nested rows do not crowd the metric columns or break README alignment.
- Confirm reduced motion, keyboard focus, screen-reader names, and print output.
- Run `make format`, `make lint-check`, targeted tests during implementation, and the
  complete `make verify` handoff gate.

## Acceptance Criteria

- Indexed logical extensions contain no more than two suffix components, including for
  source maps and declaration source maps.
- JavaScript, TypeScript, CSS, YAML, and Python render by readable family name in Files.
- Known compound logical extensions contribute to one canonical family child and one
  family parent without double counting.
- A multi-child family starts collapsed and expands accessibly; a singleton has no
  redundant disclosure.
- Navigation shows Docs/Code/Data, then present semantic families, then canonical/raw
  extension choices.
- Parent selections apply to every declared child and all render sources use the same
  predicate.
- Unknown and ambiguous extensions remain individually visible and filterable.
- No extension and Remaining types remain distinct and honest.
- Files and Treemap use one family color key while extension/file icons remain exact.
- Old documented wire fields and SDK helpers remain valid.
- Automated and live validation cover boundedness, conservation, accessibility,
  responsive layout, ignored populations, and live updates.

## Rollout Plan

Ship the taxonomy, additive server fields, and browser consumers in one release because
the static application and server are versioned together.
Preserve old wire fields for plugin compatibility.
No data migration or feature flag is required because filter and disclosure state is
transient.

If live validation finds the initial family tier too long, reduce the curated seed
catalog rather than adding a second UI cap with hidden semantic state.
Future families remain ordinary reviewed catalog additions.

## Open Questions

There are no blocking design questions.
The implementation review must approve the exact seed catalog, with the required
examples above as the minimum and ambiguous extensions excluded by default.

## References

- [Folder Overview panels and file-type summary](plan-2026-08-12-directory-file-type-summary.md)
- [GitHub Linguist classification pipeline](https://github.com/github-linguist/linguist/blob/main/docs/how-linguist-works.md)
- [GitHub Linguist language catalog](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
- [Filter controls and fine-grained navigation filtering](plan-2026-08-09-nav-filter-controls.md)
- [Design system](../../../design-system.md)
- [Architecture](../../../architecture.md)
- [Plugin API](../../../plugins.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
