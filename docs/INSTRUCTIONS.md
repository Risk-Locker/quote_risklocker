# Owner Interaction Contract (Universal)

How the owner talks, how to interpret him, and how every interaction must run. This file is portable: copy it with `AGENTS.md` and the rest of `docs/` into any project. When the owner expresses a new preference, append it here so no agent ever needs to be told twice.

## How the Owner Talks

- He speaks casually and compactly, in plain English. He uses references, sarcasm, analogies, and hypothetical examples to point at intent — they are NOT literal requirements.
- Example: "there should be around 156 unique chats" is a reference about scale, not a request to find or reconstruct 156 logs. Do not hunt for things he did not ask for.
- If a request seems impossible, excessive, or asks you to invent history — stop, interpret intent, and ask. Never guess and never fabricate.
- He expects agents to think realistically, not mechanically.

## Interaction Rules

1. **Ask first.** Ask questions before big or ambiguous work. A wrong direction costs more than a clarifying question.
2. **Design/UX feedback** ("does this button border look okay? I don't like it") — never start changing things. Instead:
   - Analyze where and how the style is currently used across the app.
   - Check whether the project already defines a design system (`docs/DESIGN-SYSTEM.md`); if styles deviate from it, say so.
   - Research options (web + relevant skills) when the design system does not answer the question.
   - Present 6-8 concrete options with descriptions; the owner picks one or merges a few.
   - Only then execute.
3. **Issue reports** ("this flow has issues") — never jump to fixes. Understand what he said, investigate systematically (see the `systematic-debugging` skill), use your own reasoning first, then external sources if needed, then present findings and execute.
4. **Big changes** follow the same pipeline: understand -> analyze -> research -> plan -> record plan in `docs/MEMORY.md` -> get approval -> execute -> log the outcome.
5. **Never claim success without the verification chain** in AGENTS.md (pytest, tsc, build, code-map check).
6. **Update this file** whenever the owner expresses a new interaction preference — that is part of the logbook duty, not an optional chore.
