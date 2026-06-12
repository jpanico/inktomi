"""Programming language identifiers for fenced code blocks.

Public symbols:

- :class:`CodeLanguage` — ``StrEnum`` of programming languages identified by a fenced code
  block's info string.
"""

import enum


class CodeLanguage(enum.StrEnum):
    """Programming language identified by a fenced code block's info string.

    Each member's value is the language identifier string as it appears in the
    info string of a fenced code block (e.g. the ``javascript`` in
    ```` ```javascript ````).
    """

    C = "c"
    CLOJURE = "clojure"
    COMMON_LISP = "commonlisp"
    CSS = "css"
    C_PLUS_PLUS = "c++"
    C_SHARP = "c#"
    DART = "dart"
    ELIXIR = "elixir"
    GO = "go"
    HASKELL = "haskell"
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSON = "json"
    JSON_LD = "json-ld"
    JSX = "jsx"
    JULIA = "julia"
    KOTLIN = "kotlin"
    LATEX = "latex"
    LUA = "lua"
    MARKDOWN = "markdown"
    OBJECTIVE_C = "objective-c"
    PHP = "php"
    PLAIN_TEXT = "plain text"
    PYTHON = "python"
    R = "r"
    RUBY = "ruby"
    RUST = "rust"
    SCALA = "scala"
    SHELL = "shell"
    SOLIDITY = "solidity"
    SPARQL = "sparql"
    SQL = "sql"
    SWIFT = "swift"
    TOML = "toml"
    TSX = "tsx"
    TURTLE = "turtle"
    TYPESCRIPT = "typescript"
    VB = "vb"
    VBSCRIPT = "vbscript"
    XML = "xml"
    YAML = "yaml"
