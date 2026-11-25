#!/usr/bin/env bash
# Put the pinned Node in a CI runner's tool cache, where actions/setup-node looks first.
#
#   devtools/install_node.sh VERSION
#
# setup-node v6.4.0 (48b55a0) gets a Node the runner image lacks by downloading it from
# actions/node-versions, with no limit on a slow transfer, unpacking it in a temporary
# folder, and copying that into the tool cache one file at a time (cacheDir in
# @actions/tool-cache). Over the 1500 ci.yml runs 43910077901 to 45542298244 (2026-11-16
# to 2026-11-25) its Set up Node step took 6 s at the median and 9 s at the 99th
# percentile of 31178, and over a minute six times: the copy took 69 to 94 s four times,
# the download 81 s once, at 0.7 MB/s, and 62 s once, when two lookups of github.com
# failed and setup-node's third attempt succeeded. In 20 of those jobs drawn at random
# the copy took 0.9 to 2.4 s and the download 0.3 to 0.7 s. The copy of 94 s ran a
# Chrome part past its limit (run 45537641286, mb-z4i7). In each of the 82 of those jobs
# whose log was read, tar unpacked the same archive in 0.6 to 1.2 s, in the nine whose
# copy then took over 20 s as well.
#
# Before it fetches anything, setup-node looks for the exact version in the runner's tool
# cache (setupNodeJs in src/distributions/official_builds/official_builds.ts), and when it
# is there it neither fetches its manifest nor downloads nor copies. This script puts it
# there: the archive setup-node downloads, fetched over HTTPS with retries that end a
# stalled transfer, checked against its pinned SHA-256, and unpacked where
# @actions/tool-cache's find() looks ($RUNNER_TOOL_CACHE/node/VERSION/ARCH, with
# ARCH.complete beside it). The setup-node step after it does the rest as before: PATH and
# the npm cache.
#
# devtools/check_ci.py holds every setup-node step to a step that runs this script just
# before it, with the same version.
set -euo pipefail

version="${1:?usage: install_node.sh VERSION}"

# setup-node's name for the runner's architecture (os.arch()) and Node's for the platform.
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) arch=x64 platform=linux-x64 ;;
  Darwin-arm64) arch=arm64 platform=darwin-arm64 ;;
  *)
    echo "install_node.sh: no Node archive for $(uname -s) $(uname -m)" >&2
    exit 2
    ;;
esac

# The actions/node-versions release that names each pinned Node's archives in
# versions-manifest.json on that repository's main branch, which setup-node reads at run
# time to find its download, and the SHA-256 GitHub records for each archive: the
# asset's digest in `gh api repos/actions/node-versions/releases/tags/RELEASE`.
# SUPPLY-CHAIN-SECURITY.md has the review. A new Node release needs a row here before its
# version can be pinned.
case "${version}-${platform}" in
  24.18.0-linux-x64)
    release=24.18.0-28070977815
    sha256=efced36c041a7a43e8b4a4b35cb929bef7747c1c7442e693901a0b4f06467e1d
    ;;
  24.18.0-darwin-arm64)
    release=24.18.0-28070977815
    sha256=ac6d3fff9356f40c7a1c06be28cad6d6468b0ae194b8937629ce9f97030782be
    ;;
  *)
    echo "install_node.sh: no pinned archive for Node ${version} on ${platform}" >&2
    exit 2
    ;;
esac

cache="${RUNNER_TOOL_CACHE:?install_node.sh runs on a GitHub Actions runner}"
archive="node-${version}-${platform}.tar.gz"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# An attempt slower than 1 MB/s for 10 s is ended and begun again. In the logs above the
# Linux archive (58 MB) took 9.2 s in the slowest download that did not stall (6.3 MB/s,
# job 138145804769), and the three slow ones averaged 0.7, 1.3, and 1.8 MB/s (81, 44,
# and 32 s); the macOS one (52 MB) arrived at 65 to 75 MB/s in four macos-app.yml runs.
# The floor is six times under the slowest healthy download, so a slow link still
# finishes, and at the floor the archive takes 58 s, which --max-time allows.
#
# Every failure, a refused connection, a failed lookup, or an error status, is tried
# again 10 s later until 90 s have passed: the budget is that time, not a count of
# attempts. When two lookups of github.com failed (EAI_AGAIN, 20 and 46 s into job
# 137994988638's download), setup-node's third attempt finished 62 s after its first began.
# A download that keeps failing fails this step, by name, within about 160 s, since the
# last attempt can begin just before 90 s and run 70.
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --connect-timeout 10 --max-time 70 --speed-limit 1000000 --speed-time 10 \
  --retry 20 --retry-delay 10 --retry-max-time 90 --retry-all-errors \
  --output "${work}/${archive}" \
  "https://github.com/actions/node-versions/releases/download/${release}/${archive}"
# sha256sum on Linux, shasum on macOS: both print the digest first.
actual="$({ sha256sum "${work}/${archive}" 2>/dev/null || shasum -a 256 "${work}/${archive}"; } | cut -d ' ' -f 1)"
if [ "$actual" != "$sha256" ]; then
  echo "install_node.sh: ${archive} has SHA-256 ${actual}, not the pinned ${sha256}" >&2
  exit 1
fi

# Straight into place, with no copy after it, dropping the first part of each path as
# setup-node does (tar --strip 1 in extractArchive). Whatever the image had there is
# replaced, so the tool cache holds exactly the pinned archive, and it is marked complete
# only once its node answers with the pinned version.
installed="${cache}/node/${version}/${arch}"
rm -rf "$installed" "${installed}.complete"
mkdir -p "$installed"
tar -xzf "${work}/${archive}" -C "$installed" --strip-components=1
reported="$("${installed}/bin/node" --version)"
if [ "$reported" != "v${version}" ]; then
  echo "install_node.sh: ${installed}/bin/node reports ${reported}, not v${version}" >&2
  exit 1
fi
touch "${installed}.complete"
echo "Node ${reported} in ${installed}"
