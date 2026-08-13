// Shared, safe request error classification for browser surfaces.

(() => {
  class RequestError extends Error {
    /**
     * @param {string} message
     * @param {{status?: number, operation?: string, cause?: unknown}} [options]
     */
    constructor(message, options = {}) {
      super(message, options.cause === undefined ? undefined : { cause: options.cause });
      this.name = "RequestError";
      this.status = options.status ?? 0;
      this.operation = options.operation ?? "request";
    }
  }

  /** @param {unknown} error */
  function isAbortError(error) {
    return Boolean(
      error &&
        typeof error === "object" &&
        "name" in error &&
        /** @type {{name?: unknown}} */ (error).name === "AbortError",
    );
  }

  /** @param {unknown} error */
  function classifyRequestError(error) {
    const status = error instanceof RequestError ? error.status : 0;
    const retryable =
      status === 0 || status === 408 || status === 425 || status === 429 || status >= 500;
    return Object.freeze({
      message:
        error instanceof RequestError ? error.message : "The request could not be completed.",
      retryable,
    });
  }

  window.MetabrowserRequestErrors = Object.freeze({
    RequestError,
    classifyRequestError,
    isAbortError,
  });
})();
