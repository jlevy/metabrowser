#!/usr/bin/env bash
# Regenerates the app icons from the SVG masters in AppIcon/ (see AppIcon/README.md):
#   Resources/AppIcon.icns       official builds, from AppIcon/metabrowser-icon.svg
#   Resources/AppIcon-Dev.icns   development builds, from AppIcon/metabrowser-icon-dev.svg
# Every size is rendered from the vector master by AppIcon/render-svg.swift, which needs only
# the Swift toolchain and macOS frameworks.
#
# Usage: scripts/build-icon.sh [--review] [--sister SISTER.svg]
#   --review          also write review images to AppIcon/review/ (ignored by git)
#   --sister FILE     with --review, add side-by-side comparisons with the sister app's icon
set -euo pipefail

cd "$(dirname "$0")/.."
review=0
sister=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --review) review=1 ;;
    --sister) sister="$2"; shift ;;
    *) echo "usage: scripts/build-icon.sh [--review] [--sister SISTER.svg]" >&2; exit 2 ;;
  esac
  shift
done

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
swiftc -O AppIcon/render-svg.swift -o "$work/render-svg"

# Renders a master at the sizes an .iconset needs, once per distinct pixel size.
icns() {
  local master="$1" out="$2" set
  set="$work/$(basename "$out" .icns).iconset"
  mkdir -p "$set"
  "$work/render-svg" "$master" \
    "$set/icon_16x16.png" 16 "$set/icon_32x32.png" 32 "$set/icon_32x32@2x.png" 64 \
    "$set/icon_128x128.png" 128 "$set/icon_256x256.png" 256 "$set/icon_512x512.png" 512 \
    "$set/icon_512x512@2x.png" 1024
  cp "$set/icon_32x32.png" "$set/icon_16x16@2x.png"
  cp "$set/icon_256x256.png" "$set/icon_128x128@2x.png"
  cp "$set/icon_512x512.png" "$set/icon_256x256@2x.png"
  iconutil -c icns "$set" -o "$out"
  echo "wrote $out"
}
icns AppIcon/metabrowser-icon.svg Resources/AppIcon.icns
icns AppIcon/metabrowser-icon-dev.svg Resources/AppIcon-Dev.icns

[[ "$review" == 1 ]] || exit 0

# ── Review images ──────────────────────────────────────────────
out=AppIcon/review
mkdir -p "$out"
swiftc -O AppIcon/make-glyphs.swift -o "$work/make-glyphs"
swiftc -O AppIcon/review-sheet.swift -o "$work/review-sheet"
render="$work/render-svg"
sheet="$work/review-sheet"
bg="#ECECEC"
ink="#202020"

"$render" AppIcon/metabrowser-icon.svg "$out/metabrowser-icon-1024.png" 1024
"$render" AppIcon/metabrowser-icon-dev.svg "$out/metabrowser-icon-dev-1024.png" 1024

# Junction options: how the M's second diagonal meets the B's stem.
for junction in gap touch overlap; do
  "$work/make-glyphs" AppIcon/metabrowser-icon.svg "$work/junction-$junction.svg" "$junction" >/dev/null
  "$render" "$work/junction-$junction.svg" "$work/junction-$junction-1024.png" 1024 \
    "$work/junction-$junction-64.png" 64
done
{
  echo "canvas 3240 1400 $bg"
  x=40
  for junction in gap touch overlap; do
    echo "image $work/junction-$junction-1024.png $x 90"
    echo "image $work/junction-$junction-64.png $((x + 480)) 1150"
    echo "text $x 30 40 $ink bold $junction"
    x=$((x + 1060))
  done
  echo "text 40 1230 28 $ink 64 px, actual size, under each option above"
} >"$work/junctions.spec"
"$sheet" "$work/junctions.spec" "$out/junction-options-1024-and-64.png"

# Construction guides over the release master: cap line, baseline, crotch and vertex lines,
# stem edges, the vertical face, the M's axis, and both diagonals' edges.
"$work/make-glyphs" AppIcon/metabrowser-icon.svg "$work/master-copy.svg" gap \
  --guides "$work/guides.svg" --dims "$work/dims.sh" >/dev/null
# shellcheck disable=SC1091
source "$work/dims.sh"
"$render" "$work/guides.svg" "$work/guides-1024.png" 1024
{
  echo "canvas 1024 1210 $bg"
  echo "image $out/metabrowser-icon-1024.png 0 0"
  echo "image $work/guides-1024.png 0 0"
  echo "text 24 1034 22 $ink bold Construction, in the 512-unit master (Reddit Mono Bold at 232 px, font units x 232/2048)"
  echo "text 24 1066 20 $ink Cyan: cap line $top, crotch $crotchY, vertex flat $vertexY, baseline $baseline; stem edges ($w);"
  echo "text 24 1092 20 $ink the vertical face at $rightEdge, the first stem's outer edge mirrored on the axis; the B's stem $gap beyond."
  echo "text 24 1122 20 $ink Pink: the M's axis; diagonal edges at 29.0 degrees (the font M's), $w thick (the K's arms)."
  echo "text 24 1152 20 $ink Crotch and vertex heights are the font M's; the B is the font's B on the K's origin line and baseline."
} >"$work/construction.spec"
"$sheet" "$work/construction.spec" "$out/construction-guides-1024.png"

# The junction at 4x the 1024 px icon (8 px per master unit), with the gap dimensioned.
"$render" AppIcon/metabrowser-icon.svg "$work/master-2048.png" 2048
read -r cx cy cw ch <<<"$(awk -v r="$rightEdge" -v b="$xB" -v t="$top" \
  'BEGIN { printf "%d %d %d %d", (r - 45) * 4, (t - 18) * 4, (b - r + 90) * 4, 82 * 4 }')"
X() { awk -v x="$1" -v r="$rightEdge" 'BEGIN { printf "%d", (x - (r - 45)) * 8 }'; }
Y() { awk -v y="$1" -v t="$top" 'BEGIN { printf "%d", (y - (t - 18)) * 8 + 70 }'; }
xf=$(X "$rightEdge")
xs=$(X "$xB")
yt=$(Y "$top")
yf=$(Y "$faceBottom")
ydim=$(Y "$(awk -v t="$top" 'BEGIN { print t + 4 }')")
face=$(awk -v a="$faceBottom" -v b="$top" 'BEGIN { printf "%.3f", a - b }')
red="#FF3B6B"
{
  echo "canvas $((cw * 2)) $((ch * 2 + 190)) $bg"
  echo "text 24 20 26 $ink bold The junction at 4x: the M's vertical face, the gap, and the B's stem"
  echo "image $work/master-2048.png 0 70 $((cw * 2)) $((ch * 2)) smooth $cx $cy $cw $ch"
  echo "line $xf $((yt - 60)) $xf $((yt + 120)) 2 $red"
  echo "line $xs $((yt - 60)) $xs $((yt + 120)) 2 $red"
  echo "line $xf $ydim $xs $ydim 3 $red"
  echo "line $((xf - 24)) $yt $((xf - 24)) $yf 3 #00D8FF"
  echo "text $((xf + 6)) $((yt - 52)) 22 #FFFFFF bold gap $gap"
  echo "text $((xf + 10)) $((yf - 6)) 20 #FFFFFF face $face"
  echo "text 24 $((ch * 2 + 90)) 22 $ink Gap: the face at x $rightEdge to the B's stem at x $xB is $gap units,"
  echo "text 24 $((ch * 2 + 122)) 22 $ink the sister app's least distance, from its chevron's tip to its K's stem."
  echo "text 24 $((ch * 2 + 154)) 22 $ink The top flat is one stem wide ($w); it meets the face at a right angle."
} >"$work/junction-zoom.spec"
"$sheet" "$work/junction-zoom.spec" "$out/junction-closeup-4x.png"

# Colors: the sister app's lightness, one step deeper (the masters), and the exact hues.
pairs=("#F9D980,#D5B1FF" "#ECC44B,#C896FF" "#F1DF53,#B4C0FF")
labels=(
  "1. Citrine and amethyst at the sister app's lightness|M #F9D980 oklch(89.36% 0.1143 90.23), relative chroma 0.83|B #D5B1FF oklch(81.91% 0.1135 305.15), relative chroma 1.00"
  "2. One step deeper, lightness -0.06 (in the masters)|M #ECC44B oklch(83.38% 0.1428 90.40), relative chroma 0.84|B #C896FF oklch(76.03% 0.1539 304.96), relative chroma 1.00"
  "3. The file overview's own hues, 102.08 and 276|M #F1DF53 oklch(89.34% 0.1570 101.94), relative chroma 0.84|B #B4C0FF oklch(82.10% 0.0898 275.89), relative chroma 1.00"
)
for i in 0 1 2; do
  "$work/make-glyphs" AppIcon/metabrowser-icon.svg "$work/color-$i.svg" gap --fills "${pairs[$i]}" >/dev/null
  "$render" "$work/color-$i.svg" "$work/color-$i-1024.png" 1024
done
columns=3
[[ -n "$sister" ]] && columns=4
{
  echo "canvas $((columns * 1064 + 40)) 1220 $bg"
  x=40
  if [[ -n "$sister" ]]; then
    "$render" "$sister" "$work/sister-1024.png" 1024
    echo "image $work/sister-1024.png $x 40"
    echo "text $x 1090 26 $ink bold The sister app"
    echo "text $x 1130 22 $ink #84FA9F oklch(89.36% 0.1651 149.47), relative chroma 0.84"
    echo "text $x 1162 22 $ink #FF9AF7 oklch(82.00% 0.1657 329.84), relative chroma 1.00"
    x=$((x + 1064))
  fi
  for i in 0 1 2; do
    IFS='|' read -r title first second <<<"${labels[$i]}"
    echo "image $work/color-$i-1024.png $x 40"
    echo "text $x 1090 26 $ink bold $title"
    echo "text $x 1130 22 $ink $first"
    echo "text $x 1162 22 $ink $second"
    x=$((x + 1064))
  done
} >"$work/colors.spec"
"$sheet" "$work/colors.spec" "$out/color-comparison-1024.png"

# Small sizes, each at actual size and magnified with nearest-neighbor sampling.
for variant in metabrowser-icon metabrowser-icon-dev; do
  "$render" "AppIcon/$variant.svg" "$work/$variant-16.png" 16 "$work/$variant-32.png" 32 \
    "$work/$variant-64.png" 64 "$work/$variant-128.png" 128 "$work/$variant-256.png" 256
  {
    echo "canvas 1880 820 $bg"
    echo "text 30 20 28 $ink bold $variant: 16, 32, 64, 128, and 256 px at actual size (top) and magnified (bottom)"
    x=30
    for size in 16 32 64 128 256; do
      echo "image $work/$variant-$size.png $x $((330 - size))"
      echo "text $x 345 20 $ink $size px"
      x=$((x + size + 60))
    done
    x=30
    for size in 16 32 64; do
      echo "image $work/$variant-$size.png $x 400 384 384 nearest"
      x=$((x + 420))
    done
    echo "text 1290 520 20 $ink Magnified 24x, 12x, and 6x"
  } >"$work/strip.spec"
  "$sheet" "$work/strip.spec" "$out/$variant-small-sizes.png"
done

# Side by side with the sister app's icon, at 512 and 64 px.
if [[ -n "$sister" ]]; then
  "$render" "$sister" "$work/sister-512.png" 512 "$work/sister-64.png" 64
  "$render" AppIcon/metabrowser-icon.svg "$work/mb-512.png" 512 "$work/mb-64.png" 64
  "$render" AppIcon/metabrowser-icon-dev.svg "$work/mbdev-64.png" 64
  {
    echo "canvas 1124 700 $bg"
    echo "image $work/sister-512.png 30 40"
    echo "image $work/mb-512.png 582 40"
    echo "image $work/sister-64.png 400 600"
    echo "image $work/mb-64.png 530 600"
    echo "image $work/mbdev-64.png 660 600"
    echo "text 30 560 22 $ink At 512 px (top) and 64 px (bottom): the sister app, then Metabrowser, then its dev icon."
  } >"$work/sister.spec"
  "$sheet" "$work/sister.spec" "$out/side-by-side-sister-512-and-64.png"
fi
echo "wrote review images to $out/"
