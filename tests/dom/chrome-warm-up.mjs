// One Chrome start and close, made before a run's first Chrome test so that the runner's
// cold first start is paid here, under its own bound, rather than inside a test's
// (tests/chrome_starts.py says why and sets the bound, BOUND_MS, in milliseconds).
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/chrome-warm-up.mjs BOUND_MS
import { launchChrome } from "./chrome-session.mjs";

const bound = Number(process.argv[2]);
const chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
  profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
  startBoundMs: bound,
  attempts: 1,
});
await chrome.close();
