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
for junction in touch overlap gap; do
  "$work/make-glyphs" AppIcon/metabrowser-icon.svg "$work/junction-$junction.svg" "$junction" \
    "$work/guides-$junction.svg" >/dev/null
  "$render" "$work/junction-$junction.svg" "$work/junction-$junction-1024.png" 1024 \
    "$work/junction-$junction-64.png" 64
  "$render" "$work/guides-$junction.svg" "$work/guides-$junction-1024.png" 1024
done
{
  echo "canvas 3240 1400 $bg"
  x=40
  for junction in touch overlap gap; do
    echo "image $work/junction-$junction-1024.png $x 90"
    echo "image $work/junction-$junction-64.png $((x + 480)) 1150"
    echo "text $x 30 40 $ink bold $junction"
    x=$((x + 1060))
  done
  echo "text 40 1230 28 $ink 64 px, actual size, under each option above"
} >"$work/junctions.spec"
"$sheet" "$work/junctions.spec" "$out/junction-options-1024-and-64.png"

# Construction guides over the chosen master (touch): cap line, baseline, crotch and vertex
# lines, stem edges, the M's axis, and both diagonals' edges.
"$work/make-glyphs" AppIcon/metabrowser-icon.svg "$work/master-copy.svg" touch "$work/guides.svg" >"$work/dims.txt"
"$render" "$work/guides.svg" "$work/guides-1024.png" 1024
{
  echo "canvas 1024 1180 $bg"
  echo "image $out/metabrowser-icon-1024.png 0 0"
  echo "image $work/guides-1024.png 0 0"
  echo "text 24 1034 22 $ink bold Construction, in the 512-unit master (Reddit Mono Bold at 232 px, font units x 232/2048)"
  echo "text 24 1066 20 $ink Cyan: cap line 172.023, crotch 239.451, vertex flat 284.418, baseline 339; stem edges (31.464)."
  echo "text 24 1096 20 $ink Pink: the M's axis; diagonal edges at 29.0 degrees (the font M's), 31.464 thick (the K's arms)."
  echo "text 24 1126 20 $ink Crotch and vertex heights are the font M's; the B is the font's B on the K's origin line and baseline."
} >"$work/construction.spec"
"$sheet" "$work/construction.spec" "$out/construction-guides-1024.png"

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
    echo "image $work/sister-64.png 448 600"
    echo "image $work/mb-64.png 612 600"
    echo "text 30 560 22 $ink At 512 px (top) and 64 px (bottom): the sister app, then Metabrowser."
  } >"$work/sister.spec"
  "$sheet" "$work/sister.spec" "$out/side-by-side-sister-512-and-64.png"
fi
echo "wrote review images to $out/"
