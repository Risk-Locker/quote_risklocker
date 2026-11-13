# Risklocker UI Plugin (`risklocker-ui`)

Repo-local Antigravity plugin providing zero-key access to the official **`shadcn@latest mcp`** server alongside Risklocker `--rl-*` Enterprise Fintech UI rules.

- **Windows Default:** Uses `"command": "cmd", "args": ["/c", "npx", "-y", "shadcn@latest", "mcp"]` so Antigravity resolves the Node `.cmd` shim reliably on Windows.
- **macOS / Linux Teammates:** If running this repo on POSIX, replace `"command": "cmd"` and `"/c"` in a local override with `"command": "npx", "args": ["-y", "shadcn@latest", "mcp"]`.
- **Manage in Antigravity UI:** Open `[risklocker-ui](customization://risklocker-ui)` in Customizations to inspect or toggle.

