#!/bin/bash
# A stand-in for a large repository: COMMITS commits and REFS refs, a few thousand
# tracked files, and IGNORED_DIRS x IGNORED_PER_DIR empty gitignored files under
# node_modules, about 303,000 entries in all with the defaults.
#
#   explorations/tree-summary-storm/make-corpus.sh DEST
set -euo pipefail
DEST=${1:?destination}
COMMITS=${COMMITS:-10000}
REFS=${REFS:-2500}
TRACKED_DIRS=${TRACKED_DIRS:-64}
TRACKED_PER_DIR=${TRACKED_PER_DIR:-50}
IGNORED_DIRS=${IGNORED_DIRS:-3000}
IGNORED_PER_DIR=${IGNORED_PER_DIR:-100}

if [ -e "$DEST" ]; then
  echo "$DEST exists; give a new directory" >&2
  exit 1
fi
mkdir -p "$DEST"
cd "$DEST"
git init -q -b main .
git config user.email storm@example.invalid
git config user.name storm
printf 'node_modules/\n' > .gitignore

# Tracked files.
for d in $(seq 1 "$TRACKED_DIRS"); do
  mkdir -p "src/pkg$d"
  for f in $(seq 1 "$TRACKED_PER_DIR"); do
    printf 'module %s %s\n' "$d" "$f" > "src/pkg$d/file$f.py"
  done
done
git add -A
git commit -q -m "initial"

# COMMITS more commits through fast-import: each touches one tracked file.
{
  for i in $(seq 1 "$COMMITS"); do
    d=$(( (i % TRACKED_DIRS) + 1 ))
    f=$(( (i % TRACKED_PER_DIR) + 1 ))
    body="change $i"
    printf 'commit refs/heads/main\n'
    printf 'committer storm <storm@example.invalid> %d +0000\n' $(( 1600000000 + i * 60 ))
    printf 'data %d\n%s\n' ${#body} "$body"
    if [ "$i" -eq 1 ]; then printf 'from refs/heads/main^0\n'; fi
    printf 'M 100644 inline src/pkg%d/file%d.py\n' "$d" "$f"
    content="module $d $f revision $i"
    printf 'data %d\n%s\n' ${#content} "$content"
    printf '\n'
  done
} | git fast-import --quiet
git reset -q --hard main

# REFS refs: tags and branches spread over history.
git rev-list main > .git/storm-revs
total=$(wc -l < .git/storm-revs)
i=0
{
  while read -r rev; do
    i=$(( i + 1 ))
    if [ $(( i % (total / REFS + 1) )) -eq 0 ]; then
      if [ $(( i % 2 )) -eq 0 ]; then
        printf 'create refs/tags/release-%06d-with-a-longer-tag-name %s\n' "$i" "$rev"
      else
        printf 'create refs/heads/feature/branch-%06d-with-a-longer-name %s\n' "$i" "$rev"
      fi
    fi
  done < .git/storm-revs
} | git update-ref --stdin
rm -f .git/storm-revs
git pack-refs --all

# Ignored files: IGNORED_DIRS directories of IGNORED_PER_DIR empty files.
mkdir -p node_modules
for d in $(seq 1 "$IGNORED_DIRS"); do
  dir="node_modules/pkg-$(( d / 100 ))/dep-$d/lib"
  mkdir -p "$dir"
  (cd "$dir" && seq -f 'f%g.js' 1 "$IGNORED_PER_DIR" | xargs touch)
done
echo "commits: $(git rev-list --count main)"
echo "refs: $(git for-each-ref | wc -l)"
echo "tracked: $(git ls-files | wc -l)"
echo "ignored: $(find node_modules -type f | wc -l)"
