# 21st.dev Opt-In UI Plugin Rules

1. Never use 21st.dev components verbatim with neon gradients, marketing hero fluff, or random hex colors inside Risklocker's operational workspaces (`comparison`, `insights`, `sessions`, `builder`, `upload`).
2. Strip any borrowed layout down to structure & keyboard mechanics first, then re-theme strictly to `docs/architecture/DESIGN-SYSTEM.md` `--rl-*` tokens (`#f5f5f7`, `#ffffff`, `#1b1717`, `#ed1c24`, `8px`/`6px` radii).
3. Respect `<600` line UI component slice limits (`Rule 02`) and avoid installing extra UI icon/animation dependencies without evaluating against `@phosphor-icons/react`, `@radix-ui/*`, and `framer-motion` already in `frontend/package.json`.

