# Metabrowser App Icon

**Status:** Draft under review.
The release and development masters use the `touch` junction; the alternatives and the
small sizes wait on review.

The icon is an MB mark on the sister app’s v6 icon: the same squircle, rim, panel,
sheen, border, and pressed-in letter shadow, with a partial M in a light shade of
Metabrowser’s JavaScript color and a B in a light shade of its Markdown color.
The partial M and the B’s stem read together as an M.

## Files

| Path | Holds |
| --- | --- |
| `metabrowser-icon.svg` | Release master, for official builds. |
| `metabrowser-icon-dev.svg` | Development master: the sister app’s canary scheme, a gold rim and a warm sheen. |
| `make-glyphs.swift` | Constructs the partial M and the B and writes them into a master, changing nothing else. |
| `render-svg.swift` | Renders a master to PNG at any size that divides 2048. |
| `review-sheet.swift` | Lays out the review images. |
| `../scripts/build-icon.sh` | Builds `Resources/AppIcon.icns` and `Resources/AppIcon-Dev.icns`, and with `--review`, the review images. |

## Regenerate

```shell
scripts/build-icon.sh                   # from apps/macos: both .icns files
scripts/build-icon.sh --review          # also AppIcon/review/, which git ignores
```

Add `--sister FILE.svg`, the sister app’s v6 release export, to include side-by-side
comparisons in the review.
The script needs only the Swift toolchain and macOS frameworks, and it writes
byte-identical files on every run.

To change the glyphs, edit the measurements at the top of `make-glyphs.swift` and
rewrite both masters in place:

```shell
swiftc -O AppIcon/make-glyphs.swift -o /tmp/make-glyphs
/tmp/make-glyphs AppIcon/metabrowser-icon.svg AppIcon/metabrowser-icon.svg touch
/tmp/make-glyphs AppIcon/metabrowser-icon-dev.svg AppIcon/metabrowser-icon-dev.svg touch
```

## The Base

The masters are the sister app’s v6 icon as Figma exports it to SVG, copied verbatim,
including Figma’s element ids, so a diff against the export shows only what changed.
In the Figma document the rim is a 376-unit square with a 65-unit corner radius at 60%
corner smoothing and a 29-unit outside stroke.
The panel is 364 units with a 60-unit radius at the same smoothing, a 9-unit outside
border, and a drop shadow of radius 10 and spread 9 at 20% black.
The sheen is a second panel-shaped fill with a diagonal gradient.
The export bakes the smoothing into the paths and turns the effects into filters with
the same parameters.

One change from the export: the export draws the panel’s outside border as an 18-unit
stroke masked to the panel’s outside, and any SVG renderer then leaves a translucent
seam where the panel’s antialiased edge meets the mask’s. The masters draw the same
stroke, unmasked, under the panel fill, which paints what Figma paints.

## The Glyphs

The sister app’s letters are live text in its Figma document.
The K is Reddit Mono Bold at 232 px, unedited: its exported outline matches the font’s
own K within 0.063 units.
The ❯ is U+276F, which Reddit Mono lacks, so Figma drew it from a fallback font at 182
px; it is resized, not edited.

Every dimension below is in the 512-unit master and comes from Reddit Mono Bold at 232
px (font units times 232/2048).

| Dimension | Value | Source |
| --- | --- | --- |
| Baseline | 339 | The K’s baseline in the export |
| Cap line | 172.023 | Cap height, 1474 font units |
| Stem | 31.464 | The B’s stem, 277.75 font units |
| Diagonal weight | 31.464 | The K’s arms, which are stem weight measured square to the stroke |
| Diagonal angle | 29.0° from vertical | The M’s outer diagonal edge |
| Crotch | 239.451 | The M’s crotch height, 878.781 font units |
| Vertex flat | 284.418 | The M’s flat cut under its vertex, 481.828 font units |
| Horizontal position | Area centroid at x 262.598 | The sister app’s glyph pair, so both marks balance alike |

The B is the font’s own outline, unedited, at the K’s size and baseline, since the
sister app applied no edits to its K. Its outline coordinates are copied into
`make-glyphs.swift`; Reddit Mono is copyright 2020-23 Reddit, Inc., under the SIL Open
Font License 1.1, and the font itself is not used or shipped.

The partial M is drawn: a stem, and two diagonal bands between parallel edges, cut flat
on the cap line and on the vertex line.
The `junction` argument of `make-glyphs.swift` chooses how the second diagonal meets the
B’s stem:

- **touch** (in the masters): its upper edge ends on the stem’s top-left corner, and the
  first diagonal leaves the first stem’s top-right corner the same way, so both stems
  stay clean rectangles.
  The mark is 218 units wide, against the sister app’s 222.
- **overlap**: it runs into the stem as in the font’s M, whose stem tops are 70% of the
  stem width.
- **gap**: it stops short with a flat terminal, the sister app’s 21.4-unit glyph gap
  from the stem. It reads as a V beside a B rather than as an M.

The partial M is drawn first and runs 2 units under the B’s stem, so their shared edge
has no antialiasing seam, and the inner shadow, a filter on the pair, treats them as one
shape.

## Colors

The file overview paints each file-type family with `ToneBand.at(family.hue, position)`
from `src/metabrowser/color_oklch.py`. The JavaScript family (hue 102.08, from GitHub’s
#f1e05a) paints oklch(68% 0.1425 102.08), #AA9A00, on the light theme and #D4C43E on the
dark.
The Markdown family (hue 276.0) paints oklch(50% 0.1856 276), #4C50CA, and #717DE5.

The sister app’s fills are #84FA9F, oklch(89.36% 0.1651 149.47), at 84% of the chroma
sRGB holds there, and #FF9AF7, oklch(82.00% 0.1657 329.84), at 100%. Each Metabrowser
glyph takes its family’s hue and the lightness and gamut-relative chroma of the sister
glyph in the same role:

| Glyph | Role | Fill | Oklch |
| --- | --- | --- | --- |
| Partial M | The ❯ | #F1DF53 | 89.36% 0.1569 102.08 |
| B | The K | #B4C0FF | 82.00% 0.0904 276.00 |

sRGB holds only 0.090 chroma at hue 276 and 82% lightness, so the B is paler than the
sister app’s K.

## The Renderer

`render-svg.swift` implements the SVG subset these masters use and stops with an error
on anything else. It renders once at 2048 px and box-filters down to each size, which
keeps filter radii in proportion at small sizes and halves the antialiasing error where
edges abut. Its coverage rasterizer is exact horizontally and samples 16 sub-scanlines
per row.

The alternatives were measured against Figma’s own 1024 px export of the sister app’s
icon, letters excluded.
NSImage (CoreSVG) drops the filters.
A WebKit snapshot shifted the panel from #1F2020 to #1C2222 through the display’s color
profile, for a mean error of 1.4 of 255 per channel.
This renderer, with the border drawn under the panel, came to a mean of 0.24 of 255,
with 0.07% of pixels off by more than 8.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
