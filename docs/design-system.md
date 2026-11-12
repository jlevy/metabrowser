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

Color families use OKLCH because its lightness and chroma steps are more perceptually
uniform than HSL steps.

Plugin styles may consume host tokens.
A plugin-specific visual language belongs in the plugin stylesheet, including any new
domain tokens, rather than in core `styles.css`.

## Color and Theming

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

### Age

One primitive produces every age: `MetabrowserFormatters.age()` returns a label and
freshness class (`.age-live` … `.age-old`), and the shared class rule owns its hue,
weight, small size, and tabular numerals.
Dense navigation uses the compact style (`<1m`, `5m`, `2h`, `3d`, `2w`). Full metadata
and conversation cards use the relative style: `2h ago`, `just now`, or `in 2h` for a
future timestamp. Unknown times have no age label.
The Pulls sidebar, file tree and compact Git history remain condensed navigation; PR
headers, comments, reviews, full commit summaries and folder headers use relative ages.
Call sites choose the presentation style and positioning, never their own suffix,
abbreviation, color, or weight.
A plugin reaches the same primitive as `metabrowser.formatAge` and puts the exact time
in `data-tip-text`. Freshness sentences such as “Fetched 2 min ago via GitHub CLI”
retain their sentence formatter.
When a summary shows created or opened and updated ages, omit the updated age when its
displayed label matches the closed or merged age beside it, or else the created or
opened age, and add the exact updated time to the tooltip of the age it repeats.

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

### Serif Is for Documents

Serif is reserved for a committed document rendered as one, such as a Markdown file or a
README on Overview, and only when the reader’s reading font is serif.
Everything else is sans in either reading font: chrome, and the messages written about
the content, such as a pull request’s description, comments, and reviews, a commit
message, and a notice.
The dividing line is again what the text is.
A document is what the repository holds, and the reading font exists for reading it at
length. A message is conversation about the content, and setting it in the document’s
face makes the two read as one thing.

A message reads at the document’s size in `--prose-sans-font`. PR descriptions,
comments, and reviews share the rendered README’s resolved reading width, including when
the reading font is serif.
See [Reading Width](#reading-width).

The serif face reaches a page only through KPress’s `--kpress-host-font-prose` hook,
which `static/styles.css` points at the reading font.
The pull request page points that hook at `--prose-sans-font` on `.github-pull`. Its
KPress prose and reading column both inherit `--doc-measure`.
`test_serif_is_only_for_documents` holds this.

### Keyboard Keys

Every keyboard key rendered anywhere in the app uses the `.kbd` component: always all
caps, bold, with one thin border.
Never hand-set a key’s type or border at a use site, and never write a key as plain text
inside a sentence.

Write the key in its natural case in markup — the caps treatment is presentational, so
the accessible name stays what the markup says.
For alternative keys, emit one `.kbd` per key, joined by the word “or,” so each keeps
its own border.

The component, its tokens, and its markup contract are documented in the
`── Keyboard keys ──` blocks of `static/styles.css`. The Shift reveal’s badges are
keycaps too: the `.kbd-badge` modifier changes only their paint, as
[Badge Targets and the Shift Reveal](#badge-targets-and-the-shift-reveal) describes.

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
| Digit key | The digit | The digit | The digit |
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
| `Shift`, a single key only | `Shift` | Shift | `Shift` |

`Shift` is a name for the formatter’s single-key entry point, `describeKey()` with
`appendKey()`, which renders a key that is not a binding, such as one named in a
sentence. No binding may use it.

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
Adding a key that is not in this vocabulary requires adding its display, spoken, and
ARIA policy together with formatter tests.

#### Main Tab Shortcuts

The sidebar orders Files, Commits, and Pulls in that order.
Help shows the fixed shortcuts: `1` for Files, `2` for Commits, and `3` for Pulls.
A missing tab keeps its number reserved.
The digits work outside text fields and dialogs, with or without Shift.
A digit opens its tab, or keeps the tab already shown, and moves focus to the panel’s
roving row, so `1` then `↓` walks the file tree; while the panel has no rows yet, the
tab button takes focus.
A missing tab has no target, so its digit does nothing.
Command and Ctrl with a digit stay the browser’s, which switches its own tabs with them.

#### Binding Grammar and Accessibility

- Every shortcut is a single key.
  No binding uses Ctrl, Alt, or Meta, and the registry rejects a binding that states any
  modifier policy, Shift included.
- Shift never changes what a key means: a letter matches in either case, a named key
  such as `↓` or `Home` matches with or without Shift outside a text field, and a digit
  matches the digit typed or, failing that, its key on the digit row, so Shift+`1` is
  `1`. A character that is another binding’s key keeps it: German Shift+`7` types `/`
  and is Quick Search.
- Punctuation matches the character typed, so `?` and `/` stay distinct even where they
  share a key, and `/` works on layouts that type it with Shift.
- Alternative bindings use the word “or”: `T` or `/`.
- Ordered key sequences are not supported and must not be implied by adjacent keycaps.
- Direction pairs use “or,” not a slash or unexplained adjacency: `↑` or `↓`.

The visual and spoken forms are both generated.
An isolated key may use its natural-case `<kbd>` text as its accessible name.
A group of alternatives exposes one visually hidden phrase such as “T or slash” or “Down
arrow or J” and hides its visual punctuation and keycaps from assistive technology,
avoiding duplicate or ambiguous announcements.
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
  views, split and unified diffs, review hunks, logs, raw JSON.
- `--micro-font-size` (10px): deliberately minimized marks — the brand line.
- `--page-title-font-size` (24px): the title of a page no file stands behind, a pull
  request’s. It sits above the 25.5px regular first heading of the text below by its
  bold weight, not by its size.

Document (rendered prose) sizes are a single token:

- `--document-body-font-size` (15px): prose, one size step above the 14px app body.
  Anything a reader reads as prose takes it, a pull request’s description and comments
  as much as a README, so the same text is the same size wherever it appears.

Everything else inside a rendered document — secondary text, table cells, captions,
footnotes, and code at every tier — belongs to KPress’s ramp, which it derives from this
one value through `--kpress-host-font-size-base` on `:root`. Chrome-context monospace is
a separate concern and uses `--mono-block-font-size`. Diff row reservation uses the same
token and line-height as the rendered rows, so deferred mounting reserves the height the
code actually occupies.
Browser zoom scales the whole interface; changing the browser’s root font preference
does not selectively enlarge diff code.

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

`test_font_sizes_come_from_the_type_scale` in `tests/test_design_vocabulary.py` holds
every stylesheet the app ships to this, plugins included.
A literal fails the build unless its exemption list names the selector and why.

### Text Roles

Keep these roles distinct:

- labels and metadata use normal weight and muted text;
- person names use `.actor-name`, and repository names use `.repository-name`: bold
  normal text ink, inheriting the surrounding context’s font size.
  Apply the same person-name primitive to commit authors, PR authors, mergers, comments,
  and reviews;
- branch names use the shared [ref chip](#branch-chips), including its color and
  hover-to-copy control, in navigation, headers, and histories;
- filenames are the identity of a row and carry bold weight at full contrast, while the
  parent path beside them is context and stays regular weight and muted;
- byte counts, durations, timestamps, and numeric table columns use tabular numerals;
- code uses monospaced text without forcing prose into a code style, and paths stay in
  the sans navigation face.

Do not shrink essential text to fit.
Prefer truncation with an accessible full-value tooltip or allow a panel to scroll.

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
The default is 102. Choose 80 for a narrower reading target in the same control.
That adjustable target follows
[WCAG 2.2 SC 1.4.8, Visual Presentation (Level AAA)](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation.html).

Document tokens live on `:root`.

| Token | Meaning |
| --- | --- |
| `--doc-max-chars` | the reader’s setting; the menu writes it, the pre-paint script seeds it |
| `--doc-char-advance` | average glyph advance per em for the current reading face |
| `--sans-char-advance` | the calibrated advance of the clean sans |
| `--doc-measure` | the resolved length: base × chars × advance |

`--doc-measure` converts the character setting to a length once.
The KPress bridge, Overview cards, the commit and PR reading column, and the fallback
`md-body` path use that length.
The reading column adds the card inset and any pane gutter inside its box so the text
can reach the same measure.
Markdown rebuilt from an untrusted source goes through
`MetabrowserInertHtml.kpressProse`, which sets it in KPress’s prose element with the
classes the allowlist removed, so it reaches the same rules.
`test_every_prose_surface_reads_the_measure` holds these.

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
conversion. Size and character-count changes are CSS inputs.

Verify a width change by measuring the *text* box with padding excluded, in both the
single-column and wide bands, and against the same file opened on its own.
A card can be the right width while the text inside it is an inset-pair too narrow.

### Rendered Markdown Layout

Document and Source keep the same outer pane gutter, `--content-padding-x`. Card borders
and source surfaces start at the first tab’s outer edge.
KPress keeps its normal padding inside the card: 4 rem in the single-column band and 2.5
rem in the wide band, with its compact prose gutter on narrow panes.
Source and Raw keep their code-block padding and line-number columns inside the shared
outer gutter. KPress’s card and `--doc-measure` cap the reading column.
At a preview width of 75 rem or more, a document with a table of contents puts the
sticky KPress rail to the right, with a 3 rem gap.
A thumbnail sits above the prose.
A wide table scrolls inside the column beside a rail.
In a single column it can use available space to the right of the text.

Below 75 rem, KPress’s icon opens the existing overlay from the trailing gutter to keep
the beginning of each line clear.
The Folder Overview README shares the same prose edge and maximum measure.
Its panel headings and bodies follow the document card’s outer edge, with text at the
README’s responsive inner inset.
It uses the surrounding folder navigation for context.

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

## Control Families

Every button belongs to one role-specific primitive:

| Role | Primitive |
| --- | --- |
| Labelled action | `.btn` |
| Icon-only action | `.icon-btn` |
| Filter value or filter menu | `.chip` and its variants |
| Exclusive choice among labelled values | `.chip-group[data-select="one"]` |
| Menu row or segmented menu choice | `.menu-item` or `.menu-seg` |
| Tab | `.tab-btn` |
| Collapsible section title | `.section-disclosure-trigger` |
| Action among links: a text action, below | The context’s text-action class, on `<a>` and `<button>` alike |

These primitives share the type scale, radii, semantic colors, focus treatment, and
motion tokens, while their shapes communicate different interaction roles.
A use-site class may add positioning, visibility, or domain state, but it must carry the
primitive class in the markup and must not recreate the primitive’s border, fill,
typography, or focus rules.
Every non-submit button declares `type="button"`, and every icon-only button has an
accessible action name.

A **text action** is an action that sits among links in a line of chrome, with no border
or fill, because a bordered button would read as a different thing from the link beside
it. It is a link when the page already has the address, and a real `<button>` when
following it first switches the served pin, so that a new tab or a copied address never
opens something a click would not.
Both forms look the same in their context, a tooltip and accessible name say which
commit opens and whether the pin switches, and keyboard and screen-reader users still
get the element they expect.
The diff file bar’s [View file](#diff-file-bar), and
[Browse code and a review comment’s file](#chrome) on a pull request’s page, are text
actions. Each context sets one look for the `<a>` and the `<button>`, box included: a
`<button>` is always an atomic inline box, so where a label can wrap, the `<a>` is one
too, and what follows a wrapped label starts on the next line in both forms.

### External GitHub Links

External GitHub destinations share a small inline icon beside the link label.
General GitHub, CLI, documentation, gist and API links use the GitHub mark.
Canonical issue and pull-request addresses use a neutral entity icon when their state is
unknown. Matching PR metadata supplies the existing open, closed, draft or merged icon;
the address alone never establishes a state.
The explicit **View on GitHub** action uses the GitHub brand mark before its text,
including when its destination is a PR. Other PR references retain their entity/state
icon. Icons preserve text, wrapping, focus and safe external-navigation attributes.

Use the shared `decorateExternalLink` view helper after source-link localization and
sanitization. A link localized to a served file stays internal.
The decorator adds no metadata request, remote image or SVG fetch, observer, or
document-wide scan. It uses the existing on-demand SDK view bundle and app-owned icon
markup; document sanitization keeps its allowlist.
Rendered Markdown retains its existing enhancement budget; links beyond the admitted
prefix keep their authored form.

### Choosing Among Values

A control that offers two or more values, or one value on or off, is one of these.
They differ in shape because they offer different things, and they agree on what each
state looks like.

| Offers | Primitive | ARIA and keyboard | Used by |
| --- | --- | --- | --- |
| One of a few labelled values | `.chip-group[data-select="one"][data-layout="joined"]` | `radiogroup` of `radio` with `aria-checked`; one tab stop, arrow keys select | Split / Unified, Files / Bytes, Branches / Tags |
| Any of a set of labelled values | `.chip-group[data-select="many"]` | `group` of buttons with `aria-pressed`; each a tab stop | An agent log’s event types |
| One of a few values in a menu, where the glyph is the label | `.menu-chooser` of `.menu-seg` | `group` of `menuitemradio` with `aria-checked`; each a tab stop | Theme and reading font |
| One of a long list, named by its trigger | `.chip-menu-trigger` over a `.menu` | `aria-haspopup`, `aria-expanded`; the panel’s pattern within | Filter dropdowns, the source ref selector |
| A boolean whose polarity has to be legible | `.filter-check` | A real checkbox | Show ignored |
| A boolean with no room for a word | `.icon-btn[aria-pressed]` | A button with an accessible action name | The filter drawer |

The chip group and the menu segment are two forms of one exclusive choice, because a
word and a glyph need different boxes.
A chip sizes to its word at `--chip-height` and sits in a row of chrome.
A segment holds one glyph, carries the weight of a word, and shares a menu’s whole width
at a target large enough to hit in a popup.

| State | Text and fill | Also |
| --- | --- | --- |
| Rest | `--muted`, no fill |  |
| Hover | `--text` on `--hover-bg` |  |
| Selected | `--link` on `--highlight-bg` | A chip’s word takes `--weight-medium` |
| Keyboard focus | Unchanged | A 2px `--link` ring, inset 2px |

Build a chip group with `metabrowser.filterControls.groupHtml` and `bind`, including
outside a filter bar: an exclusive choice is the same control whatever it chooses.
A consumer may repaint the group from its state on every change, and `bind` puts focus
back on the chosen chip, so the arrow keys keep working.
Show a Rendered | Source chooser only for a file with both formats available.
A file that falls back permanently to Source has no format chooser.

`test_a_toggle_cannot_fork_the_family` fails when a stylesheet or a source states a
toggle’s ARIA outside this family, and
`test_exclusive_choices_share_one_answer_to_each_state` holds the table above.

## Rows and Disclosures

A row is one activation target at one height, and a disclosure says what it holds and
travels the same way wherever it is.

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

This pattern does not replace the navigation-tree disclosure.
The tree keeps its leading chevron because that mark communicates hierarchy and shares
one activation target with folder navigation.

### One Chevron, One Row Contract

Every disclosure chevron in the product is the same Lucide mark: the registry’s leading
glyph on row-like targets (tree folders, tally tree, diff file bars) and the
section-disclosure mask after heading-like titles, both in `--muted`, pointing right
when closed and rotating to point down when open.
Row-like activation targets share `--ui-row-height` and `--hover-bg`. These agreements
are enforced by `tests/test_design_vocabulary.py`, which fails when a surface forks the
glyph, the row height, or the hover token.

### Row Text Shares a Baseline

A row that sets text at two sizes on one line aligns that text on its baseline and
centers only its boxes.
Centering line boxes of two sizes leaves their baselines a fraction of a pixel apart,
because ascent grows with font size.
That fraction rounds differently at each zoom and pixel ratio, so the row looks
unsettled rather than consistently offset.

| Row | Text on the shared baseline | Boxes that stay centered |
| --- | --- | --- |
| File tree row, in Files and Recent | Name, age, size, and a container child’s change letter | Icon, chevron, activity spinner, loading skeletons |
| Git history row | Subject, author, and age | Graph gutter, ref chips |
| File and folder header | Path, file size, and folder summary | Parent button, badges, copy and print buttons, a summary still loading |
| Pull request row, in [the Pulls tab](#the-pulls-tab) | Title and age | State icon |
| Diff file bar | Change letter, path, change stats, and notes | Chevron, Markdown **Rendered** \| **Source** chooser, View file controls, copy button |

The row keeps `align-items: center`, and each text child opts in with
`align-self: baseline`. A box aligned to the baseline would sit its bottom edge on the
baseline, so no opt-in selector may match one.
Where a text slot can hold a box instead — a loading skeleton, or an age the activity
spinner replaces — the opt-in selector excludes it with `:not()` rather than a later
rule overriding it, so neither rule order nor specificity decides where a box sits.

Baseline alignment places the text group at the top of the row’s content box, so the
group reads as centered only while that box is no taller than the group.
A tree row’s `--ui-row-height` is the name’s line box plus the row’s 2px pads, so change
the row height and the name’s line height together.
The header’s path fills the header’s content box and centers its own crumbs, so the
header’s text stays where centering put it at any header height.

The diff file bar’s View file controls are boxes beside the toggle, not text inside it,
so they are set at the path’s own size: text of one size centers onto one baseline.
At `--ui-small-font-size` a link sat 0.75px above the path’s baseline and a button
0.5px, measured in Chromium at a device pixel ratio of 2.

A mirror’s location note at the far end of the file header is deliberately not in the
table.
It is whole or absent, by wrapping inside a box of its own one line tall, so it is
centered rather than baseline-aligned, and sits 0.25px above the path at a device pixel
ratio of 1, with the rest of the row between them.

The Git commit summary’s metadata line also sets two sizes and is deliberately not in
the table.
Its revision is monospace at `--nav-font-size` beside body-size sans text, and
aligning the two faces on one baseline grows that line by 1.25px at a device pixel ratio
of 2, so it stays centered.

`test_row_text_shares_one_baseline` in `tests/test_design_vocabulary.py` checks this
table against the stylesheets: every text slot opts in, and no rule that aligns to the
baseline matches a box, including a text slot in its box state.

### Fold Expanders

A run of content withheld until asked for — a long stretch of changed lines in a diff —
sits behind a full-width control at `--ui-row-height` carrying the same registry
chevron, in `--highlight-bg`, hovering with `--hover-bg`. The label states the count it
holds (`86 more changed lines`) and becomes the inverse when open (`Hide 86 lines`),
because a control that hides its size is a control the reader cannot judge.
A fold inside another disclosure stops its click, so expanding a fold never collapses
its container. It is one primitive, `.fold-expander` in `static/styles.css`, on a button
or a native `summary`. `test_section_headings_and_fold_expanders_are_primitives` holds
it.

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
A native `details` keeps its state in `open` and takes the same recipe on
`::details-content`, as a pull request hunk’s earlier lines do.
`tests/test_design_vocabulary.py` pins the recipe on every site.

## Notices and Partial Content

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

## Git History

The history panel has its own vocabulary because it shows a structure nothing else in
the product shows — a graph of commits — but it borrows every general element it can:
ages come from [Age](#age), change counts from
[Inline Change Stats](#inline-change-stats), and rows follow the shared
[row height and hover](#one-chevron-one-row-contract).

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
The subject and the smaller author and age share a baseline; see
[Row Text Shares a Baseline](#row-text-shares-a-baseline).

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

The full subject uses `.page-heading` at `--page-title-font-size`, the PR title’s scale.
Its summary starts at the pane’s content edge and uses `.page-reading-column` for the
maximum reading width.
The compact subject, ref badges, author, age, file-status counts, units, and line counts
use `--body-font-size`. The revision is the one deliberate exception: it is monospace,
and mono at body size renders optically larger than the sans text beside it, so it uses
`--nav-font-size` — one step down the ramp — to sit level with its row.
The compact tooltip is bounded by width and subject line count, not made denser with
smaller type. The optional full-summary description uses the same sans prose as a PR
description: `--prose-sans-font`, `--document-body-font-size`, and
`--kpress-line-height-normal`. It preserves authored newlines and wraps long text.
Commit descriptions and PR discussion cards share `.page-card`: the normal page
background, text ink, border, and chrome radius.
Each content type owns its inner padding; code blocks and diffs keep their source
typography and spacing.

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
Arrow, K, J, Enter, and Space selection dismisses any pending or visible pointer-owned
tooltip before navigation.

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
In dense Git history they use `--micro-font-size`; full commit summaries, PR headers and
list metadata use `--ui-small-font-size`, smaller than the actor beside them.
All share the same chip form and semantic ref colors.
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

Copyable branch chips reserve a tiny copy control beside the label, revealed on hover or
keyboard focus. The control copies the complete underlying branch or ref, regardless of
label truncation or a displayed fork owner, and reports the normal copy feedback.
Its click does not select a different row or follow its link.
An outside pointer interaction hides active copy controls and restores the primary row’s
focus before a pane drag can clip its focused button.
Place copy controls beside a primary link or button rather than nesting interactive
controls. Keep local, remote, tag, trunk and HEAD semantics when rendering a chip.

### File Change Status

File-summary letters share one muted semantic palette across Git history, commit
summaries, diff headers and PR changed-file trees.
The letter and accessible status name carry the meaning even without color.

| Change | Letter | Color |
| --- | --- | --- |
| Added or copied | A, C | Green |
| Deleted | D | Red |
| Modified or type changed | M, T | Dark yellow / ochre |
| Renamed | R | Blue |
| Unmerged | U | Red |
| Unchanged, untracked or unknown | Status label or ? | Neutral |

These are application conventions, consistent with the
[Primer semantic color roles](https://primer.style/product/getting-started/foundations/color-usage/),
not a universal Git color standard.
Theme tokens keep letters legible on normal, hovered and selected surfaces.
They do not change addition/deletion counts or patch-line backgrounds.

## Diffs

Diff surfaces serve a commit, a comparison, and a pull request’s Changes tab, and they
share these rules wherever they appear.

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

### Diff File Bar

The diff view’s per-file bar is **a row, not a heading disclosure**: it leads with the
same registry chevron the tree uses (`.toggle-chevron`, rotated by the shared
`expanded`/`collapsed` classes), sits at the shared `--ui-row-height`, hovers with
`--hover-bg`, and reveals its `[data-mb-copy]` copy control on row hover or focus — the
file-header copy affordance, present wherever a filename is.
Its content is left-aligned reading order — chevron, kind letter, filename in the
shell’s file-path typography, then the stat pair beside the name — and the whole bar is
one activation surface, the folder-row rule applied to a section header: clicking
anywhere toggles, with only the copy control, the View file controls, and a Markdown
file’s **Rendered** | **Source** chooser opting out.
On a pull request’s Changes, a changed Markdown file’s bar carries that chooser, a
joined chip pair, after the chevron, and beside it a small spinner that keeps its place
in the bar and appears only after the loading-state delay while the rendered view is on
its way. A file that falls back permanently to Source loses the chooser and the spinner,
and its bar lays out as any other file’s, with a long path truncated on one line.
On a page that shows a pinned revision, and on a pull request’s Changes beside a
checkout, the bar ends with quiet text actions that open the file at a side of the
change: **View file**, and **View at parent** or **View at base** where the old side
exists. They stay visible rather than revealing on hover, because they are how a reader
leaves the diff for the file.
They are [text actions](#control-families), so each is a link or a button by whether it
first switches the served pin, and looks the same either way.
A pull request’s are always links: a side the page does not show opens on its revision
page and never switches the pin.
A collapsed section keeps the section’s own border as its single line.

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
A diff too narrow for Split draws Unified, and the control shows what is drawn, with a
tip on **Split** saying why; the stored choice is not touched, so Split returns when
there is room, and choosing **Split** there draws it with a sideways scroll.

## The Pull Request Page

The page at `/pull/<n>` shows one cached pull request.
It has almost no vocabulary of its own: it places the shell’s primitives, and a text of
the pull request reads as the same Markdown does in a file.
`test_the_pull_request_page_carries_the_shells_primitives` holds what follows, with the
tests named beside each primitive.

### Layout

The page is a header, optional native stack navigation, a [tab bar](#the-tab-bar), and a
body, in that order.
The header, tabs, Conversation, and Checks use `.page-reading-column` and start at the
same pane gutter as the commit summary.
The first tab aligns with the content in narrow and wide panes.
The column includes the card’s insets so its text can reach the same measure as the
rendered README. Both headers use `.page-heading`. The title begins with the Pulls state
icon at the title’s font size.
The text wraps under its first line while the icon stays beside the first line.
The colored badge below the title gives the state in text and the title icon is
decorative. The Changes body keeps the full pane so a diff has room for Split.
A cold page uses the same gray pulsing row skeleton as other known text layouts, in the
reading column even when Changes is selected.
Its reveal wrapper and skeleton are separate nodes, so the shared loading delay does not
replace the pulse or reduced-motion rule.
A cached page stays readable and still during refresh: nothing spins over it, and only
its age line breathes ([Refreshing Content](#refreshing-content)). Its freshness copy
names GitHub CLI and the plain fetch age, with no prefix while a refresh runs and no
suffix while the record is stale, since a stale page is refreshing.
It names a problem only when no refresh can run: `Offline`,
`GitHub rate limit · next check at` a time, or the last failure with Refresh.
The Checks tab uses the same heading and status badges for check runs and status
contexts. A check row is its status badge, its plain name, its action, and its
description. The action says where it opens: **View action on GitHub** for a GitHub
Actions run, **View on GitHub** for another page on a GitHub host, and **View details**
for the check’s own site, and its accessible name adds the check’s name.
A check whose address is not http(s) has no action.
A run’s app is its description, except GitHub Actions beside an Actions link, which
already says so.
A section a description preview does not have yet, Discussion or Checks,
shows the cold page’s gray pulsing blocks after the quiet period while its record is
fetched, never a spinner or a sentence; Changes with nothing cached shows the delayed
shared spinner, because its shape is unknown.
Idle and failed sections use static notices.

Native stack navigation uses the repository snapshot’s verified membership and order.
A Layers icon and position/total, such as 5/23, open a menu in the reading column.
The menu shows titles, ordinals, and PR numbers, ordered from stack top to base, with
the current member marked.
Its links are created only when opened.
Arrow keys, Home, End, Escape, outside click, and focus return follow the menu pattern.
On a selected PR, `N` opens the next member toward the stack top and `P` the previous
one toward its base, with or without Shift; Help lists them in its Pull request stack
group. A focused Pulls row keeps `J` and `K` for its own rows.
Editors, dialogs, unknown membership, and inactive pages keep their normal keyboard
behavior. Stack endpoints consume the shortcut without moving.
A member selection preserves the current PR tab and clears the previous file selection.
Unknown membership and unavailable optional tooling add no placeholder or setup notice;
known cached membership remains visible during refresh or failure.

### Text

A description, comment, or review body is prose, and it reads at the document’s size
rather than chrome’s, in sans whatever the reading font, because it is a message and not
a committed document ([Serif Is for Documents](#serif-is-for-documents)). The page sets
it in `article.kpress.kpress-inert > .kpress-prose` under `.metabrowser-kpress-host`,
the path a mirrored Markdown file takes, so KPress’s own rules apply: the prose size,
the heading ramp, the graded code sizes in a paragraph, a list, a table, and a heading,
and the reader’s “Max text width”.
Nothing restates a ratio.
The one rule the page adds removes the first and last block’s outer margin, because the
card’s padding is the space around a text.

The fallback `md-body` path is not used, because it is a different ramp: one flat code
size and its own heading steps, which would make the same text read differently from a
file.

A text stays inert. The server and `static/inert-html.js` reduce it to the allowlist, no
KPress script loads, and every class in the article is the page’s, chosen by element.
The route’s answer names KPress’s stylesheets, and that list is the same for every text,
so a comment does not choose what the page loads.
Until its render arrives a text shows as plain text in the same face and size.

### Chrome

| Element | Primitive | Why |
| --- | --- | --- |
| Title | `--page-title-font-size`, `--weight-bold` in normal text ink, sans | A pull request’s title is bold in normal text ink wherever it appears ([The Pulls Tab](#the-pulls-tab)). The number beside it uses normal text ink and regular weight at the same size |
| State, review, and check badge | `.file-header-badge`, in the state’s status ink | A pill means a filter, and a badge is not one. Sentence case, like all chrome |
| Username | `.actor-name`, bold in normal text ink at the surface’s normal text size | Applies to the author, merger, comments, and reviews; a small circular avatar belongs to that same actor |
| Base and head branch | `.git-ref.git-ref-remote`, at `--ui-small-font-size` | The [ref chip](#branch-chips), smaller than the actor and action; the list uses the same remote-ref ink |
| Label | Hairline box with `--radius-tag` | A name the pull request carries, the corner tag-like chips use |
| Opened, updated, commented | `metabrowser.formatAge` with relative style, exact time in the tooltip | [Age](#age); condensed navigation uses compact style |
| File of a review comment | Sans, bold, `--nav-font-size` | The diff bar’s path typography. A path is chrome |
| Link, including a check’s action off GitHub | `--link`, underline on hover, the focus ring | As the freshness row’s link is, so a check’s action never reads as the muted description after it |
| GitHub action: View on GitHub, a check’s action on GitHub, a conversation commit hash | `.github-pull-external-action`: `--muted`, with the leading GitHub mark in the same ink; `--link` on hover and focus | Quiet beside the metadata it follows, and the same in each of the three. A check is GitHub’s by the rule that gives a link the GitHub mark, so its look and its mark agree |
| Conversation commit hash | `.git-commit-sha` at `--ui-small-font-size`, its row’s size | A [revision](#git-commit-summary) sits one step below the sans beside it, but below this 12px row the ramp’s next step is `--micro-font-size`, 10px |
| Browse code, and a review comment’s file | [Text action](#control-families): a link, or `.github-pull-text-action` on a button where it first serves the pull request’s head | The look of the Link row in both forms, so moving the pin never looks like something else |
| Section title | [`.section-heading`](#section-headings) |  |
| Note about the content | [`.notice`](#notices) | `warning` when a text, list, or hunk was cut or a part could not be read; `error` when Changes cannot be drawn; no severity for the offer of newer changes, which carries its own control |
| A review comment’s earlier lines | [`.fold-expander`](#fold-expanders) on a native `summary` | States its count, and the inverse when open |
| A review comment’s hunk | `--font-mono` at `--mono-block-font-size` | The user’s code, with the diff view’s row tints |
| Empty state | `--muted`, sentence with a period |  |
| Refresh, Fetch, Switch to the head | `.btn` |  |

Author, action, and relative age share one metadata size and baseline in a header or
discussion card. The bold username uses the normal text ink wherever it names an actor.
The avatar centers independently beside that text baseline.
Compact navigation ages and branch chips retain their smaller chrome sizes.

Author avatars are decorative circles beside the visible username, with fixed dimensions
so image arrival or failure does not move the text.
Images load lazily, asynchronously, and at low priority; only mounted catalog rows can
create images. Missing or unsupported image URLs leave the username readable.
Use the avatar of the named actor: a merged header naming the merger shows the merger’s
image, while the description shows its author’s image.
Only normalized HTTPS URLs on `avatars.githubusercontent.com` are accepted, checked
again before assigning the browser image source.
Anonymous CORS and a no-referrer policy omit credentials and the local page URL. The
browser’s HTTP cache owns image bytes; PR metadata caches retain only URLs.
Document image sanitization remains independent; see [Content Trust](../SECURITY.md).

## The Pulls Tab

The list beside Files and Commits, on a GitHub repository, shows every pull request
newest first. Like the page it opens, it has almost no vocabulary of its own.
`test_the_pulls_tab_carries_the_shells_primitives` holds what follows.

A pull request’s row is a container: its chevron opens a changed-files tree under the
row, connected by `aria-owns`. Clicking the row opens the page and toggles the tree;
Right expands or enters it, and Left collapses it.
Selecting a PR, including with Up, Down, J, or K, does not expand its tree.
An address naming a changed file opens its owner’s tree if needed.
Moving to another PR closes a tree opened only for that address; trees the reader opened
stay open.

A pull request’s title is always bold in normal text ink, wherever it appears: the
page’s heading, a Pulls row, the page’s stack menu, and a search result.
A row or menu item is a link, so the title sets its own ink and weight, and no visited,
hover, focus, selected, or current state changes them.
The PR number beside a title keeps its regular weight.
The metadata line gives the PR number normal row size and text ink.
Usernames and the repository summary use the same small metadata size and bold normal
text ink. Branch names use the small shared remote-ref chip.
Known native stack membership uses a small Layers icon and bold position on that line;
the tooltip names the stack.
Their shared repository snapshot is indexed once by PR number; rows make no stack
requests, and enrichment updates retain the row and any focused changed-file tree.

Changed files use the Files tree’s row height, indent, chevron, and inline change stats.
A one-letter change badge replaces the file icon.
A folder chain is one row.
Up, Down, J, and K move through the visible rows, with one Tab anchor per file tree.
A file step calls the diff’s public jump API; a held key replaces the address once it
stops, while Enter and a click push it.
A hand-scrolled diff reports its current file through the same public page handle, so
the tree follows without moving the address.
Only the active PR’s file carries the page-selection mark.
Leaving a PR clears that mark while preserving its reader-expanded tree and roving
keyboard anchor. Repeated notices for the same page retain the observed diff file;
explicit file addresses remain selected while their jump is temporarily unavailable.

The tree draws a viewport window, keeping its focused anchor mounted.
Counts name the files fetched and say when the list is partial or capped; the rows do
not depend on hydrated diff documents.
The measured expansion and overscan choices are beside `AUTO_EXPAND_FILES` and
`FILE_ROWS_OVERSCAN` in the GitHub plugin.

### A Pull Request’s State

Four states, each with the shape GitHub gives it and a color token in GitHub’s hue:

| State | Glyph | Token | Hue |
| --- | --- | --- | --- |
| Open | Lucide `git-pull-request` | `--github-pull-open` | Green |
| Draft | Lucide `git-pull-request-draft` | `--github-pull-draft` | Gray |
| Merged | Lucide `git-merge` | `--github-pull-merged` | Purple |
| Closed | Lucide `git-pull-request-closed` | `--github-pull-closed` | Red |

The tokens are the plugin’s, in its stylesheet, as a domain’s tokens are, and each is
one color seen against two backgrounds: the hue is GitHub’s and the same in both themes.
The shapes differ. In the list, the icon’s accessible name and tooltip give the state.
On the page, the same glyph sits beside the title and the text badge below names the
state. Everything goes through `pullStateIcon` and `displayState` in
`builtin_plugins/github/pull-state.js`, so a row and its page cannot disagree.
`test_pull_state_colors_keep_their_hue_and_read_on_both_grounds` holds the hue and a
4.5:1 contrast on both grounds, because a badge sets its word in that color.

### Rows

| Part | Primitive | Why |
| --- | --- | --- |
| Tab | `.tab-btn` in the nav’s `.tab-bar` | [The Tab Bar](#the-tab-bar) |
| Row | `min-height: --ui-row-height`, `--hover-bg`, `--highlight-bg` and `--highlight-bar` when current | [One Row Contract](#one-chevron-one-row-contract) |
| State icon | The 16px alignment box around `--icon-glyph` | [One Glyph Size](#one-glyph-size) |
| Title | `--nav-font-size`, `--weight-bold` in `--text`, set on the title itself; cut with an ellipsis, the whole of it in the tooltip | It is the row’s identity, and a pull request’s title is bold wherever it appears |
| Updated time | `metabrowser.formatAge`, exact time in the tooltip | [Age](#age) |
| PR number | `--nav-font-size`, text ink | Shares the title’s primary navigation size |
| Username and repository summary | `--ui-small-font-size`; username uses `.actor-name` | Secondary context stays the same size; usernames remain bold in normal text ink |
| Stack position | Layers icon and bold position/total beside the PR number | A passive list badge uses the shared optional snapshot and identifies its stack in the tooltip |
| Base and head | `--ui-small-font-size`, remote-ref ink | Compact contextual chips below the title’s primary size |
| Open, Closed, All | `metabrowser.filterControls.groupHtml`, joined and exclusive, sticky at the list’s top; Open is the default | Small, muted tallies show each filter’s exact catalog total. Zero is visible and unknown is distinct. See [Choosing Among Values](#choosing-among-values). |
| Count | Bold numeric total and repository name in “N PRs on owner/repo,” or just the bold repository name while the count is unknown. A partial display adds “Showing last N.” | Counts describe the repository and the displayed window. |
| Reload | Flush right beside Open, Closed, All, in the same sticky row | The update age stays below the repository summary. |
| Connection | One live status row: the shared small gray spinner and “Fetching pull requests…” only while no rows are shown; otherwise the quiet update age, which breathes while a refresh runs, and actionable copy during failures | Cached rows stay visible and still. See [Refreshing Content](#refreshing-content). |
| Fetch more, Reload | `.btn` | Fetch more extends the display window. Reload checks GitHub for updates. See [Control Families](#control-families). |

A row is two lines and one target, because a pane is narrower than its parts: the state
icon and the title with the age beside it, sharing a baseline, then the metadata line
under them. It is one link, so a new tab and a copied address are the browser’s own, and
all of its text is text: GitHub’s users write it, and none of it reaches markup or a
style.

New pull requests use the [shared arrival highlight](#live-row-arrivals).

### Keys

The rows are a [Navigational Row Collection](#navigational-row-collections), with this
one difference from what the file tree does.
Moving is immediate and opening waits for a key to stop, because a pull request’s page
can cost a fetch where a file cannot: each move changes two rows, a press opens at once,
and a key held down opens only the row it stops on.
History follows the rule all three collections share: a key’s open replaces the entry,
as the file tree’s arrow keys and Git’s K and J do.
Clicking a different row or pressing Enter on it pushes a history entry.
Space toggles the focused pull request’s changed files in place.
`J` and `K` move the rows with or without Shift; walking a pull request’s stack is `N`
and `P` ([The Pull Request Page](#the-pull-request-page)). Help reads the
`pull-requests` and `pull-stack` groups of the shortcut registry, and no surface here
names a key.

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
Document-level commands ignore editable controls, composition, and previously handled
events. They never match while Ctrl, Alt, or Meta is held, and inside a text field Shift
with an arrow, `Home`, or `End` belongs to the field, where it extends the selection.
They prevent browser behavior only after an enabled handler reports that it acted.

A command may opt back into an editable target only for a key that field does not
already own. A combobox may claim the arrow keys, `Enter`, and `Escape`, because none of
them edit text. It may not claim `Home` or `End`: those move the caret, and taking them
leaves the user unable to reach the start or end of what they typed.
For the same reason, Shift with a selection key stays the field’s even for a command
that opted in: Shift+`↑` and Shift+`↓` extend the selection in Quick Search’s query,
while plain `↑` and `↓` move through results and `Enter` and `Esc` act with or without
Shift. When a list needs first-item and last-item reach behind an editable control, its
movement commands wrap instead of borrowing the caret keys.

### Badge Targets and the Shift Reveal

A command whose key acts on a control on screen attaches that control as its target with
the registry’s `attachTarget()`, which returns `retarget()` for a rebuilt control and an
idempotent `detach()`. While attached, the control carries the command’s
`aria-keyshortcuts`, so the key is announced at rest.
A command marked `targeted` is live only while one of its targets is: connected, not
`disabled`, outside any `inert` subtree, and visible by `checkVisibility()` or, without
it, by computed style.
The registry reads that at dispatch, so a key whose control is hidden, staged, or behind
a modal leaves the event to the browser.
The first live target in document order runs the command, as `context.target`, and
carries its badge. A component that rebuilds its markup calls `retarget()` after each
rebuild.

Every key runs a named activation path, the one its control’s click runs, plus the focus
a keyboard user needs next; no command synthesizes a click.
A main tab’s digit opens the tab and then focuses the panel’s roving row; a view tab’s
letter selects the tab and leaves focus where it was; a filter’s letter opens its menu
and focuses the checked row; `W` opens the branch list and focuses its filter; `U` opens
the parent folder; and `Y` copies the main-pane header’s path or revision.
View tab letters are commands in a permanent `view-tabs` scope below `global`, one per
letter, held for the bar the main pane commits and never for one still staged, so the
stack’s `P` outranks a Preview tab’s `P` only while a pull request in a stack is open.

Holding Shift alone outside a text field for the hold threshold reveals the keys: the
root gains `data-key-reveal`, each live command’s first live target carries one
`.kbd.kbd-badge` keycap, hidden from assistive technology, and the shortcut strip shows
a second layer listing the `reveal` surface’s live commands, with every binding of an
item that combines several, such as `N` or `P`. A key the registry handles keeps the
reveal and moves the badges to what is live after it; any other key, a modifier, a
pointer press, a wheel, the window losing focus, a hidden page, focus entering a text
field, or a lost `keyup` ends it.
Another key within the threshold, or pointer travel past the slop, keeps the reveal from
starting, so `?`, capitals, Shift+wheel, and Shift+click keep their meaning without a
flash. The reveal never calls `preventDefault()` and never announces itself; badges and
the revealed strip exist only while it shows.
`static/key-reveal.js` is the state machine, and `static/shell-keymap.js` holds the
shell’s targeted commands.

The reveal is drawn in the live-row yellow, `--row-flash-bg`, which `--key-reveal-bg`
names for it:

- **A badge is a keycap.** It is a `.kbd` with the `.kbd-badge` modifier, which keeps
  the keycap’s type, caps, padding, and radius and changes only its paint: the yellow at
  60% opacity (`--kbd-badge-bg`), a deeper border of the same hue
  (`--kbd-badge-border`), the body text (`--kbd-badge-color`), and the small elevation.
  It is absolutely positioned and ignores the pointer, so it moves no box and a click
  reaches the target beneath it.
  No call site styles a badge.
- **Placement.** An `inline-end` badge sits inside its target over the inline-end
  padding, centered top to bottom: the default, for tabs, chips, and text buttons.
  A keycap is wider than a tab’s padding, so it covers the label’s last letter, which
  reads through the translucent fill.
  A `beside` badge also sits over its target’s own inline end, but is positioned within
  the nearest `[data-kbd-badge-anchor]`: the file header, the folder header, or the
  commit view’s heading.
  It serves icon buttons and targets in a row that clips, such as the Copy path button
  and the breadcrumbs, where a badge inside the target would be cut off.
  It covers the icon or the crumb’s last letter, never the file name, note, size, path,
  or author that follows.
  A crumb narrower than a keycap, such as the root’s `/`, lets the keycap reach back
  over the text before it: at the root, the end of the dimmed root name, the folder Up
  opens. The target and the anchor become containing blocks through zero-specificity
  rules, so one that already declares a position keeps it.
- **Hover-revealed targets show.** A target that otherwise appears only on hover or
  focus, such as either copy button, appears for the reveal, with its pointer events, as
  [Reveal on Hover Keeps Keyboard Reach](#reveal-on-hover-keeps-keyboard-reach) requires
  of every reveal trigger.
- **The revealed strip** is the same yellow, with `--text` and keycaps in a badge’s
  paint. Its layer sits against the strip’s bottom edge and grows upward over the panel,
  which neither reflows nor scrolls; the panel’s pinned headers and open menus stay
  above it.
- **Contrast.** Everything the reveal paints keeps 4.5:1 in both themes: a badge as
  composited over each surface a target sits on, and the strip’s labels and keycaps on
  the yellow, where `--muted` would not.
  The ratios are recorded beside the tokens in `static/styles.css`, and
  `tests/test_design_vocabulary.py` recomputes them.
- **Motion and print.** Badges and the strip fade in over `--transition-fast`, appear at
  once under `prefers-reduced-motion: reduce`, and go at once when the reveal ends.
  Neither prints.

### Navigational Row Collections

A row collection whose primary action replaces the main content behaves as one keyboard
control. Exactly one mounted row participates in the Tab order: the current row when one
exists, otherwise the first row.
All other rows remain programmatically focusable with `tabindex="-1"`, so Tab enters and
leaves the collection once instead of stopping on every item.

While a row has focus, Arrow Up and Arrow Down without Ctrl, Alt, or Meta move to the
adjacent mounted row and open it; Shift changes nothing, so Shift+Arrow moves one row.
K and J are aliases for Arrow Up and Arrow Down with the same guards, in either case and
with or without Shift; they never act from a text field and get no first-row or last-row
meaning. In the file tree, the first-row and last-row keys are Home and End alone.
Key repeat remains enabled for fast traversal.
Movement clamps at the first and last row, prevents page scrolling, and does not reopen
the row at a clamped edge.
Activation updates the roving anchor without stealing focus.
Enter, Space, and pointer activation retain the control’s ordinary behavior.
A key’s move replaces the history entry in all three collections, so a skim through the
file tree, Git history, or the Pulls tab leaves its rows with one Back however many rows
it passed. The collections differ in the rest:

- **A pointer click** pushes an entry in the file tree, and in the Pulls tab for a row
  that is not the one open.
  In Commits it replaces the entry, as every selection there does that does not come
  from the address: a commit is a selection that holds the address while it is shown
  (`static/git-panel.js`, `selectCommit`).
- **Enter** in the Pulls tab opens the focused pull request and pushes an entry if it
  opens a different row.
  **Space** toggles the focused pull request’s changed files and keeps the current
  preview, focus, and history.
  On a file tree row, both keys toggle a folder or container file or show the next page
  and leave history alone.
  On a commit row, both keys select it again, replacing the entry.

The file tree and Git do here what they did in `v0.11.0`, so a change that makes one
conform to another changes a plain folder’s Back.

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
`test_nav_like_row_sets_share_the_vertical_keyboard_contract` covers the file tree, Git
history, pull-request rows, and their changed-file trees.
The adjacent `test_git_row_selection_avoids_full_collection_mutation` pins Git’s
interaction cost. Register every new navigational row collection in the shared check so
its Tab order and vertical navigation cannot silently fork this contract.

### Descriptor Contract

Every presented command declares:

- a stable identifier and scope;
- semantic bindings, each one key with no modifier policy, and an explicit repeat
  policy;
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
| Action or trigger label | Short sentence-case noun or verb phrase; no punctuation | `Quick Search` |
| Compact hint | One to three words; sentence case; no punctuation | `Toggle folder` |
| Help description | One complete active-voice sentence describing context or result | `Open the selected file.` |
| Context note | One complete sentence saying when the group applies | `Available while a file-tree row has focus.` |

Copy never repeats the rendered key name, uses a slash to mean “or,” or says “click” for
an action that also works from the keyboard.
Use the canonical product terms “Help,” “Quick Search,” “navigation pane,” “file tree,”
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
The shortcut groups end with one note, “Press `Shift` to see relevant shortcut
reminders.”, its `Shift` a keycap from the registry’s single-key `appendKey()`. The View
tabs, Controls, and Filters groups say “Available while the tabs are shown.”, “Available
while the control is shown.”, and “Available while the Files tab is shown.”

### Quick Search Results

Quick Search uses one option list for files and pull requests.
File rows show the filename and path.
Pull request rows show the title first, with the PR number and state below it.
The accessible option name includes that context.
In a GitHub repository, a leading `#` scopes results to PRs.
The empty prefix lists recent PRs, digits match number prefixes, and words match titles.

Use the same arrow, Enter, and Escape behavior for every result type.
Keep the active option selected by identity as providers return, and open the result
through its normal navigation route.

## Icons and Icon Buttons

Icons come from one Lucide-derived set in `static/icons.js`, rendered as inline SVG that
inherits `currentColor`. An icon never carries its own color.
A plugin’s own domain marks, which no other surface draws, are Lucide-derived the same
way and live with the plugin’s code, so a page that never shows them does not load them:
the GitHub plugin’s four pull-request states are in
`builtin_plugins/github/pull-state.js`.

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

A copyable path, revision, or other exact identifier pairs its visible value with an
adjacent `.icon-btn.icon-btn-reveal` using the registry’s `copy` icon.
The visible value may be abbreviated when its meaning remains clear, but the copy
payload must preserve the complete identifier.
The Git commit header therefore shows the short revision and copies the full commit ID.

Explicit values use `data-mb-copy="text"`, carry their escaped payload in
`data-mb-copy-text`, and name the resting action in `data-mb-copy-label`,
`data-tip-text`, and `aria-label`. Source blocks use the same SDK delegate in `wrap`
mode through `wrapWithCopy`. Do not add a component-local clipboard listener or inline
handler.

Build every such control with the page’s owner stamp: `mb.ownDelegate(element)` on an
element, or `mb.delegateOwnerAttribute()` spliced into markup (`wrapWithCopy` and
`partialNoticeHtml` stamp their own buttons).
The delegate ignores an unstamped control, silently, because a trusted folder’s Markdown
keeps `data-*` and can write the same attributes; the stamp is a value drawn when the
page loads, which no document can carry.
This has been required since plugin SDK 0.7. The shared delegate owns successful,
failed, and reset feedback, while the containing row owns when an `.icon-btn-reveal`
becomes visible. Keep the button in the Tab order even while it is visually quiet.

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
So is the Shift reveal for a button that is a shortcut target, so its keycap never marks
an invisible control.

## Filter Controls

Every filter in the app is built from one chip family, documented in the
`── Filter controls ──` block of `static/styles.css` and rendered by
`static/filter-controls.js`. A surface that needs a filter reaches for these rather than
inventing a pill of its own; four near-identical pills is what this family replaced.
[Choosing Among Values](#choosing-among-values) says where the family fits among the
other controls that offer a choice.

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

A file-type family’s hue is declared in the type registry (see
[Family Fields](project/architecture/file-rollup-format/file-rollup-format.md#family-fields)).
Where GitHub’s linguist names a color for the language, the hue is that color’s,
unchanged; families GitHub names no color for take a hue clear of every other.
That is what makes the palette recognizable — Ruby is red because Ruby is red
everywhere.

Each theme defines a `ToneBand` in `color_oklch.py`, with a lightness band and a chroma
target band. The registry derives each family’s lightness rank and chroma ratio from the
set of upstream colors; a family without an upstream color sits at the band’s center.
An explicit registry lightness-rank override changes that axis while retaining the
family’s derived chroma ratio.
Families therefore differ in lightness and chroma as well as hue, within the theme’s
band unless a documented lightness override places one outside it.

Chroma is a target rather than a guarantee: the Python color function reduces it only as
needed to fit sRGB, preserving the assigned hue and lightness.
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

The semantic table is the source of exact values, and a compact summary above it is what
a folder shows first.
That summary follows GitHub’s Languages box in this palette: directly under the
population bars, a legend of the largest file-type families, each a dot in its color,
its bold name, and its muted share.
A caption naming the population the shares are of, such as “Share of Total (9,169
files)”, labels the legend and the table for assistive technology only; on screen the
bars and the Show ignored checkbox already say which population it is.
Which families the legend names is data, so `/api/rollup` decides it, as
`file_type_legend`, for every measure and population at once; the browser picks the one
its controls select and only names, paints, and formats it.
The legend names at most five families (`LEGEND_TYPE_LIMIT` in `file_type_legend.py`),
from every group, ranked by the selected measure in the population the caption names,
and only above the 1% share floor at which the table folds a row into **N more**, so
every named family is also a row the table shows unfolded.
It never names **No extension** or **Other types**, which are the files no family
claims.
Whatever the named families leave is one neutral **Other** entry, so the legend’s
shares add up to the caption’s population.
The dot is as tall as the population tracks above it and serves as their color key, and
legend items wrap whole, so a dot never ends a line without its name.
The table, with every group, family, and **N more** row, sits behind a **Details**
toggle: the same section-disclosure trigger and bold label as an **N more** row.
Details starts closed on each mount, keeps its state through every repaint of that
mount, and is not saved as a preference.
Every table row names its category and reports absolute values and percentages.
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
own. Both use the same Markdown mount and pane gutter.
The panel’s width includes the document inset so the card border, section rules, and
surface panels share an edge.
`test_one_document_surface_has_one_set_of_breakpoints` holds this contract.

The **File Overview** section begins expanded.
It opens with one control row carrying the shared Files / Bytes measure and the **Show
ignored** checkbox side by side, then a fixed three-row composition table, then the
compact type summary beneath it, with the full type distribution behind its Details
toggle. **Files** comes first and reports the unignored population immediately from the
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
nested content.

A tally segment also grows, as
[Hover Styles the Thing Under the Pointer](#hover-styles-the-thing-under-the-pointer)
says; a Treemap cell takes the lift alone.
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
or metric. The metric switches all three totals rows and the map.
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

### The Tab Bar

A tab is `.tab-btn` in a `.tab-bar`, everywhere: OVERVIEW and TREEMAP, DOCUMENT and
SOURCE, FILES and COMMITS, and CONVERSATION and CHANGES. Markup keeps the label’s
natural case, and the caps are presentational.
`.active` paints the selected tab; under `role="tab"`, `aria-selected` says the same to
assistive technology, and both are set together.

A tab that is an address is `<a class="tab-btn" href>`, so back, forward, and open in a
new tab keep working.
`a.tab-btn` states what a `<button>` gets from the browser, so the two render as one
tab.

Files, Commits, and Pulls each keep their last selection and navigation scroll position.
A reader who switches tabs returns to that tab’s destination, or to its default on the
first visit. A direct URL or a browser history step selects the tab that owns the
destination.

The bar is as wide as the pane and sits under the identity it belongs to and over the
content it switches.
A use site does not pad, recolor, or re-letter it.
`test_every_tab_is_the_tab_primitive` holds the markup, the stylesheets, and the tokens.

### Section Headings

The title of a section in a stack is `.section-heading`: the tab bar’s uppercase, bold,
tracked sans grammar at `--body-font-size`, over a neutral rule.
`--section-heading-divider-gap` sets the space between its content and the rule, so the
rule is equally close to a heading with or without a disclosure control.
A use site owns the space around the heading, and the type and the rule stay with the
primitive. Overview’s panels and a pull request’s sections carry it, and
`test_section_headings_and_fold_expanders_are_primitives` holds it.

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
The composer renders the label as a visible, document-aligned
[section heading](#section-headings) above the panel body.
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
  its metadata, diagnostics, breakpoints, and print behavior.
  The Overview suppresses a nested table of contents.
  Overview adds the shared section heading but does not override the document card.
  The card keeps its standard border and shadow at regular and wide document bands, then
  becomes borderless through KPress’s own narrow breakpoint.

“Panel” describes composition and lifecycle, not a requirement to draw the same box
around unlike content.
Surface content, section headings, and document content use one responsive alignment
contract and shared stack gap.
At regular and wide Markdown breakpoints, flat surface panels and section headings align
to the README card’s outer edges.
The shared column is bounded by `--doc-measure` plus its document insets.
The same `kpress-doc` container selects the card breakpoint for the README and a
standalone file. The Markdown mount supplies KPress’s rendering and the pane gutter for
both. See [Reading Width](#reading-width).

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

### One Tooltip, and It Is Ours

The app has its own tooltip: anchored to the element it describes, styled, themed, and
on the app’s timer. The browser’s native `title` is a second tooltip system, and a
surface carrying both shows the reader two tooltips side by side on different timers.
That happened on the navigation heading, so the rule is enforced rather than remembered.

**No `title` attribute, no `.title =` assignment, and no `setAttribute("title", …)`,
anywhere the app owns the markup** — browser sources, built-in plugins, and the HTML the
server renders. `devtools/check_tooltips.py` fails the build on one, and runs in
`make lint`. Its exemption list names each exception and why: an iframe’s accessible
name, and a rendered document’s own links and embeds.

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

## Motion

Motion communicates a state transition: tree insertion, removal, refresh, loading, or
layout change. Keep durations short and use the shared motion tokens.
Avoid looping animation except for active progress indicators and
[refreshing content](#refreshing-content).

Respect `prefers-reduced-motion`. Content and status must remain understandable when
transitions are disabled.

### Live Row Arrivals

The Files tree and Pulls apply `.tree-item-flash-in` to a newly arrived row.
The shared `--row-flash-bg` tint fades to transparent in 900 ms and uses the
near-instant reduced-motion treatment.
The highlight leaves the row’s size and controls in place.

Initial snapshots, older rows revealed by paging, and edits to existing rows use their
regular presentation.
Each data source decides which rows arrived.
A live list fed by another provider can apply the same treatment when it inserts a new
item.

PR arrival classification uses a conservative timestamp cutoff.
A machine clock ahead of GitHub can suppress the tint.
The new catalog row still appears with its regular controls and selection behavior.

### Loading Chrome

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

An empty or error preview has no useful surface to retain.
It keeps the longer shell wait (`LOADING_INDICATOR_DELAY_MS`) before installing a
neutral spinner, which still uses `.mb-delayed-loading`. Ready content always wins
immediately: do not add a minimum spinner duration, progress bar, or transition that
delays usable content merely to complete an animation.
The shell ships the preview pane holding that neutral spinner rather than an empty
state, because every route that serves the shell selects something; the first selection
retains it until its view is ready.
The prompt to select a file appears only when nothing is selected and nothing is
loading, and switching navigation tabs changes neither.

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
A background refresh of content already shown is neither form: it is
[Refreshing Content](#refreshing-content).

### Refreshing Content

**Content already rendered is never covered by progress.** When a refresh checks data
the reader can already see — a cached pull request, its changed files, a Pulls list —
the content stays as it is, at full size and in place, with no spinner and no progress
or staleness sentence beside it.
A spinner over rendered content is the strongest loading signal pointed at something
that is not loading, and it drew the eye to a wait the reader was not making.

Instead, the text a refresh is checking **breathes**: its opacity eases down and back
once every `--refreshing-text-period` (2.4 s), starting only after
`--loading-state-delay`, so a refresh that lands within the quiet period shows nothing.
A status text that breathes — a page’s age line, the Pulls connection row’s text —
carries `aria-busy="true"` while it does.
Names and titles that breathe sit in rows that stay usable links and tree items, so
their breathing is paint alone and nothing marks them busy.

- `.mb-refreshing` breathes the element it is on.
- `.mb-refreshing-group` breathes the `.mb-refreshing-text` elements inside it, so a
  list toggles one container and a row drawn into it later joins.
  A view that draws rows into a breathing list brings them to the same beat
  (`alignRefreshing` in the GitHub plugin).
- **Primary ink only.** Primary ink dims to `--refreshing-text-dim-opacity` (0.8), 9.2:1
  in light and 9.8:1 in dark at its dimmest.
  Muted ink cannot dim and keep 4.5:1 (it rests at 4.62:1 in light), so a muted line
  takes `.mb-refreshing-muted` as well: it is drawn in `--text` at the opacity that
  reproduces `--muted` (`--refreshing-muted-rest-opacity`, an OKLab difference under a
  just-noticeable one) and lifts toward full ink instead.
  Status inks — change badges, line stats, state icons — never breathe.
- **One container per surface:** the pull request page’s age line, a changed-files
  tree’s folder and file names, the Pulls connection row’s age, and the titles of the
  rows whose own data GitHub is being read for.
  A tree’s file that the comparison does not hold is muted, and its name breathes as a
  muted line does.
- **Opacity only**, so the compositor runs it.
  Measured in headless Chrome 152 on 2026-11-11 with the real stylesheets: no
  compositing failure, and in the 2.7 s after the class went on, no style, layout,
  pre-paint, or paint on the main thread while the compositor drew 165 frames, in both
  themes. Starting it costs one style recalculation per breathing element: 2.5 ms for the
  120 a windowed tree and list draw, and 51 ms for 3,009 if every row of a 3,000-file
  tree were drawn, which the tree’s window never does.
  The numbers are beside the tokens in `static/styles.css`.
- `prefers-reduced-motion: reduce` stops it: the text stays as it rests, and a status
  text’s `aria-busy` still says a refresh runs.

What a stale view says follows from the same rule.
Stale data that can be refreshed is being refreshed, so a view shows its plain age
(“Fetched 3 min ago”, “Updated 3 min ago”) and never “may be out of date”.
It names a problem only when no refresh can run: offline, held by GitHub’s rate limit
until a stated time, a failure with Retry or Refresh, or a setup message.
A page left open refreshes again each time its data goes stale, at most once a freshness
window, rather than settling into a stale state.
The skeleton and spinner forms above remain for content with nothing usable cached.
`test_refreshing_text_breathes_on_the_compositor_and_keeps_its_contrast` holds the
utility, its tokens, and its contrast, and
`test_no_pull_request_surface_says_it_may_be_out_of_date` the copy.

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
