# Design System

Metabrowser’s interface is an information-dense developer tool.
Its design system prioritizes readable file contents, stable spatial relationships,
keyboard-sized controls, and consistent status cues over decorative chrome.

## Principles

1. **The selected item is primary.** Navigation and controls stay compact so a file’s
   contents or a folder’s Overview receives most of the viewport.
2. **Color has one meaning.** Status, file type, chart threshold, and selection colors
   come from tokens instead of local literals.
3. **Text remains selectable.** Use real text and DOM structure for labels and data;
   reserve canvas for charts.
4. **Large content degrades gracefully.** Truncation, lazy mounting, virtualization, and
   background indexing must remain visible to the user.
5. **Light and dark themes share semantics.** Theme overrides may change contrast and
   lightness, not the meaning of a token.

## Token Layers

`static/styles.css` defines tokens in layers:

- base surfaces, text, borders, links, and shadows;
- semantic status colors;
- file-type foreground, background, and border triplets;
- aggregate-distribution category, track, and neutral-tail colors;
- chart colors and annotation states;
- component dimensions, radii, typography, and motion.

Components consume semantic tokens.
They should not copy OKLCH, HSL, or hexadecimal values from another component.
When a new concept needs a color, add a token with a semantic name and define its
dark-theme override alongside it.

New and deliberately adjusted color families use OKLCH because its lightness and chroma
steps are more perceptually uniform than HSL steps.
Stable HSL families may migrate when their palette is deliberately adjusted; syntax-only
mass conversion adds review risk without improving the interface.

Plugin styles may consume host tokens.
A plugin-specific visual language belongs in the plugin stylesheet, including any new
domain tokens, rather than in core `styles.css`.

## File Age

File age is one shared primitive across navigation rows, file headers, recent-filter
menus, Live badges, and plugin-rendered age labels.
Each state owns two parallel OKLCH tokens in `static/styles.css`:

- `--file-age-<state>` is an accessible text foreground
- `--file-age-fill-<state>` is a translucent surface or area fill

Live is an activity state, not an elapsed-age bucket.
It uses a warm salmon family that remains distinct from the deeper destructive red and
from success green.
The six elapsed-age buckets retain the existing thresholds: under one
minute, under one hour, under one day, under one week, under one month, and older.
They move from gold through yellow-green while chroma and prominence fall monotonically
toward a warm neutral.

Text color is the sole age hue signal; dates and Live labels never gain a dot, swatch,
or adjacent color cue.
Light-theme yellow text uses contrast-safe gold and ochre values on white and tinted
surfaces. The three recent elapsed tiers descend in lightness and maintain a perceptible
OKLCH step between neighbors, so under-one-minute, under-one-hour, and under-one-day
files do not collapse into one muted color.
The `.age-live` and `.age-*` classes select tokens only, so new consumers reuse the
primitive rather than reconstructing colors.

Adjust this family only at its token definitions, preserve the semantic ordering in both
themes, and run `tests/test_file_age_palette.py` to verify OKLCH structure, gamut, and
contrast across the surfaces where ages appear.

## Typography

The shell uses a compact UI face for chrome, a monospaced face for rendered content, and
KPress typography for rendered Markdown.

### Faces: Chrome Is Sans, Content Is Mono

The dividing line is what the text *is*, not how technical it looks.

Chrome — everything the application itself says — uses `--font-sans`. That includes file
paths, and it includes the parent path and every ancestor segment: a path is navigation,
not code, so it reads in the same face as the navigation row it points at.
Key names, shortcut hints, labels, metadata, chips, tooltips, counts, and status text
are chrome too.

Monospace is for the user’s own content, where column alignment carries meaning:
highlighted source, code blocks, Markdown inline code, and raw log payloads.
Numeric alignment on its own does not justify monospace — byte counts, durations, and
timestamps stay sans and use `--tabular-numerals`.

The authoritative rule, the current list of deliberate exceptions, and the reasoning for
each live in the `── Typography roles ──` block of `static/styles.css`, next to the
tokens they govern. `tests/test_chrome_typography.py` enforces that list across the host
and plugin stylesheets, so a new monospace use site fails the build until it is
classified.

### Keyboard Keys

Every keyboard key rendered anywhere in the app uses the `.kbd` component: always all
caps, bold, with one thin border.
Never hand-set a key’s type or border at a use site, and never write a key as plain text
inside a sentence.

Write the key in its natural case in markup — the caps treatment is presentational, so
the accessible name stays what the markup says.
For a sequence, emit one `.kbd` per key so each keeps its own border.

The component, its tokens, and its markup contract are documented in the
`── Keyboard keys ──` blocks of `static/styles.css`.

### Type Scale

Every font size in the app comes from the type-scale tokens defined in
`static/styles.css` (see the `── Type scale ──` block in `:root`). Never inline a
font-size literal at a use site.

Chrome (interface) sizes:

- `--body-font-size` (14px): primary chrome text — body default, inputs, empty states,
  stat values.
- `--nav-font-size` (13px): dense navigation rows and path breadcrumbs — tree items,
  header path, file-header path.
- `--ui-small-font-size` (12px): secondary chrome — metadata, chips, tooltips, notes,
  filters, summaries.
- `--label-font-size` (= ui-small): small-caps section labels — tabs, panel and table
  headers, stat labels.
  Labels differ by caps treatment, not by another size.
- `--mono-block-font-size` (= ui-small): monospaced blocks in chrome contexts — source
  views, logs, raw JSON.
- `--micro-font-size` (10px): deliberately minimized marks — the brand line.

Document (rendered prose) sizes are a single token:

- `--document-body-font-size` (15px): prose, one size step above the 14px app body.

Everything else inside a rendered document — secondary text, table cells, captions,
footnotes, and code at every tier — belongs to KPress’s ramp, which it derives from this
one value through `--kpress-host-font-size-base` on `:root`. Chrome-context monospace is
a separate concern and uses `--mono-block-font-size`.

Do not add a host token that restates a ratio KPress already owns.
KPress ships *graded families* — secondary text at `small`/`smaller`/`tiny` and code at
`mono`/`mono-small`/`mono-tiny` — and steps each by context, because the smaller tiers
land where the surrounding text is already reduced.
A host token collapses the whole family onto one size, and the failures are not subtle:
a flat 0.9× mono token once rendered inline code in a table at 13.5px inside a 12.75px
cell, larger than the prose around it, while a flat 0.85× secondary token shrank table
text to 12.75px against 15px prose — well under the 14.25px KPress intends.

The bridge keeps one size override, and only because it is a real design difference: the
CONTENTS label uses `--label-font-size` so it matches app labels.
When adding a size, extend the ramp and its documentation; do not create a one-off.

### KPress Base-Size Boundary

The app pins all sizes in px and deliberately does not scale with the browser’s
default-font-size preference.
Standalone KPress documents preserve browser-preference scaling through a `1rem` base,
but its embedded type system consumes the host’s px value through
`--kpress-host-font-size-base`. Within a container-query band, every rendered font size
and bullet offset derives from KPress’s internal base variable, so changing the browser
root size cannot distort the embedded document’s type ratios.
The host hook lives on `:root` so body-portaled KPress overlays inherit the same scale,
and KPress can still re-root its internal base to the print size on paper.
KPress deliberately keeps layout lengths and container-query thresholds root-relative; a
root-size change near a responsive breakpoint can select a different heading tier.
Verify the type boundary at a pane width that stays in the same band and confirm
computed sizes are identical at two browser root sizes.

### Embedded Document Themes

Metabrowser owns one theme input for the embedded document:
`data-kpress-resolved-theme="light|dark"` on the root.
KPress fragments carry no theme or palette attributes, so one cached render works in
both modes and a toggle never has to chase rendered elements.
The default fragment manifest omits KPress’s standalone theme resolver; the host loads
the entry points the manifest declares without maintaining a second exclusion list.
KPress’s symmetric theme selectors keep its palette and `color-scheme` aligned, while
the bridge maps the public `--kpress-doc-*` color tokens on both the fragment and
body-portaled tooltips to Metabrowser’s semantic surface, text, border, muted, and link
tokens.

### Embedded Document Navigation

Metabrowser requests KPress’s normalized TOC collapse depth `1`, which keeps the
top-level section spine visible and lets scroll-follow open the active deeper branch.
At KPress’s wide document band, the docked TOC is a borderless rail with a hidden but
scrollable scrollbar.
The narrow overlay drawer keeps its border and visible scrollbar so it remains distinct
from the document it covers.

Keep these roles distinct:

- labels and metadata use normal weight and muted text;
- filenames are the identity of a row and carry bold weight at full contrast, while the
  parent path beside them is context and stays regular weight and muted;
- byte counts, durations, timestamps, and numeric table columns use tabular numerals;
- code uses monospaced text without forcing prose into a code style, and paths stay in
  the sans navigation face.

Do not shrink essential text to fit.
Prefer truncation with an accessible full-value tooltip or allow a panel to scroll.

## Control Families

Every button belongs to one role-specific primitive:

| Role | Primitive |
| --- | --- |
| Labelled action | `.btn` |
| Icon-only action | `.icon-btn` |
| Filter value or filter menu | `.chip` and its variants |
| Menu row or segmented menu choice | `.menu-item` or `.menu-seg` |
| Tab | `.tab-btn` |
| Collapsible section title | `.section-disclosure-trigger` |

These primitives share the type scale, radii, semantic colors, focus treatment, and
motion tokens, while their shapes communicate different interaction roles.
A use-site class may add positioning, visibility, or domain state, but it must carry the
primitive class in the markup and must not recreate the primitive’s border, fill,
typography, or focus rules.
Every non-submit button declares `type="button"`, and every icon-only button has an
accessible action name.

### Navigation Tree Folders

A folder row is one activation target, including its chevron, name, and metadata.
Activating it selects the folder, opens its default **Overview** view, and toggles its
immediate children. Activating an already open folder collapses its children without
clearing the folder selection or replacing Overview.

The chevron is a state indicator within that target, not a second action with separate
navigation semantics.
Its direction and the child container’s visibility derive from the same expanded state
so they cannot drift.
Shift-activation applies the same open or close direction recursively, while still
selecting the folder and opening Overview.

### Section Disclosure Headers

Use the section-disclosure primitive when a labelled section may hide its body without
changing the selected file, folder, or top-level view.
Folder Overview panels use a button inside their visible `h2`; rendered-document
metadata keeps native `details` and `summary` semantics.
Both forms place the same gray Lucide chevron immediately after the title with
`--section-disclosure-chevron-gap`. The mark uses `--section-disclosure-chevron-size` in
`em`, so it remains proportional to the unchanged local heading typography at every type
tier. It points right when collapsed and rotates down when expanded.

The title and chevron form one focusable target.
A button trigger declares `type="button"`, `aria-expanded`, and `aria-controls`; its
section uses `aria-labelledby` to preserve the visible heading as the accessible name.
Collapsing an already mounted section hides its body without remounting or disposing its
renderer. Overview panels start expanded on each mount.
Markdown Frontmatter and Diagnostics disclosures start collapsed through the absence of
the native `open` attribute.
These defaults are not saved as user preferences.

Section headings use `--section-heading-divider-gap` between their content and the
divider. Components consume the token instead of choosing local bottom padding, so the
divider remains equally close to headings with and without disclosure controls.

This pattern does not replace the navigation-tree disclosure.
The tree keeps its leading chevron because that mark communicates hierarchy and shares
one activation target with folder navigation.

## Icons and Icon Buttons

Icons come from one Lucide-derived set in `static/icons.js`, rendered as inline SVG that
inherits `currentColor`. An icon never carries its own color.

### One Glyph Size

Every icon in the chrome is drawn at `--icon-glyph`, whether it is a button, a file-type
mark on a tree or palette row, or a menu row’s leading mark.
Never inline a pixel size at a use site.
Where an icon reserves a column in a row of text, the alignment box around it is 16px —
one step wider than the glyph, so the mark sits optically centered.

Files and exact file extensions use the `.file-identity-icon` alignment-box primitive.
Resolve its host-owned SVG and subtype class with `window.metabrowser.fileTypeIcon()`;
do not copy the filename matcher, SVG, or `ft-*` mapping into a component.
The navigation tree, plugin views, and aggregate rows therefore change together when a
file type is added.

There is one deliberate exception, `.menu-seg svg` in the segmented theme and font
choosers, where the glyph *is* the segment’s label rather than a mark beside text and so
carries the weight of a word.
It is documented at the rule.

### Every Icon-Only Control Is the Same Control

An icon-only button is one primitive, `.icon-btn`, documented in the
`── Icon buttons ──` block of `static/styles.css`. It pairs `--icon-glyph` with
`--icon-btn-size` for the hit target, so the settings gear, the print action, and the
copy buttons are interchangeable wherever they appear.

At rest an icon button is a bare muted glyph with no border and no fill.
It raises a hover surface and a hairline border only while hovered, focused, or holding
a menu open; hover, keyboard focus, and “my menu is open” are one visual state.

Do not give an icon button a resting border or background.
A permanent box around one icon makes it read as a heavier, more primary control than
the unboxed icon beside it, and two icons of equal standing stop looking like the same
kind of thing. The hover surface is what signals “this is clickable” — a static frame
adds weight without adding information.

The one sanctioned resting surface is `.icon-btn-overlay`, for a button that floats
above content: a bare glyph over source text is unreadable, so it needs an opaque plate.

### Parent Navigation Is a Bordered Button

Moving to an enclosing folder is a labelled navigation action, even when a compact
header has room for only its arrow.
Both forms combine `.btn` with `.parent-nav-btn`, use the shared `.parent-nav-arrow`,
and keep a visible resting boundary.
The labelled form includes the destination folder; the icon-only form retains the same
arrow size and button height with its destination in the accessible label and tooltip.

Do not represent parent navigation as a bare `.icon-btn`. Icon actions such as Print
operate on the current view and remain unboxed at rest; parent navigation changes the
current location and uses the stronger bordered-button vocabulary.

### Reveal on Hover Keeps Keyboard Reach

Buttons that appear only when their row or container is hovered use `.icon-btn-reveal`,
which fades opacity and drops `pointer-events` rather than setting `visibility: hidden`.
A hidden button leaves the tab order, so the control becomes mouse-only.
Every reveal trigger restores `pointer-events` along with the opacity, and keyboard
focus is itself a reveal trigger.

## Filter Controls

Every filter in the app is built from one chip family, documented in the
`── Filter controls ──` block of `static/styles.css` and rendered by
`static/filter_controls.js`. A surface that needs a filter reaches for these rather than
inventing a pill of its own; four near-identical pills is what this family replaced.

Core and plugin views use the same renderer and interaction code.
Plugins reach it through `window.metabrowser.filterControls`; they may use a plugin
stylesheet to position the resulting control, but selected-state styling remains in the
host chip primitive.
Do not handwrite chip markup or add kind-specific selected colors.
If the shared renderer cannot express a filter, extend it and its behavior tests.

`.chip` is the atom.
`.chip-group[data-layout="joined"]` joins a short, single-row set into one bordered pill
with hairline dividers.
`.chip-group[data-layout="wrap"]` lays out a longer set as independently bordered pills
with consistent gaps, so the set can wrap without drawing one frame around several rows.
`.chip-toggle` is a standalone boolean.
`.chip-menu` is a chip that opens a dropdown, single- or multi-select.
`.chip-badge` carries a count, and `.chip-clear` is the quiet reset.

A `.chip-menu` composes the existing floating `.menu` surface rather than introducing a
second menu look — the app had a single-choice `.menu` and a native `.menu-select`, and
neither can pick several things.
Its trigger summarises the selection the way a select does (`Any age`, `Past week`,
`.md +2`) so the closed control still answers “what is filtered?”. Dismissal follows the
same rule as every other floating menu: Escape or outside interaction.
The trigger uses the shared Lucide disclosure chevron at the standard chrome glyph size,
rotated downward; do not substitute a text caret or shrink it to fit the label.

A dropdown declares its kind the same way a group does, and for the same reason: `one`
gives `role="menuitemradio"` rows and closes on pick; `many` gives `menuitemcheckbox`
rows and stays open, because picking several is the point of it.
Only one dropdown is open at a time.
The list always leads with an any-row naming the dimension’s default (`Any type`), so
clearing one dimension is a pick rather than a separate control — and the option list
must not repeat that value under another name.

### Groups Or Dropdowns

Both exist because they fail differently as the value list grows.
A `.chip-group` shows every option at once, which is the right trade for a bounded set
on a surface where scanning all values matters.
Short sets use the joined layout.
Sets that can exceed one line, such as agent-log event types, use the wrapping
chip-cluster layout; segmented controls never wrap.
A `.chip-menu` costs a click to see the options but stays one trigger wide however many
there are, so use it when the set is unbounded or the pane cannot afford the full group.

The nav filter bar uses dropdowns throughout: six age windows and six size steps as
segmented ramps left no room for anything else in a 300px pane.
The groups stay part of the family for surfaces with fewer, shorter values.

Age and file-type rows carry right-aligned file tallies in tabular numerals.
Fixed age windows remain in chronological order and show cumulative counts.
Open-ended type values are ranked by frequency and capped, so the menu cuts the long
tail rather than an arbitrary alphabetical slice.

A dropdown may lead with ordered named **preset sections** — shorthands standing for the
full set of values beneath them.
Each nonempty section has a visible small-caps label, an ARIA-labelled group, and a
separator between semantic tiers and before the raw list.
The navigation type chooser uses broad group presets first, families grouped under the
recommended file-type definitions’ group labels second, and canonical/raw extension rows
last. Empty groups and empty presets are omitted; an empty preset must never alias the
Any state. A preset is checked only when every value it names is selected, so a
half-covered group never claims to be on, and a selection that is exactly one preset
shows by its name rather than as `.md +21`.

Selecting a semantic family adds all declared canonical suffixes; selecting a broad
category adds its category-only filenames and all family members.
Removing a child clears its parent’s checked state.
A known canonical suffix matches declared compound tails, while an unknown raw extension
remains exact.

Where a row stands for an exact extension, it carries that type’s icon and leaves the
label plain. Aggregate category and family rows are text-only.
The icon is what identifies a type everywhere else in the app, and tinting a whole
column of labels makes the hues compete with the selected-state mark instead of helping
anyone scan the list.

### Selection Kind Is Visible Before the Click

A group declares its kind in `data-select`, and the two kinds look different:

| Kind | ARIA | Selected fill |
| --- | --- | --- |
| `data-select="one"` — exclusive | `role="radiogroup"`, `aria-checked` | `--highlight-bg` / `--link` |
| `data-select="many"` — additive | `role="group"`, `aria-pressed` | `--hover-bg` / `--text` |

The accent fill for exclusive choices is the same treatment `.menu-seg[aria-checked]`
uses for the theme and font pickers, so “accent means one of these” already means that
elsewhere in the app.
A user should never have to click a group to learn whether picking a second value
replaces the first or adds to it.

Because the stylesheet keys off those ARIA attributes, correct ARIA and correct
appearance are the same thing here: a group with the wrong role renders wrong, not just
inaccessibly.

### One State Mechanism, With One Exception

Anything carrying a filter *value* is a `<button>` with `aria-pressed` or
`aria-checked`. No hidden checkbox inputs behind pill styling, and no reading state two
different ways depending on which control you picked.

The exception is a boolean whose *polarity* has to be legible, which takes a real
labelled checkbox (`.filter-check`). A pressed pill reading “Gitignored” does not say
whether pressed means those rows are shown or filtered away — the user has to click it
to find out. “Show ignored” with a tick states its own direction, uses the control
everyone already knows for that, and is visibly lighter than a pill sitting beside one.
Reach for it when the label has to name the *on* state; reach for a chip when the label
names a value.

Keyboard behavior follows the kind: an exclusive group is one tab stop with arrow-key
traversal and roving `tabindex`, while each chip in an additive group is its own tab
stop, because each is an independent control.

### Filters Say What They Do Not Know

A filter that prunes rows must not imply the result is complete when it is not.
Where a surface can only judge what it has loaded, it renders a `.filter-note` saying
so. Missing data is never treated as a non-match: a pending size, an absent mtime, or an
unclassified path leaves a row in place rather than making it flicker as filtered.

## File Types

File-type classes map each subtype to three custom properties:

```css
.ft-example {
  --ft-color: var(--ft-example);
  --ft-bg: var(--ft-example-bg);
  --ft-border: var(--ft-example-border);
}
```

The icon communicates the broad type; the hue communicates the subtype.
Reuse the same class in the tree, recent-file rows, and any plugin view that references
a file.

Add new file types through the declarative matcher and token triplet.
Do not add filename-specific CSS selectors.

### Aggregate Distributions

The shipped
[Folder Overview plan](project/specs/done/plan-2026-08-12-directory-file-type-summary.md)
defines the first instance of this component contract.
An aggregate distribution relates exact categories through one selected metric column in
a semantic table. The metric cell presents an absolute value, a track normalized to that
metric’s population total, and a percentage.
A nearby exclusive control switches the entire table atomically between Files and Bytes;
it never leaves parallel metric columns competing with that control.
This keeps large category sets vertically scannable and lets the selected measure use
the available width.
It is distinct from the broad `ft-*` identity system: several exact extensions may
intentionally share one file icon, while semantic families such as JavaScript and YAML
need stable distribution identities of their own.

The component uses a bounded light/dark categorical palette, a neutral **Other** token,
a track token, and a named track-height token.
Consumers select palette classes; they do not copy color literals or set theme colors
inline. Inline percentage widths are allowed because they encode data rather than theme.

The token family is `--mb-distribution-category-1` through
`--mb-distribution-category-12`, plus `--mb-distribution-other`,
`--mb-distribution-track`, `--mb-distribution-track-height`, and
`--mb-distribution-segment-gap`. The segment-gap token remains available to consumers
that place categorical segments beside one another.
Shared `.mb-distribution-slot-*` and `.mb-distribution-other` utility classes map those
tokens to a component color variable.
Core owns these tokens and utilities; the folder plugin owns File types and Treemap
layout selectors.

When a selected metric changes, the table keeps the same category set and color map.
The active measure controls values, percentage widths, emphasis classes, and row order
as one update. Categories keep their assigned slot for the mounted folder even when live
updates change rank, and Other stays last and neutral.
A related visualization, such as the extension-colored Treemap for that folder, reuses
the same mounted mapping when both views exist.

The semantic table is the visual summary and the source of exact values.
Every row names its category and reports absolute values and percentages; the colored
fills need no separate circle or legend.
Fills do not become tab stops or add duplicate tooltips and are hidden from the
accessibility tree. Labels never rely on color or place text on a category fill.

File types uses non-subtotaling row groups in the server registry’s order: Code,
Documentation, Data, Logs, Archives, Media, and Other.
Empty groups are omitted.
Membership comes from the same recommended File Rollup Format type definitions used by
rollups, navigation filters, and Treemap colors; surfaces never maintain local extension
lists. Known canonical suffixes roll up into readable family parents such as
**JavaScript**, **TypeScript**, **CSS**, **YAML**, **Log files**, **Archives**, and
**Images**. Compound extensions inherit the longest declared suffix: `.min.js`
contributes to JavaScript’s `.js` child without rewriting the file’s exact logical
extension. Indexed logical extensions contain at most two suffix components, so source
maps remain useful `.js.map` or `.ts.map` rows without fragmenting the table into
filename-specific `.umd.min.js.map` and `.d.ts.map` variants.

Family parents are aggregate identities, so they are text-only.
Every nonempty family places the shared gray trailing chevron after its label, starts
collapsed, and reveals its indented extension rows without changing denominators or
colors. A singleton such as Rust therefore still expands to `.rs`, preserving one
consistent interaction and leaving room for future exact-extension filtering.
Canonical children retain exact extension icons and share their parent’s `family:<id>`
palette key. Unknown and deliberately ambiguous extensions remain raw rows; they are not
assigned a confident name merely to shorten the table.
**No extension** and **Other types** are disclosable special parents under Other.
No extension reveals exact basenames; Other types reveals raw logical extensions.
Each serialized fallback list is independently capped at 20 and adds a neutral
**Others** row whose file and byte metrics exactly conserve children omitted by the
producer. Presentation applies a second, consistent bound to every direct child list:
show the first 10 rows and add one neutral **N more** aggregate row.
Activating that row reveals its exact children in place.
The same grammar applies recursively to family, special-parent, and fallback lists,
including lists with only 11 entries.
Expansion does not refetch or change denominators, and remains stable across live
updates while its row still exists.
A group heading is shown only when it has rows and carries no subtotal.
Type labels use the bold design-system weight as the row’s scan anchor.
Each raw or disclosed canonical extension row leads with the shared file-identity icon
resolved from a synthetic filename, and each basename child resolves from the basename,
so both match navigation without weakening the text label.
Special parents and Others stay iconless because they describe aggregates rather than
exact files or extensions.
An unknown exact extension such as `.bin` uses the generic blank-page identity.
Family parents, Files, and Ignored are likewise iconless.
Every exact Files value uses the shared `.count` and `.count-large` convention, and
every exact byte value uses `.size` and `.size-large`. The stronger weight therefore
appears at the same count and byte thresholds as the navigation panel, including on
Files and Ignored; a row role never forces a different numeric weight.

Rows within each subsection sort by the active Bytes or Files measure, descending.
The other measure is the deterministic secondary key and the stable row identity is the
final tie-breaker. Group order remains registry-defined.
Changing the metric therefore reveals the relevant skew without making equal rows jump
unpredictably.

The **Files** section begins expanded.
It contains the shared Files / Bytes control and a fixed two-row totals table using the
neutral distribution color.
**Files** comes first and reports the unignored population immediately from the
inventory snapshot. **Ignored** follows with the excluded population.
These are disjoint rows whose counts and byte sizes each sum to the complete selected
directory. Their percentages use that complete population as the shared denominator, so
each metric also sums to 100% when its denominator is nonzero.
Both rows switch to the selected metric and are always present, including when ignored
files are hidden from the type population, so scope is explicit without a separate
notice. When the complete population has files but zero bytes, both byte rows remain
`0 B`, `0%`, and unfilled rather than implying a share of an empty byte population.

The **File Breakdown** section follows Files and begins collapsed.
It contains the full type distribution and starts with the same labelled `.filter-check`
**Show ignored** checkbox used by navigation.
Show ignored begins checked when there is no saved preference and changes only the
breakdown population; it never changes or hides the explicit Files and Ignored totals.
File Breakdown does not render another metric chooser.
Both sections observe the same state object, so the Files / Bytes choice in Files
atomically updates the totals and the complete breakdown, including while the breakdown
is collapsed.

Visual Type and metric column labels are unnecessary when every metric cell keeps the
same value-track-percentage grammar.
The semantic table retains screen-reader-only headers and updates the selected metric
header between Files and Bytes, so assistive technology receives the relationships that
sighted users get from alignment.

Zero totals do not produce a colored fill, division artifact, or header-only table.
If one metric is zero while another is not, the zero metric uses the neutral track and
the populated metric remains meaningful.
If the whole population is empty, the parent surface renders its explicit empty state
instead of the distribution body.

### Folder Treemap

Treemap is the hierarchy complement to File types, not a second composition summary.
It always lays out the bounded directory tree as folders and files; it does not offer a
Folders/Types grouping choice.
File types already answers which extensions make up the population, while Treemap
answers where space or file count sits and keeps folder and file cells navigable.

The Files context above the map mounts the same reusable folder-rollup controls used by
Overview. The metric control appears before Files and Ignored; the scope control appears
after them:

- A joined, exclusive **Files / Bytes** group chooses the cell-area metric and starts on
  Files when there is no saved preference.
- A labelled **Show ignored** checkbox chooses scope and starts checked.
  Checked includes gitignored cells and dims them; unchecked removes them and switches
  folder, remainder, and status values to the rollup’s unignored totals.

Both views observe one state object and preference key, so changing either control in
Overview or Treemap updates the other surface without a second interpretation of scope
or metric. The metric switches both totals rows and the map.
Show ignored changes map membership but leaves the explicit Files and Ignored rows
intact.

There is no separate color selector.
Every file maps its exact extension through the taxonomy’s distribution key, every
folder maps its dominant extension through the same helper, and remainder cells use the
neutral Other slot. The File types panel and Treemap acquire the same per-folder palette
session, so a semantic family keeps the same color across both views.
Modification age remains available in the tooltip; it does not compete with file type as
a second cell-color vocabulary.
Treemap derives a theme-aware surface wash and stronger border from that shared base
color so labels retain contrast; the Overview’s data bars keep the full-strength swatch.
Hover brightens the composed cell, including its type-derived surface and border, so
their contrast and hue relationship remain intact.
There is no separate label hover surface.
It never changes stacking or display: nested folder containers and their descendant
rectangles are flattened siblings, so raising a container would cover its children.

The complete visible rectangle of every folder or file is its pointer target, including
the uncovered header, gutter, and background of a nested folder.
When rectangles are nested, the deepest rectangle under the pointer wins; an inert
remainder cell does not fall through to its parent.
The nested parent remains an ARIA group and its label remains the keyboard control, so
full-cell pointer handling never creates an invalid button containing descendant
buttons.

Cell typography grows continuously with usable rectangle geometry.
The scale combines the short side with the square root of area, which lets a genuinely
large box grow while preventing a long, thin sliver from claiming display type.
Folder/file labels stay between 11px and 24px; value labels stay between 10px and 18px.
Geometry-derived inline custom properties are allowed here because they encode layout
data, just as inline bar widths encode percentages; theme colors still come only from
tokens and shared utility classes.

Large nested folders place their formatted aggregate value in the reserved header row.
Non-nested cells place the value below the name when both lines fit.
File leaves keep their formatted byte size in either area mode because “1 file” adds no
information; aggregate folders and remainder cells report the selected metric.
Values use the shared byte and file-count formatters.
A label or value that cannot fit is omitted rather than shrunk below its lower bound or
allowed to overlap child cells.
Visible folder labels end in `/`, while file labels carry the same file-identity icon as
the navigation tree.
The slash is a visual kind cue and is not added to the folder’s accessible name or path.
The accessible name preserves the cell name, kind, and visible value; the tooltip
retains the complete name, counts, bytes, and modification time.

Treemap navigation preserves the user’s spatial context.
Activating a folder cell opens that folder with Treemap selected, and Backspace opens
the parent with Treemap selected.
Every non-root Treemap also places a compact labelled action immediately above the map.
Its up arrow and enclosing folder name make the zoom-out target explicit, and activation
opens that parent with Treemap still selected.
The top-level target is shown as `/`; the control is omitted at the served root because
there is no enclosing folder within the browsing scope.
Activating a file cell opens the file’s ordinary default view.
This uses the public navigation preference rather than simulating a tab click; an
unavailable preferred view falls back to the destination’s declared default.

## Panels and Tabs

The preview pane has one scroll owner.
Views should not introduce nested full-height scroll containers unless the content
itself requires independent horizontal or virtual scrolling.

### Folder Views Are Tabs

The Folder Overview applies these rules to every served directory.
A tab changes the primary way the selected item is inspected.
For folders, **Overview** is the default tab and **Treemap** is a peer visualization.
A future **Files** listing also belongs at this level because it replaces the primary
working surface; it is not an Overview panel.

Tab renderers receive a dedicated container and own its contents.
Default views mount immediately; hidden views mount on first activation.
A loading state should preserve the tab’s dimensions and communicate whether the work is
local parsing or an HTTP request.

### Folder Overview Is a Panel Stack

Overview is one vertically ordered composition surface, not a fixed page template.
Its panel registry lets a capability contribute a region without knowing which other
regions are installed:

- **Files** is the required totals panel for every folder and starts expanded.
- **File Breakdown** is the required detailed type-distribution panel and starts
  collapsed.
- **README** is a content panel only when a direct-child README exists.
- License and other future panels use the same contribution contract and appear only
  when applicable.

The Overview composer owns panel order, measure, gaps, responsive stacking, loading,
failure isolation, and disposal.
Panels own only their data and internal rendering.
They must not query sibling DOM, reserve ad hoc margins for another panel, or create a
second preview scroll owner.
Named placement bands establish broad order; stable panel IDs break ties, so
asynchronous resolution and plugin load timing never rearrange the page.

Every contribution is a labelled semantic section.
The composer renders the label as a visible, document-aligned section heading above the
panel body. These headings use the tab bar’s uppercase, bold, tracked sans-serif grammar
at the body-text size, followed by a neutral separator.
Collapsible headings contain the shared section-disclosure trigger, with its gray
trailing chevron and unchanged heading typography.
Files and README start expanded; File Breakdown starts collapsed.
All three collapse in place without disposing their mounted contents.
Files uses the stable internal panel ID `folder.file-totals`, and File Breakdown retains
`folder.file-types`. The Files panel owns the only Overview metric chooser; shared state
applies that choice to File Breakdown and Treemap.

Panel bodies use one of two presentations:

- A **surface panel** receives a flat host-rendered body and chrome typography.
  Files and File Breakdown use this presentation without surrounding cards.
- A **document panel** supplies its normal rendered-document surface.
  README therefore looks exactly like an ordinarily rendered Markdown file, including
  its metadata, diagnostics, TOC, breakpoints, and print behavior.
  Overview adds the shared section heading but does not override the document card.
  The card keeps its standard border and shadow at regular and wide document bands, then
  becomes borderless through KPress’s own narrow breakpoint.

“Panel” describes composition and lifecycle, not a requirement to draw the same box
around unlike content.
Surface content, section headings, and document content use one responsive alignment
contract and shared stack gap.
At regular and wide Markdown breakpoints, flat surface panels and section headings align
to the README card’s outer edges; the TOC keeps its own rail in the wide band.
Below the card breakpoint, KPress removes the card boundary and the alignment follows
the README prose edge.
The Overview composer mirrors those pinned KPress breakpoints so the rule remains exact
rather than approximating the document geometry.

Panel availability is independent.
A missing README removes only that region, and one failed optional panel gets a local
error without replacing Overview or its siblings.
Transient failures offer Retry; invalid or permanent failures provide the applicable
corrective action instead of a control that cannot help.
Printing includes only contributions that declare themselves printable; host summaries
and empty-state chrome stay off paper.

### Folder Rollup Loading

Directory totals and detailed rollups have separate readiness contracts.
The totals rows at the start of Files render from the inventory snapshot attached to the
selected folder and subscribe to the public directory-totals store for later revisions.
Navigation must never replace a known total with a fabricated zero or a loading
placeholder.

The Files type breakdown and Treemap publish only terminal rollup generations.
While a scan is pending, they keep their geometry stable and render the same
low-contrast pulsing block used by the navigation tally.
Provisional rows or rectangles are never painted and then reshuffled.
The motion is delayed briefly, respects reduced-motion preferences, and is replaced
atomically when the complete, truncated, or failed generation arrives.

Treemap repeats the fixed **Files** context immediately above the map.
It does not make that context collapsible and does not duplicate totals or scan state in
a footer sentence. The print action is absent when no mounted contribution is printable.

An empty folder is still a completed Overview.
Files remains visible with the message **No files to summarize.** It renders no empty
bars, percentages, table, standalone tally, or synthetic “No README” document panel.
Loading, partial, empty, and failed states must remain visually and semantically
distinct.

Floating menus and tooltips use the shared surface, border, radius, and shadow tokens.
They must remain within the viewport and close on Escape or outside interaction.

## Structured Data and Tables

Use structured rows rather than syntax-colored walls of punctuation when the user is
inspecting object relationships.
Keys, scalar values, array counts, and expansion controls each have consistent roles.

Tables should:

- align numeric columns to the right;
- keep headers visible where practical;
- use restrained row striping and hover states;
- preserve copyable text;
- wrap or scroll long paths without widening the entire page;
- expose an explicit empty state instead of rendering a blank panel.

## Source and Syntax Colors

Metabrowser owns the complete Highlight.js semantic palette in `static/styles.css`.
Highlight.js supplies token classes but no theme stylesheet, so light and dark colors
cannot diverge through stylesheet timing or selector specificity.
Every syntax foreground must meet WCAG AA contrast against the app and code surfaces in
both themes.

## Charts

Chart specifications use CSS-variable sentinels for color.
`static/charts.js` resolves those variables before passing concrete colors to Chart.js,
because canvas cannot resolve CSS custom properties itself.
When the resolved theme changes, active charts rebuild from their unmodified token
specs; SDK-created charts re-resolve token-bearing data and options in place.

Charts must include text labels and usable summaries.
Color alone cannot distinguish series, thresholds, or success and failure.
Destroy SDK-created Chart.js instances when their view is disposed so their theme
subscription is also released.

## Motion

Motion communicates a state transition: tree insertion, removal, refresh, loading, or
layout change. Keep durations short and use the shared motion tokens.
Avoid looping animation except for active progress indicators.

Respect `prefers-reduced-motion`. Content and status must remain understandable when
transitions are disabled.

Transient loading chrome has a 30ms quiet period through the shared
`.mb-delayed-loading` utility.
The placeholder reserves its final layout immediately but stays invisible long enough
for synchronous work and fast local requests to replace it before paint.
Apply this utility to view- and panel-level loading placeholders; do not add independent
timers at each renderer.

The shell separately retains the previous preview during a fast file-envelope request.
Ready content always wins immediately: do not add a minimum spinner duration, crossfade,
or transition that delays usable content merely to complete an animation.

### Progress Spinners Stay Neutral

Loading and progress spinners use the shared neutral-gray track and accent tokens.
They must not borrow link, status, file-type, or chart colors because a spinner conveys
activity, not meaning.
Prefer the shared spinner classes; custom sizes must still use the shared spinner tokens
and keyframe.

## Text Selection

Text selection is content behavior.
Informational text—including errors, logs, file contents, status explanations, and
labels—must remain selectable for search and debugging.
Disable selection only on controls whose primary behavior is clicking, dragging,
toggling, or navigation.
Never put `user-select: none` on a container whose descendants include content.
Do not set `user-select: none` on a broad container because its children are mostly
interactive.

## Interface Copy

Product chrome includes navigation, controls, dialogs, tooltips, status regions, empty
states, errors, and plugin-owned controls around file content.
Its text is part of the component contract and receives the same review as behavior,
layout, typography, and color.

### One Role Per Element

Adjacent text elements must not repeat the same information.

| Element | Purpose | Avoid |
| --- | --- | --- |
| Label | Identify a control, field, or region | Instructions and status |
| Placeholder | Show the input’s accepted content or format | Essential labels and repeated instructions |
| Hint | Explain a non-obvious interaction or shortcut | Restating the label or visible action |
| Status | Report scope, progress, outcome, or recovery | Repeating the placeholder or control label |
| Empty state | Explain what is absent and whether the state is final | Blank panels and false finality during loading |
| Error | State what failed and, when useful, the next action | Stack traces, implementation terms, and generic failure text |
| Tooltip | Add supplementary context | Information available nowhere else |

If removing a sentence loses no information because an adjacent label, control, or
visual state already communicates it, remove the sentence.

### State Language

Use a consistent progression:

- Idle text reports scope or availability.
- Active work uses a progressive verb and a Unicode ellipsis, such as “Searching 283
  files…”
- Completion reports a result, count, or explicit empty state.
- A recoverable failure says what could not be completed and gives one relevant next
  step.

Do not announce success when the resulting state is already obvious.
Do not use a print-specific, plugin-specific, or implementation-specific explanation for
an effect that applies to the whole view.

### Style

- Use sentence case and the terms already used by the surrounding interface.
- Prefer one short sentence.
  Add a second only for recovery or material incomplete state.
- Remove filler such as “currently,” “simply,” “just,” and “successfully.”
  Use “only” when it changes the meaning.
- Use exact counts and cutoffs when known.
  Format counts for the user’s locale and use the correct singular or plural form.
- Control labels and placeholders have no terminal punctuation.
  Status, empty, and error sentences use terminal punctuation; active progress ends in
  an ellipsis.
- Describe user-visible effects, not payloads, providers, caches, exceptions, or other
  implementation details.

### Accessibility

Visible labels remain the source of accessible names; a placeholder is not a label.
A live-region message must make sense when announced without nearby visual context and
must not repeat an instruction the user has already heard.
Delay transient progress text when work normally completes before it can be read.
Essential guidance remains persistent and does not exist only in a tooltip, color, or
animation.

### Chrome Copy Review

Every change to product chrome includes a copy review of the changed component and its
adjacent text. Review idle, loading, success, empty, partial, truncated, and failure
states that the component supports.
Confirm that each text element has one role, terminology and state language are
consistent, recovery advice is actionable, and no sentence duplicates visible
information. Exercise narrow layouts and keyboard or assistive-technology announcements
where the copy can wrap, truncate, or update dynamically.
Behavior tests should protect meaningful state distinctions and recovery guidance
without freezing incidental wording throughout the codebase.

## Accessibility Checklist

- Every interactive element is reachable and operable by keyboard.
- Icon-only controls have an accessible name.
- Focus remains visible against both themes.
- Status does not rely on color alone.
- Text meets contrast requirements at its actual size and weight.
- Tooltips supplement, rather than replace, persistent labels for essential controls.
- Print views hide host chrome and retain the rendered document or source content.

## Review Checklist

When adding a component or plugin view:

1. Identify the existing primitive and tokens it can reuse.
2. Test narrow and wide panes, long paths, empty data, malformed data, and large data.
3. Review all chrome copy and adjacent text across supported states.
4. Check light theme, dark theme, keyboard focus, reduced motion, and print output.
5. Verify lazy mount and disposal behavior.
6. Run Biome, TypeScript check-JS, and the relevant browser-side tests.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
