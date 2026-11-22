// What the agents home derives from the `catalog` and `live` routes before it paints.
//
// The routes own the data: totals, buckets, per-day counts, and progress. These functions
// only arrange it for display (a bar's height, a bucket's label, a progress sentence), and
// stay free of the DOM so a browserless session pins them
// (tests/dom/agents-views-session.js).

const SECONDS_PER_DAY = 86_400;

/**
 * The days the activity chart draws, ending on the day of `now`. The route reports the
 * newest days that have sessions, which may span years, so the chart shows a fixed
 * window instead of one that grows with the history. It is a layout choice, not a cost:
 * 90 bars is about 4 px each in the narrowest pane the home is laid out for.
 */
export const ACTIVITY_DAYS = 90;

/**
 * @typedef {{day: string, sessions: number}} DayCount
 * @typedef {{day: string, sessions: number, height: number}} DayBar
 */

/** @param {number} seconds @returns {string} The UTC day, as the route names one. */
function dayOf(seconds) {
  return new Date(seconds * 1000).toISOString().slice(0, 10);
}

/**
 * One bar per day for the last `ACTIVITY_DAYS`, oldest first, each as a fraction of the
 * busiest day shown. A day the route has no count for is a day with none.
 *
 * @param {ReadonlyArray<DayCount>} perDay
 * @param {number} now Unix seconds, the response's own clock.
 * @returns {{bars: ReadonlyArray<DayBar>, peak: number, total: number}}
 */
export function activityBars(perDay, now) {
  const counts = new Map(perDay.map((entry) => [entry.day, entry.sessions]));
  const last = Math.floor(now / SECONDS_PER_DAY) * SECONDS_PER_DAY;
  /** @type {Array<{day: string, sessions: number}>} */
  const days = [];
  for (let back = ACTIVITY_DAYS - 1; back >= 0; back -= 1) {
    const day = dayOf(last - back * SECONDS_PER_DAY);
    days.push({ day, sessions: counts.get(day) ?? 0 });
  }
  const peak = days.reduce((most, entry) => Math.max(most, entry.sessions), 0);
  const total = days.reduce((sum, entry) => sum + entry.sessions, 0);
  const bars = days.map((entry) => ({
    ...entry,
    height: peak === 0 ? 0 : entry.sessions / peak,
  }));
  return { bars, peak, total };
}

/**
 * @typedef {{lower: number, upper: number | null, count: number}} SizeBucket
 * @typedef {{label: string, count: number, height: number}} SizeBar
 */

/**
 * The size histogram's bars, from the first bucket with sessions to the last, each
 * labelled by the lower bound it starts at (the last, open one reads "and up").
 *
 * @param {ReadonlyArray<SizeBucket>} buckets
 * @param {(bytes: number) => string} formatSize
 * @returns {{bars: ReadonlyArray<SizeBar>, peak: number}}
 */
export function sizeBars(buckets, formatSize) {
  const filled = buckets
    .map((bucket, index) => (bucket.count > 0 ? index : -1))
    .filter((i) => i >= 0);
  if (filled.length === 0) {
    return { bars: [], peak: 0 };
  }
  const shown = buckets.slice(filled[0], filled[filled.length - 1] + 1);
  const peak = shown.reduce((most, bucket) => Math.max(most, bucket.count), 0);
  const bars = shown.map((bucket) => ({
    label:
      bucket.upper === null
        ? `${formatSize(bucket.lower)} and up`
        : bucket.lower === 0
          ? `under ${formatSize(bucket.upper)}`
          : `${formatSize(bucket.lower)} to ${formatSize(bucket.upper)}`,
    count: bucket.count,
    height: bucket.count / peak,
  }));
  return { bars, peak };
}

/**
 * @typedef {object} Progress
 * @property {string} state
 * @property {number} total
 * @property {number} summarized
 * @property {number} failed
 * @property {boolean} complete
 */

/**
 * The indexing phase and status text shared by the home, list, and session views.
 * `complete` is the route's own verdict, which the poll stops on.
 *
 * @param {Progress} progress
 * @param {(value: number) => string} formatInteger
 * @returns {{phase: "scanning" | "summarizing" | "complete" | "error", text: string}}
 */
export function progressView(progress, formatInteger) {
  if (progress.state === "error") {
    return { phase: "error", text: "Reading the sessions failed." };
  }
  if (progress.complete) {
    return {
      phase: "complete",
      text:
        progress.failed > 0
          ? `Session indexing finished. ${formatInteger(progress.failed)} could not be read.`
          : "Session details indexed.",
    };
  }
  if (progress.state === "scanning" && progress.total === 0) {
    return { phase: "scanning", text: "Looking for sessions…" };
  }
  const done = progress.summarized + progress.failed;
  return {
    phase: "summarizing",
    text:
      progress.total > 0
        ? `Indexing session details… ${formatInteger(done)} of ${formatInteger(progress.total)} checked.`
        : "Indexing session details…",
  };
}

/**
 * How long ago, in the one unit a reader wants: seconds under a minute, then minutes,
 * hours, and days.
 *
 * @param {number | null | undefined} then Unix seconds.
 * @param {number} now Unix seconds.
 * @returns {string}
 */
export function ageText(then, now) {
  if (then === null || then === undefined) {
    return "unknown";
  }
  const seconds = Math.max(0, Math.round(now - then));
  if (seconds < 5) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds} s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return `${hours} h ago`;
  }
  return `${Math.floor(hours / 24)} d ago`;
}

/**
 * A duration as a person reads one: "31 s", "4 min 12 s", "2 h 5 min".
 *
 * @param {number | null | undefined} seconds
 * @returns {string}
 */
export function durationText(seconds) {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  const whole = Math.round(seconds);
  if (whole < 60) {
    return `${whole} s`;
  }
  const minutes = Math.floor(whole / 60);
  if (minutes < 60) {
    return `${minutes} min ${whole % 60} s`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}
