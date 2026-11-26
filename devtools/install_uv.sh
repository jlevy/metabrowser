#!/usr/bin/env bash
# Put the pinned uv in a CI runner's tool cache, where astral-sh/setup-uv looks first.
#
#   devtools/install_uv.sh VERSION SHA256
#
# setup-uv v8.2.0 (fac544c) resolves even a pinned version's download URL from a
# manifest it fetches from raw.githubusercontent.com, and src/utils/fetch.ts aborts that
# fetch after a fixed 5 s with no retry. One slow answer failed a job at its "Install uv"
# step (run 45299956083, job 138130034436, 2026-11-24); the fetch usually takes about
# 0.13 s. Before it fetches anything, setup-uv looks for an exact version in the runner's
# tool cache (setupUv in src/setup-uv.ts), and when uv is there it neither fetches the
# manifest nor downloads. This script puts it there: the release archive, fetched over
# HTTPS with retries and checked against its pinned SHA-256, unpacked where
# @actions/tool-cache's find() looks ($RUNNER_TOOL_CACHE/uv/VERSION/ARCH, with
# ARCH.complete beside it). The setup-uv step after it does the rest as before: PATH,
# UV_PYTHON, and the uv cache. Should a later setup-uv look elsewhere, it downloads uv
# as it did before, and checks the same SHA-256.
#
# devtools/check_ci.py holds every setup-uv step to a step that runs this script just
# before it, with the same version and checksum.
set -euo pipefail

version="${1:?usage: install_uv.sh VERSION SHA256}"
sha256="${2:?usage: install_uv.sh VERSION SHA256}"

# setup-uv's names for the runner (src/utils/platforms.ts) and uv's release target.
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) arch=x86_64 target=x86_64-unknown-linux-gnu ;;
  Darwin-arm64) arch=aarch64 target=aarch64-apple-darwin ;;
  *)
    echo "install_uv.sh: no uv target for $(uname -s) $(uname -m)" >&2
    exit 2
    ;;
esac

cache="${RUNNER_TOOL_CACHE:?install_uv.sh runs on a GitHub Actions runner}"
archive="uv-${target}.tar.gz"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# --retry-all-errors retries a slow or refused connection and an error status alike; the
# URL is pinned, so an error that persists fails the step after the last attempt.
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --connect-timeout 10 --max-time 120 --retry 5 --retry-delay 3 --retry-all-errors \
  --output "${work}/${archive}" \
  "https://github.com/astral-sh/uv/releases/download/${version}/${archive}"
# sha256sum on Linux, shasum on macOS: both print the digest first.
actual="$({ sha256sum "${work}/${archive}" 2>/dev/null || shasum -a 256 "${work}/${archive}"; } | cut -d ' ' -f 1)"
if [ "$actual" != "$sha256" ]; then
  echo "install_uv.sh: ${archive} has SHA-256 ${actual}, not the pinned ${sha256}" >&2
  exit 1
fi

tar -xzf "${work}/${archive}" -C "$work"
installed="${cache}/uv/${version}/${arch}"
mkdir -p "$installed"
cp "${work}/uv-${target}/uv" "${work}/uv-${target}/uvx" "$installed/"
touch "${installed}.complete"
"${installed}/uv" --version
