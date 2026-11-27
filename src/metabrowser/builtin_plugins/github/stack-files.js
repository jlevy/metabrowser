// A native stack's combined changed files, for the tree under its Stack Overview row in the
// Pulls tab (mb-odt4): the files the stack's own page lists in its Diff summary, from the
// same two reads, so the two cannot differ.
//
// The stack's page reads `GET stack` for the stack's combined comparison and then that
// comparison through the diff view, and its Diff summary lists the comparison's files
// (stack-page.js, `showSummary`). `createStackFileList` makes the same two reads and answers
// them as a list of changed files in the envelope a pull request's `pull-files` route
// answers (pull-files-tree.js, `FileListSource`), so the Pulls tab's one tree controller and
// one paint draw a stack's files as they draw a pull request's: the same rows, folders, keys,
// loading line, and notices. The rows are the Diff summary's own, which the diff view makes
// of the comparison it read (`summaryRows` in builtin_plugins/diff/index.js), and the shared
// changed-files tree orders them, as it orders the Diff summary's.
//
// When it is read, and what it costs: nothing until a reader opens the Stack Overview row's
// files, as a pull request's list is read when its row opens. Then one `GET stack`, which
// runs no GitHub call and no fetch (pull_stack.py), and, once for each comparison, the
// comparison itself, at the address the stack's page asks, so the browser's cache and the
// document's keep of comparisons answer whichever of the two asks second. While the tree
// stays open the stack is read again once a freshness window, and a comparison already
// read is not read again.
//
// A stack whose members are not all fetched has no comparison yet (`pending`): the tree
// asks `pull-refresh` for each such member no fetch is running for, as the stack's page
// does, once a freshness window, and shows its loading line until the comparison is there.
// A member still pending two reads after its fetch ended is taken as failed, and the tree
// says the list could not be had, with Retry.
//
// Nothing here touches the DOM: tests/dom/github-pulls-stack-files-session.js runs it from
// the command line.

import { diffComparison, STACK_ROUTE } from "./stack-page.js";

const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
// How long a stack's list read whole is taken as fresh before the open tree reads the stack
// again: the pull routes' own freshness window (`FRESHNESS_WINDOW_S`, mirror_refresh.py),
// which a pull request's list answers in `fresh_for_s` and the `stack` route does not
// answer, so it is stated here, and tests/test_github_stack_design.py holds it to the
// server's value. A read is `GET stack`, cached parses and no Git once the comparison is
// listed (pull_stack.py, "What a read runs").
export const STACK_FILES_FRESH_S = 60;
// How many reads must find a member still pending, with no fetch of it running, after the
// server took the ask for it, before its fetch is taken as failed: the first may have been
// answered as the fetch ended and before its record was written, as the stack's page allows
// (stack-page.js, `asksAfterRead`).
const FAILED_AFTER_READS = 2;
// The outcome a stack with no combined comparison is listed with, which the tree words
// (pull-files-tree.js, `FILE_FAILURES`).
export const STACK_NOT_ONE_COMPARISON = "stack_not_one_comparison";

/**
 * @typedef {import("./stack-page.js").StackEnvelope} StackEnvelope
 * @typedef {import("./pull-files-tree.js").FilesEnvelope} FilesEnvelope
 * @typedef {import("./pull-files-tree.js").FileListSource} FileListSource
 */

/**
 * A stack's answer as far as the list reads it.
 *
 * @param {unknown} value
 * @returns {value is StackEnvelope}
 */
function isStackAnswer(value) {
  const answer = /** @type {Record<string, unknown> | null} */ (value);
  return (
    answer !== null &&
    typeof answer === "object" &&
    typeof answer.state === "string" &&
    Array.isArray(answer.members) &&
    typeof answer.truncated === "boolean"
  );
}

/**
 * A stack's answer as a list of changed files. Pure.
 *
 * *rows* are the files of the answer's comparison, or null while it has none or they are
 * not read; *offset* is the window asked for, which a list whose rows are held asks past
 * (`holdFileList`), so a read that changes nothing carries no rows. A stack with a
 * comparison is `current`, whole, and listed from it, under the comparison's key; one
 * waiting on its members is `pending`, `refreshing` while a member is fetched; one whose
 * member could not be fetched (*failed*), or that cannot be shown as one comparison, is
 * `absent`, its last refresh ended so, and the tree says which.
 *
 * @param {StackEnvelope} answer
 * @param {MetabrowserChangedFileRow[] | null} rows
 * @param {number} offset
 * @param {{failed?: boolean, at?: string}} [how]
 * @returns {FilesEnvelope}
 */
export function stackFilesEnvelope(answer, rows, offset, how = {}) {
  const comparison = answer.state === "current" ? answer.comparison : null;
  /** @type {FilesEnvelope} */
  const none = {
    state: "absent",
    reason: answer.reason,
    number: answer.number,
    source: null,
    generation: null,
    listed_from: null,
    fetched_at: answer.fetched_at,
    reader: null,
    head: null,
    base: null,
    fresh_for_s: STACK_FILES_FRESH_S,
    refreshing: false,
    last_refresh: null,
    fetched: 0,
    pages: 0,
    last_page: null,
    complete: false,
    capped: false,
    truncated: false,
    offset: 0,
    limit: 0,
    rows: [],
  };
  if (comparison !== null && rows !== null) {
    return {
      ...none,
      state: "current",
      reason: null,
      generation: comparison.key,
      listed_from: "comparison",
      head: comparison.right,
      base: comparison.left,
      fetched: rows.length,
      pages: 1,
      complete: true,
      truncated: answer.truncated,
      offset,
      limit: rows.length,
      rows: rows.slice(offset),
    };
  }
  /** @param {string} outcome */
  const ended = (outcome) => ({ outcome, message: null, reset_at: null, at: how.at ?? "" });
  if (answer.state === "absent") {
    // A stack that is one no longer, or cannot be shown as one comparison, has no list a
    // wait would bring: the tree says so at once, with Retry, where a server that serves
    // no GitHub repository keeps its own words (`not_github`).
    return answer.reason === "not_github"
      ? none
      : { ...none, last_refresh: ended(STACK_NOT_ONE_COMPARISON) };
  }
  if (how.failed === true) {
    return { ...none, reason: null, last_refresh: ended("failed") };
  }
  return {
    ...none,
    state: "pending",
    reason: null,
    refreshing: answer.members.some((member) => member.fetching === true),
  };
}

/**
 * One stack's list of changed files, read as its page reads them.
 *
 * `request` is the panel's; `rows` reads a comparison's files, the Diff summary's rows of it,
 * or null where they cannot be had, which the panel answers through the diff view; `now`
 * says when a failure was found.
 *
 * @param {{
 *   request(
 *     method: "GET" | "POST",
 *     route: string,
 *     options: {body?: unknown, signal?: AbortSignal},
 *   ): Promise<{status: number, body: unknown}>,
 *   rows(
 *     comparison: ReturnType<typeof diffComparison>,
 *     signal: AbortSignal,
 *   ): Promise<MetabrowserChangedFileRow[] | null>,
 *   now(): number,
 * }} deps
 * @param {number} stack
 * @param {string} label What the tree is called, before its count.
 * @returns {FileListSource}
 */
export function createStackFileList(deps, stack, label) {
  /** The comparison whose files are held. @type {{key: string, rows: MetabrowserChangedFileRow[]} | null} */
  let held = null;
  /** The stack's last answer, which a refresh asks about. @type {StackEnvelope | null} */
  let last = null;
  /** Each member asked for, by number: how many reads since found its fetch ended with the
   * member still pending. @type {Map<number, number>} */
  const asked = new Map();

  /** The members a refresh asks for: pending, with no fetch running. @param {StackEnvelope} answer */
  const waiting = (answer) =>
    answer.members.filter((member) => member.pending && member.fetching !== true);

  /** @param {StackEnvelope} answer */
  function noteEnded(answer) {
    const ended = new Set(waiting(answer).map((member) => member.number));
    for (const [number, reads] of asked) {
      if (ended.has(number)) {
        asked.set(number, reads + 1);
      } else if (!answer.members.some((member) => member.number === number && member.pending)) {
        asked.delete(number);
      }
    }
  }

  const failed = () => [...asked.values()].some((reads) => reads >= FAILED_AFTER_READS);
  const at = () => new Date(deps.now()).toISOString();

  return {
    label,
    async read(query, signal) {
      const answer = await deps.request("GET", `${STACK_ROUTE}?number=${stack}`, { signal });
      if (answer.status !== 200 || !isStackAnswer(answer.body)) {
        return { status: answer.status === 200 ? 502 : answer.status, body: null };
      }
      last = answer.body;
      noteEnded(last);
      const comparison = last.state === "current" ? last.comparison : null;
      if (comparison === null) {
        held = null;
      } else if (held?.key !== comparison.key) {
        const rows = await deps.rows(diffComparison(comparison), signal);
        if (rows === null) {
          return { status: 502, body: null };
        }
        held = { key: comparison.key, rows };
      }
      const offset = Number(/(?:^|&)offset=(\d+)$/.exec(query)?.[1] ?? 0);
      return {
        status: 200,
        body: stackFilesEnvelope(last, held?.rows ?? null, offset, { failed: failed(), at: at() }),
      };
    },
    async refresh(retry) {
      if (last === null) {
        return { status: 409, body: { code: null } };
      }
      if (retry) {
        asked.clear();
      }
      const members = waiting(last).filter((member) => !asked.has(member.number));
      /** @type {string | null} */
      let refused = null;
      let taken = 0;
      for (const member of members) {
        const answer = await deps.request("POST", REFRESH_ROUTE, {
          body: { number: member.number, ...(retry ? { retry: true } : {}) },
        });
        if (answer.status === 202) {
          asked.set(member.number, 0);
          taken += 1;
        } else if (answer.status !== 200) {
          const code = /** @type {{code?: unknown} | null} */ (answer.body)?.code;
          refused ??= typeof code === "string" ? code : "";
        }
      }
      if (taken === 0 && refused !== null) {
        return { status: 503, body: { code: refused === "" ? null : refused } };
      }
      const files = stackFilesEnvelope(last, held?.rows ?? null, 0, { failed: failed(), at: at() });
      return {
        status: taken > 0 ? 202 : 200,
        body: {
          // A refresh's answer carries no rows; a fetch the server took is running.
          files: { ...files, rows: [], refreshing: files.refreshing || taken > 0 },
        },
      };
    },
  };
}
