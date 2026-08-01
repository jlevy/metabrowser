# Design System

Metabrowser’s interface is an information-dense developer tool.
Its design system prioritizes readable artifacts, stable spatial relationships,
keyboard-sized controls, and consistent status cues over decorative chrome.

## Principles

1. **The artifact is primary.** Navigation and controls stay compact so the preview
   receives most of the viewport.
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
- chart colors and annotation states;
- component dimensions, radii, typography, and motion.

Components consume semantic tokens.
They should not copy HSL or hexadecimal values from another component.
When a new concept needs a color, add a token with a semantic name and define its
dark-theme override alongside it.

Plugin styles may consume host tokens.
A plugin-specific visual language belongs in the plugin stylesheet, including any new
domain tokens, rather than in core `styles.css`.

## Typography

The shell uses a compact UI face for navigation and controls, a monospaced face for code
and structured values, and KPress typography for rendered Markdown.

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
- `--micro-font-size` (10px): deliberately minimized marks — the brand line, code inside
  truncation notes.

Document (rendered prose) sizes, where mono and small derive from the body size so a
document rescales as one unit:

- `--document-body-font-size` (17px): prose.
- `--document-mono-font-size` (0.9×): code — smaller than prose by design; mono x-height
  is larger, so this still reads close to the prose size.
- `--document-small-font-size` (0.85×): secondary document text — TOC entries, captions,
  footnotes.

Embedded KPress documents set `--kpress-host-font-size-base` to
`--document-body-font-size` on `:root`. KPress derives its full ramp, headings, bullets,
labels, and offsets from that base.
The scoped bridge overrides only intentional design differences: mono uses
`--document-mono-font-size`, secondary document tiers use `--document-small-font-size`,
and the CONTENTS label uses `--label-font-size` so it matches app labels.
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

Keep these roles distinct:

- labels and metadata use normal weight and muted text;
- selected values and filenames use stronger contrast;
- byte counts, durations, timestamps, and numeric table columns use tabular numerals;
- code and paths use monospaced text without forcing prose into a code style.

Do not shrink essential text to fit.
Prefer truncation with an accessible full-value tooltip or allow a panel to scroll.

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

## Panels and Tabs

The preview pane has one scroll owner.
Views should not introduce nested full-height scroll containers unless the content
itself requires independent horizontal or virtual scrolling.

Tab renderers receive a dedicated container and own its contents.
Default views mount immediately; hidden views mount on first activation.
A loading state should preserve the tab’s dimensions and communicate whether the work is
local parsing or an HTTP request.

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

## Charts

Chart specifications use CSS-variable sentinels for color.
`static/charts.js` resolves those variables before passing concrete colors to Chart.js,
because canvas cannot resolve CSS custom properties itself.

Charts must include text labels and usable summaries.
Color alone cannot distinguish series, thresholds, or success and failure.
Destroy Chart.js instances when their view is disposed.

## Motion

Motion communicates a state transition: tree insertion, removal, refresh, loading, or
layout change. Keep durations short and use the shared motion tokens.
Avoid looping animation except for active progress indicators.

Respect `prefers-reduced-motion`. Content and status must remain understandable when
transitions are disabled.

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
3. Check light theme, dark theme, keyboard focus, reduced motion, and print output.
4. Verify lazy mount and disposal behavior.
5. Run Biome, TypeScript check-JS, and the relevant browser-side tests.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
