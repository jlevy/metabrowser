// Browserless session: hiding the navigation pane, on the production code.
//
// `\` and Shift-\ through the shortcut registry, the shell keymap
// (static/shell-keymap.js), and static/nav-collapse.js, on the key reveal session's
// stand-in shell: the `nav` part of tests/dom/key-reveal-session.js, which builds that
// shell, run as a session of its own. cli-ui-nav-collapse.tryscript.md pins it.

const { main } = require("./key-reveal-session.js");

main("nav").catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
