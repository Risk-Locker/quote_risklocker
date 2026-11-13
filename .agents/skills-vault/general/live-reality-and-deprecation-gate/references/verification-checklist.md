# Live Grounding & Deprecation Verification Commands

## 1. Quick Runtime Inspection (Safe Read-Only)

```powershell
# Python package versions inside repo .venv
.\.venv\Scripts\python.exe -c "import importlib.metadata as m; print({p: m.version(p) for p in ('fastapi', 'pydantic', 'sqlalchemy', 'playwright')})"

# Frontend exact installed core packages
node -e "for (const p of ['next','react','tailwindcss','@playwright/test']) { console.log(p, require('./frontend/node_modules/' + p + '/package.json').version); }"

# Scan backend for hardcoded AI model strings
Select-String -Path backend\app\**\*.py -Pattern "gemini-[0-9]"
```

## 2. Verified Context7 MCP Library IDs (`context7_context7`, Connected)

Always pass Risklocker's exact runtime-matched `libraryId` to `query-docs` (never blindly mix Next.js 16 or Tailwind v4 syntax into Next 15.5 / Tailwind 3.4):

| Stack Package | Installed Version | Verified Context7 `libraryId` | Notes |
| :--- | :--- | :--- | :--- |
| **Next.js** | `15.5.20` (`node_modules`; `package.json`: `"^15.1.3"`) | `/vercel/next.js` | App Router `middleware.ts` & async `cookies()`/`headers()` |
| **FastAPI** | `0.115.6` (`requirements.txt`) | `/websites/fastapi_tiangolo` | Confirm `lifespan` async context manager vs deprecated `@app.on_event` |
| **Pydantic** | transitive (`.venv` via `fastapi`) | `/pydantic/pydantic` | Strict `Decimal` field validation & `ConfigDict` |
| **Tailwind CSS** | `3.4.19` (`node_modules`) | `/websites/tailwindcss` (v3) | Keep `tailwind.config.*` v3 conventions + `--rl-*` CSS tokens |
| **Playwright (Python)** | `1.49.1` (`requirements.txt`) | `/microsoft/playwright-python` | Chromium A4 PDF worker (`backend/app/rendering/`) |
| **Playwright (Node)** | `1.62.1` (`package.json`) | `/microsoft/playwright` | Frontend E2E & zoom/console verification |

## 3. Upstream Deprecation Query Checklist (`search_web`)
- `"ai.google.dev" gemini models active deprecated shutdown schedule <current-year>` *(Authoritative source — community DeepWiki snippets can retain older model names!)*
- `"ui.shadcn.com" mcp cli latest changes`
- `"nextjs.org/docs" app router middleware breaking changes <major.minor>`

## 4. Daily Radar Integration
`.agents/hooks/daily_radar.py` automatically runs stale-model scanning (`gemini-2.0-*`, `gemini-2.5-*`, `gemini-3.1-flash-lite*`, `gemini-3.5-flash`), native agent frontmatter validation, rule trigger validation, stale tier/cap checks, and stub regression checks so drift surfaces automatically in `.agents/proposals/`.

