# Guffin PDF Templates

## Bergfink

The `.typ` and `.typst` files in this directory are the **Bergfink** Pandoc/Typst template, copied verbatim from:

- **Repository**: [andyburri/pandoc-typst-template](https://github.com/andyburri/pandoc-typst-template)
- **Commit**: [`8abcbc1`](https://github.com/andyburri/pandoc-typst-template/commit/8abcbc177ad2e942ca1cd5ff41163205ac91a62b) (2026-05-18)

### Why Bergfink

- **Pandoc-native**: uses Pandoc's `$variable$` template syntax throughout, including `$body$`, so it slots directly into the `pypandoc.convert_text` call in `pdf_rendering.py` via `--template`.
- **Typst-based**: works with `--pdf-engine=typst`, consistent with the rest of the PDF pipeline.
- **Richly configurable**: exposes font, margins, paper size, title page, TOC, headers/footers, and more — all controllable via Pandoc `-V` variables or a `user_cfg.typ` override file, without editing the template itself.
- **No LaTeX dependency**: unlike the popular Eisvogel template (which requires a full LaTeX installation), Bergfink only needs Typst — already a project requirement.

### Files

| File | Purpose |
|---|---|
| `bergfink.typst` | Main template entry point — Pandoc injects variables and `$body$` here |
| `base_cfg.typ` | Default configuration values (font, margins, colors, etc.) |
| `user_cfg.typ` | Project-level overrides — edit this file to customize styling |
| `default_styles.typ` | Typst `#set` and `#show` rules that apply the config to the document |
| `titlepage.typ` | Title page layout |
| `abstract.typ` | Abstract and acknowledgements page layout |
| `toc.typ` | Table of contents layout |
| `yamltable.typ` | Helper for rendering YAML-defined tables |

### Customization

Edit `user_cfg.typ` to override any default from `base_cfg.typ`. Define a `#let user_cfg = (...)` dictionary with only the keys you want to change — they are merged on top of the defaults. Do not edit `base_cfg.typ` or `default_styles.typ` directly, as those track the upstream template.

### Updating

To update to a newer upstream commit, re-copy the files from the repository above and update the commit reference in this README.
