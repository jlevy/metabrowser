// The mounted panel's selection story uses the real page host and history protocol.
// Keep a no-argument command for the functional-aspect registry, as the second part does.
process.argv.push("--part", "selection");
require("./github-pulls-panel-session.js");
