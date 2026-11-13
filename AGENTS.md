# AGENTS.md — Project Context for AI Coding Agents

> Guide for AI agents (Claude, Cursor, Codex, etc.) working on ChimeraFlow.
> Update this file when architecture or conventions evolve.

---

## 1. Project Overview

**Name:** ChimeraFlow

**Description:** [Project description to be defined]

**Status:** Initial setup

**Languages:** [To be defined - e.g., TypeScript, Python]

---

## 2. Meta Principles

Before content, form matters:

- **Short and direct** — bullets, not prose. Agents read everything each session.
- **Negative + positive** — "don't do X -> do Y instead"
- **Explicit priority** — critical rules at the top, not buried in 50 lines
- **No redundant rules with linter/formatter** — configure ESLint/Prettier, not AGENTS.md

---

## 3. Session Init — execute in this order

1. `git fetch && git checkout dev && git merge origin/main` (if `main` advanced)
2. Read `docs/decisions/DECISIONS_LOG.md` (context of past decisions)
3. Read `docs/decisions/TECH_DEBT.md` if it exists
4. Identify impacted files BEFORE writing any code
5. If task touches > 5 files → reformulate scope before starting

---

## 4. Critical Rules (absolute, blocking)

- ❌ NEVER leave an unresolved problem at end of session (broken build, failing test, UI regression, discovered debt) — **fix in the same work cycle**, whether pre-existing, merge-related, or outside initial instruction; only exception: external blocker documented in `TECH_DEBT.md` + entry in `DECISIONS_LOG.md` if workaround
- ❌ NEVER consider a PR done with red GitHub checks (CI, lint, tests) — even if failure predates or is unrelated to the diff; unrelated failure (billing, quota, token permissions) must be explicitly reported to product owner and logged in `TECH_DEBT.md`
- ❌ NEVER store secrets in code or versioned files
- ❌ NEVER use `any` in TypeScript (use `unknown` or precise types)
- ❌ NEVER hardcode user-visible text in code — **No user-facing text** (labels, titles, descriptions, messages, placeholders, aria-labels, tooltips, error messages, formatted dates, etc.) directly in TSX/code. Use **exclusively** i18n files
- ❌ NEVER use configuration fallbacks (`process.env.X || 'default-value'`) — use helper functions that fail fast if required variables are missing

---

## 5. Git Workflow (absolute rule)

The repository has **two branches only**, locally and on `origin`:

| Branch | Role | Who writes |
|--------|------|------------|
| `main` | Production. Always deployable. | **Nobody directly**: only via PR from `dev` (merged by product owner) |
| `dev` | Integration. **All modifications are committed and pushed here.** | Developers and AI agents, directly |

- ❌ No `feat/*`, `fix/*`, `chore/*`, `docs/*` branches, or per-task/per-batch branches. A branch created by a tool (Cursor, cloud agent) is brought back to `dev` then deleted.
- ✅ Exception Dependabot: its PRs (max 5 open per ecosystem) come from `dependabot/*` branches created by GitHub, not to be created manually. A Dependabot PR merges into `dev` or closes; GitHub then deletes the branch.
- ✅ Start of session: `git fetch` → `git checkout dev` → `git merge origin/main` (if `main` advanced). Resolve conflicts on `dev`.
- ✅ Delivery: `git push origin dev`, then **one PR `dev` → `main`**. If one already exists open, new commits add to it, don't open a second.
- ✅ After PR merge: resync (`git checkout dev && git merge origin/main && git push origin dev`) before continuing.
- ❌ Never `push --force`, `rebase`, or rewrite history on `dev` or `main` without explicit product owner agreement.
- ❌ Don't delete `main` or `dev`. Don't create or delete other branches without explicit request.
- One commit = one logical intent (rules below); several coherent commits stack on `dev` until the PR.

**Commits:** Conventional Commits in **English** — `feat:`, `fix:`, `chore:`, `docs:`, `test:`

**PR:** always `dev` → `main`, squash merge, green CI, 1 review minimum. Squash title follows Conventional Commits (it becomes the message on `main`).

**Protected:** `main` (PR required, no direct push, green CI required) and `dev` (no force-push or deletion). These protections are set in GitHub: Settings → Branches.

---

## 6. Coding Conventions

### General
- **Language:** Code and comments in English, user documentation in French
- **Commits:** Conventional format (`feat:`, `fix:`, `docs:`, `chore:`, etc.)

### TypeScript / JavaScript
- Strict TypeScript mode — no `any`
- Naming: `camelCase` variables/functions, `PascalCase` components and types, `kebab-case` files
- One component = one file, named export only (no default export)
- Business logic in `lib/`, never in React components
- Centralized API calls in `lib/services/` — never `fetch()` in a component

### Python
- Follow PEP 8, type hints
- One class per file when appropriate
- Docstrings (Google style)
- No logic in `__init__.py` beyond imports

---

## 7. Configuration Management (absolute rule)

**Forbidden:**

```ts
const url = process.env.API_URL || 'http://localhost:3000'   // ❌
const secret = process.env.SECRET ?? 'dummy_secret'          // ❌
```

**Why:** This fallback turns a missing variable into apparent success.
The application starts, responds 200, logs nothing — but talks to the wrong host or uses an insecure default.

**Instead** — helper functions:

```ts
import { requireEnv, requireEnvUrl, optionalEnv } from './env-helpers'

requireEnv('SECRET', 'HMAC signature for webhooks')  // throws if missing
requireEnvUrl('API_URL', 'API service URL')          // + validates schema, removes trailing /
optionalEnv('SENTRY_DSN')                           // string | undefined
```

- **Required value** → `requireEnv` / `requireEnvUrl`. Error names the variable and its use: an operator knows what to set without reading code. Failing at startup is better than a service that responds incorrectly.
- **Optional value** → `optionalEnv`, then branch on `undefined`. Feature disables cleanly.
- **Fallback to empty string** (`|| ''`): allowed, it doesn't invent any value.

---

## 8. Internationalization (i18n)

- No string concatenation for translations ("Hello " + username)
  → use placeholders: `t('greeting', { name: username })`
- No hardcoded plural logic (if count > 1)
  → use i18n plural rules
- No hardcoded date/time formats → use `Intl.DateTimeFormat` with locale
- No icons with embedded text in the image
- Any new translation key added in FR must have its EN equivalent in the same PR

---

## 9. Security & Compliance

- No PII in URLs — POST body only
- Server-side + client-side input validation (Zod or similar)
- HTTPS/TLS in production
- No secrets in logs
- All sensitive operations require authentication
- Rate limiting on public endpoints

---

## 10. Accessibility

- All interactive elements keyboard accessible (tabIndex, visible focus)
- Images: non-empty alt (or alt="" if decorative)
- Minimum contrast: 4.5:1 (normal text), 3:1 (large text)
- No `display:none` to hide from screen readers → use aria-hidden

---

## 11. Testing

- Tests co-located with code (`*.test.ts`, `*.spec.ts`)
- Cover critical business logic
- Run: `npm test` or equivalent
- Test name: "should [result] when [condition]"
- No logic in tests (if, loop) → one test = one case
- Mocks limited to external boundaries (API, DB) — no internal mocks

---

## 12. Agent Behavior

### Before coding
- If task touches architecture or creates new pattern → ask ONE question first
- If multiple valid approaches exist → propose simplest first
- Verify what needs to change before implementing

### During
- Prefer modifying existing to creating new
- Respect file's existing style (spacing, quotes, etc.)
- Don't rewrite what isn't broken
- Comment the WHY, never the WHAT
- No TODO comments left in shipped code
- No commented-out code (use git)

### After
- **Create a commit** with session files (see section 5) before closing — unless user explicitly refuses or there are no versionable changes
- List modified files with one line of context per file
- Explicitly signal if any rule from this file had to be bypassed and why
- Don't ask for validation for trivial changes
- Verify build + tests + lint on touched areas; handle discovered failures (including pre-existing) before closing — don't limit to initial task diff

---

## 13. Anti-patterns Explicitly Forbidden

| Forbidden | Alternative |
|-----------|-------------|
| `"Connection successful"` in code | i18n files |
| `#FF5733` in code | CSS design tokens (`--color-*`) |
| `BASE_URL = "https://api.myapp.com"` | `.env` / centralized constants |
| `sleep(2000)` | `async delay(2000)` |
| `fetch("/api/users")` in component | centralized service (`lib/services/`) |
| `catch (e) {}` | logger + re-throw or explicit fallback |
| `any` in TypeScript | precise type or `unknown` |
| wildcard import `*` | named imports |
| `console.log` in production | structured logger with levels (error, warn, info) |
| PII data in URLs | POST body only |

---

## 14. Decision Log — `docs/decisions/DECISIONS_LOG.md`

The agent MUST update this file **before committing** when the session involves:
- An architectural choice (pattern, library, folder structure)
- Bypassing a rule from this AGENTS.md file
- A technical compromise (performance vs readability, etc.)
- Rejecting an alternative approach
- Any significant decision that future developers should know about

### Required entry format

```markdown
## [YYYY-MM-DD] Short decision title

**Context**: Why this choice arose (1-2 sentences)
**Decision**: What was done
**Alternatives rejected**: What was discarded and why
**Consequences**: Impact on codebase (debt, future constraints)
**AGENTS.md rule concerned**: (if applicable)
```

### Completion rules

- Entry at top of file (reverse chronological order)
- Never modify existing entry — add new one if revision needed
- If no notable decision in session → don't touch the file
- No excessive prose: 5 lines max per section

---

## 15. Tech Debt — `docs/decisions/TECH_DEBT.md`

The agent must add an entry when it:
- Takes a shortcut constrained by time or scope
- Identifies an existing problem outside task scope
- Bypasses an AGENTS.md rule
- Detects an issue that cannot be fixed in current cycle

### Format
- [YYYY-MM-DD] Problem description | Estimated impact (low/med/high) | Concerned file(s)

The agent fixes debt it identifies during the session (see critical rule §4). Reserve `TECH_DEBT.md` for blockers not liftable in current cycle.

---

## 16. Strict Scope

- Modify ONLY files necessary for the described task
- Don't reformat untouched files
- Don't add dependencies without explicit approval
- Don't create new files if an existing file suffices
- Don't launch tests unless explicitly requested **by the user** — but if agent launches tests/build (Cloud session, fix, PR), all failures must be resolved before closing (§4)
- Don't modify existing tests unless task specifies it

---

## 17. Useful Resources

- **[README.md](./README.md)** — Project presentation and quick start
- **[Roadmap.md](./Roadmap.md)** — Feature roadmap
- **[docs/README.md](./docs/README.md)** — Documentation index
- **[docs/decisions/DECISIONS_LOG.md](./docs/decisions/DECISIONS_LOG.md)** — Architectural decisions log
- **[docs/decisions/TECH_DEBT.md](./docs/decisions/TECH_DEBT.md)** — Identified technical debt

---

## 18. Environment Variables

[To be defined based on project needs]

**Required:**
- `NODE_ENV` — development | production | test

**Optional:**
- `PORT` — server port (default: 3000)

---

_This document is the single source of truth for development standards. Keep it updated as the project evolves._
