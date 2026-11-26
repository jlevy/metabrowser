// The words the GitHub plugin's three surfaces share when GitHub holds or refuses a
// request: the Pulls tab, a pull request's page, and a row's changed-files tree. One
// wording each, so a reader meets the same sentence wherever the same thing happened.
// Pure, with no DOM, so the sessions pin it.
//
// Each sentence is fixed copy chosen by the outcome's code, never the server's own text
// (docs/design-system-messages.md): a job's message, which names its cause, stays in the
// route's `last_refresh.message` for `metab --api` and agents, and in the event log the
// page's Details reads.

/**
 * What a rate limit says to a reader. The time is the one the next attempt is made at; a
 * limit with no known end names none. It opens with "GitHub rate limit", whole, which the
 * pull request page's held note keeps visible when it must cut the rest
 * (`.github-pull-meta-lead-held` in styles.css).
 *
 * @param {string | null} when The time the next attempt is made at, already formatted.
 * @returns {string}
 */
export function rateLimitText(when) {
  return when === null
    ? "GitHub rate limit reached."
    : `GitHub rate limit reached. Next attempt after ${when}.`;
}

/**
 * What a refresh that ended with an outcome says, where every surface says it alike: one
 * sentence each, so a surface can follow it with one of its own. A missing or outdated
 * GitHub CLI is fixed from its download page, which the surface links beside the sentence
 * (`setupHelp`), so the sentence names no step; signing in has no page, so its sentence is
 * the step, which names github.com because `gh auth login` alone can sign in to another
 * host.
 *
 * @type {Readonly<Record<string, string>>}
 */
const REFRESH_FAILURES = Object.freeze({
  gh_missing: "GitHub CLI is not installed.",
  gh_too_old: "GitHub CLI needs an update.",
  not_logged_in: "Run gh auth login --hostname github.com to sign in to GitHub.",
  network_error: "Could not reach GitHub.",
  github_unavailable: "GitHub is temporarily unavailable.",
});

/**
 * What a refresh that ended with *outcome* says: the surface's own words for it, the
 * shared ones, or the surface's *fallback* for any outcome neither names. An outcome is the
 * server's text, so only a table's own entries answer it.
 *
 * @param {string} outcome The `last_refresh.outcome`, never "succeeded" or "rate_limited".
 * @param {Readonly<Record<string, string>>} own The surface's words for the outcomes it
 *   says in its own terms, as `not_found_or_private` names what could not be found.
 * @param {string} fallback The surface's sentence for every other outcome.
 * @returns {string}
 */
export function refreshFailureText(outcome, own, fallback) {
  if (Object.hasOwn(own, outcome)) {
    return own[outcome];
  }
  return Object.hasOwn(REFRESH_FAILURES, outcome) ? REFRESH_FAILURES[outcome] : fallback;
}

/**
 * The link that fixes a refresh's *outcome*, beside its sentence: GitHub CLI's download page
 * to install it or to update it, or none.
 *
 * @param {string} outcome
 * @returns {"install" | "update" | undefined}
 */
export function setupHelp(outcome) {
  return outcome === "gh_missing" ? "install" : outcome === "gh_too_old" ? "update" : undefined;
}

/**
 * A read the server did not answer with what was asked for: said as what could not be done.
 * The status stays out of the sentence; it is not something a reader can act on.
 *
 * @param {string} what The thing asked for, "The list of files".
 * @returns {string}
 */
export function unavailableText(what) {
  return `${what} could not be loaded.`;
}

/**
 * A refresh the server refused, from the answer's `code`: one sentence, which a surface may
 * follow with its own. A refusal because too many pull requests are already being fetched
 * (`too_many`) says so, since asking again once one finishes works, which the surface's own
 * Refresh, Reload, or Retry does; the server's own `error` stays in its answer.
 *
 * @param {string} what The refresh asked for, "The refresh".
 * @param {string | null} code The answer's `code`, or null when it gave none.
 * @returns {string}
 */
export function refreshRefusedText(what, code) {
  return code === "too_many"
    ? `${what} could not start while other pull requests are being fetched.`
    : `${what} could not be started.`;
}
