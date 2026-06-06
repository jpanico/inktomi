# Guffin PDF Templates

## Bergfink

The `.typ` and `.typst` files in this directory are the **Bergfink** Pandoc/Typst template, based on:

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

### Font Requirements

The default configuration in `base_cfg.typ` uses **Noto Sans** (body, headings, headers/footers) and **Noto Sans Mono** (code blocks). Both must be installed on the system as **static** fonts (not variable fonts — Typst does not currently support variable fonts).

On macOS, download the static variants from Google Fonts: open the family page, click *Download family*, and install only the files from the `static/` subfolder via Font Book. Variable font files are identifiable by `[wght]` or `[wdth]` in their filename — do not install those.

To avoid this requirement entirely, override the font keys in `user_cfg.typ` with fonts already present on the system (e.g. `Helvetica Neue` and `Menlo` on macOS).

### Customization

Edit `user_cfg.typ` to override any default from `base_cfg.typ`. Define a `#let user_cfg = (...)` dictionary with only the keys you want to change — they are merged on top of the defaults.

### Modifications from upstream

The following changes have been made to the stock Bergfink distribution. When updating to a newer upstream commit, these modifications must be re-applied.

#### Per-level heading size, weight, and style (`base_cfg.typ`, `default_styles.typ`)

Nine new keys were added to the `cfg` dictionary in `base_cfg.typ`:

| Key | Type | Default | Description |
|---|---|---|---|
| `h1-size` | float | `1.8` | H1 font size as a ratio of `fontsize` |
| `h2-size` | float | `1.1` | H2 font size as a ratio of `fontsize` |
| `h3-size` | float | `1.0` | H3 font size as a ratio of `fontsize` |
| `h1-weight` | string | `"bold"` | H1 font weight (e.g. `"semibold"`, `"extrabold"`, or an integer 100–900) |
| `h2-weight` | string | `"bold"` | H2 font weight |
| `h3-weight` | string | `"bold"` | H3 font weight |
| `h1-style` | string | `"normal"` | H1 font style (`"normal"`, `"italic"`, or `"oblique"`) |
| `h2-style` | string | `"normal"` | H2 font style |
| `h3-style` | string | `"normal"` | H3 font style |

The defaults reproduce Typst's built-in heading appearance, so existing PDFs are unaffected. In `default_styles.typ`, the hardcoded size ratios and the H3 `#show` rule (which upstream omits a text rule for) were replaced with rules that read from `cfg`:

```typst
#show heading.where(level: 1): set text(fontsize * cfg.h1-size, weight: cfg.h1-weight, style: cfg.h1-style)
#show heading.where(level: 2): set text(fontsize * cfg.h2-size, weight: cfg.h2-weight, style: cfg.h2-style)
#show heading.where(level: 3): set text(fontsize * cfg.h3-size, weight: cfg.h3-weight, style: cfg.h3-style)
```

These keys are overridable in `user_cfg.typ` like any other `cfg` key.

### Updating

To update to a newer upstream commit, re-copy the files from the repository above, update the commit reference in this README, and re-apply the modifications described above.
