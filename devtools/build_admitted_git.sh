#!/usr/bin/env bash
# Build one admitted Git release from checksum-verified kernel.org source.
#
#   devtools/build_admitted_git.sh VERSION PREFIX
#
# Production refuses repository acquisition below the Git security floor in
# tests/fixtures/repository-cache/git-version-gates.json, and the CI runner's
# distribution Git reports a version below it. The CI admitted-git job builds the
# releases pinned here, so acquisition and the no-lazy-fetch acceptance tests run on
# a Git that production admits. SUPPLY-CHAIN-SECURITY.md ("Admitted Git in CI")
# records the review; devtools/check_supply_chain.py keeps its table, these pins,
# and the job's matrix in agreement.
#
# Only a pinned release builds. The archive is fetched over HTTPS only and checked
# against its pinned SHA-256 before it is unpacked. This compiles third-party source:
# it is written for the CI runner (GNU coreutils, apt build dependencies), not for a
# developer machine.
set -euo pipefail

version="${1:?usage: build_admitted_git.sh VERSION PREFIX}"
prefix="${2:?usage: build_admitted_git.sh VERSION PREFIX}"

# SHA-256 of git-VERSION.tar.xz, from kernel.org's sha256sums.asc.
case "$version" in
  2.43.7) sha256=657e2374455d9e62f6cdb3e7c55d867b6db5404d744e97e112cc5b0db687a19f ;;
  2.50.1) sha256=7e3e6c36decbd8f1eedd14d42db6674be03671c2204864befa2a41756c5c8fc4 ;;
  *)
    echo "build_admitted_git.sh: no pinned SHA-256 for Git ${version}" >&2
    exit 2
    ;;
esac

tarball="git-${version}.tar.xz"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --retry 3 --retry-delay 5 \
  --output "${work}/${tarball}" \
  "https://mirrors.edge.kernel.org/pub/software/scm/git/${tarball}"
echo "${sha256}  ${work}/${tarball}" | sha256sum --check --strict -

tar -xJf "${work}/${tarball}" -C "$work"

# The core commands and the HTTP(S) remote helper, which the stalled-promisor tests
# reach. No Tcl/Tk tools, translations, Perl or Python commands, DAV push, or
# OpenSSL (curl brings its own TLS).
if ! make -C "${work}/git-${version}" -j"$(nproc)" prefix="$prefix" \
  NO_TCLTK=1 NO_GETTEXT=1 NO_PERL=1 NO_PYTHON=1 NO_EXPAT=1 NO_OPENSSL=1 \
  all install >"${work}/build.log" 2>&1; then
  tail -n 60 "${work}/build.log" >&2
  exit 1
fi

"${prefix}/bin/git" --version
