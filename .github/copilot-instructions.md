# Copilot Instructions

## Code Review

When reviewing code changes (via `/review` or when asked to review):

- Run **4 independent checks** in parallel: (1) conventions compliance, (2) bug detection, (3) git blame context for intent, (4) a second conventions pass for redundancy
- Score every issue 0–100 for confidence. Only surface issues with confidence ≥ 80
- Filter out: pre-existing issues not introduced in this change, linter-catchable issues, pedantic nitpicks, and issues that look wrong but aren't
- Format each finding with a clear description and a direct link to the file + line range
- If no issues score ≥ 80, say so explicitly — don't pad the review

**What matters in this repo:**
- Plugin protocol compliance — new data providers must implement `DataProvider`, strategies must implement `generate_signals()`
- Type safety — no new `# type: ignore` comments without justification
- Specific exception handling — no bare `except Exception` in engine, loaders, or data providers
- Test coverage — hand-written fakes, not mocks; new public functions need tests

---

## Explanatory Output Style

When writing or modifying code, add a brief insight block before the implementation when the choice is non-obvious:

```
★ Insight ────────────────────────────────────────
[2–3 points explaining: what pattern was used, why it fits this codebase,
and any tradeoff worth knowing]
──────────────────────────────────────────────────
```

Focus on:
- Why this approach over the obvious alternative (e.g. "INSERT OR REPLACE instead of check-then-insert — idempotent re-runs")
- How it fits existing patterns in this repo (e.g. "matches the Protocol-based plugin design in `plugins/data/base.py`")
- Tradeoffs that aren't obvious from the code alone

Skip the insight block for trivial changes (typos, renaming, formatting).

---

## Frontend Design

This repo's dashboard is in `dashboard/`. When working on frontend:

- **Match the existing aesthetic** — the dashboard uses TanStack Query, clean sidebar nav, and color-coded signal tables. New components should feel native to it.
- **Avoid generic AI aesthetics** — no purple gradients, no Inter/Roboto, no cookie-cutter card layouts
- **Bold choices over safe defaults** — commit to a clear visual direction and execute it with precision
- **Typography** — use distinctive font pairings; avoid system fonts for display text
- **Motion** — CSS-only animations preferred; one well-orchestrated reveal beats scattered micro-interactions
- **Spatial composition** — generous negative space, asymmetry, and deliberate density are all valid; pick one and commit
- **Empty states and feedback** — every page needs a loading state, an empty state, and success/error feedback. No bare "Loading..." text.
- **Destructive actions** — always require confirmation before delete

---

## Security Guidance

Flag and block the following patterns when writing or editing code in this repo:

**Python (backend):**
- `os.system(` — use `subprocess.run([...])` with a list, never a shell string with user input
- `pickle` — use JSON or Pydantic serialization instead
- `eval(` — flag always; only acceptable with fully static, trusted input
- Bare SQL string formatting — use parameterized queries (`?` placeholders with SQLite)
- Hardcoded secrets or API keys in source — use `config.toml` (gitignored) or environment variables

**JavaScript/TypeScript (dashboard):**
- `dangerouslySetInnerHTML` — require DOMPurify sanitization if used
- `.innerHTML =` — flag if assigned from any non-static value
- `eval(` — flag always
- `document.write` — flag always; use DOM methods instead

**GitHub Actions (if any `.github/workflows/` files):**
- Never interpolate `${{ github.event.*.body }}`, `${{ github.event.*.title }}`, or `${{ github.head_ref }}` directly into `run:` commands
- Always assign untrusted inputs to `env:` variables first, then reference `$ENV_VAR` in the shell

When flagging a security issue, explain the specific risk and provide the safe alternative inline — don't just say "this is dangerous."
