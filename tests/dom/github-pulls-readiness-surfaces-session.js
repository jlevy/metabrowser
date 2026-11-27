// Each Pulls row's and stack member's readiness on the surfaces that draw it, in the
// browserless readiness session: github-pulls-readiness-session.js, run whole, prints this
// part alone, the production Pulls panel, the stack menu, and every kind of surface drawing
// one pull request at once, for cli-ui-github-pulls-readiness.tryscript.md. It is a command
// of its own because the session whole is larger than the regular expression tryscript's
// matcher compiles, as github-pull-readiness-session.js is the page session's.

process.argv.push("--part", "surfaces");
require("./github-pulls-readiness-session.js");
