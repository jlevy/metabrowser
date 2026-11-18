#!/bin/bash
# Build the Metabrowser wheel of one commit without a second git worktree, for pr-view.mjs.
#
#   explorations/performance-loop/pr-view-wheel.sh <commit> <out-dir> <build-python>
#
# The commit's pyproject.toml, README.md, LICENSE, and src/ come from `git archive` into
# <out-dir>/src-<sha12>, and the wheel is built there by hatchling's PEP 517 hook, from
# <build-python>, an environment holding the checkout's locked `build` group, so nothing
# is resolved at build time (SUPPLY-CHAIN-SECURITY.md), as `make build`'s
# --no-build-isolation is. An archive has no .git, so the version uv-dynamic-versioning
# would read from Git is computed the same way from `git describe` and passed in
# UV_DYNAMIC_VERSIONING_BYPASS: a tag itself is its version, and a commit N past tag
# vX.Y.Z is X.Y.(Z+1).devN+<abbreviated commit>, the pep440 `bump` style pyproject.toml
# sets, with the commit abbreviated as Git's %h abbreviates it, as dunamai reads it. A
# pre-release tag is refused rather than guessed at.
# The source copy is deleted after the build. It prints the commit and version, then the
# wheel's path as the last line.
#
# Make the build environment once from the checkout:
#   uv --config-file uv.toml export --frozen --only-group build --no-emit-project \
#     --no-hashes --output-file <dir>/build-constraints.txt
#   uv --config-file uv.toml venv <dir>/build-venv
#   uv --config-file uv.toml pip install --python <dir>/build-venv/bin/python \
#     -r <dir>/build-constraints.txt
set -euo pipefail
commit=$(git rev-parse --verify "$1^{commit}")
out=$2
python=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
short=${commit:0:12}
describe=$(git describe --tags --long --match 'v[0-9]*' "$commit")
tag=${describe%-*-g*}
distance=${describe%-g*}
distance=${distance##*-}
base=${tag#v}
[[ $base =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "tag $tag is not vX.Y.Z" >&2; exit 1; }
if [ "$distance" = 0 ]; then
  version=$base
else
  IFS=. read -r major minor patch <<<"$base"
  version="$major.$minor.$((patch + 1)).dev$distance+$(git rev-parse --short "$commit")"
fi
mkdir -p "$out"
out=$(cd "$out" && pwd)
src="$out/src-$short"
rm -rf "$src"
mkdir -p "$src"
git archive "$commit" pyproject.toml README.md LICENSE src | tar -x -C "$src"
(cd "$src" && UV_DYNAMIC_VERSIONING_BYPASS=$version "$python" -I -c '
import sys
import hatchling.build
print(hatchling.build.build_wheel(sys.argv[1]))
' "$out") >/dev/null
rm -rf "$src"
wheel="$out/metabrowser-$version-py3-none-any.whl"
[ -f "$wheel" ] || { echo "no wheel for $version in $out" >&2; exit 1; }
echo "$commit $version"
echo "$wheel"
