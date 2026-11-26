#!/usr/bin/env bash
# Checks a draft or published app release as a downloader gets it, and says which
# provenance it verified. Run it from a checkout of the release's commit, whose icons
# scripts/check-dmg.sh compares the image's with.
#
#   TAG=macos-v0.1.0 BUILT=local EXPECTED_TEAM_ID=TEAMID scripts/check-release.sh
#   TAG=macos-v0.1.0 BUILT=local EXPECTED_TEAM_ID=TEAMID LAUNCH=1 scripts/check-release.sh
#   make check-release TAG=... BUILT=... EXPECTED_TEAM_ID=... [LAUNCH=1]
#
# EXPECTED_TEAM_ID, the publisher's Team ID, is required: for a local build there is no
# attestation, so the Developer ID team is what ties the image to the owner. In order,
# stopping at the first failure:
#   1. reads the release with gh, a draft or published, and the commit its tag points at;
#   2. requires exactly the assets named by release_assets and downloads them;
#   3. checks the image against its checksum file and both files against the SHA-256
#      digests GitHub gives for them;
#   4. checks the build provenance BUILT names: with BUILT=ci, the release workflow's
#      attestation for the tag, which `gh attestation verify` must accept; with
#      BUILT=local, none. BUILT is an input, never inferred, so a CI build that lost its
#      attestation cannot pass as a local one;
#   5. for a draft, that the repository's immutable releases are on; once published, that
#      the release is immutable, its release attestation (`gh release verify`,
#      `gh release verify-asset`), and that it is not the repository's Latest release;
#   6. quarantines the image if it is not (scripts/quarantine.swift), which simulates a
#      browser download, since gh does not quarantine. Only the launch check depends on
#      it: none of check-dmg.sh's tools judges a file differently for its quarantine, and
#      Gatekeeper's check of a browser download is the owner's, O8;
#   7. runs NOTARIZE=1 scripts/check-dmg.sh on it, with EXPECTED_TEAM_ID, and requires
#      the app to be the release variant, the tag's version, and built from the tag's
#      commit (EXPECTED_VERSION, EXPECTED_COMMIT), with the slices the image's name says
#      (EXPECTED_ARCHES, from ARCHES as the release was built with);
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
team="${EXPECTED_TEAM_ID:-}"
[[ -n "$tag" ]] || die "TAG is required: TAG=macos-vMAJOR.MINOR.PATCH"
[[ "$built" == local || "$built" == ci ]] || die "BUILT must be local or ci, which says who built the release; it is never inferred"
[[ "$team" =~ ^[A-Z0-9]{10}$ ]] ||
  die "EXPECTED_TEAM_ID must be the publisher's 10-character Team ID, which ties the image to the owner; it is '${team}'"
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

# 1. The release, and its tag's commit.
json="$(gh release view "$tag" --repo "$release_repository" --json tagName,isDraft,isImmutable,assets)" ||
  die "could not read the release $tag"
facts="$(release_facts "$tag" "$image" "$sums" <<<"$json")"
draft="$(sed -n 's/^draft=//p' <<<"$facts")"
immutable="$(sed -n 's/^immutable=//p' <<<"$facts")"
commit="$(tag_commit "$tag")"
echo "Release $tag: $([[ "$draft" == true ]] && echo draft || echo published), $([[ "$immutable" == true ]] && echo immutable || echo "not immutable"), at $commit"

# 2. The assets.
mkdir -p "$work/download"
while IFS= read -r asset; do
  gh release download "$tag" --repo "$release_repository" --pattern "$asset" --dir "$work/download" ||
    die "could not download $asset"
done <<<"$assets"
echo "Downloaded $(tr '\n' ' ' <<<"$assets")"

# 3. The checksum and GitHub's digests.
problems="$(github_digest_problem "$work/download/$sums" "$(sed -n "s/^digest $sums=//p" <<<"$facts")")"
[[ -z "$problems" ]] || die "$sums:"$'\n'"$problems"
problems="$(asset_problems "$work/download/$image" "$work/download/$sums" "$(sed -n "s/^digest $image=//p" <<<"$facts")")"
[[ -z "$problems" ]] || die "$image:"$'\n'"$problems"
echo "checksum: $image matches $sums and GitHub's digests verify both downloads; image sha256:$(cut -d' ' -f1 "$work/download/$sums")"

# 4 and 5. Provenance.
build_provenance="$(check_build_provenance "$built" "$tag" "$work/download/$image")"
echo "$build_provenance"
release_provenance="$(check_publication "$tag" "$draft" "$immutable" "$work/download/$image" "$work/download/$sums")"
echo "$release_provenance"

# 6. Quarantine, for the launch check.
swiftc -O scripts/quarantine.swift -o "$work/quarantine" 2>"$work/swiftc.log" ||
  die "could not build scripts/quarantine.swift, which needs Xcode: $(cat "$work/swiftc.log")"
case "$("$work/quarantine" "$work/download/$image")" in
  already) quarantine="the download was quarantined already" ;;
  simulated) quarantine="simulated, for the launch check: gh does not quarantine, so the image was quarantined as a browser download is" ;;
  *) die "could not quarantine $image" ;;
esac
echo "quarantine: $quarantine"

# 7. The image, as a downloader meets it, and the app in it, as the tag names it.
NOTARIZE=1 EXPECTED_TEAM_ID="$team" EXPECTED_VERSION="$version" EXPECTED_COMMIT="$commit" EXPECTED_ARCHES="$arches" \
  scripts/check-dmg.sh "$work/download/$image"

echo
echo "Checked $tag (BUILT=$built), as downloaded:"
echo "  checksum and digest: sha256:$(cut -d' ' -f1 "$work/download/$sums")"
echo "  $build_provenance"
echo "  $release_provenance"
echo "  check-dmg.sh with NOTARIZE=1: passed, team $team, the release variant $version from $commit, slices '$arches'"
echo "  quarantine: $quarantine; Gatekeeper's check of a browser download is O8's"

# 8. The launch.
if [[ "${LAUNCH:-0}" == 1 ]]; then
  scripts/launch-release.sh "$work/download/$image"
fi
