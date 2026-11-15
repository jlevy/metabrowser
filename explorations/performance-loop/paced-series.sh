#!/bin/bash
# paced-series.sh: the performance loop's driver for a judged series of the transition
# scenario. It runs one back-to-back pair of two builds per transitions.mjs invocation,
# paced by load, behind the series lock, and checks every registered input before and
# after each pair, until the round has its target of judged pairs or reaches its cap on
# attempts. It generalizes exp-079's driver (experiments/exp-079-protocol.txt, amendments
# 1 and 2). A round's protocol registers the values its config holds.
#
# Only the coordinator starts a series. Anyone may run --check or --self-test: neither
# takes the series lock or starts a timed run.
#
#   paced-series.sh --config FILE              run the series
#   paced-series.sh --config FILE --check      check every gate once; exit 0 only if all
#                                              pass. Takes no lock and times nothing.
#   paced-series.sh --config FILE --self-test  test the lock's mechanics and the stopping
#                                              count on scratch fixtures under OUT, then run
#                                              --check under command shims and show it left
#                                              the series lock and the series files alone
#
# The coordinator starts a run detached, its output appended to a log in OUT, such as
#   paced-series.sh --config "$CFG" >>"$OUT/$ROUND-paced.log" 2>&1 &
#
# Config contract. FILE is a bash fragment of KEY=value assignments, sourced once after
# every key below is unset, so no value comes from the environment. It holds local paths,
# so it lives in the round's worktree as gitignored attic/expNNN/series.env; start it from
# paced-series.example.env, which explains each key. A config inside a Git work tree must
# be ignored by Git, and OUT must be an ignored directory inside WORKTREE.
# Required:
#   ROUND                 exp-NNN: the harness's --exp, the bench directory, file names
#   WORKTREE, BRANCH      the round's worktree and branch; the lock is read from its
#                         git common dir
#   PROTOCOL              the protocol file, relative to WORKTREE
#   OUT                   the round's output directory: power log, samples, pair logs
#   CONTROL_WT, CONTROL_HEAD, CONTROL_VERSION
#   CANDIDATE_WT, CANDIDATE_HEAD, CANDIDATE_VERSION
#                         each build's checkout, full commit, and `metab --version` line
#   HARNESS_WT, HARNESS_HEAD, SCENARIO_REVISION
#                         the frozen harness checkout, its full commit, and its revision
#   CORPUS, CORPUS_COMMIT, CORPUS_TRUNK, CORPUS_REFS
#                         the corpus and the provenance the first pair must start on
#   TARGET, MAX_ATTEMPTS  judged pairs to stop at, and the cap on attempts
#   MAX_LOAD              the pacing bound: one-minute load under it for QUIET_SECONDS
# Optional, with their defaults:
#   CONTROL_LABEL=control, CANDIDATE_LABEL=candidate
#   CONTROL_METAB=$CONTROL_WT/.venv/bin/metab, CANDIDATE_METAB=$CANDIDATE_WT/.venv/bin/metab
#   HARNESS_ARGS=         more words for `transitions.mjs run`, such as --journeys
#   EXCLUDE_MAX_LOAD=$MAX_LOAD, the load rule's bound, passed to the load filter
#   LOAD_FILTER=$WORKTREE/explorations/performance-loop/experiments/exp-060-062-load-filter.mjs
#   COUNT=paced-series-count.mjs beside this file; another count takes the same arguments
#   LOCK_WAIT_HOURS=12, QUIET_WAIT_MINUTES=60, QUIET_SECONDS=60 (a multiple of 10)
#   CAFFEINATE=1          hold `caffeinate -i` for the driver's life (exp-079 amendment 2)
#   OWNER_NOTE=           words added to the lock's owner line
#
# Exit status: 0 done, or every gate passed; 1 a --check or --self-test failure; 3 the lock
# was not taken in LOCK_WAIT_HOURS; 4 a registered input does not hold at the start; 6 the
# corpus moved; 8 a build or the harness moved, or rows record another scenario revision;
# 9 no quiet window in QUIET_WAIT_MINUTES; 10 the stopping count failed; 64 usage; 78 an
# unreadable or incomplete config; 129, 130 or 143 a signal. However a run ends, its exit
# trap stops the running pair and releases the lock it holds.
#
# Bash 3.2 (macOS /bin/bash). macOS only: pmset, sysctl vm.loadavg, caffeinate, stat -f.
set -u

SELF_DIR=$(cd "$(dirname "$0")" && pwd -P)
SELF=$SELF_DIR/$(basename "$0")

usage() {
  echo "usage: $0 --config FILE [--check | --self-test]" >&2
  exit 64
}

ACTION=run
CONFIG=""
while [ $# -gt 0 ]; do
  case $1 in
    --config)
      [ $# -ge 2 ] || usage
      CONFIG=$2
      shift 2
      ;;
    --check | --self-test)
      [ "$ACTION" = run ] || usage
      ACTION=${1#--}
      shift
      ;;
    -h | --help)
      awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$SELF"
      exit 0
      ;;
    *) usage ;;
  esac
done
[ -n "$CONFIG" ] || usage
if [ ! -f "$CONFIG" ] || [ ! -r "$CONFIG" ]; then
  echo "no readable config at $CONFIG" >&2
  exit 78
fi
CONFIG=$(cd "$(dirname "$CONFIG")" && pwd -P)/$(basename "$CONFIG")

# ------------------------------------------------------------------ the config
REQUIRED_KEYS="ROUND WORKTREE BRANCH PROTOCOL OUT
  CONTROL_WT CONTROL_HEAD CONTROL_VERSION CANDIDATE_WT CANDIDATE_HEAD CANDIDATE_VERSION
  HARNESS_WT HARNESS_HEAD SCENARIO_REVISION CORPUS CORPUS_COMMIT CORPUS_TRUNK CORPUS_REFS
  TARGET MAX_ATTEMPTS MAX_LOAD"
OPTIONAL_KEYS="CONTROL_LABEL CANDIDATE_LABEL CONTROL_METAB CANDIDATE_METAB HARNESS_ARGS
  EXCLUDE_MAX_LOAD LOAD_FILTER COUNT LOCK_WAIT_HOURS QUIET_WAIT_MINUTES QUIET_SECONDS
  CAFFEINATE OWNER_NOTE"
for k in $REQUIRED_KEYS $OPTIONAL_KEYS; do unset "$k"; done
# shellcheck source=/dev/null
. "$CONFIG" || {
  echo "sourcing $CONFIG failed" >&2
  exit 78
}
missing=""
for k in $REQUIRED_KEYS; do [ -n "${!k:-}" ] || missing="$missing $k"; done
if [ -n "$missing" ]; then
  echo "$CONFIG does not set:$missing" >&2
  exit 78
fi
: "${CONTROL_LABEL:=control}"
: "${CANDIDATE_LABEL:=candidate}"
: "${CONTROL_METAB:=$CONTROL_WT/.venv/bin/metab}"
: "${CANDIDATE_METAB:=$CANDIDATE_WT/.venv/bin/metab}"
: "${HARNESS_ARGS:=}"
: "${EXCLUDE_MAX_LOAD:=$MAX_LOAD}"
: "${LOAD_FILTER:=$WORKTREE/explorations/performance-loop/experiments/exp-060-062-load-filter.mjs}"
: "${COUNT:=$SELF_DIR/paced-series-count.mjs}"
: "${LOCK_WAIT_HOURS:=12}"
: "${QUIET_WAIT_MINUTES:=60}"
: "${QUIET_SECONDS:=60}"
: "${CAFFEINATE:=1}"
: "${OWNER_NOTE:=}"
WORKTREE=${WORKTREE%/}
OUT=${OUT%/}

PROTOCOL_PATH=$WORKTREE/$PROTOCOL
RECORD_DIR=$(dirname "$PROTOCOL") # the protocol's directory, beside the record
COMMON=$(git -C "$WORKTREE" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
LOCK=""
[ -n "$COMMON" ] && LOCK=$COMMON/metabrowser-series.lock
BENCH=$HARNESS_WT/.bench/transitions/$ROUND
RUNS=$BENCH/runs.jsonl
POWER=$OUT/$ROUND-power.jsonl
SAMPLES=$OUT/$ROUND-power-samples.log
MODEFILE=$OUT/$ROUND-judged-mode.txt
PAIRLOGS=$OUT/pairs
# The corpus as the registration records it, in the harness's own terms (provenance.mjs
# corpusProvenance): commit, dirty, trunk, refs digest. The first pair starts only on this;
# every later pair only on what the first pair started on.
CORPUS_EXPECT="$CORPUS_COMMIT false $CORPUS_TRUNK $CORPUS_REFS"

HELD=0
SAMPLER=""
NODE_PID=""
CAFF=""

# ------------------------------------------------------------------ readings
log() { echo "[$(date -u +%FT%TZ)] $*"; }
iso() { date -u +%FT%TZ; }
load1() { sysctl -n vm.loadavg | awk '{print $2}'; }
lpm() { pmset -g | awk '/lowpowermode/{print $2}'; }
src() { pmset -g batt | head -1 | sed -n "s/^Now drawing from '\(.*\)'$/\1/p"; }
under() { awk -v l="$1" -v m="$2" 'BEGIN{exit !(l + 0 < m + 0)}'; }
matches() { # matches VALUE ERE: the whole value matches
  local re=$2
  [[ $1 =~ $re ]]
}
sha() { if [ -f "$1" ]; then shasum -a 256 "$1" | cut -d' ' -f1; else echo none; fi; }
# Samples 10 s apart over QUIET_SECONDS, every one under MAX_LOAD: 7 samples span 60 s.
quiet() {
  local i n=$((QUIET_SECONDS / 10 + 1))
  for i in $(seq 1 "$n"); do
    under "$(load1)" "$MAX_LOAD" || return 1
    [ "$i" -lt "$n" ] && sleep 10
  done
  return 0
}
series_running() { pgrep -f 'transitions[.]mjs run' >/dev/null; }
# Read-only: --no-optional-locks keeps status from refreshing another checkout's index.
clean_at() {
  [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" = "$2" ] &&
    [ -z "$(git -C "$1" --no-optional-locks status --porcelain 2>/dev/null)" ]
}
version_of() { (cd "$OUT" 2>/dev/null || cd /; "$1" --version 2>/dev/null); }
# The corpus as the frozen harness reads it: "commit dirty trunk refs".
corpus_now() {
  (cd "$HARNESS_WT" && node --input-type=module -e '
import { corpusProvenance } from "./explorations/performance-loop/provenance.mjs";
const p = corpusProvenance(process.argv[1]);
console.log([p.commit, p.dirty, p.trunk, p.refs].join(" "));' "$CORPUS")
}
owner_pid() { grep -o -E 'pid[=: ]+[0-9]+' "$1/owner" 2>/dev/null | head -1 | grep -o -E '[0-9]+$'; }
owner_line() { head -1 "$1/owner" 2>/dev/null; }
# OUT holds local paths: it must be a directory inside WORKTREE that Git ignores.
out_ok() {
  case "$OUT" in "$WORKTREE"/?*) ;; *) return 1 ;; esac
  git -C "$WORKTREE" check-ignore -q -- "${OUT#"$WORKTREE"/}" 2>/dev/null
}

# ------------------------------------------------------------------ gates
FAILS=0
gate() { # gate NAME COMMAND...: prints PASS or FAIL with the detail the command printed
  local name=$1 detail rc
  shift
  detail=$("$@" 2>&1)
  rc=$?
  if [ "$rc" = 0 ]; then echo "PASS  $name: $detail"; else
    echo "FAIL  $name: $detail"
    FAILS=$((FAILS + 1))
  fi
  return "$rc"
}
g_config() {
  local p="" k w dir
  matches "$ROUND" '^exp-[0-9]{3}$' || p="$p; ROUND '$ROUND' is not exp-NNN"
  for k in CONTROL_HEAD CANDIDATE_HEAD HARNESS_HEAD CORPUS_COMMIT CORPUS_TRUNK; do
    matches "${!k}" '^[0-9a-f]{40}$' || p="$p; $k '${!k}' is not a full commit"
  done
  matches "$CORPUS_REFS" '^[0-9a-f]{16}$' || p="$p; CORPUS_REFS '$CORPUS_REFS' is not a 16-digit digest"
  for k in SCENARIO_REVISION TARGET MAX_ATTEMPTS LOCK_WAIT_HOURS QUIET_WAIT_MINUTES QUIET_SECONDS; do
    matches "${!k}" '^[1-9][0-9]*$' || p="$p; $k '${!k}' is not a positive integer"
  done
  if matches "$TARGET" '^[0-9]+$' && matches "$MAX_ATTEMPTS" '^[0-9]+$' && [ "$TARGET" -gt "$MAX_ATTEMPTS" ]; then
    p="$p; TARGET $TARGET is above MAX_ATTEMPTS $MAX_ATTEMPTS"
  fi
  if matches "$QUIET_SECONDS" '^[0-9]+$' && [ $((QUIET_SECONDS % 10)) != 0 ]; then
    p="$p; QUIET_SECONDS $QUIET_SECONDS is not a multiple of 10"
  fi
  for k in MAX_LOAD EXCLUDE_MAX_LOAD; do
    matches "${!k}" '^[0-9]+([.][0-9]+)?$' || p="$p; $k '${!k}' is not a number"
  done
  for k in CONTROL_LABEL CANDIDATE_LABEL; do
    matches "${!k}" '^[A-Za-z0-9_.-]+$' || p="$p; $k '${!k}' is not a plain word"
  done
  [ "$CONTROL_LABEL" != "$CANDIDATE_LABEL" ] || p="$p; the two labels are the same"
  case "$CAFFEINATE" in
    0) ;;
    1) command -v caffeinate >/dev/null || p="$p; CAFFEINATE=1 but no caffeinate on PATH" ;;
    *) p="$p; CAFFEINATE '$CAFFEINATE' is not 0 or 1" ;;
  esac
  case "$PROTOCOL" in /* | ../* | */../*) p="$p; PROTOCOL '$PROTOCOL' is not a path inside WORKTREE" ;; esac
  if [ -z "$COMMON" ]; then
    p="$p; WORKTREE $WORKTREE is not a Git work tree"
  elif [ "$(git -C "$WORKTREE" rev-parse --show-toplevel 2>/dev/null)" != "$(cd "$WORKTREE" && pwd -P)" ]; then
    p="$p; WORKTREE $WORKTREE is not its work tree's top level"
  fi
  out_ok || p="$p; OUT $OUT is not a Git-ignored directory inside WORKTREE"
  dir=$(dirname "$CONFIG")
  if [ "$(git -C "$dir" rev-parse --is-inside-work-tree 2>/dev/null)" = true ] &&
    ! git -C "$dir" check-ignore -q -- "$(basename "$CONFIG")"; then
    p="$p; the config $CONFIG is inside a work tree and not ignored by Git"
  fi
  set -f
  for w in $HARNESS_ARGS; do
    case "$w" in
      --exp | --exp=* | --corpus | --corpus=* | --runs | --runs=* | --out | --out=* | --condition | --condition=* | --order | --order=*)
        p="$p; HARNESS_ARGS sets $w, which the driver owns"
        ;;
    esac
  done
  set +f
  [ -f "$COUNT" ] || p="$p; no count script at $COUNT"
  [ -f "$LOAD_FILTER" ] || p="$p; no load filter at $LOAD_FILTER"
  command -v node >/dev/null || p="$p; no node on PATH"
  [ -z "$p" ] || {
    echo "${p#; }"
    return 1
  }
  echo "$ROUND, ${HARNESS_ARGS:-every journey}; sha256 config $(sha "$CONFIG"), driver $(sha "$SELF"), count $(sha "$COUNT"), load filter $(sha "$LOAD_FILTER")"
}
g_protocol() {
  [ -f "$PROTOCOL_PATH" ] || {
    echo "no $PROTOCOL in $WORKTREE"
    return 1
  }
  git -C "$WORKTREE" ls-files --error-unmatch -- "$PROTOCOL" >/dev/null 2>&1 || {
    echo "$PROTOCOL is not tracked"
    return 1
  }
  local dirty
  dirty=$(git -C "$WORKTREE" --no-optional-locks status --porcelain -- "$RECORD_DIR")
  [ -z "$dirty" ] || {
    echo "uncommitted changes beside the record: $(echo "$dirty" | tr '\n' ' ')"
    return 1
  }
  local here there
  here=$(git -C "$WORKTREE" rev-parse "HEAD:$PROTOCOL" 2>/dev/null)
  there=$(git -C "$WORKTREE" rev-parse "origin/$BRANCH:$PROTOCOL" 2>/dev/null)
  [ -n "$here" ] && [ "$here" = "$there" ] || {
    echo "committed blob ${here:-none} is not the pushed one (${there:-none} on origin/$BRANCH)"
    return 1
  }
  echo "committed and pushed at $(git -C "$WORKTREE" rev-parse --short HEAD), sha256 $(sha "$PROTOCOL_PATH")"
}
g_build() { # g_build CHECKOUT HEAD METAB VERSION
  clean_at "$1" "$2" || {
    echo "$1 is not at ${2:0:8} and clean (HEAD $(git -C "$1" rev-parse --short HEAD 2>/dev/null))"
    return 1
  }
  local v
  v=$(version_of "$3")
  [ "$v" = "$4" ] || {
    echo "version '$v', registered '$4'"
    return 1
  }
  echo "${2:0:8}, clean, $v"
}
g_harness() {
  clean_at "$HARNESS_WT" "$HARNESS_HEAD" || {
    echo "not at ${HARNESS_HEAD:0:8} and clean"
    return 1
  }
  local r
  r=$(cd "$HARNESS_WT" && node --input-type=module -e 'import { SCENARIO_REVISION } from "./explorations/performance-loop/transitions-stats.mjs"; console.log(SCENARIO_REVISION)')
  [ "$r" = "$SCENARIO_REVISION" ] || {
    echo "scenario revision $r, registered $SCENARIO_REVISION"
    return 1
  }
  echo "${HARNESS_HEAD:0:8}, clean, scenario revision $r, $(node --version)"
}
g_corpus() { # g_corpus EXPECTED
  local c
  c=$(corpus_now)
  [ "$c" = "$1" ] || {
    echo "reads '$c', expected '$1'"
    return 1
  }
  echo "$c"
}
g_fresh() {
  local f
  for f in "$BENCH" "$POWER" "$SAMPLES"; do
    [ ! -e "$f" ] || {
      echo "$f exists; refusing to append to an earlier attempt or reuse its state"
      return 1
    }
  done
  echo "no $ROUND bench, state, power log or samples yet"
}
g_lock_free() {
  [ -n "$LOCK" ] || {
    echo "no lock path: WORKTREE has no git common dir"
    return 1
  }
  if [ -e "$LOCK" ]; then
    local pid
    pid=$(owner_pid "$LOCK")
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "held, and STALE: pid $pid is not running ($(owner_line "$LOCK")); left for the coordinator"
    else
      echo "held by '$(owner_line "$LOCK")'"
    fi
    return 1
  fi
  echo "$LOCK is free"
}
g_no_series() {
  if series_running; then
    echo "a transitions.mjs run is in progress: $(pgrep -fl 'transitions[.]mjs run' | head -2 | tr '\n' ' ')"
    return 1
  fi
  echo "no transitions.mjs run in progress"
}
g_load() {
  local l
  l=$(load1)
  under "$l" "$MAX_LOAD" || {
    echo "one-minute load $l, not under $MAX_LOAD"
    return 1
  }
  echo "one-minute load $l (all three: $(sysctl -n vm.loadavg)); the series waits for $QUIET_SECONDS s under $MAX_LOAD before each pair"
}
g_power() {
  local l s
  l=$(lpm)
  s=$(src)
  [ -n "$l" ] && [ -n "$s" ] || {
    echo "unreadable (lowpowermode '$l', source '$s')"
    return 1
  }
  echo "lowpowermode $l, $s (the judged mode is the reading before the first attempt)"
}
builds_ok() {
  clean_at "$CONTROL_WT" "$CONTROL_HEAD" && clean_at "$CANDIDATE_WT" "$CANDIDATE_HEAD" &&
    clean_at "$HARNESS_WT" "$HARNESS_HEAD" &&
    [ "$(version_of "$CONTROL_METAB")" = "$CONTROL_VERSION" ] &&
    [ "$(version_of "$CANDIDATE_METAB")" = "$CANDIDATE_VERSION" ]
}

# The lock's own mechanics, on a scratch path under OUT: take, name the owner, release;
# and a stale fixture (a pid that is not running) reported and left in place. It never
# touches the series lock.
g_lock_selftest() {
  out_ok || {
    echo "OUT is not a Git-ignored directory inside WORKTREE; no scratch lock written"
    return 1
  }
  mkdir -p "$OUT"
  local t=$OUT/lock-selftest.lock s=$OUT/lock-selftest-stale.lock
  [ "$t" != "$LOCK" ] && [ "$s" != "$LOCK" ] || {
    echo "a scratch path is the series lock"
    return 1
  }
  rm -rf "$t" "$s"
  mkdir "$t" 2>/dev/null || {
    echo "mkdir failed"
    return 1
  }
  printf 'pid %s: paced-series.sh lock self-test, since %s\n' "$$" "$(iso)" >"$t/owner"
  [ "$(owner_pid "$t")" = "$$" ] || {
    echo "owner pid not read back"
    return 1
  }
  mkdir "$t" 2>/dev/null && {
    echo "a second mkdir succeeded"
    return 1
  }
  rm -f "$t/owner" && rmdir "$t" || {
    echo "release failed"
    return 1
  }
  mkdir "$s" && printf 'pid 99999999: fixture, since %s\n' "$(iso)" >"$s/owner"
  local p
  p=$(owner_pid "$s")
  kill -0 "$p" 2>/dev/null && {
    echo "fixture pid $p is running"
    return 1
  }
  [ -d "$s" ] || {
    echo "stale fixture removed"
    return 1
  }
  rm -f "$s/owner" && rmdir "$s"
  echo "atomic mkdir excludes a second taker; owner pid read back; release removes it; a dead owner (pid $p) reads as stale"
}
# The exit trap's release: only a lock this driver holds, whose owner file names this pid,
# and that holds nothing but that file. Defined here so --self-test can exercise it.
release_lock() {
  [ "$HELD" = 1 ] || return 0
  if [ "$(owner_pid "$LOCK")" = "$$" ]; then
    rm -f "$LOCK/owner" && rmdir "$LOCK" && log "lock released" || log "lock NOT released: $LOCK holds more than its owner file"
  else
    log "lock NOT released: its owner file no longer names pid $$ ($(owner_line "$LOCK"))"
  fi
  HELD=0
}

run_check_gates() {
  gate "config" g_config
  gate "protocol" g_protocol
  gate "control" g_build "$CONTROL_WT" "$CONTROL_HEAD" "$CONTROL_METAB" "$CONTROL_VERSION"
  gate "candidate" g_build "$CANDIDATE_WT" "$CANDIDATE_HEAD" "$CANDIDATE_METAB" "$CANDIDATE_VERSION"
  gate "harness" g_harness
  gate "corpus" g_corpus "$CORPUS_EXPECT"
  gate "fresh state" g_fresh
  gate "series lock" g_lock_free
  gate "lock mechanics" g_lock_selftest
  gate "other series" g_no_series
  gate "load" g_load
  gate "power" g_power
}
CHECK_GATES="config|protocol|control|candidate|harness|corpus|fresh state|series lock|lock mechanics|other series|load|power"

if [ "$ACTION" = check ]; then
  log "paced-series.sh --check for $ROUND: gates only; no lock taken, nothing timed"
  run_check_gates
  log "lock path ${LOCK:-none}; runs file $RUNS; $FAILS gate(s) failed"
  [ "$FAILS" = 0 ]
  exit $?
fi

# ------------------------------------------------------------------ self-test
# Every fixture lives under $OUT/self-test. The series lock is only ever read.
ST=$OUT/self-test
scratch_ok() { # scratch_ok PATH: under ST, and neither the series lock nor in the common dir
  case "$1" in "$ST"/?*) ;; *) return 1 ;; esac
  [ "$1" != "$LOCK" ] || return 1
  case "$1" in "$COMMON"/*) return 1 ;; esac
  return 0
}
t_lock_reports() { # g_lock_free on a fixture standing in for the lock: free, stale, held
  local d=$ST/series-fixture.lock out rc
  scratch_ok "$d" || {
    echo "fixture path $d is not scratch"
    return 1
  }
  rm -rf "$d"
  out=$(LOCK=$d && g_lock_free)
  rc=$?
  [ "$rc" = 0 ] && matches "$out" 'is free$' || {
    echo "a free path read: $out"
    return 1
  }
  mkdir "$d" && printf 'pid 99999999: fixture, since %s\n' "$(iso)" >"$d/owner"
  out=$(LOCK=$d && g_lock_free)
  rc=$?
  [ "$rc" = 1 ] && matches "$out" 'STALE' && [ -f "$d/owner" ] || {
    echo "a dead owner read: $out (left in place: $([ -d "$d" ] && echo yes || echo no))"
    return 1
  }
  printf 'pid %s: fixture, since %s\n' "$$" "$(iso)" >"$d/owner"
  out=$(LOCK=$d && g_lock_free)
  rc=$?
  [ "$rc" = 1 ] && matches "$out" '^held by' || {
    echo "a live owner read: $out"
    return 1
  }
  rm -f "$d/owner" && rmdir "$d"
  echo "a free path passes; a dead owner reads as STALE and is left in place; a live owner reads as held"
}
t_lock_release() { # the exit trap's release_lock on fixtures
  local d=$ST/release-fixture.lock out
  scratch_ok "$d" || {
    echo "fixture path $d is not scratch"
    return 1
  }
  rm -rf "$d"
  mkdir "$d" && printf 'pid %s: fixture\n' "$$" >"$d/owner"
  out=$(LOCK=$d && HELD=1 && release_lock)
  [ ! -e "$d" ] && matches "$out" 'lock released$' || {
    echo "its own lock: $out"
    return 1
  }
  mkdir "$d" && printf 'pid 1: fixture\n' >"$d/owner"
  out=$(LOCK=$d && HELD=1 && release_lock)
  [ -f "$d/owner" ] && matches "$out" 'NOT released: its owner file no longer names' || {
    echo "another owner's lock: $out"
    return 1
  }
  printf 'pid %s: fixture\n' "$$" >"$d/owner" && : >"$d/extra"
  out=$(LOCK=$d && HELD=1 && release_lock 2>/dev/null)
  [ -d "$d" ] && matches "$out" 'NOT released: .* holds more than its owner file' || {
    echo "a lock holding more than its owner file: $out"
    return 1
  }
  printf 'pid %s: fixture\n' "$$" >"$d/owner"
  out=$(LOCK=$d && HELD=0 && release_lock)
  [ -f "$d/owner" ] && [ -z "$out" ] || {
    echo "a lock not held: $out"
    return 1
  }
  rm -f "$d/owner" "$d/extra" && rmdir "$d"
  echo "releases its own lock; keeps one whose owner file names another pid, one holding more than its owner file, and one it does not hold"
}
t_count() { # the stopping count on five synthetic attempts with known verdicts
  local r=$ST/count-runs.jsonl pw=$ST/count-power.jsonl out want
  : >"$r"
  for s in s1 s2 s3 s4; do
    for c in control candidate; do
      local l=1
      [ "$s" = s2 ] && l=20
      printf '{"series":"%s","pair":1,"condition":"%s","run":1,"valid":true,"load_start":[%s,1,1],"journeys":[{"transitions":[{"load1":1}]}]}\n' "$s" "$c" "$l" >>"$r"
    done
  done
  {
    echo '{"attempt":1,"series":"s1","lpm_start":0,"lpm_end":0,"src_start":"AC Power","src_end":"AC Power"}'
    echo '{"attempt":2,"series":"s2","lpm_start":0,"lpm_end":0,"src_start":"AC Power","src_end":"AC Power"}'
    echo '{"attempt":3,"series":"s3","lpm_start":1,"lpm_end":1,"src_start":"AC Power","src_end":"AC Power"}'
    echo '{"attempt":4,"series":"s4","lpm_start":0,"lpm_end":1,"src_start":"AC Power","src_end":"AC Power"}'
    echo '{"attempt":5,"series":null,"lpm_start":0,"lpm_end":0,"src_start":"AC Power","src_end":"AC Power"}'
  } >"$pw"
  out=$(node "$COUNT" --runs "$r" --power "$pw" --mode "0|AC Power" --load-filter "$LOAD_FILTER" --max-load "$EXCLUDE_MAX_LOAD" 2>&1) || {
    echo "the count failed: $out"
    return 1
  }
  want="judged 1 excluded 3 other_mode 1 attempts 5"
  [ "$(echo "$out" | tail -1)" = "$want" ] || {
    echo "printed '$(echo "$out" | tr '\n' '/')', expected a last line '$want'"
    return 1
  }
  echo "$want, from $(basename "$COUNT") with $(basename "$LOAD_FILTER") at --max-load $EXCLUDE_MAX_LOAD (one judged; one over the load bound, one with disagreeing power readings and one with no rows excluded; one in another mode reported)"
}
snap() { # one line per path: absent, or its type, inode, mtime and size, and a lock's owner
  local f
  for f in "$@"; do
    if [ -e "$f" ]; then
      echo "$f $(stat -f '%HT %i %m %z' "$f") $(owner_line "$f")"
    else
      echo "$f absent"
    fi
  done
}
mkshim() { # mkshim NAME REAL: log every call to CALLS, then run REAL
  cat >"$SHIMS/$1" <<EOF
#!/bin/bash
printf '%s\n' "$1 \$*" >>'$CALLS'
exec '$2' "\$@"
EOF
  chmod +x "$SHIMS/$1"
}
t_check() { # --check in a child, under shims that log every mkdir, rmdir, rm, node, caffeinate
  local before after rc n_pass n_fail g missing="" real
  [ -n "$LOCK" ] || {
    echo "no lock path: WORKTREE has no git common dir"
    return 1
  }
  SHIMS=$ST/shims
  CALLS=$ST/check-calls.log
  mkdir -p "$SHIMS" && : >"$CALLS"
  for real in mkdir rmdir rm node caffeinate; do
    mkshim "$real" "$(command -v "$real" || echo "/usr/bin/false")"
  done
  before=$(snap "$LOCK" "$BENCH" "$RUNS" "$POWER" "$SAMPLES" "$MODEFILE" "$PAIRLOGS")
  PATH="$SHIMS:$PATH" "$BASH" "$SELF" --config "$CONFIG" --check >"$ST/check.out" 2>&1
  rc=$?
  after=$(snap "$LOCK" "$BENCH" "$RUNS" "$POWER" "$SAMPLES" "$MODEFILE" "$PAIRLOGS")
  [ "$before" = "$after" ] || {
    echo "state changed: before [$before] after [$after]"
    return 1
  }
  if grep -F -q -- "$LOCK" "$CALLS"; then
    echo "a logged call names the series lock: $(grep -F -- "$LOCK" "$CALLS" | head -3 | tr '\n' ' ')"
    return 1
  fi
  if grep -E -q 'transitions[.]mjs run' "$CALLS" || grep -q '^caffeinate' "$CALLS"; then
    echo "--check started the harness or caffeinate: $(grep -E 'transitions[.]mjs run|^caffeinate' "$CALLS" | head -2 | tr '\n' ' ')"
    return 1
  fi
  grep -q '^node ' "$CALLS" && grep -q '^mkdir ' "$CALLS" || {
    echo "the shims saw no node or no mkdir call, so they prove nothing"
    return 1
  }
  if pgrep -f "transitions[.]mjs run --exp $ROUND" >/dev/null; then
    echo "a transitions.mjs run for $ROUND is running"
    return 1
  fi
  local IFS='|'
  for g in $CHECK_GATES; do
    grep -E -q "^(PASS|FAIL)  $g: " "$ST/check.out" || missing="$missing, $g"
  done
  unset IFS
  [ -z "$missing" ] || {
    echo "--check did not report: ${missing#, }"
    return 1
  }
  n_pass=$(grep -c '^PASS  ' "$ST/check.out")
  n_fail=$(grep -c '^FAIL  ' "$ST/check.out")
  echo "--check (exit $rc) reported all $((n_pass + n_fail)) gates, $n_pass PASS and $n_fail FAIL; of its $(grep -c -E '^(mkdir|rmdir|rm|node|caffeinate) ' "$CALLS") logged mkdir, rmdir, rm, node and caffeinate calls none names the series lock, none starts transitions.mjs, none is caffeinate; the series lock ($(snap "$LOCK" | cut -d' ' -f2-)), bench, runs file, power log, samples, mode file and pair logs are as they were"
}

if [ "$ACTION" = self-test ]; then
  out_ok || {
    echo "FAIL  self-test: OUT $OUT is not a Git-ignored directory inside WORKTREE; no fixtures written"
    exit 1
  }
  scratch_ok "$ST/x" || {
    echo "FAIL  self-test: $ST is not a scratch path"
    exit 1
  }
  rm -rf "$ST" && mkdir -p "$ST"
  log "paced-series.sh --self-test for $ROUND: fixtures under $ST; the series lock is only read"
  gate "lock mechanics" g_lock_selftest
  gate "stale lock reported" t_lock_reports
  gate "lock release" t_lock_release
  gate "stopping count" t_count
  gate "check leaves state" t_check
  [ -f "$ST/check.out" ] && sed 's/^/    /' "$ST/check.out"
  log "$FAILS self-test(s) failed; --check's output and its call log are in $ST"
  [ "$FAILS" = 0 ]
  exit $?
fi

# ------------------------------------------------------------------ the series
finish() {
  local rc=$?
  if [ -n "$NODE_PID" ]; then
    log "stopping the running pair (pid $NODE_PID); the harness stops its servers and Chrome"
    kill -TERM "$NODE_PID" 2>/dev/null
    wait "$NODE_PID" 2>/dev/null
    NODE_PID=""
  fi
  [ -n "$SAMPLER" ] && kill "$SAMPLER" 2>/dev/null
  [ -n "$CAFF" ] && kill "$CAFF" 2>/dev/null
  release_lock
  log "driver exits $rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

for v in $(compgen -e | grep -E '^(METABROWSER_|TRANSITIONS_BENCH$)'); do
  log "unsetting $v for the series (the servers run with the default environment)"
  unset "$v"
done
fail=0
gate "config" g_config || fail=1
gate "protocol" g_protocol || fail=1
gate "control" g_build "$CONTROL_WT" "$CONTROL_HEAD" "$CONTROL_METAB" "$CONTROL_VERSION" || fail=1
gate "candidate" g_build "$CANDIDATE_WT" "$CANDIDATE_HEAD" "$CANDIDATE_METAB" "$CANDIDATE_VERSION" || fail=1
gate "harness" g_harness || fail=1
gate "corpus" g_corpus "$CORPUS_EXPECT" || fail=1
gate "fresh state" g_fresh || fail=1
[ "$fail" = 0 ] || {
  log "a registered input does not hold; nothing started"
  exit 4
}
mkdir -p "$OUT" "$PAIRLOGS"
if [ "$CAFFEINATE" = 1 ]; then
  caffeinate -i -w $$ &
  CAFF=$!
  log "caffeinate -i holds while pid $$ runs (caffeinate pid $CAFF)"
fi

# 1. The series lock, through the pacing gate: free, no transitions.mjs run in progress,
#    and the one-minute load under MAX_LOAD for QUIET_SECONDS. A lock whose owner is not
#    running is reported, never removed. Operational stop: not taken in LOCK_WAIT_HOURS.
deadline=$(($(date +%s) + LOCK_WAIT_HOURS * 3600))
stale_said=0
held_said=0
while :; do
  [ "$(date +%s)" -gt "$deadline" ] && {
    log "lock not taken in $LOCK_WAIT_HOURS h; stopping"
    exit 3
  }
  if [ -e "$LOCK" ]; then
    pid=$(owner_pid "$LOCK")
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      [ "$stale_said" = 0 ] && log "the lock looks STALE (pid $pid is not running): $(owner_line "$LOCK"); waiting, not removing it" && stale_said=1
    else
      [ "$held_said" = 0 ] && log "waiting behind the lock: $(owner_line "$LOCK")" && held_said=1
    fi
    sleep 30
    continue
  fi
  stale_said=0
  held_said=0
  if series_running; then
    sleep 30
    continue
  fi
  if quiet && ! series_running && mkdir "$LOCK" 2>/dev/null; then
    HELD=1
    printf 'pid %s: paced-series.sh, %s paced pairs%s, since %s\n' "$$" "$ROUND" "${OWNER_NOTE:+ ($OWNER_NOTE)}" "$(iso)" >"$LOCK/owner"
    break
  fi
  sleep 15
done
log "lock taken at load $(sysctl -n vm.loadavg); lowpowermode $(lpm); $(src); $LOCK"
log "driver sha256 $(sha "$SELF"); config $CONFIG sha256 $(sha "$CONFIG"); count sha256 $(sha "$COUNT"); load filter sha256 $(sha "$LOAD_FILTER"); runs $RUNS"
(while :; do
  echo "$(iso) lowpowermode $(lpm) $(src)"
  sleep 15
done >>"$SAMPLES" 2>&1) &
SAMPLER=$!

# 2. Paced pairs: one transitions.mjs invocation per pair, the control first in odd
#    attempts; TARGET judged pairs, at most MAX_ATTEMPTS attempts. Operational stop: no
#    quiet window within QUIET_WAIT_MINUTES while waiting to start a pair.
MODE=""
REF0=""
judged=0
attempt=0
while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
  attempt=$((attempt + 1))
  wait_start=$(date +%s)
  until ! series_running && quiet; do
    if [ $(($(date +%s) - wait_start)) -ge $((QUIET_WAIT_MINUTES * 60)) ]; then
      log "no quiet window in $QUIET_WAIT_MINUTES min; stopping before attempt $attempt ($((attempt - 1)) run, $judged judged)"
      exit 9
    fi
    sleep 60
  done
  builds_ok || {
    log "a build or the harness moved, became dirty, or reports another version before attempt $attempt"
    exit 8
  }
  corpus=$(corpus_now)
  if [ -z "$REF0" ]; then
    [ "$corpus" = "$CORPUS_EXPECT" ] || {
      log "the corpus reads '$corpus', the registration records '$CORPUS_EXPECT'; refusing the first pair"
      exit 6
    }
    REF0=$corpus
  elif [ "$corpus" != "$REF0" ]; then
    log "the corpus reads '$corpus', the first pair's was '$REF0'; refusing attempt $attempt"
    exit 6
  fi
  l0=$(lpm)
  s0=$(src)
  load0=$(load1)
  if [ -z "$MODE" ]; then
    MODE="$l0|$s0"
    echo "$MODE" >"$MODEFILE"
    log "judged mode: lowpowermode $l0, $s0 (read before the first attempt)"
  fi
  if [ $((attempt % 2)) = 1 ]; then
    first="$CONTROL_LABEL=$CONTROL_METAB" second="$CANDIDATE_LABEL=$CANDIDATE_METAB"
  else
    first="$CANDIDATE_LABEL=$CANDIDATE_METAB" second="$CONTROL_LABEL=$CONTROL_METAB"
  fi
  before=0
  [ -f "$RUNS" ] && before=$(wc -l <"$RUNS" | tr -d ' ')
  t0=$(iso)
  log "== attempt $attempt (${first%%=*} first) at load $load0; lowpowermode $l0; $s0; corpus refs ${REF0##* }"
  # HARNESS_ARGS is split into words on purpose, with globbing off.
  (
    set -f
    cd "$HARNESS_WT" && exec node explorations/performance-loop/transitions.mjs run --exp "$ROUND" \
      --corpus "$CORPUS" --runs 1 --out "$RUNS" $HARNESS_ARGS \
      --condition "$first" --condition "$second"
  ) >"$PAIRLOGS/attempt-$attempt.log" 2>&1 &
  NODE_PID=$!
  wait "$NODE_PID"
  rc=$?
  NODE_PID=""
  t1=$(iso)
  l1=$(lpm)
  s1=$(src)
  load_end=$(load1)
  cat "$PAIRLOGS/attempt-$attempt.log"
  # What the harness recorded: the series and, for every new row, its corpus at start and
  # end and its scenario revision.
  rows=$(tail -n +$((before + 1)) "$RUNS" 2>/dev/null | node -e '
let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => {
  const rows = s.split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const series = [...new Set(rows.map((r) => r.series))];
  const refs = [...new Set(rows.flatMap((r) => [r.corpus?.refs, r.corpus_end?.refs]))];
  const revs = [...new Set(rows.map((r) => r.scenario_revision))];
  console.log([series.length === 1 ? series[0] : "", rows.length, refs.join(","), revs.join(",")].join("|"));
});')
  IFS='|' read -r series nrows rowrefs rowrevs <<<"$rows"
  node -e 'const [a, series, first, l0, l1, s0, s1, c0, load0, load1, t0, t1, rc] = process.argv.slice(1);
const n = (v) => (v === "" ? null : Number(v));
console.log(JSON.stringify({ attempt: Number(a), series: series || null, first, lpm_start: n(l0), lpm_end: n(l1),
  src_start: s0 || null, src_end: s1 || null, corpus_start: c0, load_start: n(load0), load_end: n(load1),
  started_at: t0, finished_at: t1, exit: Number(rc) }));' \
    "$attempt" "${series:-}" "${first%%=*}" "$l0" "$l1" "$s0" "$s1" "$corpus" "$load0" "$load_end" "$t0" "$t1" "$rc" >>"$POWER"
  log "attempt $attempt exit $rc; ${nrows:-0} row(s), series ${series:-none}; load $load_end; lowpowermode $l1; $s1"
  if [ "${nrows:-0}" -gt 0 ] && [ "$rowrefs" != "${REF0##* }" ]; then
    log "the rows of attempt $attempt record corpus refs '$rowrefs', not '${REF0##* }'; stopping"
    exit 6
  fi
  if [ "${nrows:-0}" -gt 0 ] && [ "$rowrevs" != "$SCENARIO_REVISION" ]; then
    log "the rows of attempt $attempt record scenario revision '$rowrevs'; stopping"
    exit 8
  fi
  builds_ok || {
    log "a build or the harness moved, became dirty, or reports another version during attempt $attempt"
    exit 8
  }
  if ! result=$(node "$COUNT" --runs "$RUNS" --power "$POWER" --mode "$MODE" \
    --load-filter "$LOAD_FILTER" --max-load "$EXCLUDE_MAX_LOAD" 2>&1); then
    echo "$result"
    log "the stopping count failed after attempt $attempt; stopping"
    exit 10
  fi
  echo "$result"
  judged=$(echo "$result" | awk '/^judged /{print $2}' | tail -1)
  matches "${judged:-}" '^[0-9]+$' || {
    log "the stopping count printed no judged line after attempt $attempt; stopping"
    exit 10
  }
  [ "$judged" -ge "$TARGET" ] && break
done
log "series done: $judged judged pair(s) in $attempt attempt(s); judged mode $MODE"
