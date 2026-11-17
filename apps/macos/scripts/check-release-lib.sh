# What scripts/check-release.sh and scripts/launch-release.sh decide, sourced by them and
# by scripts/test-release-logic.sh, which runs these on stand-ins for gh and defaults:
# the tag, the release's assets and digests, the checksum, the provenance a release must
# carry, and the launch check's backup of the release identity's state.
# shellcheck shell=bash

# The repository whose releases these check, and the workflow whose build provenance
# attestation a CI-built release must carry (the publishing plan's release workflow).
release_repository=jlevy/metabrowser
release_workflow=.github/workflows/macos-release.yml

# The version a release tag names: macos-vMAJOR.MINOR.PATCH, as common.sh's read_version
# requires of the VERSION file. Stops for any other tag.
version_of_tag() {
  local pattern='^macos-v([0-9]+\.[0-9]+\.[0-9]+)$'
  [[ "$1" =~ $pattern ]] || die "TAG must be macos-vMAJOR.MINOR.PATCH, not '$1'"
  echo "${BASH_REMATCH[1]}"
}

# Reads `gh release view TAG --json tagName,isDraft,isImmutable,assets` on stdin and
# prints "draft=true|false", "immutable=true|false", and one "digest NAME=VALUE" line
# for each asset. Stops when it is not that tag's release.
release_facts() {
  local tag="$1" json
  json="$(cat)"
  jq -e --arg tag "$tag" '.tagName == $tag' <<<"$json" >/dev/null 2>&1 ||
    die "the release read is not $tag's: $(head -c 200 <<<"$json")"
  jq -r '"draft=\(.isDraft)", "immutable=\(.isImmutable)", (.assets[] | "digest \(.name)=\(.digest // "")")' <<<"$json"
}

# Prints, one per line, what is wrong with a downloaded asset "$1" and its checksum file
# "$2", given GitHub's digest of the asset "$3": the checksum file must be one
# `shasum -a 256` line naming the asset, `shasum -a 256 -c` must pass, and the digest must
# be the same SHA-256. Prints nothing when all three agree.
asset_problems() {
  local file="$1" sums="$2" digest="$3" name lines line actual
  local pattern='^[0-9a-f]{64}  (.+)$'
  name="$(basename "$file")"
  lines="$(wc -l <"$sums" | tr -d ' ')"
  line="$(head -n 1 "$sums")"
  if [[ "$lines" != 1 || ! "$line" =~ $pattern || "${BASH_REMATCH[1]}" != "$name" ]]; then
    echo "$(basename "$sums") is not one shasum -a 256 line for $name: $line"
  elif ! (cd "$(dirname "$file")" && shasum -a 256 -c "$(basename "$sums")" >/dev/null 2>&1); then
    echo "$name does not match $(basename "$sums")"
  fi
  actual="$(shasum -a 256 "$file" | cut -d' ' -f1)"
  if [[ -z "$digest" ]]; then
    echo "GitHub gives no digest for $name"
  elif [[ "$digest" != "sha256:$actual" ]]; then
    echo "GitHub's digest for $name is $digest, and the download's SHA-256 is $actual"
  fi
  return 0
}

# The arguments of the `gh attestation verify` that a CI-built image "$2" from tag "$1"
# must pass: an attestation made by the release workflow, for that tag.
attestation_args() {
  printf '%s\n' attestation verify "$2" --repo "$release_repository" \
    --signer-workflow "$release_repository/$release_workflow" --source-ref "refs/tags/$1"
}

# Checks the build provenance the input BUILT ("$1": local or ci) says the image "$3"
# from tag "$2" carries, and prints what it verified. A CI build must carry the
# attestation; a local build cannot, since only a workflow can make one. The input is not
# inferred, so a CI build that lost its attestation cannot pass as a local one.
check_build_provenance() {
  local built="$1" tag="$2" file="$3" output line
  local -a args=()
  case "$built" in
    ci)
      while IFS= read -r line; do args+=("$line"); done <<<"$(attestation_args "$tag" "$file")"
      output="$(gh "${args[@]}" 2>&1)" ||
        die "BUILT=ci, and $(basename "$file") has no build provenance attestation from $release_workflow for $tag: $output"
      echo "build provenance: attested by $release_workflow for refs/tags/$tag"
      ;;
    local)
      echo "build provenance: none, as BUILT=local says: only a workflow can attest a build"
      ;;
    *) die "BUILT must be local or ci, not '$built'" ;;
  esac
}

# Checks what only a published release has: that it is immutable, its release
# attestation and each asset's ("$4" onward), and that it is not the repository's Latest
# release, which stays the Python package's. A draft has none of these yet; for one, it
# checks that the repository's immutable releases are on, so that publishing it makes it
# immutable (O5), and says the rest waits for publication.
check_publication() {
  local tag="$1" draft="$2" immutable="$3" output latest file
  shift 3
  if [[ "$draft" == true ]]; then
    output="$(gh api "repos/$release_repository/immutable-releases" --jq .enabled 2>&1)" ||
      die "could not read whether immutable releases are on: $output"
    [[ "$output" == true ]] ||
      die "immutable releases are off for $release_repository, so publishing $tag would leave it mutable; turn them on first (O5)"
    echo "release attestation: not yet, since $tag is a draft; immutable releases are on, so publishing makes it immutable; run this again once it is published"
    return 0
  fi
  [[ "$immutable" == true ]] || die "$tag is published but not immutable; turn on immutable releases (O5) before publishing"
  output="$(gh release verify "$tag" --repo "$release_repository" 2>&1)" ||
    die "gh release verify $tag failed: $output"
  for file in "$@"; do
    output="$(gh release verify-asset "$tag" "$file" --repo "$release_repository" 2>&1)" ||
      die "gh release verify-asset $tag $(basename "$file") failed: $output"
  done
  latest="$(gh api "repos/$release_repository/releases/latest" --jq .tag_name 2>&1)" ||
    die "could not read the Latest release: $latest"
  [[ "$latest" != "$tag" ]] ||
    die "$tag is the repository's Latest release; publish it with --latest=false (gh release edit $tag --latest=false sets another)"
  echo "release attestation: verified for $tag and each asset; the Latest release is $latest"
}

# The commit a release tag points at, as GitHub has it: the agent creates app tags with
# `gh api .../git/refs`, which makes a lightweight tag, and an annotated one is followed
# to its commit.
tag_commit() {
  local tag="$1" object
  object="$(gh api "repos/$release_repository/git/ref/tags/$tag" --jq '.object.type + " " + .object.sha' 2>&1)" ||
    die "could not read the tag $tag: $object"
  if [[ "$object" == "tag "* ]]; then
    object="$(gh api "repos/$release_repository/git/tags/${object#tag }" --jq '.object.type + " " + .object.sha' 2>&1)" ||
      die "could not read the annotated tag $tag: $object"
  fi
  [[ "$object" =~ ^commit\ [0-9a-f]{40}$ ]] || die "$tag does not point at a commit: $object"
  echo "${object#commit }"
}

# ── The launch check ─────────────────────────────────────────

# Whether a running copy's path is a translocated one: the rule LaunchLocation in
# ShellCore applies, since macOS offers no API to detect it.
is_translocated_path() {
  [[ "$1" == */AppTranslocation/* ]]
}

# Whether a copy that ran from "$1" ran where this launch must: "$2" is translocated, for
# a first launch from Downloads, or installed, after a move in Finder.
ran_as_expected() {
  if is_translocated_path "$1"; then
    [[ "$2" == translocated ]]
  else
    [[ "$2" == installed ]]
  fi
}

# The launch checks whose backups are still in the folder "$1" (apps/macos/build), one
# per line: each ended before it restored the release identity's state, which is still
# cleared, so the backup is the only copy of it.
leftover_launch_checks() {
  local marker
  for marker in "$1"/launch-check-*/backup/complete; do
    [[ -e "$marker" ]] && echo "${marker%/backup/complete}"
  done
  return 0
}

# What a launch of the release identity "$2" reads and changes: its user defaults, the
# saved session both variants share, and the recent documents macOS keeps for it.
release_session_file() {
  echo "$HOME/Library/Application Support/Metabrowser/session.json"
}
release_recents_dir() {
  echo "$HOME/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments"
}

# Copies that state into the folder "$1", noting what was absent, then clears it, so
# that the launch meets the identity as a first launch does. Stops before clearing
# anything if the copy fails.
backup_release_state() {
  local backup="$1" id="$2" session recents file
  session="$(release_session_file)"
  recents="$(release_recents_dir)"
  mkdir -p "$backup/recents"
  if defaults read "$id" >/dev/null 2>&1; then
    defaults export "$id" "$backup/defaults.plist" || die "could not back up the defaults of $id"
  fi
  if [[ -f "$session" ]]; then
    cp -p "$session" "$backup/session.json" || die "could not back up $session"
  fi
  for file in "$recents/$id".sfl*; do
    [[ -e "$file" ]] || continue
    cp -p "$file" "$backup/recents/" || die "could not back up $file"
  done
  : >"$backup/complete"
  defaults delete "$id" >/dev/null 2>&1 || true
  rm -f "$session" "$recents/$id".sfl*
}

# Puts back what backup_release_state saved in "$1", and removes what the launch made
# where there was nothing. Returns 1, keeping the backup, when it cannot.
restore_release_state() {
  local backup="$1" id="$2" session recents file
  [[ -f "$backup/complete" ]] || return 1
  session="$(release_session_file)"
  recents="$(release_recents_dir)"
  defaults delete "$id" >/dev/null 2>&1 || true
  if [[ -f "$backup/defaults.plist" ]]; then
    defaults import "$id" "$backup/defaults.plist" || return 1
  fi
  rm -f "$session"
  if [[ -f "$backup/session.json" ]]; then
    mkdir -p "$(dirname "$session")"
    cp -p "$backup/session.json" "$session" || return 1
  fi
  rm -f "$recents/$id".sfl*
  for file in "$backup/recents"/*; do
    [[ -e "$file" ]] || continue
    mkdir -p "$recents"
    cp -p "$file" "$recents/" || return 1
  done
  return 0
}
