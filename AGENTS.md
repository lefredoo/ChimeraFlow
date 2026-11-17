# AGENTS.md — Project Context for AI Coding Agents

> Guide for AI agents (Claude, Cursor, Codex, etc.) working on ChimeraFlow.
> Update this file when architecture or conventions evolve.

---

## 1. Project Overview

**Name:** ChimeraFlow

**Description:** ChimeraFlow stitches the Excel sheets, Access databases and WhatsApp groups that small businesses actually run on into one correlated view. Rules are written in plain French or English. Built for Kiroween 2026 Hackathon.

**Status:** Active development (Hackathon: Oct 30 - Dec 4, 2026)

**Category:** Frankenstein (Chimera of technologies - Excel + Access + WhatsApp)

**Languages:** TypeScript (Next.js frontend), Python (FastAPI backend)

**Target Audience:** Small and medium businesses in Africa that operate on Excel, Access, and WhatsApp

**Bonus Prizes:** Best Startup Project (LinguaSolution LLC), Blog, Social

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

## 18. Architecture & Stack

**Frontend:**
- Next.js 15+ (App Router) on Vercel
- TypeScript strict mode
- Context API for state management
- Tailwind CSS v4 with glassmorphism design
- IBM Plex Sans (UI), IBM Plex Serif (display), IBM Plex Mono (code)

**Backend:**
- FastAPI (Python 3.11+) on VPS Hetzner (Dokploy/Traefik)
- SQLAlchemy ORM
- Redis for rate limiting and caching
- LiteLLM for NL→Rule conversion (budget capped)
- 4 MCP servers in one container (Excel, Access, WhatsApp, Mobile Money) (target architecture; not yet in docker-compose.yml)

**Data Sources:**
- Excel (.xlsx) - Supplier price lists
- Access (.mdb) - Legacy stock databases
- WhatsApp exports (.txt) - Customer orders
- Mobile Money CSV - Payment confirmations

**Deployment:**
- Frontend: Vercel (HTTPS, no secrets)
- Backend: VPS Hetzner (Docker Compose, Traefik TLS, mem_limit per container)
- Volume `/data` read-only: synthetic data files

**Key Constraints:**
- 100% synthetic data (public repo and demo)
- NO execution of generated code (JSON declarative rules only)
- LLM budget capped (~5 USD / 3,300 FCFA)
- Rate limiting per IP on rule creation
- All source text sanitized before display (XSS prevention)

---

## 19. Unified Record Schema

Every data source is normalized to this schema:

```json
{
  "id": "wa-0412",
  "source": "whatsapp",
  "source_ref": "chat.txt#L412",
  "timestamp": "2026-11-02T09:14:00+01:00",
  "lang": "fr",
  "entities": [
    {
      "type": "product",
      "raw": "ciment 50 kg",
      "norm": "ciment-50kg"
    }
  ],
  "payload": {
    "author": "Client A",
    "text": "..."
  }
}
```

**Normalization strategy:** Hybrid (manual rules + fuzzy matching)
- Case insensitive
- Accent normalization
- Whitespace handling
- FR/EN synonym mapping

**Supported languages:** French (FR), English (EN)

---

## 20. Declarative Rule Schema

Rules are JSON, never executed code:

```json
{
  "id": "r_low_stock",
  "version": 1,
  "natural_language": "...",
  "trigger": {
    "source": "whatsapp",
    "entity": "product",
    "where": []
  },
  "joins": [
    {
      "source": "access",
      "table": "Articles",
      "on": {"entity": "product", "field": "designation"},
      "where": [{"field": "qty_stock", "op": "lt", "value": 10}]
    },
    {
      "source": "excel",
      "sheet": "Tarifs",
      "on": {"entity": "product", "field": "Produit"},
      "where": [{"field": "Prix_Unitaire", "op": "gt", "ref": "access.prix_achat", "tolerance_pct": 10}]
    }
  ],
  "window_seconds": 604800,
  "emit": {
    "severity": "warning",
    "template": "{product}: stock {access.qty_stock}, prix {excel.Prix_Unitaire} FCFA"
  }
}
```

**Allowed operators:** `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`

**Closed extensions (still data, never code):**
- `trigger.where`: conditions on the triggering record, literal `value` only, same operators.
- `ref` + `tolerance_pct`: a condition's right side can be `"<source>.<field>"` of the trigger or of an earlier join. With `tolerance_pct` (0–1000, operators `lt|lte|gt|gte`) it compares the relative gap `|field − ref| / |ref|` in percent. No free expressions. `ref` is not allowed in `trigger.where` or with `in`; `value` and `ref` are exclusive.
- `on.field: "entities"`: a join compares the trigger entity with every entity of the joined record (e.g. the products of a WhatsApp message).
- Every column named by a rule (`field`, `on.field`, `ref`, template placeholders) must exist in its source (`backend/schemas/sources.py`); templates never expose `momo.phone` or `momo.customer_name`.
- Bounds: ≤ 10 conditions per list, `value` ≤ 200 characters or ≤ 50 scalars, `template` ≤ 500 characters, `on.field` required.
- Name matching: exact, synonym, typo (long words only) or token containment (`"tuyau PVC"` in `"Tuyau PVC Ø 32mm (barre 6m)"`); different numbers never match, except a number-less name contained in a numbered one. See `.kiro/specs/chimeraflow-backend/design.md` §4.

---

## 21. Kiro Usage

**Specs (`.kiro/specs/`):**
- Kiro spec folder format: one folder per spec, each with `requirements.md` (EARS, French), `design.md`, `tasks.md`
- `chimeraflow-backend/` — `requirements.md`, `design.md` (architecture as implemented and correctness properties P1–P6), `tasks.md` (checklist by phase P0–P5); detail documents: `connectors-spec.md` (MCP server contracts), `rule-engine-spec.md` (Rule DSL and interpreter), `api-spec.md` (FastAPI endpoints: method, path, body, response, error codes)
- `chimeraflow-ui/` — `requirements.md`, `design.md` (dashboard and components), `tasks.md`
- `tasks.md` is ticked only when verified in the repo

**Hooks (`.kiro/hooks/`):**
- `parser-test.json` — On parser save: run contract tests + PBT
- `spec-update-reminder.json` — On spec modification: reminder to update tasks.md
- `rule-validate.json` — On rule creation: validate schema

**Property-Based Testing (Hypothesis):**
- P1: Provenance conservation (no fabricated records)
- P2: Normalization idempotence (`norm(norm(x)) == norm(x)`)
- P3: Parser round-trip (parse ∘ export = identity)
- P4: Determinism (same inputs → same output)
- P5: Window monotonicity (wider window ⊇ narrower window)
- P6: No fabrication (all emitted values exist in sources)

**MCP Servers (`.kiro/settings/mcp.json`, local and git-ignored, absolute paths; template `backend/mcp_servers/kiro-mcp.json`, per-machine step in `backend/README.md`):** — one stdio server per source, `python backend/mcp_main.py --source <name>`
- `chimeraflow-excel`
- `chimeraflow-access`
- `chimeraflow-whatsapp`
- `chimeraflow-momo` (Mobile Money connector)
- Tools: `fetch_records(limit)`, `health_check()` (read-only). Settings: `DATA_DIR`, `ACCESS_READER` (access only), no secrets

---

## 22. Environment Variables

Read by `backend/config.py` (`docker-compose.yml` passes them to the containers; production values come from Doppler).
A missing required variable stops the process at startup. There is no `.env.example`.

**Production: the only variable kept locally is `DOPPLER_TOKEN` (read by the Doppler CLI, not by the backend).**

**Required:**
- `CORS_ORIGINS` — Comma-separated allowed origins (whitelist)
- `DATA_DIR` — Directory of the synthetic data files (`/data` in Docker)
- `DATABASE_URL` — SQLAlchemy URL, required at import. `postgresql://` is rewritten to psycopg 3 (Neon in production)
- `REDIS_URL` — Redis for rate limiting and the LLM spend counter. Not required when `BACKEND_NODE_ENV=test`
- `ACCESS_READER` — `mdbtools` (Docker/production) | `access-parser` (local Windows). Any other value stops startup, no fallback
- `RATE_LIMIT_PER_IP` — Mutation requests allowed per client IP per window (integer ≥ 1)
- `RATE_LIMIT_WINDOW_SECONDS` — Length of the rate limit window in seconds (integer ≥ 1)
- `AUTH_TOKEN_SECRET` — Secret signing the access tokens (HMAC-SHA256), 32 bytes or more, random. Changing it invalidates every session
- `DEMO_LOGIN_EMAIL` — Email of the single demo account
- `DEMO_LOGIN_PASSWORD_HASH` — scrypt hash of its password (`python -m auth.hash_password`, password on stdin). A malformed hash stops startup
- `REDIS_PASSWORD` — Required by `docker-compose.yml` only: Redis `requirepass`, embedded in `REDIS_URL` by compose. Must be URL-safe (e.g. `openssl rand -hex 24`)

**Optional:**
- `BACKEND_NODE_ENV` — `development` | `production` | `test` (`test` uses in-memory limiter storage and makes `REDIS_URL` optional)
- `BACKEND_PORT` — Port used by `python main.py` (uvicorn default when unset; compose sets 8000)
- `BACKEND_LOG_LEVEL` — Logging level (root logger untouched when unset)
- `RATE_LIMIT_NL_PER_IP` — Limit of `POST /api/v1/rules/from-text` per IP per window. When unset: `RATE_LIMIT_PER_IP // 5`, at least 1
- `RATE_LIMIT_LOGIN_PER_IP` — Limit of `POST /api/v1/auth/login` per IP per window. When unset: `RATE_LIMIT_PER_IP // 2`, at least 3
- `TRUSTED_PROXIES` — Comma-separated IPs or CIDR networks of trusted reverse proxies (Traefik). `X-Forwarded-For` is read only from them. When unset, the TCP peer is the client
- `CF_EMAIL_ACCOUNT_ID`, `CF_EMAIL_API_TOKEN`, `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO` — E-mail digest of new `warning`/`error` correlations after each execution, sent through the Cloudflare Email Service REST API (`POST /accounts/{id}/email/sending/send`; success = HTTP 2xx, `success: true` and at least one recipient in `result.delivered` or `result.queued`; a `permanent_bounces`-only result is a definitive failure, because Cloudflare answers 200 and `success: true` even when every recipient bounced). Enabled only when all four are set. `CF_EMAIL_ACCOUNT_ID` is the 32-hex Cloudflare account id; `CF_EMAIL_API_TOKEN` is a token with the "Email Sending: Edit" permission only. `ALERT_EMAIL_FROM` is an address or `Name <address>` on a sending domain onboarded in Cloudflare (e.g. `ChimeraFlow <notifications@mail.linguasolution.com>`); `ALERT_EMAIL_TO` is 1 to 5 comma-separated addresses. Malformed values stop startup (never echoed)
- `ALERT_EMAIL_COOLDOWN_SECONDS` — Minimum delay between two alert e-mails (integer ≥ 60), enforced globally in Redis (`SET NX EX`, key `chimeraflow:alerts:cooldown`). **Required** when the four e-mail variables above are set (startup stops otherwise, no fallback); ignored when the e-mail alert is disabled. Without Redis, or when Redis fails, no e-mail is sent
- `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_BUDGET_USD` — NL→rule conversion. Enabled only when all four are set (otherwise `503 nl_feature_disabled`). `LITELLM_BUDGET_USD` is the global cap in USD, must be a finite number greater than 0; `LITELLM_MODEL` is the bare model alias defined on the LiteLLM proxy (e.g. `deepseek-v4.1-flash-group`), no provider prefix: the client sends it with `custom_llm_provider="openai"` to `LITELLM_BASE_URL`. A legacy leading `openai/` is stripped once. Transient provider errors (5xx, connection, timeout) are retried up to twice with a 0.5 s then 1.5 s backoff (jitter ±25 %), within 45 s for the whole request; 4xx errors are never retried
- `LITELLM_FALLBACK_MODEL` — Optional bare proxy alias (same form as `LITELLM_MODEL`) used by the last retry after transient provider errors, e.g. `glm-4.7-flash-bedrock`. Unset or empty: every retry uses `LITELLM_MODEL`. Not part of the four variables that enable the feature

**Frontend (required at `next build`, read by `lib/config.ts` and `lib/demo-credentials.ts`):**
- `NEXT_PUBLIC_API_URL` — Backend API base URL
- `NEXT_PUBLIC_DEMO_LOGIN_EMAIL`, `NEXT_PUBLIC_DEMO_LOGIN_PASSWORD` — Demo account displayed on `/login`. Public by design (they ship in the client bundle): never a real credential, same values as `DEMO_LOGIN_EMAIL` and the password behind `DEMO_LOGIN_PASSWORD_HASH`

---

_This document is the single source of truth for development standards. Keep it updated as the project evolves._
