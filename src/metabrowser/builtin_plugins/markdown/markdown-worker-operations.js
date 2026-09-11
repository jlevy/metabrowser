/** @typedef {"prepare-primary" | "prepare-transclusion"} MarkdownWorkerOperation */

/**
 * Dispatch one pure Markdown operation. Imports stay operation-local so the worker
 * evaluates only the parser needed by its first request.
 *
 * @param {MarkdownWorkerOperation} op
 * @param {unknown} payload
 */
export async function runMarkdownOperation(op, payload) {
  if (!payload || typeof payload !== "object") {
    throw new TypeError("Markdown worker operation requires a payload");
  }
  const value = /** @type {Record<string, unknown>} */ (payload);
  if (typeof value.source !== "string") {
    throw new TypeError("Markdown worker operation requires source text");
  }
  const { preparePrimaryMarkdownSource, prepareTransclusionMarkdownSource } = await import(
    "./wiki-parser.js"
  );
  if (op === "prepare-primary") {
    return preparePrimaryMarkdownSource(value.source);
  }
  if (op === "prepare-transclusion") {
    if (value.fragment !== undefined && typeof value.fragment !== "string") {
      throw new TypeError("Markdown transclusion fragment must be a string");
    }
    return prepareTransclusionMarkdownSource(value.source, value.fragment);
  }
  throw new TypeError("Unknown Markdown worker operation");
}
