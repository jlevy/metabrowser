// The words the GitHub plugin's three surfaces share when GitHub holds or refuses a
// request: the Pulls tab, a pull request's page, and a row's changed-files tree. One
// wording each, so a reader meets the same sentence wherever the same thing happened.
// Pure, with no DOM, so the sessions pin it.

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
 * What a refresh that ended with an outcome none of a surface's own table words says, from
 * the job's own message when it left one, as a clause the surface makes a sentence of. Never the outcome's internal code.
 *
 * @param {string | null} message
 * @returns {string}
 */
export function outcomeFallback(message) {
  return message ?? "it did not complete";
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
 * A refresh the server refused, in its own words when it gave them.
 *
 * @param {string} what The refresh asked for, "The refresh".
 * @param {string | null} said The server's reason, or null when it gave none.
 * @returns {string}
 */
export function refreshRefusedText(what, said) {
  return said === null ? `${what} could not be started.` : `${what} was refused (${said}).`;
}
