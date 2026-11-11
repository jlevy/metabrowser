# Metabrowser App Icon

**Status:** Draft under review.
Both masters use the `b-over` junction and the citrine and amethyst fills, so the design
can be seen in the app.
The other junctions have parameter files for comparison, and the small sizes wait on
review.

The icon is an MB mark on the sister app’s v6 icon: the same squircle, rim, panel,
sheen, border, and pressed-in letter shadow, with a partial M in a gem tone of
Metabrowser’s JavaScript color and a B in a gem tone of its Markdown color.
The B stands where the M’s right stem would, intact, and the partial M stops one glyph
gap short of it.

## Files

| Path | Holds |
| --- | --- |
| `metabrowser-icon.json` | Parameters of the release master, for official builds. |
| `metabrowser-icon-dev.json` | Parameters of the development master. |
| `metabrowser-icon-<junction>.json` | Parameters of the other junctions (`gap`, `bevel`, `corner-bevel`, `touch`, `overlap`, and a dev `bevel`), for review only. |
| `base-release.svg`, `base-dev.svg` | The sister app’s v6 icon structure with an empty glyph group: the release base and the canary scheme, a gold rim and a warm sheen. |
| `metabrowser-icon*.svg` | The masters, generated from the parameters and the base; edit those, not these. |
| `make-glyphs.swift` | Builds a master from a parameter file, validates the parameters, and prints the derived dimensions. |
| `render-svg.swift` | Renders a master to PNG at any size that divides 2048. |
| `review-sheet.swift` | Lays out the review images. |
| `../scripts/build-icon.sh` | Regenerates every master, builds `Resources/AppIcon.icns` and `Resources/AppIcon-Dev.icns`, and with `--review`, the review images. |

## Regenerate

```shell
scripts/build-icon.sh                   # from apps/macos: every master and both .icns files
scripts/build-icon.sh --review          # also AppIcon/review/, which git ignores
```

Add `--sister FILE.svg`, the sister app’s v6 release export, to include side-by-side
comparisons in the review.
The script needs only the Swift toolchain and macOS frameworks, and it writes
byte-identical files on every run.

To adjust the design, change a value in a parameter file and rerun the script.
`make-glyphs.swift` prints every derived dimension (stem edges, the M’s axis, the face
or bevel positions, the mark’s width) for each master, and it refuses parameters that
are out of order, outside sRGB, or that would leave a flat or a fragment thinner than
`minSliver`.

## Parameters

Units are the 512-unit master.
The font measurements are Reddit Mono Bold (wght 700) at 232 px, the face and size of
the sister app’s K, in font units (2048 per em) times 232/2048. A parameter file may
omit a parameter to take its default, which is the value below; names starting with `_`
are comments, and any other unknown name is refused.

| Parameter | Default | Meaning and source |
| --- | --- | --- |
| `variant` | `release` | The base: `release` or `dev` (the canary scheme). |
| `junction` | `gap` | How the M’s rising diagonal meets the B’s stem: `gap`, `bevel`, `touch`, or `overlap` (below). |
| `gap` | 21.437 | The space between the partial M and the B: face to stem (`gap`) or the channel (`bevel`). The sister app’s least distance between its glyphs. |
| `gapMeasure` | `perpendicular` | For the bevels: the channel measured square to the diagonal or `horizontal`. |
| `cornerCut` | 0.5 | For `corner-bevel`: how far the B’s corner cut runs along the cap line, in B stems; it runs 1/tan(`angle`) times as far down the stem. Below 0.779 the diagonal stops short of the B’s stem. |
| `faceTopFlat` | 1 | For `gap`: the diagonal’s flat top in stems, which places the vertical face; 1 puts it at the first stem’s outer edge mirrored on the M’s axis. |
| `stem` | 31.464 | The partial M’s stem: the B’s stem, 277.75 font units. The B keeps the font’s stem. |
| `diagonal` | 31.464 | The diagonals’ thickness, square to the stroke: the K’s arms, which are stem weight. |
| `angle` | 28.9993 | The diagonals’ angle from vertical in degrees: the font M’s outer diagonal edge. |
| `capLine` | 172.023 | The cap line, as y: cap height 1474 font units above the baseline. |
| `baseline` | 339 | The baseline, as y: the sister app’s K (Figma snaps 339.10 to 339). |
| `crotch` | 239.451 | Where the diagonals’ upper edges meet, as y: the font M’s, 878.781 font units. |
| `vertexFlat` | 284.418 | The flat cut under the vertex, as y: the font M’s, 481.828 font units. |
| `centroidX` | 262.598 | The x of the pair’s area centroid: the sister app’s glyph pair, so both marks balance alike. |
| `bSize` | 232 | The B’s size in px per em: the sister app’s K. |
| `overlapTopFlat` | 0.697 | For `overlap`: the stem top before the diagonal starts, as a fraction of the stem: the font M’s. |
| `minSliver` | 6 | The thinnest part a cut may leave: a thinner wedge of the B’s stem is trimmed (`bevel`), and parameters that would leave a thinner flat or a smaller fragment are refused. |
| `fills` | `#ECC44B`, `#C896FF` | The partial M’s and the B’s fills, as `#RRGGBB` or `oklch(L% C H)` (see Colors). |

## The Base

The bases are the sister app’s v6 icon as Figma exports it to SVG, copied verbatim with
the glyph group emptied, including Figma’s element ids, so a diff of a master against
the export shows only what changed.
In the Figma document the rim is a 376-unit square with a 65-unit corner radius at 60%
corner smoothing and a 29-unit outside stroke.
The panel is 364 units with a 60-unit radius at the same smoothing, a 9-unit outside
border, and a drop shadow of radius 10 and spread 9 at 20% black.
The sheen is a second panel-shaped fill with a diagonal gradient.
The export bakes the smoothing into the paths and turns the effects into filters with
the same parameters.

One change from the export: the export draws the panel’s outside border as an 18-unit
stroke masked to the panel’s outside, and any SVG renderer then leaves a translucent
seam where the panel’s antialiased edge meets the mask’s. The bases draw the same
stroke, unmasked, under the panel fill, which paints what Figma paints.

## The Glyphs

The sister app’s letters are live text in its Figma document.
The K is Reddit Mono Bold at 232 px, unedited: its exported outline matches the font’s
own K within 0.063 units.
The ❯ is U+276F, which Reddit Mono lacks, so Figma drew it from a fallback font at 182
px; it is resized, not edited.

The Parameters table above gives every dimension and its source.

The B is the font’s own outline, unedited, at the K’s size and baseline, since the
sister app applied no edits to its K. Its outline coordinates are copied into
`make-glyphs.swift`; Reddit Mono is copyright 2020-23 Reddit, Inc., under the SIL Open
Font License 1.1, and the font itself is not used or shipped.

The partial M is drawn: a stem, and two diagonal bands between parallel edges, cut flat
on the cap line and on the vertex line.
The first diagonal leaves the stem’s top-right corner, so the stem stays a clean
rectangle. The `junction` parameter chooses how the second diagonal meets the B’s stem:

- **b-over** (in the masters): the B’s stem stands where the M’s right stem would, and
  the B is intact. A vertical cut ends the diagonal one gap, 21.437, left of the B’s
  stem. The cut lies left of where the diagonal meets the cap line, so the diagonal keeps
  no flat top: it ends 38.674 below the cap line in a 61° point, with a 64.901-unit
  vertical face, and keeps 15.938 units across right of the M’s axis.
  The mark is 218 units wide.
- **corner-bevel**: the diagonal runs to the cap line, and the B’s top-left corner is
  cut parallel to it, one channel away; `cornerCut` sizes the corner and so places the
  B. At 0.5 the cut is 15.732 along the cap line and 28.382 down the stem, the diagonal
  stops 8.778 short of the stem, and the mark is 263 units wide.
  A channel this wide is 24.510 across, so a diagonal reaching over the stem would take
  at least 44 units off it, as `bevel` does.
- **gap**: a vertical cut ends it where the first stem’s outer edge falls when mirrored
  on the M’s axis. Its top is then a flat cut one stem wide that meets an 8.137-unit
  vertical face at a right angle, and the partial M is symmetric about its axis but for
  the missing stem. The B’s stem follows 21.437 units beyond the face.
  The mark is 271 units wide, against the sister app’s 222.
- **bevel** (the alternate): the B’s stem stands where the M’s right stem would, and the
  diagonal runs at full width over it to the cap line.
  The B is cut by one straight line parallel to the diagonal, a 21.437-unit channel from
  it (24.510 measured across), which takes off the B’s upper-left corner.
  Above the B’s middle bar the bevel would leave only a wedge of its stem, 9.642 wide at
  its base, so the stem is trimmed there, on the font’s axes.
  The mark is 218 units wide.
- **touch**: its upper edge ends on the B stem’s top-left corner, so the B’s stem joins
  the M; the mark is 218 units wide.
- **overlap**: it runs into the B’s stem as in the font’s M, whose stem tops are 70% of
  the stem width; the mark is 199 units wide.

The gap is the sister app’s least distance between its glyphs, from the ❯’s tip to the
K’s stem, so the vertical face sits as close to the B as that tip does to the K.
Optically the two gaps are close too: capping clearance at twice the gap, the mean
clearance over the cap height is 39.3 units here and 38.1 in the sister app, whose tip
leaves open space above and below it where the face leaves it only below.
The `bevel` channel is a long run of parallel edges, which reads at about its width; the
review’s channel sweep shows 15, 18, 21.437, and 26.

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
