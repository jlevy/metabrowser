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
   Size limits are claims about cost and must be measured, not assumed; see
   [rendering large content](large-content-rendering.md) for the cost model, the
   strategy ladder, and the current limits.
5. **Light and dark themes share semantics.** Theme overrides may change contrast and
   lightness, not the meaning of a token.
6. **Everything is effortlessly fast.** Speed is a product requirement, not an
   optimization to get to later, and a visible loading state is a failure to plan rather
   than a neutral way to spend time.
   Prefetch whatever the reader is plausibly about to ask for — the subfolders in view,
   the next surface of the selected file — unless the cost is real and known.
   Where waiting is unavoidable, [Motion](#motion) governs what may appear and when.

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

Live is an activity state, not an elapsed-age bucket, but it shares the freshest
reddish-orange token and bold weight with the under-one-minute tier.
That warm family remains distinct from the deeper destructive red and from success
green. The six elapsed-age buckets retain the existing thresholds: under one minute,
under one hour, under one day, under one week, under one month, and older.
They move from gold through yellow-green while chroma and prominence fall monotonically
toward a warm neutral.

Text color is the sole age hue signal; dates and Live labels never gain a dot, swatch,
or adjacent color cue.
Light-theme text derives from the visible swatches in the approved reference ramp:
reddish orange for Live and under one minute, then high-saturation yellow followed by
progressively quieter yellow-green and neutral endpoints.
After the adjacent dots were removed, the text retained those swatch hues, lowered
lightness modestly, and raised chroma so the labels remain dark enough for the UI while
carrying the vivid color themselves.
The `.age-live` and `.age-*` classes select tokens only, so new consumers reuse the
primitive rather than reconstructing colors.
The navigation age menu’s Live entry and under-one-minute labels in file rows therefore
have identical computed color and bold weight.

Adjust this family only at its token definitions, preserve the semantic ordering in both
themes, and run `tests/test_file_age_palette.py` to verify the approved light palette,
OKLCH structure, semantic ordering, and dark-theme surface contrast.

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
For a chord or alternative, emit one `.kbd` per physical key so each keeps its own
border.

The component, its tokens, and its markup contract are documented in the
`── Keyboard keys ──` blocks of `static/styles.css`.

#### Canonical Key Names

Event matching, visible keycaps, spoken names, and `aria-keyshortcuts` are different
representations. The shared shortcut formatter derives every applicable representation
from one semantic binding; a caller never abbreviates a key or substitutes an arrow
glyph itself.

| Semantic key | Markup label | Spoken name | ARIA key token |
| --- | --- | --- | --- |
| `?` | `?` | Question mark | Omitted when matched as a produced character |
| `/` | `/` | Slash | Omitted when matched as a produced character |
| Letter key | Uppercase letter, such as `T` | The letter | Uppercase letter, such as `T` |
| `ArrowUp` | `↑` | Up arrow | `ArrowUp` |
| `ArrowDown` | `↓` | Down arrow | `ArrowDown` |
| `ArrowLeft` | `←` | Left arrow | `ArrowLeft` |
| `ArrowRight` | `→` | Right arrow | `ArrowRight` |
| `Enter` | `Enter` | Enter | `Enter` |
| Space (`KeyboardEvent.key === " "`) | `Space` | Space | `Space` |
| `Escape` | `Esc` | Escape | `Escape` |
| `Home` | `Home` | Home | `Home` |
| `End` | `End` | End | `End` |
| `Delete` | `Delete` | Delete | `Delete` |
| `F2` | `F2` | F2 | `F2` |

The `.kbd` text transform produces the visible caps treatment; source markup keeps the
mixed-case label in this table.
The
[WAI-ARIA definition of `aria-keyshortcuts`](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
describes physical keys, not generated characters.
ARIA serialization is therefore a separate, optional formatter output: it uses `Escape`
instead of the visible `Esc` and `ArrowUp` instead of `↑`, but omits a character-matched
punctuation binding when the physical chord varies by keyboard layout.
Do not guess `Shift+/` for a `?` binding that intentionally works on any layout
producing that character.
When modifier bindings are introduced, the formatter owns both platform labels and ARIA
serialization; no call site chooses between names such as Control, Command, or Meta.
Adding a key that is not in this vocabulary requires adding its display, spoken, and
ARIA policy together with formatter tests.

#### Binding Grammar and Accessibility

- Alternative bindings use the word “or”: `T` or `/`.
- Simultaneous keys use a plus sign: `Ctrl` + `F`.
- Ordered key sequences are not supported and must not be implied by adjacent keycaps.
- Direction pairs use “or,” not a slash or unexplained adjacency: `↑` or `↓`.

The visual and spoken forms are both generated.
An isolated key may use its natural-case `<kbd>` text as its accessible name.
A group of alternatives or a chord exposes one visually hidden phrase such as “T or
slash” or “Control plus F” and hides its visual punctuation and keycaps from assistive
technology, avoiding duplicate or ambiguous announcements.
An actionable control keeps its action as the accessible name and receives the
formatter’s `aria-keyshortcuts` value separately when the formatter can represent the
physical shortcut accurately.

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

### Reading Width

Prose reads at a width the reader sets, in **characters**, through “Max text width” in
the Metabrowser menu.
Characters rather than a length because that is the decision a reader has: 45–75 is the
classic range for a single column, and a browser pane is wide enough to sit above it.
The default is 105.

Three tokens, all on `:root`:

| Token | Meaning |
| --- | --- |
| `--doc-max-chars` | the reader’s setting; the menu writes it, the pre-paint script seeds it |
| `--doc-char-advance` | average glyph advance per em for the current reading face |
| `--doc-measure` | the resolved length: base × chars × advance |

`--doc-measure` is the single source of truth for how wide prose reads anywhere in the
app, and the only place the character count is converted.
Every prose surface reads it: the KPress bridge, the folder Overview’s card widths, and
the fallback `md-body` path a plugin gets when it renders Markdown without KPress.
A new surface that lays out prose reads `--doc-measure`, never a literal.

**Never read `--kpress-measure` from host CSS.** KPress declares that token on
`:root, .kpress, …` from a stylesheet that loads after the app’s, so on `:root` the
app’s value is overwritten and on `.kpress` it is shadowed on the element that consumes
it. Host CSS outside a `.kpress` scope therefore resolves KPress’s default rather than
the reader’s setting — which is exactly how the Overview’s README came to render at a
different width from the same file opened on its own.
`--doc-measure` is app-owned and cannot be shadowed.
One bridge, `.metabrowser-kpress-host .kpress { --kpress-measure: var(--doc-measure) }`,
carries it into the document.

The advance ratio is measured, not assumed, over 507 characters of representative
English prose: 0.4335 em/char for PT Serif and 0.4039 for Source Sans 3, so the sans
reading mode swaps the ratio and the same character count still holds.
This is the average advance, not the CSS `ch` unit — `ch` is the advance of “0” and
overstates a proportional face by roughly 23%. KPress ships no per-face constants
because a host may swap the face; Metabrowser pins its own faces, so it owns the
conversion.

Verify a width change by measuring the *text* box with padding excluded, in both the
single-column and wide bands, and against the same file opened on its own.
A card can be the right width while the text inside it is an inset-pair too narrow.

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

### One Tooltip, and It Is Ours

The app has its own tooltip: anchored to the element it describes, styled, themed, and
on the app’s timer. The browser’s native `title` is a second tooltip system, and a
surface carrying both shows the reader two tooltips side by side on different timers.
That happened on the navigation heading, so the rule is enforced rather than remembered.

**No `title` attribute, and no `.title =` assignment, anywhere the app owns the markup**
— browser sources, built-in plugins, and the HTML the server renders.
`devtools/check_tooltips.py` fails the build on one, and runs in `make lint`.

| Need | Use |
| --- | --- |
| A short string | `data-tip-text="…"` |
| Rich content — counts, sizes, several lines | `MetabrowserTooltip.show(html, anchor)`, or `mb.tooltip.show` from a plugin |

**A tooltip reads at body size**, `--tooltip-font-size`, with subordinate lines one step
down at `--tooltip-detail-font-size`. Neither may be spelled as another token or as a
literal. Pointing a tooltip at `--ui-small-font-size` — the size of chips, counts, and
row metadata — makes its size a side effect of a decision about chrome, so the next
adjustment to small chrome text moves every tooltip with it.
A tooltip is prose the reader has stopped to read.
`devtools/check_tooltips.py` holds this alongside the rule above.

KPress’s own tooltip inside an embedded document is not this tooltip and keeps its own
ramp; see the note beside the radius bridge in `styles.css` for why the app flattens
KPress’s radii but not its type scale.

`data-tip-text` is read by a delegated pointer listener on the document, so it works on
markup that does not exist yet, including a plugin’s.

### Tooltip Input Modality

**Navigation tooltips are pointer-only.** Keyboard focus already communicates the active
row or control through focus treatment, selection state, its accessible name, and the
content it opens.
A tooltip must not cover that content or repeat it merely because focus
moved.

Pointer hover may open supplementary tooltip detail.
Pointer leave or any focus transition dismisses it, and focus alone never opens or
retains it. This contract applies to delegated `data-tip-text` tooltips and rich
navigation tooltips such as Git commit summaries.
Tooltip content therefore cannot be the only source of an accessible name, instruction,
or state.

This is not a rule about accessible names.
`aria-label` is unaffected and still required wherever it was: a screen reader does not
read `data-tip-text`, so an icon-only control needs both.

### Hover Styles the Thing Under the Pointer

A hover is a statement about one element, so it is drawn **on that element** and nowhere
else. Dimming, fading, or desaturating an item’s neighbours to pick it out is not
available: it is a larger visual event than the interaction earns, it makes the reader’s
eye track motion across the whole component rather than the one thing they pointed at,
and a dimmed neighbour reads as *excluded* or *inactive*, which is a claim the hover is
not making.

For a segment of a bar, a treemap cell, a chart mark, or any other measure the reader
can point at:

| Do | Do not |
| --- | --- |
| Grow the hovered mark on the axis that carries **no** data, with `--viz-hover-grow` on `--viz-hover-grow-ease` | Grow the axis that encodes the value |
| Lift its own color a step with `--viz-data-mark-hover-filter` | Dim, fade, or desaturate the other marks |
| Leave every other mark exactly as it was | Outline, ring, or border the mark, or move the layout |

**Grow, do not outline.** An outline is drawn *on* the data: it covers the color it is
meant to point at, it competes with whatever separators the component already has
between marks, and on a short mark it is a large fraction of the height — two pixels of
ring is a quarter of an eight-pixel track.
Growth says the same thing and covers nothing, and the eye is already good at finding
the one thing that moved.
This was tried as a translucent ring and then as an opaque grey one before landing here;
neither is the instrument.

**Grow the axis that carries no data.** This is the part that is easy to get backwards.
On a horizontal bar the *width* is the value, so it is the one dimension that must not
move: growing it states a share the mark does not have, and every mark after it appears
to shift. Thickness means nothing there, which is exactly what frees it — so a bar
segment grows *taller*, centered on the baseline the eye follows along the row.

It also makes the answer uniform.
A proportional width grew a wide segment by fifteen pixels and a three-pixel segment by
nothing, so the marks hardest to point at were the ones that answered least.
Every segment shares one height, so every segment now answers the same.

Because the axis is small, the factor is large: an eight-pixel bar at 1.5 is twelve, and
the overshoot carries it past thirteen before it settles.
A few percent would be a fraction of a pixel.

**Grow with a transform, never with layout**, so the row does not reflow under the
pointer.

**The curve is what makes it read as an answer.** `--viz-hover-grow-ease` overshoots its
target and settles back, so the mark goes further than it ends up and returns.
At around 190ms that is a flick; the same distance on a plain ease reads as the layout
being sluggish.

Growth is proportional, so a wide mark moves further than a narrow one.
That is the right way round: a one-pixel segment has almost no color to lift either, and
its tooltip is what identifies it.

The lift darkens on light and brightens on dark, and it is relative to the mark’s own
color rather than a fixed overlay — file-type families no longer share one lightness,
they sit in a band and a deviating family sits outside it, so a fixed delta lands
differently on a pale family than on a dark one.
See [color and theming](#color-and-theming).

Under `prefers-reduced-motion` the growth is dropped rather than made instant: an
instant jump is worse than no growth, and the color lift still answers the hover.

**Where growth does not apply.** Two conditions rule it out, and the treemap meets both
— it takes the lift alone.

- *The mark’s area is its value in two dimensions.* A bar segment’s width encodes its
  share and the overshoot settles back to it, so nothing is misstated once the motion
  ends. A treemap cell’s area is the whole encoding, and a cell held larger states a size
  it does not have.
- *The mark cannot be lifted above its neighbours.* Growth needs the mark on top, and a
  treemap flattens a nested folder and its descendants into siblings, so raising a
  hovered container paints it over every rectangle inside it.
  `test_treemap_hover_never_promotes_a_container_over_nested_cells` holds that.

A new chart mark that meets neither condition grows.
One that meets either keeps the lift and states why here.

### Continuing Partial Content

A view that shows part of a file offers the control that loads the rest **at both ends
of the content**, above it and below it, whenever more remains.

The reader who most wants the next chunk is the one who just finished the current one,
and they are at the bottom.
A single control in the pane header is out of view by then, so continuing means
scrolling back through everything already read to reach it — the longer the content, the
worse the cost, which is exactly backwards.
Both controls carry the same label, act on the same state, and appear and retire
together.

### Notices

A **notice** is any box the app draws to say something *about* the content it is
showing: that a file is only partly loaded, that a document could not be rendered.
They are one primitive, `.notice` in `static/styles.css`, in core and in plugins alike.

Its fill is always the ordinary surface — `var(--bg)`, white in the light theme — and
**severity is carried by the border alone**, as one `[data-severity]` override:

| Severity | Border | Means |
| --- | --- | --- |
| (none) | `var(--border)` | Neutral; the box is a container, not a signal |
| `warning` | `var(--status-warning)` | Incomplete, capped, or degraded — the content is fine as far as it goes |
| `error` | `var(--status-error)` | The thing could not be done at all |

One tone per box, and it is the one on the edge.
Tinting the fill is how these drifted, twice: the partial-content banner wore an
info-blue fill with a warning border while the byte view announced the same condition
with no box at all, and the KPress render error wore that same blue under an orange
border — an error announcing itself in the color of an aside, beneath a border naming
the wrong severity. A tint token such as `--status-info-bg` exists for surfaces that
genuinely mean “informational”; it is never a message box’s fill.

A use site carries `.notice` in the markup alongside its own class, and owns only
**layout and position** — how it arranges its contents and where it sits.
It never restates the fill, border, or type, the same rule the
[control families](#control-families) follow, for the same reason.
Layout is deliberately not shared: a one-line notice with a button and a stacked render
error with a detail block have nothing useful in common there.

`tests/test_notice_style.py` enforces all of it.
It fails the build if the primitive is redefined outside core, if its fill stops being
the surface, if a severity does anything but set a border color, if a use site declares
its own background, border, color, or font, or if any stylesheet uses a status tint as a
box fill.

Build a partial-content notice through `mb.partialNoticeHtml` rather than by hand, so a
new view gets the markup, the severity, and the placement together.

### State Progress Once

The notice is the only place a view reports how much of a file is loaded.

Both views used to carry a second readout in their pane chrome — “1.0 MB / 6.0 MB” above
a notice reading “Showing 1.0 MB of 6.0 MB” — which is the same sentence twice in two
boxes, and gives a reader two things to reconcile where there is only one fact.
The file header states the file’s **size**, which is identity; the notice states
**progress**, which is state.
The two controls at the ends of the content are not a second statement: they bracket the
same content so the reader meets one of them wherever they are.

Three supporting rules follow from the same reasoning:

- **A notice that content is missing carries its own control.** Telling a reader that
  more exists and pointing them elsewhere to ask for it puts the explanation and the
  remedy in different places.
  The partial-content banner holds a Load more button rather than naming one.
- **Retire the control when nothing remains.** A control that cannot do anything reads
  as a broken control, and any trailing rule or spacing it owns goes with it.
- **A bound on loading is not a refusal to show anything.** When a view caps how much it
  will load, it still opens the file and loads up to the cap; it then keeps the notice,
  drops the control, and says the limit was reached.
  “No control” and “you are seeing the whole file” look identical otherwise, and a
  reader who cannot see the rest needs telling either way.
  The byte view previously refused any file above its 32 MiB ceiling outright, which
  meant the view existed for binaries and declined the large ones with nothing to look
  at.

Core provides both halves through `mb.renderTextTruncationWarning` and
`mb.renderTextLoadMoreFooter` for views whose progress comes from `/api/file`, and
`mb.partialNoticeHtml` for a view that tracks its own offsets.
A plugin gets the placement and the style by using them rather than by reproducing them.
See [Rendering Large Content](large-content-rendering.md) for the loading policy behind
the chunk sizes these controls request.

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

Every nonempty folder controls one adjacent `.tree-children[role="group"]` element.
Server-rendered rows, live inventory inserts, and restored rows use the same child-group
markup contract: the row’s `expanded` or `collapsed` class, `aria-expanded`, and the
group’s `tree-children-collapsed` class always agree.
An inline display rule must not hide the group because it would outlive later class and
ARIA updates. `test_live_folder_insert_uses_the_canonical_collapsed_group_contract`
enforces the shared renderer path, and the headed Git revision scenario opens a folder
that arrived while the Files panel was inactive.

### Container Rows

A file whose kind declares the container capability keeps its file identity — icon,
name, size, selection — and additionally leads with the tree’s disclosure chevron in the
same 16px alignment box a folder uses, so names stay aligned at every indent.
Its children are ordinary rows carrying a one-letter change badge in place of the file
icon. Clicking is one gesture, as on a folder row: it opens the file *and* toggles its
children. The keyboard splits them the same way, and every disclosure affordance in the
tree — ARIA state, arrow keys, filtering — asks whether a row owns a child group, never
what kind of row it is.
See [nav containers](project/architecture/arch-nav-containers.md).

### Section Disclosure Headers

Use the section-disclosure primitive when a labelled section may hide its body without
changing the selected file, folder, or top-level view.
Folder Overview panels use a button inside their visible `h2`; rendered-document
metadata keeps native `details` and `summary` semantics.
Both forms place the same gray Lucide chevron immediately after the title with
`--section-disclosure-chevron-gap`. Row-like triggers lead with the registry’s
`toggle-chevron` glyph instead (see One Chevron, One Row Contract below); the primitive
itself has no leading form.
The mark uses `--section-disclosure-chevron-size` in `em`, so it remains proportional to
the unchanged local heading typography at every type tier.
It points right when collapsed and rotates down when expanded.

The title and chevron form one focusable target.
A button trigger declares `type="button"`, `aria-expanded`, and `aria-controls`; its
section uses `aria-labelledby` to preserve the visible heading as the accessible name.
Collapsing an already mounted section hides its body without remounting or disposing its
renderer. Overview panels start expanded on each mount.
Markdown Frontmatter and Diagnostics disclosures start collapsed through the absence of
the native `open` attribute.
These defaults are not saved as user preferences.

The diff view’s per-file bar is **a row, not a heading disclosure**: it leads with the
same registry chevron the tree uses (`.toggle-chevron`, rotated by the shared
`expanded`/`collapsed` classes), sits at the shared `--ui-row-height`, hovers with
`--hover-bg`, and reveals its `[data-mb-copy]` copy control on row hover or focus — the
file-header copy affordance, present wherever a filename is.
Its content is left-aligned reading order — chevron, kind letter, filename in the
shell’s file-path typography, then the stat pair beside the name — and the whole bar is
one activation surface, the folder-row rule applied to a section header: clicking
anywhere toggles, with only the copy control opting out.
A collapsed section keeps the section’s own border as its single line.

### One Chevron, One Row Contract

Every disclosure chevron in the product is the same Lucide mark: the registry’s leading
glyph on row-like targets (tree folders, tally tree, diff file bars) and the
section-disclosure mask after heading-like titles, both in `--muted`, pointing right
when closed and rotating to point down when open.
Row-like activation targets share `--ui-row-height` and `--hover-bg`. These agreements
are enforced by `tests/test_design_vocabulary.py`, which fails when a surface forks the
glyph, the row height, or the hover token.

### Fold Expanders

A run of content withheld until asked for — a long stretch of changed lines in a diff —
sits behind a full-width control at `--ui-row-height` carrying the same registry
chevron, in `--highlight-bg`, hovering with `--hover-bg`. The label states the count it
holds (`86 more changed lines`) and becomes the inverse when open (`Hide 86 lines`),
because a control that hides its size is a control the reader cannot judge.
A fold inside another disclosure stops its click, so expanding a fold never collapses
its container.

### Disclosure Motion

Every toggle travels the same way: the body animates `height` between `auto` and `0` on
`var(--transition-fast)` — the same duration its chevron rotates with — with
`overflow: hidden` during travel and `visibility: hidden` at rest so collapsed content
leaves the tab order and the accessibility tree.
`interpolate-size: allow-keywords` is scoped to each animated body; engines without it
swap instantly, which was the prior behavior.
Collapse is always class-driven (`.tree-children-collapsed`,
`.diff-file-body-collapsed`, `.diff-fold-collapsed`,
`.folder-overview-panel-body-collapsed`), never inline `display`, so the stylesheet owns
the motion, and reduced-motion drops every travel to 1ms while keeping the state change.
`tests/test_design_vocabulary.py` pins the recipe on every site.

### Color and Theming

**Every color is declared in `oklch`** — there are no hex, `hsl`, or `rgb` literals, and
`tests/test_design_vocabulary.py` rejects new ones.
One notation is not a style preference: `oklch` separates the three things a theme has
to reason about — lightness, chroma, and hue — so they can be compared across tokens and
across themes. In `hsl` they cannot, which is how a chip ground came to carry four times
its neighbours’ chroma, and how thirty-five tokens came to shift hue between themes
without anyone choosing that.

> A token defined in both themes names **one color seen against two backgrounds**: its
> **hue is the invariant**, while lightness and chroma are tuned for the background it
> sits on — dark surfaces generally want less chroma, not more.

Near-neutrals are the one exemption: below about `0.02` chroma the hue is not
perceptible, so requiring it to match would constrain a number nobody can see — and
would force the dark theme’s cool grays to adopt the light theme’s warm ones.

Consequences worth knowing:

- A token that needs a different hue in one theme is two different colors and should be
  two tokens with names that say so.
- A token defined in one theme only is a bug in waiting: a literal tuned for a light
  background is unreadable on a dark one, which is exactly how `--git-ref-local` broke
  when it stopped inheriting a themed token.
- The graph lane colors are the documented exception, and the reason is in the
  stylesheet beside them: they are one *set*, chosen so the five stay distinguishable
  from one another, and that property belongs to the set rather than to any member, so
  they are identical in both themes and are never returned individually.

`tests/test_design_vocabulary.py` enforces both halves: every color is `oklch`, and
every chromatic token defined in both themes carries the same hue in each.

### Age

An age is an age, wherever it appears — a file row, a commit row, a commit’s header.
One primitive produces all of them: `MetabrowserFormatters.age()` returns the
abbreviation (`<1m`, `5m`, `2h`, `3d`, `2w`) and the freshness class (`.age-live` …
`.age-old`), and the `:is(...)` rule over those classes owns the hue, the weight, the
small size, and tabular numerals.
Call sites add positioning only, never color, weight, or their own abbreviations — the
same discipline `.size` follows for byte counts.
An exception needs a line in this document; otherwise there is one age.

## Git History

The history panel has its own vocabulary because it shows a structure nothing else in
the product shows — a graph of commits — but it borrows every general element it can:
ages come from [Age](#age), change counts from
[Inline Change Stats](#inline-change-stats), and rows follow the shared row height and
hover.

### Lane Colors

Five lane colors, `--git-lane-1` through `--git-lane-5`, assigned round-robin as lanes
open. They are **one set, not five independent choices**: the property that matters is
that the five stay distinguishable from one another, which belongs to the set, so a lane
color is never adjusted on its own and the set is identical in both themes — thin
strokes carry on either background.
This is the documented exception to the hue rule in
[Color and Theming](#color-and-theming).

The lane a commit sits on colors its node, so a commit and the history below it read as
one line. `HEAD`’s lane takes `--git-ref-local`, tying the graph to the chip that names
the branch.

### Commit Nodes

**Every vertex is the same solid dot.** Shape carries no state.

Rings and ring-plus-dot variants encoded HEAD and merges once, and the encoding failed
twice over: at this radius the variants read as noise rather than meaning, and the
hollow center had to be painted with a copy of the row’s background, so every row state
— hover, selection, anything added later — had to restate that color or the node changed
shape under the highlight.
What matters stays legible where it already was: `HEAD` by its lane color and its chip,
a merge by the arcs converging on it.

### History Rows

A row is the graph, then the commit, then who and when:

| Part | Sizing |
| --- | --- |
| Graph gutter | Shrink-wraps **this row’s** lanes, so the subject starts where that row’s graph ends. A shared column would spend the widest row’s width on every row. |
| Ref chips | Fixed; shrink last (see below) |
| Subject | Takes the remaining space and absorbs the row’s shrinkage, ellipsizing |
| Author and age | Fixed, right-aligned; slide outward as the panel widens |

When a row cannot fit everything, the order it gives way in is **subject, then chips,
never the age**: an age pushed off the row is information lost, an ellipsized message
still reads, and a halved branch name does not.
Rows are independent — no shared column — which is also what lets a new page of history
be appended to the list instead of rebuilding every row above it.

### Git Commit Summary

The selected commit begins with one `.git-commit-summary` component rendered by
`renderCommitSummary` in `static/git-panel.js`. Its anatomy has one order:

1. subject;
2. metadata containing an identity group with the short revision and refs, followed by
   author and age;
3. `.git-commit-change-stats`, with one file-status row and one line-total row; and
4. the commit description, when present.

The identity group uses the same branch, remote, tag, trunk, and HEAD badge forms as the
Git history row. The full summary makes the revision copyable; the compact summary keeps
the familiar copy glyph noninteractive.

The change-stats child sits below the identity metadata.
Its first row reports exact file-status families with Git’s letters and ends in “file”
or “files.” Its second row reports line additions and deletions and ends in “line” or
“lines.” `M` contains modified, renamed, and type-changed files; `A` contains added and
copied files; `D` contains deleted files.
These families cover every supported file status exactly once.
A zero family is omitted.
The server computes all counts before bounding the returned file list, so a large commit
remains exact. Line totals use the shared semantic colors and weight and render a true
minus sign. Missing totals remain visibly unknown.

The subject, ref badges, author, age, file-status counts, units, and line counts use
`--body-font-size` in both projections.
The revision is the one deliberate exception: it is monospace, and mono at body size
renders optically larger than the sans text beside it, so it uses `--nav-font-size` —
one step down the ramp — to sit level with its row.
The compact tooltip is bounded by width and subject line count, not made denser with
smaller type. The optional full-summary description is prose: it uses `--font-sans` at
`--body-font-size`, wraps naturally, and preserves the newlines authored in the commit
message.

Pointer hover on a Git history row uses `.git-commit-summary-compact` as the tooltip
projection of this component.
It retains the subject, author, short revision, age, and two-row change stats, while
omitting the commit description.
Refs remain beside the revision just as they do in the full summary and Git history.
The subject is clamped to two lines so one message cannot take over the viewport.
The familiar mark beside the revision is a noninteractive copy glyph, not a control:
tooltips remain supplementary and never own actions.
Selecting the commit exposes the real copy button in the full summary.
Keyboard focus does not open or retain the compact tooltip.
Arrow, Enter, and Space selection dismisses any pending or visible pointer-owned tooltip
before navigation.

The component owns commit identity and message only.
The comparison, files outside the served root, and truncation notice are siblings under
`.git-commit-view`, because they describe the rendered change rather than the commit
summary. A revision-hosted comparison suppresses its aggregate summary so the mounted
view has one set of totals; direct diff documents retain their own summary.

Do not assemble commit-summary fragments in `renderCommitDetail` or add a second root.
`tests/test_design_vocabulary.py::test_git_commit_summary_is_one_component` maintains
the renderer, root, child, styling, and documentation contract.

### Branch Chips

Git ref badges (`.git-ref`) are their own vocabulary, not filter chips.
In the dense Git history row they use `--micro-font-size`; in the commit-summary
component they use `--body-font-size` with the same form.
The name carries the meaning, so it is always `--weight-bold`, and the corner is
`--radius-tag` (square-ish) so “a ref” and a “filter” never read as the same control.

A chip answers two independent questions, and each has its own signal:

| Question | Signal |
| --- | --- |
| What kind of ref is this? | **Form.** An ordinary branch is the plain chip. **Trunk** — `main` or `master`, local or on a remote — is solid: its color becomes the ground. A **tag** carries a notched left edge, so `<tag)` and `[branch]` differ in shape, not only in hue. |
| Is HEAD here? | **A ring.** `HEAD` can sit on trunk, an ordinary branch, or nothing, so it is marked without changing the chip’s form. |

Shape carries the kind because hue alone cannot: a reader who does not separate the
branch and tag hues would otherwise see one vocabulary with two colors.
Which refs count as trunk is decided server-side, by the same names that scope the
history walk, so the answer cannot differ between the graph and the walk.
Color still carries local, remote, and tag as a secondary signal.
Their ground is `--git-ref-bg`, a near-neutral of its own rather than the shared chip
surface, sitting at the value of the surfaces beside it with just enough chroma to
separate from them. The three ref colors — `--git-ref-local`, `--git-ref-remote`,
`--git-ref-tag` — are one lightness and three hues, so a ref’s kind is legible without a
second signal, and the dark theme raises only their lightness so they stay the same
three colors.

### Inline Change Stats

The `+N` / `−N` pair that rides beside a filename wherever a surface reports change
size: `.diff-stat-add` in `--status-success`, `.diff-stat-del` in `--status-error`,
always in that order, using the true minus sign, at the local small-text size, and
always `--weight-bold` — the pair is data, and it must read at a glance.
The git commit view’s `.git-stat-add`/`.git-stat-del` follow the same color and weight
rule but use the commit summary’s standard body size.
The same pair is the summary line’s vocabulary, so a change set and its files read
identically. Kind letters reuse the same mapping — added is `--status-success`, deleted
is `--status-error` — and no diff surface introduces a local green or red.

### Diff Change Surfaces

A changed diff line has three visual layers with separate jobs:

1. The whole-line fill establishes the added or deleted region.
   A wholly added or deleted line uses the stronger semantic fill.
   When refinement finds meaningful unchanged text, the row uses a pale fill so the
   unchanged portion recedes.
2. A stronger intraline fill restores emphasis to the exact text that changed within a
   refined row.
3. A solid status-colored inset at the leading edge of the line-number gutter marks
   every added or deleted line, including whole-line and unrefined changes.

The backgrounds form three perceived depths.
An unrefined whole-line change uses the medium 9% status-token mix.
A refined pair uses only the lightest 3% mix for unchanged text and a 20% overlay for
the changed intraline ranges, producing the darkest 22.4% composite depth; it does not
also show the medium depth.
The changed range uses the standard text foreground because several syntax accents do
not retain 4.5:1 contrast over the darkest light-theme surface.

Depth selection applies to one contiguous changed run.
A run with no refined pair keeps the medium treatment for its wholly added or deleted
rows.
Once any old/new pair has meaningful unchanged text, every row in that run uses the
lightest background.
Exact changed ranges use the darkest fill, and a wholly added, deleted, or unpaired
neighboring row treats its complete text as the changed range.
This keeps a mixed rewritten paragraph coherent without making an independent new or
removed paragraph look intraline-refined.

All three layers derive from `--status-success` or `--status-error`. The diff plugin may
define compositional custom properties for opacity, but it must not introduce local
green or red literals.
The gutter is an inset decoration on the first line-number cell, not a grid column or
added element, so context and changed rows retain identical line number and text
alignment. Unified and split layouts consume the same `.diff-line-add`/`.diff-line-del`
and `.diff-intraline-change` vocabulary.

The line marker and line numbers continue to state change direction without color.
The gutter is a persistent structural cue, not the only cue.
Syntax foregrounds retain at least 4.5:1 contrast over line surfaces in both themes, and
intraline ranges use the standard text foreground to meet the same floor over their
stronger overlay.

### Diff Layout Control

The joined layout control always orders **Split** on the left and **Unified** on the
right. A reader without a valid stored `diff.layout` preference starts in Split.
Either valid stored choice remains authoritative, and switching layouts reprojects the
shared semantic model without re-fetching or re-running syntax highlighting.

Section headings use `--section-heading-divider-gap` between their content and the
divider. Components consume the token instead of choosing local bottom padding, so the
divider remains equally close to headings with and without disclosure controls.

This pattern does not replace the navigation-tree disclosure.
The tree keeps its leading chevron because that mark communicates hierarchy and shares
one activation target with folder navigation.

## Keyboard Commands and Help

Application commands have one registry and one document-level dispatcher.
The same descriptors drive matching, the full Help list, compact hints,
`aria-keyshortcuts`, and shortcut hints in menus.
No surface keeps a parallel key-name map, copies command text, or installs another
document-level application-shortcut listener.

Widget behavior that belongs to a focused control, such as arrow navigation within a
menu or radiogroup, stays on that component’s root.
If that behavior is advertised in Help or another hint surface, its presentation still
comes from a registered descriptor.
Document-level commands ignore editable controls, composition, previously handled
events, and modifiers they did not declare.
They prevent browser behavior only after an enabled handler reports that it acted.

A command may opt back into an editable target only for a key that field does not
already own. A combobox may claim the arrow keys, `Enter`, and `Escape`, because none of
them edit text. It may not claim `Home` or `End`: those move the caret, and taking them
leaves the user unable to reach the start or end of what they typed.
When a list needs first-item and last-item reach behind an editable control, its
movement commands wrap instead of borrowing the caret keys.

### Navigational Row Collections

A row collection whose primary action replaces the main content behaves as one keyboard
control. Exactly one mounted row participates in the Tab order: the current row when one
exists, otherwise the first row.
All other rows remain programmatically focusable with `tabindex="-1"`, so Tab enters and
leaves the collection once instead of stopping on every item.

While a row has focus, unmodified Arrow Up and Arrow Down move to the adjacent mounted
row and open it. Key repeat remains enabled for fast traversal.
Movement clamps at the first and last row, prevents page scrolling, and does not reopen
the row at a clamped edge.
Activation updates the roving anchor without stealing focus.
Enter, Space, and pointer activation retain the control’s ordinary behavior.

Interaction work is proportional to the change, not the collection size.
Moving or selecting mutates only the prior and next anchor or selected row; a mounted
list may scan all rows when it is first synchronized, but an Arrow-key or pointer
activation must not rewrite every row before the main view can acknowledge the
selection. When a retained view contains many focusable controls, the newly focused row
may remain programmatically focusable at `tabindex="-1"` during the pending interval.
Its visible focus, selected state, route, and claim-owned busy state update in the input
task; the component finalizes the one-row Tab anchor after painted readiness.
This avoids a whole-document focus-order recalculation before the browser can paint the
acknowledgement.

The component owns this focused behavior; it is not a document-level application
shortcut. The maintained registry in
`test_nav_like_row_sets_share_the_vertical_keyboard_contract` covers the file tree and
Git history. The adjacent `test_git_row_selection_avoids_full_collection_mutation` pins
Git’s interaction cost.
Register every new navigational row collection in the shared check so its Tab order and
vertical navigation cannot silently fork this contract.

### Descriptor Contract

Every presented command declares:

- a stable identifier and scope;
- semantic bindings, including explicit modifier and repeat policy;
- a group identifier whose heading, context sentence, and order come from one group
  registry;
- one sentence-case action label with no terminal punctuation;
- one active-voice Help description ending in a period;
- a compact hint of one to three words when the full label will not fit; and
- the surfaces where it appears and when those surfaces may show it.

A command rendered as a control that opens a managed surface also supplies a control
binding from that surface.
The binding connects a rendered trigger to its stable controlled-element ID, popup role
when applicable, and current expanded state, then restores any prior state when
disconnected.
The registry snapshot carries the binding to the renderer; a call site does
not hand-author `aria-controls`, `aria-haspopup`, or `aria-expanded`. Pointer invocation
carries the trigger element to the command so an overlay can restore focus even in
browsers that do not focus a clicked button.

The key formatter, not the descriptor, supplies visible abbreviations and glyphs.
The registry rejects duplicate normalized bindings within one scope and incomplete copy
for any requested surface.
Equivalent keys for one command are aliases in one descriptor.
Separate commands may share a compact hint; the renderer then coalesces adjacent
commands with the same hint and joins their bindings with “or.”

Full Help includes registered contextual commands even when their scope is inactive and
states when each group applies.
Compact hints include descriptors explicitly selected for that surface: persistent
global commands plus selected commands available in the active scope.
They are a high-value subset, not a second exhaustive Help list, and disappear when
their scope is unavailable rather than looking disabled.
Changing contextual hints is not a live-region announcement.

### Shortcut and Help Copy

Shortcut copy follows the general [interface-copy rules](#interface-copy) plus these
surface-specific constraints:

| Copy | Form | Example |
| --- | --- | --- |
| Action or trigger label | Short sentence-case noun or verb phrase; no punctuation | `Quick File` |
| Compact hint | One to three words; sentence case; no punctuation | `Toggle folder` |
| Help description | One complete active-voice sentence describing context or result | `Open the selected file.` |
| Context note | One complete sentence saying when the group applies | `Available while a file-tree row has focus.` |

Copy never repeats the rendered key name, uses a slash to mean “or,” or says “click” for
an action that also works from the keyboard.
Use the canonical product terms “Help,” “Quick File,” “navigation pane,” “file tree,”
and “main pane.” Key abbreviations belong only inside `.kbd`; ordinary prose uses the
full key name.

The Help surface is a modal dialog with three content blocks: a brief description of
Metabrowser, a descriptive link to the public project homepage, and registry-derived
shortcut groups. The description explains the folder, navigation, preview, and
trusted-plugin model in at most three short sentences; it links to longer documentation
instead of duplicating it.
The project link identifies GitHub and announces that it opens a new tab.
Help has a visible labelled trigger, so learning the `?` shortcut is never a
prerequisite for opening it.

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

### Copyable Identifiers Use One Delegate

A copyable path, revision, or other exact identifier pairs its visible monospace value
with an adjacent `.icon-btn.icon-btn-reveal` using the registry’s `copy` icon.
The visible value may be abbreviated when its meaning remains clear, but the copy
payload must preserve the complete identifier.
The Git commit header therefore shows the short revision and copies the full commit ID.

Explicit values use `data-mb-copy="text"`, carry their escaped payload in
`data-mb-copy-text`, and name the resting action in `data-mb-copy-label`,
`data-tip-text`, and `aria-label`. Source blocks use the same SDK delegate in `wrap`
mode. Do not add a component-local clipboard listener or inline handler.
The shared delegate owns successful, failed, and reset feedback, while the containing
row owns when an `.icon-btn-reveal` becomes visible.
Keep the button in the Tab order even while it is visually quiet.

`test_copyable_identifiers_share_the_copy_contract` maintains the registered path,
diff-file, and Git-revision consumers.
Add each new exact-identifier copy surface to that check.

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
`static/filter-controls.js`. A surface that needs a filter reaches for these rather than
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
shows by its name rather than as `.md +21`. Other remains a family-section heading
rather than a broad preset because its unknown extension population is open-ended and
cannot be represented by a fixed token list.
Named families such as Log files remain selectable within that section.

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

The component uses a declared categorical palette, a neutral **Other** token, a track
token, and a named track-height token.
Consumers apply the palette through `category-palette.js`; they do not copy color
literals or compose colors themselves.
Inline percentage widths are allowed because they encode data rather than theme.

#### The categorical palette

A file-type family owns one number: its hue, declared in the type registry (see
[Family Fields](project/architecture/file-rollup-format/file-rollup-format.md#family-fields)).
Where GitHub’s linguist names a color for the language, the hue is that color’s,
unchanged; families GitHub names no color for take a hue clear of every other.
That is what makes the palette recognizable — Ruby is red because Ruby is red
everywhere.

Lightness and chroma are not the family’s. Each theme states one pair for the whole set,
in `color_oklch.py`, so two segments of a stacked bar differ in hue and in nothing else
and no segment looks heavier than its size.
Chroma is a target rather than a constant: it is set high enough to stay vivid, above
what sRGB holds at every hue, so the cyan-blue band comes in under it.
That pullback happens in Python, not in CSS, because a browser handed an out-of-gamut
`oklch()` clips it — moving lightness and hue by as much as nine degrees, more than the
separation the palette is built on.

The server therefore ships finished colors.
`METABROWSER_SETTINGS.DISTRIBUTION_COLORS` carries each family’s distribution key with
its color on both themes, and `category-palette.js` writes both onto the element as
`--mb-distribution-color-light` and `--mb-distribution-color-dark`.
`.mb-distribution-mark` selects between them by theme and `.mb-distribution-other` takes
the neutral, so a theme change is a selector switch rather than a repaint.
The remaining tokens are `--mb-distribution-other`, `--mb-distribution-track`,
`--mb-distribution-track-height`, and `--mb-distribution-segment-gap`. Core owns these
tokens and utilities; the folder plugin owns File types and Treemap layout selectors.

Segments that sit beside one another are separated by a hairline of the page ground —
`--mb-distribution-segment-gap` wide, in `--viz-surface` — so two families of similar
hue read as two rather than as one wide band.
It is drawn as an inset shadow rather than a gap or a border, because the widths are
percentages that sum to 100 and anything occupying layout would push the last segment
past the end of the track.
A segment narrower than the hairline therefore becomes ground rather than stealing width
from its neighbor, which is the right trade: a sub-pixel share is unreadable as a color
either way.

`make lint` runs `devtools/check_file_type_colors.py`, which holds the upstream
correspondence, the separation floor, and the tone.
Adding a family GitHub has no color for starts with `--suggest`, which prints the widest
free hue.

When a selected metric changes, the table keeps the same category set and colors.
The active measure controls values, percentage widths, emphasis classes, and row order
as one update, and Other stays last and neutral.
A family’s color does not depend on which folder is open or which views are mounted, so
a related visualization such as the Treemap agrees with the table without coordinating.

The semantic table is the visual summary and the source of exact values.
Every row names its category and reports absolute values and percentages; the colored
fills need no separate circle or legend.
Detailed breakdown fills do not become tab stops or add duplicate tooltips and are
hidden from the accessibility tree.
Labels never rely on color or place text on a category fill.

File types uses non-subtotaling row groups in the server registry’s order: Code,
Documentation, Data, Archives, Media, and Other.
Empty groups are omitted.
Membership comes from the same recommended File Rollup Format type definitions used by
rollups, navigation filters, and Treemap colors; surfaces never maintain local extension
lists. Known canonical suffixes roll up into readable family parents such as
**JavaScript**, **TypeScript**, **CSS**, **YAML**, **Log files**, **Archives**, and
**Images**. Log files is a semantic family within Other rather than a separate group.
Compound extensions inherit the longest declared suffix: `.min.js` contributes to
JavaScript’s `.js` child without rewriting the file’s exact logical extension.
Indexed logical extensions contain at most two suffix components, so source maps remain
useful `.js.map` or `.ts.map` rows without fragmenting the table into filename-specific
`.umd.min.js.map` and `.d.ts.map` variants.

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

Overview renders the README at the same measure a reader gets opening that file on its
own, at every breakpoint.
Both surfaces run the same renderer over the same file, so the reader compares them
directly and any difference reads as a defect rather than as a choice.
Three things have to agree, and each one broke it alone: the band boundaries must query
one container — KPress’s `kpress-doc` on the preview pane, not Overview’s own host,
which is that pane minus its padding and so crosses 75rem about 25px later; the wide
column must be KPress’s content track, the measure plus its 2.5rem insets, because
sizing it to the measure leaves the prose padded for a track it is no longer in; and the
narrow inset must equal the article padding Overview drops, or the text runs short by
twice the difference.
`test_one_document_surface_has_one_set_of_breakpoints` holds all three.

The **File Overview** section begins expanded.
It opens with one control row carrying the shared Files / Bytes measure and the **Show
ignored** checkbox side by side, then a fixed two-row composition table, then the full
type distribution beneath it.
**Files** comes first and reports the unignored population immediately from the
inventory snapshot. **Ignored** follows with the excluded population.
Those two are disjoint.
**Total** follows them, set off by a hairline, and is their sum.

Each row displays one absolute selected-metric tally and treats its own population as
100%, so no percentage column appears.
Total earns its place despite being derivable: the type distribution below counts
against the whole directory whenever Show ignored is on, so without a Total track none
of its percentages corresponds to any bar on screen — a family reading 40% there would
be some other share of both bars above it.
With Total present, one of the three tracks always matches the distribution: Total while
Show ignored is on, Files while it is off.
Its full-width track is segmented by the top-level semantic file types in the type
distribution below and carries their declared colors.
The segments follow registry group order and then descend by the selected Files or Bytes
measure within each group.
Sorting uses the combined population, which is the one basis all three rows share and
the only one that does not move when Show ignored does.
All three tracks keep that same order so they stay comparable column by column.
Hovering a colored segment uses the shared body-portaled navigation tooltip: the bold
semantic family name is the first line, followed by the exact file count and byte size
for that row’s disjoint population.
Tooltip-bearing categorical marks use `--viz-data-mark-hover-filter`, the same subtle
whole-mark brightness change used by Treemap cells.
The filter preserves the mark’s hue and the contrast between its fill, border, and
nested content; hover never changes geometry or stacking.

On a tally track the filter alone is not enough, because the track is eight pixels tall
and a brightness change on one segment has almost no area to register in.
The rest of the track recedes as well, to `--mb-distribution-segment-recede`, so the
hovered segment holds its color while its neighbors drop toward the track behind them.
That reads at any hue and at any segment width, and it answers the question the tooltip
raises: which segment is this.
A Treemap cell is large enough to carry the filter on its own and does not recede its
siblings.
It transitions with the shared visualization hover timing, while reduced-motion
mode applies the state immediately.
These supplemental hover tooltips do not create tab stops; the type distribution remains
the accessible source for the same values.
The Ignored row dims its label, tally, track, and colors through
`--dimmed-content-opacity`, the same token used by ignored navigation and Treemap
entries.

Inventory totals render first.
Until a compatible terminal file-type projection is available, each nonzero population
uses one neutral full-width fill.
The projection replaces that fill atomically with exact segments; it never changes the
inventory-backed tally.
A zero population renders no fill.
If a stale projection does not conserve the current tally, the row stays neutral rather
than showing a misleading composition.

The type distribution follows the tallies inside the same section, under no heading of
its own: it is the same question at a finer resolution, and a reader should not have to
get past one to reach the other.

The control row uses the same labelled `.filter-check` **Show ignored** checkbox as
navigation, beside the measure chooser.
Show ignored begins checked when there is no saved preference and changes the population
the distribution counts, and nothing else.

The three tally rows are fixed populations, so the checkbox cannot move their values,
their segments, or their order.
It once decided the shared segment order, which meant toggling it silently reordered
every track — the Ignored row included, whose contents the checkbox has nothing to do
with. `buildFolderTotalsComposition` no longer accepts the flag, so this is structural
rather than a convention.
There is exactly one chooser and one checkbox: the two controls act on the same numbers,
and while they sat in separate sections each silently moved what the other reported.
Both bodies observe the same state object, so either control atomically updates the
totals and the complete distribution.

Visual Type and metric column labels are unnecessary when every metric cell keeps the
same aligned grammar.
The type distribution uses value, track, and percentage; the tallies use value and
composition track. The semantic table retains screen-reader-only headers and updates the
selected metric header between Files and Bytes, so assistive technology receives the
relationships that sighted users get from alignment.

Zero totals do not produce a colored fill, division artifact, or header-only table.
If one metric is zero while another is not, the zero metric uses the neutral track and
the populated metric remains meaningful.
If the whole population is empty, the parent surface renders its explicit empty state
instead of the distribution body.
If the selected scope contains only ignored files, the distribution body stays empty:
the adjacent **Show ignored** checkbox already exposes the relevant action, so the body
does not repeat it as passive instructions.

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
folder maps its dominant extension through the same helper, and remainder cells take the
neutral Other color.
The File types panel and Treemap read the same declared palette, so a semantic family
keeps the same color across both views and across folders.
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

- **File Overview** is the required panel for every folder and starts expanded.
  It carries the rollup controls, the totals, and the detailed type distribution as one
  section.
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
File Overview and README start expanded.
Both collapse in place without disposing their mounted contents.
File Overview uses the stable internal panel ID `folder.file-overview`. It owns the only
Overview control row; shared state applies those choices to its own bodies and to
Treemap.

Panel bodies use one of two presentations:

- A **surface panel** receives a flat host-rendered body and chrome typography.
  File Overview uses this presentation without surrounding cards.
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
In the regular band, the target is the visible `.kpress-long-text` card rather than the
wider `.kpress-doc` frame.
The shared width is
`min(100% - 4rem, var(--doc-measure) + 2 * var(--folder-overview-regular-inset))` — the
column box, meaning the reading measure plus KPress’s inset on each side — which puts
the README’s text at exactly the measure and aligns section rules, labels, tallies, and
bars with the card border.
It reads `--doc-measure`, the app’s own reading width, and never `--kpress-measure`:
KPress declares that token on `:root` from a stylesheet loaded after the app’s, so host
CSS outside a `.kpress` scope resolves KPress’s default instead of the reader’s setting.
See [Reading Width](#reading-width).
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

The type distribution and Treemap render only terminal rollup generations.
The distribution also publishes its validated terminal envelope to the per-directory
projection pool used by Files.
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
bars, table, standalone tally, or synthetic “No README” document panel.
Loading, partial, empty, and failed states must remain visually and semantically
distinct.

## Overlays, Menus, and Dialogs

“Overlay” describes shared placement and lifecycle, not accessibility semantics.
Every overlay chooses a content pattern and uses that pattern’s role and keyboard model.
“Popover” is likewise a visual description, not an ARIA role; do not use it to blur the
difference between a tooltip, menu, and dialog.

| Pattern | Purpose and semantics | Focus and dismissal |
| --- | --- | --- |
| Tooltip | Supplementary, non-interactive text with `role="tooltip"`; cannot contain essential guidance or controls; anchored to the element it describes and fixed once shown | Opens for pointer hover; closes on pointer leave, any focus transition, or Escape; keyboard focus never opens it |
| Anchored popup | A menu, listbox, or other pattern anchored to a trigger or pointer; the content role defines its semantics | Uses that pattern’s focus model; closes on Escape and outside interaction |
| Modal dialog | A labelled task or information surface with `role="dialog"` and `aria-modal="true"` | Moves focus inside, contains Tab, makes background content inert, and closes through Escape, an explicit control, or the scrim |

A compact surface can still be a modal dialog.
Help is a dialog because it contains a link and controls and temporarily owns focus; it
is not a tooltip or menu.

### A Tooltip Holds Still

**A tooltip is placed relative to the thing it annotates, not to the pointer, and it
does not move while it is up.**

Position is read from the anchor element once, when the tooltip appears.
Pointer movement never repositions a visible tooltip.
Moving onto a different annotated element dismisses the old tooltip and opens a new one
for the new anchor; moving *within* one element changes nothing at all, including when a
delegated listener fires again for a descendant the pointer crossed.

Two reasons, and the second is the important one.
A tooltip that tracks the cursor jitters, because it re-renders on every mousemove while
the reader is trying to read it.
And a tooltip placed where the pointer happened to be says nothing about *which* thing
it describes — in a stacked bar or a treemap, where the annotated elements are adjacent
and small, that is the only question the tooltip exists to answer.

`mb.tooltip.show(html, anchor)` takes the element, and there is deliberately no
`move()`. The controller centers the tooltip under its anchor, flips above when there is
no room below, and clamps to the viewport.
Calling `show` again with the same anchor is how a surface says “still here”: it cancels
a pending hide and leaves the tooltip exactly where it is.

### Shared Overlay Lifecycle

One overlay controller owns body portals, viewport-relative placement, flip and clamp,
stacking, scrims, open-surface arbitration, focus save and restore, and disposal.
Consumers do not recreate those behaviors.
At most one anchored popup and one modal are open; an anchored popup inside the active
modal may coexist with it, and Escape closes the topmost eligible surface first.

The shortcut registry owns the one document-level application keydown listener.
An overlay component registers its Escape action for the component’s lifetime.
Opening activates the command’s scope, closing removes that exact activation, and
component disposal removes the command registration.
The visible Close control, scrim, and Escape binding invoke that same command; its
descriptor supplies the Close control’s accessible action name and any representable
`aria-keyshortcuts` value.
Widget roots may handle their own roving-focus keys, and a modal root may contain Tab,
but neither installs another document-level shortcut dispatcher.

Opening and closing meet these requirements:

- pointer and keyboard triggers reach the same controller and state;
- triggers expose the appropriate accessible name, `aria-expanded`, `aria-controls`, and
  `aria-haspopup` value;
- the interaction that opens a surface cannot dismiss it in the same event sequence;
- scrolling inside a bounded overlay does not dismiss it;
- closing restores focus to the connected trigger or a documented connected fallback;
- modal background content cannot receive pointer, keyboard, or assistive-technology
  interaction while the dialog is open; and
- `dispose()` removes portals, scrims, registrations, observers, and listeners and
  restores any focus, trigger, or inert state it changed.

### Surface Anatomy and Styling

Floating surfaces use the shared raised surface, border, chrome radius, shadow, z-index,
type-scale, focus, and motion tokens.
Use-site classes may choose placement and content layout but do not restate those visual
properties. Reusable dimensions, spacing, or motion require component tokens rather than
repeated literals.

A modal dialog has one labelled surface with a header, title, visible Close control,
scrolling body, and optional action footer.
The body is the only vertical scroll owner inside the surface.
The surface clamps to the viewport, keeps the Close control visible, and remains usable
at 200% zoom and at the narrowest supported navigation-pane width.
Motion respects `prefers-reduced-motion`; content and focus order do not depend on an
animation completing.

Correct semantics are part of the primitive.
A menu renderer supplies menu roles and roving focus; a dialog renderer supplies its
label relationship and modal state; a tooltip renderer never accepts interactive
children. Visually similar surfaces do not borrow the wrong role merely to share CSS.

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

Transient loading chrome has a quiet period through the shared `.mb-delayed-loading`
utility, whose length is `--loading-state-delay` in `styles.css`. The placeholder
reserves its final layout immediately but stays invisible long enough for synchronous
work and fast local requests to replace it before paint.

**Loading chrome does not appear inside the quiet period.** This holds at every grain,
not only for view- and panel-level placeholders: a subtree expanding under the cursor is
exactly the case where the request usually beats the eye, and a spinner that appears and
vanishes reads as a glitch rather than as progress.
A spinner is the strongest form and has no reason to exist before the quiet period ends;
below it, the most that may appear is the neutral pulsing block used by the navigation
tally. Apply the utility rather than adding independent timers at each renderer.

Selection feedback is distinct from loading chrome.
When file or Git navigation can retain useful preview content, the shell immediately
updates the selected navigation row and route while leaving the retained preview
unchanged at full opacity.
The shell still adds `.preview-navigation-pending` and `aria-busy` under the current
claim, but this is an accessibility and instrumentation state, not a visual treatment.
It adds no sheet, filter, cursor, per-element styling, or animation while work is
pending. The state ends at the selected view’s painted-readiness boundary.
A stale claim cannot clear or retain it.

An asynchronously rendered replacement mounts in a connected, transparent, inert stage
while the prior useful surface remains visible.
After the active renderer and its declared readiness settle, the shell transfers the
staged content into the preview in one replacement and transfers disposal ownership with
it. This preserves the connected-container plugin contract without exposing an empty
active container, duplicate interaction surface, or intermediate blank frame.
A newer preview claim immediately disposes and removes a stale stage without touching
the current preview.

An empty initial preview has no useful surface to retain.
It keeps the longer shell wait (`LOADING_INDICATOR_DELAY_MS`) before installing a
neutral spinner, which still uses `.mb-delayed-loading`. Ready content always wins
immediately: do not add a minimum spinner duration, progress bar, or transition that
delays usable content merely to complete an animation.

After a successful atomic replacement, `animatePreviewContentArrival` applies one
compositor opacity animation to the incoming foreground content root, from 0.98 to 1
over 50 ms with `ease-out`. The preview pane’s theme background never animates, so the
handoff cannot pulse white in light mode or flash pale in dark mode.
The old preview never fades out, the new preview is usable immediately, and the shell
does not traverse or restyle the rendered document.
This small incoming-view treatment softens the paint boundary without reading as a
loading effect. `prefers-reduced-motion` skips it entirely.

Navigation implementations measure this acknowledgement separately from content
readiness. The synchronous selection-feedback span contains only the claim-owned busy
state, route, and old/new selected-row mutations; it does not include cancellation,
roving Tab order, network, parsing, syntax work, or rendering.
The standard headed scenario requires that span and pending onset/clearance, while
browser Event Timing remains the authority for the next painted response.

High-churn navigational rows update hover, focus, and selection backgrounds without a
transition so the visible answer does not ease in behind the input.
Motion belongs on the single incoming preview, not on each row crossed while scrolling.

### Progress Spinners Stay Neutral

Loading and progress spinners use the shared neutral-gray track and accent tokens.
They must not borrow link, status, file-type, or chart colors because a spinner conveys
activity, not meaning.
Prefer the shared spinner classes; custom sizes must still use the shared spinner tokens
and keyframe.

### Loading States Are Shapes, Not Sentences

A loading state says “this will be content” by taking the shape of the content.
It does not announce itself in words.
“Loading history…”, “Loading file types…”, and “Loading bytes…” are all the same
sentence, they all say what the surface being replaced already implies, and a column of
them reads as a page in trouble rather than a page working.

Two forms, and the choice between them is about whether the shape is known:

- **Skeleton blocks are the default.** When the layout is known before the data — rows,
  cells, a tally, a list — draw that layout as neutral blocks carrying the slow pulse
  used by the navigation tally (`.tally-pending`, `tally-pending-pulse`). The block
  reserves the real geometry, so arriving content replaces it without reflow, and the
  pulse reads as “loading” rather than “blinking”.
- **A spinner is for an indeterminate wait whose shape is unknown.** A document about to
  render, a comparison whose file count is not yet known — a skeleton there would invent
  a structure the result may not have.
  The spinner says only that work is happening, which is all that is honestly known.

Both forms observe the quiet period above: a state that resolves inside
`--loading-state-delay` shows nothing at all.

Screen-reader text is required and is not a violation of this rule.
A spinner or a skeleton is invisible to a screen reader, so it carries an `sr-only`
label or an `aria-label` naming what is loading.
That text is not visible copy; the rule is about what is painted.

Visible copy is for a state neither form can express — a scan still running behind an
empty result, an index that failed — and it says what that state is rather than that
something is loading.

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
Instructional copy that asks the reader to change interface state must carry the
relevant action in the same component; it must not direct the reader to a control
somewhere else. When an adjacent control already makes the action clear and no
explanation is needed, omit the instructional copy.

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
- Shortcut keycaps have canonical visible and spoken names, and actionable shortcut
  controls expose registry-derived `aria-keyshortcuts` when their physical binding is
  representable accurately.
- Modal dialogs label themselves, keep background content inert, contain focus, and
  restore focus on every close path.
- Print views hide host chrome and retain the rendered document or source content.

## Review Checklist

When adding a component or plugin view:

1. Identify the existing primitive and tokens it can reuse.
2. Test narrow and wide panes, long paths, empty data, malformed data, and large data.
   If the view can show part of its content, check that continuing is reachable from the
   bottom as well as the top.
3. Review all chrome copy and adjacent text across supported states.
4. Check light theme, dark theme, keyboard focus, reduced motion, and print output.
5. Verify lazy mount and disposal behavior.
6. For shortcut or overlay work, verify the shared descriptor, key formatter, overlay
   lifecycle, spoken labels, and contextual availability instead of testing one surface
   in isolation.
7. Run Biome, TypeScript check-JS, and the relevant browser-side tests.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
