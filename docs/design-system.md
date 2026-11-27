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
   Prefetch whatever the reader is plausibly about to ask for (the subfolders in view,
   or the next surface of the selected file) unless the cost is real and known.
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

**Every color is declared in `oklch`**: there are no hex, `hsl`, or `rgb` literals, and
`tests/test_design_vocabulary.py` rejects new ones.
One notation is not a style preference: `oklch` separates the three things a theme has
to reason about, lightness, chroma, and hue, so they can be compared across tokens and
across themes. In `hsl` they cannot, so a token’s chroma or hue can drift between themes
without anyone choosing it.

> A token defined in both themes names **one color seen against two backgrounds**: its
> **hue is the invariant**, while lightness and chroma are tuned for the background it
> sits on: dark surfaces generally want less chroma, not more.

Near-neutrals are the one exemption: below the near-neutral chroma (`_NEUTRAL_CHROMA` in
`tests/test_design_vocabulary.py`) the hue is not perceptible, so requiring it to match
would constrain a number nobody can see, and would force the dark theme’s cool grays to
adopt the light theme’s warm ones.

Consequences worth knowing:

- A token that needs a different hue in one theme is two different colors and should be
  two tokens with names that say so.
- A token defined in one theme only is a bug in waiting: a literal tuned for a light
  background is unreadable on a dark one.
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

The `agents` plugin keeps the one categorical palette a plugin owns: a color for each
event kind and each tool family, `--agent-kind-<kind>-*` and `--agent-tool-<family>-*`
in `builtin_plugins/agents/agent-log.css`, each with a `-bg` and `-text` for a badge and
a `-fill` for a chart series, a tally bar, or a timeline segment.
A kind is one color in every place it appears, and the agent and the origin are labels,
never colors. `tests/test_agent_kind_palette.py` holds each `-text` to the contrast of
its `-bg` in both themes, each token to its hue between themes, and every pair of fills
in a theme to `MIN_FILL_DISTANCE`, since kinds and families are drawn together.

## File Age

File age is one shared primitive across navigation rows, file headers, recent-filter
menus, Live badges, Group by’s age sections
([Grouping the Files Tree](#grouping-the-files-tree)), and plugin-rendered age labels.
Each state owns two parallel OKLCH tokens in `static/styles.css`:

- `--file-age-<state>` is an accessible text foreground
- `--file-age-fill-<state>` is a translucent surface or area fill

Live is an activity state, not an elapsed-age bucket, but it shares the freshest
reddish-orange token and bold weight with the freshest tier.
That warm family stays distinct from the deeper destructive red and from success green.
The elapsed-age tiers are `AGE_TIERS` in `static/formatters.js`. They move from gold
through yellow-green while chroma and prominence fall monotonically toward a warm
neutral.

Text color is the sole age hue signal; dates and Live labels never gain a dot, swatch,
or adjacent color cue.
Light-theme text takes the hues of the approved reference ramp, reddish orange for Live
and the freshest tier, then a high-saturation yellow followed by progressively quieter
yellow-green and neutral endpoints, at a lightness dark enough to read as UI text and a
chroma high enough to carry the color in the text alone.
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
weight, and tabular numerals.
One builder draws every age shown: `ageLabel` and `ageLabelHtml` in
`static/formatters.js` draw a span of the label in its freshness class, after the call
site’s own class. `retellAge` in `static/plugin-sdk-views.js` tells a drawn age again as
time passes, swapping its freshness class, the one in the `age-` namespace, and keeping
every other. It is not a startup script’s, as only a view that keeps its ages tells them
again. Plugins reach them as `metabrowser.ageLabel`, `metabrowser.ageLabelHtml`, and
`metabrowser.retellAge`. So no surface puts an age on the page without its ink, and a
call site’s class only places the age.
No stylesheet sets an age’s color, weight, size, or numerals but the freshness rule, and
`tests/test_age_single_source.py` holds both halves: no rule whose subject is an age
sets them, and no module paints an age from `formatAge`’s class.
It also holds the `age-` namespace to freshness classes, so a call site names its own
class `<surface>-age`. A Pulls row’s age drew gray when its column’s rule set `--muted`
on it, a selector more specific than the freshness rule’s. It sets no size: an age reads
at the size of the text it sits in, a navigation row’s or a header line’s
([Type Scale](#type-scale)). Dense navigation uses the compact style (`<1m`, `5m`, `2h`,
`3d`, `2w`). Full metadata and conversation cards use the relative style: `2h ago`,
`just now`, or `in 2h` for a future timestamp.
Unknown times have no age label.
The Pulls sidebar, file tree, compact Git history, and the ref selector’s list remain
condensed navigation; PR headers, comments, reviews, full commit summaries and file and
folder view headers use relative ages.
Call sites choose the presentation style and positioning, never their own suffix,
abbreviation, color, weight, or size.
A plugin draws an age with `metabrowser.ageLabel` and puts the exact time in its `tip`,
its `data-tip-text`, on a surface that has tooltips
([Tooltips Add Information](#tooltips-add-information)). `metabrowser.formatAge` gives
the label alone, for words: an accessible name, or a sentence.
Freshness sentences such as “Fetched 2 min ago via GitHub CLI” retain their sentence
formatter. When a summary shows created or opened and updated ages, omit the updated age
when its displayed label matches the closed or merged age beside it, or else the created
or opened age, and add the exact updated time to the tooltip of the age it repeats.

### Ages End the Row

In a list row with an age and no size, a timestamp or an age ends the row, right-aligned
at its end, so the ages of a list read as one column a reader scans down for what
changed last. A Pulls row’s age ends its last line, in a column of one width after its
lines and its chevron ([The Pulls Tab](#the-pulls-tab)), and a stack’s row there ends
with its stack’s age in the same column, after its size
([Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab)); a Commits row’s ends
its line after the author (`.git-graph-age`), a ref selector row’s after its commit
(`.source-ref-selector-age`), an agents session row’s after its title
(`.agents-row-age`), and a guide’s commit row’s after its subject.
A table, such as the agents Sessions table or an event log’s rows, gives its times a
column of their own, so they read as one wherever its columns put it.
An age that is not in a list row stays where its words put it:

- inline prose, such as a freshness sentence, “Fetched 2 min ago via GitHub CLI”, or a
  card’s head, “jlevy commented 3d ago”;
- a page header’s metadata line, “Opened 3d ago · updated 2h ago”, which reads as a
  sentence;
- a single-line item with no column under it, such as a tally, “3,310 commits begun 4mo
  ago”.

A size outranks an age for the row’s end.
When a row shows both, its size or count ends the row, right-aligned, and its age sits
before it, because sizes compared down one column are worth more than ages are.
A Files tree row is the standing case and keeps its layout: its age follows the name
(`.tree-item-age-inline`) and its size or count ends the row (`.tree-item-size`). Only a
row with an age and no size gives the age the row’s end.

`tests/dom/github-pulls-row-lines-chrome.mjs` holds a Pulls row’s age at the row’s end
in Chrome.

## Typography

The shell uses a compact UI face for chrome, a monospaced face for rendered content, and
KPress typography for rendered Markdown.

### Faces: Chrome Is Sans, Content Is Mono

The dividing line is what the text *is*, not how technical it looks.

Chrome (everything the application itself says) uses `--font-sans`. That includes file
paths, and it includes the parent path and every ancestor segment: a path is navigation,
not code, so it reads in the same face as the navigation row it points at.
Key names, shortcut hints, labels, metadata, chips, tooltips, counts, and status text
are chrome too.

Monospace is for the user’s own content, where column alignment carries meaning:
highlighted source, code blocks, Markdown inline code, and raw log payloads.
Numeric alignment on its own does not justify monospace: byte counts, durations, and
timestamps stay sans and use `--tabular-numerals`.

One stack, `--app-mono`, serves all of it: `--font-mono` and KPress’s
`--kpress-host-font-mono` hook both read it, so highlighted source and the code in a
rendered Markdown document draw in the same face.
The face still depends on the engine: SF Mono in WebKit (Safari and the macOS app), and
Menlo in Chromium on a Mac unless the user installed SF Mono.
The measurement behind that order sits beside the token in `static/styles.css`.

The authoritative rule, the current list of deliberate exceptions, and the reasoning for
each live in the `── Typography roles ──` block of `static/styles.css`, next to the
tokens they govern. `tests/test_chrome_typography.py` enforces that list across the host
and plugin stylesheets, so a new monospace use site fails the build until it is
classified.

### Serif Is for Documents

Rendered text is one of two things, and the dividing line is again what the text is:

- **A document** is what the repository holds, rendered as one: a Markdown file in its
  Document view, a README on Overview, a note it transcludes, a Markdown file among a
  pull request’s Changes or opened from a pull request or a commit, and a plugin’s
  Markdown view. It reads in the reader’s reading font: serif by default, and sans when
  the reader chooses Sans.

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

A document’s face rule is in KPress’s `document.css`, so a page that shows one must load
it. A rendered diff loads the stylesheets its projection names, each same-origin one
under `/kpress-static/` whatever KPress’s version (`kpressStylesheets` in
`builtin_plugins/diff/diff-markdown.js`), and warns in the console of one it leaves out
or one that does not load.
Without them, its document reads in sans.

`test_serif_is_only_for_documents` holds which rules may set a face and which builders
mark chrome prose. `tests/test_prose_faces_chrome.py` reads the faces they draw in, and
each Markdown text’s h2 style, in Chrome, under both reading fonts and both font sets,
and a pull request’s rendered Markdown under a development KPress’s addresses.

### Type Scale

Every font size in the app comes from the type-scale tokens in the `── Type scale ──`
block of `static/styles.css`, which holds each token’s value and role.
Never inline a font-size literal at a use site.

**Text is sized by its role, and secondary metadata reads at the size of the text it
accompanies.** An age, an update or fetch time, a count, a size, a row’s second line, a
note, or a caption is never set a step smaller than the text beside it: it steps back by
its ink, muted, not by its size.
So “Fetched just now via GitHub CLI” at the end of a pull request’s author’s row reads
at the body size of the sentence before it, and the repository count in the Pulls tab
reads at the list size of the rows under it.

The chrome has two text sizes, and the one region set apart is the navigation column,
which takes the smaller one throughout, its metadata and its header path included: it is
a dense list in a pane narrower than the main view, read by scanning rather than at
length. Everything else in the main view reads at the body size, its text and its
metadata, a file’s or a folder’s view header and a diff file bar among them; a tree
drawn there is the navigation’s own component and keeps its rows’ size.
The column sets its size once, on `.tree-pane`, so a primitive it shares with the main
view, a notice or an age, sets no size and takes the column’s there and the body’s in
the main view.
Metadata whose container sets the size it reads at sets none, and inherits
it.

| Role | Token | Where |
| --- | --- | --- |
| Page title | `--page-title-font-size` | The title of every [view header](#view-headers): a file’s or a folder’s name, a pull request’s title, a commit’s subject. It stands above the regular first heading of the text below by its bold weight, not by its size |
| Document prose | `--document-body-font-size` | A rendered document and a message, one step above the app body, with KPress’s ramp under it (below) |
| Reading text | `--body-font-size` | The main view’s lines, cards, tables, inputs, notes, and empty and error states; a view header’s metadata line, a file’s or a folder’s size, count, and age; a diff file bar; a commit’s files outside the served folder; every line under a page header’s title, the Diff summary’s header among them ([Page Headers](#page-headers)); a dialog’s prose; a [section heading](#section-headings), in caps |
| Tooltip | `--tooltip-font-size` | The body size; its detail lines set none and read at it ([One Tooltip, and It Is Ours](#one-tooltip-and-it-is-ours)) |
| List text | `--nav-font-size` | The navigation column throughout: its header path, the Files, Pulls, and Commits rows, the [navigation metadata line](#navigation-metadata-line), and the freshness line at its foot; a view header’s eyebrow, its address and mirror note, the twin of the navigation’s path row across the divider ([View Headers](#view-headers)); a tree’s rows wherever one is drawn, the Diff summary’s file list among them; and Quick Search’s results and Help’s commands, the lists in those dialogs |
| Secondary metadata | The token of the text it accompanies | Ages, update and fetch times, counts, sizes, a row’s second line, notes, and captions |
| A short commit ID in a line | The token of the text it sits in | Its line’s size, its monospace face scaled to the sans’s x-height, `--font-sans-ex-height` ([Short Commit IDs](#short-commit-ids)) |
| Controls | `--ui-small-font-size` | Chips and the counts in their menus, badges, buttons, filters, menus, fold expanders, and a tree row’s leading change letter, its slot’s glyph |
| Keycaps and their hint strips | `--kbd-font-size` | A [key](#keyboard-keys), and a strip of hints that labels keys, at the navigation column’s foot and in Quick Search, so a key and its word read as one mark |
| Labels | `--label-font-size` | All-caps tabs, table headers, stat labels, group headings, and dialog titles, at the controls’ size: labels differ by caps treatment, not by another size |
| Monospace blocks | `--mono-block-font-size` | Source, diffs and their hunk headers, review hunks, logs and their event headers, and raw JSON, at the controls’ size |
| Ref chip | `--git-ref-font-size` | One size in every context, the size a chip has in the navigation column: `--git-ref-font-scale` of `--nav-font-size`, and never of the text the chip sits in ([Branch Chips](#branch-chips)) |
| Micro marks | `--micro-font-size` | Marks set deliberately under the controls, never running text: a chip’s count badge, a filled mark inside the chip, and the dot between a stack’s badges, after a stack member’s place in a stack menu, in a Pulls row, and in a guide’s pull request row |

A path reads at its region’s size, and its metadata with it.
The navigation column’s header path is list text, the size of the rows it heads, in a
row of one fixed height.
In the main view a view header’s eyebrow and metadata line, a diff file bar, and a
review comment’s file, in its card’s head, read at the body size, and a view header’s
size, count, age, and mirror note share their line’s size.
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#type-by-role)
has the inventory behind this table.

Document (rendered prose) sizes are a single token:

- `--document-body-font-size`: prose, one step above the app body.
  Anything a reader reads as prose takes it, a pull request’s description and comments
  as much as a README, so the same text is the same size wherever it appears.

Everything else inside a rendered document, such as secondary text, table cells,
captions, footnotes, and code at every tier, belongs to KPress’s ramp, which it derives
from this one value through `--kpress-host-font-size-base` on `:root`. Chrome-context
monospace is a separate concern and uses `--mono-block-font-size`. Diff row reservation
uses the same token and line-height as the rendered rows, so deferred mounting reserves
the height the code occupies.
Browser zoom scales the whole interface; changing the browser’s root font preference
does not selectively enlarge diff code.

Do not add a host token that restates a ratio KPress already owns.
KPress ships *graded families*, secondary text at `small`, `smaller`, and `tiny` and
code at `mono`, `mono-small`, and `mono-tiny`, and steps each by context, because the
smaller tiers land where the surrounding text is already reduced.
A host token collapses the whole family onto one size: a flat mono ratio sets inline
code in a table cell larger than the cell’s prose, and a flat secondary ratio shrinks
table text well under the size KPress intends.

The bridge keeps one size override, because it is a real design difference: the CONTENTS
label uses `--label-font-size` so it matches app labels.
When adding a size, extend the ramp and its comment; do not create a one-off.

`test_font_sizes_come_from_the_type_scale` in `tests/test_design_vocabulary.py` holds
every stylesheet the app ships to this, plugins included.
A literal, or a `var()` that names no token in the table, fails the build unless its
exemption list names the selector and why: a treemap cell’s labels, sized from the
cell’s area, are one.
`test_secondary_metadata_reads_at_its_texts_size` holds the small size to the controls,
the keycaps, the labels, and the monospace blocks, and the micro size to its marks, each
rule that sets one named with its role, so a new rule that gives metadata a smaller size
fails until it is classified.
It holds the navigation column’s one size on `.tree-pane`, the hint strips to the
keycaps’ token, and the metadata named in its `_INHERITED_METADATA`, whose containers
set its size, the notice and a tooltip’s detail lines among it, to setting none; a rule
left off that list is not checked.
`tests/test_age_single_source.py` holds the age primitive and every age call site to
setting none. `tests/test_type_scale_chrome.py` reads the computed size of one of each
role on the Files, Pulls, and Commits panels and the navigation column’s foot, a file’s
and a folder’s header, a commit’s page and its Diff summary’s files, a pull request’s
Conversation and Checks, a tooltip, a menu, Help, and Quick Search in headless Chrome,
and holds each to this table and to the text it accompanies.

### Text Roles

Keep these roles distinct:

- labels and metadata use normal weight and muted text, and metadata reads at the size
  of the text it accompanies ([Type Scale](#type-scale));
- person names use `.actor-name`, and repository names use `.repository-name`: bold
  normal text ink, inheriting the surrounding context’s font size.
  Apply the same person-name primitive to commit authors, PR authors, mergers, comments,
  and reviews, and draw a person with an avatar’s box through the one
  [actor identity](#actor-identity);
- branch names use the shared [ref chip](#branch-chips), including its color and
  hover-to-copy control, in navigation, headers, and histories;
- a commit is named by its [short ID](#short-commit-ids), `.git-commit-sha`, one length,
  monospace, and gray wherever it appears;
- filenames are the identity of a row and carry bold weight at full contrast, while the
  parent path beside them is context and stays regular weight and muted;
- byte counts, durations, timestamps, and numeric table columns use tabular numerals;
- the numbers of a count summary are bold, and its words regular
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers));
- code uses monospaced text without forcing prose into a code style, and paths stay in
  the sans navigation face.

Do not shrink essential text to fit.
Prefer truncation with an accessible full-value tooltip or allow a panel to scroll.

### View Headers

Every page the main view shows opens with one block above its content, a **view
header**, and each kind of page fills the same parts with what it has: a file, a folder,
a pull request, and a commit.

```text
+------------------------------------------------------------------------------+
| [Up] ~/wrk/project / docs / specs /  [copy]                                  |  1 eyebrow, optional; its rule
+------------------------------------------------------------------------------+    the top bar's
| [icon] Title, at the page title's size  33.9 KB · 2h ago  [View on GitHub v] |  2 heading row, 3 metadata; the corner
| DOCUMENT   SOURCE                                                            |  4 tab bar
+------------------------------------------------------------------------------+  the tab bar's rule
| content                                                                      |
```

| Part | A file | A folder | A pull request | A commit |
| --- | --- | --- | --- | --- |
| 1. Eyebrow | Up, the address of the folder that holds it, and Copy path | Up, and the address of its parent; at the served root, the directory that holds the root | Only where it says something the rows under it do not (planned) | The same (planned) |
| 2. Heading row | The navigation row’s icon for its type, and its name and the metadata after it | The folder icon, or at the root its [kind mark](#source-kind-marks), and its name and the metadata after it | Its state icon, its title, and its number | The commit icon, its subject (planned) |
| 3. Metadata | Its badges, size, and age, after its name | Its size, file count, and age, after its name | Its author line, branches, and ages, lines under the title ([Page Headers](#page-headers)) | Its author, revision, and age, lines under the title ([Page Headers](#page-headers)) |
| 4. Tab bar | Its views: Document, Source, and so on | Overview and Treemap | Guided Review when present, then Conversation, Docs, Changes, and Checks | None |
| The corner | [View on GitHub](#view-on-github) | The same | The same | The same |

Files and folders draw these parts today (`viewHeaderHtml` in `static/view-header.js`,
an on-demand bundle the shell fetches beside the view compositor).
A pull request’s page and a commit’s draw their title and lines as
[Page Headers](#page-headers) says, and move onto the same rows, icon, and ground next
(planned). What another kind shares is the class structure, not that builder, which is
the shell’s own: a `.view-header` block holding `.view-header-eyebrow`,
`.view-header-heading`, which holds `.view-header-icon` and `.view-header-title-group`
(the title, `.view-header-title`, and its metadata line, `.view-header-line`), and
`.view-header-end`, the corner, whose rules are the rhythm and the ground below.
A plugin that draws a header, as the GitHub plugin draws a pull request’s, writes those
classes.

**The eyebrow** is a quiet line above the title: context, the address of the folder that
holds the item, whose crumbs are links.
It is the top bar’s half over the main view, the twin of the navigation’s path row
across the divider: that row’s height, `--pane-header-row-height`, its rule,
`1px solid var(--border)`, at the same height, and its text at that row’s size,
`--nav-font-size`, centered as that row centers its path, so the two rules are one line
across the window and the two rows’ text sits on one baseline.
Up is an icon button, the arrow alone at rest and the hover surface and its hairline
only while hovered or focused, as the navigation’s chevron is.
It is a target of `--view-header-up-size`, WCAG 2.2’s minimum target size
(`.view-header-eyebrow > .folder-up` in `static/styles.css`). It is optional by kind.
A file’s and a folder’s always have one, because where a file is matters: Up, which
keeps its place disabled at the served root, and the folders above the item, but not the
item, which is the title under it.
The served root’s whole address, such as `~/wrk/project`, is one crumb that opens the
root: the directories above the served root are not open, so none is a crumb of its own.
Each folder under the root, down to the item’s own folder, is a crumb that opens it, and
each crumb is followed by a slash that is text, never a link, so the address ends in a
slash, as `~/wrk/project / docs / specs /` does, and its last crumb is the folder Up
opens. A long root is cut from its start, so the end of its address survives; a served
mirror’s root is the repository’s name and is cut at its end (`.folder-crumb-root` in
`static/styles.css`). At the served root itself the eyebrow is the directory that holds
the root, dimmed and not a link, since nothing above the root is open.
A pull request’s or a commit’s has one only when it carries something the rows under it
do not, such as the repository and branch it belongs to.
Where a kind has no eyebrow, it writes it empty, and an empty eyebrow is left out: the
heading row starts the header and nothing holds empty space for one.
Where it has one, the eyebrow is the row’s height from first paint, so nothing under it
moves as it fills in.
A file’s eyebrow ends in Copy path, revealed on hover, so the heading row’s width is the
title’s and its metadata’s.

**The heading row** is the kind’s icon, then the title at `--page-title-font-size`,
bold, then a file’s or a folder’s metadata line.
The icon is the one the rest of the app draws for the item, at the title’s size: a
file’s is its navigation row’s icon for its type, through the same function, and a pull
request’s is its state icon.
A file’s or a folder’s name is whole, never cut short: a name too long for the row
wraps, anywhere, so it has no tooltip, since none of it is hidden
([Tooltips Add Information](#tooltips-add-information)), and the icon stays beside its
first line. A pull request’s title is cut short at two lines.
The served root’s header leads with the root’s kind mark, the one the navigation’s
heading draws, because the root is a root wherever its name stands; a folder inside it
leads with the ordinary folder’s ([Source Kind Marks](#source-kind-marks)). The row
holds no controls: the header’s are in its corner.
The header has no print button ([Print](#print)).

**The corner**, at the end of the title’s first line, holds the page’s
[View on GitHub](#view-on-github) button, its label on the title’s baseline.
Its first item is a strut, a line of the title’s type with nothing to see in it, so the
corner’s line is the title’s first line from first paint, and the button opts in to that
line’s baseline as a row’s text does
([Row Text Shares a Baseline](#row-text-shares-a-baseline)), whatever the title’s size
and the button’s measure.
It is placed from the top of the title’s first line, the header’s top pad under the
eyebrow’s row, and from the header’s right edge, at a fixed height
(`--view-header-corner-inset-top`, `--view-header-corner-inset-end`, and
`--view-header-corner-height` in `static/styles.css`), whatever the rows hold, so a
title that wraps or an address that fills the eyebrow never moves it.
Where on that line the button sits is the title’s, its label on the title’s first
baseline, so a native bar that draws the same button matches it from those three tokens
and the title’s type, `--page-title-font-size` and `--page-title-line-height`. The
corner follows the heading row in the reading order.
On a page whose repository is on github.com the corner is marked `data-counterpart`
before the server has answered, and the title’s first line leaves it
`--view-header-corner-room` from first paint, a float of the room’s width at that line’s
end, so the button arriving moves nothing; the title’s lines under the first keep the
row’s whole width. A main view too narrow to leave the title’s first line
`--view-header-title-room` beside the corner’s room, below the width the main view’s
container condition names in `static/styles.css`, puts the corner on the eyebrow’s row
instead, centered on its line as Up is, and the eyebrow’s end leaves it the room, so the
title has the row’s whole width.
A page title breaks anywhere, so beside the room a name the row’s whole width holds
broke mid-word: “docs” in a 260 px main view, “CONTRIBUTING.md” at 380 px, and
“arch-views-models-routes.md” at 560 px.
The title room is sized to hold most file and folder names at the title’s type, by the
measurement beside the token; a longer name can still break beside the room in a main
view a little wider than the condition’s. `tests/test_view_header_chrome.py` holds that
width to the tokens it is made of, and draws those two names one line long at 480 and
560 px, and the second beside the room at 720 px.
A page with no counterpart keeps that room empty: a file that is not committed has none,
and its corner says nothing.
A plain folder, a checkout whose `origin` is on another host or that has none, and a
mirror of a repository elsewhere mark no corner and hold no room.
A pull request’s page and a commit’s place the same corner in the page, on their title’s
first line and at the same end inset, the label on the title’s baseline, and their title
leaves it room only where the reading column reaches it.

**The metadata line** of a file or a folder follows its name in the heading row,
`--page-title-gap` after the name’s last letter and on its baseline, at the body size,
in muted ink; a pull request’s and a commit’s lines sit under their titles, the first
the same `--page-title-gap` under the title ([Page Headers](#page-headers)), so every
page leaves one space between its title and its metadata.
Each value keeps its own primitive: a size its chip, a count its count, an age its
freshness ink ([File Age](#file-age)), the same helpers a navigation row draws them
with. Badges lead and the values follow, each after a muted dot, `.summary-punctuation`,
with the age last: it is the one value that changes while nothing on disk does, “just
now” becoming “1m ago”, and last on its line it moves nothing when it does.

Where the room after the name’s last line does not hold the line, the line wraps whole
to the next line, at the name’s start.
The gap is the title’s end padding, so it stays behind, unseen, at the end of the line
above, rather than indenting the wrapped line.
A line wider than the row wraps between its items: an item and the dot before it are one
box that does not wrap, so no value is cut mid-number, and none is hidden.

While the line stays after the name, the heading row is the top pad and the title’s
line, and a value arriving, a skeleton becoming a number, or an age changing width moves
nothing but the values after it on the line.
Each item is one line of text at the line’s token’s height, so its baseline is its
text’s whatever it holds, and a pending skeleton sits the line where its number will.
At the width where the line no longer fits after the name, it wraps to the next line,
and what is under the header moves down by the line’s height.
That takes a name that nearly fills its row, which is rare, and wrapping keeps every
value in sight where a row of fixed height would cut one.
A folder’s line follows the inventory as it changes (`startFolderHeaderSubscription` in
`static/app.js`); a file’s line describes the content the view loaded, its size and age
when it was read, and a reload refreshes it (planned: following the file’s own change).

**The tab bar** is the one tab style, `.tab-bar` and `.tab-btn`, its labels on the
content’s inset, where a folder’s Overview labels start
([Folder Overview Is a Panel Stack](#folder-overview-is-a-panel-stack)), one tab’s
padding in from the header’s rows.
Every tab bar in the main view sits on `--bg`, a pull request’s among them; a pull
request’s spans its reading column rather than the pane, and moves onto the pane’s width
with the rest of its header (planned).

**Ground and rules.** The header and its tab bar sit on the main view’s ground, `--bg`,
the ground the content under them has: `--sidebar-bg` is the navigation column’s, and
stops at the divider.
The header’s one rule is its eyebrow’s, the top bar’s rule continued across the main
view; there is none between the heading row and the tab bar, whose rule,
`1px solid var(--border)`, is under the tabs, across the pane.
A kind with no tab bar ends its header without one (planned for a commit’s page).
Every ink on the header is one the main view already sets on `--bg`: `--text`,
`--muted`, `--link`, the size chip’s, and the age inks, whose contrast on every age
surface, `--bg` among them, `tests/test_file_age_palette.py` holds.

The rhythm is tokens in `static/styles.css`: the top bar’s row height,
`--pane-header-row-height`, the eyebrow’s; `--view-header-*`, the pad above the heading
row and the pad under the last row, the metadata line’s height, and the corner’s insets,
height, and room; and `--page-title-gap`, between the title and the line after it.
`tests/test_view_header_chrome.py` draws a file’s, a folder’s, and the served root’s
header, and the header of a file whose name no pane holds on one line, in headless
Chrome at four pane widths in both themes, and a commit’s page at two.
It holds the rows to those tokens; the eyebrow’s rule to the navigation path row’s
height and its address to the navigation name’s baseline; the chevron and Up to the
Metabrowser menu’s gear’s line, and Up to no surface at rest and one while hovered; the
View on GitHub label to the title’s first baseline, or in a narrow main view the button
to the eyebrow’s line; the title and the line to their sizes and ink, the line to the
title’s baseline and gap or to the next line’s start; the long name whole over several
lines; the header and its tabs to one ground; every value whole and in sight; and every
box but the line’s own still while the line’s values change and it stays after the name.

### Page Headers

A commit’s page, a pull request’s page, and a native stack’s page open with one kind of
header, a `.page-header`: the title, then its lines, the first `--page-title-gap` under
the title, the space a view header leaves between its title and the metadata line after
it, and the rest one gap apart.
The title is as tall as its own lines, one or two.
A title that held two lines from first paint, so a one-line title left the tab bar where
a two-line one put it, stood its empty second line between the title and its author:
36.5 px of space to the author’s text on a pull request’s page and 34 px on a commit’s,
where a two-line title had 6 and 4 (Chrome 152, 2026-11-18). So moving between pull
requests, or stepping through commits, whose titles take different lines moves the tab
bar and the content under it by a line, as their content differs.
A pull request’s title while its record is on its way lands moving nothing
([The Pull Request Page](#the-pull-request-page)). Every line under the title is a
`.page-header-line` at `--body-font-size`, the Diff summary’s row, the last line, among
them, whose header the diff plugin sets at the same token; the rows that are not are a
pull request’s labels, a row of chips at a chip’s size, and a stack’s members’ card, the
stack menu’s member rows at the menu’s size under a toggle at the line’s
([The Stack Page](#the-stack-page)). An age in a line takes the line’s size, as an age
does everywhere ([Type Scale](#type-scale)). A chip in a line keeps its own size, a ref
chip its [one size](#one-size), and a state badge and a label at theirs
([Label Colors](#label-colors)), and a revision takes the line’s size
([Short Commit IDs](#short-commit-ids)).

A pull request leads with its state and ages, then shows its author and branches.
A commit shows its author, revision, and age in that order.
A stack says the same of all its members, in the same order, and adds the members
themselves, under a toggle above its Diff summary.

| Line | A commit’s page | A pull request’s page | A stack’s page |
| --- | --- | --- | --- |
| Title | The subject, `.page-heading`, its own lines | The state icon, the title, and the number, `.page-heading`, cut short at two lines | The Layers glyph in the state icon’s slot, “Stack Overview”, and the number |
| Author | The [actor identity](#actor-identity) | The actor identity and its sentence, “wants to merge 2 commits” | Every member’s author, each once, and the sentence, “want to merge 12 commits”, or every merger’s once all are merged |
| Where it lives | The revision, its copy button, and its refs | The branches, head → base | The top member’s head → the stack’s base |
| Age | “Committed 3d ago”, muted, the age in its freshness ink | The state badge, then “Opened 3d ago · updated …” and Browse code, and at the end the stack chip’s slot | A state badge for each state a member is in, “2 Pulls Open”, then “Last opened 3d ago · Last update 1h ago” |
| Its own | None | The labels, a row of chips; the freshness note ending the author’s row; the status line, while it has something to say | Every member’s labels, each once; the freshness note of its stalest record; the status line, while it has something to say; the members, top first, the stack menu’s rows in a card under a “**2** Pulls” toggle |
| Size line | “4 files changed · 56.9 KB compressed (193.9 KB raw diff)”, the [change size line](#change-size-line) | “2 commits · 36 files changed · 1.8 MB compressed (6.2 MB raw diff)” | “12 commits · 4 files changed · 2.1 MB compressed (7.0 MB raw diff)”, the commits and sizes of the members the top contains, and the files of the stack’s combined comparison |
| Diff summary | The last line, drawn by the commit’s diff | The last line, drawn from the comparison | The last line, drawn from the stack’s comparison |
| Under the header | The description, a card | The tab bar | The tab bar |

The commit’s age line gives its commit time.
Its refs and the pull request’s branches say where the change lives.
`test_page_headers_set_every_line_under_the_title_at_the_body_size` in
`tests/test_design_vocabulary.py` holds that each page writes the classes on every line
but the labels, and that no rule sets another size on a line.
The pull request adds half the shared line gap above and below its size line and reduces
the padding below its Diff summary by the same total amount.
`tests/dom/git-panel-behavior.js` checks the commit’s header order.
`tests/test_page_header_chrome.py` draws both headers with their Diff summaries and
checks the row order, type sizes, title gap, and gaps around the size lines.
Its measurements are in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#page-headers).

### Actor Identity

A person is drawn through one shell component wherever a page names one with an avatar:
`metabrowser.actorIdentity(name, options)` as nodes and
`metabrowser.actorIdentityHtml(name, options)` as markup, in
`static/plugin-sdk-views.js`. It is a box, `--actor-avatar-size` square and centered on
the line, then the bold name, `.actor-name`, `--actor-identity-gap` after it.
The box holds the person’s avatar where the caller has an https address it vouches for,
and the shell’s person glyph, Lucide’s `circle-user-round` in muted ink, where it has
none; an image that fails to load gives its box to the glyph.
The glyph lives beside the component in the view bundle, not in the eager icon registry,
`static/icons.js`, which every folder’s first paint fetches
([Icons and Icon Buttons](#icons-and-icon-buttons)). The box is there from first paint
either way, so the name starts at one x and an avatar that arrives later or fails moves
nothing. A commit’s page draws its author through the markup form, and the GitHub
plugin’s `authorLabel` builds every author on a pull request’s page through the nodes
form, with GitHub’s avatar, so the box is one size on both pages and core reaches no
plugin for it. A pull request’s author with no usable avatar shows the glyph too, in the
header and on a Conversation card head, so the two pages read alike whether GitHub gave
an avatar or not. A Pulls row, a dense list whose avatar comes with its row, passes
`placeholder: false` and draws no box for an author without one, and so does a stack
menu’s member row, which draws the author its Pulls row has.
A commit’s page has no source of avatars of its own, so its author shows the glyph.
`tests/dom/actor-identity-session.js` holds what each form draws
(`cli-ui-actor-identity.tryscript.md`), `test_a_person_is_one_identity_on_every_page` in
`tests/test_design_vocabulary.py` that both pages draw through it, and
`tests/test_page_header_chrome.py` that both boxes are `--actor-avatar-size`, both names
start at one x, and an avatar of another size arriving in either box moves nothing,
which fails with the box left unsized.

### Count Summaries Bold Their Numbers

A count summary is a line of chrome that says what a list, a tree, or a change set
holds, in numbers and words: “8 files changed · 8 M · +120 −30”, “15,458 files (324.1
MB)”, “3,310 commits begun 4mo ago”.
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
Every count’s numeral takes it, a count summary’s `.summary-number` and a
[heading’s tally](#heading-tallies), `.heading-tally-figure`, and none borrows
`--pull-number-weight`, which a pull request’s number, and a stack’s position read with
it, take. `.summary-number` in `static/styles.css` sets that weight alone: the number
keeps its line’s size and ink, muted in a muted half or note.
A number is the whole figure: its grouping and decimal marks, a sign, a lower bound’s
“+”, and a size’s unit, “394.6 MB”. Parentheses, separators, and words stay regular, and
an age keeps the [age primitive](#age), which has a weight of its own.

**In a count summary, the separators and the list punctuation are muted, the numbers
bold, and each status count bold in its status’s color, its number and its letter
alike.** The “ · ” that sets a line’s groups apart and the comma between a list’s
entries are `.summary-punctuation`, which sets `--muted` and nothing else, so the counts
and the words read and the marks recede: “**19** files changed · **10 A**, **5 D**, **4
M** · +1,234 −567”, its dots and commas gray, and “10 A” green, “5 D” red, and “4 M”
ochre. A status count, “10 A”, is a file change status’s count and its letter, the badge
its rows carry, as one unit, `.summary-status-count`: both are bold, at
`--count-numeral-weight`, and both are in the status’s color, which the shell’s status
primitive on the same span, `.file-change-status`, sets
([File Change Status](#file-change-status)), so each count reads as its status and the
counts of a list read apart from one another.
Each status’s color keeps a text’s 4.5:1 contrast, at the line’s size and bold weight,
on every ground a count summary is drawn on, the page, the sidebar, a hovered header,
and a tooltip, in both themes.
A count that is not a status’s, as “19 files changed”, is a number, bold, in the line’s
ink, and its words keep the line’s ink and weight.
The dot is hidden from assistive technology, as a heading tally’s is, and a line that
shows letters tells a screen reader its statuses in words, “19 files changed: 10 added,
5 deleted, 4 modified”, so no letter is read out.
Where the line has no name that says it in words, as a paragraph or a plain line has
not, a comma is said in each hidden dot’s place, in the shell’s `.visually-hidden`. A
note that qualifies the line’s figures, as the Diff summary’s “(estimated)”, is muted
with its parentheses, as the marks are.
Each dot sits with the group before it, so a line that wraps breaks after a dot and no
line starts with one.
Parentheses around a figure, as the Files totals’ size, and a sign, which is part of its
number, are not this punctuation.

A count summary’s text comes in one shape of parts (`MetabrowserCountPart` in
`static/types.d.ts`): the words as strings, each number as `{number}`, a list’s comma as
`{punctuation}`, a separator’s dot as `{separator}`, with `spoken` for the comma said in
its place, and a status count as `{status, letter, count}`; “12,797 files” is
`[{number: "12,797"}, " files"]`, and “10 A” is
`[{status: "added", letter: "A", count: "10"}]`. They have one painter, in
`static/formatters.js`, which paints each kind in its one class: the shell paints
through `countPartsHtml` and `countPartsNodes` on `window.MetabrowserFormatters`, and a
plugin through the SDK’s `metabrowser.countPartsNodes` ([plugins](plugins.md)), as the
Diff summary and the Checks summary do.
What a change set holds is said once, by `changeSummary` beside them, as its file count
and its [brief change line](#brief-change-line): the Diff summary’s header and a
commit’s hover card say it in its words.
The words and numbers of one phrase sit in one inline element: in a flex line, as a
navigation metadata line is, each would be an item of its own, parted by the line’s gap
and read as a run of its own.
So the line’s text and accessible name are unchanged: the span adds no words, the spaces
stay where they are written, and a header with an `aria-label`, as the Diff summary’s,
keeps it.

| Count summary | Where its numbers are painted |
| --- | --- |
| The [Diff summary](#diff-summary)’s header and its fallback totals line, on a commit’s page, in a pull request’s header, and in a patch’s toolbar | `renderDiffSummary` and `summaryOrTotals` in the diff plugin’s `diff-view.js`, through `metabrowser.countPartsNodes` for its file count and `metabrowser.changeLine` and `metabrowser.changeLineNodes` for the [brief change line](#brief-change-line) after it, from `describeChanges` (`filesParts`, `line`) and `plainTotals` (`filesParts`, `change`), with its status counts and its muted dots and commas, and through `listedNote` for a list cut short, “(2,000 listed)”; its line totals are the inline change stats, bold already |
| A commit’s totals line, in its Diff summary’s place until the commit’s diff draws the summary there, and where it is not drawn | `renderCommitTotals` in `static/git-panel.js`, through `changeSummary`, `countPartsHtml`, and `changeLineHtml`, in the Diff summary’s words and paint ([Git Commit Summary](#git-commit-summary)) |
| The Files totals, tracked and ignored, and the live figures | `treeSummaryHtml`, `treeSummaryCountHtml`, and `treeSummarySizeHtml` in `static/navigation.js` |
| The Files filter’s remark, “Filtered to 1,234 files.” | `filteredTallyParts` in `static/tree-filter-model.js`, painted by `_renderFilteredTally` in `static/app.js` in one span of its line |
| The Commits tally | `renderHistorySummary` in `static/git-panel.js` |
| The Pulls count, “448 pull requests · 12 open” | `.github-pulls-total-line` in the GitHub plugin’s `pulls-panel.js` |
| A Pulls stack row’s size, “Stack #286 · 4 pulls” | `paintStackRow` in the GitHub plugin’s `pulls-panel.js`, through `metabrowser.countPartsNodes`, after the stack’s label ([Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab)) |
| A pull request’s Checks summary, “Some checks were not successful: 1 failing · 3 successful” | `paintChecks` in the GitHub plugin’s `pull-page.js`, through `metabrowser.countPartsNodes`, after `gh`’s headline, its dots `.summary-punctuation` in a line muted already, each saying a comma in its place |
| A commit’s files outside the served folder, “2 files outside this folder” | `renderCommitDetail` in `static/git-panel.js`, in one span of its line |
| A commit’s hover card, “32 files changed · 56.9 KB compressed (193.9 KB raw diff)” over “4 A, 28 M · +1,921 −160” | `renderCommitChangeStats` in `static/git-panel.js`, through `changeSizeLineHtml`, `changeSummary`, and `changeLineHtml`, in the size line’s and the Diff summary’s words and paint ([Git Commit Summary](#git-commit-summary)) |

The rule does not reach a number that is not a count summary’s:

- row metadata, as the right-aligned size and count of a tree row, and the size, count,
  and age of a view header’s metadata line, which the size and count chips set by their
  own threshold;
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
`test_count_summaries_mute_their_punctuation_and_ink_their_status_counts` holds
`.summary-punctuation` to `--muted` alone, `.summary-status-count` to the count’s weight
alone, every surface to the one painter, and the diff plugin and the Checks summary to
writing none of its classes themselves, and `test_file_status_ink_is_shared_and_legible`
each status’s color to 4.5:1 on each ground in both themes.
`tests/dom/count-parts-session.js` pins each kind’s markup, the SDK’s nodes to the
shell’s, and `changeSummary`’s words (`cli-ui-count-parts.tryscript.md`);
`tests/dom/diff-view-behavior.js` holds the Diff summary’s status counts and marks by
class, `tests/dom/git-panel-behavior.js` the hover card’s, word for word the Diff
summary’s, and `tests/dom/github-pull-core-preview-behavior.js` the Checks summary’s.
`tests/dom/diff-summary-chrome.mjs` reads the inks and weights on a commit’s Diff
summary in both themes, and `tests/dom/git-commit-summary-chrome.mjs` the hover card’s:
each status count’s number and letter bold at its status’s token, with its contrast on
the ground under it, the file count bold at `--text` with its words regular, and each
mark at `--muted`; with `.summary-status-count`’s rule removed, both fail.
The latter holds too that the commit page’s header starts no line with a dot at any
width from 60 to 400 px, and the hover card none from 60 to 360 px, 1 px apart, and that
with each dot’s group dissolved both sweeps find a dot starting a line.
A heading tally’s dot (`.heading-tally-dot`) is muted with the rest of its tally, and is
not painted from these parts.

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

### Main View Gutter

The main view’s gutter, `--content-padding-x`, and its block pad, `--content-padding-y`,
step up with the window, so a wide window’s page has room against the navigation pane
and the window’s edge, and a narrow window keeps its tight gutter.
The narrow values are the `:root` rule’s in `static/styles.css`, and the window steps
are the `@media (min-width: …)` rules right after that block, with the measurement that
set them.

The window decides rather than the main view, which is the one place the shell sizes
against the viewport: hiding the navigation pane changes the main view’s width, and a
gutter keyed to it would jump at every toggle.
Everything made from the two tokens follows, the view header’s top pad and corner inset,
the chevron centered in the gutter, and every plugin that pads by them.
A view header’s narrow container condition is computed from the narrow gutter; see the
comment beside the steps for the one case, a navigation pane dragged very wide in a wide
window, where that is not exact.
`tests/test_reading_column_chrome.py` measures the steps in headless Chrome.

### Reading Width

Prose reads at a width the reader sets, in **characters**, through “Max text width” in
the Metabrowser menu.
Characters rather than a length because that is the decision a reader has: 45–75 is the
classic range for a single column, and a browser pane is wide enough to sit above it.
The default is `DOC_MAX_CHARS_DEFAULT` in `settings.py`, and a reader can choose a
narrower target in the same control.
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
the reader’s setting, and a README on Overview would read at a different width from the
same file opened on its own.
`--doc-measure` is app-owned and cannot be shadowed.
One bridge, `.metabrowser-kpress-host .kpress { --kpress-measure: var(--doc-measure) }`,
carries it into the document.

The advance ratio is measured, not assumed, for each reading face, and the sans reading
mode swaps the ratio so the same character count still holds; the measurement and its
procedure are beside `--doc-char-advance` in `static/styles.css`. It is the average
advance, not the CSS `ch` unit, which is the advance of “0” and overstates a
proportional face. KPress ships no per-face constants because a host may swap the face;
Metabrowser pins its own faces, so it owns the conversion.
Size and character-count changes are CSS inputs.

Verify a width change by measuring the *text* box with padding excluded, in both the
single-column and wide bands, and against the same file opened on its own.
A card can be the right width while the text inside it is an inset-pair too narrow.

### Rendered Markdown Layout

Document and Source keep the same outer pane gutter, `--content-padding-x`. Card borders
and source surfaces start at the first tab’s outer edge.
KPress keeps its normal padding inside the card, wider in the single-column band than in
the wide band, with its compact prose gutter on narrow panes.
Source and Raw keep their code-block padding and line-number columns inside the shared
outer gutter. KPress’s card and `--doc-measure` cap the reading column.
In KPress’s wide document band, a document with a table of contents puts the sticky
KPress rail to the right of the prose.
A thumbnail sits above the prose.
In KPress’s wide document band, a standalone table can grow past the prose column to its
natural width, up to the room in the reading pane.
The prose keeps its reading measure.
A sticky table of contents sits at the pane’s trailing edge on a page with a top-level
table, leaving the area before the rail available for the table.
A table that needs more room scrolls in its own container.
`tests/test_reading_column_chrome.py` measures the layout using the pipeline
architecture document’s three-column table.

In medium and narrow panes, tables follow KPress’s own layout, and the table of contents
opens from the trailing gutter to keep the beginning of each line clear.
The Folder Overview README shares the same prose edge and maximum measure, and its
tables stay within its panel.
Its panel headings and bodies follow the document card’s outer edge.
Their text starts on the active tab’s label rather than at the README’s responsive inner
inset; see [Folder Overview Is a Panel Stack](#folder-overview-is-a-panel-stack).
It keeps the table of contents the same file has opened on its own: in the wide band the
rail sits to the right of the card’s edge, and below it the overlay’s toggle keeps its
trailing gutter; see [Embedded Document Navigation](#embedded-document-navigation).

### Boxed Prose

A bordered box that holds prose gives that prose one inline padding, on each side:
`--boxed-prose-padding-inline`, declared once on `:root` in `static/styles.css` beside
`--content-padding-x`, with the measurement that set it.
It is the room between the box’s edge and the text, so a heading that opens a text is
never nearer the border than a paragraph is.
It replaced the pane inset, `--pane-header-padding-x`, which is the navigation column’s
alignment inset and not a reading measure: with it, an h2 in a pull request’s
description sat a few pixels inside the border and read as touching it (owner,
2026-11-20). No box that holds prose writes its own literal.

| Box | How it takes the token |
| --- | --- |
| A pull request’s description, a comment, a review, and a review comment | `.github-pull-text`’s padding is `--github-pull-text-inset`, which the page sets to the token |
| The head of those cards, a commit’s row in the Conversation, and a review comment’s hunk lines | The same `--github-pull-text-inset`, so a head’s avatar and the text under it start at one x, and the timeline’s line down the avatars’ centers moves with them ([Conversation Timeline](#conversation-timeline)) |
| A commit’s message on its page | `.git-commit-body`’s inline padding, a message set as a pull request’s description is |

Four kinds of box keep their own padding, each for a reason:

- **A rendered document’s card**, a Markdown file’s or the Folder Overview’s README.
  KPress draws the card’s border only where its pane is wide enough for the card, and
  pads the text there by its band’s inset, wider than the token; below that the card is
  full-bleed and draws no border, so there is no edge for a heading to crowd
  ([Rendered Markdown Layout](#rendered-markdown-layout)).
- **A rendered Markdown diff’s blocks.** They pad `--content-padding-x` inside the diff
  file’s frame, a wider inset than the token, and their left edge is the change gutter,
  not a reading box’s.
- **A notice**, which holds the application’s own sentence and a control rather than a
  document’s prose, and sets its own padding ([Notices](#notices)).
- **A toolbar, a header row, or a tree row** that carries `--pane-header-padding-x`:
  they align with the navigation column, which is what that inset is for.

The pull request page and a commit’s page hold the only prose in a bordered box, and no
hover card or callout holds Markdown, so a new box that does takes the token, and a new
kind of box is added to the table.
`test_boxed_prose_takes_one_inline_padding` holds the declaration and each box’s use of
it, and `tests/test_github_pull_text_chrome.py` measures the padding the boxes lay out,
in a wide and a narrow pane, with nothing padded twice and no overflow.

### Rendered Diff Spacing

A rendered Markdown diff, in a pull request’s Changes and Docs, is the document it
compares, so it spaces its blocks as the Document view of the same text does: the
distance from one block’s text to the next block’s is the Document view’s, between two
unchanged blocks, beside a changed one, and with its removed blocks hidden, which leaves
the new version. A reader who opens a file’s Document view and then its diff reads one
rhythm.

Each block of the diff is a row of its own, `.diff-markdown-block` in the diff plugin’s
`styles.css`, and a row sets no block padding or border.
So a block’s KPress margins pass through its row and collapse with the next row’s, as
two blocks of the document collapse.
A row used to pad its block and keep the block’s margins inside it, so two blocks’
margins added up, and an h2 sat well below where the document puts it
([Rendered Diff Block Spacing](../explorations/performance-loop/design-rule-measurements.md#rendered-diff-block-spacing)
has the before and after).

- **A change’s band** (its fill and its change gutter) is one box for each run of
  changed blocks of one kind, so consecutive added blocks read as one band and
  consecutive removed blocks as another, with nothing between them.
  `changeRuns` in the diff plugin’s `diff-markdown.js` places each run of changed rows
  in a `.diff-markdown-change`, and each run of one kind in it in a
  `.diff-markdown-run`, whose `::before` draws the band; a row draws none.
  Neither wrapper sets block padding or a border or starts a formatting context, so the
  rows’ margins collapse through them as they do through a row, and the band, which is
  drawn rather than laid out, moves no text: a block sits where it sits with no band at
  all. The band spans the run’s rows and the space between them, and reaches
  `--diff-markdown-band-extent` past the first row’s text and the last row’s, behind the
  text of every block, since the article isolates its paint.
  Current hides a change’s removed runs, and the change then draws one added band across
  the runs left, which draw none, so the edits it shows read as one band too.
  A removed run meets an added run only across the space between two blocks, and the
  extent is half the least of those, so their bands meet there at most and never overlap
  into a darker seam. An article drawn a chunk at a time joins a chunk to the change on
  either side of it (`joinChanges`), so a run that crosses chunks is still one box.
  When each row drew its own band, two changed blocks in a row left the document’s space
  between them unpainted, less the two extents: a 24 px gap from a paragraph to an added
  h2.
- **A list or a quote split into rows**, as a changed list is, one row per item, reads
  as one: between two rows of one list or quote, its own margins give way, so its items
  are spaced as KPress spaces them inside it, and its first and last rows keep the
  margins that set it apart in the document.
- **KPress’s rules that key on a previous sibling** see none, since the previous block
  is in another row. A paragraph straight after an h4, h5, or h6, which KPress sets close
  under it, is joined across rows, and past the removed run that Current hides, which
  leaves the heading the block before the paragraph.
  `h2 + h3` is not: joining it would restate KPress’s margin, so an h3 straight after an
  h2 keeps the space it has after a paragraph, a little more than the document’s.
  `markJoins` in `diff-markdown.js` marks each row from the rows shown before and after
  it, so no selector has to name the changes, runs, hidden removed runs, or chunk edges
  that may lie between two rows; a list or quote continued past a hidden removed item
  joins the same way.
- **The fold of unchanged blocks** is the diff’s [fold bar](#fold-expanders) and the
  group it opens, whose rows are its content.
  The group clips its content with `overflow: clip` where a code file’s fold uses
  `hidden`, which would start a formatting context and keep the last block’s margin
  inside the open fold.
- **A table** is the one block the rule does not reach yet.
  `withoutRenderWrappers` in `static/inert-html.js` unwraps the `<div>` KPress keeps
  around a table when it is the block’s only element, so the diff’s table has no
  `.kpress-table-wrap` and none of the wrapper’s margins.
  So an edited table’s removed and added versions have no space between them, and their
  bands overlap by two extents.

`tests/test_diff_markdown_spacing_chrome.py` measures the diff, the diff with its
removed blocks hidden, and both versions’ Document views in Chrome, in the serif and the
sans reading font, and holds every gap to the document’s and the h2-to-h3 case to the
h3’s own space. No test restates the band’s geometry or colors: the band is one box per
run by construction, and `tests/dom/diff-markdown-session.js` fails on any rendered row
placed otherwise, a changed row outside a run of its kind, two runs of one kind side by
side, or two changes side by side, through every step it plays, a long document’s chunks
drawn out of order among them.
It and `tests/dom/diff-current-session.js` also fail on a row shown without its joins,
or with joins the rows shown around it no longer make.
`tests/test_diff_markdown_fold_chrome.py` measures the fold closed and open.

### Embedded Document Themes

Metabrowser owns one theme input for the embedded document:
`data-kpress-resolved-theme="light|dark"` on the root.
KPress fragments carry no theme or palette attributes, so one cached render works in
both modes and a toggle never has to chase rendered elements.
The default fragment manifest omits KPress’s standalone theme resolver; the host loads
the entry points the manifest declares without maintaining a second exclusion list.
KPress’s symmetric theme selectors keep its palette and `color-scheme` aligned, while
the bridge maps the public `--kpress-doc-*` color tokens to Metabrowser’s semantic
surface, text, border, muted, and link tokens, and KPress’s corner tokens to the app’s
square corners. It keys on every KPress fragment in the page, not on
`.metabrowser-kpress-host`: a rendered Markdown diff mounts its `article.kpress` in the
diff plugin’s host, so a bridge on the document host left it in KPress’s own palette.
Tooltips, which KPress portals to the body, have always had a rule of their own,
`:root .kpress-tooltip`.
`test_the_app_owns_the_palette_and_corners_of_every_kpress_fragment` holds the scope,
and `tests/test_diff_markdown_fold_chrome.py` measures a rendered diff’s quote and code
against a document’s in both themes.

### Embedded Document Navigation

Metabrowser requests KPress’s normalized TOC collapse depth `1`, which keeps the
top-level section spine visible and lets scroll-follow open the active deeper branch.
At KPress’s wide document band, the docked TOC is a borderless rail with a hidden but
scrollable scrollbar.
The narrow overlay drawer keeps its border and visible scrollbar so it remains distinct
from the document it covers.

The overlay’s toggle belongs to its document.
It fades in once the pane has scrolled past KPress’s threshold and the reader has
reached the document, whose top is at or above the pane’s, and fades out above the
document or past its end.
An opened file’s document starts below its view header and tab bar, and a folder
Overview’s README below File Overview, both further down than the threshold, so the
toggle appears as the reader scrolls to the document’s beginning.
One rule in `builtin_plugins/markdown/toc-toggle.js` serves KPress’s table of contents
and an inert render’s.

A document’s fragments are places on the page that shows it.
On a folder’s Overview, a README entry or a link to one of its headings scrolls the
Overview and puts the fragment on the folder’s address, as GitHub’s repository page
does, rather than opening the README as a file.

### Print

Printing is the browser’s, and nothing in the shell stands in front of it.
Command-P, or Control-P outside macOS, prints the view shown, as Print in the macOS
app’s File menu does.
The print stylesheet hides the shell’s chrome and prints the active view when it is
printable, or a line saying it is not (`static/styles.css`, “Print adapter”). No page
handler takes either chord ([Browser and App Keys](#browser-and-app-keys)).

The shell’s header has no print button.
A rendered document whose view prints the document itself carries one, in the upper
right corner of its card: the Markdown file’s Document view, and the README on a
folder’s Overview, whose one printable panel is the README. A Markdown mount draws it
only when its host asks, with `printIndicator: true`, so a source view, a rendered diff,
and any other host have none, and Command-P is their print.
It is the `.icon-btn` primitive, bare at rest, named and labelled “Print document”, and
it calls `window.print()`, the print Command-P runs.
It is the page’s own control in the document, marked with `mb.ownDelegate`, which the
tooltip recognizes by the element itself, so it keeps the app’s tooltip there, and a
document that spells its markup, owner value and all, neither prints nor labels itself.
It comes last in the card, after the document’s text, so it is last in focus and reading
order though it is drawn at the top: placed first, it would take the place the card’s
leading-heading rules give its first heading.
Command-P is the keyboard route to print, wherever focus is.

The button sits in the card’s padding and covers no text.
It is centred in a corner square, `--print-indicator-corner` in
`builtin_plugins/markdown/markdown.css`, no larger than the card band’s block-start
padding and trailing inset, and it is absolute against the card, so its arrival moves
nothing. It is shown only on a card KPress draws (`data-kpress-card="on"`), under the
same container query on the pane as KPress’s card rule; narrower, KPress draws no card
and pads the text too little to hold it, so it is not shown.
markdown.css records KPress’s lengths beside the token.
The narrow table of contents toggle sits in the trailing gutter outside the card
(`--kpress-toc-toggle-clearance`), and the wide band’s rail beside the card, so neither
meets it. `tests/test_document_print_chrome.py` measures the placement, the stillness,
the toggle and the rail, the tooltip, a click, and print output, trusted and
`--untrusted`, and `tests/dom/markdown-print-indicator-session.js` holds which mounts
carry the button.

A rendered document prints in KPress’s print model, the page KPress’s own PDF export
draws: its `print.css` on white paper, its page margin and footer, and its static print
faces. Its card, the app’s chrome, and the app’s theme do not print.

- **Ready first.** A click on the button waits for the document before it prints
  (`builtin_plugins/markdown/print-ready.js`, at most `PRINT_READY_BOUND_MS`): its
  images not yet shown, which KPress loads lazily and WebKit prints as nothing; KPress’s
  print sans, which loads only once print layout asks for it, so a print drew the
  variable face’s Type3 outlines instead, as KPress’s export waits for it; and its
  diagrams. Command-P waits on nothing: Chrome loads the images itself, and the app’s
  File > Print prints what the page holds.
- **Light paper.** While a rendered document is mounted, a print resolves the page light
  and restores the theme after it (`holdLightPrintTheme` in `print-indicator.js`), and
  the app’s color bridge to KPress is screen-only (`static/styles.css`), so text, links,
  and code are KPress’s print ink whatever the theme.
- **What WebKit leaves out.** The macOS app prints with WebKit, which resolves no custom
  property in `@page`, applies no break rule inside a grid item or a size container, and
  ignores `break-after: avoid`. So the page margin is KPress’s token written out
  (`static/styles.css`, “Print adapter”); the document is one block column outside any
  container in print; and a heading reserves room below it for the next lines, and for
  an image under it the image’s own height, so it never ends a page alone
  (`builtin_plugins/markdown/markdown.css`). WebKit draws no `@page` margin boxes, so
  the app’s print has no footer or page numbers.
- **Authored alignment.** A README’s `align="center"` logo and title stay centred, which
  KPress’s print rule for paragraphs, justified, otherwise overrode.

`tests/dom/document-print-chrome.mjs` holds the print model in Chrome, and
`apps/macos/webkit-gate`’s driver (`webkit-driver print`) prints through the app’s own
path for a check by hand.

KPress’s `doc-actions` widget, an opt-in cluster pinned to its card’s corner, is where
the button belongs once KPress can carry it in an embedded document, as an option the
host turns on.
Until then `builtin_plugins/markdown/print-indicator.js` draws it, and its
header says what KPress lacks.

## Repository Details

The root icon and name in the navigation column link to Home.
The folder glyph identifies a local folder, a Git checkout, or a cloud mirror.
The adjacent Info button opens the root’s details.
Its accessible name and tooltip identify the kind, for example “Local folder details”.
The tooltip clears while the menu is open.
The circled i has a distinct dot and foot at sidebar size.
It uses the shared icon-only button with muted ink at rest and the same highlight on
hover, focus, or while the menu is open.
Its button owns the open state and closes as
[every menu closes](#every-menu-closes-alike).

The menu shows information about the folder, including its local path, file count, size,
and commit when available.
Mirrors and pinned checkouts include a short note about where the files come from.
The branch or tag and its actions are in the [Files revision row](#the-ref-selector).

If the root has a recognized GitHub repository, its URL appears above **Copy Link** and
**Open in Browser**. The copy glyph and external arrow are the same as those in the
[ref action menu](#action-menu) and the [View on GitHub menu](#view-on-github), which
operate on their own destinations.

## View on GitHub

Every page that github.com has a page for has one **View on GitHub** button, in the same
place: its header’s [corner](#view-headers), at the end of the title’s first line, its
label on the title’s baseline, on a file’s, a folder’s, a pull request’s, a native
stack’s, and a commit’s page alike.
It is the one way to a page’s github.com counterpart, so no page also links to it from
its metadata.

```text
 ( [GitHub] View on GitHub | v )
                          +-----------------+
                          | Page URL        |
                          | Copy Link       |
                          | Open in Browser |
                          +-----------------+
```

It is a split button, a [joined chip group](#control-families) of two parts:

- **The link**, the provider’s mark and its label, in the text ink.
  It is a real link to the counterpart, so a new tab, a copied address, and a screen
  reader all get the address; in a browser it opens the page in a new tab, and its
  tooltip is the address.
- **The chevron**, a chip menu’s trigger with the shell’s caret, muted until the pointer
  is on it or its menu is open.
  The menu shows the full destination URL above **Copy Link** and **Open in Browser**.
  Copy Link puts the address on the clipboard and says “Link copied”, or “Copy failed”,
  for a moment in a status line under the button, where the menu was, which a screen
  reader announces as a polite live region; Open in Browser is a link to the same
  address in a new tab.

Both parts take a chip’s hover fill and focus ring, from tokens in both themes.
The menu is the shell’s `.menu` of `.menu-item` rows, opened under the button with its
right edge on the button’s. It is a menu button’s menu: a click or Enter on the chevron
opens it with focus on its first item, ArrowDown or ArrowUp on the chevron opens it at
its first or last item, and the arrow keys, Home, and End move among the items.
Escape, a second click on the chevron, or choosing an item closes it and gives focus
back to the chevron; Tab or a press outside the button closes it and leaves focus where
the key or the press puts it, and so does focus that moves to another element, such as a
framed preview, which sends the page no press.
A key held with Command, Control, or Option is the browser’s and the app’s, as on every
page, but Option-Tab, with which Safari moves focus, closes the menu as Tab does.
The button is not numbered for the header’s number keys: it is the page’s, not a control
in a row.

The provider supplies the label, the mark, and the address, so the same component draws
another host’s counterpart; GitHub is the one provider today.
The button is `counterpartButton` in `static/plugin-sdk-views.js`, the on-demand view
helpers, and `mountCounterpart` asks the server for a page’s counterpart and puts the
button in a corner, once per address; both are on `window.metabrowser` for a plugin, as
the pull request page uses them.
The button comes with its header when it can: the shell asks for a file’s or a folder’s
counterpart as the page starts loading (`prefetchCounterpart`), and a page drawn again
shows its last answer at once and replaces it only when the server’s new one differs.
Another place that shows a page can hold the same button by giving it a corner.

**The macOS app** shows a counterpart in a native popover of its own rather than leaving
the app. The web page does nothing for it.
The root carries `data-view-on-<provider>`, as `data-view-on-github`, which names the
button, and the app reads two hooks on its links, a contract between the two that names
no site: the link is `<a data-web-view="open" href="…" target="_blank" rel="noopener">`,
and Open in Browser is
`<a data-web-view="external" href="…" target="_blank" rel="noopener">`. The app takes a
trusted primary click on the link for its web pane, when the `href` is on a site it
knows; Open in Browser, a modified click, and Copy Link do what they do in a browser.
Any other control may mark a link `data-web-view="open"` the same way.

### Where It Appears

A page has a View on GitHub control when github.com has a page for the same thing.
`GET /api/counterpart?page=<page>` (`src/metabrowser/counterpart.py`) is the one source
of where it goes: it answers the URL, or `null` and the reason there is none, and no
page builds a github.com URL itself.
`PAGES` in that module is this table, and `tests/test_counterpart.py` holds the two
together.

Each counterpart starts with `https://github.com/<owner>/<repository>`. At the
repository root, the default branch opens that URL and a named nondefault branch opens
its branch tree.
For a file or folder, `<ref>` is the branch or tag when the last fetched
version has the path, and otherwise the commit.
For a working tree, that commit is the newest one origin has in `HEAD`’s history.
That is `HEAD`’s own commit once it is pushed, and before then its merge base with the
upstream branch, or else with origin’s default branch.
So neither unpushed commits nor a file’s local edits take a page’s button away: it links
to the version origin has.
Only a path no commit origin has holds goes without one.
`<hash>` is GitHub’s anchor for a changed file, the SHA-256 of its path.
Every page also has none when the served folder has no repository on github.com
(`no_repository`), and an address that is none of these pages has none (`not_a_page`).

| Page | Counterpart | Other reasons it has none |
| --- | --- | --- |
| `/view/<path>` | `blob/<ref>/<repo path>` | `uncommitted`, `untracked`, `ignored`, `missing`, `not_on_origin` |
| `/view/<path>/` | `tree/<ref>/<repo path>` | `uncommitted`, `untracked`, `ignored`, `missing`, `not_on_origin` |
| `/view/` | `tree/<ref>/<served prefix>`, or repository URL or `tree/<name>` at the repository root | `uncommitted`, `untracked`, `ignored`, `missing`, `not_on_origin` |
| `/pull/<n>`, `/pull/<n>/conversation`, `/pull/<n>/files`, `/pull/<n>/guided`, `/pull/<n>/checks` | `pull/<n>`, `pull/<n>`, `pull/<n>/files`, `pull/<n>`, `pull/<n>/checks` | None |
| `/pull/<n>/files/<path>` | `pull/<n>/files#diff-<hash>` | None |
| `/commit/<sha>` | `commit/<sha>` | `not_on_origin` |
| `/commit/<sha>/<path>` | `commit/<sha>#diff-<hash>` | `not_on_origin` |
| `/pulls` | `pulls` | None |
| `/stack/<n>`, `/stack/<n>/guided`, `/stack/<n>/docs`, `/stack/<n>/changes`, `/stack/<n>/changes/<path>` | `stack/<n>` | None |

`CounterpartReason`, beside `PAGES`, says what each reason means.
A file and a folder are told apart by the commit’s tree, not by the trailing slash.
There is no page of a branch’s commits to map: the Commits tab is a pane, not an
address. The pull requests’ list, `/pulls`, has a counterpart but no header to hold the
button yet. Every other page in the table draws it: a file’s, a folder’s, and the served
root’s view header, each of a pull request’s tabs and the changed file Changes is at, a
commit’s page, and each of a native stack’s tabs.
A stack’s page, each of its tabs, and each file its Changes is at open GitHub’s page of
the whole stack, `stack/<n>`: the stack is the page’s subject, and its top member’s pull
request is one member of it ([The Stack Page](#the-stack-page)).

## Control Families

Every button belongs to one role-specific primitive:

| Role | Primitive |
| --- | --- |
| Labelled action | `.btn` |
| Icon-only action | `.icon-btn` |
| Filter value or filter menu | `.chip` and its variants, with `.chip-clear` the quiet reset ([Filter Controls](#filter-controls)) |
| Exclusive choice among labelled values | `.chip-group[data-select="one"]` |
| Menu row or segmented menu choice | `.menu-item` or `.menu-seg` |
| Tab | `.tab-btn` |
| Collapsible section title | `.section-disclosure-trigger` |
| Lines or content folded in place, which a press shows | [`.fold-expander`](#fold-expanders) |
| Action among links: a text action, below | The context’s text-action class, on `<a>` and `<button>` alike |

These primitives share the type scale, radii, semantic colors, focus treatment, and
motion tokens, while their shapes communicate different interaction roles.
A use-site class may add positioning, visibility, or domain state, but it must carry the
primitive class in the markup and must not recreate the primitive’s border, fill,
typography, or focus rules.
Every non-submit button declares `type="button"`, and every icon-only button has an
accessible action name.
`test_every_plugin_button_carries_a_control_family_class` and
`test_every_shell_button_carries_a_control_family_class` in
`tests/test_plugin_design_consistency.py` hold every button the built-in plugins, the
shell’s modules, and the server’s markup build to one of these, or to an allowlisted
class with its reason.
A control that asks for something again takes its word and its widget from
[Refresh, Retry, and Reload Page](#refresh-retry-and-reload-page).

A **text action** is an action that sits among links in a line of chrome, with no border
or fill, because a bordered button would read as a different thing from the link beside
it. It is a link when the page already has the address, and a real `<button>` when
following it first switches the served pin, so that a new tab or a copied address never
opens something a click would not.
An action that opens nothing, such as a pull request’s Retry, is always a `<button>`.
Both forms look the same in their context, a tooltip and accessible name say which
commit opens and whether the pin switches, and keyboard and screen-reader users still
get the element they expect.
The diff file bar’s [View file and View on branch](#diff-file-bar), and
[Browse code, a review comment’s file, and Retry or Fetch](#chrome) on a pull request’s
page, are text actions.
A sortable column header’s label, `.agents-sort` in the session table, is a text action
in this sense: a bordered button inside a header would read as a different thing from
the label it sits in.
It is a real `<button>` with the cell’s `aria-sort`, takes the label’s type, muted at
rest and `--text` on hover, shows the sorted direction as an arrow after the label, and
has the one focus ring.
Each context sets one look for the `<a>` and the `<button>`, box included: a `<button>`
is always an atomic inline box, so where a label can wrap, the `<a>` is one too, and
what follows a wrapped label starts on the next line in both forms.

### Refresh, Retry, and Reload Page

**A control that asks for something again says which of four things it does, in one
word, and a word means the same thing wherever it appears.** The words come from what
the control does, not from where the answer comes from:

| Word | What it does | Where |
| --- | --- | --- |
| Refresh | Asks for the current state of what the view shows, in place: the page stays, and what is on screen stays until the answer replaces it ([Refreshing Content](#refreshing-content)). The answer may come from the disk, the repository, GitHub, or a mirror’s origin; the reader asks for the same thing, so the word is the same | The top of the navigation pane on every page and under every tab, for everything the page shows; the Commits tab after “No commits yet.” and after “History changed since this list loaded.” |
| Fetch | The first ask for something not held at all, where there is nothing yet to refresh | A pull request’s status line before its record, and the Changes body’s “Changes have not been fetched.” |
| Retry | Asks again for what failed, beside the sentence that says what failed | A pull request’s status line after a failed fetch or refresh, the Changes body, a page of history, a commit a mirror lacks, a folder Overview panel |
| Reload page | Reloads the whole page, as the browser’s Reload does, where the page itself is out of date | The ref selector’s and the freshness row’s “The server now serves another revision” |

- **A label is the verb alone.** The sentence beside the control says what it acts on,
  so a failed page of history reads “Could not load these commits.”
  and then Retry, never “Retry loading history”.
  Reload page names the page because the page is what sets it apart.
- **Prose uses the same words.** A sentence that sends the reader to the browser says
  “Reload the page to try again.”, and one that points at a Refresh on screen names it
  by its label, Refresh.
  Nothing says “Refresh the page”: Refresh never reloads the page, so the phrase would
  name the one thing it does not do.
  A lowercase “refresh to try again” names no control, so it says “Reload the page”
  instead. Such a sentence is a reader message’s one remedy, and
  [Reader Messages](design-system-messages.md#what-a-message-contains) holds the rest of
  it: one statement, at most one remedy, no internals.
- **The same widget for the same word.** A `.btn` in a toolbar or after a notice’s
  sentence; a [text action](#control-families) in a line of chrome among links, as a
  pull request’s Retry or Fetch ends its status line; and an
  [icon button](#every-icon-only-control-is-the-same-control) in the navigation’s
  header, where the navigation’s Refresh stands just before the Metabrowser menu’s gear
  on every page, as a circular arrow named Refresh.
  The server writes it into the page, glyph and all, so nothing in the header appears or
  moves after the first paint.
  While a refresh is running, the button stays in place with `aria-disabled` and a
  spinner in the glyph’s slot.
  A quick press shows the spinner briefly, including when the data was already fresh.
- **One Refresh for the page.** The Refresh at the top of the navigation refreshes
  everything the page holds that can be read again, each part through the path it
  already had: the mirror’s or origin’s fetch, the pull request page in the main pane,
  the Files tree with the file or folder the pane shows, the Pulls list, the Commits
  history, which follows the revision the server serves, and the branch and tag
  chooser’s list while it is open.
  A checkout’s working tree has no fetch its page waits for, so there the origin is
  fetched last, in the background, after the disk and the history are read again
  ([The Ref Selector](#the-ref-selector)). It refreshes what is on screen first, the tab
  in front and what holds the main pane, then what is behind the other tabs, so a tab
  turned to next is already fresh.
  Within each half the fetch comes first, since every other part reads what it brings.
  The button waits while the parts on screen refresh.
  Each part keeps its own busy state while it runs.
  The tooltip gives the last source fetch age when available.
  With Pulls in front, the completed list refresh time and duration take precedence when
  both are known. `static/refresh-plan.js` holds the one order, and
  `cli-ui-refresh-plan.tryscript.md` shows it for each screen.
  A pull request’s page has no Refresh of its own.
  The freshness row below the navigation appears for fetch progress, source issues, and
  actions tied to a revision.
  The page offers Fetch or Retry only beside a sentence that says what it lacks or what
  failed, so the reader still has a remedy with the navigation pane hidden; the Commits
  tab’s Refresh after its two notices is the same kind of remedy.
- **Keys.** The navigation’s Refresh, and Retry or Fetch on a pull request’s status
  line, are situational and numbered; the status line’s is the page’s one way to ask
  again while the navigation pane, and its numbers, are hidden.
  The navigation’s Refresh comes first in reading order, so it is `1` under every tab,
  and the numbers after it follow from there.
  Other Retries and Reload page are rare and take no key ([The Rules](#the-rules)).

The owner found the Pulls tab’s Reload and a pull request’s Refresh doing the same thing
under two names (2026-11-24); before that a Reload meant three different things.
The owner then asked for one Refresh that refreshes the page and the list together
(2026-11-25), so the page’s own Refresh went, and the same day for it to be an icon at
the top of the navigation, beside the gear, then for it to refresh everything the page
shows under every tab, the parts on screen first; the freshness row’s pressable age went
with that. `test_asking_again_has_one_word_for_each_meaning` in
`tests/test_browser_copy.py` holds the shipped browser code to these words: no “Refresh
the page”, no lowercase “refresh to”, no Reload that does not name the page, and none of
the labels this replaced.
It reads what a reader could see through the reader-message check’s extractor, so a
console line or an error’s own text is not held to it.

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
sanitization.
A link localized to a served file stays internal: it takes no mark, and its
tooltip is the link card ([Tooltips on Links](#tooltips-on-links)). The decorator adds
no metadata request, remote image or SVG fetch, observer, or document-wide scan.
It uses the existing on-demand SDK view bundle and app-owned icon markup; document
sanitization keeps its allowlist.
Rendered Markdown retains its existing enhancement budget; links beyond the admitted
prefix keep their authored form.

A link whose whole content is images, a badge, or the chip an image the page does not
load becomes ([Images the Page Does Not Load](#images-the-page-does-not-load)), takes no
mark: github.com draws none on one, and the mark wrapped onto a line of its own under a
row of badges. A link with words of its own is marked as before.
`decorateExternalLink` decides this from the link’s content (`holdsImagesOnly`), so
every caller, a trusted render and an untrusted one alike, gets it.

### Images the Page Does Not Load

A document from an untrusted source shows its images from the web over `https`, as
github.com does, with no referrer sent, unless the reader ticks **Block remote images**
in the Metabrowser menu.
Any image the page does not load, one over `http`, one with no address of its own, and
every image from the web with that box ticked, is its alt text in a small chip:
`.mb-image-fallback`, one line of `--ui-small-font-size` in a `--viz-border` box with
`--radius-tag` corners, an image mark before the text
([Icon Catalog](design-system-icons.md#ui-chrome-and-actions)), and the address the
image would have loaded in its tooltip (`data-tip-text`, as every tooltip is).
Inside a link with a card, as every link in rendered text has, that address is in the
link’s card, “Image from” it, and the chip has no tooltip of its own, so the reader sees
one ([Tooltips on Links](#tooltips-on-links)). The chip is the content of the link the
image was in, so a badge keeps its destination, and an image that was in no link is in a
link to the image, in the same chip.
So it is always a [clickable chip](#clickable-and-static-chips), in the link’s ink,
which a document’s lighter hover ink does not reach.
It is a badge’s height, so a row of chips lies on one line as a row of badges does, and
it never wraps its text: one wider than its line is cut with an ellipsis, and the
tooltip has the rest.
`inert_html.py` and `static/inert-html.js` write it, and nothing in a document can give
an element the class.
`tests/test_markdown_badges_chrome.py` measures the row in Chrome.

### Choosing Among Values

A control that offers two or more values, or one value on or off, is one of these.
They differ in shape because they offer different things, and they agree on what each
state looks like.

| Offers | Primitive | ARIA and keyboard | Used by |
| --- | --- | --- | --- |
| One of a few labelled values | `.chip-group[data-select="one"][data-layout="joined"]` | `radiogroup` of `radio` with `aria-checked`; one tab stop, arrow keys select | Split / Unified, Diff / Excerpt / Full, Rendered / Source, Files / Bytes, Branches / Tags, and for a checkout Branches / Remotes / Tags |
| Any of a set of labelled values | `.chip-group[data-select="many"]` | `group` of buttons with `aria-pressed`; each a tab stop | An agent log’s event types |
| One of a few values in a menu, where the glyph is the label | `.menu-chooser` of `.menu-seg` | `group` of `menuitemradio` with `aria-checked`; each a tab stop | Theme and reading font |
| One of a long list | A named trigger over a `.menu` | `aria-haspopup`, `aria-expanded`; the panel’s pattern within | Filter dropdowns and the Files revision chooser for mirrors and checkouts |
| A boolean whose polarity has to be legible | `.filter-check` | A real checkbox | Show ignored |
| A boolean with no room for a word | `.icon-btn[aria-pressed]` | A button with an accessible action name | The filter drawer |
| A boolean in the Metabrowser menu | `.menu-row` holding a real checkbox, `.menu-check` | A real checkbox, its label the row’s | Block remote images |

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
The [diff toolbar](#diff-toolbar) uses joined choices for the whole comparison.
An eligible file uses **Rendered** | **Source** in its own header.
Where only Source can be shown, Rendered stays dimmed and `aria-disabled`. Its tooltip
and accessible name say why.

`test_a_toggle_cannot_fork_the_family` fails when a stylesheet or a source states a
toggle’s ARIA outside this family, and
`test_exclusive_choices_share_one_answer_to_each_state` holds the table above.

### Links Have a Base Color

A link is `--link`, and the shell says so once: `:where(a:any-link)` in
`static/styles.css` sets `color: var(--link)`. Without it a link no rule colors falls
through to the user agent’s blue, and its purple once visited, so a new view that forgot
would read as a different app.
The selector has zero specificity, so every context’s own color, hover, and ring wins
without a fight, and `:any-link` covers a visited link as well as a fresh one.
It sets the color and nothing else, deliberately: a context that keeps the user agent’s
underline at rest (rendered Markdown, Help, an event’s details) is unchanged, and no
ring is drawn that a context did not choose.

A context that wants the link’s full treatment says so itself, as the
[Link row](#chrome) of a pull request’s page does: `--link` and no underline at rest, an
underline on hover, and the [focus ring](#focus-ring) with its outset offset, since a
bare inline link’s box is its text.
A link whose content is a chip is never underlined, whatever its context says
([Clickable and Static Chips](#clickable-and-static-chips)). A link that sets its own
ink, a Pulls row’s title, sets it on the link itself.
A new context does not add a rule of its own that only colors its anchors `--link`: the
base already does. `test_a_link_no_rule_colors_is_the_link_color` holds the base and
holds the three patches it replaced gone (older GitHub plugin rules that also set other
properties remain), and `tests/dom/agents-views-chrome.mjs` reads in Chrome that a bare
`<a href>` in a plugin view computes to `--link`, in both themes.

### Focus Ring

Every control’s keyboard focus is one ring, from four tokens in `static/styles.css`:
`--focus-ring-width`, `--focus-ring-color`, `--focus-ring-offset`, and
`--focus-ring-offset-outset`. A `:focus-visible` rule sets
`outline: var(--focus-ring-width) solid var(--focus-ring-color)` and
`outline-offset: var(--focus-ring-offset)`, which draws the ring inside the control’s
box, so no ancestor’s `overflow: hidden` clips it.
The outset offset is for a bare inline text link or a check, whose box is its text and
has no room for a ring; `_FOCUS_RING_OUTSET` in `tests/test_design_vocabulary.py` names
the controls that take it.
`test_every_focus_ring_is_the_one_ring` fails a stylesheet, a plugin’s included, that
writes a literal ring.

A button or `summary` that no rule rings draws the same ring:
`:where(button:focus-visible, summary:focus-visible)` in `static/styles.css` states it
at zero specificity, as [the link base](#links-have-a-base-color) states a link’s color,
so a family’s own rule wins and a control that sets no ring draws this one, not the user
agent’s outline in the platform’s accent color outside its box.
A diff file bar’s label drew the user agent’s until 2026-11-24. Links are not included:
a link’s ring is its context’s. `test_a_control_no_rule_rings_takes_the_one_ring` holds
the base.

Any rule that rings a control wins over the base, and that includes KPress’s document
sheet, which rings a `summary` inside `article.kpress` with a wider ring outside the
box. A `summary` the app draws inside a KPress article therefore states the one ring
itself. A rendered diff’s run of unchanged blocks draws the diff’s fold bar there, a
`button`, which KPress does not ring, so it keeps the base’s;
`tests/test_diff_markdown_fold_chrome.py` reads that ring with KPress’s sheets loaded.

### Text Fields

A typed or chosen value that is not a button carries `.field`: its border, recessed
`--bg` fill, ink, padding, hover border, and focus ring are stated once in
`static/styles.css`, and a use site sets only its layout, such as its width, text
alignment, or block padding.
The source ref selector’s filter, the font-set picker, and the line-length number carry
it in markup. `test_text_fields_carry_the_field_primitive` fails a field that restates
what `.field` owns.

### Chip Sizes

| Use | Height | Components |
| --- | --- | --- |
| Compact labels and references | `--compact-chip-height`, including any border | Branches, tags, GitHub labels, ref chooser tags such as “checked out”, and links to referenced table rows |
| Filters and other chip controls | `--chip-height` | Navigation filters, segmented chips, and removable table filters |
| Status and file-type badges | The badge’s line plus its padding or border | Pull request states such as Merged, checks, and file headers |

Compact chips share `--compact-chip-padding-inline` and `--radius-tag`. A bordered chip
fits its line inside the shared height.
For GitHub labels, set the outer box with `block-size: var(--compact-chip-height)`.
Center the capital-height band with `text-box: trim-both cap alphabetic` and
`align-content: center`, the same approach as file-header badges.
Keep the line height equal to the space inside the border for engines without text-box
support.

The tag notch has extra leading room.
A ref chip shows its full name in a tooltip when its label is cut off horizontally.

### Badges

A status or file-type badge takes its fill and ink from a `--badge-<tone>-bg` and
`--badge-<tone>-text` pair, themed for both themes and held to 4.5:1 by
`test_status_and_badge_inks_read_in_both_themes`; a failure and a front-matter error are
one tone, `--badge-failed-*`. Ref chooser tags use the outlined form in the row’s muted
ink, at the shared [compact chip size](#chip-sizes).
A badge is static, except where it is a link’s content, as a pull request’s readiness is
([Clickable and Static Chips](#clickable-and-static-chips)).

### Clickable and Static Chips

**A chip says whether it is clickable, and the pointer’s answer is a ground, never an
underline.** GitHub’s Primer draws it the same way: an interactive token changes its
ground under the pointer, and a label or a state label shows nothing.

- **A clickable chip** is a control itself, a link or button whose whole visible content
  is the chip, or a chip a control is laid over.
  It shows the pointer, paints a ground of its own under the pointer, draws the
  [one focus ring](#focus-ring), and is never underlined, at rest, under the pointer, or
  focused.
- **A static chip** shows nothing under the pointer: the same ground, no pointer, and no
  underline. A tooltip that explains it is fine, and the cursor stays the page’s.
- **A selected chip** keeps its selected look under the pointer, and **a disabled chip**
  (`aria-disabled`) is static.
- **A chip that is a part of a larger control**, a badge in a log’s row or a ref chip in
  the revision chooser’s row, is the row’s: the row answers the pointer, and nothing
  underlines the chip.

The rule is one block of `static/styles.css`, “Clickable and static chips”, which names
the shell’s chip atoms once, in the list its rules share, and applies them by markup: a
chip that is a link or a button, or the child of one, is clickable, and every other chip
is static by having no rule.

- **The hover ground is one layer over the whole chip**, `--chip-hover-overlay`, which
  darkens a chip’s fill and its ink together in the light theme and lightens both in the
  dark. So it works over any fill, a status tint, a label’s color, a trunk ref’s solid
  ground, or none, with no token for each, and the ink keeps its contrast: laid under
  the ink, the lowest clickable ink fell under 4.5:1 in the light theme.
  Its alpha takes `--hover-bg`’s step over `--bg`, and the figures are beside the token.
- **No context’s link rule reaches a chip.** A link or button that holds a chip is never
  underlined, by an important rule for that one property: the readiness badge’s link
  took the pull request header’s underline on hover, and an image’s chip a document’s.
- **The ring is the chip’s** where a control’s content is a chip, since an inline link’s
  own box is its line’s, not the chip’s.

| Family | Class | Clickable | Static |
| --- | --- | --- | --- |
| Filter chip | `.chip`, in `.chip-group`, `.chip-toggle`, and `.chip-menu-trigger` ([Filter Controls](#filter-controls)) | Always: its family answers the pointer with `--hover-bg` ([Choosing Among Values](#choosing-among-values)) | Its count, `.chip-badge`, is a part of it |
| Ref chip | `.git-ref`, from `mb.refChip` ([Branch Chips](#branch-chips)) | As the button that opens its menu (`.git-ref-action`), or under the menu button a history row lays over it (`.git-ref-menu-hit`), which lays the ground | In a commit’s tooltip; in the revision chooser’s row, a part of the row |
| Badge | `.file-header-badge` and its tones ([Badges](#badges)) | As a link’s content: a pull request’s readiness in its header, a link to the Checks tab | A state, a review, a check, a requirement, the Merge status verdict, a stack’s tally, a file header’s, and a session’s |
| Image chip | `.mb-image-fallback` ([Images the Page Does Not Load](#images-the-page-does-not-load)) | Always: it is a link’s content, in a link’s ink that the document’s hover does not change | Never |
| Label | `.github-pull-label` ([Label Colors](#label-colors)) | Never | Its description is its tooltip |
| Compact tag | `.source-ref-selector-badge`, `.github-pull-required` | Never | “checked out”, “default”, “Required” |
| Table reference | `.table-ref`, a link to the referenced row | Always: the table plugin’s rule lays the same token, under its text ink | Never |
| Table filter | `.table-chip` | Its remove control, `.table-chip-remove`, is a control of its own | The chip |
| Key hint | `.kbd-badge` ([Badge Targets and the Shift Reveal](#badge-targets-and-the-shift-reveal)) | Never | It takes no pointer |

`tests/test_chip_affordance_chrome.py` holds the rule in Chrome, in both themes, on the
surfaces that draw chips: a pull request’s header, Checks, and Changes, the Pulls tab, a
stack’s page, the Files tab, the revision chooser, the Commits tab, a commit’s page, a
table, a filtered table, a document’s image chips, and a compressed file’s header.
It finds every chip by its shape, not its class, and what control it is by what the
pointer reaches at its middle, so a new chip is held without being named; it reads each
ground from the page’s pixels, and each ink’s contrast on the ground under the pointer.
`test_a_clickable_chips_hover_keeps_its_inks_contrast` in
`tests/test_design_vocabulary.py` holds the inks of every chip that can be clickable to
4.5:1 under the token in both themes, and
`test_the_clickable_chip_rules_name_one_list_of_atoms` that every rule of the block
names the same atoms.

### Status Text Inks

A status color set as text takes a themed ink, `--status-success-text`,
`--status-warning-text`, or `--status-error-text`, defined in both themes against `--bg`
and `--hover-bg`, each at 4.5:1 or better
(`test_status_and_badge_inks_read_in_both_themes`). The unsuffixed `--status-*` tokens
are fills for dots, bars, tints, and borders and do not read as text in both themes;
`test_no_stylesheet_sets_text_in_a_status_fill` rejects one set as `color`.
`--diff-add-row-bg` and `--diff-del-row-bg` are the tints behind an added or removed
line.

A tally tree colors a leaf’s count by its label: `success` in the success ink, `failed`,
`error`, `critical`, and `kill` in the error ink (`critical` also bold), and `high` and
`elevated` in the warning ink.
Severities that share an ink are told apart by their label, not by color (`TALLY_COLORS`
in `static/charts.js`).

### Empty and Failed Loads in the Navigation Column

An empty list, `.recent-empty` or `.git-panel-empty`, is one look in every tab: the
column’s inset, left-aligned, muted.
A load that failed is not empty: it adds `.nav-error`, in the error text ink, as the
lazy-folder, history, and ref-selector failures are.
Amber (`--status-warning-text`) is for a degraded or partial result only.
A failure says what could not be done in a sentence with a period; the HTTP status is
for the console or a tooltip, never the visible text.

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

A file whose kind declares the container capability keeps its file identity (icon, name,
size, selection) and additionally leads with the tree’s disclosure chevron in the same
slot a folder uses, `--tree-icon-slot` ([One Glyph Size](#one-glyph-size)), so names
stay aligned at every indent.
Its children are ordinary rows carrying a one-letter change badge in place of the file
icon. Clicking is one gesture, as on a folder row: it opens the file *and* toggles its
children. The keyboard splits them the same way, and every disclosure affordance in the
tree (ARIA state, arrow keys, filtering) asks whether a row owns a child group, never
what kind of row it is.
See
[navigation containers](project/architecture/arch-plugin-system.md#navigation-containers).

### A Click on the Toggle’s Line Toggles

**A click on a line that carries a disclosure toggle toggles it; a click on a larger
element that holds that line, and a toggle with it, does not.** This is the one rule for
every row with a disclosure toggle, and it is why a folder’s row and a Pulls item behave
differently under one design.

- **A folder’s row is one line, and the chevron is on it**, so a click anywhere on the
  row toggles its children ([Navigation Tree Folders](#navigation-tree-folders)), as a
  container file’s row does ([Container Rows](#container-rows)).
- **A pull request in the Pulls tab is one item, its link**, and its toggle is on its
  last line: the lines the pull request changes and the chevron after them, the summary
  the chevron expands ([Diff Summary](#diff-summary)). A click on the lines or the
  chevron opens or closes the changed files and opens no page.
  A click anywhere else on the item, the title, the place, the number, the author, the
  age, or the last line past the chevron, selects and opens the pull request and expands
  nothing, because those parts belong to the item, not to the toggle
  ([The Pulls Tab](#the-pulls-tab)).

The keyboard sees the item, not its lines: an item is one stop and one selection, and
its keys are a folder’s ([Navigational Row Collections](#navigational-row-collections)).
Space on the item toggles, as a press on its toggle’s line does, and no line inside the
item takes focus of its own.

The item shows that it holds a narrower target.
The whole item takes one `--hover-bg` ground under the pointer, as a Files row does, and
while the pointer is on the toggle the chevron also stands on a `--border` plate in
`--text` ink, as an icon button’s glyph does on a plain ground.
The plate covers the chevron’s slot alone, so the toggle’s inks keep the grounds their
contrast is held on.
For assistive technology the toggle is the item’s, as it is for the keyboard.
Where the line is the item, as a folder’s row is, the line carries `aria-expanded`.
Where the item is a tree’s item holding the line, as a Pulls item is, its stop carries
`aria-expanded` and owns what it opens, and the toggle’s line is hidden (`aria-hidden`):
a tree’s item may own only items and groups, so a button inside it would make the tree
invalid. The line’s words, hidden too, describe the item’s stop (`aria-describedby`).

`tests/dom/github-pulls-row-lines-session.js` pins the rule for the Pulls item: a press
on the chevron or the lines flips exactly that item and opens no page, though they are
in the item’s link, a modified or middle press on them flips nothing and opens no tab, a
press on any other part opens the pull request and changes no expansion, and only Space,
Right, and Left change it from the keyboard, each on the item with focus.
`tests/dom/github-pulls-row-lines-chrome.mjs` measures the two hovers and the real
presses in Chrome, and reads the line’s place in Chrome’s accessibility tree.

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
glyph on row-like targets (tree folders, a Pulls stack’s row, tally tree, diff file
bars) and the section-disclosure mask after heading-like titles, both in `--muted`,
pointing right when closed and rotating to point down when open.
A toggle that expands a diff summary is the one row-like target whose chevron comes
after its words: the Diff summary’s header, and a Pulls row’s lines
([Diff Summary](#diff-summary)); the stack page’s members toggle, “**2** Pulls”, is the
shell’s summary toggle, `.summary-toggle`, as the Diff summary’s header it sits above
is, one rule for both ([The Stack Page](#the-stack-page)). A
[fold expander](#fold-expanders) takes no chevron: it sets withheld content back in
place rather than opening a row’s children, so it draws its own pair of glyphs.
Row-like activation targets share `--ui-row-height` and `--hover-bg`. These agreements
are enforced by `tests/test_design_vocabulary.py`, which fails when a surface forks the
glyph, the row height, or the hover token, or puts the chevron on a fold.

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
| Diff file bar | Change letter and path; change stats and notes, inside their box | Chevron, copy button, the box of change stats and notes, a Markdown, YAML, or JSON file’s **Rendered** \| **Source** chooser and its spinner, View file or View on branch control |

The row keeps `align-items: center`, and each text child opts in with
`align-self: baseline`. A box aligned to the baseline would sit its bottom edge on the
baseline, so no opt-in selector may match one.
Where a text slot can hold a box instead (a loading skeleton, or an age the activity
spinner replaces), the opt-in selector excludes it with `:not()` rather than a later
rule overriding it, so neither rule order nor specificity decides where a box sits.

Baseline alignment places the text group at the top of the row’s content box, so the
group reads as centered only while that box is no taller than the group.
A tree row’s `--ui-row-height` is the name’s line box plus the row’s 2px pads, so change
the row height and the name’s line height together.

A header badge whose label changes in place sits in a slot as wide as its widest label
from first paint, so the change moves nothing after it: a one-column grid of the badge,
then a sizer of each label at no height, outside the badge so its trim still centers the
capitals. A run’s status badge is one, for Running, Live, Done, Failed, and Run ended,
and a pull request’s state badge is another; `tests/dom/github-pull-header-chrome.mjs`
checks both in Chrome.

The diff file bar’s change stats and notes, and its View file or View on branch control,
are boxes after the copy control, not text inside the toggle, so each is set at the
path’s own size and line height: text of one size and one line height centers onto one
baseline. The bar’s two groups ([Diff File Bar](#diff-file-bar)) are centered rows of
boxes too, and each, and the control between them, is centered in the bar, so the
toggle, the control, and the chooser share the bar’s center.

Two rows are deliberately not in the table.
A [view header](#view-headers)’s eyebrow sets its text at one size and centers it.
Its heading row sets the title and the metadata line after it at two sizes, and puts the
line on the title’s baseline by setting both as one run of inline text rather than by
these rules: aligned as a flex item, an item holding only a pending skeleton would sit
the skeleton’s bottom edge on the baseline.
The header’s corner, `.view-header-end`, is no row of either: a strut of the title’s
type, then the View on GitHub button, which opts in to the strut’s baseline, so its
label is on the title’s first baseline; `tests/dom/view-header-chrome.mjs` and
`tests/dom/github-pull-header-chrome.mjs` measure the two baselines equal in Chrome.
The Git commit summary’s metadata line sets a monospace revision beside sans text, and
aligning the two faces on one baseline would grow the line, so it stays centered; that
was measured before a revision took its line’s size, and has not been measured again.
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#row-baselines)
has the offsets behind these three decisions.
A [Pulls](#the-pulls-tab) row left the table when its title took two lines: its run,
title to author, is one flow of inline text, and its last line sets the lines, the
chevron, and the age at one size on one line height and centers them.
Aligned to a baseline, the number and the age had taken it from the line that held the
number, a wrap whose first line can hold no text, and moved 6px when the author left
that line (Chrome 152, at 200 and 180px); `tests/dom/github-pulls-row-lines-chrome.mjs`
holds the last line still as the lines arrive.

`test_row_text_shares_one_baseline` in `tests/test_design_vocabulary.py` checks this
table against the stylesheets: every text slot opts in, and no rule that aligns to the
baseline matches a box, including a text slot in its box state.

### Fold Expanders

A run of content withheld until asked for, such as a long stretch of changed lines in a
diff, sits behind a full-width control at `--ui-row-height`, in `--highlight-bg`,
hovering with `--hover-bg`. The label states the count it holds
(`86 more changed lines`) and becomes the inverse when open (`Hide 86 lines`), because a
control that hides its size is a control the reader cannot judge.
A fold inside another disclosure stops its click, so expanding a fold never collapses
its container. It is one primitive, `.fold-expander` in `static/styles.css`, on a button
or a native `summary`. `test_section_headings_and_fold_expanders_are_primitives` holds
it.

The control leads with the **expand/contract pair** that KPress’s table of contents
draws for its expand-all button, not the registry’s chevron:

| State | Glyph | Says |
| --- | --- | --- |
| Closed | Lucide `chevrons-up-down` | Expand: the withheld content opens here |
| Open | Lucide `chevrons-down-up` | Contract: the content folds back into this bar |

A chevron says a row holds children, and it turns as they open.
A fold holds no children: what it withholds is the run’s own content, cut from its
middle and set back in place, so opening it opens no level of a tree.
The pair is the mark for expanding and contracting in place, the one a rendered
document’s table of contents already draws for its expand-all control.

The primitive draws the glyph, as a mask on `.fold-expander::before`, from the control’s
own state: a button’s `aria-expanded` or a native summary’s `details[open]`. A fold’s
markup holds only its words, so every fold, current or new, draws the pair without
asking for it, and none can carry a chevron.
The glyph is the chevron’s size, `--toggle-chevron-size`, and weight, in the place a
chevron would take, muted at rest and in `--text` under the pointer or the focus ring,
in both themes, and in `CanvasText` in forced colors, which would otherwise mask it out
on the bar’s `Canvas`. It swaps at once when the fold opens; only the group the fold
opens travels ([Disclosure Motion](#disclosure-motion)).
`test_a_fold_expander_draws_the_pair_not_the_chevron` in
`tests/test_design_vocabulary.py` holds the primitive, its two states, and that no fold
builds or turns a chevron;
[the icon catalog](design-system-icons.md#ui-chrome-and-actions) holds the drawings to
KPress’s.

Every fold of a diff is one **fold bar**, made by one factory, `foldExpander` in the
diff plugin’s `diff-fold.js`: a code file’s long run of changed lines
(`86 more changed lines`), the unchanged lines between a code file’s hunks
(`63 unchanged lines`), and a rendered Markdown file’s run of unchanged blocks
(`6 unchanged blocks`) draw the same bar, open and close alike, and differ only in what
the group they open holds.
Opening a Markdown fold sets the blocks it holds exactly as the unchanged blocks around
them. A new kind of fold in a diff calls the factory rather than drawing a bar of its
own. `tests/test_diff_markdown_fold_chrome.py` holds in Chrome that the two bars compute
alike at rest and under the pointer, and that a fold bar and a native summary’s fold
draw the pair in each state and theme, muted at rest and in the text’s ink under the
pointer and the focus ring, and in `CanvasText` with forced colors emulated;
`tests/test_diff_hunk_gap_chrome.py` holds that a gap’s bar draws the pair and computes
as a changed run’s does under the keyboard’s ring too, that its separator ends in an
ellipsis at a narrow width while its label stays whole, and that a gap opening above the
pane leaves the reader’s row where it is at every frame.

A hunk’s `@@` separator is such a bar where the diff can read the file’s lines, which a
comparison can and a patch file cannot.
The bar stands where the separator stood and keeps it after its label, muted as before
(`63 unchanged lines @@ -76,7 +77,7 @@ def main():`), so the hunk’s ranges and heading
still say where it is.
Below the last hunk a bar with no separator reads `Rest of the file` until the diff
knows where the file ends.
One open shows at most `DIFF_GAP_LINES` (settings.py) of a gap, or of very long lines
what one answer holds (`MAX_LINES_ANSWER_BYTES`, `diff/side_lines.py`), the ones nearest
its hunk, and a bar of the same kind stands for the rest at the far end of the group;
the open bar counts every line it shows, its steps’ among them (`Hide 50 lines`).
`Rest of the file` below a hunk that turns out to end the file goes when pressed, and
the keyboard goes on from the file’s bar.
While its lines load the bar is `aria-busy` beside the app’s delayed spinner; a load
that fails closes it with `Could not load 38 unchanged lines. Retry`, and a press asks
again. A file whose lines the comparison declines draws its plain separators under one
warning, `The unchanged lines of this file cannot be shown.`
`tests/golden/cli-ui-diff-hunk-gap.tryscript.md` pins each state.

### Disclosure Motion

Every toggle travels the same way: the body animates `height` between `auto` and `0` on
`var(--transition-fast)` (the same duration its chevron rotates with; a fold’s glyph
swaps at once), with `overflow: hidden` during travel and `visibility: hidden` at rest
so collapsed content leaves the tab order and the accessibility tree.
`interpolate-size: allow-keywords` is scoped to each animated body; engines without it
swap instantly. Collapse is always class-driven (`.tree-children-collapsed`,
`.diff-file-body-collapsed`, `.diff-fold-collapsed`,
`.folder-overview-panel-body-collapsed`, `.github-pull-stack-members-body-collapsed`),
never inline `display`, so the stylesheet owns the motion, and reduced-motion drops
every travel to 1ms while keeping the state change.
A native `details` keeps its state in `open` and takes the same recipe on
`::details-content`, as a pull request hunk’s earlier lines do.
`tests/test_design_vocabulary.py` pins the recipe on every site.

Only a toggle the reader asked for travels.
When navigation reveals a path, as a link, Back, or Quick Search does, the tree opens
the folders on the way with `.tree-children-instant`, which lands them in place, because
an animated deep reveal moves the rows below it with no input
([measured](../explorations/performance-loop/design-rule-measurements.md#disclosure-motion)).
The reader’s next toggle of that folder travels again.
Such a reveal is the reader’s own doing, so it then scrolls the new selection into view
in the same frame, unless a folder above the row is still travelling, one the reader has
just opened or a landing’s: then the scroll waits for that travel to end.
A landing within the inline’s bounds needs no reveal: the server inlines the folders of
the address’s path, open, and the tree’s first paint selects and shows its row, so
nothing is fetched, opened, or scrolled after it.
The bounds are a folder’s whole listing within `_INLINE_INITIAL_TREE_ROWS`, the path’s
folders within `_INLINE_LANDING_ROWS` rows and `_INLINE_LANDING_DEPTH` folders, all in
`server.py`, and the inventory’s discovery complete.
A landing outside them inlines the root alone, and the page reveals its path after the
first paint with its folders travelling, which still moves the tree with no input.
Its row is scrolled into view once they are open (`folderTravelAbove` in `app.js`):
scrolled while they travelled, it was scrolled within the opening folder’s clipped body,
not the pane, and once the folder was open it lay below the pane.

### Disclosure Toggles Never Select Text

A **disclosure toggle** is any control that shows or hides content: a tree row that owns
a child group (a folder, a container file, a tally node, a pull request in the Pulls
list, a folder of its changed files, a folder of a Diff summary), a section-disclosure
trigger, a fold expander, a diff file bar, a Diff summary’s header, the stack page’s
members toggle, an expandable log event or data row, a `summary`, and a menu trigger
that carries the registry chevron.
A control with the chevron or a `summary`’s marker is a toggle, and so is one that sets
`aria-expanded` for content it shows in place.

Every one carries `.disclosure-toggle` in its markup, beside its own primitive’s class,
the way a notice carries `.notice`. The one rule for it is in `static/styles.css`, and
it sets `-webkit-user-select` and `user-select` to `--toggle-user-select`, which is
`none`. A native `summary` matches by element, so a disclosure a document writes for
itself, in a README or a pull request’s description, behaves the same.
Plugins use the same class; `plugin-sdk.js` lists it with the SDK’s visual helpers.

A click on a toggle is a command, not a reading gesture, so it must never leave a
selection behind: a double or triple click on a fold or a folder row would otherwise
select its label and the content it reveals.
WebKit, the macOS app’s engine, reads only the prefixed `-webkit-user-select`, so
declare the prefixed property beside every `user-select`, not only on toggles.

The rule is enough on its own, with no `mousedown` handler, in Chrome and in a
`WKWebView`
([measurements](../explorations/performance-loop/design-rule-measurements.md#disclosure-toggle-selection)).
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

Its fill is always the ordinary surface (`var(--bg)`, white in the light theme), and
**severity is carried by the border alone**, as one `[data-severity]` override:

| Severity | Border | Means |
| --- | --- | --- |
| (none) | `var(--border)` | Neutral; the box is a container, not a signal |
| `warning` | `var(--status-warning)` | Incomplete, capped, or degraded: the content is fine as far as it goes |
| `error` | `var(--status-error)` | The thing could not be done at all |

One tone per box, and it is the one on the edge.
A tinted fill under a border of another severity says two things at once, so a tint
token such as `--status-info-bg` exists for surfaces that mean “informational” and is
never a message box’s fill.

A use site carries `.notice` in the markup alongside its own class, and owns only
**layout and position**: how it arranges its contents and where it sits.
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

What a notice, an empty state, or an error may say, and where the detail it leaves out
goes, is the subject of [Reader Messages](design-system-messages.md): one statement in
the reader’s terms and at most one remedy, never a commit list, an internal path, or an
exception’s text.

### Continuing Partial Content

A view that shows part of a file offers the control that loads the rest **at both ends
of the content**, above it and below it, whenever more remains.

The reader who most wants the next chunk is the one who just finished the current one,
and they are at the bottom.
A single control in the pane header is out of view by then, so continuing means
scrolling back through everything already read to reach it: the longer the content, the
worse the cost, which is exactly backwards.
Both controls carry the same label, act on the same state, and appear and retire
together.

### State Progress Once

The notice is the only place a view reports how much of a file is loaded.
A second readout in the pane chrome would say the same sentence twice in two boxes and
give a reader two things to reconcile where there is one fact.
The view header states the file’s **size**, which is identity; the notice states
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
  The byte view opens a binary above its preview ceiling this way.

Core provides both halves through `mb.renderTextTruncationWarning` and
`mb.renderTextLoadMoreFooter` for views whose progress comes from `/api/file`, and
`mb.partialNoticeHtml` for a view that tracks its own offsets.
A plugin gets the placement and the style by using them rather than by reproducing them.
See [Rendering Large Content](large-content-rendering.md) for the loading policy behind
the chunk sizes these controls request.

## Git History

The history panel has its own vocabulary because it shows a structure nothing else in
the product shows, a graph of commits, but it borrows every general element it can: ages
come from [Age](#age), change counts from [Inline Change Stats](#inline-change-stats),
and rows follow the shared [row height and hover](#one-chevron-one-row-contract).
[Branch Chips](#branch-chips), defined here, is the reference for a ref chip on every
surface: a pull request’s header and the ref selector as much as a history row.

### Lane Colors

Five lane colors, `--git-lane-1` through `--git-lane-5`, assigned round-robin as lanes
open. They are **one set, not five independent choices**: the property that matters is
that the five stay distinguishable from one another, which belongs to the set, so a lane
color is never adjusted on its own and the set is identical in both themes: thin strokes
carry on either background.
This is the documented exception to the hue rule in
[Color and Theming](#color-and-theming).

The lane a commit sits on colors its node, so a commit and the history below it read as
one line. `HEAD`’s lane takes the branch blue, `--git-ref-remote`, the color most branch
chips show. It does not take the local chip’s blue-green, though `HEAD` is usually on a
local branch: that hue sits beside lane 4’s teal, and a lane has to stay apart from the
five.

### Commit Nodes

**Every vertex is the same solid dot.** Shape carries no state.
At this radius a ring or a ring-and-dot reads as noise rather than meaning, and a hollow
center has to be painted with a copy of the row’s background, so every row state, hover
and selection included, would have to restate that color or the node would change shape
under the highlight.
What matters stays legible where it already is: `HEAD` by its lane color and its chip, a
merge by the arcs converging on it.

### History Rows

A row is the graph, then the commit, then who and when:

| Part | Sizing |
| --- | --- |
| Graph gutter | Shrink-wraps **this row’s** lanes, so the subject starts where that row’s graph ends. A shared column would spend the widest row’s width on every row. |
| Ref chips | Fixed, at the chip’s [one size](#one-size); shrink last (see below) |
| Subject | Bold, with a conventional-commit prefix regular ([Titles](#titles)); takes the remaining space and absorbs the row’s shrinkage, ellipsizing |
| Author | Right-aligned in a column bounded by `.git-graph-meta`’s `max-width`, sliding outward as the panel widens; it ellipsizes in that column first |
| Age | Fixed, at the column’s end; never cut |

When a row cannot fit everything, the order it gives way in is **subject, then chips,
then the author, never the age**: an age pushed off the row is information lost, an
ellipsized message or name still reads, and a halved branch name does not.
Rows are independent, with no shared column, which is also what lets a new page of
history be appended to the list instead of rebuilding every row above it.
The subject, the author, and the age share the row’s size and a baseline; see
[Row Text Shares a Baseline](#row-text-shares-a-baseline) and [Type Scale](#type-scale).

### Git Commit Summary

The selected commit begins with one `.git-commit-summary` component rendered by
`renderCommitSummary` in `static/git-panel.js`. On the commit’s page it is a
[page header](#page-headers), in a pull request’s header’s order, every line under the
subject at the body size; its anatomy has one order:

1. subject, bold, with a conventional-commit prefix regular ([Titles](#titles));
2. the author, `.git-commit-byline`, as the shell’s [actor identity](#actor-identity):
   the avatar’s box, holding the person glyph, then the bold name, where a pull request
   has its author;
3. the identity group, `.git-commit-revision-line`: the short revision, its copy button,
   and the refs, which wrap under it when there are many, where a pull request has its
   branches;
4. the age, `.git-commit-ages`: “Committed 3d ago”, muted, the age in its freshness ink
   with the exact time in its tooltip, where a pull request has its row of ages;
5. the commit’s changes: its [size line](#change-size-line), `.git-commit-size` in the
   full summary and `.git-commit-size-line` in the compact one, then in the full summary
   its [Diff summary](#diff-summary), in `.git-commit-diff-summary`, where the commit’s
   diff draws it, and in the compact one `.git-commit-change-stats`; and
6. the commit description, when present.

The compact summary keeps one line of metadata, `.git-commit-meta`: the identity group,
then the author’s name and the age, with no avatar’s box, since a hover card is bounded.

The identity group shows the commit’s refs as the Git history row does, with the same
kinds, trunk, and HEAD marks ([Branch Chips](#branch-chips)). The full summary makes the
revision copyable; the compact summary keeps the familiar copy glyph noninteractive.

The Diff summary is the commit page’s one statement of its changes, as on a pull
request’s page, with the same header and words, collapsed until it is opened; only a
commit past the comparison’s bound on files says its count again, in the note that the
diff is bounded.
The diff draws it in the summary’s place before the page is shown, so it
is there at first paint, and it is there for a commit of one file too.
Until the diff draws it, and where the diff is not drawn, as when the diff plugin is
absent or the comparison fails, the place says the commit’s line totals in one line,
painted as a diff’s line is where its tree did not load, “+1,234 −3,423”, its file count
on the [size line](#change-size-line) above; a failed comparison says so in the diff’s
place. The size line says the file count at first paint and the commit’s size once
`GET /api/git/commit-size/<rev>` answers it, which the page asks beside its body.
A detail with no count of files leaves the place empty, and it takes no room.
The commit hands the diff its own totals, which the server counts over the whole commit
before it caps the list of files, and for a list cut short at the comparison’s bound
(`MAX_MANIFEST_FILES` in `diff/adapters/git.py`) the summary’s header says those
([Diff Summary](#diff-summary)). The summary’s place is on the subject’s edge with its
toggle hung into the gutter, as every Diff summary’s is; its header, at the body size,
wraps in a narrow pane, breaking after a dot, before the page is shown; opened, its tree
is under it and above the description; and with no diff the totals line is one row under
the age line. `tests/test_git_commit_summary_chrome.py` holds it, and its measurements
are in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#git-commit-summary).
The compact summary, in a tooltip, has no diff: below the identity metadata, its
`.git-commit-size-line` says the [size line](#change-size-line), “**32** files changed ·
**56.9 KB** compressed (**193.9 KB** raw diff)”, and its `.git-commit-change-stats`
child says the commit’s changes in the Diff summary’s words and paint, through the same
parts and painters (`changeSummary` and the [brief change line](#brief-change-line)):
“**4 A**, **28 M** · +1,921 −160”, in the summary’s order, painted by the
[count summary](#count-summaries-bold-their-numbers)’s rule.
The hover asks for the size beside the detail and shows the card once, with the size if
it is in by then; a later hover has it kept.
Its families are Git’s, exact file-status families with Git’s letters: `A` contains
added and copied files, `D` deleted files, and `M` modified, renamed, and type-changed
files, so a rename that the commit page’s Diff summary counts as `R` is an `M` here.
These families cover every supported file status exactly once.
A zero family is omitted.
The server computes all counts before bounding the returned file list, so a large commit
remains exact. Line totals are the [inline change stats](#inline-change-stats), in the
shell’s number format with a true minus sign.
A count the commit does not know is “?”. A screen reader is told the line in words, “32
files changed: 4 added, 28 modified; 1,921 lines added, 160 deleted”, and not its
letters and marks.

The full subject uses `.page-heading` at `--page-title-font-size`, the PR title’s scale.
Its summary starts at the pane’s content edge and uses `.page-reading-column` for the
maximum reading width.
The full summary’s lines and the compact subject, author, age, and change line use
`--body-font-size`. The ref badges are chips, at the chip’s [one size](#one-size).
Among the row’s text the revision is the one deliberate exception: it is monospace, at
the row’s size, with its face scaled to the sans’s x-height so it reads at the size of
the text beside it ([Short Commit IDs](#short-commit-ids)). The compact tooltip is
bounded by width and subject line count, not made denser with smaller type.
The optional full-summary description is chrome prose, as a PR description is
(`.chrome-prose`), at `--document-body-font-size` and `--kpress-line-height-normal`. It
is Markdown, set as a PR description is: the body after the subject line, rendered by
`GET /api/git/commit-markdown/<rev>` through KPress and the inert allowlist, in a KPress
article (`placeCommitBody`), so a body hard-wrapped at 72 columns reflows into
paragraphs, `-` and `*` lines are lists, and indented and fenced code stays code.
Git’s trailers, such as `Signed-off-by:`, follow the prose as written, one per line, in
the muted ink (`.git-commit-trailers`). `src/metabrowser/git/message.py` says how a body
differs from a description: which lines are trailers, why only an absolute link keeps
its address, and the size past which a body is not rendered.
Until its Markdown comes the message as written is held out of sight, as a PR text’s
source is, and where the Markdown will not come it shows as written, wrapping long text,
with a notice when the reason is the reader’s to know.
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

### Short Commit IDs

**A short commit ID looks the same wherever it appears, as GitHub’s do: always the same
length, always monospace, always the same gray, and always the size of the text around
it.**

- **One length.** Every line that names a commit shows the first `SHORT_COMMIT_CHARS`
  characters of its full ID, from one formatter on each side:
  `MetabrowserFormatters.shortCommit` in `static/formatters.js` on the page, which
  plugins reach as `metabrowser.shortCommit`, and `short_commit` in `commit_ids.py` on
  the server and in the CLI. The ID is cut from the full one, never asked of Git, whose
  abbreviation grows in a large repository; the full ID stays a copy or a link away
  ([Copyable Identifiers Use One Delegate](#copyable-identifiers-use-one-delegate)).
- **One look.** A shown ID is an element of class `.git-commit-sha`, the commit-ID face:
  `--font-mono` and `--muted`, whatever ink the line around it has.
  A tooltip or a CLI message is plain text, so there it is the same length in the text’s
  face.
- **The size of the text around it, by a measured ratio.** The ID sets no size and
  inherits its line’s, and its monospace face is scaled so its x-height is the sans’s:
  `font-size-adjust` with `--font-sans-ex-height`, the x-height each font set’s sans has
  per em, which `static/styles.css` states beside the sans with its measurement.
  The ratio is the sans’s and not one of sizes because the monospace face is the
  engine’s: Chrome draws Menlo and WebKit SF Mono, whose x-heights differ, so one ratio
  of sizes would match one engine only.
  At one nominal size the mono face read larger than the sans, and a size one step down
  the ramp matched only the line it was chosen for: the navigation heading’s ID read
  larger than the name beside it.
  No context sets an ID’s size, and its line box is its glyphs’ (`line-height: normal`),
  so in the lines measured, a ref selector row, a commit’s page, and a pull request’s
  commit row, it does not make its line taller.

It holds in the branch and tag chooser’s button and rows, the navigation heading of a
pin with no mirror, a commit’s page and hover card, a mirror’s freshness row, and a pull
request’s timeline and offers, a linked ID among them, which hovers with an underline
and stays gray. It holds outside the page too: a development version’s label
(`commit-length` in `pyproject.toml`), the version line after it, and the macOS app’s
About box (`AppIdentity.shortCommitChars`), which cuts the full ID the build records.
`tests/test_short_commit.py` holds the lengths equal, the app’s through
`tests/test_macos_app_pins.py`, and fails a display that abbreviates a commit any other
way.

### Branch Chips

Git ref chips (`.git-ref`) are their own vocabulary, not filter chips.
Every one is drawn by `mb.refChip` or `mb.refChipHtml` in `static/plugin-sdk-views.js`,
and a merge’s two by `mb.mergeRefs` ([Merge Direction](#merge-direction)); no surface
builds its own. A chip answers three questions, each with its own signal: what kind of
ref it is, whether it is trunk, and whether `HEAD` is on it.

#### One Size

A chip is the same size in every context: the navigation’s history, a commit’s page, a
pull request’s header, and the ref chooser.
Its font size is `--git-ref-font-size`, the size a chip has in the navigation column,
and its line is the box’s height, the shared [compact chip height](#chip-sizes), so one
token sets the height and centers the name.
Nothing about a chip follows the text it sits in.
When the type was a ratio of that text and the box stayed one height, a name sat level
in a history row and low in a commit’s header, where the text is larger.
A context that needed another size would get a named form from the builder, never a rule
that restyles the chip where it sits; there is none.

| Property | Rule | Why |
| --- | --- | --- |
| Size | `--git-ref-font-size` | One length, the navigation column’s chip size: slightly smaller than the smallest text a chip sits in, so a branch name reads as a tag on that text rather than the text itself |
| Weight | `--weight-bold` | The name carries the meaning |
| Line height | `--compact-chip-height` | The box’s height and the name’s centering, from one token. Aligns with the label chips and fits a `HEAD` ring inside a history row |
| Corner | `--radius-tag` | Square-ish, so a ref and a filter never read as the same control |
| Padding | `--compact-chip-padding-inline` | A tag adds room on the left for its notch. The menu chevron overlays the chip ([Action Menu](#action-menu)) |
| Width | A maximum in em, ellipsized, with the full name in its tooltip | In em of the chip’s own size, so one width everywhere; the measurement is beside it |

`test_branch_chips_are_one_size_everywhere` in `tests/test_design_vocabulary.py` holds
the mechanism, not the pixels: it fails on a rule in any shipped stylesheet that sets a
chip’s type or box from a context, and on a size token with a part that resolves against
the chip’s surroundings.
What each context’s chip measured before and after is in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#branch-chip-sizes).

#### Kinds and Forms

| Kind or mark | Token | Form | Cue besides hue |
| --- | --- | --- | --- |
| Remote branch | `--git-ref-remote`, blue | Plain | In a history, and in a checkout’s ref selector, the name carries its remote, `origin/topic`; a merge and a mirror’s ref selector show only remote branches |
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

| Context | Drawn from | Kind | Trunk | `HEAD` | Menu |
| --- | --- | --- | --- | --- | --- |
| A checkout’s history row | The history page’s refs (`renderRefBadges` in `static/git-panel.js`) | The wire’s `kind`: `refs/heads/` local, `refs/remotes/` remote, `refs/tags/` tag | The ref’s `is_trunk` | The ref’s `is_head` | Beside the row |
| A mirror’s history row | The same | Its branches are `refs/remotes/origin/…`, so remote; its tags, tag | The ref’s `is_trunk` | None: a pin is detached | Beside the row |
| A commit’s summary | Its detail’s refs, the same parser as the row | As its row | As its row | As its row | In the chip |
| A commit’s tooltip | The same | As its row | As its row | As its row | None: a tooltip owns no action |
| A pull request’s header | `mb.mergeRefs`, head → base | Remote: GitHub’s branches, a fork’s as `owner:branch` | Never | Never | In the chip |
| The Files revision row and chooser list | `mb.refChip` in `static/source-ref-selector.js` | Tag for a tag. A mirror’s branch is remote. A checkout’s own branch is local and its remote-tracking branch remote | Never. The list says “default” beside a mirror’s default branch | Never. The list says “checked out” beside the branch a checkout’s `HEAD` is on | Click the chip in the revision row for ref actions. Click the adjacent chevron to choose a revision |

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
- **The ref selector never draws `HEAD`.** A checkout’s list says “checked out” beside
  the branch `HEAD` is on.
  The mark would say the page is there, and it is not: that branch, chosen, shows its
  last commit, and the working tree is the row above the list.
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

#### Action Menu

Click a branch or tag chip to open its menu.
Click the same chip again to close it; it closes as
[every menu closes](#every-menu-closes-alike).
A down chevron fades in over a translucent backdrop at the trailing edge on hover,
keyboard focus, and while the menu is open, and under the pointer the chip takes the
[clickable chip’s](#clickable-and-static-chips) hover ground.
The transition uses `--transition-fast` and is skipped under reduced motion.
Long names use the entire chip at rest.
The chevron uses the same neutral ink as other menu triggers.
In a clickable history row or ref chooser, the chip’s menu trigger is a separate control
above its visible chip.
In the [Files revision row](#the-ref-selector), the chip opens its own action menu.
The row uses one chevron, the standalone button for the revision chooser.

The menu names the ref and its kind.
**Copy Branch Name** and **Copy Tag Name** copy the underlying name.
**View This Branch** or **View This Tag** uses the in-app right arrow and selects the
full ref, including its Git namespace, through the same source-switch route as the
chooser. The current Files chip offers copying and an applicable GitHub destination.
Choose the checked-out branch from the adjacent chooser to open its committed snapshot
from a live working tree.
**View PR Head in Metabrowser** uses the same arrow and opens the PR snapshot when it is
available in the mirror.
**Open on GitHub** shows the destination and uses the same external arrow as the
repository menu. The remote action appears when the app can identify the matching GitHub
repository and ref.

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
| Markup | `mb.mergeRefs(source, target, options)` in `static/plugin-sdk-views.js` writes every merge; no surface places its own arrow. Each side is `{name, label}` and becomes a [branch chip](#branch-chips), and `options` (`kind`, `menu`) applies to both |
| Arrow | `.merge-refs-arrow`: `→` (U+2192) in `--muted`, at the size of the text around the merge, which the group inherits; each chip is its own one size. The spaces around it are text, so a copied selection reads `wip → topic` |
| Accessible name | The arrow is `role="img"` with `aria-label="merges into"`, so a screen reader reads “wip merges into topic” in document order. It has no tooltip: the names beside it say the merge, and a chip cut short carries its own full name ([Tooltips Add Information](#tooltips-add-information)) |
| Right to left | The group is `dir="ltr"`, an isolated left-to-right run as a path or a branch name is. The arrow points from source to target whatever the surrounding direction, the glyph is never mirrored, and the document order, source first, is the order a screen reader reads |
| Narrow places | The group is a three-column grid in which the names shrink and the arrow never does. The two names share the room equally: a name that fits in its half keeps all of it, the longer one gives way first, and each ellipsizes inside its chip with the full name in the chip’s tooltip. The group is never narrower than both chips’ padding, an ellipsis in each, and the arrow. The pull request header gives the merge a line of its own, under the author’s sentence, so only the names give way there |

A Pulls row names no branches: the pull request’s page names them, and the row’s room
goes to its title.

The rendered group, for a pull request from `wip` into `topic`:

```html
<span class="merge-refs" dir="ltr">
  <button class="git-ref git-ref-remote git-ref-action merge-refs-source">…wip…</button>
  <span class="merge-refs-arrow" role="img" aria-label="merges into"> → </span>
  <button class="git-ref git-ref-remote git-ref-action merge-refs-target">…topic…</button>
</span>
```

It appears in the header of [the pull request page](#the-pull-request-page); a new
surface that shows a merge calls `mergeRefs`.
`test_merges_read_source_to_target_in_one_notation` in `tests/test_design_vocabulary.py`
holds that the page calls it head first, draws no ref chip of its own, and never writes
`←`, that a Pulls row does not call it, the arrow’s name, direction, floor, and tokens,
and the rules by which a Pulls row’s author ends its run and its age ends the row.
The page’s session holds the order, the arrow’s name, and the literal refs it draws.

### File Change Status

File-summary letters share one muted semantic palette across Git history, commit
summaries, diff headers, PR changed-file trees, and the [Diff summary](#diff-summary)’s
header and a commit’s hover card, whose status counts read “10 A, 5 D, 4 M”, each count
bold in its status’s color with its letter
([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)). The letter
and accessible status name carry the meaning even without color.

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
size: `.diff-stat-add` in `--status-success-text`, `.diff-stat-del` in
`--status-error-text`, always in that order, using the true minus sign, at the size of
the text it rides in, and always `--weight-bold`: the pair is data, and it must read at
a glance. A total of zero is left out, and a file of no lines changed reads “0 lines”.
The pair is the [brief change line](#brief-change-line) of its line totals alone, built
and painted by the one component wherever it is drawn: `changeLine` and its painters,
`changeLineNodes` and `changeLineHtml`, in `static/formatters.js`. A tree of changed
files reaches it for a file’s row and a folder’s through `changeStats` in
`static/changed-files-tree.js`; a diff’s file bar (`renderFileBar` in
`builtin_plugins/diff/diff-view.js`, through the SDK) and a commit page’s file list
(`static/git-panel.js`) call it directly, so a change set, its folders, and its files
read identically and leave out a zero total by one rule.
Kind letters reuse the same mapping (added is `--status-success-text`, deleted is
`--status-error-text`), and no diff surface introduces a local green or red.

### Brief Change Line

**A change set said in brief, its statuses and its line totals, “**10 A**, **5 D**, **4
M** · +1,234 −567”, is one component, the brief change line.** It has one builder and
one painter: `changeLine` builds it from the model `describeChanges` reads, the statuses
in the header’s order, each with its letter, word, and count, and the line totals, and
`changeLineNodes` and `changeLineHtml` paint it (`static/formatters.js`). A plugin
reaches both through the SDK, `metabrowser.changeLine` and `metabrowser.changeLineNodes`
([plugins](plugins.md)). It is the
[count summary](#count-summaries-bold-their-numbers)’s rule in one element,
`.change-line` in the shell’s stylesheet: each status a status count, the commas and the
dot muted, and the totals the [inline change stats](#inline-change-stats).
The statuses and the dot after them are one item (`.change-line-group`), so a line that
wraps breaks after the dot and no line starts with one, and its gap is the Diff
summary’s. A change set of no statuses is its totals alone, “+1,234 −567”, and a count
it does not know is “?”. A total of zero is left out, so a change set that only adds
lines reads “+1,234” and one that only deletes them “−567”, since a “−0” is noise
wherever the line stands; totals both nonzero, or not known, read both, and a change of
no lines reads “0 lines”, muted at its line’s weight (`.change-line-none`), said “no
lines changed”.
Its `label` says it in words for a screen reader, “10 added, 5 deleted, 4
modified; 1,234 lines added, 567 deleted”, and on a line whose name does not, its hidden
dot says a comma in its place (`spoken`). The [Diff summary](#diff-summary)’s header is
this component, after its file count, “35 files changed · ”, only where no
[size line](#change-size-line) above it says the count; a commit’s
[hover card](#git-commit-summary), a commit page’s totals line, a pull request’s row in
the Pulls tab ([The Pulls Tab](#the-pulls-tab)), and a stack’s heading there
([Stack Groups](#stack-groups-in-the-pulls-tab)) draw it too; the last two draw its line
totals alone, with no statuses, on a Pulls row’s last line under the run of its title,
number, and author. It sets no size or ink of its own, so it takes its line’s.
`tests/dom/count-parts-session.js` pins its markup (`cli-ui-count-parts.tryscript.md`),
and `test_count_summaries_mute_their_punctuation_and_ink_their_status_counts` its rule
and that no plugin writes its classes itself.

### Change Size Line

**A change set’s size, “77 commits · 83 files changed · 2.3 MB compressed (14.0 MB raw
diff)”, is one component, the change size line, on its own line above the
[Diff summary](#diff-summary).** The Diff summary under it then says only what kinds of
change and how many lines, its [brief change line](#brief-change-line), so every change
set says its statuses one way and its scale on the line above.
It has one builder and one painter, `changeSizeLine` and `changeSizeLineNodes` or
`changeSizeLineHtml`, view helpers of the SDK (`static/plugin-sdk-views.js`) rather than
a startup script, since only these pages and the hover card draw it; each paints through
the shell’s one painter of a count summary.
A plugin reaches them as `metabrowser.changeSizeLine` and
`metabrowser.changeSizeLineNodes`.

- **What it says.** How many commits, where the change set has more than one to speak
  of: a pull request always, and a merge commit the commits it brings in; how many files
  changed; and, once known, the size Git pushes for it, “compressed”, then its patch’s
  size, “raw diff”, in parentheses
  ([Change Sizes](project/architecture/arch-git.md#change-sizes)). A count not known is
  “?”; a size not known, or not yet answered, is left out, and the line says its counts
  until it comes.
- **How it is painted.** The commit and file counts use the
  [count summary](#count-summaries-bold-their-numbers) style.
  The compressed and raw values use the Files navigation’s blue size style, including
  its weight threshold.
  The words and parentheses keep the line’s ink and weight.
  Each muted dot stays with the group before it by a no-break space, and a screen reader
  says a comma.
- **Its tooltip.** The size says what each size is, “2.3 MB compressed: what Git pushes
  for this change…”, which its words cannot
  ([Tooltips Add Information](#tooltips-add-information)).
- **Where it is.** A page header’s line above its Diff summary, on a commit’s page
  (`.git-commit-size`) and a pull request’s (`.github-pull-size`), and a commit’s hover
  card’s line above its change line ([Git Commit Summary](#git-commit-summary)). On a
  pull request’s page its row is as tall as the summary’s and holds the shell’s pending
  placeholder while the summary waits, so neither row moves the tabs, and it is one
  line, cut short at the row’s end in a narrow pane.

`tests/dom/git-panel-behavior.js` pins its words on a commit’s page and hover card,
`tests/test_git_commit_summary_chrome.py` its ink and weight in both themes, and
`tests/test_github_pull_header_chrome.py` its row on a pull request’s page.

### Diff Summary

A change set has one Diff summary, and it starts collapsed.
A page with a header of its own holds it at its top, on every tab, so the counts are not
inside the changes: a commit’s page under the commit’s identity, in its
[commit summary](#git-commit-summary), where the commit’s diff draws it (`summaryHost`),
for one file too; and a pull request’s page as its header’s last row
([Layout](#layout)), which the page draws from the comparison it reads, through the diff
view’s `summary`, while its Changes diff draws none (`summary: false`). Elsewhere, as in
a patch file, a diff of more than one file opens with it in the toolbar beside the
layout control. While a page waits for the comparison its summary is drawn from, the
summary’s place holds the shell’s pending placeholder: the navigation tally’s gray block
and slow pulse (`.tally-pending`), shown only after the quiet period
(`.mb-delayed-loading`, `--loading-state-delay`), in the header’s type, centred on its
row’s line from the row’s start, and as wide as a summary of one status, so the summary
takes its place and nothing moves
([Loading States Are Shapes, Not Sentences](#loading-states-are-shapes-not-sentences)).
The wait starts when a comparison is on its way, before the page has one: on a pull
request’s page, from the first paint of a page whose read will bring one, before its
first answer and while its own fetch is running, still to be sent, or waiting for the
reader; a core preview whose read prepares the comparison with the record; or a record
whose comparison the page asked the server to prepare.
One placeholder carries the wait from the first paint through the core and its record to
the read, with one quiet period and one pulse, so the row is never empty while the
comparison is on its way.
Where the pull request’s changed-files list is cached, the list a Pulls row’s change
line sums, the place holds that list’s line instead of the placeholder: “2 A, 3 D, 31 M
· +2,076 −224”, the summary’s header’s words with no chevron, which the header brings
after them, in the same place, so the summary that replaces it moves no word, and the
size line above says its file count, “36 files changed”.
It is drawn only once the page knows the head, and only for a list of that head and its
base, the record’s comparison’s base commit or the pull request’s base branch, so a
pushed or retargeted pull request never shows an earlier list’s counts; the placeholder
waits instead. It stays when the wait ends with no summary.
A page opened from a Pulls row draws it from the row’s line with no request, unless the
Pulls tab marked that line out of date (`builtin_plugins/github/pull-summary-brief.js`).
The wait is the read in flight: on Changes the mounted diff’s, so a newer comparison the
record names waits until the reader takes it.
A pull request that is not GitHub’s, a server with no store to compare in, a core whose
read prepares no comparison, and a read that failed with nothing running have nothing on
their way, and only Changes asks for their comparison; before the server’s first answer
the page cannot tell, so on such a server the placeholder ends with that answer.
A read that draws no summary, because it failed or its comparison is not a valid
document, leaves the place empty until a read of the same comparison starts again: at
the page’s next paint, such as a switch of tab or a poll that repaints it, or a Retry,
so a placeholder never outlives its wait and every wait has one.
A summary already drawn stays while a newer comparison is read
([Refreshing Content](#refreshing-content)), and the newer one’s summary replaces it in
one step. A pull request’s header shows it on every tab.
A commit’s page never shows it: the shell stages that page out of sight until its diff
has drawn the summary, so its place does not wait in view.
The row keeps its height from the placeholder to the summary, and the tab bar under it
does not move: `tests/test_github_pull_header_chrome.py`’s `summary-wait` part holds
that, and `tests/dom/github-pull-page-mount-behavior.js` which of the two the row holds
in each state; the block’s measured size is in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#diff-summary).
Its header is at `--body-font-size`, the size of the lines above it on a page
([Page Headers](#page-headers)), and in a patch’s toolbar too, and its tree’s rows at
the navigation rows’ size.
It is one row-like disclosure toggle that ends with the registry’s chevron, in the
tree’s icon slot, `--tree-icon-slot`, after its words: “35 files changed · 2 A, 3 D, 30
M · +1,234 −3,423 ›”, “1 file changed · 1 R · +5 −2 ›” for one renamed file.
**Wherever a diff summary expands, its chevron comes after the summary**: on this header
and on a Pulls row, whose toggle is its lines and the chevron after them
([The Pulls Tab](#the-pulls-tab)), so the counts are read first and the mark that opens
them follows. A folder’s toggle and a stack’s lead with their chevrons, as a tree’s rows
do ([One Chevron, One Row Contract](#one-chevron-one-row-contract)).
`tests/dom/diff-view-behavior.js` holds the header’s chevron last, and
`tests/test_reserved_chrome.py` the Pulls row’s. It is its file count, “35 files
changed”, and a muted dot, then the [brief change line](#brief-change-line), the one
component for the statuses and the line totals, “2 A, 3 D, 30 M · +1,234 −3,423”; in a
page’s header, on a commit’s page and a pull request’s, it is the brief change line
alone, “2 A, 3 D, 30 M · +1,234 −3,423 ›”, and the file count is on the
[size line](#change-size-line) above it, whose accessible name and tooltip leave the
count out too (`countsFiles` in `diff-view.js`); each dot is one item with the group
before it, so a header that wraps breaks after a dot and no line starts with one, and
one gap spaces it on both sides, on a toggle and on a line alike.
The statuses are only those some file has, in one order (added, deleted, modified,
renamed, then copied, type changed, unmerged, and any other), each a status count, its
count and the letter its rows carry, with a muted comma between each two; numbers use
the shell’s number format; the file count and the status counts are painted by the
[count summary](#count-summaries-bold-their-numbers)’s rule; the totals are the
[inline change stats](#inline-change-stats); and “(estimated)” follows totals that are
not exact, muted with its parentheses, a qualifier of the totals.
Its accessible name says the same in words, each status by its name: “35 files changed:
2 added, 3 deleted, 30 modified; 1,234 lines added, 3,423 deleted”.
A list cut short at its bound, on a page that knows the whole change set’s totals, as a
commit’s page does from the commit’s own stats (`summaryTotals`), has a header of those
totals with no breakdown, which would count only the files listed, and says how many
files are listed, muted as “(estimated)” is: “5,000 files changed · +15,000 −3,000
(2,000 listed)”; the tree holds the files listed.
A list that is whole says its own totals, whatever the page gives.
A host that cuts the breakdown short to keep the header on one line, as a pull request’s
header does, gives the header its whole words as a tooltip while it is cut, and none
while it is whole ([Tooltips Add Information](#tooltips-add-information)). A change set
of no files has nothing to open, so its header is a line, “0 files changed · 0 lines”,
which has no name, so each hidden dot says a comma in its place.
Where the shared tree did not load, the header is a line without its statuses, which
only the tree’s model names, “N files changed · +A −D” in the shell’s number format,
with no toggle, its dot saying a comma as the line of no files does; and a header whose
tree did not load when pressed is marked `aria-disabled`, with a tooltip saying a press
tries again, until a press loads it.

Opened, it shows the change set’s files as a tree by folder, the
[Pulls tab’s tree](#the-pulls-tab) adapted to the page and drawn on the same model
(`static/changed-files-tree.js`): the nav panel’s row height, indent, chevrons, change
letters, and inline change stats at the row’s end, a chain of single folders as one row,
and every folder with the line counts of the files under it rolled up, open or closed,
as a Files folder keeps its size whichever way it is turned.
Both trees draw one row, the shell’s `.changed-file-row` class set in
`static/styles.css` beside the Files tree’s rows: the 12 px content inset past the 2 px
bar, the square hover, and the focus ring 2 px inside the row; each plugin sets only its
depth’s indent, `--changed-file-indent`. The header hovers and rings in its rows’ style:
the same ground, square, and the same ring 2 px inside its own box.
`tests/test_changed_file_rows_chrome.py` mounts both trees on one list in Chrome and
holds them to one row.
A folder says in its accessible name what its sums leave out (“2 files without line
counts”, or each side’s when they differ), and its tooltip says that alone, since its
name is on the row ([Tooltips Add Information](#tooltips-add-information)). A path a
patch lists more than once, as a file that became a symlink, is one row with both
changes’ counts, and goes to the first of its sections.
The header is the tree’s root, so the tree’s first level starts one indentation step,
`--tree-indent`, in from it, its chevron from the header’s words, and each level one
step more, as a folder’s rows start one step in from the folder in the Files tree and
the Pulls tab’s, wherever the summary is: in a diff’s toolbar, under a commit’s
identity, and in a pull request’s header.
The rows give back where the header starts, `--diff-summary-header-inset`, the toolbar’s
padding in a diff and nothing at a page’s top; the header, the shell’s summary toggle
(`.summary-toggle`), pulls left by `--summary-toggle-pull` and pads back in, so its
words start where it is placed and its hover ground reaches a little past them.
Opened, the tree sits under its header, below the toolbar in a diff, as tall as its
rows, in the page’s flow, with no scroll bar of its own: the page scrolls past it.
It has no bound on its length beyond the comparison’s (`MAX_MANIFEST_FILES`), and the
document holds only the rows in the window’s view of it and `SUMMARY_ROWS_OVERSCAN` more
each way, as the Pulls tab’s tree does, so a tree at that bound shows its rows soon
after a press and scrolls with the page frame by frame; the measurement is beside the
constant in `diff-summary.js`. Nothing of it is mounted until the header first opens it.
The keys are a tree’s: the arrows move one tab stop, Right and Left open, close, and
step into or out of a folder, and Home and End go to the ends.
Only Enter, Space, or a press on a file jumps the diff to that file, because the tree
sits above the files and a jump on every step would scroll it away.
On a pull request’s page the jump goes through the file’s address,
`/pull/<n>/files/<path>`, the route a press on it in the Pulls tab takes, from any tab,
so the address names it and Back returns; a path the address cannot spell, such as one
with a backslash, opens Changes at the page’s own address and the diff goes to it once
it mounts; a patch file has no address for a place in its diff, so there the diff moves
in place and the address stays the file’s.

A path is its author’s text: a row shows it by the server’s display rule, with a
control, format, or invisible character, such as a right-to-left override or a
zero-width space, as U+FFFD, as the Pulls tab shows the same path, and the file bar the
row goes to shows it the same way ([Diff File Bar](#diff-file-bar)).
`tests/dom/diff-summary-session.js` holds the words, the rows, and the keys, and the
paint’s measurement is in the
[Parity Registry](project/architecture/arch-parity-registry.md) (`diff.summary-paint`).

A pull request’s page reads its comparison once for the page’s session, until a reload,
not once a visit: what it reads is kept for the document (`createComparisonKeep` in
`builtin_plugins/github/comparison-prefetch.js`), keyed by the comparison’s route, which
names both commits, so a pull request opened again draws its Diff summary in the paint
that shows its record, with no request, no wait for the browser to be idle, and no
placeholder, and its Changes mounts from the same answer.
That holds whichever tab read it first: a page opened on Changes reads through the keep
too, and draws the summary from what its diff read.
The summary is drawn once for each comparison and kept across the page’s tabs.
A page opened out of sight reads a comparison the document does not hold once it is
shown. A record whose head or base moved names another route, which is read anew.
The keep is bounded (`KEPT_COMPARISON_CHARS`): a comparison it no longer holds, or one
too large to keep, is read once the browser is idle, from the browser’s cache.
The first screen’s rendered Markdown is the page’s own to ask for, apart from the
comparison, so a page that goes stops it.
The Pulls tab reads ahead the comparisons of the pull requests a reader is likely to
open next ([The Pulls Tab](#the-pulls-tab)), so a first visit to one of them draws it at
once too. A read that waits for the browser to be idle arrives late, because a page is
not idle while it draws its record, and in the app’s WebKit, which has no
`requestIdleCallback`, the wait is the quiet after a press
([Idle Work](project/architecture/arch-browser-shell.md#idle-work)). The timings that
set this are beside `createComparisonKeep` and in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#diff-summary).
`tests/dom/github-pull-prefetch-session.js` holds that a second visit sends no request,
and the `summary-wait` part of `tests/test_github_pull_header_chrome.py` that a
revisit’s summary is in the frame that paints its record.

### Diff File Bar

The bar shows its path, and a rename’s two, by the server’s display rule, as the
[Diff summary](#diff-summary) does, and its stats in the shell’s number format; its copy
control copies the path as it is.

The diff view’s per-file bar is **a row, not a heading disclosure**: it leads with the
same registry chevron the tree uses (`.toggle-chevron`, rotated by the shared
`expanded`/`collapsed` classes), sits at the shared `--ui-row-height`, and hovers with
`--hover-bg`.

The bar reads in one order, left-aligned.
It leads with the group that names the file: chevron, kind letter, filename in the
shell’s file-path typography, then the `[data-mb-copy]` copy control right after the
name, the file-header copy affordance, present wherever a filename is, then the stat
pair and any note.
The stat pair and notes are not in the disclosure trigger but describe
it (`aria-describedby`), so the copy control can sit between them and the name.
The View file or View on branch control follows that group, and the bar ends with a
file’s **Rendered** | **Source** chooser when the file supports both formats.
A Markdown file can also expand or collapse its unchanged sections in Diff.
The [toolbar](#diff-toolbar) chooses the presentation for the whole comparison.

The bar reveals the copy control while the pointer is on it or the keyboard’s focus is
in it; unseen, the control keeps its place, so nothing moves when it shows.
Unlike the file header’s, whose copy control ends its row, this one sits mid-row, so at
rest its place is a gap between the name and the stats.
View file stands further off the stats than that (`--diff-file-actions-gap` in the diff
plugin’s `styles.css`), so the stats read with the name rather than with the action.

Where the bar’s parts do not fit one line, it wraps them in order, and the name’s group
keeps the first line, so no control is cut off.
A bar with a chooser wraps before its name is cut at all: View file and then the chooser
take the next line, the chooser still at the bar’s end.
Any other bar cuts a long path short on one line with its copy control, stats, and View
file still after it, the space before View file giving way before the name does, and
moves View file to the next line only where the name’s group would keep less than
`--diff-file-lead-basis`. The name’s group never breaks, and that basis was set from the
stats alone, so a group that also holds a mode-change note is wider than it: in a narrow
pane View file stays on the line and squeezes the group, its change letter under the
copy control and, with wide stats, its note under View file.

The whole bar is one activation surface, the folder-row rule applied to a section
header: clicking anywhere toggles, with only the copy control, the View file or View on
branch control, and the chooser of views opting out.

**Every card that shows a file’s changes folds by one builder.** `fileDisclosure` in
`builtin_plugins/diff/diff-view.js` makes the bar and the button that leads it, with the
chevron, and keeps the card’s state: open at first, folded to a body of no height that
stays in the document, so nothing it drew is disposed and the bar stays where it was.
Changes’ file cards are built from it (`renderFileSection`), and so is every card a
[guided review](#guided-review) step draws for a file, an excerpt’s or one that holds a
sentence in a diff’s place, which takes it from the guide’s drawer (`disclose` on
`guidePatchDrawer`) and names the file in its trigger.
Its Open full diff is a control that views the file (`.diff-file-view`), so a press on
it is the link’s. A file’s state in Changes lasts while its diff is mounted.
A guide draws a step anew each time it shows, so it remembers which of its cards the
reader folded and draws those folded again (`folds` in
`builtin_plugins/github/guide-reads.js`): for the document, as it keeps the step
answers, so a fold lasts across Next and Back, a return to the tab, and a poll, and
until the guide is read at a new head, whose files may differ.
A file a step cites whole is the diff view’s own card and is not remembered.
A new place that shows a file’s diff in a card takes the same builder, never a bar of
its own.
`tests/dom/diff-view-behavior.js` holds that the bar the builder hands a page is
the one Changes draws and what a press does, and
`tests/dom/github-guided-review-fold-chrome.mjs` measures a step’s card against the same
server’s Changes, open and folded: where the chevron sits, how it turns, how the bar is
painted, and that a real press folds the card and opens it.
On a pull request’s Docs and Changes, a changed Markdown file’s bar carries that
chooser, a joined chip group, and before it a small spinner that keeps its place in the
bar and appears only after the loading-state delay while the rendered view is on its
way.
Until that view comes the file’s body shows nothing, and neither does anything after
the file in the diff: the body takes a height only its answer knows, so a file shown
below it would move when the answer came, under a press already aimed.
A page shows its first screen once those files are drawn, or at its bound with the ones
still waiting drawn so.
The wait has a ceiling, `RENDERED_WAIT_MS` in `diff/diff-markdown.js`, counted from the
diff’s mount: a file still waiting then shows Source and keeps it, with Rendered to
choose, so a slow or busy server never keeps files that are ready out of sight for long,
and nothing replaces Source by itself afterwards.
A document drawn alone, as a guided review step draws one, has nothing after it to hide,
so its ceiling is its page’s own hold.
A file that falls back permanently to Source keeps the format chooser, with Rendered
unavailable and a tooltip giving the reason.
Where the main UI can show the file the change makes, the name’s group is followed by
one quiet text action that opens it there, with the tree, the tabs, and the ref selector
around it: **View file** on a commit’s diff, at the commit, and **View on branch** on a
pull request’s Changes and Docs, at the pull request’s head, on a mirror or beside a
checkout whose `HEAD` is the head.
Its label is a constant, since a branch name is the author’s, long, and on every bar;
its tooltip says the commit and whether the pin switches.
It stays visible rather than revealing on hover, because it is how a reader leaves the
diff for the file. It is a [text action](#control-families), so it is a link or a button
by whether it first switches the served pin, and looks the same either way.
A bar with nowhere to go has none, never a disabled one: a deleted file, a symbolic link
or submodule, a patch file, a pull request diff of another commit than its head, and a
checkout elsewhere. The old side has none, since a parent or a merge base is no branch.
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
An unrefined whole-line change uses the medium mix (`--diff-add-row-bg` and
`--diff-del-row-bg` in the diff plugin’s `styles.css`). A refined pair uses only the
lightest mix (`--diff-add-refined-row-bg`) for unchanged text and the intraline overlay
(`--diff-add-inner-bg`) for the changed ranges, which composite to the darkest depth; it
does not also show the medium depth.
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
**Excerpt** and **Full** keep those marks on added lines in the new version.
In Excerpt a deletion marker stands where lines were removed.

The line marker and line numbers continue to state change direction without color.
The gutter is a persistent structural cue, not the only cue.
Syntax foregrounds retain at least 4.5:1 contrast over line surfaces in both themes, and
intraline ranges use the standard text foreground to meet the same floor over their
stronger overlay.

### Diff Toolbar

The diff’s toolbar ends with `[Diff | Excerpt | Full] [Split | Unified]`, in one group
at its right. Docs fixes the source layout to Unified and shows only the presentation
chooser. A standalone patch omits Full because it has only the hunks.
Where the diff has a [File type](#diff-file-type-control) control, it leads them.
On a commit’s page and a pull request’s Changes and Docs the toolbar holds nothing else,
since the page draws the [Diff summary](#diff-summary) at its top; a patch’s toolbar
leads with the summary.
The toolbar wraps: where the choosers do not fit beside what leads them, their group
takes the next line together, still at the right, and a File type control too wide for
its line wraps its own parts, so nothing runs past the toolbar or scrolls sideways
(`.diff-toolbar` in `builtin_plugins/diff/styles.css`, measured in Chrome from 1,063 to
320 px by `tests/test_diff_current_chrome.py`).

Each chooser chooses one thing, and its scope is what it chooses:

| Chooser | Chooses | Where, and for what | Remembered as | Key |
| --- | --- | --- | --- | --- |
| **Diff** \| **Excerpt** \| **Full** | Both sides, the new side near changes, or the entire new side | The comparison or guide reference block | `diff.show`, or `github.docs.show` on Docs. Guide choices stay with the block. | `N` switches between Diff and Excerpt on a comparison |
| **Split** \| **Unified** | Source layout in Diff | The comparison | Settings saves the default as `diff.layout`. The toolbar overrides it for the comparison. | `L` |
| **Rendered** \| **Source** | How one file is drawn | A rendered-format file’s bar, for that file | Not remembered | None |

Changes, commits, and patches open on Diff.
Docs prefers Full and opens a large document as an excerpt, with a notice on that file.
Full source is checked against the comparison and bounded per file.
An unavailable full file falls back to its excerpt with a notice.
A guide keeps each citation’s default until the reader chooses a presentation for the
block. An old-side citation keeps its cited lines visible.
Eligible files open Rendered, and changing the presentation preserves the file’s format
choice.
Choosing redraws every file, and the reader’s place stays on the screen: the line
or rendered block at the pane’s top keeps where it is, or, where the choice leaves that
row out, the next row it draws (`anchorRow` in `diff-view.js`). A file with no such row
keeps its own top.

### Diff Layout Control

The joined layout control always orders **Split** on the left and **Unified** on the
right. Settings supplies the default for new comparisons, Split when unset.
Switching the toolbar layout reprojects the shared semantic model from cached rows.
A diff too narrow for Split draws Unified, and the control shows what is drawn, with a
tip on **Split** saying why; the stored choice is not touched, so Split returns when
there is room, and choosing **Split** there draws it with a sideways scroll.
Docs and Guided Review draw source comparisons in Unified.
In Excerpt and Full, the layout control keeps its place and marks its chips
`aria-disabled`. Their tooltip and accessible name say “Switch to Diff to change the
layout.” Returning to Diff restores the toolbar’s layout.

The diff’s toolbar, which holds the control, draws no rule under itself.
The first file card’s own border, at the cards’ 12 px gap below the toolbar’s padding,
is the line between the toolbar and the files.
On a commit’s page and a pull request’s Changes and Docs, where the toolbar holds the
diff’s choosers alone, a rule there would draw a second line 12 px above the card’s. In
a patch’s toolbar the [Diff summary](#diff-summary)’s header is its tree’s root, and the
tree opens under it with no line between them, as it does at a page’s top.
The toolbar is not sticky, so nothing scrolls under it that a rule would separate.
`tests/dom/diff-summary-chrome.mjs` reads in Chrome that a patch’s toolbar and a
commit’s draw no rule and that the first card starts 12 px below them.

### Diff File Type Control

A diff of more than one file leads its layout control with the Files tab’s **File type**
menu: the same [menu](#overlays-menus-and-dialogs) built by the same code
(`filterControls.typeMenu`), with **Any type** first, then the Groups and each display
group’s families, then the extensions most numerous first, each with how many of the
comparison’s changed files it holds.
Choosing types narrows the diff to their files and adds a muted note, “12 of 35 files”,
and **Clear** after the menu; the [Diff summary](#diff-summary) still describes the
whole change set. A choice shows in the menu at once, with the control `aria-busy` until
its files arrive, so there is no spinner; a choice that keeps no file says so in muted
text where the files would be, and one whose files do not load says so in an error
[notice](#notices) at the toolbar’s height, an alert.
`Y` opens the menu (`diff.type-filter`). `builtin_plugins/diff/diff-type-filter.js`
holds the behavior, and `tests/dom/diff-type-filter-session.js` its session.

## The Pull Request Page

The page at `/pull/<n>` shows one cached pull request.
It has almost no vocabulary of its own: it places the shell’s primitives, and a text of
the pull request reads as the same Markdown does in a file.
`test_the_pull_request_page_carries_the_shells_primitives` holds what follows, with the
tests named beside each primitive.

### Layout

The page is a header, a [tab bar](#the-tab-bar), and a body, in that order; native stack
navigation is part of the header.
The header is a [page header](#page-headers), as a commit’s summary is: the title, then
the row of ages, which ends in the stack chip, the author’s row, which ends in the
freshness note, the branches, the labels, the status line while it has something to say,
and the Diff summary, every line under the title at the body size and one gap under the
one before. It shares the title, the author, the age, and the Diff summary with a
commit’s page, in that order, and keeps the state, the branches, the labels, the stack
chip, and the status line, which a commit does not have; the table there says where the
two diverge and why.
The author is the shell’s [actor identity](#actor-identity), its avatar’s box holding
the person glyph where GitHub gave no usable avatar, as a commit’s author’s does.
The header, tabs, Conversation, and Checks use `.page-reading-column` and start at the
same pane gutter as the commit summary.
The first tab aligns with the content in narrow and wide panes.
The column includes the card’s insets so its text can reach the same measure as the
rendered README. Both headers use `.page-heading`. The title begins with the Pulls state
icon at the title’s font size.
The text wraps under its first line while the icon stays beside the first line, to two
lines at most, and one cut short there carries the whole of it in its tooltip.
The title is as tall as its own lines.
The state and ages sit `--page-title-gap` below it, followed by the author and branches
([Page Headers](#page-headers)). A two-line title puts the tab bar one line lower.
The cold page’s title is the Pulls tab’s row for the pull request where the list has
one, icon, text, and number, so it takes the record’s lines.
Where the list has none it is “Pull request #7”, held at two lines, the most a record’s
title takes, and a record that lands after the cold page was seen keeps those two lines
on that page, so it lands moving nothing; a one-line title then has an empty second line
there alone. A record that lands within the quiet period was never seen cold, and takes
its own lines. The icon and the text start at the header’s left edge, and the number,
outside the clamped text, ends on the header’s right edge, level with the title’s last
line, over the stack chip’s slot, which ends the row of ages, whatever the title’s
length. Where the title leaves the View on GitHub button its room, the row of ages keeps
that width, so the chip ends at the content edge, that room past the number’s end:
taking the room from the row too cut its ages and Browse code short in a narrow pane.
The colored badge that leads the row of ages gives the state in text and the title icon
is decorative. The header’s box is decided at first paint, on every tab, but for the
title’s lines and two rows.
The labels row is there only while a pull request has labels, so the tab bar under it
moves when a pull request gains its first label or loses its last.
The status line is there only while it has something to say, so the tab bar moves as a
failure, a message, or an offer comes and goes, and for nothing else: never between
tabs, nor as the age ticks, or a rate limit’s hold begins or lifts.
Otherwise it is decided in every state: the row of ages begins with the state’s badge,
as wide as the widest state, then an open pull request’s readiness badge, as wide as the
widest verdict, or its glyph alone in a narrow row
([A Pull Request’s Readiness](#a-pull-requests-readiness)), then “Opened”, the ages, and
Browse code, and ends in the stack chip’s slot (see native stack navigation below), one
line at a chip’s height whose ages are cut short at their end, the links after them
whole down to 420 px, or 560 px beside two stacks’ chips, below which they are clipped
at the row’s end; the author’s row is one line, the author and the sentence, then the
freshness note; where that row has no room left, the note leaves it first, whole, and
then the sentence is cut short at its end, the action first and then the author, never
moved or wrapped; the branches have the line under it to themselves, one line in every
state, their names cut short rather than wrapping it; a pull request with labels has a
row of them, one line at a label’s height, and one with none has no labels row and no
gap for it; and a cold page keeps every row, empty, at its height.
The freshness note is muted, after a muted dot, at the sentence’s size, stepping back by
its ink: one time, the record’s own fetch, “jlevy wants to merge 1 commit · Fetched just
now via GitHub CLI”, never a second time for a check that found nothing changed, since
that makes what is shown no newer.
A rate limit’s hold is said in its place, “GitHub rate limit reached.
Next attempt after 2:05 PM.”, in the failure’s ink: it begins and lifts by itself and
asks nothing of the reader, so it adds no line.
It names a time of day, in the reader’s short form, when the limit lifts today, and a
short date and time otherwise, “12/31/26, 4:00 PM”. Unlike an age, it never leaves the
line: where it cannot be whole it is cut short with its whole text as a tooltip, down to
a floor that keeps “GitHub rate limit” whole, and below that the sentence gives way, so
the page always says why nothing refreshes.
Before a record is shown the note is the page’s word on it, “Fetching the pull
request…”, so the record landing changes no line; a failure to fetch it takes that word
to the status line beside it.
The note’s slot is as wide as its widest age, so the age ticking changes its width not
at all. Beside the sentence the note is whole or not there: where it cannot be whole, it
leaves the line, dot and all, so the author and the sentence keep their natural widths
while it shows, and only then is the sentence cut short.
Alone on the row, before a record, it is cut short with its whole text as a tooltip.
The page has no Refresh of its own: the navigation’s Refresh refreshes the page, among
the first of what it refreshes while the page is in the main pane, and waits, dimmed,
while the parts on screen refresh
([Refresh, Retry, and Reload Page](#refresh-retry-and-reload-page)). The page offers its
remedy where it says what it lacks or what failed: Fetch beside “This pull request has
not been fetched yet.”, or beside a saved copy another version wrote, and Retry beside a
failure to fetch or refresh it, first among the status row’s offers, so the reader can
ask again with the navigation pane hidden.
It follows Browse code, so it takes the number after Browse code’s
([Numbered Controls](keyboard-shortcuts.md#numbered-controls)). While the refresh it
asked for is due and has not started, it waits: shown and muted, `aria-disabled`, it
keeps its place and its number, so an offer numbered after it keeps its own, and a press
does nothing.
Once that refresh runs, the status row says so in its place, and the remedy
goes. The status row is the next metadata line, a line tall, as the author’s row is,
there only while it has something to say: a failure and its remedy, a message, and the
offers at its end, its text and then its offers’ sentences cut short, never their
controls. A comparison’s refusal is said in the Changes body, beside its Retry, not on
the status row, which would then show it on Changes alone and move the tab bar between
tabs. A pull request that cannot be shown has no author’s row and no row of ages, so its
message and its remedy are on the status row.
Only a failure, which says what to do, wraps the status row.
Retry or Fetch is a [text action](#control-families), a line tall, as Browse code is, so
its row is no taller than its text.
A cold page holds the labels row while the labels are unknown, since the record may
bring some: a record with labels lands moving nothing, and one with none takes the row
and its gap away in the paint that lands it, the one paint that changes the header and
the body together. A record’s labels come with it or its core, and a label’s color and
tooltip, which the repository’s label set may bring later, change no chip’s box.
A refreshed record that gains a pull request’s first label, or loses its last, adds or
takes away the row and its gap on a loaded page, and the tab bar moves with them; only
GitHub changing the labels does that, so the header follows it rather than hold an empty
row for every pull request.
A page mounted with no record in hand, as a direct load or a reload mounts it, keeps its
header and tab column out of sight for the shell’s quiet period
(`--loading-state-delay`), by opacity alone, so its rows keep their layout and the tab
keys stay live, and shows them with the first header that has a record or core.
A read that lands within the quiet period never shows the cold header.
When the conversation’s first paint then waits for its texts’ Markdown
(`DESCRIPTION_HOLD_MS`), only the body waits: the header paints the record at once, so
the title shows as soon as the record is in hand, and the body follows below the
header’s held rows (exp-099). So the one move left on a cold page is a slow read of a
pull request with no labels: past the quiet period the cold page shows, rows held,
rather than a blank pane, and the record that lands later takes the labels row and its
gap away, moving the tab bar up by their height.
A pull request with labels lands moving nothing.
A Pulls open whose read answers within its wait hands the page its record, and a
retained navigation keeps the page out of sight until it has one, so neither shows a
cold page. The header’s rows are one gap apart (`.page-header`), whatever its state
([measurements](../explorations/performance-loop/design-rule-measurements.md#the-pull-request-header)).
A cold landing measured in place, read by read, is recorded beside `.github-pull-cold`
in `builtin_plugins/github/styles.css`, and `tests/test_github_pull_header_chrome.py`’s
`cold-landing` part holds it.
The header’s last row is the pull request’s [Diff summary](#diff-summary), on every tab,
so its counts are at the page’s top and not inside Changes.
The row is held at `--ui-row-height` from first paint, holding the
[pending placeholder](#diff-summary) from first paint while the comparison is on its way
and while it is read, and the summary’s header is one line, its breakdown cut short at
its end, so the summary that arrives moves nothing; opened, its tree pushes the tabs
down, as the reader asked.
How the page reads the comparison the row is drawn from, what the row holds while it
waits, and what a read that fails leaves there are the [Diff Summary](#diff-summary)’s
rules.
The row starts on the header’s content edge, and its toggle hangs into the gutter,
as every Diff summary’s does; a breakdown cut short carries the whole header in its
tooltip. `tests/dom/github-pull-header-chrome.mjs` holds its geometry
([measurements](../explorations/performance-loop/design-rule-measurements.md#the-pull-request-header)),
and `tests/dom/github-pull-page-mount-behavior.js` the row’s order, reads, failures, and
disposal. A tab switch or a poll builds again only the header’s parts whose inputs
changed: the title, the badge, the author, the branch chips, the row of ages, the
labels, and each status control are kept while what they show is the same, so a repaint
that leaves a control as it was does not take its focus, hover, or tooltip from the
reader. `test_the_header_keeps_its_nodes_and_each_avatar_loads_by_its_placement` counts
what each repaint builds.
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
`GitHub rate limit reached. Next attempt after` a time, or the last failure with Retry.
The wording is `rateLimitText` in `builtin_plugins/github/copy.js`, which every GitHub
surface uses. The Checks tab uses the same heading and status badges for check runs and
status contexts. A check row is its status badge, its plain name, its action, and its
description. The badge says the check’s own state, as GitHub names it, in the ink of the
bucket the server sorts it into as `gh pr checks` does: pass `--status-success-text`,
fail `--status-error-text`, pending `--github-pull-attention`, the readiness’s
attention, so waiting is one color across the plugin, and skipping and cancel `--muted`;
the page sorts no check into a bucket of its own.
A check a rule on the base branch requires carries a compact outlined **Required** tag
after its name, in the row’s muted ink, as the ref chooser’s tags are
([Chip Sizes](#chip-sizes)). The rows are in `gh`’s order, failing first, then pending,
then the rest, and the summary over them leads with `gh`’s headline for them, “Some
checks are still pending”.
While the server has counted the head’s checks and no read has listed them, as after the
Pulls tab’s scan, the summary is the server’s counts and a muted line says the list is
being read; a scan’s status is drawn as a read’s is.
The tab opens with the **Merge status** section
([A Pull Request’s Readiness](#a-pull-requests-readiness)), before the checks.
The action says where it opens: **View action on GitHub** for a GitHub Actions run,
**View on GitHub** for another page on a GitHub host, and **View details** for the
check’s own site, and its accessible name adds the check’s name.
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
Arrow keys, Home, End, and focus return follow the menu pattern, and it closes as
[every menu closes](#every-menu-closes-alike).
On a selected PR on macOS and iOS, Control-N opens the next member toward the stack top
and Control-P the previous one toward its base, with or without Shift; Help lists them
in its Pull request stack group.
On Windows and Linux those chords stay the browser’s, and the menu walks the stack
([Control Chords](#control-chords)). A focused Pulls row keeps `J` and `K` for its own
rows. Editors, dialogs, unknown membership, a header still held over the loading page,
and inactive pages keep their normal keyboard behavior.
Stack endpoints consume the shortcut without moving.
A member selection preserves the current PR tab and clears the previous file selection.
Unknown membership and unavailable optional tooling add no placeholder or setup notice;
known cached membership remains visible during refresh or failure.
Membership has its slot at the right end of the row of ages, with the state and ages it
belongs with, under the end of the title, and it ends the row at the content edge, where
the title’s number ends unless the title leaves the View on GitHub button room.
Its chip, which arrives from its own answer after the page, lands in the row’s empty end
and moves nothing. The chip keeps its whole width while any of the ages or Browse code
shows: where the row has no room left for it, the ages are cut short at their end, then
Browse code, and only once they have no width left is a chip’s position cut short, its
tip saying the whole of it, so the row never ends past the header.
The slot’s strut holds the row at a chip’s height from first paint, and the author’s row
is a line. Its menu hangs from the row’s end.
Its `details` is no taller than the strut it replaces there, since the slot sets the
chip’s own size. `tests/dom/github-pull-header-chrome.mjs` holds, in Chrome, on
Conversation and on Changes, that a late chip moves nothing in the header, every row
included, shows whole, ends the row of ages on the content edge, the title’s room past
the end of its number, does not overlap the ages, and has its position cut short only
once the ages and Browse code have no width left
([measurements](../explorations/performance-loop/design-rule-measurements.md#pull-request-stacks-and-the-timeline)).

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
precedes it. Inside a text that space is KPress’s heading spacing, exactly as in a
document in either reading font.
A heading’s top margin collapses with the block before it, so the space after a
paragraph, list, code block, or blockquote is the heading’s own, or the block’s when
that is larger. The page adds no heading rule.

The top of a text is where a message departs from a document.
A document’s card has KPress’s top padding, and only an opening h1 gives up its margin
to it (`static/styles.css`); any other first block’s top margin adds to that padding.
A message card is denser, like a comment body on GitHub, which trims the first and last
margins. The text’s padding is `--content-padding-y` above and below, and at the sides
the card head’s inset, which is `--boxed-prose-padding-inline`
([Boxed Prose](#boxed-prose)). Since the trim leaves a heading that opens a text only
that padding above it, the padding is at least any heading’s space below, so an opening
heading is never nearer the card head than its own paragraph.
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
Until its render arrives, a text in or near the view holds the loading blocks’ gray rows
in the box its plain text would take, shown after the quiet period and pulsing unless
the reader asks for reduced motion, so it first shows rendered and never as Markdown
source. A text farther than `MARKDOWN_AHEAD` (`pull-page.js`) from the view stays plain
until it nears the view, so find in page reaches it.
A text whose render will not come shows as plain text in the same face and size, with
the line that says why.

### Conversation Timeline

The Conversation is a timeline of events: the description, then its comments, reviews,
and commits, in the order the page places them
(`tests/dom/github-pull-timeline-session.js` holds the order).
A commit is an event of the same weight as a comment, so it is not set smaller for being
a commit. It is said the way a card head says a comment:

- **Type:** a commit row is set as a card head is.
  It is set at `--body-font-size` on the head’s line, and its box is that line, with no
  room of its own above or below, in a frame as wide as a card’s that draws nothing.
  Its subject is bold in text ink where a head’s author is, with a conventional-commit
  prefix regular ([Titles](#titles)), and starts where the author’s name does after the
  avatar, the shell’s `--actor-avatar-size`, and the identity’s gap,
  `--actor-identity-gap` ([Actor Identity](#actor-identity)). A card head whose author
  has no usable avatar keeps the avatar’s box, holding the person glyph and hidden from
  assistive technology, as the header’s author does, so every head’s name and every
  commit’s subject start at one x. Pulls rows draw no such box.
  “committed” and the age read as a head’s “commented” and age do, with no quieter ink
  or size. The hash is the [GitHub action](#chrome) at the size of the text beside it, as
  a [short commit ID](#short-commit-ids) is everywhere.

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
  The rhythm is the Conversation’s alone, the space above each of its events, whatever
  stands before it. The Files and Checks tabs keep `--github-pull-gap` (12 px) between
  their notices and what they show, and a section or note below an event, such as Review
  comments, keeps that gap and its own margin.

- **The line:** one 2 px line in `--border` joins every two adjacent events, down the
  center of the card heads’ avatars and the glyphs in the boxes of authors with none.
  Each commit has a solid `--muted` dot on the line at its first line, the shape of the
  history graph’s [commit nodes](#commit-nodes).
  The line starts at the first event, ends at the last, and breaks wherever something
  that is not an event, such as Review comments or a note, stands between two events.
  Commits that answer after the conversation has painted go after everything, so their
  run has a line of its own.

This is the structure of GitHub’s own pull request page, a line down the timeline with a
mark at each commit, drawn in the shell’s tokens and none of GitHub’s assets.
Its tokens are the rhythm and the avatar’s two: the commit row’s start, the line’s x
down the avatars’ centers, and an absent avatar’s box are derived from the avatar’s size
and the identity’s gap, and the rest of its geometry is the card head’s.

`tests/test_github_pull_timeline_chrome.py` measures it in headless Chrome, in both
places the page puts commits, in both themes and a narrow pane, from the boxes laid out
and the pixels painted, with one head drawn with the person glyph in its box.
Its measurements in Chrome and the app’s WebKit are in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#pull-request-stacks-and-the-timeline).

### Chrome

| Element | Primitive | Why |
| --- | --- | --- |
| Title | `--page-title-font-size`, `--weight-bold` in normal text ink, sans | A pull request’s title is bold in normal text ink wherever it appears ([The Pulls Tab](#the-pulls-tab)), and a conventional-commit prefix that starts it regular ([Titles](#titles)). The number beside it uses normal text ink at the same size, bold ([Pull Request Numbers](#pull-request-numbers)) |
| State, review, and check badge | `.file-header-badge`, in the state’s status ink; a review’s only for a state its verb does not say ([Conversation Timeline](#conversation-timeline)) | A pill means a filter, and a badge is not one: a badge is static, and the readiness’s, a link to the Checks tab, is a clickable chip ([Clickable and Static Chips](#clickable-and-static-chips)). Sentence case, like all chrome, so the badge centers its capitals: `text-box` trims its line to them and the baseline, in a box as tall as its line, pads, and borders, which `test_badges_center_their_capitals_in_the_box_they_had` holds |
| Username | The shell’s [actor identity](#actor-identity): an avatar’s box, then `.actor-name`, bold in normal text ink at the surface’s normal text size | Applies to the author, merger, comments, and reviews; a small circular avatar belongs to that same actor, and the person glyph stands in its box where there is none, as on a commit’s page |
| Head and base branch | `mb.mergeRefs`, head → base on a line of its own under the author’s sentence: “forker wants to merge 2 commits”, then “forker:count-to-two → octo:topic” | [Merge Direction](#merge-direction): two remote [ref chips](#branch-chips), each the chip’s [one size](#one-size), and the one arrow the list uses too. [Which Kind Each Context Gets](#which-kind-each-context-gets) says why remote and never trunk |
| Label | Hairline box with `--radius-tag`, in GitHub’s color for it, its description its tooltip ([Label Colors](#label-colors)) | A name the pull request carries, the corner tag-like chips use, colored as github.com colors it so a label reads as the same label in both places. It is a [static chip](#clickable-and-static-chips): nothing under the pointer |
| Opened, updated, commented | `metabrowser.ageLabel` with relative style, exact time in the tooltip | [Age](#age); condensed navigation uses compact style |
| File of a review comment | Sans, bold, at the card head’s size | A path is chrome, and in the main view it reads at the body size, as a diff file bar’s does ([Type Scale](#type-scale)) |
| Link, including a check’s action off GitHub | `--link`, underline on hover, the focus ring | As the freshness row’s link is, so a check’s action never reads as the muted description after it. A link whose content is a chip, the readiness badge’s, is a [clickable chip](#clickable-and-static-chips) instead and is never underlined |
| View on GitHub | The [View on GitHub](#view-on-github) button in the header’s corner, the page’s own counterpart on github.com | One button in one place on every page that has a counterpart, so it is never a link in the metadata |
| GitHub action: a check’s action on GitHub | `.github-pull-external-action`: `--muted`, with the leading GitHub mark in the same ink; `--link` on hover and focus | Quiet beside the metadata it follows. A check is GitHub’s by the rule that gives a link the GitHub mark, so its look and its mark agree |
| Conversation commit hash | `.git-commit-sha` at the row’s size, a link to the commit on GitHub with the leading GitHub mark, in the commit-ID gray at rest, on hover, and on focus; hover underlines it | A [short commit ID](#short-commit-ids) is the same gray and the size of the sans beside it wherever it appears, and a commit row is set at `--body-font-size` ([Conversation Timeline](#conversation-timeline)) |
| Browse code, and a review comment’s file | [Text action](#control-families): a link, or `.github-pull-text-action` on a button where it first serves the pull request’s head | The look of the Link row in both forms, so moving the pin never looks like something else |
| Section title | [`.section-heading`](#section-headings) |  |
| Note about the content | [`.notice`](#notices) | `warning` when a text, list, or hunk was cut or a part could not be read; `error` when Changes cannot be drawn; no severity for the offer of newer changes, which carries its own control |
| A review comment’s earlier lines | [`.fold-expander`](#fold-expanders) on a native `summary` | States its count, and the inverse when open |
| A review comment’s hunk | `--font-mono` at `--mono-block-font-size` | The user’s code, with the diff view’s row tints |
| Empty state | `--muted`, sentence with a period |  |
| Retry, Fetch | [Text action](#control-families): `.github-pull-text-action` on a button | The status line’s remedy, first among its offers, so it looks as a link does and is a line tall, where a bordered `.btn` is taller than a metadata line |

Author, action, and relative age share one metadata size and baseline in a header or
discussion card. The bold username uses the normal text ink wherever it names an actor.
The avatar centers independently beside that text baseline.
In the navigation column an age reads at its row’s list size, and a branch chip keeps
its ratio.

Author avatars are decorative circles beside the visible username, with fixed dimensions
so image arrival or failure does not move the text.
Images load at low priority and decode asynchronously, and when they load depends on
where they are ([A Repaint Keeps Its Images](#a-repaint-keeps-its-images)). The header’s
avatar is eager: it is at the top of the page, and it is a new image whenever its actor
changes. A Pulls row’s is eager, because only mounted catalog rows can create images,
which bounds what the Pulls tab asks for.
The conversation’s are lazy: its sections are kept across tabs and polls, and an avatar
far down a long conversation waits until the reader nears it.
Missing or unsupported image URLs, and an image that fails, leave the username readable
and the box holding the person glyph, on the page; a Pulls row and a stack menu’s member
row draw no box for a missing one ([Actor Identity](#actor-identity)). Use the avatar of
the named actor: a merged header naming the merger shows the merger’s image, while the
description shows its author’s image.
Only normalized HTTPS URLs on `avatars.githubusercontent.com` are accepted, checked
again before assigning the browser image source.
Anonymous CORS and a no-referrer policy omit credentials and the local page URL. The
browser’s HTTP cache owns image bytes; PR metadata caches retain only URLs.
Document image sanitization remains independent; see [Content Trust](../SECURITY.md).

### Guided Review

**A guide names every place the same way, in one vocabulary, from one module.** The
names, the badge, and the place labels are constants at the top of `guided-review.js`
(`GUIDE`, `OVERVIEW`, `placeName`, `groupedPlace`, `stepName`, `guideBadge`), and every
part below takes its words from them, so the step list, the arrows’ tips, the way on and
back, and a step’s card never disagree.
The user guide’s [Guided Review](reviewing-pull-requests.md#guided-review) says what a
reader does with it.

| Part | What it shows | Drawn as |
| --- | --- | --- |
| Name | “Guided Review”: the tab, the badge, and the list’s label | `GUIDE` |
| Step 0 | “Overview”: the description, as Conversation renders it | `OVERVIEW` |
| Place | “Overview”, or “Step 3 of 9”: where the reader is, never the count alone | `placeName` |
| A step by name | “Step 3: Inspect the request path”: the list, the tips, the way on and back | `stepName` |
| Badge | A state badge’s outlined box leading a head, 8px from its label, as a page header’s state badge leads its line | `guideBadge`, `.github-pull-guide-card-head` |
| Step list | A card above the step: the badge, the arrows around the place, then each step, numbered, the one shown marked as a table of contents marks its section. A row outside any group is not indented: it starts on the edge a group’s heading starts on, the overview’s title with no number before it, and a step’s number read from that edge, in a column as wide as the widest such number, so those steps’ titles line up | `.github-pull-guide-outline`, `--highlight-bg`, `--highlight-bar`, `--github-pull-guide-loose-digits` |
| Group | In the step list, the group’s title as the shell’s [group heading](#groups-in-a-menu), on the edge a row outside any group starts on, with no number and nothing to press, above its steps, which keep their numbers in a column of their own that starts on that edge, each number set to the column’s end; on a step’s card, its title before the place, “Decisions · Step 2 of 12” | `.group-heading`, `.github-pull-guide-steps-heading`, `.github-pull-guide-steps-members`, `groupedPlace` |
| Group note | The group’s note above its first step’s card at the card text’s inset, its Markdown rendered as a step’s note is, or as typed when the render did not come, with a refused render’s line under it as a step’s note has | `.github-pull-guide-group-note`, `.github-pull-guide-note-refused` |
| Arrows | Icon buttons, `arrowLeft` and `arrowRight`, centered in an icon button’s box, with no label of their own | `.github-pull-guide-arrow` |
| Way on and back | Worded buttons below a step that name the step they go to | `.github-pull-guide-pager` |
| Step | A page card, as Conversation draws a comment: the badge and the place, the title as text and the note’s Markdown rendered as the description is, at the description’s inset, then its excerpts; a note whose render did not come, as typed, and, when it was refused, the warning a description’s refusal has under it, in its words | `.github-pull-guide-card`, `.github-pull-text`, `.github-pull-guide-commentary`, `.github-pull-guide-note-refused`, `textRefusalNote` |
| Reference block | One comparison chooser immediately above the step’s file cards. Full appears when a whole-file reference can use it. | `guidePatchDrawer`, [Diff Toolbar](#diff-toolbar) |
| Excerpt | A collapsible file card with the cited side and inclusive range, source hunks, their fold bars, and Open full diff. A presentation change stays within the cited range. | `mountFilePatch`, `fileDisclosure` through `guidePatchDrawer`, `referenceBar` |
| Document | A whole file in the same collapsible card as Changes or Docs, with Rendered and Source where available. A failed read keeps the file name and Open full diff above its notice. | `mountRenderedFile`, `DOCS_DRAWING`, `CHANGES_DRAWING` |
| Out of date | One warning notice above the guide and its one remedy, or a quiet line when no file it cites changed; a step that cites a changed file is marked “changed” in the list and on its card, in muted text | `OUTDATED`, `CHANGED`, `.github-pull-guide-stale`, `.github-pull-guide-step-changed` |
| Another pull request’s file | An excerpt or a document, as a file of this pull request is drawn, under a bar that names that pull request’s number before the path, in a pull request number’s weight and muted ink; its Open full diff opens the file in that pull request’s Changes | `referenceBar`, `.github-pull-guide-reference-pull` |
| Pull request | One row in an excerpt’s card, a stack’s [member row](#stacks) in its order: the state icon and the title, which alone gives way, then at the row’s end its place in a stack, its number after a muted dot, and its author after another; the place is bare in the guide’s own stack, “1/3”, names any other stack by the Layers glyph and its number, “⧉300 2/2”, and says its stack in its tip and its accessible name, “Stack #71, position 1 of 3”; one in no stack has no place, and one this copy has not read keeps the icon’s slot empty and names itself by its number | `pullRow`, `stackMemberRow`, `namedStackPositionNodes`, `stackPlaceHint`, `.github-pull-guide-row`, `.github-pull-stack-member` |
| Commit | One such row, as the Commits tab lists a commit: its [short ID](#short-commit-ids), its subject, and at the row’s end when it was committed, the age in its freshness ink ([Ages End the Row](#ages-end-the-row)); a plain link to the commit’s page; one the store lacks says it is unavailable beside its ID, and one this checkout cannot open says so after its subject | `commitRow`, `COMMIT_UNAVAILABLE`, `.github-pull-guide-commit` |

A new part of the guide takes its words from these constants and its look from an
existing part of the design system.
It does not get a new name or a new look of its own.

**A step shows whole, and nothing in it moves.** A step is drawn out of sight and
replaces the one shown in a single change once everything its layout depends on is in
hand: its answer, the text’s stylesheets, what draws its excerpts and documents, each
document’s first screen with its rendered layer (`GUIDE_DOCUMENT_HOLD_MS` in
`guide-reads.js`), and on the overview the description’s Markdown
(`GUIDE_INTRODUCTION_HOLD_MS`, past which the overview shows with its placeholder).
Until then the step the reader left stays as it was, and the arrows move on from the
step the reader went to, with their waiting mark beside them, out of the flow, as a
delayed loading state.
A page loaded on the tab shows the delayed loading block until the guide’s first step
shows.

**What a reader is about to see is read ahead.** A pull request’s page reads its guide’s
first step and module when it is idle on another tab, and on Guided Review’s own tab
beside the module’s import; a stack’s page does the same at the comparison Docs or
Changes draws.
The guide reads the steps next to the one shown when the page is idle, and
keeps what it reads for the document (`guide-reads.js`), so moving one step, leaving the
tab and coming back, or opening the tab shows a step at once, with no loading state.
A step that cites a file whole still draws that document as it shows, so the arrows’
mark may show while it does.
A step that cites what is not read yet, as another pull request, is read again each time
the reader goes to it, so it fills in once that is read, and every step is read again
once GitHub reports newer commits, since the guide may then be out of date.
`tests/dom/github-guided-review-motion-chrome.mjs` samples every frame from a press, or
a page load, to the settled step and holds that nothing moves, on a pull request’s page
and a stack’s, cold and warm; `tests/dom/github-guided-review-session.js` pins what is
read ahead and kept.

### Label Colors

**A label is colored exactly as github.com colors it, in our chip’s box.** GitHub gives
each label a color, six hex digits, and a description, and a reader who knows a
repository’s labels by their colors on github.com should find the same colors here.
Colored and neutral chips share the same [compact box](#chip-sizes) and
`--ui-small-font-size`. The header reserves that box’s height while waiting for labels.

The colors are github.com’s own formula, read from its stylesheets (its global
`.hx_IssueLabel` and Primer React’s `.prc-Token-IssueLabel`, which agree, on
2026-11-15). The page sets the label’s red, green, and blue, 0 to 255, and its hue,
saturation, and lightness, each rounded to a whole number, as github.com does, on the
chip as `--github-label-r`, `--github-label-g`, `--github-label-b`, `--github-label-h`,
`--github-label-s`, and `--github-label-l`; `github/styles.css` states the formula once.
The formula’s custom properties are github.com’s under the plugin’s `--github-label-`
prefix, so none shares a name with the shell’s label register (`--label-color`,
`--label-font-size`); the stylesheet maps each to github.com’s name.
Its perceived lightness is (0.2126 R + 0.7152 G + 0.0722 B) / 255.

| Part | Light theme | Dark theme |
| --- | --- | --- |
| Ground | The color | The color at 0.18 alpha |
| Text | Black when the perceived lightness is above 0.453, white otherwise | The label’s hue and saturation, its lightness raised by (0.6 − perceived lightness) × 100 points when the perceived lightness is under 0.6 |
| Border | The label’s hue and saturation 25 points darker, at alpha (perceived lightness − 0.96) × 100, clamped to 0 to 1, so it shows only on a very pale label | The text’s color at 0.3 alpha |

The dark theme’s ground and border are translucent over Metabrowser’s own `--bg`, not
over github.com’s canvas, so beside github.com a dark chip’s ground looks a little
different, though every color the chip computes is github.com’s.

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

**A chip is colored on first paint once its repository’s label set is cached.** A record
or a core cached before label colors names its labels alone.
Such a record is fetched again once, but only after its page has painted it, and a core
in that shape is drawn until its record arrives.
The repository’s whole label set is cached beside its pull requests; the pull envelope
carries the set’s entry for each label its record or core names without a color, and the
chip takes its color and description from it.
A label with its own color keeps it.

The first view of such a page after an upgrade, before the set is cached, draws the
chips neutral and asks for the set at once.
The page polls fast while the set is read, and each chip takes its color when the set is
cached. A label the set does not hold, one deleted or renamed on GitHub, stays the
neutral chip, since no read of the set can color it; a later visit asks again, and the
set is read at most once in its age.

A color’s arrival moves no chip and no row, which the same Chrome check holds; it also
holds that a record of bare names, with the set cached, paints every chip as the
record’s own colors do.
`tests/dom/github-pull-labels-behavior.js` holds the ask, the fast poll, and a repaint
that changes only the chips’ colors and tooltips.

## The Pulls Tab

The list beside Files and Commits, on a GitHub repository, shows every pull request
newest first. Like the page it opens, it has almost no vocabulary of its own.
`test_the_pulls_tab_carries_the_shells_primitives` holds what follows.

A pull request is one item, its link, with one hover, one selection, and one keyboard
stop: a run and a last line.
The run is one flow: the state icon, then the title, a stack member’s place, the number,
and the author, a muted dot before each part after the title: “Fix the reader · 5/12 ·
#455 · jlevy”. The run wraps where it needs to, and every line of it starts in the text
column, past the icon, as a tree’s title wraps past its icon.
The last line is the lines the pull request changes, its
[brief change line](#brief-change-line) of its line totals alone, a total of zero left
out, “+1,234” for a pull request that only adds lines, with the registry’s chevron after
them, from the text column, and the age at the row’s end, in its freshness ink
([Ages End the Row](#ages-end-the-row)): “+1,234 −567 ›” and “3d”. Between them, in a
column of its own, an open pull request’s readiness: the verdict’s glyph in its tone,
“+1,234 −567 › ⊗ 3d”, so the glyphs down the list read as a checks column
([In the Pulls Tab and on Stacks](#in-the-pulls-tab-and-on-stacks)). The item holds the
pull request’s changed-files tree, which hangs under it, is owned by the row’s link
through `aria-owns`, whose `aria-expanded` alone says whether it is open, and starts
collapsed. The lines and the chevron after them are the toggle, the summary the chevron
expands ([Diff Summary](#diff-summary)): clicking them toggles the tree and opens no
page, and clicking anywhere else on the item, the title, the place, the number, the
author, the age, or the last line past the chevron, opens the page and expands nothing
([A Click on the Toggle’s Line Toggles](#a-click-on-the-toggles-line-toggles)). A press
on the toggle, or Space, Right, or Left on the item, keeps the row where it is, under
the pointer or the focus, even above a row a reveal placed, whose place gives way to it.
No row expands on its own: not when it opens, not when it is selected, and not on a
key’s walk, so Up, Down, J, and K walk the pull requests and each row shows its line
totals. A walk or a reveal brings the whole item into view, and the focus ring round it,
clear of the sticky filters.
An address naming a changed file opens its owner’s tree if needed
([Navigation Reveals the Item](#navigation-reveals-the-item)). Moving to another PR
closes a tree opened only for that address; trees the reader opened stay open.

The lines changed are what the pull request’s own cached list of changed files sums to,
the list its tree shows, summed as a stack’s members are, so a stack of one pull request
shows on its heading the line its row shows (`pull_change_sums.py`). The tab reads it
for the rows it draws, in one request when the browser is idle, from the cache alone
(`GET pull-files-summary`): it asks GitHub for nothing, and the lists are the ones the
tab already reads behind the reader, the changed files of the rows in view, and those of
trees the reader opens.
A row’s line is read again only when something says its list changed: the list of pull
requests names a new head commit for it, the prefetch lane reports it listed the row’s
files, or the row’s tree reads a list of another refresh
(`builtin_plugins/github/row-lines.js`). While a line is read, or for a minute at most
while the row’s files are being listed, the last line holds the shell’s pending
placeholder where the lines will be, after the quiet period; a row whose files are not
cached and not being listed shows no lines, its last line the chevron alone.
The last line is one line tall whatever it holds, so the row keeps its height as the
prefetch lane lists its files and its lines are read after all; only the chevron moves,
following the lines.
The toggle is the pointer’s alone: never focused, and hidden from assistive technology
(`aria-hidden`), since a tree’s item may own only items and groups.
Its words, hidden too, say the lines, “Changed files: 1,234 lines added, 567 deleted”,
and only “Changed files” while there are none, and the row’s link, the item’s one stop,
describes itself by them (`aria-describedby`). The link’s own name says the state and,
for an open pull request, the readiness’s label after it, then the title and the place,
and then the number, the author, and the age, in text that is out of view but read
(`rowSaid` in `pulls-panel.js`, and the run’s readiness words in `stack-member-row.js`),
since the number, the author, the age, and the readiness’s column, which show them, are
hidden.

A pull request’s title is always bold in normal text ink, wherever it appears: the
page’s heading, a Pulls row, the page’s stack menu, and a search result.
A conventional-commit prefix that starts it is regular ([Titles](#titles)). A row or
menu item is a link, so the title sets its own ink and weight, and no visited, hover,
focus, selected, or current state changes them.
A pull request’s number is bold wherever it names the pull request
([Pull Request Numbers](#pull-request-numbers)), in a row at the run’s size and in text
ink. Usernames use the same small metadata size and bold normal text ink; the repository
summary above the list is the [navigation metadata line](#navigation-metadata-line).
A row names no branches: the pull request’s page names them, head → base, as
[Merge Direction](#merge-direction) sets them, and the row’s room goes to its title.
A row’s run starts on the list’s row inset with the state icon, in the tree’s icon slot,
then the title in the text column, then, for a stack member, the stack menu’s muted dot
and its place in its stack, bold, “· 14/15”, as [Stacks](#stacks) sets the place, then
the dot and the number, “· #455”, then the dot and the author, “· jlevy”: the stack
menu’s member line’s order, the title, then the place, the number, and the author
([Authors Follow Pull Requests](#authors-follow-pull-requests)). A row not in a stack
has no place and no dot before one: the icon, the title, the number, and the author.
A dot keeps to the part before it, so a line breaks after a dot and never starts with
one; the place, the number, and the author never break, and only a word of the title
longer than the line breaks anywhere.
The run is never cut short, so it always ends with the author.
At the nav’s default width a typical title’s run takes three lines, so its row is four
with its last; a short title’s run takes two, as most do at a wider pane, and a long one
four or more. The list places each row by its measured box, so a title’s length moves no
row.
A row in no stack is flush on the list’s inset; only a stack’s members are indented,
one level in, under their stack’s row, beside its Stack Overview row, so the indent
itself says which rows are a stack’s. The changed files hang one tree level under the
state icon. The author’s name ends in an ellipsis only where the author is wider than a
line. The age never gives way: its column at the last line’s end is one width
(`--github-pulls-age-column` in the GitHub plugin’s `styles.css`), the room of the
longest compact age, “12mo”, and neither does the readiness’s column before it; where
the line has no room for the lines as well, at the narrowest panes, the lines give way
whole to an ellipsis, and the chevron, the readiness, and the age stay.
A typical row’s lines give way only at the narrowest panes, whose room the readiness’s
glyph and its gap take; `tests/dom/github-pulls-row-lines-chrome.mjs` holds the lines
whole wherever the line has their room beside the column.
The author’s avatar in a row is a tenth smaller than the shell’s `--actor-avatar-size`,
`--github-pull-row-avatar-size` in `builtin_plugins/github/styles.css`, which a stack
menu’s member and a guide’s pull request row take too, since the author is secondary to
the title it follows.
The Pulls column has no tooltips
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
Once rows are drawn, a change to them (a list’s further pages, or a refresh that changes
it) that comes `LATE_ROWS_MS` after the reader’s last press or key is offered rather
than drawn: **Show N more files** or **Show the updated list of N files**, on the tree’s
line, or floating over its top when the line is hidden, so drawn rows never move without
input. A refresh that lists no files is offered as **Show the updated list (no files)**,
and the rows drawn meanwhile keep no line saying there are none; once the reader asks
for the empty list, the tree says “No changed files.”
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

The tab also has ready, behind the reader, the comparison of each pull request it is
likely to open next, so its page draws the [Diff summary](#diff-summary) at once: the
open pull request, the two rows the pointer or focus last rested on, the open pull
request’s neighbours in its stacks, which Control-N and Control-P reach, and the rows
above and below the one that takes Tab, at most `WARM_COMPARISONS` an ask
(`createComparisonWarmer` in `builtin_plugins/github/comparison-prefetch.js`). They are
read one at a time when the browser is idle and only once no page is reading one, each a
record from the cache and a comparison from the repository store, with no GitHub request
and no rendered Markdown, at most `WARM_PER_HOUR` an hour, each counted before its
record is read. A comparison already kept or on its way is not asked for again, and no
outcome is looked up again within the record’s freshness window: a record that names no
comparison, a refusal, and an answer too large to keep included.
The tab warms only while it is shown, visible, and online; hidden, parked, or offline,
it empties the queue.
A warm’s record read is not a view, so it adds nothing to the records the server’s
prefetch lane refreshes after a scan.
Its cost is beside the constants.
`tests/dom/github-pulls-files-prefetch-behavior.js` holds which pull requests the tab
names, and `tests/dom/github-pull-prefetch-session.js` what the warmer reads.

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
`builtin_plugins/github/pull-state.js`, so a row and its page cannot disagree: the ref
selector’s rows, in the shell, draw the same icon through the plugin’s exported
`pullStateIcon` ([The Ref Selector](#the-ref-selector)).
`test_pull_state_colors_keep_their_hue_and_read_on_both_grounds` holds the hue and a
4.5:1 contrast on both grounds, because a badge sets its word in that color.

### A Pull Request’s Readiness

An open pull request’s readiness says whether it can merge and, when it cannot, what
stands in its way. The server decides it, its verdict, its tone, and its label
(`readiness` in `builtin_plugins/github/pull_readiness.py`), so every surface that shows
it and `metab` say the same.
A closed or merged pull request has no readiness, since its state is the answer, and
draws no mark.

The browser draws it with one vocabulary, `VERDICT_GLYPHS` in
`builtin_plugins/github/pull-readiness.js`, a glyph for each verdict and nothing more:

| Verdict | Glyph |
| --- | --- |
| `ready` | Lucide `circle-check` |
| `ready_for_review` | Lucide `circle-check` |
| `conflicts` | Lucide `triangle-alert` |
| `checks_failing` | Lucide `circle-x` |
| `changes_requested` | Lucide `file-diff` |
| `blocked` | Lucide `ban` |
| `queue_failing` | Lucide `list-ordered` |
| `queued` | Lucide `list-ordered` |
| `checks_pending` | Lucide `clock` |
| `review_required` | Lucide `eye` |
| `behind` | Lucide `arrow-up-to-line` |
| `checking` | Lucide `circle-dashed` |

Two verdicts share a glyph only where they mean one thing, and the label says which:
`circle-check` that nothing blocks the pull request, Ready to merge or, on a draft,
Ready for review, and `list-ordered` that it is in the merge queue
([Icon Catalog](design-system-icons.md#git-and-github-objects)). The label and the tone
come with each readiness, so the browser holds no label of its own and never infers a
color from a verdict.
`tests/test_github_pull_readiness_js.py` holds the vocabulary’s verdicts to the server’s
`Verdict`, and `test_a_plugins_readiness_verdicts_draw_the_plugins_glyphs` holds this
table to the vocabulary.

The module draws it in two forms:

- **The glyph**, `readinessIcon`, at the app’s one glyph size.
  It is named by default, by the label, as a state icon is; beside text that says the
  label it is hidden (`named: false`), as it is on a row, whose words say the label
  after the state ([In the Pulls Tab and on Stacks](#in-the-pulls-tab-and-on-stacks)).
- **The badge**, `readinessBadge`: the label in the outlined form of the state’s badge,
  `file-header-badge github-pull-badge`, so a state and a readiness side by side read as
  one vocabulary.

Each carries `data-verdict`, for what reads the page, and `data-tone`, which alone sets
its color.

The tone is the worst status among the readiness’s requirements (`STATUS_TONES` in
`pull_readiness.py`), and each tone takes one ink, the same for the glyph and the badge:

| Tone | Ink |
| --- | --- |
| `success` | `--status-success-text`, the shell’s |
| `attention` | `--github-pull-attention`, the plugin’s |
| `danger` | `--status-error-text`, the shell’s |

- **Success and danger** are the shell’s status inks, which carry GitHub’s green and
  red, so a readiness and a check read in one color.
  The lifecycle’s `--github-pull-open` and `--github-pull-closed` stay the lifecycle’s,
  since a color has one meaning.
- **Attention** has a token of its own.
  The shell’s only warning ink, `--status-warning-text`, is orange and reserved for a
  degraded or partial result
  ([Empty and Failed Loads](#empty-and-failed-loads-in-the-navigation-column)), and
  GitHub shows what waits, a pending check or a queued pull request, in yellow.
  `--github-pull-attention` is Primer’s `fgColor-attention` in light, with its hue held
  in dark; its comment in the plugin’s `styles.css` says where each value comes from.
- **No verdict is neutral**: GitHub shows every unknown in yellow, so `checking` is
  attention.

`test_a_readinesss_color_is_its_tones_alone_and_reads_where_it_is_drawn` holds that no
rule colors a readiness by its verdict, that the stylesheet’s inks are this table’s,
that attention’s hue is outside the warning ink’s family, and that each ink reads at
4.5:1 on `--bg` and `--sidebar-bg` in both themes.
`test_pull_state_colors_keep_their_hue_and_read_on_both_grounds` holds the attention
token’s hue across the themes.

Color is never the only signal: the glyph says what stands in the way, and the label,
the badge’s text or the glyph’s accessible name, says the verdict.

#### On the Pull Request Page

The page says an open pull request’s readiness twice, from the envelope’s `readiness`
(`readinessModel` in `builtin_plugins/github/pull-page.js`), and draws nothing for a
closed or merged one, or before a record or core is shown.
The server judged the verdict with the pull request in its record’s or core’s state, so
the page draws it only beside that state (`readinessForState` in `pull-readiness.js`,
which every surface that draws a verdict goes through): where it shows the list of pull
requests’ state instead, fresher than its record’s, as once the list has learned of a
merge or a draft first, it draws no badge and no Merge status section until a read
judges the state it shows.

- **The header’s badge** follows the state’s badge in the row of ages: “[Open]
  [Merge conflicts] Opened 3 days ago”.
  It is the verdict’s badge, a link to the Checks tab, which the Merge status section
  opens, and so a [clickable chip](#clickable-and-static-chips): the pointer, the chip’s
  hover ground, and no underline.
  Its accessible name adds auto-merge’s sentence while auto-merge is on, “Checks
  pending. Auto-merge enabled (squash).”, and its tooltip, also its accessible
  description, lists the requirements that are not met, which the badge abbreviates.
  Its slot is a grid as wide as the widest label the server gives a verdict, by a hidden
  sizer of each (`SLOT_LABELS` and `readinessSizers` in `pull-readiness.js`), as the
  state’s slot is the widest state’s, so a verdict that changes as checks finish moves
  nothing in the row. The sizers are the module’s one copy of the server’s labels, and
  `tests/test_github_pull_readiness_js.py` holds it to `LABELS` in `pull_readiness.py`;
  the badge always says the label its readiness came with.
  Its comment in the plugin’s `styles.css` records what the slot measured in Chrome and
  that Browse code stays whole at the row’s limits.
- **In a narrow row** the badge gives way to the verdict’s glyph alone (`readinessIcon`,
  in the tone’s ink), and the slot is the glyph’s width.
  The link, its accessible name, and its tooltip are the badge’s, and the glyph is
  hidden from assistive technology, so the two forms say the same.
  A container query on the row of ages (`@container github-pull-opened` in the plugin’s
  `styles.css`) draws the full badge only where it leaves the ages what they had at the
  row’s 420 px limit before the badge came; the comment beside the rule records the
  bound and its measurement.
  `tests/dom/github-pull-header-chrome.mjs` (its `readiness` part) holds each form to
  its side of the bound, the ages at 420 px to what they had less the glyph and its gap,
  and every verdict’s glyph and label in either form to a row that does not move.
- **The Merge status section** opens the Checks tab: the verdict’s badge and the
  sentence of the requirement that heads it, the first at the worst status, then a row
  for each requirement and one for auto-merge while it is on.
  A row is its status’s badge, the server’s word for the status with a capital, in the
  outlined form of a check’s, in the ink of the tone its status gives a verdict
  (`STATUS_TONES` in `pull-readiness.js`, held to the server’s), then the server’s
  sentence and its link.
  The badges sit in a column as wide as the widest, so the sentences line up.
  A met requirement links nowhere.
  Checks links to the first failing or running check in the list below, by its place in
  the list, since two checks can share a name, which it brings into view and focuses;
  Reviews that asked for changes to the Conversation tab when it shows a review that
  did; and every other requirement, and Checks with no list yet, to the page on GitHub
  the server names, as a check’s action does.

`tests/dom/github-pull-page-mount-behavior.js` builds both browserlessly on the
production page, and `tests/golden/cli-ui-github-pull-readiness.tryscript.md` pins what
each says for five answers GitHub could give and beside each state the list could say;
`tests/dom/github-pull-header-chrome.mjs` holds the slot’s width in Chrome at every
header width.

#### In the Pulls Tab and on Stacks

A row that names an open pull request shows its readiness as its glyph, as a row shows
its state: the glyph in the list, the word on the page.
`row-readiness.js` reads it, from the server’s verdict on each pull request the row
draws (`GET pull-statuses`), and `stackMemberRow` in `stack-member-row.js` draws it, so
a Pulls row and a stack’s member draw one thing one way.

- **A Pulls row** has a column of its own on its last line, between the toggle and the
  age, as wide as the glyph on every row, flush or a level in, so the glyphs down the
  list start at one edge and a glyph that arrives moves nothing.
  A closed or merged row keeps the column empty, and so does an open one the server has
  no status of for the head the list names: not read yet, not scanned, or pushed since.
  Where the list is wide enough the label follows the glyph, in the text’s ink: a
  container query on the list (`@container github-pulls` in the plugin’s `styles.css`)
  widens the column to the widest label exactly where a stack’s member, a level in,
  keeps the room its lines need beside it; the comment beside the rule records the bound
  and its measurement.
  The tone is the glyph’s alone, so a hundred rows are not a hundred colored words, and
  the label reads at the text’s contrast on the open row’s tint, where the success ink
  would not.
- **A stack’s member**, in the stack menu and on the stack’s page, ends its line with
  the glyph, after the author, in a cell as wide as the glyph, empty for a member with
  no readiness, so the members’ places, numbers, and authors end at one edge.
  The page’s own member draws the readiness its header shows, by the header’s rule;
  every other member the server’s, on the head the server judged, the catalog’s,
  whatever head the member’s record has.
  A guide’s pull request row shows none, and has no cell.

The glyph and the label are hidden from assistive technology on both: the row says the
label out of view after the state icon, so its name reads “Open Checks pending Fix the
reader …”, the readiness after the state, as the state icon says the state.
The Pulls column has no tooltips, and nor does the glyph.

A row is read in one request for the rows a surface draws, when the browser is idle and
behind any comparison a page is reading, from the cache alone, as a row’s change line
is. Its answer is kept for the document, the server’s alone, with the head and the state
it judged and nothing of the surface that asked, so a remounted Pulls tab and a stack
menu draw what the list read in their first paint, every surface that draws a pull
request holds one answer of it, and one read settles it for all.
A verdict is drawn only beside the head and the state it judged (`readinessForState` in
`pull-readiness.js`, the page’s rule too), so a pushed row, or one marked a draft or
ready, draws none until the server judges it anew.
It is read again when the list’s ask says the scan of every open pull request’s status
started, when the ask or a read says a scan ended later than the document had heard of,
however it started (`status_scan_at`), when a pull request page reads a newer status of
its own, when the head or the state a surface draws it with moves, and, on a stack’s
member rows, which no ask reaches, once a minute at most as the menu opens or the
stack’s page polls (`ROW_READINESS_RETRY_MS`), and on the stack’s page as a member’s
record moves to a new head; at most once for each, whichever surface reads it.
`tests/golden/cli-ui-github-pulls-readiness.tryscript.md` pins what each row and member
draws and says, from the server’s recorded answers, and
`tests/dom/github-pulls-readiness-chrome.mjs` holds the column, its label’s bound, and
the inks in Chrome.

### Pull Request Numbers

A pull request’s number, “#455”, is bold wherever it names the pull request, at the
weight of a stack’s position, “1/6”, so the two identifiers read alike.
One token sets it, `--pull-number-weight` in the shell’s stylesheet, and every surface
that shows a number takes it:

| Surface | Class |
| --- | --- |
| The pull request page’s title | `.github-pull-number`, after the title |
| A Pulls row | `.github-pulls-number`, in its run after the title and the place, after a muted dot |
| A stack menu’s member | `.github-pull-stack-member-number`, after its title, its place, and a muted dot, before its author, in the Pulls row’s ink |
| A Quick Search result | `.search-palette-pull-number` |
| The ref selector, on a pull request’s head | `.source-ref-selector-pull-number`, after “Pull request:” |
| The ref selector, on a branch’s row | `.source-ref-selector-pull-number`, after the state icon |
| A guide’s pull request row | `.github-pull-stack-member-number`, as a stack menu’s member has it |
| A guide’s file of another pull request | `.github-pull-guide-reference-pull`, before the path |

The GitHub plugin’s three are one rule.
A number in prose, a commit subject, or a tooltip is text, and keeps its line’s weight.
A count’s numeral, such as a heading’s tally, is not a pull request’s number and takes
its own token, `--count-numeral-weight` ([Heading Tallies](#heading-tallies)). A stack’s
own number, in “Stack #286”, is part of the stack’s label, in the label register
([Stacks](#stacks)). `test_the_pulls_tab_carries_the_shells_primitives` holds the rules
to the token, and `tests/dom/github-pulls-stacks-chrome.mjs` and
`tests/dom/github-pull-header-chrome.mjs` read each surface’s computed weight in Chrome.

### One Order for a Pull Request’s Fields

Wherever a row names a pull request by more than its title, its fields keep one order:
the state icon, the title, its place in its stack, its number, and its author, “title ·
14/15 · #455 · jlevy”.
A reader who learns the order once reads every such row the same way.
A surface that leaves a field out keeps the order of the rest: a pull request in no
stack reads “title · #455 · jlevy”, and a row with no room for an author ends with its
number.

One builder draws the fields on every row of the GitHub plugin that shows them,
`stackMemberRow` in `stack-member-row.js`: a Pulls row’s run (`PULLS_RUN`), and a
stack’s member in the stack menu and on the stack’s own page and a guide’s pull request
row (`MEMBER_LINE`). The order, and the muted dots that part the fields, are its; a
surface chooses only its layout, a run that wraps in the text column or one line whose
title is cut short before the rest.
A field that is absent draws neither itself nor the dot before it, in either layout and
whether the row was drawn without it or lost it later, so no row shows a stray dot.

The shell cannot import the GitHub plugin, so its own rows keep the order in their own
code: Quick Search’s pull request results, “title #N · Merged”, and a ref selector row’s
pull request line, its state icon, title, and number.
An accessible name or a tooltip says the fields in the order the row shows them, “title,
pull request #455”, never the number first.

### Authors Follow Pull Requests

Wherever a row names a pull request by its number or its stack place, its author
follows, after a muted dot, in the shell’s [actor identity](#actor-identity): the bold
name, and the avatar at `--github-pull-row-avatar-size`, where it has one.
A reader tells whose work a number is without opening it.
The name is cut short only past its share of the line, and a screen reader hears the
author after the number.

| Surface | The author |
| --- | --- |
| A Pulls row | `.github-pulls-by`, ending the run after the number, cut short only where it is wider than a line |
| A stack menu’s member | `.github-pull-stack-member-by`, ending the line after the number, at most a third of it |
| A member on a stack’s page | The stack menu’s member row itself, drawn by its builder, `stackMemberRow` |
| A guide’s pull request row | `.github-pull-stack-member-by`, as a stack menu’s member has it |
| The pull request page’s title | The header’s sentence, “jlevy wants to merge 3 commits”, which names the merger once the pull request is merged, as github.com’s does |

Two surfaces show no author:

- **The stack button**, “⧉3/4”, at the end of the header’s row of ages, has no room for
  one. An author there, a dot, an avatar, and a short login, is 58 px wide, 64 px with
  its gap. Measured in Chrome on 2026-11-25, it took 64 px of the 89 px a 360 px pane’s
  row left its ages, leaving 25, and all of a merged pull request’s; at 560 px it cut a
  closed pull request’s ages from 284 px to 232. Its pull request is the page’s own,
  whose header names its author already.
- **Plain text** cannot draw an identity: a tooltip, an accessible name, a message such
  as “#455 is not in this list.”, or a sentence that links “Pull request #12”. A row’s
  accessible name says its author in words where the row shows one (`rowSaid` in
  `pulls-panel.js`).

A stack’s own number, in “Stack #286”, names the stack, not a pull request, and has no
author. `tests/dom/github-pulls-row-lines-chrome.mjs` holds a Pulls row’s author,
`tests/dom/github-pulls-stacks-chrome.mjs` a stack menu member’s, its third, and its
baseline, and `tests/dom/github-guided-review-mount-behavior.js` and
`tests/dom/github-guided-review-kinds-chrome.mjs` a guide row’s.

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
- It counts only up to `TITLE_PREFIX_MAX_CHARS` in `static/formatters.js`, colon
  included, counted in code points, set from the prefixes of real commit subjects as
  `tests/dom/title-prefix-session.js` records: `feat(view-on-github):` counts, and a
  parenthetical sentence such as
  `note(this is how the cache and the scroller keep a row):` is part of the title.
- Whitespace and more of the title follow the colon.
  `fix:keep` and a title that ends at its colon have no prefix.

A merge commit, a `Revert "…"` title, and every title that does not match have no
prefix: the same element holds the same text, all of it at the title’s own weight.

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
| A branch’s pull request in the ref selector | `.source-ref-selector-pull-title` | Bold |
| A Commits tab row | `.git-graph-subject` | Bold, as every title is; the row keeps its 22 px, and a long subject is cut short a little sooner |
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
| Row | The item, `.github-pulls-entry`, around its link, the run and the last line: the link’s `min-height: --ui-row-height`; one `--hover-bg` under it all, the -2px focus ring round it, and `--highlight-bg` when current, with the 2px `--highlight-bar` down the link’s edge, as on a Files row (`.tree-item`) | [One Row Contract](#one-chevron-one-row-contract) |
| State icon | The tree’s icon slot, `--tree-icon-slot`, around `--icon-glyph`, on the row’s inset, in the run’s start padding, centered on its first line, so every line of the run starts in the text column past it | [One Glyph Size](#one-glyph-size) |
| Readiness | The row’s last line’s middle column, `.github-pulls-readiness` in `.github-pulls-tail`, between the toggle and the age: the verdict’s glyph (`readinessIcon`) in its tone, and, where the list is at least the container query’s bound, its label after it in text ink; one width on every row, empty on a closed or merged row and one with no status, and hidden from assistive technology, its words after the state icon in the run | [In the Pulls Tab and on Stacks](#in-the-pulls-tab-and-on-stacks) |
| Lines and chevron | The row’s last line, `.github-pulls-change` in `.github-pulls-tail`, from the text column, before the age, and one line tall whatever it holds: the [brief change line](#brief-change-line) of the line totals alone, or the pending placeholder (`.tally-pending` in `.mb-delayed-loading`) while it is read, then the registry’s chevron, a space’s width on; with no lines, the chevron alone; no ground or stop of its own, and hidden from assistive technology, its words describing the link: under the pointer its chevron stands on a `--border` plate in `--text` ink, the inner target’s hover inside the item’s | The toggle, the summary the chevron expands, so a click on it toggles the changed files, and a click elsewhere on the item opens it ([A Click on the Toggle’s Line Toggles](#a-click-on-the-toggles-line-toggles)); a diff summary’s toggle ends with its chevron ([Diff Summary](#diff-summary)) |
| Title | `--nav-font-size`, `--weight-bold` in `--text`, set on the title itself; the run’s first part, after the state icon, wrapping in the text column and never cut short (`.github-pulls-heading`) | It is the row’s identity, and a pull request’s title is bold wherever it appears, with a conventional-commit prefix regular ([Titles](#titles)) |
| Updated time | `metabrowser.ageLabel`, in its freshness ink, at the row’s end on its last line, in a column of one width, `--github-pulls-age-column`, after the lines and the chevron (`.github-pulls-age` in `.github-pulls-tail`); the page gives the exact time | [Ages End the Row](#ages-end-the-row); [Age](#age), with no tooltip ([Tooltips Add Information](#tooltips-add-information)) |
| PR number | `--nav-font-size`, text ink, bold (`--pull-number-weight`), in the run after the title and the place, after a muted dot, never breaking | Shares the title’s primary navigation size, and names the pull request ([Pull Request Numbers](#pull-request-numbers)) |
| Username | `--nav-font-size`; `.actor-name`, in the run after the number and a muted dot, ending it, never breaking. The repository summary above the list is the [navigation metadata line](#navigation-metadata-line), at `--nav-font-size` too | Secondary metadata reads at the size of its line ([Type Scale](#type-scale)); usernames remain bold in normal text ink, and a row’s username ellipsizes only where it is wider than a line ([Authors Follow Pull Requests](#authors-follow-pull-requests)) |
| Stack place | `.github-pulls-place`, after the title and before the number, in the run’s size: a muted dot, `.github-pull-stack-dot`, in `--muted` at `--micro-font-size`, then the position bold in text ink, as a stack menu’s member line has them, “title · 14/15 · #N”, with what it shows set in [Stacks](#stacks); a row in no stack has neither | A passive part of the row’s link, from the shared optional snapshot; the stack’s Stack Overview row above it has the icon |
| Stack group | A row of the tree: the chevron, then “Stack #N” in the label register (`.group-heading.github-pull-stack-label`), with no icon, the stack’s size as a count summary, “· 4 pulls” ([Heading Tallies](#heading-tallies)), and its age at the row’s end; its Stack Overview row and its pull requests one icon slot and gap in, that row’s Layers glyph and each state icon under the label’s start, and each title under “Stack Overview” | [Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab) |
| Open, Closed, All | `metabrowser.filterControls.groupHtml`, joined and exclusive, the tab’s toolbar in the navigation’s toolbar slot; Open is the default | Small, muted tallies show each filter’s exact catalog total. Zero is visible and unknown is distinct. See [Choosing Among Values](#choosing-among-values). |
| Count | The first line of the [navigation metadata line](#navigation-metadata-line). Open and All read “31 pull requests · 3 open,” and Closed reads “31 pull requests · 28 closed.” Both numbers are bold, the words are regular, and the dot is muted ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)). The total ellipsizes before the state tally, and the line stays one line tall | The total counts the repository, and the tally counts the selected state. Known counts stay while a new filter loads. A missing state count leaves just the total, and an unknown total reserves the line. |
| Refresh | The navigation’s Refresh, at the top of the navigation pane, just before the Metabrowser menu’s gear, on every page and under every tab, from the first paint, so the header never moves | With Pulls in front it refreshes the list and the pull request page beside it first, then the rest of the page. The tooltip gives the time and duration of the last completed list refresh. |
| Connection | The second, muted line of the navigation metadata line, one live status: the shared small gray spinner and “Fetching pull requests…” while no rows are shown, and actionable copy when a load is incomplete or fails, which wraps only when it is longer than the pane | Cached rows stay visible and still. See [Refreshing Content](#refreshing-content). |
| Progress below the rows | The navigation’s scan indicator, `.index-progress-spinner` and `.index-progress-text`, in `.github-pulls-progress` with `.mb-delayed-loading`: “~N pull requests fetched” while GitHub’s pages for the filter arrive, or “Fetching pull requests…” while a page is read | One progress language for a crawl, after the quiet period, and only below rows, never over them. It leaves with the filter’s last row. |
| Refresh | `.icon-btn`, the gear’s primitive, drawn by the server with its glyph, a circular arrow, with a spinner in its place after a press ([Every Icon-Only Control Is the Same Control](#every-icon-only-control-is-the-same-control)) | For the list and the pull request page, Refresh checks GitHub for changes. See [Refresh, Retry, and Reload Page](#refresh-retry-and-reload-page). |

A pull request is a run and a last line, one item, and two targets, because a pane is
narrower than its parts.
Its run is one flow: the state icon, then the title, a stack member’s place, the number,
and the author, a dot before each part after the title, every line of it in the text
column, past the icon, and never cut short, so it always ends with the author.
The run’s start padding is the text column, and the icon is out of its flow, so no
line’s start rests on `text-indent`, which WebKit drops on a `-webkit-box`: in the app’s
web view a place or a title that a first line’s indent made room for was drawn over the
state icon, and the run is no `-webkit-box`. The last line is the brief change line with
the chevron after it, from the text column, and the age at the row’s end, at one size
and centered on the line ([Rows and Disclosures](#rows-and-disclosures)). A plain click
on the lines or the chevron opens and closes the files and opens no page, a modified or
middle click on them toggles nothing and opens no tab, and a click anywhere else on the
item opens the pull request.
The keys see the item as one row of the list.
The title is the link’s first shown text, so the row’s accessible name gives the state,
from the state icon’s label, and the readiness’s label after it, out of view, then the
title and the place, before the number, the author, and the age in words.
It is one link, so a new tab and a copied address are the browser’s own, and all of its
text is text: GitHub’s users write it, and none of it reaches markup or a style.
A closed row is one height whatever its lines hold, so nothing moves when they arrive:
`ROW_ESTIMATE_PX` with a run of three lines, and a line shorter or taller for each line
fewer or more.
The list places each row by its measured height (`createPullsWindow`), and
a row not yet drawn at `ROW_ESTIMATE_PX` in `builtin_plugins/github/pulls-panel.js`, a
row with a run of three lines, which `tests/dom/github-pulls-row-lines-chrome.mjs` holds
the measured rows to and holds within half a line of this repository’s own rows at the
default pane.

New pull requests use the [shared arrival highlight](#live-row-arrivals), and the rows’
keys are under [Navigational Row Collections](#navigational-row-collections).

## The Agents Views

The agents plugin’s home, session list, and Session view (`builtin_plugins/agents/`) are
built from the shell’s parts, and add only what a session needs.
The page’s title is `.page-heading`, a section’s title is `.section-heading` over its
rule, a statistic’s label and a table’s headers are labels, and a status is the shell’s
badge. Color is an event’s kind or a tool’s family, nothing else: an agent is a label,
bold, never a color.

The overview shows [inline progress](#progress-spinners-stay-neutral) as it reads
session history to fill in details such as turn and event counts.
The checked count includes sessions whose details could not be read.

### Session Rows

The home’s Running now and Recent sessions are one list of two-line rows
(`sessionRowsHtml` in `session-rows.js`), in the manner of
[The Pulls Tab](#the-pulls-tab)’s rows.
The first line is the agent, bold, the session’s title as a link, and the age at the
line’s end, muted, in tabular numerals, never wrapping.
The second line is muted: a status badge where the list has one, the project, then the
model, parted by the design’s separator
([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)). The title
and the project are cut short with an ellipsis, the project first, and the model keeps
its words unless it alone runs past its cap (`.agents-row-model`’s `max-inline-size` in
`agents-views.css`), so a long path never pushes the age onto a line of its own, and a
row is two lines whatever it holds.
A row whose second line has nothing to say keeps the line’s height, so the rows of a
list stand at one height.
`tests/dom/agents-views-chrome.mjs` holds that the age stays at the end of the first
line and the row keeps its height under a long title and a long path.

An agent’s line on the home, “Claude Code · 2,202 sessions, 6.2 GB”, is a count summary:
the dot is the design’s separator, the figures are bold, and the served folder’s own
home names no path, so none is shown.

### Session Links

A session’s title is a link to its file, in every view that draws one, with the
treatment of the [Link row](#chrome): `--link` at rest and once visited, no underline at
rest, an underline on hover, and the focus ring with the outset offset
(`a.agents-session-link`). A session with no file is plain muted text with the same
class on a `<span>`. `tests/dom/agents-views-chrome.mjs` reads every anchor the three
views render, in both themes.

### The Session List’s Table

Its columns (`COLUMNS` in `session-rows.js`) are wider than a normal pane, so the table
scrolls inside its own wrap, as a wide table does elsewhere
([Reading Width](#reading-width)), and the wrap is a keyboard stop (`tabindex="0"`, a
region named “Sessions”) with the one focus ring, so a reader without a pointer reaches
every column too.
The cells that can run long, the title, the project, and the model, are
capped and cut with an ellipsis, the whole value in a tooltip, so a long model list
never pushes the columns after it out of reach.

## Stacks

**A native GitHub stack is named, placed, and listed one way wherever it appears:** the
pull request page’s stack button and menu, a Pulls row’s place, the Pulls tab’s stack
groups, and the stack’s own page ([The Stack Page](#the-stack-page)). The words come
from one place, `builtin_plugins/github/pull-stacks.js` (`stackLabel`, `STACK_OVERVIEW`,
`stackPosition`, `stackPositionHint`, `stackCaption` for a Pulls row’s place,
`stackGroupHint`, `stackPullsCount`, and `stackUpdatedAt` for a stack group’s row,
`wholeStackHint` for its Stack Overview row, `stackMenuOrder`, and `stackEntries` for
where the Stack Overview row goes among the members), and the look from one set of
classes in the GitHub plugin’s stylesheet on the shell’s tokens, so no surface keeps a
copy of either.

| Part | Primitive | Where |
| --- | --- | --- |
| Label, “Stack #N” | `.group-heading.github-pull-stack-label`: the shell’s [group heading](#groups-in-a-menu), so the label register (`--label-color`, `--label-font-size`, `--label-font-weight`, `--label-letter-spacing`, `--label-text-transform`): gray, all caps, and tracked | The stack menu’s heading; a stack group’s row in the Pulls tab |
| Position, “2/4” | `.github-pull-stack-position`, tabular, at the pull request number’s weight (`--pull-number-weight`); on the stack button, after the Layers icon, `.github-pull-stack-icon`, at `--icon-glyph`, and after its stack’s number when the pull request is in another stack too, “⧉300 2/2” | The stack button on the page, at the right end of the row of ages; a Pulls row’s place, after its title and a muted dot, before the number, as a stack menu’s member line has it, with no icon |
| Member row | One line: the pull request’s state icon, `.github-pull-state-icon`; its title, bold in normal text ink, cut short before its place; and at the line’s end, together, its position, bold, a muted dot, `.github-pull-stack-dot`, its number, `.github-pull-stack-member-number`, and, where it is known, another dot and its author, `.github-pull-stack-member-by`, the shell’s actor identity, “14/15 · #N · jlevy”, a Pulls row’s order, the title, the place, the number, and the author; and last, for an open pull request, its readiness’s glyph in a cell as wide as the glyph, `.github-pull-stack-member-readiness`, empty for one with none ([In the Pulls Tab and on Stacks](#in-the-pulls-tab-and-on-stacks)). On the current pull request, `aria-current="page"` and the Pulls list’s current-row mark, `--highlight-bg` and a 2px `--highlight-bar` at its left edge | The stack menu; the stack’s page, in a card |
| Stack Overview row | The stack’s Layers glyph, `.github-pull-stack-icon`, in normal text ink, in the state icon’s slot, and “Stack Overview” where a member’s title starts, in a member row’s gap. In the Pulls tab, `.github-pulls-whole-row`, after its words and a muted dot is the stack’s [brief change line](#brief-change-line) and then the registry’s chevron, the two the toggle of the stack’s changed files (`.github-pulls-whole-change`), as a pull request’s row’s last line ends | The first of a stack’s rows, above its members, in the stack menu and under an open stack in the Pulls tab; each opens the stack’s page |
| Stack group row | The registry’s chevron and the label, with no icon, the Stack Overview row under it being the stack’s own; then, after a muted dot, the stack’s size, a count summary with its number bold, “· 4 pulls” ([Heading Tallies](#heading-tallies)); and at the row’s end the age of the stack’s newest update ([Ages End the Row](#ages-end-the-row)) | The Pulls tab |

- **Label.** A stack is “Stack #N”, with GitHub’s number for it, in the label register:
  the register the menu’s heading has, so the menu’s heading and a stack group’s row are
  one class, and nothing in the GitHub plugin restyles its type or ink.
  In a menu it starts on the menu’s row inset, as every group heading does; in the Pulls
  list a stack’s row starts on the list’s row inset, where every first-level row starts,
  and with no icon after its chevron its label starts where its pull requests’ state
  icons do, one tree level in.
- **Position.** A member’s place is its position counted from the stack’s base, as
  GitHub numbers it, over the stack’s size: “2/4”. A pull request in more than one stack
  shows each position, separated by a middle dot, and names every stack but its own by
  the Layers glyph and its number before its position, `.github-pull-stack-other` at the
  text’s size: “3/4 · ⧉300 2/2”, where ⧉ is the glyph.
  A number alone, “#300”, would read as the pull request number on the same row.
  Its own stack is its only stack, the one a group places it under, or else the first
  GitHub lists. On a guide’s pull request row the stack that goes without saying is the
  guide’s own, the one its pull request is in or the one it was written for, so the row
  names any other, since nothing around it says which stack a bare position counts in.
  On the page a pull request in more than one stack has a stack button for each, and
  each names its stack, “⧉286 4/4” and “⧉300 2/2”, since no button is the page’s own
  stack; two bare positions told the stacks apart only by their tips
  (`namedStackPosition` in `pull-stacks.js`). In one stack the button is the glyph and
  the bare position, “⧉3/4”.
- **Ink.** The position is in normal text ink wherever it appears: in a Pulls row’s
  place, the ink of the title it comes before, with only its dot muted, on the stack
  button, and in a member row.
  A member row is a link, so its position and title each set their own ink, and no link,
  visited, hover, focus, or current state changes them; a part that set none would take
  the link’s blue.
- **Member row.** A stack’s member reads in one order wherever it appears: its title,
  its place, its number, and its author, “Fix the reader 14/15 · #455 · jlevy”.
  A Pulls row’s run has all four, its age at the row’s end on the line below
  ([The Pulls Tab](#the-pulls-tab)); the stack menu’s member row has all four on one
  line, and so does a guide’s pull request row, drawn by the same builder
  (`stackMemberRow` in `stack-member-row.js`), whose place says its stack in its tip and
  its accessible name, and which, for a pull request in no stack, has no place and keeps
  the rest in order; and the stack button shows the place alone, “⧉14/15”, with no
  author, since the row it ends has no room for one
  ([Authors Follow Pull Requests](#authors-follow-pull-requests)). Every member in the
  menu has one layout, one line tall, so the members line up and every row of the menu
  is as tall as the others: the state icon in the tree’s icon slot, a tree row’s gap,
  then the title, and at the line’s end, together, the position, the dot, the pull
  request’s number, and another dot and its author, “14/15 · #455 · jlevy”, the menu
  with them right-aligned.
  The number follows the place, “#455” as a Pulls row shows it, in the text’s ink at the
  number’s weight ([Pull Request Numbers](#pull-request-numbers)), so a reader tells two
  members of one title apart, and the author ends the line, as a Pulls row draws it, the
  shell’s [actor identity](#actor-identity) with its avatar where it has one and no box
  where it has none; a screen reader hears the number and the author last in the
  member’s name. The place and the number never give way, and the author takes at most a
  third of the line, its name cut short past that; the title gives way first, cut short
  before the place, and the row’s tip holds the whole of it, which the shell shows only
  while the title is cut short ([Tooltips Add Information](#tooltips-add-information)).
  The icon is the state the page shows for its own pull request, and for each other
  member the state the Pulls list last read for it (`stackMemberState` in
  `pull-page.js`); a member the list has not reached keeps the icon’s slot empty.
  The author is the page’s own for its pull request, and for each other member the one
  the stacks route reads with its title from the repository’s cached list of pull
  requests (`authors` and `avatars` beside `titles`, `pull_stacks_route.py`;
  `stackMemberAuthor`), so a member the list does not hold has no author and no dot
  before one.
- **Stack Overview.** The menu’s first row opens the stack’s page.
  It is in a member row’s grid: the stack’s Layers glyph, in normal text ink, the ink of
  the stack page’s title glyph, in the state icon’s slot, the glyph the stack button
  shows, and “Stack Overview” at a member row’s gap from it, so its words start where
  every member’s title does.
  It had a menu item’s gap, 2px wider than a member row’s, and an empty slot, so its
  words started past the titles.
  A list’s answer forgets what was noted of a pull request it no longer holds when the
  list holds the noted state and it is not a merge, so a member the Open list left out
  once it merged or closed is not drawn open; and a page notes its own record’s state
  back over an older list’s (`noteListed` and `noteRecord` in `pull-state.js`). The menu
  reads the states again each time it opens and each time the page repaints.
  The row this replaced wrapped a long title onto lines of its own and marked the
  current member with a check before its position and its number after its title.
- **Order.** A stack’s rows are its Stack Overview row, then its members, top of the
  stack first, the order of `stackEntries` and `stackMenuOrder`: the menu’s rows and a
  stack group’s rows in the Pulls tab are one order, so the Stack Overview row is first
  in both, and one of the stack’s rows in both: its members are beside it, never under
  it.
- **Links, hover, and focus.** A member row is a link to its pull request and a menu
  item, with the menu’s hover.
  The current member is marked as the Pulls list marks its current row, `--highlight-bg`
  and the 2px `--highlight-bar`, drawn inset since a menu row has no border, and keeps
  that mark hovered or focused; focus on any member shows as the header’s link ring.
  The menu’s keys are [Keys in a Menu](#keys-in-a-menu)’s: every way it opens, a press,
  Enter, Space, `↓`, or `↑`, puts focus on the current member, and Escape gives it back
  to the button. A stack group’s row is a row of the Pulls tree, not a link, since a
  press opens and closes it: it hovers, takes the focus ring, and takes the pointer as a
  pull request’s row does, and a press opens or closes it as a folder’s does.
- **Tips.** The position’s tip names the stack and the place: “Stack #286, position 3 of
  4”, every stack of a pull request in two, joined by semicolons.
  The stack button carries it, as its glyph and position do not name the stack, and its
  accessible name is “Navigate” before it.
  In the Pulls column, which has none
  ([Tooltips Add Information](#tooltips-add-information)), the glyph in a row’s place
  has no words of its own, and the place’s accessible name names each stack, “Stack
  #300, position 2 of 2”. A stack group’s row’s accessible name says its size, the count
  its heading shows (`stackPullsCount` writes both), how many the list holds when that
  is fewer, how many of those sit under an earlier stack, and its age as drawn: “Stack
  #286, 4 pull requests, 3 in this list, 1 under Stack #290 · 2h”. Its Stack Overview
  row’s name says the stack’s change line in words once it is shown, as the Diff
  summary’s does after its file count: “Stack Overview, Stack #286: 1,234 lines added,
  567 deleted”.

### The Stack Page

**A native stack’s page, `/stack/<n>`, is a pull request’s page for the whole stack:**
the same header, tab bar, and body, made of the same parts in the same order, each part
saying of the whole stack what a pull request’s says of one pull request, with what a
stack does not have left out and nothing added but its members.
It shows the stack’s combined comparison, from the bottom member’s merge base to the top
member’s head (`GET stack`, `pull_stack.py`), and is reached from the stack menu’s Stack
Overview row. `builtin_plugins/github/stack-page.js` draws it with the pull request
page’s own builders, exported from `pull-page.js`: `pageHeaderParts`, `titleHeading`,
`stateBadge`, `agesLine`, `rowStrut`, `actorSentence`, `actionWords`, `fetchedNote`,
`showNote`, `labelChip`, `statusLine`, `summaryPlaceholders`, and `holdDiff`; and
`builtin_plugins/github/stack-member-row.js`, the stack menu’s builder, draws its
members.

```text
 [Layers] Stack Overview  #70                              ( [GitHub] View on GitHub | v )
 [1 Pull Draft] [1 Pull Merged] · Last opened 2mo ago · Last update 2mo ago
 (o) maintainer wants to merge 2 commits · Fetched 3d ago via GitHub CLI
 wip -> main
 [enhancement]
 #8 joined the stack.  Show the new comparison
 2 commits · 1 file changed · 741 B compressed (289 B raw diff)
 2 Pulls v
 +--------------------------------------------------------------+
 | [state] WIP: draft the next page       2/2 · #10 · maintainer |
 | [state] Say more in the guide           1/2 · #8 · maintainer |
 +--------------------------------------------------------------+
 1 A · +1 >
 DOCS   CHANGES
```

The members’ card is shown open; it is closed at first paint, as the Diff summary is.

Each part of a pull request’s page, and what the stack’s page does with it:

- **Eyebrow:** none on either page.
- **Title:** adapted. The pull request’s title heading,
  `.page-heading.github-pull-title`, with the Layers glyph in the state icon’s slot,
  since a stack has no one state, “Stack Overview” in the title’s place, and the number
  in the number’s.
- **View on GitHub:** kept.
  The shared button in the header’s corner, from `mountCounterpart`; it opens GitHub’s
  page of the whole stack, `stack/<n>` ([Where It Appears](#where-it-appears)), not the
  top member’s pull request.
- **Row of ages, with the state badge:** adapted.
  In the state badge’s place, a tally of the members’ states (`stateTally`): a pull
  request’s state badge (`stateBadge`) for each state some member is in, in the order a
  stack’s members run from its top, drafts, open ones, merged ones, then closed ones
  (`STACK_STATE_ORDER` in `pull-state.js`), each saying how many, “5 Pulls Draft”, in
  that state’s ink, and none for a state no member is in.
  In a narrow pane the ages give way first, and then the tally, its badges together,
  each cut short at its end down to a floor that keeps its count
  (`--github-pull-tally-badge-floor`). A tally of all four states in a row too narrow
  for it leaves out each badge’s noun first, “12 Merged”, so the badges differ by their
  words and not by ink alone (`tallyBadge`). That is set for four badges in a phone’s
  375 px pane, the case measured; a narrower pane, or a longer count, still cuts a badge
  short, and a badge cut short says its whole label in its tooltip.
  After them and a dot, when a member was last opened and when one was last updated, the
  latest of each, “Last opened 3d ago · Last update 1h ago”, in a pull request’s ages’
  freshness ink and told again as time passes (`pullAge`, `retellAges`). The answer’s
  `states`, `opened_at`, and `updated_at` say them, each member counted from its record
  or else its cached list row.
- **Browse code, Refresh, and the stack chip:** dropped.
  No one branch holds a stack, the page reads the stack on its own poll, and the page is
  the stack the chip would open; the row ends in the chip’s hidden strut (`rowStrut`),
  so it is as tall as a pull request’s.
- **Author’s row and its freshness note:** adapted.
  The pull request’s sentence (`actorSentence`), said of the stack (`stackSentence`):
  every member’s author, top first, each once and a comma between, then “wants to merge”
  or, for several, “want to merge” the commits the top contains, “maintainer, forker
  want to merge 12 commits”; once every member is merged, each one’s merger and
  “merged”, and with no merger known, as list rows alone leave it, “merged 12 commits”
  alone, crediting no one, as a pull request’s record that names no merger says it
  (`headerSentence`). The answer’s `authors`, `mergers`, and `commits` say them; with no
  author known the row has the note alone, and with any member’s commits uncounted the
  sentence names no commits (`actionWords`). In a narrow pane a sentence of several
  names gives way in its names and its action together, each name down to a pull
  request’s author’s floor, so neither is cut to nothing while the other is whole, and a
  name cut short says itself in its tooltip (`sentenceActor`). The freshness note says
  the oldest of the members’ records’ fetches, “Fetched 3d ago via GitHub CLI”
  (`fetched_at`), so the stack is said to be no fresher than its stalest record, its
  slot as wide as its widest age’s words, as a pull request’s is (`showNote`). Offline,
  while a member’s record is behind and no refresh can run, it says so, “Offline ·
  fetched 3d ago via GitHub CLI”, as a pull request’s does (`fetchedNote`).
- **Branches:** kept. The merge the stack makes, the top member’s head → the stack’s
  base, in the shell’s merge refs, held a line tall until the stack’s answer names the
  head.
- **Labels:** adapted.
  Every label a member carries, top first, each once by its name, in a pull request’s
  chips (`labelChip`); a label read from a cached list row alone has no color or
  description, and is the neutral chip until a record gives it one (`labels`). The
  answer says `null` while any member has neither a record nor a list row.
  The row is decided at first paint from the labels the Pulls tab’s snapshot of the
  stack names (`knownLabels`: the stacks route’s `labels`, each member’s record’s or
  list row’s, by name), so a stack whose members carry none has no labels row from first
  paint. Where the snapshot does not know every member’s labels the row is held a line
  tall, empty, as a pull request’s is while its record is on its way, and an answer that
  says the stack has none takes it away, as a pull request’s record does.
- **Status line:** kept.
  The pull request’s status line and text actions: a failed read, a new comparison
  offered, members the top does not contain, and members being fetched or that could not
  be, with Retry. Retry and Show the new comparison are numbered, as a pull request’s
  status line’s controls are (`numberHeaderControls`). A new comparison is offered only
  when it would change what the reader sees, the two commits or the files the comparison
  keeps, and only once the reader has done something on the page: before then, the page
  is catching up as members’ records arrive, and draws the new one with no notice
  ([A New Comparison](#a-new-comparison)).
- **Size line:** adapted.
  The pull request’s [change size line](#change-size-line), said of the comparison drawn
  (`stackSizeInput`): the commits the sentence counts, the comparison’s files, and the
  comparison’s own size, “12 commits · 3 files changed · 6.5 KB compressed (30.4 KB raw
  diff)”, so the size and the file count describe one diff.
  The size is measured where the comparison is built and read where the cache keeps it
  (`size`, `kept_change_size`: no Git runs for it), and only for a comparison that is
  the plain diff of its two commits: one restricted to its layers’ files, or larger than
  `MAX_SIZED_STACK_FILES` in `pull_stack.py`, leaves the bytes out, as it does the
  commits it cannot count.
- **Members:** the one part a pull request’s page lacks, built from existing components.
  A toggle, “**2** Pulls”, a [count summary](#count-summaries-bold-their-numbers) with
  its number bold, after the size line and directly above the Diff summary, the shell’s
  summary toggle (`.summary-toggle`) as the Diff summary’s header is: its words, then
  the registry’s chevron after them
  ([One Chevron, One Row Contract](#one-chevron-one-row-contract)), the tree rows’ hover
  and focus, and its words and hover ground at the summary’s edges.
  The row is there from first paint, the toggle held out of sight and empty where the
  Pulls tab does not know the stack, until the answer names its members.
  It is closed at first paint, as the Diff summary is, and opens and closes with
  [Disclosure Motion](#disclosure-motion), the stack menu’s contents one press away.
  Under it, the stack menu’s member rows, top first, in a page card, each row inset as a
  card’s head is ([Spacing](#the-stack-pages-spacing)) and ending as the menu’s does,
  “2/4 · #455 · jlevy”, the author the shell’s actor identity with a 16 px avatar; no
  row is the page, so none takes the current-row mark.
  A member’s author is the one the stack’s answer gives it (`author` and `avatar` on
  each member of `GET stack`), its record’s or else its cached list row’s, and before
  the answer the one the stack menu draws, the stacks route’s `authors` and `avatars`. A
  reader who opened the card keeps it open across the page’s polls.
- **Diff summary:** kept.
  The header’s last line, drawn from the stack’s comparison, closed at first paint as
  every Diff summary is.
  Its rows carry the tree’s marks alone, as every Diff summary’s do; which members
  change a file is each member’s page’s to say.
  A read of it that fails leaves its row empty, and Changes’s read or Retry draws it
  again, as a pull request’s Changes does.
- **Tab bar:** adapted.
  The pull request’s tabs and keys, Guided Review (only when a member’s description
  carries the stack’s guide), Docs, and Changes; Conversation and Checks are each
  member’s, and there is no Files tab, since the Diff summary lists the files, as on a
  pull request’s page.
- **Guided Review, Docs, and Changes:** kept.
  A pull request’s tab bodies and drawings, in its columns, held out of sight until the
  first screen is ready, with the loading block under the hidden diff, and Docs’ Show
  every change when it has no documents.
  Docs or Changes that could not load say so in a pull request’s error notice, with
  Retry.
- **Body notice and the cold hold:** kept.
  A stack that cannot be shown as one comparison says so in the pull request’s body
  notice, and the page is held out of sight for the quiet period until the stack’s
  answer, as a pull request’s with no record is, since the tally, the ages, the
  sentence, and the labels come with the answer alone: an answer within the quiet period
  is the first header the reader sees.
- **Details for a late or failed read:** dropped for now.
  The page offers no Details; its failures are said on the status line.

Every header row but the status line and the labels is decided at first paint
(`stackHeader`): the row of ages and the author’s row stand empty at their heights until
the stack’s answer fills them, the members come from the repository’s stack snapshot
before it, and the size line and the Diff summary hold the shell’s pending placeholder
until theirs, so the answer lands moving nothing under the title.
The labels row is held while the labels are not known, and kept once seen (Labels,
above).
`tests/dom/github-stack-page-session.js` runs the header’s rows, from first paint
to settled, with the tally, the ages, the sentence, the note, and the labels each answer
gives; the sentence of a merged stack, of several authors, of uncounted commits, and of
no members; the size line’s input in each state; and the drawings the page asks for,
against the stack route’s recorded answers.
`tests/dom/github-stack-guide-mount-session.js` mounts the page and holds that the rows
of its first paint are its settled rows, that the page is held cold until the answer,
that the Diff summary and the members are closed, and that the members’ toggle opens,
stays open across a poll, and closes.
`tests/test_github_stack_page_chrome.py` measures in headless Chrome that, on a stack
whose members’ records are read, nothing on the page moves from the first paint the
reader sees, opening the page or its tabs, a frame held out of sight for the quiet
period not being one; that every member names its author; that the members’ toggle is
closed at first, opens its card under it with the Diff summary below, and closes again,
its words and hover ground at the Diff summary’s edges; that the tally’s badges are a
pull request’s state badges in their states’ ink; that the size line says the commits
and the files; and that View on GitHub opens the whole stack.
On a stack still being fetched, the status line says what is being fetched and then
goes, moving the lines under it; that is not measured.
A member row is not measured either: the page draws it with the stack menu’s builder,
`stackMemberRow` in `stack-member-row.js`, so it is the menu’s row by construction.
The guide’s ages are a pull request’s page’s, `pullAge` in `pull-page.js`, in their
freshness ink.

#### A New Comparison

**A new comparison is drawn without a word until the reader has done something on the
page, and offered with what changed after.** A stack’s members’ records arrive one at a
time when its page opens on a stale cache, each one a new comparison, so a notice then
would describe the page catching up, and a reader who has not moved has nothing to lose
to a redraw. One rule decides each answer (`answerAction` in `stack-page.js`):

- **Before the reader’s first move**, a wheel, a touch, a press, or a key on the page,
  or opening another tab or a file, a new comparison is drawn in place of the old.
- **One that looks the same**, the same two commits and the same files with the same
  totals (`comparisonLook`), is no change, before or after that move: Docs, Changes, and
  the Diff summary are drawn from those alone, so the page goes on drawing the one it
  has, and the reader keeps their place.
  The server keeps the one drawn admitted while the page’s poll names it (`since`),
  unless the stack moves more than `MAX_RETAINED_STACK_PAIRS` times between two polls,
  as it can while the page is out of sight; an answer then says it no longer keeps it
  (no `moved`), and the page draws the new one in its place if it looks the same and
  otherwise offers it at once, so a refusal of what the page draws always has a remedy
  in reach.
- **While a member it waits on is fetched**, it is held, and the status line says
  “Fetching #10 before its new comparison can be shown.”
- **Otherwise it is offered** on the status line, with Show the new comparison, which
  draws it and clears the notice.

The notice says what became of each member since the comparison drawn, top first, in one
sentence (`changeText`): “#845 has 2 new commits, #843 was merged, and #848 joined the
stack.”, naming at most `CHANGES_NAMED` changes, or one fewer and a count of the rest,
“and 2 more pull requests changed”.
A member whose branch no longer holds the head drawn “was rewritten”; one that moved
where no count is known “was updated”; one whose new head the comparison drawn already
shows, its record catching up, is named nowhere; and when only the order changed, the
notice says so. The answer an unchanged-looking comparison came in becomes the one the
notice counts from, so a record that caught up while the page kept its comparison is not
named later.
The new commits, those the comparison drawn did not show, are counted by the
stack route, which the page asks `since` the comparison it draws (`moved` on
`GET stack`); the rest it reads from the two answers’ members.
The notice names no commit and no branch; a title or an author in it would take the
shared order of a pull request’s fields, and it has neither.

#### The Stack Page’s Spacing

**Every part the stack’s page shares with a pull request’s stands at the same edges with
the same padding.** No shared part sets a padding, margin, or inset of its own: each
carries the pull request page’s classes inside its `.github-pull` scope, which declares
the card inset, `--github-pull-text-inset`, and the page’s gap and rhythm, so the same
component looks the same on both pages.
The members’ rows, which only the stack’s page has, take one rule of their own,
`.github-pull-stack-members .github-pull-stack-member` in `github/styles.css`, which
insets them by that same card inset; their toggle and the tally take the rest of that
stylesheet’s stack page section.

| Part | Spacing, as on a pull request’s page |
| --- | --- |
| Header | `.page-header` in the reading column, `.page-reading-column`, at the pane’s gutter, `--content-padding-x`, with the header’s own top and bottom padding |
| Members | Under their toggle, the shell’s summary toggle, pulled left and padded back in as the Diff summary’s header is (`--summary-toggle-pull`), so the two toggles’ words start at one edge and their hover grounds at another; on the page’s ground with no card or border, as the Diff summary’s files under its toggle are (the bordered card is the stack popover menu’s alone); each row the stack menu’s, at the menu’s height and size, inset by `--github-pull-text-inset` where the menu insets it by `--menu-row-inset` |
| Tab bar | In the reading column, its first tab on the header’s content edge |
| Body | `.github-pull-body`’s padding and gap; in the reading column on Guided Review, for a notice, and before anything is drawn, and across the pane on Docs and Changes, so a diff has room for Split (`bodyInColumn` in `stack-page.js`, as `diffTab` decides it in `pull-page.js`) |
| Guided Review | `guided-review.js`’s step list and step card ([Guided Review](#guided-review)), their heads, a step’s note, and its references inset by `--github-pull-text-inset` |
| Notices | `.notice.github-pull-notice`, in the body or the diff’s host |

The stack’s page before it was rebuilt as a pull request’s was outside the
`.github-pull` scope, so every part that reads the card inset had none: Guided Review’s
heads, a step’s note, and its references stood on their card’s border, and its header
and body sat inside a second gutter, 24 px in from a pull request’s. The rebuilt page,
until its body took a pull request’s columns, set Guided Review across the whole pane,
its cards 233.75 px wider than a pull request’s in a 1280 px window with the navigation
pane shown (Chrome 152, 2026-11-25). `tests/dom/github-stack-page-layout-chrome.mjs`,
which `tests/test_github_stack_page_chrome.py` runs on the stand-in with guides,
measures each shared part against a pull request’s, its edges, padding, border, and
ground within that module’s `NEAR`, in both schemes at a desktop width and a phone’s, on
each tab loaded and after the reader switches tabs in place; a part a pull request’s
page pads cannot lose its padding on the stack’s. It holds the members’ card to the step
list’s border and ground, and each member’s state icon to the badge’s edge, measured in
the card’s closed body, whose boxes are laid out as when it is open.
`tests/dom/github-stack-page-session.js` runs which column the body takes in each state.

### Stack Groups in the Pulls Tab

**The Pulls tab always groups by stack** once the repository’s stacks are known; there
is no option to turn it off, because a Group by stack chip, worded or a glyph alone, did
not fit the Pulls toolbar beside the Show group and Refresh at the default pane width,
when Refresh stood in that toolbar.

- **Rows.** Each stack with a pull request in the list has a row, open by default, and
  under it, one tree level in, its Stack Overview row and then the stack’s pull requests
  that the list holds, in the stack’s order, the stack menu’s (`stackEntries`): all
  siblings, at one level.
  No pull request is ever under the Stack Overview row.
  Each pull request keeps its own change line and changed files, a level further in, and
  the Stack Overview row has the stack’s, in the same place.
- **Heading.** A stack’s row is its chevron, its label, the stack’s size, and its age:
  “Stack #286 · 4 pulls” and, at the row’s end, “2h”. It draws no Layers icon: its Stack
  Overview row carries the stack’s. The size is how many pull requests the stack has
  (`stackPullsCount`), not how many the list holds, so it is the stack’s own figure
  under every filter, and it shows whether the stack is open or closed.
  It is a count summary
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)): the
  number bold in the text’s ink and “pulls” regular, “1 pull” for a stack of one, after
  a muted dot. The accessible name says the same count first, in words, and then how many
  the list holds when that is fewer.
  The age uses the most recent known update of any member, including members outside the
  current filter. GitHub updates this time on pushes, reviews, comments, and changes to a
  pull request’s state, base, or title.
  The heading draws it in the same column and freshness ink as the pull request rows.
  [Ages End the Row](#ages-end-the-row) Where the pane is too narrow for the label, the
  size, and the age, the size goes whole, as a change line does, and the label and the
  age stay.
- **Order by activity.** Open, Closed, and All show the newest updates first.
  Stacks use their most recent member update and share the same order as standalone pull
  requests. When a stack ranks within the visible window, it can use a member from
  further down the current filter to represent it.
  If a higher-ranked stack holds that member, the next available member can represent
  the later stack.
- **Shared membership.** A pull request in two stacks sits once, under the first of them
  by the snapshot’s activity, with equal times keeping GitHub’s stack order.
  Its place names the other.
  A list update can move the headings before the next stack snapshot assigns their
  shared members again.
  A later stack’s row’s accessible name still counts it among the pull requests the list
  holds and says where it sits.
  A stack all of whose listed pull requests sit under earlier stacks has no row; their
  places name it.
- **Unknown stacks.** Stacks are optional and arrive on their own; nothing waits for
  them. Until a snapshot is known for the list’s own GitHub account, while none of the
  list’s pull requests is in a stack, or when the stacks cannot be read, the list stays
  flat: the rows and the pull request page say nothing of stacks either.
  A snapshot kept through a failed or expired refresh still groups, as the places and
  the stack menu still show it.
- **Stack Overview.** The first row under an open stack, one level in, is its Stack
  Overview row, a link to the stack’s own page, `/stack/<n>`
  ([The Stack Page](#the-stack-page)), as the stack menu’s first row is.
  It is one line in a member’s row grid: the stack’s Layers glyph, in normal text ink,
  in the state icon’s slot; then “Stack Overview” at the tree’s icon gap from it, where
  the members’ titles start; then, after a muted dot, the stack’s change line; then the
  registry’s chevron, after the summary it expands, exactly as a pull request’s row’s
  last line ends with its change line and its chevron.
  It is the one row of a stack that carries the glyph: the stack’s row above it has
  none, so a stack reads as its label, then the row that opens it whole, then its pull
  requests beside that row.
  It is one of the stack’s set, so the rows’ places count it (“1/4” under a stack of
  three), and a closed stack hides it with its pull requests.
  While the address is the stack’s page, it is the current row, with a pull request’s
  current-row mark, `--highlight-bg` and the 2px `--highlight-bar`; a key or a press
  that opens a pull request takes the mark from it at once, before the address follows,
  so one row holds it.
  It is shown as a current pull request’s row is: an address that names the stack’s page
  opens the stack if the reader closed it and scrolls the row into view, or, where the
  list does not draw the row yet, as before the stacks are known, once it does
  (`setCurrent`’s `stack`, `pullAddress` in `pulls-nav.js`).
- **The whole stack’s files.** The Stack Overview row’s change line and the chevron
  after it are one toggle, a pull request’s row’s own (`.github-pulls-change`): the
  pointer’s target, with the chevron’s hover plate, hidden from assistive technology,
  its state the row’s `aria-expanded`. A press on it opens or closes the whole stack’s
  changed files under the row, one level in, as a pull request’s change line opens that
  pull request’s, and opens no page, though it is in the row’s link; a press anywhere
  else on the row opens the stack’s page.
  Closed by default, as a pull request’s files are.
  That is the only thing the row expands: no pull request is ever under it, and its
  toggle hides none. The files are the stack’s combined ones, the list the stack’s page
  shows in its [Diff summary](#diff-summary): the same two reads, the stack and then its
  comparison through the diff view, whose own rows of that comparison they are
  (`builtin_plugins/github/stack-files.js`, `summaryRows`), in the one tree a pull
  request’s files are drawn with (`pull-files-tree.js`, `pull-files-view.js`), so they
  are the same files in the same order, with the same rows, folders, keys, loading line,
  and notices. Nothing is read until a reader opens them, as a pull request’s list is
  read when its row opens, and the diff view’s assets load then, on demand, never as the
  list mounts. A file’s row opens the stack’s Changes at that file.
  A stack whose pull requests are not all fetched has no comparison yet: the tree asks
  for each one, as the stack’s page does, and holds its loading line until it is there;
  one that cannot be shown as one comparison says so, with Retry.
  The change line counts each member’s own lines summed (**Change line**, below), and
  the files are the combined comparison’s, as on the stack’s page, so a line two layers
  change is counted twice in the line and once in the file’s own count.
  Where the row has no room for the change line, the toggle goes with it, whole; Space
  and Right still open the files.
- **Keys.** A stack’s row is a row of the tree, as a folder is: `J` and `K` stop on it
  and open nothing; Enter and Space open or close it; Right opens it, or goes to its
  first row, the Stack Overview row; Left closes it, or returns to it from a row inside
  it. `J` from an open stack’s row goes to its Stack Overview row first, then its pull
  requests. The Stack Overview row’s keys are a pull request’s row’s: `J` and `K` stop on
  it and open the stack’s page, and Enter and a press open it; Space opens or closes the
  stack’s changed files in place; Right opens them, or, open, goes to the first; Left
  closes them, or, closed, goes to the stack’s row.
  Left on a pull request in a stack, its files closed, goes to the stack’s row.
  An address that names a pull request in a stack the reader closed reveals it by
  opening the stack. The same holds for a row that arrives after its address was named,
  when the list moved to a filter that holds it or read the window it is in: every
  reveal unfolds in one place (`unfoldOver`). Only an address that names the pull
  request unfolds: the tab shown again, a landing that keeps the list’s place, and a
  filter picked ask for the list, not the item, and leave a stack the reader closed as
  it is. A grouped list’s Tab stop, until the reader moves it, is its first row.
- **Scroll.** A grouping that arrives at the top of the list keeps the top, so its first
  stack’s row shows; elsewhere the row the reader is reading keeps its place, and a
  stack’s row can be that row, so opening one keeps its header still.
  A row a reveal scrolled to stays the row being read until the reader scrolls, at the
  top too: stacks that arrive after the list’s first window regroup the list around it,
  as far as the list’s top allows, rather than around the first row in view, which moved
  the revealed row out of view.
  It stays so across a trip to another tab, as the Pulls tab’s button brings the list
  back where the reader left it: stacks that arrive while the reader is away, or just
  after the return, regroup the list around it too.
- **Read ahead.** An open reads ahead the pull requests a key reaches next as drawn, a
  stack’s row and a Stack Overview row passed over, and the first pull requests drawn.
- **Change line.** A stack’s Stack Overview row shows the lines of the stack’s combined
  change as its [brief change line](#brief-change-line) of its line totals alone, after
  its words and a muted dot: “Stack Overview · +1,234 −567”, a total of zero left out as
  a row’s is. The line was the stack’s heading’s until the heading took the stack’s size
  and age: it says what the whole stack changes, on the row that opens the whole stack.
  A stack is the accumulation of its pull requests, merged or open, so its change is
  theirs: each member’s own changed files, the list its expanded row shows, bottom
  first, every file once with a status composed from what the members did to it (removed
  if the last one removed it, else added if the first one added it, else renamed or
  modified), and every member’s lines summed (`pull_change_sums.py`). The server
  accumulates them from the cache (`GET stack-change`); it never asks GitHub, fetches,
  or runs Git. Totals a member’s list could not count, a binary file it listed, are
  followed by the Diff summary’s muted “(estimated)”, and the accessible name says
  “estimated” after the line’s words.
  The line and its chevron are one unit that never wraps, laid out as a pull request’s
  row’s lines and chevron are (`.github-pulls-change`): the chevron right after the
  line, and where the row has no room the line gives way to an ellipsis, “(estimated)”
  first, while “Stack Overview” and the chevron stay (the owner’s word of 2026-11-26).
  It is read for the stacks the list draws, one at a time when the browser is idle,
  within the lines’ own hourly cap, apart from the comparison warms’, and read again
  never on a timer but when what it is made of may have changed: when a member moves or
  the members change, as the list’s rows report them, a member the list holds no row of
  taken as unchanged; when a member’s list arrives or is refreshed, as the prefetch or a
  row’s own read sees it; and, silently, while its answer names members not yet settled,
  a list missing or one its row would refresh, a minute on and less often each time.
  The prefetch asks for those members’ lists after the reader’s own rows, in a few
  places kept for them, so a closed stack’s line fills in too.
  The answer is kept for the document under its stack and its revision, so a row drawn
  again has it in its first paint, and a line stays shown while its stack is read again
  and when that read fails (`builtin_plugins/github/stack-lines.js`). It is read for a
  stack whose heading is drawn, open or closed, so a stack that opens later has its line
  in the paint that draws its Stack Overview row.
  While its stack’s first read is on its way, the row holds the shell’s pending
  placeholder where the line will be, after the quiet period, and its accessible name
  says “change pending”, in the filter chips’ words; a row whose read is queued behind
  another’s does not wait.
  A stack whose change cannot be had yet, a member whose changed files are not cached,
  shows neither, and a read again of it, or of a stack still settling, shows no
  placeholder, so its row never pulses and goes blank twice.
  The line follows the row’s words, and the chevron follows the line, so the line
  arrives and moves the chevron alone, as a pull request’s does.
  The row stays one line at every pane width: its words are never cut for the line, and
  where the totals have no room, never cut short with an ellipsis, the whole line goes,
  and its chevron with it.

`tests/dom/github-pulls-stack-groups-session.js` runs the grouping, the keys, and what
an open reads ahead against the production code on the server’s recorded answers, and
mounts the panel and the page’s stack menu to hold the tree’s roles, levels, places,
expansion, and order: each open stack’s Stack Overview row first among its rows, which a
key or a press opens and an address of the stack’s page marks, its members beside it at
one level, its change line and chevron the toggle of the stack’s files, which Space,
Right, Left, and a press open and close with no pull request hidden and no page opened,
an address that names a member opening a stack the reader closed, the heading’s time the
newest of its listed members’, and its accessible name saying the count it shows.
`tests/dom/github-pulls-stack-files-session.js` runs the stack’s list of files against
the production tree on the `stack` route’s recorded answers, with the diff view’s own
`summaryRows` on the recorded comparison: what each read asks for, that a comparison is
read once, and what a pending stack and one that is no single comparison show.
`tests/test_github_stack_page_chrome.py` holds in headless Chrome that the row is the
current row and in view on the stack’s page, that a press on it and `J` onto it from the
stack’s row open the page, and that a press on its change line lists under it the files
the page’s Diff summary lists, the same rows in the same order.
`tests/dom/github-pulls-stack-lines-session.js` runs what each stack shows of its change
line, and when it is read, against the production code on the route’s recorded answers,
and mounts the panel to print a Stack Overview row waiting, with its line, with none,
and with “(estimated)”, and each stack’s heading the same through every step.
`tests/test_github_pulls_stack_lines_chrome.py` measures in headless Chrome, at every
width down to the pane’s minimum in both themes, that nothing in a Stack Overview row
but its chevron, which follows the line, or in its stack’s row moves when the line
arrives, that each stays one line with its first part whole and the line whole or out of
view, never cut short, and that the line’s inks and weights are the component’s.
`tests/test_github_pulls_stacks_chrome.py` measures the same design in headless Chrome
against a running server with two native stacks: the shared label tokens, a stack’s row
that shows its label, its size, and its age, with the count in its accessible name,
where rows start, hover and focus, the toolbar’s fit, real keys and presses, a row’s
toggle among them, the scroll, a pull request’s row with the state icon centered on its
run’s first line, the number and the author in its run, and the toggle and the age at
the row’s end on its last line, a member’s place and dot after its title and its missing
icon, and the menu’s order and ink, each member’s author after its number, on its
baseline, and cut short at a third of the line for GitHub’s longest login, and the
menu’s Stack Overview row’s glyph and words where the members’ icons and titles start.
`tests/dom/github-pull-header-chrome.mjs` lays out members’ rows at every width down to
the pane’s minimum and holds that a place sits after the title with its dot before it,
and the run ends inside the row with nothing scrolling sideways; that one stack’s place
shows whole; that every line of the run starts in the text column, the icon centered on
its first line, and the run ends with the author, the last line under it with the
chevron in the text column and the age at the row’s end; and that the author follows the
number and ends the run inside the row.
`tests/dom/github-pulls-row-lines-session.js` runs what each row’s run and last line
show, when it is read, and what a press and each key do, against the production code on
the summary route’s recorded answers, and `tests/test_github_pulls_row_lines_chrome.py`
measures in headless Chrome, at every width down to the pane’s minimum in both themes,
that nothing in a row moves when its lines arrive, that every line of its run starts in
the text column and the run ends with the author, the lines and the chevron after them
on the last line and the age at its end, that its inks and weights are the component’s,
and that a press, Right, and Left keep the row in place.
`tests/test_github_stack_design.py` holds the source to one label class and one place
for every stack word.

## Keyboard Shortcuts

These are the rules every key follows: which key a meaning gets, how a key is matched,
named, and drawn, and how a command reaches what it acts on.
The reference of which key does what is [Keyboard Shortcuts](keyboard-shortcuts.md), and
`tests/test_keymap.py` holds its table to the keys the registry, the manifests, and the
built-in plugins bind.
Help, the Shift reveal, the other documents, and the code’s comments link to the two
rather than restate them.

### The Rules

- **Letters for known meanings.** A letter names something a reader can guess and keep:
  `F` for Files, `P` for Pulls, `H` for commit History, `T` for the file finder, `U` for
  up. A letter means the same thing wherever it is live, except in an open menu with
  focus, whose rows’ own letters come first ([Keys in a Menu](#keys-in-a-menu)).
- **Reusable semantics.** Some letters are verbs that apply wherever their meaning does,
  as Vim’s motions do.
  `J` and `K` move down and up a row in every row list.
  Control-N and Control-P, on macOS and iOS, go to the next and previous item one level
  up: the pull requests of a stack, and on any later page with its own next and
  previous, that page’s. `V` and `S` switch a file between its rendered view and its
  source, whatever its tabs are called.
  A page with a natural next and previous uses Control-N and Control-P, a rendered view
  is always `V`, and no other meaning takes those keys.
- **Numbers for situational items.** Links and one-off actions that depend on what the
  screen shows, such as the Files tab’s filters or a pull request’s Retry, take `1`,
  `2`, `3`, and on, in reading order, up to `9`. A tenth and later get no key: no letter
  and no wrap-around, and `0` is not a tenth number.
  Numbers are positional, so `1` reaches a different control on a different screen; Help
  says so, and the Shift reveal shows what each reaches now.
  One mechanism numbers them, the registry’s `attachNumbered()`, which the shell calls
  directly and plugins call through the shortcut surface, so no surface picks its own
  digits.
- **`0` is Home.** It is the one digit with a fixed meaning, and it goes to the served
  folder’s home view on every screen ([Home](#home)). It sits past the numbers, which
  stop at `9`, so it never reaches a numbered control, and taking it moved no letter of
  a known meaning: `H`, Home’s first letter, is commit History.
  Shift-0 is `0`, as Shift with any digit is.
- **No key on an ancillary item.** Copying a path, a revision, or a hash; a per-row or
  per-file affordance, such as a changed file’s View on branch or its chooser of views,
  of which a page has many; and a control that shows only on hover take no key.
  Each stays reachable by pointer and Tab.
  A key goes on a major tab or a major button, and a rare one, such as the Metabrowser
  menu, print, Retry, or Reload page, goes without.
- **One key, and Control only for next and previous.** Every shortcut is a single key
  but Control-N and Control-P on macOS and iOS ([Control Chords](#control-chords)),
  Shift changes nothing, and Command, Option, and every other Control chord stay the
  browser’s ([Binding Grammar and Accessibility](#binding-grammar-and-accessibility)).

### Scopes and Collisions

- **Shell keys are reserved everywhere.** The keys in `RESERVED_SHELL_KEYS` in
  `src/metabrowser/keymap.py`, its letters and `0`, keep their meaning even where they
  do nothing, so a letter never means one thing on one screen and another elsewhere;
  only an open menu with focus puts its rows’ letters ahead of them
  ([Keys in a Menu](#keys-in-a-menu)). Control-N and Control-P reserve no letter: a
  view’s key is one letter alone.
  A manifest whose view takes one is refused: the loader rejects it, the plugin does not
  load, and `metab --doctor` reports why.
  The plugin shortcut surface refuses one too, with a console warning, and the control
  works without a key.
  Two views of one kind declaring the same free letter, in one manifest or across two,
  both load: the first in tab order keeps the letter, the later view is served without
  it, and `metab --doctor` reports the lost key.
  The same table reserves `1` to `9`, which only the numbering hands out, and a view’s
  key is one letter, so no view can take a digit.
- **Tab letters are scoped to their tab bar.** A tab with a reusable meaning takes its
  letter, `V` or `S`. Any other tab takes the first letter of its label, or when that is
  taken, the next distinctive free letter of its label, never a shell letter (a menu
  row’s letter may be one: [Keys in a Menu](#keys-in-a-menu)), and declares it beside
  the label rather than deriving it, so a rename never moves a key.
  Two tabs on one screen never share a letter; two bars never shown together may, as
  Charts and Conversation share `C`.
- **A collision is settled by the newcomer.** It takes the next free letter of its own
  label, as Checks takes `E`: `C` is Conversation’s, `H` is History, `K` moves a row up,
  and `S` is Source.
- **Numbers are scoped to the screen.** The live numbered controls, the navigation
  pane’s before the main pane’s, top to bottom, are `1` to `9` in that order.
- **An open menu’s letters are scoped to it.** While a menu whose rows have letters is
  open and has focus, those letters choose its rows, the one exception to the rules
  above ([Keys in a Menu](#keys-in-a-menu)).

### Main Tabs

The sidebar orders Files, Pulls, and Commits in that order, under `F`, `P`, and `H`:
Files and Pulls take the first letter of their label, and Commits takes `H`, for commit
History, because `C` is Charts’ and Conversation’s, view tabs that a shell letter,
reserved everywhere, would leave without a key.
The letters work outside text fields and dialogs, with or without Shift.
A letter opens its tab, or keeps the tab already shown, and moves focus to the panel’s
roving row, so `F` then `↓` walks the file tree; while the panel has no rows yet, the
tab button takes focus.
A missing tab has no target, so its letter does nothing and stays reserved.

### Browser and App Keys

A key held with Command, Control, or Option belongs to the browser, and in the macOS app
to the app’s menus, but for the two [Control chords](#control-chords) the keymap lists
on macOS and iOS. No other shortcut uses one, and no page handler takes one: a handler
that cancelled a chord would keep it from the browser, and the app’s web view hands
every key to the page before its menus.
`tests/test_modified_keys.py` lists each `keydown` handler and what leaves chords alone
in it. The other exception is Option-Tab inside a dialog or an open menu: its focus trap
keeps it, because Safari moves focus with Option-Tab.

So Command-R always reloads, whatever has focus: the `modified` part of
`tests/dom/key-reveal-session.js` presses it in each place the shell puts focus.
[Keyboard Shortcuts](keyboard-shortcuts.md#browser-and-app-keys) is the user reference,
with the app’s menu keys.

### Control Chords

Control-N and Control-P are the only chords the registry binds, and only on macOS and
iOS. They walk a pull request’s stack: Control-N to the next member toward the stack’s
top, Control-P to the previous one toward its base.
Held, a chord walks once, and its repeats are consumed without walking.

- **Why these two.** The letters alone are worth more to the keymap than one walk
  through a stack: `N` is free, and `P` opens the Pulls tab.
  With Control they mean next and previous in Emacs, readline, and the macOS text
  system, which moves a field’s caret down and up a line with them, so the chords keep
  the meaning they have elsewhere.
- **Why Control, and only where it reaches the page.** On macOS and iOS, Command is the
  command key: the macOS app’s menus and the browsers there give Control with `N` or `P`
  no command, so both chords reach the page.
  On Windows and Linux, Control is the browser’s command key: Ctrl+N opens a new window,
  which a page never sees, and Ctrl+P prints.
  Bound there, one chord would be listed for a key that does something else and the
  other would take Print, a browser chord no page handler takes
  ([Browser and App Keys](#browser-and-app-keys)). So neither is bound there: Help and
  the Shift strip list neither, the browser keeps both, and the stack menu walks the
  stack. The registry reads the platform from the page’s navigator, client hints first,
  and refuses a chord where Control does not reach the page (`controlReachesPage()` in
  `static/keyboard-shortcuts.js`); without a navigator, as in a browserless session, it
  does not.
- **What the registry allows.** A binding declares Control with `control: true`, and
  only with `N` or `P` (`CONTROL_CHORD_KEYS` in `static/keyboard-shortcuts.js`). The
  chord matches Control held alone: Alt or Meta with it makes another chord, and AltGr,
  which reports Control and Alt, types its character.
  It never matches in a text field, even for a command that opted in, since the field
  moves its caret with it.
  Shift changes nothing, as for every key.
  A chord reserves no letter, since a view’s key is one letter alone.
- **How it is written.** Help, the Shift strip, and a badge write a chord `⌃N`, as macOS
  and iOS do; it is spoken “Control N”, a hidden phrase even for a chord alone, and
  announced as `Control+N` ([Canonical Key Names](#canonical-key-names)).
- **Another chord** is a design decision made here first.
  It must keep the meaning its chord has elsewhere and take no command from the browser
  or the platform where it is bound.
  Command and Option stay the browser’s and the app’s.

### Keyboard Keys

Every keyboard key rendered anywhere in the app uses the `.kbd` component: always all
caps, bold, with one thin border.
Never hand-set a key’s type or border at a use site, and never write a key as plain text
inside a sentence.

Write the key in its natural case in markup: the caps treatment is presentational, so
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
| `#` | `#` | Hash | Omitted when matched as a produced character |
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
| Control with `N` or `P`, on macOS and iOS | `⌃N` | Control N | `Control+N` |

`Shift` is a name for the formatter’s single-key entry point, `describeKey()` with
`appendKey()`, which renders a key that is not a binding, such as one named in a
sentence. No binding may use it.
A [Control chord](#control-chords) is bound only on macOS and iOS, so it is one keycap
written as they write it.
Alone or among alternatives, it is spoken as a visually hidden phrase, “Control N”, with
the keycap hidden from assistive technology, since a screen reader may name `⌃` by its
Unicode name rather than as Control.

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

#### Binding Grammar and Accessibility

- Every shortcut is a single key, but for the two [Control chords](#control-chords),
  Control-N and Control-P, bound only on macOS and iOS. A binding declares Control with
  `control: true`, and the registry rejects it with any other key or on any other
  platform. No binding uses Alt or Meta, and the registry rejects a binding that states
  any other modifier policy, Shift included.
- Shift never changes what a key means: a letter matches in either case, a named key
  such as `↓` or `Home` matches with or without Shift outside a text field, and a digit
  matches the digit typed or, failing that, its key on the digit row, so Shift+`1` is
  `1`, and Shift+`0`, which types `)` on a US keyboard, is `0`. A character that is
  another binding’s key keeps it: German Shift+`7` types `/` and is Quick Search.
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

### Keyboard Commands and Help

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

Help lists the letters by meaning, group by group, and the numbers once, in an “On this
screen” group: `1`–`9`, “Numbered links and actions,” with the note that the numbers are
not fixed. It gives no number a fixed meaning; `0`, Home, is listed under Anywhere with
Help and Quick Search.
The registry marks the numbers’ command `situational`, so every surface renders them as
that one run, and no surface special cases them.

The shortcut strip at the navigation column’s foot lists Shift first, as Reveal keys,
ahead of `?` for Help, because Shift is the one key that shows all the others.
It is the strip’s one item that is not a command, since no binding may use Shift
([Canonical Key Names](#canonical-key-names)): Help draws it once, as a reminder with
the single-key entry point’s keycap, and hides it from assistive technology, as it hides
the badges and the revealed strip.
The `nav` surface’s commands follow in their order.
The strip is always one row, the one the server reserves for it before the shell’s tools
load: where its items do not all fit, Help hides them from the end (`keepStripOnOneRow`
in `static/keyboard-help.js`), so Quick Search goes first, then Help, and Shift always
shows.
A dropped item leaves the tab order, and its key stays in Help and on the revealed
strip, which Shift calls up.
Where Shift shows alone, the strip’s named group is hidden from assistive technology as
Shift is, rather than announced empty.
`tests/dom/shortcut-strip-session.js` runs that code browserlessly on injected widths.
The widths at which each item shows in Chrome are beside `.nav-shortcut-hints[hidden]`
in `static/styles.css`, and `tests/test_shortcut_strip_chrome.py` holds every pane width
from the narrowest to the default to the rule.

Holding Shift reveals the keys in place: each live letter’s control and each numbered
control carries its keycap, and the strip lists the common letters.
The keycaps ease in on the [reveal motion](#reveals) and go at once when Shift is
released. [Badge Targets and the Shift Reveal](#badge-targets-and-the-shift-reveal) has
the mechanism.

### Badge Targets and the Shift Reveal

A command whose key acts on a control on screen attaches that control as its target
(`attachTarget()`), and the control then carries the command’s `aria-keyshortcuts`, so
the key is announced at rest.
A command marked `targeted` is live only while one of its targets is connected, enabled,
outside any `inert` subtree, and visible, so a key whose control is hidden, staged, or
behind a modal leaves the event to the browser; the first live target runs the command
and carries its badge.

Every key runs a named activation path, the one its control’s click runs, plus the focus
a keyboard user needs next; no command synthesizes a click.
A main tab’s letter opens the tab and then focuses the panel’s roving row; a view tab’s
letter selects the tab and leaves focus where it was; a filter’s number opens its menu,
and the drawer that holds it, and focuses the checked row; `W` opens the branch list and
focuses its filter; `U` opens the parent folder; and `0` goes home through the folder’s
name’s click path, and badges the name beside it.
View tab letters are commands in a permanent `view-tabs` scope below `global`, one per
letter, held for the bar the main pane commits and never for one still staged; the
keymap check keeps them off the shell’s letters.

A situational control is numbered (`attachNumbered()`) instead of given a letter: its
number is its place among the live numbered controls in reading order, the first nine
only. The numbers are one `situational` command, so Help and every other surface show
them as the run `1`–`9`. The docstrings of both calls in `static/keyboard-shortcuts.js`
give the handles, ranks, and lifecycles.

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
  the keycap’s type, caps, padding, and radius and changes only its paint: the yellow,
  translucent (`--kbd-badge-bg`), a deeper border of the same hue
  (`--kbd-badge-border`), the body text (`--kbd-badge-color`), and the small elevation.
  It is absolutely positioned and ignores the pointer, so it moves no box and a click
  reaches the target beneath it.
  No call site styles a badge.
- **Placement.** An `inline-end` badge sits inside its target over the inline-end
  padding, centered top to bottom: the default, for tabs, chips, and text buttons.
  A keycap is wider than a tab’s padding, so it covers the label’s last letter, which
  reads through the translucent fill.
  A `beside` badge also sits over its target’s own inline end, but is positioned within
  the nearest `[data-kbd-badge-anchor]`: a file’s or a folder’s view header, or the
  commit view’s heading.
  It serves icon buttons and targets in a row that clips, such as the view header’s Up
  control, where a badge inside the target would be cut off.
  It covers the icon or the crumb’s last letter, never the file name, note, size, path,
  or author that follows.
  The target and the anchor become containing blocks through zero-specificity rules, so
  one that already declares a position keeps it.
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
`WALK_SETTLE_MS` after its last repeat (`static/tree-keyboard-navigation.js`, and the
GitHub plugin’s `pulls-panel.js`). In the Pulls tab that matters most, because a pull
request’s page can cost a fetch where a file cannot.
In the file tree a repeat slower than the settle time opens each row as it reaches it,
for the rest of the hold.
A single press opens its row at once.
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
  **Space** on a pull request toggles its changed files and keeps the current preview,
  focus, and history. On a file tree row, both keys toggle a folder or container file or
  show the next page and leave history alone.
  On a commit row, both keys select it again, replacing the entry.
- **A pull request** is one item and one stop: its toggle, the lines and the chevron, is
  never focused
  ([A Click on the Toggle’s Line Toggles](#a-click-on-the-toggles-line-toggles)). Up,
  Down, `J`, and `K` walk whole pull requests, past any open files, and expand nothing.
  Every key acts on the item with focus, even after a poll or a reveal has moved the
  list’s Tab stop to the open pull request.
  Its changed files are a folder’s children: Right opens them, or, open, goes to the
  first; Left closes them, or, closed, goes to the stack’s row it is under; and Space
  opens or closes them in place, and is consumed, so the list does not scroll from under
  the focused row. In its files, Left on a top-level row goes back to the pull request.
- **A stack’s row** in the Pulls tab, grouped by stack, is a stop of its own that opens
  nothing: Enter, Space, Right, and Left open, close, enter, and leave it as a folder’s.
  Its Stack Overview row is a folder as a pull request’s row is, of the stack’s changed
  files: Right, Left, and Space open and close them, and Enter opens the stack’s page
  ([Stack Groups in the Pulls Tab](#stack-groups-in-the-pulls-tab)).
- **The other keys** in the Pulls tab are `J` and `K`, with or without Shift, for its
  rows, and Control-N and Control-P on macOS and iOS for a pull request’s stack
  ([The Pull Request Page](#the-pull-request-page)). Help reads the `pull-requests` and
  `pull-stack` groups of the shortcut registry, and no surface there names a key.

These differences are deliberate: making one collection conform to another changes a
plain folder’s Back.

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
history, pull-request rows, their changed-file trees, and the table view’s grid
([Data Tables](#data-tables)), whose arrows move without opening.
The adjacent `test_git_row_selection_avoids_full_collection_mutation` pins Git’s
interaction cost. Register every new navigational row collection in the shared check so
its Tab order and vertical navigation cannot silently fork this contract.

### Descriptor Contract

Every presented command is one descriptor: an identifier and scope, bindings that are
each one key or a [Control chord](#control-chords) declared with `control: true`, a
group, its copy, and the surfaces it appears on.
Equivalent keys are aliases of one descriptor, no call site hand-writes the ARIA a
control binding sets, and compact hints are a selected subset of Help, not a second
list. `ShortcutCommand` in `static/keyboard-shortcuts.js` holds the whole contract, and
the registry enforces it.

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
reminders.”, its `Shift` a keycap from the registry’s single-key `appendKey()`. Each
group says when its keys apply, in the `context` that `GROUP_DEFINITIONS` in
`static/keyboard-shortcuts.js` gives it.

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

## Icons and Icon Buttons

The [Icon Catalog](design-system-icons.md) lists every icon the product draws, by what
it stands for, with its meaning, the one place it is defined, its ink, and its size, and
says how to choose between similar ones; `tests/test_icon_catalog.py` holds it to the
code.

Icons come from one Lucide-derived set in `static/icons.js`, rendered as inline SVG that
inherits `currentColor`. An icon never carries its own color.
A plugin’s own domain marks, which no other surface draws, are Lucide-derived the same
way and live with the plugin’s code, so a page that never shows them does not load them:
the GitHub plugin’s four pull-request states are in
`builtin_plugins/github/pull-state.js`. A shell mark that only a view draws lives with
the view helper that draws it: the person glyph of an [actor identity](#actor-identity)
is in `static/plugin-sdk-views.js`.

### One Glyph Size

Every icon in the chrome is drawn at `--icon-glyph`, whether it is a button, a file-type
mark on a tree or palette row, or a menu row’s leading mark.
Never inline a pixel size at a use site.
Where an icon reserves a column in a palette or menu row, or a file identity’s, the
alignment box around it is `--icon-box`, one step wider than the glyph, so the mark sits
optically centered. In a text heading, lay out adjacent icons on one flex centerline and
align their ink with the visual center of the text.
Apply any optical adjustment to the SVG inside its slot so the click target stays
centered in the row.
In the sidebar heading, `--heading-icon-offset-y` places the source mark on the name’s
capital-height band.
Info uses the source mark’s ink center as its reference.
The folder variants have slightly different ink bounds inside their shared 24-unit SVG
box, so `--source-mark-ink-offset-y` carries that difference to Info at the current icon
size.

A tree row’s leading slot is the glyph’s own width, `--tree-icon-slot`, which is
`--icon-glyph`: a folder’s or a container’s chevron, a file’s type icon, a change
letter, and a Pulls row’s chevron, state icon, and a Stack Overview row’s Layers icon
all take it, so chevrons and icons make one column and the names after them line up.
The chevron, `--toggle-chevron-size`, is narrower than the slot and centered in it, and
a file icon fills the slot, the row’s gap from its name.
`tests/test_files_tab_chrome.py` and `tests/test_github_pulls_stacks_chrome.py` measure
the slots and where the names start in Chrome.

Files and exact file extensions use the `.file-identity-icon` alignment-box primitive.
Resolve its host-owned SVG and subtype class with `window.metabrowser.fileTypeIcon()`;
do not copy the filename matcher, SVG, or `ft-*` mapping into a component.
The navigation tree, plugin views, and aggregate rows therefore change together when a
file type is added.

There are two deliberate exceptions, each documented at its rule.
`.menu-seg svg`, in the segmented theme and font choosers, is the segment’s label rather
than a mark beside text, and so carries the weight of a word.
The person glyph in an [actor identity](#actor-identity)’s box,
`.actor-avatar > :is(img, svg)`, stands in for an avatar image, so it takes the image’s
box, `--actor-avatar-size`, and not `--icon-glyph`: at the glyph size it would sit
smaller than the avatar it replaces, and the box and the name after it would differ with
and without an avatar.

### Source Kind Marks

**The root’s name at the top of the navigation leads with a mark for what is open: a
folder with a cloud for a mirror, a folder with Git’s branch for a Git checkout, and a
folder with its root node for a plain folder.** The three are the source kinds of the
[Icon Catalog](design-system-icons.md#source-kinds), which says what each means, how the
kind is decided, and where else each is drawn.
The rules for the page are:

- **A mark is a root’s and never an ordinary folder’s.** A source-kind glyph differs
  from the ordinary `folder`, which a subfolder’s view header draws, so the root of a
  window and any folder inside it never wear the same icon.
  The root’s own header in the main pane draws the kind mark too (`folderGlyphHtml` in
  `static/view-header.js` copies the navigation’s), so the one root has one icon in
  both.
- **The server writes the kind, its glyph, and its sentence.** The shell puts `kind` and
  `kind_tip` of `GET /api/identity`, and the one glyph for the kind, into its first
  paint, `.header-root-kind`, from `static/source-kind-glyphs.json`, so the mark is
  there with no script and no request, in a box that is there from the markup.
  The glyphs are not in the icon registry, which every page fetches before its first
  tree under a gated budget, and the page draws one of three.
- **A glyph-only mark names itself.** Its tooltip, `data-tip-text`, is its accessible
  name too: the kind and what it is of, “Cloud mirror of owner/repo”, “Local Git
  checkout (GitHub: owner/repo)”, or “Local folder”
  ([Tooltips Add Information](#tooltips-add-information), for a glyph-only mark).
  It is no control, and takes no focus.
- **It shares the Home link with the name.** [Home](#home) puts the hover surface and
  focus ring around both.
  The adjacent chevron opens [Repository Details](#repository-details).
- **It is drawn at `--icon-glyph` in `--muted`**, so the bold name stays the heading,
  like a folder’s glyph in a view header, and it shortens nothing: the name still ends
  in an ellipsis where the column is narrow.

`tests/test_root_identity.py` holds the page’s mark to the route for each kind,
`tests/test_icon_catalog.py` holds the three glyphs, the ordinary folder’s, and where
each is drawn to the catalog, and `tests/test_root_kind_mark_chrome.py` draws a folder,
a checkout, and a mirror’s page in Chrome, and holds the root’s header in the main pane
to the navigation’s mark and a folder inside it to the ordinary one.

### Every Icon-Only Control Is the Same Control

An icon-only button is one primitive, `.icon-btn`, documented in the
`── Icon buttons ──` block of `static/styles.css`. It pairs `--icon-glyph` with
`--icon-btn-size` for the hit target, so the settings gear, the navigation’s Refresh
beside it, the print action, and the copy buttons are interchangeable wherever they
appear.

At rest an icon button is a bare muted glyph with no border and no fill.
It raises a hover surface and a hairline border only while hovered, focused, or holding
a menu open; hover, keyboard focus, and “my menu is open” are one visual state.

Do not give an icon button a resting border or background.
A permanent box around one icon makes it read as a heavier, more primary control than
the unboxed icon beside it, and two icons of equal standing stop looking like the same
kind of thing.
The hover surface is what signals “this is clickable”: a static frame adds
weight without adding information.

The one sanctioned resting surface is `.icon-btn-overlay`, for a button that floats
above content: a bare glyph over source text is unreadable, so it needs an opaque plate.

An icon button that cannot act now keeps its place with its glyph dimmed, at
`--dimmed-content-opacity`, and raises no surface under the pointer, since a press does
nothing.
Up at the served root is `disabled`; the navigation’s Refresh is `aria-disabled`
while it waits, which leaves it its focus, its tooltip, and its number
([Refresh, Retry, and Reload Page](#refresh-retry-and-reload-page)). The primitive holds
the state (`.icon-btn:is(:disabled, [aria-disabled="true"])`), so no use site draws its
own.

### Copyable Identifiers Use One Delegate

A copyable path, revision, or other exact identifier pairs its visible value with an
adjacent `.icon-btn.icon-btn-reveal` using the registry’s `copy` icon.
The visible value may be abbreviated when its meaning remains clear, but the copy
payload must preserve the complete identifier.
The Git commit header and the checkout’s folder details show the short revision
([Short Commit IDs](#short-commit-ids)) and copy the full commit ID.

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
The shared delegate owns successful, failed, and reset feedback, while the containing
row owns when an `.icon-btn-reveal` becomes visible.
Keep the button in the Tab order even while it is visually quiet.

`test_copyable_identifiers_share_the_copy_contract` maintains the registered path,
diff-file, and Git-revision consumers.
Add each new exact-identifier copy surface to that check.

### Parent Navigation

Moving to an enclosing folder is a navigation action, and it has two forms.
The labelled form, the treemap’s Zoom out, names the destination folder and is a
bordered button: `.btn` with `.parent-nav-btn`, the shared `.parent-nav-arrow`, and a
visible resting boundary.
Up alone, at the start of a view header’s eyebrow, is an icon button, `.icon-btn`: the
arrow alone at rest, and the hover surface and its hairline only while hovered or
focused, as the navigation’s chevron is, at the eyebrow’s control size
(`--view-header-up-size`), its destination in its accessible label and tooltip.
At the served root it keeps its place, disabled and dimmed, and surfaces nothing.
The owner asked for Up without a box but on hover, like the collapse chevron
(2026-11-18). `tests/test_view_header_chrome.py` holds Up to no surface at rest and one
while hovered, in both themes.

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
inventing a pill of its own.
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

A `.chip-menu` composes the floating `.menu` surface rather than introducing a second
menu look, and adds what `.menu` and the native `.menu-select` lack: picking several
things. Its trigger summarises the selection the way a select does (`Any age`,
`Past week`, `.md +2`) so the closed control still answers “what is filtered?”. It
closes as [every menu closes](#every-menu-closes-alike), a press on the bar beside it
included. Opening one puts focus on its checked row, and closing it gives focus back to
the trigger ([Keys in a Menu](#keys-in-a-menu)). The trigger uses the shared Lucide
disclosure chevron at the standard chrome glyph size, rotated downward; do not
substitute a text caret or shrink it to fit the label.

A dropdown declares its kind the same way a group does, and for the same reason: `one`
gives `role="menuitemradio"` rows and closes on pick; `many` gives `menuitemcheckbox`
rows and stays open, because picking several is the point of it.
Only one dropdown is open at a time.
The list always leads with an any-row naming the dimension’s default (`Any type`), so
clearing one dimension is a pick rather than a separate control, and the option list
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

The nav filter bar uses dropdowns throughout, because its age windows and size steps as
segmented ramps would leave no room for anything else in a navigation pane.
The groups stay part of the family for surfaces with fewer, shorter values.

Age and file-type rows carry right-aligned file tallies in tabular numerals.
Fixed age windows remain in chronological order and show cumulative counts.
Open-ended type values are ranked by frequency and capped, so the menu cuts the long
tail rather than an arbitrary alphabetical slice.

A dropdown may lead with ordered named **preset sections**: shorthands standing for the
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
label plain. Aggregate category and family rows are text-only; the heading of a family
section names a category and leads with its icon
([File-Type Category Icons](#file-type-category-icons)). The icon is what identifies a
type everywhere else in the app, and tinting a whole column of labels makes the hues
compete with the selected-state mark instead of helping anyone scan the list.

### Selection Kind Is Visible Before the Click

A group declares its kind in `data-select`, and the two kinds look different:

| Kind | ARIA | Selected fill |
| --- | --- | --- |
| `data-select="one"`: exclusive | `role="radiogroup"`, `aria-checked` | `--highlight-bg` / `--link` |
| `data-select="many"`: additive | `role="group"`, `aria-pressed` | `--hover-bg` / `--text` |

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
whether pressed means those rows are shown or filtered away: the user has to click it to
find out. “Show ignored” with a tick states its own direction, uses the control everyone
already knows for that, and is visibly lighter than a pill sitting beside one.
Reach for it when the label has to name the *on* state; reach for a chip when the label
names a value.

Keyboard behavior follows the kind: an exclusive group is one tab stop with arrow-key
traversal and roving `tabindex`, while each chip in an additive group is its own tab
stop, because each is an independent control.

### Grouping the Files Tree

**The Files tab’s filter row holds Group by; the three filters and Show ignored sit in
the drawer behind the chevron.** Group by splits the tree into sections and removes
nothing, so it needs no drawer and no badge.
The drawer holds Modified within, File type, and Minimum file size, then Show ignored,
whose tick states its own direction.
The chevron shows no count, so Clear and the chevron fit beside Group by; its accessible
name counts the ones set, Show ignored turned off among them, since the closed drawer
hides it, and Clear says that some are set.
A Git revision has no gitignored entries, so its drawer has no Show ignored.
Clear sits beside the chevron and shows while any filter is set, Show ignored included;
it resets them all, Show ignored back on, and keeps the grouping.

- **Values.** No grouping is the default and shows the one tree.
  By age splits by modification time and By file type by the registry’s display groups.
  Each row reads as the closed trigger does when it is chosen, so the menu and the
  trigger never name one value two ways.
  A Git revision has no modification times of its own: its files are dated by their last
  commit when the Git can read that
  ([file ages](project/architecture/arch-git.md#file-ages)), and a revision whose Git
  cannot offers neither By age nor Modified within.
  Where it can, the groups and the window read the times of the files that are dated;
  the rest are not in either.
  The page opens at once and draws them again when the ages land.
  Until then the Modified within counts read “…”, a Recent list says it is reading, and
  the line that counts the files a filter keeps says so, as one more item of that line,
  which moves nothing; it says too why a read failed, and how many files could not be
  dated when some could not (a shallow clone, or a read that ran out of time), and the
  Undated group is named for each state.
- **Groups.** Age groups are disjoint bands cut from Modified within’s windows: Live,
  then Past hour, Past day, Past week, and Past month, each holding only what the
  windows before it do not, then Older.
  A Git revision adds a last group, Undated, for the files whose last commit its answer
  does not know yet, or at all: a shallow clone, a read cut by its budget, or a read
  still running. Its name says the time they are older than when the answer has one, as
  Undated, older than 2020-03-01, and the group is gone once every file is dated.
  A folder row in a group or a window is dated by the newest of the files that put it
  there, as its count is, and a submodule has no age and is in no age group.
  File type groups are Documentation, Code, Data, Archives, Media, and Other, which
  takes every file the registry does not recognize.
  A group the filters leave empty is not shown.
- **Sections.** Each section is a group heading in the menu group pattern, the group’s
  name with its file count beside it ([Heading Tallies](#heading-tallies)), over a full
  tree of the group’s members after the filters.
  The heading starts on the tree’s row inset, as a menu’s starts on its rows’, and names
  the section and its tree; sections after the first draw the divider above themselves.
  A file type section’s heading starts with its category’s icon
  ([File-Type Category Icons](#file-type-category-icons)); an age band names no category
  and has none. A folder opened inside a section lists only that group’s members.
  A section is a fixed heading that never closes, where the Pulls tab’s
  [stack group](#stack-groups-in-the-pulls-tab) is a row that opens and closes, and the
  difference is deliberate: a grouping splits the whole tree into sections, while a
  stack gathers some rows of one list like a folder.
- **Age inks.** By age, a section’s name takes its band’s [file age](#file-age) ink.
  Each elapsed band lies inside one age tier, so its name reads in the ink of every file
  age it holds and of Modified within’s row for that window; Older takes the oldest
  tier’s, and Live the Live ink, as Live’s row and badge do.
  Only the ink changes: the heading keeps its size, weight, caps, and tracking, and its
  tally stays muted, so the name is a band’s name and not an age.
  The section carries the route’s group id, so the ink is paint, keyed by that id in
  `static/styles.css`; `tests/test_tree_groups.py` holds the mapping to Modified
  within’s and to `AGE_TIERS`. File type sections keep the heading’s own ink.
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
  quiet period shows none of it; a scan the row is already showing keeps its words
  through the quiet period too.
  The scan row rather than a metadata line holds the words because a metadata line takes
  its line box the moment it is drawn: a choice answered inside the quiet period would
  push the tree down a line and back.
  A newer choice, a filter change, or No grouping cancels the load on its way at once,
  and its answer is never painted.
  Pressing a grouping’s row asks for that grouping ahead of the choice, and so does
  resting on it with the arrow keys for the dwell `GROUPS_PREFETCH_DWELL_MS` sets in
  `app.js`, where its reasoning is; a row the keys pass over on the way to another asks
  for nothing, since the server runs one grouped pass at a time and a pass for that row
  would hold up the one chosen.
  Opening the menu asks for nothing, since a reader chooses at most one grouping and
  often none. A file change keeps an answer asked for ahead rather than dropping it: the
  choice takes it, since it comes sooner than a new one, and then refreshes.
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
- **Width.** The row fits the default pane width at its widest, “No grouping” with Clear
  showing, in the default font set, in a Git checkout whose branch chooser shares the
  row; the measurements are beside `.nav-filter-bar-end` in `styles.css`. In a narrower
  pane, or in the system font set in a checkout, the row wraps, Clear and the chevron
  moving down together ([Navigation Toolbars Wrap](#navigation-toolbars-wrap)). The open
  drawer wraps the same way: at the default pane its three menus take its first line and
  Show ignored its second.

The server decides membership, order, and counts (`/api/tree?group_by=` and `?group=`,
`metabrowser/tree_groups.py`), pinned by
`tests/golden/cli-api-tree-groups.tryscript.md`; the browser’s requests and sections,
its prefetch and the keyboard’s dwell, and its loads’ lifecycle run browserlessly in
`tests/dom/files-group-by-session.js`, and its refresh in
`tests/dom/group-by-refresh-behavior.js`; and `tests/test_files_tab_chrome.py` measures
the row, the drawer, the numbers, the sections’ headings and their tallies, a refresh
after a write, and, with the grouped requests held, the wait: the trigger in the
choice’s frame, the dimmed tree and the scan row’s words, a refresh that waits,
cancelling, and the arrow keys asking only for a row they rest on, in Chrome.

The server reads every group from one pass over the index, at one index version
(`GroupedTreeQuery` in `inventory_engine/contract.py`), so a grouped tree costs about
one pass whatever the number of groups.
Two groupings asked for at once each take about twice as long, which is why opening the
menu asks for neither and the keyboard asks only for a row it rests on; opening a folder
inside a section costs what it does outside one.
The measurements are in
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#grouping-cost).

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

### File-Type Colors

A file-type family has one color wherever the app draws it: the File types table, the
Overview’s tracks and legend, and the Treemap.

**The registry names only the hue.** A family’s hue is declared in the type registry
([Family Fields](project/architecture/file-rollup-format/file-rollup-format.md#family-fields)).
A hue is tool-neutral and a color is not: lightness and chroma belong to the surface a
consumer paints on, a light background wanting one range and a dark one another, so a
registry that named finished colors would be naming one theme.
Where GitHub’s linguist names a color for the language, the hue is that color’s,
converted to oklch and unchanged, including where two of GitHub’s colors are close
together: moving a familiar hue to win a distance metric costs more than the collision
does. That is what makes the palette recognizable: Ruby is red because Ruby is red
everywhere. A family GitHub names no color for takes a hue whose painted color clears
every other family’s by the perceptual floor.

**Lightness and chroma are a band each theme owns.** Hue alone cannot separate a palette
this size, and GitHub’s own colors are told apart mostly by lightness and chroma, so
`linguist_color` is more than provenance.
Each theme paints inside a `ToneBand`, `LIGHT_THEME` and `DARK_THEME` in
`color_oklch.py`, and each family’s place in it is a lightness rank and a chroma ratio
derived from its upstream color; a family without one sits at the band’s center.
The module’s docstrings hold the derivation, the measured spreads, and what a band gives
up against a constant tone.

**Chroma is a target, not a guarantee.** The color function reduces chroma only as far
as sRGB needs, keeping the hue and the lightness, because a browser handed an
out-of-gamut `oklch()` clips it and moves both (`ToneBand.at`).

#### Declared Deviations

A family departs from where its upstream color puts it only by a declaration beside it
in the registry, never by a silent edit.
A deviating family keeps `linguist` and `linguist_color`, so its provenance stays
auditable, and adds `deviation`: prose saying why it left.
It may also set `lightness_rank`, which replaces its derived rank and may fall outside
`[0, 1]` to leave the band, and `chroma_ratio`, which replaces its derived ratio and
stays inside `[0, 1]`. Either one changes its own axis and leaves the other derived, and
either without `deviation` is refused, because moving a family’s place in the band is
the change that should never read as a typo.

Most deviations nudge a hue out of a collision and keep the color a reader knows: Swift
stays orange and Markdown stays blue.
TypeScript is the exception and leaves GitHub’s color for another: GitHub makes
TypeScript and Python both blue, a shade apart, so TypeScript is a saturated yellow and
Python keeps GitHub’s blue.
It declares a rank above the band, because a yellow at the band’s lightness is mustard,
and the top of the chroma band.
`devtools/check_file_type_colors.py` names TypeScript as the one family whose deviation
may leave its color rather than nudge it, and fails a deviation that moves a hue that
far without being named.
A deviating family keeps the rule a house hue has: its painted color clears every other
family’s by the perceptual floor, in every theme.

#### Finished Colors

The server ships finished colors.
`METABROWSER_SETTINGS.DISTRIBUTION_COLORS` carries each family’s distribution key with
its color on both themes, and `category-palette.js` writes both onto the element as
`--mb-distribution-color-light` and `--mb-distribution-color-dark`.
`.mb-distribution-mark` selects between them by theme and `.mb-distribution-other` takes
the neutral, so a theme change is a selector switch rather than a repaint.
The remaining tokens are `--mb-distribution-other`, `--mb-distribution-track`,
`--mb-distribution-track-height`, `--mb-distribution-segment-gap`, and
`--mb-distribution-ink-share`. Core owns these tokens and utilities; the folder plugin
owns File types and Treemap layout selectors.

Segments that sit beside one another are separated by a hairline of the page ground,
`--mb-distribution-segment-gap` wide, in `--viz-surface`, so two families of similar hue
read as two rather than as one wide band.
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

### File-Type Category Icons

**A file-type category is named one way wherever it appears: the category heading, gray,
all caps, bold, and tracked, led by the category’s icon in the same gray.** The icon is
the one its representative format draws, typically the category’s most important format:
Documentation leads with Markdown’s icon.
The heading draws it in its own ink, never the format’s color, because it names the
category and not a format.
A specific format, a family or an extension, keeps its own icon and its own color.

- **Type.** The heading is the label register category headings already read in,
  `--label-color`, `--label-font-size`, `--label-font-weight`, `--label-letter-spacing`,
  and `--label-text-transform`; the icon changes none of it.
- **Icon.** `.category-icon` in `styles.css`: `--icon-glyph` square, in `currentColor`,
  with `--category-icon-gap` between it and the name.
  A heading that starts on a row inset starts there with the icon, and the name follows.
  In Details the icon stands in its rows’ icon box, so the heading’s icon and name start
  where its family rows’ do.
- **Where.** Every heading that names a category: a section of Group by’s By file type
  ([Grouping the Files Tree](#grouping-the-files-tree)), each family section of the type
  chooser ([Groups Or Dropdowns](#groups-or-dropdowns)), and each group of File
  Overview’s Details table ([Aggregate Distributions](#aggregate-distributions)).

| Category | Representative | Icon | Why |
| --- | --- | --- | --- |
| Documentation | Markdown | `doc` | Markdown is what a repository’s documentation is written in: READMEs and guides. |
| Code | Python | `alignLeft` | Python leads the registry’s Code families, and every Code family takes its shape. |
| Data | JSON | `list` | JSON is a repository’s commonest data: configuration, manifests, and payloads; the tabular formats keep their own grid. |
| Archives | Archives | `copy` | Archives has one family, which holds every archive format. |
| Media | Images | `monitor` | Images are the media a repository holds most: screenshots, diagrams, and icons. |
| Other | None | `file` | Other is mostly files the registry does not recognize, so the plain file shape stands for it; its one family, Log files, would misname the rest. |

The table is `_REPRESENTATIVE_FAMILIES` in `file_type_filters.py`, and
`tests/test_category_icons.py` holds this copy to it.
The registry already draws each group’s families in one shape, the group’s `icon`,
unless a family declares its own, so a category’s icon is that shape:
`file_type_filters.py` refuses a representative that is not one of its group’s families
or that declares an icon of its own, and the choice and the shape cannot disagree.
Which format represents a category is presentation, as the display order is, so it lives
beside the categories and not in the registry, whose groups the File Rollup Format
fingerprints. The browser reads the icon as each group’s `icon` in
`fileTypes.displayGroups`, and a grouped tree’s answer carries it on each type group
(`/api/tree?group_by=type`, null for an age group), pinned by
`tests/golden/cli-api-tree-groups.tryscript.md`, and
`tests/dom/files-group-by-session.js` pins that each section carries it.
`tests/dom/file-overview-session.js` and `tests/dom/filter-controls-behavior.js` pin
that a Details heading and a menu heading lead with it.
In Chrome, `tests/test_files_tab_chrome.py` measures the icon’s size, ink, and place in
a menu’s headings and a section’s, and in a section’s after a refresh rewrites it, and
`tests/test_overview_legend_hover_chrome.py` measures it in Details.

Some places name a category without a heading, and keep their own style:

- The type chooser’s Groups section lists the categories as rows to pick, text-only as
  every aggregate row in it is ([Groups Or Dropdowns](#groups-or-dropdowns)): a row is a
  value, not a heading.
- The File type trigger names a selected category as its value, in the trigger’s words.
- The Overview legend’s Other is the families it does not name, not the Other category,
  and the legend and tracks name families, so they take the families’ colors.

### Aggregate Distributions

An aggregate distribution relates exact categories through one selected metric column in
a semantic table; the shipped
[Folder Overview plan](project/specs/done/plan-2026-08-12-directory-file-type-summary.md)
defines its first instance.
The metric cell presents an absolute value, a track normalized to that metric’s
population total, and a percentage.
A nearby exclusive control switches the entire table atomically between Files and Bytes;
it never leaves parallel metric columns competing with that control.
It is distinct from the broad `ft-*` identity system: several exact extensions may share
one file icon, while semantic families such as JavaScript and YAML need stable
distribution identities of their own.

The component uses the declared categorical palette
([File-Type Colors](#file-type-colors)), a neutral **Other** token, a track token, and a
named track-height token, applied through `category-palette.js`; no consumer copies or
composes a color. Inline percentage widths are allowed because they encode data rather
than theme. When the measure changes, the category set and colors stay; values, widths,
emphasis, and row order change as one update, and Other stays last and neutral.
A family’s color does not depend on which folder is open, so the Treemap agrees with the
table without coordinating.

The semantic table is the source of exact values, and a compact summary above it is what
a folder shows first: in the manner of GitHub’s Languages box, a legend of the largest
families under the population bars, each a dot in its color as tall as the tracks above
it, its bold name, and its muted share, with one neutral **Other** for the rest.
Which families it names is data, decided on the route by `file_type_legend.py`, whose
docstring has the rule: the largest families, at most `LEGEND_TYPE_LIMIT`, that are at
least `LEGEND_MINIMUM_SHARE_PERCENT` of the population, the share below which the table
folds a row into “N more”, so a family at exactly that share is named and shown.
Counting Other, the legend is ten entries at most.
Nine families and Other are never taken for one another by color: every family has a
color of its own, `MINIMUM_HOUSE_DELTA_E` or more from every other in both themes
(`devtools/check_file_type_colors.py`), Other’s neutral is several times that from every
family (`OTHER_CLEARANCE_FLOORS`, in
`test_other_is_clear_of_every_family_in_both_themes`), and the name beside each dot says
what the dot’s color does not.
A caption naming the population labels the legend and the table for assistive technology
only.
Legend items wrap whole: in a pane too narrow for a line of them a dot never ends a
line with its name on the next, no entry is cut or clipped, and they read in order down
the lines (`tests/test_overview_label_column_chrome.py`). In the Overview’s wide band,
where an expanded README’s table of contents becomes a rail, the legend leaves its place
under the bars for that rail’s track beside File Overview, KPress’s 3rem gap past the
card and its 15rem width, from the section’s top, one entry to a line with its share at
the line’s end (`.file-overview-body`, `overview.css`). Inside the track it takes the
table of contents’ own inset, so the two read as one column: each dot sits on the line
of the contents’ entry marks, each name starts where a level-1 entry’s text does at any
root font size, and each share ends where the entries do
(`tests/test_overview_readme_toc_chrome.py`; `tests/test_kpress_dependency_contract.py`
pins the KPress values the rail copies).
The switch follows the pane’s width alone, by the same container query, so in narrower
bands File Overview is as it was, and the bars and the map keep the card’s measure in
every band. The table sits behind a **Details** toggle, the same trigger and bold label
as an **N more** row, which starts closed on each mount and keeps its state through
repaints. Each group of rows is headed by its category, led by the category’s icon
([File-Type Category Icons](#file-type-category-icons)). Every row names its category
and reports absolute values and percentages; fills are not tab stops, carry no duplicate
tooltips, and are hidden from the accessibility tree, and no label relies on color or
sits on a fill. Membership comes from the File Rollup Format type definitions that
rollups, filters, and Treemap colors also use, by the format’s
[Logical Extension](project/architecture/file-rollup-format/file-rollup-format.md#logical-extension)
rule, and the row grammar, from family parents to **N more**, is in
`builtin_plugins/folder/file-type-summary-model.js` beside
`VISIBLE_ROWS_PER_SUBSECTION`. Type labels are bold as the row’s scan anchor.

Overview renders the README at the same measure a reader gets opening that file on its
own, with the same Markdown mount and pane gutter, and the panel’s width includes the
document inset so the card border, section rules, and surface panels share an edge;
`test_one_document_surface_has_one_set_of_breakpoints` holds this.
A README with a table of contents takes the whole column, as the opened file does, and
KPress’s rail sits beyond the card.
Below KPress’s wide band, KPress keeps a trailing gutter for the floating toggle, which
takes the card in from the column’s edge where the pane is too narrow for the card’s
full measure, so while that README is shown the section rules and surface panels leave
the same gutter and keep the card’s edge.
`tests/test_overview_readme_toc_chrome.py` measures the prose and rail against the
opened file, and the shared edge in each band.

The **File Overview** section begins expanded: one control row with the Files / Bytes
measure and the `.filter-check` **Show ignored** checkbox, the same as navigation’s,
then three tally rows, **Files**, **Ignored**, and **Total** set off by a hairline, then
the legend and the Details table, under no heading of their own, since they ask the same
question at a finer resolution, and last a compact treemap of where those files sit
([Folder Treemap](#folder-treemap)). Each tally shows one absolute value and a track
segmented by the top-level families in their colors, in one order across the three rows;
`buildFolderTotalsComposition` in `folder-totals.js` explains the three rows, the order,
and the pending fill.
The bars of the tallies and of Details start at one place, in every row, with Details
closed or open and with Files or Bytes.
What they stand to the right of is a label column of one width,
`--file-type-summary-label-width` in `file_type_summary.css`: as wide as the longest
label the table holds in practice, the Documentation heading and the No extension and
Markdown rows, measured in both font sets and recorded beside the token, and no wider,
so the bars sit as far left as those labels allow.
A pane too narrow for it keeps the column a share of the table, as it always was, which
is never wider than the width would be: no pane has its bars further right than before.
A label wider than the column, a plugin’s family name or a filename, wraps inside it and
moves no bar. The Treemap’s tally rows keep their share of the table.
`tests/test_overview_label_column_chrome.py` measures it, at widths either side of the
one where the column becomes one width, in both font sets.
Show ignored begins checked without a saved preference and changes only the population
the distribution counts.
There is one chooser and one checkbox, because both act on the same numbers.
A segment’s hover tooltip, the shared body-portaled one, names the family as Details
does: its category in the table’s label type (`.data-label`), over the family’s name led
by its icon, the glyph a Treemap cell of its files shows (the generic page for files
with no extension, none for Other types), then its file count and byte size.
A tooltip-bearing mark deepens or lifts by `--viz-data-mark-hover-filter`, as a Treemap
cell does, grows by `--viz-hover-grow`, and shimmers
([Hover Styles the Thing Under the Pointer](#hover-styles-the-thing-under-the-pointer)).
The hover marks what its handle names.
A segment names one value, its family’s share of its row, so pointing at it marks that
segment alone: its tooltip describes that value, and lifting the family’s other marks
would say it describes them too.
A family’s legend entry, its dot and its words, names the family, so pointing at it
marks every mark of the family on screen: its segment in each tally row that has one,
Files, Ignored, and Total, and, while Details is open, its own row’s bar there, not its
extensions’ rows, which are its parts and other values.
Details opened or closed under a pointer still on an entry, as a key can, marks or
unmarks that row as it appears or goes.
Either way the family’s entry is marked too, so the key answers with what it keys: its
dot lifts and shimmers as the marks do, and its name takes the family’s ink, the
family’s color mixed toward the text ink by `--mb-distribution-ink-share`, which keeps
4.5:1 for every family on both pages where the family’s own color would not
(`test_a_hovered_legend_entrys_ink_reads_for_every_family`). Nothing in the entry moves
or changes size. There is one tooltip, never one per mark, anchored on the handle the
pointer is on, as any tooltip sits by what the reader points at.
On the segment it names the family; on the entry, which shows the name, it gives the
file count and byte size alone, since restating the name adds nothing
([Tooltips Add Information](#tooltips-add-information)), of the family’s segment in the
tally row the legend’s shares are of, Total while Show ignored is on and Files while it
is off. The bars, the legend, and the table share one hover (`distribution-hover.js`):
the bars draw it on themselves and show the tooltip, the legend
(`distribution-legend.js`) on its entries, and the distribution on Details, so none
keeps a copy of another’s behavior.
The Treemap shows the same legend on the same hover ([Folder Treemap](#folder-treemap)).
Other answers no hover and is never marked: it is the families too small to name and the
files no family claims, each its own segment in its own place, so there is no one mark
to point at. The bars draw again whenever the folder’s sums arrive, which a changed file
sends. A segment under the pointer is replaced, and the browser enters its replacement;
an entry outlives the draw and hears nothing, so the bars draw its hover again
themselves. A legend rebuilt or emptied under the pointer lets go of the hover its entry
held, because a removed element never hears the pointer leave, and the browser enters
the rebuilt entry under the pointer.
In a window too short for the tooltip under the legend, the shell flips it above the
entry, onto the bars, where it can cover part of the segments it lifts; File Overview is
the first panel, so that takes a window about 330 px tall or less.
These tooltips add no tab stops, on a segment or an entry; the distribution stays the
accessible source. The Ignored row dims through `--dimmed-content-opacity`, as ignored
navigation and Treemap entries do.
The table keeps screen-reader-only headers and updates the metric header between Files
and Bytes, so assistive technology gets the relationships alignment gives sighted
readers.

Zero totals produce no colored fill, division artifact, or header-only table: a zero
metric uses the neutral track while the other stays meaningful, an empty population
shows the parent surface’s empty state, and a scope of only ignored files leaves the
distribution body empty, since the adjacent Show ignored already offers the action.

### Folder Treemap

Treemap is the hierarchy complement to File types, not a second composition summary.
It always lays out the bounded directory tree as folders and files; it does not offer a
Folders/Types grouping choice.
File types already answers which extensions make up the population, while Treemap
answers where space or file count sits and keeps folder and file cells navigable.

The map is one component (`treemap-map.js`) drawn at two sizes: the Treemap view, which
fills the pane, and a compact map at a fixed height under File Overview’s type breakdown
(`treemap-compact.js`). The compact map draws the same tree with the same cells, colors,
and tooltip, follows the section’s measure and Show ignored, and joins the section’s
hover, so a legend entry marks its family’s cells there too.
At both sizes the tree sits inside an outer box for the folder itself, labelled with the
folder’s name (`withOuterBox`), so the two maps of one folder match.
On the compact map, activating a cell opens the Treemap view: the outer box at the
folder, a folder’s cell at that folder, and a file’s or a remainder’s at the folder that
holds it. In the Treemap view the outer box opens nothing, since the view is already at
that folder.
It leaves out value lines and remainder glyphs, which its small cells cannot
hold. Its box follows the breakdown’s answer, so it is there or not from the section’s
first paint: it shows a skeleton while the index scans, and asks for its own tree only
once the index has settled; it is left out when the breakdown’s request failed, the
index stopped at its cap before finishing the folder, or the folder holds no files in
the population shown, since the breakdown above already says why.
A map whose own request fails keeps its box, says the treemap is unavailable, and tries
again with the breakdown’s Retry.

The map goes as deep as it has room for.
Both sizes ask the rollup for its deepest and widest tree, and the server spends its
node budget on the heaviest folders first (`inventory_rollup.py`), so the nodes go where
the map can draw them.
The compact map asks at the route’s default budget, which a map a few hundred pixels
tall does not outgrow.
The Treemap view asks at its largest, in the compact encoding, which sends a file as one
positional entry and which the view decodes to the ordinary tree before it lays it out
(`treemapFullRollupQuery` in `treemap-map.js`, `treemap-rollup-decode.js`). While Show
ignored is off it asks without the gitignored nodes, so the budget goes to the nodes it
draws. The layout fills the largest pending folder next, from a share of the remaining
cell budget proportional to its area, so the cells reach every large region of the map
rather than draining into the first folder drawn (`treemap-layout.js`). A folder with
room for its label is labelled, and nests under its label strip when it is tall enough
for a row of children too; only a folder too small for a label nests inside a thin
frame, with no label, and its files are still drawn.
Frames thin with depth, and a folder too small for one draws its children edge to edge,
so deep levels keep their area for cells (`frameDecay` in `treemap-layout.js`). A folder
whose children all fold into its remainder stays one solid cell.
A folder is sized for its header and frame as well as its contents, so a file’s area is
its share of the map’s value at every depth rather than shrinking by each folder’s
chrome around it: the layout weights each folder by its value plus an estimate of the
chrome its subtree draws, and corrects that estimate with one more layout on a map small
enough for it to be cheap (`chromeRounds`, `chromePasses`, and `chromePassMaxCells` in
`treemap-layout.js`, with their measurements).
A folder’s own rectangle is therefore larger than its value alone: its area is its
files’ and its chrome’s. Every cell lies inside its parent’s cell and inside the map’s
border. A folder’s children are laid out largest first, which sets every cell’s size;
children of equal value, as every file is by Files, sit by the color family their
extension belongs to, then by extension and name, so cells of one color sit together
(`compareChildren` in `treemap-layout.js`, given the palette’s families by the map).

The map paints its cells on a canvas rather than drawing an element for each, so it
draws cells down to a device pixel, up to `PAINT_MAX_CELLS` (`treemap-map.js`, with its
measurement), where an element per cell cost too much to build and tear down.
Its layers, bottom to top:

- **The paint canvas** holds every cell, snapped to device pixels so neighbours share an
  edge. A nesting folder paints its interior in its edge tone, and each child large
  enough draws one device pixel short, so the edge shows between neighbours
  (`treemap-paint.js`). A nested folder’s edge tone is the border tone deepened toward
  the muted ink (`.tm-nested-folder`), so every cell stands apart from its neighbours on
  any fill. Its colors come from probe cells styled as a cell is, so the palette, the
  ignored dimming, and the theme stay in the stylesheet.
- **The marks canvases**, two, hold copies of the marked cells’ pixels under the lift
  filter. A hover that marks other cells draws them on the canvas not shown, which fades
  in on the hover’s timing as the shown one fades out, so the lift eases in and out as a
  bar segment’s does; under reduced motion it is drawn at once.
- **The icons canvas** holds the icons of the cells too small for their names, each
  rasterized once for each size and color it is drawn at, since a map can hold as many
  such icons as cells.
- **The hover anchor** is a transparent cell over the cell under the pointer.
  It carries that cell’s shimmer and anchors its tooltip.
- **The labels** are one element per labelled cell, positioned in the map’s padding box.
- **The focus proxy** is the map’s one focusable control.

The map lays out to its padding box, and a label lies inside its cell and the map’s
border; `tests/test_treemap_containment_chrome.py` measures it, with the canvas’s fill
at each cell. A file’s name sits under its icon, and a file without room for both its
name’s smallest width and both lines shows its icon alone, so cells of one size draw
alike. The name ellipsizes in the width it has; a size shows only when the whole of it
fits, by the bound beside `VALUE_CHAR_EM` (`treemap-map.js`), and is otherwise left out.
Each icon is sized to its cell, as its label is, by `ICON_DEFAULTS`
(`builtin_plugins/folder/treemap-layout.js`): over a name it is a share of the name’s
size, and alone it is centered, a share of the cell’s short side, so a smaller cell
shows a smaller icon.
A cell too small for the smallest glyph shows nothing and names itself in its tooltip.
The icons are painted, not elements: a folder of a few thousand small files would
otherwise hold an element per file.
A folder has no icon, as its row in the navigation has none
([design-system-icons.md](design-system-icons.md)).

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
intact. In the Treemap view it asks again for the tree, with or without the gitignored
nodes, and keeps the map it has, laid out as Show ignored off, until that tree arrives,
so no folder is sized by totals whose nodes are missing; a view out of sight asks when
it shows. If the tree with the ignored files fails, the status line says the map shows
the others.

There is no separate color selector.
Every file maps its exact extension through the taxonomy’s distribution key, a folder
drawn as one solid cell maps its dominant extension through the same helper, and
remainder cells take the neutral Other color.
A nested folder, whose children are drawn inside it, paints its header and frame in the
neutral border tone (`.tm-nested-folder`): it usually holds many types, and its dominant
one would claim them all.
The File types panel and Treemap read the same declared palette, so a semantic family
keeps the same color across both views and across folders.
Modification age remains available in the tooltip; it does not compete with file type as
a second cell-color vocabulary.
Treemap derives a theme-aware surface wash and stronger border from that shared base
color so labels retain contrast; the Overview’s data bars keep the full-strength swatch.
Hover brightens the composed cell’s fill, so its contrast and hue relationship remain
intact: the marks canvas copies the marked cells’ painted pixels, and the lift filter
applies to the copy.
The edges between cells never change under a hover: they stay at their deeper tone, and
a hovered folder lifts its header and frame and leaves the edges between its children as
they are. There is no separate label hover surface.
It never raises or grows a cell: a folder is painted under its children, so raising it
would cover them.

Under the tally bars the Treemap shows File Overview’s legend, from the same builder
(`distribution-legend.js` and `buildFileTypeLegendModel`), on a row one line tall that
it holds while it has no entries, so at a width that fits the entries the map does not
move when they arrive.
In a pane too narrow for them the entries wrap, the row takes the lines they need, and
the map below moves down by those lines once and is measured again for the space left
under it. The map’s cells, its bars, and its legend share one hover
(`distribution-hover.js`), as File Overview’s do
([Aggregate Distributions](#aggregate-distributions)). Pointing at an entry marks every
cell painted its family’s color, the files of its types and the solid folders it is the
dominant type of but no nested folder, its segment in every tally row, and the entry,
with the entry’s counts tooltip.
Pointing at a cell or a segment marks it and its family’s entry, and a cell keeps its
own tooltip. Every marked cell lifts, and none grows
([Hover Styles the Thing Under the Pointer](#hover-styles-the-thing-under-the-pointer)).
Only the file or remainder under the pointer also shimmers, on the hover anchor, which
lies under the labels, so its sheen does too.
A family’s cells take the lift alone while the bars and the entry’s dot shimmer: a
family can hold every cell the map draws, and a shimmer per cell is an animation each.
The cost is measured beside the rule in the folder plugin’s stylesheet.
A nesting folder lifts without the shimmer, which would cover its children.
A layout replaces the cells: it lets go of a cell’s hover, which the browser enters
again on the new cell, and draws an entry’s hover again on the new cells.
`tests/test_treemap_legend_hover_chrome.py` measures it.

The complete visible rectangle of every folder or file is its pointer target, including
the uncovered header, gutter, and frame of a nested folder.
A canvas says nothing about what is painted on it, so the map answers the pointer from
the layout: a grid of buckets over the map lists the cells over each, and the pointer
names the cell painted at the device pixel under it, the deepest whose fill covers it
(`treemap-hit.js`), so a cell a pixel wide is the cell it names, and the edge between
two cells is their folder’s. An inert remainder cell does not fall through to its
parent. A hover lifts the same pixels: a marked cell’s own fill, and a marked folder’s
header and frame, never an edge between cells (`markOps`, `treemap-paint.js`). The
keyboard reaches every folder and file cell through the focus proxy, which the arrow
keys move in layout order and which stays on its cell when the map is laid out again and
which takes the cell’s accessible name, with the folder’s remainder named when it has
one; Enter or Space opens it.
One control rather than one per cell keeps the page’s focus order short and never makes
a button inside another.

Cell typography grows continuously with usable rectangle geometry.
The scale combines the short side with the square root of area, which lets a genuinely
large box grow while preventing a long, thin sliver from claiming display type.
Folder and file labels, and value labels, stay between the bounds in
`TYPOGRAPHY_DEFAULTS` (`builtin_plugins/folder/treemap-layout.js`). A folder’s label and
value stop at the navigation’s own sizes there, `folderLabelMaxPx` and
`folderValueMaxPx`: a folder’s name heads the files drawn inside it, and display type
over them competed with the files for attention.
A file’s label keeps growing with its cell.
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
Visible folder labels end in `/`, while file labels always carry the same file-identity
icon as the navigation tree, as tall as the name’s line.
The slash is a visual kind cue and is not added to the folder’s accessible name or path.
The accessible name preserves the cell name, kind, and visible value.
The tooltip names the cell as the navigation does: a file’s icon, its complete path,
which wraps inside the tooltip however long, then a folder’s file count and size or a
file’s size, and its age, through the navigation columns’ own formatters, hues, and
freshness classes (`mb.formatFileCount` and `mb.countClass`, `mb.sizeHtml`, and
`mb.ageLabelHtml`).

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
The history is the revision the Files tab shows, under the same revision row, and a
revision chosen there reloads the page on Commits at its newest commit
([The Ref Selector](#the-ref-selector)). `static/git-panel.js` (`landOnNewestCommit`)
owns the selection; `tests/dom/git-commit-history-session.js` runs it.

The bar is as wide as the pane and sits under the identity it belongs to and over the
content it switches.
A use site does not pad, recolor, or re-letter it.
In the navigation, a pane too narrow for its tabs wraps the bar between them
([Navigation Toolbars Wrap](#navigation-toolbars-wrap)).
`test_every_tab_is_the_tab_primitive` holds the markup, the stylesheets, and the tokens.

### Home

**The folder icon and name at the top of the nav link to Home, and `0` goes there too.**
Either shows the served folder’s home view as a fresh load of `/view/` does, from any
tab and whatever the reader was doing.
A reader who has wandered off into a pull request’s Changes, a file’s Source, or an old
commit gets the page back as it first came up.

Home resets everything a fresh load decides:

- **The main pane.** Files comes to the front, and the served root is drawn at its
  default view, Overview.
  A root already shown at another view, such as Treemap, is drawn again.
- **Every tab’s place.** Files and Pulls forget their last destinations, and every panel
  forgets its scroll. So Pulls next opens its list of open pull requests, a pull request
  opened from it opens on Conversation, and Commits lands on its newest commit, as it
  always does.
- **The Files tab.** Every filter and Group by go back to their defaults, and the filter
  drawer closes with no menu open.
  The tree is drawn again from the server’s answer, with the folders a first paint opens
  and no row selected, at the top of its panel.
- **The Pulls list.** Every stack opens, every pull request’s changed files close, and
  the Tab stop goes back to the first row, so `P` focuses it there.
  The list is drawn from the rows it holds, with no request.

Each panel resets its own part: the tab controller calls every registered panel’s `home`
(`static/main-tabs.js`, `goHome`), so a panel added later says what a fresh load draws
in it rather than relying on Home to know.
Commits has none: a switch to it always lands on its newest commit at its top.

Home keeps what a fresh load would only fetch again, or keeps itself:

- **The caches.** Files, folders’ rows, pull request records, pull requests’ changed
  files, and the history already read stay in memory.
  This is why Home stays in the page rather than reloading it: a reload draws the same
  page from nothing, and the next open would wait on the network.
  A pull request’s changed files the list has read open at once when its row is opened
  again, with the folders in them as the reader left them.
  Home asks the server again only for what it draws: the tree, as a change of filter
  does, and the root’s view, as a return to Files does.
  `tests/test_folder_home_chrome.py` prints each request and its time.
- **Preferences.** The theme, the fonts, the text width, a folder overview’s rollup
  choices, and the diff layout are kept across a reload too.
- **History.** Home is the reader’s own open of `/view/`. It pushes one entry, none when
  Files already shows the root at `/view/`, so Back returns to where the reader was, and
  a pull request’s page writes its place into its entry first.

Home uses a folder crumb’s hover surface and link-colored focus ring around the icon and
name. The [source kind mark](#source-kind-marks) keeps its own tooltip.
The link’s accessible name is “Home:” followed by the visible name, including the ref
and commit for a pin without a mirror.
It stays a link to `/view/`, so a modified or middle click and its context menu do what
they do on any link.
A plain click, or Enter on it, stays in the page.

[Repository Details](#repository-details) opens from the adjacent chevron.

`0` runs the name’s own click path, from anywhere a shell letter works, and never in a
text field ([Keyboard Shortcuts](#keyboard-shortcuts)). `static/main-tabs.js` (`goHome`)
makes every tab forget its place and calls each panel’s `home`; `app.js` (`goHome`,
`resetFilesTab`, `homeTreeExpansion`, `openHomeRoot`) resets the Files tab and draws the
root, and `builtin_plugins/github/pulls-panel.js` (`home`) resets the Pulls list.
`tests/dom/preview-pane-state-session.js` (`goingHome`), pinned by
`cli-ui-file-lifecycle.tryscript.md`, and
`tests/dom/github-pulls-stack-groups-session.js`, pinned by
`cli-ui-github-pulls-stack-groups.tryscript.md`, run that on the production code.
`tests/test_folder_home_chrome.py` checks in headless Chrome that a click, `0`, and
Shift-0 leave exactly what a fresh load of `/view/` shows, from a pull request’s Changes
tab, the Pulls list with its Tab stop moved and a row’s changed files open, a file’s
Source view, Commits, and the root at Treemap.
It also checks that the pane never blanks on the way, that the tooltip survives the
click, and that the name is called “Home: <folder>”.

### The Main Page’s Focus Ring

**With the main page focused from the keyboard, a 2 px `--link` ring frames it, over
anything the page itself draws.** The ring is on the frame (`.preview-frame::after` in
`static/styles.css`), not on the scrolling pane: the pane’s own inset outline painted
under a positioned box with a ground of its own, so a pull request’s tab bar covered its
top edge. It takes no press, sits under KPress’s floating UI, and does not print.
`tests/test_nav_collapse_chrome.py` samples a painted pixel at its top edge over a
positioned band.

### Hiding the Navigation Pane

**A chevron at the start of the main page’s foot hides the navigation pane, and so does
the Backslash key.** The page slides left over the pane to fill the window, and the
chevron turns to point right; a second press slides the page back and shows the pane as
it was. Shift-Backslash, which types `|` on a US keyboard, does the same, as Shift
changes no key ([Keyboard Shortcuts](#keyboard-shortcuts)); the key is read by the
character it types.
On UK and German keyboards, the key in that position types `#`, which
opens Quick Search for pull requests in a GitHub repository.

The chevron is the shared disclosure chevron in an icon button
([Every Icon-Only Control Is the Same Control](#every-icon-only-control-is-the-same-control)),
muted at rest with the hover surface, pointing left at the pane it hides.
It fills the main frame’s gutter, before the content’s edge, on the shortcut strip’s row
at the foot: centered on the strip below its rule, the line the strip’s keys are on
across the divider, so it reads as the strip’s last control.
It is a target of Up’s size, and the divider’s resize reach stops above the row, so a
press anywhere in it hides the pane.
Every page has it in the same place, and it stays there while the pane is hidden.
The strip moves up when a row under it shows, the scan’s progress or a mirror’s
freshness, so `alignNavCollapseButton` in `static/app.js`, in the shell’s eager path,
measures the strip’s row from the first paint and gives `--nav-shortcut-row-top` and
`--nav-shortcut-row-height` to the chevron and the divider alone; set on their shared
container, each change restyled the whole open document.
The stylesheet places the chevron from them, the gutter’s `--content-padding-x`, and
Up’s size, `--view-header-up-size`. It has no plate of its own, so the page’s edge and
the pane’s shadow show through it; only the hover surface fills it.
Holding Shift badges it with Backslash, over its inline end, as every icon button’s
badge sits.

The pane does not shrink.
Hidden, it leaves the layout, keeps its width under the frame, and is `inert`, so no Tab
stop or key reaches a control in it: `0`, the main tabs’ letters, and the filters’
numbers do nothing until it is shown, and focus in it moves to the main page.
Backslash stays live on the chevron, and closes a filter menu the pane held open as it
hides it. The frame keeps its full width for the whole slide and reflows once, at the
start of a hide or the end of a show, so a long document is laid out once per toggle;
the slide is a transform on the frame, which already carries one for KPress’s floating
UI. It takes `--motion-reveal`’s time and easing, and a press during a slide turns it
back from where the frame is, for the share of the time that distance is.
Under reduced motion the page moves at once.
The state belongs to the page and is not kept across a reload.

**With the pane hidden, a reading column is centered in the frame.** A column left at
the gutter put all the room the pane gave up at its end, beside the text, and the point
of hiding the pane is a calmer page to read.
A rendered document and a folder’s Overview sit in the middle of the pane, the same room
before them as after.
The document’s table of contents is part of that group.
A page with a top-level table in the Document view places the rail at the trailing edge
to make room for tables beside the reading column.
The header’s Up, icon, and title and the first tab move with the column, so the page
keeps one reading edge, and what is flush right, the header’s corner and the eyebrow’s
copy button, stays there.
A view whose body is not a column, source, a table, a diff, or a log, keeps the gutter
and the frame’s whole width.
Only in the wide band, a main view wide enough for KPress to dock a document’s table of
contents (`@container kpress-doc` in `markdown.css`): narrower, the card is nearly all
the pane holds, and with the pane shown every column starts at the gutter, as before.
The column glides to its place with the frame’s slide, from where it was drawn, rather
than jumping when the layout changes, and moves at once under reduced motion.

A view opts in by stating its column’s width as `--reading-unit` on the main view’s
children; the shell turns it into `--reading-inset` (`static/styles.css`), which the
header’s rows, the tab bar, and the body add to their start.
The Markdown plugin (`markdown.css`) and the folder plugin’s Overview (`overview.css`)
state theirs.

`static/nav-collapse.js` owns it, and `static/shell-keymap.js` binds the key.
`tests/dom/key-reveal-session.js`, pinned by `cli-ui-nav-collapse.tryscript.md`, runs
both on the production code, the column’s glide included;
`tests/test_nav_collapse_chrome.py` measures the chevron’s place and the slide in
headless Chrome with real keys, and `tests/test_reading_column_chrome.py` where a
centered column lands and how it glides.

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
  An address the pull request’s page writes reveals its row only when it names another
  pull request (`revealPullAddress` in `app.js`).
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
  another view of the file shown, another tab of the pull request shown, or one of its
  changed files, clicked or walked with `J` and `K`. The list stays on the reader’s row,
  not the pull request’s. Opening the item shown again, as Quick Search does, reveals it
  again, opening a folder or stack the reader closed since, even after a tab’s button
  kept the panel’s place.
  The reveal call says so itself (`again`): no state carries it from one call to the
  next.
- **A long folder draws only the page that holds the item.** A folder draws its first
  200 rows and holds the rest behind a row that shows them 200 at a time.
  When the item is among them, the reveal draws only the 200-row page that holds it.
  The rows before that page stay behind a “Show N more” row above it, and the rows after
  it behind one below it.
  Pressing either row draws its next page where the row was, so the folder still reads
  in order. When the selected row is below the row pressed, as the revealed one is below
  the row above it, the rows below stay in place, so the selected row stays in view.
  Otherwise the page grows down from the row, as at the end of a folder, and focus goes
  to its first row: a reader reading down reads on into it.
  A reveal therefore costs one page however long the folder is.
  Drawing every page up to the item instead took 2.75 s for the last of 10,000 files,
  and the cost grew with the folder (`mountTreePageAt` in `app.js` records both
  measurements).
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
- **A pull request the list does not draw moves the list to a filter that draws it.**
  Open and Closed hold only their state’s pull requests, and every list reads its
  windows from the newest, up to its display limit.
  A navigation to one that Open or Closed leaves out moves the list, as a reveal opens a
  stack the reader closed: to All, which holds every pull request, when All’s drawn rows
  reach it, so that a stack walk across open and merged pull requests stays on one list,
  and otherwise to the filter of its own state, which reaches as far or further.
  A navigation under All to one further down than All draws moves the list to its
  state’s filter the same way.
  Where it is comes from the catalog, by two one-row indexed reads: the pull request
  itself, and the newest, since no more pull requests than the difference of their
  numbers are newer than it (`readSought` in `pulls-panel.js`). The windows a list has
  read cannot say it: they do not tell an older pull request from one the filter leaves
  out, nor a catalog still being read from GitHub from one read to its end.
  While the catalog cannot say yet, the list stays and says nothing, and asks again at
  its next poll. One the catalog, read to its end, lacks is asked for again after a poll
  whose list says the catalog has read more, as it has when a pull request was opened
  since its last read, and placed then; an unchanged catalog is not asked again.
  A catalog that starts again, for a new reader or source, has not said what the old one
  lacked, so the list says nothing of it until the new one can.
  The list a navigation moved to reveals the row at the first read that brings it,
  though its first read failed.
  When the list moves while focus is on one of its rows, the revealed row takes focus,
  unless the reader has moved focus out of the list by the time it arrives.
  A filter the reader picks while a pull request is shown is theirs: the list says
  nothing of a pull request it leaves out, since the filter’s chip says what it holds,
  and a note that a filter leaves a pull request out reads as a row gone missing.
  The list reads on for the pull request, up to its display limit, and reveals it when
  it arrives. Only one the list still cannot show is named under its band: one further
  down than the list draws, “#8 is not among the pull requests loaded.”, or one the
  catalog, read to its end, lacks, “#8 is not in this list.”
  (`outsideText`). A page the reader scrolls in keeps the note until the page that
  brings the row.
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
Nothing in it is cut, scrolled out of reach, or cut short.** The pane drags down to its
narrowest supported width, and the system font set’s face is wider than the default
one’s, so no toolbar can promise one line.

The rule covers every toolbar in the navigation: the Files filter row, the Pulls
filters, the Commits tally, which stands in the toolbar slot, and the tab bar over them.
The Files row and the Pulls filters are one primitive, `.nav-toolbar-row` in
`static/styles.css`, which a plugin whose toolbar stands in the slot gives its row.

- **One line while it fits.** A toolbar whose controls fit one line is that line, and
  the toolbar slot’s height, `--nav-toolbar-height`. A toolbar wraps only when its
  controls do not fit, and never adds space when they do.
- **Where it breaks.** Between controls, in their order, each line as full as it can be,
  so a control moves down only when it must.
  The Files filters start with Group by.
  A mirror or checkout shows the [revision row](#the-ref-selector) above the filters,
  directly below the tabs.
  The trailing group, which takes the line’s end with an auto margin, moves down whole
  and stays right-aligned: Clear and the chevron on Files.
  The Commits tally breaks between its phrases, “12,345 commits”, then “begun 1y ago”,
  and the tab bar between its tabs.
  A segmented group in the cluster layout (below) is the one exception: it is one
  control drawn over several lines, and what follows it starts a line of its own.
- **Line spacing.** A row’s lines are `--nav-toolbar-line-height` tall, a chip’s height,
  and `--nav-toolbar-gap` apart.
  That is also the gap between controls along a line and above the first line and below
  the last, so a wrapped toolbar is a grid of one spacing and reads as one toolbar, and
  it grows by a line and a gap for each line it adds.
  Every control is one line tall: a shorter one is centered in a line’s height, and a
  taller one, such as a `.btn`, is held to it, so no line is cramped and none stands
  taller than the rest.
  An open drawer’s controls wrap on the same gap and are one line tall too, Show
  ignored’s checkbox centered in its line, and a closed drawer adds nothing under the
  lines. The Commits tally is text, so its lines are its line height apart,
  `--nav-metadata-line-height`, as any metadata line’s are; a tab is its own line, so
  the tab bar’s lines are a tab’s height apart.
- **A segmented group.** One that its whole line cannot hold joined takes the cluster
  layout until it can ([Groups Or Dropdowns](#groups-or-dropdowns)). Whether it fits is
  measured on a copy in the joined layout, so the answer at one width is the same
  whichever layout the group shows, and the two cannot alternate near the break.
  A change to its text, or its toolbar shown again on its tab, is fitted before it
  paints, and a change of size in the next frame, which a drag across the break shows
  for one frame.
- **Keys.** Wrapping keeps the controls’ order, so reading the lines top to bottom meets
  them in their Tab order, and their keyboard numbers stay theirs.

The width from which each toolbar is one line, in both font sets, and the widths at
which the Pulls Show group is joined, are measured beside the rules in `styles.css`. At
the narrowest pane, with a filter set, the Files row is three lines: Group by, then Show
ignored, then Clear and the chevron.
`tests/dom/nav-toolbar-wrap.mjs` holds a toolbar to this rule at every width from the
narrowest pane up, in both font sets: `tests/test_files_tab_chrome.py` the Files row in
each Group by and filter state, with its numbers, Tab order, and drawer at the
narrowest; `tests/test_github_pulls_stacks_chrome.py` the Pulls filters with three- and
four-digit tallies, and the Show group’s two layouts, its observers, the tab shown again
after the pane narrowed behind it, and their disposal; and
`tests/test_nav_metadata_chrome.py` the Commits tally and the tab bar.
`tests/dom/filter-controls-behavior.js` holds the fit and its observers’ lifecycle
without a browser.

### Navigation Metadata Line

Under each main tab’s toolbar, a line or two says what the list below holds and how
current it is: the Files totals, “12,797 files (413.8 MB)” over “+ 248,189 ignored (10.1
GB)”, and the filter’s remarks under them; the Commits tally, “10,044 commits begun 1y
ago”; and the Pulls count, “381 pull requests · 12 open”, with a connection line for
first load, incomplete results, and failures.
All of them are one component, `.nav-metadata` in `static/styles.css`. They were three
recipes, and the reader saw it: 13px text 6px under the Files filters, 13px text centred
in the Commits slot, and 12px muted text with no space above it under the Pulls filters.

- **Type.** `--nav-font-size`, the navigation column’s list size
  ([Type Scale](#type-scale)), in regular weight and `--text` ink, line height
  `--nav-metadata-line-height`, and tabular numerals, so a count that grows while it is
  counted does not jitter.
  A remark on the line above it, such as a filter’s count or a connection’s state or
  remedy, adds `.nav-metadata-note`, which mutes it and changes nothing else.
  Inside a line, spans carry only what they mean: the gitignored half is muted, an age
  is the [age primitive](#age), a repository name is `.repository-name`, and a count’s
  number is bold, `.summary-number`
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)).
- **Box.** The navigation column’s inset, `--pane-header-padding-x`, and
  `--nav-metadata-padding-y` above and below, with the band’s rule,
  `--nav-metadata-rule-width`, under it.
  The padding is derived from the slot’s height, the line height, and the rule, so one
  line of it is exactly the toolbar slot’s height, and on Commits, which has no toolbar
  of its own, the line stands in the slot and its text sits as far from what stands over
  it, the tab bar’s rule or a checkout’s revision row, and from the rule under it, as it
  does under the Files and Pulls toolbars.
  Consecutive lines are one band: padding above the first, below the last, and one rule.
- **Placement.** Every line stands in the fixed chrome over its panel, never in the
  panel’s scroller, so it stays in view while the tree or the list scrolls, and its rule
  runs the pane’s full width, as the tab bar’s and the toolbar’s do.
  On Commits the line is the toolbar slot; on Files and Pulls the lines are a band of
  their own directly under the toolbar, `.nav-metadata-band`, which the shell draws
  empty under each toolbar, the tab fills, and which shows only while its toolbar does.
  The scroller reserves its scrollbar’s gutter (`scrollbar-gutter: stable`) and clips
  what it holds at its padding box, so a line inside it ended its rule a gutter short of
  the pane’s edge, 11 px with classic scrollbars, at every pane width.
  While the panel says it could not load, the band gives way to that alert, as the lines
  went with it when they were the panel’s; they show again with the next list.
  The cost, accepted: a line that comes or goes while the reader has scrolled, such as a
  recency window’s note that its list may be out of date, moves the scroller’s top and
  the rows with it, by a line’s height.
  In the scroller, scroll anchoring held the rows still.
  Holding them from the band takes a script that watches the band’s height on every
  page, which the move out of the scroller did not add to the shell’s startup scripts.
- **Spacing.** `--nav-metadata-gap` between a line’s items and between the words of an
  item built of spans, about a word space and a half.
- **Pending.** A figure still being counted is the pending tally inside the span its
  figure will fill, so it sits across the middle of the line, where the text will.
  On Commits the server ships it so, and the tally replaces it in place.
- **The Files totals.** The tracked count is the first line and the gitignored count a
  line of its own under it.
  Each is one line in every pane: in a pane too narrow for it, its size is cut short at
  its end, as “+ 10,000 ignored (1001.4 MB)” is at the 180 px minimum, never wrapped,
  and its whole phrase is its tooltip, which the shell shows only while it is cut
  ([Tooltips Add Information](#tooltips-add-information)). So the band’s height is
  decided by whether it has the ignored line, never by the figures’ lengths.
  The shell inlines the root’s totals with its first rows (the root’s own entry carries
  them, so they cost nothing to read), and the band paints at its settled height in the
  first frame: two lines for a folder with something ignored, one for a folder with
  nothing ignored. A shell drawn before the walk finished the root cannot tell whether
  anything is ignored, so its band holds the ignored line with the shell’s pending
  placeholder (`.tally-pending`), shown only after the quiet period
  (`.mb-delayed-loading`), with its figures pending, and the count fills the held line
  in place. Once the root’s entry has totals, the line is drawn from them only, and every
  root upsert brings them current.
  The server’s tally, its pass over every file, fills the line only while the entry has
  none, and never with a provisional answer: mid-walk it can say “nothing ignored yet”
  of a folder whose ignored files the walk has not reached, and a tally answered after
  an upsert is older than it.
  A page keeps the ignored line once it has drawn it: when the totals say nothing is
  ignored, the line says so, “No ignored files”, in the same box, rather than go away
  and move the tree. A reload of that folder draws the one-line band.
  A folder that gains its first ignored file while it is open gains the line, as the
  pull request header gains its labels row with its first label ([Layout](#layout));
  that is the folder changing, not a count arriving late.
  The [Files totals layout record](project/qa/qa-2026-11-16-files-totals-layout.md)
  holds the measurements.
- **Height.** Each line reserves its own line box before anything arrives.
  While a line’s text fits the pane, a pending tally, a count still being taken, and a
  settled one are one height, and the Pulls lines are one height from loading through a
  failure. Text wraps only when it is longer than the pane, and then the band grows by
  the lines it needs: a Pulls remedy, which keeps its whole command, as the pull request
  header’s does, and the Commits tally in the toolbar slot, between its phrases, the
  slot growing with it ([Navigation Toolbars Wrap](#navigation-toolbars-wrap)); at the
  default pane width the remedies for an unreachable GitHub, a gh that is not signed in,
  and a missing gh each take a second line.

The built-in Pulls tab uses the class; its stylesheet lays out only the lines’ spans.
No stylesheet but the component’s sets anything on a line element beyond how a long word
in it breaks. `tests/test_nav_metadata_line.py` holds the markup and every shipped
stylesheet to that, however a rule is scoped.
`tests/dom/tree-summary-line-session.js` records what the Files line says in each state,
the held ignored line and “No ignored files” among them, and runs the reducer the shell
draws it from, `createRootTotals` in `static/navigation.js`, through what reaches a
page: a provisional tally, a tally older than an upsert, a Git revision.
`tests/test_files_totals_stable_chrome.py` records, in Chrome, every frame of the
navigation from the document’s start to settled, for a folder with ignored files and one
with none, with the tally answered at once and held, in both themes, in the default pane
and the narrowest, with the shell’s inlined totals taken out, and with a provisional
first tally; and reads each line’s tooltip, which shows only while the line is cut.
`tests/test_nav_metadata_chrome.py` measures, in Chrome, at the default pane width and
at one wide enough for every text: the Files totals settled, pending, counting,
filtered, with the outside-filter note, and with the stale recent-files note; the
Commits tally settled, as the server ships it pending, and failed; and the Pulls lines
loading, updated, unreachable, signed out, and with no gh; and the Pulls lead count cut
short with its state tally visible in a narrow pane.
It also holds every section rule on Files, Commits, and Pulls, the tab bar’s, the
toolbar’s, and the band’s, to the pane’s full width, at the narrowest pane, the default,
and a wide one, with the content under them overflowing its scroller and not.

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
  its metadata, diagnostics, breakpoints, table of contents, print button, and print
  behavior. Overview adds the shared section heading but does not override the document
  card. The card keeps its standard border and shadow at regular and wide document bands,
  then becomes borderless through KPress’s own narrow breakpoint.

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
The inset is declared once, outside any container query, because an inset that followed
the README’s would move the labels as the window widened.
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
a footer sentence. Without a README the Overview prints nothing of its own: Command-P
prints the line saying the view is not printable, and no print button is drawn
([Print](#print)).

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
surface carrying both shows the reader two tooltips side by side on different timers, so
the rule is enforced rather than remembered.

**No `title` attribute, no `.title =` assignment, and no `setAttribute("title", …)`,
anywhere the app owns the markup**: browser sources, built-in plugins, and the HTML the
server renders. `devtools/check_tooltips.py` fails the build on one, and runs in
`make lint`. Its exemption list names each exception and why: an iframe’s accessible
name, a rendered document’s own links and embeds, and a link whose card’s code did not
load, which gets back the title its author wrote.

| Need | Use |
| --- | --- |
| A short string | `data-tip-text="…"` |
| Rich content: counts, sizes, several lines | `MetabrowserTooltip.show(html, anchor)`, or `mb.tooltip.show` from a plugin |
| A link in authored text, in-app or to another site | The link card: register the link through the SDK, `metabrowser.previewLink` ([Tooltips on Links](#tooltips-on-links)) |

**A tooltip reads at body size**, `--tooltip-font-size`, and so do its subordinate
lines, which set no size and read at the tooltip’s: a file’s size and age under its name
are secondary metadata, muted, at the size of the text they accompany
([Type Scale](#type-scale)). The tooltip’s size may not be spelled as another token or
as a literal, and its lines may not set one.
Pointing a tooltip at `--ui-small-font-size` (the size of chips and controls) makes its
size a side effect of a decision about chrome, so the next adjustment to small chrome
text moves every tooltip with it.
A tooltip is prose the reader has stopped to read.
`devtools/check_tooltips.py` holds this alongside the rule above.

**A tooltip’s text stays inside it.** A long path or file name has no space to break at,
so every line of the tooltip may break anywhere (`.custom-tooltip` in `styles.css`), and
a name breaks anywhere already (`.tip-name`). `tests/test_treemap_containment_chrome.py`
holds it on a name with no break in it.

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
| The name of a glyph-only control or mark | Copy, print, the parent folder’s arrow, the theme and font segments, the filter drawer’s chevron |
| What a letter, badge, or color abbreviates | A Git file’s status letter, a compression badge, a front-matter error |
| The exact value behind a rounded or relative one | An age’s exact time on the pull request page; a tree row’s exact date, a folder’s other total, and the exact bytes of a size its chip rounds |
| What a control does that its words do not say | The ref selector’s “Switch branch or tag”, the HTML preview’s “Open as full page” (its own tab, still sandboxed), a View file control’s commit, a fallback layout’s reason |
| The whole of something cut short | A chip’s full name, a crumb’s own name, a diff file bar’s path, the page title past its two lines, a pull request header’s Diff summary with its breakdown cut short |

**The Pulls column has none.** A pull request’s row, a stack’s row, and their parts
carry no tooltip: the state icon’s name, a stack place’s stacks, and a stack row’s
counts are their accessible names, and the age’s exact time and a title cut short are on
the page the row opens.
A pull request’s changed files under its row keep the tooltips the tree gives a file:
its full path when its row shows only its name, “not in this comparison”, the name it
was renamed from, and what a folder’s sums leave out, the counts alone.

**Restating is not adding.** A “Show ignored” check, in the Files filter drawer and a
folder’s rollup, has no tooltip, as its label says it; nor has the treemap’s parent
button, which shows the folder it opens; nor a merge’s arrow, beside the two names it
would restate; and a crumb’s tooltip is its own name, cut short, not the path the trail
already shows. A Files tree row’s tooltip leaves out what the row shows: its name, and
the size or file count its chip holds, where the chip shows it exactly, as it does a
count and a size under 1,024 bytes.
It gives the exact date, a folder’s other total, and the exact bytes of a size the chip
rounds, “1,234 bytes” where the chip reads “1.2 KB”.

The shell holds the repeat case.
A `data-tip-text` that is its element’s own text, in any case and spacing, shows only
while that text is cut short, by an ellipsis or a line clamp, so a surface may give an
ellipsizing element its full text as a tip and the reader sees it only when the ellipsis
hides some of it (`tipAddsInformation` in `static/app.js`). A tip that is the text of a
box inside the element, as a changed file’s row holds its name beside its status letter
and counts, shows only while that box is cut short.
`devtools/check_tooltips.py` fails a literal tip that is its element’s literal text.
`tests/dom/github-pulls-stacks-chrome.mjs` checks the shell’s rule in Chrome, through
the document’s own listener and the tooltip it shows, on a changed file’s row among
others, and checks that the Pulls column carries no tip.

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

A rebuild may focus the replacement of a control that left the document.
When the reader has pressed neither a key nor a pointer button since the old control
lost focus, the replacement keeps the pointer’s tooltip if its anchor still exists.
For example, refreshing the Files filter bar leaves a tree row’s tooltip in place while
the pointer remains over that row (`hideTooltipOnFocus` in `static/app.js`).

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
it describes: in a stacked bar or a treemap, where the annotated elements are adjacent
and small, that is the only question the tooltip exists to answer.

`mb.tooltip.show(html, anchor)` takes the element, and there is deliberately no
`move()`. The controller centers the tooltip under its anchor, flips above when there is
no room below, and clamps to the viewport.
Calling `show` again with the element whose tooltip is up is how a surface says “still
here”: it cancels a pending hide and leaves the tooltip exactly as and where it is.
Calling it again for an element whose tooltip still waits out its delay gives that
tooltip the newer markup and keeps its time, so what a surface learns during the delay,
such as a link card’s title, appears on schedule with it.
Only the element whose markup is up is still here: a pointer that moves straight from
one element onto the next, within the first one’s fade, gets the next one’s tooltip at
the next one’s place, however often the next is announced again, and never the first
one’s (`tooltipShown` in `static/app.js`). `tests/dom/tooltip-anchor-session.js` holds
this on the shell’s own code, for a link card and for `data-tip-text`, and
`tests/test_link_card_chrome.py` holds it in Chrome on a document’s links.

**A tooltip that is up does not take new markup.** What a surface learns once its
tooltip is up waits for the tooltip’s next appearance.
New markup in place would not move the box, but it would change the box’s size: one that
grows wider from where it was placed is no longer centered on its anchor, and one
flipped above its anchor grows down over it, while placing it again moves it.
Either breaks this rule, and the lines the reader is partway through would shift with
it. A link card’s title that arrives after the card is up is its provider’s to keep, and
the next rest’s card says it from the pointer’s arrival
([Tooltips on Links](#tooltips-on-links)).

### A Surface Puts Away Only Its Own Tooltip

**A surface that repaints or is disposed puts away the tooltip it showed, and no
other.** `mb.tooltip.hide(within)` hides the tooltip when its anchor is `within` or
inside it, whether the tooltip is up or still waiting out its delay.
It also hides a tooltip whose anchor has left the document: that tooltip belongs to no
surface on the page and would never hear the pointer leave, so a view’s `hide(root)` at
disposal still puts its own away after its markup is gone.
A tooltip shown with no anchor is inside no element, so only a bare `hide()` puts it
away. `MetabrowserTooltip.hide(within)` is the shell’s form of the same call.
Without `within`, `hide()` puts away whatever tooltip there is, which is what a pointer
leaving a surface means, but one in the nav’s header: the header is the shell’s chrome,
which no view draws, so a view’s hide never takes the root kind mark’s tooltip
([Home](#home)).

The page has one tooltip, so a surface that calls `hide()` to clear its own puts away
another surface’s too: the folder view’s totals draw again whenever the folder’s sums
arrive, and a bare `hide()` there would take away a hovered Files tree row’s tooltip, or
keep it from appearing, each time the folder view beside it updated.
The folder view’s totals and treemap and the Commits history hide within their own
element when they repaint or are disposed.
File Overview’s totals also show a tooltip anchored outside their element, on the legend
entry the pointer is on, and put that one away by the entry it is anchored on
([Aggregate Distributions](#aggregate-distributions)).
`tests/dom/tooltip-anchor-session.js` holds the rule on the shell’s own code, and
`tests/dom/files-tab-chrome.mjs` checks it in Chrome on a tree row while the totals
redraw and the filter bar rebuilds.
`tests/dom/folder-totals-view-behavior.js`, `tests/dom/folder-plugin-behavior.js`,
`tests/dom/treemap-not-indexed-session.js` and `tests/dom/git-panel-behavior.js` check
that each of those surfaces passes its own element.

### Tooltips on Links

**Every link follows one rule for its tooltip, by where it goes and what its words say,
on every page.** A link’s words in authored text are the author’s, and say nothing of
whether it leaves the app; the app’s own chrome names what it opens.
A page with no GitHub identity, a plain folder’s or a checkout with no github.com
remote, keeps the rule too: its documents’ links to files and folders, and its links to
other sites, have their cards.
A pull request’s, a stack’s, or a commit’s card exists only where a repository identity
makes such a link open here.

| Link | Tooltip |
| --- | --- |
| Opens a page in Metabrowser, in text whose words say nothing about what it opens (rendered Markdown, a pull request’s text, a Guided Review note, a commit’s message, a rendered diff) | The **link card**: what it opens, its title where known, and that it opens here |
| Leaves for another site, in the same texts | The link card’s one line saying where it goes, “Opens example.com in a new tab”, with “in a new tab” only where the link opens one |
| The app’s own chrome, whose text names what it opens (a Pulls row’s title, a crumb, a Files row) | None, as [Tooltips Add Information](#tooltips-add-information) says |

An outside link has a card because its words do not say where it goes, and nothing else
there does: the macOS app’s web view has no status bar to show its address, and the
[External GitHub Links](#external-github-links) mark is only a GitHub address’s. The
card names the host the address goes to, as the browser follows it from the page, so a
link whose words or user name name another site still says which one it opens, and an
in-app card’s “Opens here in Metabrowser” reads against it.
An address the browser reads as one of the page’s own, such as `http:example.com` on an
`http` page, leaves for no other site and has no such card.

The card is the app’s one tooltip
([One Tooltip, and It Is Ours](#one-tooltip-and-it-is-ours)), so it keeps every rule
above: it appears on pointer rest and never on focus or a touch
([Tooltip Input Modality](#tooltip-input-modality)), and a press or a focus while the
pointer rests on the link ends that rest, so nothing it asked for brings the card back
(`endOnInput` in `static/link-previews.js`); placed on its link and holding still
([A Tooltip Holds Still](#a-tooltip-holds-still)), and the surface that drew the link
puts it away
([A Surface Puts Away Only Its Own Tooltip](#a-surface-puts-away-only-its-own-tooltip)).

**Its lines**, in order, using the tooltip’s own content classes, as a Files row’s
tooltip does:

1. **What it is**, in `.tip-name`: “Pull request #12”, “Stack #3”, “Commit a1b2c3d” (the
   short commit ID, [Short Commit IDs](#short-commit-ids)), the path of a file or
   folder, a folder’s ending in `/`, the root by the name its
   [view header](#view-headers)’s title gives it, the served folder’s own, with or
   without a repository identity and whatever the repository is called, from the one
   function both read (`servedRootName` in `static/app.js`), or “Pull requests”.
   A link to a tab or a changed file names it after the identity: “Pull request #12 ·
   Changes · docs/guide.md”.
2. **Its title**, when the app knows it: a pull request’s title, a commit’s subject, a
   stack’s top member’s title, drawn as every title is ([Titles](#titles)).
3. **The author’s title**, when the author gave the link one, in quotation marks, as the
   author’s words and never the app’s.
4. **A detail**, in `.tip-detail`, when its data has one, and for each image inside the
   link that the page did not load, “Image from” the address it would have loaded.
5. **Where it opens**, in `.tip-detail`, always: “Opens here in Metabrowser”, or, for a
   link to a branch, which opens whatever the page serves rather than what it named,
   what that is: “Opens in the served working tree” on a folder’s page and “Opens at the
   served revision” on a pin’s or a mirror’s; or, for a commit the Commits panel found
   the repository lacks, “Not in this repository”.
   The words are `OPENS` in `static/link-previews.js`. Only a commit is ever called
   missing. A file’s or folder’s card says where it opens whether or not the page lists
   it, since nothing the page holds is every path a link can open: a served folder’s
   Quick File catalog leaves out hidden, gitignored, and symlinked files that the folder
   still opens, and a pin’s lists no folder, though a link with no closing slash can
   name one (`knownPath` in `static/link-preview-providers.js`).

A line that is the link’s own text, in any case and spacing, or a line above it, is left
out: a card never says its link’s words again, as a Files row’s tooltip leaves out the
row’s name. The first line the card keeps leads with the object’s mark, so a card whose
identity is its link’s text still shows its state.
A card that quotes its author keeps its identity first even then, so the author’s words
never stand where the app says what the link opens.

**An outside link’s card** is one line in the tooltip’s own ink, where it goes, then its
author’s title, quoted, and no mark: its object is another site’s, of which the app
knows nothing more.

**The mark** is the [icon catalog](design-system-icons.md#git-and-github-objects)’s for
the object: a pull request’s state glyph only where its data gives the state, and the
neutral pull request mark where only its address is known, the two marks
`decorateExternalLink` gives a pull request’s address, since the address alone never
establishes a state; a stack’s `layers`; a file’s type, from `fileTypeIcon`. A folder
ends in `/` and a commit is its ID, as the catalog draws neither.

**An author’s title is folded in.** A trusted Markdown link can carry its author’s
`title`, an in-app link’s or an outside link’s, and so can an image inside it, as
`[![d](d.png "Its title")](x.md)` writes one.
The surface that registers the link takes every title off the link and what it holds,
and hands the link’s own, or else the image’s, to the card, which quotes it on its own
line after the identity and the object’s title, and never twice.
A title is also what assistive technology reads of a link, its name where nothing else
names it and otherwise its description, so the titles leave through the SDK alone
(`takeAuthorTitles` in `static/plugin-sdk-views.js`), which keeps the card’s for it: as
the link’s `aria-label` where it has no words, `aria-label`, or image `alt` of its own,
and otherwise as its `aria-description`, unless that says its name again, never in place
of one the link already has.
When an image’s title supplies its accessible name, that name stays on the image as
`aria-label`. Wherever the link’s card ends, when it is forgotten, its text disposed, a
later registration gives it none, or the card’s code does not load, the SDK gives back
exactly the titles it took and takes off only what it added (`giveAuthorTitlesBack`), so
the link is as its author wrote it.
An image the page does not load is a chip whose own tooltip says its address
([Images the Page Does Not Load](#images-the-page-does-not-load)); inside a link with a
card, the card takes that tooltip off the chip as the link is registered, gives it back
if the link loses its card, and says the address itself.
So the reader never sees two tooltips, and moving from a link’s words onto its image
changes nothing.

**Its timing.** The card is asked for as soon as the pointer arrives and appears on the
tooltip’s own appear delay, `TOOLTIP_APPEAR_DELAY` in `static/app.js`. Once the pointer
has rested for the tree’s own hover delay (`INTENT_MS` in `static/link-previews.js`,
equal to app.js’s `FILE_PREFETCH_HOVER_DELAY_MS`), the card’s data is read and what the
link opens is prefetched, from reads the app already makes for that object, all from its
caches.
A title that arrives while the tooltip still waits is shown with it, on the delay
the rest began; one that arrives after the card is up is its provider’s to keep
([A Tooltip Holds Still](#a-tooltip-holds-still)). The card’s registry keeps no answer:
each provider keeps what it reads for as long as that stays true, reads again what
failed or was not yet known, and says what it keeps as the pointer arrives, so a card
never says what the page knew once and no longer does.
At most one read and one prefetch are in flight, and a newer rest waits for them rather
than aborting them, since an aborted request counts against the page’s `fetch_aborts`
budget
([performance budgets](../explorations/performance-loop/performance-budgets.toml)).

**One renderer draws every card.** A surface registers each link it draws through the
SDK, `metabrowser.previewLink`, and puts its links away with `disposePreviews`
([docs/plugins.md](plugins.md)), never through the module’s window global; it never
draws a card. `card` in `static/link-previews.js` draws every one from data, escaping
every value, and each kind’s provider gives that data as plain text, never markup.
The card’s code loads only at a page’s first rest on a link it registered, so a page
whose pointer rests on none fetches none of it, and that first rest still shows its
card, its appear delay counted from the code’s arrival (`previewLink` in
`static/plugin-sdk-views.js`, and `server.py`’s `link-previews` bundle, which has the
measurement). `devtools/check_tooltips.py` fails any other browser source or stylesheet
that writes the card’s classes or its words for where a link opens.
`tests/dom/link-previews-session.js` holds the lines, the timing, and the input modality
on the module’s own code and app.js’s tooltip, and `tests/test_link_previews_js.py`
holds its invariants; `tests/dom/link-card-integration-session.js` runs app.js’s tooltip
and its delegated listeners, the resolver, the registry, and the providers on recorded
answers together, and `tests/test_link_card_integration_session.py` holds the rules
across those boundaries.
`tests/dom/link-preview-loader-session.js` holds what a link registered before the
card’s code loads does, on pages with no GitHub identity among them, and what assistive
technology reads of a titled link while it has its card and after, by the rules Chrome’s
accessibility tree follows for the same markup, and
`tests/test_link_preview_loader_session.py` its invariants.

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

- activating an open menu’s trigger closes it once, with the same result for pointer,
  keyboard, and accessibility actions;
- a press or activation outside both the trigger and panel closes the menu and leaves
  focus on the reader’s destination;
- pointer and keyboard triggers reach the same controller and state;
- triggers expose the appropriate accessible name, `aria-expanded`, `aria-controls`, and
  `aria-haspopup` value;
- the interaction that opens a surface cannot dismiss it in the same event sequence;
- scrolling inside a bounded overlay does not dismiss it;
- closing from within the surface restores focus to the connected trigger or a
  documented connected fallback;
- modal background content cannot receive pointer, keyboard, or assistive-technology
  interaction while the dialog is open; and
- `dispose()` removes portals, scrims, registrations, observers, and listeners and
  restores any focus, trigger, or inert state it changed.

### Every Menu Closes Alike

Every menu closes the same way, wherever it is and whoever draws it: the Files tab’s
Group by and filter dropdowns, every other filter bar’s, the branch chooser, the gear,
the root’s details, a ref’s action menu, View on GitHub’s menu, a pull request’s stack
menu, and a table’s column menus.

- **A press or a tap outside** the menu and its trigger closes it, and the press goes on
  to act on what it landed on, as a press beside the branch chooser always has.
  A press inside the menu leaves it open, and so does a drag that starts inside it, as
  in selecting a field’s text, and lets go outside it.
- **A second press on the trigger** closes it, through the trigger’s own toggle.
- **Escape** closes it and gives focus back to its trigger.
  An Escape that a surface above the menu took first, such as Quick Search’s, closes
  only that surface, and one held with Command, Control, or Option is the browser’s.
- **Focus arriving outside** the menu and its trigger closes it, as does the window
  losing focus, to another application or to a frame in the page, such as an HTML
  preview, whose presses never reach the page.
  Focus that goes nowhere, as when the focused row is removed, leaves it open.
  Focus that a press in the menu or on its trigger moves is that press’s own and closes
  nothing: WebKit, the macOS app’s engine, focuses no button on a press and gives focus
  to the nearest ancestor a press can focus instead, which for a menu in a view is the
  preview pane. A menu opened with focus outside it, as that press leaves it, takes focus
  to its trigger, so a tree redrawn under it that puts focus back on its row does not
  close it. A press is over at its click, at the next press, and at any key.
  One that brings no click, as on a disabled row, is over a task after a mouse’s or a
  pen’s button comes up, and at once where the browser takes it for a scroll or a
  context menu, so focus that arrives outside afterwards closes the menu.
- **Opening one menu closes any other**, so at most one is open.

A press inside a filter bar beside its open dropdown closes the dropdown once the
control it landed on has acted: on the control’s click, or a checkbox’s change, since
the bar is redrawn as the dropdown closes and would otherwise take that control from
under the press. So a press on the drawer’s chevron opens the drawer, a press on Show
ignored turns it off, and a press on another dropdown’s trigger opens that one, each
closing the dropdown that was open.

A filter bar answers for every dropdown inside the element it is bound to
(`filterControls.bind`), so each control is bound by itself, and never a region that
holds another bound control: the outer binding would take that control’s open dropdown
for its own, and opening it there closes it for the control.
A diff binds each file’s Rendered and Source chooser by itself for that reason, since
the diff’s toolbar holds the File type menu.

The behavior is one helper’s, `metabrowser.menus.dismissible` (`static/menus.js`,
reached through `static/filter-controls.js`), and a plugin’s menu uses it too
([Menus](plugins.md#menus)). A menu says how it closes and which nodes are its own; the
helper listens on the document only while a menu is open.
`tests/test_menu_dismissal.py` fails a `.menu` surface that does not close through it,
`tests/dom/menu-dismissal-session.js` walks each rule without a browser, and
`tests/test_menu_dismissal_chrome.py` presses each menu in Chrome.

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

### The Ref Selector

A served mirror or a served checkout has a revision row directly below the tab bar,
above the Files filters, including Group by, and above the Commits tally
(`static/source-ref-selector.js`). The row names what the page shows in one form: a ref
alone, and, for a checkout’s files on disk, **Working tree** and the branch they are on.
The row has two targets, and the same two whatever the page shows:

- **The branch or tag chip** names the ref the page shows, or, on a checkout’s working
  tree, the branch its `HEAD` is on.
  Click its name to open that ref’s [action menu](#action-menu).
- **The standalone down chevron** opens the revision chooser.
  Its tooltip and accessible name say “Switch branch or tag”.
  The `W` shortcut opens the same list.
  It remains visible beside the chip and keeps its open highlight while the chooser is
  open. The list spans the pane to give ref names, commit IDs, and ages room.

The chooser has a tab for each list, a filter box, and one row per ref.
A mirror’s tabs are **Branches** and **Tags**, and a checkout’s are **Working tree**,
**Branches**, **Remotes**, and **Tags**.

- **The list opens on the tab that holds what the page shows** (`openKind`): the working
  tree’s on a page of the files on disk, and a branch’s, a remote-tracking branch’s, or
  a tag’s own list on a page of that ref, where its row is marked current.
  A commit with no ref, or a pull request’s head, which no list holds, opens on
  Branches. It opens there each time, whichever tab it was closed on.

- **One choice heads Files and Commits.** The server serves one source at a time, and
  both tabs show it: Files its files, and Commits its history, from the chosen commit,
  or, on a checkout’s working tree, from `HEAD`, its upstream, and the trunk refs
  ([Source Sessions and Pins](project/architecture/arch-source-sessions-and-pins.md)).
  So the row is one element with one chooser, mounted once, which `activateNavPanel` in
  `static/main-tabs.js` shows under both tabs.
  The two tabs cannot name different revisions, and a tab switch neither resets the row
  nor draws it again; it only closes an open list, as each tab’s own menus close.
  Pulls has its own scope, and the row hides there.

- **A switch keeps the reader on their tab.** Chosen under Files, the page reloads on
  the same file or folder in the new revision when it has it, else at the root.
  Chosen under Commits, the page reloads on Commits at the tab’s own landing, the newest
  commit of the new history, as a press on the tab lands (`switchTo`).

- **A ref’s row is its name, its commit, and its age.** The name is its
  [chip](#branch-chips), the commit is its [short ID](#short-commit-ids), and the age is
  `MetabrowserFormatters.age` in the compact style, in its tier’s ink, with the commit’s
  time as its tooltip ([Age](#age)). A tag’s age is its commit’s. The ID is the size of
  the row’s text, as an ID is everywhere.
  The ages end the rows in one column, so the IDs line up.
  A pin that names no ref puts “Commit:” and the same face beside the chevron.

- **A commit reads the same wherever a line names it.** The revision row, the chooser
  rows, and a mirror’s line about the commit its branch moved to show it by the rule in
  [Short Commit IDs](#short-commit-ids).

- **The revision row names the ref.** The navigation heading remains a Home link named
  for the repository or checkout folder.
  The chooser’s rows show the short commit IDs.
  A pin with no mirror shows its ref and short commit in the heading.

- **A branch that is a pull request’s head shows the pull request, on a second line.**
  The row’s own line, the chip, its badge, its commit, and its age, is every row’s;
  under it goes the pull request: its [state’s icon](#a-pull-requests-state) in the
  Pulls tab’s shape and hue, its [number](#pull-request-numbers), and its
  [title](#titles), bold in normal text ink and cut at the line’s end, with the whole
  title and any other pull request of the branch in the row’s tooltip.
  A branch with several shows the open ones first and then the newest, and counts the
  rest, “+1”, in the muted ink; the row lists the first `REF_PULLS_PER_ROW` of them and
  says how many there are, so a branch with dozens is no larger a row, and the others
  are named for assistive technology in the row’s description as well as its tooltip.
  Only a pull request from the repository’s own branch is its branch’s: a fork’s branch
  of the same name is another branch.
  A tag, which no pull request has for its head, never has the line, and a pull
  request’s `refs/pull/<n>/head` is not listed as a ref of its own: it is the branch’s
  pull request, and a page served on one says “Pull request: #7” in the revision row.
  The pull requests are what the repository’s provider has cached, so the list never
  waits for GitHub: a list opened before they are cached shows none, asks again every
  `PULLS_POLL_MS` while the server fills them, and its rows gain the line as the pages
  arrive. The filter box then says “Filter branches or pull requests” and finds a branch
  by its pull request’s number, `#` and the start of one, or by every word of its title,
  as well as by its name; “#” alone lists the branches that have one.
  While the server has cached only some of the pull requests, the list says under a
  filter’s finds that a number or a title may match more branches.
  What arrives while the list is open changes what the reader sees as little as it can:
  an ask that finds the listing unchanged draws nothing, so focus, a tooltip, and a
  press in progress stay where they are, and one that finds pull requests for rows the
  list has patches them into those rows.
  The rows above the view grow when they gain a line, so the list is scrolled to keep
  the row at the top of its view where it was, a list at its foot at its foot, and a
  focused row in view (`anchoredScroll`). The icon is the GitHub plugin’s, which the
  list loads on demand and draws the rows with once it has; the slot is the icon’s width
  from the first frame, so nothing moves.

- **The list holds every ref and draws only the rows near its view.** The branch lists
  put `main`, `master`, their remote-tracking counterparts, and known default branches
  above other branches.
  Each group sorts newest first by the age its rows show.
  Tags sort newest first.
  The lists state no count because they hold every ref.
  Each row is placed by its offset over a box as tall as the whole list (`rowOffsets`,
  `ROWS_OVERSCAN` and `drawWindow` in `static/source-ref-selector.js`), and a row has
  one of two heights, with a pull request or without, each measured by a row drawn out
  of sight, so nothing else in a row may make it taller than the rest of its kind: the
  badge fits the row’s line, and the pull request’s line is one line of
  `--nav-metadata-line-height`, however tall the glyphs of its title are: an emoji or a
  Japanese title falls back to a font whose `normal` line is taller, which made the row
  2 to 3 px taller than the list places it.
  A row with no pull request is as tall as every row was before the line existed.
  The row that takes Tab stays drawn however far the list scrolls from it, so focus on
  it is never lost. Branches and Remotes open at the top, with their first row as the
  initial Tab stop. Tags opens scrolled to the served tag when it holds it.
  The `ul` says `role="list"`, which WebKit drops from a list drawn without markers.
  `tests/test_ref_selector_long_list_chrome.py` measures in headless Chrome over
  thousands of branches that the rows are one height and abut, that a scroll and End
  draw the rows they bring into view, that a focused row keeps focus, and that the
  filter narrows the list; `tests/test_ref_selector_pulls_chrome.py` does the same over
  branches that are pull requests’ heads, with the two heights, each row where the rows
  before it put it, the pull request’s icon, title, and number, and the filter’s finds.

A checkout also has the live working tree and can switch between it and pinned
revisions.

- **The working tree is the first tab, and its panel is one entry.** It is the one
  choice that is not a ref, so it has a tab of its own and no filter or list.
  The entry is a `.menu-item` like a ref’s (`.source-ref-selector-working-tree`): where
  a ref’s row has its name it has the branch `HEAD` is on, as that branch’s
  [chip](#branch-chips), or the [short ID](#short-commit-ids) of the commit a detached
  `HEAD` is at, and where a ref’s row has its commit and age it has the folder’s path as
  the page names the folder, with the home directory as `~`, in the same muted ink, and
  the folder’s own name in the row’s ink.
  It has no age, since it is the files on disk now.
  Where the pane is too narrow, the path before the folder’s name gives way first, and
  the branch and the folder’s name stay whole.
  A screen reader hears “Working tree, on main”, and the path as the entry’s
  description. The entry shows no count of uncommitted changes: counting them is a
  `git status`, whose cost grows with the working tree, and it would be out of date at
  the next save.

- **Choosing the working tree switches the page to the files on disk, and changes
  nothing on disk.** Nothing is checked out: the branch is whichever one `HEAD` is on,
  which is why the entry names it.
  The owner asked for the tab to “show the actual branch of the working tree, because we
  should not be changing the working tree but rather just switching to it” (2026-11-25).

- **A press on the Working tree tab switches; an arrow key onto it does not.** A
  pointer’s click on the tab, or Enter or Space with focus on it, from a page that shows
  a ref, asks for the working tree at once, as choosing the tab’s entry does
  (`pressKind`). The tabs are a radio group
  ([Choosing Among Values](#choosing-among-values)), where an arrow key moves the
  selection, so an arrow key onto Working tree shows its entry and leaves the page where
  it is (`setKind`): a reader moving along the tabs to look never loses their page.
  The entry is there for the same reason.
  A tab that switched the page as focus passed over it would be a trap for a keyboard or
  screen-reader user, and one that could only be pressed would leave them nothing to
  read first. With both, the arrow keys read, the entry says what will be shown, and
  Enter on either one switches.
  A press on the tab while the page already shows the working tree has nothing to
  switch, and shows the tab.
  `cli-ui-source-ref-selector-keys.tryscript.md` presses and arrows the mounted tab.

- **The served choice is marked one way.** A ref’s row and the working tree’s entry both
  carry `aria-current` when they are what the server shows, and exactly one of them
  does. It is drawn as a Pulls row and a stack’s member are drawn current: the medium
  weight, `--highlight-bg`, and the 2px `--highlight-bar` inset at its left edge,
  hovered or not. The weight alone left the list on the working tree and the list on a
  revision looking the same (2026-11-25). The highlight takes the place of the hover
  tint a menu row shows focus with, so keyboard focus on the current row draws the one
  [focus ring](#focus-ring) instead.

- **The checked-out branch stays in Branches, as its last commit.** It says “checked
  out” in the `.source-ref-selector-badge` a mirror’s default branch says “default” in.
  Choosing it shows what is committed on it.
  Uncommitted changes appear in Working tree.
  It is current there only once it was chosen.
  Dropping it would leave Branches without the branch a reader is most likely to look
  for, and the filter unable to find it; and its committed state beside the files on
  disk is a view worth having.
  The two no longer read alike, since each is under its own tab and names itself
  differently in the row.

- **The row says “Working tree” exactly when the page shows the files on disk.** A
  checkout has two views, the working tree and a revision, and the checked-out branch
  names both: its live files, and its last commit chosen from the list.
  So the ref alone cannot say which one the page is.
  The owner found choosing **Working tree** changed nothing on screen when the row named
  only the branch, on the working tree and on the branch’s revision alike (2026-11-25).
  - **Working tree · `main`**: the live files.
    The words (`.source-ref-selector-view`), a muted dot (`.source-ref-selector-sep`),
    then the branch `HEAD` is on as its chip, which opens its actions.
    A detached `HEAD` names its commit, in the commit-ID face; a `HEAD` the server
    cannot read leaves the words alone.
  - **`feature`**: one commit chosen from the list, read-only, whichever ref it came
    from, the checked-out branch included.
    The row names it alone, as a mirror’s row does, so there is one form for a ref
    wherever it is served.
    An earlier row said “Revision” before it and ended with a “← Working tree” button.
    The word told a reader nothing the absence of “Working tree” does not, and the
    button was a second way to do what the list does, on some pages only, which made the
    row a different shape on them; the owner asked for both to go (2026-11-25). The main
    heading’s note still says “committed revision of” the folder, and the Info button’s
    menu describes the pinned source beside its local path.

- **The source label’s tooltip gives the location and freshness.** A working tree shows
  the resolved absolute checkout path and how long ago Metabrowser read its `HEAD` from
  disk. A revision read from the checkout shows the same path and says it is read-only.
  A cloud-backed revision identifies the remote repository and shows how long ago
  Metabrowser last synced it successfully, when that time is known.
  Paths use the app’s path typography and wrap within the
  [shared tooltip](#one-tooltip-and-it-is-ours).

- **The working tree’s branch is kept current.** The server names `HEAD` when it draws
  the page. After that the page watches the checkout’s `HEAD` on the event stream it
  already holds, as a
  [file watch](project/architecture/arch-live-delivery.md#file-watches) on
  `HEAD_WATCH_PATH`, and when a terminal or an agent checks out another branch, detaches
  `HEAD`, or commits, it asks where `HEAD` is now and names it in the row, its tooltip,
  and the open tab’s entry, in place (`headChanged`). The Files view follows the files
  on disk, and an open list keeps its scroll and focus.
  An open Branches list moves its “checked out” mark too.
  The ask is the refs route’s `kind=working_tree`, which runs no Git.
  The server’s poll of its watches sets how soon the row follows, and its measurement is
  beside `HEAD_WATCH_PATH` in `file_watches.py`. A page that shows a ref has no event
  stream, so there the entry names `HEAD` as each listing reads it: when the list opens
  and when the tab is shown.

- **Refresh reads the list again and fetches the origin.** The navigation’s
  [Refresh](#refresh-retry-and-reload-page) reads an open list again in place, with its
  scroll and focus kept (`reread`). A press on Refresh is therefore the one press beside
  the list that does not close it ([Every Menu Closes Alike](#every-menu-closes-alike)):
  closing it would hide what the press asked to read again.
  The row or box that had focus has it back once the list is read.
  On a page that shows a ref it does so after the fetch of the mirror or the origin’s
  store, so the list holds what the fetch brought.
  On the working tree’s page nothing on screen waits for a fetch, so Refresh reads the
  disk and the history first and only then fetches the store of the origin, in the
  background (`fetchOrigin`); an open Remotes or Tags list follows that fetch to its
  end.

- **A page the server has moved on from says so at the foot of the pane,** in the
  freshness row a mirror offers its reload in, with one `.btn`, “Reload page”
  (`.source-ref-selector-stale`). Every tab shows it because every tab’s requests are
  refused then (`SourcePinGuard` in `source_routes.py`): the Files tree’s, the Commits
  history’s, which is the revision’s, and the Pulls tab’s and a comparison’s. It appears
  only after another tab has switched the server.

- **The revision row is one shape, from first paint.** It is its label and the chooser’s
  button on every page, with nothing else in it, so it is one line of one height
  whatever the page shows, and nothing in it moves when the list opens, when the page
  switches, or when `HEAD` moves.
  A switch that fails says why in the open list, where every switch is asked from, not
  in the row. The server draws the row, the working tree’s words included, before the
  chooser module loads.
  The module adopts the chevron button, preserving focus that reaches it early
  ([Regions Keep Their Boxes](#regions-keep-their-boxes)). Changes to filters or tallies
  leave the open chooser’s query, scroll position, and focus in place.
  `tests/test_checkout_ref_selector_chrome.py` records the selector’s height and the
  first tree row’s place in every frame of the working tree’s page and of a revision’s,
  and each has one value; `tests/test_files_totals_stable_chrome.py` holds the same for
  every box of the Files navigation on a folder that holds a `.git`.

What each state shows is pinned by
`tests/golden/cli-ui-source-ref-selector.tryscript.md`, and
`tests/test_checkout_ref_selector_chrome.py` measures in headless Chrome that the panel
stays inside the navigation pane with no row wider than it, that every ref’s ID is in
the commit-ID face with an age, and that the folder’s name is whole.

### Groups in a Menu

**A menu that groups its rows heads each group one way: a `.menu-group` named by its
`.group-heading`.** The pattern lives in the shell’s `styles.css`, so a built-in menu
and a plugin’s use the same markup:

```html
<div class="menu-group" role="group" aria-labelledby="types-section-1">
  <div class="group-heading" id="types-section-1"><svg class="category-icon">…</svg>Code</div>
  <!-- the group's .menu-item rows -->
</div>
```

- **Heading.** A `.group-heading` is the quiet label register, gray, all caps, and
  tracked, and it starts on the menu’s row inset, `--menu-row-inset`: the edge a row’s
  first column starts on, a check or an icon, and the edge the menu’s `.menu-title`, a
  labelled `.menu-row`, and `.menu-version` start on.
  It is not indented to the rows’ labels: a heading on the label column reads as a row
  of its group rather than its name.
  A heading that names a file-type category starts there with the category’s icon, and
  its name follows ([File-Type Category Icons](#file-type-category-icons)).
- **Separator.** A `.menu-group` draws its own divider as its top edge, in the
  `.menu-separator` geometry, unless it is the menu’s first child, where the menu’s edge
  already sets it off, or follows a `.menu-separator`, which already draws the rule.
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
`tests/test_github_pull_header_chrome.py` measure in Chrome that each heading starts on
its rows’ inset, with its icon where it names a category, and names its group or its
menu; `tests/test_browser_filter_ui.py` pins that the row, title, labelled row, foot,
and heading all read the one token.

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
  A [group heading](#groups-in-a-menu) or a [section heading](#section-headings) takes
  it. In a flex heading, as the Files section’s is, the name and the tally are flex
  items, and white space between them in the markup is dropped.
  In an inline heading, as Review comments is, the tally follows the name with no white
  space between them, since any would render and widen the gap before the dot.
- **Register.** The tally is a figure, not part of the name, so the heading’s caps,
  tracking, and weight are for the name alone: the tally is at the heading’s size,
  regular, untracked, in `--muted`, with tabular numerals.
  Its numeral is bold and its words regular, through the shell’s token for a count’s
  numeral, `--count-numeral-weight`. That token is not `--pull-number-weight`
  ([Pull Request Numbers](#pull-request-numbers)): a count is not a pull request’s
  number.
- **One line.** The tally itself never wraps, and keeps its spaces where a heading lays
  out its name and tally as flex items.
  Cutting the name short is the heading’s own: a flex heading whose name shrinks with an
  ellipsis (`min-width: 0; overflow: hidden; text-overflow: ellipsis`) cuts the name
  where the two do not fit and keeps the tally whole, as a Files section’s
  `.tree-section-label` does, and its tooltip then gives the whole name
  ([Tooltips Add Information](#tooltips-add-information)). An inline heading wraps its
  name instead.
- **Accessible name.** The dot is hidden from assistive technology, so the heading reads
  its name and its count: Chrome names a Files section “OLDER 10,004 files”, in the
  label register’s capitals.
- **A row of a tree is not a heading.** A Pulls stack group’s row says its stack’s size,
  “Stack #286 · 4 pulls”, in this place, beside its name after a dot, but it is a row
  that opens and closes, in the nav’s type and the text’s ink, not a heading over a
  section, and the figure is the stack’s size, not the number of rows under it, which a
  filter changes. So it is a count summary, painted by `metabrowser.countPartsNodes`, its
  number bold in the line’s ink
  ([Count Summaries Bold Their Numbers](#count-summaries-bold-their-numbers)), and not
  `.heading-tally`, which is muted ([Stacks](#stacks)). It showed no count at first, and
  a closed stack said nothing of its size.

The headings that carry a tally, each with the builder that writes its markup:

| Heading | Builder | Its name cut short |
| --- | --- | --- |
| A Files Group by section’s ([Grouping the Files Tree](#grouping-the-files-tree)) | `treeSectionHeadingHtml` in `src/metabrowser/static/app.js` | With an ellipsis and a tooltip, in a flex heading |
| A pull request page’s Review comments | `reviewThreads` in `src/metabrowser/builtin_plugins/github/pull-page.js` | Never: an inline `.section-heading`, whose name wraps |
| An event log view’s section headings, over what failed, what never ended, what the pages reported, and each kind | `tally` in `src/metabrowser/builtin_plugins/event_log/event-log-views.js` | Never: an inline `.section-heading`, whose name wraps |

A filter menu’s group headings, the stack menu’s heading, Overview’s panel headings, and
File Overview’s type groups count nothing.
`test_every_heading_tally_is_the_one_node_sequence` in `tests/test_design_vocabulary.py`
holds this table to every source that builds a `.heading-tally`, and each builder to the
one node sequence: the tally directly after the name, then a space, the hidden dot, a
space, and the figure.
`tests/test_files_tab_chrome.py` measures in Chrome that each File type section’s tally
starts where its name ends, its dot one space’s advance after it, leaves the rest of the
line empty, shares the name’s line at the default pane and at the 180 px minimum, sets
its numeral at `--count-numeral-weight`, and leaves the section and its tree named by
the heading’s words without the dot, and that at 180 px a name cut short shows its whole
in a tooltip and a whole one shows none; `tests/dom/github-pull-timeline-chrome.mjs`
holds the Review comments heading to the same place and register, and
`tests/dom/github-pulls-stacks-chrome.mjs` holds that a stack’s row shows its label, its
size, and its age.

### Menu Height

**A filter dropdown takes its rows’ natural height, up to a fixed number of rows, and
never reaches past the window.** Its `max-height` is the smaller of `MENU_MAX_ROWS`
rendered rows plus its padding and border, and the room from its top edge to the
window’s bottom edge less `MENU_WINDOW_MARGIN`, the tooltip’s viewport margin; both
constants are in `static/filter-controls.js`, with the measurement beside them.
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
natural height unless the window is shorter than its top, plus that height, plus the
margin; then it scrolls like the others.
Other menus are out of scope and keep the caps their stylesheets set: a pull request’s
stack menu, the branch and tag list, and Quick Search (`--search-palette-max-height`).

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
marks, by a press, Enter, Space, `↓`, or `↑` ([Stacks](#stacks)); on its button, as on a
filter’s trigger, `Home` and `End` open nothing.

- **Closing.** Escape, a second click on the trigger, and a choice that closes a
  single-select menu give focus back to the trigger
  ([Every Menu Closes Alike](#every-menu-closes-alike)). Focus the reader moved
  elsewhere in the page stays there, and an Escape that a surface above the menu took,
  such as Quick Search’s or Help’s, closes only that surface: the topmost closes first.
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

### Quick Search Results

Quick Search is a modal dialog whose results are one option list for files and pull
requests. File rows show the filename and path.
Pull request rows show the title first, with the PR number, bold
([Pull Request Numbers](#pull-request-numbers)), and state below it.
The accessible option name includes that context.
In a GitHub repository, a leading `#` scopes results to PRs.
The empty prefix lists recent PRs, digits match number prefixes, and words match titles.

Use the same arrow, Enter, and Escape behavior for every result type.
Keep the active option selected by identity as providers return, and open the result
through its normal navigation route.

File results lead, and pull requests follow as their own group.
Files answer from memory and pull requests from the server, later, so the later group is
appended below the painted rows instead of ranked in among them, and a late answer never
moves a file row or the selection.
Files keep the whole result cap, and pull requests have `PULL_RESULT_LIMIT`
(`static/search-controller.js`) rows of their own after them, so a full file group does
not crowd out pull requests and a file search is not cut short for a group that matches
nothing.

## Structured Data and Tables

Use structured rows rather than syntax-colored walls of punctuation when the user is
inspecting object relationships.
Keys, scalar values, array counts, and expansion controls each have consistent roles.

## Data Tables

Every table of data the app draws is one component, with one definition of each rule in
`static/styles.css`: the table plugin’s grid (`builtin_plugins/table/`), which every
tabular source draws through, and the folder’s Distribution and totals tables, which
take its numeric and label rules.
The view is drawn after the knowledge-base browser in
[paraverse](https://github.com/jlevy/paraverse) and adapted to these tokens.

| Class | Rule |
| --- | --- |
| `.data-grid` | The table: chrome in `--font-sans` at the body size, a hairline in `--border` under each row, the header in the resting label type and on `--bg`, staying at the top of its scroll box, and `--hover-bg` under the pointer |
| `.data-num` | A number, or a numeric column’s cell or header: right-aligned, in `--tabular-numerals`, never wrapped |
| `.data-literal` | A literal value, a key, timestamp, hex, JSON, or `null`, in `--font-mono` at `--mono-block-font-size` |
| `.data-label` | The resting label type a header has, for a heading that is not a `.data-grid` header, as a Distribution group’s is |

**Every value is visible, and none is mistaken for another.**

- `null` is drawn as the word, muted and monospaced; the empty string is an empty cell;
  a short row’s missing cell is a muted dash whose tooltip says the row is shorter than
  the header.
- A number keeps its digits: an integer past what a browser number holds arrives as text
  and is drawn as text, and an infinite or undefined real says `Infinity` or `NaN`.
- A value whose stored type differs from its column’s, which SQLite allows, carries a
  small outlined badge naming the stored type, in `--status-warning`, beside the value
  rather than in its place.
- A value the server cut for the page ends in a muted ellipsis, and its tooltip gives
  its length, or its size in bytes where the source read only its first bytes, and says
  the record shows more; the record says how much of it it shows.
- A reference to a row that is not there is drawn as its value, not a chip, with the
  same outlined badge saying `missing`, and its tooltip says no row of the referenced
  table holds it.

**Rows are one height, and cells are cut, never wrapped past it.** A table’s rows are
one line, or two when a value it holds is longer than its column or holds a line break;
a longer value is cut with an ellipsis, and its whole text is the shared tooltip, which
shows only while the value is cut
([Tooltips Add Information](#tooltips-add-information)). Each column is as wide as its
header and its first values in the face they are drawn in, up to `COLUMN_MAX_CH`
characters (`builtin_plugins/table/table-model.js`), and keeps that width as more rows
arrive or a filter narrows them, so columns do not move under the reader.
Numbers are right-aligned only in a column the source says is numeric.

**Columns fit the pane.** With a source’s default columns, those from the right hide
until the rest fit, and a note in the toolbar says how many are hidden and opens the
Columns menu; columns the reader chose never hide, and when they overflow, the table
scrolls sideways with its first column in place.

**Values that mean a choice are links.** A boolean or enum value adds a filter on its
column; a reference is a chip, a rounded box rather than the filter pill, whose card is
the shared tooltip, and which opens the record it names.
Every filter is a removable chip in the filter pill, `--radius-pill`; a header’s menu
sorts its column either way, filters it by an operator and a value, and hides it.
Search is one field, which asks the server once the typing pauses.

**Relationship links retain their context.** A back-reference count opens rows for the
field pair it counted.
Its filter chip links to the original record and uses the card’s name when available.
The record heading uses the source’s label when it provides one.
The key fields or position remain visible in the record.

**One Tab stop.** The grid is a row collection under
[Navigational Row Collections](#navigational-row-collections): one element of the grid
is in the Tab order, a row, a cell’s link, or a header’s button.
Up and Down or `J` and `K` move a row, Left and Right move between the row and its
cells, so a link in a cell is reachable, and Enter on the row opens its record in place
of the grid; Back returns the keyboard to that row.
Up from the first row moves to the header, where Left and Right cross each column’s sort
and menu buttons and Down returns to the rows, so a column adds no Tab stop.
Arrows do not open a row here, because a record replaces the grid the reader is reading.
A header’s menu and the Columns menu are labelled dialogs: Tab moves through them, and
they close when the focus leaves them or on Escape, which returns it to their button.

**Small tables are drawn whole; large ones are windows.** Either is `role="grid"`,
multiselectable, with `scope="col"` headers and `aria-sort`, and `aria-colcount` while
columns are hidden to fit.
A table of at most `WHOLE_TABLE_MAX_ROWS` (`builtin_plugins/table/table-view.js`) draws
every row and keeps the browser’s find, select all, copy, and print.
A larger one adds `aria-rowcount` and `aria-rowindex`, and draws only the rows near the
view at one fixed row height; there, Search stands in for find in page, Shift with Up,
Down, Home, or End selects rows that copy as tab-separated values, since a chord such as
Command-A stays the browser’s, and print draws the rows held, up to `PRINT_MAX_ROWS`,
with a line on the paper saying which rows it printed when it did not print them all
([Rendering Large Content](large-content-rendering.md)).

**The reader’s place is kept.** Back to the table, and a reload, return to the row that
had focus and the scroll it had.
The view writes its place to the history entry only when it matters, before it
navigates, when the page is hidden, and once a pause after the last move or scroll
(`PLACE_SAVE_MS`), because browsers bound history writes and a write a key press would
use up the one a record’s address needs.

**A live table moves nothing under the reader.** When its file changes, the table reads
the rows it holds again with the same question, gathering a burst of changes for
`LIVE_COALESCE_MS` (`builtin_plugins/table/table-view.js`). A row whose cells changed,
and a row that arrived where the reader is, flash once in `--row-flash-bg`, as
[Live Row Arrivals](#live-row-arrivals) do; a row that would land above the first row on
screen is offered as a “3 new rows” `.btn` in the toolbar rather than drawn, and taking
it draws the rows, goes to the first, and puts the keyboard on it.
The scroll position, the focused row and the selected rows (by key, or by position where
rows have none), an open menu, and what is typed but not sent stay as they were, and a
read whose rows are the same draws nothing.
A **Live** `.btn` beside it, whose label is its state and whose accessible name is the
action, pauses the table and then reads **Paused · 2 changes**; pressing it again reads
once. An open record has its own, since the toolbar is hidden while it shows, and is
drawn again only when its cells change, keeping the keyboard on its control.
Both the offer and the Live control sit between the fit note and Columns, and once shown
keep their slot while hidden, so the toolbar keeps its box
([Regions Keep Their Boxes](#regions-keep-their-boxes)). A read is spaced from the last
by `LIVE_COST_SPACING` times what that one took, and none is made while the page is
hidden; it reads once when shown.
A read that fails keeps the rows on screen with a notice saying they are the last read,
a watch the page could not register says the table is not following its file, and a
column the address named that is gone is dropped from the address with a notice.
The offer when it appears, Paused, and a failure until a read succeeds are each
announced once in the view’s one polite live region.

`tests/dom/table-view-session.js` runs the view’s behavior from the command line, and
`tests/test_table_view_chrome.py` checks in Chrome what only layout and the browser’s
history show: one row height, which the view’s estimates match, cutting and its tooltip,
the inks and faces, the header that stays put, the pinned first column, the printed
line, and a run of key presses past Chrome’s bound on history writes followed by a
record, its Back, and a reload.

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

A hover is a statement about what its handle names, so it is drawn **on what the handle
names** and nowhere else: a mark under the pointer names itself, and a legend entry
names the marks of its family.
Dimming, fading, or desaturating the neighbours to pick them out is not available: it is
a larger visual event than the interaction earns, it makes the reader’s eye track motion
across the whole component rather than the one thing they pointed at, and a dimmed
neighbour reads as *excluded* or *inactive*, which is a claim the hover is not making.

For a segment of a bar, a treemap cell, a chart mark, or any other measure the reader
can point at:

| Do | Do not |
| --- | --- |
| Grow the hovered mark on the axis that carries **no** data, with `--viz-hover-grow` on `--viz-hover-grow-ease` | Grow the axis that encodes the value |
| Lift its own color a step with `--viz-data-mark-hover-filter` | Dim, fade, or desaturate the other marks |
| Ease in and out on the viz layout scale, and shimmer on the `--viz-hover-shimmer-*` tokens | Spring past the target, or pulse as a loading block does |
| Leave every other mark exactly as it was | Outline, ring, or border the mark, or move the layout |

A legend entry is a handle on the marks it keys: pointing at it draws this hover on
every mark of its family on screen, and on the entry, and nowhere else; pointing at a
mark draws it on that mark and on its family’s entry, as File Overview’s legend does
([Aggregate Distributions](#aggregate-distributions)).

**Grow, do not outline.** An outline is drawn *on* the data: it covers the color it is
meant to point at, it competes with whatever separators the component already has
between marks, and on a short mark it is a large fraction of the height.
Growth says the same thing and covers nothing, and the eye is already good at finding
the one thing that moved.

**Grow the axis that carries no data.** This is the part that is easy to get backwards.
On a horizontal bar the *width* is the value, so it is the one dimension that must not
move: growing it states a share the mark does not have, and every mark after it appears
to shift.
Thickness means nothing there, which is exactly what frees it, so a bar segment
grows *taller*, centered on the baseline the eye follows along the row.

It also makes the answer uniform.
Growing a width in proportion would move a wide segment far and a narrow one not at all,
so the marks hardest to point at would answer least; every segment shares one height, so
every segment answers the same.

Because the axis is small, the factor, `--viz-hover-grow`, is large: a few percent of a
thin track would be a fraction of a pixel.
Its bound is the room beside the mark: a legend entry grows its family’s segment in
every tally row at once, so grown neighbours must still clear each other and the legend,
which the measurement beside the token records.

**Grow with a transform, never with layout**, so the row does not reflow under the
pointer.

**Ease in and out, without a spring.** The growth and the lift move together, on the viz
layout scale’s duration and plain ease (`--viz-hover-grow-duration` and
`--viz-hover-grow-ease`), and run back the same way when the pointer leaves.
A spring that overshot its target, which this replaced, read as a snap.

**A hovered mark shimmers.** While it is marked, a sheen over its color breathes in and
settles, once a period, on the `--viz-hover-shimmer-*` tokens and the
`viz-hover-shimmer` keyframes.
It is a sibling of the progress blocks’ pulse (`tally-pending-pulse`), and meant not to
read as one: the progress pulse fades a whole block, steadily and without a pause, which
says “waiting”, while the shimmer lightens a mark that is there by a fraction of what
the lift moved it, rises, settles, and rests, on a longer period
(`--viz-hover-shimmer-period`), so it reads as a glint.
At its peak the mark keeps its family’s color and stays clear of its rest color.
It is a pseudo-element’s opacity, so the compositor runs it with no main-thread work
while the pointer holds; the values and their measurements are beside the tokens in
`static/styles.css`. Marks the hover enters together shimmer in step, and one marked
later, as a Details row opened under a held hover, starts its own cycle.

The shimmer is for the few marks a handle names.
Each shimmering mark is a composited layer and an animation of its own, so the cost
grows with their number, though no main-thread work runs.
Where a handle can mark every mark a view draws, as a legend entry marks every Treemap
cell of its family, those marks take the lift alone, and only the mark under the pointer
shimmers. The cost at the Treemap’s cell limit, with and without the family’s sheen, is
measured beside the rule in the folder plugin’s stylesheet
([Folder Treemap](#folder-treemap)). A new mark that a handle can name in numbers
bounded only by the view states the same, or measures the shimmer at that bound.

The lift darkens on light and brightens on dark, and it is relative to the mark’s own
color rather than a fixed overlay: file-type families sit at different lightnesses in a
band, and a deviating family outside it, so a fixed delta lands differently on a pale
family than on a dark one.
See [File-Type Colors](#file-type-colors).

Under `prefers-reduced-motion: reduce` the motion goes, the transitions and the shimmer,
and the lift and the growth stay, drawn at once: a darker, thicker mark is a state, not
a movement, and the stronger highlight is what makes the hover read.

**Where growth does not apply.** Two conditions rule it out, and the treemap meets both,
so it takes the lift alone.

- *The mark’s area is its value in two dimensions.* A bar segment’s width encodes its
  share and the growth leaves it as it is, so nothing is misstated.
  A treemap cell’s area is the whole encoding, and a cell held larger states a size it
  does not have.
- *The mark cannot be lifted above its neighbours.* Growth needs the mark on top, and a
  treemap flattens a nested folder and its descendants into siblings, so raising a
  hovered container paints it over every rectangle inside it.
  `test_treemap_hover_never_promotes_a_container_over_nested_cells` holds that.

A new chart mark that meets neither condition grows.
One that meets either keeps the lift and states why here.

## Motion

Motion communicates a state transition: tree insertion, removal, refresh, loading, or
layout change. Keep durations short and use the shared motion tokens.
Avoid looping animation except for active progress indicators,
[refreshing content](#refreshing-content), and the shimmer on a hovered data mark
([Hover Styles the Thing Under the Pointer](#hover-styles-the-thing-under-the-pointer)),
which runs only while the pointer holds the mark.

Respect `prefers-reduced-motion`. Content and status must remain understandable when
transitions are disabled.

### Reveals

Chrome that appears because the reader asked to see it eases in on one token,
`--motion-reveal`, a short decelerating curve, so it settles rather than pops.
The Shift reveal is its user: each key badge fades in and grows from slightly smaller
than its size, and the revealed strip fades in.
A reveal never animates out.
It ends at once, because the reader has let go and is about to act on what was under it,
and a fading badge would cover the label they reach for or point at a state a key has
already changed. The duration is under the hold that starts the Shift reveal
(`REVEAL_HOLD_MS` in `static/key-reveal.js`), so a held Shift reads as one gesture, and
a quick Shift-tap still never starts it.
Under `prefers-reduced-motion: reduce` a reveal appears at once.
WebKit, the macOS app’s engine, runs the reveal unprefixed: `@keyframes`, `animation`,
and the `scale` property need no `-webkit-` form there, unlike `user-select`. A new
reveal uses `--motion-reveal` rather than a duration of its own.

### Live Row Arrivals

The Files tree and Pulls apply `.tree-item-flash-in` to a newly arrived row.
The shared `--row-flash-bg` tint fades to transparent on the `.tree-item-flash-in`
rule’s animation and uses the near-instant reduced-motion treatment.
The highlight leaves the row’s size and controls in place.

Initial snapshots, older rows revealed by paging, and edits to existing rows use their
regular presentation, except in a [data table](#data-tables), which flashes a row whose
cells a live refresh changed as it flashes one that arrived (`.table-row-flash`). Each
data source decides which rows arrived.
A live list fed by another provider can apply the same treatment when it inserts a new
item.

PR arrival classification uses a conservative timestamp cutoff.
A machine clock ahead of GitHub can suppress the tint.
The new catalog row still appears with its regular controls and selection behavior.

### Regions Keep Their Boxes

Every region’s box is decided by the first paint and does not depend on data that
arrives later, except a navigation toolbar in a pane too narrow for it (below), because
chrome that comes and goes moves the content beside or below it
([measurements](../explorations/performance-loop/design-rule-measurements.md#regions-that-moved)).
So a region keeps its slot while its content is absent, and holds the height it will
have: one toolbar slot at the top of the navigation that every main tab fills with its
own toolbar at one height while each is one line (the Files filters, the Commits tally,
the Pulls filters), the Commits tab from the server at a repository’s root, a scrollbar
gutter on the tree and the preview pane, the shortcut strip’s row, a view tab bar in
every file, a run badge’s width, the Pulls tab’s status and connection lines and its age
column, the Files totals’ ignored line, which a folder with nothing ignored does not
have ([Navigation Metadata Line](#navigation-metadata-line)), and the pull request
header’s rows, but for a labels row a pull request with no labels does not have
([Layout](#layout)). In a pane too narrow for a toolbar’s controls the toolbar wraps
instead of cutting them ([Navigation Toolbars Wrap](#navigation-toolbars-wrap)), and the
slot is as tall as the lines of the toolbar in front.
There a tab switch can move the panel under the slot, and the Commits slot gains a line
when its tally lands, if the tally is wider than the pane; the Treemap’s legend row
likewise holds one line and takes as many as its entries wrap to
([Folder Treemap](#folder-treemap)), which `tests/test_treemap_legend_hover_chrome.py`
holds at one line where they fit.
Heights are in line units, or struts of the controls a row holds, never pixels measured
in one engine, because WebKit’s font metrics differ from Chrome’s. Where a region’s size
is its data’s and arrives a moment after the rest, as the File Overview’s first rollup
does, the view holds its first paint for that data, briefly, with the previous view
still shown. The Files tree holds its first paint until the Files toolbar has its
controls, so a toolbar that wraps in a narrow pane is at its height before the tree
shows under it. The toolbar is drawn just before the tree’s first rows, so no row waits
for it, and the hold ends at a bound, so a toolbar that never loads does not hide the
tree; the bound and its measurement are beside the rule in `static/styles.css`. The
server draws the tab an address lands on in front, a commit’s address on Commits, so a
landing never shows one tab’s chrome and then swaps it; a toolbar that cannot load says
so in its slot rather than pulsing.
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

An asynchronously rendered replacement mounts in a transparent, inert stage while the
prior useful surface stays visible, and replaces it in one step once its renderer is
ready, so no empty container, duplicate surface, or blank frame shows; the
[browser shell](project/architecture/arch-browser-shell.md) holds the staging mechanism.

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
compositor opacity animation to the incoming foreground content root, from
`PREVIEW_ARRIVAL_START_OPACITY` to full over `PREVIEW_ARRIVAL_DURATION_MS`
(`static/app.js`) with `ease-out`. The preview pane’s theme background never animates,
so the handoff cannot pulse white in light mode or flash pale in dark mode.
The old preview never fades out, the new preview is usable immediately, and the shell
does not traverse or restyle the rendered document.
This small incoming-view treatment softens the paint boundary without reading as a
loading effect. `prefers-reduced-motion` skips it entirely.

The acknowledgement is measured separately from content readiness, as the performance
loop’s
[Attributing Stateful-Navigation Delay](../explorations/performance-loop/README.md#attributing-stateful-navigation-delay)
describes.

High-churn navigational rows update hover, focus, and selection backgrounds without a
transition so the visible answer does not ease in behind the input.
Motion belongs on the single incoming preview, not on each row crossed while scrolling.

### Progress Spinners Stay Neutral

Loading and progress spinners use the shared neutral-gray track and accent tokens.
They must not borrow link, status, file-type, or chart colors because a spinner conveys
activity, not meaning.
Prefer the shared spinner classes; custom sizes must still use the shared spinner tokens
and keyframe.

When a page can show partial results while an index is built, put the status line
alongside the content in muted text (`--muted`) with the shared small
`.index-progress-spinner`. Name the work and show a count when one is known.
Keep the line in the page’s surface so it reads as secondary information beside the
results.

### Loading States Are Shapes, Not Sentences

A loading state says “this will be content” by taking the shape of the content.
It does not announce itself in words.
“Loading history…”, “Loading file types…”, and “Loading bytes…” are all the same
sentence, they all say what the surface being replaced already implies, and a column of
them reads as a page in trouble rather than a page working.

Two forms, and the choice between them is about whether the shape is known:

- **Skeleton blocks are the default.** When the layout is known before the data (rows,
  cells, a tally, a list), draw that layout as neutral blocks carrying the slow pulse
  used by the navigation tally (`.tally-pending`, `tally-pending-pulse`). The block
  reserves the real geometry, so arriving content replaces it without reflow, and the
  pulse reads as “loading” rather than “blinking”.
- **A spinner is for an indeterminate wait whose shape is unknown.** A document about to
  render, a comparison whose file count is not yet known: a skeleton there would invent
  a structure the result may not have.
  The spinner says only that work is happening, which is all that is honestly known.

Both forms observe the quiet period above: a state that resolves inside
`--loading-state-delay` shows nothing at all.

Screen-reader text is required and is not a violation of this rule.
A spinner or a skeleton is invisible to a screen reader, so it carries an `sr-only`
label or an `aria-label` naming what is loading.
That text is not visible copy; the rule is about what is painted.

Visible copy is for a state neither form can express (a scan still running behind an
empty result, an index that failed), and it says what that state is rather than that
something is loading.
A background refresh of content already shown is neither form: it is
[Refreshing Content](#refreshing-content).

### Refreshing Content

**Content already rendered is never covered by progress.** When a refresh checks data
the reader can already see, such as a cached pull request, its changed files, or a Pulls
list, the content stays as it is, at full size and in place, with no spinner and no
progress or staleness sentence beside it.
A spinner over rendered content is the strongest loading signal pointed at something
that is not loading, and it drew the eye to a wait the reader was not making.

Instead, the text a refresh is checking **breathes**: its opacity eases down and back
once every `--refreshing-text-period`, starting only after `--loading-state-delay`, so a
refresh that lands within the quiet period shows nothing.
A status text that breathes, such as a page’s age line or a retry notice, carries
`aria-busy="true"` while it does.
The navigation’s Refresh shows its own spinner after a press.
Names and titles that breathe sit in rows that stay usable links and tree items, so
their breathing is paint alone and nothing marks them busy.

- `.mb-refreshing` breathes the element it is on.
- `.mb-refreshing-group` breathes the `.mb-refreshing-text` elements inside it, so a
  list toggles one container and a row drawn into it later joins.
  A view that draws rows into a breathing list brings them to the same beat
  (`alignRefreshing` in the GitHub plugin).
- **Primary ink only.** Primary ink dims to `--refreshing-text-dim-opacity` and keeps
  4.5:1 at its dimmest in both themes.
  Muted ink cannot dim and keep 4.5:1, so a muted line takes `.mb-refreshing-muted` as
  well: it is drawn in `--text` at the opacity that reproduces `--muted`
  (`--refreshing-muted-rest-opacity`, an OKLab difference under a just-noticeable one)
  and lifts toward full ink instead.
  Status inks (change badges, line stats, state icons) never breathe.
- **One container per surface:** the pull request page’s age line, a changed-files
  tree’s folder and file names, the Pulls connection row’s age, and the titles of the
  rows whose own data GitHub is being read for.
  A tree’s file that the comparison does not hold is muted, and its name breathes as a
  muted line does.
- **Opacity only**, so the compositor runs it with no main-thread style, layout, or
  paint, and starting it costs one style recalculation per breathing element, which the
  tree’s window bounds.
  The measurements and the contrast figures are beside the tokens in
  `static/styles.css`.
- `prefers-reduced-motion: reduce` stops it: the text stays as it rests, and a status
  text’s `aria-busy` still says a refresh runs.

A Group by choice’s first sections are the one wait that dims what is shown
([Grouping the Files Tree](#grouping-the-files-tree), Waiting): the tree on screen then
is not the content being checked but the arrangement the reader left, and the reader is
waiting for the new one, so past the quiet period it dims to its own token,
`--loading-dim-opacity`, while the scan row says what is coming.
Nothing else takes that token.

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

The reason is WebKit, the macOS app’s engine: a lazy image waits for layout before it
asks for its bytes, and WebKit then asks the network again rather than use the copy it
holds, leaving the image blank for several frames; an eager one takes the copy in its
first frame. Chrome reuses the copy either way.
An image whose address does change is a new image, and its slot keeps its size, so its
arrival moves nothing.
A node replaced under a still pointer is also a new target for hover and focus: the
tooltip restarts its delay and a focused control’s focus goes to the body, which is the
other reason the header keeps its parts.
`test_the_header_keeps_its_nodes_and_each_avatar_loads_by_its_placement` checks, in a
browserless DOM, each avatar’s loading by placement and which of the header’s nodes a
repaint keeps or builds: their attributes and node lifecycle, not their paint.

A Markdown document is built again each time its file is entered; switching between its
Document and Source views keeps it.
KPress writes its images lazy, and one far down a long document should wait for the
reader. So an image the page has already loaded, at an address that names its bytes, is
made eager and takes the copy the page holds; an image the page has not loaded stays
lazy.

A served file’s address names its bytes by a version.
Each render answers, beside its HTML, `raw_versions`: for each served file the document
embeds, a token of the file’s resolved path, size, modification and change times, inode,
and device, of the trust profile and its sandbox policy, and of the build, read when the
render is asked for, which is on every entry.
The link enhancer puts the version in the file’s `/raw` address, so a replaced file is a
new address.
`/raw` keeps a raster image’s answer for a long time at the version the file
has now, and revalidates every other, an SVG’s included, since its sandbox differs by
trust profile (`SECURITY.md`); a revalidated image the page holds is still taken from
its copy. So the page reuses what it holds at an address without asking whether the file
changed: an image whose file changed has a new address, which the page does not hold,
and loads lazily there.
That holds for a hidden file, a file behind a link, a file deeper than the shell’s event
stream watches, and a replacement that keeps the file’s size and time, because the
version is read from the file, not heard from the shell.
On a pinned revision a file never changes at its address, and an image from another
origin, a scheme-relative `//host/badge.svg` on another host included, is that host’s to
keep fresh, so both are held too.
A served address without a version, which is any past `_MAX_RAW_VERSIONS` files of a
render (`server.py`), and an absolute or scheme-relative address on the page’s own
origin can change under the page, and are never held.

A held served image is made eager before its address is set, its authored address
removed first: an eager image asks for its address at once, and the authored one,
relative to the document, is not where the image is served.
A held image from another origin keeps the address its author wrote, so it has to be
eager before the page adopts it: a trusted render is parsed in a template, whose
document loads nothing, and the template’s images the page holds are made eager there.
The page remembers `MAX_HELD_IMAGES` images (the Markdown plugin’s `place-rendered.js`)
and past that forgets the one loaded least recently; the costs behind both bounds are
beside their constants.

The rule has its limits.
A version is read when the document is rendered, so a document on screen keeps the image
it has until it is entered again.
Which file an address names is decided in the page (`builtin_plugins/markdown/links.js`)
and predicted by the server (`embedded_resources.py`); an address the prediction misses
is left unversioned, and its image is not held.
An image from another origin is held while the page lives, so a change on that host
shows after a reload.

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
[Design Rule Measurements](../explorations/performance-loop/design-rule-measurements.md#a-repaint-keeps-its-images)
has the WebKit and Chrome frame counts behind each part of this rule.

## Text Selection

Text selection is content behavior.
Informational text, including errors, logs, file contents, status explanations, and
labels, must remain selectable for search and debugging.
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
