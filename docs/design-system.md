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
- A GitHub label’s colors are the other exception ([Label Colors](#label-colors)): the
  color is GitHub’s data, not a token, and the formula that paints it is github.com’s,
  written in `rgb()` and `hsl()` of the label’s own custom properties, so it paints what
  github.com paints.

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

Rendered text is one of two things, and the dividing line is again what the text is:

- **A document** is what the repository holds, rendered as one: a Markdown file in its
  Document view, a README on Overview, a note it transcludes, a Markdown file among a
  pull request’s Changes or opened from a pull request or a commit, a pull request’s
  revision page, and a plugin’s Markdown view.
  It reads in the reader’s reading font: serif by default, and sans when the reader
  chooses Sans.

- **Chrome prose** is text the app shows about the content: a pull request’s
  description, comments, and reviews, a commit message, and any other message or
  Markdown in the app’s own interface.
  It is sans in either reading font, as the rest of the chrome is.

The reading font exists for reading a document at length.
A message is conversation about the content, and setting it in the document’s face makes
the two read as one thing.
Inside a document, the faces of KPress’s own roles, such as footnotes, tables, small
headings, and code, are KPress’s typography and do not change with either rule.

A message reads at the document’s size in `--prose-sans-font`. PR descriptions,
comments, and reviews share the rendered README’s resolved reading width, including when
the reading font is serif.
See [Reading Width](#reading-width).

Each context has one mechanism, and no other rule sets a face by context:

- **A document takes the reading font from `<html>`.** The pre-paint script and the
  settings menu set `data-prose-font` there, and `static/styles.css` points KPress’s
  `--kpress-host-font-prose` hook at the reading face.
  A plugin’s `md-body` view sets the same face on its text, its headings, paragraphs,
  lists, and quotes, and not on the view, so what the host or the plugin draws in the
  view keeps the chrome face, as KPress keeps `.kpress` sans around `.kpress-prose`.
  Nothing between `<html>` and a document sets a face, so a document keeps the reading
  font inside any page that shows it.

- **Chrome prose carries `.chrome-prose`** on the element that holds the text, never on
  a page or a pane. The class sets the text’s own face and points KPress’s prose hook at
  `--prose-sans-font`, so a KPress article inside it is sans too, and so is `md-body`
  Markdown, whose text reads the hook before KPress’s token.
  A plugin that shows a message puts the class on the message’s element.

An h2 is upright wherever the prose face is sans.
KPress sets its h2 italic, an accent of its serif that reads as slanted sans in the sans
face. So a serif document keeps the italic, and an h2 in chrome prose or in a document
under the Sans reading font is upright, with KPress’s size, weight, and spacing.
The one rule in `static/styles.css` keys on the two places that point the prose hook at
sans, `.chrome-prose` and `html[data-prose-font="sans"]`, not on each surface.
The rule leaves h4 and h6 italic, each for its own reason.
KPress sets h4 in its sans font under either reading font, so the h4 italic is KPress’s
own sans style, not the serif’s accent.
An h6 follows the reading face like an h2, and keeps its italic because the request this
rule answers named only h2s. The `md-body` fallback sets no italic in either face.

`test_serif_is_only_for_documents` holds which rules may set a face and which builders
mark chrome prose. `tests/test_prose_faces_chrome.py` reads the faces they draw in, and
each Markdown text’s h2 style, in Chrome, under both reading fonts and both font sets.

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
| Control with `N` or `P` | `⌃N` on macOS and iOS, `Ctrl+N` elsewhere | Control N | `Control+N` |

`Shift` is a name for the formatter’s single-key entry point, `describeKey()` with
`appendKey()`, which renders a key that is not a binding, such as one named in a
sentence. No binding may use it.
A [Control chord](#control-chords) is one keycap, written as its platform writes it; the
formatter reads the platform from the page’s navigator, and without one, as in a
browserless session, writes `Ctrl+N`.

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

The sidebar orders Files, Pulls, and Commits in that order, and their keys are `F`, `P`,
and `H` ([Keyboard Shortcuts](#keyboard-shortcuts)): Files and Pulls take the first
letter of their label, and Commits takes `H`, for commit History: `C` is Charts’ and
Conversation’s, view tabs that a shell letter, reserved everywhere, would leave without
a key. The letters work outside text fields and dialogs, with or without Shift.
A letter opens its tab, or keeps the tab already shown, and moves focus to the panel’s
roving row, so `F` then `↓` walks the file tree; while the panel has no rows yet, the
tab button takes focus.
A missing tab has no target, so its letter does nothing and stays reserved.

#### Binding Grammar and Accessibility

- Every shortcut is a single key, but for the two [Control chords](#control-chords),
  Control-N and Control-P. A binding declares Control with `control: true`, and the
  registry rejects it with any other key.
  No binding uses Alt or Meta, and the registry rejects a binding that states any other
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
  header path, file-header path — and the
  [navigation metadata line](#navigation-metadata-line) that states their totals.
- `--ui-small-font-size` (12px): secondary chrome — metadata, chips, tooltips, notes,
  filters, summaries.
- `--label-font-size` (= ui-small): all-caps section labels — tabs, panel and table
  headers, stat labels.
  Labels differ by caps treatment, not by another size.
- `--mono-block-font-size` (= ui-small): monospaced blocks in chrome contexts — source
  views, split and unified diffs, review hunks, logs, raw JSON.
- `--micro-font-size` (10px): deliberately minimized marks — the brand line.
- `--page-title-font-size` (24px): the title of a page no file stands behind, a pull
  request’s. It sits above the 25.5px regular first heading of the text below by its
  bold weight, not by its size.
- `--git-ref-font-size` (`--git-ref-font-scale`, 0.9, of the inherited size): a ref
  chip, slightly smaller than the text it sits in.
  The ramp’s one relative size, because a chip sits in text of several sizes and reads
  as part of it; see [Branch Chips](#branch-chips).

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
- the numbers of a count summary are bold, and its words regular
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers));
- code uses monospaced text without forcing prose into a code style, and paths stay in
  the sans navigation face.

Do not shrink essential text to fit.
Prefer truncation with an accessible full-value tooltip or allow a panel to scroll.

### Count Summaries Bold Their Numbers

A count summary is a line of chrome that says what a list, a tree, or a change set
holds, in numbers and words: “8 changed files (8 modified)”, “15,458 files (324.1 MB)”,
“3,310 commits begun 4mo ago”.
It is a line of the [navigation metadata band](#navigation-metadata-line), or a summary
line that heads a list or a change set; a remark on that band that counts
(`.nav-metadata-note`), as the Files filter’s “Filtered to 1,234 files.”, is one too,
since it reads against the totals above it.
A search’s or a process’s status is not one, though it counts: it says how far the
search or the process has got, not what a list holds.
In every count summary, each number is bold and the words around it keep the line’s
weight, so the counts read at a glance and two of them read against each other.
One token sets the weight, `--count-numeral-weight` in the shell’s stylesheet, which is
`--weight-bold`, the weight of the [inline change stats](#inline-change-stats) and of a
[pull request’s number](#pull-request-numbers).
Every count’s numeral takes it, a count summary’s `.summary-number`, a commit hover
card’s `.git-commit-file-status`, and a [heading’s tally](#heading-tallies),
`.heading-tally-figure`, and none borrows `--pull-number-weight`, which only a pull
request’s number takes.
`.summary-number` in `static/styles.css` sets that weight alone: the number keeps its
line’s size and ink, muted in a muted half or note.
A number is the whole figure: its grouping and decimal marks, a sign, a lower bound’s
“+”, and a size’s unit, “394.6 MB”. Parentheses, separators, and words stay regular, and
an age keeps the [age primitive](#age), which has a weight of its own.

A count summary’s text comes in one shape of parts: the words as strings and each number
as `{number}`, “12,797 files” as `[{number: "12,797"}, " files"]`. The shell paints them
through `countPartsHtml` and `countPartsNodes` on `window.MetabrowserFormatters`
(`static/formatters.js`), and the built-in plugins with their own `el()` and `h()`. The
words and numbers of one phrase sit in one inline element: in a flex line, as a
navigation metadata line is, each would be an item of its own, parted by the line’s gap
and read as a run of its own.
So the line’s text and accessible name are unchanged: the span adds no words, the spaces
stay where they are written, and a header with an `aria-label`, as the Diff summary’s,
keeps it.

| Count summary | Where its numbers are painted |
| --- | --- |
| The [Diff summary](#diff-summary)’s header and its fallback totals line, on a commit’s page, in a pull request’s header, and in a patch’s toolbar | `renderDiffSummary` and `summaryOrTotals` in the diff plugin’s `diff-view.js`, from `describeChanges` (`filesParts`, `breakdownParts`) and `plainTotals`; its line totals are the inline change stats, bold already |
| The Files totals, tracked and ignored, and the live figures | `treeSummaryHtml`, `treeSummaryCountHtml`, and `treeSummarySizeHtml` in `static/navigation.js` |
| The Files filter’s remark, “Filtered to 1,234 files.” | `filteredTallyParts` in `static/tree-filter-model.js`, painted by `_renderFilteredTally` in `static/app.js` in one span of its line |
| The Commits tally | `renderHistorySummary` in `static/git-panel.js` |
| The Pulls count, “448 PRs on owner/repo” | `.github-pulls-total` in the GitHub plugin’s `pulls-panel.js` |
| A pull request’s Checks summary, “3 success · 1 failure” | `paintChecks` in the GitHub plugin’s `pull-page.js` |
| A commit’s files outside the served folder, “2 files outside this folder” | `renderCommitDetail` in `static/git-panel.js`, in one span of its line |
| A commit’s hover card, “28 M 4 A files” and “+1921 −160 lines” | `.git-commit-file-status`, at `--count-numeral-weight`, with its status letter, and the commit’s change stats ([Git Commit Summary](#git-commit-summary)) |

The rule does not reach a number that is not a count summary’s:

- row metadata, as the right-aligned size and count of a tree row, and the size, count,
  and age of a folder’s header strip, which the size and count chips set by their own
  threshold;
- a control’s label or a chip’s tally, as “Show 40 more” or the Pulls filters’ “Open
  30”;
- prose or a notice, as “wants to merge 6 commits” or “This commit changes 900 files;
  the diff below is bounded.”, where a number is text and keeps its line’s weight, as a
  pull request’s number does in prose;
- a search’s or a process’s status, as a Quick Search status, “12 matching files.”, a
  progress line, “~1,200 files scanned”, or a Pulls row’s file list while it fills or
  stops; and
- a labelled value, as a stat card’s, which has its own type.

`test_count_summaries_bold_their_numbers_through_one_token` in
`tests/test_design_vocabulary.py` holds every rule that reads `--count-numeral-weight`
or `--pull-number-weight` to its list, and no stylesheet to restyling a count summary’s
number. `tests/dom/diff-view-behavior.js`, `tests/dom/tree-summary-line-session.js`,
`tests/dom/tree-filter-model-behavior.js`, `tests/dom/git-panel-behavior.js`,
`tests/dom/github-pulls-panel-session.js`, and
`tests/dom/github-pull-core-preview-behavior.js` hold each surface’s numbers apart from
its words without a browser.
In Chrome, `tests/dom/diff-summary-chrome.mjs` reads the computed weights on a patch’s
Diff summary, a commit’s, and the Files totals and Commits tally beside it, and
`tests/dom/nav-metadata-chrome.mjs` the Files filter’s remark and the Pulls count’s;
both hold that every number is inline with its words, and the second that the remark
reads as one run.

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
Its panel headings and bodies follow the document card’s outer edge.
Their text starts on the active tab’s label rather than at the README’s responsive inner
inset; see [Folder Overview Is a Panel Stack](#folder-overview-is-a-panel-stack).
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
An action that opens nothing, such as a pull request’s Refresh, is always a `<button>`.
Both forms look the same in their context, a tooltip and accessible name say which
commit opens and whether the pin switches, and keyboard and screen-reader users still
get the element they expect.
The diff file bar’s [View file](#diff-file-bar), and
[Browse code, a review comment’s file, Refresh, and Switch to the head](#chrome) on a
pull request’s page, are text actions.
Each context sets one look for the `<a>` and the `<button>`, box included: a `<button>`
is always an atomic inline box, so where a label can wrap, the `<a>` is one too, and
what follows a wrapped label starts on the next line in both forms.

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
same slot a folder uses, `--tree-icon-slot` ([One Glyph Size](#one-glyph-size)), so
names stay aligned at every indent.
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
| Pull request row, in [the Pulls tab](#the-pulls-tab) | The number’s line and the age, on the first line; the title, alone on the second | Chevron and state icon, on the first line |
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

A header badge whose label changes in place sits in a slot as wide as its widest label
from first paint, so the change moves nothing after it: a one-column grid of the badge,
then a sizer of each label at no height, outside the badge so its trim still centers the
capitals. A run’s status badge is one, for Running, Live, Done, Failed, and Run ended,
and a pull request’s state badge is another; `tests/dom/github-pull-header-chrome.mjs`
checks both in Chrome.

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

One fold is not a row: a rendered Markdown diff’s fold of unchanged blocks (“6 unchanged
blocks”) is a line in the document, because the user asked that it have no borders and
expand in place in the rendered document.
It has no box, fill, or rules, closed or open; its chevron starts on the blocks’ text
edge; its label brightens from muted to `--text` under the pointer, as a document’s own
disclosures in the shell do; and opening it sets the blocks it holds exactly as the
unchanged blocks around them.
`tests/test_diff_markdown_fold_chrome.py` measures it in Chrome.

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

Only a toggle the reader asked for travels.
When navigation reveals a path, as a link, Back, or Quick Search does, the tree opens
the folders on the way with `.tree-children-instant`, which lands them in place.
Animated, a deep reveal moved the rows below it 43–131 px a frame with no input.
The reader’s next toggle of that folder travels again.
Such a reveal is the reader’s own doing, so it then scrolls the new selection into view
in the same frame. A landing within the inline’s bounds needs no reveal: the server
inlines the folders of the address’s path, open, and the tree’s first paint selects and
shows its row, so nothing is fetched, opened, or scrolled after it.
Opening them after the first paint had moved the tree with no input.
The bounds are each folder’s whole listing (200 entries at most), 300 rows for the
path’s folders in all, and 8 folders, and the inventory’s discovery complete.
A landing outside them inlines the root alone, and the page reveals its path after the
first paint, its folders travelling, as before: that still moves the tree with no input.

### Disclosure Toggles Never Select Text

A **disclosure toggle** is any control that shows or hides content: a tree row that owns
a child group (a folder, a container file, a tally node, a pull request in the Pulls
list, a folder of its changed files, a folder of a Diff summary), a section-disclosure
trigger, a fold expander, a diff file bar, a Diff summary’s header, an expandable log
event or data row, a `summary`, and a menu trigger that carries the registry chevron.
A control with the chevron or a `summary`’s marker is a toggle, and so is one that sets
`aria-expanded` for content it shows in place.

Every one carries `.disclosure-toggle` in its markup, beside its own primitive’s class,
the way a notice carries `.notice`. The one rule for it is in `static/styles.css`, and
it sets `-webkit-user-select` and `user-select` to `--toggle-user-select`, which is
`none`. A native `summary` matches by element, so a disclosure a document writes for
itself, in a README or a pull request’s description, behaves the same.
Plugins use the same class; `plugin-sdk.js` lists it with the SDK’s visual helpers.

A click on a toggle is a command, not a reading gesture, so it must never leave a
selection behind. Before this rule, a triple click on a rendered Markdown diff’s **5
unchanged blocks** fold selected its label and every paragraph it revealed, in Chrome;
in WebKit, which is the macOS app’s engine, a double click on a folder row selected the
folder’s name. WebKit reads only the prefixed `-webkit-user-select`, so the unprefixed
rule the tree rows had was never applied there.
Declare the prefixed property beside every `user-select`, not only on toggles.

The rule is enough on its own.
Measured on 2026-11-13 with real double and triple clicks, in headless Chrome on a
folder row’s name, padding, and size and on the fold’s label and padding, and in a
`WKWebView` on a folder row’s name and a section trigger: nothing was selected, and a
`mousedown` handler that prevented the default of the second and third presses changed
nothing in either engine, so there is none.
A drag that starts in content still selects it, because the rule applies to the toggle
alone.
What a toggle reveals is its sibling, never its child, and stays selectable; never
put the class on a container that holds content.
The rule is paint only: focus, Enter and Space, `aria-expanded`, and the click target
are the toggle’s own and do not change.

Not toggles: a dialog trigger or an icon-only menu button with no chevron, such as the
settings gear and the overlays’ triggers, which have no label to select, and the search
field, a combobox whose text must stay editable.

`test_disclosure_toggles_never_select_text` in `tests/test_design_vocabulary.py` holds
the rule, its prefixed half on every `user-select`, that no stylesheet makes a toggle or
anything inside it selectable (content a toggle reveals beside it may be), and the
inventory: each registered toggle carries the class, every chevron and `summary` a
source builds is listed with the builder of the element it goes into, and a source that
sets `aria-expanded` is registered or named with the reason it builds no toggle.
The check reads source text, so it cannot see which element a listed chevron lands in;
it holds only that the builder it is listed with sits near it, and review holds the
rest.

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
[Branch Chips](#branch-chips), defined here, is the reference for a ref chip on every
surface: a pull request’s header and the ref selector as much as a history row.

### Lane Colors

Five lane colors, `--git-lane-1` through `--git-lane-5`, assigned round-robin as lanes
open. They are **one set, not five independent choices**: the property that matters is
that the five stay distinguishable from one another, which belongs to the set, so a lane
color is never adjusted on its own and the set is identical in both themes — thin
strokes carry on either background.
This is the documented exception to the hue rule in
[Color and Theming](#color-and-theming).

The lane a commit sits on colors its node, so a commit and the history below it read as
one line. `HEAD`’s lane takes the branch blue, `--git-ref-remote`, the color most branch
chips show. It does not take the local chip’s blue-green, though `HEAD` is usually on a
local branch: that hue sits beside lane 4’s teal, and a lane has to stay apart from the
five.

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
| Ref chips | Fixed, slightly smaller than the subject by the [chip ratio](#one-ratio); shrink last (see below) |
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
3. the commit’s changes: in the full summary its [Diff summary](#diff-summary), in
   `.git-commit-diff-summary`, where the commit’s diff draws it, and in the compact one
   `.git-commit-change-stats`; and
4. the commit description, when present.

The identity group shows the commit’s refs as the Git history row does, with the same
kinds, trunk, and HEAD marks ([Branch Chips](#branch-chips)). The full summary makes the
revision copyable; the compact summary keeps the familiar copy glyph noninteractive.

The Diff summary is the commit page’s one statement of its changes, as on a pull
request’s page, with the same header and words, collapsed until it is opened.
The diff draws it in the summary’s place before the page is shown, so it is there at
first paint, and it is there for a commit of one file too.
Where the diff is not drawn, as when the diff plugin is absent or the comparison fails,
the place is empty and takes no room; a failed comparison says so in the diff’s place.
Measured in Chrome 152 at 980 to 320 px, the summary sits 6 px under the identity and 16
px over the description, its place on the subject’s edge and its toggle hung 4 px into
the gutter, as every Diff summary’s is; its header is one 24 px row at 560 px and wider
and wraps to two lines at 420 px and three at 320 px, all before the page is shown;
opened, its tree is under it and above the description; and an empty place takes no
room. `tests/test_git_commit_summary_chrome.py` holds it.
The compact summary, in a tooltip, has no diff: its `.git-commit-change-stats` child
sits below the identity metadata.
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
The compact subject, author, age, file-status counts, units, and line counts use
`--body-font-size`. The ref badges are chips, slightly smaller than that text, by the
[chip ratio](#one-ratio).
Among the row’s text the revision is the one deliberate exception: it is monospace, and
mono at body size renders optically larger than the sans text beside it, so it uses
`--nav-font-size` — one step down the ramp — to sit level with its row.
The compact tooltip is bounded by width and subject line count, not made denser with
smaller type. The optional full-summary description is chrome prose, as a PR description
is (`.chrome-prose`), at `--document-body-font-size` and `--kpress-line-height-normal`.
It preserves authored newlines and wraps long text.
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
summary. A revision-hosted comparison draws its [Diff summary](#diff-summary) in the
summary’s place, at the page’s top, not in its toolbar, so the page has one set of
totals; a patch file opens with its own in its toolbar.

Do not assemble commit-summary fragments in `renderCommitDetail` or add a second root.
`tests/test_design_vocabulary.py::test_git_commit_summary_is_one_component` maintains
the renderer, root, child, styling, and documentation contract.

### Branch Chips

Git ref chips (`.git-ref`) are their own vocabulary, not filter chips.
Every one is drawn by `mb.refChip` or `mb.refChipHtml` in `static/plugin-sdk-views.js`,
and a merge’s two by `mb.mergeRefs` ([Merge Direction](#merge-direction)); no surface
builds its own. A chip answers three questions, each with its own signal: what kind of
ref it is, whether it is trunk, and whether `HEAD` is on it.

#### One Ratio

A chip is slightly smaller than the text around it, wherever it appears: one ratio, not
one size. Its size is `--git-ref-font-size`, `--git-ref-font-scale` (0.9) of the size it
inherits, so a chip in a 14px header line is 12.6px and one in the 12px ref selector is
10.8px. One rule on `.git-ref` sets its type and box.
No context overrides them, and the box a chip sits in — a merge’s grid, a history row’s
ref group, a summary’s identity group, the ref selector’s label — sets no size of its
own, so the chip scales from the text beside it.

Measured in Chrome, light theme, the text each context sets and the chip it gets:

| Context | Text around the chip | Chip | Chip before the ratio |
| --- | --- | --- | --- |
| A Git history row | 13px subject | 11.7px | 12px |
| A commit’s summary and its tooltip | 14px metadata | 12.6px | 12px |
| A pull request’s header | 14px branch line | 12.6px | 12px |
| The ref selector’s button and list | 12px | 10.8px | 12px |

| Property | Value | Why |
| --- | --- | --- |
| Size | `--git-ref-font-size` | Slightly smaller than its text, so a branch name reads as a tag on that text rather than the text itself. The smallest context gives 10.8px bold, above the 10px of `--micro-font-size`, so the ratio needs no floor |
| Weight | `--weight-bold` | The name carries the meaning |
| Line height | `1.333` | The chip’s box scales with its text: 16px at 12px, as before, and at most 16.8px. A 13px history row’s 15.6px chip keeps the `HEAD` ring inside its 22px row |
| Corner | `--radius-tag` | Square-ish, so a ref and a filter never read as the same control |
| Padding | `0 5px` | Room around the name, not text, so it stays in px. A tag adds 4px on the left for its notch, and a copyable chip reserves 19px on the right for its copy control, a fixed-size icon ([One Glyph Size](#one-glyph-size)) |
| Width | At most `22em`, ellipsized, with the full name in its tooltip | In em so the bound keeps its meaning at any chip size; the measurement is beside it in `styles.css` |

`test_branch_chips_scale_with_their_text` in `tests/test_design_vocabulary.py` holds the
ratio: it fails on a rule in any shipped stylesheet that sets a chip’s type or box from
a context, or that gives a box a chip sits in a size of its own.

#### Kinds and Forms

| Kind or mark | Token | Form | Cue besides hue |
| --- | --- | --- | --- |
| Remote branch | `--git-ref-remote`, blue | Plain | In a history the name carries its remote, `origin/topic`; a merge and the ref selector show only remote branches |
| Local branch | `--git-ref-local`, blue-green | Plain | A name with no remote |
| Tag | `--git-ref-tag`, amber | Notched left edge, `<v1.0)` | The notch |
| Trunk | Its kind’s color becomes the ground | Solid | The solid form |
| `HEAD` | Its kind’s color, `--git-ref-ink`, so a ring on solid trunk shows too | A ring, kept inside a history row’s clip | The ring |

Hue is never the only cue: shape carries the kind, because a reader who does not
separate the branch and tag hues would otherwise see one vocabulary with two colors.
Trunk and `HEAD` are marks on top of a kind.
`HEAD` can sit on trunk, an ordinary branch, or nothing, so it is a ring and leaves the
chip’s form alone.

#### Which Kind Each Context Gets

A chip’s kind says where the ref lives, and trunk and `HEAD` come only from the server,
so a definition cannot differ between two places.

| Context | Drawn from | Kind | Trunk | `HEAD` | Copy |
| --- | --- | --- | --- | --- | --- |
| A checkout’s history row | The history page’s refs (`renderRefBadges` in `static/git-panel.js`) | The wire’s `kind`: `refs/heads/` local, `refs/remotes/` remote, `refs/tags/` tag | The ref’s `is_trunk` | The ref’s `is_head` | Beside the row |
| A mirror’s history row | The same | Its branches are `refs/remotes/origin/…`, so remote; its tags, tag | The ref’s `is_trunk` | None: a pin is detached | Beside the row |
| A commit’s summary | Its detail’s refs, the same parser as the row | As its row | As its row | As its row | In the chip |
| A commit’s tooltip | The same | As its row | As its row | As its row | None: a tooltip owns no action |
| A pull request’s header | `mb.mergeRefs`, head → base | Remote: GitHub’s branches, a fork’s as `owner:branch` | Never | Never | In the chip |
| The ref selector’s button and list | `mb.refChip` in `static/source-ref-selector.js` | Remote for a branch, tag for a tag | Never; the list says “default” beside the default branch | Never | Button beside it; list none |

The reasons:

- **A pull request’s branches are remote** even when a checkout has a local branch of
  the same name. They are the hosted repository’s refs, and the local branch is another
  ref that can point elsewhere; in the checkout’s history it is a local chip.
- **Trunk is a fact about a Git ref**, `main` or `master`, local or on a remote, decided
  server-side by `is_trunk_ref` in `git/log.py` from the same names that scope the
  history walk. The history page, a commit’s detail, and `/api/git/refs` all carry it.
- **A merge never draws trunk.** The arrow already names the target, and a solid base on
  nearly every pull request would stop trunk standing out where it is worth finding: in
  a history of many refs.
- **The ref selector never draws trunk.** Its default branch is the mirror’s default,
  which need not be the branch the history draws solid, so it says “default” in words.
- **`HEAD` belongs to a checkout.** Only refs from Git carry `is_head`, and a pin, a
  mirror’s page, is detached.

`test_each_context_assigns_its_chip_kind` in `tests/test_design_vocabulary.py` holds
this table against the code that draws each context, and `tests/test_git_api.py` holds
that a commit’s detail and `/api/git/refs` carry the refs and trunk its history row
does.

#### Color

The chips’ ground is `--git-ref-bg`, a near-neutral of its own rather than the shared
chip surface, sitting at the value of the surfaces beside it with just enough chroma to
separate from them. The three ref colors are one lightness and three hues, and the dark
theme raises their lightness so they stay the same three colors.
The branch most chips show is remote, so remote is the blue.
The local blue-green is clear of that blue, of a merged pull request’s purple, and of
the tag’s amber. Each color reads at 4.5:1 or better on `--git-ref-bg` in both themes,
and the figures are beside the tokens in `styles.css`.
`test_branch_chips_are_blue_and_never_a_merged_pull_requests_purple` in
`tests/test_design_vocabulary.py` holds the contrast, the blue, and the distance from
the merged purple.

#### Copy

Copyable branch chips reserve a tiny copy control beside the label, revealed on hover or
keyboard focus. The control copies the complete underlying branch or ref, regardless of
label truncation or a displayed fork owner, and reports the normal copy feedback.
Its click does not select a different row or follow its link.
An outside pointer interaction hides active copy controls and restores the primary row’s
focus before a pane drag can clip its focused button.
Place copy controls beside a primary link or button rather than nesting interactive
controls.

### Merge Direction

A merge between two branches always reads **source → target**, left to right: the branch
whose commits merge, an arrow, and the branch they merge into.
For a pull request that is its head, then its base: `claude/x → main`.

Reading order is the direction of change, so the eye follows the commits.
Never write “into … from …”, which names the target first and makes the reader reverse
the sentence, and never `target ← source`. A sentence keeps its verbs and the branches
follow it in the notation: the pull request page’s header reads “octo wants to merge 1
commit” or “octo merged 1 commit”, and under it `wip → topic`. A rename in a diff reads
the same way, `old → new`.

| Part | Rule |
| --- | --- |
| Markup | `mb.mergeRefs(source, target, options)` in `static/plugin-sdk-views.js` writes every merge; no surface places its own arrow. Each side is `{name, label}` and becomes a [branch chip](#branch-chips), and `options` (`kind`, `copy`) applies to both |
| Arrow | `.merge-refs-arrow`: `→` (U+2192) in `--muted`, at the size of the text around the merge, which the group inherits; each chip is slightly smaller. The spaces around it are text, so a copied selection reads `wip → topic` |
| Accessible name | The arrow is `role="img"` with `aria-label="merges into"`, so a screen reader reads “wip merges into topic” in document order. It has no tooltip: the names beside it say the merge, and a chip cut short carries its own full name ([Tooltips Add Information](#tooltips-add-information)) |
| Right to left | The group is `dir="ltr"`, an isolated left-to-right run as a path or a branch name is. The arrow points from source to target whatever the surrounding direction, the glyph is never mirrored, and the document order, source first, is the order a screen reader reads |
| Narrow places | The group is a three-column grid in which the names shrink and the arrow never does. The two names share the room equally: a name that fits in its half keeps all of it, the longer one gives way first, and each ellipsizes inside its chip with the full name in the chip’s tooltip. The group is never narrower than both chips’ padding and copy slot, an ellipsis in each, and the arrow. The pull request header gives the merge a line of its own, under the author’s sentence, so only the names give way there |

A Pulls row names no branches: the pull request’s page names them, and the row’s room
goes to its title.

The rendered group, for a pull request from `wip` into `topic`:

```html
<span class="merge-refs" dir="ltr">
  <span class="git-ref git-ref-remote git-ref-copyable merge-refs-source">…wip…</span>
  <span class="merge-refs-arrow" role="img" aria-label="merges into"> → </span>
  <span class="git-ref git-ref-remote git-ref-copyable merge-refs-target">…topic…</span>
</span>
```

It appears in the header of [the pull request page](#the-pull-request-page); a new
surface that shows a merge calls `mergeRefs`.
`test_merges_read_source_to_target_in_one_notation` in `tests/test_design_vocabulary.py`
holds that the page calls it head first, draws no ref chip of its own, and never writes
`←`, that a Pulls row does not call it, the arrow’s name, direction, floor, and tokens,
and the rules by which a Pulls row’s number’s line gives way.
The page’s session holds the order, the arrow’s name, and the literal refs it draws.

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
The same pair is the [Diff summary](#diff-summary)’s vocabulary, so a change set, its
folders, and its files read identically.
Kind letters reuse the same mapping — added is `--status-success`, deleted is
`--status-error` — and no diff surface introduces a local green or red.

### Diff Summary

A change set has one Diff summary, and it starts collapsed.
A page with a header of its own holds it at its top, on every tab, so the counts are not
inside the changes: a commit’s page under the commit’s identity, in its
[commit summary](#git-commit-summary), where the commit’s diff draws it (`summaryHost`),
for one file too; and a pull request’s page as its header’s last row
([Layout](#layout)), which the page draws from the comparison it reads, through the diff
view’s `summary`, while its Changes diff draws none (`summary: false`). Elsewhere, as in
a patch file, a diff of more than one file opens with it in the toolbar beside the
layout control. Its header is one row-like disclosure toggle that leads with the
registry’s chevron in the tree’s icon slot, `--tree-icon-slot`: “35 changed files (2
added, 3 removed, 30 modified) +1,234 −3,423”. The breakdown lists only the statuses
some file has, in one order (added, removed, modified, renamed, then copied, type
changed, unmerged, and any other), in `--muted`; numbers use the shell’s number format
and are bold, the file count’s and each status’s, with the words regular
([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)); the totals
are the [inline change stats](#inline-change-stats); and “(estimated)” follows totals
that are not exact. Its accessible name says the same in words.
A change set of no files has nothing to open, so its header is a line.
Where the shared tree did not load, the header is the line main drew, “N changed files
+A −D” in the shell’s number format, with no toggle; and a header whose tree did not
load when pressed is marked `aria-disabled`, with a tooltip saying a press tries again,
until a press loads it.

Opened, it shows the change set’s files as a tree by folder, the
[Pulls tab’s tree](#the-pulls-tab) adapted to the page and drawn on the same model
(`static/changed-files-tree.js`): the nav panel’s row height, indent, chevrons, change
letters, and inline change stats at the row’s end, a chain of single folders as one row,
and every folder with the line counts of the files under it rolled up, open or closed,
as a Files folder keeps its size whichever way it is turned.
Both trees draw one row, the shell’s `.changed-file-row` class set in
`static/styles.css` beside the Files tree’s rows: the 12 px content inset past the 2 px
bar, the square hover, and the focus ring 2 px inside the row; each plugin sets only its
depth’s indent, `--changed-file-indent`. The header hovers and rings as its rows do.
`tests/test_changed_file_rows_chrome.py` mounts both trees on one list in Chrome and
holds them to one row; before the shared set the summary’s rows started 2 px further
left.
A folder says in its accessible name what its sums leave out (“2 files without line
counts”, or each side’s when they differ), and its tooltip says that alone, since its
name is on the row ([Tooltips Add Information](#tooltips-add-information)). A path a
patch lists more than once, as a file that became a symlink, is one row with both
changes’ counts, and goes to the first of its sections.
The header is the tree’s root, so the tree’s first level starts one indentation step,
`--tree-indent`, in from it, its chevron from the header’s chevron and its name from the
header’s words, and each level one step more, as a folder’s rows start one step in from
the folder in the Files tree and the Pulls tab’s, wherever the summary is: in a diff’s
toolbar, under a commit’s identity, and in a pull request’s header.
The rows give back where the header starts, `--diff-summary-header-inset`, the toolbar’s
padding in a diff and nothing at a page’s top, less its pull to the left,
`--diff-summary-toggle-pull`, which lets its hover ground reach past its chevron.
Before, a diff’s toolbar started the first level 4 px in from the header.
Opened, the tree sits under its header, below the toolbar in a diff, as tall as its
rows, in the page’s flow, with no scroll bar of its own: the page scrolls past it.
It has no bound on its length beyond the comparison’s, at most 2,000 files, and the
document holds only the rows in the window’s view of it and `SUMMARY_ROWS_OVERSCAN` more
each way, as the Pulls tab’s tree does.
On synthetic patches of 106, 600, and 2,000 files (3,197, 23,237, and 54,965 px tall) in
Chrome the rows showed 8 to 57 ms after a press, the document held at most 116 rows, and
scrolling the page through the tree kept its frames; the numbers are beside the constant
in `diff-summary.js`. Nothing of it is mounted until the header first opens it.
The keys are a tree’s: the arrows move one tab stop, Right and Left open, close, and
step into or out of a folder, and Home and End go to the ends.
Only Enter, Space, or a press on a file jumps the diff to that file, because the tree
sits above the files and a jump on every step would scroll it away.
On a pull request’s page the jump goes through the file’s address,
`/pull/<n>/files/<path>`, the route a press on it in the Pulls tab takes, from any tab,
so the address names it and Back returns; a patch file has no address for a place in its
diff, so there the diff moves in place and the address stays the file’s. A path is its
author’s text: a row shows it by the server’s display rule, with a control, format, or
invisible character, such as a right-to-left override or a zero-width space, as U+FFFD,
as the Pulls tab shows the same path, and the file bar the row goes to shows it the same
way ([Diff File Bar](#diff-file-bar)). `tests/dom/diff-summary-session.js` holds the
words, the rows, and the keys, and the paint’s measurement is in the views, models, and
routes map (`diff.summary-paint`).

### Diff File Bar

The bar shows its path, and a rename’s two, by the server’s display rule, as the
[Diff summary](#diff-summary) does, and its stats in the shell’s number format; its copy
control copies the path as it is.

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

The diff’s toolbar, which holds the control, draws no rule under itself.
The first file card’s own border, at the cards’ 12 px gap below the toolbar’s padding,
is the line between the toolbar and the files.
On a commit’s page and a pull request’s Changes, where the toolbar holds the control
alone, a rule there would draw a second line 12 px above the card’s. In a patch’s
toolbar the [Diff summary](#diff-summary)’s header is its tree’s root, and the tree
opens under it with no line between them, as it does at a page’s top.
The toolbar is not sticky, so nothing scrolls under it that a rule would separate.
`tests/dom/diff-summary-chrome.mjs` reads in Chrome that a patch’s toolbar and a
commit’s draw no rule and that the first card starts 12 px below them.

## The Pull Request Page

The page at `/pull/<n>` shows one cached pull request.
It has almost no vocabulary of its own: it places the shell’s primitives, and a text of
the pull request reads as the same Markdown does in a file.
`test_the_pull_request_page_carries_the_shells_primitives` holds what follows, with the
tests named beside each primitive.

### Layout

The page is a header, a [tab bar](#the-tab-bar), and a body, in that order; native stack
navigation is part of the header.
The header, tabs, Conversation, and Checks use `.page-reading-column` and start at the
same pane gutter as the commit summary.
The first tab aligns with the content in narrow and wide panes.
The column includes the card’s insets so its text can reach the same measure as the
rendered README. Both headers use `.page-heading`. The title begins with the Pulls state
icon at the title’s font size.
The text wraps under its first line while the icon stays beside the first line, to two
lines at most: the title holds two lines from first paint, and one cut short there
carries the whole of it in its tooltip.
The icon and the text start at the header’s left edge, and the number, outside the
clamped text, ends on the header’s right edge, level with the title’s last line, over
the stack chip that ends the author’s row, whatever the title’s length.
The colored badge that leads the row of ages gives the state in text and the title icon
is decorative. The header’s box is decided at first paint, in every state and on every
tab, so the tab bar under it never moves between tabs, nor between pull requests that
both have labels or both have none: the author’s row is one line, the author and the
sentence, then at its right end the stack chip’s slot (see native stack navigation
below), and the sentence is cut short at its end, the action first and then the author,
never moved or wrapped; the branches have the line under it to themselves, one line in
every state, their names cut short rather than wrapping it; the row of ages begins with
the state’s badge, as wide as the widest state, then “Opened”, the ages, View on GitHub,
and Browse code, one line cut short at its end; a pull request with labels has a row of
them, one line at a label’s height, and one with none has no labels row and no gap for
it; the status row, the freshness line, is the next metadata line, as tall as the row of
ages, and ends in Refresh’s slot, held hidden on a tab with nothing to refresh, its text
and then its offers’ sentences cut short, never their controls, and a rate limit’s hold
on the line too; and a cold page keeps every row, empty, at its height.
Only a failure, which says what to do, wraps the status row.
Refresh or Fetch and Switch to the head are [text actions](#control-families), a line
tall, as Browse code is, so the freshness line is no taller than its text.
A cold page holds the labels row while the labels are unknown, since the record may
bring some: a record with labels lands moving nothing, and one with none takes the row
and its gap away in the paint that lands it, the one paint that changes the header and
the body together. A record’s labels come with it or its core, and a label’s color and
tooltip, which the repository’s label set may bring later, change no chip’s box.
Measured in Chrome 152 at 560, 420, and 360 px in both themes, every row is 6 px under
the one before it and the freshness line is 18 px, the row of ages’ height; the header
is 229 px with no labels and 255 px with labels or while its record is on its way.
Before, Refresh was a bordered `.btn` that made the line 26 px, an empty 20 px labels
row stood between it and the row of ages, 32 px under that row, and the header was 263
px in every state (mb-2u08). The header’s last row is the pull request’s
[Diff summary](#diff-summary), on every tab, so its counts are at the page’s top and not
inside Changes. The row is held at `--ui-row-height` from first paint, empty until the
comparison is read, and the summary’s header is one line, its breakdown cut short at its
end, so the summary that arrives moves nothing; opened, its tree pushes the tabs down,
as the reader asked.
On every tab but Changes the page reads the comparison once it is idle, as it would for
Changes; on Changes it draws the summary from what the diff read.
It is drawn once for each comparison it shows and kept across tabs.
Measured in Chrome 152 at 980 to 320 px, the row is 24 px from first paint; a summary of
“35 changed files (2 added, 3 removed, 30 modified) +1,234 −3,423” arriving moved no row
and not the tab bar, and kept its row’s 24 px on one line; the row starts on the
header’s content edge, and its toggle hangs 4 px into the gutter, as every Diff
summary’s does. The row adds its 24 px and one 6 px gap to the header.
`tests/dom/github-pull-header-chrome.mjs` holds the measurement, and
`tests/dom/github-pull-page-mount-behavior.js` the row’s order, reads, and disposal.
A tab switch or a poll builds again only the header’s parts whose inputs changed: the
title, the badge, the author, the branch chips, the row of ages, the labels, and each
status control are kept while what they show is the same, so a repaint that leaves a
control as it was does not take its focus, hover, or tooltip from the reader.
`test_the_header_keeps_its_nodes_and_each_avatar_loads_by_its_placement` counts what
each repaint builds.
The Changes body keeps the full pane so a diff has room for Split.
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

Native stack navigation uses the repository snapshot’s verified membership and order, in
the one stack design ([Stacks](#stacks)). A Layers icon and position/total, such as
5/23, open a menu in the reading column.
The menu shows titles, ordinals, and PR numbers, ordered from stack top to base, with
the current member marked.
Its links are created only when opened.
Arrow keys, Home, End, Escape, outside click, and focus return follow the menu pattern.
On a selected PR, Control-N opens the next member toward the stack top and Control-P the
previous one toward its base, with or without Shift; Help lists them in its Pull request
stack group ([Control Chords](#control-chords)). A focused Pulls row keeps `J` and `K`
for its own rows. Editors, dialogs, unknown membership, a header still held over the
loading page, and inactive pages keep their normal keyboard behavior.
Stack endpoints consume the shortcut without moving.
A member selection preserves the current PR tab and clears the previous file selection.
Unknown membership and unavailable optional tooling add no placeholder or setup notice;
known cached membership remains visible during refresh or failure.
Membership has its slot at the right end of the author’s row, under the end of the
title, so its chip, which arrives from its own answer after the page, lands in the row’s
empty end and moves nothing; where the row has no room left for it, the sentence is cut
short at its end. Its menu hangs from the chip’s end of the row.
Measured in Chrome 152 at 980 to 320 px, one stack’s chip is 54.75 px and two stacks’
113.5 px; a late chip moved no part’s start and no row, kept 8 px from the sentence, and
cut the sentence only where it needed the room: at 560 px two stacks cut a long author’s
sentence by 34.88 px, and at 360 px two stacks cut “forker wants to merge 2 commits” by
38.04 px. Its `details` is no taller than the strut it replaces there, since the slot
sets the chip’s own size.

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

A heading belongs to the section it opens, so it sits nearer what follows it than what
precedes it. Inside a text that space is KPress’s, exactly as in a document in either
reading font: 2 rem above an h1 or h2 and 1 rem below, 1.4 rem above an h3 and a
paragraph’s 0.75 rem below.
A heading’s top margin collapses with the block before it, so the space after a
paragraph, list, code block, or blockquote is the heading’s own, or the block’s when
that is larger, as a blockquote’s 1.5 rem is above an h3. The page adds no heading rule.

The top of a text is where a message departs from a document.
A document’s card has 2.5 rem of top padding in KPress’s bands from 48 rem up, and only
an opening h1 gives up its margin to it (`static/styles.css`); any other first block’s
top margin adds to that padding.
A message card is denser, like the comment body on GitHub, which pads 16 px and trims
the first and last margins.
The text’s padding is `--content-padding-y` above and below, and the card head’s inset
at the sides. Since the trim leaves a heading that opens a text only that padding above
it, the padding is at least any heading’s space below.
A header row’s 8 px put an opening h2 nearer the card head than its own paragraph.
`test_a_heading_is_nearer_its_section_than_what_precedes_it` holds the rule, and
`tests/test_github_pull_text_chrome.py` measures it in Chrome against a document’s
frame.

The fallback `md-body` path is not used, because it is a different ramp: one flat code
size and its own heading steps, which would make the same text read differently from a
file.

A text stays inert. The server and `static/inert-html.js` reduce it to the allowlist, no
KPress script loads, and every class in the article is the page’s, chosen by element.
The route’s answer names KPress’s stylesheets, and that list is the same for every text,
so a comment does not choose what the page loads.
Until its render arrives a text shows as plain text in the same face and size.

### Conversation Timeline

The Conversation is a timeline of events: the description, then its comments, reviews,
and commits, in the order the page places them
(`tests/dom/github-pull-timeline-session.js` holds the order).
A commit is an event of the same weight as a comment, so it is not set smaller for being
a commit. It is said the way a card head says a comment:

- **Type:** a commit row is set as a card head is.
  It is set at `--body-font-size` on the head’s line, and its box is that line, with no
  room of its own above or below, in a frame as wide as a card’s that draws nothing.
  Its subject is bold in text ink where a head’s author is, and starts where the
  author’s name does after the avatar, `--github-pull-avatar-size` (18 px), and the
  identity’s gap, `--github-pull-identity-gap` (4 px).
  A card head whose author has no usable avatar keeps the avatar’s box, empty and hidden
  from assistive technology (`authorLabel`’s `slot`), so every head’s name and every
  commit’s subject start at one x. The header and Pulls rows draw no such box.
  “committed” and the age read as a head’s “commented” and age do, with no quieter ink
  or size. The hash is the [GitHub action](#chrome) at a revision’s own
  `--nav-font-size`, one step below the text beside it, as in the
  [Git Commit Summary](#git-commit-summary).

- **Headings:** every event’s heading reads alike: the author, a plain verb in the
  heading’s own type, and the age, “jlevy opened 4d ago”, “jlevy commented 4d ago”,
  “jlevy reviewed 4d ago”, and a commit’s “committed 4d ago”.
  A boxed chip follows the age only where it says a state the verb does not: a review’s
  Approved, Changes requested, or Dismissed, in its status ink, as GitHub marks them.
  A plain review is all in its verb, and a pending one in its “(pending)”, so neither
  has a chip; a chip on every review read “Reviewed” as a status where a comment’s
  “commented” was plain text.

- **Spacing:** one rhythm.
  Every two consecutive events are `--github-pull-rhythm` (20 px) apart, card to card,
  card to commit, commit to card, and commit to commit alike, and so are two review
  comments under Review comments, whose heading sits over the first at the sections’ own
  gap, as every section’s does.
  The space is what the reader sees: a card’s border, and a commit’s text, whose row is
  its line. 20 px is the space between two commits’ text that the owner called good; the
  12 px between cards read as crowded.

- **The line:** one 2 px line in `--border` joins every two adjacent events, down the
  center of the card heads’ avatars and their empty slots.
  Each commit has a solid `--muted` dot on the line at its first line, the shape of the
  history graph’s [commit nodes](#commit-nodes).
  The line starts at the first event, ends at the last, and breaks wherever something
  that is not an event, such as Review comments or a note, stands between two events.
  Commits that answer after the conversation has painted go after everything, so their
  run has a line of its own.

This is the structure of GitHub’s own pull request page, a line down the timeline with a
mark at each commit, drawn in the shell’s tokens and none of GitHub’s assets.
Its tokens are the rhythm and the avatar’s two: the commit row’s start, the line’s x
down the avatars’ centers, and an absent avatar’s slot are derived from the avatar’s
size and the identity’s gap, and the rest of its geometry is the card head’s.

`tests/test_github_pull_timeline_chrome.py` measures it in headless Chrome, in both
places the page puts commits, in both themes and a narrow pane, from the boxes laid out
and the pixels painted, with one head drawn with only its slot.
In Chrome 152 every pair of events is 20 px apart, card border or commit text, in both
themes and at 980 and 420 px.
Before the rhythm, two cards were 12 px apart, a card and a commit 23.5 px, and two
commits 20 px; before a run of commits kept a room outside it, a card and a commit were
16 px apart. Before this rule, a commit was set at 12 px against the head’s 14 px, its
glyphs sat 13 px below the event above, 1 px under its row’s top and 6 px over its
bottom, and nothing joined the events.

In the macOS app’s web view (WebKit 21624.2.5.11.8 on macOS 26.5.2), run through the
WebKit gate’s `webkit-driver measure` (`apps/macos/webkit-gate`) on the same page and
layouts, every one of that test’s layout checks passes in both themes, apart from its
pixel reads, which the driver cannot make: an event card computes to `overflow-x: clip`
and `overflow-y: visible`, and in every gap between joined events WebKit hit-tests the
line’s x to the following event’s connector, which it would not do for a clipped one,
and 9 px beside it to the page.
Each node sits 0.5 px below its first line’s middle there, as in Chrome, and every pair
of events is 20 px apart, as in Chrome.

### Chrome

| Element | Primitive | Why |
| --- | --- | --- |
| Title | `--page-title-font-size`, `--weight-bold` in normal text ink, sans | A pull request’s title is bold in normal text ink wherever it appears ([The Pulls Tab](#the-pulls-tab)), and a conventional-commit prefix that starts it regular ([Titles](#titles)). The number beside it uses normal text ink at the same size, bold ([Pull Request Numbers](#pull-request-numbers)) |
| State, review, and check badge | `.file-header-badge`, in the state’s status ink; a review’s only for a state its verb does not say ([Conversation Timeline](#conversation-timeline)) | A pill means a filter, and a badge is not one. Sentence case, like all chrome, so the badge centers its capitals: `text-box` trims its line to them and the baseline, in a box as tall as its line, pads, and borders, which `test_badges_center_their_capitals_in_the_box_they_had` holds |
| Username | `.actor-name`, bold in normal text ink at the surface’s normal text size | Applies to the author, merger, comments, and reviews; a small circular avatar belongs to that same actor |
| Head and base branch | `mb.mergeRefs`, head → base on a line of its own under the author’s sentence: “forker wants to merge 2 commits”, then “forker:count-to-two → octo:topic” | [Merge Direction](#merge-direction): two remote [ref chips](#branch-chips), slightly smaller than the actor and action by the [chip ratio](#one-ratio), and the one arrow the list uses too. [Which Kind Each Context Gets](#which-kind-each-context-gets) says why remote and never trunk |
| Label | Hairline box with `--radius-tag`, in GitHub’s color for it, its description its tooltip ([Label Colors](#label-colors)) | A name the pull request carries, the corner tag-like chips use, colored as github.com colors it so a label reads as the same label in both places |
| Opened, updated, commented | `metabrowser.formatAge` with relative style, exact time in the tooltip | [Age](#age); condensed navigation uses compact style |
| File of a review comment | Sans, bold, `--nav-font-size` | The diff bar’s path typography. A path is chrome |
| Link, including a check’s action off GitHub | `--link`, underline on hover, the focus ring | As the freshness row’s link is, so a check’s action never reads as the muted description after it |
| GitHub action: View on GitHub, a check’s action on GitHub, a conversation commit hash | `.github-pull-external-action`: `--muted`, with the leading GitHub mark in the same ink; `--link` on hover and focus | Quiet beside the metadata it follows, and the same in each of the three. A check is GitHub’s by the rule that gives a link the GitHub mark, so its look and its mark agree |
| Conversation commit hash | `.git-commit-sha` at its own `--nav-font-size` | A [revision](#git-commit-summary) sits one step below the sans beside it, and a commit row is set at `--body-font-size` ([Conversation Timeline](#conversation-timeline)) |
| Browse code, and a review comment’s file | [Text action](#control-families): a link, or `.github-pull-text-action` on a button where it first serves the pull request’s head | The look of the Link row in both forms, so moving the pin never looks like something else |
| Section title | [`.section-heading`](#section-headings) |  |
| Note about the content | [`.notice`](#notices) | `warning` when a text, list, or hunk was cut or a part could not be read; `error` when Changes cannot be drawn; no severity for the offer of newer changes, which carries its own control |
| A review comment’s earlier lines | [`.fold-expander`](#fold-expanders) on a native `summary` | States its count, and the inverse when open |
| A review comment’s hunk | `--font-mono` at `--mono-block-font-size` | The user’s code, with the diff view’s row tints |
| Empty state | `--muted`, sentence with a period |  |
| Refresh, Fetch, Switch to the head | [Text action](#control-families): `.github-pull-text-action` on a button | The status row is one of the header’s metadata lines, among links such as Browse the checkout, so its controls look as links do and are a line tall; a bordered `.btn` made the line 26 px against the row of ages’ 18 |

Author, action, and relative age share one metadata size and baseline in a header or
discussion card. The bold username uses the normal text ink wherever it names an actor.
The avatar centers independently beside that text baseline.
Compact navigation ages and branch chips retain their smaller chrome sizes.

Author avatars are decorative circles beside the visible username, with fixed dimensions
so image arrival or failure does not move the text.
Images load at low priority and decode asynchronously, and when they load depends on
where they are ([A Repaint Keeps Its Images](#a-repaint-keeps-its-images)). The header’s
avatar is eager: it is at the top of the page, and it is a new image whenever its actor
changes. A Pulls row’s is eager, because only mounted catalog rows can create images,
which bounds what the Pulls tab asks for.
The conversation’s are lazy: its sections are kept across tabs and polls, and an avatar
far down a long conversation waits until the reader nears it.
Missing or unsupported image URLs leave the username readable.
Use the avatar of the named actor: a merged header naming the merger shows the merger’s
image, while the description shows its author’s image.
Only normalized HTTPS URLs on `avatars.githubusercontent.com` are accepted, checked
again before assigning the browser image source.
Anonymous CORS and a no-referrer policy omit credentials and the local page URL. The
browser’s HTTP cache owns image bytes; PR metadata caches retain only URLs.
Document image sanitization remains independent; see [Content Trust](../SECURITY.md).

### Label Colors

**A label is colored exactly as github.com colors it, in our chip’s box.** GitHub gives
each label a color, six hex digits, and a description, and a reader who knows a
repository’s labels by their colors on github.com should find the same colors here.
The chip keeps the size every label chip has: `--ui-small-font-size`, the `0 5px`
padding, the hairline border, `--radius-tag`, and its height, so a colored label is as
tall as a neutral one and the header’s rows keep their heights.

The colors are github.com’s own formula, read from its stylesheets (Primer’s
`.IssueLabel`, on 2026-11-15). The page sets the label’s red, green, and blue, 0 to 255,
and its hue, saturation, and lightness, each rounded to a whole number, as github.com
does, on the chip as `--github-label-r`, `--github-label-g`, `--github-label-b`,
`--github-label-h`, `--github-label-s`, and `--github-label-l`; `github/styles.css`
states the formula once.
The formula’s custom properties are github.com’s under the plugin’s `--github-label-`
prefix, so none shares a name with the shell’s label register (`--label-color`,
`--label-font-size`); the stylesheet maps each to Primer’s name.
Its perceived lightness is (0.2126 R + 0.7152 G + 0.0722 B) / 255.

| Part | Light theme | Dark theme |
| --- | --- | --- |
| Ground | The color | The color at 0.18 alpha |
| Text | Black when the perceived lightness is above 0.453, white otherwise | The label’s hue and saturation, its lightness raised by (0.6 − perceived lightness) × 100 points when the perceived lightness is under 0.6 |
| Border | The label’s hue and saturation 25 points darker, at alpha (perceived lightness − 0.96) × 100, clamped to 0 to 1, so it shows only on a very pale label | The text’s color at 0.3 alpha |

A color that is not six hex digits, or none, is kept as none, and its chip is the
neutral one: `--muted` text on no ground in a `--border` box.
A label’s description is its chip’s tooltip, since it says what the name does not
([Tooltips Add Information](#tooltips-add-information)); a label with no description has
none. The name is the label’s meaning and is always there, so color is never the only
signal.

These are the one place the stylesheet writes `rgb()` and `hsl()`
([Color and Theming](#color-and-theming)): the color is GitHub’s sRGB data and the
formula is github.com’s, so stating it in `oklch` would paint other colors than
github.com does. `test_colors_are_declared_in_oklch` takes out the formula’s two rules
alone and holds that every color they write is computed from a `--github-label-`
property.
`tests/test_github_label_colors.py` holds the properties to the ones github.com
set on 112 colors of six public repositories’ labels.
`tests/dom/github-pull-header-chrome.mjs` (its `labels` part) holds each chip’s computed
ground, text, and border in both themes to the formula and to what github.com’s own
stylesheet computed for a pale, a dark, a very pale, a white, an indigo, and a gray
label, a colorless or malformed one to the neutral chip, and every chip to the neutral
chip’s box.

**A chip never waits for its record to have its color.** A record or a core cached
before label colors names its labels alone, and the catalog vouches for such a record as
current until its pull request changes, so it is never read again.
The repository’s whole label set is cached once, beside its pull requests, and kept
fresh as the native stack snapshot is; the pull envelope carries the set’s entry for
each label its record or core names without a color, and the chip takes its color and
description from it, so the header is colored on first paint whenever the set is cached.
A label with its own color keeps it.
A label the set does not hold, one deleted on GitHub, stays the neutral chip and asks
for the set again once a freshness window; while the set is read the page polls fast, so
the color lands at once.
Its arrival moves no chip and no row, which the same Chrome check holds; it also holds
that a record of bare names, with the set cached, paints every chip as the record’s own
colors do.

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
A conventional-commit prefix that starts it is regular ([Titles](#titles)). A row or
menu item is a link, so the title sets its own ink and weight, and no visited, hover,
focus, selected, or current state changes them.
A pull request’s number is bold wherever it names the pull request
([Pull Request Numbers](#pull-request-numbers)). The number’s line gives the PR number
normal row size and text ink.
Usernames use the same small metadata size and bold normal text ink; the repository
summary above the list is the [navigation metadata line](#navigation-metadata-line).
A row names no branches: the pull request’s page names them, head → base, as
[Merge Direction](#merge-direction) sets them, and the row’s room goes to its title.
A row’s first line is the chevron and the state icon, each in the tree’s icon slot, then
its number’s line: a stack member’s place in its stack, as [Stacks](#stacks) sets it,
the number, and the author, “1/4 · #113 · jlevy”, with the age at the row’s end.
A row not in a stack starts at its number.
The number’s line is one line, so a row is always two, and its parts give way in order:
the author’s name ends in an ellipsis, down to its avatar and a little of the name; past
that the author, with its separator, leaves the line whole; and a place too wide for
what is left is cut short with an ellipsis, the number whole after it.
The author is on the pull request’s page, and the age never gives way.
The second line is the title alone, from the text column, where the number’s line
starts, under the age to the row’s end, cut there with an ellipsis, so a member’s title
has the room a first-level row’s has, less its one indent: 208 px at the default 299 px
pane, where beside the age it had 170. The Pulls column has no tooltips
([Tooltips Add Information](#tooltips-add-information)). Stack membership comes from one
shared repository snapshot, indexed once by PR number; rows make no stack requests, and
enrichment updates retain the row and any focused changed-file tree.

Changed files use the Files tree’s row height, indent, chevron, and inline change stats.
A one-letter change badge replaces the file icon.
A folder chain is one row, and every folder row ends with the line counts of the files
under it, rolled up, open or closed, as in a diff’s [Diff summary](#diff-summary), which
draws its tree on the same model.
Up, Down, J, and K move through the visible rows, with one Tab anchor per file tree.
A file step calls the diff’s public jump API; a held key replaces the address once it
stops, while Enter and a click push it.
A hand-scrolled diff reports its current file through the same public page handle, so
the tree follows without moving the address.
Only the active PR’s file carries the page-selection mark.
Leaving a PR clears that mark while preserving its reader-expanded tree and roving
keyboard anchor. Repeated notices for the same page retain the observed diff file;
explicit file addresses remain selected while their jump is temporarily unavailable.

Expanding a row shows its changed files.
A tree waits up to `FILES_OPEN_HOLD_MS` for the cached list before it paints open, so a
cached list opens in one step at its height; past that, it shows its loading line,
“Listing changed files…” with the shared delayed spinner, until the files arrive, and
draws its first rows whenever they come.
Once rows are drawn, a change to them — a list’s further pages, or a refresh that
changes it — that comes `LATE_ROWS_MS` after the reader’s last press or key is offered
rather than drawn: **Show N more files** or **Show the updated list of N files**, on the
tree’s line, or floating over its top when the line is hidden, so drawn rows never move
without input. A refresh that lists no files is offered as **Show the updated list (no
files)**, and the rows drawn meanwhile keep no line saying there are none; once the
reader asks for the empty list, the tree says “No changed files.”
A read or a refresh that answers that the server no longer holds the list is offered as
**Show the updated list (not listed)**: the drawn rows stay as the files last listed,
breathing while the list is listed again rather than sitting under the loading line.
The offer says what the tree holds, not what the latest answer says, so it stands across
a refresh’s answer that carries no rows, and it is withdrawn once a read brings back the
same files.
**An offer stands in only for a change to drawn rows.** An expanded tree with
none drawn never shows one.
`test_a_tree_opens_once_and_never_grows_without_input` holds both.

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
The shapes differ. In the list, the icon’s accessible name gives the state.
On the page, the same glyph sits beside the title and the text badge below names the
state. Everything goes through `pullStateIcon` and `displayState` in
`builtin_plugins/github/pull-state.js`, so a row and its page cannot disagree.
`test_pull_state_colors_keep_their_hue_and_read_on_both_grounds` holds the hue and a
4.5:1 contrast on both grounds, because a badge sets its word in that color.

### Pull Request Numbers

A pull request’s number, “#455”, is bold wherever it names the pull request, at the
weight of a stack’s position, so a member’s “1/6 · #455” reads as one identifier.
One token sets it, `--pull-number-weight` in the shell’s stylesheet, and every surface
that shows a number takes it:

| Surface | Class |
| --- | --- |
| The pull request page’s title | `.github-pull-number`, after the title |
| A Pulls row | `.github-pulls-number`, on the number’s line |
| A stack menu’s member | `.github-pull-stack-member-number` |
| A Quick Search result | `.search-palette-pull-number` |
| The ref selector, on a pull request’s head | `.source-ref-selector-pull-number`, after “Pull request:” |

The GitHub plugin’s three are one rule.
A number in prose, a commit subject, or a tooltip is text, and keeps its line’s weight.
A stack’s own number, in “Stack #286”, is part of the stack’s label, in the label
register ([Stacks](#stacks)). `test_the_pulls_tab_carries_the_shells_primitives` holds
the rules to the token, and `tests/dom/github-pulls-stacks-chrome.mjs` and
`tests/dom/github-pull-header-chrome.mjs` read each surface’s computed weight in Chrome.

### Titles

A commit’s or a pull request’s title that starts with a conventional-commit prefix sets
the prefix at regular weight and the rest of the title at the title’s own weight, so in
“feat(ledger): chart strategies, range bands and Extended default” only “feat(ledger):”
is regular. The prefix is a type, an optional scope in parentheses, an optional `!`, and
the colon:

- The type is lowercase ASCII letters, as commitlint’s conventional config holds types
  to. A capitalized word before a colon, as in “Docs:” or “WIP:”, is the title’s own
  text.
- The scope is one or more characters other than parentheses, so a list such as
  `fix(ui, git):` counts, as conventional-changelog’s parser reads one, and an empty
  `()` does not.
- It counts only at 16 characters or fewer, colon included, counted in code points:
  `refactor(stack):` counts, and `refactor(stacks):` is part of the title.
- Whitespace and more of the title follow the colon.
  `fix:keep` and a title that ends at its colon have no prefix.

A merge commit, a `Revert "…"` title, and every title that does not match are drawn
exactly as before: the same element holding the same text.

One function splits a title, `titlePrefix` in `static/formatters.js`, and `titleNodes`
and `titleHtml` beside it draw the prefix in a `span.title-prefix`; plugins draw with
`metabrowser.titleNodes`. One rule, `.title-prefix` in the shell’s stylesheet, sets the
prefix’s weight from `--weight-normal`, so no surface sets a weight or writes markup of
its own, and the prefix keeps the title’s face, size, and ink.
The title’s element still holds the whole title, so an ellipsis, a two-line clamp, and a
tooltip that gives the whole of a title cut short all work on all of it.

| Surface | Title element | The rest |
| --- | --- | --- |
| A Pulls row | `.github-pulls-title` | Bold |
| The pull request page’s title | `.github-pull-title-text` | Bold |
| A stack menu’s member | `.github-pull-stack-member-title` | Bold |
| A Conversation commit | `.github-pull-commit-subject` | Bold |
| A Quick Search pull request | `.search-palette-label` | Bold; a match in the prefix is marked bold, as a match in a path is |
| A Commits tab row | `.git-graph-subject` | Regular, the row’s own weight, so the prefix looks as the rest does |
| A commit’s page | `.git-commit-subject.page-heading` | Bold |
| A commit’s tooltip | `.git-commit-summary-compact .git-commit-subject` | Bold |

A plain-text tooltip, such as the whole of a title cut short, has no weights.
`tests/dom/title-prefix-session.js` pins the split, and
`tests/test_title_prefix_chrome.py` reads each surface’s computed weights in Chrome and
holds the one helper and the one rule in source.

### Rows

| Part | Primitive | Why |
| --- | --- | --- |
| Tab | `.tab-btn` in the nav’s `.tab-bar` | [The Tab Bar](#the-tab-bar) |
| Row | `min-height: --ui-row-height`, `--hover-bg`, `--highlight-bg` and `--highlight-bar` when current | [One Row Contract](#one-chevron-one-row-contract) |
| State icon | The tree’s icon slot, `--tree-icon-slot`, around `--icon-glyph`, as the chevron before it, both on the first line before the number’s line | [One Glyph Size](#one-glyph-size) |
| Title | `--nav-font-size`, `--weight-bold` in `--text`, set on the title itself; the second line, alone, from the text column under the age to the row’s end, cut there with an ellipsis, the whole of it on the page it opens | It is the row’s identity, and a pull request’s title is bold wherever it appears |
| Updated time | `metabrowser.formatAge`, at the first line’s end, on the number’s baseline; the page gives the exact time | [Age](#age), with no tooltip ([Tooltips Add Information](#tooltips-add-information)) |
| PR number | `--nav-font-size`, text ink, bold (`--pull-number-weight`) | Shares the title’s primary navigation size, and names the pull request ([Pull Request Numbers](#pull-request-numbers)) |
| Username | `--ui-small-font-size`; `.actor-name`. The repository summary above the list is the [navigation metadata line](#navigation-metadata-line), at `--nav-font-size` | Secondary context stays the same size; usernames remain bold in normal text ink, and on a short line a row’s username ellipsizes, then leaves the number’s line whole |
| Stack place | `.github-pulls-place`, before the number on the number’s line and at its size, “1/6 · #455”, with what it shows set in [Stacks](#stacks); on a line too short for it, cut short with an ellipsis, the number whole | A passive part of the row’s link, from the shared optional snapshot; the stack’s row above it has the icon |
| Stack group | A row of the tree: the chevron, the Layers icon, “Stack #N” in the label register (`.group-heading.github-pull-stack-label`), with no count of its pull requests ([Heading Tallies](#heading-tallies)); its pull requests one `--tree-indent` in | [Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab) |
| Open, Closed, All | `metabrowser.filterControls.groupHtml`, joined and exclusive, the tab’s toolbar in the navigation’s toolbar slot; Open is the default | Small, muted tallies show each filter’s exact catalog total. Zero is visible and unknown is distinct. See [Choosing Among Values](#choosing-among-values). |
| Count | The first line of the [navigation metadata line](#navigation-metadata-line): the numeric total bold ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)), the words in the line’s regular weight, and the bold `.repository-name` in “N PRs on owner/repo,” or just the repository name while the count is unknown, cut short rather than wrapped | Counts describe the repository, set as the Files and Commits totals are. Nothing says how many rows are held: the list continues as the reader scrolls. |
| Reload | Flush right beside Open, Closed, All, in the same toolbar row | The update age stays below the repository summary. |
| Connection | The second, muted line of the navigation metadata line, one live status: the shared small gray spinner and “Fetching pull requests…” only while no rows are shown; otherwise the quiet update age, which breathes while a refresh runs, and actionable copy during failures, which wraps only when it is longer than the pane | Cached rows stay visible and still. See [Refreshing Content](#refreshing-content). |
| Progress below the rows | The navigation’s scan indicator, `.index-progress-spinner` and `.index-progress-text`, in `.github-pulls-progress` with `.mb-delayed-loading`: “~N pull requests fetched” while GitHub’s pages for the filter arrive, or “Fetching pull requests…” while a page is read | One progress language for a crawl, after the quiet period, and only below rows, never over them. It leaves with the filter’s last row. |
| Reload | `.btn` | Reload checks GitHub for updates. See [Control Families](#control-families). |

A row is two lines and one target, because a pane is narrower than its parts: first the
chevron, the state icon, and the number’s line, a stack member’s place, the number, and
the author, with the age at the row’s end on its baseline; then the title alone, from
the text column under the age to the row’s end.
The title comes first in the link’s text, so the row’s accessible name leads with it.
It is one link, so a new tab and a copied address are the browser’s own, and all of its
text is text: GitHub’s users write it, and none of it reaches markup or a style.

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
Grouped by stack, a stack’s row is a stop of its own that opens nothing, and Enter,
Space, Right, and Left open, close, enter, and leave it as a folder’s
([Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab)). `J` and `K` move the
rows with or without Shift; walking a pull request’s stack is Control-N and Control-P
([The Pull Request Page](#the-pull-request-page)). Help reads the `pull-requests` and
`pull-stack` groups of the shortcut registry, and no surface here names a key.

## Stacks

**A native GitHub stack is named, placed, and listed one way wherever it appears:** the
pull request page’s stack button and menu, a Pulls row’s place, and the Pulls tab’s
stack groups. The words come from one place, `builtin_plugins/github/pull-stacks.js`
(`stackLabel`, `stackPosition`, `stackPositionHint`, `stackCaption` for a Pulls row’s
place, `stackGroupHint` for a stack group’s row, and `stackMenuOrder`), and the look
from one set of classes in the GitHub plugin’s stylesheet on the shell’s tokens, so no
surface keeps a copy of either.

| Part | Primitive | Where |
| --- | --- | --- |
| Label, “Stack #N” | `.group-heading.github-pull-stack-label`: the shell’s [group heading](#groups-in-a-menu), so the label register (`--label-color`, `--label-font-size`, `--label-font-weight`, `--label-letter-spacing`, `--label-text-transform`): gray, all caps, and tracked | The stack menu’s heading; a stack group’s row in the Pulls tab |
| Position, “2/4” | `.github-pull-stack-position`, tabular, at the pull request number’s weight (`--pull-number-weight`); on the stack button, after the Layers icon, `.github-pull-stack-icon`, at `--icon-glyph`, and after its stack’s number when the pull request is in another stack too, “⧉300 2/2” | The stack button on the page, at the right end of the author’s row; a Pulls row’s place, before its number, with no icon |
| Member row | Its position, bold; its title, bold in normal text ink; its `#number`, bold ([Pull Request Numbers](#pull-request-numbers)); and on the current pull request a check, `aria-current="page"`, and the Pulls list’s current-row mark, `--highlight-bg` and a 2px `--highlight-bar` at its left edge | The stack menu |
| Stack group row | The registry’s chevron, the Layers icon, and the label, with no count, since its pull requests are the rows under it ([Heading Tallies](#heading-tallies)) | The Pulls tab |

- **Label.** A stack is “Stack #N”, with GitHub’s number for it, in the label register:
  the register the menu’s heading has, so the menu’s heading and a stack group’s row are
  one class, and nothing in the GitHub plugin restyles its type or ink.
  In a menu it starts on the menu’s row inset, as every group heading does; in the Pulls
  list a stack’s row starts on the list’s row inset, where every first-level row starts,
  so its label sits in the title’s column.
- **Position.** A member’s place is its position counted from the stack’s base, as
  GitHub numbers it, over the stack’s size: “2/4”. A pull request in more than one stack
  shows each position, separated by a middle dot, and names every stack but its own by
  the Layers glyph and its number before its position, `.github-pull-stack-other` at the
  text’s size: “3/4 · ⧉300 2/2”, where ⧉ is the glyph.
  A number alone, “#300”, read as the pull request number on the same row.
  Its own stack is its only stack, the one a group places it under, or else the first
  GitHub lists. On the page a pull request in more than one stack has a stack button for
  each, and each names its stack, “⧉286 4/4” and “⧉300 2/2”, since no button is the
  page’s own stack; two bare positions told the stacks apart only by their tips
  (`namedStackPosition` in `pull-stacks.js`). In one stack the button is the glyph and
  the bare position, “⧉3/4”.
- **Ink.** The position is in normal text ink wherever it appears: in a Pulls row’s
  place, the ink of the number it comes before, on the stack button, and in a member
  row. A member row is a link, so its position, title, and number each set their own ink,
  and no link, visited, hover, focus, or current state changes them; a part that set
  none would take the link’s blue.
- **Order.** A stack’s members are listed top of the stack first, the order of
  `stackMenuOrder`: the menu’s rows and a stack group’s rows in the Pulls tab are one
  order.
- **Links, hover, and focus.** A member row is a link to its pull request and a menu
  item, with the menu’s hover.
  The current member is marked as the Pulls list marks its current row, `--highlight-bg`
  and the 2px `--highlight-bar`, drawn inset since a menu row has no border, and keeps
  that mark hovered or focused; focus on any member shows as the header’s link ring.
  The menu’s keys are [Keys in a Menu](#keys-in-a-menu)’s: every way it opens, a press,
  Enter, Space, `↓`, or `↑`, puts focus on the current member, and Escape gives it back
  to the button. A stack group’s row is a row of the Pulls tree, not a link, since no
  page stands for a stack: it hovers, takes the focus ring, and takes the pointer as a
  pull request’s row does, and a press opens or closes it as a folder’s does.
- **Tips.** The position’s tip names the stack and the place: “Stack #286, position 3 of
  4”, every stack of a pull request in two, joined by semicolons.
  The stack button carries it, as its glyph and position do not name the stack, and its
  accessible name is “Navigate” before it.
  In the Pulls column, which has none
  ([Tooltips Add Information](#tooltips-add-information)), the glyph in a row’s place
  has no words of its own, and the place’s accessible name names each stack, “Stack
  #300, position 2 of 2”. A stack group’s row’s accessible name says its size, how many
  the list holds when that is fewer, and how many of those sit under an earlier stack:
  “Stack #286, 4 pull requests, 3 in this list, 1 under Stack #290”.

### Stack Groups in the Pulls Tab

**The Pulls tab always groups by stack** once the repository’s stacks are known; there
is no option to turn it off.
A Group by stack chip in the toolbar fit in no form: at the default pane width, 299 px,
the worded chip reached 36 px past the pane and a glyph-only one 7 to 17 px, where the
toolbar, the Show group and Reload, has 23 px to spare.

- **Rows.** Each stack with a pull request in the list has a row, open by default, and
  under it, one tree level in, the stack’s pull requests that the list holds, in the
  stack’s order. Each keeps its own changed-files toggle, a level further in.
- **Stack order.** The stacks come in the order of their first pull request in the list,
  so the list’s own order, newest first, still decides which comes first.
  The pull requests in no stack follow the stacks, in the list’s order.
- **Shared membership.** A pull request in two stacks sits once, under the first of them
  in that order, and its place names the other.
  A later stack’s row’s accessible name still counts it among the pull requests the list
  holds and says where it sits.
  A stack all of whose listed pull requests sit under earlier stacks has no row; their
  places name it.
- **Unknown stacks.** Stacks are optional and arrive on their own; nothing waits for
  them. Until a snapshot is known for the list’s own GitHub account, while none of the
  list’s pull requests is in a stack, or when the stacks cannot be read, the list stays
  flat, as it was before stacks: the rows and the pull request page say nothing of
  stacks either. A snapshot kept through a failed or expired refresh still groups, as the
  places and the stack menu still show it.
- **Keys.** A stack’s row is a row of the tree, as a folder is: `J` and `K` stop on it
  and open nothing; Enter and Space open or close it; Right opens it, or goes to its
  first pull request; Left closes it, or from a pull request in it whose files are
  closed, goes to it. An address that names a pull request in a closed stack opens the
  stack. A grouped list’s Tab stop, until the reader moves it, is its first row.
- **Scroll.** A grouping that arrives at the top of the list keeps the top, so its first
  stack’s row shows; elsewhere the row the reader is reading keeps its place, and a
  stack’s row can be that row, so opening one keeps its header still.
- **Read ahead.** An open reads ahead the pull requests a key reaches next as drawn, a
  stack’s row passed over, and the first pull requests drawn.

`tests/dom/github-pulls-stack-groups-session.js` runs the grouping, the keys, and what
an open reads ahead against the production code on the server’s recorded answers; mounts
the panel to drive its handle’s Space, Right, and Left and a press on a stack’s row, and
print the tree’s roles and places; and mounts the page’s stack menu to hold that the
groups list its order.
`tests/test_github_pulls_stacks_chrome.py` measures in headless Chrome, against a
running server with two native stacks, that a stack row’s header and the stack menu’s
heading resolve to the same label tokens, that a stack’s row shows its label alone, with
its size in its accessible name, where a stack’s row and its pull requests start, that
the two kinds of row hover and focus alike, that the toolbar fits the default pane with
room to spare, that real keys and a press move focus and open and close a stack, that a
member’s changed files are a level further in, that the first stack’s row is in view
after grouping arrives and after Left then Right, that a member’s place is on its
number’s line, before the number, in the number’s ink, and names another stack by its
glyph, that a member’s row draws no stack icon and its title has a first-level row’s
room less its indent, and that the menu lists the group’s order with its positions in
text ink.
`tests/dom/github-pull-header-chrome.mjs` lays out members’ rows from 420 px to
the 180 px minimum and holds that a place arriving moves nothing on its row’s title line
and leaves the title its width, that it sits before the number, which shows whole, that
nothing ends past the row, and that one stack’s place shows whole and, at 300 px and
wider, keeps its row two lines.
`tests/test_github_stack_design.py` holds the source to one label class and one place
for every stack word.

## Keyboard Shortcuts

This section is the one reference for which key does what, and why.
Help, the Shift reveal, the other documents, and the code’s comments link here rather
than restate it. `tests/test_keymap.py` holds the table below to the keys the registry,
the manifests, and the built-in plugins bind, so the two cannot drift.
How a key is matched, named, and drawn is under [Keyboard Keys](#keyboard-keys) and
[Keyboard Commands and Help](#keyboard-commands-and-help).

### The Rules

- **Letters for known meanings.** A letter names something a reader can guess and keep:
  `F` for Files, `P` for Pulls, `H` for commit History, `T` for the file finder, `U` for
  up. A letter means the same thing wherever it is live, except in an open menu with
  focus, whose rows’ own letters come first ([Keys in a Menu](#keys-in-a-menu)).
- **Reusable semantics.** Some letters are verbs that apply wherever their meaning does,
  as Vim’s motions do.
  `J` and `K` move down and up a row in every row list.
  Control-N and Control-P go to the next and previous item one level up: today the pull
  requests of a stack, and on any later page with its own next and previous, that
  page’s. `V` and `S` switch a file between its rendered view and its source, whatever
  its tabs are called.
  A page with a natural next and previous uses Control-N and Control-P, a rendered view
  is always `V`, and no other meaning takes those keys.
- **Numbers for situational items.** Links and one-off actions that depend on what the
  screen shows, such as the Files tab’s filters or a pull request’s Refresh, take `1`,
  `2`, `3`, and on, in reading order, up to `9`. A tenth and later get no key: no `0`,
  no letter, and no wrap-around.
  Numbers are positional, so `1` reaches a different control on a different screen; Help
  says so, and the Shift reveal shows what each reaches now.
  One mechanism numbers them, the registry’s `attachNumbered()`, which the shell calls
  directly and plugins call through the shortcut surface, so no surface picks its own
  digits.
- **No key on an ancillary item.** Copying a path, a revision, or a hash; a per-row or
  per-file affordance, such as a changed file’s View file or its Rendered | Source
  chooser, of which a page has many; and a control that shows only on hover take no key.
  Each stays reachable by pointer and Tab.
  A key goes on a major tab or a major button.
- **One key, and Control only for next and previous.** Every shortcut is a single key
  but Control-N and Control-P ([Control Chords](#control-chords)), Shift changes
  nothing, and Command, Option, and every other Control chord stay the browser’s
  ([Binding Grammar and Accessibility](#binding-grammar-and-accessibility)).

### Scopes and Collisions

- **Shell letters are reserved everywhere.** `F`, `P`, `H`, `T`, `J`, `K`, `U`, and `W`
  keep their meaning even where they do nothing, so a letter never means one thing on
  one screen and another elsewhere; only an open menu with focus puts its rows’ letters
  ahead of them ([Keys in a Menu](#keys-in-a-menu)). Control-N and Control-P reserve no
  letter: a view’s key is one letter alone.
  A manifest whose view takes one is refused: the loader rejects it, the plugin does not
  load, and `metab --doctor` reports why.
  The plugin shortcut surface refuses one too, with a console warning, and the control
  works without a key.
  A different case is two views of one kind declaring the same free letter, in one
  manifest or across two: both load, the first in tab order keeps the letter, the later
  view is served without it, and `metab --doctor` reports the lost key.
  `src/metabrowser/keymap.py` holds the table, and also reserves `1` to `9`, which only
  the numbering hands out.
- **Tab letters are scoped to their tab bar.** A tab with a reusable meaning takes its
  letter, `V` or `S`. Any other tab takes the first letter of its label, or when that is
  taken, the next distinctive free letter of its label, never a shell letter (a menu
  row’s letter may be one: [Keys in a Menu](#keys-in-a-menu)), and declares it beside
  the label rather than deriving it, so a rename never moves a key.
  Two tabs on one screen never share a letter; two bars never shown together may, as
  Charts and Conversation share `C`.
- **A collision is settled by the newcomer.** It takes the next free letter of its own
  label. Checks took `E` this way: `C` is Conversation’s, `H` is History, `K` moves a row
  up, and `S` is Source.
- **Numbers are scoped to the screen.** The live numbered controls, the navigation
  pane’s before the main pane’s, top to bottom, are `1` to `9` in that order.
- **An open menu’s letters are scoped to it.** While a menu whose rows have letters is
  open and has focus, those letters choose its rows, the one exception to the rules
  above ([Keys in a Menu](#keys-in-a-menu)).

### The Keymap

| Key | Meaning | Live while | Kind |
| --- | --- | --- | --- |
| `?` | Help | Always | Punctuation, by convention |
| `T` or `/` | Quick Search, the file finder | Always | Letter |
| `F` | The Files tab | Always | Letter, main tab |
| `P` | The Pulls tab | The tab is drawn: a hosted origin | Letter, main tab |
| `H` | The Commits tab: commit History | Git discovery found a repository | Letter, main tab |
| `J` or `K` | Down or up a row | A tree, Commits, Pulls, or changed-file row has focus | Reusable |
| `Control-N` or `Control-P` | Next or previous item one level up: the pull requests of a stack | A pull request in a stack is open, outside text fields | Reusable, Control chord |
| `U` | Up: the parent folder | A file, or a folder below the root, is shown | Letter |
| `W` | The branch or tag switcher | A mirror’s pin is served | Letter, GitHub’s convention |
| `V` | The rendered view: Document, Preview, Tree, or Log | A file’s tab bar is shown | Reusable, view tab |
| `S` | The source: Source, or Raw JSON | A file’s tab bar is shown | Reusable, view tab |
| `C` | Charts | An agent log is shown | View tab |
| `O` | Overview | A folder is shown | View tab |
| `M` | Treemap, from its map | A folder is shown | View tab |
| `C` | Conversation | A pull request page is shown | Page tab |
| `G` | Changes, from chan-*g*es | A pull request page is shown | Page tab |
| `E` | Checks, from ch-*e*-cks | A pull request page is shown | Page tab |
| `L` | Diff layout: Split or Unified | A diff with a layout control is shown | Letter |
| `1`–`9` | The numbered links and actions on this screen, in reading order | A numbered control is shown | Number |

A menu’s row letters are live only while that menu is open and has focus, so they are
not in the table: Group by’s `N`, `A`, and `T` choose No grouping, By age, and By file
type ([Keys in a Menu](#keys-in-a-menu)).

What is numbered, in reading order, each only while it is shown:

| Screen | Numbered controls |
| --- | --- |
| The Files tab | Group by, Modified within (Any age), and File type (Any type), open or closed as the filter drawer is; a Git pin has no Modified within |
| The Pulls tab | Open, Closed, and All, then Reload, which keeps its number while it waits |
| A pull request page | View on GitHub, Browse code, Refresh or Fetch, Switch to the head, and Browse the checkout |

The navigation pane’s numbers come first, so a pull request page’s numbers start at `5`
beside the Pulls tab and at `4` beside the Files tab, its drawer open or closed (`3` on
a Git pin).

The keys and buttons that have no key, and why: every copy control, ancillary; a changed
file’s disclosure, View at base, View file, and Rendered | Source chooser, per-file; the
Metabrowser menu, print, retry, and the freshness row’s Reload, rare.

### Browser and App Keys

A key held with Command, Control, or Option belongs to the browser, and in the macOS app
to the app’s menus, but for the two [Control chords](#control-chords) the keymap lists.
No other shortcut uses one, and no page handler takes one: a handler that cancelled a
chord would keep it from the browser, and the app’s web view hands every key to the page
before its menus. `tests/test_modified_keys.py` lists each `keydown` handler and what
leaves chords alone in it.
The other exception is Option-Tab inside a dialog or an open menu: its focus trap keeps
it, because Safari moves focus with Option-Tab.

| Key | Meaning | Where |
| --- | --- | --- |
| Command-R (Control-R or F5 elsewhere) | Reload | Everywhere, whatever has focus |

Command-R always reloads.
In a browser it is the browser’s own Reload, in the page, a tree row, Quick Search’s
field, Help, or an open menu alike; the `modified` part of
`tests/dom/key-reveal-session.js` presses it in each of those places.
In the macOS app it is View > Reload Page, which is never disabled in a folder window:
while the status view covers the page it loads the page again, starts the server or
waits for the start under way, or, after the server failed, restarts it as Retry does
([apps/macos/README.md](../apps/macos/README.md#the-window) has each case).
The app’s other keys are the standard ones of its menus: Back and Forward are Command-\[
and Command-\], and Restart Server is Command-Option-R.

### Control Chords

Control-N and Control-P are the only chords the registry binds.
They walk a pull request’s stack: Control-N to the next member toward the stack’s top,
Control-P to the previous one toward its base.

- **Why these two.** The letters alone are worth more to the keymap than one walk
  through a stack: `N` is free, and `P` opens the Pulls tab.
  With Control they mean next and previous in Emacs, readline, and the macOS text
  system, which moves a field’s caret down and up a line with them, so the chords keep
  the meaning they have elsewhere.
- **Why Control, and where it reaches the page.** On macOS, Command is the command key:
  the macOS app’s menus and the browsers there give Control with `N` or `P` no command,
  so both chords reach the page.
  On Windows and Linux, Control is the browser’s command key.
  Chrome keeps Ctrl+N for a new window, and a page never sees it, so there only Ctrl+P
  walks the stack, in place of the browser’s Print while a stack’s pull request is open;
  Print stays in the browser’s menu.
- **What the registry allows.** A binding declares Control with `control: true`, and
  only with `N` or `P` (`CONTROL_CHORD_KEYS` in `static/keyboard-shortcuts.js`). The
  chord matches Control held alone: Alt or Meta with it makes another chord, and AltGr,
  which reports Control and Alt, types its character.
  It never matches in a text field, even for a command that opted in, since the field
  moves its caret with it.
  Shift changes nothing, as for every key.
  A chord reserves no letter, since a view’s key is one letter alone.
- **How it is written.** Help, the Shift strip, and a badge write a chord as its
  platform does, `⌃N` on macOS and iOS and `Ctrl+N` elsewhere; it is spoken “Control N”
  and announced as `Control+N` ([Canonical Key Names](#canonical-key-names)).
- **Another chord** is a design decision made here first.
  It must keep the meaning its chord has elsewhere and take no command from the
  platform, on macOS at least.
  Command and Option stay the browser’s and the app’s.

### Help and the Reveal

Help lists the letters by meaning, group by group, and the numbers once, in an “On this
screen” group: `1`–`9`, “Numbered links and actions,” with the note that the numbers are
not fixed. It gives no digit a fixed meaning.
The registry marks the numbers’ command `situational`, so every surface renders them as
that one run, and no surface special cases them.

Holding Shift reveals the keys in place: each live letter’s control and each numbered
control carries its keycap, and the strip lists the common letters.
The keycaps ease in on the [reveal motion](#reveals) and go at once when Shift is
released. [Badge Targets and the Shift Reveal](#badge-targets-and-the-shift-reveal) has
the mechanism.

### Plugin Keys

Plugins follow the same rules, through two declarations:

- A view of a multi-view kind declares its tab’s letter as `key` in its manifest
  `[[view]]`: `v` for a rendered view, `s` for a source view, and otherwise a letter of
  its label.
- A plugin control takes a key through `metabrowser.shortcuts.attach()`: a letter for a
  known meaning, or `numbered: true` for a situational link or action, which then takes
  its number from its place on screen with the shell’s numbered controls.

A manifest view key that takes a reserved letter keeps the whole plugin from loading,
while a letter already held by an earlier view of the kind only costs the later view its
key ([Scopes and Collisions](#scopes-and-collisions)). A reserved letter passed to
`metabrowser.shortcuts.attach()` is refused with a warning.
[Keyboard Shortcuts in docs/plugins.md](plugins.md#keyboard-shortcuts) has the API.

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
events. They never match while Alt or Meta is held, nor while Ctrl is unless the binding
is a [Control chord](#control-chords), which never matches in a text field; and inside a
text field Shift with an arrow, `Home`, or `End` belongs to the field, where it extends
the selection. They prevent browser behavior only after an enabled handler reports that
it acted.

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
A main tab’s letter opens the tab and then focuses the panel’s roving row; a view tab’s
letter selects the tab and leaves focus where it was; a filter’s number opens its menu,
and the drawer that holds it, and focuses the checked row; `W` opens the branch list and
focuses its filter; and `U` opens the parent folder.
View tab letters are commands in a permanent `view-tabs` scope below `global`, one per
letter, held for the bar the main pane commits and never for one still staged; the
keymap check keeps them off the shell’s letters.

A situational control is numbered with `attachNumbered(element, {activate})` instead of
a letter. Its number is its place among the live numbered controls in document order,
which the shell’s layout makes reading order, read when a number is pressed or shown;
the first nine are `1` to `9`, and the rest have none.
The numbers are one command, `numbered`, in `global`, registered while any control is
numbered and marked `situational`, so its presentation is the run `1`–`9` and Help
renders it as such. A numbered control carries no `aria-keyshortcuts`, since its number
is not its own.

Holding Shift alone outside a text field for the hold threshold reveals the keys: the
root gains `data-key-reveal`, each live command’s first live target carries one
`.kbd.kbd-badge` keycap, hidden from assistive technology, and the shortcut strip shows
a second layer listing the `reveal` surface’s live commands, with every binding of an
item that combines several, such as Control-N or Control-P. A key the registry handles
keeps the reveal and moves the badges to what is live after it; any other key, a chord,
even a Control chord the registry handles, a modifier, a pointer press, a wheel, the
window losing focus, a hidden page, focus entering a text field, or a lost `keyup` ends
it. Another key within the threshold, or pointer travel past the slop, keeps the reveal
from starting, so `?`, capitals, Shift+wheel, and Shift+click keep their meaning without
a flash.
The reveal never calls `preventDefault()` and never announces itself; badges and
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
- **Hover-revealed controls take no key.** A control that appears only on hover or
  focus, such as either copy button, is ancillary
  ([Keyboard Shortcuts](#keyboard-shortcuts)), so it is never a badge target and the
  reveal never has to show it.
- **The revealed strip** is the same yellow, with `--text` and keycaps in a badge’s
  paint. Its layer sits against the strip’s bottom edge and grows upward over the panel,
  which neither reflows nor scrolls; the panel’s pinned headers and open menus stay
  above it.
- **Contrast.** Everything the reveal paints keeps 4.5:1 in both themes: a badge as
  composited over each surface a target sits on, and the strip’s labels and keycaps on
  the yellow, where `--muted` would not.
  The ratios are recorded beside the tokens in `static/styles.css`, and
  `tests/test_design_vocabulary.py` recomputes them.
- **Motion and print.** Badges and the strip ease in on the [reveal motion](#reveals),
  appear at once under `prefers-reduced-motion: reduce`, and go at once when the reveal
  ends. A badge that stays on its target while the badges move after a key keeps its
  node, so it does not fade in again.
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
In the file tree, as in the Pulls tab, a held key selects each row and replaces the
address as it reaches it, but opens only the row it stops on: when the key is let go, or
120 ms after its last repeat.
In the file tree a repeat slower than that opens each row as it reaches it, for the rest
of the hold. A single press opens its row at once.
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
- semantic bindings, each one key, or a [Control chord](#control-chords) declared with
  `control: true`, with no other modifier policy, and an explicit repeat policy;
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
Pull request rows show the title first, with the PR number, bold
([Pull Request Numbers](#pull-request-numbers)), and state below it.
The accessible option name includes that context.
In a GitHub repository, a leading `#` scopes results to PRs.
The empty prefix lists recent PRs, digits match number prefixes, and words match titles.

Use the same arrow, Enter, and Escape behavior for every result type.
Keep the active option selected by identity as providers return, and open the result
through its normal navigation route.

File results lead, and pull requests follow as their own group.
Files answer from memory and pull requests from the server about 110 ms later, so the
later group is appended below the painted rows instead of ranked in among them, and a
late answer never moves a file row or the selection.
Files keep the whole result cap, and pull requests have twenty rows of their own after
them, so a full file group does not crowd out pull requests and a file search is not cut
short for a group that matches nothing.

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
Where an icon reserves a column in a palette or menu row, or a file identity’s, the
alignment box around it is `--icon-box`, 16px — one step wider than the glyph, so the
mark sits optically centered.

A tree row’s leading slot is the glyph’s own width, `--tree-icon-slot`, which is
`--icon-glyph`, 14px: a folder’s or a container’s chevron, a file’s type icon, a change
letter, and a Pulls row’s chevron, state icon, and a stack’s Layers icon all take it, so
chevrons and icons make one column and the names after them line up.
The chevron is `--toggle-chevron-size`, 12px, and sits 1px in, and a file icon fills the
slot, the row’s 6px gap from its name.
At 16px a Files name started 22px from the row’s content edge and a Pulls title 44px,
past two slots; at 14px they start at 20 and 40, and a pull request’s title is 4px
wider. `tests/test_files_tab_chrome.py` and `tests/test_github_pulls_stacks_chrome.py`
measure the slots and where the names start in Chrome.

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
A button that shows only on hover is ancillary, so it takes no shortcut
([Keyboard Shortcuts](#keyboard-shortcuts)), and the Shift reveal never marks one.

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
Opening one puts focus on its checked row, and closing it gives focus back to the
trigger ([Keys in a Menu](#keys-in-a-menu)). The trigger uses the shared Lucide
disclosure chevron at the standard chrome glyph size, rotated downward; do not
substitute a text caret or shrink it to fit the label.

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
The one exception is a joined group in a navigation toolbar, whose pane can be dragged
narrower than a short set: while its whole line cannot hold it joined, it takes the
cluster layout, and it takes the joined layout back once its line can.
`filterControls.bind` keeps every such group fitted, and `data-fit="wrap"` on the group
is how it asks for the cluster; the Pulls tab’s Show group is one
([Navigation Toolbars Wrap](#navigation-toolbars-wrap)). A `.chip-menu` costs a click to
see the options but stays one trigger wide however many there are, so use it when the
set is unbounded or the pane cannot afford the full group.

The nav filter bar uses dropdowns throughout: six age windows and six size steps as
segmented ramps left no room for anything else in a 300px pane.
The groups stay part of the family for surfaces with fewer, shorter values.

Age and file-type rows carry right-aligned file tallies in tabular numerals.
Fixed age windows remain in chronological order and show cumulative counts.
Open-ended type values are ranked by frequency and capped, so the menu cuts the long
tail rather than an arbitrary alphabetical slice.

A dropdown may lead with ordered named **preset sections** — shorthands standing for the
full set of values beneath them.
Each nonempty section is a menu group ([Groups in a Menu](#groups-in-a-menu)): a
`.group-heading` at the menu’s row inset naming a `.menu-group`, which draws the divider
above it, and a plain separator before the raw list.
The navigation type chooser uses broad group presets first, families grouped under the
recommended file-type definitions’ group labels second, and canonical/raw extension rows
last. Groups are listed Documentation first
([Grouping the Files Tree](#grouping-the-files-tree)). Empty groups and empty presets
are omitted; an empty preset must never alias the Any state.
A preset is checked only when every value it names is selected, so a half-covered group
never claims to be on, and a selection that is exactly one preset shows by its name
rather than as `.md +21`. Other remains a family-section heading rather than a broad
preset because its unknown extension population is open-ended and cannot be represented
by a fixed token list.
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

### Grouping the Files Tree

**The Files tab’s filter row holds Group by and Show ignored; the three filters sit in
the drawer behind the chevron.** Group by splits the tree into sections and removes
nothing, so it needs no drawer and no badge.
Show ignored follows it: its tick states its own direction, so the row shows its state
and the badge need not.
A Git revision has no gitignored entries, so its row has no Show ignored.
The drawer holds Modified within, File type, and Minimum file size, and the chevron’s
badge counts the ones set.
Clear sits beside the chevron and shows while any filter is set, Show ignored included;
it resets them all, Show ignored back on, and keeps the grouping.

- **Values.** No grouping is the default and shows the one tree.
  By age splits by modification time and By file type by the registry’s display groups.
  Each row reads as the closed trigger does when it is chosen, so the menu and the
  trigger never name one value two ways.
  A Git revision has no modification times, so it offers no By age.
- **Groups.** Age groups are disjoint bands cut from Modified within’s windows: Live,
  then Past hour, Past day, Past week, and Past month, each holding only what the
  windows before it do not, then Older.
  File type groups are Documentation, Code, Data, Archives, Media, and Other, which
  takes every file the registry does not recognize.
  A group the filters leave empty is not shown.
- **Sections.** Each section is a group heading in the menu group pattern, the group’s
  name with its file count beside it ([Heading Tallies](#heading-tallies)), over a full
  tree of the group’s members after the filters.
  The heading starts on the tree’s row inset, 12 px, as a menu’s starts on its rows’,
  and names the section and its tree; sections after the first draw the divider above
  themselves. A folder opened inside a section lists only that group’s members.
  A section is a fixed heading that never closes, where the Pulls tab’s
  [stack group](#stack-groups-in-the-pulls-tab) is a row that opens and closes, and the
  difference is deliberate: a grouping splits the whole tree into sections, while a
  stack gathers some rows of one list like a folder.
- **One order.** Every surface that lists the file type groups lists them in one
  presentation order, Documentation first: the type filter’s Groups and sections, Group
  by, and File Overview’s type table and bars.
  The order is `FILE_TYPE_GROUP_DISPLAY_ORDER` in `file_type_filters.py`, published to
  the browser as `fileTypes.displayGroups`. The registry keeps its own order, Code
  first, because a group’s `order` is part of the File Rollup Format’s fingerprinted
  definitions that rollups and conformance fixtures follow.
- **Symbolic links.** Grouping keeps them, as No grouping does: By file type puts a link
  in Other, since a link has no file type, and By age places it by its own modification
  time. A file filter set beside the grouping leaves links out, as it does without one.
  On a Git pin a link is a blob, counted and grouped by its name as a file is.
- **Keys.** The drawer’s filters keep their numbers while it is closed.
  Its triggers are inert then, so the numbers sit on stand-ins beside the chevron, in
  the order the triggers take when it opens, and a filter’s number opens the drawer with
  its menu. Group by’s rows take `N`, `A`, and `T` while its menu is open and has focus
  ([Keys in a Menu](#keys-in-a-menu)).
- **Persistence.** The choice is transient view state, as the filters are: every page
  starts with No grouping.
- **Waiting.** A choice shows at once: the trigger reads it in the frame it is made,
  whatever the groups then take, because the bar renders from the choice before any
  request starts. The tree on screen stays while the groups load, and the trigger does
  not breathe: it reads the choice in the link’s ink on the accent ground, and only
  primary ink breathes ([Refreshing Content](#refreshing-content)). For a choice’s first
  sections, the tree on screen is the arrangement the reader left, so past
  `--loading-state-delay` it dims to `--loading-dim-opacity`, and the navigation’s scan
  row says what is coming, “Grouping by file type…” or “Grouping by age…”, in its
  spinner and words. The dim is the tree’s dimmest level, `--dimmed-content-opacity`’s
  0.45, and a row already dimmed, an ignored file or an empty folder, is held there
  rather than dimmed twice: at 0.45 of 0.45 its name read 1.54:1 in Chrome, near
  invisible, where it reads 2.86:1, as at rest.
  The metadata band and notices above the tree keep their ink, and an answer inside the
  quiet period shows none of it.
  The scan row rather than a metadata line holds the words because a metadata line takes
  its line box the moment it is drawn: a choice answered inside the quiet period would
  push the tree down a line and back.
  A newer choice, a filter change, or No grouping cancels the load on its way at once,
  and its answer is never painted.
  Pressing a grouping’s row, or moving to it with the arrow keys, asks for that grouping
  ahead of the choice; opening the menu asks for nothing, since a reader chooses at most
  one grouping and often none.
  A file change keeps an answer asked for ahead rather than dropping it: the choice
  takes it, since it comes sooner than a new one, and then refreshes.
  A reveal made while a choice’s first sections are on their way
  ([Navigation Reveals the Item](#navigation-reveals-the-item)) waits for them, and
  lands in its section once they paint.
- **Refresh.** When files change, the sections refresh in place, in one frame: each
  keeps its heading and updates its count, a group that fills or empties appears or
  goes, the folders open in a section stay open, and the scroll position and the focused
  row are kept. A folder whose cached children a write dropped is fetched before the
  paint. A refresh that fails keeps what is shown and retries with a backoff.
  A refresh asked for while a choice’s first sections are on their way waits for them
  and runs once they paint; started at once, it would discard them and begin again, and
  on a folder whose files keep changing each refresh would restart the wait.
- **Width.** The row fits the default 299 px pane at its widest, “No grouping” with
  Clear and the badge showing, in the default font set.
  The badge sits against the chevron to make that room; the measurements are beside
  `.nav-filter-bar-end > .chip-badge` in `styles.css`. In a narrower pane, or in the
  system font set, the row wraps: Show ignored moves down, then Clear and the chevron
  ([Navigation Toolbars Wrap](#navigation-toolbars-wrap)).

The server decides membership, order, and counts (`/api/tree?group_by=` and `?group=`,
`metabrowser/tree_groups.py`), pinned by
`tests/golden/cli-api-tree-groups.tryscript.md`; the browser’s requests and sections run
browserlessly in `tests/dom/files-group-by-session.js`, and its refresh in
`tests/dom/group-by-refresh-behavior.js`; and `tests/test_files_tab_chrome.py` measures
the row, the drawer, the numbers, the sections’ headings and their tallies, a refresh
after a write, and, with the grouped requests held, the wait: the trigger in the
choice’s frame, the dimmed tree and the scan row’s words, a refresh that waits, and
cancelling, in Chrome.

The server reads every group from one pass over the index, at one index version
(`GroupedTreeQuery` in `inventory_engine/contract.py`). Measured in process, warm, on
2026-11-15, against the read per group it replaced, with identical answers:

| Folder | Ungrouped rows | By file type | By age |
| --- | --- | --- | --- |
| 100,000 files (the bench corpus) | 2 ms | 92–96 ms, was 622–688 ms | 72–98 ms, was 404–505 ms |
| 270,000 files and 110,000 folders | 3–4 ms | 0.42–0.48 s, was 4.0–4.5 s | 0.34–0.47 s, was 3.3–3.6 s |

In headless Chrome on the 100,000-file corpus, a click on By file type painted its
sections 130–132 ms later when the press asked for nothing ahead, and 27–47 ms later
after a 100 ms press had asked for it; By age took 98–116 ms and 29–32 ms; No grouping
painted its tree in 29–49 ms.
On the larger folder By file type took 0.50–0.53 s, or 0.39–0.48 s after a 100 ms press,
and No grouping 41–95 ms.
Two groupings asked for at once each took twice as long there, 0.86 s against about 0.42
s, which is why opening the menu no longer asks for both.
Opening a folder inside a section took 24 to 32 ms, the same as outside one, with no
spinner shown. On a folder of 112 files, a file written every 250 ms for 6 s into a
folder open one or two levels down gave four paced refreshes of at most 8 ms of paint
each, and the scroll position, the focused row inside that folder, and the open folders
held through all of them.

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
everywhere. A family departs from GitHub only by a deviation declared beside it in the
registry. TypeScript is the one that leaves GitHub’s color for another: GitHub makes it
and Python both blue, so TypeScript is a saturated yellow and Python keeps GitHub’s
blue.

Each theme defines a `ToneBand` in `color_oklch.py`, with a lightness band and a chroma
target band. The registry derives each family’s lightness rank and chroma ratio from the
set of upstream colors; a family without an upstream color sits at the band’s center.
An explicit registry lightness-rank or chroma-ratio override changes that axis while
retaining the other one as derived.
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

Files and Pulls each keep their last selection and navigation scroll position.
A reader who switches to one returns to that tab’s destination, or to its default on the
first visit. A direct URL or a browser history step selects the tab that owns the
destination and reveals the item there, as every route to an item does
([Navigation Reveals the Item](#navigation-reveals-the-item)).

Switching to Commits always selects the newest commit, the top row, and shows its
detail, whether by a click, the tab’s shortcut, or a history step onto the tab’s own
entry; a return after reading an older commit lands on the newest again.
Only an address that names a commit, opened directly or reached by Back or Forward,
selects another. The selection waits for the first page of history, and for any check
under way of whether HEAD moved; when HEAD moved, the history is read again, a page of
the old one still on its way notwithstanding, and its newest commit is selected.
A check that gets no answer keeps the history the panel has.
The pane keeps what it showed until the commit is ready, so the switch paints no prompt
and no blank frame. The commit’s address replaces the tab’s entry, so Back returns to
where the reader was.
The list starts from its top, and the newest row becomes the list’s Tab stop.
A click leaves focus on the tab.
The tab’s shortcut moves focus to the newest row without scrolling the list, so `H` then
`↓` opens the next commit; when the newest row is not in the list yet, the tab holds
focus until the row arrives, unless the reader moves focus first.
An empty history selects nothing, and the pane says “No commits yet.”
Clicking Commits while it is already in front changes nothing.
`static/git-panel.js` (`landOnNewestCommit`) owns the selection;
`tests/dom/git-commit-history-session.js` runs it.

The heading above the nav’s tab bar, the served root’s name, is home.
Activating it, by pointer or by Enter, shows the Files tab at the served root from any
tab, with the tree at the top of its panel.
It pushes one history entry, or none when Files already shows the root, so Back returns
to the tab the reader left.
It stays a link to `/view/`, so a modified or middle click and its context menu do what
they do on any link.
Its accessible name is the text it shows, and a description says that it goes home, as
its tooltip does for a pointer.
`static/main-tabs.js` (`goHome`) owns the switch;
`tests/dom/preview-pane-state-session.js` (`goingHome`) runs it.

The bar is as wide as the pane and sits under the identity it belongs to and over the
content it switches.
A use site does not pad, recolor, or re-letter it.
In the navigation, a pane too narrow for its tabs wraps the bar between them
([Navigation Toolbars Wrap](#navigation-toolbars-wrap)).
`test_every_tab_is_the_tab_primitive` holds the markup, the stylesheets, and the tokens.

### Navigation Reveals the Item

Navigating to an item by any route shows it in the navigation pane.
The item’s tab comes to the front: Files for a file or folder, Pulls for a pull request
or one of its changed files, and Commits for a commit.
That tab’s panel then opens the folders or the stack that hold the item, selects its
row, and scrolls the row into view.
The routes are:

- Quick Search;
- a link in a document, a diff, a pull request’s page, or a commit;
- the address bar’s crumbs, and the page loading at an address;
- Back and Forward;
- a key that opens an item, such as `J` and `K` on a row or Control-N along a stack.

`static/main-tabs.js` holds the rule once, as `revealPlan`, and the one path every route
takes, as its controller’s `reveal`. That path brings the address’s tab to the front and
calls the panel’s own `reveal`:

- **Files:** `revealFileRow` in `app.js`.
- **Pulls:** `pulls-nav.js` marks the pull request in the list (`setCurrent` in
  `builtin_plugins/github/pulls-panel.js`), which opens a closed stack that holds it.
- **Commits:** the panel reveals a commit from its own landing (`restoreCommitLanding`
  in `git-panel.js`), since it has to read history first.

Each exception has a reason:

- **Focus stays where the reader is.** No route moves focus.
  The panel selects and scrolls, and focus stays in the document, the diff, or the page
  the reader was reading, so its keys keep working there.
  A route that starts in the navigation, a row’s click or its keys, has focus there
  already and keeps it.
  A tab’s letter, `F`, `P`, or `H`, moves focus to the panel’s row, because that is the
  letter’s own command, not a reveal.
- **A tab’s button keeps the panel’s place.** A click on a tab, or its letter, returns
  to the tab’s last destination with the panel scrolled as the reader left it.
  The reader asked for the tab, not the item.
  Back and Forward reveal the item.
- **A step within the item shown reveals nothing.** This is a fragment, a line anchor,
  another view of the file shown, or another tab of the pull request shown.
  Opening the item shown again, as Quick Search does, reveals it again, opening a folder
  or stack the reader closed since.
- **A long folder draws the rest of its rows.** A folder draws its first 200 rows and
  holds the rest behind a row that shows them.
  When the item is among them, the reveal draws them first.
- **A file a filter hides is named, not drawn.** The Files tree takes the selection from
  whatever row had it, so no other row stays selected, and a note under its totals says
  “src/app.txt is outside this filter.”
  The tree does not grow a row for the file: a pinned row would mean refetching, and
  repainting, the tree as the reader moves.
  The note appears only when the tree can tell.
  That is when a folder above the file has no row, or the open folder that would hold
  the file lacks it. A file in a folder the reader closed gets no note.
  Under Group by, the file is looked for in its own section first, then in each other
  section.
- **A pull request outside the list is named.** Open and Closed hold only their state’s
  pull requests, and the list reads its windows from the newest.
  A pull request the list does not hold is named under its band: “#8 is not listed under
  Open.”, or under All, “#8 is not in this list.”
  A list that has not read as far says only “#8 is not among the pull requests loaded.”,
  since it may be further down.
  Under All, the list keeps reading for one older than the rows it has read, up to its
  display limit, and reveals it when it arrives.
  A reveal never changes the filter, which is the reader’s choice.
- **A commit outside the history read is not chased.** Commits reads history from the
  newest commit, 250 commits a page.
  A commit’s address reveals its row once the pages read hold it, so the first page’s
  commits are always found.
  The list does not page further for an older commit, or for one on no branch the
  history walks. The pane shows that commit with no row selected, because paging the
  history for one row costs a request a page.
- **A file at a pinned revision is the served tree’s.** A page serving a pinned revision
  shows that revision’s tree in Files, and a file reveals there like any other.
  A file a commit’s address names (`/commit/<rev>/<path>`) belongs to the commit.
  It reveals the commit in Commits and leaves the Files tree alone, because that tree
  lists the served source, not that commit’s.

`tests/dom/nav-reveal-session.js`, pinned by `cli-ui-nav-reveal.tryscript.md`, runs the
rule, the tabs, the Files tree’s reveal, and the Pulls list’s on the production code.
`tests/test_nav_reveal_chrome.py` checks in headless Chrome, after each route, that the
row is in the tab in front, selected, and in view, and that focus has not moved to the
navigation.

### Navigation Toolbars Wrap

**A navigation toolbar that its pane is too narrow for wraps between its controls.
Nothing in it is cut, scrolled out of reach, or cut short.** The pane drags down to 180
px, which leaves its toolbars 179 px, and the system font set’s face is wider than the
default one’s, so no toolbar can promise one line.

The rule covers every toolbar in the navigation: the Files filter row, the Pulls
filters, the Commits tally, which stands in the toolbar slot, and the tab bar over them.
The Files row and the Pulls filters are one primitive, `.nav-toolbar-row` in
`static/styles.css`, which a plugin whose toolbar stands in the slot gives its row.

- **One line while it fits.** A toolbar whose controls fit one line is that line, and
  the toolbar slot’s height, `--nav-toolbar-height`, as it was before the rule.
  A toolbar wraps only when its controls do not fit, and never adds space when they do.
- **Where it breaks.** Between controls, in their order, each line as full as it can be,
  so a control moves down only when it must.
  The leading controls stay first.
  The trailing group, which takes the line’s end with an auto margin, moves down whole
  and stays right-aligned: Clear and the chevron on Files, Reload on Pulls.
  The Commits tally breaks between its phrases, “12,345 commits”, then “begun 1y ago”,
  and the tab bar between its tabs.
- **Line spacing.** A row’s lines are `--nav-toolbar-line-height` tall, a chip’s height,
  and `--nav-toolbar-gap` apart.
  That is also the gap between controls along a line and above the first line and below
  the last, so a wrapped toolbar is a grid of one spacing and reads as one toolbar, and
  it grows by a line and a gap for each line it adds.
  Every control is one line tall: a shorter one, Show ignored’s checkbox, is centred in
  a line’s height, and a taller one, a `.btn` such as Reload, is held to it, so no line
  is cramped and none stands taller than the rest.
  An open drawer’s menus wrap on the same gap, and a closed drawer adds nothing under
  the lines. The Commits tally is text, so its lines are its line height apart,
  `--nav-metadata-line-height`, as any metadata line’s are; a tab is its own line, so
  the tab bar’s lines are a tab’s height apart.
- **A segmented group.** One that its whole line cannot hold joined takes the cluster
  layout until it can ([Groups Or Dropdowns](#groups-or-dropdowns)). Whether it fits is
  measured on a copy in the joined layout, so the answer at one width is the same
  whichever layout the group shows, and the two cannot alternate near the break.
  A change to its text is fitted before it paints, and a change of size in the next
  frame, which a drag across the break shows for one frame.
- **Keys.** Wrapping keeps the controls’ order, so reading the lines top to bottom meets
  them in their Tab order, and their keyboard numbers stay theirs.

Measured in headless Chrome on 2026-11-15, the widths each toolbar is one line from,
default font set / system font set:

| Toolbar | One line from |
| --- | --- |
| Tab bar: Files, Pulls, Commits | 196 / 216 px |
| Files, no filter set | 246 / 262 px |
| Files, a filter set, “No grouping”, its widest | 298 / 317 px |
| Pulls: Show and Reload; Open 100, Closed 2, All 102 | 276 / 308 px |
| Pulls: Show and Reload; four-digit tallies | 303 / 341 px |
| Commits: “5 commits begun 3mo ago” | 179 / 186 px |
| Commits: “123,456 commits begun 12mo ago”, its count bold | 214 / 242 px |

The Pulls Show group is joined from 218 / 245 px with three-digit tallies (Open 100,
Closed 200, All 300) and from 244 / 278 px with four (1,234, 5,678, 6,912), and the
cluster below. At the narrowest pane, 179 px, with a filter set, the Files row is three
lines: Group by, then Show ignored, then Clear and the chevron.
The measurements are beside the rules in `styles.css`. `tests/dom/nav-toolbar-wrap.mjs`
holds a toolbar to this rule at every width from 179 to 420 px, in both font sets:
`tests/test_files_tab_chrome.py` the Files row in every Group by and filter state, with
its numbers, Tab order, and drawer at the narrowest;
`tests/test_github_pulls_stacks_chrome.py` the Pulls filters with three- and four-digit
tallies, and the Show group’s two layouts, its observers, and their disposal; and
`tests/test_nav_metadata_chrome.py` the Commits tally and the tab bar.
`tests/dom/filter-controls-behavior.js` holds the fit and its observers’ lifecycle
without a browser.

### Navigation Metadata Line

Under each main tab’s toolbar, a line or two says what the list below holds and how
current it is: the Files totals, “12,797 files (413.8 MB) + 248,189 ignored (10.1 GB)”,
and the filter’s remarks under them; the Commits tally, “10,044 commits begun 1y ago”;
and the Pulls count, “381 PRs on owner/repo”, over its connection line, “Updated just
now” or what keeps the list from refreshing.
All of them are one component, `.nav-metadata` in `static/styles.css`. They were three
recipes, and the reader saw it: 13px text 6px under the Files filters, 13px text centred
in the Commits slot, and 12px muted text with no space above it under the Pulls filters.

- **Type.** `--nav-font-size` in regular weight and `--text` ink, line height
  `--nav-metadata-line-height`, and tabular numerals, so a count that grows while it is
  counted does not jitter.
  A remark on the line above it — a filter’s count, a connection’s state or remedy —
  adds `.nav-metadata-note`, which mutes it and changes nothing else.
  Inside a line, spans carry only what they mean: the gitignored half is muted, an age
  is the [age primitive](#age), a repository name is `.repository-name`, and a count’s
  number is bold, `.summary-number`
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)).
- **Box.** The navigation column’s inset, `--pane-header-padding-x`, and
  `--nav-metadata-padding-y` above and below, with the band’s rule,
  `--nav-metadata-rule-width`, under it.
  The padding is derived from the slot’s height, the line height, and the rule, so one
  line of it is exactly the toolbar slot’s height, and on Commits, which has no toolbar
  of its own, the line stands in the slot and its text sits as far from either rule as
  it does under the Files and Pulls toolbars.
  Consecutive lines are one band: padding above the first, below the last, and one rule.
- **Spacing.** `--nav-metadata-gap` between a line’s items and between the words of an
  item built of spans, about a word space and a half.
- **Pending.** A figure still being counted is the pending tally inside the span its
  figure will fill, so it sits across the middle of the line, where the text will.
  On Commits the server ships it so, and the tally replaces it in place.
- **Height.** Each line reserves its own line box before anything arrives.
  While a line’s text fits the pane, a pending tally, a count still being taken, and a
  settled one are one height, and the Pulls lines are one height from loading through a
  failure. Text wraps only when it is longer than the pane, and then the band grows by
  the lines it needs: the Files split totals in a narrow pane (tracked as H54), a Pulls
  remedy, which keeps its whole command, as the pull request header’s does, and the
  Commits tally in the toolbar slot, between its phrases, the slot growing with it
  ([Navigation Toolbars Wrap](#navigation-toolbars-wrap)); at the default pane width the
  remedies for an unreachable GitHub, a gh that is not signed in, and a missing gh each
  take a second line.

The built-in Pulls tab uses the class; its stylesheet lays out only the lines’ spans.
No stylesheet but the component’s sets anything on a line element beyond how a long word
in it breaks. `tests/test_nav_metadata_line.py` holds the markup and every shipped
stylesheet to that, however a rule is scoped.
`tests/dom/tree-summary-line-session.js` records what the Files line says in each state.
`tests/test_nav_metadata_chrome.py` measures, in Chrome, at the default pane width and
at one wide enough for every text: the Files totals settled, pending, counting,
filtered, with the outside-filter note, and with the stale recent-files note; the
Commits tally settled, as the server ships it pending, and failed; and the Pulls lines
loading, updated, unreachable, signed out, and with no gh; and the Pulls count cut short
in a narrow pane.

### Section Headings

The title of a section in a stack is `.section-heading`: the tab bar’s uppercase, bold,
tracked sans grammar at `--body-font-size`, over a neutral rule.
`--section-heading-divider-gap` sets the space between its content and the rule, so the
rule is equally close to a heading with or without a disclosure control.
A use site owns the space around the heading, and the type and the rule stay with the
primitive. Overview’s panels and a pull request’s sections carry it, and
`test_section_headings_and_fold_expanders_are_primitives` holds it.
A heading that counts its section sets the count beside its name
([Heading Tallies](#heading-tallies)), as Review comments does.

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

Text the Overview draws itself starts on one left edge at every width: each panel
heading’s label, and a surface body’s controls, rows, and toggles such as **Details**,
start `--file-tab-padding-x` in from the card edge, under the active tab’s label.
The README’s prose keeps KPress’s responsive inset inside its card, as a standalone file
does, so it is not that edge.
The inset is declared once, outside any container query.
When it followed the README’s inset, the labels moved from 0.75 to 4 to 2.5 rem in from
the card edge as the window widened.
`tests/test_folder_overview_alignment.py` measures the edge in Chrome at widths in all
three document bands.

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
a footer sentence. The print action keeps its slot, hidden, when no mounted contribution
is printable.

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

### Tooltips Add Information

**A tooltip says something the reader cannot already see, or it is not there.** A
tooltip that repeats visible text is a second copy of what the reader just read,
appearing under the pointer on its own timer, and it is removed.
A tooltip earns its place by one of these:

| Reason | Examples |
| --- | --- |
| The name of a glyph-only control or mark | Copy, print, the parent folder’s arrow, the theme and font segments, the filter drawer’s chevron, the served root’s “/” |
| What a letter, badge, or color abbreviates | A Git file’s status letter, a compression badge, a front-matter error |
| The exact value behind a rounded or relative one | An age’s exact time on the pull request page; a tree row’s exact date, and a folder’s other total |
| What a control does that its words do not say | The ref selector’s “Switch branch or tag”, the HTML preview’s “Open as full page” (its own tab, still sandboxed), a View file control’s commit, a freshness line’s “Press to refresh now”, a fallback layout’s reason |
| The whole of something cut short | A chip’s full name, a crumb’s own name, a diff file bar’s path, the page title past its two lines |

**The Pulls column has none.** A pull request’s row, a stack’s row, and their parts
carry no tooltip: the state icon’s name, a stack place’s stacks, and a stack row’s
counts are their accessible names, and the age’s exact time and a title cut short are on
the page the row opens.
A pull request’s changed files under its row keep the tooltips the tree gives a file:
its full path when its row shows only its name, “not in this comparison”, the name it
was renamed from, and what a folder’s sums leave out, the counts alone.

**Restating is not adding.** A “Show ignored” check, in the Files filter row and a
folder’s rollup, has no tooltip, as its label says it; nor has the treemap’s parent
button, which shows the folder it opens; nor a merge’s arrow, beside the two names it
would restate; and a crumb’s tooltip is its own name, cut short, not the path the trail
already shows. A Files tree row’s tooltip leaves out what the row shows, its name, a
file’s size, and a folder’s size or file count, whichever its chip holds, and gives the
exact date and a folder’s other total.

The shell holds the repeat case.
A `data-tip-text` that is its element’s own text, in any case and spacing, shows only
while that text is cut short, by an ellipsis or a line clamp, so a surface may give an
ellipsizing element its full text as a tip and the reader sees it only when the ellipsis
hides some of it (`tipAddsInformation` in `static/app.js`). `devtools/check_tooltips.py`
fails a literal tip that is its element’s literal text, and
`tests/dom/github-pull-header-chrome.mjs` checks the shell’s rule in Chrome;
`tests/dom/github-pulls-stacks-chrome.mjs` checks that the Pulls column carries no tip.

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

### Groups in a Menu

**A menu that groups its rows heads each group one way: a `.menu-group` named by its
`.group-heading`.** The pattern lives in the shell’s `styles.css`, so a built-in menu
and a plugin’s use the same markup:

```html
<div class="menu-group" role="group" aria-labelledby="types-section-1">
  <div class="group-heading" id="types-section-1">Code</div>
  <!-- the group's .menu-item rows -->
</div>
```

- **Heading.** A `.group-heading` is the quiet label register, gray, all caps, and
  tracked, and it starts on the menu’s row inset, `--menu-row-inset`: the edge a row’s
  first column starts on, a check or an icon, and the edge the menu’s `.menu-title`, a
  labelled `.menu-row`, and `.menu-version` start on.
  It is not indented to the rows’ labels: a heading on the label column reads as a row
  of its group rather than its name.
- **Separator.** A `.menu-group` draws its own divider as its top edge, in the
  `.menu-separator` geometry (4 px, a 1 px rule, 4 px), unless it is the menu’s first
  child, where the menu’s edge already sets it off, or follows a `.menu-separator`,
  which already draws the rule.
  So a heading never lacks a divider or gets two.
  Rows that no heading names, such as the type filter’s raw extensions after its groups,
  are set off with a plain `.menu-separator`.
- **Semantics.** The group carries `role="group"` and `aria-labelledby` naming its
  heading, so a screen reader announces the group as the eye reads it.
  The heading is the group’s first child.
- **Title or one group.** A heading names the whole menu when nothing else in the menu
  needs a name: the menu’s own `.menu-title`, as the gear menu’s wordmark is, or a menu
  whose rows are all one group, as a pull request’s stack menu is.
  That one group keeps the `.menu-group` and `.group-heading` look, but the menu is
  named from the heading through `aria-labelledby`, with no `aria-label` of its own and
  no `role="group"` on the wrapper, so the name is read once.
  A menu with two or more groups names each one, as above.

`tests/test_files_tab_chrome.py` and the stack part of
`tests/test_github_pull_header_chrome.py` measure in Chrome that each heading’s text
starts on its rows’ inset and names its group or its menu;
`tests/test_browser_filter_ui.py` pins that the row, title, labelled row, foot, and
heading all read the one token.

### Heading Tallies

**A heading that counts what it heads sets the count beside its name, after the
separator, on the heading’s line: “Older · 10,004 files”.** The far end of a line is
where a row keeps its total, a folder’s size or a menu row’s count, so a count there
read as a total of the heading’s row rather than the size of its group.

```html
<div class="group-heading tree-section-heading" id="metabrowser-tree-section-age%3Aolder">
  <span class="tree-section-label">Older</span>
  <span class="heading-tally"> <span class="heading-tally-dot" aria-hidden="true">·</span> <span class="heading-tally-figure">10,004</span> files</span>
</div>
```

- **Primitive.** `.heading-tally` in the shell’s `styles.css` follows the heading’s
  name: a space, the dot, a space, the figure, and its unit if it has one, on one line
  of markup, since the tally keeps its white space.
  Any heading takes it, a [group heading](#groups-in-a-menu) or a
  [section heading](#section-headings).
- **Register.** The tally is a figure, not part of the name, so the heading’s caps,
  tracking, and weight are for the name alone: the tally is at the heading’s size,
  regular, untracked, in `--muted`, with tabular numerals.
  Its numeral and words follow the count-summary rule for numbers.
- **One line.** The tally never wraps, and keeps its spaces where a heading lays out its
  name and tally as flex items.
  Where the two do not fit, the name is cut short with an ellipsis and the tally stays
  whole.
- **Accessible name.** The dot is hidden from assistive technology, so the heading reads
  its name and its count: Chrome names a Files section “OLDER 10,004 files”, in the
  label register’s capitals.
- **No tally where its rows are the count.** A heading over rows that each stand for one
  of what it would count carries none, since the rows show it: a Pulls stack group’s row
  shows no count of its pull requests ([Stacks](#stacks)). Its accessible name still
  says how many.

The headings that carry a tally are a Files Group by section’s
([Grouping the Files Tree](#grouping-the-files-tree)) and a pull request page’s Review
comments. A filter menu’s group headings, the stack menu’s heading, Overview’s panel
headings, and File Overview’s type groups count nothing.
`tests/test_files_tab_chrome.py` measures in Chrome that each File type section’s tally
starts where its name ends, leaves the rest of the line empty, shares the name’s line at
the default pane and at the 180 px minimum, sets its numeral at the numbers’ weight, and
leaves the section and its tree named by the heading’s words without the dot;
`tests/dom/github-pull-timeline-chrome.mjs` holds the Review comments heading to the
same place and register, and `tests/dom/github-pulls-stacks-chrome.mjs` holds that a
stack’s row shows its label alone.

### Menu Height

**A filter dropdown takes its rows’ natural height, up to 16 rows, and never reaches
past the window.** Its `max-height` is the smaller of 16 rendered rows plus its padding
and border, and the room from its top edge to the window’s bottom edge less 8 px, the
tooltip’s viewport margin.
Past that it scrolls inside itself.
The rule is stated from the rendered row, not in pixels, so it follows the row if the
row’s type or padding changes.

The room depends on where the trigger sits and on the window, so the height is measured,
not declared: `filterControls.bind` fits a dropdown when its trigger opens it and again
when the window resizes, and a consumer that renders one open another way calls
`filterControls.fitOpenMenus(root)` after rendering.
Until it is fitted, the panel’s CSS keeps it inside the window.
A panel with no box, its toolbar hidden, is not fitted, and the Files toolbar closes an
open filter menu when it is hidden.

The rule applies to every filter dropdown, not only the type filter.
A dropdown with few rows, such as Modified within or Minimum file size, keeps its
natural height unless the window is shorter than its top, plus that height, plus the 8
px margin; then it scrolls like the others.
Other menus are out of scope and keep their own caps: a pull request’s stack menu at
`min(60vh, 480px)`, the branch and tag list at `min(50vh, 320px)`, and Quick Search at
`min(70vh, 640px)`.

Measured in headless Chrome on the Files type filter: every row is 29 px and the frame
10 px, so the cap is 474 px.
`menuMaxHeight` is checked without a browser in `tests/dom/filter-controls-behavior.js`,
and `tests/test_files_tab_chrome.py` measures the type menu at a tall and a short
window, through a resize and a reopen, and the age menu at both.

### Keys in a Menu

**Opening a menu puts focus in it, so its keys work at once.** Every way a filter
dropdown opens comes to one path, `filterControls.focusMenu`: its trigger’s click,
Enter, and Space, `↓` or `↑` on its trigger, and a filter’s number, which opens the
drawer that holds it too.
Focus lands on the checked row, or on the first row when none is checked, so `↑`, `↓`,
`Home`, `End`, Enter, Escape, and the rows’ letters below act on the next key.
`W`’s branch list is the precedent: it opens with focus in its filter box.
The pull request page’s stack menu opens the same way, on its current member, the row it
checks, by a press, Enter, Space, `↓`, or `↑` ([Stacks](#stacks)); on its button, as on
a filter’s trigger, `Home` and `End` open nothing.

- **Closing.** Escape, a second click on the trigger, and a choice that closes a
  single-select menu give focus back to the trigger.
  Focus the reader moved elsewhere in the page stays there, and an Escape that a surface
  above the menu took, such as Quick Search’s or Help’s, closes only that surface: the
  topmost closes first.
- **Staying.** A pick in a multi-select menu leaves it open with focus on the row
  picked, and a rebuild of the bar while a row or a trigger has focus, such as a tally
  refresh, puts focus back on the same control, or on the trigger of a menu the rebuild
  closed: the bar calls `filterControls.keepFocus` around every rebuild.

**An open menu that has focus can also give each of its rows a letter, and the letter
chooses the row.** Group by’s rows are the first to have them: `N` for No grouping, `A`
for By age, and `T` for By file type.

- **Which letter.** A row’s letter is the first letter of the word that names its value:
  No, age, and type. It is declared beside the row’s label, as `key` on an option and
  `anyKey` for the any-row, rather than derived, so renaming a row never moves its key.
  Two rows of one menu never share a letter; when two declare one, the first keeps it.
  A menu that gives one row a letter gives every row one, its any-row included.
- **When it is live.** Only while the menu is open and focus is in it, on its trigger or
  a row. The rows’ commands sit in the menu’s own scope, active while it is open and
  above the shell’s, so there a row’s letter outranks the shell’s, as a text field’s
  typing does: in Group by’s menu `T` chooses By file type, where elsewhere it is Quick
  Search. Quick Search keeps `/` there, a letter the menu does not declare still reaches
  the shell, and every letter is the shell’s again once the menu closes or focus leaves
  it.
- **What it does.** A letter runs the row’s click path,
  `filterControls.activateMenuRow`, never a synthesized click, so it does what a click
  on the row does: a single-select menu closes on the choice, and a multi-select menu
  stays open.
- **How it is shown.** As every other key is: the row carries the letter as its
  `aria-keyshortcuts`; holding Shift badges each row with its keycap and lists the
  letters in the revealed strip, which then shows only the keys that still reach another
  command, Quick Search by `/` alone; and Help lists them in its Menus group, “Available
  while the menu is open and has focus.”, each by the row’s label and the menu it is in.
- **Where.** The shell’s keymap reads the letters from the navigation pane’s filter bar
  (`syncMenuLetters` in `static/shell-keymap.js`), so only its menus take them.

`tests/dom/key-reveal-session.js` runs both on the production registry, keymap, and
filter controls: where focus lands for each way a menu opens and closes, through a pick
and a rebuild, and for the letters the Help group, the badges and the strip, each
letter’s choice, and `T` as Quick Search with the menu closed or focus outside it.
`tests/dom/filter-controls-behavior.js` pins the focus path on a rendered bar, the rows’
markup, and the click path a letter shares, and
`tests/dom/keyboard-shortcuts-behavior.js` the scope’s precedence and what the live
surfaces show. `tests/test_files_tab_chrome.py` reads `document.activeElement` in Chrome
after each number, `↓` and Enter on a trigger, each letter, Escape, and a pick in File
type as the bar rebuilds.

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

### Reveals

Chrome that appears because the reader asked to see it eases in on one token,
`--motion-reveal`: a 180 ms decelerating curve, `cubic-bezier(0.2, 0, 0, 1)`, so it
settles rather than pops.
The Shift reveal is its user: each key badge fades in and grows from 85% of its size,
and the revealed strip fades in.
A reveal never animates out.
It ends at once, because the reader has let go and is about to act on what was under it,
and a fading badge would cover the label they reach for or point at a state a key has
already changed.
The duration is under the 200 ms hold that starts the Shift reveal, so a
held Shift reads as one gesture, and a quick Shift-tap still never starts it.
Under `prefers-reduced-motion: reduce` a reveal appears at once.
WebKit, the macOS app’s engine, runs the reveal unprefixed: `@keyframes`, `animation`,
and the `scale` property need no `-webkit-` form there, unlike `user-select`. A new
reveal uses `--motion-reveal` rather than a duration of its own.

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

### Regions Keep Their Boxes

Every region’s box is decided by the first paint and does not depend on data that
arrives later. Chrome that comes and goes moved more than content did: the filter bar 37
px on every main-tab switch, the view tab bar 30 px between files, a scrollbar 11 px,
the Commits tab 78 px on every landing.
So a region keeps its slot while its content is absent, and holds the height it will
have: one toolbar slot at the top of the navigation that every main tab fills with its
own toolbar at one height (the Files filters, the Commits tally, the Pulls filters), the
Commits tab from the server at a repository’s root, a scrollbar gutter on the tree and
the preview pane, the shortcut strip’s row, a view tab bar in every file, the print
button’s and a run badge’s widths, the Pulls tab’s status and connection lines and its
age column, and the pull request header’s rows, but for a labels row a pull request with
no labels does not have ([Layout](#layout)). Heights are in line units, or struts of the
controls a row holds, never pixels measured in one engine, because WebKit’s font metrics
differ from Chrome’s. Where a region’s size is its data’s and arrives a moment after the
rest, as the File Overview’s first rollup does, the view holds its first paint for that
data, briefly, with the previous view still shown.
The server draws the tab an address lands on in front, a commit’s address on Commits, so
a landing never shows one tab’s chrome and then swaps it; a toolbar that cannot load
says so in its slot rather than pulsing.
`tests/test_reserved_chrome.py` pins the rules.

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

One wait dims what is shown, and it is named here because it is the exception: a Group
by choice’s first sections ([Grouping the Files Tree](#grouping-the-files-tree),
Waiting). The tree on screen then is not the content being checked but the arrangement
the reader left, and the reader is waiting for the new one, so past the quiet period it
dims to its own token, `--loading-dim-opacity`, while the scan row says what is coming.
Nothing else takes that token.

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

### A Repaint Keeps Its Images

**A repaint never blanks an image whose address did not change.** Where it can, a view
keeps the image’s node: the Pulls tab patches a row in place and builds its metadata
line, avatar and all, again only when the author or the avatar changed, and the pull
request page keeps its conversation’s sections and its header’s parts across tabs and
polls. Where a repaint builds an image again, as the pull request page builds its
header’s actor when the actor or the avatar changes, the image is created with
`loading="eager"`. So is an image that only the visible window creates, such as a Pulls
row’s avatar, which the list mounts again as it scrolls back.
The conversation’s avatars stay `loading="lazy"`, as a long document’s figures do, so
neither is asked for until the reader nears it.

A lazy image waits for layout before it asks for its bytes, and WebKit, the macOS app’s
engine, then asks the network again rather than use the copy it holds.
Measured in the app’s WKWebView (WebKit 21624, macOS 26.5) on 2026-11-13, when the
header built its actor on every tab switch, with the avatar served locally after 80 ms,
by reading the header’s avatar at each animation frame and counting requests at the
server: on each of 9 tab switches the rebuilt lazy avatar was requested again, and its
`complete` was false and its `naturalWidth` 0 for 3 frames, 100 ms at that window’s 30
frames a second.
Eager, it made no request, and `complete` and `naturalWidth` were set in
its first frame on all 9. That the eager avatar then paints in that frame is an
inference: a page cannot read WebKit’s decoding or paint.
Pixels were read only in headless Chrome 152, whose screencast showed no blank avatar
frame in 9 switches either way; Chrome had the lazy image complete in its first frame
too, so the blank was WebKit’s.

An image whose address does change is a new image, and its slot keeps its size, so its
arrival moves nothing.
`test_the_header_keeps_its_nodes_and_each_avatar_loads_by_its_placement` checks, in a
browserless DOM, each avatar’s loading by placement and which of the header’s nodes a
repaint keeps or builds: their attributes and node lifecycle, not their paint.

A node replaced under a still pointer is also a new target for hover and focus.
Measured in headless Chrome 152 on 2026-11-13, with the pointer resting on the header’s
head branch chip while the page switched tabs: when the header built its parts again,
the new chip was not hovered and its copy button was hidden in the task that replaced
it, and read at the next animation frame Chrome had hovered it again and fired
`mouseenter` on it again.
That no frame painted the button hidden is an inference from those readings.
That `mouseenter` gives the shell’s tooltip a new anchor and restarts its delay
(`showTooltip` in `static/app.js`). Keyboard focus on the chip’s copy button went to the
document body on each tab switch.
With the header keeping its parts, the chip is the same node, no `mouseenter` fires, and
the focus stays. WebKit’s hover after such a replacement was not measured.

A Markdown document is built again each time its file is entered; switching between its
Document and Source views keeps it.
KPress writes its images lazy, and one far down a long document should wait for the
reader. So an image the page has already loaded, at an address that names its bytes, is
made eager, and takes the copy the page holds; an image the page has not loaded stays
lazy.

A served file’s address names its bytes by a version.
Each render answers, beside its HTML, `raw_versions`: for each served file the document
embeds, a token of the file’s resolved path, size, modification and change times, inode,
and device, of the trust profile and its sandbox policy, and of the build, read when the
render is asked for, which is on every entry.
The link enhancer puts the version in the file’s `/raw` address, so a replaced file is a
new address. `/raw` keeps a raster image’s answer for a year at the version the file has
now, and revalidates every other, an SVG’s included, since its sandbox differs by trust
profile (`SECURITY.md`); a revalidated image the page holds is still taken from its
copy. So the page reuses what it holds at an address without asking whether the file
changed: an image whose file changed has a new address, which the page does not hold,
and loads lazily there.
That is true of a hidden file, a file behind a link, a file deeper than the shell’s
event stream watches, and a replacement that keeps the file’s size and time, because the
version is read from the file, not heard from the shell.
On a pinned revision a file never changes at its address, and an image from another
origin, a scheme-relative `//host/badge.svg` on another host included, is that host’s to
keep fresh, as Chrome reuses one anyway, so both are held too.
A served address without a version, which is any past the render’s first 256 files, and
an absolute or scheme-relative address on the page’s own origin can change under the
page, and are never held.

A held served image is made eager before its address is set, its authored address
removed first: an eager image asks for its address at once, and the authored one,
relative to the document, is not where the image is served.
A held image from another origin keeps the address its author wrote, so it has to be
eager before the page adopts it: a trusted render is parsed in a template, whose
document loads nothing, and the template’s images the page holds are made eager there.
The page remembers `MAX_HELD_IMAGES`, 1,024, and past that forgets the image loaded
least recently. The costs behind that number are beside the constant in the plugin’s
`place-rendered.js`, and the cost of a version beside `_MAX_RAW_VERSIONS` in
`server.py`.

Measured in the same WKWebView on 2026-11-13, on a document with three images in its
first screen and one 4,800 px down, served by Metabrowser behind a proxy that delayed
each image 80 ms and counted requests, and reading each of the three at each animation
frame and again after layout.
Leaving for another file and coming back, each of 5 returns asked for all three images
again and left each without its image for 3 frames, 100 ms at 30 frames a second.
With the held images eager, the returns asked for none, and each image was complete,
with its width, in its first frame.
Making the shown images eager in the first frame, after they had been created lazy,
changed nothing: each return still asked for all three, and each was blank for 3 or 4
frames. So WebKit had given up the copy when it deferred them, an inference from the
counts. Without removing the authored address first, each return also asked the server
for the three images at their authored addresses.
Switching to Source and back built nothing, before and after: no request and no blank
frame. Headless Chrome 152 asked for nothing and had every image complete in its first
frame, before and after, and neither engine asked for the image far down.

Measured again on 2026-11-14, in the same WKWebView (WebKit 21624.2.5.11.8, macOS
26.5.2) and in headless Chrome 152, against the code before versions (7e27e32b), with
the same document and an image from another origin added to its first screen, served
with `max-age=300` and delayed 80 ms like the rest.
Each return was read the same way, and the replaced image, 240 by 120 and red, became
360 by 90 and magenta at the same path, told apart by its natural size and by a pixel
drawn from it:

| Engine | Code | 5 returns, nothing changed | Return after editing the document | Return after replacing the image | Reload after that |
| --- | --- | --- | --- | --- | --- |
| WKWebView | before | served images: no request, no blank frame; outside image: asked again each time, 3 or 4 blank frames | asked again, 3 blank frames | asked again, 3 blank frames, new image | new image |
| WKWebView | versions | no request, no blank frame, outside image included | no request, no blank frame | asked at its new address, 3 or 4 blank frames, new image | new image |
| Chrome 152 | before | no request, no blank frame | no request | no request, old image | asked again, new image |
| Chrome 152 | versions | no request, no blank frame | no request | asked at its new address, 6 blank frames at 60 a second, new image | no request, new image |

Before versions, Chrome showed the old image on the return without asking, because it
reuses an image the page has loaded at the same address whatever its headers say; its
reload asked again because `/raw` was `no-cache`. With versions a change to the document
no longer costs its images a round trip in WebKit, since nothing forgets them, and a
replaced image is asked for once, at its new address, in both engines.
After the reload Chrome kept the new image from its cache without asking, the PNG’s
answer at the current version being kept for a year; WebKit asked for it again.
With an SVG added to the first screen, whose answer is revalidated, and an image from
another origin at a scheme-relative address, each of 5 returns in WKWebView asked for
neither and had both complete in their first frame, as Chrome did for the SVG.

The rule has its limits.
A version is read when the document is rendered, so a document on screen keeps the image
it has until it is entered again, as it did before.
Which file an address names is decided in the page (`builtin_plugins/markdown/links.js`)
and predicted by the server (`embedded_resources.py`); an address the prediction misses
is left unversioned, and its image is not held.
An image from another origin is held while the page lives, so a change on that host
shows after a reload, as it already did in Chrome.

`test_a_reentered_document_takes_the_images_the_page_holds` checks, in a browserless
DOM, with the production placement and link enhancer running as a mount runs them, which
images are eager, the order in which their attributes change and they are placed, that
an outside image the page holds is eager before it is placed, that a replaced file’s new
version loads lazily, that an unversioned address and one on the page’s own origin are
never held, and the bound and which image goes past it: attributes and the record, not
loading or paint. `tests/golden/cli-ui-markdown-image-reentry.tryscript.md` is its
transcript. `tests/test_raw_versions.py` checks which files a render versions, that a
replaced file gets a new version, and which `/raw` answers are kept and which
revalidated.

## Text Selection

Text selection is content behavior.
Informational text—including errors, logs, file contents, status explanations, and
labels—must remain selectable for search and debugging.
Disable selection only on controls whose primary behavior is clicking, dragging,
toggling, or navigation.
Never put `user-select: none` on a container whose descendants include content.
Do not set `user-select: none` on a broad container because its children are mostly
interactive. A control that shows or hides content is a disclosure toggle and takes the
shared rule in
[Disclosure Toggles Never Select Text](#disclosure-toggles-never-select-text).
Pair every `user-select` with `-webkit-user-select`, which is the only one WebKit reads.

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
