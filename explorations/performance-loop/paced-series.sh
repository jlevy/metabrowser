#!/bin/bash
# paced-series.sh: the performance loop's driver for a judged series of the transition
# scenario. It runs one back-to-back pair of two builds per transitions.mjs invocation,
# paced by load, behind the series lock, and checks every registered input before and
# after each pair, until the round has its target of judged pairs or reaches its cap on
# attempts. It generalizes exp-079's driver (experiments/exp-079-protocol.txt, amendments
# 1 and 2). A round's protocol registers the values its config holds.
#
# Only the coordinator starts a series. Anyone may run --check or --self-test; neither
# takes the series lock or starts a timed run. While the series lock is held or a
# transitions.mjs run is live, both skip every gate that would run git status, metab or
# node, so as not to disturb a timed pair, and say why.
#
#   paced-series.sh --config FILE              run the series
#   paced-series.sh --config FILE --check      check every gate once
#   paced-series.sh --config FILE --self-test  test the lock's mechanics, the stopping
#                                              count, the busy skip, the config's
#                                              isolation and a queued run on scratch
#                                              fixtures under OUT, then run --check under
#                                              command shims and show it left the lock and
#                                              series files alone
#
# The coordinator starts a run detached, its output appended to a log in OUT, such as
#   paced-series.sh --config "$CFG" >>"$OUT/$ROUND-paced.log" 2>&1 &
#
# A run queues quietly. Before the lock it checks only what --check checks while a series
# holds the lock (config, fresh state, power), then waits for the lock without running git
# status, metab or node. Once it holds the lock it runs the protocol, build, harness and
# corpus gates; if any fails, it exits 4 and its exit trap releases the lock.
#
# The lock is $(git rev-parse --path-format=absolute --git-common-dir)/metabrowser-series.lock,
# one directory for every worktree of the checkout, taken by one atomic mkdir with an
# owner file naming the driver's pid. It serializes paced-series.sh series only: run.py,
# startup_pairs.py, wkprobe and a hand-run transitions.mjs take no lock. The driver also
# waits while any transitions.mjs run is live, but it cannot see the other instruments.
# The exit trap stops the running pair and releases the lock whenever the shell exits,
# but SIGKILL, a crash or a restart skip the trap and leave the lock naming a dead pid.
# Every later driver and --check reports that lock as stale and never removes it; the
# coordinator does.
#
# Config contract. FILE is a bash fragment of KEY=value assignments. It is sourced in a
# subshell with every key unset, and only the keys below are read back, so it takes no
# value from the environment and cannot set the driver's own variables. A config that
# assigns ACTION, CONFIG or SELF is refused. It holds local paths, so it lives in the
# round's worktree as gitignored attic/expNNN/series.env; start it from
# paced-series.example.env, which explains each key. A config inside a Git work tree
# must be ignored by Git, and OUT must be an ignored directory inside WORKTREE.
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
#   EXCLUDE_MAX_LOAD=     the load rule's bound, passed to the load filter as --max-load;
#                         empty runs the filter at its own default (12), as exp-079 did
#   LOAD_FILTER=$WORKTREE/explorations/performance-loop/experiments/exp-060-062-load-filter.mjs
#   COUNT=paced-series-count.mjs beside this file; another count takes the same arguments
#   LOCK_WAIT_HOURS=12, QUIET_WAIT_MINUTES=60, QUIET_SECONDS=60 (a multiple of 10)
#   CAFFEINATE=1          hold `caffeinate -i` for the driver's life (exp-079 amendment 2)
#   OWNER_NOTE=           words added to the lock's owner line
#
# Power. Low Power Mode and the power source are read before and after every pair. As in
# exp-079's power rule, a pair has a mode only if all four readings are readable and
# agree. A pair whose readings before it are unreadable is not run: it is recorded in the
# power log as an excluded attempt. Before the first attempt the series stops instead
# (exit 7), since the judged mode is that reading.
#
# Exit status:
#   0     the series reached TARGET judged pairs; or every --check gate or self-test passed
#   1     a --check gate or a self-test failed
#   2     --check or --self-test skipped gates because a series is running; none failed
#   3     the lock was not taken in LOCK_WAIT_HOURS
#   4     a registered input does not hold, before the lock or once it is held; nothing
#         was timed, and a lock taken was released
#   5     MAX_ATTEMPTS ran out before TARGET judged pairs
#   6     the corpus moved
#   7     power was unreadable before the first attempt, so no judged mode was read
#   8     a build or the harness moved, or rows record another scenario revision
#   9     no quiet window came in QUIET_WAIT_MINUTES
#   10    the stopping count failed
#   64    usage
#   78    an unreadable, incomplete or refused config
#   129, 130, 143  HUP, INT, TERM
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
readonly SELF SELF_DIR ACTION CONFIG

# ------------------------------------------------------------------ the config
REQUIRED_KEYS="ROUND WORKTREE BRANCH PROTOCOL OUT
  CONTROL_WT CONTROL_HEAD CONTROL_VERSION CANDIDATE_WT CANDIDATE_HEAD CANDIDATE_VERSION
  HARNESS_WT HARNESS_HEAD SCENARIO_REVISION CORPUS CORPUS_COMMIT CORPUS_TRUNK CORPUS_REFS
  TARGET MAX_ATTEMPTS MAX_LOAD"
OPTIONAL_KEYS="CONTROL_LABEL CANDIDATE_LABEL CONTROL_METAB CANDIDATE_METAB HARNESS_ARGS
  EXCLUDE_MAX_LOAD LOAD_FILTER COUNT LOCK_WAIT_HOURS QUIET_WAIT_MINUTES QUIET_SECONDS
  CAFFEINATE OWNER_NOTE"
# shellcheck disable=SC2086
KEYLIST=" $(echo $REQUIRED_KEYS $OPTIONAL_KEYS) "
readonly REQUIRED_KEYS OPTIONAL_KEYS KEYLIST
for k in $KEYLIST; do unset "$k"; done
# The config runs in a subshell, with the read-only names above, and sends back only its
# keys, NUL-delimited. An assignment to a read-only name aborts the subshell, so no
# __loaded marker arrives and the config is refused.
config_stream() {
  (
    for k in $KEYLIST; do unset "$k"; done
    # shellcheck source=/dev/null
    . "$CONFIG" >/dev/null || exit 1
    for k in $KEYLIST; do
      [ -n "${!k+x}" ] && printf '%s\0%s\0' "$k" "${!k}"
    done
    printf '%s\0%s\0' __loaded 1
  )
}
loaded=0
while IFS= read -r -d '' k && IFS= read -r -d '' v; do
  case "$KEYLIST" in *" $k "*) printf -v "$k" '%s' "$v" ;; esac
  [ "$k" = __loaded ] && loaded=1
done < <(config_stream)
if [ "$loaded" != 1 ]; then
  echo "$CONFIG was refused: it failed, read an unset variable, or assigned a read-only name of the driver (ACTION, CONFIG, SELF)" >&2
  exit 78
fi
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
: "${EXCLUDE_MAX_LOAD:=}"
: "${LOAD_FILTER:=$WORKTREE/explorations/performance-loop/experiments/exp-060-062-load-filter.mjs}"
: "${COUNT:=$SELF_DIR/paced-series-count.mjs}"
: "${LOCK_WAIT_HOURS:=12}"
: "${QUIET_WAIT_MINUTES:=60}"
: "${QUIET_SECONDS:=60}"
: "${CAFFEINATE:=1}"
: "${OWNER_NOTE:=}"
WORKTREE=${WORKTREE%/}
OUT=${OUT%/}
for k in $KEYLIST; do readonly "$k"; done

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
BUSY=""

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
# Why a timed pair may be running now: the lock held by a live or unnamed owner, or a live
# transitions.mjs run. A lock whose owner is dead is stale, not busy.
busy_reason() {
  local pid
  if [ -n "$LOCK" ] && [ -e "$LOCK" ]; then
    pid=$(owner_pid "$LOCK")
    if [ -z "$pid" ] || kill -0 "$pid" 2>/dev/null; then
      echo "the series lock is held ($(owner_line "$LOCK"))"
      return 0
    fi
  fi
  if series_running; then echo "a transitions.mjs run is live"; fi
  return 0
}
# One attempt's line in the power log: attempt, series, first, lowpowermode and source
# before and after, corpus, load before and after, times, exit, and why it was skipped.
power_line() {
  node -e 'const [a, series, first, l0, l1, s0, s1, c0, load0, load1, t0, t1, rc, skipped] = process.argv.slice(1);
const n = (v) => (v === "" || v === undefined ? null : Number(v));
const row = { attempt: Number(a), series: series || null, first: first || null, lpm_start: n(l0), lpm_end: n(l1),
  src_start: s0 || null, src_end: s1 || null, corpus_start: c0, load_start: n(load0), load_end: n(load1),
  started_at: t0, finished_at: t1, exit: n(rc) };
if (skipped) row.skipped = skipped;
console.log(JSON.stringify(row));' "$@"
}

# ------------------------------------------------------------------ gates
FAILS=0
SKIPS=0
gate() { # gate NAME COMMAND...: PASS (status 0), SKIP (2) or FAIL, with the command's detail
  local name=$1 detail rc
  shift
  detail=$("$@" 2>&1)
  rc=$?
  case "$rc" in
    0) echo "PASS  $name: $detail" ;;
    2)
      echo "SKIP  $name: $detail"
      SKIPS=$((SKIPS + 1))
      ;;
    *)
      echo "FAIL  $name: $detail"
      FAILS=$((FAILS + 1))
      ;;
  esac
  return "$rc"
}
g_skipped() {
  echo "skipped: $BUSY; rerun when no series is running"
  return 2
}
heavy() { # heavy NAME COMMAND...: a gate that runs git status, metab or node; skipped while BUSY
  if [ -n "$BUSY" ]; then gate "$1" g_skipped; else gate "$@"; fi
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
  matches "$MAX_LOAD" '^[0-9]+([.][0-9]+)?$' || p="$p; MAX_LOAD '$MAX_LOAD' is not a number"
  [ -z "$EXCLUDE_MAX_LOAD" ] || matches "$EXCLUDE_MAX_LOAD" '^[0-9]+([.][0-9]+)?$' ||
    p="$p; EXCLUDE_MAX_LOAD '$EXCLUDE_MAX_LOAD' is not empty or a number"
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
  echo "$ROUND, ${HARNESS_ARGS:-every journey}, load rule at ${EXCLUDE_MAX_LOAD:-the filter default}; sha256 config $(sha "$CONFIG"), driver $(sha "$SELF"), count $(sha "$COUNT"), load filter $(sha "$LOAD_FILTER")"
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
  [ -x "$3" ] || {
    echo "no executable metab at $3"
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
    if [ -z "$pid" ]; then
      echo "held, with no owner pid in $LOCK/owner: being taken this instant, or abandoned; left for the coordinator"
    elif ! kill -0 "$pid" 2>/dev/null; then
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
# The exit trap's release. It removes only a lock this driver holds, whose owner file
# names this pid, and that holds nothing else. It never leaves a lock without an owner
# file: if rmdir fails after the owner file is removed, it writes the owner file again,
# and once this driver has exited the lock reads as stale.
release_lock() {
  [ "$HELD" = 1 ] || return 0
  HELD=0
  if [ "$(owner_pid "$LOCK")" != "$$" ]; then
    log "lock NOT released: its owner file no longer names pid $$ ($(owner_line "$LOCK"))"
    return 0
  fi
  local extra
  extra=$(ls -A "$LOCK" 2>/dev/null | grep -v -x owner | tr '\n' ' ')
  if [ -n "$extra" ]; then
    log "lock NOT released: $LOCK holds more than its owner file (${extra% }); left whole, its owner file naming pid $$"
    return 0
  fi
  if rm -f "$LOCK/owner" && rmdir "$LOCK" 2>/dev/null; then
    log "lock released"
  else
    printf 'pid %s: paced-series.sh, %s, release failed at %s\n' "$$" "$ROUND" "$(iso)" >"$LOCK/owner"
    log "lock NOT released: rmdir failed after the owner file was removed; the owner file names pid $$ again, so the lock reads as stale once this driver exits"
  fi
}

run_check_gates() {
  BUSY=$(busy_reason)
  [ -z "$BUSY" ] || log "$BUSY: skipping the gates that run git status, metab or node (protocol, control, candidate, harness, corpus), so as not to disturb a timed pair"
  gate "config" g_config
  heavy "protocol" g_protocol
  heavy "control" g_build "$CONTROL_WT" "$CONTROL_HEAD" "$CONTROL_METAB" "$CONTROL_VERSION"
  heavy "candidate" g_build "$CANDIDATE_WT" "$CANDIDATE_HEAD" "$CANDIDATE_METAB" "$CANDIDATE_VERSION"
  heavy "harness" g_harness
  heavy "corpus" g_corpus "$CORPUS_EXPECT"
  gate "fresh state" g_fresh
  gate "series lock" g_lock_free
  gate "lock mechanics" g_lock_selftest
  gate "other series" g_no_series
  gate "load" g_load
  gate "power" g_power
}
CHECK_GATES="config|protocol|control|candidate|harness|corpus|fresh state|series lock|lock mechanics|other series|load|power"
verdict() { # the exit status of --check or --self-test
  if [ "$FAILS" != 0 ]; then return 1; elif [ "$SKIPS" != 0 ]; then return 2; else return 0; fi
}

if [ "$ACTION" = check ]; then
  log "paced-series.sh --check for $ROUND: gates only; no lock taken, nothing timed"
  run_check_gates
  log "lock path ${LOCK:-none}; runs file $RUNS; $FAILS gate(s) failed, $SKIPS skipped"
  verdict
  exit $?
fi

# ------------------------------------------------------------------ self-test
# Every fixture lives under $OUT/self-test. The series lock is only ever read.
ST=$OUT/self-test
SHIMS=$ST/shims
CALLS=$ST/calls.log
scratch_ok() { # scratch_ok PATH: under ST, and neither the series lock nor in the common dir
  case "$1" in "$ST"/?*) ;; *) return 1 ;; esac
  [ "$1" != "$LOCK" ] || return 1
  case "$1" in "$COMMON"/*) return 1 ;; esac
  return 0
}
t_lock_reports() { # g_lock_free on a fixture standing in for the lock
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
    echo "a dead owner read: $out (left in place: $([ -f "$d/owner" ] && echo yes || echo no))"
    return 1
  }
  printf 'pid %s: fixture, since %s\n' "$$" "$(iso)" >"$d/owner"
  out=$(LOCK=$d && g_lock_free)
  rc=$?
  [ "$rc" = 1 ] && matches "$out" '^held by' || {
    echo "a live owner read: $out"
    return 1
  }
  rm -f "$d/owner"
  out=$(LOCK=$d && g_lock_free)
  rc=$?
  [ "$rc" = 1 ] && matches "$out" 'no owner pid' && [ -d "$d" ] || {
    echo "a lock with no owner file read: $out"
    return 1
  }
  rmdir "$d"
  echo "a free path passes; a dead owner reads as STALE, a live one as held, and a lock with no owner file as held with no owner pid; each is left in place"
}
t_lock_release() { # the exit trap's release_lock, each case on a fresh fixture
  local d=$ST/release-fixture.lock out
  scratch_ok "$d" || {
    echo "fixture path $d is not scratch"
    return 1
  }
  fixture() {
    rm -rf "$d" && mkdir "$d" && printf 'pid %s: fixture\n' "$1" >"$d/owner"
  }
  fixture $$
  out=$(LOCK=$d && HELD=1 && release_lock)
  [ ! -e "$d" ] && matches "$out" 'lock released$' || {
    echo "its own lock: $out"
    return 1
  }
  fixture 1
  out=$(LOCK=$d && HELD=1 && release_lock)
  [ "$(owner_pid "$d")" = 1 ] && matches "$out" 'NOT released: its owner file no longer names' || {
    echo "another pid's lock: $out"
    return 1
  }
  fixture $$ && : >"$d/extra"
  out=$(LOCK=$d && HELD=1 && release_lock)
  [ "$(owner_pid "$d")" = "$$" ] && [ -f "$d/extra" ] && matches "$out" 'NOT released: .* holds more than its owner file' || {
    echo "a lock holding more than its owner file: $out (owner pid now '$(owner_pid "$d")')"
    return 1
  }
  fixture $$
  out=$(
    LOCK=$d
    HELD=1
    rmdir() { return 1; }
    release_lock
  )
  [ -d "$d" ] && [ "$(owner_pid "$d")" = "$$" ] && matches "$out" 'NOT released: rmdir failed' || {
    echo "a failed rmdir: $out (owner pid now '$(owner_pid "$d")')"
    return 1
  }
  fixture $$
  out=$(LOCK=$d && HELD=0 && release_lock)
  [ "$(owner_pid "$d")" = "$$" ] && [ -z "$out" ] || {
    echo "a lock not held: $out"
    return 1
  }
  rm -rf "$d"
  echo "releases its own lock; leaves whole, owner file intact, a lock naming another pid, one holding more than its owner file, and one it does not hold; after a failed rmdir it writes the owner file again"
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
    echo '{"attempt":5,"series":null,"lpm_start":null,"lpm_end":null,"src_start":null,"src_end":null,"skipped":"power unreadable before the pair; not run"}'
  } >"$pw"
  out=$(node "$COUNT" --runs "$r" --power "$pw" --mode "0|AC Power" --load-filter "$LOAD_FILTER" \
    ${EXCLUDE_MAX_LOAD:+--max-load "$EXCLUDE_MAX_LOAD"} 2>&1) || {
    echo "the count failed: $out"
    return 1
  }
  want="judged 1 excluded 3 other_mode 1 attempts 5"
  [ "$(echo "$out" | tail -1)" = "$want" ] || {
    echo "printed '$(echo "$out" | tr '\n' '/')', expected a last line '$want'"
    return 1
  }
  echo "$want, from $(basename "$COUNT") with $(basename "$LOAD_FILTER") at ${EXCLUDE_MAX_LOAD:-its default bound} (one judged; one over the load bound, one with disagreeing power readings and one skipped for unreadable power excluded; one in another mode reported)"
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
state_now() { snap "$LOCK" "$BENCH" "$RUNS" "$POWER" "$SAMPLES" "$MODEFILE" "$PAIRLOGS"; }
shim_one() { # shim_one NAME REAL: $SHIMS/NAME logs each call to CALLS, then runs REAL
  cat >"$SHIMS/$1" <<EOF
#!/bin/bash
printf '%s\n' "$1 \$*" >>'$CALLS'
exec '$2' "\$@"
EOF
  chmod +x "$SHIMS/$1"
}
make_shims() { # shims that log every mkdir, rmdir, rm, node, caffeinate and git call to CALLS
  local name
  mkdir -p "$SHIMS"
  for name in mkdir rmdir rm node caffeinate git; do
    shim_one "$name" "$(command -v "$name" || echo /usr/bin/false)"
  done
  : >"$CALLS"
}
calls_clean() { # no logged call names the series lock, starts the harness, or is caffeinate
  if grep -F -q -- "$LOCK" "$CALLS"; then
    echo "a logged call names the series lock: $(grep -F -- "$LOCK" "$CALLS" | head -3 | tr '\n' ' ')"
    return 1
  fi
  if grep -E -q 'transitions[.]mjs run|^caffeinate' "$CALLS"; then
    echo "a logged call starts the harness or caffeinate: $(grep -E 'transitions[.]mjs run|^caffeinate' "$CALLS" | head -2 | tr '\n' ' ')"
    return 1
  fi
  grep -q '^mkdir ' "$CALLS" || {
    echo "the shims saw no mkdir call, so they prove nothing"
    return 1
  }
  return 0
}
check_child() { # check_child CONFIG: --check in a child process, under the shims
  CHILD_OUT=$ST/check-$(basename "$1" .env).out
  : >"$CALLS"
  PATH="$SHIMS:$PATH" "$BASH" "$SELF" --config "$1" --check >"$CHILD_OUT" 2>&1
  CHILD_RC=$?
}
all_gates_reported() { # all_gates_reported FILE: one PASS, FAIL or SKIP line per --check gate
  local g missing="" IFS='|'
  for g in $CHECK_GATES; do
    grep -E -q "^(PASS|FAIL|SKIP)  $g: " "$1" || missing="$missing, $g"
  done
  [ -z "$missing" ] || {
    echo "did not report: ${missing#, }"
    return 1
  }
}
t_busy() { # the check gates beside a fixture lock with a live owner: the heavy ones skipped
  local d=$ST/busy-fixture.lock out g missing=""
  scratch_ok "$d" || {
    echo "fixture path $d is not scratch"
    return 1
  }
  make_shims
  rm -rf "$d" && mkdir "$d" && printf 'pid %s: fixture\n' "$$" >"$d/owner"
  out=$(
    LOCK=$d
    FAILS=0
    SKIPS=0
    PATH="$SHIMS:$PATH"
    run_check_gates 2>&1
  )
  rm -f "$d/owner" && rmdir "$d"
  for g in protocol control candidate harness corpus; do
    echo "$out" | grep -E -q "^SKIP  $g: skipped: the series lock is held" || missing="$missing, $g"
  done
  [ -z "$missing" ] || {
    echo "not skipped: ${missing#, }; output: $(echo "$out" | grep -E '^(PASS|FAIL|SKIP)' | cut -c1-60 | tr '\n' '/')"
    return 1
  }
  if grep -E -q '^node |^git .*status' "$CALLS"; then
    echo "a skipped gate still ran: $(grep -E '^node |^git .*status' "$CALLS" | head -2 | tr '\n' ' ')"
    return 1
  fi
  grep -q '^mkdir ' "$CALLS" || {
    echo "the shims saw no mkdir call, so they prove nothing"
    return 1
  }
  echo "beside a lock with a live owner, protocol, control, candidate, harness and corpus are skipped and say why; the $(grep -c -E '^(mkdir|rmdir|rm|node|caffeinate|git) ' "$CALLS") logged calls include no node and no git status (metab runs only inside the skipped build gates)"
}
t_config_isolation() { # configs that assign the driver's own names
  local a=$ST/sets-action.env b=$ST/sets-driver-vars.env before after
  make_shims
  # Should ACTION ever leak, these registered values fail the run path's gates before it
  # takes any lock, so this test can never start a series.
  {
    cat "$CONFIG"
    echo 'PROTOCOL=explorations/performance-loop/experiments/paced-series-self-test-no-protocol.txt'
    echo 'CANDIDATE_HEAD=0000000000000000000000000000000000000000'
    echo 'ACTION=run'
  } >"$a"
  {
    cat "$CONFIG"
    # shellcheck disable=SC2016
    echo 'LOCK=$OUT/self-test/hijacked.lock HELD=1 FAILS=-100 SKIPS=-100 BUSY=x CHECK_GATES=none'
  } >"$b"
  before=$(state_now)
  check_child "$a"
  [ "$CHILD_RC" = 78 ] && grep -q 'ACTION: readonly variable' "$CHILD_OUT" &&
    ! grep -E -q -- '--check for|registered input|PASS|FAIL' "$CHILD_OUT" || {
    echo "a config assigning ACTION=run: exit $CHILD_RC, $(tr '\n' '/' <"$CHILD_OUT" | cut -c1-300)"
    return 1
  }
  check_child "$b"
  all_gates_reported "$CHILD_OUT" >/dev/null && grep -F -q "lock path $LOCK;" "$CHILD_OUT" &&
    [ ! -e "$ST/hijacked.lock" ] || {
    echo "a config assigning LOCK, HELD, FAILS, SKIPS, BUSY and CHECK_GATES: exit $CHILD_RC, $(tail -2 "$CHILD_OUT" | tr '\n' '/')"
    return 1
  }
  calls_clean || return 1
  after=$(state_now)
  [ "$before" = "$after" ] || {
    echo "state changed: before [$before] after [$after]"
    return 1
  }
  echo "a config assigning ACTION=run is refused (exit 78, 'ACTION: readonly variable') before any gate; one assigning LOCK, HELD, FAILS, SKIPS, BUSY and CHECK_GATES changes none of them: --check (exit $CHILD_RC) reports every gate and the real lock path"
}
t_check() { # --check in a child, under the shims: the lock and the series files untouched
  local before after n_pass n_fail n_skip
  [ -n "$LOCK" ] || {
    echo "no lock path: WORKTREE has no git common dir"
    return 1
  }
  make_shims
  before=$(state_now)
  check_child "$CONFIG"
  after=$(state_now)
  [ "$before" = "$after" ] || {
    echo "state changed: before [$before] after [$after]"
    return 1
  }
  calls_clean || return 1
  if pgrep -f "transitions[.]mjs run --exp $ROUND" >/dev/null; then
    echo "a transitions.mjs run for $ROUND is running"
    return 1
  fi
  all_gates_reported "$CHILD_OUT" || return 1
  cp "$CHILD_OUT" "$ST/check.out"
  n_pass=$(grep -c '^PASS  ' "$CHILD_OUT")
  n_fail=$(grep -c '^FAIL  ' "$CHILD_OUT")
  n_skip=$(grep -c '^SKIP  ' "$CHILD_OUT")
  echo "--check (exit $CHILD_RC) reported all $((n_pass + n_fail + n_skip)) gates: $n_pass PASS, $n_fail FAIL, $n_skip SKIP; of its $(grep -c -E '^(mkdir|rmdir|rm|node|caffeinate|git) ' "$CALLS") logged calls none names the series lock, starts transitions.mjs, or is caffeinate; the series lock ($(snap "$LOCK" | cut -d' ' -f2-)), bench, runs file, power log, samples, mode file and pair logs are as they were"
}

# A queued run, as a child process in run mode against a scratch Git repo whose series
# lock is a scratch path. Its config fails the protocol and candidate gates on purpose, so
# it can never reach a pair; its builds' metab runs through logging shims.
queued_repo() { # queued_repo REPO: a scratch repo with an ignored attic/
  rm -rf "$1" && mkdir -p "$1" && git init -q --template= "$1" && printf 'attic/\n' >"$1/.gitignore"
}
queued_config() { # queued_config REPO: the config, moved to REPO
  cat "$CONFIG"
  printf '%s\n' "WORKTREE='$1'" "OUT='$1/attic/queued'" \
    "PROTOCOL=explorations/performance-loop/experiments/paced-series-self-test-no-protocol.txt" \
    "CANDIDATE_HEAD=0000000000000000000000000000000000000000" \
    "LOAD_FILTER='$LOAD_FILTER'" "COUNT='$COUNT'" \
    "CONTROL_METAB='$SHIMS/metab-control'" "CANDIDATE_METAB='$SHIMS/metab-candidate'" \
    "CAFFEINATE=0" "QUIET_SECONDS=10" "MAX_LOAD=100000" "LOCK_WAIT_HOURS=1"
}
queued_setup() { # queued_setup REPO: shims, the repo, and its lock path in QLOCK
  make_shims
  shim_one metab-control "$CONTROL_METAB"
  shim_one metab-candidate "$CANDIDATE_METAB"
  scratch_ok "$1" && queued_repo "$1" || {
    echo "no scratch repo at $1"
    return 1
  }
  QLOCK=$(git -C "$1" rev-parse --path-format=absolute --git-common-dir)/metabrowser-series.lock
  scratch_ok "$QLOCK" || {
    echo "the scratch repo's lock $QLOCK is not a scratch path"
    return 1
  }
}
stop_child() { # stop_child PID: TERM the driver and its sleep, so its trap runs now
  kill -TERM "$1" 2>/dev/null
  pkill -TERM -P "$1" 2>/dev/null
  wait "$1" 2>/dev/null
}
heavy_calls() { grep -E '^(git .*status|node |metab-)' "$CALLS"; }
n_calls() { grep -c -E '^(mkdir|rmdir|rm|node|caffeinate|git|metab-[a-z]+) ' "$CALLS"; }
t_queued() { # queued behind a held lock: light gates only, no heavy work, the lock left alone
  local repo=$ST/queued-repo cfg=$ST/queued.env out=$ST/queued.out child i rc before after g ran=""
  queued_setup "$repo" || return 1
  mkdir "$QLOCK" && printf 'pid %s: queued-run fixture\n' "$$" >"$QLOCK/owner"
  queued_config "$repo" >"$cfg"
  before=$(state_now && snap "$QLOCK")
  : >"$CALLS"
  PATH="$SHIMS:$PATH" "$BASH" "$SELF" --config "$cfg" >"$out" 2>&1 &
  child=$!
  for i in $(seq 1 30); do
    grep -q 'waiting behind the lock' "$out" && break
    kill -0 "$child" 2>/dev/null || break
    sleep 1
  done
  sleep 1
  stop_child "$child"
  rc=$?
  after=$(state_now && snap "$QLOCK")
  grep -F -q "waiting behind the lock: pid $$: queued-run fixture" "$out" || {
    echo "the run never waited behind the fixture lock (exit $rc): $(tr '\n' '/' <"$out" | cut -c1-400)"
    return 1
  }
  for g in protocol control candidate harness corpus; do
    grep -E -q "^(PASS|FAIL|SKIP)  $g: " "$out" && ran="$ran, $g"
  done
  [ -z "$ran" ] || {
    echo "a heavy gate ran while queued: ${ran#, }"
    return 1
  }
  for g in config "fresh state" power; do
    grep -E -q "^PASS  $g: " "$out" || {
      echo "the light gate '$g' did not pass: $(grep -E '^(PASS|FAIL)' "$out" | cut -c1-80 | tr '\n' '/')"
      return 1
    }
  done
  if heavy_calls >/dev/null; then
    echo "heavy work while queued: $(heavy_calls | head -3 | tr '\n' ' ')"
    return 1
  fi
  calls_clean || return 1
  ! grep -q 'lock taken' "$out" && [ ! -e "$repo/attic/queued/$ROUND-power-samples.log" ] || {
    echo "the queued run took a lock or started sampling"
    return 1
  }
  [ "$before" = "$after" ] || {
    echo "state changed: before [$before] after [$after]"
    return 1
  }
  grep -q 'driver exits 143' "$out" || {
    echo "TERM did not stop the queued run through its trap (exit $rc)"
    return 1
  }
  rm -rf "$repo"
  echo "a run queued behind a fixture lock with a live owner passed config, fresh state and power and waited; it ran no protocol, build, harness or corpus gate, and none of its $(n_calls) logged calls is git status, node or metab; the fixture lock, the series lock and the series files are as they were; TERM stopped it through its trap (exit $rc)"
}
t_queued_release() { # the lock free: heavy gates under the lock, a failure, the lock released
  local repo=$ST/release-repo cfg=$ST/release.env out=$ST/release.out child i rc before after lt lp
  queued_setup "$repo" || return 1
  queued_config "$repo" >"$cfg"
  before=$(state_now)
  : >"$CALLS"
  PATH="$SHIMS:$PATH" "$BASH" "$SELF" --config "$cfg" >"$out" 2>&1 &
  child=$!
  for i in $(seq 1 120); do
    kill -0 "$child" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$child" 2>/dev/null; then
    stop_child "$child"
    echo "the run did not finish in 120 s: $(tail -3 "$out" | tr '\n' '/')"
    return 1
  fi
  wait "$child"
  rc=$?
  after=$(state_now)
  lt=$(grep -n 'lock taken' "$out" | head -1 | cut -d: -f1)
  lp=$(grep -n -E '^FAIL  protocol: ' "$out" | head -1 | cut -d: -f1)
  [ "$rc" = 4 ] && [ -n "$lt" ] && [ -n "$lp" ] && [ "$lt" -lt "$lp" ] && grep -q 'lock released' "$out" &&
    [ ! -e "$QLOCK" ] && [ ! -e "$repo/attic/queued/$ROUND-power-samples.log" ] || {
    echo "exit $rc; lock taken at line ${lt:-none}, protocol failed at line ${lp:-none}; scratch lock $([ -e "$QLOCK" ] && echo left || echo released): $(grep -E 'lock|FAIL|exits' "$out" | cut -c1-90 | tr '\n' '/')"
    return 1
  }
  heavy_calls >/dev/null || {
    echo "the gates under the lock made no heavy call, so this proves nothing"
    return 1
  }
  calls_clean || return 1
  [ "$before" = "$after" ] || {
    echo "state changed: before [$before] after [$after]"
    return 1
  }
  rm -rf "$repo"
  echo "with the scratch lock free, the run took it, then ran the protocol, build, harness and corpus gates; the protocol failed, so it exited 4 and its trap released the lock, with no pair, no samples, and the series lock and series files as they were"
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
  BUSY=$(busy_reason)
  log "paced-series.sh --self-test for $ROUND: fixtures under $ST; the series lock is only read"
  gate "lock mechanics" g_lock_selftest
  gate "lock reports" t_lock_reports
  gate "lock release" t_lock_release
  if [ -n "$BUSY" ]; then gate "stopping count" g_skipped; else gate "stopping count" t_count; fi
  gate "busy skip" t_busy
  gate "config isolation" t_config_isolation
  gate "queued run" t_queued
  if [ -n "$BUSY" ]; then gate "gates under the lock" g_skipped; else gate "gates under the lock" t_queued_release; fi
  gate "check leaves state" t_check
  [ -f "$ST/check.out" ] && sed 's/^/    /' "$ST/check.out"
  log "$FAILS self-test(s) failed, $SKIPS skipped; each --check's output and the call log are in $ST"
  verdict
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
# 0. Before the lock, only what --check checks while a series holds it: no git status,
#    metab or node, so a run queued behind another series' lock cannot disturb its pair.
fail=0
gate "config" g_config || fail=1
gate "fresh state" g_fresh || fail=1
gate "power" g_power || fail=1
[ "$fail" = 0 ] || {
  log "a registered input does not hold; nothing started, no lock taken"
  exit 4
}
mkdir -p "$OUT" "$PAIRLOGS"
if [ "$CAFFEINATE" = 1 ]; then
  caffeinate -i -w $$ &
  CAFF=$!
  log "caffeinate -i holds while pid $$ runs (caffeinate pid $CAFF)"
fi

# 1. The series lock, through the pacing gate: free, no transitions.mjs run in progress,
#    and the one-minute load under MAX_LOAD for QUIET_SECONDS. A lock that is stale or has
#    no owner file is reported, never removed. Operational stop: not taken in
#    LOCK_WAIT_HOURS.
deadline=$(($(date +%s) + LOCK_WAIT_HOURS * 3600))
said=""
while :; do
  [ "$(date +%s)" -gt "$deadline" ] && {
    log "lock not taken in $LOCK_WAIT_HOURS h; stopping"
    exit 3
  }
  if [ -e "$LOCK" ]; then
    pid=$(owner_pid "$LOCK")
    if [ -z "$pid" ]; then
      [ "$said" = ownerless ] || log "the lock has no owner pid: being taken this instant, or abandoned; waiting, not removing it"
      said=ownerless
    elif ! kill -0 "$pid" 2>/dev/null; then
      [ "$said" = "stale $pid" ] || log "the lock looks STALE (pid $pid is not running): $(owner_line "$LOCK"); waiting, not removing it"
      said="stale $pid"
    else
      [ "$said" = "held $pid" ] || log "waiting behind the lock: $(owner_line "$LOCK")"
      said="held $pid"
    fi
    sleep 30
    continue
  fi
  said=""
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
# 1b. The gates that run git status, metab or node, now that no other series is timing a
#     pair. A failure exits 4, and the exit trap releases the lock; nothing was timed.
fail=0
gate "protocol" g_protocol || fail=1
gate "control" g_build "$CONTROL_WT" "$CONTROL_HEAD" "$CONTROL_METAB" "$CONTROL_VERSION" || fail=1
gate "candidate" g_build "$CANDIDATE_WT" "$CANDIDATE_HEAD" "$CANDIDATE_METAB" "$CANDIDATE_VERSION" || fail=1
gate "harness" g_harness || fail=1
gate "corpus" g_corpus "$CORPUS_EXPECT" || fail=1
gate "fresh state" g_fresh || fail=1
[ "$fail" = 0 ] || {
  log "a registered input does not hold under the lock; nothing timed; the exit trap releases the lock"
  exit 4
}
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
  # exp-079's power rule gives a pair with an unreadable reading no mode, so it is
  # excluded: such a pair is not run, only recorded. The judged mode needs a reading.
  if [ -z "$l0" ] || [ -z "$s0" ]; then
    if [ -z "$MODE" ]; then
      log "lowpowermode '$l0', source '$s0': power is unreadable before the first attempt, so the judged mode cannot be read; stopping"
      exit 7
    fi
    t0=$(iso)
    power_line "$attempt" "" "" "$l0" "" "$s0" "" "$corpus" "$load0" "" "$t0" "$t0" "" \
      "power unreadable before the pair; not run" >>"$POWER"
    log "attempt $attempt not run: lowpowermode '$l0', source '$s0' unreadable before it; recorded as excluded"
    continue
  fi
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
  power_line "$attempt" "${series:-}" "${first%%=*}" "$l0" "$l1" "$s0" "$s1" "$corpus" "$load0" "$load_end" "$t0" "$t1" "$rc" >>"$POWER"
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
    --load-filter "$LOAD_FILTER" ${EXCLUDE_MAX_LOAD:+--max-load "$EXCLUDE_MAX_LOAD"} 2>&1); then
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
if [ "$judged" -ge "$TARGET" ]; then
  log "series done: $judged judged pair(s) in $attempt attempt(s); judged mode $MODE"
  exit 0
fi
log "attempts ran out: $judged judged pair(s) of $TARGET in $attempt attempt(s); judged mode ${MODE:-none}"
exit 5
