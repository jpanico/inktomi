---
name: feedback_venv_pytest
description: Use .venv/bin/pytest directly instead of chaining source + pytest with &&
metadata:
  type: feedback
---

Always invoke pytest and other venv tools via their direct `.venv/bin/` path rather than chaining `source .venv/bin/activate && pytest ...`.

**Why:** Chaining with `&&` violates the CLAUDE.md "no `&&` in Bash tool calls" convention and triggers repeated permission prompts because the full command starts with `source`, not `pytest`. The project's `.claude/settings.local.json` already has `Bash(.venv/bin/*)` in the allow list, so `.venv/bin/pytest`, `.venv/bin/pyright`, `.venv/bin/black`, etc. all run without prompts.

**How to apply:** Replace every `source .venv/bin/activate && <tool>` pattern with `.venv/bin/<tool>`. Examples:
- `source .venv/bin/activate && pytest` → `.venv/bin/pytest`
- `source .venv/bin/activate && pyright` → `.venv/bin/pyright`
- `source .venv/bin/activate && black` → `.venv/bin/black`
- `source .venv/bin/activate && python scripts/foo.py` → `.venv/bin/python scripts/foo.py`
