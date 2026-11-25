// Every string a shipped browser script could show a reader, for tests/test_reader_messages.py.
//
//   node tests/dom/reader-message-literals.mjs <file.js>...
//
// Parses each file with the TypeScript compiler's own parser, which tells a regular
// expression from a division and a template's text from its expressions, and prints one
// JSON array of records:
//
//   {file, line, kind, text, expressions, context, functions, callee, caught}
//
// kind is "string" or "template". text is the literal's own characters; a template's
// expressions are joined into it as `${…}`, and their source is in expressions. context
// says where the literal sits, because a literal no reader sees is not a message:
//
//   "console"  an argument of a console.* call, which only a developer reads
//   "thrown"   an argument of `new Error(...)` or another built-in error, which reaches a
//              reader only through a read of its `.message`, which the check sees
//   "module"   an import, export, or dynamic import specifier
//   "key"      a property name, or the key of an element access
//   "compare"  an operand of ===, !==, ==, !=, or `in`, or a switch case
//   "text"     anything else: a value the code may set into the page
//
// functions names the functions around the literal, innermost first, so the check can tell
// a notice's builder; callee is the call the literal is the first argument of, such as
// `element` in `element("ul")`.
//
// It also prints a record of kind "access" for each read of `.message` or `.stack` off a
// value, and of kind "stringified" for each `String(x)`, with the source as its text;
// caught is true when x is a catch clause's binding or a `.catch()` callback's parameter,
// so the check can tell an exception's own text from a server's answer. It prints a record
// of kind "caught-value" for each such binding written into text as it is: a template's
// expression, an operand of `+`, or the value assigned to a property, as
// `note.textContent = error` writes it. And it prints a record of kind "call" for each call
// of a function named `shortCommit`, which names a commit by its ID.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const COMPARISON = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
  ts.SyntaxKind.InKeyword,
]);

const BUILT_IN_ERRORS = new Set([
  "Error",
  "TypeError",
  "RangeError",
  "SyntaxError",
  "ReferenceError",
  "DOMException",
]);

// The names a script reaches the global object by, so `global.console.warn(...)` is the
// console as `console.warn(...)` is.
const GLOBALS = new Set(["global", "globalThis", "window", "self"]);

/** @param {import("typescript").Node} node */
function isConsole(node) {
  if (ts.isIdentifier(node)) {
    return node.text === "console";
  }
  return (
    ts.isPropertyAccessExpression(node) &&
    node.name.text === "console" &&
    ts.isIdentifier(node.expression) &&
    GLOBALS.has(node.expression.text)
  );
}

/** @param {import("typescript").Node} node */
function isConsoleCall(node) {
  if (!ts.isCallExpression(node)) {
    return false;
  }
  const callee = node.expression;
  return ts.isPropertyAccessExpression(callee) && isConsole(callee.expression);
}

/**
 * Whether the identifier *node* is written into text as it is: a template's expression, an
 * operand of `+`, or the value assigned to a property.
 * @param {import("typescript").Node} node
 */
function isWrittenAsText(node) {
  const parent = node.parent;
  if (!parent) {
    return false;
  }
  if (ts.isTemplateSpan(parent) && parent.expression === node) {
    return true;
  }
  if (!ts.isBinaryExpression(parent)) {
    return false;
  }
  const operator = parent.operatorToken.kind;
  if (operator === ts.SyntaxKind.PlusToken) {
    return true;
  }
  return (
    (operator === ts.SyntaxKind.EqualsToken || operator === ts.SyntaxKind.PlusEqualsToken) &&
    parent.right === node &&
    (ts.isPropertyAccessExpression(parent.left) || ts.isElementAccessExpression(parent.left))
  );
}

/**
 * Where a literal sits, from the nearest ancestor that decides it.
 * @param {import("typescript").Node} node
 */
function contextOf(node) {
  const parent = node.parent;
  if (
    parent &&
    (ts.isImportDeclaration(parent) ||
      ts.isExportDeclaration(parent) ||
      ts.isExternalModuleReference(parent) ||
      (ts.isCallExpression(parent) && parent.expression.kind === ts.SyntaxKind.ImportKeyword))
  ) {
    return "module";
  }
  if (
    parent &&
    ((ts.isPropertyAssignment(parent) && parent.name === node) ||
      (ts.isElementAccessExpression(parent) && parent.argumentExpression === node) ||
      (ts.isMethodDeclaration(parent) && parent.name === node) ||
      (ts.isPropertyDeclaration(parent) && parent.name === node))
  ) {
    return "key";
  }
  if (
    parent &&
    ((ts.isBinaryExpression(parent) && COMPARISON.has(parent.operatorToken.kind)) ||
      ts.isCaseClause(parent))
  ) {
    return "compare";
  }
  for (let at = node.parent; at; at = at.parent) {
    if (isConsoleCall(at)) {
      return "console";
    }
    if (
      ts.isNewExpression(at) &&
      ts.isIdentifier(at.expression) &&
      BUILT_IN_ERRORS.has(at.expression.text)
    ) {
      return "thrown";
    }
    if (ts.isSourceFile(at)) {
      break;
    }
  }
  return "text";
}

/**
 * A function's name: its declaration's, or the variable, property, or method it is.
 * @param {import("typescript").Node} node
 */
function functionName(node) {
  if (node.name && ts.isIdentifier(node.name)) {
    return node.name.text;
  }
  const parent = node.parent;
  if (
    parent &&
    (ts.isVariableDeclaration(parent) || ts.isPropertyAssignment(parent)) &&
    ts.isIdentifier(parent.name)
  ) {
    return parent.name.text;
  }
  return "";
}

/** @param {import("typescript").Node} node */
function functionsAround(node) {
  const names = [];
  for (let at = node.parent; at; at = at.parent) {
    if (ts.isFunctionLike(at)) {
      const name = functionName(at);
      if (name) {
        names.push(name);
      }
    }
  }
  return names;
}

/**
 * Whether *name*, read at *node*, is bound to something thrown: a catch clause's
 * variable, or a parameter of a function passed to `.catch()` or as `.then()`'s second.
 * @param {import("typescript").Node} node
 * @param {string} name
 */
function isCaught(node, name) {
  for (let at = node.parent; at; at = at.parent) {
    if (ts.isCatchClause(at)) {
      const declared = at.variableDeclaration?.name;
      if (declared && ts.isIdentifier(declared) && declared.text === name) {
        return true;
      }
    }
    if (ts.isFunctionLike(at)) {
      const parameters = /** @type {any} */ (at).parameters ?? [];
      const bound = parameters.some(
        (/** @type {any} */ parameter) =>
          ts.isIdentifier(parameter.name) && parameter.name.text === name,
      );
      if (bound) {
        const call = at.parent;
        if (call && ts.isCallExpression(call) && ts.isPropertyAccessExpression(call.expression)) {
          const method = call.expression.name.text;
          return method === "catch" || (method === "then" && call.arguments[1] === at);
        }
        return false;
      }
    }
  }
  return false;
}

/** @param {import("typescript").Node} node */
function calleeOf(node) {
  const parent = node.parent;
  if (parent && ts.isCallExpression(parent) && parent.arguments[0] === node) {
    const callee = parent.expression;
    if (ts.isIdentifier(callee)) {
      return callee.text;
    }
    if (ts.isPropertyAccessExpression(callee)) {
      return callee.name.text;
    }
  }
  return "";
}

/**
 * @param {string} file
 * @param {object[]} records
 */
function collect(file, records) {
  const source = readFileSync(file, "utf8");
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const lineOf = (/** @type {import("typescript").Node} */ node) =>
    tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1;

  /** @param {import("typescript").Node} node */
  function visit(node) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      records.push({
        file,
        line: lineOf(node),
        kind: ts.isStringLiteral(node) ? "string" : "template",
        text: node.text,
        expressions: [],
        context: contextOf(node),
        functions: functionsAround(node),
        callee: calleeOf(node),
        caught: false,
      });
    } else if (ts.isTemplateExpression(node)) {
      const expressions = node.templateSpans.map((span) => span.expression.getText(tree));
      const text =
        node.head.text + node.templateSpans.map((span) => `\${…}${span.literal.text}`).join("");
      records.push({
        file,
        line: lineOf(node),
        kind: "template",
        text,
        expressions,
        context: contextOf(node),
        functions: functionsAround(node),
        callee: calleeOf(node),
        caught: false,
      });
    } else if (ts.isIdentifier(node) && isWrittenAsText(node) && isCaught(node, node.text)) {
      records.push({
        file,
        line: lineOf(node),
        kind: "caught-value",
        text: ts.isTemplateSpan(node.parent) ? `\${${node.text}}` : node.parent.getText(tree),
        expressions: [],
        context: contextOf(node),
        functions: functionsAround(node),
        callee: "",
        caught: true,
      });
    } else if (
      ts.isPropertyAccessExpression(node) &&
      (node.name.text === "message" || node.name.text === "stack")
    ) {
      records.push({
        file,
        line: lineOf(node),
        kind: "access",
        text: node.getText(tree),
        expressions: [],
        context: contextOf(node),
        functions: functionsAround(node),
        callee: "",
        caught: ts.isIdentifier(node.expression) && isCaught(node, node.expression.text),
      });
    } else if (ts.isCallExpression(node)) {
      const callee = node.expression;
      const name = ts.isIdentifier(callee)
        ? callee.text
        : ts.isPropertyAccessExpression(callee)
          ? callee.name.text
          : "";
      const [argument] = node.arguments;
      if (name === "String" && argument && ts.isIdentifier(argument)) {
        records.push({
          file,
          line: lineOf(node),
          kind: "stringified",
          text: node.getText(tree),
          expressions: [],
          context: contextOf(node),
          functions: functionsAround(node),
          callee: "",
          caught: isCaught(node, argument.text),
        });
      } else if (name === "shortCommit") {
        records.push({
          file,
          line: lineOf(node),
          kind: "call",
          text: node.getText(tree),
          expressions: [],
          context: contextOf(node),
          functions: functionsAround(node),
          callee: name,
          caught: false,
        });
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(tree);
}

const records = [];
for (const file of process.argv.slice(2)) {
  collect(file, records);
}
process.stdout.write(JSON.stringify(records));
