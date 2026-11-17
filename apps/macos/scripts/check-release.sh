#!/usr/bin/env bash
# Checks a draft or published app release as a downloader gets it, and says which
# provenance it verified. Run it from a checkout of the release's commit, whose icons
# scripts/check-dmg.sh compares the image's with.
#
#   TAG=macos-v0.1.0 BUILT=local scripts/check-release.sh  # make check-release TAG=... BUILT=...
#   TAG=macos-v0.1.0 BUILT=local LAUNCH=1 scripts/check-release.sh
#
# In order, stopping at the first failure:
#   1. reads the release with gh: the tag's own release, a draft or published;
#   2. downloads its assets (release_assets in common.sh) into a scratch folder;
#   3. checks each against its .sha256 file with `shasum -a 256 -c`, and against the
#      SHA-256 digest GitHub gives for it;
#   4. checks the build provenance BUILT names: with BUILT=ci, the release workflow's
#      attestation for the tag, which `gh attestation verify` must accept; with
#      BUILT=local, none. BUILT is an input, never inferred, so a CI build that lost its
#      attestation cannot pass as a local one;
#   5. once published, checks that the release is immutable, its release attestation
#      (`gh release verify`, `gh release verify-asset`), and that it is not the
#      repository's Latest release;
#   6. quarantines the image if it is not (scripts/quarantine.swift), saying that this
#      simulates a browser download, since gh does not quarantine;
#   7. runs NOTARIZE=1 scripts/check-dmg.sh on it, with EXPECTED_TEAM_ID when set;
#   8. with LAUNCH=1, at the Mac and never in CI, launches the downloaded app
#      translocated, relaunches it, and moves it (scripts/launch-release.sh).
#
# It needs a gh signed in to github.com that can read the repository's draft releases.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=common.sh
source scripts/common.sh
# shellcheck source=check-release-lib.sh
source scripts/check-release-lib.sh

tag="${TAG:-}"
built="${BUILT:-}"
[[ -n "$tag" ]] || die "TAG is required: TAG=macos-vMAJOR.MINOR.PATCH"
[[ "$built" == local || "$built" == ci ]] || die "BUILT must be local or ci, which says who built the release; it is never inferred"
release_version="$(version_of_tag "$tag")"
variant_settings release
[[ "$release_version" == "$version" ]] ||
  die "$tag is version $release_version, and this checkout's VERSION is $version; check out the release's commit"
command -v gh >/dev/null || die "gh is missing; it reads and downloads the release"
command -v jq >/dev/null || die "jq is missing; macOS includes it from macOS 15"

work="$(scratch_dir metabrowser-check-release)"
trap 'rm -rf "$work"' EXIT
assets="$(release_assets "$version" "$arch_label")"
image="$(head -n 1 <<<"$assets")"
sums="$(sed -n 2p <<<"$assets")"

# 1. The release.
json="$(gh release view "$tag" --repo "$release_repository" --json tagName,isDraft,isImmutable,assets)" ||
  die "could not read the release $tag"
facts="$(release_facts "$tag" <<<"$json")"
draft="$(sed -n 's/^draft=//p' <<<"$facts")"
immutable="$(sed -n 's/^immutable=//p' <<<"$facts")"
echo "Release $tag: $([[ "$draft" == true ]] && echo draft || echo published), $([[ "$immutable" == true ]] && echo immutable || echo "not immutable")"

# 2. The assets, and nothing else expected of it.
mkdir -p "$work/download"
while IFS= read -r asset; do
  [[ $'\n'"$facts" == *$'\n'"digest $asset="* ]] || die "$tag has no asset $asset"
  gh release download "$tag" --repo "$release_repository" --pattern "$asset" --dir "$work/download" ||
    die "could not download $asset"
done <<<"$assets"
echo "Downloaded $(tr '\n' ' ' <<<"$assets")"

# 3. The checksum and GitHub's digest.
problems="$(asset_problems "$work/download/$image" "$work/download/$sums" "$(sed -n "s/^digest $image=//p" <<<"$facts")")"
[[ -z "$problems" ]] || die "$image:"$'\n'"$problems"
echo "checksum: $image matches $sums and GitHub's digest, sha256:$(cut -d' ' -f1 "$work/download/$sums")"

# 4 and 5. Provenance.
build_provenance="$(check_build_provenance "$built" "$tag" "$work/download/$image")"
echo "$build_provenance"
release_provenance="$(check_publication "$tag" "$draft" "$immutable" "$work/download/$image" "$work/download/$sums")"
echo "$release_provenance"

# 6. Quarantine, as a browser download has.
swiftc -O scripts/quarantine.swift -o "$work/quarantine" 2>"$work/swiftc.log" ||
  die "could not build scripts/quarantine.swift, which needs Xcode: $(cat "$work/swiftc.log")"
case "$("$work/quarantine" "$work/download/$image")" in
  already) quarantine="the download was quarantined already" ;;
  simulated) quarantine="simulated: gh does not quarantine, so the image was quarantined as a browser download is" ;;
  *) die "could not quarantine $image" ;;
esac
echo "quarantine: $quarantine"

# 7. The image, as a downloader meets it.
NOTARIZE=1 scripts/check-dmg.sh "$work/download/$image"

echo
echo "Checked $tag (BUILT=$built), as downloaded:"
echo "  checksum and digest: sha256:$(cut -d' ' -f1 "$work/download/$sums")"
echo "  $build_provenance"
echo "  $release_provenance"
echo "  quarantine: $quarantine"
echo "  check-dmg.sh with NOTARIZE=1: passed"

# 8. The launch.
if [[ "${LAUNCH:-0}" == 1 ]]; then
  scripts/launch-release.sh "$work/download/$image"
fi
