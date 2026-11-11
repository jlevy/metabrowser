# Metabrowser App Icon

**Status:** Draft under review.
Both masters use the `gap` junction and the citrine and amethyst fills; the small sizes
wait on review.

The icon is an MB mark on the sister app’s v6 icon: the same squircle, rim, panel,
sheen, border, and pressed-in letter shadow, with a partial M in a gem tone of
Metabrowser’s JavaScript color and a B in a gem tone of its Markdown color.
The partial M stops one glyph gap short of the B, whose stem completes the M.

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
/tmp/make-glyphs AppIcon/metabrowser-icon.svg AppIcon/metabrowser-icon.svg gap
/tmp/make-glyphs AppIcon/metabrowser-icon-dev.svg AppIcon/metabrowser-icon-dev.svg gap
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
The first diagonal leaves the stem’s top-right corner, so the stem stays a clean
rectangle.
The `junction` argument of `make-glyphs.swift` chooses how the second diagonal
meets the B’s stem:

- **gap** (in the masters): a vertical cut ends it where the first stem’s outer edge
  falls when mirrored on the M’s axis.
  Its top is then a flat cut one stem wide that meets an 8.137-unit vertical face at a
  right angle, and the partial M is symmetric about its axis but for the missing stem.
  The B’s stem follows 21.437 units beyond the face.
  The mark is 271 units wide, against the sister app’s 222.
- **touch**: its upper edge ends on the B stem’s top-left corner, so the B’s stem joins
  the M; the mark is 218 units wide.
- **overlap**: it runs into the B’s stem as in the font’s M, whose stem tops are 70% of
  the stem width; the mark is 199 units wide.

The gap is the sister app’s least distance between its glyphs, from the ❯’s tip to the
K’s stem, so the vertical face sits as close to the B as that tip does to the K.
Optically the two gaps are close too: capping clearance at twice the gap, the mean
clearance over the cap height is 39.3 units here and 38.1 in the sister app, whose tip
leaves open space above and below it where the face leaves it only below.

In the `touch` and `overlap` junctions the partial M runs 2 units under the B’s stem, so
their shared edge has no antialiasing seam.
In every junction the inner shadow, a filter on the pair, treats them as one shape.

## Colors

The file overview paints each file-type family with `ToneBand.at(family.hue, position)`
from `src/metabrowser/color_oklch.py`. The JavaScript family (hue 102.08, from GitHub’s
#f1e05a) paints oklch(68% 0.1425 102.08), #AA9A00, on the light theme and #D4C43E on the
dark.
The Markdown family (hue 276.0) paints oklch(50% 0.1856 276), #4C50CA, and #717DE5.

The sister app’s fills are #84FA9F, oklch(89.36% 0.1651 149.47), at 84% of the chroma
sRGB holds there, and #FF9AF7, oklch(82.00% 0.1657 329.84), at 100%. Their radiance, a
gem tone, comes from that high lightness and chroma near the limit.

At the sister app’s lightness the file overview’s own hues fail: hue 102 turns lemon,
#F1DF53, and hue 276 can reach only 0.090 chroma, a pale periwinkle, #B4C0FF. So each
glyph keeps its family but moves its hue to where sRGB holds the color as a gem, and
takes the gamut-relative chroma of the sister glyph in the same role:

| Glyph | Role | Fill | Oklch | Relative chroma |
| --- | --- | --- | --- | --- |
| Partial M | The ❯ | #ECC44B, citrine | 83.38% 0.1428 90.40 | 0.84 |
| B | The K | #C896FF, amethyst | 76.03% 0.1539 304.96 | 1.00 |

The yellow moves 11.7° from the JavaScript hue toward amber, which keeps its brownish,
golden warmth, and the purple moves 29° from the Markdown hue toward violet, where sRGB
holds a saturated purple.
Both sit 0.06 below the sister glyphs’ lightness: at the sister app’s own lightness
these hues reach only 0.114 chroma and read as pastel, #F9D980 and #D5B1FF, while one
step deeper they reach 0.143 and 0.154, near the sister app’s 0.165. The two keep the
sister pair’s lightness difference, 0.074, so they balance as its green and pink do.
The review’s color sheet shows all three pairs.

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
