// Lean 4 for Highlight.js: a rule-for-rule port of the official Lean 4 grammar.
//
// Upstream is `vscode-lean4/syntaxes/lean4.json` in github.com/leanprover/vscode-lean4,
// the grammar VS Code, GitHub's linguist ("Lean 4", tm_scope source.lean4), and Shiki
// use. It is Apache-2.0 licensed (lean.license.txt beside this file); the copy this port
// follows is pinned in tests/fixtures/vscode-lean4/, and tests/test_lean_grammar.py
// holds the constants below to that copy, so refreshing the fixture fails until this
// file follows it.
//
// Every upstream `match`, `begin`, and `end` is one constant below, copied verbatim. A
// constant no rule reads is an unused variable, which the Biome lint refuses. What
// differs between Oniguruma under TextMate and a JavaScript regex under Highlight.js is
// in ADAPTATIONS, applied when a constant is compiled; tests/test_lean_grammar.py has a
// behaviour case for each entry. Three differences are not regex changes:
//
// - The Markdown grammar upstream embeds in comments is not ported, so a comment is one
//   comment.
// - TextMate scopes map to the standard Highlight.js scopes. `sorry` and `admit`, which
//   upstream marks invalid.illegal because they leave a proof unfinished, keep the
//   `sorry` scope Lean's earlier Highlight.js grammar gave them. Upstream's rule also
//   names `#exit`, between two `\b`, so it matches only after a word character
//   (`foo#exit`) and never the command at the start of a line; the port keeps that.
// - Highlight.js tries a rule's contents before its `end`, the reverse of TextMate;
//   unlessEnd restores TextMate's order where the two can meet.

(() => {
  /** @typedef {Record<string, unknown>} HljsMode */

  const dashCommentBegin = String.raw`--`;
  const dashCommentEnd = String.raw`$`;
  const docCommentBegin = String.raw`/--`;
  const modDocCommentBegin = String.raw`/-!`;
  const blockCommentBegin = String.raw`/-`;
  const commentEnd = String.raw`-/`;
  const sortKeywords = String.raw`\b(Prop|Type|Sort)\b`;
  const attributeCommand = String.raw`\b(attribute\b\s*)(?:(\[[^\]\s]*\])|\[([^\]\s]*))`;
  const attributeAt = String.raw`(@)(?:(\[[^\]\s]*\])|\[([^\]\s]*))`;
  const modifiers = String.raw`\b(?<!\.)(local|scoped|partial|unsafe|nonrec|public|private|protected|noncomputable|meta)(?!\.)\b`;
  const unfinished = String.raw`\b(sorry|admit|#exit)\b`;
  const hashCommands = String.raw`#(print|eval|eval!|reduce|synth|widget|where|version|with_exporting|check|check_tactic|check_tactic_failure|check_failure|check_simp|discr_tree_key|discr_tree_simp_key|guard|guard_expr|guard_msgs)\b`;
  const derivingInstance = String.raw`\bderiving\s+instance\b`;
  const definitionBegin = String.raw`\b(?<!\.)(inductive|coinductive|structure|theorem|axiom|abbrev|lemma|def|instance|class)\b\s+(\{[^}]*\})?`;
  const definitionEnd = String.raw`(?=\bwith\b|\bextends\b|\bwhere\b|[:\|\(\[\{⦃<>])`;
  const definitionName = String.raw`\b[^:«»\(\)\{\}[:space:]=→λ∀?][^:«»\(\)\{\}[:space:]]*`;
  const definitionComma = String.raw`,`;
  const keywords = String.raw`\b(?<!\.)(theorem|show|have|using|haveI|from|suffices|nomatch|nofun|no_index|def|class|structure|instance|elab|set_option|initialize|builtin_initialize|example|inductive_fixpoint|inductive|coinductive_fixpoint|coinductive|termination_by\?|termination_by|decreasing_by|partial_fixpoint|axiom|universe|variable|module|import all|import|open|export|prelude|renaming|hiding|do|by\?|by|let|letI|let_expr|extends|mutual|mut|where|rec|declare_syntax_cat|syntax|macro_rules|macro|binop_lazy%|binop%|unop%|binrel_no_prop%|binrel%|leftact%|rightact%|max_prec|leading_parser|elab_rules|deriving|fun|section|namespace|end|prefix|postfix|infixl|infixr|infix|notation|abbrev|if|bif|then|else|calc|matches|match_expr|match|with|forall|for|while|repeat|unless|until|panic!|unreachable!|assert!|try|catch|finally|return|continue|break|exists|mod_cast|exact\?%|include_str|include|in|trailing_parser|tactic_tag|tactic_alt|tactic_extension|register_tactic_tag|type_of%|binder_predicate|grind_propagator|builtin_grind_propagator|grind_pattern|simproc|builtin_simproc|simproc_pattern%|builtin_simproc_pattern%|simproc_decl|builtin_simproc_decl|dsimproc|builtin_dsimproc|dsimproc_decl|builtin_dsimproc_decl|show_panel_widgets|show_term|seal|unseal|nat_lit|norm_cast_add_elim|println!|private_decl%|declare_config_elab|decl_name%|register_error_explanation|register_builtin_option|register_option|register_parser_alias|register_simp_attr|register_linter_set|register_label_attr|recommended_spelling|reportIssue!|reprove|run_elab|run_cmd|run_meta|value_of%|add_decl_doc|omit|opaque|json%|dbg_trace|trace_goal\[[^\]\s]*\]|trace\[[^\]\s]*\]|throwErrorAt|throwError|throwNamedErrorAt|throwNamedError|logNamedWarningAt|logNamedWarning|logNamedErrorAt|logNamedError)(?!\.)\b`;
  const guillemetBegin = String.raw`«`;
  const guillemetEnd = String.raw`»`;
  const interpolatedBegin = String.raw`(s!|m!|throwError|dbg_trace|panic!|reportIssue!|(?:trace_goal|trace)\[[^\]\s]*\])\s*"`;
  const interpolationBegin = String.raw`(\{)`;
  const interpolationEnd = String.raw`(\})`;
  const stringQuote = String.raw`"`;
  const escapeSimple = String.raw`\\[\\"ntr']`;
  const escapeHex = String.raw`\\x[0-9A-Fa-f][0-9A-Fa-f]`;
  const escapeUnicode = String.raw`\\u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]`;
  const booleans = String.raw`\b(true|false)\b`;
  const character = String.raw`(?<!\]|\w)'[^\\']'`;
  const characterEscape = String.raw`(?<!\]|\w)'(\\(x[0-9A-Fa-f][0-9A-Fa-f]|u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]|.))'`;
  const numbers = String.raw`\b([0-9]+|0([xX][0-9a-fA-F]+)|[-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?)\b`;

  // Oniguruma's `\w` on UTF-8 text: General_Category Letter, Mark, Decimal_Number, or
  // Connector_Punctuation (oniguruma doc/RE, "Character Property"). `\b` is the edge
  // between such a character and any other.
  const WORD = "[\\p{Letter}\\p{Mark}\\p{Decimal_Number}\\p{Connector_Punctuation}]";
  const WORD_EDGE = `(?:(?<=${WORD})(?!${WORD})|(?<!${WORD})(?=${WORD}))`;

  // The longest run an upstream `[^…]*` may scan for its closing bracket. Upstream's
  // scans are unbounded: TextMate gives a regex one line, and VS Code stops tokenizing
  // a long line. Highlight.js gives a regex the whole file, so an opener with no closer
  // rescans the rest of the file at every occurrence. Measured on a file of
  // SYNTAX_HIGHLIGHT_MAX_BYTES (settings.py) made of one repeated unit, unbounded in
  // Node 24 and then at this limit in Chrome 158: `def { ` 22.1 s and 417 ms,
  // `def { x\n` 12.7 s and 173 ms, `trace[` 55.1 s and 101 ms, `trace_goal[` 29.0 s and
  // 60 ms, beside 136 ms for ordinary Lean of that size. The `trace[` cost is linear in
  // the limit (41 ms at 64, 476 ms at 1024, in Node). A real binder or trace class is a
  // few tens of characters; a longer one stays plain.
  const SCAN_LIMIT = 256;

  /**
   * Each entry rewrites the source of an upstream regex for one difference between
   * Oniguruma under TextMate and JavaScript under Highlight.js.
   * @type {Readonly<Record<string, (source: string) => string>>}
   */
  const ADAPTATIONS = Object.freeze({
    // A JavaScript character class reads POSIX `[:space:]` as the letters of the word.
    posixSpace: (source) => source.replaceAll("[:space:]", String.raw`\s`),
    // TextMate matches one line at a time, so a definition's `{…}` binder closes on its
    // own line or is not a binder.
    lineScopedBinder: (source) => source.replaceAll("[^}]", String.raw`[^}\n]`),
    // See SCAN_LIMIT. These are the scans upstream ends with a required closing bracket.
    boundedScan: (source) =>
      ["[^}]", String.raw`[^}\n]`, String.raw`[^\]\s]`].reduce(
        (bounded, scan) => bounded.replaceAll(`${scan}*`, `${scan}{0,${SCAN_LIMIT}}`),
        source,
      ),
    // JavaScript's `\b` and `\w` are ASCII; Oniguruma's are Unicode, and Lean names are
    // full of Greek. Escapes are read in pairs, so `\\b` stays a backslash and a `b`.
    unicodeWord: (source) =>
      source.replace(/\\(.)/gsu, (pair, char) =>
        char === "b" ? WORD_EDGE : char === "w" ? WORD : pair,
      ),
  });

  /**
   * Compile an upstream regex, or a part of one, with every adaptation applied.
   * @param {string} source
   */
  const re = (source) =>
    new RegExp(
      Object.values(ADAPTATIONS).reduce((adapted, adapt) => adapt(adapted), source),
      "u",
    );

  /**
   * TextMate tries a rule's `end` before its patterns at a position; Highlight.js tries
   * the patterns first. Guarding a contained pattern with a lookahead of *end* restores
   * TextMate's order, so `structure Point where` ends at `where` as it does upstream.
   * @param {string} end
   * @param {string} pattern
   */
  const unlessEnd = (end, pattern) => re(`(?!${end})${pattern}`);

  /**
   * An upstream `begin` whose `beginCaptures` names capture 1 alone, as the two parts
   * Highlight.js needs to scope a capture: through the first capturing group, and the
   * rest. Highlight.js scopes a part of a `begin` only when the `begin` is an array.
   * @param {string} source
   * @returns {[RegExp, RegExp]}
   */
  function throughFirstCapture(source) {
    let depth = 0;
    let captureDepth = 0;
    let inClass = false;
    for (let index = 0; index < source.length; index += 1) {
      const char = source[index];
      if (char === "\\") {
        index += 1;
      } else if (inClass) {
        inClass = char !== "]";
      } else if (char === "[") {
        inClass = true;
      } else if (char === "(") {
        depth += 1;
        if (captureDepth === 0 && source[index + 1] !== "?") {
          captureDepth = depth;
        }
      } else if (char === ")") {
        if (depth === captureDepth) {
          const rest = source.slice(index + 1);
          if (rest === "") {
            break;
          }
          return [re(source.slice(0, index + 1)), re(rest)];
        }
        depth -= 1;
      }
    }
    throw new Error(`lean.js: no capturing group with a remainder in ${source}`);
  }

  /** @returns {HljsMode} */
  function lean4() {
    /** @type {HljsMode} */
    const blockComment = {
      scope: "comment",
      begin: re(blockCommentBegin),
      end: re(commentEnd),
      contains: ["self"],
    };
    const comments = [
      { scope: "comment", begin: re(dashCommentBegin), end: re(dashCommentEnd) },
      {
        scope: "comment",
        begin: re(docCommentBegin),
        end: re(commentEnd),
        contains: [blockComment],
      },
      {
        scope: "comment",
        begin: re(modDocCommentBegin),
        end: re(commentEnd),
        contains: [blockComment],
      },
      blockComment,
    ];
    const escapes = [escapeSimple, escapeHex, escapeUnicode].map((source) => ({
      scope: "char.escape",
      match: re(source),
    }));
    /** @type {HljsMode[]} */
    const top = [];
    /** @type {HljsMode} */
    const interpolation = {
      begin: re(interpolationBegin),
      end: re(interpolationEnd),
      beginScope: "keyword",
      endScope: "keyword",
      contains: top,
    };
    top.push(
      ...comments,
      { scope: "type", match: re(sortKeywords) },
      { scope: "meta", match: re(attributeCommand) },
      { scope: "meta", match: re(attributeAt) },
      { scope: "keyword", match: re(modifiers) },
      { scope: "sorry", match: re(unfinished) },
      { scope: "keyword", match: re(hashCommands) },
      { scope: "keyword", match: re(derivingInstance) },
      {
        begin: throughFirstCapture(definitionBegin),
        beginScope: { 1: "keyword" },
        end: re(definitionEnd),
        contains: [
          ...comments,
          { scope: "title.function", match: unlessEnd(definitionEnd, definitionName) },
          { scope: "title.function", begin: re(guillemetBegin), end: re(guillemetEnd) },
          { match: re(definitionComma) },
        ],
      },
      { scope: "keyword", match: re(keywords) },
      { begin: re(guillemetBegin), end: re(guillemetEnd) },
      {
        scope: "string",
        begin: throughFirstCapture(interpolatedBegin),
        beginScope: { 1: "keyword" },
        end: re(stringQuote),
        contains: [interpolation, ...escapes],
      },
      {
        scope: "string",
        begin: re(stringQuote),
        end: re(stringQuote),
        contains: escapes,
      },
      { scope: "literal", match: re(booleans) },
      { scope: "string", match: re(character) },
      { scope: "string", match: re(characterEscape) },
      { scope: "number", match: re(numbers) },
    );
    return { name: "Lean 4", aliases: ["lean4"], unicodeRegex: true, contains: top };
  }

  if (typeof hljs !== "undefined") {
    hljs.registerLanguage("lean", lean4);
  }
})();
