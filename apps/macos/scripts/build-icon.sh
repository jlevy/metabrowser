#!/usr/bin/env bash
# Regenerates the app icons from the parameter files in AppIcon/ (see AppIcon/README.md).
# Each AppIcon/metabrowser-icon*.json makes the master SVG of the same name, and two of the
# masters become the icons:
#   Resources/AppIcon.icns       official builds, from AppIcon/metabrowser-icon.json
#   Resources/AppIcon-Dev.icns   development builds, from AppIcon/metabrowser-icon-dev.json
# Every size is rendered from the vector master by AppIcon/render-svg.swift. The script needs
# only the Swift toolchain and macOS frameworks.
#
# Usage: scripts/build-icon.sh [--check | --review] [--sister SISTER.svg]
#   --check           only check that the renderer refuses every file in AppIcon/rejects/
#   --review          also write review images to AppIcon/review/ (ignored by git)
#   --sister FILE     with --review, add side-by-side comparisons with the sister app's icon
set -euo pipefail

cd "$(dirname "$0")/.."
review=0
check_only=0
sister=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) check_only=1 ;;
    --review) review=1 ;;
    --sister) sister="$2"; shift ;;
    *) echo "usage: scripts/build-icon.sh [--check | --review] [--sister SISTER.svg]" >&2; exit 2 ;;
  esac
  shift
done

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
swiftc -O AppIcon/render-svg.swift -o "$work/render-svg"

# The renderer must refuse every file in AppIcon/rejects/, each with the reason its first
# line names, and promptly: an unsupported attribute once rendered without one, and a
# malformed path once hung the renderer instead of stopping it.
for fixture in AppIcon/rejects/*.svg; do
  reason="$(sed -n '1s/^<!-- render-svg refuses: \(.*\) -->$/\1/p' "$fixture")"
  [[ -n "$reason" ]] || { echo "$fixture: its first line must be <!-- render-svg refuses: REASON -->" >&2; exit 1; }
  "$work/render-svg" --internal 16 "$fixture" "$work/rejected.png" 16 2>"$work/rejected.txt" &
  renderer=$!
  (sleep 10 && kill -9 "$renderer" 2>/dev/null) &
  watchdog=$!
  if wait "$renderer"; then
    echo "$fixture: render-svg accepted it; it must refuse it: $reason" >&2
    exit 1
  fi
  kill "$watchdog" 2>/dev/null || true
  grep -qF -- "$reason" "$work/rejected.txt" || {
    echo "$fixture: render-svg must refuse it with \"$reason\", not: $(cat "$work/rejected.txt")" >&2
    exit 1
  }
done
echo "render-svg refuses all $(ls AppIcon/rejects/*.svg | wc -l | tr -d ' ') files in AppIcon/rejects/"
[[ "$check_only" == 0 ]] || exit 0

swiftc -O AppIcon/make-glyphs.swift -o "$work/make-glyphs"

# Every master comes from its parameter file and the variant's base.
for params in AppIcon/metabrowser-icon*.json; do
  "$work/make-glyphs" "$params" "${params%.json}.svg"
done

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

# Review images.
out=AppIcon/review
mkdir -p "$out" "$out/icns"
swiftc -O AppIcon/review-sheet.swift -o "$work/review-sheet"
render="$work/render-svg"
sheet="$work/review-sheet"
bg="#ECECEC"
ink="#202020"
red="#FF3B6B"
cyan="#00D8FF"

"$render" AppIcon/metabrowser-icon.svg "$out/metabrowser-icon-1024.png" 1024
"$render" AppIcon/metabrowser-icon-dev.svg "$out/metabrowser-icon-dev-1024.png" 1024
# The masters' name in the review images; "default", not a junction name, since an alternate
# may share the masters' junction.
default_name=default

# Every release variant: its junction, a 1024 px render, a 64 px render, its width, and a
# release .icns to swap into a built app for comparison in the Dock. The junction alternates go
# on one sheet; the symmetry (sym-*) and |\B (norise-*) families go on the refresh sheet.
variants=("$default_name")
junctions=("$default_name")
sym=()
norise=()
for params in AppIcon/metabrowser-icon-*.json; do
  name=$(basename "$params" .json)
  name=${name#metabrowser-icon-}
  [[ "$name" == dev* ]] && continue
  variants+=("$name")
  case "$name" in
    sym-*) sym+=("$name") ;;
    norise-*) norise+=("$name") ;;
    *) junctions+=("$name") ;;
  esac
done
# The release parameter file of a variant, a string parameter from it, and its width (macOS's
# bash has no hash tables).
params_of() { if [[ "$1" == "$default_name" ]]; then echo AppIcon/metabrowser-icon.json; else echo "AppIcon/metabrowser-icon-$1.json"; fi; }
param_of() { sed -n "s/.*\"$2\": \"\\([^\"]*\\)\".*/\\1/p" "$(params_of "$1")"; }
dim_of() { sed -n "s/^$2=//p" "$work/$1.dims"; }
width_of() { dim_of "$1" inkWidth; }
# How a variant's partial M ends, in words, and where, for captions.
bar_word() {
  case "$1" in
    barTop) echo "the bar's top" ;; barCenter) echo "the bar's center" ;;
    barBottom) echo "the bar's bottom" ;; vertex) echo "the vertex flat" ;; *) echo "$1" ;;
  esac
}
end_of() {
  local face floor
  if [[ "$(param_of "$1" junction)" == no-rise ]]; then
    face=$(param_of "$1" endFace)
    floor=$(param_of "$1" endFloor)
    if [[ "$face" == none ]]; then echo "horizontal cut at $(bar_word "$floor")"; else
      echo "vertical face from $(bar_word "$face") to $(bar_word "$floor")"; fi
  else
    awk -v t="$(dim_of "$1" top)" -v f="$(dim_of "$1" faceTop)" -v w="$(dim_of "$1" topFlat)" 'BEGIN {
      if (w + 0 > 0) printf "flat top %.3f wide on the cap line", w
      else if (f - t < 0.0005) printf "point on the cap line"
      else printf "point %.3f below the cap line", f - t }'
  fi
}
detail_of() {
  if [[ "$(param_of "$1" junction)" == no-rise ]]; then
    awk -v e="$(dim_of "$1" endBottom)" -v c="$(dim_of "$1" crotchY)" -v f="$(dim_of "$1" vertexY)" \
      'BEGIN { printf "ends at y %.3f: %.3f below the crotch, %.3f above the vertex flat", e, e - c, f - e }'
  else
    awk -v a="$(dim_of "$1" faceTop)" -v b="$(dim_of "$1" faceBottom)" -v r="$(dim_of "$1" rightEdge)" -v m="$(dim_of "$1" xm)" \
      'BEGIN { printf "vertical face from y %.3f to %.3f, %.3f right of the axis", a, b, r - m }'
  fi
}
# How far the B's stem moved right from the M's stem, and in the icon, against the default.
shift_of() {
  awk -v b="$(dim_of "$1" xB)" -v x="$(dim_of "$1" x0)" -v rb="$(dim_of "$default_name" xB)" \
    -v rx="$(dim_of "$default_name" x0)" 'BEGIN { printf "%+.3f from the M'"'"'s stem, %+.3f in the icon", (b - x) - (rb - rx), b - rb }'
}
for v in "${variants[@]}"; do
  "$work/make-glyphs" "$(params_of "$v")" "$work/$v.svg" --dims "$work/$v.dims" >/dev/null
  "$render" "$work/$v.svg" "$work/$v-2048.png" 2048 "$out/variant-$v-1024.png" 1024 "$work/$v-64.png" 64
  icns "$work/$v.svg" "$out/icns/AppIcon-$v.icns" >/dev/null
done
if [[ -f AppIcon/metabrowser-icon-dev-bevel.json ]]; then
  "$render" AppIcon/metabrowser-icon-dev-bevel.svg "$out/variant-bevel-dev-1024.png" 1024
fi

# The junction alternates side by side, with the sister app, at 1024 and 64 px.
count=${#junctions[@]}
[[ -n "$sister" ]] && count=$((count + 1))
{
  echo "canvas $((count * 1064 + 40)) 1290 $bg"
  x=40
  if [[ -n "$sister" ]]; then
    "$render" "$sister" "$work/sister-1024.png" 1024 "$work/sister-64.png" 64
    echo "image $work/sister-1024.png $x 70"
    echo "image $work/sister-64.png $((x + 480)) 1120"
    echo "text $x 20 30 $ink bold The sister app: 222 units wide"
    x=$((x + 1064))
  fi
  for v in "${junctions[@]}"; do
    label="$v"
    [[ "$v" == "$default_name" ]] && label="the default"
    echo "image $out/variant-$v-1024.png $x 70"
    echo "image $work/$v-64.png $((x + 480)) 1120"
    echo "text $x 20 30 $ink bold $label: $(width_of "$v") units wide"
    x=$((x + 1064))
  done
  echo "text 40 1220 24 $ink 64 px, actual size, under each icon. Release .icns files for each are in review/icns/."
} >"$work/compare.spec"
"$sheet" "$work/compare.spec" "$out/variants-1024-and-64.png"

# The refresh: the symmetry and |\B families, a row each after the default, each family in order
# of how far the B's stem stands from the M's stem: at 1024 and 64 px, and at 64 px magnified.
by_shift() {
  local v
  for v in "$@"; do
    awk -v b="$(dim_of "$v" xB)" -v x="$(dim_of "$v" x0)" -v n="$v" 'BEGIN { printf "%.3f %s\n", b - x, n }'
  done | sort -n | cut -d' ' -f2
}
family_title() {
  if [[ "$1" == sym ]]; then
    echo "Symmetry: the M's cut moves up toward the cap line, and the gap widens toward a stem (31.464)"
  else
    echo "|\\B: no rising diagonal; the falling diagonal's end lines up with the B's middle bar"
  fi
}
rows=0
cols=0
for family in sym norise; do
  if [[ "$family" == sym ]]; then n=${#sym[@]}; else n=${#norise[@]}; fi
  ((n > 0)) && rows=$((rows + 1))
  ((n > cols)) && cols=$n
done
if ((rows > 0)); then
  {
    echo "canvas $(((cols + 1) * 1064 + 40)) $((rows * 1372 + 110)) $bg"
    y=30
    for family in sym norise; do
      # shellcheck disable=SC2207
      if [[ "$family" == sym ]]; then members=($(by_shift ${sym[@]+"${sym[@]}"})); else
        members=($(by_shift ${norise[@]+"${norise[@]}"})); fi
      ((${#members[@]} > 0)) || continue
      echo "text 40 $y 34 $ink bold $(family_title "$family")"
      x=40
      for v in "$default_name" "${members[@]}"; do
        label="$v"
        [[ "$v" == "$default_name" ]] && label="the default, for reference"
        echo "text $x $((y + 60)) 28 $ink bold $label"
        echo "text $x $((y + 102)) 24 $ink $(end_of "$v"); gap $(dim_of "$v" gap)"
        echo "text $x $((y + 136)) 24 $ink $(detail_of "$v")"
        echo "text $x $((y + 170)) 24 $ink $(width_of "$v") wide; B's stem vs. the default: $(shift_of "$v")"
        echo "image $out/variant-$v-1024.png $x $((y + 214))"
        echo "image $work/$v-64.png $((x + 480)) $((y + 1262))"
        x=$((x + 1064))
      done
      y=$((y + 1372))
    done
    echo "text 40 $y 24 $ink 64 px, actual size, under each icon. Release .icns files for each are in review/icns/; 4x close-ups are closeup-*-4x.png."
  } >"$work/refresh.spec"
  "$sheet" "$work/refresh.spec" "$out/refresh-1024-and-64.png"

  # The same icons at 64 px only: actual size, then magnified 4x with nearest-neighbor sampling.
  {
    echo "canvas $(((cols + 1) * 320 + 40)) $((rows * 470 + 90)) $bg"
    y=30
    for family in sym norise; do
      # shellcheck disable=SC2207
      if [[ "$family" == sym ]]; then members=($(by_shift ${sym[@]+"${sym[@]}"})); else
        members=($(by_shift ${norise[@]+"${norise[@]}"})); fi
      ((${#members[@]} > 0)) || continue
      echo "text 40 $y 26 $ink bold $(family_title "$family")"
      x=40
      for v in "$default_name" "${members[@]}"; do
        echo "image $work/$v-64.png $((x + 96)) $((y + 50))"
        echo "image $work/$v-64.png $x $((y + 134)) 256 256 nearest"
        echo "text $x $((y + 400)) 18 $ink $v"
        x=$((x + 320))
      done
      y=$((y + 470))
    done
    echo "text 40 $y 22 $ink Each at 64 px: actual size (top) and magnified 4x (bottom). The first in each row is today's default."
  } >"$work/refresh-64.spec"
  "$sheet" "$work/refresh-64.spec" "$out/refresh-64-px.png"
fi

# 4x close-ups of each junction (8 px per master unit), from the 2048 px renders.
# closeup VARIANT X0 Y0 X1 Y1: crops the master region and writes the sheet header.
closeup() {
  local v="$1"
  cox="$2"; coy="$3"
  read -r cx cy cw ch <<<"$(awk -v a="$2" -v b="$3" -v c="$4" -v d="$5" \
    'BEGIN { printf "%d %d %d %d", a * 4, b * 4, (c - a) * 4, (d - b) * 4 }')"
  {
    echo "canvas $((cw * 2)) $((ch * 2 + 232)) $bg"
    echo "image $work/$v-2048.png 0 70 $((cw * 2)) $((ch * 2)) smooth $cx $cy $cw $ch"
  } >"$work/closeup-$v.spec"
}
P() { awk -v x="$1" -v y="$2" -v ox="$cox" -v oy="$coy" 'BEGIN { printf "%d %d", (x - ox) * 8, (y - oy) * 8 + 70 }'; }
for v in "${variants[@]}"; do
  unset faceTop endFaceTop
  # shellcheck disable=SC1090
  source "$work/$v.dims"
  junction=$(param_of "$v" junction)
  case "${junction:-gap}" in
    gap | b-over)
      ft=${faceTop:-$top}
      closeup "$v" "$(awk -v r="$rightEdge" 'BEGIN { print r - 45 }')" "$(awk -v t="$top" 'BEGIN { print t - 18 }')" \
        "$(awk -v b="$xB" 'BEGIN { print b + 45 }')" "$(awk -v f="$faceBottom" 'BEGIN { print f + 25 }')"
      read -r fx fy <<<"$(P "$rightEdge" "$ft")"
      read -r _ fb <<<"$(P "$rightEdge" "$faceBottom")"
      read -r sx _ <<<"$(P "$xB" "$ft")"
      gy=$(( (fy + fb) / 2 ))
      face=$(awk -v a="$faceBottom" -v b="$ft" 'BEGIN { printf "%.3f", a - b }')
      {
        echo "text 24 20 26 $ink bold $v at 4x: the M's vertical face, the gap, and the B's stem"
        echo "line $fx $((fy - 40)) $fx $((fb + 40)) 2 $red"
        echo "line $sx $((fy - 40)) $sx $((fb + 40)) 2 $red"
        echo "line $fx $gy $sx $gy 3 $red"
        echo "text $((fx + 8)) $((gy - 34)) 22 #FFFFFF bold gap $gap"
        echo "line $((fx - 16)) $fy $((fx - 16)) $fb 3 $cyan"
        echo "text $((fx - 150)) $(( (fy + fb) / 2 + 30 )) 20 #FFFFFF face $face"
        echo "text 24 $((ch * 2 + 90)) 22 $ink Gap $gap from the face (x $rightEdge) to the B's stem (x $xB);"
        echo "text 24 $((ch * 2 + 122)) 22 $ink the face is $face tall, from y $ft to $faceBottom; the mark is $(width_of "$v") wide."
        echo "text 24 $((ch * 2 + 154)) 22 $ink The diagonal ends in a $(end_of "$v")."
        echo "text 24 $((ch * 2 + 186)) 22 $ink B's stem vs. the default: $(shift_of "$v")."
      } >>"$work/closeup-$v.spec"
      ;;
    bevel | corner-bevel)
      closeup "$v" "$(awk -v d="$diagonalTopRight" -v b="$xB" 'BEGIN { m = (d - 60 < b - 40) ? d - 60 : b - 40; print m }')" \
        "$(awk -v t="$top" 'BEGIN { print t - 18 }')" \
        "$(awk -v r="$bevelAtCap" 'BEGIN { print r + 30 }')" "$(awk -v l="$bevelMeetsStemLeft" 'BEGIN { print l + 26 }')"
      read -r ax ay bx by hx1 hy hx2 <<<"$(awk -v d="$diagonalTopRight" -v t="$top" -v k="$tanTheta" \
        -v c="$channel" -v h="$channelHorizontal" 'BEGIN {
          th = atan2(k, 1); y = t + 20; x = d - (y - t) * k
          y2 = t + 44; x2 = d - (y2 - t) * k
          printf "%f %f %f %f %f %f %f", x, y, x + c * cos(th), y + c * sin(th), x2, y2, x2 + h }')"
      read -r pax pay <<<"$(P "$ax" "$ay")"
      read -r pbx pby <<<"$(P "$bx" "$by")"
      read -r ph1x phy <<<"$(P "$hx1" "$hy")"
      read -r ph2x _ <<<"$(P "$hx2" "$hy")"
      {
        echo "text 24 20 26 $ink bold $v at 4x: the M's diagonal, the channel, and the B's bevel"
        echo "line $pax $pay $pbx $pby 3 $red"
        echo "text $((pbx + 10)) $((pby - 30)) 22 #FFFFFF bold channel $channel"
        echo "line $ph1x $phy $ph2x $phy 3 $cyan"
        echo "text $((ph2x + 10)) $((phy - 12)) 20 #FFFFFF $channelHorizontal across"
        echo "text 24 $((ch * 2 + 90)) 22 $ink Channel $channel square to the diagonal ($channelHorizontal across); one straight cut at 29 degrees."
        if [[ "$junction" == corner-bevel ]]; then
          echo "text 24 $((ch * 2 + 122)) 22 $ink Corner cut $cornerCut along the cap line, $cornerCutDown down the stem; the mark is $(width_of "$v") wide."
        else
          echo "text 24 $((ch * 2 + 122)) 22 $ink The B's stem is trimmed above its middle bar (y $middleBarTop); the mark is $(width_of "$v") wide."
        fi
      } >>"$work/closeup-$v.spec"
      ;;
    no-rise)
      closeup "$v" "$(awk -v s="$stemRight" 'BEGIN { print s - 12 }')" "$(awk -v c="$crotchY" 'BEGIN { print c - 34 }')" \
        "$(awk -v b="$xBRight" 'BEGIN { print b + 28 }')" "$(awk -v y="$vertexY" 'BEGIN { print y + 22 }')"
      # The gap is drawn across the end face's middle, or just above a horizontal end's corner.
      gapY=$(awk -v a="${endFaceTop:-}" -v b="$endBottom" -v f="$endFloor" 'BEGIN { print (a == "") ? f - 3 : (a + b) / 2 }')
      read -r _ bt <<<"$(P "$xB" "$barTop")"
      read -r _ bb <<<"$(P "$xB" "$barBottom")"
      read -r lx _ <<<"$(P "$xBRight" "$barTop")"
      read -r ex gy <<<"$(P "$rightEdge" "$gapY")"
      read -r sx _ <<<"$(P "$xB" "$gapY")"
      read -r _ ty <<<"$(P "$rightEdge" "${endFaceTop:-$endFloor}")"
      read -r _ ey <<<"$(P "$rightEdge" "$endBottom")"
      {
        echo "text 24 20 26 $ink bold $v at 4x: the falling diagonal's end, the gap, and the B's middle bar"
        echo "line 0 $bt $((cw * 2)) $bt 2 $cyan"
        echo "line 0 $bb $((cw * 2)) $bb 2 $cyan"
        echo "text $((lx + 10)) $((bt - 30)) 20 #FFFFFF bar top $barTop"
        echo "text $((lx + 10)) $((bb + 8)) 20 #FFFFFF bar bottom $barBottom"
        echo "line $ex $((ty - 40)) $ex $((ey + 40)) 2 $red"
        echo "line $sx $((ty - 40)) $sx $((ey + 40)) 2 $red"
        echo "line $ex $gy $sx $gy 3 $red"
        echo "text $((ex + 8)) $((gy - 34)) 22 #FFFFFF bold gap $gap"
        echo "text 24 $((ch * 2 + 90)) 22 $ink End: $(end_of "$v")."
        echo "text 24 $((ch * 2 + 122)) 22 $ink It $(detail_of "$v")."
        echo "text 24 $((ch * 2 + 154)) 22 $ink Gap $gap from its rightmost point (x $rightEdge) to the B's stem (x $xB); the bar is $barThickness thick."
        echo "text 24 $((ch * 2 + 186)) 22 $ink Mark $(width_of "$v") wide. B's stem vs. the default: $(shift_of "$v")."
      } >>"$work/closeup-$v.spec"
      ;;
    *) continue ;;
  esac
  "$sheet" "$work/closeup-$v.spec" "$out/closeup-$v-4x.png"
done
unset faceTop endFaceTop

# Construction guides over the release master: cap line, baseline, crotch and vertex lines,
# stem edges, the vertical face, the M's axis, and both diagonals' edges.
"$work/make-glyphs" AppIcon/metabrowser-icon.json "$work/master-copy.svg" \
  --guides "$work/guides.svg" --dims "$work/dims.sh" >/dev/null
# shellcheck disable=SC1091
source "$work/dims.sh"
"$render" "$work/guides.svg" "$work/guides-1024.png" 1024
{
  echo "canvas 1024 1180 $bg"
  echo "image $out/metabrowser-icon-1024.png 0 0"
  echo "image $work/guides-1024.png 0 0"
  echo "text 24 1034 22 $ink bold Construction, in the 512-unit master (Reddit Mono Bold at 232 px, font units x 232/2048)"
  echo "text 24 1066 20 $ink Cyan: cap line $top, crotch $crotchY, vertex flat $vertexY, baseline $baseline; stem edges ($w); the face."
  echo "text 24 1096 20 $ink Pink: the M's axis; diagonal edges at 29.0 degrees (the font M's), $w thick (the K's arms)."
  echo "text 24 1126 20 $ink Crotch and vertex heights are the font M's; the B is the font's B on the K's origin line and baseline."
} >"$work/construction.spec"
"$sheet" "$work/construction.spec" "$out/construction-guides-1024.png"

# Colors: the sister app's lightness, one step deeper (the masters), and the exact hues.
pairs=("#F9D980,#D5B1FF" "#ECC44B,#C896FF" "#F1DF53,#B4C0FF")
labels=(
  "1. Citrine and amethyst at the sister app's lightness|M #F9D980 oklch(89.36% 0.1143 90.23), relative chroma 0.83|B #D5B1FF oklch(81.91% 0.1135 305.15), relative chroma 1.00"
  "2. One step deeper, lightness -0.06 (in the masters)|M #ECC44B oklch(83.38% 0.1428 90.40), relative chroma 0.84|B #C896FF oklch(76.03% 0.1539 304.96), relative chroma 1.00"
  "3. The file overview's own hues, 102.08 and 276|M #F1DF53 oklch(89.34% 0.1570 101.94), relative chroma 0.84|B #B4C0FF oklch(82.10% 0.0898 275.89), relative chroma 1.00"
)
for i in 0 1 2; do
  "$work/make-glyphs" AppIcon/metabrowser-icon.json "$work/color-$i.svg" --fills "${pairs[$i]}" >/dev/null
  "$render" "$work/color-$i.svg" "$work/color-$i-1024.png" 1024
done
columns=3
[[ -n "$sister" ]] && columns=4
{
  echo "canvas $((columns * 1064 + 40)) 1220 $bg"
  x=40
  if [[ -n "$sister" ]]; then
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

# Small sizes of the masters, each at actual size and magnified with nearest-neighbor sampling.
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

# The masters side by side with the sister app's icon, at 512 and 64 px.
if [[ -n "$sister" ]]; then
  "$render" "$sister" "$work/sister-512.png" 512
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

# The bevel channel width, swept around the sister app's gap.
if [[ -f AppIcon/metabrowser-icon-bevel.json ]]; then
  cp AppIcon/base-release.svg "$work/base-release.svg"
  {
    echo "canvas 2200 640 $bg"
    echo "text 30 20 26 $ink bold Bevel channel widths, square to the diagonal, at 512 px"
    x=30
    for g in 15 18 21.437 26; do
      sed "s/\"gap\": [0-9.]*/\"gap\": $g/" AppIcon/metabrowser-icon-bevel.json >"$work/sweep.json"
      "$work/make-glyphs" "$work/sweep.json" "$work/sweep-$g.svg" >/dev/null
      "$render" "$work/sweep-$g.svg" "$work/sweep-$g.png" 512
      echo "image $work/sweep-$g.png $x 70"
      echo "text $x 590 22 $ink channel $g"
      x=$((x + 540))
    done
  } >"$work/sweep.spec"
  "$sheet" "$work/sweep.spec" "$out/bevel-channel-sweep-512.png"
fi
echo "wrote review images to $out/"
