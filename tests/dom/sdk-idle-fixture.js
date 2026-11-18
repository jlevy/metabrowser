// metabrowser.whenIdle for a double of the SDK, on the session's own window timers.
//
// It does what a page did, before the helper, in an engine without requestIdleCallback
// (as these sessions are): timed work runs at its timeout, untimed work at once. So a
// session keeps the timing it pins. The helper itself runs against the production SDK in
// tests/dom/idle-work-behavior.js.
function whenIdle(callback, options) {
  if (options?.timeout === undefined) {
    callback();
    return () => {};
  }
  const timer = globalThis.window.setTimeout(callback, options.timeout);
  return () => globalThis.window.clearTimeout?.(timer);
}
module.exports = { whenIdle };
